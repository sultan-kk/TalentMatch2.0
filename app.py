
"""
ARL HireMatrix Pro — Official Corporate Edition
=============================================================================
Branding: Attock Refinery Limited (ARL Official Forest Green & Charcoal Palette)
Features: Clickable Executive Badges, Bulletproof PIN Authentication,
Fast 150 DPI OCR, Safe Multi-CV Extraction, Exact 13-Column Sequence,
ARL Cascading Job Hierarchy & Real-Time Supabase Cloud Synchronized Grids.
Now with: Built-in MovieBox-Style Windows Desktop (.exe) Download Landing Page
and One-Click Desktop Mode Dismissal (Hide CTA inside Desktop Client).
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
# 1. PAGE CONFIGURATION & ARL GREEN HEXAGON FAVICON
# ===========================================================================
APP_NAME = "ARL TalentMatch "
APP_TAGLINE = "Attock Refinery Limited (ARL) • AI-Driven Automated CV Parser & JD Screener"
GROQ_MODEL = "openai/gpt-oss-120b"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]

# ⬇️ Hosted .msi / .exe release link
EXE_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/ARL-HireMatrix-Pro_1.0.0_x64_en-US.msi"

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
# 2. CLICKABLE PROFILE CARD DETECTOR (URL QUERY PARAMETERS)
# ===========================================================================
if "profile" in st.query_params:
    selected_prof = st.query_params["profile"]
    if isinstance(selected_prof, list):
        selected_prof = selected_prof[0]
    del st.query_params["profile"]
    if not st.session_state.get("selected_profile_email"):
        st.session_state.selected_profile_email = selected_prof

# ===========================================================================
# 3. SUPABASE CLOUD DATABASE CONNECTION
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

# ----------------- BULLETPROOF PIN AUTHENTICATION -----------------
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
        
        success, msg = send_smtp_email(clean_email, "ARL HireMatrix Pro - Verification OTP", f"Your verification code is: {otp}")
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
    return True, "Employee profile removed."

# ===========================================================================
# 4. ARL CORPORATE JOB CATALOG & SUPABASE HIERARCHY
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
# 5. CANDIDATE REPOSITORY & SCREENED STORAGE (13-COLUMN SEQUENCE)
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

def check_if_exists_in_db(email):
    if email in ["Not Provided", "Not Found", ""] or not email or not supabase:
        return False
    try:
        response = supabase.table("candidates").select("email").ilike("email", email.lower().strip()).execute()
        return len(response.data) > 0
    except Exception:
        return False

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
# 6. ARL CHARCOAL BLACK & OFFICIAL GREEN ACCENTS CSS
# ===========================================================================
ARL_GREEN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* ARL Header */
.cyber-header-box {
    text-align: center;
    padding: 1.8rem 1rem 1.2rem 1rem;
    margin-bottom: 1.2rem;
}

.cyber-title {
    font-size: 3.2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.8px !important;
    color: #111827 !important;
    margin: 0 0 8px 0 !important;
}

.cyber-title-pro {
    color: #166534 !important;
    background: linear-gradient(135deg, #15803D 0%, #166534 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.cyber-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
    background: rgba(22, 101, 52, 0.08) !important;
    border: 1.5px solid #166534 !important;
    padding: 5px 20px !important;
    border-radius: 30px !important;
    font-size: 0.78rem !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 1.5px !important;
    color: #166534 !important;
}

@media (prefers-color-scheme: dark) {
    .cyber-title {
        color: #F8FAFC !important;
    }
    .cyber-badge {
        background: rgba(22, 101, 52, 0.2) !important;
        border-color: #22C55E !important;
        color: #22C55E !important;
    }
}

/* CLICKABLE PROFILE BADGE CARD (CHARCOAL BLACK WITH ARL GREEN ACCENT) */
.arl-clickable-badge {
    text-decoration: none !important;
    color: inherit !important;
    display: block !important;
    cursor: pointer !important;
    transition: all 0.25s ease-in-out !important;
}

.cyber-badge-card {
    position: relative;
    background: linear-gradient(135deg, #181B1E 0%, #111315 100%) !important;
    border: 1.5px solid #1E2328 !important;
    border-left: 5px solid #166534 !important;
    border-radius: 16px !important;
    padding: 1.5rem 1.8rem !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.45) !important;
    transition: all 0.25s ease-in-out !important;
}

.arl-clickable-badge:hover .cyber-badge-card {
    border-color: #22C55E !important;
    border-left-color: #22C55E !important;
    box-shadow: 0 14px 35px rgba(0, 0, 0, 0.6), inset 0 0 15px rgba(34, 197, 94, 0.08) !important;
    transform: translateY(-3px) scale(1.01);
}

.cyber-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.8rem;
    border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
    padding-bottom: 0.5rem;
}

.cyber-access-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    color: #94A3B8;
    letter-spacing: 1px;
}

.cyber-status-dot {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    color: #22C55E;
    letter-spacing: 1px;
}

.cyber-avatar-ring {
    width: 58px;
    height: 58px;
    border-radius: 50%;
    background: #14171A;
    border: 2px solid #166534;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.7rem;
    box-shadow: 0 0 15px rgba(0, 0, 0, 0.5);
    flex-shrink: 0;
}

.cyber-name-title {
    margin: 0;
    font-size: 1.45rem;
    font-weight: 800;
    color: #F8FAFC !important;
    letter-spacing: -0.3px;
}

.cyber-role-pill {
    background: rgba(34, 197, 94, 0.12);
    border: 1px solid #166534;
    color: #22C55E;
    padding: 2px 10px;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.cyber-email-mono {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.84rem;
    color: #94A3B8;
    background: #0E1012;
    padding: 4px 10px;
    border-radius: 6px;
    display: inline-block;
    margin-top: 5px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}

/* ARL Green Corporate Buttons */
.stButton > button {
    background: linear-gradient(135deg, #166534 0%, #14532D 100%) !important;
    color: #FFFFFF !important;
    border: 1.5px solid #22C55E !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
    padding: 0.65rem 1.2rem !important;
    box-shadow: 0 4px 15px rgba(22, 101, 52, 0.3) !important;
    transition: all 0.25s ease-in-out !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #15803D 0%, #166534 100%) !important;
    color: #FFFFFF !important;
    border-color: #FFFFFF !important;
    box-shadow: 0 6px 20px rgba(34, 197, 94, 0.5) !important;
    transform: translateY(-2px);
}

/* PIN & Login Form Container */
[data-testid="stForm"] {
    background: #14171A !important;
    border: 1.5px solid #1E2328 !important;
    border-radius: 20px !important;
    padding: 2.2rem !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5) !important;
}

/* PIN Screen Heading ('🔐 Sign In: ...') */
[data-testid="stVerticalBlockBorderWrapper"] h3 {
    color: #22C55E !important;
    font-weight: 800 !important;
    font-size: 1.5rem !important;
    text-shadow: 0 0 12px rgba(34, 197, 94, 0.3) !important;
    margin-bottom: 6px !important;
}

/* 'Enter 4-digit PIN for ...' Caption */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"] p,
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"] {
    color: #CBD5E1 !important;
    font-size: 0.92rem !important;
}

/* Form Input Label ('4-Digit PIN') */
[data-testid="stForm"] label,
[data-testid="stWidgetLabel"] label,
[data-testid="stWidgetLabel"] p,
[data-testid="stForm"] label p {
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: 0.5px !important;
}

/* Character counter (0/4) color */
[data-testid="stInputCounter"] {
    color: #94A3B8 !important;
}

/* Navbar */
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
    background: linear-gradient(135deg, rgba(22, 101, 52, 0.12) 0%, rgba(20, 23, 26, 0.8) 100%);
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
    background: var(--background-color);
    border: 1.5px solid rgba(22, 101, 52, 0.25);
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
}

.corp-card h4 {
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.2px !important;
    color: light-dark(#166534, #FFFFFF) !important;
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    margin-top: 0 !important;
    margin-bottom: 1.2rem !important;
    background: linear-gradient(90deg, rgba(34, 197, 94, 0.12) 0%, rgba(22, 101, 52, 0.04) 100%) !important;
    border-left: 4px solid #166534 !important;
    border-bottom: 1px solid rgba(22, 101, 52, 0.25) !important;
    border-radius: 8px 12px 12px 8px !important;
    padding: 10px 16px !important;
}

.metric-box .val { font-size: 1.8rem; font-weight: 800; color: #22C55E; }
.metric-box .lbl { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; font-weight: 700; opacity: 0.85; }

.score-high { color: #10B981 !important; font-weight: 800; }
.score-mid { color: #F59E0B !important; font-weight: 800; }
.score-low { color: #EF4444 !important; font-weight: 800; }

div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { display: none !important; }

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
    transition: all 0.25s ease-in-out !important;
}

button[data-baseweb="tab"]:hover {
    color: #22C55E !important;
    background: rgba(34, 197, 94, 0.08) !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(22, 101, 52, 0.6) 0%, rgba(34, 197, 94, 0.2) 100%) !important;
    border: 1.5px solid #22C55E !important;
    color: #22C55E !important;
}

[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:first-child {
    border: 1.5px solid rgba(22, 101, 52, 0.4) !important;
    border-radius: 24px !important;
    padding: 2.2rem 2.2rem !important;
    background: rgba(22, 101, 52, 0.05) !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06) !important;
}

[data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"], [data-testid="column"] > div {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
}

@media (prefers-color-scheme: dark) {
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:first-child {
        border: 1.5px solid rgba(34, 197, 94, 0.35) !important;
        background: linear-gradient(135deg, rgba(13, 35, 25, 0.82) 0%, rgba(9, 24, 17, 0.92) 100%) !important;
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55), inset 0 0 25px rgba(22, 101, 52, 0.15) !important;
        backdrop-filter: blur(16px) !important;
    }
}
</style>
"""
st.markdown(ARL_GREEN_CSS, unsafe_allow_html=True)

# ===========================================================================
# 7. SESSION STATE INITIALIZATION & DESKTOP DETECTION
# ===========================================================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "hr_name" not in st.session_state: st.session_state.hr_name = ""
if "hr_email" not in st.session_state: st.session_state.hr_email = ""
if "hr_role" not in st.session_state: st.session_state.hr_role = "Recruiter"
if "selected_profile_email" not in st.session_state: st.session_state.selected_profile_email = None
if "pending_otp_email" not in st.session_state: st.session_state.pending_otp_email = None
if "pending_pin_email" not in st.session_state: st.session_state.pending_pin_email = None
if "screening_results" not in st.session_state: st.session_state.screening_results = []
if "show_download_page" not in st.session_state: st.session_state.show_download_page = False

if "is_desktop_mode" not in st.session_state:
    st.session_state.is_desktop_mode = (st.query_params.get("mode") == "desktop")
is_desktop_mode = st.session_state.is_desktop_mode or (st.query_params.get("mode") == "desktop")

# ===========================================================================
# 7.1 MOVIEBOX-STYLE DEDICATED DESKTOP DOWNLOAD LANDING PAGE
# ===========================================================================
def render_download_landing_page(exe_direct_url: str):
    st.markdown("""
    <style>
    .dl-hero-box {
        text-align: center;
        padding: 3rem 1.5rem 2.2rem 1.5rem;
        background: linear-gradient(180deg, rgba(22, 101, 52, 0.18) 0%, rgba(20, 23, 26, 0.9) 100%);
        border: 1.5px solid #1E2328;
        border-top: 3px solid #22C55E;
        border-radius: 24px;
        margin-bottom: 2.5rem;
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
    }
    .dl-badge {
        display: inline-block;
        background: rgba(34, 197, 94, 0.15);
        color: #22C55E;
        border: 1px solid #166534;
        padding: 6px 18px;
        border-radius: 30px;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 1.5px;
        margin-bottom: 1.2rem;
        text-transform: uppercase;
    }
    .dl-title {
        font-size: 3.2rem;
        font-weight: 800;
        color: #FFFFFF;
        margin: 0 0 1rem 0;
        line-height: 1.15;
    }
    .dl-subtitle {
        color: #94A3B8;
        font-size: 1.15rem;
        max-width: 680px;
        margin: 0 auto 2.2rem auto;
        line-height: 1.6;
    }
    .dl-main-btn {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        background: linear-gradient(135deg, #166534 0%, #15803D 100%);
        color: #FFFFFF !important;
        font-size: 1.18rem;
        font-weight: 800;
        padding: 1.1rem 2.8rem;
        border-radius: 14px;
        text-decoration: none;
        box-shadow: 0 10px 30px rgba(22, 101, 52, 0.45);
        border: 1.5px solid #22C55E;
        transition: all 0.25s ease-in-out;
    }
    .dl-main-btn:hover {
        background: linear-gradient(135deg, #15803D 0%, #166534 100%);
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 14px 35px rgba(34, 197, 94, 0.6);
        border-color: #FFFFFF;
    }
    .step-card {
        background: #14171A;
        border: 1.5px solid #1E2328;
        border-radius: 18px;
        padding: 2rem 1.5rem;
        text-align: center;
        height: 100%;
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        transition: all 0.25s ease;
    }
    .step-card:hover {
        border-color: #22C55E;
        transform: translateY(-4px);
    }
    .step-num {
        display: inline-block;
        width: 48px;
        height: 48px;
        line-height: 48px;
        border-radius: 50%;
        background: rgba(34, 197, 94, 0.15);
        color: #22C55E;
        font-weight: 800;
        font-size: 1.2rem;
        border: 1.5px solid #166534;
        margin-bottom: 1.2rem;
        font-family: 'JetBrains Mono', monospace;
    }
    .step-title {
        color: #FFFFFF;
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }
    .step-desc {
        color: #94A3B8;
        font-size: 0.92rem;
        line-height: 1.55;
    }
    </style>
    """, unsafe_allow_html=True)

    c_back, _ = st.columns([2.5, 7.5])
    with c_back:
        if st.button("⬅️ Back to Web Portal", use_container_width=True, key="back_to_portal_from_dl"):
            st.session_state.show_download_page = False
            st.rerun()

    st.markdown(f"""
        <div class="dl-hero-box">
            <div class="dl-badge">🪟 BUILT FOR WINDOWS 10 / 11</div>
            <h1 class="dl-title">ARL HireMatrix Pro for Windows</h1>
            <p class="dl-subtitle">Run Attock Refinery Limited's enterprise candidate extraction, AI matching, and cloud recruitment pipeline as a dedicated, high-speed desktop software.</p>
            <a href="{exe_direct_url}" target="_blank" class="dl-main-btn">
                <span>⬇️</span> Download for Windows · ARL-HireMatrix-Pro.msi (Free)
            </a>
            <div style="margin-top: 18px; color: #94A3B8; font-size: 0.85rem; font-family: 'JetBrains Mono', monospace;">
                Official Windows Installer &bull; 64-bit Architecture &bull; Instant Cloud Sync
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<h3 style='text-align: center; color: #FFFFFF; margin-bottom: 2rem;'>⚡ From Download to Screening in Three Steps</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
            <div class="step-card">
                <div class="step-num">01</div>
                <div class="step-title">Download the Installer</div>
                <div class="step-desc">Click the primary download button above and save the standalone Windows installer package to your PC.</div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
            <div class="step-card">
                <div class="step-num">02</div>
                <div class="step-title">Run Installer</div>
                <div class="step-desc">Double click the .msi package. If prompted by Windows SmartScreen, click <i>More Info &rarr; Run Anyway</i>.</div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
            <div class="step-card">
                <div class="step-num">03</div>
                <div class="step-title">Open Portal</div>
                <div class="step-desc">Launch ARL HireMatrix Pro from your desktop and enter your 4-digit PIN to begin candidate screening.</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 3.5rem;'></div>", unsafe_allow_html=True)
    st.markdown("<h4 style='color: #22C55E; margin-bottom: 1rem;'>❓ Desktop App FAQs & Guidance</h4>", unsafe_allow_html=True)
    with st.expander("❓ What should I do if Windows SmartScreen shows a warning?"):
        st.write("Since this is a custom internal enterprise package without an expensive commercial EV certificate, Windows SmartScreen may show a security prompt. Simply click **'More info'** and then click **'Run anyway'**. The application is 100% virus-free and verified.")
    with st.expander("❓ Will my screened candidate data sync between Desktop and Web?"):
        st.write("Yes! Both the Desktop application and the Web portal connect directly to the same Supabase Cloud database. Any resume uploaded or candidate screened on the desktop app is immediately available in real-time on the web version.")
    with st.expander("❓ What are the system requirements?"):
        st.write("Windows 10 or 11 (64-bit), minimum 4 GB RAM, and an active internet connection for Groq AI screening and Supabase synchronization.")

if st.session_state.show_download_page:
    render_download_landing_page(EXE_DOWNLOAD_URL)
    st.stop()

# ===========================================================================
# 8. AUTHENTICATION & LOGIN SCREEN (CHARCOAL CARDS)
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()
    col_c1, col_c2, col_c3 = st.columns([1, 3.8, 1])
    with col_c2:
        # Desktop Download CTA Banner on Login Page with ✕ Dismiss Button
        if not is_desktop_mode:
            c_banner_l, c_banner_r, c_banner_x = st.columns([6.8, 2.5, 0.7], vertical_alignment="center")
            with c_banner_l:
                st.caption("Prefer a standalone PC software?")
            with c_banner_r:
                if st.button("💻 Get App", key="dl_btn_login_top", use_container_width=True):
                    st.session_state.show_download_page = True
                    st.rerun()
            with c_banner_x:
                if st.button("✕", key="dismiss_desktop_banner", help="Hide in Desktop App"):
                    st.session_state.is_desktop_mode = True
                    st.rerun()

        with st.container(border=True):
            st.markdown(f"""
                <div class="cyber-header-box">
                    <div style="display: flex; justify-content: center; margin-bottom: 12px;">
                        <div style="
                            width: 68px; 
                            height: 68px; 
                            border-radius: 18px; 
                            background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, #14171A 100%);
                            border: 2px solid #166534;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 0 25px rgba(22, 101, 52, 0.35);
                        ">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <polygon points="12 2 22 7.5 22 16.5 12 22 2 16.5 2 7.5"></polygon>
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
                st.info(f"Email verified for **{st.session_state.pending_pin_email}**. Create your 4-digit security PIN.")
                with st.form("pin_setup_form"):
                    new_pin = st.text_input("Create 4-Digit PIN", type="password", max_chars=4, placeholder="••••")
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
                            st.success(msg)
                            st.session_state.pending_pin_email = None
                            st.rerun()
                        else:
                            st.error(msg)
                            
            elif st.session_state.pending_otp_email:
                st.markdown("### 📬 Email Verification")
                st.info(f"Enter the 6-digit security code sent to **{st.session_state.pending_otp_email}**.")
                with st.form("otp_form"):
                    otp_input = st.text_input("Enter 6-Digit OTP", placeholder="123456")
                    submit_otp = st.form_submit_button("Verify OTP", use_container_width=True)
                col_o1, col_o2 = st.columns(2)
                if submit_otp:
                    success, nag = verify_otp_code(st.session_state.pending_otp_email, otp_input)
                    if success:
                        st.success(nag)
                        st.session_state.pending_pin_email = st.session_state.pending_otp_email
                        st.session_state.pending_otp_email = None
                        st.rerun()
                    else:
                        st.error(nag)
                with col_o2:
                    if st.button("Cancel", use_container_width=True, key="cancel_otp_btn"):
                        st.session_state.pending_otp_email = None
                        st.rerun()
                        
            elif saved_profiles and not st.session_state.selected_profile_email:
                st.markdown("""
                    <div style="margin-bottom: 14px;">
                        <h3 style="margin: 0 0 0.2rem 0; font-size: 1.3rem; font-weight: 700; color: #22C55E;">👥 Active Executive Profiles</h3>
                        <p style="font-size: 0.85rem; color: #94A3B8; margin: 0;">Click on your profile card to enter your PIN:</p>
                    </div>
                """, unsafe_allow_html=True)
                
                for p_email, p_name, p_pin, p_role in saved_profiles:
                    col_card, col_del = st.columns([8.6, 1.4], vertical_alignment="center")
                    with col_card:
                        st.markdown(f"""
                            <a href="?profile={p_email}{'&mode=desktop' if is_desktop_mode else ''}" target="_self" class="arl-clickable-badge">
                                <div class="cyber-badge-card">
                                    <div class="cyber-top-bar">
                                        <span class="cyber-access-id">ARL // {hashlib.md5(p_email.encode()).hexdigest()[:8].upper()}</span>
                                        <span class="cyber-status-dot">ONLINE ◈ CLICK TO SIGN IN ➔</span>
                                    </div>
                                    <div style="display: flex; align-items: center; gap: 18px;">
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
                            </a>
                        """, unsafe_allow_html=True)
                    with col_del:
                        if st.button("🗑️", key=f"del_card_{p_email}", help=f"Delete {p_name}'s profile", use_container_width=True):
                            delete_employee_profile(p_email)
                            st.success("Profile removed.")
                            st.rerun()
                    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)
                
                st.markdown("---")
                if st.button("➕ Register New Profile", use_container_width=True, key="reg_new_emp_auth_btn"):
                    st.session_state.selected_profile_email = "new"
                    st.rerun()
                    
            elif st.session_state.selected_profile_email and st.session_state.selected_profile_email != "new":
                target_email = st.session_state.selected_profile_email
                p_match = next((p for p in saved_profiles if p[0].lower() == target_email.lower()), (target_email, "Executive User", "", "Recruiter"))
                st.markdown(f"### 🔐 Sign In: {p_match[1]}")
                st.caption(f"Enter 4-digit PIN for **{target_email}**")
                
                with st.form("pin_login_form"):
                    pin_input = st.text_input("4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                    submit_log = st.form_submit_button("Access Portal (Press Enter)", use_container_width=True)
                col_b1, col_b2 = st.columns(2)
                if submit_log:
                    success, name, role = verify_employee_pin(target_email, pin_input)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.hr_name = name if name else p_match[1]
                        st.session_state.hr_email = target_email
                        st.session_state.hr_role = role if role else "Recruiter"
                        st.session_state.selected_profile_email = None
                        try:
                            st.query_params.clear()
                            if is_desktop_mode:
                                st.query_params["mode"] = "desktop"
                        except Exception:
                            pass
                        st.success(f"Welcome back, {st.session_state.hr_name}!")
                        st.rerun()
                    else:
                        st.error("❌ Incorrect 4-Digit PIN. Please verify.")
                with col_b2:
                    if st.button("Switch Profile", use_container_width=True, key="switch_prof_auth_btn"):
                        st.session_state.selected_profile_email = None
                        try:
                            st.query_params.clear()
                            if is_desktop_mode:
                                st.query_params["mode"] = "desktop"
                        except Exception:
                            pass
                        st.rerun()
            else:
                st.markdown("### 📝 Employee / Admin Registration")
                st.caption("First registered user automatically becomes Admin with dedicated PIN creation.")
                with st.form("registration_form"):
                    reg_name = st.text_input("Full Name", placeholder="Alex Mercer")
                    reg_email = st.text_input("Company Email (@arl.com.pk)", placeholder="employee@arl.com.pk")
                    reg_pass = st.text_input("Master Password", type="password")
                    submit_reg = st.form_submit_button("Send Verification OTP", use_container_width=True)
                col_r1, col_r2 = st.columns(2)
                if submit_reg:
                    if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                        st.warning("Please verify all required fields.")
                    else:
                        success, msg = register_initial_employee(reg_name, reg_email, reg_pass)
                        if success:
                            st.success(msg)
                            st.session_state.pending_otp_email = reg_email.lower().strip()
                            st.rerun()
                        else:
                            st.error(msg)
                with col_r2:
                    if saved_profiles and st.button("Back to Profiles", use_container_width=True, key="back_to_prof_auth_btn"):
                        st.session_state.selected_profile_email = None
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
        st.error(f"⚠️ Could not read {uploaded_file.name}: {exc}")
    return None

# ===========================================================================
# 10. GROQ AI: SAFE EXTRACTION & GHOST CANDIDATE FILTER
# ===========================================================================
def build_multi_candidate_extraction_prompt(resume_text: str) -> str:
    return f"""You are an expert HR Data Extraction Specialist for Attock Refinery Limited (ARL).
Analyze the following document text carefully. The document contains candidate CVs/resumes.

CRITICAL RULES TO AVOID ERRORS:
1. FATHER IS NOT A CANDIDATE:
   - NEVER create a candidate entry for a Father, Mother, or Guardian!
   - Words like 'Father Name', 'S/O', 'D/O', or 'W/O' belong strictly inside the candidate's "father_name" field.
2. FULL NAMES ONLY:
   - Extract the COMPLETE name of the applicant (e.g. 'Dawood Hussain', do NOT truncate to 'Hussain').
3. NO DUPLICATE CLONES:
   - Do NOT split one applicant's CV into two candidates. If a resume lists 'Dawood Hussain s/o Hussain Ali', it is ONE single candidate.
   - Do not copy or duplicate identical education/degrees under multiple names.

Return a strictly valid JSON object matching this schema:
{{
  "candidates": [
    {{
      "name": "Complete Candidate Name (e.g. Dawood Hussain)",
      "father_name": "Father Name (e.g. Hussain Ali) or Not Provided",
      "education": "Qualification / Degree Title (e.g. DAE Chemical / Matric Science)",
      "cgpa": "CGPA / GPA / Percentage or Not Provided",
      "passing_year": "Passing / Graduation Year or Not Provided",
      "university_name": "Institute / Board / University Name or Not Provided",
      "dob": "Date of Birth or Not Provided",
      "email": "Candidate Email Address or Not Provided",
      "phone": "Candidate Phone Number or Not Provided",
      "experience_years": "Total Experience (e.g. Fresh, 2 Years)",
      "latest_experience": "Latest job role or company or Not Provided",
      "reference": "Reference contacts or Not Provided",
      "skills": "Key technical / engineering skills"
    }}
  ]
}}

Rules:
- If a field is not mentioned, use 'Not Provided'.
- Return ONLY the JSON object.

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
        
        if isinstance(parsed, dict):
            candidates_list = parsed.get("candidates", [])
            if not candidates_list and "name" in parsed:
                candidates_list = [parsed]
        elif isinstance(parsed, list):
            candidates_list = parsed
        else:
            candidates_list = []

        cleaned_candidates = []
        for cand in candidates_list:
            name = cand.get("name", "Unknown").strip()
            email = cand.get("email", "Not Provided").strip()
            phone = cand.get("phone", "Not Provided").strip()

            cleaned_candidates.append({
                "file_name": file_name,
                "name": name if name else "Unknown",
                "father_name": cand.get("father_name", "Not Provided").strip(),
                "education": cand.get("education", "Not Provided").strip(),
                "cgpa": cand.get("cgpa", "Not Provided").strip(),
                "passing_year": cand.get("passing_year", "Not Provided").strip(),
                "university_name": cand.get("university_name", "Not Provided").strip(),
                "dob": cand.get("dob", "Not Provided").strip(),
                "email": email,
                "phone": phone,
                "experience_years": str(cand.get("experience_years", "0")).strip(),
                "latest_experience": cand.get("latest_experience", "Not Provided").strip(),
                "reference": cand.get("reference", "Not Provided").strip(),
                "skills": cand.get("skills", "Not Provided").strip()
            })

        final_candidates = []
        for cand in cleaned_candidates:
            is_ghost = False
            for existing in final_candidates:
                same_edu = (cand["education"] != "Not Provided" and cand["education"].lower() == existing["education"].lower())
                name_is_father = (cand["name"].lower() == existing["father_name"].lower())
                if same_edu and name_is_father:
                    is_ghost = True
                    break
            if not is_ghost:
                final_candidates.append(cand)

        return final_candidates
    except Exception as exc:
        st.error(f"⚠️ Extraction failed for **{file_name}**: {exc}")
        return []

def evaluate_candidate_against_jd(client, candidate_row, jd_text: str):
    try:
        summary = f"Name: {candidate_row['Name']}, Education: {candidate_row['Qualification']}, Institute: {candidate_row['Institute']}, Experience: {candidate_row['Experience']}, Latest Role: {candidate_row['Latest Experience']}"
        prompt = f"""You are an expert HR recruiter AI for Attock Refinery Limited (ARL). Evaluate the CANDIDATE PROFILE against the JOB DESCRIPTION.
CANDIDATE: {summary}
JOB DESCRIPTION: {jd_text}

Return ONLY a valid JSON object:
{{
  "match_score": A number between 0 and 100,
  "is_relevant": true or false,
  "missing_skills": ["List", "of", "missing skills"]
}}
"""
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw_content = response.choices[0].message.content.strip()
        result = json.loads(raw_content)
        return float(result.get("match_score", 0)), bool(result.get("is_relevant", True)), result.get("missing_skills", [])
    except Exception:
        return 0.0, True, []

def generate_ai_interview_questions(client, skills_text: str, job_title: str) -> str:
    try:
        prompt = f"""Based on candidate skills '{skills_text}' and ARL Refinery job title '{job_title}', generate 5 precise technical and behavioral interview questions with model answers. Format clearly with Markdown bullet points. Do not include raw HTML."""
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw_output = response.choices[0].message.content.strip()
        return raw_output.replace("<br>", "\n").replace("<br/>", "\n").replace("<BR>", "\n")
    except Exception as e:
        return f"Could not generate interview questions: {e}"

# ===========================================================================
# 11. PORTAL NAVIGATION BAR & DASHBOARD
# ===========================================================================
df_all = load_database()
total_repo_db = len(df_all)

latest_candidate = df_all.iloc[-1]["Name"] if not df_all.empty else "None"

col_n1, col_n2 = st.columns([7.8, 2.2], vertical_alignment="center")
with col_n1:
    st.markdown(f"""
        <div class="top-navbar" style="display: flex; align-items: center; gap: 16px;">
            <div style="
                width: 48px; 
                height: 48px; 
                border-radius: 14px; 
                background: linear-gradient(135deg, rgba(34, 197, 94, 0.25) 0%, #14171A 100%);
                border: 2px solid #22C55E;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 0 20px rgba(34, 197, 94, 0.35);
                flex-shrink: 0;
            ">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 2 22 7.5 22 16.5 12 22 2 16.5 2 7.5"></polygon>
                </svg>
            </div>
            <div>
                <h2 class="top-brand-title" style="margin: 0; font-size: 1.55rem; color: #FFFFFF;">ARL HireMatrix <span style="color: #22C55E;">Pro</span></h2>
                <p class="top-brand-subtitle" style="margin: 4px 0 0 0;">Attock Refinery Limited &bull; Active: <b>{st.session_state.get('hr_name', 'Recruiter')}</b> ({st.session_state.get('hr_email', 'admin@arl.com.pk')}) &bull; Role: <b>{st.session_state.get('hr_role', 'Recruiter')}</b></p>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_n2:
    if not is_desktop_mode:
        col_dl_top, col_lock_top = st.columns(2)
        with col_dl_top:
            if st.button("💻 App", use_container_width=True, key="btn_open_dl_page_top", help="Download Windows Desktop App"):
                st.session_state.show_download_page = True
                st.rerun()
        with col_lock_top:
            if st.button("🚪 Lock", use_container_width=True, key="lock_portal_btn_top", help="Lock Session"):
                st.session_state.logged_in = False
                st.session_state.hr_name = ""
                st.session_state.hr_email = ""
                st.session_state.hr_role = "Recruiter"
                st.session_state.selected_profile_email = None
                st.session_state.screening_results = []
                try:
                    st.query_params.clear()
                    if is_desktop_mode:
                        st.query_params["mode"] = "desktop"
                except Exception:
                    pass
                st.rerun()
    else:
        if st.button("🚪 Lock Portal", use_container_width=True, key="lock_portal_btn_top_desktop", help="Lock Session"):
            st.session_state.logged_in = False
            st.session_state.hr_name = ""
            st.session_state.hr_email = ""
            st.session_state.hr_role = "Recruiter"
            st.session_state.selected_profile_email = None
            st.session_state.screening_results = []
            try:
                st.query_params.clear()
                if is_desktop_mode:
                    st.query_params["mode"] = "desktop"
            except Exception:
                pass
            st.rerun()

st.markdown(f"""
    <div class="corp-hero">
        <div class="corp-badge">
            <span>🟢 Multi-Stage ATS Session</span> &bull; <span>Total Talent Pool: {total_repo_db} Candidates</span>
        </div>
        <h1>Attock Refinery Executive Suite</h1>
        <p>Welcome back, <b>{st.session_state.get('hr_name', 'Recruiter')}</b> &mdash; Latest Added: <b>{latest_candidate}</b> | All extracted resumes are automatically appended and permanently saved to Supabase Cloud.</p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Talent Repository (Upload)", "🎯 2. JD Screening & Matching", "🗄️ 3. Live Database & Screening Grids", "🛡️ 4. Admin Controls"])

# ----------------- TAB 1: TALENT REPOSITORY INGESTION -----------------
with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Ingest & Parse Candidate Resumes (Single / Multi-CV PDF)</h4>', unsafe_allow_html=True)
    st.caption("Upload individual resumes or single bulk merged PDFs containing multiple candidates. AI will extract and append every candidate.")
    
    uploaded_repo_files = st.file_uploader("Upload candidate resumes to repository", type=ACCEPTED_TYPES, accept_multiple_files=True, label_visibility="collapsed")
    
    g_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    if st.button("⚡ Extract & Save All Candidates to Master Database", type="primary", use_container_width=True, disabled=not (uploaded_repo_files and g_key)):
        client = Groq(api_key=g_key)
        extracted_batch = []
        progress = st.progress(0.0, text="Reading and extracting profiles via Groq...")
        
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
            if skp > 0:
                st.success(f"🎉 Successfully extracted **{ins} new candidate(s)**! (Skipped **{skp} duplicate profiles**)")
            else:
                st.success(f"🎉 Successfully extracted **{ins} candidate(s)** and appended to Supabase repository!")
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    df_repo = load_database()
    if not df_repo.empty:
        st.markdown('<div class="corp-card"><h4>📋 Current Candidates in Talent Repository</h4>', unsafe_allow_html=True)
        
        st.download_button(
            "📊 Download Master Talent Repository Report (.xlsx)",
            data=generate_repository_excel(df_repo),
            file_name="ARL_Master_Talent_Repository.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_repo_master_btn"
        )
        st.markdown("---")
        
        for idx, row in df_repo.iterrows():
            c_d1, c_d2, c_d3, c_d4 = st.columns([2, 2, 2, 1])
            with c_d1: st.write(f"👤 **{row['Name']}**")
            with c_d2: st.write(f"✉️ `{row['Email']}`")
            with c_d3: st.write(f"🎓 {row['Qualification']} ({row['Institute']})")
            with c_d4:
                unique_hash = hashlib.md5(f"repo_{idx}_{row['Email']}_{row['Name']}".encode()).hexdigest()[:10]
                safe_key = f"del_repo_btn_{unique_hash}"
                if st.button("🗑️ Delete", key=safe_key, use_container_width=True):
                    delete_single_candidate_from_db(row['Email'] if row['Email'] not in ["Not Provided", "Not Found", ""] else row['Name'])
                    st.success(f"Removed {row['Name']} from repository!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 2: ARL CASCADING JOB MENU & SCREENING -----------------
with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening & Smart Matching</h4>', unsafe_allow_html=True)
    st.caption("Select Target Position from ARL Department & Job Titles hierarchy, or customize on the fly.")
    
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
        jd_title_input = st.text_input("Enter Specific Job Designation", placeholder="e.g. Lead Turnaround Planning Specialist", key="custom_jd_title")
    else:
        jd_title_input = chosen_job_item
        
    st.info(f"Target Position Selected: **{jd_title_input}** *(Department: {chosen_dept})*")
    
    with st.expander("⚙️ Manage ARL Job Catalog (Add, Edit, or Remove Jobs & Departments)"):
        st.caption("Permanently modify or add job positions in the ARL database hierarchy.")
        m_tab1, m_tab2, m_tab3 = st.tabs(["➕ Add New Job", "✏️ Edit / Rename Job", "🗑️ Delete Job"])
        
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
    jd_desc_text = st.text_area("Job Description & Requirements", height=120, placeholder="Paste detailed refinery requirements, qualifications, and skills here...", key="jd_desc_text_field")
    
    st.markdown("**🎯 Select Minimum Passing Score Threshold (%)**")
    screening_threshold = st.slider(
        "Candidates scoring above this will be highlighted; all JD-relevant candidates remain reviewable.",
        min_value=0, max_value=100, value=50, step=5,
        label_visibility="collapsed",
        key="screening_threshold_slider_step2"
    )
    st.caption(f"Current Highlight Threshold: **{screening_threshold}%**")
    
    df_pool = load_database()
    g_key_active = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    
    if st.button("⚡ Run AI Screening against Talent Pool", type="primary", use_container_width=True, disabled=not (jd_desc_text.strip() and jd_title_input.strip() and not df_pool.empty and g_key_active), key="run_screening_btn_main"):
        client = Groq(api_key=g_key_active)
        screened_results = []
        progress = st.progress(0.0, text="Evaluating candidates against ARL Job Description via Groq...")
        
        for idx, row in df_pool.iterrows():
            progress.progress((idx + 1) / (len(df_pool) + 1), text=f"Evaluating {row['Name']}...")
            score, is_relevant, missing = evaluate_candidate_against_jd(client, row, jd_desc_text)
            
            if is_relevant:
                initial_status = "Shortlisted" if score >= screening_threshold else "Talent Pool"
                
                screened_results.append({
                    "job_title": jd_title_input,
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
                    "pipeline_status": initial_status
                })
            
        progress.empty()
        screened_results.sort(key=lambda x: x["match_score"], reverse=True)
        st.session_state.screening_results = screened_results
        save_screened_to_supabase(screened_results)
        st.success(f"Screening complete! Evaluated {len(screened_results)} candidate(s) & saved to Supabase.")
        st.rerun()
        
    if df_pool.empty:
        st.info("⚠️ Talent repository is currently empty. Please upload resumes in **Step 1** first.")
        
    st.markdown('</div>', unsafe_allow_html=True)

    screening_results_safe = st.session_state.get('screening_results', [])
    if screening_results_safe:
        st.markdown('<div class="corp-card"><h4>📊 JD-Relevant Candidates & Recruiter Decision Pipeline</h4>', unsafe_allow_html=True)
        results = sorted(screening_results_safe, key=lambda x: x["match_score"], reverse=True)
        
        if not results:
            st.warning("⚠️ No candidates in the repository matched the requirements of this Job Description.")
        else:
            st.download_button(
                "📊 Download Master Screened Candidates Report (.xlsx)",
                data=generate_screening_excel(results),
                file_name="ARL_Screened_Candidates_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_screened_master_btn"
            )
            st.markdown("---")
        
        client = Groq(api_key=g_key_active) if g_key_active else None

        for rank, cand in enumerate(results, start=1):
            score_cls = "score-high" if cand["match_score"] >= 75 else ("score-mid" if cand["match_score"] >= 40 else "score-low")
            
            with st.expander(f"#{rank} — {cand['name']} | Match Score: {cand['match_score']}% | Stage: {cand['pipeline_status']}", expanded=(rank == 1)):
                c1, c2 = st.columns([1.3, 1])
                with c1:
                    st.markdown(f"**💼 Target Role:** `{cand.get('job_title', 'Not Specified')}`")
                    st.markdown(f"**✉️️ Email:** `{cand['email']}` | **📞 Phone:** `{cand['phone']}`")
                    st.markdown(f"**👤 Father's Name:** {cand['father_name']}")
                    st.markdown(f"**🎓 Qualification:** {cand['education']} (CGPA: {cand['cgpa']} | Year: {cand['passing_year']})")
                    st.markdown(f"**🏫 Institute:** {cand['university_name']}")
                    st.markdown(f"**💼 Experience:** {cand['experience_years']} | **Latest:** {cand['latest_experience']}")
                    st.markdown(f"**🔗 Reference:** {cand['reference']}")
                    
                    st.markdown(f'<div class="metric-box" style="margin-top: 15px; width: 150px;"><div class="val {score_cls}">{cand["match_score"]}%</div><div class="lbl">Match Rating</div></div>', unsafe_allow_html=True)
                
                with c2:
                    st.markdown("**❌ Skill Gaps / Missing vs. JD:**")
                    if cand["missing_skills"]:
                        for skill in cand["missing_skills"]:
                            st.markdown(f"- {skill}")
                    else:
                        st.caption("No significant skill gaps identified.")

                st.markdown("---")
                st.markdown("#### 🔄 Recruiter Decision & Pipeline Stage")
                stage_options = ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"]
                current_stage = cand["pipeline_status"]
                stage_idx = stage_options.index(current_stage) if current_stage in stage_options else 0
                
                cand_hash = hashlib.md5(f"screen_{rank}_{cand['email']}_{cand['name']}".encode()).hexdigest()[:10]
                stage_key = f"stage_sel_{rank}_{cand_hash}"
                new_stage = st.selectbox(
                    "Update Stage", 
                    stage_options, 
                    index=stage_idx,
                    key=stage_key
                )
                if new_stage != cand["pipeline_status"]:
                    cand["pipeline_status"] = new_stage
                    update_candidate_pipeline_status(cand["email"], new_stage)
                    update_screened_candidate_status(cand["email"], cand["job_title"], new_stage)
                    st.success(f"Pipeline stage updated to **{new_stage}**!")
                    st.rerun()

                st.markdown("---")
                q_key = f"gen_q_{rank}_{cand_hash}"
                if st.button(f"💡 Generate AI Interview Q&A for {cand['name']}", key=q_key):
                    if client:
                        with st.spinner("Generating tailored interview questions..."):
                            q_text = generate_ai_interview_questions(client, "General Engineering and Refinery Skills", cand['job_title'])
                            st.markdown("#### 🎯 AI Generated Interview Guide:")
                            st.markdown(q_text)
                    else:
                        st.error("Groq API key required.")

                if cand['email'] not in ["Not Provided", "Not Found", ""] and cand['email']:
                    st.markdown("#### ✉ Conditional Email Dispatcher")
                    
                    if cand["pipeline_status"] in ["Shortlisted", "Interview Scheduled"]:
                        default_msg = f"Dear {cand['name']},\n\nWe were deeply impressed by your credentials and match score ({cand['match_score']}%) for the {cand['job_title']} position at Attock Refinery Limited (ARL). We would love to invite you for an interview round.\n\nBest Regards,\nTeam ARL HR"
                        email_subject = f"Interview Invitation - {cand['job_title']}"
                        st.info(f"✓ Stage is **{cand['pipeline_status']}**: Interview Invitation template loaded.")
                    elif cand["pipeline_status"] == "Hired":
                        default_msg = f"Dear {cand['name']},\n\nCongratulations! We are thrilled to offer you the position of {cand['job_title']} at Attock Refinery Limited (ARL). Welcome aboard!\n\nBest Regards,\nTeam ARL HR"
                        email_subject = f"Official Offer Letter - {cand['job_title']}"
                        st.success("✓ Stage is **Hired**: Official Offer Letter template loaded.")
                    else:
                        default_msg = f"Dear {cand['name']},\n\nThank you for your interest in the {cand['job_title']} position at Attock Refinery Limited (ARL). Although your background is notable, we have decided to move forward with other candidates. We wish you the best.\n\nBest Regards,\nTeam ARL HR"
                        email_subject = f"Application Status Update - {cand['job_title']}"
                        st.warning("⚠ Stage is **Rejected**: Regret template loaded.")

                    msg_key = f"inv_msg_{rank}_{cand_hash}"
                    invite_msg = st.text_area("Email Message", value=default_msg, key=msg_key)
                    
                    send_key = f"send_inv_{rank}_{cand_hash}"
                    if st.button(f"📧 Send Email to {cand['name']}", key=send_key):
                        ok, res_m = send_smtp_email(cand['email'], email_subject, invite_msg)
                        if ok:
                            st.success(f"Email sent successfully to {cand['email']}!")
                        else:
                            st.error(res_m)

        st.markdown("</div>", unsafe_allow_html=True)

# ----------------- TAB 3: DUAL LIVE SYNCHRONIZED GRIDS -----------------
with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Live Database & Screening Grids</h4>', unsafe_allow_html=True)
    st.caption("Real-time synchronized candidate records from Supabase Cloud.")
    
    sub_grid_1, sub_grid_2 = st.tabs(["🎯 Screened Candidates Grid", "📥 Master Talent Pool Grid"])
    
    with sub_grid_1:
        df_screened = load_screened_database()
        if df_screened.empty:
            st.info("No candidates have been screened yet. Run AI Screening in Step 2 to populate this live cloud grid.")
        else:
            grid_s = df_screened.copy()
            grid_s.insert(0, "Sr. No.", range(1, len(grid_s) + 1))
            st.data_editor(grid_s, use_container_width=True, height=420, disabled=True, key="screened_grid_view_live")
            st.markdown("---")
            c_s1, c_s2 = st.columns([2, 1])
            with c_s1:
                st.download_button(
                    "📊 Download Screened Report (.xlsx)",
                    data=generate_screening_excel(df_screened.to_dict(orient="records")),
                    file_name="ARL_Screened_Candidates_Master.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_screened_master_grid_btn"
                )
            with c_s2:
                if st.button("🗑️ Clear Screened History", type="secondary", key="clear_screened_btn_grid", use_container_width=True):
                    clear_screened_database()
                    st.success("Screened candidate records cleared successfully!")
                    st.rerun()

    with sub_grid_2:
        df_db = load_database()
        if df_db.empty:
            st.info("Master database is currently empty. Upload resumes in Step 1.")
        else:
            grid_df = df_db.copy()
            grid_df.insert(0, "Sr. No.", range(1, len(grid_df) + 1))
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
                    st.success("Repository cleared successfully!")
                    st.rerun()
                    
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------- TAB 4: ADMIN CONTROLS -----------------
with tab4:
    st.markdown('<div class="corp-card"><h4>🛡️ Admin Access & Employee Management</h4></div>', unsafe_allow_html=True)
    
    if st.session_state.get('hr_role') != "Admin":
        st.error("⛔ **Access Denied**: You do not have Administrator privileges to view this control panel.")
    else:
        st.success("✓ Admin privileges active & verified.")
        
        st.markdown("### 👥 Active Employee Profiles & Confidential PINs")
        all_emps = get_all_verified_profiles_admin()
        st.markdown(f"**Total Active Registered Employees:** {len(all_emps)}")
        for emp_email, emp_name, emp_pin, emp_role in all_emps:
            col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
            with col_a1: st.write(f"👤 **{emp_name}** ({emp_email}) — *{emp_role}*")
            with col_a2: st.write(f"PIN: `{emp_pin}`")
            with col_a3:
                if emp_email.lower() != st.session_state.get('hr_email', '').lower():
                    if st.button("🗑️ Revoke", key=f"rev_admin_{emp_email.replace('@','_')}", use_container_width=True):
                        delete_employee_profile(emp_email)
                        st.success(f"Access revoked for {emp_name}.")
                        st.rerun()
                else:
                    st.caption("Current User")
    st.markdown("</div>", unsafe_allow_html=True)
