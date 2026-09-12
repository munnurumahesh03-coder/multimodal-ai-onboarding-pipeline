# 🏥 HextGen AI Client Onboarding Automation

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg )](https://www.python.org/ )
[![Streamlit](https://img.shields.io/badge/Streamlit-Deployed-FF4B4B.svg )](https://streamlit.io/ )
[![MongoDB](https://img.shields.io/badge/MongoDB_Atlas-Cloud_Database-47A248.svg )](https://www.mongodb.com/ )
[![AI](https://img.shields.io/badge/AI-Groq_%7C_Gemini-F9AB00.svg )]()

## 📖 Overview
This project is an **End-to-End Multimodal AI Automation Pipeline** designed to eliminate manual data entry for hospital onboarding. It dynamically ingests client data from highly unpredictable formats (WhatsApp text, handwritten notes, PDFs, Excel files), structures it into a strict JSON schema using Large Language Models, intelligently merges it with existing records, and securely pushes it to a MongoDB Atlas NoSQL database.

The entire pipeline is deployed via **Streamlit Cloud**, providing a secure Human-in-the-Loop (HITL) dashboard for the operations team to track database updates in real-time.

## ⚙️ System Architecture (ETL Pipeline)

1. **Ingestion (Webhook Simulator):** Since live Meta WhatsApp Business API webhooks require verified business credentials, a Streamlit UI acts as a payload simulator. It allows testers to inject Text, CSV/Excel, PDFs, and Images directly into the pipeline.
2. **Omni-Modal Routing:** The system dynamically processes inputs based on file type. It uses `pandas` for spreadsheets, `PyMuPDF` for documents, and Google Gemini 3.6 Flash Vision for OCR/Handwriting recognition.
3. **LLM Extraction:** Groq (`gpt-oss-120b`) parses the normalized text. Using advanced Prompt Engineering, the AI intelligently filters the data and formats it into a strict Pydantic-style JSON schema.
4. **Smart Merge & Validation:** The system validates mandatory fields and performs a deep merge of new data over existing database records. This ensures zero data loss and prevents duplicate arrays (e.g., duplicate doctor accounts) when clients send data across multiple messages.
5. **Load (MongoDB Atlas):** The Python script connects to a cloud-hosted MongoDB cluster and securely upserts the validated JSON payload using the client's phone number as the Primary Key.

## 🧠 Key Engineering Decisions
| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Omni-Modal Routing** | Pandas, PyMuPDF, Gemini Vision | Ensures the pipeline can ingest structured (Excel), unstructured (Text/PDF), and visual (Handwriting) data seamlessly without breaking. |
| **Data Structuring** | Groq (Llama-3 120B) | Replaces brittle RegEx rules. The LLM understands context and maps messy, conversational client messages into a strict JSON schema. |
| **State Management** | Custom Smart Merge Algorithm | Deep-merges new JSON payloads over existing MongoDB records to prevent data loss when clients send information in pieces over several days. |
| **Deployment** | Streamlit Cloud | Provides a secure, interactive Human-in-the-Loop (HITL) dashboard for staff to review flagged records and monitor the audit log. |

## 🚀 Live Cloud Deployment
The automation pipeline and HITL dashboard are fully deployed and accessible via Streamlit Cloud. 

**[View the Live Interactive Prototype Here](https://multimodal-ai-app-pipeline-4ybajaphreddx8jsvyx6tt.streamlit.app/ )**

## 💻 Manual Local Execution
If you wish to run the pipeline and dashboard directly on your local machine:

```bash
# 1. Clone the repository
git clone https://github.com/munnurumahesh03-coder/multimodal-ai-onboarding-pipeline.git
cd multimodal-ai-onboarding-pipeline

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your secrets
# Create a .streamlit folder and a secrets.toml file inside it
mkdir .streamlit
touch .streamlit/secrets.toml

# Add your API keys to secrets.toml:
# MONGO_URI = "your_mongodb_connection_string"
# GROQ_API_KEY = "your_groq_key"
# GEMINI_API_KEY = "your_gemini_key"

# 4. Run the Dashboard
streamlit run app.py
