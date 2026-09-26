"""
Super TalentMatch AI — Ultimate Advanced Creative Edition (v2.6)
========================================================================
Designed with Fully Immersive Glassmorphic Sidebar, Glowing Holographic Title, 
Advanced Card Layouts, Secure HR Login/Signup with OTP, and Deep LLM Screening.
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
import pandas as pd
import streamlit as st
from groq import Groq

# ===========================================================================
# CONFIGURATION & AUTH DB
# ===========================================================================
APP_NAME = "Super TalentMatch AI"
APP_TAGLINE = "Unified Resume Extraction & Deep LLM Screening"
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
            is_verified INTEGER DEFAULT 0,
            otp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_auth_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def send_otp_email(receiver_email, otp_code):
    try:
        sender_email = st.secrets["SMTP_EMAIL"]
        sender_password = st.secrets["SMTP_PASSWORD"]
    except Exception:
        return False, "SMTP credentials Streamlit secrets mein configure nahi hain."

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "Super TalentMatch AI - Verification OTP"
        
        body = f"""
        Hello,\n\n
        Aapka Super TalentMatch AI account verification code yeh hai:\n\n
        OTP Code: {otp_code}\n\n
        Yeh code kisi ke sath share mat karein.\n
        Regards,\nTeam TalentMatch
        """
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True, "OTP successfully email par bhej diya gaya hai!"
    except Exception as e:
        return False, f"Email bhejne mein error aaya: {e}"

def register_user(name, email, password):
    clean_email = email.lower().strip()
    otp = str(random.randint(100000, 999999))
    try:
        conn = sqlite3.connect(AUTH_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT is_verified FROM hr_users WHERE email = ?", (clean_email,))
        row = cursor.fetchone()
        
        if row:
            if row[0] == 1:
                conn.close()
                return False, "Yeh email pehle se registered aur verified hai. Baraye meherbani login karein."
            else:
                cursor.execute("UPDATE hr_users SET name = ?, password = ?, otp = ? WHERE email = ?", 
                               (name, hash_password(password), otp, clean_email))
        else:
            cursor.execute("INSERT INTO hr_users (email, name, password, is_verified, otp) VALUES (?, ?, ?, 0, ?)", 
                           (clean_email, name, hash_password(password), otp))
        conn.commit()
        conn.close()
        
        success, msg = send_otp_email(clean_email, otp)
        if success:
            return True, "Account ban gaya hai! Aapki email par OTP bhej diya gaya hai."
        else:
            return False, msg
    except Exception as e:
        return False, f"Error: {e}"

def verify_otp_code(email, entered_otp):
    conn = sqlite3.connect(AUTH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT otp FROM hr_users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    if row and row[0] == entered_otp:
        cursor.execute("UPDATE hr_users SET is_verified = 1 WHERE email = ?", (email.lower().strip(),))
        conn.commit()
        conn.close()
        return True, "Account successfully verify ho gaya hai!"
    conn.close()
    return False, "Ghalat OTP code! Dobara check karein."

def verify_user(email, password):
    conn = sqlite3.connect(AUTH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, password, is_verified FROM hr_users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        if row[2] == 0:
            return False, "Not Verified"
        if row[1] == hash_password(password):
            return True, row[0]
    return False, "Invalid"

# ===========================================================================
# PAGE CONFIG & ADVANCED CYBERPUNK STYLING
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

/* Deep Space Luxury Background */
.stApp {
    background: radial-gradient(circle at 10% 10%, rgba(10, 15, 25, 1) 0%, rgba(4, 7, 13, 1) 100%);
    color: #F8FAFC;
}

/* Stunning Cyber-Hero Header */
.cyber-hero {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.8) 100%);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(0, 229, 255, 0.15);
    border-radius: 20px;
    padding: 2.2rem 2.8rem;
    margin-bottom: 2rem;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 35px rgba(0, 229, 255, 0.04);
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
    background: rgba(0, 229, 255, 0.08);
    border: 1px solid rgba(0, 229, 255, 0.25);
    color: #00e5ff;
    padding: 5px 14px;
    border-radius: 25px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 0.8rem;
}
.cyber-hero h1 {
    color: #FFFFFF;
    font-size: 2.3rem;
    font-weight: 800;
    letter-spacing: -0.8px;
    margin: 0;
    background: linear-gradient(to right, #FFFFFF, #94A3B8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.cyber-hero p {
    color: #94A3B8;
    margin-top: 0.5rem;
    margin-bottom: 0;
    font-size: 1.05rem;
    font-weight: 400;
}

/* Glassmorphism Floating Cards */
.glass-card {
    background: rgba(26, 35, 50, 0.4);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 1.6rem;
    margin-bottom: 1.5rem;
    transition: all 0.3s ease;
    box-shadow: 0 12px 35px -10px rgba(0,0,0,0.5);
}
.glass-card:hover {
    border-color: rgba(0, 229, 255, 0.25);
    box-shadow: 0 20px 45px -12px rgba(0, 229, 255, 0.1);
}
.glass-card h4 {
    font-size: 1.15rem;
    color: #F8FAFC;
    font-weight: 700;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Glowing Metric Pill */
.metric-pill {
    background: rgba(13, 20, 32, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 1.1rem;
    text-align: center;
    box-shadow: inset 0 2px 4px rgba(255,255,255,0.02);
}
.metric-pill .val {
    font-size: 1.7rem;
    font-weight: 800;
    color: #00e5ff;
}
.metric-pill .lbl {
    font-size: 0.75rem;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-top: 4px;
    font-weight: 600;
}

/* Score Colors */
.score-high { color: #10B981 !important; text-shadow: 0 0 15px rgba(16, 185, 129, 0.3); }
.score-mid { color: #F59E0B !important; text-shadow: 0 0 15px rgba(245, 158, 11, 0.3); }
.score-low { color: #EF4444 !important; text-shadow: 0 0 15px rgba(239, 68, 68, 0.3); }

/* Futuristic Gradient Buttons */
.stButton>button[kind="primary"] {
    background: linear-gradient(135deg, #00e5ff 0%, #3b82f6 50%, #6366f1 100%);
    color: #04070D;
    font-weight: 800;
    border-radius: 12px;
    padding: 0.65rem 1.4rem;
    border: none;
    box-shadow: 0 6px 20px rgba(0, 229, 255, 0.35);
    transition: all 0.25s ease;
}
.stButton>button[kind="primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(0, 229, 255, 0.55);
    color: #04070D;
}

/* Advanced Glassmorphic Sidebar Styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(8, 12, 20, 0.95) 0%, rgba(4, 7, 13, 0.98) 100%);
    border-right: 1px solid rgba(0, 229, 255, 0.1);
}
[data-testid="stSidebar"] .stMarkdown {
    color: #CBD5E1;
}
.sidebar-card {
    background: rgba(20, 30, 48, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 1.2rem;
    margin-bottom: 1.2rem;
    backdrop-filter: blur(10px);
}
/* Holographic Sidebar Brand Header */
.sidebar-brand {
    background: linear-gradient(135deg, rgba(0, 229, 255, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%);
    border: 1px solid rgba(0, 229, 255, 0.25);
    border-radius: 14px;
    padding: 1.2rem 1rem;
    text-align: center;
    margin-bottom: 1rem;
    box-shadow: 0 0 20px rgba(0, 229, 255, 0.05);
}
.sidebar-brand h3 {
    color: #00e5ff;
    font-size: 1.25rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
    text-shadow: 0 0 10px rgba(0, 229, 255, 0.4);
}
.sidebar-brand span {
    font-size: 0.65rem;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 700;
    display: block;
    margin-top: 4px;
}
</style>
"""
st.markdown(ADVANCED_CSS, unsafe_allow_html=True)

# ===========================================================================
# SESSION STATE MANAGEMENT
# ===========================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "hr_name" not in st.session_state:
    st.session_state.hr_name = ""
if "pending_verification_email" not in st.session_state:
    st.session_state.pending_verification_email = None
if "results" not in st.session_state:
    st.session_state.results = []

# ===========================================================================
# AUTHENTICATION SCREEN
# ===========================================================================
if not st.session_state.logged_in:
    st.markdown("""
        <div style="text-align: center; padding: 3.5rem 0 1.5rem 0;">
            <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(0,229,255,0.08); border: 1px solid rgba(0,229,255,0.3); padding: 6px 16px; border-radius: 30px; color: #00e5ff; font-size: 0.8rem; font-weight: 700; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 1px;">
                ⚡ Autonomous Executive HR Suite
            </div>
            <h1 style="color: #FFFFFF; font-size: 2.6rem; font-weight: 800; letter-spacing: -1px; margin: 0;">Super TalentMatch AI</h1>
            <p style="color: #94A3B8; font-size: 1.15rem; margin-top: 0.6rem;">Next-Generation Deep LLM Resume Screening & Extraction Engine</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.35, 1])
    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        if st.session_state.pending_verification_email:
            st.markdown("### 🔐 Verify Email OTP")
            st.info(f"Verification code has been sent to **{st.session_state.pending_verification_email}**")
            otp_input = st.text_input("Enter 6-Digit OTP", placeholder="123456", key="otp_code_in")
            
            if st.button("Verify & Enter Portal", type="primary", use_container_width=True):
                success, msg = verify_otp_code(st.session_state.pending_verification_email, otp_input)
                if success:
                    st.success(msg)
                    st.session_state.pending_verification_email = None
                    st.rerun()
                else:
                    st.error(msg)
            if st.button("Cancel & Go Back", use_container_width=True):
                st.session_state.pending_verification_email = None
                st.rerun()
        else:
            auth_tab1, auth_tab2 = st.tabs(["✨ HR Login", "🚀 Create Account"])
            
            with auth_tab1:
                st.markdown("#### Manager Sign In")
                login_email = st.text_input("Work Email", placeholder="alex@company.com", key="l_email")
                login_pass = st.text_input("Password", type="password", key="l_pass")
                
                if st.button("Access Portal", type="primary", use_container_width=True):
                    success, res_val = verify_user(login_email, login_pass)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.hr_name = res_val
                        st.success(f"Welcome back, {res_val}!")
                        st.rerun()
                    elif res_val == "Not Verified":
                        st.warning("Account pending verification. Enter OTP.")
                        st.session_state.pending_verification_email = login_email
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Please check email/password.")
                        
            with auth_tab2:
                st.markdown("#### New HR Registration")
                reg_name = st.text_input("Full Name", placeholder="Alex Mercer", key="r_name")
                reg_email = st.text_input("Work Email", placeholder="alex@company.com", key="r_email")
                reg_pass = st.text_input("Create Password", type="password", key="r_pass")
                
                if st.button("Register & Send OTP", type="primary", use_container_width=True):
                    if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                        st.warning("Please fill in all required fields.")
                    else:
                        success, msg = register_user(reg_name, reg_email, reg_pass)
                        if success:
                            st.success(msg)
                            st.session_state.pending_verification_email = reg_email.lower().strip()
                            st.rerun()
                        else:
                            st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ===========================================================================
# DATABASE OPERATIONS (Local CSV for Candidates)
# ===========================================================================
def load_database():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    else:
        return pd.DataFrame(columns=["Job Title", "Candidate Name", "Email", "Phone", "Match Score"])

def save_to_database(new_results):
    df = load_database()
    new_data = []
    for r in new_results:
        new_data.append({
            "Job Title": r["job_title"],
            "Candidate Name": r["name"],
            "Email": r["email"],
            "Phone": r["phone"],
            "Match Score": r["match_score"]
        })
    df_new = pd.DataFrame(new_data)
    df_combined = pd.concat([df, df_new], ignore_index=True)
    df_combined.drop_duplicates(subset=['Email', 'Job Title'], keep='last', inplace=True)
    df_combined.to_csv(DB_FILE, index=False)

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
# GROQ API INTEGRATION
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

# ===========================================================================
# EXCEL EXPORT
# ===========================================================================
def build_results_dataframe(results: list) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "Job Title": r["job_title"],
            "Match Score (%)": r["match_score"],
            "Candidate Name": r["name"],
            "Father Name": r["father_name"],
            "Email": r["email"],
            "Phone": r["phone"],
            "CGPA": r["cgpa"],
            "Education": r["education"],
            "University Name": r["university_name"],
            "Experience Years": r["experience_years"],
            "Latest Experience": r["latest_experience"],
            "Extracted Skills": r["skills"],
            "Reference": r["reference"],
            "Missing Skills (vs JD)": "; ".join(r.get("missing_skills", [])) or "None",
            "History Status": "Old Candidate (Already in DB)" if r["is_duplicate"] else "New Candidate",
            "Source File": r["file_name"],
        })
    return pd.DataFrame(rows).sort_values("Match Score (%)", ascending=False).reset_index(drop=True)

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
# ADVANCED GLASSMORPHIC SIDEBAR & DASHBOARD INTERFACE
# ===========================================================================
with st.sidebar:
    st.markdown("""
        <div class="sidebar-brand">
            <h3>⚡ TalentMatch AI</h3>
            <span>Executive HR Suite v2.6</span>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown(f"""
        <div class="sidebar-card">
            <div style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; margin-bottom: 4px;">Active Session</div>
            <div style="font-size: 1rem; font-weight: 700; color: #F8FAFC;">👤 {st.session_state.hr_name}</div>
        </div>
    """, unsafe_allow_html=True)
    
    if "GROQ_API_KEY" in st.secrets:
        groq_api_key = st.secrets["GROQ_API_KEY"]
        st.markdown('<div class="sidebar-card" style="border-color: rgba(16, 185, 129, 0.3); color: #10B981; font-size: 0.85rem; font-weight: 600;">✓ Groq API Secured</div>', unsafe_allow_html=True)
    else:
        groq_api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    
    st.markdown("---")
    if st.button("🗑️ Clear Session Cache", use_container_width=True):
        st.session_state.results = []
        st.rerun()
        
    if st.button("🚪 Secure Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.results = []
        st.rerun()

# Cyber Hero Graphic Header
st.markdown(f"""
    <div class="cyber-hero">
        <div class="cyber-badge">
            <span>🟢 System Operational</span> &bull; <span>Secure Session Active</span>
        </div>
        <h1>{APP_NAME}</h1>
        <p>Welcome back, <b>{st.session_state.hr_name}</b> &mdash; {APP_TAGLINE}</p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🚀 Screening Workspace", "🗄️ Candidate Database"])

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

        st.markdown('<div class="glass-card"><h4>🧾 Ranked Candidate Insights</h4>', unsafe_allow_html=True)
        results = sorted(results, key=lambda x: x["match_score"], reverse=True)
        
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
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="glass-card"><h4>⬇️ Master Data Export</h4>', unsafe_allow_html=True)
        df = build_results_dataframe(results)
        st.download_button(
            "Download Formatted Master Report (.xlsx)",
            data=dataframe_to_formatted_excel_bytes(df),
            file_name=f"{job_title_input.replace(' ', '_')}_Candidates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.dataframe(df, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="glass-card"><h4>🗄️ Master Candidate Database Repository</h4>', unsafe_allow_html=True)
    try:
        df_history = load_database()
        if df_history.empty:
            st.info("Database is currently empty.")
        else:
            st.dataframe(df_history, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load database records: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
