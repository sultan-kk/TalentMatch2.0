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
from groq import Groq
from supabase import create_client, Client
from PIL import Image, ImageDraw


# ===========================================================================
# 1. PAGE CONFIGURATION
# ===========================================================================
APP_NAME = "Arl TalentMatch:AI-Driven Automated CV Parser & JD Matcher"
APP_TAGLINE = "Attock Refinery Limited (ARL) • HR Intelligence & AI Screening Engine"
GROQ_MODEL = "openai/gpt-oss-120b"
ACCEPTED_TYPES = ["pdf", "docx", "png", "jpg", "jpeg"]
AVATAR_STORAGE_FILE = "user_avatars.json"
EXE_DOWNLOAD_URL = "https://github.com/sultan-kk/TalentMatch2.0/releases/download/v1.0/ARL-HireMatrix-Pro_1.0.0_x64_en-US.msi"

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
    "🚀": "Turnaround Specialist",
}


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
# 2. SAFE HELPERS
# ===========================================================================
def safe_secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


def safe_str(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def normalize_email(email: str) -> str:
    return safe_str(email).lower()


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", safe_str(phone))


def safe_execute(query):
    try:
        return query.execute()
    except Exception:
        return None


def make_key(prefix: str, *parts) -> str:
    raw = "|".join([prefix] + [safe_str(p) for p in parts])
    return f"{prefix}_{hashlib.md5(raw.encode()).hexdigest()[:12]}"


def get_groq_client():
    g_key = safe_secret("GROQ_API_KEY", "")
    if not g_key:
        return None
    try:
        return Groq(api_key=g_key)
    except Exception:
        return None


# ===========================================================================
# 3. SUPABASE CONNECTION
# ===========================================================================
@st.cache_resource
def init_supabase():
    url = safe_secret("SUPABASE_URL")
    key = safe_secret("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠ Supabase Connection Error: {e}")
        return None


supabase: Client = init_supabase()


# ===========================================================================
# 4. AUTH / EMAIL / AVATARS
# ===========================================================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def send_smtp_email(receiver_email, subject, body_text):
    sender_email = safe_secret("SMTP_EMAIL")
    sender_password = safe_secret("SMTP_PASSWORD")

    if not sender_email or not sender_password:
        return False, "SMTP credentials are not configured in Streamlit secrets."

    try:
        msg = MIMEMultipart()
        msg["From"] = formataddr(("ARL Recruitment Notifications", sender_email))
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True, "Email dispatched successfully!"
    except Exception as e:
        return False, f"Failed to send email: {e}"


def load_local_avatars():
    if os.path.exists(AVATAR_STORAGE_FILE):
        try:
            with open(AVATAR_STORAGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_local_avatar(email, sticker):
    data = load_local_avatars()
    data[normalize_email(email)] = sticker
    try:
        with open(AVATAR_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_default_sticker(email: str) -> str:
    stickers = list(PROFESSIONAL_STICKERS.keys())
    if not stickers:
        return "👔"
    idx = int(hashlib.md5(normalize_email(email).encode()).hexdigest(), 16) % len(stickers)
    return stickers[idx]


def get_user_sticker(email: str, db_avatar: str = None) -> str:
    clean = normalize_email(email)
    if "custom_stickers" in st.session_state and clean in st.session_state.custom_stickers:
        return st.session_state.custom_stickers[clean]

    local_data = load_local_avatars()
    if clean in local_data:
        return local_data[clean]

    if db_avatar:
        return db_avatar

    return get_default_sticker(clean)


def update_user_sticker(email: str, sticker: str):
    clean = normalize_email(email)
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


def get_all_verified_profiles():
    if not supabase:
        default_stk = get_user_sticker("admin@arl.com.pk", "🛢️")
        return [("admin@arl.com.pk", "ARL Admin", "1234", "Admin", default_stk)]

    profiles = []

    try:
        res = supabase.table("hr_users").select("*").execute()
        if res and getattr(res, "data", None):
            for r in res.data:
                pin_val = safe_str(r.get("pin"))
                email = safe_str(r.get("email"))
                if email and pin_val:
                    profiles.append((
                        email,
                        safe_str(r.get("name"), "Employee"),
                        pin_val,
                        safe_str(r.get("role"), "Recruiter"),
                        get_user_sticker(email, r.get("avatar"))
                    ))
    except Exception:
        pass

    try:
        res2 = supabase.table("employees").select("*").execute()
        if res2 and getattr(res2, "data", None):
            existing = {normalize_email(p[0]) for p in profiles}
            for r in res2.data:
                email = safe_str(r.get("email"))
                pin_val = safe_str(r.get("pin"))
                if email and pin_val and normalize_email(email) not in existing:
                    profiles.append((
                        email,
                        safe_str(r.get("name"), "Employee"),
                        pin_val,
                        safe_str(r.get("role"), "Recruiter"),
                        get_user_sticker(email, r.get("avatar"))
                    ))
    except Exception:
        pass

    return profiles


def get_all_verified_profiles_admin():
    return get_all_verified_profiles()


def verify_employee_pin(email, entered_pin):
    clean_email = normalize_email(email)
    entered_str = safe_str(entered_pin)

    cached = get_all_verified_profiles()
    for p_email, p_name, p_pin, p_role, p_sticker in cached:
        if normalize_email(p_email) == clean_email and safe_str(p_pin) == entered_str:
            return True, p_name, p_role

    if not supabase:
        return False, None, None

    try:
        res = supabase.table("hr_users").select("*").ilike("email", clean_email).execute()
        if res and res.data:
            rec = res.data[0]
            if safe_str(rec.get("pin")) == entered_str:
                return True, safe_str(rec.get("name"), "Employee"), safe_str(rec.get("role"), "Recruiter")
    except Exception:
        pass

    try:
        res2 = supabase.table("employees").select("*").ilike("email", clean_email).execute()
        if res2 and res2.data:
            rec = res2.data[0]
            if safe_str(rec.get("pin")) == entered_str:
                return True, safe_str(rec.get("name"), "Employee"), safe_str(rec.get("role"), "Recruiter")
    except Exception:
        pass

    return False, None, None


def register_initial_employee(name, email, password, sticker="👔"):
    clean_email = normalize_email(email)
    otp = str(random.randint(100000, 999999))

    if not supabase:
        return False, "Supabase client not initialized."

    try:
        existing_res = supabase.table("hr_users").select("pin").eq("email", clean_email).execute()
        existing = existing_res.data if existing_res and getattr(existing_res, "data", None) else []
        if existing and existing[0].get("pin"):
            return False, "This email is already registered and active. Please sign in."

        count_res = supabase.table("hr_users").select("email", count="exact").execute()
        count = count_res.count if count_res and getattr(count_res, "count", None) is not None else 0
        role = "Admin" if count == 0 else "Recruiter"

        data = {
            "email": clean_email,
            "name": safe_str(name),
            "password": hash_password(password),
            "pin": None,
            "role": role,
            "is_verified": 0,
            "otp": otp,
            "avatar": sticker,
        }

        supabase.table("hr_users").upsert(data).execute()
        update_user_sticker(clean_email, sticker)

        success, msg = send_smtp_email(
            clean_email,
            "ARL TalentMatch - Verification OTP",
            f"Your verification code is: {otp}"
        )
        if success:
            return True, "Registration initiated! Please check your email for the verification OTP."
        return False, msg

    except Exception as e:
        return False, f"Error: {e}"


def verify_otp_code(email, entered_otp):
    if not supabase:
        return False, "Supabase client not initialized."
    try:
        response = supabase.table("hr_users").select("otp").eq("email", normalize_email(email)).execute()
        rows = response.data if response and getattr(response, "data", None) else []
        if rows and safe_str(rows[0].get("otp")) == safe_str(entered_otp):
            return True, "OTP verified successfully!"
    except Exception:
        pass
    return False, "Invalid OTP code. Please verify and try again."


def save_employee_pin(email, pin):
    if not supabase:
        return False, "Supabase client not initialized."

    clean_email = normalize_email(email)
    pin_str = safe_str(pin)

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

    clean_email = normalize_email(email)
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
# 5. ARL JOB CATALOG
# ===========================================================================
DEFAULT_ARL_CATALOG = {
    "Operations & Refining": [
        "Process Engineer", "Plant Shift Incharge", "Senior Plant Operator (CDU / Reformer)",
        "Control Room DCS Operator", "Refining Operations Manager", "Lead Commissioning Engineer"
    ],
    "Maintenance & Engineering": [
        "Mechanical Maintenance Engineer", "Electrical Maintenance Engineer",
        "Instrumentation & Control (I&C) Engineer", "Reliability & Inspection Engineer",
        "Turnaround & Maintenance Planning Specialist", "Rotary Equipment Specialist"
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
            if res and getattr(res, "data", None):
                for row in res.data:
                    dept = safe_str(row.get("department"), "General")
                    job = safe_str(row.get("job_title"))
                    if job:
                        catalog.setdefault(dept, []).append(job)
                if catalog:
                    return catalog
            else:
                seed = []
                for d, j_list in DEFAULT_ARL_CATALOG.items():
                    for j in j_list:
                        seed.append({"department": d, "job_title": j})
                if seed:
                    supabase.table("arl_job_hierarchy").insert(seed).execute()
                return DEFAULT_ARL_CATALOG
        except Exception:
            pass
    return DEFAULT_ARL_CATALOG


def add_arl_job_to_db(department, job_title):
    if supabase:
        try:
            supabase.table("arl_job_hierarchy").insert({
                "department": safe_str(department),
                "job_title": safe_str(job_title)
            }).execute()
            return True, "Job designation added successfully."
        except Exception as e:
            return False, str(e)
    return True, "Saved locally."


def edit_arl_job_in_db(old_dept, old_job, new_dept, new_job):
    if supabase:
        try:
            supabase.table("arl_job_hierarchy").update({
                "department": safe_str(new_dept),
                "job_title": safe_str(new_job)
            }).eq("department", old_dept).eq("job_title", old_job).execute()
            return True, "Job designation updated."
        except Exception as e:
            return False, str(e)
    return True, "Updated locally."


def delete_arl_job_from_db(department, job_title):
    if supabase:
        try:
            supabase.table("arl_job_hierarchy").delete().eq("department", department).eq("job_title", job_title).execute()
            return True, "Job designation removed."
        except Exception as e:
            return False, str(e)
    return True, "Removed locally."


# ===========================================================================
# 6. CANDIDATE REPOSITORY
# ===========================================================================
REPO_COLUMNS = [
    "Name", "Father Name", "Qualification", "CGPA",
    "Passing Year", "Institute", "DOB", "Email",
    "Phone Number", "Experience", "Latest Experience", "Reference"
]

SCREENED_COLUMNS = [
    "Job Title", "Match Score (%)", "Pipeline Status", "Name", "Father Name",
    "Qualification", "CGPA", "Passing Year", "Institute", "DOB", "Email",
    "Phone Number", "Experience", "Latest Experience", "Reference", "Missing Skills", "Screened At"
]


def load_database():
    if not supabase:
        return pd.DataFrame(columns=REPO_COLUMNS)

    try:
        response = supabase.table("candidates").select("*").order("id", desc=False).execute()
        rows = response.data if response and getattr(response, "data", None) else []
        if rows:
            mapped = []
            for r in rows:
                mapped.append({
                    "Name": r.get("candidate_name") or r.get("name") or "Unknown",
                    "Father Name": r.get("father_name", "Not Provided"),
                    "Qualification": r.get("education", "Not Provided"),
                    "CGPA": r.get("cgpa", "Not Provided"),
                    "Passing Year": r.get("passing_year", "Not Provided"),
                    "Institute": r.get("university_name", "Not Provided"),
                    "DOB": r.get("dob", "Not Provided"),
                    "Email": r.get("email", "Not Provided"),
                    "Phone Number": r.get("phone", "Not Provided"),
                    "Experience": safe_str(r.get("experience_years", "0")),
                    "Latest Experience": r.get("latest_experience", "Not Provided"),
                    "Reference": r.get("reference", "Not Provided"),
                })
            return pd.DataFrame(mapped)
    except Exception:
        pass

    return pd.DataFrame(columns=REPO_COLUMNS)


def save_candidates_to_repository(new_candidates):
    if not supabase:
        return 0, 0

    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_emails = set()
    existing_phones = set()

    try:
        res = supabase.table("candidates").select("email, phone").execute()
        if res and getattr(res, "data", None):
            for r in res.data:
                em = normalize_email(r.get("email", ""))
                ph = normalize_phone(r.get("phone", ""))
                if em and em not in {"not provided", "not found", "nan"}:
                    existing_emails.add(em)
                if ph and len(ph) >= 7:
                    existing_phones.add(ph)
    except Exception:
        pass

    inserted_count = 0
    skipped_count = 0

    for c in new_candidates:
        cand_email = normalize_email(c.get("email", ""))
        cand_phone = normalize_phone(c.get("phone", ""))

        is_dup = False
        if cand_email and cand_email not in {"not provided", "not found", "nan"} and cand_email in existing_emails:
            is_dup = True
        elif cand_phone and len(cand_phone) >= 7 and cand_phone in existing_phones:
            is_dup = True

        if is_dup:
            skipped_count += 1
            continue

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
            "experience_years": safe_str(c.get("experience_years", "0")),
            "latest_experience": c.get("latest_experience", "Not Provided"),
            "reference": c.get("reference", "Not Provided"),
            "pipeline_status": "Talent Pool",
            "added_at": current_timestamp,
        }

        try:
            supabase.table("candidates").insert(payload).execute()
            inserted_count += 1
            if cand_email and cand_email not in {"not provided", "not found", "nan"}:
                existing_emails.add(cand_email)
            if cand_phone and len(cand_phone) >= 7:
                existing_phones.add(cand_phone)
        except Exception:
            skipped_count += 1

    return inserted_count, skipped_count


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
        supabase.table("candidates").delete().neq("id", 0).execute()
    except Exception:
        pass


def save_screened_to_supabase(screened_list):
    if not supabase or not screened_list:
        return

    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in screened_list:
        skills_str = ", ".join(r.get("missing_skills", [])) if isinstance(r.get("missing_skills"), list) else safe_str(r.get("missing_skills", ""))
        payload = {
            "job_title": r.get("job_title", "Not Specified"),
            "candidate_name": r.get("name", "Unknown"),
            "father_name": r.get("father_name", "Not Provided"),
            "education": r.get("education", "Not Provided"),
            "cgpa": r.get("cgpa", "Not Provided"),
            "passing_year": r.get("passing_year", "Not Provided"),
            "university_name": r.get("university_name", "Not Provided"),
            "dob": r.get("dob", "Not Provided"),
            "email": r.get("email", "Not Provided"),
            "phone": r.get("phone", "Not Provided"),
            "experience_years": safe_str(r.get("experience_years", "0")),
            "latest_experience": r.get("latest_experience", "Not Provided"),
            "reference": r.get("reference", "Not Provided"),
            "match_score": float(r.get("match_score", 0)),
            "missing_skills": skills_str,
            "pipeline_status": r.get("pipeline_status", "Shortlisted"),
            "screened_at": current_timestamp,
        }
        try:
            supabase.table("screened_candidates").insert(payload).execute()
        except Exception:
            pass


def load_screened_database():
    if not supabase:
        return pd.DataFrame(columns=SCREENED_COLUMNS)

    try:
        response = supabase.table("screened_candidates").select("*").order("id", desc=True).execute()
        rows = response.data if response and getattr(response, "data", None) else []
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
                    "Experience": safe_str(r.get("experience_years", "0")),
                    "Latest Experience": r.get("latest_experience", "Not Provided"),
                    "Reference": r.get("reference", "Not Provided"),
                    "Missing Skills": r.get("missing_skills", "None"),
                    "Screened At": r.get("screened_at", ""),
                })
            return pd.DataFrame(mapped)
    except Exception:
        pass

    return pd.DataFrame(columns=SCREENED_COLUMNS)


def update_screened_candidate_status(email, job_title, new_status):
    if not supabase:
        return
    try:
        supabase.table("screened_candidates").update({"pipeline_status": new_status}).ilike("email", email).ilike("job_title", job_title).execute()
    except Exception:
        pass


def clear_screened_database():
    if not supabase:
        return
    try:
        supabase.table("screened_candidates").delete().neq("id", 0).execute()
    except Exception:
        pass


def generate_repository_excel(df: pd.DataFrame) -> bytes:
    import openpyxl
    buffer = io.BytesIO()
    export_df = df.copy()
    export_df.insert(0, "Sr. No.", range(1, len(export_df) + 1))

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Candidates_Master")
        worksheet = writer.sheets["Candidates_Master"]
        worksheet.freeze_panes = "A2"

        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
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
            "Job Title": r.get("job_title", r.get("Job Title", "Not Specified")),
            "Candidate Name": r.get("name", r.get("Name", "Unknown")),
            "Father Name": r.get("father_name", r.get("Father Name", "Not Provided")),
            "Qualification": r.get("education", r.get("Qualification", "Not Provided")),
            "CGPA": r.get("cgpa", r.get("CGPA", "Not Provided")),
            "Passing Year": r.get("passing_year", r.get("Passing Year", "Not Provided")),
            "Institute": r.get("university_name", r.get("Institute", "Not Provided")),
            "DOB": r.get("dob", r.get("DOB", "Not Provided")),
            "Email": r.get("email", r.get("Email", "Not Provided")),
            "Phone Number": r.get("phone", r.get("Phone Number", "Not Provided")),
            "Experience": r.get("experience_years", r.get("Experience", "0")),
            "Latest Experience": r.get("latest_experience", r.get("Latest Experience", "Not Provided")),
            "Reference": r.get("reference", r.get("Reference", "Not Provided")),
            "Match Score (%)": r.get("match_score", r.get("Match Score (%)", 0)),
            "Pipeline Status": r.get("pipeline_status", r.get("Pipeline Status", "Shortlisted")),
        })

    export_df = pd.DataFrame(data)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Screened_Results")
        worksheet = writer.sheets["Screened_Results"]
        worksheet.freeze_panes = "A2"

        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 40)
            for cell in col:
                cell.alignment = openpyxl.styles.Alignment(wrap_text=True, vertical="top")

    buffer.seek(0)
    return buffer.getvalue()


# ===========================================================================
# 7. GLOBAL CSS
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

button,
button[kind="secondary"],
button[kind="primary"],
div[data-testid="stButton"] button {
    background: linear-gradient(145deg, #113f26 0%, #082416 100%) !important;
    color: #FFFFFF !important;
    border: 1.5px solid #22C55E !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    transition: all 0.2s ease-in-out !important;
}

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
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
}
.top-brand-title {
    font-size: 1.45rem;
    font-weight: 800;
    color: #FFFFFF;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 10px;
}
.top-brand-subtitle {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 700;
    color: #86EFAC;
    margin: 0;
}

.corp-hero {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.18) 0%, rgba(8, 28, 18, 0.9) 100%);
    border: 1.5px solid rgba(74, 222, 128, 0.3);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    border-left: 6px solid #4ADE80;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}
.corp-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(34, 197, 94, 0.2);
    color: #86EFAC;
    padding: 5px 14px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.8rem;
    border: 1px solid rgba(74, 222, 128, 0.4);
}
.corp-card {
    background: rgba(14, 46, 29, 0.65);
    border: 1.5px solid rgba(74, 222, 128, 0.25);
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.3);
}
.corp-card h4 {
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.2px !important;
    color: #FFFFFF !important;
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    margin-top: 0 !important;
    margin-bottom: 1.2rem !important;
    background: linear-gradient(90deg, rgba(34, 197, 94, 0.18) 0%, rgba(22, 101, 52, 0.08) 100%) !important;
    border-left: 4px solid #4ADE80 !important;
    border-bottom: 1px solid rgba(74, 222, 128, 0.25) !important;
    border-radius: 8px 12px 12px 8px !important;
    padding: 10px 16px !important;
}
.metric-box .val { font-size: 1.8rem; font-weight: 800; color: #4ADE80; }
.metric-box .lbl { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; font-weight: 700; color: #86EFAC; }
.score-high { color: #4ADE80 !important; font-weight: 800; }
.score-mid { color: #FBBF24 !important; font-weight: 800; }
.score-low { color: #F87171 !important; font-weight: 800; }

div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { display: none !important; }
div[data-baseweb="tab-list"] {
    background: rgba(10, 34, 21, 0.9) !important;
    border: 1.5px solid rgba(74, 222, 128, 0.25) !important;
    border-radius: 16px !important;
    padding: 6px 10px !important;
    gap: 8px !important;
    margin-bottom: 1.8rem !important;
}
button[data-baseweb="tab"] {
    background: transparent !important;
    border: 1.5px solid transparent !important;
    border-radius: 12px !important;
    padding: 8px 20px !important;
    color: #CBD5E1 !important;
    font-size: 0.92rem !important;
    font-weight: 700 !important;
    transition: all 0.25s ease-in-out !important;
}
button[data-baseweb="tab"]:hover {
    color: #4ADE80 !important;
    background: rgba(34, 197, 94, 0.1) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(22, 101, 52, 0.8) 0%, rgba(34, 197, 94, 0.35) 100%) !important;
    border: 1.5px solid #4ADE80 !important;
    color: #FFFFFF !important;
}

/* Netflix-style profile deck */
.netflix-shell {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 1.4rem 0 0.5rem 0;
}
.netflix-heading {
    text-align: center;
    margin-bottom: 1.4rem;
}
.netflix-heading h2 {
    margin: 0 0 8px 0 !important;
    font-size: 2.1rem !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    letter-spacing: -0.4px !important;
}
.netflix-heading p {
    margin: 0 !important;
    font-size: 0.95rem !important;
    color: #9CA3AF !important;
    font-weight: 500 !important;
}
.netflix-profiles {
    display: flex !important;
    flex-wrap: wrap !important;
    justify-content: center !important;
    align-items: flex-start !important;
    gap: 32px !important;
    width: 100% !important;
    max-width: 1100px !important;
    margin: 0 auto !important;
    padding: 0.5rem 0 0.75rem 0 !important;
}
.netflix-profile {
    width: 152px !important;
    display: inline-flex !important;
    flex-direction: column !important;
    align-items: center !important;
    position: relative !important;
    vertical-align: top !important;
}
.netflix-profile-card {
    position: relative !important;
    width: 152px !important;
    height: 152px !important;
}
.netflix-profile-card .stButton > button {
    width: 152px !important;
    height: 152px !important;
    min-height: 152px !important;
    border-radius: 10px !important;
    background: linear-gradient(180deg, #1a4a31 0%, #0d2418 100%) !important;
    border: 2px solid rgba(255,255,255,0.14) !important;
    color: #FFFFFF !important;
    font-size: 4.2rem !important;
    font-weight: 700 !important;
    padding: 0 !important;
    margin: 0 !important;
    box-shadow: none !important;
    transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease !important;
}
.netflix-profile-card .stButton > button:hover {
    transform: scale(1.08) !important;
    border-color: #FFFFFF !important;
    box-shadow: 0 10px 28px rgba(0,0,0,0.45), 0 0 18px rgba(74, 222, 128, 0.22) !important;
}
.netflix-profile.add-profile .stButton > button {
    background: rgba(255,255,255,0.02) !important;
    border: 2px dashed rgba(255,255,255,0.28) !important;
    color: #D1D5DB !important;
    font-size: 3rem !important;
}
.netflix-profile.add-profile .stButton > button:hover {
    border-color: #FFFFFF !important;
    color: #FFFFFF !important;
    background: rgba(255,255,255,0.05) !important;
}
.netflix-profile-name {
    margin-top: 14px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    color: #BFC7D1 !important;
    text-align: center !important;
    line-height: 1.25 !important;
    transition: color 0.2s ease !important;
}
.netflix-profile-role {
    margin-top: 6px !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
    color: #7DD3A7 !important;
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 999px !important;
    padding: 3px 10px !important;
    display: inline-block !important;
}
.netflix-profile:hover .netflix-profile-name {
    color: #FFFFFF !important;
}
.profile-edit-overlay {
    position: absolute;
    right: 10px;
    bottom: 10px;
    width: 36px;
    height: 36px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.78);
    border: 1.5px solid rgba(255,255,255,0.22);
    color: #FFFFFF;
    font-size: 1rem;
    box-shadow: 0 4px 12px rgba(0,0,0,0.35);
    pointer-events: none;
}
.netflix-manage-wrap {
    display: flex;
    justify-content: center;
    margin-top: 1.4rem;
    margin-bottom: 0.4rem;
}
.netflix-manage-wrap .stButton > button {
    min-width: 220px !important;
    height: 48px !important;
    border-radius: 6px !important;
    background: transparent !important;
    color: #D1D5DB !important;
    border: 1.5px solid rgba(255,255,255,0.28) !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.6px !important;
    box-shadow: none !important;
}
.netflix-manage-wrap .stButton > button:hover {
    color: #FFFFFF !important;
    border-color: #FFFFFF !important;
    background: rgba(255,255,255,0.04) !important;
}

/* Dialog */
div[data-testid="stModalBackdrop"], div[data-testid="stDialogBackdrop"] {
    background: rgba(0,0,0,0.45) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
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
    border-radius: 18px !important;
    border: 1.5px solid rgba(74, 222, 128, 0.55) !important;
    background: #12161A !important;
    background-color: #12161A !important;
    box-shadow: 0 24px 60px rgba(0,0,0,0.72) !important;
    max-width: 340px !important;
    width: 340px !important;
    padding: 1.4rem 1.4rem 1.2rem 1.4rem !important;
}
div[data-testid="stDialog"] h2,
div[role="dialog"] h2 {
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    text-align: center !important;
}
div[data-testid="stDialog"] input[type="password"],
div[role="dialog"] input[type="password"] {
    height: 52px !important;
    border-radius: 12px !important;
    border: 1.5px solid rgba(74, 222, 128, 0.7) !important;
    background: #0B0E11 !important;
    color: #FFFFFF !important;
    font-size: 1.5rem !important;
    text-align: center !important;
    letter-spacing: 8px !important;
}
.sticker-modal-grid div[data-testid="stColumn"] button {
    font-size: 2.1rem !important;
    height: 62px !important;
    width: 100% !important;
    padding: 0 !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    border-radius: 16px !important;
    background: linear-gradient(145deg, #113f26 0%, #082416 100%) !important;
    border: 2px solid #22C55E !important;
}
</style>
"""
st.markdown(ARL_GREEN_CSS, unsafe_allow_html=True)


# ===========================================================================
# 8. SESSION STATE
# ===========================================================================
DEFAULT_SESSION = {
    "logged_in": False,
    "hr_name": "",
    "hr_email": "",
    "hr_role": "Recruiter",
    "pending_otp_email": None,
    "pending_pin_email": None,
    "register_mode": False,
    "screening_results": [],
    "show_download_page": False,
    "manage_profiles_mode": False,
}

for k, v in DEFAULT_SESSION.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "is_desktop_mode" not in st.session_state:
    st.session_state.is_desktop_mode = (st.query_params.get("mode") == "desktop")

is_desktop_mode = st.session_state.is_desktop_mode or (st.query_params.get("mode") == "desktop")


# ===========================================================================
# 9. DOWNLOAD PAGE
# ===========================================================================
def render_download_landing_page(exe_direct_url: str):
    c_back, _ = st.columns([2.5, 7.5])
    with c_back:
        if st.button("⬅️ Back to Web Portal", use_container_width=True, key="back_to_portal_from_dl"):
            st.session_state.show_download_page = False
            st.rerun()

    st.markdown(f"""
        <div style="
            text-align: center; padding: 3rem 1.5rem 2.2rem 1.5rem;
            background: linear-gradient(180deg, rgba(34, 197, 94, 0.22) 0%, rgba(8, 28, 18, 0.95) 100%);
            border: 1.5px solid rgba(74, 222, 128, 0.35); border-top: 4px solid #4ADE80;
            border-radius: 24px; margin-bottom: 2.5rem; box-shadow: 0 16px 45px rgba(0, 0, 0, 0.6);
        ">
            <div style="display: inline-block; background: rgba(34, 197, 94, 0.18); color: #4ADE80; border: 1px solid #22C55E; padding: 6px 18px; border-radius: 30px; font-size: 0.78rem; font-weight: 800; letter-spacing: 1.5px; margin-bottom: 1.2rem; text-transform: uppercase;">
                🪟 BUILT FOR WINDOWS 10 / 11
            </div>
            <h1 style="font-size: 3.2rem; font-weight: 800; color: #FFFFFF; margin: 0 0 1rem 0; line-height: 1.15;">
                Arl TalentMatch for Windows
            </h1>
            <p style="color: #CBD5E1; font-size: 1.15rem; max-width: 680px; margin: 0 auto 2.2rem auto; line-height: 1.6;">
                Run Attock Refinery Limited's enterprise candidate extraction, AI matching, and cloud recruitment pipeline as a dedicated, high-speed desktop software.
            </p>
            <a href="{exe_direct_url}" target="_blank" style="
                display: inline-flex; align-items: center; gap: 12px; background: linear-gradient(135deg, #16A34A 0%, #15803D 100%);
                color: #FFFFFF !important; font-size: 1.18rem; font-weight: 800; padding: 1.1rem 2.8rem; border-radius: 14px;
                text-decoration: none; box-shadow: 0 10px 30px rgba(22, 163, 74, 0.45); border: 1.5px solid #4ADE80;
            ">
                <span>⬇</span> Download for Windows · ARL-HireMatrix-Pro.msi (Free)
            </a>
            <div style="margin-top: 18px; color: #86EFAC; font-size: 0.85rem; font-family: 'JetBrains Mono', monospace;">
                Official Windows Installer • 64-bit Architecture • Instant Cloud Sync
            </div>
        </div>
    """, unsafe_allow_html=True)


if st.session_state.show_download_page:
    render_download_landing_page(EXE_DOWNLOAD_URL)
    st.stop()


# ===========================================================================
# 10. DIALOGS
# ===========================================================================
if hasattr(st, "dialog"):
    @st.dialog("Enter PIN")
    def show_pin_dialog(target_email, p_name, p_role):
        components.html("""
        <script>
        (function autoFocusPin() {
            let attempts = 0;
            const timer = setInterval(function() {
                const doc = window.parent.document;
                const input = doc.querySelector('div[role="dialog"] input[type="password"], div[data-testid="stDialog"] input[type="password"]');
                if (input) {
                    input.focus();
                    input.select();
                    input.addEventListener('input', function() {
                        if (this.value.length === 4) {
                            const form = this.closest('form');
                            if (form) {
                                const btn = form.querySelector('button[type="submit"]');
                                if (btn) btn.click();
                            }
                        }
                    }, { once: true });
                    clearInterval(timer);
                }
                if (++attempts > 50) clearInterval(timer);
            }, 40);
        })();
        </script>
        """, height=0, width=0)

        st.markdown(f"""
            <div style="text-align:center; margin-bottom: 0.8rem;">
                <div style="font-size: 0.92rem; color: #9CA3AF;">Secure sign-in for</div>
                <div style="font-size: 1.05rem; font-weight: 700; color: #FFFFFF; margin-top: 4px;">{p_name}</div>
            </div>
        """, unsafe_allow_html=True)

        with st.form(f"pin_form_clean_{target_email}"):
            pin_input = st.text_input(
                "PIN",
                type="password",
                max_chars=4,
                placeholder="••••",
                label_visibility="collapsed",
                key=f"clean_pin_{target_email}",
            )
            submitted = st.form_submit_button("Continue", use_container_width=True)

        if submitted:
            success, name, role = verify_employee_pin(target_email, pin_input)
            if success:
                st.session_state.logged_in = True
                st.session_state.hr_name = name or p_name
                st.session_state.hr_email = target_email
                st.session_state.hr_role = role or p_role
                st.session_state.manage_profiles_mode = False
                st.rerun()
            else:
                st.error("Incorrect PIN")

    @st.dialog("Edit Profile")
    def show_sticker_dialog(target_email, p_name):
        st.markdown(f"""
            <div style="text-align:center; margin-bottom: 0.8rem;">
                <div style="font-size:1rem; font-weight:700; color:#FFFFFF;">{p_name}</div>
                <div style="font-size:0.85rem; color:#9CA3AF;">Choose a badge or remove this profile</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sticker-modal-grid">', unsafe_allow_html=True)
        cols = st.columns(4)
        sticker_items = list(PROFESSIONAL_STICKERS.items())
        for idx, (stk, title) in enumerate(sticker_items):
            with cols[idx % 4]:
                if st.button(stk, key=f"stk_select_{target_email}_{idx}", help=title, use_container_width=True):
                    update_user_sticker(target_email, stk)
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑 Delete Profile", key=f"del_prof_dialog_{target_email}", use_container_width=True):
                delete_employee_profile(target_email)
                st.rerun()
        with c2:
            if st.button("Done", key=f"close_stk_dialog_btn_{target_email}", use_container_width=True):
                st.rerun()
else:
    def show_pin_dialog(*args, **kwargs):
        pass
    def show_sticker_dialog(*args, **kwargs):
        pass


# ===========================================================================
# 11. FILE EXTRACTION
# ===========================================================================
def extract_text_from_image(file_bytes: bytes) -> str:
    import pytesseract
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert("L")
        return pytesseract.image_to_string(img)
    except Exception as e:
        st.error(f"⚠️ Image OCR failed: {e}")
        return ""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    import pytesseract

    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if len(page_text.strip()) > 40:
                    text_parts.append(f"\\n--- [PAGE {idx}] ---\\n{page_text}")
                else:
                    try:
                        pil_img = page.to_image(resolution=150).original.convert("L")
                        ocr_text = pytesseract.image_to_string(pil_img)
                        if ocr_text.strip():
                            text_parts.append(f"\\n--- [PAGE {idx} (OCR)] ---\\n{ocr_text}")
                    except Exception:
                        pass
    except Exception as e:
        st.error(f"⚠️ PDF extraction failed: {e}")
        return ""

    return "\\n\\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx
    try:
        document = docx.Document(io.BytesIO(file_bytes))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    txt = safe_str(cell.text)
                    if txt:
                        parts.append(txt)
        return "\\n".join(parts)
    except Exception as e:
        st.error(f"⚠️ DOCX extraction failed: {e}")
        return ""


def extract_resume_text(uploaded_file):
    name = uploaded_file.name.lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    try:
        file_bytes = uploaded_file.getvalue()
        if ext == "pdf":
            return extract_text_from_pdf(file_bytes)
        if ext == "docx":
            return extract_text_from_docx(file_bytes)
        if ext in ["png", "jpg", "jpeg"]:
            return extract_text_from_image(file_bytes)
    except Exception as exc:
        st.error(f"⚠️ Could not read {uploaded_file.name}: {exc}")
    return ""


# ===========================================================================
# 12. GROQ AI
# ===========================================================================
def build_multi_candidate_extraction_prompt(resume_text: str) -> str:
    return f"""You are an expert HR Data Extraction Specialist for Attock Refinery Limited (ARL).
Analyze the following document text carefully. The document contains candidate CVs/resumes.

CRITICAL RULES TO AVOID ERRORS:
1. FATHER IS NOT A CANDIDATE:
   - NEVER create a candidate entry for a Father, Mother, or Guardian!
   - Words like 'Father Name', 'S/O', 'D/O', or 'W/O' belong strictly inside the candidate's "father_name" field.
2. FULL NAMES ONLY:
   - Extract the COMPLETE name of the applicant.
3. NO DUPLICATE CLONES:
   - Do NOT split one applicant's CV into two candidates.

Return a strictly valid JSON object matching this schema:
{{
  "candidates": [
    {{
      "name": "Complete Candidate Name",
      "father_name": "Father Name or Not Provided",
      "education": "Qualification / Degree Title",
      "cgpa": "CGPA / GPA / Percentage or Not Provided",
      "passing_year": "Passing / Graduation Year or Not Provided",
      "university_name": "Institute / Board / University Name or Not Provided",
      "dob": "Date of Birth or Not Provided",
      "email": "Candidate Email Address or Not Provided",
      "phone": "Candidate Phone Number or Not Provided",
      "experience_years": "Total Experience",
      "latest_experience": "Latest job role or company or Not Provided",
      "reference": "Reference contacts or Not Provided",
      "skills": "Key technical / engineering skills"
    }}
  ]
}}

Rules:
- If a field is not mentioned, use 'Not Provided'.
- Return ONLY the JSON object.

DOCUMENT TEXT:
{resume_text[:28000]}
"""


def extract_candidates_for_repo(client, resume_text: str, file_name: str):
    if not client or not resume_text.strip():
        return []

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": build_multi_candidate_extraction_prompt(resume_text)}],
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=0.1,
        )
        raw_content = response.choices[0].message.content.strip()
        parsed = json.loads(raw_content)

        if isinstance(parsed, dict):
            candidates_list = parsed.get("candidates", [])
            if not candidates_list and "name" in parsed:
                candidates_list = [parsed]
        elif isinstance(parsed, list):
            candidates_list = parsed
        else:
            candidates_list = []

        cleaned = []
        for cand in candidates_list:
            name = safe_str(cand.get("name"), "Unknown")
            father_name = safe_str(cand.get("father_name"), "Not Provided")

            cleaned.append({
                "file_name": file_name,
                "name": name or "Unknown",
                "father_name": father_name,
                "education": safe_str(cand.get("education"), "Not Provided"),
                "cgpa": safe_str(cand.get("cgpa"), "Not Provided"),
                "passing_year": safe_str(cand.get("passing_year"), "Not Provided"),
                "university_name": safe_str(cand.get("university_name"), "Not Provided"),
                "dob": safe_str(cand.get("dob"), "Not Provided"),
                "email": safe_str(cand.get("email"), "Not Provided"),
                "phone": safe_str(cand.get("phone"), "Not Provided"),
                "experience_years": safe_str(cand.get("experience_years"), "0"),
                "latest_experience": safe_str(cand.get("latest_experience"), "Not Provided"),
                "reference": safe_str(cand.get("reference"), "Not Provided"),
                "skills": safe_str(cand.get("skills"), "Not Provided"),
            })

        final_candidates = []
        seen = set()

        for cand in cleaned:
            dedupe_key = (
                normalize_email(cand["email"]),
                normalize_phone(cand["phone"]),
                cand["name"].lower(),
                cand["father_name"].lower(),
                cand["education"].lower(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            final_candidates.append(cand)

        ghost_filtered = []
        for cand in final_candidates:
            is_ghost = False
            for existing in ghost_filtered:
                same_edu = cand["education"] != "Not Provided" and cand["education"].lower() == existing["education"].lower()
                name_is_father = cand["name"].lower() == existing["father_name"].lower()
                if same_edu and name_is_father:
                    is_ghost = True
                    break
            if not is_ghost:
                ghost_filtered.append(cand)

        return ghost_filtered

    except Exception as exc:
        st.error(f"⚠️ Extraction failed for **{file_name}**: {exc}")
        return []


def evaluate_candidate_against_jd(client, candidate_row, jd_text: str):
    if not client:
        return 0.0, True, []

    try:
        summary = (
            f"Name: {candidate_row['Name']}, "
            f"Education: {candidate_row['Qualification']}, "
            f"Institute: {candidate_row['Institute']}, "
            f"Experience: {candidate_row['Experience']}, "
            f"Latest Role: {candidate_row['Latest Experience']}"
        )

        prompt = f"""You are an expert HR recruiter AI for Attock Refinery Limited (ARL). Evaluate the CANDIDATE PROFILE against the JOB DESCRIPTION.

CANDIDATE: {summary}
JOB DESCRIPTION: {jd_text}

Return ONLY a valid JSON object:
{{
  "match_score": A number between 0 and 100,
  "is_relevant": true or false,
  "missing_skills": ["List", "of", "missing skills"]
}}
"""

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
    if not client:
        return "Groq client unavailable."
    try:
        prompt = f"""Based on candidate skills '{skills_text}' and ARL Refinery job title '{job_title}', generate 5 precise technical and behavioral interview questions with model answers. Format clearly with Markdown bullet points. Do not include raw HTML."""
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw_output = response.choices[0].message.content.strip()
        return raw_output.replace("<br>", "\\n").replace("<br/>", "\\n").replace("<BR>", "\\n")
    except Exception as e:
        return f"Could not generate interview questions: {e}"


# ===========================================================================
# 13. AUTH SCREEN
# ===========================================================================
if not st.session_state.logged_in:
    saved_profiles = get_all_verified_profiles()

    col_c1, col_c2, col_c3 = st.columns([1, 4.2, 1])
    with col_c2:
        if not is_desktop_mode:
            c_banner_l, c_banner_r, c_banner_x = st.columns([6.8, 2.5, 0.7], vertical_alignment="center")
            with c_banner_l:
                st.caption("Prefer a standalone PC software?")
            with c_banner_r:
                if st.button("💻 Get App", key="dl_btn_login_top", use_container_width=True):
                    st.session_state.show_download_page = True
                    st.rerun()
            with c_banner_x:
                if st.button("✕", key="dismiss_desktop_banner", help="Hide in Desktop App"):
                    st.session_state.is_desktop_mode = True
                    st.rerun()

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

            elif saved_profiles and not st.session_state.register_mode:
                manage_mode = st.session_state.manage_profiles_mode

                st.markdown("""
                    <div class="netflix-shell">
                        <div class="netflix-heading">
                            <h2>Select Executive Profile</h2>
                            <p>Choose your profile to continue. Manage mode lets you edit profile badges and settings.</p>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                outer_left, outer_center, outer_right = st.columns([1, 10, 1])

                with outer_center:
                    grid_cols = st.columns(min(len(saved_profiles) + 1, 6))
                    all_cards = saved_profiles + [("__ADD__", "Add Profile", "", "Register", "＋")]

                    for idx, item in enumerate(all_cards):
                        col = grid_cols[idx % len(grid_cols)]
                        with col:
                            if item[0] == "__ADD__":
                                st.markdown('<div class="netflix-profile add-profile">', unsafe_allow_html=True)
                                st.markdown('<div class="netflix-profile-card">', unsafe_allow_html=True)
                                if st.button("＋", key="netflix_add_profile_btn", help="Add Profile", use_container_width=True):
                                    st.session_state.register_mode = True
                                    st.rerun()
                                st.markdown("</div>", unsafe_allow_html=True)
                                st.markdown("""
                                    <div class="netflix-profile-name">Add Profile</div>
                                    <div class="netflix-profile-role">Register</div>
                                """, unsafe_allow_html=True)
                                st.markdown("</div>", unsafe_allow_html=True)
                            else:
                                p_email, p_name, p_pin, p_role, p_sticker = item
                                st.markdown('<div class="netflix-profile">', unsafe_allow_html=True)
                                st.markdown('<div class="netflix-profile-card">', unsafe_allow_html=True)

                                if st.button(p_sticker, key=f"netflix_profile_{idx}", help=p_name, use_container_width=True):
                                    if manage_mode:
                                        show_sticker_dialog(p_email, p_name)
                                    else:
                                        show_pin_dialog(p_email, p_name, p_role)

                                if manage_mode:
                                    st.markdown('<div class="profile-edit-overlay">✎</div>', unsafe_allow_html=True)

                                st.markdown("</div>", unsafe_allow_html=True)
                                st.markdown(f'''
                                    <div class="netflix-profile-name">{p_name}</div>
                                    <div class="netflix-profile-role">{p_role}</div>
                                ''', unsafe_allow_html=True)
                                st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown('<div class="netflix-manage-wrap">', unsafe_allow_html=True)
                    if not manage_mode:
                        if st.button("✏ Manage Profiles", key="toggle_manage_profiles_btn"):
                            st.session_state.manage_profiles_mode = True
                            st.rerun()
                    else:
                        if st.button("Done", key="toggle_done_manage_profiles_btn"):
                            st.session_state.manage_profiles_mode = False
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

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

                col_r1, col_r2 = st.columns(2)
                if submit_reg:
                    if not reg_name.strip() or not reg_email.strip() or not reg_pass.strip():
                        st.warning("Please verify all required fields.")
                    else:
                        success, msg = register_initial_employee(reg_name, reg_email, reg_pass, sticker=reg_sticker)
                        if success:
                            st.success(msg)
                            st.session_state.pending_otp_email = normalize_email(reg_email)
                            st.session_state.register_mode = False
                            st.rerun()
                        else:
                            st.error(msg)

                with col_r2:
                    if st.button("Back to Profiles", use_container_width=True, key="back_to_prof_auth_btn"):
                        st.session_state.register_mode = False
                        st.rerun()

    st.stop()


# ===========================================================================
# 14. MAIN APP
# ===========================================================================
df_all = load_database()
total_repo_db = len(df_all)
latest_candidate = df_all.iloc[-1]["Name"] if not df_all.empty else "None"

col_n1, col_n2 = st.columns([7.8, 2.2], vertical_alignment="center")
with col_n1:
    st.markdown(f"""
        <div class="top-navbar" style="display: flex; align-items: center; gap: 16px;">
            <div style="
                width: 48px; height: 48px; border-radius: 14px;
                background: linear-gradient(135deg, rgba(74, 222, 128, 0.25) 0%, #082416 100%);
                border: 2px solid #4ADE80; display: flex; align-items: center; justify-content: center;
                box-shadow: 0 0 20px rgba(34, 197, 94, 0.4); flex-shrink: 0;
            ">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 2 22 7.5 22 16.5 12 22 2 16.5 2 7.5"></polygon>
                </svg>
            </div>
            <div>
                <h2 class="top-brand-title" style="margin: 0; font-size: 1.35rem; color: #FFFFFF;">Arl TalentMatch: <span style="color: #4ADE80;">AI-Driven Automated CV Parser & JD Matcher</span></h2>
                <p class="top-brand-subtitle" style="margin: 4px 0 0 0;">Attock Refinery Limited • Active: <b>{st.session_state.get('hr_name', 'Recruiter')}</b> ({st.session_state.get('hr_email', 'admin@arl.com.pk')}) • Role: <b>{st.session_state.get('hr_role', 'Recruiter')}</b></p>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_n2:
    if not is_desktop_mode:
        col_dl_top, col_lock_top = st.columns(2)
        with col_dl_top:
            if st.button("💻 App", use_container_width=True, key="btn_open_dl_page_top", help="Download Windows Desktop App"):
                st.session_state.show_download_page = True
                st.rerun()
        with col_lock_top:
            if st.button("🚪 Lock", use_container_width=True, key="lock_portal_btn_top", help="Lock Session"):
                st.session_state.logged_in = False
                st.session_state.hr_name = ""
                st.session_state.hr_email = ""
                st.session_state.hr_role = "Recruiter"
                st.session_state.screening_results = []
                st.session_state.manage_profiles_mode = False
                try:
                    st.query_params.clear()
                    if is_desktop_mode:
                        st.query_params["mode"] = "desktop"
                except Exception:
                    pass
                st.rerun()
    else:
        if st.button("🚪 Lock Portal", use_container_width=True, key="lock_portal_btn_top_desktop", help="Lock Session"):
            st.session_state.logged_in = False
            st.session_state.hr_name = ""
            st.session_state.hr_email = ""
            st.session_state.hr_role = "Recruiter"
            st.session_state.screening_results = []
            st.session_state.manage_profiles_mode = False
            try:
                st.query_params.clear()
                if is_desktop_mode:
                    st.query_params["mode"] = "desktop"
            except Exception:
                pass
            st.rerun()

st.markdown(f"""
    <div class="corp-hero">
        <div class="corp-badge">
            <span>🟢 Multi-Stage ATS Session</span> • <span>Total Talent Pool: {total_repo_db} Candidates</span>
        </div>
        <h1>Attock Refinery Executive Suite</h1>
        <p>Welcome back, <b>{st.session_state.get('hr_name', 'Recruiter')}</b> — Latest Added: <b>{latest_candidate}</b> | All extracted resumes are automatically appended and permanently saved to Supabase Cloud.</p>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 1. Talent Repository (Upload)", "🎯 2. JD Screening & Matching", "🗄️ 3. Live Database & Screening Grids", "🛡️ 4. Admin Controls"])

with tab1:
    st.markdown('<div class="corp-card"><h4>📥 Step 1: Ingest & Parse Candidate Resumes (Single / Multi-CV PDF)</h4>', unsafe_allow_html=True)
    st.caption("Upload individual resumes or single bulk merged PDFs containing multiple candidates. AI will extract and append every candidate.")

    uploaded_repo_files = st.file_uploader(
        "Upload candidate resumes to repository",
        type=ACCEPTED_TYPES,
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    groq_client = get_groq_client()

    if st.button(
        "⚡ Extract & Save All Candidates to Master Database",
        type="primary",
        use_container_width=True,
        disabled=not (uploaded_repo_files and groq_client)
    ):
        extracted_batch = []
        progress = st.progress(0.0, text="Reading and extracting profiles via Groq...")

        total_files = len(uploaded_repo_files)
        for i, file in enumerate(uploaded_repo_files):
            progress.progress((i + 1) / max(total_files, 1), text=f"Processing {file.name}...")
            text = extract_resume_text(file)
            if text:
                candidates_in_file = extract_candidates_for_repo(groq_client, text, file.name)
                extracted_batch.extend(candidates_in_file)

        progress.empty()

        if extracted_batch:
            ins, skp = save_candidates_to_repository(extracted_batch)
            if skp > 0:
                st.success(f"🎉 Successfully extracted **{ins} new candidate(s)**! (Skipped **{skp} duplicate/failed profiles**)")
            else:
                st.success(f"🎉 Successfully extracted **{ins} candidate(s)** and appended to Supabase repository!")
            st.rerun()
        else:
            st.warning("No candidates could be extracted from the uploaded files.")

    st.markdown("</div>", unsafe_allow_html=True)

    df_repo = load_database()
    if not df_repo.empty:
        st.markdown('<div class="corp-card"><h4>📋 Current Candidates in Talent Repository</h4>', unsafe_allow_html=True)

        st.download_button(
            "📊 Download Master Talent Repository Report (.xlsx)",
            data=generate_repository_excel(df_repo),
            file_name="ARL_Master_Talent_Repository.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_repo_master_btn"
        )
        st.markdown("---")

        for idx, row in df_repo.iterrows():
            c_d1, c_d2, c_d3, c_d4 = st.columns([2, 2, 2, 1])
            with c_d1:
                st.write(f"👤 **{row['Name']}**")
            with c_d2:
                st.write(f"✉️ `{row['Email']}`")
            with c_d3:
                st.write(f"🎓 {row['Qualification']} ({row['Institute']})")
            with c_d4:
                safe_key = make_key("del_repo_btn", idx, row["Email"], row["Name"])
                if st.button("🗑️ Delete", key=safe_key, use_container_width=True):
                    target = row["Email"] if row["Email"] not in ["Not Provided", "Not Found", ""] else row["Name"]
                    delete_single_candidate_from_db(target)
                    st.success(f"Removed {row['Name']} from repository!")
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="corp-card"><h4>🎯 Step 2: Job Description Screening & Smart Matching</h4>', unsafe_allow_html=True)
    st.caption("Select Target Position from ARL Department & Job Titles hierarchy, or customize on the fly.")

    arl_catalog = load_arl_job_catalog()
    dept_options = list(arl_catalog.keys()) if arl_catalog else ["General"]

    col_dept, col_job = st.columns(2)
    with col_dept:
        chosen_dept = st.selectbox("🏢 Select ARL Department", dept_options, index=0)

    available_jobs = arl_catalog.get(chosen_dept, [])
    job_dropdown_list = available_jobs + ["✍️ Custom / Other Job Title..."]

    with col_job:
        chosen_job_item = st.selectbox(f"💼 Select Job Designation ({chosen_dept})", job_dropdown_list, index=0)

    if chosen_job_item == "✍️ Custom / Other Job Title...":
        jd_title_input = st.text_input("Enter Specific Job Designation", placeholder="e.g. Lead Turnaround Planning Specialist", key="custom_jd_title")
    else:
        jd_title_input = chosen_job_item

    st.info(f"Target Position Selected: **{jd_title_input}** *(Department: {chosen_dept})*")

    with st.expander("⚙️ Manage ARL Job Catalog (Add, Edit, or Remove Jobs & Departments)"):
        st.caption("Permanently modify or add job positions in the ARL database hierarchy.")
        m_tab1, m_tab2, m_tab3 = st.tabs(["➕ Add New Job", "✏️ Edit / Rename Job", "🗑️️ Delete Job"])

        with m_tab1:
            col_ad1, col_ad2 = st.columns(2)
            with col_ad1:
                dept_mode = st.radio("Department Mode", ["Existing Department", "New Department"], horizontal=True)
                if dept_mode == "Existing Department":
                    target_dept_add = st.selectbox("Choose Department", dept_options, key="add_exist_dept")
                else:
                    target_dept_add = st.text_input("New Department Name", placeholder="e.g. Digital Transformation", key="add_new_dept")
            with col_ad2:
                new_title_add = st.text_input("New Job Title", placeholder="e.g. Data Scientist")
                if st.button("➕ Add to ARL Catalog", use_container_width=True, key="btn_add_arl_job"):
                    if target_dept_add and new_title_add:
                        ok, msg = add_arl_job_to_db(target_dept_add, new_title_add)
                        if ok:
                            st.success(f"Added **{new_title_add}** under **{target_dept_add}**!")
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Please specify both department and job title.")

        with m_tab2:
            col_ed1, col_ed2 = st.columns(2)
            with col_ed1:
                edit_dept_sel = st.selectbox("Department", dept_options, key="edit_dept_sel")
                edit_jobs = arl_catalog.get(edit_dept_sel, [])
                edit_job_sel = st.selectbox("Select Job to Edit", edit_jobs if edit_jobs else [""], key="edit_job_sel")
            with col_ed2:
                updated_job_name = st.text_input("New Job Title Name", value=edit_job_sel if edit_job_sel else "", key="edit_job_input")
                updated_dept_name = st.text_input("New Department Name", value=edit_dept_sel, key="edit_dept_input")
                if st.button("💾 Update Job Title", use_container_width=True, key="btn_update_arl_job"):
                    if edit_job_sel and updated_job_name:
                        ok, msg = edit_arl_job_in_db(edit_dept_sel, edit_job_sel, updated_dept_name, updated_job_name)
                        if ok:
                            st.success("Designation updated successfully!")
                            st.rerun()
                        else:
                            st.error(msg)

        with m_tab3:
            col_del1, col_del2 = st.columns(2)
            with col_del1:
                del_dept_sel = st.selectbox("Department", dept_options, key="del_dept_sel")
            with col_del2:
                del_jobs = arl_catalog.get(del_dept_sel, [])
                del_job_sel = st.selectbox("Select Job to Remove", del_jobs if del_jobs else [""], key="del_job_sel")
                if st.button("🗑️ Delete Job Designation", type="secondary", use_container_width=True, key="btn_del_arl_job"):
                    if del_dept_sel and del_job_sel:
                        ok, msg = delete_arl_job_from_db(del_dept_sel, del_job_sel)
                        if ok:
                            st.success(f"Removed **{del_job_sel}** from catalog.")
                            st.rerun()
                        else:
                            st.error(msg)

    st.markdown("---")
    jd_desc_text = st.text_area(
        "Job Description & Requirements",
        height=120,
        placeholder="Paste detailed refinery requirements, qualifications, and skills here...",
        key="jd_desc_text_field"
    )

    st.markdown("**🎯 Select Minimum Passing Score Threshold (%)**")
    screening_threshold = st.slider(
        "Candidates scoring above this will be highlighted; all JD-relevant candidates remain reviewable.",
        min_value=0, max_value=100, value=50, step=5,
        label_visibility="collapsed",
        key="screening_threshold_slider_step2"
    )
    st.caption(f"Current Highlight Threshold: **{screening_threshold}%**")

    df_pool = load_database()
    groq_client_active = get_groq_client()

    if st.button(
        "⚡ Run AI Screening against Talent Pool",
        type="primary",
        use_container_width=True,
        disabled=not (jd_desc_text.strip() and jd_title_input.strip() and not df_pool.empty and groq_client_active),
        key="run_screening_btn_main"
    ):
        screened_results = []
        progress = st.progress(0.0, text="Evaluating candidates against ARL Job Description via Groq...")

        total_rows = len(df_pool)
        for idx, row in df_pool.iterrows():
            progress.progress((idx + 1) / max(total_rows, 1), text=f"Evaluating {row['Name']}...")
            score, is_relevant, missing = evaluate_candidate_against_jd(groq_client_active, row, jd_desc_text)

            if is_relevant:
                initial_status = "Shortlisted" if score >= screening_threshold else "Talent Pool"
                screened_results.append({
                    "job_title": jd_title_input,
                    "name": row["Name"],
                    "father_name": row["Father Name"],
                    "education": row["Qualification"],
                    "cgpa": row["CGPA"],
                    "passing_year": row["Passing Year"],
                    "university_name": row["Institute"],
                    "dob": row["DOB"],
                    "email": row["Email"],
                    "phone": row["Phone Number"],
                    "experience_years": row["Experience"],
                    "latest_experience": row["Latest Experience"],
                    "reference": row["Reference"],
                    "match_score": score,
                    "missing_skills": missing if isinstance(missing, list) else [],
                    "pipeline_status": initial_status,
                })

        progress.empty()
        screened_results.sort(key=lambda x: x["match_score"], reverse=True)
        st.session_state.screening_results = screened_results
        save_screened_to_supabase(screened_results)
        st.success(f"Screening complete! Evaluated {len(screened_results)} candidate(s) & saved to Supabase.")
        st.rerun()

    if df_pool.empty:
        st.info("⚠️ Talent repository is currently empty. Please upload resumes in **Step 1** first.")

    st.markdown("</div>", unsafe_allow_html=True)

    screening_results_safe = st.session_state.get("screening_results", [])
    if screening_results_safe:
        st.markdown('<div class="corp-card"><h4>📊 JD-Relevant Candidates & Recruiter Decision Pipeline</h4>', unsafe_allow_html=True)
        results = sorted(screening_results_safe, key=lambda x: x["match_score"], reverse=True)

        if not results:
            st.warning("⚠️ No candidates in the repository matched the requirements of this Job Description.")
        else:
            st.download_button(
                "📊 Download Master Screened Candidates Report (.xlsx)",
                data=generate_screening_excel(results),
                file_name="ARL_Screened_Candidates_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_screened_master_btn"
            )
            st.markdown("---")

        client = get_groq_client()

        for rank, cand in enumerate(results, start=1):
            score_cls = "score-high" if cand["match_score"] >= 75 else ("score-mid" if cand["match_score"] >= 40 else "score-low")

            with st.expander(f"#{rank} — {cand['name']} | Match Score: {cand['match_score']}% | Stage: {cand['pipeline_status']}", expanded=(rank == 1)):
                c1, c2 = st.columns([1.3, 1])

                with c1:
                    st.markdown(f"**💼 Target Role:** `{cand.get('job_title', 'Not Specified')}`")
                    st.markdown(f"**✉ Email:** `{cand['email']}` | **📞 Phone:** `{cand['phone']}`")
                    st.markdown(f"**👤 Father's Name:** {cand['father_name']}")
                    st.markdown(f"**🎓 Qualification:** {cand['education']} (CGPA: {cand['cgpa']} | Year: {cand['passing_year']})")
                    st.markdown(f"**🏫 Institute:** {cand['university_name']}")
                    st.markdown(f"**💼 Experience:** {cand['experience_years']} | **Latest:** {cand['latest_experience']}")
                    st.markdown(f"**🔗 Reference:** {cand['reference']}")
                    st.markdown(
                        f'<div class="metric-box" style="margin-top: 15px; width: 150px;"><div class="val {score_cls}">{cand["match_score"]}%</div><div class="lbl">Match Rating</div></div>',
                        unsafe_allow_html=True
                    )

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

                stage_key = make_key("stage_sel", rank, cand["email"], cand["name"])
                new_stage = st.selectbox("Update Stage", stage_options, index=stage_idx, key=stage_key)

                if new_stage != cand["pipeline_status"]:
                    cand["pipeline_status"] = new_stage
                    update_candidate_pipeline_status(cand["email"], new_stage)
                    update_screened_candidate_status(cand["email"], cand["job_title"], new_stage)
                    st.success(f"Pipeline stage updated to **{new_stage}**!")
                    st.rerun()

                st.markdown("---")
                q_key = make_key("gen_q", rank, cand["email"], cand["name"])
                if st.button(f"💡 Generate AI Interview Q&A for {cand['name']}", key=q_key):
                    if client:
                        with st.spinner("Generating tailored interview questions..."):
                            q_text = generate_ai_interview_questions(client, "General Engineering and Refinery Skills", cand["job_title"])
                            st.markdown("#### 🎯 AI Generated Interview Guide:")
                            st.markdown(q_text)
                    else:
                        st.error("Groq API key required.")

                if cand["email"] not in ["Not Provided", "Not Found", ""] and cand["email"]:
                    st.markdown("#### ✉ Conditional Email Dispatcher")

                    if cand["pipeline_status"] in ["Shortlisted", "Interview Scheduled"]:
                        default_msg = (
                            f"Dear {cand['name']},\\n\\n"
                            f"We were deeply impressed by your credentials and match score ({cand['match_score']}%) for the {cand['job_title']} position at Attock Refinery Limited (ARL). "
                            f"We would love to invite you for an interview round.\\n\\nBest Regards,\\nTeam ARL HR"
                        )
                        email_subject = f"Interview Invitation - {cand['job_title']}"
                        st.info(f"✓ Stage is **{cand['pipeline_status']}**: Interview Invitation template loaded.")
                    elif cand["pipeline_status"] == "Hired":
                        default_msg = (
                            f"Dear {cand['name']},\\n\\n"
                            f"Congratulations! We are thrilled to offer you the position of {cand['job_title']} at Attock Refinery Limited (ARL). Welcome aboard!\\n\\nBest Regards,\\nTeam ARL HR"
                        )
                        email_subject = f"Official Offer Letter - {cand['job_title']}"
                        st.success("✓ Stage is **Hired**: Official Offer Letter template loaded.")
                    else:
                        default_msg = (
                            f"Dear {cand['name']},\\n\\n"
                            f"Thank you for your interest in the {cand['job_title']} position at Attock Refinery Limited (ARL). "
                            f"Although your background is notable, we have decided to move forward with other candidates. We wish you the best.\\n\\nBest Regards,\\nTeam ARL HR"
                        )
                        email_subject = f"Application Status Update - {cand['job_title']}"
                        st.warning("⚠ Stage is **Rejected**: Regret template loaded.")

                    msg_key = make_key("inv_msg", rank, cand["email"], cand["name"])
                    invite_msg = st.text_area("Email Message", value=default_msg, key=msg_key)

                    send_key = make_key("send_inv", rank, cand["email"], cand["name"])
                    if st.button(f"📧 Send Email to {cand['name']}", key=send_key):
                        ok, res_m = send_smtp_email(cand["email"], email_subject, invite_msg)
                        if ok:
                            st.success(f"Email sent successfully to {cand['email']}!")
                        else:
                            st.error(res_m)

        st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="corp-card"><h4>🗄️ Live Database & Screening Grids</h4>', unsafe_allow_html=True)
    st.caption("Real-time synchronized candidate records from Supabase Cloud.")

    sub_grid_1, sub_grid_2 = st.tabs(["🎯 Screened Candidates Grid", "📥 Master Talent Pool Grid"])

    with sub_grid_1:
        df_screened = load_screened_database()
        if df_screened.empty:
            st.info("No candidates have been screened yet. Run AI Screening in Step 2 to populate this live cloud grid.")
        else:
            grid_s = df_screened.copy()
            grid_s.insert(0, "Sr. No.", range(1, len(grid_s) + 1))
            st.data_editor(grid_s, use_container_width=True, height=420, disabled=True, key="screened_grid_view_live")
            st.markdown("---")

            c_s1, c_s2 = st.columns([2, 1])
            with c_s1:
                st.download_button(
                    "📊 Download Screened Report (.xlsx)",
                    data=generate_screening_excel(df_screened.to_dict(orient="records")),
                    file_name="ARL_Screened_Candidates_Master.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_screened_master_grid_btn"
                )
            with c_s2:
                if st.button("🗑️ Clear Screened History", type="secondary", key="clear_screened_btn_grid", use_container_width=True):
                    clear_screened_database()
                    st.success("Screened candidate records cleared successfully!")
                    st.rerun()

    with sub_grid_2:
        df_db = load_database()
        if df_db.empty:
            st.info("Master database is currently empty. Upload resumes in Step 1.")
        else:
            grid_df = df_db.copy()
            grid_df.insert(0, "Sr. No.", range(1, len(grid_df) + 1))
            st.data_editor(grid_df, use_container_width=True, height=420, disabled=True, key="master_excel_grid_view")
            st.markdown("---")

            c_ex1, c_ex2 = st.columns([2, 1])
            with c_ex1:
                st.download_button(
                    "📊 Download Master Talent Repository Report (.xlsx)",
                    data=generate_repository_excel(df_db),
                    file_name="ARL_Master_Talent_Repository.xlsx",
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
    st.markdown('<div class="corp-card"><h4>🛡 Admin Access & Employee Management</h4></div>', unsafe_allow_html=True)

    if st.session_state.get("hr_role") != "Admin":
        st.error("⛔ **Access Denied**: You do not have Administrator privileges to view this control panel.")
    else:
        st.success("✓ Admin privileges active & verified.")

        st.markdown("### 👥 Active Employee Profiles & Confidential PINs")
        all_emps = get_all_verified_profiles_admin()
        st.markdown(f"**Total Active Registered Employees:** {len(all_emps)}")

        for emp_email, emp_name, emp_pin, emp_role, emp_sticker in all_emps:
            col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
            with col_a1:
                st.write(f"{emp_sticker} **{emp_name}** ({emp_email}) — *{emp_role}*")
            with col_a2:
                st.write(f"PIN: `{emp_pin}`")
            with col_a3:
                if normalize_email(emp_email) != normalize_email(st.session_state.get("hr_email", "")):
                    if st.button("🗑️ Revoke", key=make_key("rev_admin", emp_email), use_container_width=True):
                        delete_employee_profile(emp_email)
                        st.success(f"Access revoked for {emp_name}.")
                        st.rerun()
                else:
                    st.caption("Current User")
    st.markdown("</div>", unsafe_allow_html=True)
