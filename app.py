"""
ARL TalentMatch — Official Corporate Edition (Enterprise Suite)
=============================================================================
Branding: Attock Refinery Limited (ARL Forest Green & Adaptive Theme)
Features: Guaranteed 165x165px Square Profile Cards, Emerald Glow Hover,
Permanent Supabase Badges, Deduplication Engine, AI Vision OCR for JPG/PNG.
"""

import io
import json
import os
import re
import hashlib
import random
import smtplib
import base64
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import pandas as pd
import streamlit as st
from groq import Groq
from supabase import create_client, Client
from PIL import Image, ImageDraw

# ===========================================================================
# 1. PAGE CONFIGURATION & ARL FAVICON
# ===========================================================================
APP_NAME = "ARL TalentMatch"
APP_TAGLINE = "Attock Refinery Limited (ARL) • AI-Driven Automated CV Parser & JD Screener"
GROQ_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "llama-3.2-11b-vision-preview"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
EXE_DIRECT_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/TalentMatch.msi"
AVAILABLE_BADGES = ["👔", "💼", "🛡️", "🎖️", "⚡", "🔬", "🛢️", "⚙️", "📈", "🎯", "👑", "🚀", "💡", "💻", "💎", "🏛️"]

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

# ----------------- AUTHENTICATION HELPERS -----------------
def get_user_avatar(email):
    clean_email = email.lower().strip()
    if "profile_avatars" in st.session_state and clean_email in st.session_state.profile_avatars:
        return st.session_state.profile_avatars[clean_email]
    if supabase:
        try:
            res = supabase.table("hr_users").select("avatar").eq("email", clean_email).execute()
            if res.data and res.data[0].get("avatar"):
                av = res.data[0].get("avatar")
                if "profile_avatars" not in st.session_state:
                    st.session_state.profile_avatars = {}
                st.session_state.profile_avatars[clean_email] = av
                return av
        except Exception:
            pass
    return "👑"

def set_user_avatar(email, avatar_char):
    clean_email = email.lower().strip()
    if "profile_avatars" not in st.session_state:
        st.session_state.profile_avatars = {}
    st.session_state.profile_avatars[clean_email] = avatar_char
    if supabase:
        try:
            supabase.table("hr_users").update({"avatar": avatar_char}).eq("email", clean_email).execute()
        except Exception:
            pass

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
                if r.get("avatar"):
                    if "profile_avatars" not in st.session_state:
                        st.session_state.profile_avatars = {}
                    st.session_state.profile_avatars[r.get("email").lower().strip()] = r.get("avatar")
    except Exception:
        pass
    return profiles

def register_initial_employee(name, email, password):
    clean_email = email.lower().strip()
    otp = str(random.randint(100000, 999999))
    if not supabase:
        return False, "Supabase client not initialized."
    try:
        existing = supabase.table("hr_users").select("pin").eq("email", clean_email).execute().data
        if existing and existing[0].get("pin"):
            return False, "This email is already registered. Please sign in."
        
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
            "avatar": "👑"
        }
        supabase.table("hr_users").upsert(data).execute()
        
        success, msg = send_smtp_email(clean_email, "ARL TalentMatch - Verification OTP", f"Your verification code is: {otp}")
        if success:
            return True, "Registration initiated! Check your email for verification OTP."
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
    return False, "Invalid OTP code."

def save_employee_pin(email, pin):
    if not supabase:
        return False, "Supabase client not initialized."
    clean_email = email.lower().strip()
    pin_str = str(pin).strip()
    try:
        supabase.table("hr_users").update({"pin": pin_str, "is_verified": 1}).eq("email", clean_email).execute()
        return True, "Security PIN configured successfully!"
    except Exception as e:
        return False, str(e)

def delete_employee_profile(email):
    if not supabase:
        return False, "Supabase client not initialized."
    try:
        supabase.table("hr_users").delete().eq("email", email.lower().strip()).execute()
        return True, "Profile removed."
    except Exception as e:
        return False, str(e)

# ===========================================================================
# 3. ARL JOB CATALOG
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
        except Exception:
            pass
    return DEFAULT_ARL_CATALOG

# ===========================================================================
# 4. DATABASE STORAGE (DEDUPLICATION & CHRONOLOGICAL APPEND)
# ===========================================================================
def load_database():
    expected_cols = [
        "Name", "Father Name", "Qualification", "CGPA", "Passing Year", "Institute",
        "DOB", "Email", "Phone Number", "Experience", "Latest Experience", "Reference",
        "Pipeline Status", "Added At"
    ]
    if not supabase:
        return pd.DataFrame(columns=expected_cols)
    try:
        response = supabase.table("candidates").select("*").order("id", desc=False).execute()
        rows = response.data
        if rows:
            mapped = []
            for r in rows:
                mapped.append({
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
                    "Pipeline Status": r.get("pipeline_status", "Talent Pool"),
                    "Added At": r.get("added_at", "Not Provided")
                })
            df = pd.DataFrame(mapped)[expected_cols]
            df.index = range(1, len(df) + 1)
            return df
    except Exception:
        pass
    return pd.DataFrame(columns=expected_cols)

def save_candidates_to_repository(new_candidates):
    if not supabase:
        return 0, 0
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_emails = set()
    existing_phones = set()
    existing_names = set()
    try:
        curr_res = supabase.table("candidates").select("candidate_name, email, phone").execute()
        if curr_res.data:
            for rec in curr_res.data:
                em = str(rec.get("email", "")).strip().lower()
                ph = str(rec.get("phone", "")).strip()
                nm = str(rec.get("candidate_name", "")).strip().lower()
                if em and "not" not in em: existing_emails.add(em)
                if ph and "not" not in ph: existing_phones.add(ph)
                if nm and "not" not in nm and "unknown" not in nm: existing_names.add(nm)
    except Exception:
        pass

    inserted, skipped = 0, 0
    for c in new_candidates:
        c_name = str(c.get("name", "Unknown")).strip()
        c_email = str(c.get("email", "Not Provided")).strip().lower()
        c_phone = str(c.get("phone", "Not Provided")).strip()

        is_dup = False
        if c_email and "not" not in c_email and c_email in existing_emails:
            is_dup = True
        elif c_phone and "not" not in c_phone and c_phone in existing_phones:
            is_dup = True
        elif c_name and c_name.lower() in existing_names and c_name.lower() not in ["unknown", "name"]:
            is_dup = True

        if is_dup:
            skipped += 1
            continue

        payload = {
            "candidate_name": c_name,
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
            inserted += 1
            if c_email and "not" not in c_email: existing_emails.add(c_email)
            if c_phone and "not" not in c_phone: existing_phones.add(c_phone)
            if c_name: existing_names.add(c_name.lower())
        except Exception:
            skipped += 1

    return inserted, skipped

def save_screened_to_supabase(screened_list):
    if not supabase or not screened_list:
        return
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in screened_list:
        skills_str = ", ".join(r.get("missing_skills", [])) if isinstance(r.get("missing_skills"), list) else str(r.get("missing_skills", ""))
        payload = {
            "job_title": str(r.get("job_title", "Not Specified")),
            "candidate_name": str(r.get("name", "Unknown")),
            "father_name": str(r.get("father_name", "Not Provided")),
            "education": str(r.get("education", "Not Provided")),
            "cgpa": str(r.get("cgpa", "Not Provided")),
            "passing_year": str(r.get("passing_year", "Not Provided")),
            "university_name": str(r.get("university_name", "Not Provided")),
            "dob": str(r.get("dob", "Not Provided")),
            "email": str(r.get("email", "Not Provided")),
            "phone": str(r.get("phone", "Not Provided")),
            "experience_years": str(r.get("experience_years", "0")),
            "latest_experience": str(r.get("latest_experience", "Not Provided")),
            "reference": str(r.get("reference", "Not Provided")),
            "match_score": float(r.get("match_score", 0)),
            "missing_skills": skills_str,
            "pipeline_status": str(r.get("pipeline_status", "Shortlisted")),
            "screened_at": current_timestamp
        }
        try:
            supabase.table("screened_candidates").insert(payload).execute()
        except Exception as e:
            st.error(f"Supabase Screened Insert Error: {e}")

def load_screened_database():
    expected_cols = [
        "Job Title", "Match Score (%)", "Pipeline Status", "Name", "Father Name",
        "Qualification", "CGPA", "Passing Year", "Institute", "DOB", "Email",
        "Phone Number", "Experience", "Latest Experience", "Reference", "Missing Skills", "Screened At"
    ]
    if not supabase:
        return pd.DataFrame(columns=expected_cols)
    try:
        response = supabase.table("screened_candidates").select("*").order("id", desc=False).execute()
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
            df = pd.DataFrame(mapped)[expected_cols]
            df.index = range(1, len(df) + 1)
            return df
    except Exception:
        pass
    return pd.DataFrame(columns=expected_cols)

def update_screened_candidate_status_db(email, job_title, new_status):
    if not supabase:
        return
    try:
        supabase.table("screened_candidates").update({"pipeline_status": new_status}).ilike("email", email).ilike("job_title", job_title).execute()
    except Exception:
        pass

def clear_candidate_database():
    if supabase:
        supabase.table("candidates").delete().neq("id", 0).execute()

def clear_screened_database():
    if supabase:
        supabase.table("screened_candidates").delete().neq("id", 0).execute()

# ===========================================================================
# 5. CSS (BULLET-PROOF PROFILE GRID STYLING)
# ===========================================================================
ADAPTIVE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

[data-testid="stSidebar"], [data-testid="collapsedControl"] {
    display: none !important;
}

div[data-testid="stColumn"]:has(.profile-card-marker) {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: flex-start !important;
}

div[data-testid="stColumn"]:has(.profile-card-marker) div[data-testid="stButton"] {
    display: flex !important;
    justify-content: center !important;
    width: 100% !important;
}

div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] {
    width: 165px !important;
    height: 165px !important;
    min-width: 165px !important;
    max-width: 165px !important;
    min-height: 165px !important;
    max-height: 165px !important;
    border-radius: 30px !important;
    background: linear-gradient(145deg, #181B20 0%, #111317 100%) !important;
    border: 2px solid #2D333B !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5) !important;
    padding: 0 !important;
    margin: 0 auto !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
}

div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] p {
    font-size: 5.5rem !important;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 !important;
    transition: transform 0.3s ease !important;
}

div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"]:hover {
    transform: translateY(-8px) scale(1.05) !important;
    border-color: #10B981 !important;
    box-shadow: 0 15px 35px rgba(16, 185, 129, 0.4), 0 0 20px rgba(16, 185, 129, 0.2) !important;
    background: #1C2026 !important;
}

div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"] {
    border-radius: 20px !important;
    font-size: 0.75rem !important;
    padding: 0.15rem 0.8rem !important;
    background: rgba(16, 185, 129, 0.1) !important;
    border: 1px solid rgba(16, 185, 129, 0.3) !important;
    color: #10B981 !important;
    margin-top: 10px !important;
    width: auto !important;
    min-height: 28px !important;
}

.profile-meta-title {
    text-align: center;
    font-size: 1.15rem;
    font-weight: 700;
    color: #FFFFFF !important;
    margin-top: 12px;
    line-height: 1.2;
}

.profile-meta-role {
    text-align: center;
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    color: #10B981 !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-top: 2px;
}

div[data-testid="stMainBlockContainer"]:not(:has(.profile-card-marker)) button[kind="primary"] {
    background: #047857 !important;
    border-color: #059669 !important;
    color: #FFFFFF !important;
}

.top-navbar {
    background: var(--secondary-background-color);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-left: 6px solid #10B981;
    border-radius: 14px;
    padding: 0.9rem 1.4rem;
    margin-bottom: 1.2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.corp-hero {
    background: var(--secondary-background-color);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 14px;
    padding: 1.5rem 1.8rem;
    margin-bottom: 1.5rem;
    border-left: 6px solid #10B981;
}

.corp-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 16px;
    padding: 1.6rem;
    margin-bottom: 1.5rem;
}

.corp-card h4 {
    margin-top: 0;
    margin-bottom: 1rem;
    font-weight: 700;
    color: #10B981;
}
</style>
"""
st.markdown(ADAPTIVE_CSS, unsafe_allow_html=True)

# ===========================================================================
# 6. SESSION STATE INITIALIZATION
# ===========================================================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "hr_name" not in st.session_state: st.session_state.hr_name = ""
if "hr_email" not in st.session_state: st.session_state.hr_email = ""
if "hr_role" not in st.session_state: st.session_state.hr_role = "Recruiter"
if "profile_avatars" not in st.session_state: st.session_state.profile_avatars = {}
if "screening_results" not in st.session_state: st.session_state.screening_results = []
if "show_registration" not in st.session_state: st.session_state.show_registration = False
if "pending_pin_email" not in st.session_state: st.session_state.pending_pin_email = None
if "pending_otp_email" not in st.session_state: st.session_state.pending_otp_email = None
if "show_download_page" not in st.session_state: st.session_state.show_download_page = False

# ===========================================================================
# 7. DIALOGS (PIN & BADGE)
# ===========================================================================
@st.dialog("🔐 Enter Security PIN")
def show_pin_dialog(email, name, role):
    st.write(f"Sign in to executive profile for **{name}**")
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
    st.markdown("""
        <style>
        div[data-testid="stDialog"] div[data-testid="stColumn"] { padding: 3px !important; }
        div[data-testid="stDialog"] div.stButton > button {
            width: 100% !important; height: 55px !important;
            border-radius: 12px !important; background: #18191C !important;
            border: 1.5px solid #2A2E33 !important; padding: 0 !important;
        }
        div[data-testid="stDialog"] div.stButton > button p { font-size: 2rem !important; margin: 0 !important; }
        </style>
    """, unsafe_allow_html=True)
    st.write(f"Select a corporate avatar badge for **{name}**:")
    cols = st.columns(4)
    for idx, badge in enumerate(AVAILABLE_BADGES):
        with cols[idx % 4]:
            if st.button(badge, key=f"stk_btn_{email}_{idx}", use_container_width=True):
                set_user_avatar(email, badge)
                st.success("Badge permanently saved!")
                st.rerun()

# ===========================================================================
# 8. AUTHENTICATION & LOGIN SCREEN
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()

    if st.session_state.show_download_page:
        st.markdown("---")
        st.markdown(f"""
            <div style="background: var(--secondary-background-color); border: 1.5px solid #10B981; border-radius: 18px; padding: 2.2rem; margin-bottom: 2rem; text-align: center;">
                <div style="font-size: 2.8rem; margin-bottom: 8px;">💻</div>
                <h2 style="margin-bottom: 8px; font-weight: 800;">ARL TalentMatch Desktop Edition</h2>
                <p style="max-width: 650px; margin: 0 auto 20px auto; opacity: 0.85;">
                    Run Attock Refinery's recruitment suite natively on your Windows PC for high-performance offline execution and cloud synchronization.
                </p>
                <a href="{EXE_DIRECT_DOWNLOAD_URL}" target="_blank" style="background: #059669; color: white; padding: 0.75rem 2rem; border-radius: 10px; font-weight: 700; font-size: 1.05rem; text-decoration: none; display: inline-block;">📥 Download Windows Installer (.msi)</a>
            </div>
        """, unsafe_allow_html=True)
        if st.button("⬅ Back to Portal Login", use_container_width=True):
            st.session_state.show_download_page = False
            st.rerun()
        st.stop()

    if st.session_state.pending_pin_email:
        _, mid_col, _ = st.columns([1, 2.2, 1])
        with mid_col:
            st.markdown("### 🔐 Security PIN Setup")
            with st.form("pin_setup_form"):
                new_pin = st.text_input("Create 4-Digit PIN", type="password", max_chars=4)
                confirm_pin = st.text_input("Confirm 4-Digit PIN", type="password", max_chars=4)
                submit_pin = st.form_submit_button("Save PIN & Continue", use_container_width=True)
            if submit_pin:
                if len(new_pin) == 4 and new_pin == confirm_pin:
                    success, msg = save_employee_pin(st.session_state.pending_pin_email, new_pin)
                    if success:
                        st.success(msg)
                        st.session_state.pending_pin_email = None
                        st.rerun()
                else:
                    st.error("Invalid or non-matching PIN.")
        st.stop()

    elif st.session_state.show_registration:
        _, mid_col, _ = st.columns([1, 2.2, 1])
        with mid_col:
            st.markdown("### 📝 Register Executive Profile")
            with st.form("universal_registration_form"):
                reg_name = st.text_input("Full Name")
                reg_email = st.text_input("Email Address")
                reg_pass = st.text_input("Master Password", type="password")
                submit_reg = st.form_submit_button("Register Profile", use_container_width=True)
            if submit_reg:
                success, msg = register_initial_employee(reg_name, reg_email, reg_pass)
                if success:
                    st.success(msg)
                    st.session_state.pending_pin_email = reg_email.lower().strip()
                    st.session_state.show_registration = False
                    st.rerun()
                else:
                    st.error(msg)
            if st.button("⬅ Back to Profiles", use_container_width=True):
                st.session_state.show_registration = False
                st.rerun()
        st.stop()

    col_dl1, col_dl2 = st.columns([7.5, 2.5], vertical_alignment="center")
    with col_dl1:
        st.markdown("🖥️ **Need desktop offline execution?** Download our standalone Windows MSI app.")
    with col_dl2:
        if st.button("📥 Download App & FAQs", key="dl_portal_top", use_container_width=True):
            st.session_state.show_download_page = True
            st.rerun()

    st.markdown("<hr style='opacity: 0.25; margin-top: 0.5rem; margin-bottom: 0.5rem;'>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="text-align: center; padding: 1.5rem 1rem 2rem 1rem;">
            <h1 style="font-size: 2.8rem; font-weight: 800; margin-bottom: 4px;">{APP_NAME}</h1>
            <div style="font-size: 1.05rem; font-weight: 500; opacity: 0.85;">{APP_TAGLINE}</div>
        </div>
    """, unsafe_allow_html=True)

    all_items = list(saved_profiles) + [("REGISTER_CARD", "New Profile", "", "Register")]
    cols_per_row = 4
    for i in range(0, len(all_items), cols_per_row):
        row_items = all_items[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for idx, item in enumerate(row_items):
            with cols[idx]:
                st.markdown('<div class="profile-card-marker" style="display:none;"></div>', unsafe_allow_html=True)
                if item[0] == "REGISTER_CARD":
                    if st.button("➕", key=f"add_card_{i}_{idx}", type="primary"):
                        st.session_state.show_registration = True
                        st.rerun()
                    st.markdown("""
                        <div class="profile-meta-title">New Profile</div>
                        <div class="profile-meta-role">Register Account</div>
                    """, unsafe_allow_html=True)
                else:
                    p_email, p_name, p_pin, p_role = item
                    avatar_sticker = get_user_avatar(p_email)
                    if st.button(avatar_sticker, key=f"ucard_{i}_{idx}", type="primary"):
                        show_pin_dialog(p_email, p_name, p_role)
                    if st.button("✏️ Change Badge", key=f"ebtn_{i}_{idx}", type="secondary"):
                        show_sticker_picker_dialog(p_email, p_name)
                    st.markdown(f"""
                        <div class="profile-meta-title">{p_name}</div>
                        <div class="profile-meta-role">{p_role}</div>
                    """, unsafe_allow_html=True)
    st.stop()

# ===========================================================================
# 9. OCR & MULTI-RESUME EXTRACTION ENGINE (AI VISION + ROBUST OCR)
# ===========================================================================
def extract_text_from_image(file_bytes: bytes, client: Groq = None) -> str:
    """Extract text from PNG/JPG using Groq AI Vision first, local OCR as fallback."""
    g_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    if g_key:
        try:
            g_client = client or Groq(api_key=g_key)
            b64_img = base64.b64encode(file_bytes).decode("utf-8")
            resp = g_client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all readable text, candidate names, contact details, education, work experience, and technical skills from this resume image. Output pure clean text."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                        }
                    ]
                }],
                max_tokens=2500,
                temperature=0.1,
            )
            extracted_text = resp.choices[0].message.content.strip()
            if len(extracted_text) > 30:
                return extracted_text
        except Exception:
            pass

    # Fallback to local tesseract if installed
    try:
        import pytesseract
        if os.name == 'nt' and os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        pil_img = Image.open(io.BytesIO(file_bytes)).convert("L")
        return pytesseract.image_to_string(pil_img)
    except Exception:
        return ""

def extract_text_from_pdf(file_bytes: bytes, client: Groq = None) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if len(page_text.strip()) > 30:
                text_parts.append(f"--- PAGE {idx} ---\n" + page_text)
            else:
                # Scanned PDF page fallback to AI Vision
                try:
                    pil_img = page.to_image(resolution=150).original
                    img_buffer = io.BytesIO()
                    pil_img.save(img_buffer, format="PNG")
                    ocr_res = extract_text_from_image(img_buffer.getvalue(), client=client)
                    if ocr_res.strip():
                        text_parts.append(f"--- PAGE {idx} (OCR) ---\n" + ocr_res)
                except Exception:
                    pass
    return "\n\n".join(text_parts)

def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx
    document = docx.Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in document.paragraphs if p.text.strip()])

def extract_resume_text(uploaded_file, client: Groq = None):
    name = uploaded_file.name.lower()
    try:
        uploaded_file.seek(0)
        b = uploaded_file.read()
        if name.endswith(".pdf"):
            return extract_text_from_pdf(b, client=client)
        elif name.endswith(".docx"):
            return extract_text_from_docx(b)
        elif name.endswith((".png", ".jpg", ".jpeg")):
            return extract_text_from_image(b, client=client)
    except Exception as e:
        st.error(f"Read error on {uploaded_file.name}: {e}")
    return ""

def parse_multiple_candidates_from_text(client, full_text):
    chunk_size = 14000
    overlap = 500
    chunks = []
    if len(full_text) <= chunk_size:
        chunks.append(full_text)
    else:
        start = 0
        while start < len(full_text):
            chunks.append(full_text[start:start + chunk_size])
            start += chunk_size - overlap

    all_extracted_candidates = []
    seen_identifiers = set()

    for chunk in chunks:
        prompt = f"""You are an expert HR Parser analyzing a combined document containing ONE OR MULTIPLE RESUMES/CVS. Detect ALL separate candidates present in this text and return each as a separate item in the 'candidates' array.
Return strictly valid JSON with this exact schema:
{{
  "candidates": [
    {{
      "name": "Full Name",
      "father_name": "Father Name or Not Provided",
      "education": "Degree Name",
      "cgpa": "CGPA or percentage",
      "passing_year": "Graduation Year",
      "university_name": "University/College",
      "dob": "Date of birth",
      "email": "Email address",
      "phone": "Phone number",
      "experience_years": "Total years of experience (numeric string, e.g. '3')",
      "latest_experience": "Most recent role & company",
      "reference": "Reference if any"
    }}
  ]
}}

DOCUMENT TEXT:
{chunk}
"""
        try:
            res = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = res.choices[0].message.content.strip()
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1:
                content = content[start_idx:end_idx+1]
                parsed = json.loads(content)
            else:
                parsed = {}

            for cand in parsed.get("candidates", []):
                cand_name = str(cand.get("name", "")).strip()
                cand_email = str(cand.get("email", "")).strip().lower()
                cand_phone = str(cand.get("phone", "")).strip()
                uid = cand_email if cand_email and "not" not in cand_email else f"{cand_name.lower()}_{cand_phone}"
                if cand_name and cand_name.lower() not in ["unknown", "name"] and uid not in seen_identifiers:
                    seen_identifiers.add(uid)
                    all_extracted_candidates.append(cand)
        except Exception as e:
            st.error(f"❌ Groq API ya Data Parsing Error: {e}")

    return all_extracted_candidates

def evaluate_candidate_against_jd(client, candidate_row, jd_text, selected_job_title=""):
    try:
        summary = f"Name: {candidate_row['Name']}, Edu: {candidate_row['Qualification']}, Inst: {candidate_row['Institute']}, Exp: {candidate_row['Experience']}, Latest: {candidate_row['Latest Experience']}"
        prompt = f"""Evaluate CANDIDATE against ARL position '{selected_job_title}' and JD. Provide match_score (0-100), is_relevant (true), and missing_skills list.
CANDIDATE: {summary}
JD: {jd_text}
Return ONLY valid JSON:
{{"match_score": 50, "is_relevant": true, "missing_skills": []}}
"""
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        content = res.choices[0].message.content.strip()
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1:
            content = content[start_idx:end_idx+1]
            parsed = json.loads(content)
        else:
            parsed = {"match_score": 50, "is_relevant": True, "missing_skills": ["JSON Error"]}
        return float(parsed.get("match_score", 50)), True, parsed.get("missing_skills", [])
    except Exception as e:
        st.error(f"❌ Groq API Screening Error: {e}")
        return 50.0, True, []

def generate_ai_interview_questions(client, name, role, skills):
    try:
        prompt = f"Generate 5 precise interview questions with ideal answers for candidate {name} applying for ARL position {role} with skills: {skills}. Bullet points."
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate questions: {e}"

# ===========================================================================
# 10. MAIN DASHBOARD & TABS
# ===========================================================================
df_all = load_database()
user_avatar = get_user_avatar(st.session_state.hr_email)

col_nav_left, col_nav_right = st.columns([7, 3], vertical_alignment="center")
with col_nav_left:
    st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="font-size: 1.8rem; background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 10px; padding: 4px 10px;">{user_avatar}</div>
            <div>
                <h3 style="margin: 0; font-size: 1.35rem; font-weight: 800;">{APP_NAME} Pro</h3>
                <span style="font-size: 0.8rem; opacity: 0.8;">Logged in as: <b>{st.session_state.hr_name}</b> ({st.session_state.hr_role})</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_nav_right:
    c_btn1, c_btn2 = st.columns([1.2, 1], vertical_alignment="center")
    with c_btn1:
        if st.button("📥 Download Suite", key="dash_top_dl_btn", use_container_width=True):
            st.session_state.show_download_page = True
            st.rerun()
    with c_btn2:
        if st.button("🚪 Lock Portal", key="dash_top_lock_btn", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.hr_name = ""
            st.session_state.hr_email = ""
            st.session_state.hr_role = "Recruiter"
            st.rerun()

st.markdown(f"""
    <div class="corp-hero">
        <h2 style="margin: 0 0 6px 0; font-weight: 800;">Attock Refinery Executive Suite</h2>
        <p style="margin: 0; opacity: 0.85;">Total Central Repository: <b>{len(df_all)} Screened & Registered Candidates</b></p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "📥 1. Talent Repository (Upload)", "🎯 2. JD Screening & Matching",
    "🗄️ 3. Live Database Grids", "🛡️ 4. Admin Controls"
])

# ----------------- TAB 1: TALENT REPOSITORY -----------------
with tab1:
    if st.session_state.get("extraction_done"):
        st.toast("✅ Data extraction finished successfully!", icon="✅")
        st.success(st.session_state.get("extraction_msg", "Candidates successfully extracted and saved!"))
        st.session_state.extraction_done = False

    st.markdown('<div class="corp-card"><h4>📥 Step 1: Ingest & Parse Resumes (Bulk & Combined PDFs Supported)</h4>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Upload Candidate CVs (PDF, DOCX, PNG, JPG) — Multiple Files & Scanned CVs Supported",
        type=ACCEPTED_TYPES, accept_multiple_files=True
    )
    
    g_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    if st.button("⚡ Extract & Append to Supabase", type="primary", use_container_width=True, disabled=not uploaded_files):
        client = Groq(api_key=g_key)
        batch = []
        total_files = len(uploaded_files)
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, file in enumerate(uploaded_files, start=1):
            status_text.markdown(f"⏳ **Reading & Segmenting File {idx} of {total_files}:** `{file.name}`...")
            progress_bar.progress(int((idx / total_files) * 100))
            try:
                text = extract_resume_text(file, client=client)
                if not text or len(text.strip()) < 30:
                    st.error(f"❌ File '{file.name}' se readable text extract nahi ho saka.")
                    continue

                st.info(f"📄 '{file.name}' se {len(text)} characters read ho gaye. AI parsing shuru...")
                candidates_in_file = parse_multiple_candidates_from_text(client, text)
                if not candidates_in_file:
                    st.warning(f"⚠ AI ne '{file.name}' read ki lekin valid candidate data wapis nahi kiya.")
                else:
                    batch.extend(candidates_in_file)
            except Exception as err:
                st.error(f"⚠ Unexpected Error on `{file.name}`: {err}")

        status_text.empty()
        progress_bar.empty()

        if batch:
            ins, skp = save_candidates_to_repository(batch)
            msg = f"🎉 Processed {len(batch)} candidate(s): **{ins} new candidate(s) appended to database**."
            if skp > 0:
                msg += f" ({skp} duplicate(s) automatically skipped)."
            st.session_state.extraction_done = True
            st.session_state.extraction_msg = msg
            st.rerun()
        else:
            st.error("No candidate profiles could be extracted.")
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 2: JD SCREENING -----------------
with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening</h4>', unsafe_allow_html=True)
    catalog = load_arl_job_catalog()
    dept = st.selectbox("Select Department", list(catalog.keys()))
    job_role = st.selectbox("Select Position", catalog.get(dept, []))
    jd_text = st.text_area("Job Description / Requirements", height=130, placeholder="Paste job specs here...")
    slider_thresh = st.slider("Match Score Threshold (%)", 0, 100, 40, step=5)

    if st.button("⚡ Run AI Candidate Screening", type="primary", use_container_width=True, disabled=not (jd_text.strip() and not df_all.empty)):
        client = Groq(api_key=g_key)
        res = []
        for idx, row in df_all.iterrows():
            score, is_rel, missing = evaluate_candidate_against_jd(client, row, jd_text, selected_job_title=job_role)
            if score >= slider_thresh:
                res.append({
                    "job_title": job_role, "name": row["Name"], "father_name": row["Father Name"],
                    "education": row["Qualification"], "cgpa": row["CGPA"], "passing_year": row["Passing Year"],
                    "university_name": row["Institute"], "dob": row["DOB"], "email": row["Email"],
                    "phone": row["Phone Number"], "experience_years": row["Experience"],
                    "latest_experience": row["Latest Experience"], "reference": row["Reference"],
                    "match_score": score, "missing_skills": missing, "pipeline_status": "Shortlisted"
                })
        st.session_state.screening_results = res
        save_screened_to_supabase(res)
        st.success(f"Screening complete! {len(res)} candidate(s) evaluated and saved to database.")

    display_results = st.session_state.screening_results
    if not display_results:
        db_s = load_screened_database()
        if not db_s.empty:
            display_results = db_s.to_dict(orient="records")

    if display_results:
        st.markdown("### 📋 Screened Candidates")
        if st.button("🗑️ Clear Screening View", type="secondary", key="clear_screening_view_btn"):
            st.session_state.screening_results = []
            st.success("Screening view reset.")
            st.rerun()

        for rank, cand in enumerate(display_results, 1):
            c_name = cand.get('Name') or cand.get('name', 'Unknown')
            c_score = cand.get('Match Score (%)') if 'Match Score (%)' in cand else cand.get('match_score', 0)
            c_email = cand.get('Email') or cand.get('email', '')
            c_job = cand.get('Job Title') or cand.get('job_title', job_role)

            with st.expander(f"#{rank} — {c_name} • Match: {c_score}%"):
                col_st1, col_st2 = st.columns([3, 1], vertical_alignment="center")
                with col_st1:
                    new_status = st.selectbox("Update Pipeline Status", ["Shortlisted", "Interviewing", "Offered", "Rejected", "Talent Pool"], index=0, key=f"status_{rank}_{c_email}")
                with col_st2:
                    if st.button("Save Status", key=f"up_{rank}_{c_email}"):
                        update_screened_candidate_status_db(c_email, c_job, new_status)
                        st.success("Status updated!")

                c_act1, c_act2 = st.columns(2)
                with c_act1:
                    if st.button("📧 Send Interview Call Email", key=f"email_{rank}_{c_email}", use_container_width=True):
                        body = f"Dear {c_name},\n\nYou have been shortlisted for the position of {c_job} at Attock Refinery Limited (ARL).\n\nBest regards,\nARL HR Team"
                        ok, msg = send_smtp_email(c_email, f"Interview Call - ARL TalentMatch ({c_job})", body)
                        if ok: st.success("Email dispatched!")
                        else: st.error(msg)
                with c_act2:
                    if st.button("💡 Generate AI Questions", key=f"q_{rank}_{c_email}", use_container_width=True):
                        q_text = generate_ai_interview_questions(Groq(api_key=g_key), c_name, c_job, str(cand))
                        st.info(q_text)
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 3: DATABASE GRIDS -----------------
with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Real-Time Synchronized Database Grids</h4>', unsafe_allow_html=True)
    g1, g2 = st.tabs(["Screened Candidates", "Master Talent Pool"])
    with g1:
        s_df = load_screened_database()
        if not s_df.empty:
            st.dataframe(s_df, use_container_width=True)
            if st.button("🗑️ Clear Screened Candidates Table", type="secondary", key="clear_screened_btn"):
                clear_screened_database()
                st.success("Screened candidates records cleared from Supabase.")
                st.rerun()
        else:
            st.info("No screened candidates found.")
    with g2:
        m_df = load_database()
        if not m_df.empty:
            st.dataframe(m_df, use_container_width=True)
            if st.button("🗑️ Clear Master Talent Pool", type="secondary", key="clear_pool_btn"):
                clear_candidate_database()
                st.success("Master talent pool cleared.")
                st.rerun()
        else:
            st.info("Master talent pool is empty.")
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- TAB 4: ADMIN CONTROLS -----------------
with tab4:
    st.markdown('<div class="corp-card"><h4>🛡 Admin User Controls</h4>', unsafe_allow_html=True)
    profiles = get_all_verified_profiles()
    for p_em, p_nm, p_p, p_r in profiles:
        c1, c2, c3 = st.columns([3, 1.5, 1], vertical_alignment="center")
        with c1: st.write(f"👤 **{p_nm}** ({p_em})")
        with c2: st.write(f"Role: `{p_r}`")
        with c3:
            if st.button("Revoke", key=f"rev_{p_em}", type="secondary"):
                delete_employee_profile(p_em)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
