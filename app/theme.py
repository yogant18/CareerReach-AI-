import streamlit as st

def theme_picker():
    """Renders theme selector dropdown in sidebar."""
    options = ["Classic Dark (Linear/Simpliflow)", "Paper", "Ink", "Graphite"]
    default_index = 0
    chosen = st.selectbox("Theme", options=options, index=default_index, key="theme_picker_select")
    return chosen

def apply_theme(theme_name: str = "Classic Dark"):
    """Applies high-end SaaS dark aesthetic matching modern AI tools like Simpliflow & Linear."""
    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&family=Material+Icons&display=swap');

/* Restrict app font strictly to text elements — never span, div, button or wildcard */
html { color-scheme: light; }
html, body, .stApp, p, h1, h2, h3, h4, label, input, textarea {
    font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif !important;
}

/* Overall Dark Mesh & Particle Glow Background */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #EAF2FF !important;
    background-image: 
        radial-gradient(circle at 50% -10%, rgba(59, 130, 246, 0.16) 0%, transparent 50%),
        radial-gradient(circle at 85% 15%, rgba(37, 99, 235, 0.12) 0%, transparent 40%),
        radial-gradient(circle at 15% 45%, rgba(14, 165, 233, 0.10) 0%, transparent 45%),
        linear-gradient(rgba(15, 23, 42, 0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(15, 23, 42, 0.015) 1px, transparent 1px) !important;
    background-size: 100% 100%, 100% 100%, 100% 100%, 48px 48px, 48px 48px !important;
    background-attachment: fixed !important;
    color: #0F172A !important;
}

[data-testid="stHeader"] {
    background: rgba(255, 255, 255, 0.7) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border-bottom: 1px solid rgba(15, 23, 42, 0.06) !important;
}

/* Premium Sleek Sidebar */
[data-testid="stSidebar"] {
    background: #F3F8FF !important;
    border-right: 1px solid rgba(15, 23, 42, 0.08) !important;
    box-shadow: 4px 0 24px rgba(15, 23, 42, 0.088) !important;
}

[data-testid="stSidebar"] * {
    color: #334155 !important;
}

[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #0F172A !important;
    letter-spacing: -0.02em !important;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    color: #0F172A !important;
    font-weight: 700 !important;
    letter-spacing: -0.035em !important;
    line-height: 1.25 !important;
}

p, span, label, div {
    color: #475569;
}

/* Hero Pill Badge */
.hero-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(59, 130, 246, 0.12);
    border: 1px solid rgba(37, 99, 235, 0.35);
    color: #1D4ED8 !important;
    padding: 6px 18px;
    border-radius: 9999px;
    font-size: 0.84rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    margin-bottom: 1.4rem;
    box-shadow: 0 0 25px rgba(37, 99, 235, 0.22);
    animation: pillPulse 3s infinite ease-in-out;
}

@keyframes pillPulse {
    0%, 100% { box-shadow: 0 0 20px rgba(37, 99, 235, 0.2); }
    50% { box-shadow: 0 0 32px rgba(37, 99, 235, 0.4); }
}

/* Hero Section */
.hero-container {
    text-align: center;
    padding: 2rem 1.5rem 2.2rem 1.5rem;
    max-width: 980px;
    margin: 0 auto;
    position: relative;
}

.hero-title {
    font-size: 3.4rem;
    font-weight: 800;
    letter-spacing: -0.045em;
    line-height: 1.14;
    color: #0F172A !important;
    margin-bottom: 1.15rem;
    text-shadow: 0 2px 20px rgba(15, 23, 42, 0.154);
}

.hero-title-gradient {
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 50%, #0EA5E9 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: inline-block;
    
}

.hero-sub {
    font-size: 1.18rem;
    color: #475569 !important;
    line-height: 1.65;
    max-width: 640px;
    margin: 0 auto 1.5rem auto;
}

.hero-mcp-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(15, 23, 42, 0.05);
    border: 1px solid rgba(15, 23, 42, 0.12);
    color: #1E293B !important;
    padding: 7px 20px;
    border-radius: 10px;
    font-size: 0.88rem;
    font-weight: 600;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.088);
    margin-bottom: 1.5rem;
}

/* Interactive Orbit Stage (Simpliflow centerpiece) */
.orbit-stage {
    margin: 1rem auto 2.2rem auto;
    max-width: 880px;
    height: 310px;
    position: relative;
    background: radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.18) 0%, transparent 72%);
    border: 1px solid rgba(15, 23, 42, 0.09);
    border-radius: 24px;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 25px 60px rgba(15, 23, 42, 0.143), inset 0 1px 0 rgba(15, 23, 42, 0.12);
}

.orbit-ring {
    position: absolute;
    border-radius: 50%;
    border: 1px dashed rgba(37, 99, 235, 0.25);
}
.orbit-ring-1 { width: 140px; height: 140px; }
.orbit-ring-2 { width: 280px; height: 280px; border-color: rgba(14, 165, 233, 0.22); }
.orbit-ring-3 { width: 440px; height: 440px; border-color: rgba(15, 23, 42, 0.07); }

.orbit-core {
    width: 68px;
    height: 68px;
    border-radius: 50%;
    background: linear-gradient(135deg, #2563EB 0%, #0EA5E9 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 30px rgba(37, 99, 235, 0.35), inset 0 1px 2px rgba(255, 255, 255, 0.6);
    z-index: 2;
    animation: corePulse 3s infinite ease-in-out;
}

@keyframes corePulse {
    0%, 100% { transform: scale(1); box-shadow: 0 0 35px rgba(37, 99, 235, 0.8); }
    50% { transform: scale(1.05); box-shadow: 0 0 50px rgba(37, 99, 235, 0.95); }
}

/* Rich Micro-Card Nodes */
.orbit-node {
    position: absolute;
    padding: 8px 14px;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(15, 23, 42, 0.14);
    border-radius: 12px;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.143), inset 0 1px 0 rgba(15, 23, 42, 0.08);
    display: flex;
    align-items: center;
    gap: 10px;
    z-index: 3;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    cursor: default;
    backdrop-filter: blur(12px);
}

.orbit-node:hover {
    transform: translateY(-3px) scale(1.02);
    border-color: rgba(37, 99, 235, 0.5);
    box-shadow: 0 16px 36px rgba(37, 99, 235, 0.35);
}

.orbit-icon-box {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.95rem;
}

.orbit-node-title {
    font-size: 0.82rem;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.2;
}

.orbit-node-sub {
    font-size: 0.70rem;
    color: #475569;
    line-height: 1.2;
}

/* Glow Buttons */
.stButton > button, button[kind="primary"], .stDownloadButton > button {
    background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(96, 165, 250, 0.35) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.94rem !important;
    padding: 0.65rem 1.45rem !important;
    box-shadow: 0 4px 22px rgba(37, 99, 235, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    cursor: pointer !important;
}

.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px rgba(37, 99, 235, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.35) !important;
    border-color: rgba(147, 197, 253, 0.6) !important;
}

.stButton > button:active, .stDownloadButton > button:active {
    transform: translateY(0) !important;
}

/* Modern Inputs, Text Areas, Number Inputs & Selectboxes — All Layers Unified */
input, textarea, select,
[data-baseweb="input"], [data-baseweb="input"] > div, [data-baseweb="input"] input,
[data-baseweb="textarea"], [data-baseweb="textarea"] > div, [data-baseweb="textarea"] textarea,
[data-baseweb="select"], [data-baseweb="select"] > div, [data-baseweb="select"] > div > div {
    background-color: rgba(255, 255, 255, 0.95) !important;
    color: #0F172A !important;
    border-color: rgba(15, 23, 42, 0.12) !important;
    border-radius: 10px !important;
    font-size: 0.95rem !important;
}

[data-baseweb="select"] svg {
    fill: #334155 !important;
    color: #334155 !important;
}

/* Dropdown popover menu list */
div[data-baseweb="popover"], div[data-baseweb="popover"] > div,
ul[role="listbox"], li[role="option"] {
    background-color: #0F172A !important;
    color: #0F172A !important;
    border-color: rgba(15, 23, 42, 0.12) !important;
}

li[role="option"]:hover, li[role="option"][aria-selected="true"] {
    background-color: rgba(37, 99, 235, 0.22) !important;
    color: #0F172A !important;
}

input:focus, textarea:focus, [data-baseweb="select"]:focus {
    background-color: rgba(255, 255, 255, 0.95) !important;
    border-color: #2563EB !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.3) !important;
}

/* Segmented Capsule Tabs */
div[data-baseweb="tab-list"] {
    background: rgba(255, 255, 255, 0.75) !important;
    padding: 6px !important;
    border-radius: 14px !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    gap: 6px !important;
    max-width: 680px !important;
    margin: 0 auto 2.2rem auto !important;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.088), inset 0 1px 0 rgba(15, 23, 42, 0.04) !important;
}

button[data-baseweb="tab"] {
    background: transparent !important;
    color: #475569 !important;
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    padding: 9px 20px !important;
    border: none !important;
    transition: all 0.2s ease !important;
}

button[data-baseweb="tab"]:hover {
    color: #0F172A !important;
    background: rgba(15, 23, 42, 0.04) !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: rgba(37, 99, 235, 0.22) !important;
    color: #0F172A !important;
    border: 1px solid rgba(37, 99, 235, 0.45) !important;
    box-shadow: 0 4px 18px rgba(37, 99, 235, 0.22), inset 0 1px 0 rgba(15, 23, 42, 0.15) !important;
}

/* Radio buttons as Segmented Pills */
div[role="radiogroup"] {
    background: rgba(255, 255, 255, 0.6) !important;
    padding: 6px 12px !important;
    border-radius: 12px !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    display: inline-flex !important;
    gap: 16px !important;
    margin-bottom: 1rem !important;
}

div[role="radiogroup"] label {
    color: #1E293B !important;
    font-weight: 500 !important;
}

/* Badges */
.badge-glow {
    display: inline-block;
    background: rgba(37, 99, 235, 0.16);
    color: #1E40AF;
    border: 1px solid rgba(37, 99, 235, 0.35);
    padding: 4px 12px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    margin: 3px;
    box-shadow: 0 0 12px rgba(37, 99, 235, 0.18);
}

/* Chat Messages Glass */
[data-testid="stChatMessage"] {
    background: rgba(255, 255, 255, 0.6) !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(16px) !important;
    box-shadow: 0 10px 25px rgba(15, 23, 42, 0.077) !important;
    margin-bottom: 0.9rem !important;
}

/* Streamlit Alert customization */
div[data-testid="stAlert"] {
    background: rgba(255, 255, 255, 0.85) !important;
    border: 1px solid rgba(37, 99, 235, 0.25) !important;
    border-radius: 12px !important;
    color: #1E293B !important;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.088) !important;
}

div[data-testid="stAlert"] * {
    color: #1E293B !important;
}

/* Custom Skeleton Shimmer */
@keyframes darkPulse {
    0% { opacity: 0.45; background-position: -200% 0; }
    100% { opacity: 1; background-position: 200% 0; }
}
.skeleton-loader {
    background: linear-gradient(90deg, rgba(15, 23, 42, 0.03) 25%, rgba(168,85,247,0.12) 50%, rgba(15, 23, 42, 0.03) 75%);
    background-size: 200% 100%;
    animation: darkPulse 1.8s infinite;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 10px 0;
    border: 1px solid rgba(37, 99, 235, 0.2);
}

/* Ensure Material Symbols are strictly applied at the end so icon ligature font wins */
[data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stExpandSidebarButton"],
[data-testid="stExpandSidebarButton"] button,
[data-testid="stExpandSidebarButton"] span,
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stSidebarCollapsedControl"] span,
[data-testid="collapsedControl"],
[data-testid="collapsedControl"] button,
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
    color: #2563EB !important;
    font-size: 1.5rem !important;
}

/* Minimalist Glassmorphism (Vercel) Cards & Lists */
.glass-panel {
    background: rgba(255, 255, 255, 0.6) !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    border-radius: 16px !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    padding: 1.4rem !important;
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.099) !important;
    margin-bottom: 1.2rem !important;
}

.portfolio-glass-card {
    background: rgba(255, 255, 255, 0.5) !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    border-radius: 12px !important;
    padding: 12px 18px !important;
    margin-bottom: 10px !important;
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    transition: transform 0.2s ease, border-color 0.2s ease !important;
}

.portfolio-glass-card:hover {
    transform: translateY(-2px) !important;
    border-color: rgba(37, 99, 235, 0.4) !important;
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.2) !important;
}

/* Streamlit Dataframe Dark Override */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    background: rgba(255, 255, 255, 0.7) !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
}

[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="collapsedControl"] button:hover,
[data-testid="stSidebarCollapsedControl"] button:hover {
    background: rgba(37, 99, 235, 0.18) !important;
    border-radius: 8px !important;
}

/* ---- Polish ---- */
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent !important; }
[data-testid="stChatInput"], [data-testid="stChatInput"] > div { background: #FFFFFF !important; border-color: rgba(37, 99, 235, 0.25) !important; border-radius: 14px !important; }
[data-testid="stChatInput"] textarea { background: transparent !important; color: #0F172A !important; }
input::placeholder, textarea::placeholder { color: #64748B !important; opacity: 1 !important; }
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] { border: 1px solid rgba(37, 99, 235, 0.22) !important; }

/* Keep white text on gradient buttons (sidebar wildcard would darken it) */
.stButton > button *, .stDownloadButton > button *, button[kind="primary"] *,
[data-testid="stSidebar"] .stButton > button, [data-testid="stSidebar"] .stButton > button * { color: #FFFFFF !important; }
.stButton > button:hover { color: #FFFFFF !important; }
.orbit-core svg { stroke: #FFFFFF; }
[data-testid="stSidebar"] { box-shadow: 4px 0 24px rgba(15, 23, 42, 0.05) !important; }

.hero-dot { width: 7px; height: 7px; border-radius: 50%; background: #2563EB; box-shadow: 0 0 10px #2563EB; display: inline-block; }
.orbit-icon-box svg { display: block; }
.block-container { padding-top: 2rem !important; max-width: 1100px !important; }

::selection { background: rgba(37, 99, 235, 0.4); color: #fff; }

* { scrollbar-width: thin; scrollbar-color: rgba(37, 99, 235, 0.35) transparent; }

/* Gradient hairline on top of the orbit stage */
.orbit-stage::before {
    content: ""; position: absolute; top: 0; left: 15%; right: 15%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(96, 165, 250, 0.8), transparent);
}

/* Slow rotation for outer rings */
.orbit-ring-3 { animation: ringSpin 60s linear infinite; }
.orbit-ring-2 { animation: ringSpin 40s linear infinite reverse; }
@keyframes ringSpin { to { transform: rotate(360deg); } }

/* Staggered float on nodes */
.orbit-node:nth-of-type(5) { animation: nodeFloat 6s ease-in-out infinite; }
.orbit-node:nth-of-type(6) { animation: nodeFloat 7s ease-in-out infinite .5s; }
.orbit-node:nth-of-type(7) { animation: nodeFloat 6.5s ease-in-out infinite 1s; }
.orbit-node:nth-of-type(8) { animation: nodeFloat 7.5s ease-in-out infinite 1.5s; }
.orbit-node:nth-of-type(9) { animation: nodeFloat 6s ease-in-out infinite 2s; }
.orbit-node:nth-of-type(10) { animation: nodeFloat 7s ease-in-out infinite 2.5s; }
@keyframes nodeFloat { 0%,100% { translate: 0 0; } 50% { translate: 0 -5px; } }

/* Subtle gradient border on chat messages + expanders */
[data-testid="stExpander"] {
    background: rgba(255, 255, 255, 0.55) !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    border-radius: 14px !important;
}
[data-testid="stExpander"]:hover { border-color: rgba(37, 99, 235, 0.35) !important; }

/* File uploader */
[data-testid="stFileUploaderDropzone"] {
    background: rgba(255, 255, 255, 0.6) !important;
    border: 1px dashed rgba(37, 99, 235, 0.4) !important;
    border-radius: 14px !important;
    transition: border-color .2s ease, background .2s ease !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #2563EB !important;
    background: rgba(37, 99, 235, 0.08) !important;
}

/* Bordered containers (replace unbalanced glass-panel divs) */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
    border-radius: 16px;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"], [data-testid="stForm"] {
    background: rgba(255, 255, 255, 0.6) !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    border-radius: 16px !important;
}

.portfolio-glass-card a { word-break: break-all; }

/* Keyboard focus visibility */
button:focus-visible, [role="tab"]:focus-visible {
    outline: 2px solid #2563EB !important; outline-offset: 2px !important;
}

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
}

/* Responsive: stack the orbit nodes on small screens */
@media (max-width: 820px) {
    .hero-title { font-size: 2.2rem; }
    .hero-sub { font-size: 1rem; }
    .orbit-stage {
        height: auto; flex-direction: column; gap: 10px; padding: 18px 14px;
    }
    .orbit-ring { display: none; }
    .orbit-core { display: none; }
    .orbit-node {
        position: static !important; width: 100%; box-sizing: border-box; animation: none !important;
    }
    div[data-baseweb="tab-list"] { max-width: 100% !important; overflow-x: auto !important; }
}
</style>"""
    st.markdown(css, unsafe_allow_html=True)

def hero(title: str = "CareerReach AI", subtitle: str = "AI-powered B2B cold outreach & portfolio matching"):
    """Renders the luxury Simpliflow & Linear hero with 6 attractive agent nodes."""
    orbit_html = (
        '<div class="hero-container">'
        '<div class="hero-pill"><span class="hero-dot"></span> All the tools your outreach will ever need</div>'
        f'<div class="hero-title">Introducing <span class="hero-title-gradient">{title}</span><br>Your Intelligent Outreach Studio</div>'
        f'<div class="hero-sub">{subtitle}</div>'
        '<div class="hero-mcp-badge"><span style="color: #2563EB;">●</span> Autonomous Agent Pipeline Ready</div>'
        '<div class="orbit-stage">'
        '<div class="orbit-ring orbit-ring-3"></div>'
        '<div class="orbit-ring orbit-ring-2"></div>'
        '<div class="orbit-ring orbit-ring-1"></div>'
        '<div class="orbit-core">'
        '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>'
        '</svg>'
        '</div>'
        
        # Node 1: Ultra-Fast AI (Top Left)
        '<div class="orbit-node" style="top: 24px; left: 60px;">'
        '<div class="orbit-icon-box" style="background: rgba(234, 88, 12, 0.15); color: #FB923C;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></div>'
        '<div><div class="orbit-node-title">Ultra-Fast LLMs</div><div class="orbit-node-sub">Groq LPU Engine</div></div>'
        '</div>'
        
        # Node 2: Career Scraper (Top Center Right)
        '<div class="orbit-node" style="top: 24px; right: 60px;">'
        '<div class="orbit-icon-box" style="background: rgba(14, 165, 233, 0.15); color: #38BDF8;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15 15 0 0 1 0 20a15 15 0 0 1 0-20"/></svg></div>'
        '<div><div class="orbit-node-title">Live URL Extractor</div><div class="orbit-node-sub">Instant JD Parsing</div></div>'
        '</div>'
        
        # Node 3: Semantic Matcher (Mid Left)
        '<div class="orbit-node" style="top: 130px; left: 30px;">'
        '<div class="orbit-icon-box" style="background: rgba(37, 99, 235, 0.15); color: #2563EB;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 7l3 3M17 7l-3 3M7 17l3-3M17 17l-3-3"/></svg></div>'
        '<div><div class="orbit-node-title">Semantic RAG</div><div class="orbit-node-sub">ChromaDB Vector</div></div>'
        '</div>'
        
        # Node 4: Conversational Strategist (Mid Right)
        '<div class="orbit-node" style="top: 130px; right: 30px;">'
        '<div class="orbit-icon-box" style="background: rgba(236, 72, 153, 0.15); color: #F472B6;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V4"/><circle cx="9" cy="14" r="1"/><circle cx="15" cy="14" r="1"/></svg></div>'
        '<div><div class="orbit-node-title">Strategy Copilot</div><div class="orbit-node-sub">Interactive Advisor</div></div>'
        '</div>'
        
        # Node 5: Cold Email Synthesis (Bottom Left)
        '<div class="orbit-node" style="bottom: 24px; left: 80px;">'
        '<div class="orbit-icon-box" style="background: rgba(34, 197, 94, 0.15); color: #15803D;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><polyline points="3 7 12 13 21 7"/></svg></div>'
        '<div><div class="orbit-node-title">Hyper-Personalized</div><div class="orbit-node-sub">B2B Pitch Synthesis</div></div>'
        '</div>'
        
        # Node 6: Portfolio Proof Engine (Bottom Right)
        '<div class="orbit-node" style="bottom: 24px; right: 80px;">'
        '<div class="orbit-icon-box" style="background: rgba(245, 158, 11, 0.15); color: #FBBF24;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/></svg></div>'
        '<div><div class="orbit-node-title">Portfolio Linker</div><div class="orbit-node-sub">Case Study Proofs</div></div>'
        '</div>'

        '</div>'
        '</div>'
    )
    st.markdown(orbit_html, unsafe_allow_html=True)

def skeleton(message: str = "Synthesizing AI output..."):
    """Renders a sleek glowing skeleton loader."""
    html_skel = f'<div class="skeleton-loader"><span style="color: #2563EB; font-weight: 700;">AI Processing</span> &nbsp;|&nbsp; <span style="color: #1E293B;">{message}</span></div>'
    return html_skel
