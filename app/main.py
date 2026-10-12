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
from app.theme import apply_theme, hero, skeleton
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

# Render Copy button component
def render_copy_button(text_to_copy: str, key_suffix: str, label: str = "Copy"):
    safe_text = json.dumps(text_to_copy)
    btn_id = f"cp_{key_suffix}"
    
    html_code = f"""
    <div style="margin-top: 4px; margin-bottom: 8px;">
        <button id="{btn_id}" onclick="doCopy_{btn_id}()" style="
            background: rgba(255, 255, 255, 0.05);
            color: #E2E8F0;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
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
    components.html(html_code, height=44)


# Apply luxury dark theme
apply_theme("Classic Dark")

# Sidebar Configurations
with st.sidebar:
    st.markdown("### Settings")

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
    if "portfolio_instance" not in st.session_state or not hasattr(st.session_state.portfolio_instance, "load_from_dataframe"):
        st.cache_resource.clear()
        st.session_state.portfolio_instance = get_portfolio_resource()
    portfolio = st.session_state.portfolio_instance
    doc_count = portfolio.collection.count()
    st.markdown(f"**Portfolio Database**: `{doc_count}` items indexed.")
    if st.button("Reload Portfolio Data"):
        portfolio.load_portfolio(force_reload=True)
        st.success("Vector store refreshed.")
        st.rerun()


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


# Hero Header — Simpliflow-inspired hero
hero("CareerReach AI", "AI-powered B2B cold outreach & portfolio matching")

# Demo-mode banner: shown once, before tabs, only when key is absent/invalid
_probe_chain = get_chain()
if _probe_chain and _probe_chain.is_demo_mode:
    st.warning(
        "Demo Mode — AI features are disabled. "
        "No valid Groq API key was found. All outputs will use built-in templates. "
        "Add your key to app/.env (local) or Streamlit Secrets (cloud), then refresh."
    )

# Tabs Navigation
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
                st.markdown(skeleton("Scraping webpage and parsing job listings..."), unsafe_allow_html=True)
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
                st.markdown(skeleton("Analyzing job requirements and matching portfolio case studies..."), unsafe_allow_html=True)
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
                                        skill_badges = "".join([f'<span class="badge-glow">{html.escape(str(s))}</span>' for s in skills])
                                        st.markdown(skill_badges, unsafe_allow_html=True)
                                    else:
                                        st.write("None detected.")

                                # Retrieve matching portfolio links for cold email generation
                                portfolio = st.session_state.portfolio_instance
                                matched_links = portfolio.query_links(skills, base_portfolio_url=portfolio_url)

                                # Generate Cold Email with Skeleton indicator
                                st.markdown(skeleton(f"Writing personalized outreach email for {role}..."), unsafe_allow_html=True)
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
                st.markdown(skeleton("Formulating outreach strategy..."), unsafe_allow_html=True)
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
        "Upload your own portfolio CSV (Techstack, Links) or use our Demo Agency Library. "
        "When you upload your CSV, ChromaDB indexes your projects in real-time so your outreach emails quote your own real case studies."
    )

    # -------------------------------------------------------------
    # OPTION 2: Upload Custom Portfolio CSV or Use Demo Library
    # -------------------------------------------------------------
    st.markdown('<div class="glass-panel" style="margin-bottom: 24px;">', unsafe_allow_html=True)
    st.markdown("#### 📂 Portfolio Source & Custom CSV Upload")
    
    col_upload, col_reset = st.columns([3, 1])
    portfolio = st.session_state.get("portfolio_instance")
    if portfolio is None or not hasattr(portfolio, "load_from_dataframe"):
        st.cache_resource.clear()
        portfolio = get_portfolio_resource()
        st.session_state.portfolio_instance = portfolio
    
    with col_upload:
        uploaded_csv = st.file_uploader(
            "Upload your own portfolio CSV (Techstack, Links) or use our Demo Agency Library",
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
                        portfolio.load_from_dataframe(user_df, force_reload=True)
                        st.session_state["current_portfolio_upload"] = upload_id
                        st.session_state["portfolio_source_label"] = f"Custom CSV: {uploaded_csv.name}"
                        st.success(f"Indexed {len(user_df)} custom case studies from '{uploaded_csv.name}' into ChromaDB! Emails will now cite your own case studies.")
                        st.rerun()
                    else:
                        st.error("Uploaded CSV must contain 'Techstack' and 'Links' columns.")
                except Exception as e:
                    st.error(f"Error reading uploaded CSV: {e}")

    with col_reset:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Reset to Demo Library", help="Reload the standard enterprise case studies library"):
            portfolio.load_portfolio(force_reload=True)
            st.session_state["current_portfolio_upload"] = None
            st.session_state["portfolio_source_label"] = "Demo Agency Library"
            st.success("Reset back to Demo Agency Library!")
            st.rerun()

        # Download sample template
        sample_csv = "Techstack,Links\n\"FastAPI, PostgreSQL, Docker\",https://example.com/case-studies/fintech-api\n\"React, Next.js, Stripe\",https://example.com/case-studies/ecommerce-platform\n\"PyTorch, LLMs, LangChain\",https://example.com/case-studies/ai-copilot\n"
        st.download_button(
            label="📥 Sample CSV Template",
            data=sample_csv,
            file_name="portfolio_template.csv",
            mime="text/csv"
        )

    active_source = st.session_state.get("portfolio_source_label", "Demo Agency Library")
    st.markdown(f'<div style="font-size: 0.85rem; color: #94A3B8; margin-top: 6px;">Active Library: <span class="badge-glow" style="margin-left: 6px;">{html.escape(active_source)}</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    col_view, col_add = st.columns([3, 2])

    with col_view:
        st.subheader("Current Indexed Portfolios")
        df_port = portfolio.get_all_portfolios()

        # Minimalist Glassmorphism (Vercel) Cards instead of a glaring white table
        if df_port is not None and not df_port.empty:
            for _, row in df_port.iterrows():
                tech = html.escape(str(row.get("Techstack", "")))
                link = str(row.get("Links", ""))
                card_html = f"""
                <div class="portfolio-glass-card">
                    <div>
                        <div style="font-weight: 700; color: #F8FAFC; font-size: 0.95rem; margin-bottom: 4px;">{tech}</div>
                        <a href="{link}" target="_blank" style="color: #A855F7; text-decoration: none; font-size: 0.82rem;">{link}</a>
                    </div>
                    <div>
                        <a href="{link}" target="_blank" style="
                            background: rgba(168, 85, 247, 0.15);
                            color: #D8B4FE;
                            border: 1px solid rgba(168, 85, 247, 0.3);
                            padding: 6px 14px;
                            border-radius: 8px;
                            font-size: 0.8rem;
                            font-weight: 600;
                            text-decoration: none;
                            display: inline-block;
                        ">Open ↗</a>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("No portfolios currently indexed.")

        st.markdown("---")
        st.subheader("Test Semantic Search")
        search_query = st.text_input(
            "Enter skills or tech query (e.g. 'Kubernetes cloud deployment', 'iOS ARKit')",
            value="Machine Learning Python"
        )
        if st.button("Search Vector DB", type="primary"):
            st.session_state["search_matches"] = portfolio.query_links(
                search_query, n_results=3, base_portfolio_url=portfolio_url
            )
            st.session_state["has_searched"] = True

        matches = st.session_state.get("search_matches", [])
        if st.session_state.get("has_searched"):
            if matches:
                st.write("**Matching Links Found:**")
                for i, m in enumerate(matches):
                    link_url = m.get('links', '')
                    match_html = f"""
                    <div class="portfolio-glass-card" style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 1; margin-right: 12px; overflow: hidden;">
                            <span style="color: #4ADE80; font-size: 0.85rem; font-weight: 600;">Match #{i+1}</span>
                            <div style="margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                <a href="{link_url}" target="_blank" rel="noopener noreferrer" style="color: #A855F7; text-decoration: underline; font-size: 0.88rem; font-weight: 500;">{html.escape(link_url)}</a>
                            </div>
                        </div>
                        <div>
                            <a href="{link_url}" target="_blank" rel="noopener noreferrer" style="
                                background: rgba(168, 85, 247, 0.2);
                                color: #D8B4FE;
                                border: 1px solid rgba(168, 85, 247, 0.4);
                                padding: 6px 14px;
                                border-radius: 8px;
                                font-size: 0.82rem;
                                font-weight: 600;
                                text-decoration: none;
                                display: inline-block;
                            ">Open ↗</a>
                        </div>
                    </div>
                    """
                    st.markdown(match_html, unsafe_allow_html=True)
            else:
                st.info("No matching portfolio entries found.")

    with col_add:
        st.subheader("Add Portfolio Item")
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)

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
        st.markdown('</div>', unsafe_allow_html=True)
