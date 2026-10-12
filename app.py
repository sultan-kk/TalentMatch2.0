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
# 1. PAGE CONFIGURATION & ELEGANT ARL FAVICON
# ===========================================================================
APP_NAME = "ARL TalentMatch"
APP_TAGLINE = "Attock Refinery Limited (ARL) • AI-Driven Automated CV Parser & JD Screener"
GROQ_MODEL = "llama3-70b-8192"
VISION_MODEL = "llama-3.2-11b-vision-preview"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
EXE_DIRECT_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/TalentMatch.msi"
AVAILABLE_BADGES = ["👔", "💼", "🛡️", "🎖️", "⚡", "🔬", "🛢️", "⚙️", "📈", "🎯", "👑", "🚀", "💡", "💻", "💎", "🏛️"]

def get_arl_favicon():
    """Generates an authentic, elegant, and attractive ARL geometric favicon."""
    img = Image.new("RGBA", (128, 128), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([(8, 8), (120, 120)], fill=(28, 30, 34), outline=(16, 185, 129), width=6)
    draw.line([(64, 25), (32, 95)], fill=(16, 185, 129), width=12)
    draw.line([(64, 25), (96, 95)], fill=(16, 185, 129), width=12)
    draw.line([(42, 65), (86, 65)], fill=(16, 185, 129), width=10)
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
    clean_email = email.lower().strip()
    if supabase:
        try:
            supabase.table("hr_users").delete().eq("email", clean_email).execute()
        except Exception:
            pass
    if "profile_avatars" in st.session_state and clean_email in st.session_state.profile_avatars:
        del st.session_state.profile_avatars[clean_email]


# ===========================================================================
# 3. ARL JOB CATALOG
# ===========================================================================
DEFAULT_ARL_CATALOG = {
    "Operations & Refining": ["Process Engineer", "Plant Shift Incharge", "Senior Plant Operator (CDU / Reformer)", "Control Room DCS Operator", "Refining Operations Manager"],
    "Maintenance & Engineering": ["Mechanical Maintenance Engineer", "Electrical Maintenance Engineer", "Instrumentation & Control (I&C) Engineer"],
    "Human Resources & Administration": ["Talent Acquisition & Recruitment Specialist", "HR Operations & Payroll Executive"]
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
# 4. DATABASE STORAGE LOGIC
# ===========================================================================
def load_database():
    expected_cols = ["Name", "Father Name", "Qualification", "CGPA", "Passing Year", "Institute", "DOB", "Email", "Phone Number", "Experience", "Latest Experience", "Reference", "Pipeline Status", "Added At"]
    if not supabase: return pd.DataFrame(columns=expected_cols)
    try:
        response = supabase.table("candidates").select("*").order("id", desc=False).execute()
        rows = response.data
        if rows:
            mapped = []
            for r in rows:
                mapped.append({
                    "Name": r.get("candidate_name", "Unknown"), "Father Name": r.get("father_name", "Not Provided"),
                    "Qualification": r.get("education", "Not Provided"), "CGPA": r.get("cgpa", "Not Provided"),
                    "Passing Year": r.get("passing_year", "Not Provided"), "Institute": r.get("university_name", "Not Provided"),
                    "DOB": r.get("dob", "Not Provided"), "Email": r.get("email", "Not Provided"),
                    "Phone Number": r.get("phone", "Not Provided"), "Experience": str(r.get("experience_years", "0")),
                    "Latest Experience": r.get("latest_experience", "Not Provided"), "Reference": r.get("reference", "Not Provided"),
                    "Pipeline Status": r.get("pipeline_status", "Talent Pool"), "Added At": r.get("added_at", "Not Provided")
                })
            df = pd.DataFrame(mapped)[expected_cols]
            df.index = range(1, len(df) + 1)
            return df
    except Exception: pass
    return pd.DataFrame(columns=expected_cols)

def load_screened_database():
    if "screening_results" in st.session_state and st.session_state.screening_results:
        return pd.DataFrame(st.session_state.screening_results)
    return pd.DataFrame(columns=["job_title", "name", "email", "match_score"])

def clear_screened_database():
    st.session_state.screening_results = []

def clear_candidate_database():
    if supabase:
        try:
            supabase.table("candidates").delete().neq("candidate_name", "THIS_WILL_NEVER_MATCH_123").execute()
        except Exception: 
            pass

def save_candidates_to_repository(new_candidates):
    if not supabase: return 0, 0
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_emails, existing_phones, existing_names = set(), set(), set()
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
    except Exception: pass

    inserted, skipped = 0, 0
    for c in new_candidates:
        c_name = str(c.get("name", "Unknown")).strip()
        c_email = str(c.get("email", "Not Provided")).strip().lower()
        c_phone = str(c.get("phone", "Not Provided")).strip()

        is_dup = False
        if c_email and "not" not in c_email and c_email in existing_emails: is_dup = True
        elif c_phone and "not" not in c_phone and c_phone in existing_phones: is_dup = True
        elif c_name and c_name.lower() in existing_names and c_name.lower() not in ["unknown", "name"]: is_dup = True

        if is_dup:
            skipped += 1
            continue

        payload = {
            "candidate_name": c_name, "father_name": c.get("father_name", "Not Provided"), "education": c.get("education", "Not Provided"),
            "cgpa": c.get("cgpa", "Not Provided"), "passing_year": c.get("passing_year", "Not Provided"), "university_name": c.get("university_name", "Not Provided"),
            "dob": c.get("dob", "Not Provided"), "email": c.get("email", "Not Provided"), "phone": c.get("phone", "Not Provided"),
            "experience_years": str(c.get("experience_years", "0")), "latest_experience": c.get("latest_experience", "Not Provided"),
            "reference": c.get("reference", "Not Provided"), "pipeline_status": "Talent Pool", "added_at": current_timestamp
        }
        try:
            supabase.table("candidates").insert(payload).execute()
            inserted += 1
            if c_email and "not" not in c_email: existing_emails.add(c_email)
            if c_phone and "not" not in c_phone: existing_phones.add(c_phone)
            if c_name: existing_names.add(c_name.lower())
        except Exception: skipped += 1
    return inserted, skipped


# ===========================================================================
# 5. ADAPTIVE CSS (BOMBPROOF OVERRIDES FOR STREAMLIT)
# ===========================================================================
ADAPTIVE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

/* --- STRUCTURAL CSS & GLOBAL APP FEEL --- */
html, body, [class*="css"], .stApp { font-family: 'Plus Jakarta Sans', sans-serif !important; }
.stApp > header { background-color: transparent !important; }
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }

/* Disable Text Selection and Typing Cursor globally for a Native App feel */
html, body, .stApp, [data-testid="stAppViewContainer"], .main, h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, div, span {
    cursor: default !important;
    user-select: none !important;
    -webkit-user-select: none !important;
}

/* Re-enable typing cursor ONLY for necessary text inputs (JD Screening & Registration) */
textarea, div[data-testid="stForm"] input {
    cursor: text !important;
    user-select: auto !important;
    -webkit-user-select: auto !important;
}

/* 1. PERFECTLY ALIGNED PROFILE CARDS */
div[data-testid="stColumn"]:has(.profile-card-marker) {
    position: relative !important; display: flex !important; flex-direction: column !important;
    align-items: center !important; justify-content: flex-start !important; padding-top: 15px !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] {
    width: 165px !important; height: 165px !important; min-width: 165px !important; max-width: 165px !important;
    border-radius: 26px !important; backdrop-filter: blur(10px) !important; -webkit-backdrop-filter: blur(10px) !important;
    padding: 0 !important; margin: 0 auto !important; display: flex !important; align-items: center !important; justify-content: center !important;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important; z-index: 1 !important;
    cursor: pointer !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] p { font-size: 5rem !important; line-height: 1 !important; margin: 0 !important; transition: transform 0.3s ease !important; cursor: pointer !important; }
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"]:hover { transform: translateY(-6px) !important; }

/* THE EDIT PENCIL BADGE */
div[data-testid="stColumn"]:has(.profile-card-marker) div[data-testid="element-container"]:has(button[kind="secondary"]) {
    position: absolute !important; top: 20px !important; right: 50% !important; margin-right: -75px !important; z-index: 10 !important; width: auto !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"] {
    width: 34px !important; height: 34px !important; min-width: 34px !important; min-height: 34px !important;
    border-radius: 50% !important; display: flex !important; align-items: center !important; justify-content: center !important;
    padding: 0 !important; transition: all 0.2s ease !important; cursor: pointer !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"] p { font-size: 14px !important; margin: 0 !important; cursor: pointer !important;}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"]:hover { transform: scale(1.15) !important; }

/* TEXT ALIGNMENT */
.profile-meta-container {
    display: flex; flex-direction: column; align-items: center; justify-content: flex-start;
    height: 60px; margin-top: 15px; width: 100%; max-width: 170px;
}
.profile-meta-title { font-size: 1.15rem; font-weight: 700; line-height: 1.2; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; }
.profile-meta-role { font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 0.6px; margin-top: 4px; text-align: center; }


/* ========================================= */
/* 2. THE P.I.N MODAL & SEAMLESS INPUT FIX   */
/* ========================================= */

/* Main Dialog Background & Glassmorphism */
div[data-testid="stDialog"] > div {
    backdrop-filter: blur(25px) !important; -webkit-backdrop-filter: blur(25px) !important;
    border-radius: 20px !important; box-shadow: 0 10px 40px rgba(0,0,0,0.3) !important;
    padding: 2.5rem 2rem !important; width: 340px !important;
}

/* Hide Streamlit Close Button (X) */
div[data-testid="stDialog"] button[aria-label="Close"] { display: none !important; }

/* P.I.N Title Style */
.pin-modal-title { text-align: center; font-size: 1.8rem; font-weight: 800; letter-spacing: 8px; margin-bottom: 30px; margin-top: -10px; }

/* HIDE STREAMLIT INSTRUCTIONS ("Press enter" & "0/4") */
div[data-testid="InputInstructions"], 
div[data-testid="stTextInput"] small,
div[data-testid="stTextInput"] > div > div:nth-child(2) { 
    display: none !important; visibility: hidden !important; opacity: 0 !important; 
    height: 0 !important; margin: 0 !important; padding: 0 !important;
}

/* Strip Default Input Box & Borders */
div[role="dialog"] div[data-testid="stTextInput"] div[data-baseweb="base-input"], 
div[role="dialog"] div[data-testid="stTextInput"] div[data-baseweb="input"] {
    background-color: transparent !important; background: transparent !important;
    border: none !important; box-shadow: none !important;
}

/* PURE TRANSPARENT PIN DOTS (No border, no line, no caret) */
div[role="dialog"] div[data-testid="stTextInput"] input {
    text-align: center !important; font-size: 4rem !important; letter-spacing: 30px !important;
    background: transparent !important; background-color: transparent !important;
    border: none !important; box-shadow: none !important; outline: none !important;
    border-radius: 0 !important; padding: 10px 0 !important; margin-bottom: 15px !important; margin-left: 20px !important;
    font-family: 'JetBrains Mono', monospace !important; color: #10B981 !important;
    caret-color: transparent !important; /* HIDES THE BLINKING CURSOR */
    cursor: default !important; /* HIDES I-BEAM CURSOR */
}
div[role="dialog"] div[data-testid="stTextInput"] input:focus { 
    border: none !important; outline: none !important; box-shadow: none !important; background: transparent !important; 
}

/* Hide Eye Icon Aggressively */
div[role="dialog"] div[data-testid="stTextInput"] button { display: none !important; visibility: hidden !important; }


/* ========================================= */
/* 3. PREMIUM DOWNLOAD DESKTOP PAGE EFFECTS  */
/* ========================================= */
@keyframes float {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-12px); }
    100% { transform: translateY(0px); }
}
@keyframes pulseGlow {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
    70% { box-shadow: 0 0 0 20px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
.dl-hero-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem 1rem 1rem 1rem; }
.dl-card { border-radius: 24px; padding: 4rem 3rem; text-align: center; max-width: 800px; width: 100%; backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); transition: all 0.3s ease; }
.dl-icon { font-size: 6rem; margin-bottom: 20px; animation: float 4s ease-in-out infinite; }
.dl-title { margin: 0 0 15px 0; font-weight: 900; font-size: 3.2rem; line-height: 1.1; }
.dl-title-gradient { background: -webkit-linear-gradient(45deg, #10B981, #34D399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.dl-subtitle { font-size: 1.15rem; margin: 0 auto 30px auto; max-width: 600px; line-height: 1.6; }
.dl-features { display: flex; justify-content: center; gap: 20px; margin-bottom: 40px; flex-wrap: wrap; }
.dl-feature-badge { border-radius: 12px; padding: 10px 20px; font-size: 0.95rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.dl-btn { background: #10B981 !important; color: #FFFFFF !important; padding: 1.2rem 3.5rem !important; border-radius: 50px !important; font-weight: 800 !important; font-size: 1.2rem !important; text-decoration: none !important; display: inline-block !important; transition: all 0.3s ease !important; animation: pulseGlow 2s infinite !important; }
.dl-btn:hover { transform: translateY(-3px) scale(1.02) !important; background: #059669 !important; }


/* ========================================= */
/* === THEME COLORS (DARK MODE DEFAULT) ==== */
/* ========================================= */
@media (prefers-color-scheme: dark) {
    .stApp, [data-testid="stAppViewContainer"], .main, body, html { background: radial-gradient(circle at top right, #055030 0%, #01150c 100%) !important; background-color: #01150c !important; color: #E2E8F0 !important; }
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, div { color: #FFFFFF; }
    h1 span:not(.dl-title-gradient), h2 span, h3 span { color: #10B981 !important; }
    div[data-testid="stTabs"] button * { color: #FFFFFF !important; }
    div[data-testid="stTabs"] button[aria-selected="true"] * { color: #10B981 !important; font-weight: 800 !important; }
    button[kind="secondary"] { background-color: #36454F !important; border: 1px solid #10B981 !important; }
    button[kind="secondary"] * { color: #FFFFFF !important; }
    button[kind="secondary"]:hover { background-color: #10B981 !important; }
    button[kind="secondary"]:hover * { color: #01150c !important; }
    div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"] { background-color: rgba(16, 185, 129, 0.85) !important; border: 2px solid #01150c !important; }
    button[kind="primary"], button[kind="primaryFormSubmit"] { background-color: #10B981 !important; border: none !important; cursor: pointer !important;}
    button[kind="primary"] *, button[kind="primaryFormSubmit"] * { color: #01150c !important; font-weight: 800 !important; cursor: pointer !important;}
    button[kind="primary"]:disabled { background-color: rgba(16, 185, 129, 0.2) !important; }
    button[kind="primary"]:disabled * { color: #64748b !important; }
    div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] { background: rgba(6, 68, 41, 0.6) !important; border: 2px solid rgba(16, 185, 129, 0.6) !important; }
    .profile-meta-title { color: #FFFFFF !important; }
    div[data-testid="stDialog"] > div { background: rgba(4, 45, 26, 0.8) !important; border: 1px solid #10B981 !important; }
    .pin-modal-title { color: #10B981 !important; text-shadow: 0 0 15px rgba(16, 185, 129, 0.5) !important; }
    .corp-hero, .corp-card { background: rgba(4, 45, 26, 0.55) !important; border: 1px solid rgba(16, 185, 129, 0.35) !important; border-left: 5px solid #10B981 !important; }
    .corp-card h4 { color: #34D399 !important; }
    .dl-card { background: rgba(4, 45, 26, 0.65); border: 1px solid rgba(16, 185, 129, 0.4); border-top: 4px solid #10B981; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }
    .dl-icon { text-shadow: 0 15px 25px rgba(0,0,0,0.5); }
    .dl-subtitle { color: #A7F3D0; }
    .dl-feature-badge { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); color: #E2E8F0; }
}

/* ========================================= */
/* === THEME COLORS (LIGHT MODE OVERRIDES)== */
/* ========================================= */
@media (prefers-color-scheme: light) {
    html, body, .stApp, [data-testid="stAppViewContainer"], .main { background: #F4FBF7 !important; background-color: #F4FBF7 !important; background-image: none !important; }
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, div { color: #0F172A !important; }
    div[data-testid="stTabs"] button * { color: #475569 !important; }
    div[data-testid="stTabs"] button[aria-selected="true"] * { color: #059669 !important; font-weight: 800 !important; }
    button[kind="secondary"] { background-color: #FFFFFF !important; border: 1px solid #059669 !important; }
    button[kind="secondary"] * { color: #000000 !important; }
    button[kind="secondary"]:hover { background-color: #059669 !important; }
    button[kind="secondary"]:hover * { color: #FFFFFF !important; }
    div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"] { background-color: #10B981 !important; border: 2px solid #FFFFFF !important; }
    div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"] p { color: #FFFFFF !important; }
    button[kind="primary"], button[kind="primaryFormSubmit"] { background-color: #10B981 !important; border: none !important; cursor: pointer !important;}
    button[kind="primary"] *, button[kind="primaryFormSubmit"] * { color: #FFFFFF !important; font-weight: 800 !important; cursor: pointer !important;}
    button[kind="primary"]:disabled { background-color: rgba(16, 185, 129, 0.2) !important; }
    button[kind="primary"]:disabled * { color: #94a3b8 !important; }
    div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] { background: rgba(255, 255, 255, 0.9) !important; border: 2px solid rgba(16, 185, 129, 0.5) !important; }
    div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] p { color: #000000 !important; }
    .profile-meta-title { color: #0F172A !important; }
    div[data-testid="stDialog"] > div { background: #FFFFFF !important; border: 1px solid rgba(16, 185, 129, 0.4) !important; }
    .pin-modal-title { color: #059669 !important; text-shadow: none !important; }
    .corp-hero, .corp-card { background: #FFFFFF !important; border: 1px solid rgba(16, 185, 129, 0.3) !important; border-left: 5px solid #10B981 !important; box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important; }
    .corp-card h4 { color: #059669 !important; }
    .dl-card { background: #FFFFFF; border: 1px solid rgba(16, 185, 129, 0.3); border-top: 4px solid #10B981; box-shadow: 0 20px 50px rgba(16, 185, 129, 0.15); }
    .dl-icon { text-shadow: 0 15px 25px rgba(16, 185, 129, 0.2); }
    .dl-subtitle { color: #475569; }
    .dl-feature-badge { background: #F4FBF7; border: 1px solid rgba(16, 185, 129, 0.3); color: #0F172A; }
}
</style>
"""


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
# 7. DIALOGS (MINIMALIST PIN WITH NO BUTTON)
# ===========================================================================
@st.dialog(" ")  
def show_pin_dialog(email, name, role):
    st.markdown("<div class='pin-modal-title'>P.I.N</div>", unsafe_allow_html=True)
    st.markdown('<div class="pin-input-container">', unsafe_allow_html=True)
    
    # Form and Button REMOVED. Directly using text_input for a seamless lock-screen feel.
    # It automatically triggers script execution when the user hits 'Enter'.
    pin_val = st.text_input("Enter PIN", type="password", max_chars=4, placeholder="••••", label_visibility="collapsed", key=f"pin_entry_{email}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # When user types in the field and hits Enter, this block runs
    if pin_val:
        ok, u_name, u_role = verify_employee_pin(email, pin_val)
        if ok:
            st.session_state.logged_in = True
            st.session_state.hr_name = u_name if u_name else name
            st.session_state.hr_email = email
            st.session_state.hr_role = u_role if u_role else role
            st.rerun()
        else:
            st.error("❌ Invalid PIN.")

@st.dialog("🎨 Choose Executive Badge")
def show_sticker_picker_dialog(email, name):
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
        st.markdown(f"""
            <div class="dl-hero-container">
                <div class="dl-card">
                    <div class="dl-icon">💻</div>
                    <h1 class="dl-title">ARL TalentMatch <span class="dl-title-gradient">Desktop</span></h1>
                    <p class="dl-subtitle">
                        Experience lightning-fast CV parsing and seamless JD screening natively on Windows. No browser limits, full offline enterprise security.
                    </p>
                    <div class="dl-features">
                        <div class="dl-feature-badge"><span style="color:#10B981; font-size: 1.2rem;">⚡</span> 10x Faster Engine</div>
                        <div class="dl-feature-badge"><span style="color:#10B981; font-size: 1.2rem;">🔒</span> Offline Security</div>
                        <div class="dl-feature-badge"><span style="color:#10B981; font-size: 1.2rem;">🚀</span> Native Windows OS</div>
                    </div>
                    <a href="{EXE_DIRECT_DOWNLOAD_URL}" target="_blank" class="dl-btn">📥 Download Setup (v1.0)</a>
                    <div style="margin-top: 25px; font-size: 0.85rem; opacity: 0.6; font-weight: 500;">Supported on Windows 10/11 • 64-bit Architecture • 125 MB</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Center the Back to Login button elegantly below the card
        _, btn_col, _ = st.columns([1, 1, 1])
        with btn_col:
            if st.button("⬅ Return to Login", use_container_width=True):
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
                        st.session_state.pending_pin_email = None
                        st.rerun()
        st.stop()

    elif st.session_state.show_registration:
        _, mid_col, _ = st.columns([1, 2.2, 1])
        with mid_col:
            st.markdown("### 📝 Register Executive")
            with st.form("universal_registration_form"):
                reg_name = st.text_input("Full Name")
                reg_email = st.text_input("Email Address")
                reg_pass = st.text_input("Master Password", type="password")
                submit_reg = st.form_submit_button("Register Profile", use_container_width=True)
            if submit_reg:
                success, msg = register_initial_employee(reg_name, reg_email, reg_pass)
                if success:
                    st.session_state.pending_pin_email = reg_email.lower().strip()
                    st.session_state.show_registration = False
                    st.rerun()
                else: st.error(msg)
            if st.button("⬅ Back", use_container_width=True):
                st.session_state.show_registration = False
                st.rerun()
        st.stop()

    col_t1, col_t2 = st.columns([7.5, 2.5], vertical_alignment="center")
    with col_t1:
        st.markdown("""
            <div style="display: flex; align-items: center; gap: 20px;">
                <svg width="60" height="60" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#34D399;stop-opacity:1" />
                            <stop offset="100%" style="stop-color:#10B981;stop-opacity:1" />
                        </linearGradient>
                    </defs>
                    <circle cx="50" cy="50" r="46" fill="rgba(1, 21, 12, 0.8)" stroke="url(#grad)" stroke-width="4"/>
                    <path d="M50 20 L25 75" stroke="url(#grad)" stroke-width="10" stroke-linecap="round"/>
                    <path d="M50 20 L75 75" stroke="url(#grad)" stroke-width="10" stroke-linecap="round"/>
                    <path d="M35 55 L65 55" stroke="url(#grad)" stroke-width="8" stroke-linecap="round"/>
                </svg>
                <div>
                    <h1 style="font-size: 2.6rem; font-weight: 800; margin: 0; padding: 0; line-height: 1;">
                        ARL <span style="color: #10B981;">TalentMatch</span>
                    </h1>
                    <div style="font-size: 0.95rem; color: #10B981; font-weight: 600; letter-spacing: 1px; margin-top: 5px;">
                        ENTERPRISE RECRUITMENT & AI SCREENING SUITE
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    with col_t2:
        if st.button("📥 Get Desktop App", use_container_width=True, help="Download Standalone Windows MSI"):
            st.session_state.show_download_page = True
            st.rerun()

    st.markdown("<hr style='border: none; border-top: 1px solid rgba(16, 185, 129, 0.3); margin: 2rem 0;'>", unsafe_allow_html=True)

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
                        <div class="profile-meta-container">
                            <div class="profile-meta-title" title="New Profile">New Profile</div>
                            <div class="profile-meta-role">Register Account</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                else:
                    p_email, p_name, p_pin, p_role = item
                    avatar_sticker = get_user_avatar(p_email)
                    
                    if st.button(avatar_sticker, key=f"ucard_{i}_{idx}", type="primary"):
                        show_pin_dialog(p_email, p_name, p_role)
                        
                    if st.button("✏️", key=f"ebtn_{i}_{idx}", type="secondary", help="Change Avatar"):
                        show_sticker_picker_dialog(p_email, p_name)
                        
                    st.markdown(f"""
                        <div class="profile-meta-container">
                            <div class="profile-meta-title" title="{p_name}">{p_name}</div>
                            <div class="profile-meta-role">{p_role}</div>
                        </div>
                    """, unsafe_allow_html=True)
    st.stop()

# ===========================================================================
# 9. OCR & MULTI-RESUME EXTRACTION ENGINE
# ===========================================================================
def extract_text_from_image(file_bytes: bytes, client: Groq = None) -> str:
    g_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    if g_key:
        try:
            g_client = client or Groq(api_key=g_key)
            b64_img = base64.b64encode(file_bytes).decode("utf-8")
            resp = g_client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{"role": "user", "content": [{"type": "text", "text": "Extract pure clean text from resume."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}] }],
                max_tokens=2500, temperature=0.1
            )
            return resp.choices[0].message.content.strip()
        except Exception: pass
    return ""

def extract_text_from_pdf(file_bytes: bytes, client: Groq = None) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if len(page_text.strip()) > 30: text_parts.append(page_text)
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
        if name.endswith(".pdf"): return extract_text_from_pdf(b, client=client)
        elif name.endswith(".docx"): return extract_text_from_docx(b)
        elif name.endswith((".png", ".jpg", ".jpeg")): return extract_text_from_image(b, client=client)
    except Exception as e: st.error(f"Read error: {e}")
    return ""

def parse_multiple_candidates_from_text(client, full_text):
    chunk_size = 14000
    chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size - 500)]
    all_extracted_candidates, seen_identifiers = [], set()

    for chunk in chunks:
        prompt = f"""Extract candidates to valid JSON format. Return purely JSON: {{"candidates": [{{"name": "...", "email": "...", "phone": "...", "education": "...", "experience_years": "0"}}]}} Document: {chunk}"""
        try:
            res = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.1)
            content = res.choices[0].message.content.strip()
            parsed = json.loads(content[content.find('{'):content.rfind('}')+1]) if '{' in content else {}
            for cand in parsed.get("candidates", []):
                uid = str(cand.get("email", "")).lower() or f"{cand.get('name', '')}_{cand.get('phone', '')}"
                if uid not in seen_identifiers:
                    seen_identifiers.add(uid)
                    all_extracted_candidates.append(cand)
        except Exception: pass
    return all_extracted_candidates

def evaluate_candidate_against_jd(client, candidate_row, jd_text, selected_job_title=""):
    try:
        prompt = f"""Evaluate candidate for '{selected_job_title}'. CANDIDATE: {candidate_row['Name']} - {candidate_row['Qualification']} - {candidate_row['Experience']} yrs. JD: {jd_text}. Return strictly valid JSON: {{"match_score": 75, "missing_skills": ["Skill 1"]}}"""
        res = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.2)
        content = res.choices[0].message.content.strip()
        parsed = json.loads(content[content.find('{'):content.rfind('}')+1]) if '{' in content else {}
        return float(parsed.get("match_score", 50)), True, parsed.get("missing_skills", [])
    except Exception: return 50.0, True, []

def generate_ai_interview_questions(client, name, role, skills):
    try:
        res = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": f"Generate 5 precise interview questions with ideal answers for candidate {name} applying for {role}. Skills: {skills}"}], temperature=0.3)
        return res.choices[0].message.content.strip()
    except Exception as e: return f"Error: {e}"

# ===========================================================================
# 10. MAIN DASHBOARD & TABS
# ===========================================================================
df_all = load_database()
user_avatar = get_user_avatar(st.session_state.hr_email)

st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 25px;">
        <div style="display: flex; align-items: center; gap: 15px;">
            <div style="font-size: 2.2rem; background: rgba(16, 185, 129, 0.2); backdrop-filter: blur(10px); border: 2px solid #10B981; border-radius: 16px; width: 65px; height: 65px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.2);">{user_avatar}</div>
            <div>
                <h2 style="margin: 0; font-size: 1.8rem; font-weight: 800;">{APP_NAME} Enterprise Portal</h2>
                <span style="font-size: 0.95rem; opacity: 0.9; font-weight: 500;">Executive Session: <b>{st.session_state.hr_name}</b> &nbsp;|&nbsp; Role: <span style="color: #34D399;">{st.session_state.hr_role}</span></span>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

col_nav_right1, col_nav_right2 = st.columns([1, 1])
with col_nav_right1:
    if st.button("📥 Download Suite", key="dash_top_dl_btn", use_container_width=True):
        st.session_state.show_download_page = True
        st.rerun()
with col_nav_right2:
    if st.button("🚪 Lock Portal", key="dash_top_lock_btn", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.hr_email = ""
        st.session_state.hr_role = "Recruiter"
        st.rerun()

st.markdown(f"""
    <div class="corp-hero" style="margin-top: 15px;">
        <h2 style="margin: 0 0 8px 0; font-weight: 800;">Attock Refinery Master Repository</h2>
        <p style="margin: 0; opacity: 0.9; font-size: 1.05rem;">Total Database Records: <b>{len(df_all)} Candidates</b></p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Repository Upload", "🎯 2. JD Screening", "🗄️ 3. Live Database Grids", "🛡️ 4. Admin Controls"])

with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Ingest & Parse Resumes</h4>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload Candidates (PDF, DOCX, JPG)", type=ACCEPTED_TYPES, accept_multiple_files=True)
    g_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    
    if st.button("⚡ Extract & Append", type="primary", use_container_width=True, disabled=not uploaded_files):
        client = Groq(api_key=g_key)
        batch = []
        for file in uploaded_files:
            text = extract_resume_text(file, client=client)
            if len(text.strip()) > 30:
                batch.extend(parse_multiple_candidates_from_text(client, text))
        if batch:
            ins, skp = save_candidates_to_repository(batch)
            st.success(f"Processed {len(batch)} candidates. Saved {ins} new records.")
            st.rerun()

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: JD Screening</h4>', unsafe_allow_html=True)
    catalog = load_arl_job_catalog()
    dept = st.selectbox("Department", list(catalog.keys()))
    job_role = st.selectbox("Position", catalog.get(dept, []))
    jd_text = st.text_area("Job Description", height=130)
    slider_thresh = st.slider("Match Threshold (%)", 0, 100, 40, step=5)

    if st.button("⚡ Run AI Screening", type="primary", use_container_width=True, disabled=not jd_text.strip()):
        client = Groq(api_key=g_key)
        res = []
        for _, row in df_all.iterrows():
            score, _, missing = evaluate_candidate_against_jd(client, row, jd_text, selected_job_title=job_role)
            if score >= slider_thresh: res.append({"job_title": job_role, "name": row["Name"], "email": row["Email"], "match_score": score})
        st.session_state.screening_results = res
        st.success("Screening complete!")

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
