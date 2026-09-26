"""
Super TalentMatch AI — Unified HR Screener & Extractor with Real Email OTP
========================================================================
Professional Edition: Secure HR Login/Signup with Live Email OTP Verification, 
Adaptive UI, Precise Data Extraction, Local Database, and Deep LLM Screening.
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
# PAGE CONFIG & CSS
# ===========================================================================
st.set_page_config(
    page_title=f"{APP_NAME} | HR Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
html, body, [class*="css"] {font-family: "Segoe UI", Roboto, sans-serif; font-size: 15px;}
.tm-header {padding: 1.5rem 2rem; border-radius: 8px; margin-bottom: 1.5rem; background: #1A202C; border-left: 6px solid #3182CE;}
.tm-header h1 { color: #FFFFFF; font-size: 1.7rem; font-weight: 600; margin: 0;}
.tm-header p { color: #A0AEC0; margin-top: 0.3rem; margin-bottom: 0; font-size: 0.95rem;}
.tm-card {background: var(--background-color); border: 1px solid var(--faded-text-20); border-radius: 8px; padding: 1.2rem 1.5rem; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);}
.tm-card h4 { font-size: 1.1rem; color: var(--text-color); font-weight: 600; margin-bottom: 1rem;}
.tm-metric-box {background: var(--secondary-background-color); border-radius: 6px; padding: 0.8rem; text-align: center; border: 1px solid var(--faded-text-20);}
.tm-metric-box .tm-value { font-size: 1.4rem; font-weight: 700; color: var(--text-color);}
.tm-metric-box .tm-label { font-size: 0.75rem; color: var(--text-color); text-transform: uppercase; opacity: 0.8;}
.tm-score-high { color: #38A169; }
.tm-score-mid { color: #DD6B20; }
.tm-score-low { color: #E53E3E; }
.stButton>button[kind="primary"] {background: #3182CE; color: #fff; font-weight: 600; border-radius: 6px; padding: 0.5rem 1rem;}
.stButton>button[kind="primary"]:hover { background: #2B6CB0; color: white;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

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
# AUTHENTICATION SCREEN (IF NOT LOGGED IN)
# ===========================================================================
if not st.session_state.logged_in:
    st.markdown("""
        <div style="text-align: center; padding: 2rem 0 1rem 0;">
            <h1 style="color: #00e5ff; font-size: 2.2rem;">⚡ Super TalentMatch AI</h1>
            <p style="color: #A0AEC0; font-size: 1.1rem;">HR Portal - Secure Login & Live Email OTP</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        if st.session_state.pending_verification_email:
            st.markdown("### Enter Email Verification Code")
            st.info(f"OTP code aapki email ({st.session_state.pending_verification_email}) par bhej diya gaya hai.")
            otp_input = st.text_input("6-Digit OTP Code", placeholder="123456", key="otp_code_in")
            
            if st.button("Verify OTP", type="primary", use_container_width=True):
                success, msg = verify_otp_code(st.session_state.pending_verification_email, otp_input)
                if success:
                    st.success(msg)
                    st.session_state.pending_verification_email = None
                    st.rerun()
                else:
                    st.error(msg)
            if st.button("Cancel / Back", use_container_width=True):
                st.session_state.pending_verification_email = None
                st.rerun()
        else:
            auth_tab1, auth_tab2 = st.tabs(["🔑 HR Login", "📝 Create Account (Sign Up)"])
            
            with auth_tab1:
                st.markdown("### Login to Dashboard")
                login_email = st.text_input("Work Email", placeholder="hr@company.com", key="l_email")
                login_pass = st.text_input("Password", type="password", key="l_pass")
                
                if st.button("Login", type="primary", use_container_width=True):
                    success, res_val = verify_user(login_email, login_pass)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.hr_name = res_val
                        st.success(f"Khush amdeed, {res_val}!")
                        st.rerun()
                    elif res_val == "Not Verified":
                        st.warning("Aapka account verify nahi hai. Baraye meherbani OTP enter karein.")
                        st.session_state.pending_verification_email = login_email
                        st.rerun()
                    else:
                        st.error("Ghalat Email ya Password!")
                        
            with auth_tab2:
                st.markdown("### Register New HR Account")
                reg_name = st.text_input("Full Name", placeholder="Muhammad Sultan", key="r_name")
                reg_email = st.text_input("Work Email", placeholder="hr@company.com", key="r_email")
                reg_pass = st.text_input("Create Password", type="password", key="r_pass")
                
                if st.button("Sign Up & Send OTP", type="primary", use_container_width=True):
                    if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                        st.warning("Baraye meherbani tamam fields pur karein.")
                    else:
                        success, msg = register_user(reg_name, reg_email, reg_pass)
                        if success:
                            st.success(msg)
                            st.session_state.pending_verification_email = reg_email.lower().strip()
                            st.rerun()
                        else:
                            st.error(msg)
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
            "bold": True, "bg_color": "#2D3748", "font_color": "#FFFFFF", 
            "border": 1, "align": "center", "valign": "vcenter",
        })
        wrap_format = workbook.add_format({"text_wrap": True, "valign": "top"})
        
        for col_idx, col_name in enumerate(df.columns):
            worksheet.write(0, col_idx, col_name, header_format)
            width = 20
            if col_name in ["Missing Skills (vs JD)", "Extracted Skills", "Latest Experience", "University Name"]:
                width = 40
            elif col_name in ["Match Score (%)", "CGPA", "History Status"]:
                width = 15
            worksheet.set_column(col_idx, col_idx, width, wrap_format)
        worksheet.freeze_panes(1, 0)
    buffer.seek(0)
    return buffer.getvalue()

# ===========================================================================
# DASHBOARD INTERFACE (IF LOGGED IN)
# ===========================================================================
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 10px;">
            <h2 style="color: #00e5ff; margin-bottom: 0px;">⚡ Super TalentMatch AI</h2>
            <p style="color: #888888; font-size: 12px;">Unified Resume Extraction & Deep LLM Screening</p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    st.info(f"👤 **HR Manager:** {st.session_state.hr_name}")
    
    if "GROQ_API_KEY" in st.secrets:
        groq_api_key = st.secrets["GROQ_API_KEY"]
        st.success("✓ Groq API key loaded.")
    else:
        groq_api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    
    st.markdown("---")
    if st.button("🗑️ Clear Session Results", use_container_width=True):
        st.session_state.results = []
        st.rerun()
        
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.results = []
        st.rerun()

st.markdown(f'<div class="tm-header"><h1>{APP_NAME}</h1><p>Welcome back, {st.session_state.hr_name} | {APP_TAGLINE}</p></div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🚀 New Processing", "🗄️ Database Records"])

with tab1:
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="tm-card"><h4>📋 Job Setup</h4>', unsafe_allow_html=True)
        job_title_input = st.text_input("Job Title / Position Name", placeholder="e.g. Senior Python Developer")
        jd_text = st.text_area("Job Description", height=130, placeholder="Paste Job Description here...")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="tm-card"><h4>📥 Upload Resumes</h4>', unsafe_allow_html=True)
        uploaded_files = st.file_uploader("Upload resumes", type=ACCEPTED_TYPES, accept_multiple_files=True, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 Process & Screen Candidates", type="primary", use_container_width=True, disabled=not (uploaded_files and jd_text.strip() and job_title_input.strip() and groq_api_key)):
        client = Groq(api_key=groq_api_key)
        results = []
        progress = st.progress(0.0, text="Initializing...")
        
        for i, file in enumerate(uploaded_files):
            progress.progress((i + 1) / (len(uploaded_files) + 1), text=f"Processing {file.name}...")
            text = extract_resume_text(file)
            if text:
                analysis = analyze_and_extract_with_groq(client, text, jd_text, job_title_input, file.name)
                if analysis:
                    results.append(analysis)
                    
        progress.empty()
        st.session_state.results = results
        if results:
            save_to_database(results)
            st.success(f"Successfully processed {len(results)} candidates and saved records!")

    # --- DISPLAY RESULTS ---
    if st.session_state.results:
        results = st.session_state.results
        st.markdown('<div class="tm-card"><h4>📊 Screening Overview</h4>', unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        m1.metric("Total Candidates Processed", len(results))
        avg_score = round(sum(r["match_score"] for r in results) / len(results), 1)
        m2.metric("Average Match Score", f"{avg_score}%")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="tm-card"><h4>🧾 Candidate Details & Rankings</h4>', unsafe_allow_html=True)
        results = sorted(results, key=lambda x: x["match_score"], reverse=True)
        
        for rank, cand in enumerate(results, start=1):
            history_badge = " ⚠️ (Previously Saved)" if cand["is_duplicate"] else " 🆕 (New Candidate)"
            with st.expander(f"#{rank} — {cand['name']} | Score: {cand['match_score']}%{history_badge}", expanded=(rank == 1)):
                c1, c2 = st.columns([1.2, 1])
                with c1:
                    st.markdown(f"**✉️ Email:** {cand['email']} | **📞 Phone:** {cand['phone']}")
                    st.markdown(f"**👤 Father's Name:** {cand['father_name']}")
                    st.markdown(f"**🎓 Education:** {cand['education']} (CGPA: {cand['cgpa']})")
                    st.markdown(f"**🏫 University:** {cand['university_name']}")
                    st.markdown(f"**💼 Experience:** {cand['experience_years']} | **Latest:** {cand['latest_experience']}")
                    st.markdown(f"**🔗 Reference:** {cand['reference']}")
                    st.markdown(f"**🛠️ Skills:** {cand['skills']}")
                    
                    score_class = "tm-score-high" if cand["match_score"] >= 75 else ("tm-score-mid" if cand["match_score"] >= 50 else "tm-score-low")
                    st.markdown(f'<div class="tm-metric-box" style="margin-top: 15px; width: 160px;"><div class="tm-value {score_class}">{cand["match_score"]}%</div><div class="tm-label">Match Score</div></div>', unsafe_allow_html=True)
                
                with c2:
                    st.markdown("**❌ Missing Skills (vs. JD):**")
                    if cand["missing_skills"]:
                        for skill in cand["missing_skills"]:
                            st.markdown(f"- {skill}")
                    else:
                        st.caption("No significant gaps identified.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="tm-card"><h4>⬇️ Export Master Sheet</h4>', unsafe_allow_html=True)
        df = build_results_dataframe(results)
        st.download_button(
            "Download Formatted Excel (.xlsx)",
            data=dataframe_to_formatted_excel_bytes(df),
            file_name=f"{job_title_input.replace(' ', '_')}_Candidates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.dataframe(df, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="tm-card"><h4>🗄️ All Saved Candidates (Database)</h4>', unsafe_allow_html=True)
    try:
        df_history = load_database()
        if df_history.empty:
            st.info("No candidates saved in the database yet.")
        else:
            st.dataframe(df_history, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load history: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
