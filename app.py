import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import pandas as pd
import json
import io
import os
import hashlib
import re
from datetime import datetime
from PIL import Image, ImageDraw

# ===========================================================================
# 1. CORE APPLICATION CONFIGURATION & FAVICON GENERATOR
# ===========================================================================
APP_NAME = "ARL HireMatrix Pro"
APP_TAGLINE = "Attock Refinery Limited (ARL) • HR Intelligence & AI Screening Engine"

def get_cyber_favicon():
    img = Image.new("RGBA", (64, 64), (11, 19, 43, 255))
    draw = ImageDraw.Draw(img)
    draw.polygon([(32, 6), (58, 32), (32, 58), (6, 32)], outline=(0, 242, 254), width=4)
    draw.polygon([(32, 18), (46, 32), (32, 46), (18, 32)], fill=(0, 242, 254))
    return img

st.set_page_config(
    page_title=f"{APP_NAME} | Executive Portal",
    page_icon=get_cyber_favicon(),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ===========================================================================
# 2. CLIENT INITIALIZATION (SUPABASE & GEMINI)
# ===========================================================================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

@st.cache_resource
def init_supabase() -> Client:
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            st.error(f"Supabase connection failed: {e}")
    return None

supabase = init_supabase()

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash")
else:
    gemini_model = None

# ===========================================================================
# 3. HIGH-TECH CYBER-NEON CSS & ADAPTIVE STYLING
# ===========================================================================
CYBER_NEON_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Outer Border Wrapper on Login Screen */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:first-child {
    border: 1.5px solid #D1D5DB !important;
    border-radius: 24px !important;
    padding: 2.2rem 2.2rem !important;
    background: rgba(255, 255, 255, 0.02) !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04) !important;
}

/* Remove duplicate borders from inner button columns */
[data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="column"] > div {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
    box-shadow: none !important;
}

@media (prefers-color-scheme: dark) {
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:first-child {
        border: 1.5px solid rgba(255, 255, 255, 0.2) !important;
        background: rgba(15, 23, 42, 0.6) !important;
        box-shadow: 0 14px 40px rgba(0, 0, 0, 0.35) !important;
        backdrop-filter: blur(14px) !important;
    }
}

/* Cyber Header in Login */
.cyber-header-box {
    text-align: center;
    padding: 0.5rem 0 1.2rem 0;
}
.cyber-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    color: #00F2FE;
    letter-spacing: -0.5px;
    margin: 0;
}
.cyber-title-pro {
    color: #38BDF8;
    background: linear-gradient(90deg, #00F2FE 0%, #4FACFE 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.cyber-badge {
    display: inline-block;
    padding: 5px 16px;
    border-radius: 20px;
    background: rgba(0, 242, 254, 0.08);
    border: 1px solid rgba(0, 242, 254, 0.3);
    color: #94A3B8;
    font-size: 0.8rem;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 8px;
}

/* Profile Card Styling */
.cyber-badge-card {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(13, 20, 36, 0.95) 100%);
    border: 1.5px solid rgba(0, 242, 254, 0.45);
    border-radius: 20px;
    padding: 1.4rem 1.6rem !important;
    margin-bottom: 1rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), inset 0 0 20px rgba(0, 242, 254, 0.08);
    backdrop-filter: blur(16px);
}
.cyber-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(0, 242, 254, 0.18);
    padding-bottom: 8px;
    margin-bottom: 12px;
}
.cyber-access-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #00F2FE;
    letter-spacing: 1px;
}
.cyber-status-dot {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #10B981;
    display: flex;
    align-items: center;
    gap: 6px;
}
.cyber-avatar-ring {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: rgba(0, 242, 254, 0.1);
    border: 1.5px solid #00F2FE;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
}
.cyber-name-title {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: #F8FAFC;
    font-family: 'Space Grotesk', sans-serif;
}
.cyber-role-pill {
    background: rgba(56, 189, 248, 0.15);
    color: #38BDF8;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 700;
}
.cyber-email-mono {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    color: #94A3B8;
    margin-top: 4px;
}

/* Button Styling (Strict single-line nowrap) */
.stButton > button {
    background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%) !important;
    color: #FFFFFF !important;
    border: 1.5px solid #00F2FE !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
    white-space: nowrap !important;
    padding: 0.65rem 1rem !important;
    box-shadow: 0 0 15px rgba(0, 242, 254, 0.25) !important;
    transition: all 0.25s ease-in-out !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #00C6FF 0%, #0072FF 100%) !important;
    border-color: #FFFFFF !important;
    box-shadow: 0 0 25px rgba(0, 242, 254, 0.6) !important;
    transform: translateY(-2px);
}

/* Adaptive Step Headings (.corp-card h4) */
.corp-card h4 {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.2px !important;
    color: light-dark(#008DDA, #FFFFFF) !important;
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    margin-top: 0 !important;
    margin-bottom: 1.2rem !important;
    background: linear-gradient(90deg, rgba(0, 180, 216, 0.12) 0%, rgba(0, 180, 216, 0.02) 100%) !important;
    border-left: 4px solid #00B4D8 !important;
    border-bottom: 1px solid rgba(0, 180, 216, 0.25) !important;
    border-radius: 8px 12px 12px 8px !important;
    padding: 10px 16px !important;
}
</style>
"""
st.markdown(CYBER_NEON_CSS, unsafe_allow_html=True)

# ===========================================================================
# 4. SESSION STATE INITIALIZATION
# ===========================================================================
defaults = {
    "logged_in": False,
    "hr_name": "Admin",
    "hr_email": "admin@arl.com.pk",
    "hr_role": "Executive HR Lead",
    "selected_profile_email": None,
    "pending_otp_email": None,
    "pending_pin_email": None,
    "screening_results": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ===========================================================================
# 5. ARL DEFAULT CORPORATE JOB CATALOG & SUPABASE HIERARCHY
# ===========================================================================
DEFAULT_ARL_CATALOG = {
    "Operations & Refining": [
        "Process Engineer",
        "Plant Shift Incharge",
        "Senior Plant Operator (CDU / Reformer)",
        "Control Room DCS Operator",
        "Refining Operations Manager",
        "Lead Commissioning Engineer"
    ],
    "Maintenance & Engineering": [
        "Mechanical Maintenance Engineer",
        "Electrical Maintenance Engineer",
        "Instrumentation & Control (I&C) Engineer",
        "Reliability & Inspection Engineer",
        "Turnaround & Maintenance Planning Specialist",
        "Rotary Equipment Specialist"
    ],
    "Technical Services & Quality Control (QC Lab)": [
        "Technical Services Engineer",
        "Senior Petroleum Chemist",
        "Lab Quality Analyst",
        "Corrosion & Metallurgy Engineer",
        "Catalyst & Yield Optimization Specialist"
    ],
    "Health, Safety, Environment & Security (HSE&S)": [
        "HSE Lead / Manager",
        "Process Safety Management (PSM) Specialist",
        "Fire & Industrial Safety Engineer",
        "Environmental Compliance Officer"
    ],
    "Supply Chain, Logistics & Procurement": [
        "Procurement & Contracts Lead",
        "Crude Oil Logistics & Storage Supervisor",
        "Commercial & Petroleum Dispatch Executive",
        "Warehouse & Inventory Controller"
    ],
    "Finance, Accounts & Commercial": [
        "Treasury & Budgeting Lead",
        "Corporate & Cost Accountant",
        "Internal Audit Executive",
        "Taxation & Compliance Specialist"
    ],
    "Human Resources & Administration": [
        "Talent Acquisition & Recruitment Specialist",
        "HR Operations & Payroll Executive",
        "Industrial Relations & Labor Compliance Officer",
        "Organizational Development (OD) Lead",
        "Administration & Estate Management Officer"
    ],
    "Information Technology & Industrial Automation": [
        "SAP ERP Functional Consultant",
        "SCADA & Process Automation Specialist",
        "IT Systems & Network Administrator",
        "Cyber Security Analyst"
    ]
}

def load_arl_job_catalog():
    catalog = {}
    if supabase:
        try:
            res = supabase.table("arl_job_hierarchy").select("*").order("id", desc=False).execute()
            if res.data and len(res.data) > 0:
                for row in res.data:
                    dept = row.get("department", "General")
                    job = row.get("job_title", "")
                    if job:
                        catalog.setdefault(dept, []).append(job)
                return catalog
            else:
                seed = []
                for d, j_list in DEFAULT_ARL_CATALOG.items():
                    for j in j_list:
                        seed.append({"department": d, "job_title": j})
                if seed:
                    supabase.table("arl_job_hierarchy").insert(seed).execute()
                return DEFAULT_ARL_CATALOG
        except Exception:
            pass
    return DEFAULT_ARL_CATALOG

def add_arl_job_to_db(department, job_title):
    if supabase:
        try:
            supabase.table("arl_job_hierarchy").insert({
                "department": department.strip(),
                "job_title": job_title.strip()
            }).execute()
            return True, "Job designation added successfully."
        except Exception as e:
            return False, str(e)
    return True, "Saved locally."

def edit_arl_job_in_db(old_dept, old_job, new_dept, new_job):
    if supabase:
        try:
            supabase.table("arl_job_hierarchy").update({
                "department": new_dept.strip(),
                "job_title": new_job.strip()
            }).eq("department", old_dept).eq("job_title", old_job).execute()
            return True, "Job designation updated."
        except Exception as e:
            return False, str(e)
    return True, "Updated locally."

def delete_arl_job_from_db(department, job_title):
    if supabase:
        try:
            supabase.table("arl_job_hierarchy").delete().eq("department", department).eq("job_title", job_title).execute()
            return True, "Job designation removed."
        except Exception as e:
            return False, str(e)
    return True, "Removed locally."

# ===========================================================================
# 6. EMPLOYEE AUTH & PROFILE FUNCTIONS
# ===========================================================================
def get_all_verified_profiles():
    if not supabase:
        return [("admin@arl.com.pk", "ARL HR Admin", "1234", "Executive Admin")]
    try:
        res = supabase.table("employees").select("*").execute()
        if res.data:
            return [(r.get("email"), r.get("name"), r.get("pin"), r.get("role", "Recruiter")) for r in res.data]
    except Exception:
        pass
    return []

def verify_employee_pin(email, pin):
    if not supabase:
        return (pin == "1234", "ARL HR Admin", "Executive Admin")
    try:
        res = supabase.table("employees").select("*").ilike("email", email).execute()
        if res.data:
            rec = res.data[0]
            if str(rec.get("pin")).strip() == str(pin).strip():
                return True, rec.get("name", "Employee"), rec.get("role", "Recruiter")
    except Exception:
        pass
    return False, "", ""

def save_employee_pin(email, pin):
    if not supabase:
        return True, "PIN saved in offline mode."
    try:
        supabase.table("employees").update({"pin": str(pin)}).ilike("email", email).execute()
        return True, "PIN configured successfully."
    except Exception as e:
        return False, str(e)

def delete_employee_profile(email):
    if supabase:
        try:
            supabase.table("employees").delete().ilike("email", email).execute()
        except Exception:
            pass

def register_initial_employee(name, email, password):
    if not supabase:
        return True, "Registered offline."
    try:
        supabase.table("employees").insert({
            "name": name, 
            "email": email.lower().strip(), 
            "password": password, 
            "pin": "0000", 
            "role": "Recruiter"
        }).execute()
        return True, "Registration successful. Please set up your PIN."
    except Exception as e:
        return False, str(e)

# ===========================================================================
# 7. TALENT POOL & SCREENED CANDIDATES (SEQUENCE 1 TO 13)
# ===========================================================================
def load_database():
    expected_cols = [
        "Name", "Father Name", "Qualification", "CGPA", 
        "Passing Year", "Institute", "DOB", "Email", 
        "Phone Number", "Experience", "Latest Experience", "Reference"
    ]
    if not supabase:
        return pd.DataFrame(columns=expected_cols)
    try:
        response = supabase.table("candidates").select("*").order("id", desc=True).execute()
        rows = response.data
        if rows:
            mapped = []
            for r in rows:
                mapped.append({
                    "Name": r.get("candidate_name") or r.get("name", "Unknown"),
                    "Father Name": r.get("father_name", "Not Provided"),
                    "Qualification": r.get("education", "Not Provided"),
                    "CGPA": r.get("cgpa", "Not Provided"),
                    "Passing Year": r.get("passing_year", "Not Provided"),
                    "Institute": r.get("university_name", "Not Provided"),
                    "DOB": r.get("dob", "Not Provided"),
                    "Email": r.get("email", "Not Provided"),
                    "Phone Number": r.get("phone", "Not Provided"),
                    "Experience": str(r.get("experience_years", "0")),
                    "Latest Experience": r.get("latest_experience", "Not Provided"),
                    "Reference": r.get("reference", "Not Provided")
                })
            return pd.DataFrame(mapped)
    except Exception:
        pass
    return pd.DataFrame(columns=expected_cols)

def save_candidate_to_database(cand):
    if not supabase or not cand:
        return
    payload = {
        "candidate_name": cand.get("name", "Unknown"),
        "father_name": cand.get("father_name", "Not Provided"),
        "education": cand.get("education", "Not Provided"),
        "cgpa": cand.get("cgpa", "Not Provided"),
        "passing_year": cand.get("passing_year", "Not Provided"),
        "university_name": cand.get("university_name", "Not Provided"),
        "dob": cand.get("dob", "Not Provided"),
        "email": cand.get("email", "Not Provided"),
        "phone": cand.get("phone", "Not Provided"),
        "experience_years": str(cand.get("experience_years", "0")),
        "latest_experience": cand.get("latest_experience", "Not Provided"),
        "reference": cand.get("reference", "Not Provided")
    }
    try:
        supabase.table("candidates").insert(payload).execute()
    except Exception:
        pass

def clear_candidate_database():
    if not supabase:
        return
    try:
        supabase.table("candidates").delete().neq("id", 0).execute()
    except Exception:
        pass

def save_screened_to_supabase(screened_list):
    if not supabase or not screened_list:
        return
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in screened_list:
        skills_str = ", ".join(r.get("missing_skills", [])) if isinstance(r.get("missing_skills"), list) else str(r.get("missing_skills", ""))
        payload = {
            "job_title": r.get("job_title", "Not Specified"),
            "candidate_name": r.get("name", "Unknown"),
            "father_name": r.get("father_name", "Not Provided"),
            "education": r.get("education", "Not Provided"),
            "cgpa": r.get("cgpa", "Not Provided"),
            "passing_year": r.get("passing_year", "Not Provided"),
            "university_name": r.get("university_name", "Not Provided"),
            "dob": r.get("dob", "Not Provided"),
            "email": r.get("email", "Not Provided"),
            "phone": r.get("phone", "Not Provided"),
            "experience_years": str(r.get("experience_years", "0")),
            "latest_experience": r.get("latest_experience", "Not Provided"),
            "reference": r.get("reference", "Not Provided"),
            "match_score": float(r.get("match_score", 0)),
            "missing_skills": skills_str,
            "pipeline_status": r.get("pipeline_status", "Shortlisted"),
            "screened_at": current_timestamp
        }
        try:
            supabase.table("screened_candidates").insert(payload).execute()
        except Exception:
            pass

def load_screened_database():
    expected_cols = [
        "Job Title", "Match Score (%)", "Pipeline Status",
        "Name", "Father Name", "Qualification", "CGPA", 
        "Passing Year", "Institute", "DOB", "Email", 
        "Phone Number", "Experience", "Latest Experience", "Reference",
        "Missing Skills", "Screened At"
    ]
    if not supabase:
        return pd.DataFrame(columns=expected_cols)
    try:
        response = supabase.table("screened_candidates").select("*").order("id", desc=True).execute()
        rows = response.data
        if rows:
            mapped = []
            for r in rows:
                mapped.append({
                    "Job Title": r.get("job_title", "Not Specified"),
                    "Match Score (%)": r.get("match_score", 0),
                    "Pipeline Status": r.get("pipeline_status", "Shortlisted"),
                    "Name": r.get("candidate_name", "Unknown"),
                    "Father Name": r.get("father_name", "Not Provided"),
                    "Qualification": r.get("education", "Not Provided"),
                    "CGPA": r.get("cgpa", "Not Provided"),
                    "Passing Year": r.get("passing_year", "Not Provided"),
                    "Institute": r.get("university_name", "Not Provided"),
                    "DOB": r.get("dob", "Not Provided"),
                    "Email": r.get("email", "Not Provided"),
                    "Phone Number": r.get("phone", "Not Provided"),
                    "Experience": str(r.get("experience_years", "0")),
                    "Latest Experience": r.get("latest_experience", "Not Provided"),
                    "Reference": r.get("reference", "Not Provided"),
                    "Missing Skills": r.get("missing_skills", "None"),
                    "Screened At": r.get("screened_at", "")
                })
            return pd.DataFrame(mapped)
    except Exception:
        pass
    return pd.DataFrame(columns=expected_cols)

def update_screened_candidate_status(email, job_title, new_status):
    if not supabase:
        return
    try:
        supabase.table("screened_candidates").update({"pipeline_status": new_status}).ilike("email", email).ilike("job_title", job_title).execute()
    except Exception:
        pass

def clear_screened_database():
    if not supabase:
        return
    try:
        supabase.table("screened_candidates").delete().neq("id", 0).execute()
    except Exception:
        pass

def generate_repository_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Candidates_Master')
    return output.getvalue()

# ===========================================================================
# 8. MULTI-CANDIDATE AI EXTRACTION (1 OR MULTIPLE CVS PER PDF)
# ===========================================================================
def extract_text_from_file(uploaded_file):
    try:
        if uploaded_file.name.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(uploaded_file)
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        elif uploaded_file.name.endswith(".docx"):
            import docx
            doc = docx.Document(uploaded_file)
            return "\n".join([p.text for p in doc.paragraphs])
        else:
            return uploaded_file.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""

def extract_candidate_data_from_text(resume_text):
    if not gemini_model or not resume_text.strip():
        return []
        
    prompt = f"""
    You are an expert HR Data Extraction Specialist for an industrial petroleum & refining corporation.
    Analyze the following document text carefully. The document may contain ONE single resume or MULTIPLE resumes/CVs merged together.
    
    Identify EACH candidate distinctly. For every candidate found, extract their information into a valid JSON array.
    
    Format:
    [
      {{
        "name": "Full Name",
        "father_name": "Father Name or Not Provided",
        "education": "Qualification / Degree Title (e.g. BS Chemical / Mechanical Engineering)",
        "cgpa": "CGPA / GPA / Percentage or Not Provided",
        "passing_year": "Passing / Graduation Year (e.g. 2023) or Not Provided",
        "university_name": "Institute / University Name or Not Provided",
        "dob": "Date of Birth or Not Provided",
        "email": "Email Address or Not Provided",
        "phone": "Phone Number or Not Provided",
        "experience_years": "Total Experience (e.g. 3 Years, Fresh)",
        "latest_experience": "Latest job role and company or Not Provided",
        "reference": "Reference contacts or Not Provided",
        "skills": ["Skill1", "Skill2"]
      }}
    ]

    Rules:
    - Never merge two different people into one object.
    - If a field is missing, write 'Not Provided'.
    - Output strictly valid JSON array with no markdown code blocks.

    DOCUMENT TEXT:
    {resume_text}
    """
    try:
        response = gemini_model.generate_content(prompt)
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip("` \n")
        parsed = json.loads(raw_text)
        return [parsed] if isinstance(parsed, dict) else parsed
    except Exception:
        return []

# ===========================================================================
# 9. AUTHENTICATION & LOGIN SCREEN
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()
    
    col_c1, col_c2, col_c3 = st.columns([1, 3.8, 1])
    with col_c2:
        with st.container(border=True):
            st.markdown(f"""
                <div class="cyber-header-box">
                    <div style="display: flex; justify-content: center; margin-bottom: 12px;">
                        <div style="
                            width: 68px; 
                            height: 68px; 
                            border-radius: 18px; 
                            background: linear-gradient(135deg, rgba(0, 242, 254, 0.15) 0%, rgba(15, 23, 42, 0.9) 100%);
                            border: 2px solid #00F2FE;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 0 25px rgba(0, 242, 254, 0.4), inset 0 0 15px rgba(0, 242, 254, 0.2);
                        ">
                            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#00F2FE" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                                <polyline points="2 17 12 22 22 17"></polyline>
                                <polyline points="2 12 12 17 22 12"></polyline>
                            </svg>
                        </div>
                    </div>
                    <h1 class="cyber-title">ARL HireMatrix <span class="cyber-title-pro">Pro</span></h1>
                    <div class="cyber-badge">
                        <span>◈</span> {APP_TAGLINE} <span>◈</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.pending_pin_email:
                st.markdown("### 🔐 Security PIN Setup")
                st.info(f"Create a 4-digit security PIN for **{st.session_state.pending_pin_email}**.")
                with st.form("pin_setup_form"):
                    new_pin = st.text_input("4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                    confirm_pin = st.text_input("Confirm PIN", type="password", max_chars=4, placeholder="••••")
                    submit_pin = st.form_submit_button("Save PIN & Continue", use_container_width=True)
                if submit_pin:
                    if len(new_pin) != 4 or not new_pin.isdigit():
                        st.warning("PIN must be exactly 4 numeric digits.")
                    elif new_pin != confirm_pin:
                        st.error("PINs do not match.")
                    else:
                        success, msg = save_employee_pin(st.session_state.pending_pin_email, new_pin)
                        if success:
                            st.success(msg)
                            st.session_state.pending_pin_email = None
                            st.rerun()

            elif saved_profiles and not st.session_state.selected_profile_email:
                st.markdown("""
                    <div style="margin-bottom: 12px;">
                        <h3 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: #00F2FE;">👥 Active Executive Profiles</h3>
                        <p style="font-size: 0.85rem; color: #94A3B8; margin-top: 4px;">Select your digital access badge to sign in:</p>
                    </div>
                """, unsafe_allow_html=True)
                
                for p_email, p_name, p_pin, p_role in saved_profiles:
                    st.markdown(f"""
                        <div class="cyber-badge-card">
                            <div class="cyber-top-bar">
                                <span class="cyber-access-id">ARL // {hashlib.md5(p_email.encode()).hexdigest()[:8].upper()}</span>
                                <span class="cyber-status-dot">ONLINE</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 16px;">
                                <div class="cyber-avatar-ring">👤</div>
                                <div style="flex-grow: 1;">
                                    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                                        <h3 class="cyber-name-title">{p_name}</h3>
                                        <span class="cyber-role-pill">{p_role}</span>
                                    </div>
                                    <div class="cyber-email-mono">✉ {p_email}</div>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    c_btn1, c_btn2 = st.columns([3, 1.2])
                    with c_btn1:
                        if st.button(f"🔐 Sign In as {p_name}", use_container_width=True, key=f"sel_card_{p_email}"):
                            st.session_state.selected_profile_email = p_email
                            st.rerun()
                    with c_btn2:
                        if st.button("🗑️ Delete", use_container_width=True, key=f"del_card_{p_email}"):
                            delete_employee_profile(p_email)
                            st.success("Profile removed.")
                            st.rerun()
                    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)
                
                st.markdown("---")
                if st.button("➕ Register New Profile", use_container_width=True, key="reg_new_emp_btn"):
                    st.session_state.selected_profile_email = "new"
                    st.rerun()

            elif st.session_state.selected_profile_email and st.session_state.selected_profile_email != "new":
                target_email = st.session_state.selected_profile_email
                p_match = next((p for p in saved_profiles if p[0] == target_email), ("admin@arl.com.pk", "Admin", "", "Admin"))
                st.markdown(f"### 🔐 Sign In: {p_match[1]}")
                st.caption(f"Enter 4-digit PIN for {target_email}")
                
                with st.form("pin_form"):
                    pin_in = st.text_input("4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                    sub_btn = st.form_submit_button("Access Portal", use_container_width=True)
                    
                col_s1, col_s2 = st.columns(2)
                if sub_btn:
                    success, name, role = verify_employee_pin(target_email, pin_in)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.hr_name = name
                        st.session_state.hr_email = target_email
                        st.session_state.hr_role = role
                        st.rerun()
                    else:
                        st.error("Incorrect PIN. Please try again.")
                with col_s2:
                    if st.button("Switch Profile", use_container_width=True):
                        st.session_state.selected_profile_email = None
                        st.rerun()
            else:
                st.markdown("### 📝 Register New Profile")
                with st.form("reg_form"):
                    reg_name = st.text_input("Full Name")
                    reg_email = st.text_input("Work Email (@arl.com.pk)")
                    reg_pass = st.text_input("Master Password", type="password")
                    sub_reg = st.form_submit_button("Register & Setup PIN", use_container_width=True)
                col_r1, col_r2 = st.columns(2)
                if sub_reg:
                    if not reg_name or not reg_email:
                        st.warning("Please fill all fields.")
                    else:
                        success, msg = register_initial_employee(reg_name, reg_email, reg_pass)
                        if success:
                            st.session_state.pending_pin_email = reg_email.lower().strip()
                            st.session_state.selected_profile_email = None
                            st.rerun()
                with col_r2:
                    if st.button("Back to Profiles", use_container_width=True):
                        st.session_state.selected_profile_email = None
                        st.rerun()
    st.stop()

# ===========================================================================
# 10. TOP DASHBOARD NAVIGATION BAR (CYBER EMBLEM LOGO)
# ===========================================================================
col_n1, col_n2 = st.columns([8.2, 1.8], vertical_alignment="center")
with col_n1:
    st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 16px; padding: 0.5rem 0 1.2rem 0;">
            <div style="
                width: 48px; 
                height: 48px; 
                border-radius: 14px; 
                background: linear-gradient(135deg, rgba(0, 242, 254, 0.18) 0%, rgba(15, 23, 42, 0.9) 100%);
                border: 2px solid #00F2FE;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 0 20px rgba(0, 242, 254, 0.45), inset 0 0 10px rgba(0, 242, 254, 0.2);
                flex-shrink: 0;
            ">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#00F2FE" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                    <polyline points="2 17 12 22 22 17"></polyline>
                    <polyline points="2 12 12 17 22 12"></polyline>
                </svg>
            </div>
            <div>
                <h2 style="margin: 0; font-size: 1.55rem; color: #00F2FE; font-family: 'Space Grotesk', sans-serif;">ARL HireMatrix <span style="color: #38BDF8;">Pro</span></h2>
                <p style="margin: 3px 0 0 0; font-size: 0.85rem; color: #94A3B8;">
                    Attock Refinery Limited • Active: <b>{st.session_state.hr_name}</b> ({st.session_state.hr_email}) &bull; Role: <b>{st.session_state.hr_role}</b>
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_n2:
    if st.button("🚪 Lock Portal", use_container_width=True, key="lock_portal_top_btn"):
        st.session_state.logged_in = False
        st.session_state.selected_profile_email = None
        st.rerun()

# ===========================================================================
# 11. MAIN RECRUITER WORKFLOW TABS
# ===========================================================================
tab1, tab2, tab3 = st.tabs([
    "📥 Step 1: Ingest & Extract Resumes", 
    "⚡ Step 2: AI Candidate Screening", 
    "🗄️ Step 3: Live Synchronized Grids"
])

# ----------------- TAB 1: RESUME EXTRACTION (MULTI-CANDIDATES SUPPORT) -----------------
with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Ingest & Parse Candidate Resumes (Single / Multi-CV PDF)</h4>', unsafe_allow_html=True)
    st.caption("Upload individual resumes or bulk merged PDFs containing multiple candidates.")
    
    uploaded_files = st.file_uploader(
        "Upload Candidate Documents (.pdf, .docx, .txt)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("🚀 Process & Extract All Candidates", use_container_width=True):
            total_added = 0
            with st.spinner("Extracting candidate profiles via Gemini AI..."):
                for f in uploaded_files:
                    text_content = extract_text_from_file(f)
                    candidates = extract_candidate_data_from_text(text_content)
                    if candidates:
                        for cand in candidates:
                            save_candidate_to_database(cand)
                            total_added += 1
                        st.success(f"Extracted **{len(candidates)} candidate(s)** from `{f.name}`.")
                    else:
                        st.warning(f"Could not parse valid candidate data from `{f.name}`.")
            st.success(f"🎉 Ingested **{total_added} candidate(s)** into Master Talent Pool!")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 2: AI SCREENING ENGINE (ARL CASCADING JOB MENU & EDITOR) -----------------
with tab2:
    st.markdown('<div class="corp-card"><h4>⚡ AI Job Description Screening & Semantic Match</h4>', unsafe_allow_html=True)
    st.caption("Select Target Position from ARL Department & Job Titles hierarchy, or customize on the fly.")
    
    # Load ARL Catalog
    arl_catalog = load_arl_job_catalog()
    dept_options = list(arl_catalog.keys())
    
    col_dept, col_job = st.columns(2)
    with col_dept:
        chosen_dept = st.selectbox("🏢 Select ARL Department", dept_options, index=0)
        
    available_jobs = arl_catalog.get(chosen_dept, [])
    job_dropdown_list = available_jobs + ["✍️ Custom / Other Job Title..."]
    
    with col_job:
        chosen_job_item = st.selectbox(f"💼 Select Job Designation ({chosen_dept})", job_dropdown_list, index=0)
        
    if chosen_job_item == "✍️ Custom / Other Job Title...":
        jd_title = st.text_input("Enter Specific Job Designation", placeholder="e.g. Lead Turnaround Planning Specialist")
    else:
        jd_title = chosen_job_item
        
    st.info(f"Target Position Selected: **{jd_title}** *(Department: {chosen_dept})*")
    
    # ⚙️ LIVE ARL JOB CATALOG MANAGER (ADD / EDIT / DELETE)
    with st.expander("⚙️ Manage ARL Job Catalog (Add, Edit, or Remove Jobs & Departments)"):
        st.caption("Permanently modify or add job positions in the ARL database hierarchy.")
        m_tab1, m_tab2, m_tab3 = st.tabs(["➕ Add New Job", "✏️ Edit / Rename Job", "🗑️ Delete Job"])
        
        # 1. Add New Job
        with m_tab1:
            col_ad1, col_ad2 = st.columns(2)
            with col_ad1:
                dept_mode = st.radio("Department Mode", ["Existing Department", "New Department"], horizontal=True)
                if dept_mode == "Existing Department":
                    target_dept_add = st.selectbox("Choose Department", dept_options, key="add_exist_dept")
                else:
                    target_dept_add = st.text_input("New Department Name", placeholder="e.g. Digital Transformation", key="add_new_dept")
            with col_ad2:
                new_title_add = st.text_input("New Job Title", placeholder="e.g. Data Scientist")
                if st.button("➕ Add to ARL Catalog", use_container_width=True, key="btn_add_arl_job"):
                    if target_dept_add and new_title_add:
                        ok, msg = add_arl_job_to_db(target_dept_add, new_title_add)
                        if ok:
                            st.success(f"Added **{new_title_add}** under **{target_dept_add}**!")
                            st.rerun()
                    else:
                        st.warning("Please specify both department and job title.")

        # 2. Edit / Rename Job
        with m_tab2:
            col_ed1, col_ed2 = st.columns(2)
            with col_ed1:
                edit_dept_sel = st.selectbox("Department", dept_options, key="edit_dept_sel")
                edit_job_sel = st.selectbox("Select Job to Edit", arl_catalog.get(edit_dept_sel, []), key="edit_job_sel")
            with col_ed2:
                updated_job_name = st.text_input("New Job Title Name", value=edit_job_sel if edit_job_sel else "", key="edit_job_input")
                updated_dept_name = st.text_input("New Department Name", value=edit_dept_sel, key="edit_dept_input")
                if st.button("💾 Update Job Title", use_container_width=True, key="btn_update_arl_job"):
                    if edit_job_sel and updated_job_name:
                        ok, msg = edit_arl_job_in_db(edit_dept_sel, edit_job_sel, updated_dept_name, updated_job_name)
                        if ok:
                            st.success("Designation updated successfully!")
                            st.rerun()

        # 3. Delete Job
        with m_tab3:
            col_del1, col_del2 = st.columns(2)
            with col_del1:
                del_dept_sel = st.selectbox("Department", dept_options, key="del_dept_sel")
            with col_del2:
                del_job_sel = st.selectbox("Select Job to Remove", arl_catalog.get(del_dept_sel, []), key="del_job_sel")
                if st.button("🗑️ Delete Job Designation", type="secondary", use_container_width=True, key="btn_del_arl_job"):
                    if del_dept_sel and del_job_sel:
                        ok, msg = delete_arl_job_from_db(del_dept_sel, del_job_sel)
                        if ok:
                            st.success(f"Removed **{del_job_sel}** from catalog.")
                            st.rerun()

    st.markdown("---")
    jd_desc = st.text_area("Paste Job Description (JD) Requirements", height=150, placeholder="Key skills, qualification, technical refinery requirements...")
    
    if st.button("🔍 Run AI Candidate Screening", use_container_width=True):
        if not jd_title.strip() or not jd_desc.strip():
            st.warning("Please ensure Job Title and Job Description are provided.")
        else:
            db_candidates = load_database()
            if db_candidates.empty:
                st.warning("No candidates found in database. Please upload resumes in Step 1 first.")
            else:
                with st.spinner("Analyzing candidate relevance against Job Description..."):
                    cands_list = db_candidates.to_dict(orient="records")
                    screen_prompt = f"""
                    You are an expert HR Recruitment Screening AI for Attock Refinery Limited (ARL).
                    JOB POSITION: {jd_title} (Department: {chosen_dept})
                    JOB DESCRIPTION:
                    {jd_desc}

                    CANDIDATES POOL:
                    {json.dumps(cands_list)}

                    Evaluate each candidate strictly for this industrial petroleum refining position.
                    Return a JSON array of objects with:
                    [
                      {{
                        "name": "Candidate Name",
                        "match_score": 85, (0 to 100 numeric score)
                        "missing_skills": ["Skill1", "Skill2"],
                        "interview_questions": ["Question 1", "Question 2"],
                        "summary_reason": "Why this candidate matches or doesn't match"
                      }}
                    ]
                    Output ONLY valid JSON array without markdown wrapping.
                    """
                    try:
                        ai_res = gemini_model.generate_content(screen_prompt)
                        raw = ai_res.text.strip()
                        if raw.startswith("```"):
                            raw = raw.split("```")[1]
                            if raw.startswith("json"):
                                raw = raw[4:]
                        raw = raw.strip("` \n")
                        evaluations = json.loads(raw)
                        
                        screened_final = []
                        for ev in evaluations:
                            orig = next((c for c in cands_list if c["Name"].lower() == ev["name"].lower()), {})
                            screened_final.append({
                                "job_title": jd_title,
                                "name": ev.get("name", orig.get("Name", "Unknown")),
                                "father_name": orig.get("Father Name", "Not Provided"),
                                "education": orig.get("Qualification", "Not Provided"),
                                "cgpa": orig.get("CGPA", "Not Provided"),
                                "passing_year": orig.get("Passing Year", "Not Provided"),
                                "university_name": orig.get("Institute", "Not Provided"),
                                "dob": orig.get("DOB", "Not Provided"),
                                "email": orig.get("Email", "Not Provided"),
                                "phone": orig.get("Phone Number", "Not Provided"),
                                "experience_years": orig.get("Experience", "0"),
                                "latest_experience": orig.get("Latest Experience", "Not Provided"),
                                "reference": orig.get("Reference", "Not Provided"),
                                "match_score": ev.get("match_score", 50),
                                "missing_skills": ev.get("missing_skills", []),
                                "interview_questions": ev.get("interview_questions", []),
                                "pipeline_status": "Shortlisted"
                            })
                        
                        screened_final.sort(key=lambda x: x["match_score"], reverse=True)
                        st.session_state.screening_results = screened_final
                        save_screened_to_supabase(screened_final)
                        st.success(f"Screening complete! Evaluated {len(screened_final)} candidate(s) & saved to Supabase.")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Screening error: {err}")

    # Display Screening Results
    if st.session_state.screening_results:
        st.markdown("### 📊 Screened Pipeline & Decision Center")
        for i, cand in enumerate(st.session_state.screening_results):
            score = cand["match_score"]
            badge_color = "#10B981" if score >= 75 else "#F59E0B" if score >= 50 else "#EF4444"
            with st.expander(f"**{cand['name']}** — Match Score: {score}% | Status: {cand['pipeline_status']}"):
                col_e1, col_e2 = st.columns([2, 1])
                with col_e1:
                    st.write(f"**Target Role:** {cand.get('job_title', 'Not Specified')}")
                    st.write(f"**Qualification:** {cand['education']} ({cand['university_name']})")
                    st.write(f"**CGPA:** {cand['cgpa']} | **Passing Year:** {cand['passing_year']}")
                    st.write(f"**Experience:** {cand['experience_years']} | **Latest:** {cand['latest_experience']}")
                    st.write(f"**Missing Skills:** {', '.join(cand['missing_skills']) if cand['missing_skills'] else 'None'}")
                    if cand.get("interview_questions"):
                        st.markdown("**Suggested Technical Interview Questions:**")
                        for q in cand["interview_questions"]:
                            st.write(f"- {q}")
                with col_e2:
                    current_status = cand.get("pipeline_status", "Shortlisted")
                    new_stage = st.selectbox(
                        "Update Pipeline Stage",
                        ["Shortlisted", "Interviewing", "Offered", "Rejected"],
                        index=["Shortlisted", "Interviewing", "Offered", "Rejected"].index(current_status),
                        key=f"stage_sel_{i}_{cand['name']}"
                    )
                    if new_stage != current_status:
                        cand["pipeline_status"] = new_stage
                        update_screened_candidate_status(cand["email"], cand["job_title"], new_stage)
                        st.success(f"Status updated to {new_stage}!")
                        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 3: DUAL LIVE SYNCHRONIZED GRIDS -----------------
with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Live Database & Screening Grids</h4>', unsafe_allow_html=True)
    st.caption("Real-time synchronized candidate records from Supabase Cloud.")
    
    sub_grid_1, sub_grid_2 = st.tabs(["🎯 Screened Candidates Grid", "📥 Master Talent Pool Grid"])
    
    # Grid 1: Screened Candidates
    with sub_grid_1:
        df_screened = load_screened_database()
        if df_screened.empty:
            st.info("No candidates have been screened yet. Run AI Screening in Step 2 to populate this live cloud grid.")
        else:
            grid_s = df_screened.copy()
            grid_s.insert(0, "Sr. No", range(1, len(grid_s) + 1))
            st.data_editor(grid_s, use_container_width=True, height=420, disabled=True, key="screened_grid_view_live")
            st.markdown("---")
            c_s1, c_s2 = st.columns([2, 1])
            with c_s1:
                st.download_button(
                    "📊 Download Screened Report (.xlsx)",
                    data=generate_repository_excel(df_screened),
                    file_name="ARL_Screened_Candidates.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_screened_master_grid_btn"
                )
            with c_s2:
                if st.button("🗑️ Clear Screened History", type="secondary", key="clear_screened_btn_grid", use_container_width=True):
                    clear_screened_database()
                    st.success("Screened records cleared successfully!")
                    st.rerun()

    # Grid 2: Master Talent Repository Grid (Exact 13-column sequence)
    with sub_grid_2:
        df_db = load_database()
        if df_db.empty:
            st.info("Master database is currently empty. Upload resumes in Step 1.")
        else:
            grid_df = df_db.copy()
            grid_df.insert(0, "Sr. No", range(1, len(grid_df) + 1))
            st.data_editor(grid_df, use_container_width=True, height=420, disabled=True, key="master_excel_grid_view")
            st.markdown("---")
            c_ex1, c_ex2 = st.columns([2, 1])
            with c_ex1:
                st.download_button(
                    "📊 Download Master Talent Repository Report (.xlsx)", 
                    data=generate_repository_excel(df_db), 
                    file_name="ARL_Master_Talent_Repository.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                    use_container_width=True, 
                    key="download_live_grid_xlsx_btn"
                )
            with c_ex2:
                if st.button("🗑️ Clear Entire Database", type="secondary", key="clear_db_btn_master_grid", use_container_width=True):
                    clear_candidate_database()
                    st.success("Master repository cleared successfully!")
                    st.rerun()
                    
    st.markdown("</div>", unsafe_allow_html=True)
