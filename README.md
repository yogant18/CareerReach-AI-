# 🚀 CareerReach AI

CareerReach AI is an **AI-powered cold email generator** for services companies, built with **Groq**, **LangChain**, and **Streamlit**.  
Give it a company careers-page URL and it will:
- **Extract job listings** from the page,
- **Generate personalized cold emails** tailored to each job,
- **Attach relevant portfolio links** pulled from a **vector database** based on the job description.

---

## ✨ Example Use Case

- **Nike** is hiring a *Principal Software Engineer* and investing time in hiring, onboarding, and training.  
- **Atliq** (a software development company) can provide a dedicated engineer.  
- Using **CareerReach AI**, Atliq’s BD executive (Mohan) generates a **personalized outreach email** to Nike—fast, targeted, and scalable.

---


## Set-up
1. To get started we first need to get an API_KEY from here: https://console.groq.com/keys. Inside `app/.env` update the value of `GROQ_API_KEY` with the API_KEY you created. 


2. To get started, first install the dependencies using:
    ```commandline
     pip install -r requirements.txt
    ```
   
3. Run the streamlit app:
   ```commandline
   streamlit run app/main.py
   ```
   

