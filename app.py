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
GROQ_MODEL = "openai/gpt-oss-120b"
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
            # Requires matching a condition to delete rows in Supabase
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
# 5. CSS (SEAMLESS GLASSMORPHISM & PENCIL OVERLAP FIX)
# ===========================================================================
ADAPTIVE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

/* --- MAIN BACKGROUND (Deep Bright Green Radial Gradient) --- */
html, body, [class*="css"], .stApp { 
    font-family: 'Plus Jakarta Sans', sans-serif !important; 
    color: #E2E8F0 !important;
}
.stApp {
    background: radial-gradient(circle at top right, #055030 0%, #01150c 100%) !important;
    background-attachment: fixed !important;
}
.stApp > header { background-color: transparent !important; }
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }

/* --- 1. PERFECTLY ALIGNED PROFILE CARDS --- */
div[data-testid="stColumn"]:has(.profile-card-marker) {
    position: relative !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: flex-start !important;
    padding-top: 15px !important;
}

/* THE MAIN AVATAR CARD */
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] {
    width: 165px !important;
    height: 165px !important;
    min-width: 165px !important;
    max-width: 165px !important;
    min-height: 165px !important;
    max-height: 165px !important;
    border-radius: 26px !important;
    background: rgba(6, 68, 41, 0.6) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    border: 2px solid rgba(16, 185, 129, 0.6) !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4) !important;
    padding: 0 !important;
    margin: 0 auto !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    z-index: 1 !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"] p {
    font-size: 5rem !important;
    line-height: 1 !important;
    margin: 0 !important;
    transition: transform 0.3s ease !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="primary"]:hover {
    transform: translateY(-6px) !important;
    border-color: #10B981 !important;
    box-shadow: 0 0 25px rgba(16, 185, 129, 0.7), inset 0 0 15px rgba(16, 185, 129, 0.3) !important;
}

/* --- THE EDIT PENCIL BADGE (Overlap Fix) --- */
div[data-testid="stColumn"]:has(.profile-card-marker) div[data-testid="element-container"]:has(button[kind="secondary"]) {
    position: absolute !important;
    top: 20px !important;
    right: 50% !important;
    margin-right: -75px !important;
    z-index: 10 !important;
    width: auto !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"] {
    width: 34px !important;
    height: 34px !important;
    min-width: 34px !important;
    min-height: 34px !important;
    border-radius: 50% !important;
    background: rgba(16, 185, 129, 0.85) !important; 
    border: 2px solid #01150c !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
    padding: 0 !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"] p {
    font-size: 14px !important;
    margin: 0 !important;
}
div[data-testid="stColumn"]:has(.profile-card-marker) button[kind="secondary"]:hover {
    background: #10B981 !important;
    transform: scale(1.15) !important;
}

/* TEXT ALIGNMENT */
.profile-meta-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    height: 60px;
    margin-top: 15px; 
    width: 100%;
    max-width: 170px;
}
.profile-meta-title { font-size: 1.15rem; font-weight: 700; color: #FFFFFF !important; line-height: 1.2; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; }
.profile-meta-role { font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; color: #10B981 !important; text-transform: uppercase; letter-spacing: 0.6px; margin-top: 4px; text-align: center; }


/* --- 2. THE P.I.N MODAL & PURE GLASSMORPHISM --- */

/* 1. Blur the entire background screen when modal opens */
div[data-testid="stModal"] {
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
    background: rgba(1, 21, 12, 0.5) !important; /* Dark overlay */
}
/* Disable streamlit default modal background tint */
div[data-testid="stModal"] > div:first-child { 
    background: transparent !important; 
}

/* 2. Position the Modal exactly at center */
div[data-testid="stModal"], div[data-testid="stDialog"], div[role="dialog"] {
    top: 50% !important;
    transform: translateY(-50%) !important;
    height: auto !important;
    bottom: auto !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

/* 3. The Modal Body (No White Shadow, Pure Glass) */
div[role="dialog"] {
    background: rgba(4, 45, 26, 0.5) !important; /* Deep Green Glass */
    backdrop-filter: blur(25px) !important;
    -webkit-backdrop-filter: blur(25px) !important;
    border: 1px solid rgba(16, 185, 129, 0.4) !important;
    border-radius: 20px !important;
    box-shadow: none !important; /* <--- WHITE SHADOW COMPLETELY REMOVED */
    padding: 2.5rem 2rem !important;
    width: 340px !important;
}
/* Hide default cross/header */
div[role="dialog"] > div:first-child > div:first-child { display: none !important; }

/* The P.I.N Title */
.pin-modal-title {
    text-align: center;
    font-size: 1.8rem;
    font-weight: 800;
    color: #10B981;
    letter-spacing: 8px;
    margin-bottom: 25px;
    margin-top: -10px;
    text-shadow: 0 0 15px rgba(16, 185, 129, 0.5);
}

/* --- THE SEAMLESS PIN ENTRY (NO TEXT BOX) --- */
/* Remove Streamlit's inner grey backgrounds & borders entirely */
.pin-input-container div[data-baseweb="base-input"],
.pin-input-container div[data-baseweb="input"] {
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Style just the typing text */
.pin-input-container input {
    text-align: center !important;
    font-size: 2.8rem !important;
    letter-spacing: 25px !important;
    background: transparent !important; /* No background */
    color: #10B981 !important;
    border: none !important; /* No bounding box */
    border-bottom: 2px solid rgba(16, 185, 129, 0.3) !important; /* Just a sleek underline */
    border-radius: 0 !important;
    padding: 10px 0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    transition: all 0.3s ease;
}
.pin-input-container input:focus { 
    border-bottom: 2px solid #34D399 !important; 
    box-shadow: none !important; 
}
.pin-input-container input::placeholder { 
    color: rgba(16, 185, 129, 0.25) !important; 
    letter-spacing: 25px !important; 
    transform: translateY(-5px); 
}

/* Hide the eye icon to keep the UI perfectly clean */
.pin-input-container svg, 
.pin-input-container [role="button"] {
    display: none !important;
}

/* Access Portal Button */
div[role="dialog"] button[kind="primaryFormSubmit"] {
    background: #10B981 !important;
    color: #01150c !important;
    font-weight: 800 !important;
    border-radius: 10px !important;
    border: none !important;
    margin-top: 25px !important;
    height: 48px !important;
    font-size: 1.05rem !important;
    transition: all 0.3s ease !important;
}
div[role="dialog"] button[kind="primaryFormSubmit"]:hover { 
    background: #059669 !important; 
    transform: scale(1.02); 
}

/* Sections/Cards Glassmorphism */
.corp-hero, .corp-card {
    background: rgba(4, 45, 26, 0.55) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border: 1px solid rgba(16, 185, 129, 0.35) !important;
    border-left: 5px solid #10B981 !important;
    border-radius: 14px;
    padding: 1.5rem 1.8rem;
    margin-bottom: 1.5rem;
    color: #FFFFFF !important;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3) !important;
}
.corp-card h4 { margin-top: 0; margin-bottom: 1rem; font-weight: 700; color: #34D399; }
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
# 7. DIALOGS (MINIMALIST PIN & BADGE)
# ===========================================================================
@st.dialog(" ")  
def show_pin_dialog(email, name, role):
    st.markdown("<div class='pin-modal-title'>P.I.N</div>", unsafe_allow_html=True)
    with st.form(f"modal_pin_form_{email}", clear_on_submit=True):
        st.markdown('<div class="pin-input-container">', unsafe_allow_html=True)
        # Added input with no label and placeholder for clean dots
        pin_val = st.text_input("Enter PIN", type="password", max_chars=4, placeholder="••••", label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
        
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
            st.error("❌ Invalid PIN.")

@st.dialog("🎨 Choose Executive Badge")
def show_sticker_picker_dialog(email, name):
    st.write(f"Select a corporate avatar badge for **{name}**:")
    cols = st.columns(4)
    for idx, badge in enumerate(AVAILABLE_BADGES):
        with cols[idx % 4]:
            if st.button(badge, key=f"stk_btn_{email}_{idx}", use_container_width=True):
                set_user_avatar(email, badge)
                st
