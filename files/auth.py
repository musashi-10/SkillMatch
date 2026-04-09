"""
auth.py  –  SkillMatch Authentication Module
  - User registration (job_seeker | recruiter)
  - Email verification via token
  - Login with hashed passwords
  - SQLite-backed users table
"""

import sqlite3, os, hashlib, secrets, smtplib, re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

AUTH_DB = "auth.db"

# ── Email config (set env vars or update here) ────────────────────────────────
SMTP_HOST   = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT   = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER   = os.getenv("SMTP_USER", "")          # your Gmail address
SMTP_PASS   = os.getenv("SMTP_PASS", "")          # Gmail app-password
FROM_EMAIL  = os.getenv("FROM_EMAIL", SMTP_USER)
APP_URL     = os.getenv("APP_URL", "http://localhost:8501")

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'job_seeker',   -- job_seeker | recruiter
    company_name    TEXT,                                     -- recruiters only
    verified        INTEGER NOT NULL DEFAULT 0,
    verify_token    TEXT,
    token_expiry    TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);
"""

CREATE_RECRUITER_JOBS = """
CREATE TABLE IF NOT EXISTS recruiter_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id    INTEGER NOT NULL,
    job_title       TEXT    NOT NULL,
    company         TEXT    NOT NULL,
    location        TEXT    NOT NULL,
    work_mode       TEXT    NOT NULL,
    job_type        TEXT    NOT NULL,
    description     TEXT,
    required_skills TEXT,
    salary_range    TEXT,
    apply_link      TEXT    NOT NULL,
    posted_date     TEXT    DEFAULT (date('now')),
    is_active       INTEGER DEFAULT 1,
    FOREIGN KEY (recruiter_id) REFERENCES users(id)
);
"""

CREATE_APPLICATIONS = """
CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL,
    recruiter_id    INTEGER NOT NULL,
    applicant_name  TEXT    NOT NULL,
    applicant_email TEXT    NOT NULL,
    resume_text     TEXT,
    cover_letter    TEXT,
    status          TEXT    DEFAULT 'pending',   -- pending | verified | rejected
    verify_token    TEXT,
    token_expiry    TEXT,
    applied_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES recruiter_jobs(id)
);
"""


def _get_conn():
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(CREATE_USERS)
    cur.execute(CREATE_RECRUITER_JOBS)
    cur.execute(CREATE_APPLICATIONS)
    conn.commit()
    conn.close()


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _gen_token() -> str:
    return secrets.token_urlsafe(32)


def _token_expiry(hours: int = 24) -> str:
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[\w.+-]+@[\w-]+\.[a-z]{2,}$", email, re.I))


# ── Email sender ──────────────────────────────────────────────────────────────
def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send HTML email. Returns True on success."""
    if not SMTP_USER or not SMTP_PASS:
        # Dev mode: print token to console instead
        print(f"\n[DEV EMAIL] To: {to_email}\nSubject: {subject}\n{html_body}\n")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = FROM_EMAIL
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def _verification_email_html(name: str, token: str, email: str) -> str:
    link = f"{APP_URL}/?verify_token={token}&email={email}"
    return f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;background:#080C14;color:#E8EDF5;border-radius:16px">
        <h2 style="color:#38BDF8;font-size:22px">Verify your SkillMatch account</h2>
        <p>Hi <b>{name}</b>, welcome to SkillMatch!</p>
        <p>Click the button below to verify your email address. This link expires in 24 hours.</p>
        <a href="{link}" style="display:inline-block;margin:20px 0;padding:12px 28px;background:linear-gradient(135deg,#0EA5E9,#2563EB);color:#fff;border-radius:10px;text-decoration:none;font-weight:700">
            ✅ Verify Email
        </a>
        <p style="color:#4B6080;font-size:12px">If you didn't create this account, ignore this email.</p>
    </div>
    """


def _applicant_verify_email_html(applicant_name: str, job_title: str, company: str, token: str, app_id: int) -> str:
    link = f"{APP_URL}/?verify_application={token}&app_id={app_id}"
    return f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;background:#080C14;color:#E8EDF5;border-radius:16px">
        <h2 style="color:#38BDF8;font-size:22px">Confirm your job application</h2>
        <p>Hi <b>{applicant_name}</b>!</p>
        <p>You applied for <b>{job_title}</b> at <b>{company}</b> via SkillMatch.</p>
        <p>Please confirm your application by clicking the button below:</p>
        <a href="{link}" style="display:inline-block;margin:20px 0;padding:12px 28px;background:linear-gradient(135deg,#0EA5E9,#2563EB);color:#fff;border-radius:10px;text-decoration:none;font-weight:700">
            ✅ Confirm Application
        </a>
        <p style="color:#4B6080;font-size:12px">Link expires in 48 hours. If you didn't apply, ignore this email.</p>
    </div>
    """


# ── Public API ────────────────────────────────────────────────────────────────

def register_user(name: str, email: str, password: str, role: str, company_name: str = "") -> dict:
    """Register a new user. Returns {ok, message, user_id}."""
    if not name.strip():
        return {"ok": False, "message": "Name is required."}
    if not _is_valid_email(email):
        return {"ok": False, "message": "Invalid email address."}
    if len(password) < 6:
        return {"ok": False, "message": "Password must be at least 6 characters."}
    if role not in ("job_seeker", "recruiter"):
        return {"ok": False, "message": "Invalid role."}
    if role == "recruiter" and not company_name.strip():
        return {"ok": False, "message": "Company name is required for recruiters."}

    token = _gen_token()
    expiry = _token_expiry(24)
    try:
        conn = _get_conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO users (name, email, password_hash, role, company_name, verified, verify_token, token_expiry)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
        """, (name.strip(), email.lower().strip(), _hash(password),
              role, company_name.strip(), token, expiry))
        user_id = cur.lastrowid
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        return {"ok": False, "message": "Email already registered. Please log in."}

    sent = send_email(
        email,
        "Verify your SkillMatch account",
        _verification_email_html(name, token, email)
    )
    msg = "Account created! Check your email to verify." if sent else \
          "Account created! (Email delivery failed — contact support.)"
    return {"ok": True, "message": msg, "user_id": user_id}


def verify_email(email: str, token: str) -> dict:
    conn = _get_conn()
    cur  = conn.cursor()
    row  = cur.execute(
        "SELECT id, verify_token, token_expiry, verified FROM users WHERE email=?",
        (email.lower(),)
    ).fetchone()

    if not row:
        conn.close()
        return {"ok": False, "message": "User not found."}
    if row["verified"]:
        conn.close()
        return {"ok": True, "message": "Already verified! Please log in."}
    if row["verify_token"] != token:
        conn.close()
        return {"ok": False, "message": "Invalid verification token."}
    if datetime.utcnow() > datetime.fromisoformat(row["token_expiry"]):
        conn.close()
        return {"ok": False, "message": "Verification link expired. Please register again."}

    cur.execute("UPDATE users SET verified=1, verify_token=NULL WHERE id=?", (row["id"],))
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Email verified! You can now log in."}


def login_user(email: str, password: str) -> dict:
    """Returns {ok, message, user} where user has id, name, email, role, company_name."""
    conn = _get_conn()
    row  = conn.execute(
        "SELECT id, name, email, role, company_name, verified, password_hash FROM users WHERE email=?",
        (email.lower().strip(),)
    ).fetchone()
    conn.close()

    if not row:
        return {"ok": False, "message": "No account found with this email."}
    if row["password_hash"] != _hash(password):
        return {"ok": False, "message": "Incorrect password."}
    if not row["verified"]:
        return {"ok": False, "message": "Please verify your email first. Check your inbox."}

    return {"ok": True, "message": "Login successful!", "user": dict(row)}


# ── Recruiter Job CRUD ─────────────────────────────────────────────────────────

def recruiter_post_job(recruiter_id: int, job_data: dict) -> dict:
    required = ["job_title", "location", "work_mode", "job_type", "apply_link"]
    for f in required:
        if not job_data.get(f, "").strip():
            return {"ok": False, "message": f"'{f}' is required."}

    conn = _get_conn()
    cur  = conn.cursor()
    # Get recruiter's company
    rec  = conn.execute("SELECT company_name FROM users WHERE id=?", (recruiter_id,)).fetchone()
    company = (rec["company_name"] if rec else "") or job_data.get("company", "")

    cur.execute("""
        INSERT INTO recruiter_jobs
            (recruiter_id, job_title, company, location, work_mode, job_type,
             description, required_skills, salary_range, apply_link)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (recruiter_id, job_data["job_title"], company,
          job_data["location"], job_data["work_mode"], job_data["job_type"],
          job_data.get("description", ""), job_data.get("required_skills", ""),
          job_data.get("salary_range", ""), job_data["apply_link"]))
    job_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Job posted successfully!", "job_id": job_id}


def recruiter_get_jobs(recruiter_id: int) -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM recruiter_jobs WHERE recruiter_id=? ORDER BY posted_date DESC",
        (recruiter_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recruiter_delete_job(job_id: int, recruiter_id: int) -> dict:
    conn = _get_conn()
    conn.execute(
        "DELETE FROM recruiter_jobs WHERE id=? AND recruiter_id=?",
        (job_id, recruiter_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Job removed."}


def get_recruiter_applications(recruiter_id: int) -> list:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT a.*, rj.job_title, rj.company
        FROM applications a
        JOIN recruiter_jobs rj ON a.job_id = rj.id
        WHERE rj.recruiter_id = ?
        ORDER BY a.applied_at DESC
    """, (recruiter_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Applicant flow ─────────────────────────────────────────────────────────────

def submit_application(job_id: int, name: str, email: str,
                        resume_text: str, cover_letter: str) -> dict:
    if not _is_valid_email(email):
        return {"ok": False, "message": "Invalid email address."}
    if not name.strip():
        return {"ok": False, "message": "Name is required."}

    conn = _get_conn()
    job  = conn.execute(
        "SELECT job_title, company FROM recruiter_jobs WHERE id=?", (job_id,)
    ).fetchone()
    if not job:
        conn.close()
        return {"ok": False, "message": "Job not found."}

    # Check duplicate
    existing = conn.execute(
        "SELECT id FROM applications WHERE job_id=? AND applicant_email=?",
        (job_id, email.lower())
    ).fetchone()
    if existing:
        conn.close()
        return {"ok": False, "message": "You already applied for this job."}

    rec = conn.execute(
        "SELECT recruiter_id FROM recruiter_jobs WHERE id=?", (job_id,)
    ).fetchone()

    token  = _gen_token()
    expiry = _token_expiry(48)
    cur    = conn.cursor()
    cur.execute("""
        INSERT INTO applications
            (job_id, recruiter_id, applicant_name, applicant_email,
             resume_text, cover_letter, status, verify_token, token_expiry)
        VALUES (?,?,?,?,?,?,'pending',?,?)
    """, (job_id, rec["recruiter_id"], name.strip(), email.lower(),
          resume_text, cover_letter, token, expiry))
    app_id = cur.lastrowid
    conn.commit()
    conn.close()

    send_email(
        email,
        f"Confirm your application — {job['job_title']} at {job['company']}",
        _applicant_verify_email_html(name, job["job_title"], job["company"], token, app_id)
    )
    return {"ok": True, "message": "Application submitted! Check your email to confirm it."}


def verify_application(app_id: int, token: str) -> dict:
    conn = _get_conn()
    row  = conn.execute(
        "SELECT id, verify_token, token_expiry, status FROM applications WHERE id=?",
        (app_id,)
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "message": "Application not found."}
    if row["status"] == "verified":
        conn.close()
        return {"ok": True, "message": "Application already confirmed!"}
    if row["verify_token"] != token:
        conn.close()
        return {"ok": False, "message": "Invalid token."}
    if datetime.utcnow() > datetime.fromisoformat(row["token_expiry"]):
        conn.close()
        return {"ok": False, "message": "Verification link expired."}

    conn.execute(
        "UPDATE applications SET status='verified', verify_token=NULL WHERE id=?",
        (row["id"],)
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Application confirmed! The recruiter will be in touch."}


def update_application_status(app_id: int, status: str, recruiter_id: int) -> dict:
    if status not in ("pending", "verified", "rejected", "shortlisted"):
        return {"ok": False, "message": "Invalid status."}
    conn = _get_conn()
    conn.execute("""
        UPDATE applications SET status=?
        WHERE id=? AND recruiter_id=?
    """, (status, app_id, recruiter_id))
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"Status updated to '{status}'."}


# Initialise DB on import
init_auth_db()
