# 🚀 CareerReach AI

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://careerreach-ai.streamlit.app/)
[![Live Demo](https://img.shields.io/badge/Live_Demo-careerreach--ai.streamlit.app-brightgreen?style=for-the-badge&logo=streamlit)](https://careerreach-ai.streamlit.app/)

> 🌐 **Live Demo**: [https://careerreach-ai.streamlit.app/](https://careerreach-ai.streamlit.app/)

**CareerReach AI** is an AI-powered B2B cold outreach platform and interactive sales advisor built with **Groq**, **LangChain**, **ChromaDB**, and **Streamlit**.

It extracts job postings directly from company career page URLs (or manual descriptions), matches relevant company portfolio case studies from a vector database, writes personalized cold emails, and features a built-in **Interactive AI Chatbot** for strategic outreach guidance.

---

## ✨ Features

- 📧 **Cold Email Generator**:
  - Scrape job postings from any career page URL or paste job descriptions directly.
  - Automatically extracts key details: Role, Experience, Skills, and Responsibilities.
  - Generates personalized, high-converting cold emails tailored to the role.
  - 1-click download and copy functionality.

- 🤖 **Interactive AI Chatbot**:
  - Real-time conversational AI sales & outreach advisor powered by Groq Llama 3.
  - Conversational memory for multi-turn discussions.
  - Brainstorms catchy subject lines, follow-up sequences, and objection handlers.
  - Queries indexed portfolio case studies to suggest the best angles.

- 💼 **ChromaDB Vector Store**:
  - Semantically searches portfolio case studies based on extracted job tech stacks.
  - Live search and interactive addition of new portfolio records.

- ⚙️ **Customizable Sender Persona**:
  - Customize sender name, company name, role, email tone, and Groq LLM model (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `openai/gpt-oss-20b`).

---

## 📁 Repository Structure

```
├── app/
│   ├── main.py            # Streamlit multi-tab application & UI
│   ├── chains.py          # Groq LLM chains (Extraction, Cold Email, Chatbot)
│   ├── portfolio.py       # ChromaDB vector store manager
│   ├── utils.py           # Web scraping & text cleaning
│   └── .env               # Groq API Key configuration
├── .streamlit/
│   └── config.toml        # Streamlit configuration & theme
├── my_portfolio.csv       # Sample portfolio case studies
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container configuration for cloud deployment
├── DEPLOYMENT.md          # Step-by-step live hosting guide
└── README.md
```

---

## 🛠️ Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yogant18/CareerReach-AI-.git
   cd CareerReach-AI-
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your Groq API Key**:
   - Get a free key at [console.groq.com/keys](https://console.groq.com/keys).
   - Set it inside `app/.env`:
     ```env
     GROQ_API_KEY=gsk_your_key_here
     ```
   - *(Alternatively, you can enter the API key directly in the sidebar of the web app).*

4. **Run the Streamlit app**:
   ```bash
   streamlit run app/main.py
   ```
   Open `http://localhost:8501` in your browser.

---

## 🌐 Live Cloud Deployment

You can host CareerReach AI live on the web for free:

### 1. Streamlit Community Cloud (Recommended & Free)
1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **Create app**.
3. Select your repository, branch (`main`), and set the main file path to `app/main.py`.
4. In **Advanced Settings** -> **Secrets**, set:
   ```toml
   GROQ_API_KEY = "gsk_your_key_here"
   ```
5. Click **Deploy**.

For detailed instructions on deploying to **Hugging Face Spaces** or **Docker (Render/Railway)**, check [DEPLOYMENT.md](DEPLOYMENT.md).

---

## 🔑 API Keys — Security Rules

> **Never hard-code a Groq API key (or any secret) in source code, notebooks, or config files that are committed to git.**

### Where to put your key

| Environment | Where to set it |
|-------------|----------------|
| **Local development** | `app/.env` — copy `app/.env.example` and fill in your real key. This file is gitignored. |
| **Streamlit Cloud** | App Settings → **Secrets** (`.streamlit/secrets.toml` format). The file itself is gitignored. |
| **Docker / Render / Railway** | Set `GROQ_API_KEY` as an environment variable in the platform's dashboard. |

### What the codebase does to protect you

- **`.gitignore`** excludes `app/.env`, `.env`, `.streamlit/secrets.toml`, and `vectorstore/`.
- **`app/.env.example`** is the only file committed; it contains a placeholder, never a real key.
- **A git pre-commit hook** (`.git/hooks/pre-commit`) scans every staged change for real `gsk_…` keys and **aborts the commit** if one is found.

### If a key is accidentally exposed

1. **Rotate it immediately** at [console.groq.com/keys](https://console.groq.com/keys) — the old key is compromised the moment it is pushed.
2. Remove it from all files and replace with `os.environ["GROQ_API_KEY"]`.
3. Scrub git history: `git filter-repo --path app/.env --invert-paths`.
