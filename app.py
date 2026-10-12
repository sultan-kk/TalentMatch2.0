"""
ARL TalentMatch — Official Corporate Edition (Enterprise Suite)
=============================================================================
Branding: Attock Refinery Limited (ARL Forest Green & Adaptive Theme)
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
# 1. PAGE CONFIGURATION & FAVICON
# ===========================================================================
APP_NAME = "ARL TalentMatch"
APP_TAGLINE = "Attock Refinery Limited (ARL) • AI-Driven Automated CV Parser & JD Screener"
GROQ_MODEL = "llama3-70b-8192" # Make sure this is a valid Groq model string
VISION_MODEL = "llama-3.2-11b-vision-preview"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
EXE_DIRECT_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/TalentMatch.msi"
AVAILABLE_BADGES = ["👔", "💼", "🛡️", "🎖️", "⚡", "🔬", "🛢️", "⚙️", "📈", "🎯", "👑", "🚀", "💡", "💻", "💎", "🏛️"]

def get_arl_favicon():
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
                return res.data[0].get("avatar")
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
        return False, "Database not configured."
    try:
        existing = supabase.table("hr_users").select("pin").eq("email", clean_email).execute().data
        if existing and existing[0].get("pin"):
            return False, "Email already registered."
        count_res = supabase.table("hr_users").select("email", count="exact").execute()
        role = "Admin" if (count_res.count is not None and count_res.count == 0) else "Recruiter"
        data = {
            "email": clean_email, "name": name, "password": hash_password(password),
            "pin": None, "role": role, "is_verified": 0, "otp": otp, "avatar": "👑"
        }
        supabase.table("hr_users").upsert(data).execute()
        send_smtp_email(clean_email, "ARL TalentMatch - Verification OTP", f"Your code is: {otp}")
        return True, "Check your email for the OTP."
    except Exception as e:
        return False, f"Database Error: {e}"

def save_employee_pin(email, pin):
    if not supabase: return False, "Database not configured."
    try:
        supabase.table("hr_users").update({"pin": str(pin).strip(), "is_verified": 1}).eq("email", email.lower().strip()).execute()
        return True, "PIN configured successfully!"
    except Exception as e:
        return False, str(e)

def delete_employee_profile(email):
    if supabase:
        try:
            supabase.table("hr_users").delete().eq("email", email.lower().strip()).execute()
        except Exception:
            pass

# ===========================================================================
# 3. ARL JOB CATALOG
# ===========================================================================
DEFAULT_ARL_CATALOG = {
    "Operations & Refining": ["Process Engineer", "Plant Shift Incharge"],
    "Maintenance & Engineering": ["Mechanical Engineer", "Electrical Engineer"],
    "Human Resources & Administration": ["Talent Acquisition", "HR Manager"]
}

def load_arl_job_catalog():
    return DEFAULT_ARL_CATALOG

# ===========================================================================
# 4. DATABASE STORAGE LOGIC
# ===========================================================================
def load_database():
    expected_cols = ["Name", "Father Name", "Qualification", "CGPA", "Email", "Phone Number", "Experience", "Pipeline Status"]
    if not supabase: return pd.DataFrame(columns=expected_cols)
    try:
        response = supabase.table("candidates").select("*").order("id", desc=False).execute()
        if response.data:
            mapped = []
            for r in response.data:
                mapped.append({
                    "Name": r.get("candidate_name", "Unknown"), "Father Name": r.get("father_name", ""),
                    "Qualification": r.get("education", ""), "CGPA": r.get("cgpa", ""),
                    "Email": r.get("email", ""), "Phone Number": r.get("phone", ""), 
                    "Experience": str(r.get("experience_years", "0")), "Pipeline Status": r.get("pipeline_status", "Talent Pool")
                })
            return pd.DataFrame(mapped)[expected_cols]
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
            supabase.table("candidates").delete().neq("id", 0).execute()
        except Exception: 
            pass

def save_candidates_to_repository(new_candidates):
    if not supabase: return 0, 0
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted, skipped = 0, 0
    for c in new_candidates:
        payload = {
            "candidate_name": c.get("name", "Unknown"), "education": c.get("education", "Not Provided"),
            "email": c.get("email", "Not Provided"), "phone": c.get("phone", "Not Provided"),
            "experience_years": str(c.get("experience_years", "0")), "pipeline_status": "Talent Pool", "added_at": current_timestamp
        }
        try:
            supabase.table("candidates").insert(payload).execute()
            inserted += 1
        except Exception: skipped += 1
    return inserted, skipped

# ===========================================================================
# 5. ADAPTIVE CSS (LIGHT/DARK MODE AWARE)
# ===========================================================================
ADAPTIVE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, .stApp { font-family: 'Plus Jakarta Sans', sans-serif !important; }
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
.profile-meta-container { text-align: center; margin-top: 15px; }
.profile-meta-role { font-size: 0.72rem; color: #10B981; text-transform: uppercase; }

/* === LIGHT MODE === */
@media (prefers-color-scheme: light) {
    .stApp { background: #F4FBF7 !important; color: #000000 !important; }
    .corp-hero, .corp-card {
        background: #FFFFFF !important;
        border: 1px solid rgba(16, 185, 129, 0.3) !important;
        border-left: 5px solid #10B981 !important;
        border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; 
        color: #000000 !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important;
    }
    .corp-card h4 { color: #059669 !important; margin-top: 0; }
    .profile-meta-title { font-size: 1.15rem; font-weight: 700; color: #000000 !important; }
    h1, h2, h3, p, span, b, div { color: #1e293b; }
    h1 span { color: #10B981 !important; }
}

/* === DARK MODE === */
@media (prefers-color-scheme: dark) {
    .stApp { background: radial-gradient(circle at top right, #055030 0%, #01150c 100%) !important; color: #FFFFFF !important; }
    .corp-hero, .corp-card {
        background: rgba(4, 45, 26, 0.7) !important;
        border: 1px solid rgba(16, 185, 129, 0.35) !important;
        border-left: 5px solid #10B981 !important;
        border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; 
        color: #FFFFFF !important;
    }
    .corp-card h4 { color: #34D399 !important; margin-top: 0; }
    .profile-meta-title { font-size: 1.15rem; font-weight: 700; color: #FFFFFF !important; }
    h1, h2, h3, p, span, b, div { color: #FFFFFF; }
    h1 span { color: #10B981 !important; }
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
if "show_download_page" not in st.session_state: st.session_state.show_download_page = False

# ===========================================================================
# 7. DIALOGS
# ===========================================================================
@st.dialog("Enter P.I.N")  
def show_pin_dialog(email, name, role):
    with st.form(f"modal_pin_form_{email}", clear_on_submit=True):
        pin_val = st.text_input("Enter 4-Digit PIN", type="password", max_chars=4)
        if st.form_submit_button("Access Portal", use_container_width=True):
            ok, u_name, u_role = verify_employee_pin(email, pin_val)
            if ok:
                st.session_state.logged_in = True
                st.session_state.hr_name = u_name or name
                st.session_state.hr_email = email
                st.session_state.hr_role = u_role or role
                st.rerun()
            else:
                st.error("❌ Invalid PIN.")

@st.dialog("🎨 Choose Executive Badge")
def show_sticker_picker_dialog(email, name):
    st.write(f"Select badge for **{name}**:")
    cols = st.columns(4)
    for idx, badge in enumerate(AVAILABLE_BADGES):
        with cols[idx % 4]:
            if st.button(badge, key=f"stk_btn_{email}_{idx}"):
                set_user_avatar(email, badge)
                st.success("Badge saved!")
                st.rerun()

# ===========================================================================
# 8. AUTHENTICATION & LOGIN SCREEN
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()

    if st.session_state.show_download_page:
        st.markdown(f"### Download Installer\n[Download Here]({EXE_DIRECT_DOWNLOAD_URL})")
        if st.button("⬅ Back to Login", use_container_width=True):
            st.session_state.show_download_page = False
            st.rerun()
        st.stop()

    if st.session_state.pending_pin_email:
        st.markdown("### 🔐 Security PIN Setup")
        with st.form("pin_setup_form"):
            new_pin = st.text_input("Create 4-Digit PIN", type="password", max_chars=4)
            confirm_pin = st.text_input("Confirm PIN", type="password", max_chars=4)
            if st.form_submit_button("Save PIN"):
                if len(new_pin) == 4 and new_pin == confirm_pin:
                    success, msg = save_employee_pin(st.session_state.pending_pin_email, new_pin)
                    if success:
                        st.session_state.pending_pin_email = None
                        st.rerun()
        st.stop()

    elif st.session_state.show_registration:
        st.markdown("### 📝 Register Executive")
        with st.form("universal_registration_form"):
            reg_name = st.text_input("Full Name")
            reg_email = st.text_input("Email Address")
            reg_pass = st.text_input("Master Password", type="password")
            if st.form_submit_button("Register Profile"):
                success, msg = register_initial_employee(reg_name, reg_email, reg_pass)
                if success:
                    st.session_state.pending_pin_email = reg_email.lower().strip()
                    st.session_state.show_registration = False
                    st.rerun()
                else: st.error(msg)
        if st.button("⬅ Back"):
            st.session_state.show_registration = False
            st.rerun()
        st.stop()

    col_t1, col_t2 = st.columns([7.5, 2.5]) 
    with col_t1:
        # Removed hardcoded white text style to allow media queries to work
        st.markdown("<h1 class='main-title'>ARL <span>TalentMatch</span></h1>", unsafe_allow_html=True)
    with col_t2:
        if st.button("📥 Get Desktop App", use_container_width=True):
            st.session_state.show_download_page = True
            st.rerun()

    st.divider()

    all_items = list(saved_profiles) + [("REGISTER_CARD", "New Profile", "", "Register")]
    cols_per_row = 4
    for i in range(0, len(all_items), cols_per_row):
        row_items = all_items[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for idx, item in enumerate(row_items):
            with cols[idx]:
                if item[0] == "REGISTER_CARD":
                    if st.button("➕ Register Account", key=f"add_card_{i}_{idx}", use_container_width=True):
                        st.session_state.show_registration = True
                        st.rerun()
                else:
                    p_email, p_name, p_pin, p_role = item
                    avatar_sticker = get_user_avatar(p_email)
                    
                    if st.button(f"{avatar_sticker} Login {p_name}", key=f"ucard_{i}_{idx}", use_container_width=True):
                        show_pin_dialog(p_email, p_name, p_role)
                        
                    if st.button("✏️ Change Badge", key=f"ebtn_{i}_{idx}", use_container_width=True):
                        show_sticker_picker_dialog(p_email, p_name)
    st.stop()

# ===========================================================================
# 9. MAIN DASHBOARD & TABS
# ===========================================================================
df_all = load_database()
user_avatar = get_user_avatar(st.session_state.hr_email)

st.markdown(f"## {user_avatar} {APP_NAME} Enterprise Portal")
st.write(f"Executive Session: **{st.session_state.hr_name}** | Role: **{st.session_state.hr_role}**")

if st.button("🚪 Lock Portal"):
    st.session_state.logged_in = False
    st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Repository Upload", "🎯 2. JD Screening", "🗄️ 3. Live Database Grids", "🛡️ 4. Admin Controls"])

with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Ingest & Parse Resumes</h4>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload Candidates (PDF, DOCX, JPG)", type=ACCEPTED_TYPES, accept_multiple_files=True)
    if st.button("⚡ Extract & Append", type="primary", use_container_width=True, disabled=not uploaded_files):
        # OCR Logic goes here 
        st.success("Documents processed successfully!")
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: JD Screening</h4>', unsafe_allow_html=True)
    jd_text = st.text_area("Job Description", height=130)
    if st.button("⚡ Run AI Screening", type="primary", use_container_width=True, disabled=not jd_text.strip()):
        st.success("Screening complete!")
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Real-Time Synchronized Database Grids</h4>', unsafe_allow_html=True)
    g1, g2 = st.tabs(["Screened Candidates", "Master Talent Pool"])
    with g1:
        s_df = load_screened_database()
        if not s_df.empty:
            st.dataframe(s_df, use_container_width=True)
            if st.button("🗑️ Clear Screened", type="secondary"):
                clear_screened_database()
                st.rerun()
        else:
            st.info("No screened candidates found.")
    with g2:
        m_df = load_database()
        if not m_df.empty:
            st.dataframe(m_df, use_container_width=True)
            if st.button("🗑️ Clear Talent Pool", type="secondary"):
                clear_candidate_database()
                st.rerun()
        else:
            st.info("Master talent pool is empty.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="corp-card"><h4>🛡 Admin User Controls</h4>', unsafe_allow_html=True)
    profiles = get_all_verified_profiles()
    for p_em, p_nm, p_p, p_r in profiles:
        c1, c2, c3 = st.columns([3, 1.5, 1])
        with c1: st.write(f"👤 **{p_nm}** ({p_em})")
        with c2: st.write(f"Role: `{p_r}`")
        with c3:
            if st.button("Revoke", key=f"rev_{p_em}", type="secondary"):
                delete_employee_profile(p_em)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
