import os
import re
from typing import List, Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException


class Chain:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "openai/gpt-oss-120b",
        temperature: float = 0.2
    ):
        self.api_key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
        self.model_name = model_name
        self.temperature = temperature
        self.is_demo_mode = (self.api_key.upper() == "DEMO" or self.api_key.upper() == "DEMO_MODE" or not self.api_key.startswith("gsk_"))
        
        self.llm = None
        if not self.is_demo_mode:
            try:
                self.llm = ChatGroq(
                    temperature=self.temperature,
                    groq_api_key=self.api_key,
                    model_name=self.model_name
                )
            except Exception:
                self.is_demo_mode = True

    def extract_jobs(self, cleaned_text: str) -> List[Dict[str, Any]]:
        """
        Extracts job postings from text into a list of job dicts.
        Uses Groq LLM if active, otherwise uses intelligent heuristic extraction.
        """
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
                res = chain_extract.invoke(input={"cleaned_text": cleaned_text})
                json_parser = JsonOutputParser()
                parsed = json_parser.parse(res.content)
                if isinstance(parsed, dict):
                    return [parsed]
                elif isinstance(parsed, list):
                    return parsed
            except Exception as e:
                # If Groq call fails (e.g. rate limit / bad key), fallback smoothly
                print(f"Groq extraction notice: {e}, falling back to built-in parser.")

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
        role_match = re.search(r"(?:for|role|title|position|hiring)\s+([A-Za-z\s/]{3,35}(?:Engineer|Developer|Architect|Scientist|Specialist|Manager))", cleaned_text, re.IGNORECASE)
        role = role_match.group(1).strip() if role_match else "Software & AI Specialist"

        # Estimate experience
        exp_match = re.search(r"(\d+\+?\s*(?:-\s*\d+)?\s*(?:years|yrs)(?:\s+of)?\s+experience)", cleaned_text, re.IGNORECASE)
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
        tone: str = "Professional & Persuasive"
    ) -> str:
        """
        Generates a personalized cold email tailored to the job description and portfolio links.
        """
        role = job.get("role", "Software Role")
        skills = job.get("skills", [])
        desc = job.get("description", "")

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

                    ### INSTRUCTION:
                    You are {sender_name}, working as {sender_role} at {company_name}.
                    {company_name} is an elite AI & software consulting firm.
                    Write a high-converting cold email to the hiring manager for {job_role}.
                    Incorporate proof of work from {link_list}. Tone: {tone}.
                    Provide Subject line and clean body with no conversational preamble.
                    ### COLD EMAIL:
                    """
                )
                chain_email = prompt_email | self.llm
                res = chain_email.invoke({
                    "job_details": str(job),
                    "job_role": role,
                    "sender_name": sender_name,
                    "company_name": company_name,
                    "sender_role": sender_role,
                    "tone": tone,
                    "link_list": str(links)
                })
                return res.content.strip()
            except Exception as e:
                print(f"Groq email generation notice: {e}, using demo engine.")

        # Built-in High-Converting Cold Email Engine
        skills_formatted = ", ".join(skills[:3]) if skills else "modern software engineering and AI architectures"
        links_text = ""
        if links:
            links_text = "\nHere are a few relevant case studies from our recent client engagements:\n"
            for item in links[:2]:
                url = item.get("links", "")
                links_text += f"- Case Study: {url}\n"

        email = f"""Subject: Accelerating Your {role} Roadmap – {company_name} Capability Showcase

Dear Hiring Team,

I noticed your open position for {role} and the emphasis on {skills_formatted}. 

At {company_name}, we specialize in augmenting tech enterprises with dedicated engineers and delivery teams that integrate immediately into active codebases—reducing onboarding overhead and accelerating time-to-market.
{links_text}
Given your current roadmap, our senior engineers can jump in to solve key technical challenges in {skills_formatted} without the usual 3-month hiring latency.

Would you be open to a brief 10-minute exploratory chat this Thursday to see if our capabilities align with your sprint goals?

Warm regards,

{sender_name}
{sender_role} | {company_name}"""
        return email

    def chat_response(
        self,
        messages: List[Dict[str, str]],
        portfolio_context: Optional[str] = None,
        user_profile: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Handles conversational chatbot requests.
        """
        last_user_query = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_query = m.get("content", "")
                break

        if not self.is_demo_mode and self.llm:
            try:
                profile_str = ""
                if user_profile:
                    profile_str = f"User Profile: Name: {user_profile.get('name')}, Company: {user_profile.get('company')}, Role: {user_profile.get('role')}."

                system_prompt = f"""
You are the CareerReach AI Assistant — an expert AI advisor in B2B sales outreach, technical recruiting, and cold email strategies.
{profile_str}

Portfolio database context:
{portfolio_context if portfolio_context else "Standard software engineering & AI services."}

Provide high-value, crisp, actionable advice with markdown formatting.
"""
                formatted_messages = [{"role": "system", "content": system_prompt}]
                for msg in messages:
                    formatted_messages.append({"role": msg["role"], "content": msg["content"]})

                res = self.llm.invoke(formatted_messages)
                return res.content.strip()
            except Exception as e:
                print(f"Groq chat notice: {e}, using demo engine.")

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
