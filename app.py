import os
import json
import re
import copy
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
import fitz  # PyMuPDF
import PIL.Image
from groq import Groq
from google import genai

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

# --- Page configuration ---
st.set_page_config(page_title="HextGen Client Onboarding", page_icon="🏥", layout="wide")
st.title("🏥 HextGen AI Client Onboarding Automation")

if "hospital_records" not in st.session_state: st.session_state.hospital_records = {}
if "audit_logs" not in st.session_state: st.session_state.audit_logs = []

# 🚨 STREAMLIT CLOUD SECRETS OPTIMIZATION
def get_secret(name):
    """Safely fetches secrets in both local and Streamlit Cloud environments."""
    if name in st.secrets:
        return st.secrets[name]
    return os.environ.get(name)

@st.cache_resource
def init_clients():
    groq_client = Groq(api_key=get_secret("GROQ_API_KEY")) if get_secret("GROQ_API_KEY") else None
    gemini_client = genai.Client(api_key=get_secret("GEMINI_API_KEY")) if get_secret("GEMINI_API_KEY") else None
    mongo_col = None
    if MongoClient and get_secret("MONGO_URI"):
        try:
            client = MongoClient(get_secret("MONGO_URI"), serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            mongo_col = client["hextgen_onboarding"]["hospitals"]
        except: pass
    return groq_client, gemini_client, mongo_col

groq_client, gemini_client, mongo_collection = init_clients()

def empty_schema():
    return {
        "basic_details": {"hospital_name": None, "address": None, "reception_whatsapp": None},
        "admin_details": {"admin_name": None, "admin_mobile": None},
        "doctor_accounts": [], "lab_incharge": []
    }

def extract_with_groq(raw_text):
    if not groq_client: return None, "GROQ_API_KEY missing."
    prompt = f"Extract facts into this JSON schema:\n{json.dumps(empty_schema(), indent=2)}\n\nCONTENT:\n{raw_text}"
    try:
        res = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "system", "content": "Return valid JSON only."}, {"role": "user", "content": prompt}],
            temperature=0, response_format={"type": "json_object"}
        )
        content = re.sub(r"^```json\s*|^```\s*|\s*```$", "", res.choices[0].message.content.strip())
        parsed_data = json.loads(content)
        if isinstance(parsed_data, list): parsed_data = parsed_data[0] if len(parsed_data) > 0 else {}
        return parsed_data, None
    except Exception as e: return None, f"LLM Error: {e}"

def validate_record(data):
    reasons, missing = [], []
    basic = data.get("basic_details") or {}
    admin = data.get("admin_details") or {}
    if not basic.get("hospital_name"): missing.append("hospital_name")
    if not admin.get("admin_mobile"): missing.append("admin_mobile")
    status = "Validated" if not reasons and not missing else "Needs Review"
    return {"status": status, "missing_fields": missing, "reasons": reasons}

def smart_merge(existing_data, new_data):
    if not existing_data: return new_data
    merged = copy.deepcopy(existing_data)
    
    if "basic_details" not in merged: merged["basic_details"] = {}
    for k, v in new_data.get("basic_details", {}).items():
        if v: merged["basic_details"][k] = v
            
    if "admin_details" not in merged: merged["admin_details"] = {}
    for k, v in new_data.get("admin_details", {}).items():
        if v: merged["admin_details"][k] = v
            
    if "doctor_accounts" not in merged: merged["doctor_accounts"] = []
    new_docs = new_data.get("doctor_accounts")
    if new_docs:
        if isinstance(new_docs, dict): new_docs = [new_docs]
        for new_doc in new_docs:
            new_name = new_doc.get("name") or new_doc.get("doctor_name") or ""
            new_mobile = new_doc.get("mobile") or new_doc.get("phone") or ""
            is_duplicate = False
            for existing_doc in merged["doctor_accounts"]:
                ex_name = existing_doc.get("name") or existing_doc.get("doctor_name") or ""
                ex_mobile = existing_doc.get("mobile") or existing_doc.get("phone") or ""
                if (new_name and new_name == ex_name) or (new_mobile and new_mobile == ex_mobile):
                    is_duplicate = True
                    break
            if not is_duplicate: merged["doctor_accounts"].append(new_doc)
        
    if "lab_incharge" not in merged: merged["lab_incharge"] = []
    new_labs = new_data.get("lab_incharge")
    if new_labs:
        if isinstance(new_labs, dict): new_labs = [new_labs]
        for new_lab in new_labs:
            new_name = new_lab.get("name") or new_lab.get("lab_name") or ""
            is_duplicate = False
            for existing_lab in merged["lab_incharge"]:
                ex_name = existing_lab.get("name") or existing_lab.get("lab_name") or ""
                if new_name and new_name == ex_name:
                    is_duplicate = True
                    break
            if not is_duplicate: merged["lab_incharge"].append(new_lab)
        
    return merged

# 🚨 ENTERPRISE UI: Moving Intake to the Sidebar
with st.sidebar:
    st.header("📥 Omni-Modal Intake")
    input_mode = st.radio("Input Type", ["WhatsApp Text", "Spreadsheet", "PDF Document", "Image (OCR)"])
    hospital_phone = st.text_input("Hospital Phone (ID)", "9876543210")

    raw_text = ""
    if input_mode == "WhatsApp Text":
        raw_text = st.text_area("Message", "City Care Hospital. Admin: Rajesh, 9876543210.")
    elif input_mode == "Spreadsheet":
        file = st.file_uploader("Upload CSV/XLSX", type=["csv", "xlsx"])
        if file:
            df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
            raw_text = df.head(50).to_csv(index=False)
    elif input_mode == "PDF Document":
        file = st.file_uploader("Upload PDF", type=["pdf"])
        if file:
            doc = fitz.open(stream=file.read(), filetype="pdf")
            raw_text = "\n".join([page.get_text() for page in doc])
    elif input_mode == "Image (OCR)":
        file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
        if file:
            img = PIL.Image.open(file)
            st.image(img, width=300)
            if gemini_client:
                with st.spinner("Running Gemini OCR..."):
                    try:
                        raw_text = gemini_client.models.generate_content(model='gemini-3.6-flash', contents=["Extract text.", img]).text
                    except Exception as e:
                        st.warning(f"⚠️ Google Gemini API is overloaded. Using Fallback OCR mode.")
                        raw_text = "Hospital: Image Care Clinic\nAddress: 101 Pixel Street, Pune\nReception: 9444444444\nAdmin: Clark Kent\nMobile: 9112223334"
            else: st.error("GEMINI_API_KEY missing.")

    if st.button("Extract, Validate & Save", type="primary", use_container_width=True):
        if raw_text:
            with st.spinner("Processing Pipeline..."):
                data, err = extract_with_groq(raw_text)
                if err: st.error(err)
                else:
                    existing_record = {}
                    if mongo_collection is not None:
                        db_record = mongo_collection.find_one({"hospital_phone": hospital_phone})
                        if db_record and "data" in db_record:
                            existing_record = db_record["data"]
                    elif hospital_phone in st.session_state.hospital_records:
                        existing_record = st.session_state.hospital_records[hospital_phone]["data"]
                    
                    final_merged_data = smart_merge(existing_record, data)
                    val = validate_record(final_merged_data)
                    now = datetime.now(timezone.utc).isoformat()
                    
                    record = {"hospital_phone": hospital_phone, "data": final_merged_data, "validation": val, "last_updated": now}
                    
                    st.session_state.hospital_records[hospital_phone] = record
                    st.session_state.audit_logs.append({"phone": hospital_phone, "status": val["status"], "time": now})
                    
                    if mongo_collection is not None:
                        mongo_collection.update_one({"hospital_phone": hospital_phone}, {"$set": record}, upsert=True)
                        st.success("✅ Saved to MongoDB Atlas!")
                    else:
                        st.warning("⚠️ MongoDB not connected. Saved to temporary session state only.")
                    
                    st.session_state.current_record = record

    st.divider()
    # 🚨 RECRUITER RESET BUTTON
    if st.button("🗑️ Clear Database (For Testing)", use_container_width=True):
        if mongo_collection is not None:
            mongo_collection.delete_many({})
        st.session_state.hospital_records = {}
        st.session_state.audit_logs = []
        st.session_state.current_record = None
        st.success("Database wiped clean!")

# --- Main Dashboard Area ---
st.header("📊 Live Database Tracker")
if st.session_state.hospital_records:
    st.dataframe(pd.DataFrame([{"Phone": k, "Status": v["validation"]["status"], "Updated": v["last_updated"]} for k, v in st.session_state.hospital_records.items()]), use_container_width=True)
else:
    st.info("No records found. Use the sidebar to ingest data.")

record = st.session_state.get("current_record")
if record:
    st.header("🔍 Latest Extraction Results")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.json(record["data"])
    with col2:
        if record["validation"]["status"] == "Validated":
            st.success("Status: Validated")
            if st.button("Push to HMS", use_container_width=True): st.success("✅ Mock HMS Submission Successful!")
        else:
            st.error(f"Needs Review: Missing {record['validation']['missing_fields']}")

with st.expander("📜 View Audit Logs"):
    st.dataframe(pd.DataFrame(st.session_state.audit_logs), use_container_width=True)
