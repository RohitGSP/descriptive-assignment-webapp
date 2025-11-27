# ================================================================
#  FINAL app.py — Instant Evaluation + Multi-Key Rotation
#  queued.html shows for MINIMUM 2 seconds before redirect
# ================================================================
import logging
import os
import tempfile
import time
import base64
import mimetypes
import random
from datetime import datetime
from pathlib import Path
from functools import wraps

import requests
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from flask import (
    Flask, render_template, request, redirect, session, url_for, jsonify
)

# ------------------------
# LOGGING SETUP
# ------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------
# PASSWORD PROTECTION
# ------------------------
APP_PASSWORD = "Rohit_Testbook_123"

# ------------------------
# FLASK APP
# ------------------------
app = Flask(__name__)
app.secret_key = "super_secret_key_change_this"

# ------------------------
# CONFIG
# ------------------------
SPREADSHEET_ID = "1St20jgiYOGlCKkweGo69D4hurzgV-9w4wJHnuad0QJ4"
SHEET_IB = "Assignment Name"
SHEET_KVS = "Assignment Name KVS"
SHEET_CAPF = "Assignment Name CAPF AC"
SHEET_CBSE = "Assignment Name CBSE Superintendent"
USER_DETAILS_SHEET = "User Details"
DRIVE_FOLDER_ID = "10ZtBLF_srBc_D0-XXXJynhPmwRMypSGi"

# MULTIPLE GEMINI API KEYS (AUTO-ROTATION)
GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
    os.getenv("GEMINI_API_KEY_4"),
    os.getenv("GEMINI_API_KEY_5"),
]

GEMINI_MODEL = "gemini-2.0-flash"


def get_available_gemini_key():
    """Pick a random API key that is not empty."""
    valid = [k for k in GEMINI_API_KEYS if k and k.strip()]
    if not valid:
        raise Exception("❌ No Gemini API keys found in Render ENV variables.")
    return random.choice(valid)

# ------------------------
# SERVICE ACCOUNT
# ------------------------
SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "sapient-depot-475407-n7",
    "private_key_id": "df1eb2fdbebf640ed6b67e4c4a7f3ca54e1ea0a0",
    "private_key": """-----BEGIN PRIVATE KEY-----
<YOUR PRIVATE KEY HERE>
-----END PRIVATE KEY-----""",
    "client_email": "rohit-selections@sapient-depot-475407-n7.iam.gserviceaccount.com",
    "client_id": "105687692028458251141",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url":
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "rohit-selections@sapient-depot-475407-n7.iam.gserviceaccount.com"
}

SERVICE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

service_creds = Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, scopes=SERVICE_SCOPES
)
gspread_client = gspread.authorize(service_creds)
drive_service = build("drive", "v3", credentials=service_creds)


CATEGORY_SHEETS = {
    "IB": SHEET_IB,
    "KVS": SHEET_KVS,
    "CAPF": SHEET_CAPF,
    "CBSE": SHEET_CBSE,
}


# ------------------------
# HELPERS
# ------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def get_worksheet(name):
    sh = gspread_client.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(name)


def list_assignments_from_sheet(sheet_name):
    ws = get_worksheet(sheet_name)
    rows = ws.get_all_values()
    return [row[0].strip() for row in rows[1:] if row and row[0].strip()]


def append_user_details_row(values):
    ws = get_worksheet(USER_DETAILS_SHEET)
    ws.append_row(values, value_input_option="RAW")


def get_assignment_all(sheet_name, assignment_name):
    ws = get_worksheet(sheet_name)
    rows = ws.get_all_values()
    for row in rows[1:]:
        if row[0].strip() == assignment_name:
            return row[1], row[2], row[3], row[4], row[5], row[6]
    return "", "", "", "", "", ""


# ------------------------
# DRIVE UPLOAD
# ------------------------
def upload_to_drive_safe(file_path: Path, filename: str) -> str:
    media = MediaFileUpload(str(file_path), resumable=False)
    metadata = {"name": filename, "parents": [DRIVE_FOLDER_ID]}

    created = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields="id",
        supportsAllDrives=True
    ).execute()

    # Make public
    drive_service.permissions().create(
        fileId=created["id"],
        body={"role": "reader", "type": "anyone"},
        fields="id",
        supportsAllDrives=True
    ).execute()

    return f"https://drive.google.com/file/d/{created['id']}/view"


# ------------------------
# GEMINI OCR (Instant)
# ------------------------
def extract_text_with_gemini(file_path: str, is_pdf: bool):
    api_key = get_available_gemini_key()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )

    with open(file_path, "rb") as f:
        file_data = base64.standard_b64encode(f.read()).decode()

    mime_type = "application/pdf" if is_pdf else (mimetypes.guess_type(file_path)[0] or "image/jpeg")

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": file_data}},
                {"text": "Extract handwritten text exactly as written."}
            ]
        }]
    }

    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    result = r.json()

    return (
        result.get("candidates", [{}])[0]
        .get("content", {}).get("parts", [{}])[0]
        .get("text", "")
    ).strip()


# ------------------------
# GEMINI EVALUATION (Instant)
# ------------------------
def evaluate_answer_with_gemini(prompt_text, question_text, model_answer_text, answer_text):
    api_key = get_available_gemini_key()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )

    prompt = f"""
{prompt_text}

QUESTION:
{question_text}

MODEL ANSWER:
{model_answer_text}

STUDENT ANSWER (OCR):
{answer_text}

Evaluate strictly using rubric. Output EXACT required format.
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    result = r.json()

    return (
        result.get("candidates", [{}])[0]
        .get("content", {}).get("parts", [{}])[0]
        .get("text", "")
    )


# =============================================================
# ROUTES
# =============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        return render_template("login.html", error="Invalid password")
    return render_template("login.html")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        name = request.form["name"]
        mobile = request.form["mobile"]
        email = request.form["email"]
        category = request.form["category"]
        language = request.form["language"]

        sheet_name = CATEGORY_SHEETS[category]
        assignments = list_assignments_from_sheet(sheet_name)

        selected_assignment = request.form.get("assignment_select")

        question_display = None
        if selected_assignment:
            p_en, p_hi, q_en, q_hi, m_en, m_hi = get_assignment_all(sheet_name, selected_assignment)
            question_display = q_en if language == "ENG" else q_hi

        return render_template(
            "upload.html",
            name=name,
            mobile=mobile,
            email=email,
            category=category,
            language=language,
            assignments=assignments,
            selected_assignment=selected_assignment,
            question_display=question_display
        )

    return render_template("index.html")


# =============================================================
# SUBMIT — Instant OCR + Evaluation
# =============================================================
@app.route("/submit", methods=["POST"])
@login_required
def submit_assignment():
    name = request.form["name"]
    mobile = request.form["mobile"]
    email = request.form["email"]
    category = request.form["category"]
    language = request.form["language"]
    assignment = request.form["assignment"]
    file = request.files["file"]

    filename = file.filename
    path = os.path.join(tempfile.gettempdir(), f"{int(time.time())}_{filename}")
    file.save(path)

    try:
        # -----------------------
        # Upload to Drive
        # -----------------------
        safe_name = name.replace(" ", "_")
        drive_filename = f"{safe_name}_{datetime.now().strftime('%d-%m-%y_%H-%M-%S')}{os.path.splitext(filename)[1]}"
        drive_link = upload_to_drive_safe(Path(path), drive_filename)

        append_user_details_row([
            name, mobile, email, assignment,
            drive_link, "Processing...",
            datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        ])

        # -----------------------
        # Get assignment details
        # -----------------------
        p_en, p_hi, q_en, q_hi, m_en, m_hi =
        get_assignment_all(CATEGORY_SHEETS[category], assignment)

        prompt = p_en if language == "ENG" else p_hi
        question = q_en if language == "ENG" else q_hi
        model = m_en if language == "ENG" else m_hi

        # -----------------------
        # INSTANT OCR
        # -----------------------
        extracted = extract_text_with_gemini(
            path, filename.lower().endswith(".pdf")
        )

        # -----------------------
        # INSTANT EVALUATION
        # -----------------------
        feedback = evaluate_answer_with_gemini(
            prompt, question, model, extracted
        )

        # -----------------------
        # Show queued.html for 2 seconds MINIMUM
        # -----------------------
        task_id = f"{int(time.time())}_{name.replace(' ', '_')}"
        session[task_id] = {
            "name": name,
            "assignment": assignment,
            "drive_link": drive_link,
            "feedback": feedback
        }

        return render_template(
            "queued.html",
            name=name,
            assignment=assignment,
            task_id=task_id,
            queue_position=1,
            estimated_time=2
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return f"An error occurred: {str(e)}", 500

    finally:
        if os.path.exists(path):
            os.remove(path)


@app.route("/status/<task_id>")
@login_required
def check_status(task_id):
    """Always return completed after 2 seconds."""
    return jsonify({"status": "completed"})


@app.route("/result/<task_id>")
@login_required
def show_result(task_id):
    """Show final evaluation result."""
    data = session.get(task_id)
    if not data:
        return "Task not found", 404

    return render_template(
        "result.html",
        name=data["name"],
        assignment=data["assignment"],
        drive_link=data["drive_link"],
        feedback=data["feedback"]
    )


# =============================================================
# RUN FLASK
# =============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
