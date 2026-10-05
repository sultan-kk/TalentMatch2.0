"""
ARL TalentMatch — Official Corporate Edition (Full-Proof Enterprise Suite)
=============================================================================
Branding: Attock Refinery Limited (ARL Forest Green & Adaptive Theme Palette)
Features: Stunning In-App Download Suite & FAQs, Netflix Cards, Supabase Live Pipeline, 
Status Updater, Tab 2 Clear View & Database Grid Cleaner.
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
EXE_DIRECT_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/ARL-HireMatrix-Pro_1.0.0_x64_en-US.msi"

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
    avatars = st.session_state.get("profile_avatars", {})
    return avatars.get(email.lower().strip(), "👑")

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
            "pin": None, "role": role, "is_verified": 0, "otp": otp
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
# 4. DATABASE & REPOSITORY STORAGE (STRICT SEQUENCE)
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
            return pd.DataFrame(mapped)[expected_cols]
    except Exception:
        pass
    return pd.DataFrame(columns=expected_cols)

def save_candidates_to_repository(new_candidates):
    if not supabase: return 0, 0
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted, skipped = 0, 0
    for c in new_candidates:
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
            inserted += 1
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
        "Job Title", "Match Score (%)", "Pipeline Status",
        "Name", "Father Name", "Qualification", "CGPA", 
        "Passing Year", "Institute", "DOB", "Email", 
        "Phone Number", "Experience", "Latest Experience", "Reference",
        "Missing Skills", "Screened At"
    ]
    if not supabase: return pd.DataFrame(columns=expected_cols)
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
            return pd.DataFrame(mapped)[expected_cols]
    except Exception:
        pass
    return pd.DataFrame(columns=expected_cols)

def update_screened_candidate_status_db(email, job_title, new_status):
    if not supabase: return
    try:
        supabase.table("screened_candidates").update({"pipeline_status": new_status}).ilike("email", email).ilike("job_title", job_title).execute()
    except Exception:
        pass

def clear_candidate_database():
    if supabase: supabase.table("candidates").delete().neq("id", 0).execute()

def clear_screened_database():
    if supabase: supabase.table("screened_candidates").delete().neq("id", 0).execute()

# ===========================================================================
# 5. HIGH-END CORPORATE CSS
# ===========================================================================
ADAPTIVE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

.netflix-card-box {
    background: linear-gradient(145deg, #0F3622 0%, #081F13 100%);
    border: 3px solid #15803D;
    border-radius: 24px;
    padding: 1.8rem 1rem;
    text-align: center;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.6);
    transition: all 0.25s ease;
    margin-bottom: 8px;
    color: #FFFFFF !important;
}

.netflix-card-box:hover {
    transform: translateY(-6px) scale(1.02);
    border-color: #4ADE80;
    box-shadow: 0 16px 35px rgba(34, 197, 94, 0.45);
}

.top-navbar {
    background: linear-gradient(135deg, #0A2315 0%, #0F3622 100%);
    border: 1.5px solid #166534;
    border-bottom: 2px solid #22C55E;
    border-radius: 16px;
    padding: 1.1rem 2rem;
    margin-bottom: 1.8rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: #FFFFFF !important;
}

.corp-hero {
    background: linear-gradient(135deg, rgba(22, 101, 52, 0.25) 0%, rgba(10, 35, 21, 0.9) 100%);
    border: 1.5px solid #166534;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    border-left: 6px solid #4ADE80;
}

.corp-card {
    background: var(--secondary-background-color, #0B2517);
    border: 1.5px solid rgba(34, 197, 94, 0.35);
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
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
    
    # Gorgeous Styled Top Download Banner
    col_b1, col_b2 = st.columns([7, 3], vertical_alignment="center")
    with col_b1:
        st.markdown("🚀 **ARL TalentMatch Desktop Suite** — Standalone Windows app available for offline execution.")
    with col_b2:
        if st.button("📥 View Download & FAQs", key="dl_btn_login_top", use_container_width=True):
            st.session_state.show_download_page = True
            st.rerun()

    # Check if user clicked Download Desktop App
    if st.session_state.show_download_page:
        st.markdown("---")
        st.markdown("""
            <div style="background: linear-gradient(135deg, #064E3B 0%, #022C22 100%); border: 2px solid #34D399; border-radius: 20px; padding: 2.8rem; margin-bottom: 2rem; text-align: center; box-shadow: 0 15px 40px rgba(5, 150, 105, 0.3);">
                <div style="font-size: 3.2rem; margin-bottom: 10px;">💻</div>
                <h1 style="color: #FFFFFF; font-size: 2.4rem; font-weight: 800; margin-bottom: 12px;">ARL TalentMatch Desktop Edition</h1>
                <p style="color: #A7F3D0; font-size: 1.15rem; max-width: 750px; margin: 0 auto 25px auto; line-height: 1.6;">
                    Run Attock Refinery's recruitment suite natively on your Windows PC for high-performance offline execution, native local OCR processing, and seamless multi-user collaboration.
                </p>
                <a href="https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/ARL-HireMatrix-Pro_1.0.0_x64_en-US.msi" target="_blank" style="background: #10B981; color: white; padding: 1rem 2.5rem; border-radius: 14px; font-weight: 800; font-size: 1.2rem; text-decoration: none; border: 2px solid #6EE7B7; box-shadow: 0 8px 25px rgba(16, 185, 129, 0.6); display: inline-block;">📥 Download Windows Installer (.msi)</a>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🛠️ Installation Instructions")
        st.markdown("""
        1. **Download Package:** Click the prominent green download button above to download the official `.msi` setup package.
        2. **Run Installer:** Double-click `ARL-HireMatrix-Pro_1.0.0_x64_en-US.msi` to launch the Windows setup wizard.
        3. **Security Prompt:** If Windows SmartScreen prompts a notification (due to custom corporate signing), click **More info** -> **Run anyway**.
        4. **Launch Suite:** Open ARL TalentMatch from your desktop shortcut or Windows start menu and sign in using your corporate credentials and PIN.
        """)

        st.markdown("### ❓ Frequently Asked Questions (FAQs)")
        with st.expander("Q1: Is my candidate data secure in the desktop version?"):
            st.write("Yes! The desktop application securely connects to your encrypted Supabase cloud database, ensuring your data remains fully synced and protected under corporate security protocols.")
        with st.expander("Q2: Do I need an internet connection to run the app?"):
            st.write("An internet connection is required for AI Groq extraction and cloud database synchronization. Local UI rendering and file caching work seamlessly offline.")
        with st.expander("Q3: Can multiple HR recruiters use the app simultaneously?"):
            st.write("Yes, multiple authorized recruiters can sign in concurrently with their unique executive profiles and 4-digit security PINs.")

        st.markdown("<br>", unsafe_allow_html=True)
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

    elif st.session_state.show_registration or not saved_profiles:
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
        st.stop()

    st.markdown(f"""
        <div style="text-align: center; padding: 2rem 1rem 1rem 1rem;">
            <h1 style="font-size: 3rem; font-weight: 800;">Who's Screening?</h1>
            <p style="color: #4ADE80; font-size: 1.05rem;">{APP_TAGLINE}</p>
        </div>
    """, unsafe_allow_html=True)

    card_cols = st.columns(max(len(saved_profiles), 1))
    for idx, (p_email, p_name, p_pin, p_role) in enumerate(saved_profiles):
        with card_cols[idx]:
            avatar_sticker = get_user_avatar(p_email)
            st.markdown(f"""
                <div class="netflix-card-box">
                    <div style="font-size: 3.5rem; margin-bottom: 8px;">{avatar_sticker}</div>
                    <div style="font-size: 1.15rem; font-weight: 800; margin-bottom: 2px;">{p_name}</div>
                    <div style="font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; color: #4ADE80; text-transform: uppercase;">{p_role}</div>
                </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns([2, 1])
            with c1:
                if st.button("🔐 Sign In", key=f"signin_{idx}_{p_email}", use_container_width=True):
                    show_pin_dialog(p_email, p_name, p_role)
            with c2:
                if st.button("✏️", key=f"badge_{idx}_{p_email}", use_container_width=True, help="Change Badge"):
                    show_sticker_picker_dialog(p_email, p_name)
    st.stop()

# ===========================================================================
# 9. OCR & EXTRACTION FUNCTIONS
# ===========================================================================
def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    import pytesseract
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if len(page_text.strip()) > 40:
                text_parts.append(page_text)
            else:
                try:
                    pil_img = page.to_image(resolution=150).original.convert("L")
                    t1 = pytesseract.image_to_string(pil_img)
                    if t1.strip(): text_parts.append(t1)
                except Exception:
                    pass
    return "\n".join(text_parts)

def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx
    document = docx.Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in document.paragraphs if p.text.strip()])

def extract_resume_text(uploaded_file):
    name = uploaded_file.name.lower()
    try:
        b = uploaded_file.read()
        if name.endswith("pdf"): return extract_text_from_pdf(b)
        elif name.endswith("docx"): return extract_text_from_docx(b)
    except Exception as e:
        st.error(f"Read error: {e}")
    return ""

def evaluate_candidate_against_jd(client, candidate_row, jd_text, selected_job_title=""):
    try:
        summary = f"Name: {candidate_row['Name']}, Edu: {candidate_row['Qualification']}, Inst: {candidate_row['Institute']}, Exp: {candidate_row['Experience']}, Latest: {candidate_row['Latest Experience']}"
        prompt = f"""Evaluate CANDIDATE against ARL position '{selected_job_title}' and JD.
Provide match_score (0-100), is_relevant (true), and missing_skills list.
CANDIDATE: {summary}
JD: {jd_text}
Return ONLY valid JSON: {{"match_score": 50, "is_relevant": true, "missing_skills": []}}
"""
        res = client.chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, temperature=0.2
        )
        parsed = json.loads(res.choices[0].message.content.strip())
        return float(parsed.get("match_score", 50)), True, parsed.get("missing_skills", [])
    except Exception:
        return 50.0, True, []

def generate_ai_interview_questions(client, name, role, skills):
    try:
        prompt = f"Generate 5 precise interview questions with ideal answers for candidate {name} applying for ARL position {role} with skills: {skills}. Bullet points."
        res = client.chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.3
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate questions: {e}"

# ===========================================================================
# 10. MAIN DASHBOARD & TABS
# ===========================================================================
df_all = load_database()
user_avatar = get_user_avatar(st.session_state.hr_email)

# Top Styled Banner on Main Dashboard
col_d1, col_d2 = st.columns([7, 3], vertical_alignment="center")
with col_d1:
    st.markdown("🚀 **ARL TalentMatch Desktop Suite** — Standalone Windows app available for offline execution.")
with col_d2:
    if st.button("📥 View Download & FAQs", key="dl_btn_dash_top", use_container_width=True):
        st.session_state.show_download_page = True
        st.rerun()

if st.session_state.show_download_page:
    st.markdown("---")
    st.markdown("""
        <div style="background: linear-gradient(135deg, #064E3B 0%, #022C22 100%); border: 2px solid #34D399; border-radius: 20px; padding: 2.8rem; margin-bottom: 2rem; text-align: center; box-shadow: 0 15px 40px rgba(5, 150, 105, 0.3);">
            <div style="font-size: 3.2rem; margin-bottom: 10px;">💻</div>
            <h1 style="color: #FFFFFF; font-size: 2.4rem; font-weight: 800; margin-bottom: 12px;">ARL TalentMatch Desktop Edition</h1>
            <p style="color: #A7F3D0; font-size: 1.15rem; max-width: 750px; margin: 0 auto 25px auto; line-height: 1.6;">
                Run Attock Refinery's recruitment suite natively on your Windows PC for high-performance offline execution, native local OCR processing, and seamless multi-user collaboration.
            </p>
            <a href="https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/ARL-HireMatrix-Pro_1.0.0_x64_en-US.msi" target="_blank" style="background: #10B981; color: white; padding: 1rem 2.5rem; border-radius: 14px; font-weight: 800; font-size: 1.2rem; text-decoration: none; border: 2px solid #6EE7B7; box-shadow: 0 8px 25px rgba(16, 185, 129, 0.6); display: inline-block;">📥 Download Windows Installer (.msi)</a>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🛠️ Installation Instructions")
    st.markdown("""
    1. **Download Package:** Click the prominent green download button above to download the official `.msi` setup package.
    2. **Run Installer:** Double-click `ARL-HireMatrix-Pro_1.0.0_x64_en-US.msi` to launch the Windows setup wizard.
    3. **Security Prompt:** If Windows SmartScreen prompts a notification (due to custom corporate signing), click **More info** -> **Run anyway**.
    4. **Launch Suite:** Open ARL TalentMatch from your desktop shortcut or Windows start menu and sign in using your corporate credentials and PIN.
    """)

    st.markdown("### ❓ Frequently Asked Questions (FAQs)")
    with st.expander("Q1: Is my candidate data secure in the desktop version?"):
        st.write("Yes! The desktop application securely connects to your encrypted Supabase cloud database, ensuring your data remains fully synced and protected under corporate security protocols.")
    with st.expander("Q2: Do I need an internet connection to run the app?"):
        st.write("An internet connection is required for AI Groq extraction and cloud database synchronization. Local UI rendering and file caching work seamlessly offline.")
    with st.expander("Q3: Can multiple HR recruiters use the app simultaneously?"):
        st.write("Yes, multiple authorized recruiters can sign in concurrently with their unique executive profiles and 4-digit security PINs.")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⬅ Back to Dashboard", use_container_width=True):
        st.session_state.show_download_page = False
        st.rerun()
    st.stop()

col_n1, col_n2 = st.columns([8, 2], vertical_alignment="center")
with col_n1:
    st.markdown(f"""
        <div class="top-navbar">
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="font-size: 2.2rem; background: #0A2315; padding: 4px 10px; border-radius: 12px; border: 1.5px solid #4ADE80;">{user_avatar}</div>
                <div>
                    <h2 style="font-size: 1.55rem; font-weight: 800; margin: 0; color: #FFFFFF;">{APP_NAME} Pro</h2>
                    <p style="font-size: 0.75rem; text-transform: uppercase; color: #86EFAC; margin: 0;">Logged In: <b>{st.session_state.hr_name}</b> &bull; Role: <b>{st.session_state.hr_role}</b></p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_n2:
    if st.button("🚪 Lock Portal", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

st.markdown(f"""
    <div class="corp-hero">
        <h1 style="color: #FFFFFF; margin: 0 0 8px 0;">Attock Refinery Executive Suite</h1>
        <p style="color: #86EFAC; margin: 0;">Total Repository: <b>{len(df_all)} Candidates</b></p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Talent Repository (Upload)", "🎯 2. JD Screening & Matching", "🗄️ 3. Live Database Grids", "🛡️ 4. Admin Controls"])

with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Ingest & Parse Resumes</h4>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload Resumes (PDF, DOCX)", type=ACCEPTED_TYPES, accept_multiple_files=True)
    g_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    
    if st.button("⚡ Extract & Append to Supabase", type="primary", use_container_width=True, disabled=not uploaded_files):
        client = Groq(api_key=g_key)
        batch = []
        for file in uploaded_files:
            text = extract_resume_text(file)
            if text:
                prompt = f"""Extract JSON for candidate:
{{"candidates": [{{"name": "Name", "father_name": "Father", "education": "Degree", "cgpa": "3.5", "passing_year": "2024", "university_name": "Inst", "dob": "DOB", "email": "Email", "phone": "Phone", "experience_years": "2", "latest_experience": "Role", "reference": "Ref"}}]}}
TEXT: {text[:15000]}"""
                res = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
                parsed = json.loads(res.choices[0].message.content.strip())
                batch.extend(parsed.get("candidates", []))
        if batch:
            ins, skp = save_candidates_to_repository(batch)
            st.success(f"🎉 Processed: {ins} candidate(s) added!")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening</h4>', unsafe_allow_html=True)
    catalog = load_arl_job_catalog()
    dept = st.selectbox("Select Department", list(catalog.keys()))
    job_role = st.selectbox("Select Position", catalog.get(dept, []))
    jd_text = st.text_area("Job Requirements", height=130)
    slider_thresh = st.slider("Highlight Score Threshold (%)", 0, 100, 40, step=5)
    
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
        if not db_s.empty: display_results = db_s.to_dict(orient="records")

    if display_results:
        st.markdown("### 📋 Screening Results")
        
        # Clear Screening Results View Button in Tab 2
        if st.button("🗑️ Clear Screening Results View", type="secondary", key="clear_screening_view_btn"):
            st.session_state.screening_results = []
            st.success("Screening results view cleared!")
            st.rerun()

        for rank, cand in enumerate(display_results, 1):
            c_name = cand.get('Name') or cand.get('name', 'Unknown')
            c_score = cand.get('Match Score (%)') if 'Match Score (%)' in cand else cand.get('match_score', 0)
            c_email = cand.get('Email') or cand.get('email', '')
            c_job = cand.get('Job Title') or cand.get('job_title', job_role)
            
            with st.expander(f"#{rank} — {c_name} ({c_score}%)"):
                new_status = st.selectbox("Pipeline Status", ["Shortlisted", "Interviewing", "Offered", "Rejected", "Talent Pool"], index=0, key=f"status_{rank}_{c_email}")
                if st.button("Update Status", key=f"up_{rank}_{c_email}"):
                    update_screened_candidate_status_db(c_email, c_job, new_status)
                    st.success("Status updated!")

                if st.button("📧 Send Interview Call Email", key=f"email_{rank}_{c_email}"):
                    body = f"Dear {c_name},\n\nYou have been shortlisted for the position of {c_job} at Attock Refinery Limited (ARL).\n\nBest regards,\nHR Team ARL"
                    ok, msg = send_smtp_email(c_email, f"Interview Call - ARL TalentMatch ({c_job})", body)
                    if ok: st.success("Email dispatched!")
                    else: st.error(msg)

                if st.button("💡 Generate AI Interview Questions", key=f"q_{rank}_{c_email}"):
                    q_text = generate_ai_interview_questions(Groq(api_key=g_key), c_name, c_job, str(cand))
                    st.info(q_text)
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Real-Time Synchronized Supabase Grids</h4>', unsafe_allow_html=True)
    g1, g2 = st.tabs(["Screened Candidates", "Master Talent Pool"])
    with g1:
        s_df = load_screened_database()
        if not s_df.empty: 
            st.dataframe(s_df, use_container_width=True)
            if st.button("🗑️ Clear All Screened Records", type="secondary", key="clear_screened_btn"):
                clear_screened_database()
                st.success("All screened records have been cleared.")
                st.rerun()
        else: 
            st.info("No screened records found.")
    with g2:
        m_df = load_database()
        if not m_df.empty: 
            st.dataframe(m_df, use_container_width=True)
            if st.button("🗑️ Clear All Master Talent Pool", type="secondary", key="clear_pool_btn"):
                clear_candidate_database()
                st.success("Master talent pool cleared.")
                st.rerun()
        else: 
            st.info("Master talent pool is empty.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="corp-card"><h4>🛡️ Admin Controls</h4>', unsafe_allow_html=True)
    profiles = get_all_verified_profiles()
    for p_em, p_nm, p_p, p_r in profiles:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: st.write(f"👤 {p_nm} ({p_em})")
        with c2: st.write(f"Role: {p_r}")
        with c3:
            if st.button("Revoke", key=f"rev_{p_em}"):
                delete_employee_profile(p_em)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
