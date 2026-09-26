"""
HireMatrix Pro — Enterprise Edition v10.50 (Multi-Stage ATS Architecture)
========================================================================
Features: 2-Step Workflow (1. Talent Pool Repository & CV Extraction -> 2. JD Matching & Ranked Scoring), 
Conditional Email Dispatchers, Dynamic Threshold, and Executive Excel Report.
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
            is_verified INTEGER DEFAULT 0,
            otp TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(hr_users)")
    columns = [col[1] for col in cursor.fetchall()]
    if "pin" not in columns: cursor.execute("ALTER TABLE hr_users ADD COLUMN pin TEXT")
    if "role" not in columns: cursor.execute("ALTER TABLE hr_users ADD COLUMN role TEXT DEFAULT 'Recruiter'")
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
        msg['From'] = formataddr(("HireMatrix Pro Notifications", sender_email))
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

def get_all_verified_profiles():
    conn = sqlite3.connect(AUTH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email, name, pin, role FROM hr_users WHERE is_verified = 1 AND pin IS NOT NULL")
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
        
        cursor.execute("""
            INSERT OR REPLACE INTO hr_users (email, name, password, pin, role, is_verified, otp) 
            VALUES (?, ?, ?, NULL, ?, 0, ?)
        """, (clean_email, name, hash_password(password), role, otp))
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
    cursor.execute("SELECT name, pin, role FROM hr_users WHERE email = ? AND is_verified = 1", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if row and row[1] == entered_pin:
        return True, row[0], row[2]
    return False, None, None

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
    background: linear-gradient(135deg, rgba(14, 165, 233, 0.10) 0%, rgba(30, 41, 59, 0.06) 100%);
    border: 1.5px solid rgba(14, 165, 233, 0.35);
    border-radius: 14px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 6px 20px rgba(14, 165, 233, 0.08);
    border-left: 6px solid #0EA5E9;
}
.corp-badge {
    display: inline-flex; align-items: center; gap: 8px; 
    background: rgba(14, 165, 233, 0.15); color: #0EA5E9; 
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
if "selected_profile_email" not in st.session_state: st.session_state.selected_profile_email = None
if "pending_otp_email" not in st.session_state: st.session_state.pending_otp_email = None
if "pending_pin_email" not in st.session_state: st.session_state.pending_pin_email = None
if "screening_results" not in st.session_state: st.session_state.screening_results = []

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
                <p style="font-size: 0.95rem; opacity: 0.9;">Empowering modern corporate enterprises with multi-stage ATS workflow, intelligent talent repository, automated candidate scoring, and secure role management.</p>
            </div>
        """, unsafe_allow_html=True)
        
    with col_right:
        st.markdown('<div class="auth-form-card">', unsafe_allow_html=True)
        
        if st.session_state.pending_pin_email:
            st.markdown("### 🔐 Security Setup")
            st.info(f"Email verified for **{st.session_state.pending_pin_email}**.")
            
            with st.form("pin_setup_form"):
                new_pin = st.text_input("Enter 4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                confirm_pin = st.text_input("Confirm 4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                submit_pin = st.form_submit_button("Save PIN & Enter Portal", use_container_width=True)
                
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
                success, msg = verify_otp_code(st.session_state.pending_otp_email, otp_input)
                if success:
                    st.success(msg)
                    st.session_state.pending_pin_email = st.session_state.pending_otp_email
                    st.session_state.pending_otp_email = None
                    st.rerun()
                else:
                    st.error(msg)
            with col_o2:
                if st.button("Cancel", use_container_width=True, key="cancel_otp_btn"):
                    st.session_state.pending_otp_email = None
                    st.rerun()
            
        elif saved_profiles and not st.session_state.selected_profile_email:
            st.markdown("""
                <div style="background: rgba(14, 165, 233, 0.08); border: 1.5px solid #0EA5E9; border-radius: 14px; padding: 1.6rem; margin-bottom: 1.5rem; box-shadow: 0 4px 15px rgba(0,0,0,0.04);">
                    <h3 style="margin-top: 0; margin-bottom: 0.3rem; font-size: 1.2rem; font-weight: 700;">👥 Saved Employee Profiles</h3>
                    <p style="font-size: 0.85rem; opacity: 0.8; margin-bottom: 0;">Select your secure profile card below to sign in instantly:</p>
                </div>
            """, unsafe_allow_html=True)
            
            for p_email, p_name, p_pin, p_role in saved_profiles:
                c_p1, c_p2 = st.columns([3, 1])
                with c_p1:
                    if st.button(f"👤 {p_name} ({p_role})", use_container_width=True, key=f"sel_{p_email}"):
                        st.session_state.selected_profile_email = p_email
                        st.rerun()
                with c_p2:
                    if st.button("🗑️ Delete", key=f"del_{p_email}", use_container_width=True):
                        delete_employee_profile(p_email)
                        st.success(f"Profile for {p_name} has been removed.")
                        st.rerun()
            
            st.markdown("")
            if st.button("➕ Register New Employee Profile", use_container_width=True, key="reg_new_emp_auth_btn"):
                st.session_state.selected_profile_email = "new"
                st.rerun()
            
        elif st.session_state.selected_profile_email and st.session_state.selected_profile_email != "new":
            target_email = st.session_state.selected_profile_email
            p_match = next((p for p in saved_profiles if p[0] == target_email), ("Employee", "", "", "Recruiter"))
            
            st.markdown(f"### 🔐 Sign In: {p_match[1]}")
            st.caption("Enter your 4-digit security PIN to access portal.")
            
            with st.form("pin_login_form"):
                pin_input = st.text_input("4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                submit_login = st.form_submit_button("Sign In (Press Enter)", use_container_width=True)
                
            col_b1, col_b2 = st.columns(2)
            if submit_login:
                success, name, role = verify_employee_pin(target_email, pin_input)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.hr_name = name
                    st.session_state.hr_email = target_email
                    st.session_state.hr_role = role
                    st.success(f"Welcome back, {name}!")
                    st.rerun()
                else:
                    st.error("Incorrect 4-Digit PIN. Please verify.")
            with col_b2:
                if st.button("Switch Profile", use_container_width=True, key="switch_prof_auth_btn"):
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
                if saved_profiles and st.button("Back to Profiles", use_container_width=True, key="back_to_prof_auth_btn"):
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
            "Candidate Name", "Father Name", "Email", "Phone", 
            "CGPA", "Education", "University Name", "Experience Years", 
            "Latest Experience", "Extracted Skills", "Reference", "Pipeline Status", "Added At"
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = "Not Provided"
        df.to_csv(DB_FILE, index=False)
        return df
    else:
        return pd.DataFrame(columns=[
            "Candidate Name", "Father Name", "Email", "Phone", 
            "CGPA", "Education", "University Name", "Experience Years", 
            "Latest Experience", "Extracted Skills", "Reference", "Pipeline Status", "Added At"
        ])

def save_candidates_to_repository(new_candidates):
    df = load_database()
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_data = []
    for c in new_candidates:
        new_data.append({
            "Candidate Name": c["name"],
            "Father Name": c.get("father_name", "Not Provided"),
            "Email": c["email"],
            "Phone": c["phone"],
            "CGPA": c.get("cgpa", "Not Provided"),
            "Education": c.get("education", "Not Provided"),
            "University Name": c.get("university_name", "Not Provided"),
            "Experience Years": c.get("experience_years", "0"),
            "Latest Experience": c.get("latest_experience", "Not Provided"),
            "Extracted Skills": c.get("skills", "Not Provided"),
            "Reference": c.get("reference", "Not Provided"),
            "Pipeline Status": "Talent Pool",
            "Added At": current_timestamp
        })
    df_new = pd.DataFrame(new_data)
    
    # Smart Duplicate Prevention based on Email
    if not df.empty and not df_new.empty:
        for _, new_row in df_new.iterrows():
            incoming_email = str(new_row["Email"]).lower().strip()
            if incoming_email not in ["not provided", "not found", "", "nan"]:
                df = df[~(df["Email"].str.lower().str.strip() == incoming_email)]
                
    df_combined = pd.concat([df, df_new], ignore_index=True)
    df_combined.to_csv(DB_FILE, index=False)

def update_candidate_pipeline_status(email, new_status):
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df.loc[df["Email"].str.lower() == email.lower(), "Pipeline Status"] = new_status
        df.to_csv(DB_FILE, index=False)

def clear_candidate_database():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def check_if_exists_in_db(email):
    if not os.path.exists(DB_FILE) or email in ["Not Provided", "Not Found", ""] or not email:
        return False
    df = load_database()
    return email.lower().strip() in df["Email"].str.lower().str.strip().values

def dataframe_to_formatted_executive_report(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Talent Repository Report")
        workbook = writer.book
        worksheet = writer.sheets["Talent Repository Report"]
        
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
            if col_name in ["Extracted Skills", "Latest Experience", "University Name"]:
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
def build_repository_extraction_prompt(resume_text: str) -> str:
    return f"""You are an expert HR AI assistant. Extract candidate profile information from the following resume.

RESUME TEXT:
{resume_text[:12000]}

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
  "reference": "Reference names/details mentioned (if any, else 'Available on Request' or 'Not Provided')"
}}
"""

def build_jd_matching_prompt(candidate_text_summary: str, jd_text: str) -> str:
    return f"""You are an expert HR recruiter AI. Evaluate the CANDIDATE PROFILE against the JOB DESCRIPTION.

CANDIDATE PROFILE SUMMARY:
{candidate_text_summary}

JOB DESCRIPTION:
{jd_text}

Return ONLY a valid JSON object with exactly the following keys. Do not include markdown fences.
{{
  "match_score": A number between 0 and 100 representing how well the candidate matches the JD,
  "missing_skills": ["List", "of", "key JD skills", "missing from candidate profile"]
}}
"""

def extract_candidate_for_repo(client, resume_text: str, file_name: str):
    try:
        prompt = build_repository_extraction_prompt(resume_text)
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
            "is_duplicate": is_duplicate
        }
    except Exception as exc:
        st.error(f"⚠️ Extraction failed for **{file_name}**: {exc}")
        return None

def evaluate_candidate_against_jd(client, candidate_row, jd_text: str):
    try:
        summary = f"Name: {candidate_row['Candidate Name']}, Education: {candidate_row['Education']}, University: {candidate_row['University Name']}, Experience: {candidate_row['Experience Years']}, Latest Role: {candidate_row['Latest Experience']}, Skills: {candidate_row['Extracted Skills']}"
        prompt = build_jd_matching_prompt(summary, jd_text)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw_content = response.choices[0].message.content.strip()
        result = json.loads(raw_content)
        return float(result.get("match_score", 0)), result.get("missing_skills", [])
    except Exception:
        return 0.0, []

def generate_ai_interview_questions(client, skills_text: str, job_title: str) -> str:
    try:
        prompt = f"""Based on the candidate skills '{skills_text}' and the job title '{job_title}', generate 5 precise technical and behavioral interview questions along with ideal expected answers. Format clearly with Markdown bullet points and headings. Do not include raw HTML tags."""
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
# SIDEBAR & DASHBOARD INTERFACE
# ===========================================================================
with st.sidebar:
    st.markdown(f"""
        <div class="sidebar-brand-box">
            <h2>{APP_NAME}</h2>
            <p>Multi-Stage ATS v10.50</p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown(f"""
        <div class="sidebar-card">
            <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700; margin-bottom: 4px;">Active Employee</div>
            <div style="font-size: 0.95rem; font-weight: 700;">👤 {st.session_state.hr_name}</div>
            <div style="font-size: 0.75rem; color: #10B981; margin-top: 4px; font-weight: 600;">🌟 FULL ACCESS UNLOCKED</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    if "GROQ_API_KEY" in st.secrets:
        groq_api_key = st.secrets["GROQ_API_KEY"]
        st.markdown('<div class="sidebar-card" style="border-color: #10B981; color: #059669; font-size: 0.8rem; font-weight: 600;">✓ Groq API Secured</div>', unsafe_allow_html=True)
    else:
        groq_api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    
    st.markdown("---")
    if st.button("🗑️ Clear Session Cache", use_container_width=True, key="clear_cache_btn"):
        st.session_state.screening_results = []
        st.rerun()
        
    if st.button("🚪 Lock & Switch Profile", use_container_width=True, key="lock_switch_btn"):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.hr_email = ""
        st.session_state.hr_role = "Recruiter"
        st.session_state.selected_profile_email = None
        st.session_state.screening_results = []
        st.rerun()

# --- TOP LIVE MENU ACTIVITY FEED ---
df_all = load_database()
total_repo_db = len(df_all)
latest_candidate = df_all.iloc[-1]["Candidate Name"] if not df_all.empty else "None"

st.markdown(f"""
    <div class="corp-hero">
        <div class="corp-badge">
            <span>🟢 Multi-Stage ATS Session</span> &bull; <span>{st.session_state.hr_email} (UNLOCKED)</span>
        </div>
        <h1>{APP_NAME}</h1>
        <p>Welcome back, <b>{st.session_state.hr_name}</b> &mdash; Total Candidates in Talent Pool: <b>{total_repo_db}</b> | Latest Added: <b>{latest_candidate}</b></p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Talent Repository (Upload)", "🎯 2. JD Screening & Matching", "🗄️ 3. Candidate Database & Pipeline", "🛡️ 4. Admin Controls"])

with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Talent Repository Ingestion (Upload Resumes)</h4>', unsafe_allow_html=True)
    st.caption("Upload candidate resumes below. AI will extract their profile details and save them to the central repository independently of any Job Description.")
    
    uploaded_repo_files = st.file_uploader("Upload candidate resumes to repository", type=ACCEPTED_TYPES, accept_multiple_files=True, label_visibility="collapsed")
    
    if st.button("⚡ Extract & Save to Talent Pool", type="primary", use_container_width=True, disabled=not (uploaded_repo_files and groq_api_key)):
        client = Groq(api_key=groq_api_key)
        extracted_batch = []
        progress = st.progress(0.0, text="Reading and extracting profiles...")
        
        for i, file in enumerate(uploaded_repo_files):
            progress.progress((i + 1) / (len(uploaded_repo_files) + 1), text=f"Extracting {file.name}...")
            text = extract_resume_text(file)
            if text:
                profile_data = extract_candidate_for_repo(client, text, file.name)
                if profile_data:
                    extracted_batch.append(profile_data)
                    
        progress.empty()
        if extracted_batch:
            save_candidates_to_repository(extracted_batch)
            st.success(f"Successfully processed and added {len(extracted_batch)} candidates to the Talent Pool!")
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Display current repo summary
    df_repo = load_database()
    if not df_repo.empty:
        st.markdown('<div class="corp-card"><h4>📋 Current Candidates in Talent Repository</h4>', unsafe_allow_html=True)
        st.dataframe(df_repo[["Candidate Name", "Email", "Phone", "Education", "Experience Years", "Extracted Skills", "Pipeline Status"]], use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening & Smart Matching</h4>', unsafe_allow_html=True)
    st.caption("Enter a Job Description below. AI will scan your stored Talent Pool repository, evaluate candidates against the JD, and rank them instantly.")
    
    jd_title_input = st.text_input("Job Position Title", placeholder="e.g. Senior AI Engineer")
    jd_desc_text = st.text_area("Job Description & Requirements", height=120, placeholder="Paste detailed job description here...")
    
    st.markdown("---")
    st.markdown("**🎯 Select Minimum Passing Score Threshold (%)**")
    screening_threshold = st.slider(
        "Candidates scoring above this will be Shortlisted; others will be marked as Rejected.",
        min_value=0, max_value=100, value=50, step=5,
        label_visibility="collapsed",
        key="screening_threshold_slider"
    )
    st.caption(f"Current Selected Threshold: **{screening_threshold}%**")
    
    df_pool = load_database()
    
    if st.button("⚡ Run AI Screening against Talent Pool", type="primary", use_container_width=True, disabled=not (jd_desc_text.strip() and jd_title_input.strip() and not df_pool.empty and groq_api_key)):
        client = Groq(api_key=groq_api_key)
        screened_results = []
        progress = st.progress(0.0, text="Evaluating candidates against Job Description...")
        
        for idx, row in df_pool.iterrows():
            progress.progress((idx + 1) / (len(df_pool) + 1), text=f"Evaluating {row['Candidate Name']}...")
            score, missing = evaluate_candidate_against_jd(client, row, jd_desc_text)
            
            initial_status = "Shortlisted" if score >= screening_threshold else "Rejected"
            
            screened_results.append({
                "job_title": jd_title_input,
                "name": row["Candidate Name"],
                "father_name": row["Father Name"],
                "email": row["Email"],
                "phone": row["Phone"],
                "cgpa": row["CGPA"],
                "education": row["Education"],
                "university_name": row["University Name"],
                "experience_years": row["Experience Years"],
                "latest_experience": row["Latest Experience"],
                "skills": row["Extracted Skills"],
                "reference": row["Reference"],
                "match_score": score,
                "missing_skills": missing,
                "pipeline_status": initial_status
            })
            
        progress.empty()
        st.session_state.screening_results = screened_results
        st.success(f"Successfully evaluated {len(df_pool)} candidates from repository!")
        st.rerun()
        
    if df_pool.empty:
        st.info("⚠️ Talent repository is currently empty. Please upload resumes in **Step 1** first.")
        
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SCREENED RESULTS & PIPELINE STATUS / CONDITIONAL EMAILS ---
    if st.session_state.screening_results:
        st.markdown('<div class="corp-card"><h4>📊 Ranked Screening Results & Conditional Action Pipeline</h4>', unsafe_allow_html=True)
        results = sorted(st.session_state.screening_results, key=lambda x: x["match_score"], reverse=True)
        
        client = Groq(api_key=groq_api_key) if groq_api_key else None

        for rank, cand in enumerate(results, start=1):
            score_cls = "score-high" if cand["match_score"] >= 75 else ("score-mid" if cand["match_score"] >= 50 else "score-low")
            
            with st.expander(f"#{rank} — {cand['name']} | Match Score: {cand['match_score']}% | Stage: {cand['pipeline_status']}", expanded=(rank == 1)):
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
                # --- PIPELINE STATUS SELECTOR ---
                st.markdown("#### 🔄 Candidate Pipeline Stage")
                new_stage = st.selectbox(
                    "Update Stage", 
                    ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"], 
                    index=["Shortlisted", "Interview Scheduled", "Hired", "Rejected"].index(cand["pipeline_status"]) if cand["pipeline_status"] in ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"] else 0,
                    key=f"stage_sel_{rank}"
                )
                if new_stage != cand["pipeline_status"]:
                    cand["pipeline_status"] = new_stage
                    update_candidate_pipeline_status(cand["email"], new_stage)
                    st.success(f"Pipeline stage updated to **{new_stage}**!")
                    st.rerun()

                st.markdown("---")
                if st.button(f"💡 Generate AI Interview Q&A for {cand['name']}", key=f"gen_q_{rank}"):
                    if client:
                        with st.spinner("Generating tailored interview questions..."):
                            q_text = generate_ai_interview_questions(client, cand['skills'], cand['job_title'])
                            st.markdown("#### 🎯 AI Generated Interview Guide:")
                            st.markdown(q_text)
                    else:
                        st.error("Groq API key required.")

                # --- CONDITIONAL EMAIL DISPATCHER (TRIGGERS ONLY ON STAGE CHANGE) ---
                if cand['email'] not in ["Not Provided", "Not Found", ""] and cand['email']:
                    st.markdown("#### ✉️ Conditional Email Dispatcher")
                    
                    if cand["pipeline_status"] in ["Shortlisted", "Interview Scheduled"]:
                        default_msg = f"Dear {cand['name']},\n\nWe were deeply impressed by your credentials and match score ({cand['match_score']}%) for the {cand['job_title']} position at HireMatrix Pro. We would love to invite you for an interview round.\n\nBest Regards,\nTeam HireMatrix Pro"
                        email_subject = f"Interview Invitation - {cand['job_title']}"
                        st.info(f"✓ Stage is **{cand['pipeline_status']}**: Interview Invitation template loaded.")
                    elif cand["pipeline_status"] == "Hired":
                        default_msg = f"Dear {cand['name']},\n\nCongratulations! We are thrilled to offer you the position of {cand['job_title']} at HireMatrix Pro. Welcome aboard!\n\nBest Regards,\nTeam HireMatrix Pro"
                        email_subject = f"Official Offer Letter - {cand['job_title']}"
                        st.success("✓ Stage is **Hired**: Official Offer Letter template loaded.")
                    else:
                        default_msg = f"Dear {cand['name']},\n\nThank you for your interest in the {cand['job_title']} position at HireMatrix Pro. Although your background is notable, we have decided to move forward with other candidates. We wish you the best.\n\nBest Regards,\nTeam HireMatrix Pro"
                        email_subject = f"Application Status Update - {cand['job_title']}"
                        st.warning("⚠️ Stage is **Rejected**: Regret template loaded.")

                    invite_msg = st.text_area("Email Message", value=default_msg, key=f"inv_msg_{rank}")
                    
                    if st.button(f"📧 Send Email to {cand['name']}", key=f"send_inv_{rank}"):
                        ok, res_m = send_smtp_email(cand['email'], email_subject, invite_msg)
                        if ok:
                            st.success(f"Email sent successfully to {cand['email']}!")
                        else:
                            st.error(res_m)

        st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Candidate Database, Search Filters & Analytics Charts</h4>', unsafe_allow_html=True)
    
    df_export = load_database()
    st.download_button(
        "📊 Download Executive Formatted Report (.xlsx)",
        data=dataframe_to_formatted_executive_report(df_export),
        file_name=f"Executive_Talent_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.markdown("---")
    
    if st.button("🗑️ Clear Entire Talent Repository", type="secondary", key="clear_db_btn"):
        clear_candidate_database()
        st.success("Talent repository has been successfully cleared!")
        st.rerun()
        
    st.markdown("---")
    
    df_db = load_database()
    if df_db.empty:
        st.info("Talent repository database is currently empty.")
    else:
        search_query = st.text_input("🔍 Live Search (Candidate Name, Skills, Education, Email)", placeholder="Type to search repository...")
            
        filtered_df = df_db.copy()
        if search_query.strip():
            q = search_query.lower()
            filtered_df = filtered_df[
                filtered_df["Candidate Name"].str.lower().str.contains(q, na=False) |
                filtered_df["Extracted Skills"].str.lower().str.contains(q, na=False) |
                filtered_df["Education"].str.lower().str.contains(q, na=False) |
                filtered_df["Email"].str.lower().str.contains(q, na=False)
            ]
            
        st.markdown(f"**Showing {len(filtered_df)} of {len(df_db)} candidates in repository:**")
        st.dataframe(filtered_df, use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 📈 Built-in Visual Analytics & Pipeline Breakdown")
        
        c_ch1, c_ch2 = st.columns(2)
        with c_ch1:
            st.markdown("#### Experience Distribution")
            st.bar_chart(df_db["Experience Years"].value_counts())
            
        with c_ch2:
            st.markdown("#### Pipeline Status Breakdown")
            if "Pipeline Status" in df_db.columns:
                st.bar_chart(df_db["Pipeline Status"].value_counts())
                        
    st.markdown("</div>", unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="corp-card"><h4>🛡️ Admin Access & Employee Management</h4>', unsafe_allow_html=True)
    if st.session_state.hr_role != "Admin":
        st.warning("⚠️ Access Restricted: Only users with **Admin** role can manage company employee profiles.")
    else:
        st.success("✓ Admin privileges active.")
        
        st.markdown("### 👥 Active Employee Profiles")
        all_emps = get_all_verified_profiles()
        st.markdown(f"**Total Active Registered Employees:** {len(all_emps)}")
        for emp_email, emp_name, emp_pin, emp_role in all_emps:
            col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
            with col_a1: st.write(f"👤 **{emp_name}** ({emp_email}) — *{emp_role}*")
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
