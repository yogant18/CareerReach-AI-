import os
import sys
import json
import html
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Add project root to sys.path to enable smooth module importing
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit.components.v1 as components
from app.chains import Chain
from app.portfolio import Portfolio
from app.utils import clean_text, scrape_website

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(root_dir, ".env"))


@st.cache_resource
def get_portfolio_resource():
    csv_path = os.path.join(root_dir, "my_portfolio.csv")
    vector_path = os.path.join(root_dir, "vectorstore")
    return Portfolio(file_path=csv_path, vectorstore_path=vector_path)


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
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# DESIGN SYSTEM: 4 THEMES (MONOCHROME: WHITE, BLACK, GREYS ONLY)
# Paper: white page, light grey cards, black buttons
# Ink: black page, charcoal cards, white buttons
# Graphite: dark grey throughout
# Split: light grey page with a black sidebar
# ---------------------------------------------------------------------------
THEMES = {
    "Paper": {
        "page_bg": "#FFFFFF",
        "card_bg": "#F5F5F5",
        "card_border": "#E5E5E5",
        "text_primary": "#171717",
        "text_muted": "#737373",
        "sidebar_bg": "#FAFAFA",
        "sidebar_border": "#E5E5E5",
        "sidebar_text": "#171717",
        "sidebar_muted": "#737373",
        "btn_bg": "#000000",
        "btn_text": "#FFFFFF",
        "btn_hover": "#262626",
        "input_bg": "#FFFFFF",
        "input_border": "#D4D4D4",
        "input_text": "#171717",
        "shimmer_1": "#E5E5E5",
        "shimmer_2": "#D4D4D4",
    },
    "Ink": {
        "page_bg": "#0A0A0A",
        "card_bg": "#171717",
        "card_border": "#262626",
        "text_primary": "#FAFAFA",
        "text_muted": "#A3A3A3",
        "sidebar_bg": "#0A0A0A",
        "sidebar_border": "#262626",
        "sidebar_text": "#FAFAFA",
        "sidebar_muted": "#A3A3A3",
        "btn_bg": "#FFFFFF",
        "btn_text": "#0A0A0A",
        "btn_hover": "#E5E5E5",
        "input_bg": "#171717",
        "input_border": "#262626",
        "input_text": "#FAFAFA",
        "shimmer_1": "#262626",
        "shimmer_2": "#333333",
    },
    "Graphite": {
        "page_bg": "#1E1E1E",
        "card_bg": "#282828",
        "card_border": "#383838",
        "text_primary": "#EDEDED",
        "text_muted": "#A0A0A0",
        "sidebar_bg": "#181818",
        "sidebar_border": "#333333",
        "sidebar_text": "#EDEDED",
        "sidebar_muted": "#A0A0A0",
        "btn_bg": "#E0E0E0",
        "btn_text": "#121212",
        "btn_hover": "#CCCCCC",
        "input_bg": "#242424",
        "input_border": "#383838",
        "input_text": "#EDEDED",
        "shimmer_1": "#303030",
        "shimmer_2": "#404040",
    },
    "Split": {
        "page_bg": "#F5F5F5",
        "card_bg": "#FFFFFF",
        "card_border": "#E5E5E5",
        "text_primary": "#171717",
        "text_muted": "#737373",
        "sidebar_bg": "#0A0A0A",
        "sidebar_border": "#262626",
        "sidebar_text": "#FAFAFA",
        "sidebar_muted": "#A3A3A3",
        "btn_bg": "#0A0A0A",
        "btn_text": "#FFFFFF",
        "btn_hover": "#262626",
        "input_bg": "#FFFFFF",
        "input_border": "#D4D4D4",
        "input_text": "#171717",
        "shimmer_1": "#E5E5E5",
        "shimmer_2": "#D4D4D4",
    }
}

# Theme selection in sidebar
if "app_theme" not in st.session_state:
    st.session_state["app_theme"] = "Paper"

# Inject dynamic CSS based on active theme
def inject_custom_css(theme_name: str):
    t = THEMES.get(theme_name, THEMES["Paper"])
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&display=swap');

    /* Global Typography & Palette */
    *, *::before, *::after {{
        font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        box-sizing: border-box;
    }}

    :root {{
        --bg-page: {t["page_bg"]};
        --card-bg: {t["card_bg"]};
        --card-border: {t["card_border"]};
        --text-primary: {t["text_primary"]};
        --text-muted: {t["text_muted"]};
        --sidebar-bg: {t["sidebar_bg"]};
        --sidebar-border: {t["sidebar_border"]};
        --sidebar-text: {t["sidebar_text"]};
        --sidebar-muted: {t["sidebar_muted"]};
        --btn-bg: {t["btn_bg"]};
        --btn-text: {t["btn_text"]};
        --btn-hover: {t["btn_hover"]};
        --input-bg: {t["input_bg"]};
        --input-border: {t["input_border"]};
        --input-text: {t["input_text"]};
    }}

    /* Base Body & App View */
    .stApp, [data-testid="stAppViewContainer"] {{
        background-color: var(--bg-page) !important;
        color: var(--text-primary) !important;
    }}

    [data-testid="stHeader"] {{
        background-color: var(--bg-page) !important;
        border-bottom: 1px solid var(--card-border) !important;
    }}

    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }}

    [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {{
        color: var(--sidebar-text) !important;
    }}

    [data-testid="stSidebar"] hr {{
        border-color: var(--sidebar-border) !important;
    }}

    /* Headings — large with tight spacing */
    h1, h2, h3, h4, h5, h6 {{
        color: var(--text-primary) !important;
        font-weight: 700 !important;
        letter-spacing: -0.03em !important;
        line-height: 1.25 !important;
    }}

    /* Main Title with page-load fade motion */
    @keyframes titleFadeIn {{
        0% {{ opacity: 0; transform: translateY(6px); }}
        100% {{ opacity: 1; transform: translateY(0); }}
    }}

    .main-title {{
        font-size: 2.35rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.04em !important;
        color: var(--text-primary) !important;
        margin-bottom: 0.25rem !important;
        animation: titleFadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
    }}

    /* Body Text — 16px, line length under 80 characters */
    p, .stMarkdown p, .sub-title {{
        font-size: 16px !important;
        line-height: 1.6 !important;
        color: var(--text-primary) !important;
        max-width: 78ch !important;
    }}

    .sub-title {{
        color: var(--text-muted) !important;
        font-size: 1.05rem !important;
        margin-bottom: 1.5rem !important;
        max-width: 75ch !important;
    }}

    /* Cards */
    .feature-card {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        padding: 1.25rem !important;
        margin-bottom: 1rem !important;
        max-width: 80ch !important;
    }}

    /* Badges & Chips — strictly monochrome */
    .badge-skill {{
        display: inline-block;
        background-color: var(--card-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--card-border) !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        padding: 4px 10px !important;
        border-radius: 4px !important;
        margin: 2px 4px 2px 0 !important;
    }}

    .quick-chip {{
        display: inline-block;
        background: var(--card-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--card-border) !important;
        padding: 7px 14px !important;
        border-radius: 6px !important;
        font-size: 0.85rem !important;
        margin: 4px !important;
        cursor: pointer;
        transition: transform 0.15s ease, background-color 0.15s ease !important;
    }}

    .quick-chip:hover {{
        transform: translateY(-2px) !important;
        background: var(--card-border) !important;
    }}

    /* Buttons: Button lift on hover, monochrome colors */
    button, .stButton > button, .stDownloadButton > button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {{
        background-color: var(--btn-bg) !important;
        color: var(--btn-text) !important;
        border: 1px solid var(--btn-bg) !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 0.55rem 1.15rem !important;
        cursor: pointer !important;
        transition: transform 0.16s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.16s ease, box-shadow 0.16s ease !important;
    }}

    button:hover, .stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
        transform: translateY(-2px) !important;
        background-color: var(--btn-hover) !important;
        border-color: var(--btn-hover) !important;
        color: var(--btn-text) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12) !important;
    }}

    button:active, .stButton > button:active, .stDownloadButton > button:active {{
        transform: translateY(0) !important;
    }}

    /* Inputs, Textareas, Selectboxes — Smooth transitions */
    input, textarea, select, [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] {{
        background-color: var(--input-bg) !important;
        color: var(--input-text) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 6px !important;
        font-size: 15px !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease !important;
    }}

    input:focus, textarea:focus, select:focus {{
        border-color: var(--text-primary) !important;
        box-shadow: 0 0 0 1px var(--text-primary) !important;
        outline: none !important;
    }}

    /* Tabs Styling & Smooth Transitions */
    div[data-baseweb="tab-list"] {{
        border-bottom: 1px solid var(--card-border) !important;
        gap: 8px !important;
    }}

    button[data-baseweb="tab"] {{
        background-color: transparent !important;
        color: var(--text-muted) !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 0 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 10px 16px !important;
        transition: all 0.2s ease !important;
    }}

    button[data-baseweb="tab"]:hover {{
        color: var(--text-primary) !important;
        transform: none !important;
        box-shadow: none !important;
    }}

    button[data-baseweb="tab"][aria-selected="true"] {{
        color: var(--text-primary) !important;
        border-bottom: 2px solid var(--text-primary) !important;
    }}

    /* Grey Shimmer animation while AI writes */
    @keyframes greyShimmer {{
        0% {{ background-position: -200% 0; }}
        100% {{ background-position: 200% 0; }}
    }}

    .ai-shimmer {{
        background: linear-gradient(90deg, {t["shimmer_1"]} 25%, {t["shimmer_2"]} 50%, {t["shimmer_1"]} 75%);
        background-size: 200% 100%;
        animation: greyShimmer 1.8s infinite linear;
        border-radius: 6px;
        padding: 10px 14px;
        border: 1px solid var(--card-border);
        color: var(--text-muted);
        font-size: 14px;
        margin: 8px 0;
        max-width: 80ch;
    }}

    /* Monochrome Streamlit Alerts & Messages */
    div[data-testid="stAlert"] {{
        background-color: var(--card-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 6px !important;
        max-width: 80ch !important;
    }}

    div[data-testid="stAlert"] * {{
        color: var(--text-primary) !important;
    }}

    /* Chat Messages */
    [data-testid="stChatMessage"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        padding: 1rem !important;
        margin-bottom: 0.75rem !important;
        max-width: 80ch !important;
    }}

    /* Links: Monochrome underline */
    a {{
        color: var(--text-primary) !important;
        text-decoration: underline !important;
    }}

    /* Respect prefers-reduced-motion */
    @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
            animation-duration: 0.001s !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.001s !important;
            scroll-behavior: auto !important;
            transform: none !important;
        }}
        .main-title {{
            animation: none !important;
        }}
        .ai-shimmer {{
            animation: none !important;
        }}
    }}

    /* Mobile Width Optimization (~380px) */
    @media (max-width: 480px) {{
        .block-container {{
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 1.25rem !important;
        }}
        .main-title {{
            font-size: 1.65rem !important;
        }}
        .sub-title {{
            font-size: 0.92rem !important;
        }}
        button, .stButton > button, .stDownloadButton > button {{
            width: 100% !important;
            margin-bottom: 6px !important;
        }}
        p, .stMarkdown p {{
            font-size: 15px !important;
        }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# Render Copy button component (No emojis, monochrome theme)
def render_copy_button(text_to_copy: str, key_suffix: str, label: str = "Copy Email"):
    t = THEMES.get(st.session_state.get("app_theme", "Paper"), THEMES["Paper"])
    safe_text = json.dumps(text_to_copy)
    btn_id = f"cp_{key_suffix}"
    
    html_code = f"""
    <div style="margin-top: 4px; margin-bottom: 8px; font-family: 'Manrope', -apple-system, sans-serif;">
        <button id="{btn_id}" onclick="doCopy_{btn_id}()" style="
            background-color: {t['btn_bg']};
            color: {t['btn_text']};
            border: 1px solid {t['card_border']};
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 600;
            font-family: 'Manrope', -apple-system, sans-serif;
            cursor: pointer;
            transition: transform 0.16s ease, background-color 0.16s ease;
        ">{label}</button>
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
    components.html(html_code, height=48)


# Sidebar Configurations
with st.sidebar:
    st.markdown("### Settings")

    # Theme Switcher (Paper, Ink, Graphite, Split)
    selected_theme = st.selectbox(
        "Theme",
        options=["Paper", "Ink", "Graphite", "Split"],
        index=["Paper", "Ink", "Graphite", "Split"].index(st.session_state.get("app_theme", "Paper")),
        key="theme_selector"
    )
    if selected_theme != st.session_state.get("app_theme"):
        st.session_state["app_theme"] = selected_theme
        st.rerun()

    st.markdown("---")
    st.markdown("### Model & Creativity")
    selected_model = st.selectbox(
        "Groq Model",
        options=[
            "openai/gpt-oss-120b",
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-20b"
        ],
        index=0
    )
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)

    st.markdown("---")
    st.markdown("### Sender Profile")
    sender_name = st.text_input("Your / Sender Name", value="", placeholder="Alex Johnson")
    company_name = st.text_input("Your Company", value="", placeholder="Acme AI Consulting")
    sender_role = st.text_input("Your Role", value="Business Development Executive")
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
    if "portfolio_instance" not in st.session_state:
        st.session_state.portfolio_instance = get_portfolio_resource()
    portfolio = st.session_state.portfolio_instance
    doc_count = portfolio.collection.count()
    st.markdown(f"**Portfolio Database**: `{doc_count}` items indexed.")
    if st.button("Reload Portfolio Data"):
        portfolio.load_portfolio(force_reload=True)
        st.success("Vector store refreshed.")
        st.rerun()

# Apply CSS for chosen theme
inject_custom_css(st.session_state["app_theme"])

# Helper function to get chain (silently reads server secrets / environment)
def get_chain():
    key = ""
    try:
        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            key = str(st.secrets["GROQ_API_KEY"]).strip()
    except Exception:
        pass
    if not key:
        key = os.getenv("GROQ_API_KEY", "DEMO_MODE").strip()

    try:
        return Chain(api_key=key, model_name=selected_model, temperature=temperature)
    except Exception as e:
        st.error(f"Error initializing Groq LLM: {e}")
        return None


# Top App Header (Manrope, large tight spacing, page-load fade motion, no emoji in title)
st.markdown('<div class="main-title">CareerReach AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">AI-powered B2B cold outreach & portfolio matching with conversational strategy assistant.</div>',
    unsafe_allow_html=True
)

# Demo-mode banner: shown once, before tabs, only when key is absent/invalid
_probe_chain = get_chain()
if _probe_chain and _probe_chain.is_demo_mode:
    st.warning(
        "Demo Mode — AI features are disabled. "
        "No valid Groq API key was found. All outputs will use built-in templates. "
        "Add your key to app/.env (local) or Streamlit Secrets (cloud), then refresh."
    )

# Tabs Navigation — no emoji in tabs
tab_email, tab_chat, tab_portfolio = st.tabs([
    "Cold Email Generator",
    "Interactive AI Chatbot",
    "Portfolio Vector Store"
])


# ==========================================
# TAB 1: COLD EMAIL GENERATOR
# ==========================================
with tab_email:
    st.markdown("### Generate Job-Tailored Cold Emails")
    st.write(
        "Extract job postings from any career page URL or paste the job description directly. "
        "CareerReach AI will match relevant portfolio case studies and draft an outreach email."
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
                placeholder="https://jobs.nike.com/job/R-33460"
            )
        with col_example:
            st.write("")
            st.write("")
            if st.button("Use Sample URL"):
                url_input = "https://jobs.nike.com/job/R-33460"
                st.session_state["sample_url"] = url_input

        if "sample_url" in st.session_state and not url_input:
            url_input = st.session_state["sample_url"]

        submit_btn = st.button("Extract & Generate Email", type="primary")

        if submit_btn:
            if not url_input.strip():
                st.warning("Please provide a valid URL.")
            else:
                st.markdown('<div class="ai-shimmer">Scraping webpage and parsing job listings...</div>', unsafe_allow_html=True)
                with st.spinner("Processing..."):
                    try:
                        scraped_content = scrape_website(url_input.strip())
                        if not scraped_content:
                            st.error("No readable text could be retrieved from the given URL. Try pasting the job description directly.")
                        else:
                            run_generation = True
                    except Exception as err:
                        st.error(f"Web scraping error: {err}. You can switch to 'Paste Job Description Directly' to proceed.")

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

    # Processing Generation
    if run_generation and scraped_content:
        if not sender_name.strip() or not company_name.strip():
            st.error("Please fill in both Sender Name and Company in the sidebar before generating emails.")
        else:
            chain = get_chain()
            if not chain:
                st.error("Please configure a valid Groq API Key to generate cold emails.")
            else:
                st.markdown('<div class="ai-shimmer">Analyzing job requirements and matching portfolio case studies...</div>', unsafe_allow_html=True)
                with st.spinner("Processing..."):
                    try:
                        jobs = chain.extract_jobs(scraped_content)

                        # Show fallback notice and real error when AI step failed
                        fallback_note = getattr(chain, "fallback_notice", None)
                        err_note = getattr(chain, "last_error", None)
                        is_demo = getattr(chain, "is_demo_mode", False)
                        if fallback_note:
                            st.info(fallback_note)
                        if err_note and not is_demo:
                            st.warning(
                                f"AI extraction failed and built-in parser was used.  \n"
                                f"**Error:** `{err_note}`"
                            )

                        if not jobs:
                            st.warning("No specific job roles could be identified in the text.")
                            # Empty state: one clear button
                            if st.button("Try Sample Job Description", key="empty_jobs_retry"):
                                st.session_state["sample_url"] = "https://jobs.nike.com/job/R-33460"
                                st.rerun()
                        else:
                            total_found = len(jobs)
                            if total_found > 3:
                                st.info(
                                    f"Found {total_found} job roles — showing the first 3. "
                                    f"Paste a more specific job description to target individual roles."
                                )
                                jobs = jobs[:3]

                            st.success(f"Successfully identified {len(jobs)} job role(s).")

                            for idx, job in enumerate(jobs, 1):
                                role = job.get("role", f"Role #{idx}")
                                experience = job.get("experience", "Not specified")
                                skills = job.get("skills", [])
                                desc = job.get("description", "")

                                st.markdown(f"#### Job #{idx}: {role}")
                                
                                col_meta1, col_meta2 = st.columns([1, 2])
                                with col_meta1:
                                    st.markdown(f"**Experience:** {experience}")
                                    st.markdown(f"**Summary:** {desc[:250]}..." if len(desc) > 250 else f"**Summary:** {desc}")
                                with col_meta2:
                                    st.markdown("**Detected Skills:**")
                                    if skills:
                                        skill_badges = "".join([f'<span class="badge-skill">{html.escape(str(s))}</span>' for s in skills])
                                        st.markdown(skill_badges, unsafe_allow_html=True)
                                    else:
                                        st.write("None detected.")

                                # Retrieve matching portfolio links for cold email generation
                                portfolio = st.session_state.portfolio_instance
                                matched_links = portfolio.query_links(skills)

                                # Generate Cold Email with Grey shimmer indicator
                                st.markdown(f'<div class="ai-shimmer">Writing personalized outreach email for {role}...</div>', unsafe_allow_html=True)
                                with st.spinner("Drafting..."):
                                    user_profile_tone = email_tone
                                    email_text = chain.write_mail(
                                        job=job,
                                        links=matched_links,
                                        sender_name=sender_name,
                                        company_name=company_name,
                                        sender_role=sender_role,
                                        tone=user_profile_tone,
                                        max_words=max_words_selected
                                    )

                                    # Show fallback/error info for write_mail step
                                    fallback_note = getattr(chain, "fallback_notice", None)
                                    err_note = getattr(chain, "last_error", None)
                                    is_demo = getattr(chain, "is_demo_mode", False)
                                    if fallback_note:
                                        st.info(fallback_note)
                                    if err_note and not is_demo:
                                        st.warning(
                                            f"AI email generation failed; built-in template used.  \n"
                                            f"**Error:** `{err_note}`"
                                        )

                                    st.markdown("##### Generated Cold Email:")
                                    st.text_area(
                                        label=f"Cold Email for {role}",
                                        value=email_text,
                                        height=300,
                                        key=f"email_{idx}"
                                    )

                                    # Word count display & threshold warning
                                    email_word_count = len(email_text.split())
                                    if email_word_count > max_words_selected:
                                        st.warning(
                                            f"Word Count: {email_word_count} words "
                                            f"(exceeds target limit of {max_words_selected} words)."
                                        )
                                    else:
                                        st.caption(
                                            f"Word Count: {email_word_count} / {max_words_selected} words."
                                        )

                                    # Every output has a Copy button & download button
                                    col_copy, col_download = st.columns([1, 3])
                                    with col_copy:
                                        render_copy_button(email_text, key_suffix=f"mail_{idx}", label="Copy Email")
                                    with col_download:
                                        st.download_button(
                                            label="Download Email (.txt)",
                                            data=email_text,
                                            file_name=f"cold_email_{role.lower().replace(' ', '_')}.txt",
                                            mime="text/plain",
                                            key=f"dl_{idx}"
                                        )
                                st.markdown("---")

                    except Exception as err:
                        st.error(f"Error generating email: {str(err)}")


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

    # Quick Action Prompt Chips (No emojis)
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
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant":
                    render_copy_button(msg["content"], key_suffix=f"chat_msg_{idx}", label="Copy Response")

    # Handle New Chat Input
    user_query = st.chat_input("Type your question or outreach request here...")
    
    # Check if a quick prompt chip was pressed
    if suggested_prompt and not user_query:
        user_query = suggested_prompt

    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Generate Assistant response
        chain = get_chain()
        if not chain:
            error_msg = "Please enter a valid Groq API Key in the sidebar to talk with the chatbot."
            st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
            with st.chat_message("assistant"):
                st.warning(error_msg)
        else:
            with st.chat_message("assistant"):
                st.markdown('<div class="ai-shimmer">Formulating outreach strategy...</div>', unsafe_allow_html=True)
                with st.spinner("Thinking..."):
                    try:
                        portfolio_df = st.session_state.portfolio_instance.get_all_portfolios()
                        portfolio_summary = portfolio_df.to_string(index=False)
                        
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

                        chat_fallback = getattr(chain, "fallback_notice", None)
                        chat_err = getattr(chain, "last_error", None)
                        chat_demo = getattr(chain, "is_demo_mode", False)
                        if chat_fallback:
                            st.info(chat_fallback)
                        if chat_err and not chat_demo:
                            st.warning(
                                f"AI call failed; built-in response used.  \n"
                                f"**Error:** `{chat_err}`"
                            )
                        st.markdown(response)
                        render_copy_button(response, key_suffix=f"chat_reply_{len(st.session_state.chat_history)}", label="Copy Response")
                        st.session_state.chat_history.append({"role": "assistant", "content": response})
                    except Exception as chat_err:
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
        "Browse indexed client case studies and tech stacks. "
        "Query ChromaDB semantic search or register new case studies."
    )

    col_view, col_add = st.columns([3, 2])

    with col_view:
        st.subheader("Current Indexed Portfolios")
        portfolio = st.session_state.portfolio_instance
        df_port = portfolio.get_all_portfolios()
        st.dataframe(df_port, hide_index=True)

        st.markdown("---")
        st.subheader("Test Semantic Search")
        search_query = st.text_input(
            "Enter skills or tech query (e.g. 'Kubernetes cloud deployment', 'iOS ARKit')",
            value="Machine Learning Python"
        )
        if st.button("Search Vector DB"):
            matches = portfolio.query_links(search_query, n_results=3)
            if matches:
                st.write("**Matching Links Found:**")
                for i, m in enumerate(matches):
                    link_url = m.get('links', '')
                    st.markdown(f"- [{link_url}]({link_url})")
                    render_copy_button(link_url, key_suffix=f"link_{i}", label="Copy Link")
            else:
                st.info("No matching portfolio entries found.")
                # Empty state: one clear button
                if st.button("Reset Search Query", key="empty_search_reset"):
                    st.rerun()

    with col_add:
        st.subheader("Add Portfolio Item")
        with st.form("add_portfolio_form"):
            new_techstack = st.text_input("Techstack / Skills (e.g. Next.js, FastAPI, PostgreSQL)")
            new_link = st.text_input("Portfolio / Case Study URL", placeholder="https://github.com/your-username/repo")
            submitted = st.form_submit_button("Add to Database", type="primary")

            if submitted:
                if not new_techstack.strip() or not new_link.strip():
                    st.warning("Please fill in both Techstack and Link fields.")
                else:
                    try:
                        success = portfolio.add_portfolio(new_techstack, new_link)
                        if success:
                            st.success(f"Added '{new_techstack}' to portfolio.")
                            st.rerun()
                        else:
                            st.error("Failed to add portfolio.")
                    except ValueError as val_err:
                        st.warning(f"Validation error: {val_err}")
                    except Exception as err:
                        st.error(f"Error saving portfolio: {err}")
