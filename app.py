"""
Arl TalentMatch: AI-Driven Automated CV Parser & JD Matcher
=============================================================================
Branding: Attock Refinery Limited (ARL Official Forest Green & Charcoal Palette)
Features: True Netflix Profile Selection UX, Two-State 'Manage Profiles' Flow,
Clean Focused Single-Card PIN Modal, Supabase Sync, and ATS Screening Engine.
"""

import io
import json
import os
import re
import hashlib
import random
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
from supabase import create_client, Client
from PIL import Image, ImageOps, ImageEnhance, ImageDraw

# ===========================================================================
# 1. PAGE CONFIGURATION & ARL GREEN HEXAGON FAVICON
# ===========================================================================
APP_NAME = "Arl TalentMatch: AI-Driven Automated CV Parser & JD Matcher"
APP_TAGLINE = "Attock Refinery Limited (ARL) • HR Intelligence & AI Screening Engine"
GROQ_MODEL = "openai/gpt-oss-120b"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]

PROFESSIONAL_STICKERS = {
    "👔": "Executive / HR Lead",
    "🛢️": "Refinery Operations",
    "🔬": "QC Petroleum Chemist",
    "⚙️": "Process Engineer",
    "🛡️": "HSE & Safety Lead",
    "💻": "IT & Automation Specialist",
    "📊": "Commercial & Finance",
    "🎯": "Talent Acquisition Lead",
    "👷": "Plant Maintenance Specialist",
    "⚡": "Power & Energy Lead",
    "👑": "Chief Executive",
    "🚀": "Turnaround Specialist"
}

AVATAR_STORAGE_FILE = "user_avatars.json"
EXE_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/ARL-HireMatrix-Pro_1.0.0_x64_en-US.msi"

def get_arl_favicon():
    img = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon([(32, 6), (58, 20), (58, 44), (32, 58), (6, 44), (6, 20)], outline=(34, 197, 94), width=5)
    draw.polygon([(32, 16), (46, 25), (46, 39), (32, 48), (18, 39), (18, 25)], fill=(22, 101, 52))
    return img

st.set_page_config(
    page_title=f"{APP_NAME} | Corporate Portal",
    page_icon=get_arl_favicon(),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ===========================================================================
# 2. SUPABASE CLOUD DATABASE CONNECTION & AUTH LOGIC
# ===========================================================================
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠ Supabase Connection Error: {e}")
        return None

supabase: Client = init_supabase()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def send_smtp_email(receiver_email, subject, body_text):
    try:
        sender_email = st.secrets["SMTP_EMAIL"]
        sender_password = st.secrets["SMTP_PASSWORD"]
    except Exception:
        return False, "SMTP credentials are not configured in Streamlit secrets."

    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr(("ARL Recruitment Notifications", sender_email))
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True, "Email dispatched successfully!"
    except Exception as e:
        return False, f"Failed to send email: {e}"

def load_local_avatars():
    if os.path.exists(AVATAR_STORAGE_FILE):
        try:
            with open(AVATAR_STORAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_local_avatar(email, sticker):
    data = load_local_avatars()
    data[email.lower().strip()] = sticker
    try:
        with open(AVATAR_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

def get_default_sticker(email: str) -> str:
    stickers = list(PROFESSIONAL_STICKERS.keys())
    idx = int(hashlib.md5(email.encode()).hexdigest(), 16) % len(stickers)
    return stickers[idx]

def get_user_sticker(email: str, db_avatar: str = None) -> str:
    clean = email.lower().strip()
    if "custom_stickers" in st.session_state and clean in st.session_state.custom_stickers:
        return st.session_state.custom_stickers[clean]
    local_data = load_local_avatars()
    if clean in local_data:
        return local_data[clean]
    if db_avatar:
        return db_avatar
    return get_default_sticker(email)

def update_user_sticker(email: str, sticker: str):
    clean = email.lower().strip()
    if "custom_stickers" not in st.session_state:
        st.session_state.custom_stickers = {}
    st.session_state.custom_stickers[clean] = sticker
    save_local_avatar(clean, sticker)
    if supabase:
        try:
            supabase.table("hr_users").update({"avatar": sticker}).eq("email", clean).execute()
        except Exception:
            pass
        try:
            supabase.table("employees").update({"avatar": sticker}).eq("email", clean).execute()
        except Exception:
            pass
    return True

def verify_employee_pin(email, entered_pin):
    clean_email = email.lower().strip()
    entered_str = str(entered_pin).strip()

    cached = get_all_verified_profiles()
    for p_email, p_name, p_pin, p_role, p_sticker in cached:
        if p_email.lower().strip() == clean_email:
            if str(p_pin).strip() == entered_str:
                return True, p_name, p_role

    if not supabase:
        return False, None, None

    try:
        res = supabase.table("hr_users").select("*").ilike("email", clean_email).execute()
        if res.data:
            rec = res.data[0]
            if str(rec.get("pin", "")).strip() == entered_str:
                return True, rec.get("name", "Employee"), rec.get("role", "Recruiter")
    except Exception:
        pass

    try:
        res2 = supabase.table("employees").select("*").ilike("email", clean_email).execute()
        if res2.data:
            rec = res2.data[0]
            if str(rec.get("pin", "")).strip() == entered_str:
                return True, rec.get("name", "Employee"), rec.get("role", "Recruiter")
    except Exception:
        pass

    return False, None, None

def get_all_verified_profiles():
    if not supabase:
        default_stk = get_user_sticker("admin@arl.com.pk", "🛢️️")
        return [("admin@arl.com.pk", "ARL Admin", "1234", "Admin", default_stk)]
    profiles = []
    try:
        res = supabase.table("hr_users").select("*").execute()
        if res.data:
            for r in res.data:
                if r.get("pin"):
                    email = r.get("email")
                    sticker = get_user_sticker(email, r.get("avatar"))
                    profiles.append((email, r.get("name"), str(r.get("pin")), r.get("role", "Recruiter"), sticker))
    except Exception:
        pass
    try:
        res2 = supabase.table("employees").select("*").execute()
        if res2.data:
            existing_emails = [p[0].lower() for p in profiles]
            for r in res2.data:
                em = r.get("email", "")
                if r.get("pin") and em.lower() not in existing_emails:
                    sticker = get_user_sticker(em, r.get("avatar"))
                    profiles.append((em, r.get("name"), str(r.get("pin")), r.get("role", "Recruiter"), sticker))
    except Exception:
        pass
    return profiles

def get_all_verified_profiles_admin():
    return get_all_verified_profiles()

def register_initial_employee(name, email, password, sticker="👔"):
    clean_email = email.lower().strip()
    otp = str(random.randint(100000, 999999))
    if not supabase:
        return False, "Supabase client not initialized."
    try:
        existing = supabase.table("hr_users").select("pin").eq("email", clean_email).execute().data
        if existing and existing[0].get("pin"):
            return False, "This email is already registered and active. Please sign in."
        
        count_res = supabase.table("hr_users").select("email", count="exact").execute()
        count = count_res.count if count_res.count is not None else 0
        role = "Admin" if count == 0 else "Recruiter"
        
        data = {
            "email": clean_email,
            "name": name,
            "password": hash_password(password),
            "pin": None,
            "role": role,
            "is_verified": 0,
            "otp": otp,
            "avatar": sticker
        }
        supabase.table("hr_users").upsert(data).execute()
        update_user_sticker(clean_email, sticker)
        
        success, msg = send_smtp_email(clean_email, "ARL TalentMatch - Verification OTP", f"Your verification code is: {otp}")
        if success:
            return True, "Registration initiated! Please check your email for the verification OTP."
        else:
            return False, msg
    except Exception as e:
        return False, f"Error: {e}"

def verify_otp_code(email, entered_otp):
    if not supabase:
        return False, "Supabase client not initialized."
    try:
        response = supabase.table("hr_users").select("otp").eq("email", email.lower().strip()).execute().data
        if response and response[0].get("otp") == entered_otp:
            return True, "OTP verified successfully!"
    except Exception:
        pass
    return False, "Invalid OTP code. Please verify and try again."

def save_employee_pin(email, pin):
    if not supabase:
        return False, "Supabase client not initialized."
    clean_email = email.lower().strip()
    pin_str = str(pin).strip()
    try:
        supabase.table("hr_users").update({"pin": pin_str, "is_verified": 1}).eq("email", clean_email).execute()
    except Exception:
        pass
    try:
        supabase.table("employees").update({"pin": pin_str}).eq("email", clean_email).execute()
    except Exception:
        pass
    return True, "Security PIN configured successfully!"

def delete_employee_profile(email):
    if not supabase:
        return False, "Supabase client not initialized."
    clean_email = email.lower().strip()
    try:
        supabase.table("hr_users").delete().eq("email", clean_email).execute()
    except Exception:
        pass
    try:
        supabase.table("employees").delete().eq("email", clean_email).execute()
    except Exception:
        pass
    if "custom_stickers" in st.session_state and clean_email in st.session_state.custom_stickers:
        del st.session_state.custom_stickers[clean_email]
    return True, "Employee profile removed."

# ===========================================================================
# 3. ARL CORPORATE JOB CATALOG & HIERARCHY
# ===========================================================================
DEFAULT_ARL_CATALOG = {
    "Operations & Refining": [
        "Process Engineer", "Plant Shift Incharge", "Senior Plant Operator (CDU / Reformer)",
        "Control Room DCS Operator", "Refining Operations Manager", "Lead Commissioning Engineer"
    ],
    "Maintenance & Engineering": [
        "Mechanical Maintenance Engineer", "Electrical Maintenance Engineer",
        "Instrumentation & Control (I&C) Engineer", "Reliability & Inspection Engineer",
        "Turnaround & Maintenance Planning Specialist", "Rotary Equipment Specialist"
    ],
    "Technical Services & Quality Control (QC Lab)": [
        "Technical Services Engineer", "Senior Petroleum Chemist", "Lab Quality Analyst",
        "Corrosion & Metallurgy Engineer", "Catalyst & Yield Optimization Specialist"
    ],
    "Health, Safety, Environment & Security (HSE&S)": [
        "HSE Lead / Manager", "Process Safety Management (PSM) Specialist",
        "Fire & Industrial Safety Engineer", "Environmental Compliance Officer"
    ],
    "Supply Chain, Logistics & Procurement": [
        "Procurement & Contracts Lead", "Crude Oil Logistics & Storage Supervisor",
        "Commercial & Petroleum Dispatch Executive", "Warehouse & Inventory Controller"
    ],
    "Finance, Accounts & Commercial": [
        "Treasury & Budgeting Lead", "Corporate & Cost Accountant",
        "Internal Audit Executive", "Taxation & Compliance Specialist"
    ],
    "Human Resources & Administration": [
        "Talent Acquisition & Recruitment Specialist", "HR Operations & Payroll Executive",
        "Industrial Relations & Labor Compliance Officer", "Organizational Development (OD) Lead",
        "Administration & Estate Management Officer"
    ],
    "Information Technology & Industrial Automation": [
        "SAP ERP Functional Consultant", "SCADA & Process Automation Specialist",
        "IT Systems & Network Administrator", "Cyber Security Analyst"
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
# 4. CANDIDATE REPOSITORY & SCREENED STORAGE
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
        response = supabase.table("candidates").select("*").order("id", desc=False).execute()
        rows = response.data
        if rows:
            mapped_rows = []
            for r in rows:
                mapped_rows.append({
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
            return pd.DataFrame(mapped_rows)
    except Exception:
        pass
    return pd.DataFrame(columns=expected_cols)

def save_candidates_to_repository(new_candidates):
    if not supabase:
        return 0, 0
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_emails = set()
    existing_phones = set()
    try:
        res = supabase.table("candidates").select("email, phone").execute()
        if res.data:
            for r in res.data:
                em = str(r.get("email", "")).strip().lower()
                ph = re.sub(r"\D", "", str(r.get("phone", "")))
                if em and em != "not provided": existing_emails.add(em)
                if ph and len(ph) >= 7: existing_phones.add(ph)
    except Exception: pass

    inserted_count = 0
    skipped_count = 0
    for c in new_candidates:
        cand_email = str(c.get("email", "")).strip().lower()
        cand_phone = re.sub(r"\D", "", str(c.get("phone", "")))
        is_dup = False
        if cand_email and cand_email not in ["not provided", "not found", "", "nan"] and cand_email in existing_emails:
            is_dup = True
        elif cand_phone and len(cand_phone) >= 7 and cand_phone in existing_phones:
            is_dup = True
        if is_dup:
            skipped_count += 1
            continue

        payload = {
            "candidate_name": c.get("name", "Unknown"), "father_name": c.get("father_name", "Not Provided"),
            "education": c.get("education", "Not Provided"), "cgpa": c.get("cgpa", "Not Provided"),
            "passing_year": c.get("passing_year", "Not Provided"), "university_name": c.get("university_name", "Not Provided"),
            "dob": c.get("dob", "Not Provided"), "email": c.get("email", "Not Provided"),
            "phone": c.get("phone", "Not Provided"), "experience_years": str(c.get("experience_years", "0")),
            "latest_experience": c.get("latest_experience", "Not Provided"), "reference": c.get("reference", "Not Provided"),
            "pipeline_status": "Talent Pool", "added_at": current_timestamp
        }
        try:
            supabase.table("candidates").insert(payload).execute()
            inserted_count += 1
            if cand_email and cand_email not in ["not provided", "not found", "", "nan"]: existing_emails.add(cand_email)
            if cand_phone and len(cand_phone) >= 7: existing_phones.add(cand_phone)
        except Exception:
            pass
    return inserted_count, skipped_count

def delete_single_candidate_from_db(email_or_name):
    if not supabase: return
    try:
        supabase.table("candidates").delete().or_(f"email.ilike.{email_or_name},candidate_name.ilike.{email_or_name}").execute()
    except Exception: pass

def update_candidate_pipeline_status(email, new_status):
    if not supabase: return
    try:
        supabase.table("candidates").update({"pipeline_status": new_status}).ilike("email", email).execute()
    except Exception: pass

def clear_candidate_database():
    if not supabase: return
    try: supabase.table("candidates").delete().neq("id", 0).execute()
    except Exception: pass

def save_screened_to_supabase(screened_list):
    if not supabase or not screened_list: return
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in screened_list:
        skills_str = ", ".join(r.get("missing_skills", [])) if isinstance(r.get("missing_skills"), list) else str(r.get("missing_skills", ""))
        payload = {
            "job_title": r.get("job_title", "Not Specified"), "candidate_name": r.get("name", "Unknown"),
            "father_name": r.get("father_name", "Not Provided"), "education": r.get("education", "Not Provided"),
            "cgpa": r.get("cgpa", "Not Provided"), "passing_year": r.get("passing_year", "Not Provided"),
            "university_name": r.get("university_name", "Not Provided"), "dob": r.get("dob", "Not Provided"),
            "email": r.get("email", "Not Provided"), "phone": r.get("phone", "Not Provided"),
            "experience_years": str(r.get("experience_years", "0")), "latest_experience": r.get("latest_experience", "Not Provided"),
            "reference": r.get("reference", "Not Provided"), "match_score": float(r.get("match_score", 0)),
            "missing_skills": skills_str, "pipeline_status": r.get("pipeline_status", "Shortlisted"),
            "screened_at": current_timestamp
        }
        try: supabase.table("screened_candidates").insert(payload).execute()
        except Exception: pass

def load_screened_database():
    expected_cols = [
        "Job Title", "Match Score (%)", "Pipeline Status", "Name", "Father Name",
        "Qualification", "CGPA", "Passing Year", "Institute", "DOB", "Email",
        "Phone Number", "Experience", "Latest Experience", "Reference", "Missing Skills", "Screened At"
    ]
    if not supabase: return pd.DataFrame(columns=expected_cols)
    try:
        response = supabase.table("screened_candidates").select("*").order("id", desc=True).execute()
        rows = response.data
        if rows:
            mapped = []
            for r in rows:
                mapped.append({
                    "Job Title": r.get("job_title", "Not Specified"), "Match Score (%)": r.get("match_score", 0),
                    "Pipeline Status": r.get("pipeline_status", "Shortlisted"), "Name": r.get("candidate_name", "Unknown"),
                    "Father Name": r.get("father_name", "Not Provided"), "Qualification": r.get("education", "Not Provided"),
                    "CGPA": r.get("cgpa", "Not Provided"), "Passing Year": r.get("passing_year", "Not Provided"),
                    "Institute": r.get("university_name", "Not Provided"), "DOB": r.get("dob", "Not Provided"),
                    "Email": r.get("email", "Not Provided"), "Phone Number": r.get("phone", "Not Provided"),
                    "Experience": str(r.get("experience_years", "0")), "Latest Experience": r.get("latest_experience", "Not Provided"),
                    "Reference": r.get("reference", "Not Provided"), "Missing Skills": r.get("missing_skills", "None"),
                    "Screened At": r.get("screened_at", "")
                })
            return pd.DataFrame(mapped)
    except Exception: pass
    return pd.DataFrame(columns=expected_cols)

def update_screened_candidate_status(email, job_title, new_status):
    if not supabase: return
    try: supabase.table("screened_candidates").update({"pipeline_status": new_status}).ilike("email", email).ilike("job_title", job_title).execute()
    except Exception: pass

def clear_screened_database():
    if not supabase: return
    try: supabase.table("screened_candidates").delete().neq("id", 0).execute()
    except Exception: pass

def generate_repository_excel(df: pd.DataFrame) -> bytes:
    import openpyxl
    buffer = io.BytesIO()
    export_df = df.copy()
    export_df.insert(0, "Sr. No.", range(1, len(export_df) + 1))
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Candidates_Master")
        worksheet = writer.sheets["Candidates_Master"]
        worksheet.freeze_panes = "A2"
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 40)
            for cell in col:
                cell.alignment = openpyxl.styles.Alignment(wrap_text=True, vertical="top")
    buffer.seek(0)
    return buffer.getvalue()

def generate_screening_excel(results_list) -> bytes:
    import openpyxl
    buffer = io.BytesIO()
    data = []
    for idx, r in enumerate(results_list, start=1):
        data.append({
            "Sr. No.": idx, "Job Title": r.get("job_title", "Not Specified"), "Candidate Name": r["name"],
            "Father Name": r["father_name"], "Qualification": r["education"], "CGPA": r["cgpa"],
            "Passing Year": r["passing_year"], "Institute": r["university_name"], "DOB": r["dob"],
            "Email": r["email"], "Phone Number": r["phone"], "Experience": r["experience_years"],
            "Latest Experience": r["latest_experience"], "Reference": r["reference"],
            "Match Score (%)": r["match_score"], "Pipeline Status": r["pipeline_status"]
        })
    export_df = pd.DataFrame(data)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Screened_Results")
        worksheet = writer.sheets["Screened_Results"]
        worksheet.freeze_panes = "A2"
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 40)
            for cell in col:
                cell.alignment = openpyxl.styles.Alignment(wrap_text=True, vertical="top")
    buffer.seek(0)
    return buffer.getvalue()

# ===========================================================================
# 5. AUTHENTIC NETFLIX-THEME CSS & STREAMLINED DIALOG STYLING
# ===========================================================================
ARL_GREEN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

.stApp {
    background: radial-gradient(circle at 50% 10%, #0f3d24 0%, #072113 45%, #031008 100%) !important;
    color: #F8FAFC !important;
}

[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }

/* ------------------------------------------------------------- */
/* NETFLIX "WHO'S WATCHING?" AUTH LAYOUT & CARDS                 */
/* ------------------------------------------------------------- */
.netflix-header-container {
    text-align: center;
    margin-top: 1rem;
    margin-bottom: 2.2rem;
}
.netflix-main-title {
    font-size: 2.9rem !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    letter-spacing: -0.5px !important;
    margin: 0 0 8px 0 !important;
}
.netflix-sub-title {
    font-size: 0.95rem !important;
    color: #86EFAC !important;
    margin: 0 !important;
    font-weight: 500 !important;
}

/* Row Deck: Fixed Proportions, Centered, No Squeezing */
div[data-testid="column"]:has(.netflix-profile-wrapper) {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    min-width: 150px !important;
    max-width: 150px !important;
    margin: 0 10px 24px 10px !important;
}

.netflix-profile-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 140px;
    user-select: none;
}

/* Card Button: Exact 140px x 140px Rounded Tile */
.netflix-profile-wrapper button {
    width: 140px !important;
    height: 140px !important;
    min-width: 140px !important;
    min-height: 140px !important;
    border-radius: 12px !important;
    font-size: 4rem !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin: 0 !important;
    padding: 0 !important;
    background: linear-gradient(145deg, #134629 0%, #082416 100%) !important;
    border: 2px solid rgba(74, 222, 128, 0.35) !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.6) !important;
    transition: transform 0.2s ease-in-out, border-color 0.2s ease-in-out, box-shadow 0.2s ease-in-out !important;
    cursor: pointer !important;
}

.netflix-profile-wrapper:hover button {
    border-color: #FFFFFF !important;
    transform: scale(1.08) !important;
    box-shadow: 0 14px 30px rgba(0, 0, 0, 0.8), 0 0 15px rgba(74, 222, 128, 0.4) !important;
}

/* Manage Mode Active: Dim card & highlight pencil */
.netflix-manage-mode .netflix-profile-wrapper button {
    filter: brightness(0.7) !important;
    border-color: #4ADE80 !important;
}
.netflix-manage-mode .netflix-profile-wrapper:hover button {
    filter: brightness(1) !important;
    border-color: #86EFAC !important;
}

/* + Add Profile Card */
.netflix-add-card button {
    background: rgba(34, 197, 94, 0.05) !important;
    border: 2.5px dashed rgba(74, 222, 128, 0.45) !important;
    color: #86EFAC !important;
    font-size: 3rem !important;
}
.netflix-add-card:hover button {
    background: rgba(34, 197, 94, 0.15) !important;
    border-color: #FFFFFF !important;
    color: #FFFFFF !important;
}

.netflix-label-name {
    margin-top: 12px;
    font-size: 0.96rem;
    font-weight: 700;
    color: #94A3B8;
    text-align: center;
    line-height: 1.25;
    transition: color 0.2s ease;
}
.netflix-profile-wrapper:hover .netflix-label-name {
    color: #FFFFFF;
}

.netflix-label-role {
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    color: #4ADE80;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    text-align: center;
}

/* Manage Profiles Toggle Button */
.manage-profiles-toggle button {
    background: transparent !important;
    color: #94A3B8 !important;
    border: 1.5px solid #475569 !important;
    border-radius: 4px !important;
    padding: 8px 26px !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    transition: all 0.2s ease-in-out !important;
}
.manage-profiles-toggle button:hover {
    color: #FFFFFF !important;
    border-color: #FFFFFF !important;
    background: rgba(255, 255, 255, 0.05) !important;
}

/* ------------------------------------------------------------- */
/* SEAMLESS SINGLE-CARD PIN DIALOG MODAL                         */
/* ------------------------------------------------------------- */
div[data-testid="stModalBackdrop"], div[data-testid="stDialogBackdrop"] {
    background-color: rgba(3, 16, 9, 0.75) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
}

div[data-testid="stDialog"], div[role="dialog"] {
    background: #12161A !important;
    background-color: #12161A !important;
    border: 1.5px solid #22C55E !important;
    border-radius: 16px !important;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.9), 0 0 30px rgba(34, 197, 94, 0.25) !important;
    max-width: 320px !important;
    width: 320px !important;
    padding: 1.8rem !important;
    margin: auto !important;
}

div[data-testid="stDialog"] [data-testid="stForm"],
div[role="dialog"] [data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    box-shadow: none !important;
}

div[data-testid="stDialog"] input[type="password"] {
    font-size: 1.6rem !important;
    letter-spacing: 8px !important;
    text-align: center !important;
    background: #090C0E !important;
    border: 1.5px solid #22C55E !important;
    color: #FFFFFF !important;
    border-radius: 10px !important;
    height: 50px !important;
    margin-bottom: 0.8rem !important;
}

/* Portal Navbar & Cards */
.top-navbar {
    background: linear-gradient(135deg, rgba(14, 46, 29, 0.95) 0%, rgba(8, 28, 18, 0.95) 100%);
    border: 1.5px solid rgba(74, 222, 128, 0.25);
    border-bottom: 2.5px solid #22C55E;
    border-radius: 16px;
    padding: 1.1rem 2rem;
    margin-bottom: 1.8rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.corp-hero {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.18) 0%, rgba(8, 28, 18, 0.9) 100%);
    border: 1.5px solid rgba(74, 222, 128, 0.3);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    border-left: 6px solid #4ADE80;
}
.corp-badge {
    display: inline-flex; align-items: center; gap: 8px; 
    background: rgba(34, 197, 94, 0.2); color: #86EFAC; 
    padding: 5px 14px; border-radius: 6px;
    font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.8rem;
    border: 1px solid rgba(74, 222, 128, 0.4);
}
.corp-card {
    background: rgba(14, 46, 29, 0.65);
    border: 1.5px solid rgba(74, 222, 128, 0.25);
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
}
.corp-card h4 {
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    margin-top: 0 !important;
    margin-bottom: 1.2rem !important;
    background: linear-gradient(90deg, rgba(34, 197, 94, 0.18) 0%, rgba(22, 101, 52, 0.08) 100%) !important;
    border-left: 4px solid #4ADE80 !important;
    padding: 10px 16px !important;
    border-radius: 8px 12px 12px 8px !important;
}
.metric-box .val { font-size: 1.8rem; font-weight: 800; color: #4ADE80; }
.metric-box .lbl { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; font-weight: 700; color: #86EFAC; }
.score-high { color: #4ADE80 !important; font-weight: 800; }
.score-mid { color: #FBBF24 !important; font-weight: 800; }
.score-low { color: #F87171 !important; font-weight: 800; }

div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { display: none !important; }
div[data-baseweb="tab-list"] {
    background: rgba(10, 34, 21, 0.9) !important;
    border: 1.5px solid rgba(74, 222, 128, 0.25) !important;
    border-radius: 16px !important;
    padding: 6px 10px !important;
    gap: 8px !important;
    margin-bottom: 1.8rem !important;
}
button[data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 12px !important;
    padding: 8px 20px !important;
    color: #CBD5E1 !important;
    font-size: 0.92rem !important;
    font-weight: 700 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(22, 101, 52, 0.8) 0%, rgba(34, 197, 94, 0.35) 100%) !important;
    border: 1.5px solid #4ADE80 !important;
    color: #FFFFFF !important;
}
</style>
"""
st.markdown(ARL_GREEN_CSS, unsafe_allow_html=True)

# ===========================================================================
# 6. SESSION STATE INITIALIZATION & DESKTOP DETECTION
# ===========================================================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "hr_name" not in st.session_state: st.session_state.hr_name = ""
if "hr_email" not in st.session_state: st.session_state.hr_email = ""
if "hr_role" not in st.session_state: st.session_state.hr_role = "Recruiter"
if "manage_profiles_mode" not in st.session_state: st.session_state.manage_profiles_mode = False
if "pending_otp_email" not in st.session_state: st.session_state.pending_otp_email = None
if "pending_pin_email" not in st.session_state: st.session_state.pending_pin_email = None
if "register_mode" not in st.session_state: st.session_state.register_mode = False
if "screening_results" not in st.session_state: st.session_state.screening_results = []
if "show_download_page" not in st.session_state: st.session_state.show_download_page = False

if "is_desktop_mode" not in st.session_state:
    st.session_state.is_desktop_mode = (st.query_params.get("mode") == "desktop")
is_desktop_mode = st.session_state.is_desktop_mode or (st.query_params.get("mode") == "desktop")

def render_download_landing_page(exe_direct_url: str):
    c_back, _ = st.columns([2.5, 7.5])
    with c_back:
        if st.button("⬅️ Back to Web Portal", use_container_width=True, key="back_to_portal_from_dl"):
            st.session_state.show_download_page = False
            st.rerun()

    st.markdown(f"""
        <div style="text-align: center; padding: 3rem 1.5rem; background: linear-gradient(180deg, rgba(34, 197, 94, 0.22) 0%, rgba(8, 28, 18, 0.95) 100%); border: 1.5px solid rgba(74, 222, 128, 0.35); border-radius: 24px;">
            <h1 style="font-size: 3rem; font-weight: 800; color: #FFFFFF;">Arl TalentMatch for Windows</h1>
            <p style="color: #CBD5E1; font-size: 1.15rem; max-width: 650px; margin: 0 auto 2rem auto;">Download the standalone desktop installation suite for enterprise recruitment intelligence.</p>
            <a href="{exe_direct_url}" target="_blank" style="display: inline-block; background: #16A34A; color: #FFF; padding: 1rem 2.5rem; border-radius: 12px; font-weight: 800; text-decoration: none; border: 1.5px solid #4ADE80;">
                ⬇ Download ARL-HireMatrix-Pro.msi
            </a>
        </div>
    """, unsafe_allow_html=True)

if st.session_state.show_download_page:
    render_download_landing_page(EXE_DOWNLOAD_URL)
    st.stop()

# ===========================================================================
# 7. CLEAN SINGLE-CARD PIN DIALOG & BADGE PICKER
# ===========================================================================
if hasattr(st, "dialog"):
    @st.dialog("Enter Security PIN")
    def show_pin_dialog(target_email, p_name, p_role):
        components.html("""
        <script>
        (function autoFocus() {
            var attempts = 0;
            var timer = setInterval(function() {
                var doc = window.parent.document;
                var input = doc.querySelector('div[role="dialog"] input[type="password"], div[data-testid="stDialog"] input[type="password"]');
                if (input) {
                    input.focus();
                    input.select();
                    clearInterval(timer);
                }
                if (++attempts > 30) clearInterval(timer);
            }, 40);
        })();
        </script>
        """, height=0, width=0)

        st.caption(f"Signing in as **{p_name}**")
        with st.form("clean_pin_entry_form"):
            pin_input = st.text_input("PIN", type="password", max_chars=4, placeholder="••••", label_visibility="collapsed", key=f"pin_in_{target_email}")
            submitted = st.form_submit_button("Sign In ➔", use_container_width=True)

        if submitted or (pin_input and len(pin_input) == 4):
            success, name, role = verify_employee_pin(target_email, pin_input)
            if success:
                st.session_state.logged_in = True
                st.session_state.hr_name = name or p_name
                st.session_state.hr_email = target_email
                st.session_state.hr_role = role or p_role
                st.session_state.manage_profiles_mode = False
                st.rerun()
            else:
                st.error("❌ Incorrect PIN")

    @st.dialog("Edit Profile")
    def show_sticker_dialog(target_email, p_name):
        st.markdown(f"#### Change Badge for **{p_name}**")
        cols = st.columns(6)
        for idx, (stk, title) in enumerate(PROFESSIONAL_STICKERS.items()):
            with cols[idx % 6]:
                if st.button(stk, key=f"stk_select_{stk}_{idx}", help=title, use_container_width=True):
                    update_user_sticker(target_email, stk)
                    st.rerun()
                    
        st.markdown("---")
        c1, c2 = st.columns([1.5, 1])
        with c1:
            if st.button("🗑️ Delete Profile", key=f"del_prof_{target_email}", use_container_width=True):
                delete_employee_profile(target_email)
                st.rerun()
        with c2:
            if st.button("Done", key="close_edit_dialog", use_container_width=True):
                st.rerun()
else:
    def show_pin_dialog(e, n, r): pass
    def show_sticker_dialog(e, n): pass

# ===========================================================================
# 8. AUTHENTICATION & LOGIN SCREEN (NETFLIX PROFILE ARCHITECTURE)
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()

    if not is_desktop_mode:
        _, c_desk, _ = st.columns([7, 2.5, 0.5])
        with c_desk:
            if st.button("💻 Get Windows Desktop App", key="top_dl_btn", use_container_width=True):
                st.session_state.show_download_page = True
                st.rerun()

    # --- VIEW A: SECURITY PIN SETUP ---
    if st.session_state.pending_pin_email:
        _, center_col, _ = st.columns([1, 1.8, 1])
        with center_col:
            st.markdown("### 🔐 Configure 4-Digit PIN")
            st.info(f"Email verified for **{st.session_state.pending_pin_email}**.")
            with st.form("pin_setup_form"):
                new_pin = st.text_input("Enter 4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                confirm_pin = st.text_input("Confirm 4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                submit_pin = st.form_submit_button("Save PIN & Continue", use_container_width=True)
            if submit_pin:
                if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
                    st.warning("Please enter an exact 4-digit numeric PIN.")
                elif new_pin != confirm_pin:
                    st.error("PINs do not match. Please try again.")
                else:
                    success, msg = save_employee_pin(st.session_state.pending_pin_email, new_pin)
                    if success:
                        st.session_state.pending_pin_email = None
                        st.rerun()
                    else:
                        st.error(msg)

    # --- VIEW B: OTP VERIFICATION ---
    elif st.session_state.pending_otp_email:
        _, center_col, _ = st.columns([1, 1.8, 1])
        with center_col:
            st.markdown("### 📬 Verify Security Code")
            st.info(f"Enter the 6-digit code sent to **{st.session_state.pending_otp_email}**.")
            with st.form("otp_form"):
                otp_input = st.text_input("Enter 6-Digit OTP", placeholder="123456")
                submit_otp = st.form_submit_button("Verify OTP", use_container_width=True)
            if submit_otp:
                success, nag = verify_otp_code(st.session_state.pending_otp_email, otp_input)
                if success:
                    st.session_state.pending_pin_email = st.session_state.pending_otp_email
                    st.session_state.pending_otp_email = None
                    st.rerun()
                else:
                    st.error(nag)
            if st.button("Cancel", use_container_width=True, key="cancel_otp_btn"):
                st.session_state.pending_otp_email = None
                st.rerun()

    # --- VIEW C: AUTHENTIC NETFLIX "WHO'S WATCHING?" SCREEN ---
    elif saved_profiles and not st.session_state.register_mode:
        manage_mode = st.session_state.manage_profiles_mode

        title_text = "Manage Profiles" if manage_mode else "Who's In?"
        subtitle_text = "Select a profile to edit avatar or settings:" if manage_mode else "Select your executive profile to enter security PIN:"

        st.markdown(f"""
            <div class="netflix-header-container">
                <h1 class="netflix-main-title">{title_text}</h1>
                <p class="netflix-sub-title">{subtitle_text}</p>
            </div>
        """, unsafe_allow_html=True)

        if manage_mode:
            st.markdown('<div class="netflix-manage-mode">', unsafe_allow_html=True)

        total_items = len(saved_profiles) + 1
        deck_cols = st.columns(total_items)

        # 1. Existing Profiles
        for idx, (p_email, p_name, p_pin, p_role, p_sticker) in enumerate(saved_profiles):
            with deck_cols[idx]:
                st.markdown('<div class="netflix-profile-wrapper">', unsafe_allow_html=True)
                
                button_display = "✏️" if manage_mode else p_sticker
                btn_action = st.button(button_display, key=f"net_prof_tile_{idx}")
                
                if btn_action:
                    if manage_mode:
                        show_sticker_dialog(p_email, p_name)
                    else:
                        show_pin_dialog(p_email, p_name, p_role)

                st.markdown(f"""
                    <div class="netflix-label-name">{p_name}</div>
                    <div class="netflix-label-role">{p_role}</div>
                </div>
                """, unsafe_allow_html=True)

        # 2. Add Profile Tile
        with deck_cols[-1]:
            st.markdown('<div class="netflix-profile-wrapper netflix-add-card">', unsafe_allow_html=True)
            if st.button("＋", key="net_add_profile_card"):
                st.session_state.register_mode = True
                st.session_state.manage_profiles_mode = False
                st.rerun()
            st.markdown("""
                <div class="netflix-label-name">Add Profile</div>
                <div class="netflix-label-role">REGISTER</div>
            </div>
            """, unsafe_allow_html=True)

        if manage_mode:
            st.markdown('</div>', unsafe_allow_html=True)

        # 3. Two-State Netflix "Manage Profiles" Toggle Button
        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
        _, btn_center, _ = st.columns([4, 2.5, 4])
        with btn_center:
            st.markdown('<div class="manage-profiles-toggle">', unsafe_allow_html=True)
            if manage_mode:
                if st.button("DONE", key="toggle_done_mode", use_container_width=True):
                    st.session_state.manage_profiles_mode = False
                    st.rerun()
            else:
                if st.button("MANAGE PROFILES", key="toggle_manage_mode", use_container_width=True):
                    st.session_state.manage_profiles_mode = True
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # --- VIEW D: REGISTER NEW EMPLOYEE PROFILE ---
    else:
        _, center_col, _ = st.columns([1, 1.8, 1])
        with center_col:
            st.markdown("### 📝 Register Executive Profile")
            with st.form("reg_form_clean"):
                reg_name = st.text_input("Full Name", placeholder="Alex Mercer")
                reg_email = st.text_input("Corporate Email (@arl.com.pk)", placeholder="employee@arl.com.pk")
                reg_pass = st.text_input("Account Password", type="password")
                reg_sticker = st.selectbox(
                    "Select Initial Badge",
                    options=list(PROFESSIONAL_STICKERS.keys()),
                    format_func=lambda x: f"{x} {PROFESSIONAL_STICKERS[x]}"
                )
                submit_reg = st.form_submit_button("Send Verification Code ➔", use_container_width=True)

            if submit_reg:
                if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                    st.warning("Please fill out all fields.")
                else:
                    success, msg = register_initial_employee(reg_name, reg_email, reg_pass, sticker=reg_sticker)
                    if success:
                        st.session_state.pending_otp_email = reg_email.lower().strip()
                        st.session_state.register_mode = False
                        st.rerun()
                    else:
                        st.error(msg)

            if st.button("Back to Profiles", use_container_width=True):
                st.session_state.register_mode = False
                st.rerun()

    st.stop()

# ===========================================================================
# 9. OPTIMIZED FAST TEXT EXTRACTION & OCR (150 DPI)
# ===========================================================================
def extract_text_from_image(file_bytes: bytes) -> str:
    import pytesseract
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert("L")
        return pytesseract.image_to_string(img)
    except Exception as e:
        st.error(f"⚠️ Image OCR failed: {e}")
        return ""

def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    import pytesseract
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if len(page_text.strip()) > 40:
                text_parts.append(f"\n--- [PAGE {idx}] ---\n" + page_text)
            else:
                try:
                    pil_img = page.to_image(resolution=150).original.convert("L")
                    t1 = pytesseract.image_to_string(pil_img)
                    if t1.strip():
                        text_parts.append(f"\n--- [PAGE {idx} (OCR)] ---\n" + t1)
                except Exception:
                    pass
    return "\n\n".join(text_parts)

def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx
    document = docx.Document(io.BytesIO(file_bytes))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text.strip())
    return "\n".join(parts)

def extract_resume_text(uploaded_file):
    name = uploaded_file.name.lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    try:
        file_bytes = uploaded_file.read()
        if ext == "pdf":
            return extract_text_from_pdf(file_bytes)
        elif ext == "docx":
            return extract_text_from_docx(file_bytes)
        elif ext in ["png", "jpg", "jpeg"]:
            return extract_text_from_image(file_bytes)
    except Exception as exc:
        st.error(f"⚠ Could not read {uploaded_file.name}: {exc}")
    return None

# ===========================================================================
# 10. GROQ AI: SAFE EXTRACTION & EVALUATION
# ===========================================================================
def build_multi_candidate_extraction_prompt(resume_text: str) -> str:
    return f"""You are an expert HR Data Extraction Specialist for Attock Refinery Limited (ARL).
Analyze the following document text carefully.

CRITICAL RULES:
1. FATHER IS NOT A CANDIDATE: Extract father names solely into "father_name".
2. FULL NAMES ONLY: Capture the complete applicant name.
3. NO DUPLICATE CLONES: Do not split single resumes.

Return ONLY a strictly valid JSON object:
{{
  "candidates": [
    {{
      "name": "Complete Candidate Name",
      "father_name": "Father Name or Not Provided",
      "education": "Degree Title",
      "cgpa": "CGPA or Not Provided",
      "passing_year": "Passing Year or Not Provided",
      "university_name": "Institute / Board or Not Provided",
      "dob": "Date of Birth or Not Provided",
      "email": "Email Address or Not Provided",
      "phone": "Phone Number or Not Provided",
      "experience_years": "Experience (e.g. Fresh, 2 Years)",
      "latest_experience": "Latest job role or Not Provided",
      "reference": "Reference or Not Provided",
      "skills": "Key technical skills"
    }}
  ]
}}

DOCUMENT TEXT:
{resume_text[:28000]}
"""

def extract_candidates_for_repo(client, resume_text: str, file_name: str):
    try:
        prompt = build_multi_candidate_extraction_prompt(resume_text)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=0.1,
        )
        raw_content = response.choices[0].message.content.strip()
        parsed = json.loads(raw_content)
        
        candidates_list = parsed.get("candidates", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
        if not candidates_list and isinstance(parsed, dict) and "name" in parsed:
            candidates_list = [parsed]

        final_candidates = []
        for cand in candidates_list:
            final_candidates.append({
                "file_name": file_name,
                "name": cand.get("name", "Unknown").strip(),
                "father_name": cand.get("father_name", "Not Provided").strip(),
                "education": cand.get("education", "Not Provided").strip(),
                "cgpa": cand.get("cgpa", "Not Provided").strip(),
                "passing_year": cand.get("passing_year", "Not Provided").strip(),
                "university_name": cand.get("university_name", "Not Provided").strip(),
                "dob": cand.get("dob", "Not Provided").strip(),
                "email": cand.get("email", "Not Provided").strip(),
                "phone": cand.get("phone", "Not Provided").strip(),
                "experience_years": str(cand.get("experience_years", "0")).strip(),
                "latest_experience": cand.get("latest_experience", "Not Provided").strip(),
                "reference": cand.get("reference", "Not Provided").strip(),
                "skills": cand.get("skills", "Not Provided").strip()
            })
        return final_candidates
    except Exception as exc:
        st.error(f"⚠️ Extraction failed for **{file_name}**: {exc}")
        return []

def evaluate_candidate_against_jd(client, candidate_row, jd_text: str):
    try:
        summary = f"Name: {candidate_row['Name']}, Education: {candidate_row['Qualification']}, Institute: {candidate_row['Institute']}, Experience: {candidate_row['Experience']}, Latest Role: {candidate_row['Latest Experience']}"
        prompt = f"""You are an expert HR recruiter AI for Attock Refinery Limited (ARL). Evaluate the CANDIDATE against the JOB DESCRIPTION.
CANDIDATE: {summary}
JOB DESCRIPTION: {jd_text}

Return ONLY a valid JSON object:
{{
  "match_score": A number between 0 and 100,
  "is_relevant": true or false,
  "missing_skills": ["Missing skill 1", "Missing skill 2"]
}}
"""
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        result = json.loads(response.choices[0].message.content.strip())
        return float(result.get("match_score", 0)), bool(result.get("is_relevant", True)), result.get("missing_skills", [])
    except Exception:
        return 0.0, True, []

def generate_ai_interview_questions(client, skills_text: str, job_title: str) -> str:
    try:
        prompt = f"Generate 5 targeted technical and behavioral interview questions for an applicant applying for '{job_title}' with skills: '{skills_text}' at Attock Refinery. Return markdown formatted list."
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate interview questions: {e}"

# ===========================================================================
# 11. PORTAL APPLICATION INTERFACE (TABS 1-4)
# ===========================================================================
df_all = load_database()
total_repo_db = len(df_all)
latest_candidate = df_all.iloc[-1]["Name"] if not df_all.empty else "None"

col_n1, col_n2 = st.columns([7.8, 2.2], vertical_alignment="center")
with col_n1:
    st.markdown(f"""
        <div class="top-navbar">
            <div>
                <h2 style="margin: 0; font-size: 1.35rem; color: #FFFFFF;">Arl TalentMatch: <span style="color: #4ADE80;">Corporate Recruitment Suite</span></h2>
                <p style="margin: 4px 0 0 0; font-size: 0.75rem; color: #86EFAC;">Logged In: <b>{st.session_state.get('hr_name', 'Recruiter')}</b> ({st.session_state.get('hr_email', '')}) &bull; Role: <b>{st.session_state.get('hr_role', 'Recruiter')}</b></p>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_n2:
    if st.button("🚪 Lock Session", use_container_width=True, key="lock_portal_btn_active"):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.hr_email = ""
        st.session_state.hr_role = "Recruiter"
        st.session_state.manage_profiles_mode = False
        st.session_state.screening_results = []
        st.rerun()

st.markdown(f"""
    <div class="corp-hero">
        <div class="corp-badge">
            <span>🟢 ATS Master Session</span> &bull; <span>Total Talent Pool: {total_repo_db} Candidates</span>
        </div>
        <h1>Attock Refinery Executive Suite</h1>
        <p>Active User: <b>{st.session_state.get('hr_name')}</b> | Latest Candidate Ingested: <b>{latest_candidate}</b></p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Talent Repository (Upload)", "🎯 2. JD Screening & Matching", "🗄️ 3. Live Database & Screening Grids", "🛡️ 4. Admin Controls"])

# ----------------- TAB 1: TALENT REPOSITORY INGESTION -----------------
with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Ingest & Parse Candidate Resumes</h4>', unsafe_allow_html=True)
    st.caption("Upload PDF/DOCX/image resumes. Multi-candidate documents are parsed into independent records.")
    
    uploaded_repo_files = st.file_uploader("Upload resumes", type=ACCEPTED_TYPES, accept_multiple_files=True, label_visibility="collapsed")
    g_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    
    if st.button("⚡ Extract & Append to Supabase Master Database", type="primary", use_container_width=True, disabled=not (uploaded_repo_files and g_key)):
        client = Groq(api_key=g_key)
        extracted_batch = []
        progress = st.progress(0.0, text="Extracting profiles...")
        
        for i, file in enumerate(uploaded_repo_files):
            progress.progress((i + 1) / (len(uploaded_repo_files) + 1), text=f"Processing {file.name}...")
            text = extract_resume_text(file)
            if text:
                candidates_in_file = extract_candidates_for_repo(client, text, file.name)
                for cand in candidates_in_file:
                    extracted_batch.append(cand)
                    
        progress.empty()
        if extracted_batch:
            ins, skp = save_candidates_to_repository(extracted_batch)
            st.success(f"Extracted **{ins} new candidate(s)**! (Skipped {skp} duplicate profiles)")
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    df_repo = load_database()
    if not df_repo.empty:
        st.markdown('<div class="corp-card"><h4>📋 Current Master Talent Repository</h4>', unsafe_allow_html=True)
        st.download_button(
            "📊 Download Talent Repository (.xlsx)",
            data=generate_repository_excel(df_repo),
            file_name="ARL_Master_Talent_Repository.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_repo_tab1"
        )
        st.markdown("---")
        for idx, row in df_repo.iterrows():
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            with c1: st.write(f"👤 **{row['Name']}**")
            with c2: st.write(f"✉️ `{row['Email']}`")
            with c3: st.write(f"🎓 {row['Qualification']}")
            with c4:
                if st.button("🗑️ Delete", key=f"del_repo_entry_{idx}", use_container_width=True):
                    delete_single_candidate_from_db(row['Email'] if row['Email'] not in ["Not Provided", ""] else row['Name'])
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 2: JD SCREENING & SMART MATCHING -----------------
with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening & AI Matcher</h4>', unsafe_allow_html=True)
    
    arl_catalog = load_arl_job_catalog()
    dept_options = list(arl_catalog.keys())
    
    col_dept, col_job = st.columns(2)
    with col_dept: chosen_dept = st.selectbox("Select Department", dept_options, index=0)
    available_jobs = arl_catalog.get(chosen_dept, [])
    with col_job: chosen_job_item = st.selectbox(f"Select Job Designation", available_jobs + ["✍️ Custom Title..."], index=0)
        
    jd_title_input = st.text_input("Enter Job Designation", placeholder="e.g. Chemical Process Engineer") if chosen_job_item == "✍️ Custom Title..." else chosen_job_item
    jd_desc_text = st.text_area("Job Requirements", height=120, placeholder="Paste job qualifications and requirements...")
    screening_threshold = st.slider("Highlight Score Threshold (%)", 0, 100, 50, 5)
    
    df_pool = load_database()
    g_key_active = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    
    if st.button("⚡ Run AI Screening Against Talent Pool", type="primary", use_container_width=True, disabled=not (jd_desc_text.strip() and jd_title_input.strip() and not df_pool.empty and g_key_active)):
        client = Groq(api_key=g_key_active)
        screened_results = []
        progress = st.progress(0.0, text="Evaluating profiles against Job Description...")
        
        for idx, row in df_pool.iterrows():
            progress.progress((idx + 1) / (len(df_pool) + 1), text=f"Screening {row['Name']}...")
            score, is_relevant, missing = evaluate_candidate_against_jd(client, row, jd_desc_text)
            if is_relevant:
                screened_results.append({
                    "job_title": jd_title_input, "name": row["Name"], "father_name": row["Father Name"],
                    "education": row["Qualification"], "cgpa": row["CGPA"], "passing_year": row["Passing Year"],
                    "university_name": row["Institute"], "dob": row["DOB"], "email": row["Email"],
                    "phone": row["Phone Number"], "experience_years": row["Experience"],
                    "latest_experience": row["Latest Experience"], "reference": row["Reference"],
                    "match_score": score, "missing_skills": missing,
                    "pipeline_status": "Shortlisted" if score >= screening_threshold else "Talent Pool"
                })
        progress.empty()
        screened_results.sort(key=lambda x: x["match_score"], reverse=True)
        st.session_state.screening_results = screened_results
        save_screened_to_supabase(screened_results)
        st.success(f"Screening complete! {len(screened_results)} candidate(s) evaluated and recorded.")
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.get('screening_results'):
        st.markdown('<div class="corp-card"><h4>📊 Evaluated Candidates Pipeline</h4>', unsafe_allow_html=True)
        results = st.session_state.screening_results
        st.download_button("📊 Export Screened Report (.xlsx)", data=generate_screening_excel(results), file_name="ARL_Screened_Results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        st.markdown("---")

        client = Groq(api_key=g_key_active) if g_key_active else None
        for rank, cand in enumerate(results, start=1):
            score_cls = "score-high" if cand["match_score"] >= 75 else ("score-mid" if cand["match_score"] >= 40 else "score-low")
            with st.expander(f"#{rank} — {cand['name']} | Match Score: {cand['match_score']}% | Stage: {cand['pipeline_status']}"):
                c1, c2 = st.columns([1.3, 1])
                with c1:
                    st.write(f"**Target Role:** `{cand.get('job_title')}` | **Email:** `{cand['email']}`")
                    st.write(f"**Education:** {cand['education']} ({cand['university_name']})")
                    st.write(f"**Experience:** {cand['experience_years']} | Latest: {cand['latest_experience']}")
                    st.markdown(f'<div class="metric-box"><div class="val {score_cls}">{cand["match_score"]}%</div><div class="lbl">Match Score</div></div>', unsafe_allow_html=True)
                with c2:
                    st.write("**Identified Skill Gaps:**")
                    if cand["missing_skills"]:
                        for s in cand["missing_skills"]: st.write(f"- {s}")
                    else: st.caption("No notable gaps identified.")
                
                new_st = st.selectbox("Stage", ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"], index=["Shortlisted", "Interview Scheduled", "Hired", "Rejected"].index(cand["pipeline_status"]) if cand["pipeline_status"] in ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"] else 0, key=f"sel_stg_{rank}")
                if new_st != cand["pipeline_status"]:
                    cand["pipeline_status"] = new_st
                    update_candidate_pipeline_status(cand["email"], new_st)
                    update_screened_candidate_status(cand["email"], cand["job_title"], new_st)
                    st.rerun()

                if st.button(f"💡 Generate Interview Q&A for {cand['name']}", key=f"q_btn_{rank}") and client:
                    st.markdown(generate_ai_interview_questions(client, ", ".join(cand["missing_skills"]), cand["job_title"]))
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 3: DUAL LIVE SYNCHRONIZED GRIDS -----------------
with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Real-Time Database Tables</h4>', unsafe_allow_html=True)
    g1, g2 = st.tabs(["🎯 Screened Candidates", "📥 Master Talent Repository"])
    
    with g1:
        df_screened = load_screened_database()
        if not df_screened.empty:
            st.dataframe(df_screened, use_container_width=True, height=380)
            if st.button("🗑️ Clear Screened Records", key="clr_scrn_grid"):
                clear_screened_database()
                st.rerun()
        else:
            st.info("No candidates screened yet.")
            
    with g2:
        df_repo_all = load_database()
        if not df_repo_all.empty:
            st.dataframe(df_repo_all, use_container_width=True, height=380)
            if st.button("🗑️ Clear Master Talent Pool", key="clr_repo_grid"):
                clear_candidate_database()
                st.rerun()
        else:
            st.info("Talent pool is empty.")
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 4: ADMIN CONTROLS -----------------
with tab4:
    st.markdown('<div class="corp-card"><h4>🛡 Admin Management Console</h4></div>', unsafe_allow_html=True)
    if st.session_state.get('hr_role') != "Admin":
        st.error("⛔ Access restricted to Administrators.")
    else:
        st.write(f"**Active User Profiles ({len(get_all_verified_profiles_admin())}):**")
        for emp_email, emp_name, emp_pin, emp_role, emp_sticker in get_all_verified_profiles_admin():
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: st.write(f"{emp_sticker} **{emp_name}** ({emp_email}) — *{emp_role}*")
            with c2: st.write(f"PIN: `{emp_pin}`")
            with c3:
                if emp_email.lower() != st.session_state.get('hr_email', '').lower():
                    if st.button("Revoke", key=f"rev_{emp_email}"):
                        delete_employee_profile(emp_email)
                        st.rerun()
                else:
                    st.caption("Active Session")
    st.markdown('</div>', unsafe_allow_html=True)
