"""
HireMatrix Pro — Enterprise Edition v9.1 (Fixed License & Payment Gateway)
========================================================================
Features: Auto-created License Tables, Live SMTP OTP, Quick PIN Setup, 
Automated Sadapay/Meezan Bank Payment Verification & Auto License Key Dispatch via Email, 
AI Interview Q&A, Kanban Pipeline, Admin Controls, and Deep LLM Screening.
"""

import io
import json
import os
import sqlite3
import hashlib
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import pandas as pd
import streamlit as st
from groq import Groq

# ===========================================================================
# CONFIGURATION & AUTH DB (WITH SECURE TABLE CREATION)
# ===========================================================================
APP_NAME = "HireMatrix Pro"
APP_TAGLINE = "Autonomous HR Intelligence & Executive Recruitment Suite"
GROQ_MODEL = "openai/gpt-oss-120b"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
DB_FILE = "master_candidates.csv"
AUTH_DB_FILE = "hr_users.db"

# Aapke official payment accounts
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
    # Check missing columns in hr_users
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

def generate_and_send_pro_license(email):
    key = f"HMPRO-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
    try:
        conn = sqlite3.connect(AUTH_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO license_keys (license_key, email, is_used) VALUES (?, ?, 0)", (key, email))
        conn.commit()
        conn.close()
        
        body = f"""
        Hello,\n\n
        Thank you for your interest in HireMatrix Pro Subscription (6,999 PKR).\n\n
        Your Exclusive Pro License Key is: {key}\n\n
        You can enter this key in your app sidebar under the Pro Subscription section to unlock all executive features instantly.\n\n
        Regards,\nTeam HireMatrix Pro Billing
        """
        send_smtp_email(email, "Your HireMatrix Pro License Key", body)
        return True, key
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
# PAGE CONFIG & STYLING
# ===========================================================================
st.set_page_config(
    page_title=f"{APP_NAME} | Executive Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

ADVANCED_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Stunning Adaptive Header */
.cyber-hero {
    background: rgba(0, 229, 255, 0.04);
    border: 1px solid rgba(0, 229, 255, 0.2);
    border-radius: 20px;
    padding: 2.2rem 2.8rem;
    margin-bottom: 2rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
    position: relative;
    overflow: hidden;
}
.cyber-hero::before {
    content: '';
    position: absolute;
    top: 0; left: 0; width: 6px; height: 100%;
    background: linear-gradient(to bottom, #00e5ff, #3b82f6, #8b5cf6);
}
.cyber-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(0, 229, 255, 0.1);
    border: 1px solid rgba(0, 229, 255, 0.3);
    color: #00838f;
    padding: 5px 14px;
    border-radius: 25px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 0.8rem;
}
.cyber-hero h1 {
    font-size: 2.3rem;
    font-weight: 800;
    letter-spacing: -0.8px;
    margin: 0;
}
.cyber-hero p {
    margin-top: 0.5rem;
    margin-bottom: 0;
    font-size: 1.05rem;
}

/* Glassmorphism Cards that adapt to Light/Dark */
.glass-card {
    background: rgba(128, 128, 128, 0.04);
    border: 1px solid rgba(128, 128, 128, 0.15);
    border-radius: 16px;
    padding: 1.6rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 25px rgba(0,0,0,0.03);
}
.glass-card h4 {
    font-size: 1.15rem;
    font-weight: 700;
    margin-bottom: 1rem;
}

/* Metric Pills */
.metric-pill {
    background: rgba(128, 128, 128, 0.06);
    border: 1px solid rgba(128, 128, 128, 0.12);
    border-radius: 14px;
    padding: 1.1rem;
    text-align: center;
}
.metric-pill .val {
    font-size: 1.7rem;
    font-weight: 800;
    color: #00838f;
}
.metric-pill .lbl {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-top: 4px;
    font-weight: 600;
}

.score-high { color: #10B981 !important; }
.score-mid { color: #F59E0B !important; }
.score-low { color: #EF4444 !important; }

/* Buttons */
.stButton>button[kind="primary"] {
    background: linear-gradient(135deg, #00e5ff 0%, #3b82f6 50%, #6366f1 100%);
    color: #FFFFFF;
    font-weight: 800;
    border-radius: 12px;
    padding: 0.65rem 1.4rem;
    border: none;
    box-shadow: 0 4px 15px rgba(0, 229, 255, 0.3);
}
</style>
"""
st.markdown(ADVANCED_CSS, unsafe_allow_html=True)

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
    st.markdown("""
        <div style="text-align: center; padding: 2.5rem 0 1rem 0;">
            <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(0,229,255,0.08); border: 1px solid rgba(0,229,255,0.3); padding: 6px 16px; border-radius: 30px; color: #00e5ff; font-size: 0.8rem; font-weight: 700; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 1px;">
                ⚡ Enterprise Automated Payment Portal (6,999 PKR / mo)
            </div>
            <h1 style="color: #FFFFFF; font-size: 2.5rem; font-weight: 800; margin: 0;">HireMatrix Pro</h1>
            <p style="color: #94A3B8; font-size: 1.1rem; margin-top: 0.5rem;">Autonomous HR Intelligence & Executive Recruitment Suite</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        saved_profiles = get_all_verified_profiles()
        
        if st.session_state.pending_pin_email:
            st.markdown('<div class="glass-card"><h4>🔐 Step 2: Create Your 4-Digit Quick PIN</h4>', unsafe_allow_html=True)
            st.info(f"Email verified for **{st.session_state.pending_pin_email}**. Secure your account with a 4-digit PIN.")
            
            new_pin = st.text_input("Enter 4-Digit PIN", type="password", max_chars=4, placeholder="••••", key="setup_pin_in")
            confirm_pin = st.text_input("Confirm 4-Digit PIN", type="password", max_chars=4, placeholder="••••", key="setup_pin_confirm")
            
            if st.button("Save PIN & Enter Portal", type="primary", use_container_width=True):
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
            st.markdown('</div>', unsafe_allow_html=True)

        elif st.session_state.pending_otp_email:
            st.markdown('<div class="glass-card"><h4>📬 Email Verification (OTP)</h4>', unsafe_allow_html=True)
            st.info(f"A 6-digit verification code has been sent to **{st.session_state.pending_otp_email}**.")
            otp_input = st.text_input("Enter 6-Digit OTP", placeholder="123456", key="reg_otp_in")
            
            col_o1, col_o2 = st.columns(2)
            with col_o1:
                if st.button("Verify OTP", type="primary", use_container_width=True):
                    success, msg = verify_otp_code(st.session_state.pending_otp_email, otp_input)
                    if success:
                        st.success(msg)
                        st.session_state.pending_pin_email = st.session_state.pending_otp_email
                        st.session_state.pending_otp_email = None
                        st.rerun()
                    else:
                        st.error(msg)
            with col_o2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.pending_otp_email = None
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        elif saved_profiles and not st.session_state.selected_profile_email:
            st.markdown('<div class="glass-card"><h4>👥 Saved Employee Profiles</h4>', unsafe_allow_html=True)
            st.caption("Select your profile card to sign in instantly:")
            
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
            st.markdown("---")
            if st.button("➕ Register New Employee Profile", use_container_width=True):
                st.session_state.selected_profile_email = "new"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        elif st.session_state.selected_profile_email and st.session_state.selected_profile_email != "new":
            target_email = st.session_state.selected_profile_email
            p_match = next((p for p in saved_profiles if p[0] == target_email), ("Employee", "", "", "Recruiter", 0))
            
            st.markdown(f'<div class="glass-card"><h4>🔐 Enter 4-Digit PIN for {p_match[1]}</h4>', unsafe_allow_html=True)
            pin_input = st.text_input("4-Digit PIN", type="password", max_chars=4, placeholder="••••", key="quick_pin_in")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("Sign In", type="primary", use_container_width=True):
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
            st.markdown('</div>', unsafe_allow_html=True)
            
        else:
            st.markdown('<div class="glass-card"><h4>📝 Step 1: Employee Registration</h4>', unsafe_allow_html=True)
            reg_name = st.text_input("Full Name", placeholder="Alex Mercer", key="r_name")
            reg_email = st.text_input("Company Email", placeholder="employee@company.com", key="r_email")
            reg_pass = st.text_input("Master Password", type="password", key="r_pass")
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                if st.button("Send Verification OTP", type="primary", use_container_width=True):
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
# DATABASE OPERATIONS
# ===========================================================================
def load_database():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if "Pipeline Status" not in df.columns:
            df["Pipeline Status"] = "Shortlisted"
            df.to_csv(DB_FILE, index=False)
        return df
    else:
        return pd.DataFrame(columns=["Job Title", "Candidate Name", "Email", "Phone", "Match Score", "Pipeline Status"])

def save_to_database(new_results):
    df = load_database()
    new_data = []
    for r in new_results:
        new_data.append({
            "Job Title": r["job_title"],
            "Candidate Name": r["name"],
            "Email": r["email"],
            "Phone": r["phone"],
            "Match Score": r["match_score"],
            "Pipeline Status": "Shortlisted"
        })
    df_new = pd.DataFrame(new_data)
    df_combined = pd.concat([df, df_new], ignore_index=True)
    df_combined.drop_duplicates(subset=['Email', 'Job Title'], keep='last', inplace=True)
    df_combined.to_csv(DB_FILE, index=False)

def update_candidate_status_in_db(email, job_title, new_status):
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df.loc[(df["Email"].str.lower() == email.lower()) & (df["Job Title"] == job_title), "Pipeline Status"] = new_status
        df.to_csv(DB_FILE, index=False)

def check_if_exists_in_db(email):
    if not os.path.exists(DB_FILE) or email in ["Not Provided", "Not Found", ""] or not email:
        return False
    df = load_database()
    return email.lower().strip() in df["Email"].str.lower().str.strip().values

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
# EXCEL EXPORT
# ===========================================================================
def dataframe_to_formatted_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Candidates")
        workbook = writer.book
        worksheet = writer.sheets["Candidates"]
        header_format = workbook.add_format({
            "bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", 
            "border": 1, "align": "center", "valign": "vcenter",
        })
        wrap_format = workbook.add_format({"text_wrap": True, "valign": "top"})
        for col_idx, col_name in enumerate(df.columns):
            worksheet.write(0, col_idx, col_name, header_format)
            width = 25 if col_name in ["Missing Skills (vs JD)", "Extracted Skills", "Latest Experience"] else 18
            worksheet.set_column(col_idx, col_idx, width, wrap_format)
        worksheet.freeze_panes(1, 0)
    buffer.seek(0)
    return buffer.getvalue()

# ===========================================================================
# SIDEBAR & DASHBOARD INTERFACE
# ===========================================================================
with st.sidebar:
    st.markdown(f"""
        <div class="sidebar-brand">
            <h3>⚡ HireMatrix Pro</h3>
            <span>Pro Edition v9.1</span>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    tier_badge = "🌟 PRO TIER (6,999 PKR/mo)" if st.session_state.is_pro == 1 else "🆓 FREE BASIC TIER"
    st.markdown(f"""
        <div class="sidebar-card">
            <div style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; margin-bottom: 4px;">Active Employee</div>
            <div style="font-size: 1rem; font-weight: 700; color: #F8FAFC;">👤 {st.session_state.hr_name}</div>
            <div style="font-size: 0.8rem; color: #00e5ff; margin-top: 4px;">{tier_badge}</div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.is_pro == 0:
        st.markdown("### 🌟 Upgrade to PRO (6,999 PKR)")
        st.info(f"Pay to our Meezan Bank / Sadapay account and get your automated Pro License Key via email instantly.")
        
        with st.expander("💳 View Bank / Sadapay Details"):
            st.markdown(f"**Meezan Bank Account:**\n- Title: `{MEEZAN_TITLE}`\n- IBAN: `{MEEZAN_IBAN}`")
            st.markdown(f"**Sadapay / JazzCash Wallet:**\n- Number: `{SADAPAY_NUMBER}`")
            st.markdown("---")
            if st.button("🤖 Request Auto-License Key", use_container_width=True):
                ok, k_or_err = generate_and_send_pro_license(st.session_state.hr_email)
                if ok:
                    st.success("Pro License Key generated & sent to your email! Check inbox.")
                else:
                    st.error(f"Error: {k_or_err}")

        license_input = st.text_input("Enter Pro License Key", type="password", placeholder="HMPRO-XXXX-XXXX")
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
        st.markdown('<div class="sidebar-card" style="border-color: rgba(16, 185, 129, 0.3); color: #10B981; font-size: 0.85rem; font-weight: 600;">✓ Groq API Secured</div>', unsafe_allow_html=True)
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

# Cyber Hero Graphic Header
st.markdown(f"""
    <div class="cyber-hero">
        <div class="cyber-badge">
            <span>🟢 Secure Employee Session</span> &bull; <span>{st.session_state.hr_email} ({'PRO' if st.session_state.is_pro == 1 else 'FREE'})</span>
        </div>
        <h1>{APP_NAME}</h1>
        <p>Welcome back, <b>{st.session_state.hr_name}</b> &mdash; {APP_TAGLINE}</p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🚀 Screening Workspace", "🗄️ Candidate Database", "🛡️ Admin Controls"])

with tab1:
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="glass-card"><h4>📋 Job Specification</h4>', unsafe_allow_html=True)
        job_title_input = st.text_input("Job Position Title", placeholder="e.g. Lead AI Engineer")
        jd_text = st.text_area("Job Description & Requirements", height=140, placeholder="Paste detailed job description here...")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="glass-card"><h4>📥 Resume Dropzone</h4>', unsafe_allow_html=True)
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
            save_to_database(results)
            st.success(f"Successfully processed {len(results)} candidate resumes!")

    # --- RESULTS DISPLAY ---
    if st.session_state.results:
        results = st.session_state.results
        
        st.markdown('<div class="glass-card"><h4>📊 Screening Metrics Overview</h4>', unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f'<div class="metric-pill"><div class="val">{len(results)}</div><div class="lbl">Total Screened</div></div>', unsafe_allow_html=True)
        with m2:
            avg_score = round(sum(r["match_score"] for r in results) / len(results), 1)
            st.markdown(f'<div class="metric-pill"><div class="val">{avg_score}%</div><div class="lbl">Average Match Score</div></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="glass-card"><h4>🧾 Ranked Candidate Insights & Pro Tools</h4>', unsafe_allow_html=True)
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
                    
                    st.markdown(f'<div class="metric-pill" style="margin-top: 15px; width: 150px;"><div class="val {score_cls}">{cand["match_score"]}%</div><div class="lbl">Match Rating</div></div>', unsafe_allow_html=True)
                
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
                        st.markdown("#### ✉️ Send Automated Interview Invite")
                        invite_msg = st.text_area("Custom Message", value=f"Dear {cand['name']},\n\nWe were deeply impressed by your resume for the {job_title_input} position at HireMatrix Pro. We would love to invite you for an interview round.\n\nBest Regards,\nTalent Acquisition Team", key=f"inv_msg_{rank}")
                        if st.button(f"📧 Send Invite Email", key=f"send_inv_{rank}"):
                            ok, res_m = send_smtp_email(cand['email'], f"Interview Invitation - {job_title_input}", invite_msg)
                            if ok:
                                st.success(f"Interview invite sent successfully to {cand['email']}!")
                                update_candidate_status_in_db(cand['email'], job_title_input, "Interview Scheduled")
                            else:
                                st.error(res_m)
                else:
                    st.warning("🔒 **Pro Feature Locked:** Upgrade to **PRO (6,999 PKR/mo)** from the sidebar to unlock AI Interview Q&A Generation and Automated Email Invites.")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="glass-card"><h4>⬇️ Master Data Export</h4>', unsafe_allow_html=True)
        df_export = load_database()
        st.download_button(
            "Download Formatted Master Report (.xlsx)",
            data=dataframe_to_formatted_excel_bytes(df_export),
            file_name=f"{job_title_input.replace(' ', '_')}_Candidates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.dataframe(df_export, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="glass-card"><h4>🗄️ Candidate Kanban Pipeline & Database</h4>', unsafe_allow_html=True)
    if st.session_state.is_pro == 0:
        st.warning("🔒 **Kanban Pipeline Locked:** Upgrade to **PRO (6,999 PKR/mo)** from the sidebar to manage candidate pipeline stages (Shortlisted, Interview Scheduled, Hired, Rejected).")
        df_history = load_database()
        if not df_history.empty:
            st.dataframe(df_history, use_container_width=True)
    else:
        try:
            df_history = load_database()
            if df_history.empty:
                st.info("Database is currently empty.")
            else:
                st.markdown("Update candidate pipeline stage below:")
                for idx, row in df_history.iterrows():
                    cols = st.columns([2, 2, 2, 2])
                    with cols[0]: st.write(f"**{row['Candidate Name']}**")
                    with cols[1]: st.write(f"*{row['Job Title']}*")
                    with cols[2]: st.write(f"Score: {row['Match Score']}%")
                    with cols[3]:
                        current_status = row["Pipeline Status"] if "Pipeline Status" in df_history.columns else "Shortlisted"
                        new_status = st.selectbox("Stage", ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"], index=["Shortlisted", "Interview Scheduled", "Hired", "Rejected"].index(current_status) if current_status in ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"] else 0, key=f"status_{idx}")
                        if new_status != current_status:
                            update_candidate_status_in_db(row['Email'], row['Job Title'], new_status)
                            st.rerun()
                st.markdown("---")
                st.dataframe(df_history, use_container_width=True)
        except Exception as e:
            st.error(f"Could not load database records: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="glass-card"><h4>🛡️ Admin Access & Employee Management</h4>', unsafe_allow_html=True)
    if st.session_state.hr_role != "Admin":
        st.warning("⚠️ Access Restricted: Only users with **Admin** role can manage company employee profiles.")
    else:
        st.success("✓ Admin privileges active.")
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
