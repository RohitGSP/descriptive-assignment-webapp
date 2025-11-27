import logging
import os
import tempfile
import time
import base64
import mimetypes
import queue
import threading
import random
from datetime import datetime
from pathlib import Path
from functools import wraps

import requests
import pytz
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
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQC0pDssEpofp9Nr
dC4Ql7EL8dzawNVkqBRHNYHPHGI5MbieLEB2v4X9Vd0+609S7wkWoyGZaSeiiPRS
hshVtMC+9cWLMKTiJ8YigLUTYBrrnc1i17m+1NlwiqmG+i5UEKHFC7nUXtOO8Ywc
eP6fbIUO+hot4QJQRkyCML3wk93eF/E96R8Om7tg/5IP9nunyThpGXEuUd9RbwgZ
OldDG3WlrkMqzIHEneBo9RTEZQ9Azo2GDBugjK76SoMD7H8HkEIYqGb4H9kdMjoU
1dEPgG75G1EE5BMhOfolx2da0GXcrKI2u+fHfgVDzh1f+tV3Lzu0ZX+Mc8Lo6lDg
LqAfwPfHAgMBAAECggEAB6MT28uI3uZMHPt8K79NJGX4l4iPMltjrPkHa0zkSfie
480JQOMVqba4VCFgU4vjO8FiK1JFgWywEsHJ5st8BKFvRxt437/yZVNdlHDYVEuq
5cDyEq4LIOPeiUe6y5PUNbFjRgmEgPwX3qCEBmlUgFXfxulVHRi1iQUWocQducwB
hkUQc871DElb+bi7LtexOk/NB/pyjOUnDQmNzLD+7P0v02MOzYvIV0ykvh8wId+H
Eu9v1x09aJCHTGw83qbyqYimxGbuNss7wiUbux6gNH4nf4iQU5BNpbxxvKOLigTg
SKgx/cWbXQ2WIdipimVqpH8zuQ4HQ8t9k/7q57yupQKBgQD3txNy2Eb2RLQsQW7D
Qa5cqgi18kUWBpv9ijzMS6Zdfv+GpOofYgaVDrwO3j0dtfjOptILV/uayqBhBjaB
vfzyV0KFLq5pF1S0iQVpAziXG2ySv22BB+UaOfQj+t9b38QZByE4DDTscCXnnBTY
Wg83jrILXPAZTxNCznDWSGRTtQKBgQC6rt/Z/XsXUbueG9R7wrYYcbPjpZeh3/TR
BSs98Clm6fF1FbZoTd8Mm97fbEX4BltjnXi6Wgg8L3xRUnl603Xmpy90SLLSXyjM
R8cYp51N0TzaLC6vaDbfhGV1sP85xpU9YNENWdilMLlCn+N6leI8i/xqQp82eRP0
bQhoAwVDCwKBgF7KCYEqzYyzIZbFuxKwcX43+nlVKaaSBOLyIO20DQc9752gQY6c
vhQPvVqbJBvYZEr/fuSkWD0VSGWYMQdYohBB38yC3m6MZPdob0+N0fvQnK1S3x4+
3SY6Avg5qXrIl4tUNRvzX9UR3Q9RpJBddfE2g17hw2aL4bzwrjDxJqL5AoGALVno
VbvHmG2pp4pZP0uZEy0kJ2yF/rQ6dEDONXjPhgnVN71zl7k7M4P2S86w3MUmlHef
6Z2PnJdomxTvIBCY9tSsqZIzpvmpHp9dVbb6dvoaz2GmYcRueDRgtYuvJSkB/mwz
vQuTnuXMS8wt5gzdbhoP0vymUwRs/ZczUJlTQOsCgYBRt8JJFdW1gETZkuW0YTFU
3pJTBopj8Xd128Z89CNPJCzyUYE0MKbo/lSkPoHJp5+BqoOQ0qVLgqgGpwrb1wE/
NwPfjn6wnaH3jhIE6MdftTkGxc6WOkYGHWuL4CGu2yt7GvbcZU+MAHVU+I3wE29X
NsZM40giRjwq1uMmJKHaDQ==
-----END PRIVATE KEY-----""",
    "client_email": "rohit-selections@sapient-depot-475407-n7.iam.gserviceaccount.com",
    "client_id": "105687692028458251141",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/rohit-selections@sapient-depot-475407-n7.iam.gserviceaccount.com"
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
# QUEUE & RATE LIMITING SETUP
# ------------------------
gemini_queue = queue.Queue()
drive_semaphore = threading.Semaphore(5)  # Max 5 concurrent Drive uploads
task_results = {}  # Store results: {task_id: {status, data}}
task_lock = threading.Lock()

# ------------------------
# RETRY DECORATOR WITH EXPONENTIAL BACKOFF
# ------------------------
def retry_with_backoff(max_retries=3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in str(e) or "quota" in error_msg or "rate" in error_msg:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Rate limit hit, attempt {attempt+1}/{max_retries}, waiting {wait_time:.2f}s")
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            raise
                    else:
                        raise
            raise Exception("Max retries exceeded")
        return wrapper
    return decorator

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

@retry_with_backoff(max_retries=3)
def upload_to_drive_safe(file_path: Path, filename: str) -> str:
    """Thread-safe Drive upload with semaphore and retry logic"""
    with drive_semaphore:
        try:
            media = MediaFileUpload(str(file_path), resumable=False)
            metadata = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
            created = drive_service.files().create(
                body=metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True
            ).execute()
            
            drive_service.permissions().create(
                fileId=created["id"],
                body={"role": "reader", "type": "anyone"},
                fields="id",
                supportsAllDrives=True
            ).execute()
            
            return f"https://drive.google.com/file/d/{created['id']}/view"
        except Exception as e:
            logger.error(f"Drive upload failed: {e}")
            raise

# ------------------------
# GEMINI OCR WITH RETRY
# ------------------------
@retry_with_backoff(max_retries=5)
def extract_text_with_gemini(file_path: str, is_pdf: bool = False) -> str:
    api_key = get_available_gemini_key()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )

    headers = {"Content-Type": "application/json"}

    with open(file_path, "rb") as f:
        file_data = base64.standard_b64encode(f.read()).decode("utf-8")

    mime_type = (
        "application/pdf"
        if is_pdf
        else (mimetypes.guess_type(file_path)[0] or "image/jpeg")
    )

    ocr_prompt = (
        "Extract ALL text from this document/image exactly as written. "
        "This is a handwritten answer sheet. Preserve the original structure, "
        "paragraphs, and formatting as much as possible. "
        "If there are any diagrams or drawings, describe them briefly. "
        "Output only the extracted text, nothing else."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": file_data,
                        }
                    },
                    {"text": ocr_prompt},
                ]
            }
        ]
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    content = (
        result.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )

    if not content:
        logger.error("Gemini OCR returned empty content: %s", result)
        return ""

    return content.strip()

# ------------------------
# GEMINI EVALUATION WITH RETRY
# ------------------------
@retry_with_backoff(max_retries=5)
def evaluate_answer_with_gemini(prompt_text, question_text, model_answer_text, answer_text):
    api_key = get_available_gemini_key()

url = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={api_key}"
)
    headers = {"Content-Type": "application/json"}
    
    full_prompt = f"""
=== EVALUATION INSTRUCTIONS & RUBRIC ===
{prompt_text}

=== QUESTION PROMPT (What student was asked) ===
{question_text}

=== MODEL ANSWER (Ideal Reference Answer) ===
{model_answer_text}

=== STUDENT'S SUBMITTED ANSWER (Extracted via OCR) ===
{answer_text}

=== FINAL INSTRUCTIONS ===
Now evaluate the Student's Submitted Answer by:
1. Comparing it against the Model Answer
2. Checking if it properly answers the Question Prompt
3. Applying the scoring rubric from the Evaluation Instructions

IMPORTANT:
- Follow the OUTPUT FORMAT specified in the Evaluation Instructions EXACTLY
- Do NOT use JSON format or markdown code blocks
- Output plain text only in the exact format specified in the rubric
- Be strict but fair in scoring
"""
    
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}]
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    result = resp.json()
    
    content = (
        result.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    
    if not content:
        logger.error("Gemini evaluation returned empty: %s", result)
        return "Error: Gemini returned empty response."
    
    return content

# ------------------------
# BACKGROUND QUEUE PROCESSOR
# ------------------------
def process_gemini_queue():
    """Background worker that processes Gemini requests with rate limiting"""
    logger.info("Gemini queue processor started")
    
    while True:
        try:
            task = gemini_queue.get(timeout=1)
            task_id = task['task_id']
            
            logger.info(f"Processing task {task_id}, queue size: {gemini_queue.qsize()}")
            
            # Update status to processing
            with task_lock:
                task_results[task_id] = {
                    'status': 'processing',
                    'message': 'Extracting text and evaluating answer...'
                }
            
            try:
                # Extract text
                extracted = extract_text_with_gemini(
                    task['file_path'], 
                    task['is_pdf']
                )
                
                if not extracted:
                    extracted = "[No text extracted - please check the file quality]"
                    logger.warning(f"Task {task_id}: Text extraction failed")
                
                # Evaluate answer
                feedback = evaluate_answer_with_gemini(
                    task['prompt'],
                    task['question'],
                    task['model'],
                    extracted
                )
                
                # Store result
                with task_lock:
                    task_results[task_id] = {
                        'status': 'completed',
                        'feedback': feedback,
                        'name': task['name'],
                        'assignment': task['assignment'],
                        'drive_link': task['drive_link']
                    }
                
                logger.info(f"Task {task_id} completed successfully")
                
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                with task_lock:
                    task_results[task_id] = {
                        'status': 'error',
                        'message': f'Processing failed: {str(e)}'
                    }
            
            finally:
                # Clean up temp file
                try:
                    if os.path.exists(task['file_path']):
                        os.remove(task['file_path'])
                except Exception as e:
                    logger.error(f"Failed to delete temp file: {e}")
            
            # Rate limiting: Wait 12 seconds between requests (5 RPM = 1 request per 12 sec)
            time.sleep(12)
            
            gemini_queue.task_done()
            
        except queue.Empty:
            time.sleep(1)
        except Exception as e:
            logger.error(f"Queue processor error: {e}")
            time.sleep(5)

# Start background worker thread
worker_thread = threading.Thread(target=process_gemini_queue, daemon=True)
worker_thread.start()

# ------------------------
# ROUTES
# ------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pwd = request.form.get("password")
        if pwd == APP_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        return render_template("login.html", error="Invalid password.")
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
            
            if language == "ENG":
                question_display = q_en
            else:
                question_display = q_hi
        
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
        # Upload to Drive (with retry and semaphore protection)
        safe_name = name.replace(" ", "_")
        drive_filename = f"{safe_name}_{datetime.now().strftime('%d-%m-%y_%H-%M-%S')}{os.path.splitext(filename)[1]}"
        drive_link = upload_to_drive_safe(Path(path), drive_filename)
        
        # Log to Google Sheets
        append_user_details_row([
            name,
            mobile,
            email,
            assignment,
            drive_link,
            "Processing...",
            datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        ])
        
        # Get assignment data
        p_en, p_hi, q_en, q_hi, m_en, m_hi = get_assignment_all(
            CATEGORY_SHEETS[category], assignment
        )
        
        if language == "ENG":
            prompt = p_en
            question = q_en
            model = m_en
        else:
            prompt = p_hi
            question = q_hi
            model = m_hi
        
        # Create unique task ID
        task_id = f"{int(time.time())}_{name.replace(' ', '_')}"
        
        # Add task to queue
        task = {
            'task_id': task_id,
            'file_path': path,
            'is_pdf': filename.lower().endswith(".pdf"),
            'prompt': prompt,
            'question': question,
            'model': model,
            'name': name,
            'assignment': assignment,
            'drive_link': drive_link
        }
        
        with task_lock:
            task_results[task_id] = {
                'status': 'queued',
                'message': 'Your submission is in queue for processing'
            }
        
        gemini_queue.put(task)
        
        queue_position = gemini_queue.qsize()
        estimated_time = queue_position * 12  # 12 seconds per request
        
        logger.info(f"Task {task_id} added to queue. Position: {queue_position}")
        
        return render_template(
            "queued.html",
            name=name,
            assignment=assignment,
            drive_link=drive_link,
            task_id=task_id,
            queue_position=queue_position,
            estimated_time=estimated_time
        )
        
    except Exception as e:
        logger.error(f"Error in submit_assignment: {e}")
        try:
            os.remove(path)
        except:
            pass
        return f"An error occurred: {str(e)}", 500

@app.route("/status/<task_id>")
@login_required
def check_status(task_id):
    """API endpoint to check task status"""
    with task_lock:
        result = task_results.get(task_id, {'status': 'not_found'})
    return jsonify(result)

@app.route("/result/<task_id>")
@login_required
def show_result(task_id):
    """Display final result"""
    with task_lock:
        result = task_results.get(task_id)
    
    if not result:
        return "Task not found", 404
    
    if result['status'] == 'completed':
        return render_template(
            "result.html",
            name=result['name'],
            assignment=result['assignment'],
            drive_link=result['drive_link'],
            feedback=result['feedback']
        )
    elif result['status'] == 'error':
        return f"Error: {result.get('message', 'Unknown error')}", 500
    else:
        return redirect(url_for('check_status', task_id=task_id))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
