import html as _html
import streamlit as st

# Chat avatars (Material icons), styled by the theme below.
AVATAR_USER = ":material/person:"
AVATAR_ASSISTANT = ":material/auto_awesome:"


def apply_theme(theme_name: str = "Light"):
    """Applies the CareerReach light theme: calm surfaces, one blue accent, clear button hierarchy."""
    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&family=Material+Icons&display=swap');

:root {
    --cr-bg: #F5F7FB;
    --cr-surface: #FFFFFF;
    --cr-border: #E2E8F0;
    --cr-border-strong: #CBD5E1;
    --cr-text: #0F172A;
    --cr-body: #334155;
    --cr-muted: #64748B;
    --cr-accent: #2563EB;
    --cr-accent-hover: #1D4ED8;
    --cr-accent-soft: #EEF4FF;
    --cr-accent-line: #BFD3FE;
    --cr-radius: 10px;
    --cr-radius-lg: 14px;
    --cr-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    --cr-shadow-md: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.06);
    --cr-font: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', sans-serif;
}

/* Font on text elements only (never span/div wildcards, which would break icon ligatures) */
html { color-scheme: light; }
html, body, .stApp, p, h1, h2, h3, h4, h5, h6, label, input, textarea, li {
    font-family: var(--cr-font) !important;
}

/* ---------- Page ---------- */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: var(--cr-bg) !important;
    background-image: radial-gradient(1200px 420px at 50% -120px, rgba(37, 99, 235, 0.10), transparent 70%) !important;
    background-repeat: no-repeat !important;
    color: var(--cr-text) !important;
}
[data-testid="stHeader"] {
    background: rgba(245, 247, 251, 0.85) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border-bottom: 1px solid transparent !important;
}
.block-container { padding-top: 4.6rem !important; padding-bottom: 4rem !important; max-width: 1080px !important; }

/* ---------- Type ---------- */
h1, h2, h3, h4, h5, h6 {
    color: var(--cr-text) !important;
    font-weight: 700 !important;
    letter-spacing: -0.018em !important;
    line-height: 1.3 !important;
}
[data-testid="stMain"] h3 { font-size: 1.45rem !important; }
[data-testid="stMain"] h4 { font-size: 1.1rem !important; }
[data-testid="stMain"] h5 { font-size: 0.98rem !important; }
p, li { color: var(--cr-body); line-height: 1.6; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--cr-muted) !important; }
[data-testid="stWidgetLabel"] p { color: var(--cr-body) !important; font-weight: 600 !important; font-size: 0.86rem !important; }
a { color: var(--cr-accent); }
hr { border-color: var(--cr-border) !important; margin: 1.4rem 0 !important; }
code { background: var(--cr-accent-soft) !important; color: #1E40AF !important; border-radius: 6px !important; }

/* ---------- Hero ---------- */
.cr-hero { margin: 0 0 1.8rem 0; font-family: var(--cr-font); }
.cr-brand {
    display: inline-flex; align-items: center; gap: 14px;
    font-weight: 800; font-size: 1.9rem; color: var(--cr-text); letter-spacing: -0.025em; line-height: 1;
    margin-bottom: 1.3rem;
}
.cr-logo {
    width: 46px; height: 46px; border-radius: 13px; background: var(--cr-accent); flex: none;
    display: inline-flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28);
}
.cr-headline {
    font-size: 2.35rem; font-weight: 800; line-height: 1.16; letter-spacing: -0.024em;
    color: var(--cr-text); max-width: 760px; margin: 0 0 0.7rem 0; text-wrap: balance;
}
.cr-headline em { font-style: normal; color: var(--cr-accent); }
.cr-sub { font-size: 1.05rem; line-height: 1.6; color: var(--cr-muted); max-width: 640px; margin: 0 0 1.5rem 0; }
.cr-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0; padding: 0; }
.cr-step {
    display: flex; gap: 12px; align-items: flex-start;
    background: var(--cr-surface); border: 1px solid var(--cr-border); border-radius: var(--cr-radius-lg);
    padding: 14px 16px; box-shadow: var(--cr-shadow); margin: 0;
}
.cr-step-n {
    flex: none; width: 26px; height: 26px; border-radius: 8px;
    background: var(--cr-accent-soft); color: var(--cr-accent); border: 1px solid var(--cr-accent-line);
    font-weight: 700; font-size: 0.82rem; display: flex; align-items: center; justify-content: center;
    font-variant-numeric: tabular-nums;
}
.cr-step-title { font-weight: 700; font-size: 0.92rem; color: var(--cr-text); line-height: 1.35; }
.cr-step-sub { font-size: 0.82rem; color: var(--cr-muted); line-height: 1.45; margin-top: 2px; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: var(--cr-surface) !important;
    border-right: 1px solid var(--cr-border) !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] * { color: var(--cr-body) !important; }
[data-testid="stSidebar"] h3 {
    font-size: 0.74rem !important; font-weight: 700 !important; letter-spacing: 0.08em !important;
    text-transform: uppercase !important; color: var(--cr-muted) !important; padding-bottom: 0.2rem !important;
}
[data-testid="stSidebar"] hr { margin: 0.9rem 0 !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] li { font-size: 0.86rem !important; line-height: 1.5 !important; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: var(--cr-muted) !important; font-size: 0.8rem !important; }
[data-testid="stSidebar"] [data-testid="stRadioCaption"] p,
[data-testid="stSidebar"] [data-testid="stRadioCaption"] { color: var(--cr-muted) !important; font-size: 0.78rem !important; }

/* Free-trial allowance card */
.st-key-cr_quota {
    background: var(--cr-accent-soft) !important; border: 1px solid var(--cr-accent-line) !important;
    border-radius: var(--cr-radius) !important; padding: 10px 12px !important; gap: 0.2rem !important;
}
.st-key-cr_quota p { font-size: 0.86rem !important; }
.st-key-cr_quota strong { color: #1E3A8A !important; }

/* ---------- Buttons: one filled primary, quiet secondary ---------- */
.stButton button, .stDownloadButton button, .stFormSubmitButton button, .stLinkButton a {
    background: var(--cr-surface) !important;
    color: var(--cr-text) !important;
    border: 1px solid var(--cr-border-strong) !important;
    border-radius: var(--cr-radius) !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.5rem 1rem !important;
    min-height: 2.5rem !important;
    box-shadow: var(--cr-shadow) !important;
    transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease !important;
    cursor: pointer !important;
}
.stButton button *, .stDownloadButton button *, .stFormSubmitButton button *, .stLinkButton a * {
    color: inherit !important; font-weight: 600 !important;
}
.stButton button:hover, .stDownloadButton button:hover, .stFormSubmitButton button:hover, .stLinkButton a:hover {
    background: var(--cr-accent-soft) !important;
    border-color: var(--cr-accent) !important;
    color: var(--cr-accent-hover) !important;
}
.stButton button:active, .stDownloadButton button:active, .stFormSubmitButton button:active { transform: translateY(1px) !important; }

.stButton button[kind="primary"], .stFormSubmitButton button[kind="primaryFormSubmit"],
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: var(--cr-accent) !important;
    color: #FFFFFF !important;
    border-color: var(--cr-accent) !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08), 0 4px 12px rgba(37, 99, 235, 0.24) !important;
}
.stButton button[kind="primary"] *, .stFormSubmitButton button[kind="primaryFormSubmit"] *,
[data-testid="stSidebar"] .stButton button[kind="primary"] * { color: #FFFFFF !important; }
.stButton button[kind="primary"]:hover, .stFormSubmitButton button[kind="primaryFormSubmit"]:hover {
    background: var(--cr-accent-hover) !important;
    border-color: var(--cr-accent-hover) !important;
    color: #FFFFFF !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08), 0 6px 16px rgba(37, 99, 235, 0.32) !important;
}
.stButton button:disabled, .stButton button[disabled] {
    background: #EEF2F7 !important; color: #94A3B8 !important; border-color: var(--cr-border) !important;
    box-shadow: none !important; cursor: not-allowed !important;
}
.stButton button:disabled * { color: #94A3B8 !important; }

/* ---------- Inputs ---------- */
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"],
[data-testid="stTextArea"] div:has(> textarea), [data-testid="stNumberInputContainer"],
[data-testid="stSelectbox"] [role="group"],
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
    background-color: var(--cr-surface) !important;
    border: 1px solid var(--cr-border-strong) !important;
    border-radius: var(--cr-radius) !important;
    box-shadow: var(--cr-shadow) !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
[data-testid="stTextInputRootElement"]:focus-within, [data-testid="stTextAreaRootElement"]:focus-within,
[data-testid="stTextArea"] div:has(> textarea):focus-within, [data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stSelectbox"] [role="group"]:focus-within,
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within {
    border-color: var(--cr-accent) !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16) !important;
}
[data-testid="stTextInputField"], [data-testid="stSelectbox"] input, [data-testid="stTextArea"] textarea {
    background-color: transparent !important;
    color: var(--cr-text) !important;
    font-size: 0.94rem !important;
}
[data-testid="stTextArea"] textarea { line-height: 1.6 !important; }
input::placeholder, textarea::placeholder { color: #94A3B8 !important; opacity: 1 !important; }
[data-testid="stSelectbox"] svg { fill: var(--cr-muted) !important; color: var(--cr-muted) !important; }

/* Dropdown menus */
[role="listbox"] {
    background-color: var(--cr-surface) !important;
    border-radius: var(--cr-radius) !important;
}
[role="option"] { color: var(--cr-text) !important; }
[role="option"]:hover, [role="option"][aria-selected="true"], [role="option"][data-focused="true"] { background-color: var(--cr-accent-soft) !important; }

/* ---------- Tabs as a segmented control ---------- */
[data-testid="stTabs"] [role="tablist"] {
    background: #E9EEF6 !important;
    padding: 4px !important;
    border-radius: 12px !important;
    gap: 4px !important;
    display: inline-flex !important;
    width: fit-content !important;
    max-width: 100% !important;
    border: none !important;
    box-shadow: none !important;
    margin-bottom: 0.4rem !important;
}
[data-testid="stTabs"] [role="tablist"]::before, [data-testid="stTabs"] [role="tablist"]::after { display: none !important; }
[data-testid="stTab"] {
    background: transparent !important;
    border: none !important;
    border-radius: 9px !important;
    padding: 8px 16px !important;
    height: auto !important;
    margin: 0 !important;
    transition: background 0.15s ease, color 0.15s ease !important;
}
[data-testid="stTab"] p { color: var(--cr-muted) !important; font-weight: 600 !important; font-size: 0.9rem !important; }
[data-testid="stTab"]:hover p { color: var(--cr-text) !important; }
[data-testid="stTab"][aria-selected="true"] {
    background: var(--cr-surface) !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.10), 0 1px 6px rgba(15, 23, 42, 0.06) !important;
}
[data-testid="stTab"][aria-selected="true"] p { color: var(--cr-text) !important; }
/* Hide the default underline / sliding highlight */
[data-testid="stTab"] > div:not([data-testid="stMarkdownContainer"]),
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none !important; }

/* ---------- Radios ---------- */
[data-testid="stMain"] div[role="radiogroup"][aria-orientation="horizontal"] {
    background: var(--cr-surface) !important;
    padding: 6px 14px !important;
    border-radius: var(--cr-radius) !important;
    border: 1px solid var(--cr-border) !important;
    display: inline-flex !important;
    gap: 18px !important;
    box-shadow: var(--cr-shadow) !important;
}
div[role="radiogroup"] label p { color: var(--cr-text) !important; font-weight: 500 !important; }

/* ---------- Cards: bordered containers, forms, expanders ---------- */
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stForm"], [data-testid="stExpander"] details,
[class*="st-key-cr_card"] {
    background: var(--cr-surface) !important;
    border-color: var(--cr-border) !important;
    border-radius: var(--cr-radius-lg) !important;
    box-shadow: var(--cr-shadow) !important;
}
[data-testid="stForm"], [class*="st-key-cr_card"] { border: 1px solid var(--cr-border) !important; }
.st-key-cr_card_limit { border-color: var(--cr-accent-line) !important; background: var(--cr-accent-soft) !important; }
[data-testid="stExpander"] details { border: 1px solid var(--cr-border) !important; }
[data-testid="stExpander"] summary p { font-weight: 600 !important; font-size: 0.88rem !important; }
[data-testid="stExpander"] summary:hover p { color: var(--cr-accent) !important; }

/* Alerts keep Streamlit's meaning-carrying colours; only the shape is ours */
div[data-testid="stAlert"] { border-radius: var(--cr-radius) !important; }
div[data-testid="stAlert"] p { font-size: 0.92rem !important; }

/* ---------- Badges ---------- */
.badge-glow {
    display: inline-block;
    background: var(--cr-accent-soft);
    color: #1E40AF;
    border: 1px solid var(--cr-accent-line);
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 3px 4px 3px 0;
    font-family: var(--cr-font);
}

.badge-hit { background: #ECFDF3; color: #166534; border-color: #BBF7D0; }
.badge-miss { background: #FFF7ED; color: #9A3412; border-color: #FED7AA; }
.cr-match { font-family: var(--cr-font); font-size: 0.92rem; color: var(--cr-body); margin: 0 0 6px 0; }
.cr-match strong { color: var(--cr-text); }
.cr-match-label { font-family: var(--cr-font); font-size: 0.78rem; font-weight: 600; color: var(--cr-muted); margin: 8px 0 2px 0; }

/* LinkedIn card */
.cr-li-head { display: flex; align-items: center; gap: 10px; font-family: var(--cr-font); margin-bottom: 2px; }
.cr-li-badge {
    width: 26px; height: 26px; border-radius: 6px; background: #0A66C2; color: #FFFFFF;
    font-weight: 800; font-size: 0.95rem; display: inline-flex; align-items: center; justify-content: center;
    font-family: Arial, sans-serif; flex: none; line-height: 1;
}
.cr-li-title { font-weight: 700; font-size: 1.02rem; color: var(--cr-text); }
.cr-li-sub { font-size: 0.82rem; color: var(--cr-muted); }
[class*="st-key-cr_card_li"] { border-color: #BFD9F2 !important; border-left: 4px solid #0A66C2 !important; }

/* ---------- Chat ---------- */
[data-testid="stChatMessage"] {
    background: var(--cr-surface) !important;
    border: 1px solid var(--cr-border) !important;
    border-radius: var(--cr-radius-lg) !important;
    box-shadow: var(--cr-shadow) !important;
    padding: 14px 16px !important;
    margin-bottom: 0.2rem !important;
    gap: 12px !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
[data-testid="stChatMessage"]:has(.cr-user-msg) {
    background: var(--cr-accent-soft) !important;
    border-color: var(--cr-accent-line) !important;
}
[data-testid="stChatMessage"] [data-testid^="stChatMessageAvatar"] {
    background: var(--cr-accent-soft) !important;
    border: 1px solid var(--cr-accent-line) !important;
    border-radius: 9px !important;
    color: var(--cr-accent) !important;
}
[data-testid="stChatMessage"] [data-testid^="stChatMessageAvatar"] * { color: var(--cr-accent) !important; font-size: 1.15rem !important; }
[data-testid="stChatMessage"]:has(.cr-user-msg) [data-testid^="stChatMessageAvatar"] { background: var(--cr-surface) !important; }
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] .cr-user-msg) { display: none !important; }

[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent !important; }
[data-testid="stChatInput"] { background: transparent !important; }
[data-testid="stChatInput"] > div {
    background: var(--cr-surface) !important;
    border: 1px solid var(--cr-border-strong) !important;
    border-radius: var(--cr-radius-lg) !important;
    box-shadow: var(--cr-shadow-md) !important;
}
[data-testid="stChatInput"] > div:focus-within { border-color: var(--cr-accent) !important; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16) !important; }
[data-testid="stChatInput"] textarea { background: transparent !important; color: var(--cr-text) !important; }
[data-testid="stChatInput"] [data-baseweb="textarea"] { border: none !important; box-shadow: none !important; background: transparent !important; }

/* ---------- Loading row ---------- */
@keyframes crShimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
@keyframes crPulse { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }
.skeleton-loader {
    display: flex; align-items: center; gap: 10px;
    background: linear-gradient(90deg, #FFFFFF 25%, var(--cr-accent-soft) 50%, #FFFFFF 75%);
    background-size: 200% 100%;
    animation: crShimmer 2.2s linear infinite;
    border: 1px solid var(--cr-accent-line);
    border-radius: var(--cr-radius);
    padding: 12px 16px;
    margin: 10px 0;
    font-family: var(--cr-font);
    font-size: 0.9rem;
    color: var(--cr-body);
}
.skeleton-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--cr-accent); animation: crPulse 1.2s ease-in-out infinite; flex: none; }

/* ---------- File uploader ---------- */
[data-testid="stFileUploaderDropzone"] {
    background: var(--cr-bg) !important;
    border: 1px dashed var(--cr-border-strong) !important;
    border-radius: var(--cr-radius) !important;
    transition: border-color 0.15s ease, background 0.15s ease !important;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--cr-accent) !important; background: var(--cr-accent-soft) !important; }

[data-testid="stDataFrame"], [data-testid="stTable"] {
    background: var(--cr-surface) !important; border: 1px solid var(--cr-border) !important;
    border-radius: var(--cr-radius-lg) !important; overflow: hidden !important;
}

/* ---------- Icons: keep the ligature font winning ---------- */
[data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stExpandSidebarButton"] span,
[data-testid="stSidebarCollapsedControl"] span,
[data-testid="collapsedControl"] span,
.material-symbols-rounded, .material-icons {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    font-feature-settings: 'liga' !important;
    font-style: normal !important;
    font-weight: normal !important;
    letter-spacing: normal !important;
    line-height: 1 !important;
    text-transform: none !important;
    display: inline-block !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-smoothing: antialiased !important;
}
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="collapsedControl"] button:hover,
[data-testid="stSidebarCollapsedControl"] button:hover { background: var(--cr-accent-soft) !important; border-radius: 8px !important; }

/* ---------- Misc ---------- */
::selection { background: rgba(37, 99, 235, 0.22); }
* { scrollbar-width: thin; scrollbar-color: #CBD5E1 transparent; }
button:focus-visible, [role="tab"]:focus-visible, a:focus-visible {
    outline: 2px solid var(--cr-accent) !important; outline-offset: 2px !important;
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
}
@media (max-width: 820px) {
    .cr-headline { font-size: 1.7rem; }
    .cr-brand { font-size: 1.5rem; gap: 12px; }
    .cr-logo { width: 40px; height: 40px; border-radius: 11px; }
    .cr-sub { font-size: 0.98rem; }
    .cr-steps { grid-template-columns: 1fr; }
    [data-testid="stTabs"] [role="tablist"] { display: flex !important; overflow-x: auto !important; }
    [data-testid="stTab"] { white-space: nowrap !important; }
    .block-container { padding-top: 4rem !important; }
}
</style>"""
    st.markdown(css, unsafe_allow_html=True)


_STEPS = [
    ("Paste a job posting", "A careers page link, or the job description itself."),
    ("We match your work", "The role's skills are matched to your portfolio case studies."),
    ("Get an email and LinkedIn messages", "A tailored email, a LinkedIn connection note and an InMail, ready to edit and send."),
]


def hero(title: str = "CareerReach AI", subtitle: str = ""):
    """Compact page header: brand, what the app does, and the three steps."""
    steps = "".join(
        f'<div class="cr-step"><div class="cr-step-n">{i}</div>'
        f'<div><div class="cr-step-title">{t}</div><div class="cr-step-sub">{s}</div></div></div>'
        for i, (t, s) in enumerate(_STEPS, 1)
    )
    sub = f'<p class="cr-sub">{_html.escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        '<div class="cr-hero">'
        '<div class="cr-brand"><span class="cr-logo">'
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg></span>'
        f'{_html.escape(title)}</div>'
        '<div class="cr-headline" role="heading" aria-level="1">'
        'Turn any job posting into a cold email and LinkedIn message that <em>cite your real work</em>.</div>'
        f'{sub}'
        f'<div class="cr-steps">{steps}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def skeleton(message: str = "Working..."):
    """A slim loading row shown while the AI is working."""
    return f'<div class="skeleton-loader"><span class="skeleton-dot"></span><span>{message}</span></div>'
