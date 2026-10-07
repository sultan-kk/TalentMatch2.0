"""
ARL TalentMatch — Official Corporate Edition (Enterprise Suite)
=============================================================================
Branding: Attock Refinery Limited (ARL Forest Green & Adaptive Theme)
Features: Guaranteed 165x165px Square Profile Cards, Smooth Emerald Glow Hover,
Instant Logout/Lock, Permanent Supabase Badges, Deduplication Engine, Bottom Append.
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
from PIL import Image, ImageDraw

# ===========================================================================
# 1. PAGE CONFIGURATION & ARL FAVICON
# ===========================================================================
APP_NAME = "ARL TalentMatch"
APP_TAGLINE = "Attock Refinery Limited (ARL) • AI-Driven Automated CV Parser & JD Screener"
GROQ_MODEL = "openai/gpt-oss-120b"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
EXE_DIRECT_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/Arl_TalentMatch.exe"
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
            "email": clean_email, "name": name, "password": hash_password(password),
            "pin": None, "role": role, "is_verified": 0, "otp": otp, "avatar": "👑"
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
    if not supabase: return False, "Supabase client not initialized."
    try:
        response = supabase.table("hr_users").select("otp").eq("email", email.lower().strip()).execute().data
        if response and response[0].get("otp") == entered_otp:
            return True, "OTP verified successfully!"
    except Exception:
        pass
    return False, "Invalid OTP code."

def save_employee_pin(email, pin):
    if not supabase: return False, "Supabase client not initialized."
    clean_email = email.lower().strip()
    pin_str = str(pin).strip()
    try:
        supabase.table("hr_users").update({"pin": pin_str, "is_verified": 1}).eq("email", clean_email).execute()
        return True, "Security PIN configured successfully!"
    except Exception as e:
        return False, str(e)

def delete_employee_profile(email):
    if not supabase: return False, "Supabase client not initialized."
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
        except Exception:
            pass
    return DEFAULT_ARL_CATALOG

# ===========================================================================
# 4. DATABASE STORAGE (DEDUPLICATION & CHRONOLOGICAL APPEND)
# ===========================================================================
def load_database():
    expected_cols = [
        "Name", "Father Name", "Qualification", "CGPA", 
        "Passing Year", "Institute", "DOB", "Email", 
        "Phone Number", "Experience", "Latest Experience", "Reference", "Pipeline Status", "Added At"
    ]
    if not supabase: return pd.DataFrame(columns=expected_cols)
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
    if not supabase: return 0, 0
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
        elif c_name and c_name.lower() in existing_names and c_name.lower() not in ["unknown", "not provided"]:
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
    if not supabase or not screened_list: return
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in screened_list:
        skills_str = ", ".join(r.get("missing_skills", [])) if isinstance(r.get("missing_skills"), list) else str(r.get("missing_skills", ""))
        payload = {
            "job_title": str(r.get("job_title", "Not Specified")),
            "candidate_name": str(r.get("name", "Unknown")),
            "father_name": str(r.get("
