# 🌐 Live Deployment Guide: CareerReach AI

> 🚀 **Official Live App**: [https://careerreach-ai.streamlit.app/](https://careerreach-ai.streamlit.app/)

You can host **CareerReach AI** live on the web for free using any of the following platforms.

---

## ⚡ Option 1: Streamlit Community Cloud (Recommended & Free)

The easiest and fastest way to host CareerReach AI with zero cost and automatic GitHub updates:

### Steps:
1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Add CareerReach AI app with interactive chatbot and deployment files"
   git push origin main
   ```
2. **Go to Streamlit Community Cloud**:
   - Visit [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. **Create a New App**:
   - Click **"Create app"** -> **"I already have an app"**.
   - **Repository**: Select `CareerReach-AI-` (or your repository name).
   - **Branch**: `main`
   - **Main file path**: `app/main.py`
   - **App URL**: Choose a custom subdomain (e.g., `careerreach-ai.streamlit.app`).
4. **Set your Groq API Key (Secrets)**:
   - Click **"Advanced settings"** -> **"Secrets"**.
   - Add:
     ```toml
     GROQ_API_KEY = "your_groq_api_key_here"
     ```
5. **Click Deploy**:
   - Streamlit Cloud will install dependencies from `requirements.txt` and launch your live URL!

---

## 🤗 Option 2: Hugging Face Spaces (Free)

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces) and click **"Create new Space"**.
2. **Space Name**: `careerreach-ai`
3. **Select Space SDK**: **Streamlit**.
4. Push your repository code to the Hugging Face Space repository or connect via GitHub.
5. In your Space's **Settings** -> **Variables and secrets**, add a secret:
   - Key: `GROQ_API_KEY`
   - Value: `gsk_...`
6. Hugging Face will automatically build and host your app live.

---

## 🐳 Option 3: Render / Railway / Cloud (Docker)

A production-ready `Dockerfile` is included in the root directory.

### On Render:
1. Go to [render.com](https://render.com) and create a **New Web Service**.
2. Connect your GitHub repository.
3. Select **Docker** environment.
4. Add Environment Variable:
   - `GROQ_API_KEY` = `your_key`
5. Click **Create Web Service**.

---

## 🔑 Getting Your Free Groq API Key
1. Sign in to [console.groq.com/keys](https://console.groq.com/keys).
2. Click **Create API Key**.
3. Copy the key (starts with `gsk_...`).
4. You can paste it into the app sidebar when running live, or save it in `app/.env` / cloud secrets.
