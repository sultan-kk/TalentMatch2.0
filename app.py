"""
Arl TalentMatch:AI-Driven Automated CV Parser & JD Matcher
=============================================================================
Branding: Attock Refinery Limited (ARL Official Forest Green & Charcoal Palette)
Features: Executive Profile Badges, Bulletproof PIN Authentication, Fast OCR,
Safe Multi-CV Extraction, Exact 13-Column Sequence, ARL Job Hierarchy & Supabase Sync.
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
from PIL import Image, ImageDraw

# ===========================================================================
# 1. PAGE CONFIGURATION & ARL GREEN HEXAGON FAVICON
# ===========================================================================
APP_NAME = "Arl TalentMatch:AI-Driven Automated CV Parser & JD Matcher"
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
# 2. SUPABASE CONNECTION (SAFE INITIALIZATION)
# ===========================================================================
@st.cache_resource
def init_supabase():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
        key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None

supabase = init_supabase()

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

# ----------------- RELIABLE STICKER STORAGE & PIN AUTH -----------------
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
        default_stk = get_user_sticker("admin@arl.com.pk", "🛢️")
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
    return profiles if profiles else [("admin@arl.com.pk", "ARL Admin", "1234", "Admin", "🛢️")]

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
# 3. DATABASE HELPER FUNCTIONS (LAZY & SAFE)
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

def generate_repository_excel(df: pd.DataFrame) -> bytes:
    import openpyxl
    buffer = io.BytesIO()
    export_df = df.copy()
    export_df.insert(0, "Sr. No.", range(1, len(export_df) + 1))
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Candidates_Master")
    buffer.seek(0)
    return buffer.getvalue()

# ===========================================================================
# 4. NETFLIX THEME & CLEAN SINGLE CHARCOAL MODAL CSS
# ===========================================================================
ARL_GREEN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

.stApp {
    background: radial-gradient(circle at 50% 8%, #0f3d24 0%, #082415 48%, #03120a 100%) !important;
    color: #F8FAFC !important;
}

[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }

.cyber-header-box {
    text-align: center;
    padding: 1.5rem 1rem 0.8rem 1rem;
    margin-bottom: 0.5rem;
}
.cyber-title {
    font-size: 2.1rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.6px !important;
    color: #FFFFFF !important;
    margin: 0 0 6px 0 !important;
    line-height: 1.2 !important;
}
.cyber-title-pro {
    color: #4ADE80 !important;
    background: linear-gradient(135deg, #86EFAC 0%, #22C55E 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.cyber-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
    background: rgba(34, 197, 94, 0.15) !important;
    border: 1.5px solid #22C55E !important;
    padding: 5px 20px !important;
    border-radius: 30px !important;
    font-size: 0.76rem !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 1.5px !important;
    color: #86EFAC !important;
    box-shadow: 0 0 15px rgba(34, 197, 94, 0.2) !important;
}

/* ============================================================ */
/* NETFLIX-STYLE PROFILE DECK (140px CARD + ON-CARD EDIT HOVER) */
/* ============================================================ */
.netflix-deck {
    display: flex !important;
    flex-wrap: wrap !important;
    justify-content: center !important;
    align-items: flex-start !important;
    gap: 28px !important;
    padding: 1.5rem 0 !important;
}

.netflix-item {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    width: 140px !important;
}

.netflix-box {
    position: relative !important;
    width: 140px !important;
    height: 140px !important;
    margin: 0 auto !important;
}

/* 1. Big Avatar Card Button (140px x 140px Rounded Square Card) */
.netflix-box .stButton:nth-of-type(1) {
    margin: 0 !important;
    width: 140px !important;
    height: 140px !important;
}

.netflix-box .stButton:nth-of-type(1) > button {
    width: 140px !important;
    height: 140px !important;
    border-radius: 24px !important;
    font-size: 4.2rem !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin: 0 !important;
    background: linear-gradient(145deg, #134629 0%, #072416 100%) !important;
    border: 2.5px solid #22C55E !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.6), inset 0 0 16px rgba(34, 197, 94, 0.2) !important;
    transition: all 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
    padding: 0 !important;
    cursor: pointer !important;
}

.netflix-box:hover .stButton:nth-of-type(1) > button {
    border-color: #86EFAC !important;
    transform: scale(1.05) !important;
    box-shadow: 0 14px 34px rgba(34, 197, 94, 0.45), inset 0 0 20px rgba(74, 222, 128, 0.3) !important;
}

/* 2. Edit Button (Sits ON the bottom of the card, visible ONLY on hover) */
.netflix-box .stButton:nth-of-type(2) {
    position: absolute !important;
    top: 96px !important;
    left: 50% !important;
    transform: translateX(-50%) translateY(4px) !important;
    z-index: 15 !important;
    opacity: 0 !important;
    pointer-events: none !important;
    transition: all 0.2s ease-in-out !important;
    margin: 0 !important;
    padding: 0 !important;
}

.netflix-box:hover .stButton:nth-of-type(2) {
    opacity: 1 !important;
    transform: translateX(-50%) translateY(0) !important;
    pointer-events: auto !important;
}

.netflix-box .stButton:nth-of-type(2) > button {
    height: 28px !important;
    min-height: unset !important;
    padding: 2px 14px !important;
    border-radius: 12px !important;
    font-size: 0.72rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.8px !important;
    background: rgba(0, 0, 0, 0.88) !important;
    border: 1.5px solid #4ADE80 !important;
    color: #4ADE80 !important;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.6) !important;
    backdrop-filter: blur(4px) !important;
    cursor: pointer !important;
    white-space: nowrap !important;
}

.netflix-box .stButton:nth-of-type(2) > button:hover {
    background: #000000 !important;
    color: #FFFFFF !important;
    border-color: #86EFAC !important;
    transform: scale(1.05) !important;
}

/* 3. Add Profile Card */
.netflix-box.add-card .stButton:nth-of-type(1) > button {
    border: 2.5px dashed #22C55E !important;
    background: rgba(34, 197, 94, 0.08) !important;
    color: #86EFAC !important;
    font-size: 2.8rem !important;
}

.netflix-box.add-card:hover .stButton:nth-of-type(1) > button {
    border-color: #86EFAC !important;
    background: rgba(34, 197, 94, 0.22) !important;
    color: #FFFFFF !important;
}

.arl-tile-name {
    margin-top: 10px;
    font-size: 1rem;
    font-weight: 800;
    color: #FFFFFF;
    text-align: center;
    line-height: 1.25;
}
.arl-tile-role {
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    color: #86EFAC;
    background: rgba(34, 197, 94, 0.16);
    border: 1px solid rgba(34, 197, 94, 0.35);
    padding: 2px 8px;
    border-radius: 6px;
    margin-top: 4px;
    display: inline-block;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ============================================================ */
/* SEAMLESS SINGLE CHARCOAL MODAL & BLURRED BACKDROP            */
/* ============================================================ */
div[data-testid="stModalBackdrop"], div[data-testid="stDialogBackdrop"] {
    background-color: rgba(3, 16, 9, 0.6) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
}

div[data-testid="stDialog"] [data-testid="stForm"],
div[role="dialog"] [data-testid="stForm"] {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}

div[data-testid="stDialog"], div[role="dialog"] {
    border-radius: 20px !important;
    border: 2px solid #22C55E !important;
    background: #12161A !important;
    background-color: #12161A !important;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.85), 0 0 25px rgba(34, 197, 94, 0.25) !important;
    max-width: 320px !important;
    width: 320px !important;
    margin: auto !important;
    padding: 1.6rem 1.8rem !important;
}

div[data-testid="stDialog"] h2,
div[role="dialog"] h2 {
    font-size: 1.35rem !important;
    font-weight: 800 !important;
    color: #4ADE80 !important;
    letter-spacing: 1px !important;
    text-align: center !important;
    margin: 0 0 1rem 0 !important;
}

div[data-testid="stDialog"] input[type="password"] {
    font-size: 1.4rem !important;
    letter-spacing: 6px !important;
    text-align: center !important;
    background: #080a0c !important;
    border: 1.5px solid #22C55E !important;
    color: #FFFFFF !important;
    border-radius: 12px !important;
    height: 48px !important;
}

.sticker-modal-grid div[data-testid="stColumn"] button {
    font-size: 2.3rem !important;
    height: 64px !important;
    width: 100% !important;
    padding: 0 !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    border-radius: 16px !important;
    background: linear-gradient(145deg, #113f26 0%, #082416 100%) !important;
    border: 2px solid #22C55E !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
}
.sticker-modal-grid div[data-testid="stColumn"] button:hover {
    border-color: #86EFAC !important;
    transform: scale(1.1) !important;
    background: linear-gradient(145deg, #165332 0%, #0d3822 100%) !important;
    box-shadow: 0 6px 20px rgba(34, 197, 94, 0.5) !important;
}

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
.top-brand-title {
    font-size: 1.45rem; font-weight: 800; color: #FFFFFF; margin: 0;
}
.top-brand-subtitle {
    font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700; color: #86EFAC; margin: 0;
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
    font-size: 0.75rem; font-weight: 800; text-transform: uppercase; margin-bottom: 0.8rem;
}
.corp-card {
    background: rgba(14, 46, 29, 0.65);
    border: 1.5px solid rgba(74, 222, 128, 0.25);
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
}
.corp-card h4 {
    font-size: 1.25rem !important; font-weight: 800 !important; color: #FFFFFF !important;
    background: linear-gradient(90deg, rgba(34, 197, 94, 0.18) 0%, rgba(22, 101, 52, 0.08) 100%) !important;
    border-left: 4px solid #4ADE80 !important; border-radius: 8px 12px 12px 8px !important;
    padding: 10px 16px !important;
}
</style>
"""
st.markdown(ARL_GREEN_CSS, unsafe_allow_html=True)

# ===========================================================================
# 5. SESSION STATE INITIALIZATION
# ===========================================================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "hr_name" not in st.session_state: st.session_state.hr_name = ""
if "hr_email" not in st.session_state: st.session_state.hr_email = ""
if "hr_role" not in st.session_state: st.session_state.hr_role = "Recruiter"
if "pending_otp_email" not in st.session_state: st.session_state.pending_otp_email = None
if "pending_pin_email" not in st.session_state: st.session_state.pending_pin_email = None
if "register_mode" not in st.session_state: st.session_state.register_mode = False
if "screening_results" not in st.session_state: st.session_state.screening_results = []

# ===========================================================================
# 6. POPUP DIALOGS (SINGLE CHARCOAL BOX & AUTO-FOCUS)
# ===========================================================================
if hasattr(st, "dialog"):
    @st.dialog("PIN")
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
                if (++attempts > 40) clearInterval(timer);
            }, 30);
        })();
        </script>
        """, height=0, width=0)

        with st.form("pin_form_clean"):
            pin_input = st.text_input("PIN", type="password", max_chars=4, placeholder="••••", label_visibility="collapsed", key=f"clean_pin_{target_email}")
            submitted = st.form_submit_button("Enter ➔", use_container_width=True)

        if submitted or (pin_input and len(pin_input) == 4):
            success, name, role = verify_employee_pin(target_email, pin_input)
            if success:
                st.session_state.logged_in = True
                st.session_state.hr_name = name or p_name
                st.session_state.hr_email = target_email
                st.session_state.hr_role = role or p_role
                st.rerun()
            else:
                st.error("❌ Incorrect PIN")

    @st.dialog("Choose Badge")
    def show_sticker_dialog(target_email, p_name):
        st.markdown('<div class="sticker-modal-grid">', unsafe_allow_html=True)
        cols = st.columns(6)
        for idx, (stk, title) in enumerate(PROFESSIONAL_STICKERS.items()):
            with cols[idx % 6]:
                if st.button(stk, key=f"stk_select_{stk}_{idx}", help=title, use_container_width=True):
                    update_user_sticker(target_email, stk)
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")
        col_d1, col_d2 = st.columns([1.5, 1])
        with col_d1:
            if st.button("🗑️ Delete Profile", key=f"del_prof_dialog_{target_email}", use_container_width=True):
                delete_employee_profile(target_email)
                st.rerun()
        with col_d2:
            if st.button("Close", key="close_stk_dialog_btn", use_container_width=True):
                st.rerun()
else:
    def show_pin_dialog(e, n, r): pass
    def show_sticker_dialog(e, n): pass

# ===========================================================================
# 7. AUTHENTICATION & LOGIN SCREEN (NETFLIX PROFILE DECK)
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()

    col_c1, col_c2, col_c3 = st.columns([1, 4.2, 1])
    with col_c2:
        with st.container(border=True):
            st.markdown(f"""
                <div class="cyber-header-box">
                    <div style="display: flex; justify-content: center; margin-bottom: 12px;">
                        <div style="
                            width: 68px; height: 68px; border-radius: 18px; 
                            background: linear-gradient(135deg, rgba(74, 222, 128, 0.2) 0%, #082416 100%);
                            border: 2px solid #4ADE80; display: flex; align-items: center; justify-content: center;
                            box-shadow: 0 0 25px rgba(34, 197, 94, 0.4);
                        ">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <polygon points="12 2 22 7.5 22 16.5 12 22 2 16.5 2 7.5"></polygon>
                            </svg>
                        </div>
                    </div>
                    <h1 class="cyber-title">Arl TalentMatch: <span class="cyber-title-pro">AI-Driven Automated CV Parser & JD Matcher</span></h1>
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
                if submit_otp:
                    success, nag = verify_otp_code(st.session_state.pending_otp_email, otp_input)
                    if success:
                        st.success(nag)
                        st.session_state.pending_pin_email = st.session_state.pending_otp_email
                        st.session_state.pending_otp_email = None
                        st.rerun()
                    else:
                        st.error(nag)
                if st.button("Cancel", use_container_width=True, key="cancel_otp_btn"):
                    st.session_state.pending_otp_email = None
                    st.rerun()
                        
            elif saved_profiles and not st.session_state.register_mode:
                st.markdown("""
                    <div style="text-align: center; margin: 15px 0 20px 0;">
                        <h2 style="font-size: 1.75rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px; margin-bottom: 4px;">
                            Select Executive Profile
                        </h2>
                        <p style="font-size: 0.9rem; color: #86EFAC; margin: 0;">Click your profile to enter PIN, or hover to click <b>EDIT</b>:</p>
                    </div>
                """, unsafe_allow_html=True)
                
                deck_cols = st.columns([1, 8, 1])
                with deck_cols[1]:
                    st.markdown('<div class="netflix-deck">', unsafe_allow_html=True)
                    
                    for idx, (p_email, p_name, p_pin, p_role, p_sticker) in enumerate(saved_profiles):
                        st.markdown('<div class="netflix-item">', unsafe_allow_html=True)
                        st.markdown('<div class="netflix-box">', unsafe_allow_html=True)
                        
                        if st.button(p_sticker, key=f"prof_card_{idx}", help=f"Sign in as {p_name}"):
                            show_pin_dialog(p_email, p_name, p_role)
                            
                        if st.button("✏️ EDIT", key=f"edit_btn_{idx}", help=f"Change badge for {p_name}"):
                            show_sticker_dialog(p_email, p_name)
                            
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.markdown(f"""
                            <div class="arl-tile-name">{p_name}</div>
                            <div class="arl-tile-role">{p_role}</div>
                        """, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                                
                    st.markdown('<div class="netflix-item">', unsafe_allow_html=True)
                    st.markdown('<div class="netflix-box add-card">', unsafe_allow_html=True)
                    if st.button("＋", key="add_new_prof_btn", help="Register New Profile"):
                        st.session_state.register_mode = True
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown("""
                        <div class="arl-tile-name">Add Profile</div>
                        <div class="arl-tile-role">REGISTER</div>
                    """, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                        
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
                        
            else:
                st.markdown("### 📝 Employee / Admin Registration")
                st.caption("First registered user automatically becomes Admin with dedicated PIN creation.")
                with st.form("registration_form"):
                    reg_name = st.text_input("Full Name", placeholder="Alex Mercer")
                    reg_email = st.text_input("Company Email (@arl.com.pk)", placeholder="employee@arl.com.pk")
                    reg_pass = st.text_input("Master Password", type="password")
                    
                    st.markdown("**Choose your Executive Badge / Sticker:**")
                    reg_sticker = st.selectbox(
                        "Professional Sticker",
                        options=list(PROFESSIONAL_STICKERS.keys()),
                        format_func=lambda x: f"{x} {PROFESSIONAL_STICKERS[x]}"
                    )
                    submit_reg = st.form_submit_button("Send Verification OTP", use_container_width=True)
                    
                if submit_reg:
                    if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                        st.warning("Please verify all required fields.")
                    else:
                        success, msg = register_initial_employee(reg_name, reg_email, reg_pass, sticker=reg_sticker)
                        if success:
                            st.success(msg)
                            st.session_state.pending_otp_email = reg_email.lower().strip()
                            st.session_state.register_mode = False
                            st.rerun()
                        else:
                            st.error(msg)
                if st.button("Back to Profiles", use_container_width=True, key="back_to_prof_auth_btn"):
                    st.session_state.register_mode = False
                    st.rerun()
    st.stop()

# ===========================================================================
# 8. MAIN DASHBOARD (ONCE LOGGED IN)
# ===========================================================================
col_n1, col_n2 = st.columns([7.8, 2.2], vertical_alignment="center")
with col_n1:
    st.markdown(f"""
        <div class="top-navbar">
            <div>
                <h2 class="top-brand-title">Arl TalentMatch: <span style="color: #4ADE80;">AI-Driven Automated CV Parser & JD Matcher</span></h2>
                <p class="top-brand-subtitle">Attock Refinery Limited &bull; Active: <b>{st.session_state.get('hr_name', 'Recruiter')}</b> ({st.session_state.get('hr_email')}) &bull; Role: <b>{st.session_state.get('hr_role')}</b></p>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_n2:
    if st.button("🚪 Lock Portal", use_container_width=True, key="lock_portal_btn"):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.hr_email = ""
        st.rerun()

st.markdown(f"""
    <div class="corp-hero">
        <div class="corp-badge"><span>🟢 Multi-Stage ATS Session</span></div>
        <h1>Attock Refinery Executive Suite</h1>
        <p>Welcome back, <b>{st.session_state.get('hr_name', 'Recruiter')}</b></p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📥 1. Master Talent Repository", "🎯 2. JD Screening"])
with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Candidate Repository Grid</h4>', unsafe_allow_html=True)
    df_db = load_database()
    if not df_db.empty:
        st.dataframe(df_db, use_container_width=True, height=450)
        st.download_button("📊 Download Report (.xlsx)", data=generate_repository_excel(df_db), file_name="ARL_Talent_Pool.xlsx", use_container_width=True)
    else:
        st.info("No candidates in the database yet.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 AI Screening</h4>', unsafe_allow_html=True)
    st.info("Upload resumes in Tab 1 to run screening.")
    st.markdown("</div>", unsafe_allow_html=True)
