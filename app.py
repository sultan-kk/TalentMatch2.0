"""
HireMatrix Pro — Enterprise Edition v11.7 (Cyber-Neon Holographic Executive UI)
========================================================================
Features: High-tech Cyberpunk/Neon Executive Cards, Glowing Glassmorphism, 
Dual-Pass OCR for colored resumes, and full Supabase cloud integration.
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
from PIL import Image, ImageOps, ImageEnhance

# ===========================================================================
# 1. PAGE CONFIGURATION
# ===========================================================================
APP_NAME = "HireMatrix Pro"
APP_TAGLINE = "Autonomous HR Intelligence & Executive Recruitment Suite"
GROQ_MODEL = "openai/gpt-oss-120b"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]

st.set_page_config(
    page_title=f"{APP_NAME} | Executive Portal",
    page_icon="💼",
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
        st.error(f"⚠️ Supabase Connection Error: Please verify SUPABASE_URL and SUPABASE_KEY in Streamlit Secrets. Details: {e}")
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

def verify_employee_pin(email, entered_pin):
    clean_email = email.lower().strip()
    if not supabase:
        return False, None, None
    try:
        response = supabase.table("hr_users").select("name, pin, role").eq("email", clean_email).eq("is_verified", 1).execute()
        rows = response.data
        if rows and rows[0].get("pin") == entered_pin:
            return True, rows[0]["name"], rows[0]["role"]
    except Exception:
        pass
    return False, None, None

def get_all_verified_profiles():
    if not supabase:
        return []
    try:
        response = supabase.table("hr_users").select("email, name, pin, role").eq("is_verified", 1).not_.is_("pin", "null").execute()
        return [(r["email"], r["name"], r["pin"], r["role"]) for r in response.data]
    except Exception:
        return []

def get_all_verified_profiles_admin():
    return get_all_verified_profiles()

def register_initial_employee(name, email, password):
    clean_email = email.lower().strip()
    otp = str(random.randint(100000, 999999))
    if not supabase:
        return False, "Supabase client not initialized."
    try:
        existing = supabase.table("hr_users").select("is_verified, pin").eq("email", clean_email).execute().data
        if existing and existing[0].get("is_verified") == 1 and existing[0].get("pin"):
            return False, "This email is already registered and active. Please sign in."
        
        count_res = supabase.table("hr_users").select("email", count="exact").eq("is_verified", 1).execute()
        count = count_res.count if count_res.count is not None else 0
        role = "Admin" if count == 0 else "Recruiter"
        
        data = {
            "email": clean_email,
            "name": name,
            "password": hash_password(password),
            "pin": None,
            "role": role,
            "is_verified": 0,
            "otp": otp
        }
        supabase.table("hr_users").upsert(data).execute()
        
        success, msg = send_smtp_email(clean_email, "HireMatrix Pro - Verification OTP", f"Your verification code is: {otp}")
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
    try:
        supabase.table("hr_users").update({"pin": pin, "is_verified": 1}).eq("email", email.lower().strip()).execute()
        return True, "Admin & Employee PIN configured successfully!"
    except Exception as e:
        return False, f"Error: {e}"

def delete_employee_profile(email):
    if not supabase:
        return False, "Supabase client not initialized."
    try:
        supabase.table("hr_users").delete().eq("email", email.lower().strip()).execute()
        return True, "Employee profile successfully removed."
    except Exception as e:
        return False, f"Error: {e}"

# ===========================================================================
# 3. CANDIDATE REPOSITORY STORAGE (SUPABASE)
# ===========================================================================
def load_database():
    expected_cols = [
        "Candidate Name", "Father Name", "Email", "Phone", 
        "CGPA", "Education", "University Name", "Experience Years", 
        "Latest Experience", "Reference", "Pipeline Status", "Added At"
    ]
    if not supabase:
        return pd.DataFrame(columns=expected_cols)
    try:
        response = supabase.table("candidates").select("*").execute()
        rows = response.data
        if rows:
            mapped_rows = []
            for r in rows:
                mapped_rows.append({
                    "Candidate Name": r.get("candidate_name", "Not Provided"),
                    "Father Name": r.get("father_name", "Not Provided"),
                    "Email": r.get("email", "Not Provided"),
                    "Phone": r.get("phone", "Not Provided"),
                    "CGPA": r.get("cgpa", "Not Provided"),
                    "Education": r.get("education", "Not Provided"),
                    "University Name": r.get("university_name", "Not Provided"),
                    "Experience Years": r.get("experience_years", "0"),
                    "Latest Experience": r.get("latest_experience", "Not Provided"),
                    "Reference": r.get("reference", "Not Provided"),
                    "Pipeline Status": r.get("pipeline_status", "Talent Pool"),
                    "Added At": r.get("added_at", str(datetime.now()))
                })
            return pd.DataFrame(mapped_rows)
    except Exception:
        pass
    return pd.DataFrame(columns=expected_cols)

def check_if_exists_in_db(email):
    if email in ["Not Provided", "Not Found", ""] or not email or not supabase:
        return False
    try:
        response = supabase.table("candidates").select("email").ilike("email", email.lower().strip()).execute()
        return len(response.data) > 0
    except Exception:
        return False

def save_candidates_to_repository(new_candidates):
    if not supabase:
        return
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for c in new_candidates:
        email = str(c.get("email", "Not Provided")).lower().strip()
        if email not in ["not provided", "not found", "", "nan"] and check_if_exists_in_db(email):
            continue
            
        payload = {
            "candidate_name": c["name"],
            "father_name": c.get("father_name", "Not Provided"),
            "email": c["email"],
            "phone": c["phone"],
            "cgpa": c.get("cgpa", "Not Provided"),
            "education": c.get("education", "Not Provided"),
            "university_name": c.get("university_name", "Not Provided"),
            "experience_years": str(c.get("experience_years", "0")),
            "latest_experience": c.get("latest_experience", "Not Provided"),
            "reference": c.get("reference", "Not Provided"),
            "pipeline_status": "Talent Pool",
            "added_at": current_timestamp
        }
        try:
            supabase.table("candidates").insert(payload).execute()
        except Exception:
            pass

def delete_single_candidate_from_db(email_or_name):
    if not supabase:
        return
    try:
        supabase.table("candidates").delete().or_(f"email.ilike.{email_or_name},candidate_name.ilike.{email_or_name}").execute()
    except Exception:
        pass

def update_candidate_pipeline_status(email, new_status):
    if not supabase:
        return
    try:
        supabase.table("candidates").update({"pipeline_status": new_status}).ilike("email", email).execute()
    except Exception:
        pass

def clear_candidate_database():
    if not supabase:
        return
    try:
        df = load_database()
        for _, row in df.iterrows():
            supabase.table("candidates").delete().eq("email", row["Email"]).execute()
    except Exception:
        pass

def generate_repository_excel(df: pd.DataFrame) -> bytes:
    import openpyxl
    buffer = io.BytesIO()
    export_df = df.copy()
    if "Job Title" in export_df.columns:
        export_df = export_df.drop(columns=["Job Title"])
    export_df.insert(0, "Sr. No.", range(1, len(export_df) + 1))
    
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Talent_Repository")
        worksheet = writer.sheets["Talent_Repository"]
        worksheet.freeze_panes = "A2"
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 40)
            for cell in col:
                cell.alignment = openpyxl.styles.Alignment(wrap_text=True, vertical="top")
                
    buffer.seek(0)
    return buffer.getvalue()

def generate_screening_excel(results_list) -> bytes:
    import openpyxl
    buffer = io.BytesIO()
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
            "Match Score (%)": r["match_score"],
            "Pipeline Status": r["pipeline_status"]
        })
    export_df = pd.DataFrame(data)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Screened_Results")
        worksheet = writer.sheets["Screened_Results"]
        worksheet.freeze_panes = "A2"
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 40)
            for cell in col:
                cell.alignment = openpyxl.styles.Alignment(wrap_text=True, vertical="top")
                
    buffer.seek(0)
    return buffer.getvalue()

# ===========================================================================
# 4. CYBER-NEON HOLOGRAPHIC EXECUTIVE CSS
# ===========================================================================
CYBER_NEON_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif !important;
}

[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* Futuristic Cyber-Neon Header (Unified Glowing Cyan) */
.cyber-header-box {
    text-align: center;
    padding: 2rem 1rem 1.4rem 1rem;
    margin-bottom: 1.2rem;
}

.cyber-title {
    font-size: 3.6rem !important;
    font-weight: 900 !important;
    letter-spacing: -1.2px !important;
    color: #00B4D8 !important;
    -webkit-text-fill-color: #00B4D8 !important;
    margin: 0 0 10px 0 !important;
    background: none !important;
    text-shadow: 0 0 22px rgba(0, 180, 216, 0.5) !important;
}

.cyber-title-pro {
    color: #00B4D8 !important;
    -webkit-text-fill-color: #00B4D8 !important;
    text-shadow: 0 0 25px rgba(0, 180, 216, 0.6) !important;
}

.cyber-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
    background: rgba(0, 180, 216, 0.08) !important;
    border: 1.5px solid #00B4D8 !important;
    padding: 6px 22px !important;
    border-radius: 30px !important;
    font-size: 0.8rem !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 2px !important;
    color: #0284C7 !important;
    box-shadow: 0 2px 12px rgba(0, 180, 216, 0.15) !important;
}

@media (prefers-color-scheme: dark) {
    .cyber-title, .cyber-title-pro {
        color: #00F2FE !important;
        -webkit-text-fill-color: #00F2FE !important;
        text-shadow: 0 0 28px rgba(0, 242, 254, 0.65) !important;
    }
    .cyber-badge {
        background: rgba(0, 242, 254, 0.12) !important;
        border-color: #00F2FE !important;
        color: #00F2FE !important;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.3) !important;
    }
}
/* Profiles Section Header */
.cyber-profiles-header {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(0, 242, 254, 0.3);
    border-radius: 16px;
    padding: 1.2rem 1.6rem;
    margin-bottom: 1.4rem;
    backdrop-filter: blur(12px);
}

/* Holographic Executive Profile Badge */
.cyber-badge-card {
    position: relative;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(13, 20, 36, 0.95) 100%);
    border: 1.5px solid rgba(0, 242, 254, 0.45);
    border-radius: 20px;
    padding: 1.8rem 2.2rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), inset 0 0 20px rgba(0, 242, 254, 0.08);
    backdrop-filter: blur(16px);
    transition: all 0.3s ease;
}

.cyber-badge-card:hover {
    border-color: #00F2FE;
    box-shadow: 0 14px 40px rgba(0, 242, 254, 0.25), inset 0 0 30px rgba(0, 242, 254, 0.15);
    transform: translateY(-2px);
}

/* Card Micro-Tags */
.cyber-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    border-bottom: 1px dashed rgba(0, 242, 254, 0.2);
    padding-bottom: 0.6rem;
}

.cyber-access-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    font-weight: 700;
    color: #64748B;
    letter-spacing: 1.5px;
}

.cyber-status-dot {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    color: #10B981;
    letter-spacing: 1px;
}

.cyber-status-dot::before {
    content: '';
    display: inline-block;
    width: 7px;
    height: 7px;
    background-color: #10B981;
    border-radius: 50%;
    box-shadow: 0 0 10px #10B981;
}

.cyber-avatar-ring {
    width: 66px;
    height: 66px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(0, 242, 254, 0.2) 0%, rgba(79, 172, 254, 0.3) 100%);
    border: 2px solid #00F2FE;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    box-shadow: 0 0 20px rgba(0, 242, 254, 0.35);
    flex-shrink: 0;
}

.cyber-name-title {
    margin: 0;
    font-size: 1.6rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.5px;
    text-shadow: 0 0 14px rgba(0, 242, 254, 0.4);
}

.cyber-role-pill {
    background: rgba(0, 242, 254, 0.15);
    border: 1px solid #00F2FE;
    color: #00F2FE;
    padding: 3px 12px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.cyber-email-mono {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.88rem;
    color: #94A3B8;
    background: rgba(15, 23, 42, 0.6);
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid rgba(148, 163, 184, 0.15);
    display: inline-block;
    margin-top: 6px;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%) !important;
    color: #FFFFFF !important;
    border: 1.5px solid #00F2FE !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    padding: 0.65rem 1.5rem !important;
    box-shadow: 0 0 15px rgba(0, 242, 254, 0.3) !important;
    transition: all 0.25s ease-in-out !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #00C6FF 0%, #0072FF 100%) !important;
    border-color: #FFFFFF !important;
    box-shadow: 0 0 25px rgba(0, 242, 254, 0.6) !important;
    transform: translateY(-2px);
}

/* Forms */
[data-testid="stForm"] {
    background: rgba(15, 23, 42, 0.85) !important;
    border: 1.5px solid rgba(0, 242, 254, 0.4) !important;
    border-radius: 20px !important;
    padding: 2.5rem !important;
    box-shadow: 0 0 35px rgba(0, 242, 254, 0.2) !important;
    backdrop-filter: blur(16px);
}

/* Portal Navbar */
.top-navbar {
    background: rgba(15, 23, 42, 0.85);
    border: 1.5px solid rgba(0, 242, 254, 0.4);
    border-radius: 16px;
    padding: 1.2rem 2rem;
    margin-bottom: 1.8rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 0 25px rgba(0, 242, 254, 0.2);
}
.top-brand-title {
    font-size: 1.6rem; font-weight: 800; color: #00F2FE; margin: 0;
    display: flex; align-items: center; gap: 10px;
    text-shadow: 0 0 15px rgba(0, 242, 254, 0.4);
}
.top-brand-subtitle {
    font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1.4px; font-weight: 700; color: #94A3B8; margin: 0;
}

.corp-hero {
    background: linear-gradient(135deg, rgba(0, 242, 254, 0.12) 0%, rgba(15, 23, 42, 0.8) 100%);
    border: 1.5px solid rgba(0, 242, 254, 0.4);
    border-radius: 16px;
    padding: 2.2rem 2.8rem;
    margin-bottom: 2rem;
    border-left: 6px solid #00F2FE;
    box-shadow: 0 0 30px rgba(0, 242, 254, 0.2);
}
.corp-badge {
    display: inline-flex; align-items: center; gap: 8px; 
    background: rgba(0, 242, 254, 0.15); color: #00F2FE; 
    padding: 6px 16px; border-radius: 8px;
    font-size: 0.78rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 0.9rem;
    border: 1px solid rgba(0, 242, 254, 0.4);
}
.corp-card {
    background: var(--background-color);
    border: 1.5px solid rgba(0, 242, 254, 0.3);
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 0 20px rgba(0, 242, 254, 0.1);
}
/* =========================================================
   FUTURISTIC CYBER-NEON STEP HEADINGS (.corp-card h4)
   ========================================================= */
.corp-card h4 {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.2px !important;
    color: #008DDA !important;
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    margin-top: 0 !important;
    margin-bottom: 1.2rem !important;
    /* Cyber Accent Background Ribbon */
    background: linear-gradient(90deg, rgba(0, 180, 216, 0.12) 0%, rgba(0, 180, 216, 0.02) 100%) !important;
    border-left: 4px solid #00B4D8 !important;
    border-bottom: 1px solid rgba(0, 180, 216, 0.25) !important;
    border-radius: 8px 12px 12px 8px !important;
    padding: 10px 16px !important;
    box-shadow: inset 0 0 15px rgba(0, 180, 216, 0.06) !important;
    text-shadow: 0 0 12px rgba(0, 180, 216, 0.2) !important;
}

@media (prefers-color-scheme: dark) {
    .corp-card h4 {
        color: #0B132B !important;
        background: linear-gradient(90deg, rgba(0, 242, 254, 0.16) 0%, rgba(15, 23, 42, 0.6) 100%) !important;
        border-left: 4px solid #00F2FE !important;
        border-bottom: 1px solid rgba(0, 242, 254, 0.3) !important;
        box-shadow: inset 0 0 20px rgba(0, 242, 254, 0.1), 0 4px 12px rgba(0, 0, 0, 0.25) !important;
        text-shadow: 0 0 20px rgba(0, 242, 254, 0.5) !important;
    }
}
.metric-box {
    background: var(--secondary-background-color);
    border: 1.5px solid rgba(0, 242, 254, 0.35);
    border-radius: 14px;
    padding: 1.2rem;
    text-align: center;
}
.metric-box .val { font-size: 1.8rem; font-weight: 800; color: #00F2FE; text-shadow: 0 0 10px rgba(0, 242, 254, 0.4); }
.metric-box .lbl { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; font-weight: 700; opacity: 0.85; }

.score-high { color: #10B981 !important; font-weight: 800; }
.score-mid { color: #F59E0B !important; font-weight: 800; }
.score-low { color: #EF4444 !important; font-weight: 800; }
/* =========================================================
   FUTURISTIC CYBER-NEON TABS (NAV-PILLS)
   ========================================================= */

/* Default red underline aur border hide karna */
div[data-baseweb="tab-highlight"],
div[data-baseweb="tab-border"] {
    display: none !important;
}

/* Tabs ka outer container */
div[data-baseweb="tab-list"] {
    background: rgba(15, 23, 42, 0.75) !important;
    border: 1.5px solid rgba(0, 242, 254, 0.35) !important;
    border-radius: 16px !important;
    padding: 6px 10px !important;
    gap: 8px !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.35), inset 0 0 15px rgba(0, 242, 254, 0.06) !important;
    backdrop-filter: blur(12px) !important;
    margin-bottom: 1.8rem !important;
}

/* Individual tab button */
button[data-baseweb="tab"] {
    background: transparent !important;
    border: 1.5px solid transparent !important;
    border-radius: 12px !important;
    padding: 8px 20px !important;
    color: #94A3B8 !important;
    font-size: 0.92rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    transition: all 0.25s ease-in-out !important;
}

/* Hover effect */
button[data-baseweb="tab"]:hover {
    color: #00F2FE !important;
    background: rgba(0, 242, 254, 0.1) !important;
    border-color: rgba(0, 242, 254, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* Active / Selected Tab (Glowing Neon Pill) */
button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(2, 132, 199, 0.35) 0%, rgba(0, 242, 254, 0.2) 100%) !important;
    border: 1.5px solid #00F2FE !important;
    color: #00F2FE !important;
    box-shadow: 0 0 18px rgba(0, 242, 254, 0.4) !important;
    text-shadow: 0 0 10px rgba(0, 242, 254, 0.5) !important;
}
</style>
"""
st.markdown(CYBER_NEON_CSS, unsafe_allow_html=True)

# ===========================================================================
# 5. SESSION STATE INITIALIZATION
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
# 6. AUTHENTICATION & LOGIN SCREEN (CYBER-NEON)
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()
    
    st.markdown(f"""
        <div class="cyber-header-box">
            <h1 class="cyber-title">HireMatrix <span class="cyber-title-pro">Pro</span></h1>
            <div class="cyber-badge">
                <span>◈</span> {APP_TAGLINE} <span>◈</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col_c1, col_c2, col_c3 = st.columns([1, 2.2, 1])
    with col_c2:
        if st.session_state.pending_pin_email:
            st.markdown("### 🔐 Dedicated Admin & Employee PIN Setup")
            st.info(f"Email verified for **{st.session_state.pending_pin_email}**. Please create your confidential 4-digit security PIN.")
            
            with st.form("pin_setup_form"):
                new_pin = st.text_input("Create 4-Digit PIN", type="password", max_chars=4, placeholder="••••")
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
                success, nag = verify_otp_code(st.session_state.pending_otp_email, otp_input)
                if success:
                    st.success(nag)
                    st.session_state.pending_pin_email = st.session_state.pending_otp_email
                    st.session_state.pending_otp_email = None
                    st.rerun()
                else:
                    st.error(nag)
            with col_o2:
                if st.button("Cancel", use_container_width=True, key="cancel_otp_btn"):
                    st.session_state.pending_otp_email = None
                    st.rerun()
            
        elif saved_profiles and not st.session_state.selected_profile_email:
            st.markdown("""
                <div class="cyber-profiles-header">
                    <h3 style="margin: 0 0 0.3rem 0; font-size: 1.35rem; font-weight: 700; color: #00F2FE;">👥 Active Executive Profiles</h3>
                    <p style="font-size: 0.85rem; opacity: 0.85; margin: 0; color: #94A3B8;">Select your digital access badge to sign in:</p>
                </div>
            """, unsafe_allow_html=True)
            
            for p_email, p_name, p_pin, p_role in saved_profiles:
                st.markdown(f"""
                    <div class="cyber-badge-card">
                        <div class="cyber-top-bar">
                            <span class="cyber-access-id">ID // {hashlib.md5(p_email.encode()).hexdigest()[:8].upper()}</span>
                            <span class="cyber-status-dot">ONLINE</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 20px;">
                            <div class="cyber-avatar-ring">
                                👤
                            </div>
                            <div style="flex-grow: 1;">
                                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                                    <h3 class="cyber-name-title">{p_name}</h3>
                                    <span class="cyber-role-pill">{p_role}</span>
                                </div>
                                <div class="cyber-email-mono">✉ {p_email}</div>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                c_btn1, c_btn2 = st.columns([2.2, 1])
                with c_btn1:
                    if st.button(f"🔐 Sign In as {p_name}", use_container_width=True, key=f"sel_card_{p_email}"):
                        st.session_state.selected_profile_email = p_email
                        st.rerun()
                with c_btn2:
                    if st.button("🗑️ Delete", key=f"del_card_{p_email}", use_container_width=True):
                        delete_employee_profile(p_email)
                        st.success("Profile removed.")
                        st.rerun()
                st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            if st.button("➕ Register New Employee / Admin Profile", use_container_width=True, key="reg_new_emp_auth_btn"):
                st.session_state.selected_profile_email = "new"
                st.rerun()
            
        elif st.session_state.selected_profile_email and st.session_state.selected_profile_email != "new":
            target_email = st.session_state.selected_profile_email
            p_match = next((p for p in saved_profiles if p[0] == target_email), ("Employee", "", "", "Recruiter"))
            
            st.markdown(f"### 🔐 Sign In: {p_match[1]}")
            st.caption("Enter your 4-digit security PIN to access portal.")
            
            with st.form("pin_login_form"):
                pin_input = st.text_input("4-Digit PIN", type="password", max_chars=4, placeholder="••••")
                submit_log = st.form_submit_button("Sign In (Press Enter)", use_container_width=True)
                
            col_b1, col_b2 = st.columns(2)
            if submit_log:
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
            st.markdown("### 📝 Employee / Admin Registration")
            st.caption("Enter your credentials. First registered user automatically becomes Admin with dedicated PIN creation.")
            
            with st.form("registration_form"):
                reg_name = st.text_input("Full Name", placeholder="Alex Mercer")
                reg_email = st.text_input("Company Email", placeholder="employee@company.com")
                reg_pass = st.text_input("Master Password", type="password")
                submit_reg = st.form_submit_button("Send Verification OTP", use_container_width=True)
                
            col_r1, col_r2 = st.columns(2)
            if submit_reg:
                if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                    st.warning("Please verify all required fields.")
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
            
    st.stop()

# ===========================================================================
# 7. ENHANCED DUAL-PASS TEXT EXTRACTION & OCR
# ===========================================================================
def extract_text_from_image(file_bytes: bytes) -> str:
    import pytesseract
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        gray = img.convert("L")
        t1 = pytesseract.image_to_string(gray)
        
        inverted = ImageOps.invert(gray)
        inv_contrasted = ImageEnhance.Contrast(inverted).enhance(2.2)
        t2 = pytesseract.image_to_string(inv_contrasted)
        
        return f"{t1}\n{t2}"
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
                    pil_img = page.to_image(resolution=300).original.convert("RGB")
                    gray = pil_img.convert("L")
                    t1 = pytesseract.image_to_string(gray)
                    inv = ImageEnhance.Contrast(ImageOps.invert(gray)).enhance(2.2)
                    t2 = pytesseract.image_to_string(inv)
                    text_parts.append(f"{t1}\n{t2}")
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
# 8. GROQ AI INTEGRATION & SMART FALLBACK EXTRACTION
# ===========================================================================
def build_repository_extraction_prompt(resume_text: str) -> str:
    return f"""You are an expert HR AI assistant. Extract candidate profile information from the following resume.

CRITICAL INSTRUCTIONS:
- Search carefully for the candidate's Full Name at the beginning or top header.
- Locate the candidate's Email Address (look for words with '@' symbol).
- Locate the candidate's Phone Number or Mobile digits.
- Extract accurately without leaving fields as 'Not Provided' if visible anywhere in the text.

RESUME TEXT:
{resume_text[:14000]}

Return ONLY a valid JSON object with exactly the following keys:
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
    return f"""You are an expert HR recruiter AI. Evaluate the CANDIDATE PROFILE against the JOB DESCRIPTION. Determine if the candidate is relevant to the job domain.

CANDIDATE PROFILE SUMMARY:
{candidate_text_summary}

JOB DESCRIPTION:
{jd_text}

Return ONLY a valid JSON object:
{{
  "match_score": A number between 0 and 100,
  "is_relevant": true if the candidate has domain relevance, else false,
  "missing_skills": ["List", "of", "key JD skills missing"]
}}
"""

def extract_candidate_for_repo(client, resume_text: str, file_name: str):
    try:
        prompt = build_repository_extraction_prompt(resume_text)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw_content = response.choices[0].message.content.strip()
        result = json.loads(raw_content)
        
        name = result.get("name", "Unknown").strip()
        email = result.get("email", "Not Provided").strip()
        phone = result.get("phone", "Not Provided").strip()

        if email in ["Not Provided", "Not Found", "", "None"]:
            found_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', resume_text)
            if found_emails:
                email = found_emails[0].strip()

        if phone in ["Not Provided", "Not Found", "", "None"]:
            found_phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,5}', resume_text)
            if found_phones:
                phone = found_phones[0].strip()

        if name in ["Unknown", "Not Provided", "", "None"]:
            lines = [l.strip() for l in resume_text.splitlines() if len(l.strip()) > 3]
            for l in lines[:5]:
                if not any(kw in l.lower() for kw in ["curriculum", "resume", "objective", "education", "experience", "skills", "profile"]):
                    if len(l.split()) in [2, 3]:
                        name = l.title()
                        break
        
        return {
            "file_name": file_name,
            "name": name if name else "Unknown",
            "father_name": result.get("father_name", "Not Provided"),
            "email": email,
            "phone": phone,
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
        summary = f"Name: {candidate_row['Candidate Name']}, Education: {candidate_row['Education']}, University: {candidate_row['University Name']}, Experience: {candidate_row['Experience Years']}, Latest Role: {candidate_row['Latest Experience']}"
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
# 9. PORTAL NAVIGATION BAR & DASHBOARD
# ===========================================================================
df_all = load_database()
total_repo_db = len(df_all)
latest_candidate = df_all.iloc[-1]["Candidate Name"] if not df_all.empty else "None"

col_n1, col_n2 = st.columns([8, 2])
with col_n1:
    st.markdown(f"""
        <div class="top-navbar">
            <div>
                <h2 class="top-brand-title">💼 {APP_NAME}</h2>
                <p class="top-brand-subtitle">Autonomous HR Intelligence &bull; Active: <b>{st.session_state.get('hr_name', 'Recruiter')}</b> ({st.session_state.get('hr_email', 'admin@company.com')}) &bull; Role: <b>{st.session_state.get('hr_role', 'Recruiter')}</b></p>
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_n2:
    if st.button("🚪 Lock Portal", use_container_width=True, key="lock_portal_btn_top"):
        st.session_state.logged_in = False
        st.session_state.hr_name = ""
        st.session_state.hr_email = ""
        st.session_state.hr_role = "Recruiter"
        st.session_state.selected_profile_email = None
        st.session_state.screening_results = []
        st.rerun()

st.markdown(f"""
    <div class="corp-hero">
        <div class="corp-badge">
            <span>🟢 Multi-Stage ATS Session</span> &bull; <span>Total Talent Pool: {total_repo_db} Candidates</span>
        </div>
        <h1>Executive Recruitment Suite</h1>
        <p>Welcome back, <b>{st.session_state.get('hr_name', 'Recruiter')}</b> &mdash; Latest Added: <b>{latest_candidate}</b> | All extracted resumes are automatically appended and permanently saved to Supabase Cloud.</p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Talent Repository (Upload)", "🎯 2. JD Screening & Matching", "🗄️ 3. Live Master Excel Sheet Grid", "🛡️ 4. Admin Controls"])

with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Talent Repository Ingestion (Upload Resumes)</h4>', unsafe_allow_html=True)
    st.caption("Upload candidate resumes below. AI will extract their profile details and save them to the Supabase cloud repository.")
    
    uploaded_repo_files = st.file_uploader("Upload candidate resumes to repository", type=ACCEPTED_TYPES, accept_multiple_files=True, label_visibility="collapsed")
    
    if st.button("⚡ Extract & Save to Master Database", type="primary", use_container_width=True, disabled=not (uploaded_repo_files and ("GROQ_API_KEY" in st.secrets or 'groq_api_key' in locals()))):
        g_key = st.secrets["GROQ_API_KEY"] if "GROQ_API_KEY" in st.secrets else ""
        client = Groq(api_key=g_key)
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
            st.success("Successfully processed and permanently saved candidates to Supabase cloud!")
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    df_repo = load_database()
    if not df_repo.empty:
        st.markdown('<div class="corp-card"><h4>📋 Current Candidates in Talent Repository</h4>', unsafe_allow_html=True)
        
        st.download_button(
            "📊 Download Master Talent Repository Report (.xlsx)",
            data=generate_repository_excel(df_repo),
            file_name="Master_Talent_Repository.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_repo_master_btn"
        )
        st.markdown("---")
        
        for idx, row in df_repo.iterrows():
            c_d1, c_d2, c_d3, c_d4 = st.columns([2, 2, 2, 1])
            with c_d1: st.write(f"👤 **{row['Candidate Name']}**")
            with c_d2: st.write(f"✉️ `{row['Email']}`")
            with c_d3: st.write(f"🎓 {row['Education']}")
            with c_d4:
                unique_hash = hashlib.md5(f"repo_{idx}_{row['Email']}_{row['Candidate Name']}".encode()).hexdigest()[:10]
                safe_key = f"del_repo_btn_{unique_hash}"
                if st.button("🗑️ Delete", key=safe_key, use_container_width=True):
                    delete_single_candidate_from_db(row['Email'] if row['Email'] not in ["Not Provided", "Not Found", ""] else row['Candidate Name'])
                    st.success(f"Removed {row['Candidate Name']} from repository!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening & Smart Matching</h4>', unsafe_allow_html=True)
    st.caption("Enter a Job Description below. AI will scan your stored Talent Pool repository, filter strictly for candidates relevant to this JD, and display them.")
    
    jd_title_input = st.text_input("Job Position Title", placeholder="e.g. Senior Human Resources Manager", key="jd_title_input_field")
    jd_desc_text = st.text_area("Job Description & Requirements", height=120, placeholder="Paste detailed job description here...", key="jd_desc_text_field")
    
    st.markdown("---")
    st.markdown("**🎯 Select Minimum Passing Score Threshold (%)**")
    screening_threshold = st.slider(
        "Candidates scoring above this will be highlighted; all JD-relevant candidates remain reviewable.",
        min_value=0, max_value=100, value=50, step=5,
        label_visibility="collapsed",
        key="screening_threshold_slider_step2"
    )
    st.caption(f"Current Highlight Threshold: **{screening_threshold}%**")
    
    df_pool = load_database()
    g_key_active = st.secrets["GROQ_API_KEY"] if "GROQ_API_KEY" in st.secrets else ""
    
    if st.button("⚡ Run AI Screening against Talent Pool", type="primary", use_container_width=True, disabled=not (jd_desc_text.strip() and jd_title_input.strip() and not df_pool.empty and g_key_active), key="run_screening_btn_main"):
        client = Groq(api_key=g_key_active)
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

    screening_results_safe = st.session_state.get('screening_results', [])
    if screening_results_safe:
        st.markdown('<div class="corp-card"><h4>📊 JD-Relevant Candidates & Recruiter Decision Pipeline</h4>', unsafe_allow_html=True)
        results = sorted(screening_results_safe, key=lambda x: x["match_score"], reverse=True)
        
        if not results:
            st.warning("⚠️ No candidates in the repository matched the requirements of this Job Description.")
        else:
            st.download_button(
                "📊 Download Master Screened Candidates Report (.xlsx)",
                data=generate_screening_excel(results),
                file_name="Master_Screened_Candidates_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_screened_master_btn"
            )
            st.markdown("---")
        
        client = Groq(api_key=g_key_active) if g_key_active else None

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
                
                cand_hash = hashlib.md5(f"screen_{rank}_{cand['email']}_{cand['name']}".encode()).hexdigest()[:10]
                stage_key = f"stage_sel_{rank}_{cand_hash}"
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
                q_key = f"gen_q_{rank}_{cand_hash}"
                if st.button(f"💡 Generate AI Interview Q&A for {cand['name']}", key=q_key):
                    if client:
                        with st.spinner("Generating tailored interview questions..."):
                            q_text = generate_ai_interview_questions(client, "General HR and Professional Skills", cand['job_title'])
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

                    msg_key = f"inv_msg_{rank}_{cand_hash}"
                    invite_msg = st.text_area("Email Message", value=default_msg, key=msg_key)
                    
                    send_key = f"send_inv_{rank}_{cand_hash}"
                    if st.button(f"📧 Send Email to {cand['name']}", key=send_key):
                        ok, res_m = send_smtp_email(cand['email'], email_subject, invite_msg)
                        if ok:
                            st.success(f"Email sent successfully to {cand['email']}!")
                        else:
                            st.error(res_m)

        st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Live Master Excel Sheet Grid (Real-time Database View)</h4>', unsafe_allow_html=True)
    st.caption("Interactive candidate database grid. All extracted talent pool records are synchronized in real-time.")
    
    df_db = load_database()
    
    if df_db.empty:
        st.info("Master database is currently empty. Upload resumes in Step 1.")
    else:
        grid_df = df_db.copy()
        if "Job Title" in grid_df.columns:
            grid_df = grid_df.drop(columns=["Job Title"])
        if "Extracted Skills" in grid_df.columns:
            grid_df = grid_df.drop(columns=["Extracted Skills"])
        grid_df.insert(0, "Sr. No.", range(1, len(grid_df) + 1))
        
        st.data_editor(grid_df, use_container_width=True, height=400, disabled=True, key="master_excel_grid_view")
        
        st.markdown("---")
        c_ex1, c_ex2 = st.columns([2, 1])
        with c_ex1:
            st.download_button(
                "📊 Download Master Talent Repository Report (.xlsx)",
                data=generate_repository_excel(df_db),
                file_name="Master_Talent_Repository.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_live_grid_xlsx_btn"
            )
        with c_ex2:
            if st.button("🗑️ Clear Entire Database", type="secondary", key="clear_db_btn_master_grid", use_container_width=True):
                clear_candidate_database()
                st.success("Repository cleared successfully!")
                st.rerun()
                
    st.markdown("</div>", unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="corp-card"><h4>🛡️ Admin Access & Employee Management</h4></div>', unsafe_allow_html=True)
    
    if st.session_state.get('hr_role') != "Admin":
        st.error("⛔ **Access Denied**: You do not have Administrator privileges to view this control panel.")
    else:
        st.success("✓ Admin privileges active & verified.")
        
        st.markdown("### 👥 Active Employee Profiles & Confidential PINs")
        all_emps = get_all_verified_profiles_admin()
        st.markdown(f"**Total Active Registered Employees:** {len(all_emps)}")
        for emp_email, emp_name, emp_pin, emp_role in all_emps:
            col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
            with col_a1: st.write(f"👤 **{emp_name}** ({emp_email}) — *{emp_role}*")
            with col_a2: st.write(f"PIN: `{emp_pin}`")
            with col_a3:
                if emp_email.lower() != st.session_state.get('hr_email', '').lower():
                    if st.button("🗑️ Revoke", key=f"rev_admin_{emp_email.replace('@','_')}", use_container_width=True):
                        delete_employee_profile(emp_email)
                        st.success(f"Access revoked for {emp_name}.")
                        st.rerun()
                else:
                    st.caption("Current User")
    st.markdown("</div>", unsafe_allow_html=True)
