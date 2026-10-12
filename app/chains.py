import os
import re
import logging
from typing import List, Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException

logger = logging.getLogger(__name__)

# Fallback model used when the selected model is not found on Groq
_FALLBACK_MODEL = "openai/gpt-oss-120b"

# Models known to return <think>…</think> reasoning blocks (strip them always)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    """Remove <think>…</think> reasoning blocks from any LLM output."""
    return _THINK_RE.sub("", text).strip()


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


class Chain:
    last_error: Optional[str] = None
    fallback_notice: Optional[str] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "openai/gpt-oss-120b",
        temperature: float = 0.2
    ):
        self.api_key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
        self.model_name = model_name
        self.temperature = temperature
        self.last_error = None          # item 1
        self.fallback_notice = None     # item 4 — surface in UI

        self.is_demo_mode = (
            self.api_key.upper() == "DEMO"
            or self.api_key.upper() == "DEMO_MODE"
            or not self.api_key.startswith("gsk_")
        )

        self.llm = None
        if not self.is_demo_mode:
            try:
                self.llm = ChatGroq(
                    temperature=self.temperature,
                    groq_api_key=self.api_key,
                    model_name=self.model_name
                )
            except Exception as exc:
                # item 1 — record error type + message, never the key
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("Chain init failed — %s: %s", type(exc).__name__, exc)
                self.is_demo_mode = True

    # ------------------------------------------------------------------
    # Internal: invoke LLM with automatic model-not-found retry (item 4)
    # ------------------------------------------------------------------
    def _invoke_with_fallback(self, runnable, inputs: dict) -> Any:
        """
        Invoke a LangChain runnable. If the call fails because the model is not
        found, rebuild with llama-3.3-70b-versatile and retry once.
        Raises the original exception if retry also fails.
        """
        try:
            return runnable.invoke(inputs)
        except Exception as exc:
            if _is_model_not_found(exc) and self.model_name != _FALLBACK_MODEL:
                notice = (
                    f"Model **{self.model_name}** was not found on Groq. "
                    f"Retrying with **{_FALLBACK_MODEL}**."
                )
                self.fallback_notice = notice
                logger.warning("Model not found (%s), retrying with %s", self.model_name, _FALLBACK_MODEL)
                fallback_llm = ChatGroq(
                    temperature=self.temperature,
                    groq_api_key=self.api_key,
                    model_name=_FALLBACK_MODEL
                )
                # Rebuild the runnable with the fallback LLM
                # runnable is prompt | llm — replace the llm part
                prompt_part = runnable.first if hasattr(runnable, "first") else None
                if prompt_part is not None:
                    return (prompt_part | fallback_llm).invoke(inputs)
                # For direct llm invocations (list of messages)
                return fallback_llm.invoke(inputs)
            raise

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
                json_parser = JsonOutputParser()
                parsed = json_parser.parse(raw)
                if isinstance(parsed, dict):
                    return [parsed]
                elif isinstance(parsed, list):
                    return parsed
            except Exception as exc:
                # item 1 + 3 — store error for UI display
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("Groq extraction failed — %s: %s", type(exc).__name__, exc)

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
        sender_name: str = "Mohan",
        company_name: str = "AtliQ",
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
                return _clean_email_markdown(raw)
            except Exception as exc:
                # item 1 + 3
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("Groq email generation failed — %s: %s", type(exc).__name__, exc)

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
{portfolio_context if portfolio_context else "Standard software engineering & AI services."}

Provide high-value, crisp, actionable advice with markdown formatting.
"""
                # item 6 — cap history to last 12 messages before prepending system
                recent_messages = messages[-12:]
                formatted_messages = [{"role": "system", "content": system_prompt}]
                for msg in recent_messages:
                    formatted_messages.append({"role": msg["role"], "content": msg["content"]})

                res = self._invoke_with_fallback(self.llm, formatted_messages)
                return _strip_think(res.content).strip()  # item 5
            except Exception as exc:
                # item 1 + 3
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("Groq chat failed — %s: %s", type(exc).__name__, exc)

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
        elif "react" in q_lower or "node" in q_lower or "match" in q_lower:
            return """### 💼 Matched Portfolio Case Studies:

Based on the indexed portfolio database, the top matching case studies for **React & Node.js** are:

- 🔗 **React, Node.js, MongoDB Portfolio**: [https://example.com/react-portfolio](https://example.com/react-portfolio)
- 🔗 **Full-Stack JavaScript (Express.js) Showcase**: [https://example.com/full-stack-js-portfolio](https://example.com/full-stack-js-portfolio)
- 🔗 **React Native Mobile Solution**: [https://example.com/react-native-portfolio](https://example.com/react-native-portfolio)

Would you like me to draft a cold outreach email pitching one of these case studies?
"""
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
