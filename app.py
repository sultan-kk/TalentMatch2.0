"""
HireMatrix Pro — Enterprise Edition v10.33 (Complete Code with Styled Profile Box)
========================================================================
Features: Visually distinct Saved Profile box with custom background color and border, 
Dynamic Passing Score Threshold, Smart Duplicate Prevention, and Executive Excel Report.
"""

import io
import json
import os
import sqlite3
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

# ===========================================================================
# CONFIGURATION & AUTO-MIGRATION AUTH DB
# ===========================================================================
APP_NAME = "HireMatrix Pro"
APP_TAGLINE = "Autonomous HR Intelligence & Executive Recruitment Suite"
GROQ_MODEL = "openai/gpt-oss-120b"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
DB_FILE = "master_candidates.csv"
AUTH_DB_FILE = "hr_users.db"

MEEZAN_TITLE = "Muhammad Sultan Sheraz"
MEEZAN_IBAN = "PK24MEZN0098820105114718"
SADAPAY_NUMBER = "0325-8641257"

def init_auth_db():
    conn = sqlite3.connect(AUTH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hr_users (
            email TEXT PRIMARY KEY,
            name TEXT,
            password TEXT,
            pin TEXT,
            role TEXT DEFAULT 'Recruiter',
            is_pro INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            otp TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS license_keys (
            license_key TEXT PRIMARY KEY,
            email TEXT,
            is_used INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_requests (
            trx_id TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            status TEXT DEFAULT 'Pending'
        )
    """)
    cursor.execute("PRAGMA table_info(hr_users)")
    columns = [col[1] for col in cursor.fetchall()]
    if "pin" not in columns: cursor.execute("ALTER TABLE hr_users ADD COLUMN pin TEXT")
    if "role" not in columns: cursor.execute("ALTER TABLE hr_users ADD COLUMN role TEXT DEFAULT 'Recruiter'")
    if "is_pro" not in columns: cursor.execute("ALTER TABLE hr_users ADD COLUMN is_pro INTEGER DEFAULT 0")
    if "otp" not in columns: cursor.execute("ALTER TABLE hr_users ADD COLUMN otp TEXT")
    conn.commit()
    conn.close()

init_auth_db()

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
        msg['From'] = formataddr(("HireMatrix Pro Billing", sender_email))
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

def submit_payment_request(email, name, trx_id):
    clean_trx = trx_id.strip()
    if len(clean_trx) < 5:
        return False, "Please enter a valid Transaction ID."
    try:
        conn = sqlite3.connect(AUTH_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM payment_requests WHERE trx_id = ?", (clean_trx,))
        if cursor.fetchone():
            conn.close()
            return False, "This Transaction ID has already been submitted."
        
        cursor.execute("INSERT INTO payment_requests (trx_id, email, name, status) VALUES (?, ?, ?, 'Pending')", (clean_trx, email, name))
        conn.commit()
        conn.close()
        return True, "Payment request submitted! Admin will verify and approve your license key shortly."
    except Exception as e:
        return False, str(e)

def admin_approve_payment(trx_id, email):
    key = f"HMPRO-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
    try:
        conn = sqlite3.connect(AUTH_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE payment_requests SET status = 'Approved' WHERE trx_id = ?", (trx_id,))
        cursor.execute("INSERT OR REPLACE INTO license_keys (license_key, email, is_used) VALUES (?, ?, 0)", (key, email))
        cursor.execute("UPDATE hr_users SET is_pro = 1 WHERE email = ?", (email,))
        conn.commit()
        conn.close()
        
        body = f"""
        Hello,\n\n
        Your payment for HireMatrix Pro (6,999 PKR) has been verified and approved by Admin!\n\n
        Your Exclusive Pro License Key is: {key}\n\n
        Your account has been automatically upgraded to PRO Tier.\n\n
        Regards,\nTeam HireMatrix Pro Billing
        """
        send_smtp_email(email, "Your Approved HireMatrix Pro License Key", body)
        return True, "Payment approved & license dispatched!"
    except Exception as e:
        return False, str(e)

def get_all_verified_profiles():
    conn = sqlite3.connect(AUTH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email, name, pin, role, is_pro FROM hr_users WHERE is_verified = 1 AND pin IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    return rows

def register_initial_employee(name, email, password):
    clean_email = email.lower().strip()
    otp = str(random.randint(100000, 999999))
    try:
        conn = sqlite3.connect(AUTH_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT is_verified, pin FROM hr_users WHERE email = ?", (clean_email,))
        row = cursor.fetchone()
        
        if row and row[0] == 1 and row[1]:
            conn.close()
            return False, "This email is already registered and active. Please sign in."
        
        cursor.execute("SELECT COUNT(*) FROM hr_users")
        count = cursor.fetchone()[0]
        role = "Admin" if count == 0 else "Recruiter"
        is_pro_val = 1 if count == 0 else 0
        
        cursor.execute("""
            INSERT OR REPLACE INTO hr_users (email, name, password, pin, role, is_pro, is_verified, otp) 
            VALUES (?, ?, ?, NULL, ?, ?, 0, ?)
        """, (clean_email, name, hash_password(password), role, is_pro_val, otp))
        conn.commit()
        conn.close()
        
        success, msg = send_smtp_email(clean_email, "HireMatrix Pro - Verification OTP", f"Your verification code is: {otp}")
        if success:
            return True, "Registration initiated! Please check your email for the verification OTP."
        else:
            return False, msg
    except Exception as e:
        return False, f"Error: {e}"

def verify_otp_code(email, entered_otp):
    conn = sqlite3.connect(AUTH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT otp FROM hr_users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if row and row[0] == entered_otp:
        return True, "OTP verified successfully!"
    return False, "Invalid OTP code. Please verify and try again."

def save_employee_pin(email, pin):
    try:
        conn = sqlite3.connect(AUTH_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE hr_users SET pin = ?, is_verified = 1 WHERE email = ?", (pin, email.lower().strip()))
        conn.commit()
        conn.close()
        return True, "Quick PIN configured successfully!"
    except Exception as e:
        return False, f"Error: {e}"

def activate_license_key(email, key):
    conn = sqlite3.connect(AUTH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT is_used FROM license_keys WHERE license_key = ? AND email = ?", (key, email))
    row = cursor.fetchone()
    if row:
        if row[0] == 1:
            conn.close()
            return False, "This license key has already been used."
        cursor.execute("UPDATE license_keys SET is_used = 1 WHERE license_key = ?", (key,))
        cursor.execute("UPDATE hr_users SET is_pro = 1 WHERE email = ?", (email,))
        conn.commit()
        conn.close()
        return True, "Pro Subscription successfully activated!"
    conn.close()
    return False, "Invalid license key for this email address."

def delete_employee_profile(email):
    try:
        conn = sqlite3.connect(AUTH_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM hr_users WHERE email = ?", (email.lower().strip(),))
        conn.commit()
        conn.close()
        return True, "Employee profile successfully removed."
    except Exception as e:
        return False, f"Error: {e}"

def verify_employee_pin(email, entered_pin):
    conn = sqlite3.connect(AUTH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, pin, role, is_pro FROM hr_users WHERE email = ? AND is_verified = 1", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if row and row[1] == entered_pin:
        return True, row[0], row[2], row[3]
    return False, None, None, 0

# ===========================================================================
# PAGE CONFIG & EXECUTIVE STYLING
# ===========================================================================
st.set_page_config(
    page_title=f"{APP_NAME} | Executive Portal",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

EXECUTIVE_UI_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.sidebar-brand-box {
    background: linear-gradient(135deg, rgba(14, 165, 233, 0.12) 0%, rgba(2, 132, 199, 0.04) 100%);
    border: 1px solid rgba(14, 165, 233, 0.3);
    border-radius: 14px;
    padding: 1.4rem 1rem;
    text-align: center;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 12px rgba(14, 165, 233, 0.08);
}
.sidebar-brand-box h2 {
    font-size: 1.35rem; font-weight: 800; color: #0EA5E9; margin: 0 0 4px 0; letter-spacing: -0.5px;
}
.sidebar-brand-box p {
    font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; opacity: 0.85; margin: 0;
}

.auth-brand-side {
    background: linear-gradient(135deg, #0EA5E9 0%, #1E293B 100%);
    border-radius: 18px;
    padding: 3.5rem 2.5rem;
    color: #FFFFFF;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    box-shadow: 0 10px 30px rgba(14, 165, 233, 0.15);
}
.auth-brand-side h1 { font-size: 2.6rem; font-weight: 800; margin-bottom: 1rem; color: #FFFFFF; letter-spacing: -0.5px; }
.auth-brand-side p { font-size: 1.05rem; opacity: 0.9; line-height: 1.6; }

.auth-form-card {
    background: var(--background-color);
    border: 1.5px solid rgba(14, 165, 233, 0.3);
    border-radius: 18px;
    padding: 2.5rem;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.06);
}

/* Explicit Distinct Background Color Override for Profile Box */
div[data-testid="stVerticalBlock"] div[data-testid="stContainer"] {
    background: rgba(14, 165, 233, 0.08) !important;
    border: 1.5px solid #0EA5E9 !important;
    border-radius: 16px !important;
    padding: 1.5rem !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.06) !important;
}

/* Custom Distinct Background Color for Profile & Action Buttons */
.stButton > button {
    background: rgba(14, 165, 233, 0.14) !important;
    color: inherit !important;
    border: 1.5px solid rgba(14, 165, 233, 0.45) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease-in-out;
}
.stButton > button:hover {
    background: rgba(14, 165, 233, 0.25) !important;
    border-color: #0EA5E9 !important;
    box-shadow: 0 4px 12px rgba(14, 165, 233, 0.18);
}

.corp-hero {
    background: var(--background-color);
    border: 1px solid var(--secondary-background-color);
    border-radius: 14px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
    border-left: 6px solid #0EA5E9;
}
.corp-badge {
    display: inline-flex; align-items: center; gap: 8px; 
    background: rgba(14, 165, 233, 0.12); color: #0EA5E9; 
    padding: 5px 14px; border-radius: 8px;
    font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.8rem;
}
.corp-card {
    background: var(--background-color);
    border: 1px solid var(--secondary-background-color);
    border-radius: 14px;
    padding: 1.6rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 3px 10px rgba(0,0,0,0.03);
}
.metric-box {
    background: var(--secondary-background-color);
    border: 1px solid var(--secondary-background-color);
    border-radius: 12px;
    padding: 1.1rem;
    text-align: center;
}
.metric-box .val { font-size: 1.7rem; font-weight: 800; color: #0EA5E9; }
.metric-box .lbl { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.9px; margin-top: 4px; font-weight: 700; opacity: 0.8; }

.score-high { color: #10B981 !important; font-weight: 800; }
.score-mid { color: #D97706 !important; font-weight: 800; }
.score-low { color: #DC2626 !important; font-weight: 800; }

.stButton>button[kind="primary"] {
    background: #0EA5E9 !important; color: #FFFFFF !important; font-weight: 700; border-radius: 10px; padding: 0.6rem 1.4rem; border: none !important;
    box-shadow: 0 4px 12px rgba(14, 165, 233, 0.25);
}
.stButton>button[kind="primary"]:hover { background: #0284C7 !important; }

.sidebar-card { background: var(--secondary-background-color); border-radius: 12px; padding: 1.1rem; margin-bottom: 1rem; border: 1px solid rgba(14,165,233,0.15); }
</style>
"""
st.markdown(EXECUTIVE_UI_CSS, unsafe_allow_html=True)

# ===========================================================================
# SESSION STATE
# ===========================================================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "hr_name" not in st.session_state: st.session_state.hr_name = ""
if "hr_email" not in st.session_state: st.session_state.hr_email = ""
if "hr_role" not in st.session_state: st.session_state.hr_role = "Recruiter"
if "is_pro" not in st.session_state: st.session_state.is_pro = 0
if "selected_profile_email" not in st.session_state: st.session_state.selected_profile_email = None
if "pending_otp_email" not in st.session_state: st.session_state.pending_otp_email = None
if "pending_pin_email" not in st.session_state: st.session_state.pending_pin_email = None
if "results" not in st.session_state: st.session_state.results = []

# ===========================================================================
# AUTHENTICATION SCREEN
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()
    
    col_left, col_right = st.columns([1.1, 1.4], gap="large")
    
with col_left:
        st.markdown(f"""
            <div class="auth-brand-side">
                <h1>{APP_NAME}</h1>
                <p>{APP_TAGLINE}</p>
                <hr style="border-color: rgba(255,255,255,0.2); margin: 1.8rem 0;">
                <p style="font-size: 0.95rem; opacity: 0.9;">Empowering modern corporate enterprises with deep AI resume evaluation, automated candidate scoring, instant workflow pipelines, and secure employee role management.</p>
            </div>
        """, unsafe_allow_html=True)
        
    with col_right:
        st.markdown('<div class="auth-form-card">', unsafe_allow_html=True)
        
        # ... (OTP, PIN, aur Registration handlers yahan aayenge) ...
            
        elif saved_profiles and not st.session_state.selected_profile_email:
            # --- DISTINCT BACKGROUND CONTAINER FOR SAVED PROFILES ---
            st.markdown("""
                <div style="background-color: rgba(14, 165, 233, 0.12); border: 1.5px solid #0EA5E9; border-radius: 14px; padding: 1.5rem; margin-bottom: 1.2rem; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                    <h3 style="margin-top: 0; margin-bottom: 0.3rem; font-size: 1.2rem; font-weight: 700;">👥 Saved Employee Profiles</h3>
                    <p style="font-size: 0.85rem; opacity: 0.8; margin-bottom: 0;">Select your secure profile card below to sign in instantly:</p>
                </div>
            """, unsafe_allow_html=True)
            
            for p_email, p_name, p_pin, p_role, p_pro in saved_profiles:
                pro_badge = " 🌟 [PRO]" if p_pro == 1 else " 🆓 [Free]"
                c_p1, c_p2 = st.columns([3, 1])
                with c_p1:
                    if st.button(f"👤 {p_name} ({p_role}){pro_badge}", use_container_width=True, key=f"sel_{p_email}"):
                        st.session_state.selected_profile_email = p_email
                        st.rerun()
                with c_p2:
                    if st.button("🗑️ Delete", key=f"del_{p_email}", use_container_width=True):
                        delete_employee_profile(p_email)
                        st.success(f"Profile for {p_name} has been removed.")
                        st.rerun()
            
            st.markdown("")
            if st.button("➕ Register New Employee Profile", use_container_width=True):
                st.session_state.selected_profile_email = "new"
                st.rerun()
                
        # ... (baqi login aur registration forms yahan rahenge) ...
        
        st.markdown('</div>', unsafe_allow_html=True)
            
        elif st.session_state.selected_profile_email and st.session_state.selected_profile_email != "new":
            target_email = st.session_state.selected_profile_email
            p_match = next((p for p in saved_profiles if p[0] == target_email), ("Employee", "", "", "Recruiter", 0))
            
            st.markdown(f"### 🔐 Sign In: {p_match[1]}")
            st.caption("Enter your 4-digit security PIN to access portal.")
            
            with st.form("pin_login_form"):
                pin_input = st.text_input("4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                submit_login = st.form_submit_button("Sign In (Press Enter)", use_container_width=True)
                
            col_b1, col_b2 = st.columns(2)
            if submit_login:
                success, name, role, pro_status = verify_employee_pin(target_email, pin_input)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.hr_name = name
                    st.session_state.hr_email = target_email
                    st.session_state.hr_role = role
                    st.session_state.is_pro = pro_status
                    st.success(f"Welcome back, {name}!")
                    st.rerun()
                else:
                    st.error("Incorrect 4-Digit PIN. Please verify.")
            with col_b2:
                if st.button("Switch Profile", use_container_width=True):
                    st.session_state.selected_profile_email = None
                    st.rerun()
            
        else:
            st.markdown("### 📝 Employee Registration")
            st.caption("Enter your credentials to create a secure corporate account.")
            
            with st.form("registration_form"):
                reg_name = st.text_input("Full Name", placeholder="Alex Mercer")
                reg_email = st.text_input("Company Email", placeholder="employee@company.com")
                reg_pass = st.text_input("Master Password", type="password")
                submit_reg = st.form_submit_button("Send Verification OTP (Press Enter)", use_container_width=True)
                
            col_r1, col_r2 = st.columns(2)
            if submit_reg:
                if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                    st.warning("Please fill in all required fields.")
                else:
                    success, msg = register_initial_employee(reg_name, reg_email, reg_pass)
                    if success:
                        st.success(msg)
                        st.session_state.pending_otp_email = reg_email.lower().strip()
                        st.rerun()
                    else:
                        st.error(msg)
            with col_r2:
                if saved_profiles and st.button("Back to Profiles", use_container_width=True):
                    st.session_state.selected_profile_email = None
                    st.rerun()
                    
        st.markdown('</div>', unsafe_allow_html=True)
            
    st.stop()

# ===========================================================================
# DATABASE OPERATIONS & FORMATTED EXCEL EXPORT
# ===========================================================================
def load_database():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        expected_cols = [
            "Job Title", "Candidate Name", "Father Name", "Email", "Phone", 
            "CGPA", "Education", "University Name", "Experience Years", 
            "Latest Experience", "Extracted Skills", "Reference", "Match Score", "Pipeline Status", "Screened At"
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = "Not Provided"
        df.to_csv(DB_FILE, index=False)
        return df
    else:
        return pd.DataFrame(columns=[
            "Job Title", "Candidate Name", "Father Name", "Email", "Phone", 
            "CGPA", "Education", "University Name", "Experience Years", 
            "Latest Experience", "Extracted Skills", "Reference", "Match Score", "Pipeline Status", "Screened At"
        ])

def save_to_database(new_results, default_status="Shortlisted"):
    df = load_database()
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_data = []
    for r in new_results:
        new_data.append({
            "Job Title": r["job_title"],
            "Candidate Name": r["name"],
            "Father Name": r.get("father_name", "Not Provided"),
            "Email": r["email"],
            "Phone": r["phone"],
            "CGPA": r.get("cgpa", "Not Provided"),
            "Education": r.get("education", "Not Provided"),
            "University Name": r.get("university_name", "Not Provided"),
            "Experience Years": r.get("experience_years", "0"),
            "Latest Experience": r.get("latest_experience", "Not Provided"),
            "Extracted Skills": r.get("skills", "Not Provided"),
            "Reference": r.get("reference", "Not Provided"),
            "Match Score": r["match_score"],
            "Pipeline Status": default_status,
            "Screened At": current_timestamp
        })
    df_new = pd.DataFrame(new_data)
    
    # --- SMART DUPLICATE MERGE & PREVENTION BASED ON EMAIL ---
    if not df.empty and not df_new.empty:
        for _, new_row in df_new.iterrows():
            incoming_email = str(new_row["Email"]).lower().strip()
            if incoming_email not in ["not provided", "not found", "", "nan"]:
                df = df[~(df["Email"].str.lower().str.strip() == incoming_email)]
    
    df_combined = pd.concat([df, df_new], ignore_index=True)
    df_combined.to_csv(DB_FILE, index=False)

def update_candidate_status_in_db(email, job_title, new_status):
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df.loc[(df["Email"].str.lower() == email.lower()) & (df["Job Title"] == job_title), "Pipeline Status"] = new_status
        df.to_csv(DB_FILE, index=False)

def clear_candidate_database():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def check_if_exists_in_db(email):
    if not os.path.exists(DB_FILE) or email in ["Not Provided", "Not Found", ""] or not email:
        return False
    df = load_database()
    return email.lower().strip() in df["Email"].str.lower().str.strip().values

# --- FORMATTED EXECUTIVE RECRUITMENT REPORT EXPORTER ---
def dataframe_to_formatted_executive_report(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Recruitment Master Report")
        workbook = writer.book
        worksheet = writer.sheets["Recruitment Master Report"]
        
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#1E293B",
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        
        wrap_format = workbook.add_format({
            "text_wrap": True,
            "valign": "top",
            "border": 1
        })
        
        for col_idx, col_name in enumerate(df.columns):
            worksheet.write(0, col_idx, col_name, header_format)
            if col_name in ["Extracted Skills", "Latest Experience", "University Name", "Job Title"]:
                worksheet.set_column(col_idx, col_idx, 30, wrap_format)
            else:
                worksheet.set_column(col_idx, col_idx, 18, wrap_format)
                
        worksheet.freeze_panes(1, 0)
    buffer.seek(0)
    return buffer.getvalue()

# ===========================================================================
# TEXT EXTRACTION & OCR
# ===========================================================================
def extract_text_from_image(file_bytes: bytes) -> str:
    import pytesseract
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        return pytesseract.image_to_string(img)
    except Exception as e:
        st.error(f"⚠️ Image OCR failed: {e}")
        return ""

def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    import pytesseract
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
            else:
                try:
                    pil_img = page.to_image(resolution=300).original
                    ocr_text = pytesseract.image_to_string(pil_img)
                    text_parts.append(ocr_text)
                except Exception:
                    pass
    return "\n".join(text_parts)

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
# GROQ AI INTEGRATION
# ===========================================================================
def build_unified_prompt(resume_text: str, jd_text: str) -> str:
    return f"""You are an expert HR AI assistant. Analyze the CANDIDATE RESUME against the JOB DESCRIPTION.

CANDIDATE RESUME:
{resume_text[:12000]}

JOB DESCRIPTION:
{jd_text}

Return ONLY a valid JSON object with exactly the following keys. Extract the information precisely. Do not include markdown fences or explanations.
{{
  "name": "Candidate's full name",
  "father_name": "Father's name (if available, else 'Not Provided')",
  "email": "Candidate's email address (if available, else 'Not Provided')",
  "phone": "Candidate's phone number (if available, else 'Not Provided')",
  "cgpa": "CGPA or grades (if available, else 'Not Provided')",
  "education": "Highest degree or education level",
  "university_name": "Name of the University/Institution",
  "experience_years": "Total years of experience (e.g. '3 Years', 'Fresh', etc.)",
  "latest_experience": "Most recent job title and company (or 'None')",
  "skills": "Core skills extracted from the resume (comma-separated)",
  "reference": "Reference names/details mentioned (if any, else 'Available on Request' or 'Not Provided')",
  "match_score": A number between 0 and 100 representing how well the resume matches the JD,
  "missing_skills": ["List", "of", "key JD skills", "missing from resume"]
}}
"""

def analyze_and_extract_with_groq(client, resume_text: str, jd_text: str, job_title: str, file_name: str):
    try:
        prompt = build_unified_prompt(resume_text, jd_text)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw_content = response.choices[0].message.content.strip()
        result = json.loads(raw_content)
        email = result.get("email", "Not Provided")
        is_duplicate = check_if_exists_in_db(email)
        
        return {
            "file_name": file_name,
            "job_title": job_title,
            "name": result.get("name", "Unknown"),
            "father_name": result.get("father_name", "Not Provided"),
            "email": email,
            "phone": result.get("phone", "Not Provided"),
            "cgpa": result.get("cgpa", "Not Provided"),
            "education": result.get("education", "Not Provided"),
            "university_name": result.get("university_name", "Not Provided"),
            "experience_years": str(result.get("experience_years", "0")),
            "latest_experience": result.get("latest_experience", "Not Provided"),
            "skills": result.get("skills", "Not Provided"),
            "reference": result.get("reference", "Not Provided"),
            "match_score": float(result.get("match_score", 0)),
            "missing_skills": result.get("missing_skills", []),
            "is_duplicate": is_duplicate
        }
    except Exception as exc:
        st.error(f"⚠️ Groq analysis failed for **{file_name}**: {exc}")
        return None

def generate_ai_interview_questions(client, resume_text: str, job_title: str) -> str:
    try:
        prompt = f"""Based on the candidate resume and the job title '{job_title}', generate 5 precise technical and behavioral interview questions along with ideal expected answers for the interviewer. Format clearly with Markdown."""
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate interview questions: {e}"

# ===========================================================================
# SIDEBAR & DASHBOARD INTERFACE
# ===========================================================================
with st.sidebar:
    st.markdown(f"""
        <div class="sidebar-brand-box">
            <h2>{APP_NAME}</h2>
            <p>Enterprise v10.33</p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    tier_badge = "🌟 PRO TIER (6,999 PKR/mo)" if st.session_state.is_pro == 1 else "🆓 FREE BASIC TIER"
    st.markdown(f"""
        <div class="sidebar-card">
            <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700; margin-bottom: 4px;">Active Employee</div>
            <div style="font-size: 0.95rem; font-weight: 700;">👤 {st.session_state.hr_name}</div>
            <div style="font-size: 0.75rem; color: #0EA5E9; margin-top: 4px; font-weight: 600;">{tier_badge}</div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.is_pro == 0:
        st.markdown("### 🌟 Upgrade to PRO (6,999 PKR)")
        st.info("Transfer to our Meezan Bank or Sadapay account and submit your Transaction ID (TRX ID). Admin will verify and approve your license key.")
        
        with st.expander("💳 View Bank / Sadapay Details"):
            st.markdown(f"**Meezan Bank Account:**\n- Title: `{MEEZAN_TITLE}`\n- IBAN: `{MEEZAN_IBAN}`")
            st.markdown(f"**Sadapay Mobile Wallet:**\n- Number: `{SADAPAY_NUMBER}`")
        
        trx_input = st.text_input("Enter Transaction ID (TRX ID)", placeholder="e.g. TRX98234105", key="trx_sub_in")
        if st.button("Submit Payment for Approval", use_container_width=True):
            ok, msg = submit_payment_request(st.session_state.hr_email, st.session_state.hr_name, trx_input)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        license_input = st.text_input("Enter Pro License Key", type="password", placeholder="HMPRO-XXXX-XXXX", key="lic_act_in")
        if st.button("Activate Pro Subscription", use_container_width=True):
            ok, msg = activate_license_key(st.session_state.hr_email, license_input)
            if ok:
                st.session_state.is_pro = 1
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        st.markdown("---")

    if "GROQ_API_KEY" in st.secrets:
        groq_api_key = st.secrets["GROQ_API_KEY"]
        st.markdown('<div class="sidebar-card" style="border-color: #10B981; color: #059669; font-size: 0.8rem; font-weight: 600;">✓ Groq API Secured</div>', unsafe_allow_html=True)
    else:
        groq_api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    
    st.markdown("---")
    if st.button("🗑️ Clear Session Cache", use_container_width=True):
        st.session_state.results = []
        st.rerun()
        
    if st.button("🚪 Lock & Switch Profile", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.hr_email = ""
        st.session_state.hr_role = "Recruiter"
        st.session_state.is_pro = 0
        st.session_state.selected_profile_email = None
        st.session_state.results = []
        st.rerun()

# --- TOP LIVE MENU ACTIVITY FEED ---
df_all = load_database()
total_screened_db = len(df_all)
latest_candidate = df_all.iloc[-1]["Candidate Name"] if not df_all.empty else "None"
latest_job = df_all.iloc[-1]["Job Title"] if not df_all.empty else "N/A"

st.markdown(f"""
    <div class="corp-hero">
        <div class="corp-badge">
            <span>🟢 Live Employee Session</span> &bull; <span>{st.session_state.hr_email} ({'PRO' if st.session_state.is_pro == 1 else 'FREE'})</span>
        </div>
        <h1>{APP_NAME}</h1>
        <p>Welcome back, <b>{st.session_state.hr_name}</b> &mdash; Total Screened Profiles in System: <b>{total_screened_db}</b> | Latest Screening: <b>{latest_candidate} ({latest_job})</b></p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🚀 Screening Workspace", "🗄️ Candidate Database & Analytics", "🛡️ Admin Controls"])

with tab1:
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="corp-card"><h4>📋 Job Specification & Threshold</h4>', unsafe_allow_html=True)
        job_title_input = st.text_input("Job Position Title", placeholder="e.g. Lead AI Engineer")
        jd_text = st.text_area("Job Description & Requirements", height=110, placeholder="Paste detailed job description here...")
        
        # --- DYNAMIC MATCH SCORE THRESHOLD SETTING ---
        st.markdown("---")
        st.markdown("**🎯 Select Minimum Passing Score Threshold (%)**")
        custom_threshold = st.slider(
            "Candidates scoring above this will be Shortlisted; others will be marked as Rejected.",
            min_value=0, max_value=100, value=50, step=5,
            label_visibility="collapsed"
        )
        st.caption(f"Current Selected Threshold: **{custom_threshold}%**")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="corp-card"><h4>📥 Resume Dropzone</h4>', unsafe_allow_html=True)
        uploaded_files = st.file_uploader("Upload candidate resumes", type=ACCEPTED_TYPES, accept_multiple_files=True, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("⚡ Execute Deep LLM Screening", type="primary", use_container_width=True, disabled=not (uploaded_files and jd_text.strip() and job_title_input.strip() and groq_api_key)):
        client = Groq(api_key=groq_api_key)
        results = []
        progress = st.progress(0.0, text="Initializing Neural Extraction...")
        
        for i, file in enumerate(uploaded_files):
            progress.progress((i + 1) / (len(uploaded_files) + 1), text=f"Analyzing {file.name}...")
            text = extract_resume_text(file)
            if text:
                analysis = analyze_and_extract_with_groq(client, text, jd_text, job_title_input, file.name)
                if analysis:
                    results.append(analysis)
                    
        progress.empty()
        st.session_state.results = results
        if results:
            for r in results:
                r["initial_status"] = "Shortlisted" if r["match_score"] >= custom_threshold else "Rejected"
            
            save_to_database(results, default_status="Shortlisted")
            st.success(f"Successfully processed {len(results)} candidate resumes! Duplicates merged/prevented.")
            st.rerun()

    # --- RESULTS DISPLAY ---
    if st.session_state.results:
        results = st.session_state.results
        
        st.markdown('<div class="corp-card"><h4>📊 Screening Metrics Overview</h4>', unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f'<div class="metric-box"><div class="val">{len(results)}</div><div class="lbl">Total Screened (Batch)</div></div>', unsafe_allow_html=True)
        with m2:
            avg_score = round(sum(r["match_score"] for r in results) / len(results), 1)
            st.markdown(f'<div class="metric-box"><div class="val">{avg_score}%</div><div class="lbl">Average Match Score</div></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="corp-card"><h4>🧾 Ranked Candidate Insights & Pro Tools</h4>', unsafe_allow_html=True)
        results = sorted(results, key=lambda x: x["match_score"], reverse=True)
        
        client = Groq(api_key=groq_api_key) if groq_api_key else None

        for rank, cand in enumerate(results, start=1):
            history_badge = " ⚠️ [Previously in DB]" if cand["is_duplicate"] else " 🆕 [New Candidate]"
            score_cls = "score-high" if cand["match_score"] >= 75 else ("score-mid" if cand["match_score"] >= 50 else "score-low")
            
            with st.expander(f"#{rank} — {cand['name']} | Match Score: {cand['match_score']}%{history_badge}", expanded=(rank == 1)):
                c1, c2 = st.columns([1.3, 1])
                with c1:
                    st.markdown(f"**✉️ Email:** `{cand['email']}` | **📞 Phone:** `{cand['phone']}`")
                    st.markdown(f"**👤 Father's Name:** {cand['father_name']}")
                    st.markdown(f"**🎓 Education:** {cand['education']} (CGPA: {cand['cgpa']})")
                    st.markdown(f"**🏫 Institution:** {cand['university_name']}")
                    st.markdown(f"**💼 Experience:** {cand['experience_years']} | **Latest Role:** {cand['latest_experience']}")
                    st.markdown(f"**🔗 Reference:** {cand['reference']}")
                    st.markdown(f"**🛠️ Extracted Skills:** {cand['skills']}")
                    
                    st.markdown(f'<div class="metric-box" style="margin-top: 15px; width: 150px;"><div class="val {score_cls}">{cand["match_score"]}%</div><div class="lbl">Match Rating</div></div>', unsafe_allow_html=True)
                
                with c2:
                    st.markdown("**❌ Skill Gaps / Missing vs. JD:**")
                    if cand["missing_skills"]:
                        for skill in cand["missing_skills"]:
                            st.markdown(f"- {skill}")
                    else:
                        st.caption("No significant skill gaps identified.")

                st.markdown("---")
                if st.session_state.is_pro == 1:
                    if st.button(f"💡 Generate AI Interview Q&A for {cand['name']}", key=f"gen_q_{rank}"):
                        if client:
                            with st.spinner("Generating tailored interview questions..."):
                                q_text = generate_ai_interview_questions(client, cand['skills'], job_title_input)
                                st.markdown("#### 🎯 AI Generated Interview Guide:")
                                st.markdown(q_text)
                        else:
                            st.error("Groq API key required.")

                    if cand['email'] not in ["Not Provided", "Not Found", ""] and cand['email']:
                        st.markdown("#### ✉️ Conditional Email Dispatcher (Score-Based)")
                        
                        if cand['match_score'] >= 50:
                            default_msg = f"Dear {cand['name']},\n\nWe were deeply impressed by your credentials and match score ({cand['match_score']}%) for the {job_title_input} position at HireMatrix Pro. We would love to invite you for an interview round.\n\nBest Regards,\nTeam HireMatrix Pro"
                            email_subject = f"Interview Invitation - {job_title_input}"
                            st.info("✓ Score >= 50%: **Interview Invitation Template loaded.**")
                        else:
                            default_msg = f"Dear {cand['name']},\n\nThank you for your interest in the {job_title_input} position at HireMatrix Pro. Although your background is notable, your match score ({cand['match_score']}%) does not meet our current threshold for this role. We wish you the best in your career pursuits.\n\nBest Regards,\nTeam HireMatrix Pro"
                            email_subject = f"Application Status Update - {job_title_input}"
                            st.warning("⚠️ Score < 50%: **Apology / Rejection Template loaded.**")

                        invite_msg = st.text_area("Email Message", value=default_msg, key=f"inv_msg_{rank}")
                        
                        if st.button(f"📧 Send Email", key=f"send_inv_{rank}"):
                            ok, res_m = send_smtp_email(cand['email'], email_subject, invite_msg)
                            if ok:
                                st.success(f"Email sent successfully to {cand['email']}!")
                                new_status = "Interview Scheduled" if cand['match_score'] >= 50 else "Rejected"
                                update_candidate_status_in_db(cand['email'], job_title_input, new_status)
                            else:
                                st.error(res_m)
                else:
                    st.warning("🔒 **Pro Feature Locked:** Upgrade to **PRO (6,999 PKR/mo)** from the sidebar to unlock AI Interview Q&A Generation and Automated Email Invites.")

        st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🗄️ Candidate Database, Search Filters & Analytics Charts</h4>', unsafe_allow_html=True)
    
    # --- DOWNLOAD EXECUTIVE FORMATTED REPORT BUTTON ---
    df_export = load_database()
    st.download_button(
        "📊 Download Executive Formatted Report (.xlsx)",
        data=dataframe_to_formatted_executive_report(df_export),
        file_name=f"Executive_Recruitment_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.markdown("---")
    
    if st.button("🗑️ Clear Entire Candidate Database", type="secondary"):
        clear_candidate_database()
        st.success("Candidate database has been successfully cleared!")
        st.rerun()
        
    st.markdown("---")
    
    df_db = load_database()
    if df_db.empty:
        st.info("Database is currently empty.")
    else:
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            search_query = st.text_input("🔍 Live Search (Candidate Name, Skills, Job Title, Email)", placeholder="Type to search...")
        with col_f2:
            min_score_filter = st.slider("Minimum Match Score (%)", 0, 100, 0)
            
        filtered_df = df_db.copy()
        if min_score_filter > 0:
            filtered_df = filtered_df[filtered_df["Match Score"] >= min_score_filter]
            
        if search_query.strip():
            q = search_query.lower()
            filtered_df = filtered_df[
                filtered_df["Candidate Name"].str.lower().str.contains(q, na=False) |
                filtered_df["Job Title"].str.lower().str.contains(q, na=False) |
                filtered_df["Extracted Skills"].str.lower().str.contains(q, na=False) |
                filtered_df["Email"].str.lower().str.contains(q, na=False)
            ]
            
        st.markdown(f"**Showing {len(filtered_df)} of {len(df_db)} candidates matching criteria:**")
        st.dataframe(filtered_df, use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 📈 Built-in Visual Analytics & Charts")
        
        c_ch1, c_ch2 = st.columns(2)
        with c_ch1:
            st.markdown("#### Match Score Distribution")
            st.bar_chart(df_db.set_index("Candidate Name")["Match Score"])
            
        with c_ch2:
            st.markdown("#### Pipeline Status Breakdown")
            if "Pipeline Status" in df_db.columns:
                status_counts = df_db["Pipeline Status"].value_counts()
                st.bar_chart(status_counts)

        if st.session_state.is_pro == 1:
            st.markdown("---")
            st.markdown("Update candidate pipeline stage below:")
            for idx, row in df_db.iterrows():
                cols = st.columns([2, 2, 2, 2])
                with cols[0]: st.write(f"**{row['Candidate Name']}**")
                with cols[1]: st.write(f"*{row['Job Title']}*")
                with cols[2]: st.write(f"Score: {row['Match Score']}%")
                with cols[3]:
                    current_status = row["Pipeline Status"] if "Pipeline Status" in df_db.columns else "Shortlisted"
                    new_status = st.selectbox("Stage", ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"], index=["Shortlisted", "Interview Scheduled", "Hired", "Rejected"].index(current_status) if current_status in ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"] else 0, key=f"status_{idx}")
                    if new_status != current_status:
                        update_candidate_status_in_db(row['Email'], row['Job Title'], new_status)
                        st.rerun()
                        
    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="corp-card"><h4>🛡️ Admin Access & Employee & Payment Management</h4>', unsafe_allow_html=True)
    if st.session_state.hr_role != "Admin":
        st.warning("⚠️ Access Restricted: Only users with **Admin** role can manage company employee profiles and payment requests.")
    else:
        st.success("✓ Admin privileges active.")
        
        st.markdown("### 💳 Pending Subscription Payment Requests")
        try:
            conn_p = sqlite3.connect(AUTH_DB_FILE)
            cur_p = conn_p.cursor()
            cur_p.execute("SELECT trx_id, email, name, status FROM payment_requests WHERE status = 'Pending'")
            pendings = cur_p.fetchall()
            conn_p.close()
            
            if not pendings:
                st.info("No pending payment requests found.")
            else:
                for trx, p_email, p_name, status in pendings:
                    c_pr1, c_pr2 = st.columns([3, 1])
                    with c_pr1:
                        st.write(f"👤 **{p_name}** (`{p_email}`) — TRX ID: **`{trx}`**")
                    with c_pr2:
                        if st.button("✅ Approve & Send Key", key=f"app_{trx}", use_container_width=True):
                            ok_a, msg_a = admin_approve_payment(trx, p_email)
                            if ok_a:
                                st.success(msg_a)
                                st.rerun()
                            else:
                                st.error(msg_a)
        except Exception as e:
            st.error(f"Error loading payments: {e}")
            
        st.markdown("---")
        st.markdown("### 👥 Active Employee Profiles")
        all_emps = get_all_verified_profiles()
        st.markdown(f"**Total Active Registered Employees:** {len(all_emps)}")
        for emp_email, emp_name, emp_pin, emp_role, emp_pro in all_emps:
            pro_st = "🌟 PRO" if emp_pro == 1 else "🆓 Free"
            col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
            with col_a1: st.write(f"👤 **{emp_name}** ({emp_email}) — *{emp_role}* [{pro_st}]")
            with col_a2: st.write(f"PIN: `{emp_pin}`")
            with col_a3:
                if emp_email.lower() != st.session_state.hr_email.lower():
                    if st.button("🗑️ Revoke", key=f"rev_{emp_email}", use_container_width=True):
                        delete_employee_profile(emp_email)
                        st.success(f"Access revoked for {emp_name}.")
                        st.rerun()
                else:
                    st.caption("Current User")
    st.markdown("</div>", unsafe_allow_html=True)
