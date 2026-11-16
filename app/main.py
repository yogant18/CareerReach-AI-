import os
import re
import sys
import json
import html
import uuid
import hashlib
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Add project root to sys.path to enable smooth module importing
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.theme import AVATAR_ASSISTANT, AVATAR_USER, apply_theme, hero, skeleton
from app.chains import Chain
from app.portfolio import MAX_ITEMS, Portfolio
from app.utils import ScrapeError, clean_text, find_sample_job_url, scrape_website
from app.matching import skill_match
from app.resume import ResumeError, extract_resume_text, tidy_resume_text
from app.email_tools import compose_links, record_feedback, replace_subject, split_subject
from app.providers import (
    GROQ, PROVIDER_ORDER, PROVIDERS, explain_error, is_valid_key, list_models, supports_temperature,
)
from app.usage import (
    CHAT, EMAIL, UsageLimiter, _int_setting, client_identifier,
    format_reset_time, format_wait,
)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(root_dir, ".env"))

GROQ_KEYS_URL = PROVIDERS[GROQ]["key_url"]
MODE_FREE = "Free trial"
MODE_OWN = "Use my own API key"
OTHER_MODEL = "Other (type a model ID)"
OUTPUT_BOTH = "Email + LinkedIn messages"
OUTPUT_EMAIL = "Email only"
OUTPUT_LINKEDIN = "LinkedIn messages only"
WRITER_AGENCY = "An agency or freelancer"
WRITER_SEEKER = "A job seeker"
LINKEDIN_NOTE_LIMIT = 300


@st.cache_data(ttl=600, show_spinner=False)
def _models_for_key(provider: str, key_fingerprint: str, _api_key: str) -> list:
    """Models this key can use. Cached per provider + key fingerprint; the key itself is never part of the cache key."""
    return list_models(provider, _api_key)


def provider_guide_md(provider: str) -> str:
    """Short 'how to get a key' steps for one provider."""
    info = PROVIDERS[provider]
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(info["guide"], 1))
    return (
        f"**{info['name']} key** — {info['cost_note']}\n\n{steps}\n"
        f"{len(info['guide']) + 1}. Paste it in the key field above.\n\n"
        "Your key stays in this browser session only. It is never saved or logged."
    )


def _secrets():
    try:
        return st.secrets if hasattr(st, "secrets") else None
    except Exception:
        return None


def _server_key() -> str:
    """Server-side Groq key from Streamlit secrets or the environment ('' if none)."""
    key = ""
    try:
        sec = _secrets()
        if sec is not None and "GROQ_API_KEY" in sec:
            key = str(sec["GROQ_API_KEY"]).strip()
    except Exception:
        key = ""
    if not key:
        key = os.getenv("GROQ_API_KEY", "").strip()
    return key if key.startswith("gsk_") else ""


def _free_trial_model() -> str:
    try:
        sec = _secrets()
        if sec is not None and "FREE_TRIAL_MODEL" in sec:
            return str(sec["FREE_TRIAL_MODEL"]).strip()
    except Exception:
        pass
    return os.getenv("FREE_TRIAL_MODEL", "openai/gpt-oss-20b").strip()


@st.cache_resource
def get_limiter() -> UsageLimiter:
    sec = _secrets()
    salt = ""
    try:
        if sec is not None and "USAGE_SALT" in sec:
            salt = str(sec["USAGE_SALT"])
    except Exception:
        salt = ""
    salt = salt or os.getenv("USAGE_SALT", "") or uuid.uuid4().hex
    return UsageLimiter(
        store_path=os.getenv("USAGE_STORE_PATH") or os.path.join(root_dir, "usage_data.json"),
        per_visitor={
            # 0 means "not limited" for that kind of action.
            EMAIL: _int_setting("FREE_EMAILS_PER_DAY", 7, sec),
            CHAT: _int_setting("FREE_CHATS_PER_DAY", 0, sec),
        },
        global_daily_cap=_int_setting("FREE_GLOBAL_DAILY_CAP", 150, sec),
        salt=salt,
    )


def _visitor() -> str:
    if "_session_uid" not in st.session_state:
        st.session_state["_session_uid"] = uuid.uuid4().hex
    headers, ip = None, None
    try:
        headers = st.context.headers
        ip = getattr(st.context, "ip_address", None)
    except Exception:
        pass
    raw = client_identifier(headers, ip, st.session_state["_session_uid"])
    return get_limiter().visitor_id(raw)


def _free_trial_summary(limits: dict) -> str:
    """e.g. '7 emails per day + unlimited chat'."""
    emails = f"{limits[EMAIL]} emails per day" if limits[EMAIL] else "Unlimited emails"
    chats = f"{limits[CHAT]} chat messages per day" if limits[CHAT] else "unlimited chat"
    return f"{emails} + {chats}"


KEY_GUIDE_MD = f"""
**Get a free Groq key in about a minute:**
1. Open [console.groq.com/keys]({GROQ_KEYS_URL}) and sign in (free, no card needed).
2. Click **Create API Key**, give it any name.
3. Copy the key. It starts with `gsk_`.
4. In the sidebar, choose **{MODE_OWN}**, pick **Groq** and paste it.

Already have an OpenAI (ChatGPT), Google Gemini or Claude key? Those work too: pick the provider in the sidebar.

Your key stays in this browser session only. It is never saved or logged.
"""


def render_limit_notice(status: dict, what: str) -> None:
    """Friendly box shown when a free allowance is used up."""
    if status.get("reason") == "global":
        wait = format_wait(status["global_reset_at"])
        when = format_reset_time(status["global_reset_at"])
        headline = (
            f"Today's free {what} for all visitors are used up. "
            f"They come back in **{wait}** ({when})."
        )
    else:
        wait = format_wait(status["reset_at"])
        when = format_reset_time(status["reset_at"])
        headline = (
            f"You've used all {status['limit']} free {what} for today. "
            f"Your allowance resets in **{wait}** ({when})."
        )
    with st.container(border=True, key="cr_card_limit"):
        st.markdown(f"#### Free limit reached\n{headline}")
        st.markdown("Want to keep going now? Use your own API key. Groq's is free:")
        st.markdown(KEY_GUIDE_MD)
        st.link_button("Get a free Groq key", GROQ_KEYS_URL)


@st.cache_resource
def _chroma_client():
    """One in-memory ChromaDB shared by the process; each visitor gets their own collection in it."""
    import chromadb
    return chromadb.EphemeralClient()


def get_session_portfolio() -> Portfolio:
    """
    This visitor's private portfolio. It lives in st.session_state, so items one
    visitor uploads, adds or clears are never seen by anyone else.
    """
    p = st.session_state.get("portfolio_instance")
    if p is None or not all(hasattr(p, m) for m in ("to_csv", "has_seed", "collection_name")):
        p = Portfolio(
            client=_chroma_client(),
            seed_csv_path=os.path.join(root_dir, "my_portfolio.csv"),
        )
        st.session_state.portfolio_instance = p
    return p


# ---------------------------------------------------------------------------
# Startup key presence check — prints "Groq key: found" or "Groq key: missing"
# Never prints or logs the key value.
# ---------------------------------------------------------------------------
def _check_groq_key() -> None:
    _key = ""
    try:
        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            _key = str(st.secrets["GROQ_API_KEY"]).strip()
    except Exception:
        pass
    if not _key:
        _key = os.getenv("GROQ_API_KEY", "").strip()
    if _key and _key.startswith("gsk_"):
        print("Groq key: found", flush=True)
    else:
        print("Groq key: missing", flush=True)

_check_groq_key()

# Streamlit Page Config — no emoji in title or page icon
st.set_page_config(
    page_title="CareerReach AI — Cold Email & Outreach",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto"  # open on desktop, collapsed on phones
)

# Render Copy button component
def render_copy_button(text_to_copy: str, key_suffix: str, label: str = "Copy"):
    safe_text = json.dumps(text_to_copy).replace("</", "<\\/")
    btn_id = f"cp_{key_suffix}"
    
    html_code = f"""
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600&display=swap">
    <div style="margin-top: 4px; margin-bottom: 8px;">
        <button id="{btn_id}" onclick="doCopy_{btn_id}()" style="
            background: #FFFFFF;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 6px 14px;
            font-family: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', sans-serif;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
        " onmouseover="this.style.borderColor='#2563EB';this.style.color='#1D4ED8'"
          onmouseout="this.style.borderColor='#CBD5E1';this.style.color='#0F172A'">{label}</button>
        <script>
            function doCopy_{btn_id}() {{
                const content = {safe_text};
                navigator.clipboard.writeText(content).then(function() {{
                    const el = document.getElementById("{btn_id}");
                    const prev = el.innerText;
                    el.innerText = "Copied";
                    setTimeout(function() {{ el.innerText = prev; }}, 2000);
                }}).catch(function(e) {{
                    console.error("Clipboard copy failed: ", e);
                }});
            }}
        </script>
    </div>
    """
    st.iframe(html_code, height=44)


@st.cache_data(ttl=3600, show_spinner=False)
def _sample_job_url():
    return find_sample_job_url()


def _set_sample_url():
    """Fill the URL box with a job posting that is live today (fixed sample links go dead)."""
    url = _sample_job_url()
    if url:
        st.session_state["url_input"] = url
        st.session_state["sample_url_failed"] = False
    else:
        _sample_job_url.clear()  # don't remember a failure for an hour
        st.session_state["sample_url_failed"] = True


def md_safe(text) -> str:
    """Escape Markdown in text that came from a web page or the AI, so it shows as plain text."""
    return re.sub(r"([\\`*_\[\]<>!#|~])", r"\\\1", str(text))


def error_details(raw: str) -> str:
    """A plain explanation of an AI error, followed by the technical detail."""
    hint = explain_error(raw)
    detail = f"**Details:** `{raw}`"
    return f"{hint}  \n{detail}" if hint else detail


# Apply the app theme
apply_theme()

# Sidebar Configurations
with st.sidebar:
    st.markdown("### API Access")
    _has_server_key = bool(_server_key())
    _limits = get_limiter().per_visitor
    if _has_server_key:
        access_mode = st.radio(
            "How do you want to run the AI?",
            [MODE_FREE, MODE_OWN],
            captions=[
                _free_trial_summary(_limits) + ", no key needed",
                "Unlimited. Groq (free), ChatGPT, Gemini or Claude",
            ],
            key="access_mode",
        )
    else:
        access_mode = MODE_OWN
        st.caption("The free trial isn't available on this server. Add your own API key to use the AI.")

    user_key = ""
    provider = GROQ
    key_ok = False
    if access_mode == MODE_OWN:
        provider = st.selectbox(
            "AI provider",
            options=PROVIDER_ORDER,
            format_func=lambda pid: PROVIDERS[pid]["label"],
            key="provider_choice",
        )
        _pinfo = PROVIDERS[provider]
        user_key = st.text_input(
            f"Your {_pinfo['name']} API key",
            type="password",
            placeholder=_pinfo["key_placeholder"],
            key=f"user_key_{provider}",  # one field per provider, so keys never cross over
            help="Kept in this browser session only. Never saved or logged.",
        ).strip()
        key_ok = is_valid_key(provider, user_key)
        if user_key and not key_ok:
            st.error(f"That doesn't look like a {_pinfo['name']} key. {_pinfo['key_hint']}")
        elif user_key:
            st.success("Key added for this session.")
        else:
            st.caption(_pinfo["cost_note"])
    # Filled at the end of the script so it reflects usage from this run.
    quota_slot = st.empty()

    if access_mode == MODE_OWN:
        with st.expander(f"Get your {PROVIDERS[provider]['name']} key", expanded=not user_key):
            st.markdown(provider_guide_md(provider))
            st.link_button(f"Open {PROVIDERS[provider]['name']} keys page", PROVIDERS[provider]["key_url"])
    else:
        with st.expander("How to get a free Groq key"):
            st.markdown(KEY_GUIDE_MD)
            st.link_button("Open Groq console", GROQ_KEYS_URL)

    st.markdown("---")
    st.markdown("### Model & Creativity")
    if access_mode == MODE_FREE:
        selected_model = _free_trial_model()
        st.selectbox("Model", options=[selected_model], index=0, disabled=True)
        st.caption("Free trial uses a fast model. Add your own key to choose other models.")
    else:
        if key_ok:
            _fingerprint = hashlib.sha256(user_key.encode("utf-8")).hexdigest()[:16]
            _model_options = _models_for_key(provider, _fingerprint, user_key)
        else:
            _model_options = list(PROVIDERS[provider]["default_models"])
        _choice = st.selectbox(
            f"{PROVIDERS[provider]['name']} model",
            options=_model_options + [OTHER_MODEL],
            index=0,
            key=f"model_choice_{provider}",
        )
        if _choice == OTHER_MODEL:
            selected_model = st.text_input(
                "Model ID",
                placeholder=_model_options[0],
                key=f"model_custom_{provider}",
                help="The exact model name from the provider's documentation.",
            ).strip() or _model_options[0]
        else:
            selected_model = _choice
    if supports_temperature(provider):
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.2)
    else:
        temperature = 0.2
        st.caption("Claude sets its own creativity level, so there is no temperature setting.")

    st.markdown("---")
    st.markdown("### Sender Profile")
    writer_mode = st.radio(
        "I'm writing as",
        [WRITER_AGENCY, WRITER_SEEKER],
        captions=["Pitching your services to a company", "Applying for the role yourself"],
        key="writer_mode",
    )
    is_seeker = writer_mode == WRITER_SEEKER
    resume_text = ""
    if is_seeker:
        sender_name = st.text_input("Your name", value="", placeholder="Alex Johnson", key="seeker_name")
        sender_role = st.text_input("Your current title (optional)", value="", placeholder="Data Analyst", key="seeker_title")
        company_name = ""
        resume_file = st.file_uploader(
            "Your resume",
            type=["pdf", "docx", "txt"],
            key="resume_file",
            help="PDF, Word (.docx) or text, up to 5 MB. It is read in this browser session only and never saved.",
        )
        if resume_file is not None:
            _resume_id = f"{resume_file.name}_{resume_file.size}"
            if st.session_state.get("resume_file_id") != _resume_id:
                st.session_state["resume_file_id"] = _resume_id
                try:
                    st.session_state["resume_text"] = extract_resume_text(resume_file.name, resume_file.getvalue())
                    st.session_state["resume_error"] = None
                except ResumeError as _resume_err:
                    st.session_state["resume_text"] = ""
                    st.session_state["resume_error"] = str(_resume_err)
            if st.session_state.get("resume_error"):
                st.error(st.session_state["resume_error"])
        elif st.session_state.get("resume_file_id"):
            # file removed from the uploader
            st.session_state["resume_file_id"] = None
            st.session_state["resume_text"] = ""
            st.session_state["resume_error"] = None
        with st.expander("Or paste your resume text"):
            _pasted_resume = st.text_area("Resume text", key="resume_pasted", height=160, label_visibility="collapsed")
        resume_text = st.session_state.get("resume_text") or tidy_resume_text(_pasted_resume)
        if resume_text:
            st.caption(f"Resume loaded: {len(resume_text.split())} words. It stays in this browser session only.")
        portfolio_url = st.text_input(
            "Your LinkedIn, GitHub or portfolio URL (optional)",
            value="",
            placeholder="https://github.com/username",
            key="seeker_url",
        )
    else:
        sender_name = st.text_input("Your / Sender Name", value="", placeholder="Alex Johnson")
        company_name = st.text_input("Your Company", value="", placeholder="Acme AI Consulting")
        sender_role = st.text_input("Your Role", value="Business Development Executive")
        portfolio_url = st.text_input(
            "Your Portfolio / Website URL",
            value="",
            placeholder="https://youragency.com/work or https://github.com/username"
        )
    email_tone = st.selectbox(
        "Email Tone",
        options=[
            "Professional & Persuasive",
            "Friendly & Consultative",
            "Short, Direct & High-Impact",
            "Executive & Strategic"
        ],
        index=0
    )
    email_length_option = st.selectbox(
        "Email Length",
        options=[
            "Short (max 100 words)",
            "Standard (max 150 words)",
            "Full (max 300 words)"
        ],
        index=1
    )
    length_limits = {
        "Short (max 100 words)": 100,
        "Standard (max 150 words)": 150,
        "Full (max 300 words)": 300
    }
    max_words_selected = length_limits.get(email_length_option, 150)

    st.markdown("---")
    # Vector store status
    portfolio = get_session_portfolio()
    doc_count = portfolio.collection.count()
    st.markdown("### Your Portfolio")
    st.markdown(f"**{doc_count}** {'item' if doc_count == 1 else 'items'} indexed")
    if doc_count == 0:
        st.caption("Empty. Add items in the Portfolio Vector Store tab.")
    st.caption("Private to this browser session. Other visitors can't see it.")
    if portfolio.has_seed() and st.button("Reset to Starter Portfolio"):
        portfolio.load_portfolio(force_reload=True)
        st.session_state["portfolio_source_label"] = "Starter Portfolio"
        st.success("Portfolio reset.")
        st.rerun()


def using_free_trial() -> bool:
    return access_mode == MODE_FREE


# Helper function to get chain: the visitor's own key, or the server key on the free trial
def get_chain():
    if using_free_trial():
        key = _server_key() or "DEMO_MODE"
    else:
        key = user_key if key_ok else "DEMO_MODE"

    try:
        return Chain(api_key=key, model_name=selected_model, temperature=temperature, provider=provider)
    except Exception as e:
        st.error(f"Error initializing the AI model: {e}")
        return None


def take_free_credit(chain, kind: str, what: str) -> bool:
    """
    On the free trial, use one credit before a real AI call.
    Returns False (and shows the limit notice) when the allowance is used up.
    Own-key and template-only (demo) runs are never metered.
    """
    if not using_free_trial() or chain is None or chain.is_demo_mode:
        return True
    if not get_limiter().per_visitor.get(kind):
        return True  # this kind of action is not limited
    status = get_limiter().consume(_visitor(), kind)
    if not status["allowed"]:
        render_limit_notice(status, what)
        return False
    return True


# ---------------------------------------------------------------------------
# Email generation and the tools shown under each generated email
# ---------------------------------------------------------------------------
REWRITE_PRESETS = [
    ("Shorter", "Make it noticeably shorter and tighter. Keep the subject line, the main point and the call to action."),
    ("More formal", "Make the tone more formal and polished."),
    ("Friendlier", "Make the tone warmer and more conversational, while staying professional."),
    ("Stronger opening", "Rewrite the first sentence so it is specific to this role and earns attention. Keep the rest."),
]
FEEDBACK_PATH = os.getenv("FEEDBACK_PATH") or os.path.join(root_dir, "feedback.jsonl")


def _chain_notices(chain, failed_text: str) -> list:
    """Messages to show after an AI step: model fallback notices and real errors."""
    notes = []
    if getattr(chain, "fallback_notice", None):
        notes.append(("info", chain.fallback_notice))
    if getattr(chain, "last_error", None) and not getattr(chain, "is_demo_mode", False):
        notes.append(("warning", f"{failed_text} {error_details(chain.last_error)}"))
    return notes


def generate_email_batch(chain, content: str) -> dict:
    """Extract the job roles from the text and draft one email per role."""
    batch = {
        "id": uuid.uuid4().hex[:8],
        "notices": [],
        "results": [],
        "max_words": max_words_selected,
        "tone": email_tone,
        "length": email_length_option,
        "sender_name": sender_name,
        "writer": "job_seeker" if is_seeker else "agency",
        "match_source": "your resume" if is_seeker else "your portfolio",
        "output": output_choice,
    }
    slot = st.empty()
    slot.markdown(skeleton("Analyzing job requirements and matching portfolio case studies..."), unsafe_allow_html=True)
    try:
        jobs = chain.extract_jobs(content)
    except Exception as err:
        slot.empty()
        batch["notices"].append(("error", f"Error reading the job posting: {err}"))
        return batch
    batch["notices"] += _chain_notices(chain, "AI extraction failed and built-in parser was used.")

    if not jobs:
        slot.empty()
        batch["notices"].append((
            "warning",
            "No specific job roles could be identified in the text. "
            "Try pasting the job description directly.",
        ))
        return batch
    if len(jobs) > 3:
        batch["notices"].append((
            "info",
            f"Found {len(jobs)} job roles — showing the first 3. "
            "Paste a more specific job description to target individual roles.",
        ))
        jobs = jobs[:3]

    portfolio = get_session_portfolio()
    if is_seeker:
        match_reference = resume_text
    else:
        match_reference = " , ".join(str(t) for t in portfolio.get_all_portfolios()["Techstack"].tolist())
    for idx, job in enumerate(jobs, 1):
        if not isinstance(job, dict):
            continue
        role = str(job.get("role") or f"Role #{idx}")
        slot.markdown(
            skeleton(f"Writing personalized outreach email for {html.escape(role)}..."),
            unsafe_allow_html=True,
        )
        links = portfolio.query_links(job.get("skills", []), base_portfolio_url=portfolio_url)
        try:
            if is_seeker:
                email_text = chain.write_application_mail(
                    job=job,
                    links=links,
                    sender_name=sender_name,
                    resume_text=resume_text,
                    sender_role=sender_role,
                    tone=email_tone,
                    max_words=max_words_selected,
                )
            else:
                email_text = chain.write_mail(
                    job=job,
                    links=links,
                    sender_name=sender_name,
                    company_name=company_name,
                    sender_role=sender_role,
                    tone=email_tone,
                    max_words=max_words_selected,
                )
        except Exception as err:
            batch["notices"].append(("error", f"Error writing the email for {role}: {err}"))
            continue
        batch["results"].append({
            "job": job,
            "role": role,
            "links": links,
            "email": email_text,
            "v": 0,              # bumped whenever the app changes the text, to refresh the editor
            "history": [],       # earlier versions, for Undo
            "subjects": [],
            "followups": [],
            "notices": _chain_notices(chain, "AI email generation failed; built-in template used."),
            "flash": None,
            "feedback": None,
            "linkedin": None,
            "match": (
                skill_match(job.get("skills", []), match_reference)
                if match_reference.strip() and job.get("skills") else None
            ),
        })
        if output_choice != OUTPUT_EMAIL:
            slot.markdown(
                skeleton(f"Writing LinkedIn messages for {html.escape(role)}..."),
                unsafe_allow_html=True,
            )
            _write_linkedin(chain, batch["results"][-1], job, email_text, sender_name)
    slot.empty()
    return batch


def _set_email(result: dict, current: str, new_text: str) -> None:
    """Replace the email text, remembering the previous version for Undo."""
    result["history"].append(current)
    result["email"] = new_text
    result["v"] += 1


def _write_linkedin(chain, r: dict, job: dict, email_text: str, sender: str) -> None:
    """Write (or rewrite) the LinkedIn messages for one result."""
    r["linkedin"] = chain.linkedin_messages(job, email_text, sender, LINKEDIN_NOTE_LIMIT)
    if chain.last_error and not chain.is_demo_mode:
        r["flash"] = ("warning", f"AI LinkedIn messages failed; built-in templates shown. {error_details(chain.last_error)}")


def render_linkedin_fields(uid: str, li: dict) -> None:
    """Editable connection note (with the 300-character counter) and InMail."""
    st.markdown("**Connection note** (sent with a connection request)")
    li["note"] = st.text_area(
        "LinkedIn connection note",
        value=li["note"],
        height=110,
        key=f"li_note_{uid}_{li.get('v', 0)}",
        label_visibility="collapsed",
    )
    note_len = len(li["note"])
    if note_len > LINKEDIN_NOTE_LIMIT:
        st.warning(f"{note_len} / {LINKEDIN_NOTE_LIMIT} characters. LinkedIn will not accept a note this long.")
    else:
        st.caption(f"{note_len} / {LINKEDIN_NOTE_LIMIT} characters (LinkedIn's limit for connection notes).")
    render_copy_button(li["note"], key_suffix=f"li_note_{uid}_{li.get('v', 0)}", label="Copy note")

    st.markdown(f"**InMail** · {md_safe(li['inmail_subject'])}")
    li["inmail_body"] = st.text_area(
        "LinkedIn InMail",
        value=li["inmail_body"],
        height=240,
        key=f"li_inmail_{uid}_{li.get('v', 0)}",
        label_visibility="collapsed",
    )
    render_copy_button(li["inmail_body"], key_suffix=f"li_inmail_{uid}_{li.get('v', 0)}", label="Copy InMail")


def render_linkedin_card(batch: dict, uid: str, r: dict, job: dict) -> None:
    """LinkedIn messages shown in the open, as their own card."""
    with st.container(border=True, key=f"cr_card_li_{uid}"):
        st.markdown(
            '<div class="cr-li-head"><span class="cr-li-badge">in</span><div>'
            '<div class="cr-li-title">LinkedIn messages</div>'
            '<div class="cr-li-sub">A connection note and an InMail for the same role. Edit, then copy into LinkedIn.</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        li = r.get("linkedin")
        if li:
            render_linkedin_fields(uid, li)
        c_refresh, c_open, _ = st.columns([2, 2, 3])
        with c_refresh:
            label = "Rewrite from current email" if li else "Write LinkedIn messages"
            if st.button(label, key=f"li_go_{uid}", help="Writes new LinkedIn messages based on the email as it is now."):
                chain = get_chain()
                if chain:
                    with st.spinner("Writing LinkedIn messages..."):
                        version = (li or {}).get("v", 0) + 1
                        _write_linkedin(chain, r, job, r["email"], batch["sender_name"])
                        r["linkedin"]["v"] = version
                    st.rerun()
        with c_open:
            st.link_button("Open LinkedIn", "https://www.linkedin.com/", key=f"li_open_{uid}")


def render_email_result(batch: dict, i: int, r: dict) -> None:
    uid = f"{batch['id']}_{i}"
    job, role = r["job"], r["role"]
    experience = job.get("experience", "Not specified")
    skills = job.get("skills", []) or []
    desc = str(job.get("description", ""))

    st.markdown(f"#### Job #{i + 1}: {md_safe(role)}")
    col_meta1, col_meta2 = st.columns([1, 2])
    with col_meta1:
        st.markdown(f"**Experience:** {md_safe(experience)}")
        st.markdown(f"**Summary:** {md_safe(desc[:250])}..." if len(desc) > 250 else f"**Summary:** {md_safe(desc)}")
    with col_meta2:
        match = r.get("match")
        if match and match["total"]:
            def _badges(items, css):
                return "".join(f'<span class="badge-glow {css}">{html.escape(str(s))}</span>' for s in items)

            source = html.escape(batch.get("match_source", "your profile"))
            parts = [
                f'<div class="cr-match"><strong>Skill match: {match["score"]}%</strong> '
                f'({len(match["matched"])} of {match["total"]} skills found in {source})</div>'
            ]
            if match["matched"]:
                parts.append('<div class="cr-match-label">Found</div>' + _badges(match["matched"], "badge-hit"))
            if match["missing"]:
                parts.append('<div class="cr-match-label">Not found</div>' + _badges(match["missing"], "badge-miss"))
            st.markdown("".join(parts), unsafe_allow_html=True)
            st.caption("Keyword match only: a skill described in different words may show as not found.")
        else:
            st.markdown("**Detected Skills:**")
            if skills:
                st.markdown(
                    "".join(f'<span class="badge-glow">{html.escape(str(s))}</span>' for s in skills),
                    unsafe_allow_html=True,
                )
                st.caption(
                    "Upload your resume to see how well you match."
                    if batch.get("writer") == "job_seeker"
                    else "Add portfolio items to see how well your work matches."
                )
            else:
                st.write("None detected.")
    if not r["links"]:
        st.caption(
            "No portfolio links available, so this email has no proof-of-work link. "
            "Add portfolio items or set your Portfolio URL in the sidebar."
        )
    for kind, text in r["notices"]:
        getattr(st, kind)(text)

    output = batch.get("output", OUTPUT_EMAIL)
    if output == OUTPUT_LINKEDIN:
        render_linkedin_card(batch, uid, r, job)

    # ---- The email itself (editable) ----
    st.markdown("##### Email version" if output == OUTPUT_LINKEDIN else "##### Your cold email")
    st.caption("You can edit the text directly. The tools below work on whatever is in the box.")
    current = st.text_area(
        label=f"Cold Email for {role}",
        value=r["email"],
        height=300,
        key=f"mail_{uid}_v{r['v']}",
        label_visibility="collapsed",
    )
    r["email"] = current

    if r.get("flash"):
        kind, text = r["flash"]
        getattr(st, kind)(text)
        r["flash"] = None

    word_count = len(current.split())
    if word_count > batch["max_words"]:
        st.warning(f"Word Count: {word_count} words (exceeds target limit of {batch['max_words']} words).")
    else:
        st.caption(f"Word Count: {word_count} / {batch['max_words']} words.")

    # ---- Copy, download, open in a mail app ----
    subject, body = split_subject(current)
    links = compose_links(subject, body)
    c_copy, c_dl, c_gmail, c_outlook, c_mail = st.columns(5)
    with c_copy:
        render_copy_button(current, key_suffix=f"mail_{uid}_{r['v']}", label="Copy Email")
    with c_dl:
        st.download_button(
            label="Download (.txt)",
            data=current,
            file_name=f"cold_email_{re.sub(r'[^a-z0-9]+', '_', role.lower()).strip('_') or 'role'}.txt",
            mime="text/plain",
            key=f"dl_{uid}",
        )
    with c_gmail:
        st.link_button("Open in Gmail", links["gmail"], help="Opens a new Gmail message with this email filled in.")
    with c_outlook:
        st.link_button("Open in Outlook", links["outlook"], help="Opens a new Outlook (web) message with this email filled in.")
    with c_mail:
        st.link_button("Mail app", links["mailto"], help="Opens your computer's default mail app.")

    if output == OUTPUT_BOTH:
        render_linkedin_card(batch, uid, r, job)

    # ---- Rewrite ----
    st.markdown("**Improve this email**")
    instruction = None
    preset_cols = st.columns(len(REWRITE_PRESETS))
    for col, (label, preset_instruction) in zip(preset_cols, REWRITE_PRESETS):
        with col:
            if st.button(label, key=f"rw_{uid}_{label}"):
                instruction = preset_instruction
    c_custom, c_go, c_undo = st.columns([4, 1, 1], vertical_alignment="bottom")
    with c_custom:
        custom = st.text_input(
            "Or describe the change you want",
            placeholder="e.g. mention that we can start within two weeks",
            key=f"rw_custom_{uid}",
        )
    with c_go:
        if st.button("Rewrite", key=f"rw_go_{uid}", type="primary", disabled=not custom.strip()):
            instruction = custom.strip()
    with c_undo:
        if st.button("Undo", key=f"rw_undo_{uid}", disabled=not r["history"], help="Go back to the previous version"):
            r["email"] = r["history"].pop()
            r["v"] += 1
            st.rerun()

    if instruction:
        chain = get_chain()
        if chain:
            with st.spinner("Rewriting..."):
                new_text = chain.rewrite_mail(current, instruction, batch["max_words"])
            if chain.last_error:
                r["flash"] = ("warning", f"The email was not changed. {explain_error(chain.last_error) or chain.last_error}")
            else:
                _set_email(r, current, new_text)
                r["flash"] = ("success", "Email rewritten. Use Undo to go back.")
            st.rerun()

    # ---- Subject lines ----
    with st.expander("Subject line ideas", expanded=bool(r["subjects"])):
        if st.button("Suggest 5 subject lines", key=f"subj_go_{uid}"):
            chain = get_chain()
            if chain:
                with st.spinner("Thinking of subject lines..."):
                    r["subjects"] = chain.subject_lines(job, current)
                if chain.last_error and not chain.is_demo_mode:
                    r["flash"] = ("warning", f"AI subject lines failed; built-in ideas shown. {error_details(chain.last_error)}")
                st.rerun()
        for j, item in enumerate(r["subjects"]):
            c_text, c_use = st.columns([5, 1], vertical_alignment="center")
            with c_text:
                st.markdown(f"**{md_safe(item['subject'])}**")
                if item.get("why"):
                    st.caption(item["why"])
            with c_use:
                if st.button("Use", key=f"subj_use_{uid}_{j}", help="Put this subject line on the email"):
                    _set_email(r, current, replace_subject(current, item["subject"]))
                    st.rerun()

    # ---- Follow-ups ----
    with st.expander("Follow-up emails (day 3, 7 and 14)", expanded=bool(r["followups"])):
        if st.button("Write follow-ups", key=f"fu_go_{uid}"):
            chain = get_chain()
            if chain:
                with st.spinner("Writing follow-ups..."):
                    r["followups"] = chain.follow_ups(job, current, batch["sender_name"], batch["tone"])
                if chain.last_error and not chain.is_demo_mode:
                    r["flash"] = ("warning", f"AI follow-ups failed; built-in templates shown. {error_details(chain.last_error)}")
                st.rerun()
        for j, item in enumerate(r["followups"]):
            st.markdown(f"**Day {item['day']}** · {md_safe(item['subject'])}")
            item["body"] = st.text_area(
                f"Follow-up for day {item['day']}",
                value=item["body"],
                height=210,
                key=f"fu_{uid}_{j}",
                label_visibility="collapsed",
            )
            c_fcopy, c_fgmail, _ = st.columns([1, 1, 3])
            with c_fcopy:
                render_copy_button(item["body"], key_suffix=f"fu_{uid}_{j}", label="Copy")
            with c_fgmail:
                st.link_button("Open in Gmail", compose_links(item["subject"], item["body"])["gmail"], key=f"fu_gm_{uid}_{j}")

    # ---- LinkedIn (only tucked away when the visitor asked for email only) ----
    if output == OUTPUT_EMAIL:
        with st.expander("LinkedIn messages", expanded=bool(r.get("linkedin"))):
            if st.button("Write LinkedIn messages", key=f"li_go_{uid}"):
                chain = get_chain()
                if chain:
                    with st.spinner("Writing LinkedIn messages..."):
                        _write_linkedin(chain, r, job, current, batch["sender_name"])
                    st.rerun()
            if r.get("linkedin"):
                render_linkedin_fields(uid, r["linkedin"])

    # ---- Feedback ----
    c_fb_label, c_fb = st.columns([1, 4], vertical_alignment="center")
    with c_fb_label:
        st.caption("Was this email useful?")
    with c_fb:
        rating = st.feedback("thumbs", key=f"fb_{uid}")
    if rating is not None and rating != r["feedback"]:
        r["feedback"] = rating
        record_feedback(FEEDBACK_PATH, {
            "rating": "up" if rating == 1 else "down",
            "tone": batch["tone"],
            "length": batch["length"],
            "mode": "free_trial" if using_free_trial() else "own_key",
            "provider": provider,
            "model": selected_model,
            "rewrites": len(r["history"]),
            "writer": batch.get("writer", "agency"),
        })
    if r["feedback"] is not None:
        st.caption("Thanks for the feedback.")
    st.markdown("---")


def render_email_batch() -> None:
    batch = st.session_state.get("email_batch")
    if not batch:
        return
    for kind, text in batch["notices"]:
        getattr(st, kind)(text)
    if batch["results"]:
        st.success(f"Drafted {len(batch['results'])} email(s). Results stay here until you generate again.")
    for i, r in enumerate(batch["results"]):
        render_email_result(batch, i, r)
    if batch["results"] and st.button("Clear results", key="clear_email_batch"):
        st.session_state["email_batch"] = None
        st.rerun()


# Page header
hero(
    "CareerReach AI",
    "For job seekers, freelancers and agencies reaching out to companies that are hiring.",
)

# Demo-mode banner: shown once, before tabs, only when no usable key is available
_probe_chain = get_chain()
if _probe_chain and _probe_chain.is_demo_mode:
    if access_mode == MODE_OWN:
        st.info(
            f"Add your {PROVIDERS[provider]['name']} API key in the sidebar to turn on the AI. "
            "Until then, outputs use built-in templates. "
            "The sidebar has a short guide to getting a key."
        )
    else:
        st.warning(
            "Demo Mode — AI features are disabled. "
            "No valid Groq API key was found. All outputs will use built-in templates. "
            "Add your key to app/.env (local) or Streamlit Secrets (cloud), then refresh."
        )

# Tabs Navigation
tab_email, tab_chat, tab_portfolio = st.tabs([
    "Email & LinkedIn Generator",
    "Interactive AI Chatbot",
    "Portfolio Vector Store"
])


# ==========================================
# TAB 1: COLD EMAIL GENERATOR
# ==========================================
with tab_email:
    st.markdown("### Generate Job-Tailored Emails and LinkedIn Messages")
    st.write(
        "Give us a job posting, as a link or pasted text. CareerReach AI matches it to your work and "
        "drafts a cold email, plus a LinkedIn connection note and InMail for the same role."
    )

    output_choice = st.radio(
        "What do you need?",
        [OUTPUT_BOTH, OUTPUT_EMAIL, OUTPUT_LINKEDIN],
        horizontal=True,
        key="output_choice",
    )

    input_mode = st.radio(
        "Choose Input Method:",
        ["Extract from Careers Page URL", "Paste Job Description Directly"],
        horizontal=True
    )

    scraped_content = ""
    run_generation = False

    if input_mode == "Extract from Careers Page URL":
        col_url, col_example = st.columns([4, 1])
        with col_url:
            url_input = st.text_input(
                "Company Careers Page / Job Posting URL",
                placeholder="https://boards.greenhouse.io/company/jobs/1234567",
                key="url_input"
            )
        with col_example:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            st.button("Use Sample URL", on_click=_set_sample_url, help="Fills in a job posting that is live today.")
        if st.session_state.get("sample_url_failed"):
            st.warning(
                "Couldn't find a live sample posting right now. Choose 'Paste Job Description Directly' "
                "instead: it has a sample filled in."
            )

        submit_btn = st.button("Extract & Generate", type="primary")

        if submit_btn:
            if not url_input.strip():
                st.warning("Please provide a valid URL.")
            else:
                sk_scrape = st.empty()
                sk_scrape.markdown(skeleton("Scraping webpage and parsing job listings..."), unsafe_allow_html=True)
                with st.spinner("Processing..."):
                    try:
                        scraped_content = scrape_website(url_input.strip())
                        sk_scrape.empty()
                        if not scraped_content:
                            st.error("No readable text could be retrieved from the given URL. Try pasting the job description directly.")
                        else:
                            run_generation = True
                    except ScrapeError as err:
                        sk_scrape.empty()
                        st.error(str(err))
                    except Exception:
                        sk_scrape.empty()
                        st.error(
                            "Something went wrong while reading that page. "
                            "Switch to 'Paste Job Description Directly' and paste the posting text instead."
                        )

    else:
        sample_jd = (
            "We are looking for a Senior Python & Machine Learning Engineer with 3+ years of experience "
            "in building scalable ML pipelines, AWS cloud deployments, and microservices using FastAPI/Docker. "
            "Experience with ChromaDB or vector databases is a huge plus."
        )
        jd_input = st.text_area(
            "Paste the Job Description or Requirements:",
            value=sample_jd,
            height=180
        )
        submit_btn = st.button("Generate from Description", type="primary")

        if submit_btn:
            if not jd_input.strip():
                st.warning("Please enter job description text.")
            else:
                scraped_content = clean_text(jd_input)
                run_generation = True

    # Generation. Results are kept in session state so they survive reruns
    # (editing, rewriting, downloads and feedback all rerun the script).
    if run_generation and scraped_content:
        if is_seeker and not sender_name.strip():
            st.error("Please add your name in the sidebar before generating emails.")
        elif is_seeker and not resume_text:
            st.error("Please upload or paste your resume in the sidebar, so the email can be based on your real experience.")
        elif not is_seeker and (not sender_name.strip() or not company_name.strip()):
            st.error("Please fill in both Sender Name and Company in the sidebar before generating emails.")
        else:
            chain = get_chain()
            if not chain:
                st.error("Please add a valid API key in the sidebar to generate cold emails.")
            elif take_free_credit(chain, EMAIL, "email generations"):
                with st.spinner("Processing..."):
                    st.session_state["email_batch"] = generate_email_batch(chain, scraped_content)

    render_email_batch()


# ==========================================
# TAB 2: INTERACTIVE AI CHATBOT
# ==========================================
with tab_chat:
    st.markdown("### Outreach Strategy Chatbot")
    st.write(
        "Chat with your AI outreach strategist. Draft custom pitches, polish subject lines, "
        "find matching portfolio case studies, or prepare follow-up sequences."
    )

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "Hello. I am your CareerReach outreach strategist. I can help craft high-converting cold emails, refine messaging angles, or match portfolio case studies. What role or campaign are you targeting today?"
            }
        ]

    # Quick Action Prompt Chips
    st.markdown("**Quick Starters:**")
    quick_col1, quick_col2 = st.columns(2)
    
    suggested_prompt = None
    with quick_col1:
        if st.button("5 high-converting subject lines for an AI role"):
            suggested_prompt = "Give me 5 catchy, high-converting cold email subject lines for an AI/ML Engineer reachout."
        if st.button("Write a 3-day follow-up email after no reply"):
            suggested_prompt = "Write a short, polite 3-day follow-up email after no response to our initial cold outreach."
    with quick_col2:
        if st.button("Which portfolio links match React & Node.js?"):
            suggested_prompt = "Which portfolio case studies from our database match a React, Node.js, and MongoDB tech stack?"
        if st.button("Handle objection: We do not use external agencies"):
            suggested_prompt = "How should I reply to a prospect who responds with: 'We don't use external agencies or vendors right now'?"

    st.markdown("---")

    # The input box is created after this container, so it always sits below the conversation.
    chat_area = st.container()

    # Handle New Chat Input
    user_query = st.chat_input("Type your question or outreach request here...")
    
    # Check if a quick prompt chip was pressed
    if suggested_prompt and not user_query:
        user_query = suggested_prompt

    with chat_area:
        # Display Chat Messages with Copy buttons on assistant outputs
        if not st.session_state.chat_history:
            # Empty state: one clear button
            st.info("No conversation messages yet.")
            if st.button("Start Conversation", key="empty_chat_starter"):
                st.session_state.chat_history = [
                    {
                        "role": "assistant",
                        "content": "Hello. I am ready to help draft pitches or plan your cold outreach campaign. What would you like to work on?"
                    }
                ]
                st.rerun()
        else:
            for idx, msg in enumerate(st.session_state.chat_history):
                is_user = msg["role"] == "user"
                with st.chat_message(msg["role"], avatar=AVATAR_USER if is_user else AVATAR_ASSISTANT):
                    if is_user:
                        st.markdown('<span class="cr-user-msg"></span>', unsafe_allow_html=True)
                    st.markdown(msg["content"])
                    if msg["role"] == "assistant":
                        render_copy_button(msg["content"], key_suffix=f"chat_msg_{idx}", label="Copy Response")

        chat_chain = get_chain() if user_query else None
        if user_query and not take_free_credit(chat_chain, CHAT, "chat messages"):
            user_query = None  # limit notice already shown; don't add the message to history

        if user_query:
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            with st.chat_message("user", avatar=AVATAR_USER):
                st.markdown('<span class="cr-user-msg"></span>', unsafe_allow_html=True)
                st.markdown(user_query)

            # Generate Assistant response
            chain = chat_chain
            if not chain:
                error_msg = "Please add a valid API key in the sidebar to talk with the chatbot."
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
                with st.chat_message("assistant", avatar=AVATAR_ASSISTANT):
                    st.warning(error_msg)
            else:
                with st.chat_message("assistant", avatar=AVATAR_ASSISTANT):
                    sk_chat = st.empty()
                    sk_chat.markdown(skeleton("Formulating outreach strategy..."), unsafe_allow_html=True)
                    with st.spinner("Thinking..."):
                        try:
                            portfolio_df = get_session_portfolio().get_all_portfolios()
                            portfolio_summary = portfolio_df.to_string(index=False) if not portfolio_df.empty else ""
                        
                            user_prof = {
                                "name": sender_name,
                                "company": company_name,
                                "role": sender_role
                            }

                            response = chain.chat_response(
                                messages=st.session_state.chat_history,
                                portfolio_context=portfolio_summary,
                                user_profile=user_prof
                            )

                            sk_chat.empty()
                            chat_fallback = getattr(chain, "fallback_notice", None)
                            chat_err = getattr(chain, "last_error", None)
                            chat_demo = getattr(chain, "is_demo_mode", False)
                            if chat_fallback:
                                st.info(chat_fallback)
                            if chat_err and not chat_demo:
                                st.warning(
                                    f"AI call failed; built-in response used.  \n"
                                    f"{error_details(chat_err)}"
                                )
                            st.markdown(response)
                            render_copy_button(response, key_suffix=f"chat_reply_{len(st.session_state.chat_history)}", label="Copy Response")
                            st.session_state.chat_history.append({"role": "assistant", "content": response})
                        except Exception as chat_err:
                            sk_chat.empty()
                            err_text = f"Error generating response: {str(chat_err)}"
                            st.error(err_text)
                            st.session_state.chat_history.append({"role": "assistant", "content": err_text})

    # Clear Chat History Button — empty state reset
    col_clear, _ = st.columns([1, 4])
    with col_clear:
        if st.button("Clear Conversation"):
            st.session_state.chat_history = []
            st.rerun()


# ==========================================
# TAB 3: PORTFOLIO & VECTOR STORE
# ==========================================
with tab_portfolio:
    st.markdown("### Portfolio Vector Database")
    st.write(
        "Upload your own portfolio CSV (Techstack, Links) or add items one by one. "
        "When you upload your CSV, ChromaDB indexes your projects in real-time so your outreach emails quote your own real case studies. "
        "Your portfolio is private to this browser session and is cleared when you close or refresh the page, "
        "so use **Download My Portfolio** to keep a copy."
    )

    # -------------------------------------------------------------
    # Upload a custom portfolio CSV or add items manually
    # -------------------------------------------------------------
    with st.container(border=True, key="cr_card_source"):
        st.markdown("#### Portfolio Source & Custom CSV Upload")
    
        col_upload, col_reset = st.columns([3, 1])
        portfolio = get_session_portfolio()
    
        with col_upload:
            uploaded_csv = st.file_uploader(
                "Upload your own portfolio CSV (Techstack, Links)",
                type=["csv"],
                help="Upload a CSV with 'Techstack' and 'Links' headers. ChromaDB will index your case studies immediately."
            )
            if uploaded_csv is not None:
                upload_id = f"{uploaded_csv.name}_{uploaded_csv.size}"
                if st.session_state.get("current_portfolio_upload") != upload_id:
                    try:
                        user_df = pd.read_csv(uploaded_csv)
                        # Normalize column names
                        col_map = {c: c.strip().capitalize() for c in user_df.columns}
                        user_df.rename(columns=col_map, inplace=True)
                        if "Techstack" in user_df.columns and "Links" in user_df.columns:
                            added = portfolio.load_from_dataframe(user_df, force_reload=True)
                            st.session_state["current_portfolio_upload"] = upload_id
                            st.session_state["portfolio_source_label"] = f"Custom CSV: {uploaded_csv.name}"
                            st.session_state["add_portfolio_msg"] = (
                                f"Indexed {added} case studies from '{uploaded_csv.name}'. "
                                f"Emails will now cite your own case studies."
                                + (f" Only the first {MAX_ITEMS} items are kept." if added >= MAX_ITEMS else "")
                            )
                            st.rerun()
                        else:
                            st.error("Uploaded CSV must contain 'Techstack' and 'Links' columns.")
                    except Exception as e:
                        st.error(f"Error reading uploaded CSV: {e}")
            else:
                # Uploader emptied: allow the same file to be uploaded again later.
                st.session_state["current_portfolio_upload"] = None

        with col_reset:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("Clear Portfolio", help="Remove every item from your portfolio"):
                portfolio.clear_portfolio()
                st.session_state["portfolio_source_label"] = "Empty"
                st.success("Portfolio cleared.")
                st.rerun()

            # Download sample template
            sample_csv = "Techstack,Links\n\"FastAPI, PostgreSQL, Docker\",https://example.com/case-studies/fintech-api\n\"React, Next.js, Stripe\",https://example.com/case-studies/ecommerce-platform\n\"PyTorch, LLMs, LangChain\",https://example.com/case-studies/ai-copilot\n"
            st.download_button(
                label="Sample CSV Template",
                data=sample_csv,
                file_name="portfolio_template.csv",
                mime="text/csv"
            )
            if not portfolio.is_empty():
                st.download_button(
                    label="Download My Portfolio",
                    data=portfolio.to_csv(),
                    file_name="my_portfolio.csv",
                    mime="text/csv",
                    help="Your portfolio is cleared when you close or refresh this page. Save it here and upload it again next time.",
                )

        active_source = st.session_state.get("portfolio_source_label", "My Portfolio")
        st.markdown(f'<div style="font-size: 0.85rem; color: #475569; margin-top: 6px;">Active Library: <span class="badge-glow" style="margin-left: 6px;">{html.escape(active_source)}</span></div>', unsafe_allow_html=True)

    col_view, col_add = st.columns([3, 2])

    with col_view:
        st.subheader("Current Indexed Portfolios")
        df_port = portfolio.get_all_portfolios()

        # Minimalist Glassmorphism (Vercel) Cards instead of a glaring white table
        def _safe_url(u):
            u = str(u).strip()
            return u if u.lower().startswith(("http://", "https://")) else None

        if df_port is not None and not df_port.empty:
            for n, (_, row) in enumerate(df_port.iterrows()):
                tech = html.escape(str(row.get("Techstack", "")))
                raw = str(row.get("Links", ""))
                url = _safe_url(raw)
                with st.container(border=True, key=f"cr_card_item_{n}"):
                    c_txt, c_btn = st.columns([4, 1], vertical_alignment="center")
                    with c_txt:
                        st.markdown(
                            f'<div style="font-weight:700;color:#0F172A;font-size:0.95rem;margin-bottom:2px;">{tech}</div>'
                            f'<div style="font-size:0.82rem;color:#2563EB;word-break:break-all;">{html.escape(raw)}</div>',
                            unsafe_allow_html=True,
                        )
                    with c_btn:
                        if url:
                            st.link_button("Open", url, key=f"open_port_{n}")
                        else:
                            st.caption("Invalid URL")
        else:
            st.info(
                "Your portfolio is empty. Upload a CSV above or add an item on the right. "
                "Until then, emails will only cite the Portfolio / Website URL from the sidebar, if you set one."
            )

        st.markdown("---")
        st.subheader("Test Semantic Search")
        search_query = st.text_input(
            "Enter skills or tech query (e.g. 'Kubernetes cloud deployment', 'iOS ARKit')",
            value="Machine Learning Python"
        )
        if st.button("Search Vector DB", type="primary", disabled=portfolio.is_empty(),
                     help="Add portfolio items first" if portfolio.is_empty() else None):
            st.session_state["search_matches"] = portfolio.query_links(
                search_query, n_results=3, base_portfolio_url=portfolio_url
            )
            st.session_state["has_searched"] = True

        matches = st.session_state.get("search_matches", [])
        if st.session_state.get("has_searched"):
            if matches:
                st.write("**Matching Links Found:**")
                for i, m in enumerate(matches):
                    raw_url = str(m.get('links', ''))
                    url = _safe_url(raw_url)
                    with st.container(border=True, key=f"cr_card_match_{i}"):
                        c_txt, c_btn = st.columns([4, 1], vertical_alignment="center")
                        with c_txt:
                            st.markdown(
                                f'<span style="color:#15803D;font-size:0.85rem;font-weight:600;">Match #{i+1}</span>'
                                f'<div style="font-size:0.88rem;color:#2563EB;word-break:break-all;">{html.escape(raw_url)}</div>',
                                unsafe_allow_html=True,
                            )
                        with c_btn:
                            if url:
                                st.link_button("Open", url, key=f"open_match_{i}")
                            else:
                                st.caption("Invalid URL")
            else:
                st.info("No matching portfolio entries found.")

    with col_add:
        st.subheader("Add Portfolio Item")
        # Show persistent success notice when an item is added
        if st.session_state.get("add_portfolio_msg"):
            st.success(st.session_state["add_portfolio_msg"])
            st.session_state["add_portfolio_msg"] = None

        with st.form("add_portfolio_form", clear_on_submit=True):
            new_techstack = st.text_input("Techstack / Skills (e.g. Next.js, FastAPI, PostgreSQL)")
            new_link = st.text_input("Portfolio / Case Study URL", placeholder="https://example.com/case-studies/project")
            submitted = st.form_submit_button("Add to Database", type="primary")

            if submitted:
                if not new_techstack.strip() or not new_link.strip():
                    st.warning("Please fill in both Techstack and Link fields.")
                elif not (new_link.strip().startswith("http://") or new_link.strip().startswith("https://")):
                    st.warning("Portfolio link must start with http:// or https://")
                else:
                    try:
                        success = portfolio.add_portfolio(new_techstack.strip(), new_link.strip())
                        if success:
                            st.session_state["add_portfolio_msg"] = f"Successfully added '{new_techstack.strip()}' to portfolio database!"
                            st.rerun()
                        else:
                            st.error("Failed to add portfolio.")
                    except ValueError as val_err:
                        st.warning(f"Validation error: {val_err}")
                    except Exception as err:
                        st.error(f"Error saving portfolio: {err}")


# ==========================================
# SIDEBAR: free-trial allowance (rendered last so it includes this run's usage)
# ==========================================
if using_free_trial():
    _vid = _visitor()
    _email_st = get_limiter().status(_vid, EMAIL)
    _chat_st = get_limiter().status(_vid, CHAT)

    def _left(st_: dict, noun: str) -> str:
        return f"{st_['remaining']}/{st_['limit']} {noun}" if st_["limit"] else f"unlimited {noun}"

    with quota_slot.container(key="cr_quota"):
        st.markdown(f"**Free today:** {_left(_email_st, 'emails')} · {_left(_chat_st, 'chat')}")
        if not (_email_st["limit"] or _chat_st["limit"]):
            pass
        elif _email_st["reason"] == "global" or _chat_st["reason"] == "global":
            st.caption(
                f"Daily free limit for all visitors reached. Back in "
                f"{format_wait(_email_st['global_reset_at'])} "
                f"({format_reset_time(_email_st['global_reset_at'])})."
            )
        elif _email_st["reset_at"]:
            st.caption(
                f"Resets in {format_wait(_email_st['reset_at'])} "
                f"({format_reset_time(_email_st['reset_at'])})."
            )
        else:
            st.caption("Your 24-hour allowance starts with your first free use.")
