import os
import re
import logging
from typing import List, Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException

from .providers import GROQ, PROVIDERS, build_llm, is_valid_key, redact_keys

logger = logging.getLogger(__name__)

# Fallback model used when the selected model is not found on Groq
_FALLBACK_MODEL = "openai/gpt-oss-120b"

# Models known to return <think>…</think> reasoning blocks (strip them always)
_CLOSED_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE)
_STRAY_THINK_RE = re.compile(r"</think>", re.IGNORECASE)


def _strip_think(text: str) -> str:
    """
    Remove <think>…</think> reasoning blocks from any LLM output.
    Handles:
    - Closed tags: <think>...</think>
    - Unclosed tags: <think>... (strips <think> and everything after)
    - Stray closing tags: </think>
    """
    if not text:
        return ""
    # 1. Remove closed <think>...</think> blocks
    cleaned = _CLOSED_THINK_RE.sub("", text)
    # 2. Remove unclosed <think> and everything after it
    cleaned = _UNCLOSED_THINK_RE.sub("", cleaned)
    # 3. Remove stray </think> tags
    cleaned = _STRAY_THINK_RE.sub("", cleaned)
    return cleaned.strip()


def _clean_email_markdown(text: str) -> str:
    """
    Remove leftover markdown asterisks (**bold**, *italic*), bullets (* or -),
    and markdown headings (#) from email text to guarantee clean plain text.
    """
    # Remove asterisks (e.g. **bold**, *bullet*, etc.)
    cleaned = text.replace("*", "")
    # Remove markdown heading hashes at beginning of lines (e.g. ### Subject -> Subject)
    cleaned = re.sub(r"(?m)^[ \t]*#+[ \t]*", "", cleaned)
    # Remove leftover bullet markers at beginning of lines (- or +)
    cleaned = re.sub(r"(?m)^[ \t]*[-+][ \t]+", "", cleaned)
    return cleaned.strip()


def _is_model_not_found(exc: Exception) -> bool:
    """Return True when the exception indicates the model ID is unknown."""
    msg = str(exc).lower()
    return any(k in msg for k in ("model not found", "does not exist", "no such model",
                                   "invalid model", "404", "not_found"))


def _clean_error_message(exc: Exception) -> str:
    """
    Sanitize exception message to ensure no API key, bearer tokens, or headers are included.
    """
    msg = redact_keys(str(exc))
    return f"{type(exc).__name__}: {msg}"


class Chain:
    last_error: Optional[str] = None
    fallback_notice: Optional[str] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "openai/gpt-oss-120b",
        temperature: float = 0.2,
        provider: str = GROQ
    ):
        self.provider = provider if provider in PROVIDERS else GROQ
        raw_key = api_key if api_key is not None else (
            os.getenv("GROQ_API_KEY", "") if self.provider == GROQ else ""
        )
        self.api_key = str(raw_key).strip()
        self.model_name = model_name
        self.temperature = temperature
        self.last_error = None          # item 1
        self.fallback_notice = None     # item 4 — surface in UI

        # No usable key for the chosen provider -> built-in templates only
        self.is_demo_mode = not is_valid_key(self.provider, self.api_key)

        self.llm = None
        if not self.is_demo_mode:
            try:
                self.llm = build_llm(self.provider, self.api_key, self.model_name, self.temperature)
            except Exception as exc:
                # item 1 — record error type + message, never the key
                self.last_error = _clean_error_message(exc)
                logger.warning("Chain init failed — %s", self.last_error)
                self.is_demo_mode = True

    # ------------------------------------------------------------------
    # Internal: invoke LLM with automatic model-not-found retry (item 4)
    # ------------------------------------------------------------------
    def _invoke_with_fallback(self, runnable, inputs: dict) -> Any:
        """
        Invoke a LangChain runnable. If the call fails because the model is not
        found, rebuild with openai/gpt-oss-120b and retry once.
        If every fallback attempt fails, raises a RuntimeError naming ALL models tried.
        """
        models_tried = [self.model_name]
        try:
            return runnable.invoke(inputs)
        except Exception as exc:
            if self.provider == GROQ and _is_model_not_found(exc) and self.model_name != _FALLBACK_MODEL:
                models_tried.append(_FALLBACK_MODEL)
                notice = (
                    f"Model **{self.model_name}** was not found on Groq. "
                    f"Retrying with **{_FALLBACK_MODEL}**."
                )
                self.fallback_notice = notice
                logger.warning("Model not found (%s), retrying with %s", self.model_name, _FALLBACK_MODEL)
                try:
                    fallback_llm = ChatGroq(
                        temperature=self.temperature,
                        groq_api_key=self.api_key,
                        model_name=_FALLBACK_MODEL
                    )
                    prompt_part = runnable.first if hasattr(runnable, "first") else None
                    if prompt_part is not None:
                        return (prompt_part | fallback_llm).invoke(inputs)
                    return fallback_llm.invoke(inputs)
                except Exception as fallback_exc:
                    err_clean = _clean_error_message(fallback_exc)
                    models_str = ", ".join(models_tried)
                    raise RuntimeError(f"Tried {models_str}: {err_clean}") from fallback_exc
            err_clean = _clean_error_message(exc)
            models_str = ", ".join(models_tried)
            raise RuntimeError(f"Tried {models_str}: {err_clean}") from exc

    def extract_jobs(self, cleaned_text: str) -> List[Dict[str, Any]]:
        """
        Extracts job postings from text into a list of job dicts.
        Uses Groq LLM if active, otherwise uses intelligent heuristic extraction.
        """
        self.last_error = None
        self.fallback_notice = None

        if not self.is_demo_mode and self.llm:
            try:
                prompt_extract = PromptTemplate.from_template(
                    """
                    ### SCRAPED / PROVIDED JOB TEXT:
                    {cleaned_text}

                    ### INSTRUCTION:
                    The text above is from a company's career page or job posting.
                    Extract all job postings mentioned and return them strictly as a JSON array of objects.
                    Each object must contain the following keys:
                    - "role": Job title / role name
                    - "experience": Required years or level of experience
                    - "skills": List of required or preferred skills/technologies (array of strings)
                    - "description": Concise summary of what the role entails

                    Return ONLY valid JSON list: `[{{...}}]`. No markdown ticks, no preamble.
                    ### VALID JSON:
                    """
                )
                chain_extract = prompt_extract | self.llm
                res = self._invoke_with_fallback(chain_extract, {"cleaned_text": cleaned_text})
                raw = _strip_think(res.content)        # item 5
                if not raw:
                    raise ValueError("Model output was empty or contained only reasoning blocks after stripping <think> tags.")
                json_parser = JsonOutputParser()
                parsed = json_parser.parse(raw)
                if isinstance(parsed, dict):
                    return [parsed]
                elif isinstance(parsed, list):
                    return parsed
            except Exception as exc:
                # item 1 + 3 — store error for UI display
                self.last_error = _clean_error_message(exc)
                logger.warning("AI extraction failed — %s", self.last_error)

        # Built-in Heuristic Extraction
        detected_skills = []
        common_skills = [
            "Python", "Java", "Machine Learning", "AI", "React", "Node.js", "AWS", "Cloud",
            "DevOps", "Docker", "Kubernetes", "Django", "FastAPI", "SQL", "PostgreSQL",
            "MongoDB", "TypeScript", "Angular", "Vue", "Go", "Golang", "C++", "PyTorch", "TensorFlow"
        ]
        text_lower = cleaned_text.lower()
        for skill in common_skills:
            if re.search(rf"\b{re.escape(skill.lower())}\b", text_lower):
                detected_skills.append(skill)

        # Estimate role
        role_match = re.search(
            r"(?:for|role|title|position|hiring)\s+([A-Za-z\s/]{3,35}"
            r"(?:Engineer|Developer|Architect|Scientist|Specialist|Manager))",
            cleaned_text, re.IGNORECASE
        )
        role = role_match.group(1).strip() if role_match else "Software & AI Specialist"

        # Estimate experience
        exp_match = re.search(
            r"(\d+\+?\s*(?:-\s*\d+)?\s*(?:years|yrs)(?:\s+of)?\s+experience)",
            cleaned_text, re.IGNORECASE
        )
        experience = exp_match.group(1).strip() if exp_match else "2+ years of relevant experience"

        return [{
            "role": role,
            "experience": experience,
            "skills": detected_skills if detected_skills else ["Python", "Machine Learning", "Cloud Infrastructure"],
            "description": cleaned_text[:350] + ("..." if len(cleaned_text) > 350 else "")
        }]

    def write_mail(
        self,
        job: Dict[str, Any],
        links: List[Dict[str, str]],
        sender_name: str = "",
        company_name: str = "",
        sender_role: str = "Business Development Executive",
        tone: str = "Professional & Persuasive",
        max_words: int = 150
    ) -> str:
        """
        Generates a personalized cold email tailored to the job description and portfolio links.
        Supports max_words length options: Short (100), Standard (150), Full (300).
        """
        self.last_error = None
        self.fallback_notice = None

        role = job.get("role", "Software Role")
        skills = job.get("skills", [])
        desc = job.get("description", "")

        # For Full length, allow up to 3 links; for Short/Standard, at most 1 link
        link_limit = 3 if max_words >= 300 else 1
        filtered_links = links[:link_limit] if links else []
        para_guidance = (
            "Format: a 'Subject:' line, a blank line, then up to 4 short paragraphs, then a sign-off."
            if max_words >= 300
            else "Format: a 'Subject:' line, a blank line, then 3 short paragraphs, then a sign-off."
        )
        link_guidance = (
            f"Mention up to {link_limit} portfolio link(s) from {filtered_links}."
            if filtered_links
            else "No portfolio links available."
        )

        if not self.is_demo_mode and self.llm:
            try:
                prompt_email = PromptTemplate.from_template(
                    """
                    ### JOB DETAILS:
                    {job_details}

                    ### SENDER IDENTITY:
                    - Name: {sender_name}
                    - Role: {sender_role}
                    - Company: {company_name}
                    - Tone: {tone}

                    ### RELEVANT PORTFOLIO LINKS:
                    {link_list}

                    ### RULES:
                    - Output plain text only. No markdown, no asterisks, no bullet lists, no bold.
                    - {para_guidance}
                    - Maximum {max_words} words.
                    - One clear call to action.
                    - Use only the provided portfolio links. Never invent clients, results or numbers.
                    - {link_guidance} Incorporate in plain text sentences without bullet points.
                    - No preamble, no conversational intro, no commentary.

                    ### INSTRUCTION:
                    You are {sender_name}, working as {sender_role} at {company_name}.
                    {company_name} is an elite AI & software consulting firm.
                    Write a high-converting cold email to the hiring manager for {job_role}.
                    Tone: {tone}.

                    ### COLD EMAIL:
                    """
                )
                chain_email = prompt_email | self.llm
                res = self._invoke_with_fallback(chain_email, {
                    "job_details": str(job),
                    "job_role": role,
                    "sender_name": sender_name,
                    "company_name": company_name,
                    "sender_role": sender_role,
                    "tone": tone,
                    "link_list": str(filtered_links),
                    "max_words": max_words,
                    "para_guidance": para_guidance,
                    "link_guidance": link_guidance
                })
                raw = _strip_think(res.content).strip()
                cleaned_mail = _clean_email_markdown(raw)
                if not cleaned_mail:
                    raise ValueError("Model output was empty or contained only reasoning blocks after stripping <think> tags.")
                return cleaned_mail
            except Exception as exc:
                # item 1 + 3
                self.last_error = _clean_error_message(exc)
                logger.warning("AI email generation failed — %s", self.last_error)

        # Built-in High-Converting Cold Email Engine
        skills_formatted = ", ".join(skills[:3]) if skills else "modern software engineering and AI architectures"
        links_text = ""
        if filtered_links:
            links_text = f"\nYou can review our relevant proof of work here: {filtered_links[0].get('links', '')}\n"

        email = f"""Subject: Accelerating Your {role} Roadmap – {company_name} Capability Showcase

Dear Hiring Team,

I noticed your open position for {role} and the emphasis on {skills_formatted}.

At {company_name}, we specialize in augmenting tech enterprises with dedicated engineers and delivery teams that integrate immediately into active codebases—reducing onboarding overhead and accelerating time-to-market.
{links_text}
Would you be open to a brief 10-minute exploratory chat this Thursday to see if our capabilities align with your sprint goals?

Warm regards,

{sender_name}
{sender_role} | {company_name}"""
        return _clean_email_markdown(email)

    def chat_response(
        self,
        messages: List[Dict[str, str]],
        portfolio_context: Optional[str] = None,
        user_profile: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Handles conversational chatbot requests.
        Sends only the last 12 messages to the model (item 6).
        """
        self.last_error = None
        self.fallback_notice = None

        last_user_query = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_query = m.get("content", "")
                break

        if not self.is_demo_mode and self.llm:
            try:
                profile_str = ""
                if user_profile:
                    profile_str = (
                        f"User Profile: Name: {user_profile.get('name')}, "
                        f"Company: {user_profile.get('company')}, "
                        f"Role: {user_profile.get('role')}."
                    )

                system_prompt = f"""You are the CareerReach AI Assistant — an expert AI advisor in B2B sales outreach, technical recruiting, and cold email strategies.
{profile_str}

Portfolio database context:
{portfolio_context if portfolio_context else "The user has not added any portfolio items yet. Do not invent case studies, clients, results or links; if asked for matching case studies, tell them to add items in the Portfolio Vector Store tab (upload a CSV or add an item) or set their portfolio URL in the sidebar."}

Provide high-value, crisp, actionable advice with markdown formatting.
"""
                # item 6 — cap history to last 12 messages before prepending system
                recent_messages = messages[-12:]
                formatted_messages = [{"role": "system", "content": system_prompt}]
                for msg in recent_messages:
                    formatted_messages.append({"role": msg["role"], "content": msg["content"]})

                res = self._invoke_with_fallback(self.llm, formatted_messages)
                stripped_chat = _strip_think(res.content).strip()  # item 5
                if not stripped_chat:
                    raise ValueError("Model output was empty or contained only reasoning blocks after stripping <think> tags.")
                return stripped_chat
            except Exception as exc:
                # item 1 + 3
                self.last_error = _clean_error_message(exc)
                logger.warning("AI chat failed — %s", self.last_error)

        # Built-in Conversational Assistant Engine
        q_lower = last_user_query.lower()

        if "subject" in q_lower:
            return """### 🎯 5 High-Converting Cold Email Subject Lines:

1. **Quick question regarding your [Target Role] search** *(Open rate: ~58%)*
2. **Resource on accelerating your [Specific Skill] roadmap**
3. **Idea for [Target Company]'s current engineering sprint**
4. **Relevant case study: Scaling [Techstack] architectures**
5. **[First Name] — 10 min chat about augmenting your [Role] pipeline?**

💡 *Pro Tip:* Keep subject lines under 7 words and avoid hype words like "Revolutionary" or "Free".
"""
        elif "follow" in q_lower:
            return """### 📬 Recommended 3-Day Follow-Up Template:

**Subject:** Re: Accelerating your engineering roadmap

Hi [Hiring Manager Name],

I know how demanding hiring cycles can be, so I wanted to bring this back to the top of your inbox.

We recently helped a similar team ship their backend services in half the scheduled timeline. I'd love to share the exact framework we used.

Do you have 5 minutes for a quick touchpoint this Thursday afternoon?

Best,  
**[Your Name]**
"""
        elif "portfolio" in q_lower or "react" in q_lower or "node" in q_lower or "match" in q_lower:
            if not portfolio_context:
                return (
                    "### Portfolio Case Studies\n\n"
                    "Your portfolio is empty, so there is nothing to match yet.\n\n"
                    "- Open the **Portfolio Vector Store** tab and upload a CSV (Techstack, Links), or add a single item.\n"
                    "- Or set **Your Portfolio / Website URL** in the sidebar to use it as proof of work.\n\n"
                    "Once you add items, ask again and I will match them to the role."
                )
            return (
                "### Your Indexed Portfolio\n\n"
                "Here is what is currently in your portfolio database:\n\n"
                f"```\n{portfolio_context}\n```\n\n"
                "Tell me the target role and I can suggest which of these to cite."
            )
        elif "vendor" in q_lower or "objection" in q_lower:
            return """### 🛡️ How to Handle "We don't work with external vendors":

**Strategy: Pivot from 'vendor' to 'specialized capacity partner'.**

**Response Template:**
> *"Completely understand, [Name] — most agencies overpromise and add bloat. We actually don't operate as a traditional vendor; our senior engineers plug into existing Git workflows under your direct tech leads on a month-to-month basis.*
>
> *Even if now isn't the right time, happy to leave our architecture benchmark doc with you for when your sprint timeline tightens. Wishing you all the best with the current release!"*
"""
        else:
            return f"""I received your request: *"{last_user_query}"*.

Here is my recommendation:
- **Direct Value First:** Tailor your outreach directly to the company's tech stack and immediate pain points.
- **Proof of Work:** Always link 1-2 verified case studies from your portfolio.
- **Frictionless CTA:** Ask for a 10-minute discovery chat rather than a 30-minute sales pitch.

Feel free to ask me to write a specific cold email, refine a pitch, or suggest portfolio links!
"""

    # ------------------------------------------------------------------
    # Extras that build on a generated email
    # ------------------------------------------------------------------
    def _parse_json_list(self, raw: str) -> List[Dict[str, Any]]:
        """Parse a model reply that should be a JSON array of objects."""
        cleaned = _strip_think(raw)
        if not cleaned:
            raise ValueError("Model output was empty.")
        parsed = JsonOutputParser().parse(cleaned)
        if isinstance(parsed, dict):
            # Some models wrap the list: {"subjects": [...]}
            lists = [v for v in parsed.values() if isinstance(v, list)]
            parsed = lists[0] if lists else [parsed]
        if not isinstance(parsed, list):
            raise ValueError("Model output was not a JSON list.")
        return [item for item in parsed if isinstance(item, dict)]

    def subject_lines(self, job: Dict[str, Any], email_text: str, count: int = 5) -> List[Dict[str, str]]:
        """
        Suggests alternative subject lines for an email.
        Returns a list of {"subject": ..., "why": ...}.
        """
        self.last_error = None
        self.fallback_notice = None
        role = str(job.get("role", "the open role"))

        if not self.is_demo_mode and self.llm:
            try:
                prompt = PromptTemplate.from_template(
                    """
                    ### COLD EMAIL:
                    {email_text}

                    ### TARGET ROLE:
                    {job_role}

                    ### INSTRUCTION:
                    Write {count} different subject lines for the cold email above.
                    Each must be under 60 characters, specific to this role, and free of clickbait,
                    ALL CAPS and exclamation marks. Vary the angle: a question, a specific skill,
                    a result, a direct statement, a short curiosity hook.
                    For each one, give a short reason (under 15 words) why it could get opened.
                    Never invent clients, results or numbers that are not in the email.

                    Return ONLY a valid JSON array of objects with keys "subject" and "why".
                    No markdown ticks, no preamble.
                    ### VALID JSON:
                    """
                )
                res = self._invoke_with_fallback(prompt | self.llm, {
                    "email_text": email_text, "job_role": role, "count": count,
                })
                items = []
                for item in self._parse_json_list(res.content):
                    subject = str(item.get("subject", "")).strip().strip('"')
                    if subject:
                        items.append({"subject": subject, "why": str(item.get("why", "")).strip()})
                if items:
                    return items[:count]
                raise ValueError("Model returned no subject lines.")
            except Exception as exc:
                self.last_error = _clean_error_message(exc)
                logger.warning("AI subject lines failed — %s", self.last_error)

        skills = job.get("skills", []) or []
        skill = str(skills[0]) if skills else "engineering"
        return [
            {"subject": f"Quick question about your {role} search", "why": "A question invites a reply."},
            {"subject": f"{skill} help for your {role} opening", "why": "Names the skill they are hiring for."},
            {"subject": f"An idea for filling the {role} role faster", "why": "Promises a concrete benefit."},
            {"subject": f"Saw your {role} posting", "why": "Short, plain and clearly relevant."},
            {"subject": f"Extra {skill} capacity while you hire", "why": "Offers help with the immediate gap."},
        ][:count]

    def follow_ups(
        self,
        job: Dict[str, Any],
        email_text: str,
        sender_name: str,
        tone: str = "Professional & Persuasive",
        days: tuple = (3, 7, 14),
    ) -> List[Dict[str, Any]]:
        """
        Writes a follow-up sequence for an email that got no reply.
        Returns a list of {"day": int, "subject": ..., "body": ...}.
        """
        self.last_error = None
        self.fallback_notice = None
        role = str(job.get("role", "the open role"))

        if not self.is_demo_mode and self.llm:
            try:
                prompt = PromptTemplate.from_template(
                    """
                    ### ORIGINAL COLD EMAIL (no reply yet):
                    {email_text}

                    ### INSTRUCTION:
                    You are {sender_name}. Write {n} short follow-up emails to send {day_list} days
                    after the original email above, which got no reply. Tone: {tone}.

                    Rules:
                    - Each follow-up is under 80 words, plain text, no markdown, no bullet lists.
                    - Each one adds something new (a different angle, a useful detail from the original
                      email, or an easier ask). Do not just repeat "checking in".
                    - The last one is a polite final note that leaves the door open.
                    - Use only facts and links from the original email. Never invent clients, results or numbers.
                    - Sign each one as {sender_name}.

                    Return ONLY a valid JSON array of {n} objects with keys
                    "day" (number), "subject" (string) and "body" (string).
                    No markdown ticks, no preamble.
                    ### VALID JSON:
                    """
                )
                res = self._invoke_with_fallback(prompt | self.llm, {
                    "email_text": email_text,
                    "sender_name": sender_name,
                    "tone": tone,
                    "n": len(days),
                    "day_list": ", ".join(str(d) for d in days),
                })
                items = []
                for i, item in enumerate(self._parse_json_list(res.content)):
                    body = _clean_email_markdown(str(item.get("body", "")))
                    if not body:
                        continue
                    try:
                        day = int(item.get("day", days[min(i, len(days) - 1)]))
                    except (TypeError, ValueError):
                        day = days[min(i, len(days) - 1)]
                    items.append({
                        "day": day,
                        "subject": str(item.get("subject", "")).strip() or f"Re: {role}",
                        "body": body,
                    })
                if items:
                    return items[:len(days)]
                raise ValueError("Model returned no follow-ups.")
            except Exception as exc:
                self.last_error = _clean_error_message(exc)
                logger.warning("AI follow-ups failed — %s", self.last_error)

        name = sender_name or "Me"
        templates = [
            f"Hi,\n\nFollowing up on my note about your {role} opening. I know hiring takes a lot of "
            f"attention, so I'll keep it short: would a 10-minute call this week be useful?\n\nBest,\n{name}",
            f"Hi,\n\nOne more thought on the {role} role. If it helps, I can send a short summary of how "
            f"we'd approach the first 30 days, so you can judge the fit without a call.\n\nBest,\n{name}",
            f"Hi,\n\nI don't want to crowd your inbox, so this is my last note about the {role} role. "
            f"If the timing changes, I'd be glad to pick this up again.\n\nBest,\n{name}",
        ]
        return [
            {"day": d, "subject": f"Re: {role}", "body": templates[min(i, len(templates) - 1)]}
            for i, d in enumerate(days)
        ]

    def rewrite_mail(self, email_text: str, instruction: str, max_words: int = 150) -> str:
        """
        Rewrites an email following a short instruction (e.g. "make it shorter").
        Returns the original text unchanged, with last_error set, when no AI is available.
        """
        self.last_error = None
        self.fallback_notice = None

        if self.is_demo_mode or not self.llm:
            self.last_error = "Rewriting needs an AI key. Add one in the sidebar or use the free trial."
            return email_text

        try:
            prompt = PromptTemplate.from_template(
                """
                ### CURRENT EMAIL:
                {email_text}

                ### CHANGE REQUESTED:
                {instruction}

                ### RULES:
                - Apply the change requested and keep everything else the same in meaning.
                - Keep the 'Subject:' line as the first line, then a blank line, then the body and sign-off.
                - Output plain text only. No markdown, no asterisks, no bullet lists, no bold.
                - Maximum {max_words} words.
                - Keep every link exactly as written. Never invent clients, results or numbers.
                - No preamble and no commentary: return only the rewritten email.

                ### REWRITTEN EMAIL:
                """
            )
            res = self._invoke_with_fallback(prompt | self.llm, {
                "email_text": email_text, "instruction": instruction, "max_words": max_words,
            })
            rewritten = _clean_email_markdown(_strip_think(res.content).strip())
            if not rewritten:
                raise ValueError("Model output was empty.")
            return rewritten
        except Exception as exc:
            self.last_error = _clean_error_message(exc)
            logger.warning("AI rewrite failed — %s", self.last_error)
            return email_text

    # ------------------------------------------------------------------
    # Job-seeker mode and LinkedIn
    # ------------------------------------------------------------------
    def write_application_mail(
        self,
        job: Dict[str, Any],
        links: List[Dict[str, str]],
        sender_name: str,
        resume_text: str,
        sender_role: str = "",
        tone: str = "Professional & Persuasive",
        max_words: int = 150,
    ) -> str:
        """
        Writes an email from a job seeker to the hiring manager for a role,
        grounded in the candidate's resume.
        """
        self.last_error = None
        self.fallback_notice = None

        role = str(job.get("role", "the open role"))
        skills = job.get("skills", []) or []
        link_limit = 2 if max_words >= 300 else 1
        filtered_links = links[:link_limit] if links else []
        link_guidance = (
            f"Mention up to {link_limit} of these links to the candidate's work: {filtered_links}."
            if filtered_links
            else "No links are available, so do not mention any link."
        )

        if not self.is_demo_mode and self.llm:
            try:
                prompt = PromptTemplate.from_template(
                    """
                    ### JOB DETAILS:
                    {job_details}

                    ### CANDIDATE RESUME:
                    {resume_text}

                    ### CANDIDATE:
                    - Name: {sender_name}
                    - Current title: {sender_role}

                    ### RULES:
                    - Output plain text only. No markdown, no asterisks, no bullet lists, no bold.
                    - Format: a 'Subject:' line, a blank line, then 3 short paragraphs, then a sign-off with the candidate's name.
                    - Maximum {max_words} words.
                    - Open with why this specific role fits, not with "I am writing to apply".
                    - Pick the two or three experiences from the resume that best match the job's requirements,
                      and state them concretely.
                    - Use only facts that appear in the resume. Never invent employers, titles, results, numbers or skills.
                      If the resume does not show a required skill, do not claim it.
                    - {link_guidance}
                    - End with one clear, low-pressure call to action.
                    - No preamble and no commentary.

                    ### INSTRUCTION:
                    You are {sender_name}, a candidate interested in the {job_role} role.
                    Write a short email to the hiring manager. Tone: {tone}.

                    ### EMAIL:
                    """
                )
                res = self._invoke_with_fallback(prompt | self.llm, {
                    "job_details": str(job),
                    "job_role": role,
                    "resume_text": resume_text,
                    "sender_name": sender_name,
                    "sender_role": sender_role or "not given",
                    "tone": tone,
                    "max_words": max_words,
                    "link_guidance": link_guidance,
                })
                cleaned = _clean_email_markdown(_strip_think(res.content).strip())
                if not cleaned:
                    raise ValueError("Model output was empty.")
                return cleaned
            except Exception as exc:
                self.last_error = _clean_error_message(exc)
                logger.warning("AI application email failed — %s", self.last_error)

        skills_text = ", ".join(str(s) for s in skills[:3]) if skills else "the skills you listed"
        link_line = f"\nYou can see some of my work here: {filtered_links[0].get('links', '')}\n" if filtered_links else ""
        title_line = f" I currently work as {sender_role}." if sender_role else ""
        return (
            f"Subject: Interested in your {role} role\n\n"
            f"Dear Hiring Team,\n\n"
            f"I saw your opening for {role} and wanted to reach out directly.{title_line} "
            f"The role's focus on {skills_text} lines up closely with the work I have been doing.\n"
            f"{link_line}\n"
            f"My resume is attached. Would you be open to a short call this week to see whether I could be a fit?\n\n"
            f"Best regards,\n{sender_name}"
        )

    @staticmethod
    def _fit_to_limit(text: str, limit: int) -> str:
        """Shorten text to a character limit, cutting at a sentence or word boundary."""
        text = " ".join(str(text).split())
        if len(text) <= limit:
            return text
        cut = text[:limit]
        sentence_end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        if sentence_end >= limit * 0.5:
            return cut[:sentence_end + 1]
        return cut[:cut.rfind(" ")].rstrip(",;:") if " " in cut else cut

    def linkedin_messages(
        self,
        job: Dict[str, Any],
        email_text: str,
        sender_name: str,
        note_limit: int = 300,
    ) -> Dict[str, str]:
        """
        Turns an email into LinkedIn outreach: a connection note (LinkedIn caps these at
        300 characters) and a longer InMail. Returns {"note", "inmail_subject", "inmail_body"}.
        """
        self.last_error = None
        self.fallback_notice = None
        role = str(job.get("role", "the open role"))

        if not self.is_demo_mode and self.llm:
            try:
                prompt = PromptTemplate.from_template(
                    """
                    ### EMAIL THIS IS BASED ON:
                    {email_text}

                    ### INSTRUCTION:
                    You are {sender_name}. Rewrite the email above as two LinkedIn messages about the {job_role} role.

                    1. "note": a connection request note. HARD LIMIT: {note_limit} characters including spaces.
                       Aim for about {note_target}. One specific reason for connecting and one light ask. No links.
                    2. "inmail_subject": an InMail subject under 60 characters.
                    3. "inmail_body": an InMail under 120 words, conversational, with one clear ask.

                    Plain text only: no markdown, no emojis, no hashtags.
                    Use only facts from the email. Never invent clients, employers, results or numbers.

                    Return ONLY a valid JSON object with the keys "note", "inmail_subject" and "inmail_body".
                    No markdown ticks, no preamble.
                    ### VALID JSON:
                    """
                )
                res = self._invoke_with_fallback(prompt | self.llm, {
                    "email_text": email_text,
                    "sender_name": sender_name,
                    "job_role": role,
                    "note_limit": note_limit,
                    "note_target": max(50, note_limit - 40),
                })
                cleaned = _strip_think(res.content)
                if not cleaned:
                    raise ValueError("Model output was empty.")
                parsed = JsonOutputParser().parse(cleaned)
                if isinstance(parsed, list):
                    parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {}
                note = self._fit_to_limit(parsed.get("note", ""), note_limit)
                body = _clean_email_markdown(str(parsed.get("inmail_body", "")))
                if not note or not body:
                    raise ValueError("Model returned incomplete LinkedIn messages.")
                return {
                    "note": note,
                    "inmail_subject": " ".join(str(parsed.get("inmail_subject", "")).split()) or f"Your {role} role",
                    "inmail_body": body,
                }
            except Exception as exc:
                self.last_error = _clean_error_message(exc)
                logger.warning("AI LinkedIn messages failed — %s", self.last_error)

        name = sender_name or "me"
        note = self._fit_to_limit(
            f"Hi, I came across your {role} opening and it lines up closely with my work. "
            f"I'd be glad to connect and share a couple of relevant details. Thanks, {name}",
            note_limit,
        )
        return {
            "note": note,
            "inmail_subject": f"Your {role} role",
            "inmail_body": (
                f"Hi,\n\nI noticed you're hiring for {role}. The requirements match work I've done recently, "
                f"and I think I could be useful.\n\nWould you be open to a quick chat this week?\n\nBest,\n{name}"
            ),
        }
