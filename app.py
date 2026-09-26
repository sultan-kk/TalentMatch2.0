"""
HireMatrix Pro — Enterprise Edition v10.65 (Unique Sheet Name Fix)
========================================================================
Features: Fixed duplicate worksheet name errors in Excel exports, persistent same-file master Excel appends, 
Clean numbered exports, individual candidate deletes, strict duplicate blocking, and complete ATS workflow.
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
# DATABASE OPERATIONS & SAFE EXCEL EXPORTS
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
        
        if not df.empty and "Email" in df.columns:
            df["CleanEmail"] = df["Email"].astype(str).str.lower().str.strip()
            valid_mask = ~df["CleanEmail"].isin(["not provided", "not found", "nan", ""])
            df_valid = df[valid_mask].drop_duplicates(subset=["CleanEmail"], keep="first")
            df_invalid = df[~valid_mask]
            df = pd.concat([df_valid, df_invalid], ignore_index=True).drop(columns=["CleanEmail"])
            df.to_csv(DB_FILE, index=False)
            
        return df
    else:
        return pd.DataFrame(columns=[
            "Candidate Name", "Father Name", "Email", "Phone", 
            "CGPA", "Education", "University Name", "Experience Years", 
            "Latest Experience", "Extracted Skills", "Reference", "Pipeline Status", "Added At"
        ])

def check_if_exists_in_db(email):
    if not os.path.exists(DB_FILE) or email in ["Not Provided", "Not Found", ""] or not email:
        return False
    df = load_database()
    clean_in = email.lower().strip()
    if "Email" not in df.columns:
        return False
    existing_emails = df["Email"].astype(str).str.lower().str.strip().values
    return clean_in in existing_emails

def save_candidates_to_repository(new_candidates):
    df = load_database()
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_data = []
    
    for c in new_candidates:
        email = str(c.get("email", "Not Provided")).lower().strip()
        if email not in ["not provided", "not found", "", "nan"] and check_if_exists_in_db(email):
            continue
            
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
        
    if new_data:
        df_new = pd.DataFrame(new_data)
        df_combined = pd.concat([df, df_new], ignore_index=True)
        if "Email" in df_combined.columns:
            df_combined["CleanEmail"] = df_combined["Email"].astype(str).str.lower().str.strip()
            valid_mask = ~df_combined["CleanEmail"].isin(["not provided", "not found", "nan", ""])
            df_v = df_combined[valid_mask].drop_duplicates(subset=["CleanEmail"], keep="first")
            df_inv = df_combined[~valid_mask]
            df_combined = pd.concat([df_v, df_inv], ignore_index=True).drop(columns=["CleanEmail"])
        df_combined.to_csv(DB_FILE, index=False)

def delete_single_candidate_from_db(email_or_name):
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df = df[~(df["Email"].astype(str).str.lower().str.strip() == str(email_or_name).lower().strip()) & 
                ~(df["Candidate Name"].astype(str).str.lower().str.strip() == str(email_or_name).lower().strip())]
        df.to_csv(DB_FILE, index=False)

def update_candidate_pipeline_status(email, new_status):
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df.loc[df["Email"].str.lower() == email.lower(), "Pipeline Status"] = new_status
        df.to_csv(DB_FILE, index=False)

def clear_candidate_database():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def generate_repository_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        export_df = df.copy()
        if "Job Title" in export_df.columns:
            export_df = export_df.drop(columns=["Job Title"])
        export_df.insert(0, "Sr. No.", range(1, len(export_df) + 1))
        
        export_df.to_excel(writer, index=False, sheet_name="Talent_Repository")
        workbook = writer.book
        worksheet = writer.sheets["Talent_Repository"]
        
        header_format = workbook.add_format({
            "bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", "border": 1, "align": "center", "valign": "vcenter",
        })
        wrap_format = workbook.add_format({"text_wrap": True, "valign": "top", "border": 1})
        
        for col_idx, col_name in enumerate(export_df.columns):
            worksheet.write(0, col_idx, col_name, header_format)
            if col_name == "Sr. No.": worksheet.set_column(col_idx, col_idx, 10, wrap_format)
            elif col_name in ["Extracted Skills", "Latest Experience", "University Name"]: worksheet.set_column(col_idx, col_idx, 30, wrap_format)
            else: worksheet.set_column(col_idx, col_idx, 18, wrap_format)
        worksheet.freeze_panes(1, 0)
    buffer.seek(0)
    return buffer.getvalue()

def generate_screening_excel(results_list) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        data = []
        for idx, r in enumerate(results_list, start=1):
            data.append({
                "Sr. No.": idx,
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
                "Match Score (%)": r["match_score"],
                "Pipeline Status": r["pipeline_status"]
            })
        export_df = pd.DataFrame(data)
        export_df.to_excel(writer, index=False, sheet_name="Screened_Results")
        workbook = writer.book
        worksheet = writer.sheets["Screened_Results"]
        
        header_format = workbook.add_format({
            "bold": True, "bg_color": "#0EA5E9", "font_color": "#FFFFFF", "border": 1, "align": "center", "valign": "vcenter",
        })
        wrap_format = workbook.add_format({"text_wrap": True, "valign": "top", "border": 1})
        
        for col_idx, col_name in enumerate(export_df.columns):
            worksheet.write(0, col_idx, col_name, header_format)
            if col_name == "Sr. No.": worksheet.set_column(col_idx, col_idx, 10, wrap_format)
            elif col_name in ["Extracted Skills", "Latest Experience", "University Name"]: worksheet.set_column(col_idx, col_idx, 30, wrap_format)
            else: worksheet.set_column(col_idx, col_idx, 18, wrap_format)
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
    return f"""You are an expert HR recruiter AI. Evaluate the CANDIDATE PROFILE against the JOB DESCRIPTION. Determine if the candidate is relevant to the job description (e.g. matching domain, background, or skills).

CANDIDATE PROFILE SUMMARY:
{candidate_text_summary}

JOB DESCRIPTION:
{jd_text}

Return ONLY a valid JSON object with exactly the following keys. Do not include markdown fences.
{{
  "match_score": A number between 0 and 100 representing how well the candidate matches the JD,
  "is_relevant": true if the candidate has at least basic or moderate relevance to the job domain/requirements, otherwise false,
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
            "reference": result.get("reference", "Not Provided")
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
        return float(result.get("match_score", 0)), bool(result.get("is_relevant", True)), result.get("missing_skills", [])
    except Exception:
        return 0.0, True, []

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
            <p>Multi-Stage ATS v10.65</p>
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
            st.success(f"Successfully processed and added candidates to the Talent Pool (Duplicates automatically blocked & appended to Master file)!")
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    df_repo = load_database()
    if not df_repo.empty:
        st.markdown('<div class="corp-card"><h4>📋 Current Candidates in Talent Repository (Manage & Delete)</h4>', unsafe_allow_html=True)
        
        st.download_button(
            "📊 Download Master Talent Repository Report (.xlsx)",
            data=generate_repository_excel(df_repo),
            file_name="Master_Talent_Repository.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.markdown("---")
        
        for idx, row in df_repo.iterrows():
            c_d1, c_d2, c_d3, c_d4 = st.columns([2, 2, 2, 1])
            with c_d1: st.write(f"👤 **{row['Candidate Name']}**")
            with c_d2: st.write(f"✉️ `{row['Email']}`")
            with c_d3: st.write(f"🎓 {row['Education']}")
            with c_d4:
                safe_key = f"del_repo_{idx}_{str(row['Email']).replace('@', '_').replace('.', '_')}"
                if st.button("🗑️ Delete", key=safe_key, use_container_width=True):
                    delete_single_candidate_from_db(row['Email'] if row['Email'] not in ["Not Provided", "Not Found", ""] else row['Candidate Name'])
                    st.success(f"Removed {row['Candidate Name']} from repository!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening & Smart Matching</h4>', unsafe_allow_html=True)
    st.caption("Enter a Job Description below. AI will scan your stored Talent Pool repository, filter strictly for candidates relevant to this JD, and display them.")
    
    jd_title_input = st.text_input("Job Position Title", placeholder="e.g. Senior Human Resources Manager")
    jd_desc_text = st.text_area("Job Description & Requirements", height=120, placeholder="Paste detailed job description here...")
    
    st.markdown("---")
    st.markdown("**🎯 Select Minimum Passing Score Threshold (%)**")
    screening_threshold = st.slider(
        "Candidates scoring above this will be highlighted; all JD-relevant candidates remain reviewable.",
        min_value=0, max_value=100, value=50, step=5,
        label_visibility="collapsed",
        key="screening_threshold_slider"
    )
    st.caption(f"Current Highlight Threshold: **{screening_threshold}%**")
    
    df_pool = load_database()
    
    if st.button("⚡ Run AI Screening against Talent Pool", type="primary", use_container_width=True, disabled=not (jd_desc_text.strip() and jd_title_input.strip() and not df_pool.empty and groq_api_key)):
        client = Groq(api_key=groq_api_key)
        screened_results = []
        progress = st.progress(0.0, text="Evaluating candidates against Job Description...")
        
        for idx, row in df_pool.iterrows():
            progress.progress((idx + 1) / (len(df_pool) + 1), text=f"Evaluating {row['Candidate Name']}...")
            score, is_relevant, missing = evaluate_candidate_against_jd(client, row, jd_desc_text)
            
            if is_relevant:
                initial_status = "Shortlisted" if score >= screening_threshold else row.get("Pipeline Status", "Talent Pool")
                
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
        st.success(f"Screening complete! Found {len(screened_results)} JD-relevant candidates.")
        st.rerun()
        
    if df_pool.empty:
        st.info("⚠️ Talent repository is currently empty. Please upload resumes in **Step 1** first.")
        
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.screening_results:
        st.markdown('<div class="corp-card"><h4>📊 JD-Relevant Candidates & Recruiter Decision Pipeline</h4>', unsafe_allow_html=True)
        results = sorted(st.session_state.screening_results, key=lambda x: x["match_score"], reverse=True)
        
        if not results:
            st.warning("⚠️ No candidates in the repository matched the requirements of this Job Description.")
        else:
            st.download_button(
                "📊 Download Master Screened Candidates Report (.xlsx)",
                data=generate_screening_excel(results),
                file_name="Master_Screened_Candidates_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.markdown("---")
        
        client = Groq(api_key=groq_api_key) if groq_api_key else None

        for rank, cand in enumerate(results, start=1):
            score_cls = "score-high" if cand["match_score"] >= 75 else ("score-mid" if cand["match_score"] >= 40 else "score-low")
            
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
                st.markdown("#### 🔄 Recruiter Decision & Pipeline Stage")
                stage_options = ["Shortlisted", "Interview Scheduled", "Hired", "Rejected"]
                current_stage = cand["pipeline_status"]
                stage_idx = stage_options.index(current_stage) if current_stage in stage_options else 0
                
                stage_key = f"stage_sel_{rank}_{str(cand['email']).replace('@', '_').replace('.', '_')}"
                new_stage = st.selectbox(
                    "Update Stage", 
                    stage_options, 
                    index=stage_idx,
                    key=stage_key
                )
                if new_stage != cand["pipeline_status"]:
                    cand["pipeline_status"] = new_stage
                    update_candidate_pipeline_status(cand["email"], new_stage)
                    st.success(f"Pipeline stage updated to **{new_stage}**!")
                    st.rerun()

                st.markdown("---")
                q_key = f"gen_q_{rank}_{str(cand['email']).replace('@', '_').replace('.', '_')}"
                if st.button(f"💡 Generate AI Interview Q&A for {cand['name']}", key=q_key):
                    if client:
                        with st.spinner("Generating tailored interview questions..."):
                            q_text = generate_ai_interview_questions(client, cand['skills'], cand['job_title'])
                            st.markdown("#### 🎯 AI Generated Interview Guide:")
                            st.markdown(q_text)
                    else:
                        st.error("Groq API key required.")

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

                    msg_key = f"inv_msg_{rank}_{str(cand['email']).replace('@', '_').replace('.', '_')}"
                    invite_msg = st.text_area("Email Message", value=default_msg, key=msg_key)
                    
                    send_key = f"send_inv_{rank}_{str(cand['email']).replace('@', '_').replace('.', '_')}"
                    if st.button(f"📧 Send Email to {cand['name']}", key=send_key):
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
        "📊 Download Master Talent Repository Report (.xlsx)",
        data=generate_repository_excel(df_export),
        file_name="Master_Talent_Repository.xlsx",
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
