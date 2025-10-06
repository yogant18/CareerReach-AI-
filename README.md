# 🚀 CareerReach AI

CareerReach AI is an **AI-powered cold email generator** for services companies, built with **Groq**, **LangChain**, and **Streamlit**.  
Give it a company careers-page URL and it will:
- **Extract job listings** from the page,
- **Generate personalized cold emails** tailored to each job,
- **Attach relevant portfolio links** pulled from a **vector database** based on the job description.

---

## ✨ Example Use Case

- **Siemens** is hiring a *Senior Machine Learning Engineer* and investing significant time in sourcing, interviews, and onboarding.
- **TechNova**, an AI services firm, can allocate a dedicated ML engineer to accelerate Siemens’ roadmap.
- Using **CareerReach AI**, TechNova’s BD executive (Aisha) pastes Siemens’ careers-page URL, and the app:
  - Extracts the ML Engineer job description,
  - Retrieves matching case studies from TechNova’s portfolio via the vector DB,
  - Generates a **personalized cold email** tailored to Siemens’ role—fast, targeted, and scalable.



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
   

