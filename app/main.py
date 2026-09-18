import os
import sys
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Add project root to sys.path to enable smooth module importing
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.chains import Chain
from app.portfolio import Portfolio
from app.utils import clean_text, scrape_website

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(root_dir, ".env"))

# Streamlit Page Config
st.set_page_config(
    page_title="CareerReach AI | Cold Email & AI Outreach",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    /* Main container styling */
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    /* Card style */
    .feature-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    /* Quick prompt button style */
    .quick-chip {
        display: inline-block;
        background: #EFF6FF;
        color: #1E40AF;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        margin: 4px;
        border: 1px solid #BFDBFE;
        cursor: pointer;
    }
    .quick-chip:hover {
        background: #DBEAFE;
    }
    .badge-skill {
        display: inline-block;
        background-color: #EDE9FE;
        color: #5B21B6;
        font-weight: 500;
        font-size: 0.8rem;
        padding: 3px 10px;
        border-radius: 12px;
        margin: 2px 4px 2px 0;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State
if "portfolio_instance" not in st.session_state:
    csv_path = os.path.join(root_dir, "my_portfolio.csv")
    vector_path = os.path.join(root_dir, "vectorstore")
    st.session_state.portfolio_instance = Portfolio(file_path=csv_path, vectorstore_path=vector_path)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": "👋 Hi there! I'm your **CareerReach AI Assistant**.\n\nI can help you craft high-converting cold emails, refine outreach strategies, find matching portfolio case studies, or prepare follow-up sequences. What role or campaign are you targeting today?"
        }
    ]

# Sidebar Configurations
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # Check if a key is securely configured on the server/environment or secrets
    server_key = ""
    try:
        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            server_key = str(st.secrets["GROQ_API_KEY"]).strip()
    except Exception:
        pass
    if not server_key:
        server_key = os.getenv("GROQ_API_KEY", "").strip()

    user_custom_key = ""
    if server_key and server_key != "DEMO_MODE":
        st.success("🔒 **Groq API Key Active**")
        st.caption("Securely loaded from server secrets / environment. Key is protected and hidden from viewers.")
        with st.expander("🔑 Override with Custom Key (Optional)"):
            user_custom_key = st.text_input(
                "Enter your personal Groq key",
                value="",
                type="password",
                placeholder="Leave blank to use server key",
                help="Only enter if you wish to use your own Groq API key instead of the server key."
            )
    else:
        st.info("🟢 **Enter API Key or Use Demo Mode**")
        user_custom_key = st.text_input(
            "Groq API Key",
            value="",
            type="password",
            placeholder="gsk_... (or leave blank for Demo Mode)",
            help="Get your free API key at https://console.groq.com/keys"
        )
        if not user_custom_key.strip():
            st.caption("No key entered. The app will run in **Demo Mode**.")

    st.markdown("---")
    st.subheader("🧠 Model & Creativity")
    selected_model = st.selectbox(
        "Groq Model",
        options=[
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "groq/compound",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ],
        index=0
    )
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)

    st.markdown("---")
    st.subheader("👤 Sender Profile")
    sender_name = st.text_input("Your / Sender Name", value="Mohan")
    company_name = st.text_input("Your Company", value="AtliQ")
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

    st.markdown("---")
    # Vector store status
    portfolio = st.session_state.portfolio_instance
    doc_count = portfolio.collection.count()
    st.info(f"📊 **Portfolio Database**: `{doc_count}` items indexed.")
    if st.button("🔄 Reload Portfolio Data"):
        portfolio.load_portfolio()
        st.success("Vector store refreshed!")


# Helper function to get chain
def get_chain():
    active_key = user_custom_key.strip() if user_custom_key.strip() else server_key
    if not active_key:
        active_key = "DEMO_MODE"
    try:
        return Chain(api_key=active_key, model_name=selected_model, temperature=temperature)
    except Exception as e:
        st.error(f"Error initializing Groq LLM: {e}")
        return None


# Top App Header
st.markdown('<div class="main-title">🚀 CareerReach AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">AI-Powered B2B Cold Outreach & Portfolio Matching with Interactive Conversational Assistant</div>',
    unsafe_allow_html=True
)

# Tabs Navigation
tab_email, tab_chat, tab_portfolio = st.tabs([
    "📧 Cold Email Generator",
    "🤖 Interactive AI Chatbot",
    "💼 Portfolio Vector Store"
])


# ==========================================
# TAB 1: COLD EMAIL GENERATOR
# ==========================================
with tab_email:
    st.markdown("### 🎯 Generate Job-Tailored Cold Emails")
    st.write(
        "Extract job postings from any career page URL or paste the job description directly. "
        "CareerReach AI will match relevant portfolio case studies and draft an irresistible cold email."
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

        submit_btn = st.button("🚀 Extract & Generate Cold Email", type="primary")

        if submit_btn:
            if not url_input.strip():
                st.warning("Please provide a valid URL.")
            else:
                with st.spinner("Scraping webpage and parsing job listings..."):
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
        submit_btn = st.button("🚀 Generate Cold Email from Description", type="primary")

        if submit_btn:
            if not jd_input.strip():
                st.warning("Please enter job description text.")
            else:
                scraped_content = clean_text(jd_input)
                run_generation = True

    # Processing Generation
    if run_generation and scraped_content:
        chain = get_chain()
        if not chain:
            st.error("⚠️ Please configure a valid Groq API Key in the sidebar to generate cold emails.")
        else:
            with st.spinner("Analyzing job requirements and matching portfolio case studies..."):
                try:
                    jobs = chain.extract_jobs(scraped_content)
                    
                    if not jobs:
                        st.warning("No specific job roles could be identified in the text. Try refining the input.")
                    else:
                        st.success(f"Successfully identified {len(jobs)} job role(s)!")

                        for idx, job in enumerate(jobs, 1):
                            role = job.get("role", f"Role #{idx}")
                            experience = job.get("experience", "Not specified")
                            skills = job.get("skills", [])
                            desc = job.get("description", "")

                            st.markdown(f"#### 📌 Job #{idx}: **{role}**")
                            
                            col_meta1, col_meta2 = st.columns([1, 2])
                            with col_meta1:
                                st.markdown(f"**Experience:** {experience}")
                                st.markdown(f"**Summary:** {desc[:250]}..." if len(desc) > 250 else f"**Summary:** {desc}")
                            with col_meta2:
                                st.markdown("**Detected Skills:**")
                                if skills:
                                    skill_badges = "".join([f'<span class="badge-skill">{s}</span>' for s in skills])
                                    st.markdown(skill_badges, unsafe_allow_html=True)
                                else:
                                    st.write("None detected.")

                            # Retrieve matching portfolio links
                            portfolio = st.session_state.portfolio_instance
                            matched_links = portfolio.query_links(skills)

                            if matched_links:
                                st.markdown("**🔗 Relevant Portfolio Case Studies Found:**")
                                for link_item in matched_links:
                                    link_url = link_item.get("links", "")
                                    st.markdown(f"- [{link_url}]({link_url})")
                            else:
                                st.caption("No direct portfolio match found. Standard company credentials will be used.")

                            # Generate Cold Email
                            with st.spinner(f"Writing personalized cold email for {role}..."):
                                user_profile_tone = email_tone
                                email_text = chain.write_mail(
                                    job=job,
                                    links=matched_links,
                                    sender_name=sender_name,
                                    company_name=company_name,
                                    sender_role=sender_role,
                                    tone=user_profile_tone
                                )

                                st.markdown("##### ✉️ Generated Cold Email:")
                                st.text_area(
                                    label=f"Cold Email for {role}",
                                    value=email_text,
                                    height=320,
                                    key=f"email_{idx}"
                                )

                                col_copy, col_download = st.columns([1, 4])
                                with col_copy:
                                    st.download_button(
                                        label="📥 Download Email (.txt)",
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
    st.markdown("### 🤖 CareerReach AI Chatbot")
    st.write(
        "Chat with your AI outreach strategist. Ask it to draft custom pitches, polish subject lines, "
        "find matching portfolio case studies, write follow-up messages, or simulate client objections."
    )

    # Quick Action Prompt Chips
    st.markdown("**💡 Quick Starters:**")
    quick_col1, quick_col2 = st.columns(2)
    
    suggested_prompt = None
    with quick_col1:
        if st.button("✨ 5 High-converting subject lines for an AI/ML role"):
            suggested_prompt = "Give me 5 catchy, high-converting cold email subject lines for an AI/ML Engineer reachout."
        if st.button("🔄 Write a 3-day follow-up email after no reply"):
            suggested_prompt = "Write a short, polite 3-day follow-up email after no response to our initial cold outreach."
    with quick_col2:
        if st.button("💼 Which portfolio links match React & Node.js?"):
            suggested_prompt = "Which portfolio case studies from our database match a React, Node.js, and MongoDB tech stack?"
        if st.button("🛡️ How to handle: 'We don't work with external vendors'"):
            suggested_prompt = "How should I reply to a prospect who responds with: 'We don't use external agencies or vendors right now'?"

    st.markdown("---")

    # Display Chat Messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Handle New Chat Input
    user_query = st.chat_input("Type your question or outreach request here...")
    
    # Check if a quick prompt chip was pressed
    if suggested_prompt and not user_query:
        user_query = suggested_prompt

    if user_query:
        # Display user message
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Generate Assistant response
        chain = get_chain()
        if not chain:
            error_msg = "⚠️ Please enter a valid Groq API Key in the sidebar to talk with the chatbot."
            st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
            with st.chat_message("assistant"):
                st.warning(error_msg)
        else:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        # Prepare context from portfolio
                        portfolio_df = st.session_state.portfolio_instance.get_all_portfolios()
                        portfolio_summary = portfolio_df.to_string(index=False)
                        
                        user_prof = {
                            "name": sender_name,
                            "company": company_name,
                            "role": sender_role
                        }

                        # Call Groq LLM
                        response = chain.chat_response(
                            messages=st.session_state.chat_history,
                            portfolio_context=portfolio_summary,
                            user_profile=user_prof
                        )
                        st.markdown(response)
                        st.session_state.chat_history.append({"role": "assistant", "content": response})
                    except Exception as chat_err:
                        err_text = f"Error generating response: {str(chat_err)}"
                        st.error(err_text)
                        st.session_state.chat_history.append({"role": "assistant", "content": err_text})

    # Clear Chat History Button
    col_clear, _ = st.columns([1, 5])
    with col_clear:
        if st.button("🗑️ Clear Conversation"):
            st.session_state.chat_history = [
                {
                    "role": "assistant",
                    "content": "Conversation reset. How can I assist with your outreach today?"
                }
            ]
            st.rerun()


# ==========================================
# TAB 3: PORTFOLIO & VECTOR STORE
# ==========================================
with tab_portfolio:
    st.markdown("### 💼 Portfolio Vector Database")
    st.write(
        "Browse all indexed client case studies and tech stacks. "
        "Test ChromaDB semantic search or dynamically register new case studies."
    )

    col_view, col_add = st.columns([3, 2])

    with col_view:
        st.subheader("📚 Current Indexed Portfolios")
        portfolio = st.session_state.portfolio_instance
        df_port = portfolio.get_all_portfolios()
        st.dataframe(df_port, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("🔍 Test Semantic Search")
        search_query = st.text_input(
            "Enter skills or tech query (e.g. 'Kubernetes cloud deployment', 'iOS ARKit')",
            value="Machine Learning Python"
        )
        if st.button("Search Vector DB"):
            matches = portfolio.query_links(search_query, n_results=3)
            if matches:
                st.write("**Matching Links Found:**")
                for m in matches:
                    st.markdown(f"- [{m.get('links')}]({m.get('links')})")
            else:
                st.info("No matching portfolio entries found.")

    with col_add:
        st.subheader("➕ Add New Portfolio Item")
        with st.form("add_portfolio_form"):
            new_techstack = st.text_input("Techstack / Skills (e.g. Next.js, Tailwind, Supabase)")
            new_link = st.text_input("Portfolio / Case Study URL", placeholder="https://example.com/nextjs-portfolio")
            submitted = st.form_submit_button("Add to Database", type="primary")

            if submitted:
                if not new_techstack.strip() or not new_link.strip():
                    st.warning("Please fill in both Techstack and Link fields.")
                else:
                    success = portfolio.add_portfolio(new_techstack, new_link)
                    if success:
                        st.success(f"Added '{new_techstack}' to portfolio!")
                        st.rerun()
                    else:
                        st.error("Failed to add portfolio.")
