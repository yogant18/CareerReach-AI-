# 🚀 CareerReach AI

**CareerReach AI** is an AI-powered B2B cold outreach platform and interactive sales advisor built with **Groq (Llama 3.3)**, **LangChain**, **ChromaDB**, and **Streamlit**.

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
  - Customize sender name, company name, role, email tone, and Groq LLM model (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, etc.).

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
