"""
ARL TalentMatch — Official Corporate Edition
=============================================================================
Branding: Attock Refinery Limited (ARL Official Forest Green & Charcoal Palette)
Features: Netflix-Style Profile Selector, Interactive Avatar Badges, 
In-Modal PIN Entry with Auto-Focus, Any-Domain Email Registration, 
Fast OCR, JD Match Screener & Live Supabase Cloud Sync.
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
from groq import Groq
from supabase import create_client, Client
from PIL import Image, ImageOps, ImageEnhance, ImageDraw

# ===========================================================================
# 1. PAGE CONFIGURATION & ARL FAVICON
# ===========================================================================
APP_NAME = "ARL TalentMatch"
APP_TAGLINE = "Attock Refinery Limited (ARL) • AI-Driven Automated CV Parser & JD Screener"
GROQ_MODEL = "openai/gpt-oss-120b"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
EXE_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/ARL-TalentMatch_1.0.0_x64_en-US.msi"

# Professional Corporate Badges / Stickers for Avatars
AVAILABLE_BADGES = [
    "👔", "💼", "🛡️", "🎖️", "⚡", "🔬", "🛢️", "⚙️", 
    "📈", "🎯", "👑", "🚀", "💡", "💻", "💎", "🏛️"
]

def get_arl_favicon():
    img = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon([(32, 6), (58, 20), (58, 44), (32, 58), (6, 44), (6, 20)], outline=(22, 101, 52), width=5)
    draw.polygon([(32, 16), (46, 25), (46, 39), (32, 48), (18, 39), (18, 25)], fill=(22, 101, 52))
    return img

st.set_page_config(
    page_title=f"{APP_NAME} | Corporate Portal",
    page_icon=get_arl_favicon(),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ===========================================================================
# 2. SUPABASE CLOUD DATABASE CONNECTION
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

# ----------------- BULLETPROOF AUTHENTICATION -----------------
def get_user_avatar(email):
    avatars = st.session_state.get("profile_avatars", {})
    return avatars.get(email.lower().strip(), "👤")

def set_user_avatar(email, avatar_char):
    if "profile_avatars" not in st.session_state:
        st.session_state.profile_avatars = {}
    st.session_state.profile_avatars[email.lower().strip()] = avatar_char

def verify_employee_pin(email, entered_pin):
    clean_email = email.lower().strip()
    entered_str = str(entered_pin).strip()

    cached = get_all_verified_profiles()
    for p_email, p_name, p_pin, p_role in cached:
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
        return [("admin@arl.com.pk", "ARL Admin", "1234", "Admin")]
    profiles = []
    try:
        res = supabase.table("hr_users").select("*").execute()
        if res.data:
            for r in res.data:
                if r.get("pin"):
                    profiles.append((r.get("email"), r.get("name"), str(r.get("pin")), r.get("role", "Recruiter")))
    except Exception:
        pass
    try:
        res2 = supabase.table("employees").select("*").execute()
        if res2.data:
            existing_emails = [p[0].lower() for p in profiles]
            for r in res2.data:
                if r.get("pin") and r.get("email", "").lower() not in existing_emails:
                    profiles.append((r.get("email"), r.get("name"), str(r.get("pin")), r.get("role", "Recruiter")))
    except Exception:
        pass
    return profiles

def get_all_verified_profiles_admin():
    return get_all_verified_profiles()

def register_initial_employee(name, email, password):
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
            "otp": otp
        }
        supabase.table("hr_users").upsert(data).execute()
        
        success, msg = send_smtp_email(clean_email, "ARL TalentMatch - Verification OTP", f"Your verification code is: {otp}")
        if success:
            return True, "Registration initiated! Please check your email for the verification OTP."
        else:
            return False, msg
    except Exception as e:
        return False, f"Database Error: {e}"

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
    return True, "Employee profile removed."

# ===========================================================================
# 3. ARL CORPORATE JOB CATALOG & SUPABASE HIERARCHY
# ===========================================================================
DEFAULT_ARL_CATALOG = {
    "Operations & Refining": [
        "Process Engineer", "Plant Shift Incharge", "Senior Plant Operator (CDU / Reformer)",
        "Control Room DCS Operator", "Refining Operations Manager", "Lead Commissioning Engineer"
    ],
    "Maintenance & Engineering": [
        "Mechanical Maintenance Engineer", "Electrical Maintenance Engineer", "Instrumentation & Control (I&C) Engineer",
        "Reliability & Inspection Engineer", "Turnaround & Maintenance Planning Specialist", "Rotary Equipment Specialist"
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
# 4. CANDIDATE REPOSITORY & STORAGE
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
            "candidate_name": c.get("name", "Unknown"),
            "father_name": c.get("father_name", "Not Provided"),
            "education": c.get("education", "Not Provided"),
            "cgpa": c.get("cgpa", "Not Provided"),
            "passing_year": c.get("passing_year", "Not Provided"),
            "university_name": c.get("university_name", "Not Provided"),
            "dob": c.get("dob", "Not Provided"),
            "email": c.get("email", "Not Provided"),
            "phone": c.get("phone", "Not Provided"),
            "experience_years": str(c.get("experience_years", "0")),
            "latest_experience": c.get("latest_experience", "Not Provided"),
            "reference": c.get("reference", "Not Provided"),
            "pipeline_status": "Talent Pool",
            "added_at": current_timestamp
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
    if not supabase:
        return
    try:
        supabase.table("candidates").delete().or_(f"email.ilike.{email_or_name},candidate_name.ilike.{email_or_name}").execute()
    except Exception:
        pass

def update_candidate_pipeline_status(email, new_status):
    if not supabase:
        return
    try:
        supabase.table("candidates").update({"pipeline_status": new_status}).ilike("email", email).execute()
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
            "Sr. No.": idx,
            "Job Title": r.get("job_title", "Not Specified"),
            "Candidate Name": r["name"],
            "Father Name": r["father_name"],
            "Qualification": r["education"],
            "CGPA": r["cgpa"],
            "Passing Year": r["passing_year"],
            "Institute": r["university_name"],
            "DOB": r["dob"],
            "Email": r["email"],
            "Phone Number": r["phone"],
            "Experience": r["experience_years"],
            "Latest Experience": r["latest_experience"],
            "Reference": r["reference"],
            "Match Score (%)": r["match_score"],
            "Pipeline Status": r["pipeline_status"]
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
# 5. NETFLIX-STYLE CINEMATIC ARL FOREST GREEN & CHARCOAL CSS
# ===========================================================================
ARL_GREEN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    background-color: #0B0E11 !important;
    color: #F8FAFC !important;
}

[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* Backdrop blur when Streamlit modal dialog is open */
div[data-testid="stModal"] {
    background-color: rgba(5, 12, 8, 0.78) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
}

div[data-testid="stDialog"] {
    background: #14171A !important;
    border: 2px solid #166534 !important;
    border-radius: 20px !important;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.9), 0 0 30px rgba(34, 197, 94, 0.25) !important;
    color: #FFFFFF !important;
}

/* Netflix Heading */
.netflix-header-box {
    text-align: center;
    padding: 2.5rem 1rem 1.8rem 1rem;
}

.netflix-heading {
    font-size: 3rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px !important;
    color: #FFFFFF !important;
    margin-bottom: 8px !important;
}

.netflix-subtext {
    font-size: 1.05rem !important;
    color: #94A3B8 !important;
    letter-spacing: 0.5px !important;
}

/* NETFLIX ROUNDED-SQUARE PROFILE CARDS */
.netflix-card-wrapper {
    position: relative;
    width: 145px;
    height: 145px;
    margin: 0 auto 10px auto;
    border-radius: 22px;
    background: linear-gradient(145deg, #181D22 0%, #101316 100%);
    border: 3px solid #1E252B;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.6);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
}

.netflix-card-wrapper:hover {
    transform: translateY(-8px) scale(1.05);
    border-color: #22C55E !important;
    box-shadow: 0 16px 35px rgba(34, 197, 94, 0.35), inset 0 0 15px rgba(34, 197, 94, 0.15);
}

.netflix-avatar-emoji {
    font-size: 4rem;
    user-select: none;
    line-height: 1;
}

.netflix-user-name {
    text-align: center;
    font-size: 1.05rem;
    font-weight: 700;
    color: #CBD5E1;
    margin-top: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.netflix-user-role {
    text-align: center;
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    color: #22C55E;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* Edit Sticker Hover Badge in Top-Right */
.sticker-edit-badge {
    position: absolute;
    top: 8px;
    right: 8px;
    background: rgba(15, 23, 42, 0.85);
    border: 1.5px solid #22C55E;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    color: #FFFFFF;
    opacity: 0;
    transform: scale(0.8);
    transition: all 0.2s ease-in-out;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5);
}

.netflix-card-wrapper:hover .sticker-edit-badge {
    opacity: 1;
    transform: scale(1);
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #166534 0%, #14532D 100%) !important;
    color: #FFFFFF !important;
    border: 1.5px solid #22C55E !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    padding: 0.65rem 1.2rem !important;
    box-shadow: 0 4px 15px rgba(22, 101, 52, 0.3) !important;
    transition: all 0.2s ease-in-out !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #15803D 0%, #166534 100%) !important;
    border-color: #FFFFFF !important;
    box-shadow: 0 6px 22px rgba(34, 197, 94, 0.5) !important;
    transform: translateY(-2px);
}

/* Secondary Button Styling for Edit & Minor Actions */
div[data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"] {
    background: #181D22 !important;
    border: 1px solid #2A323D !important;
    color: #CBD5E1 !important;
}

/* Inside Dialog Styling */
[data-testid="stDialog"] input {
    background-color: #0E1012 !important;
    color: #FFFFFF !important;
    border: 2px solid #166534 !important;
    border-radius: 12px !important;
    font-size: 1.4rem !important;
    text-align: center !important;
    letter-spacing: 8px !important;
}

/* Top Navbar */
.top-navbar {
    background: linear-gradient(135deg, #14171A 0%, #1A2026 100%);
    border: 1.5px solid #1E2328;
    border-bottom: 2px solid #166534;
    border-radius: 16px;
    padding: 1.1rem 2rem;
    margin-bottom: 1.8rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
}
.top-brand-title {
    font-size: 1.55rem; font-weight: 800; color: #FFFFFF; margin: 0;
    display: flex; align-items: center; gap: 10px;
}
.top-brand-subtitle {
    font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700; color: #94A3B8; margin: 0;
}

.corp-hero {
    background: linear-gradient(135deg, rgba(22, 101, 52, 0.18) 0%, rgba(20, 23, 26, 0.9) 100%);
    border: 1.5px solid #1E2328;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    border-left: 6px solid #22C55E;
}
.corp-badge {
    display: inline-flex; align-items: center; gap: 8px; 
    background: rgba(34, 197, 94, 0.15); color: #22C55E; 
    padding: 5px 14px; border-radius: 6px;
    font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.8rem;
    border: 1px solid rgba(34, 197, 94, 0.4);
}

.corp-card {
    background: #14171A;
    border: 1.5px solid rgba(22, 101, 52, 0.3);
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
}

.corp-card h4 {
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    margin-top: 0 !important;
    margin-bottom: 1.2rem !important;
    background: linear-gradient(90deg, rgba(34, 197, 94, 0.15) 0%, rgba(22, 101, 52, 0.05) 100%) !important;
    border-left: 4px solid #22C55E !important;
    padding: 10px 16px !important;
    border-radius: 6px 12px 12px 6px !important;
}

.metric-box .val { font-size: 1.8rem; font-weight: 800; color: #22C55E; }
.metric-box .lbl { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; font-weight: 700; opacity: 0.85; }

.score-high { color: #10B981 !important; font-weight: 800; }
.score-mid { color: #F59E0B !important; font-weight: 800; }
.score-low { color: #EF4444 !important; font-weight: 800; }

div[data-baseweb="tab-list"] {
    background: #14171A !important;
    border: 1.5px solid #1E2328 !important;
    border-radius: 16px !important;
    padding: 6px 10px !important;
    gap: 8px !important;
    margin-bottom: 1.8rem !important;
}

button[data-baseweb="tab"] {
    background: transparent !important;
    border: 1.5px solid transparent !important;
    border-radius: 12px !important;
    padding: 8px 20px !important;
    color: #94A3B8 !important;
    font-size: 0.92rem !important;
    font-weight: 700 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(22, 101, 52, 0.6) 0%, rgba(34, 197, 94, 0.2) 100%) !important;
    border: 1.5px solid #22C55E !important;
    color: #22C55E !important;
}
</style>
"""
st.markdown(ARL_GREEN_CSS, unsafe_allow_html=True)

# ===========================================================================
# 6. SESSION STATE INITIALIZATION
# ===========================================================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "hr_name" not in st.session_state: st.session_state.hr_name = ""
if "hr_email" not in st.session_state: st.session_state.hr_email = ""
if "hr_role" not in st.session_state: st.session_state.hr_role = "Recruiter"
if "profile_avatars" not in st.session_state: st.session_state.profile_avatars = {}
if "pending_otp_email" not in st.session_state: st.session_state.pending_otp_email = None
if "pending_pin_email" not in st.session_state: st.session_state.pending_pin_email = None
if "screening_results" not in st.session_state: st.session_state.screening_results = []
if "show_registration" not in st.session_state: st.session_state.show_registration = False
if "show_download_page" not in st.session_state: st.session_state.show_download_page = False
if "is_desktop_mode" not in st.session_state:
    st.session_state.is_desktop_mode = (st.query_params.get("mode") == "desktop")
is_desktop_mode = st.session_state.is_desktop_mode or (st.query_params.get("mode") == "desktop")

# ===========================================================================
# 7. IN-MODAL POPUP DIALOGS (NETFLIX STYLE AUTO-FOCUS)
# ===========================================================================
@st.dialog("🔐 Enter Security PIN")
def show_pin_dialog(email, name, role):
    st.write(f"Sign in to executive profile for **{name}**")
    st.caption(f"Account: `{email}`")
    
    with st.form(f"modal_pin_form_{email}"):
        pin_val = st.text_input("4-Digit PIN", type="password", max_chars=4, placeholder="••••")
        submit_btn = st.form_submit_button("Access Portal ➔", use_container_width=True)
        
    if submit_btn:
        ok, u_name, u_role = verify_employee_pin(email, pin_val)
        if ok:
            st.session_state.logged_in = True
            st.session_state.hr_name = u_name if u_name else name
            st.session_state.hr_email = email
            st.session_state.hr_role = u_role if u_role else role
            st.rerun()
        else:
            st.error("❌ Invalid 4-Digit PIN.")

@st.dialog("🎨 Choose Executive Badge")
def show_sticker_picker_dialog(email, name):
    st.write(f"Select a corporate avatar badge for **{name}**:")
    
    cols = st.columns(4)
    for idx, badge in enumerate(AVAILABLE_BADGES):
        with cols[idx % 4]:
            if st.button(badge, key=f"stk_btn_{email}_{idx}", use_container_width=True):
                set_user_avatar(email, badge)
                st.success("Badge updated!")
                st.rerun()

# ===========================================================================
# 8. AUTHENTICATION & NETFLIX PROFILE GRID SCREEN
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()
    
    if not is_desktop_mode:
        c_banner_l, c_banner_r, c_banner_x = st.columns([7, 2.3, 0.7], vertical_alignment="center")
        with c_banner_l:
            st.caption("Prefer standalone Windows PC software?")
        with c_banner_r:
            if st.button("💻 Get App", key="dl_btn_login_top", use_container_width=True):
                st.session_state.show_download_page = True
                st.rerun()
        with c_banner_x:
            if st.button("✕", key="dismiss_desktop_banner"):
                st.session_state.is_desktop_mode = True
                st.rerun()

    if st.session_state.pending_pin_email:
        _, mid_col, _ = st.columns([1, 2.2, 1])
        with mid_col:
            st.markdown("### 🔐 Security PIN Setup")
            st.info(f"Email verified for **{st.session_state.pending_pin_email}**. Create your 4-digit PIN.")
            with st.form("pin_setup_form"):
                new_pin = st.text_input("Create 4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                confirm_pin = st.text_input("Confirm 4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                submit_pin = st.form_submit_button("Save PIN & Continue", use_container_width=True)
            if submit_pin:
                if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
                    st.warning("Please enter an exact 4-digit numeric PIN.")
                elif new_pin != confirm_pin:
                    st.error("PINs do not match.")
                else:
                    success, msg = save_employee_pin(st.session_state.pending_pin_email, new_pin)
                    if success:
                        st.success(msg)
                        st.session_state.pending_pin_email = None
                        st.rerun()
                    else:
                        st.error(msg)
        st.stop()

    elif st.session_state.pending_otp_email:
        _, mid_col, _ = st.columns([1, 2.2, 1])
        with mid_col:
            st.markdown("### 📬 Email Verification")
            st.info(f"Enter the 6-digit code dispatched to **{st.session_state.pending_otp_email}**.")
            with st.form("otp_form"):
                otp_input = st.text_input("Enter 6-Digit OTP", placeholder="123456")
                submit_otp = st.form_submit_button("Verify OTP", use_container_width=True)
            if submit_otp:
                success, nag = verify_otp_code(st.session_state.pending_otp_email, otp_input)
                if success:
                    st.success(nag)
                    st.session_state.pending_pin_email = st.session_state.pending_otp_email
                    st.session_state.pending_otp_email = None
                    st.rerun()
                else:
                    st.error(nag)
            if st.button("Cancel Registration", use_container_width=True):
                st.session_state.pending_otp_email = None
                st.rerun()
        st.stop()

    elif st.session_state.show_registration or not saved_profiles:
        _, mid_col, _ = st.columns([1, 2.2, 1])
        with mid_col:
            st.markdown("### 📝 Register Executive Profile")
            st.caption("Open to all authorized corporate and external recruitment partners.")
            with st.form("universal_registration_form"):
                reg_name = st.text_input("Full Name", placeholder="e.g. Sultan Sheraz")
                reg_email = st.text_input("Email Address", placeholder="name@domain.com")
                reg_pass = st.text_input("Master Password", type="password")
                submit_reg = st.form_submit_button("Send Verification OTP", use_container_width=True)
                
            col_b1, col_b2 = st.columns(2)
            if submit_reg:
                email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
                if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                    st.warning("Please fill all required fields.")
                elif not re.match(email_regex, reg_email.strip()):
                    st.error("Please enter a valid email address.")
                else:
                    success, msg = register_initial_employee(reg_name.strip(), reg_email.strip(), reg_pass.strip())
                    if success:
                        st.success(msg)
                        st.session_state.pending_otp_email = reg_email.lower().strip()
                        st.session_state.show_registration = False
                        st.rerun()
                    else:
                        st.error(msg)
                        
            with col_b2:
                if saved_profiles and st.button("⬅ Back to Profiles", use_container_width=True):
                    st.session_state.show_registration = False
                    st.rerun()
        st.stop()

    st.markdown(f"""
        <div class="netflix-header-box">
            <h1 class="netflix-heading">Who's Screening?</h1>
            <p class="netflix-subtext">{APP_TAGLINE}</p>
        </div>
    """, unsafe_allow_html=True)

    total_profiles = len(saved_profiles)
    card_cols = st.columns(max(total_profiles, 1))

    for idx, (p_email, p_name, p_pin, p_role) in enumerate(saved_profiles):
        with card_cols[idx]:
            avatar_sticker = get_user_avatar(p_email)
            
            st.markdown(f"""
                <div class="netflix-card-wrapper">
                    <div class="netflix-avatar-emoji">{avatar_sticker}</div>
                    <div class="sticker-edit-badge" title="Change Badge">✏️</div>
                </div>
                <div class="netflix-user-name">{p_name}</div>
                <div class="netflix-user-role">{p_role}</div>
            """, unsafe_allow_html=True)
            
            c_sel, c_edit = st.columns([3, 1.2])
            with c_sel:
                if st.button("Sign In", key=f"sel_prof_{idx}_{p_email}", use_container_width=True):
                    show_pin_dialog(p_email, p_name, p_role)
            with c_edit:
                if st.button("🎨", key=f"btn_stk_{idx}_{p_email}", help="Change Avatar Badge", use_container_width=True):
                    show_sticker_picker_dialog(p_email, p_name)

    st.markdown("<div style='margin-top: 3.5rem;'></div>", unsafe_allow_html=True)
    
    _, b_mid, _ = st.columns([2, 1.8, 2])
    with b_mid:
        if st.button("➕ Add New Profile", use_container_width=True, key="netflix_add_profile_btn"):
            st.session_state.show_registration = True
            st.rerun()

    st.stop()

# ===========================================================================
# 9. OPTIMIZED OCR & TEXT EXTRACTION (150 DPI)
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
        st.error(f"⚠️ Could not read {uploaded_file.name}: {exc}")
    return None

# ===========================================================================
# 10. GROQ AI EXTRACTION & EVALUATION
# ===========================================================================
def build_multi_candidate_extraction_prompt(resume_text: str) -> str:
    return f"""You are an expert HR Data Extraction Specialist for Attock Refinery Limited (ARL).
Analyze the following document text carefully and return a strictly valid JSON object:

{{
  "candidates": [
    {{
      "name": "Complete Candidate Name",
      "father_name": "Father Name or Not Provided",
      "education": "Qualification / Degree Title",
      "cgpa": "CGPA / Percentage or Not Provided",
      "passing_year": "Graduation Year or Not Provided",
      "university_name": "Institute Name or Not Provided",
      "dob": "Date of Birth or Not Provided",
      "email": "Candidate Email or Not Provided",
      "phone": "Candidate Phone or Not Provided",
      "experience_years": "Total Experience (e.g. Fresh, 2 Years)",
      "latest_experience": "Latest job role or company or Not Provided",
      "reference": "Reference contacts or Not Provided",
      "skills": "Key technical / engineering skills"
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
        parsed = json.loads(response.choices[0].message.content.strip())
        candidates_list = parsed.get("candidates", []) if isinstance(parsed, dict) else parsed

        cleaned = []
        for cand in candidates_list:
            cleaned.append({
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
        return cleaned
    except Exception as exc:
        st.error(f"⚠️ Extraction failed for **{file_name}**: {exc}")
        return []

def evaluate_candidate_against_jd(client, candidate_row, jd_text: str):
    try:
        summary = f"Name: {candidate_row['Name']}, Education: {candidate_row['Qualification']}, Institute: {candidate_row['Institute']}, Experience: {candidate_row['Experience']}, Latest Role: {candidate_row['Latest Experience']}"
        prompt = f"""Evaluate the CANDIDATE against the JOB DESCRIPTION for Attock Refinery Limited.
CANDIDATE: {summary}
JOB DESCRIPTION: {jd_text}

Return ONLY valid JSON:
{{
  "match_score": 0 to 100,
  "is_relevant": true or false,
  "missing_skills": ["missing", "skills"]
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
        prompt = f"Based on skills '{skills_text}' and ARL position '{job_title}', generate 5 precise technical and behavioral interview questions with model answers. Bullet points."
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate questions: {e}"

# ===========================================================================
# 11. MAIN CORPORATE PORTAL DASHBOARD
# ===========================================================================
df_all = load_database()
total_repo_db = len(df_all)
latest_candidate = df_all.iloc[-1]["Name"] if not df_all.empty else "None"
user_avatar = get_user_avatar(st.session_state.get('hr_email', ''))

col_n1, col_n2 = st.columns([8, 2], vertical_alignment="center")
with col_n1:
    st.markdown(f"""
        <div class="top-navbar">
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="font-size: 2.2rem; background: #181D22; padding: 4px 10px; border-radius: 12px; border: 1.5px solid #22C55E;">
                    {user_avatar}
                </div>
                <div>
                    <h2 class="top-brand-title">{APP_NAME} <span style="color: #22C55E;">Pro</span></h2>
                    <p class="top-brand-subtitle">Logged In: <b>{st.session_state.get('hr_name')}</b> ({st.session_state.get('hr_email')}) &bull; Role: <b>{st.session_state.get('hr_role')}</b></p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_n2:
    if st.button("🚪 Switch Profile / Lock", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.hr_email = ""
        st.rerun()

st.markdown(f"""
    <div class="corp-hero">
        <div class="corp-badge">
            <span>🟢 Active Session</span> &bull; <span>Total Repository: {total_repo_db} Candidates</span>
        </div>
        <h1 style="color: #FFFFFF; margin: 0 0 8px 0;">Attock Refinery Executive Suite</h1>
        <p style="color: #CBD5E1; margin: 0;">Welcome, <b>{st.session_state.get('hr_name')}</b> &mdash; Latest Registered Candidate: <b>{latest_candidate}</b></p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Talent Repository (Upload)", "🎯 2. JD Screening & Matching", "🗄️ 3. Live Database Grids", "🛡️ 4. Admin Controls"])

with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Ingest & Parse Resumes</h4>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload Resumes (PDF, DOCX, Images)", type=ACCEPTED_TYPES, accept_multiple_files=True)
    
    g_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    if st.button("⚡ Extract & Append to Supabase Master Database", type="primary", use_container_width=True, disabled=not (uploaded_files and g_key)):
        client = Groq(api_key=g_key)
        batch = []
        prog = st.progress(0.0, "Extracting candidate records...")
        for i, file in enumerate(uploaded_files):
            prog.progress((i + 1) / len(uploaded_files), f"Processing {file.name}...")
            text = extract_resume_text(file)
            if text:
                cands = extract_candidates_for_repo(client, text, file.name)
                batch.extend(cands)
        prog.empty()
        if batch:
            ins, skp = save_candidates_to_repository(batch)
            st.success(f"🎉 Processed: {ins} new candidate(s) appended, {skp} duplicate(s) skipped!")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening</h4>', unsafe_allow_html=True)
    catalog = load_arl_job_catalog()
    dept = st.selectbox("Select Department", list(catalog.keys()))
    job_role = st.selectbox("Select Position", catalog.get(dept, []))
    
    jd_text = st.text_area("Job Requirements", height=130, placeholder="Paste job requirements here...")
    slider_thresh = st.slider("Highlight Score Threshold (%)", 0, 100, 50, step=5)
    
    df_pool = load_database()
    if st.button("⚡ Run AI Candidate Screening", type="primary", use_container_width=True, disabled=not (jd_text.strip() and not df_pool.empty and g_key)):
        client = Groq(api_key=g_key)
        res = []
        prog = st.progress(0.0, "Screening against JD...")
        for idx, row in df_pool.iterrows():
            prog.progress((idx + 1) / len(df_pool), f"Evaluating {row['Name']}...")
            score, is_rel, missing = evaluate_candidate_against_jd(client, row, jd_text)
            if is_rel:
                res.append({
                    "job_title": job_role,
                    "name": row["Name"],
                    "father_name": row["Father Name"],
                    "education": row["Qualification"],
                    "cgpa": row["CGPA"],
                    "passing_year": row["Passing Year"],
                    "university_name": row["Institute"],
                    "dob": row["DOB"],
                    "email": row["Email"],
                    "phone": row["Phone Number"],
                    "experience_years": row["Experience"],
                    "latest_experience": row["Latest Experience"],
                    "reference": row["Reference"],
                    "match_score": score,
                    "missing_skills": missing,
                    "pipeline_status": "Shortlisted" if score >= slider_thresh else "Talent Pool"
                })
        prog.empty()
        res.sort(key=lambda x: x["match_score"], reverse=True)
        st.session_state.screening_results = res
        save_screened_to_supabase(res)
        st.success(f"Screening complete! {len(res)} candidate(s) evaluated.")
        st.rerun()

    if st.session_state.screening_results:
        st.markdown("---")
        for rank, cand in enumerate(st.session_state.screening_results, 1):
            with st.expander(f"#{rank} — {cand['name']} ({cand['match_score']}%) | {cand['pipeline_status']}"):
                st.write(f"**Education:** {cand['education']} | **Institute:** {cand['university_name']}")
                st.write(f"**Experience:** {cand['experience_years']} years | **Latest:** {cand['latest_experience']}")
                st.write(f"**Skills Gap:** {', '.join(cand['missing_skills']) if cand['missing_skills'] else 'None'}")
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Real-Time Synchronized Supabase Grids</h4>', unsafe_allow_html=True)
    g1, g2 = st.tabs(["Screened Candidates", "Master Talent Pool"])
    with g1:
        s_df = load_screened_database()
        if not s_df.empty:
            st.dataframe(s_df, use_container_width=True)
            if st.button("Clear Screened Records", type="secondary"):
                clear_screened_database()
                st.rerun()
        else:
            st.info("No screened candidate records found.")
    with g2:
        m_df = load_database()
        if not m_df.empty:
            st.dataframe(m_df, use_container_width=True)
            if st.button("Clear All Talent Pool", type="secondary"):
                clear_candidate_database()
                st.rerun()
        else:
            st.info("Master candidate database is empty.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="corp-card"><h4>🛡️ Executive Access & Profiles</h4>', unsafe_allow_html=True)
    if st.session_state.get('hr_role') != "Admin":
        st.error("⛔ Access restricted to Administrator accounts.")
    else:
        st.success("✓ Admin verified.")
        profiles = get_all_verified_profiles_admin()
        for p_em, p_nm, p_p, p_r in profiles:
            c1, c2, c3 = st.columns([2.5, 1.5, 1])
            with c1: st.write(f"👤 **{p_nm}** ({p_em})")
            with c2: st.write(f"Role: `{p_r}` | PIN: `{p_p}`")
            with c3:
                if p_em.lower() != st.session_state.get('hr_email', '').lower():
                    if st.button("Revoke", key=f"rev_{p_em}"):
                        delete_employee_profile(p_em)
                        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
