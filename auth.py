"""
auth.py  –  SkillMatch Authentication Module  (v2 – production-hardened)

Changes from v1:
  - Passwords hashed with bcrypt (was SHA-256 – trivially brute-forceable)
  - JWT access + refresh tokens (was session_state only)
  - Email validation via regex before DB insert
  - Password strength check (min 8 chars, 1 digit)
  - install: pip install bcrypt PyJWT
"""

import sqlite3, os, secrets, smtplib, re, time, json
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import bcrypt
import jwt   # PyJWT

_APP_ROOT = os.path.dirname(os.path.abspath(__file__))


def _data_dir() -> str:
    return os.path.abspath(os.getenv("SKILLMATCH_DATA_DIR", _APP_ROOT))


AUTH_DB = os.path.join(_data_dir(), "auth.db")
JWT_SECRET   = os.getenv("JWT_SECRET", secrets.token_hex(32))  # set in .env for prod!
JWT_ALGO     = "HS256"
ACCESS_TTL   = 60 * 60        # 1 hour
REFRESH_TTL  = 60 * 60 * 24 * 7  # 7 days

SMTP_HOST    = os.getenv("SMTP_HOST",  "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER",  "")
SMTP_PASS    = os.getenv("SMTP_PASS",  "")
FROM_EMAIL   = os.getenv("FROM_EMAIL", SMTP_USER)
APP_URL      = os.getenv("APP_URL",    "http://localhost:8501")


# ── Tables (unchanged schema — safe to run on existing DB) ────────────────────
CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'job_seeker',
    company_name    TEXT,
    verified        INTEGER NOT NULL DEFAULT 0,
    verify_token    TEXT,
    token_expiry    TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);"""

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
    is_premium      INTEGER DEFAULT 0,
    FOREIGN KEY (recruiter_id) REFERENCES users(id)
);"""

CREATE_APPLICATIONS = """
CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL,
    recruiter_id    INTEGER NOT NULL,
    applicant_name  TEXT    NOT NULL,
    applicant_email TEXT    NOT NULL,
    resume_text     TEXT,
    cover_letter    TEXT,
    status          TEXT    DEFAULT 'pending',
    verify_token    TEXT,
    token_expiry    TEXT,
    applied_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES recruiter_jobs(id)
);"""

# New: saved jobs per seeker
CREATE_SAVED_JOBS = """
CREATE TABLE IF NOT EXISTS saved_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    job_id      INTEGER NOT NULL,
    saved_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, job_id)
);"""

# New: subscription tiers (monetization-ready)
CREATE_SUBSCRIPTIONS = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL UNIQUE,
    plan        TEXT    NOT NULL DEFAULT 'free',   -- free | pro | recruiter_pro
    expires_at  TEXT,
    created_at  TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);"""

CREATE_USER_JOB_EVENTS = """
CREATE TABLE IF NOT EXISTS user_job_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    job_id      INTEGER NOT NULL,
    event_type  TEXT    NOT NULL,
    created_at  TEXT    DEFAULT (datetime('now'))
);"""

CREATE_SEEKER_PROFILES = """
CREATE TABLE IF NOT EXISTS seeker_profiles (
    user_id              INTEGER PRIMARY KEY,
    resume_text          TEXT,
    normalized_skills    TEXT,
    preferred_locations  TEXT,
    target_roles         TEXT,
    updated_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);"""

CREATE_JOB_ALERTS = """
CREATE TABLE IF NOT EXISTS job_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE,
    cadence         TEXT    NOT NULL DEFAULT 'weekly',
    location        TEXT,
    work_mode       TEXT,
    job_type        TEXT,
    keywords        TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    last_sent_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);"""

CREATE_ALERT_SENT_JOBS = """
CREATE TABLE IF NOT EXISTS alert_sent_jobs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    job_id     INTEGER NOT NULL,
    sent_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, job_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);"""

CREATE_APPLICATION_TRACKER = """
CREATE TABLE IF NOT EXISTS application_tracker (
    application_id   INTEGER PRIMARY KEY,
    stage            TEXT NOT NULL DEFAULT 'applied',
    reminder_date    TEXT,
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (application_id) REFERENCES applications(id)
);"""

CREATE_APPLICATION_NOTES = """
CREATE TABLE IF NOT EXISTS application_notes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id   INTEGER NOT NULL,
    note             TEXT NOT NULL,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (application_id) REFERENCES applications(id)
);"""

# Applications to scraped catalog jobs (jobs.db) — separate from recruiter_jobs applications
CREATE_CATALOG_APPLICATIONS = """
CREATE TABLE IF NOT EXISTS catalog_applications (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_email  TEXT    NOT NULL,
    applicant_name   TEXT    NOT NULL,
    catalog_job_id   INTEGER NOT NULL,
    job_title        TEXT    NOT NULL,
    company          TEXT,
    applied_at       TEXT    DEFAULT (datetime('now')),
    resume_text      TEXT,
    cover_letter     TEXT,
    stage            TEXT    DEFAULT 'applied',
    reminder_date    TEXT,
    UNIQUE(applicant_email, catalog_job_id)
);"""

CREATE_CATALOG_APPLICATION_NOTES = """
CREATE TABLE IF NOT EXISTS catalog_application_notes (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_application_id   INTEGER NOT NULL,
    note                     TEXT NOT NULL,
    created_at               TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (catalog_application_id) REFERENCES catalog_applications(id)
);"""


# API id for catalog-application rows (avoid collision with recruiter applications.id)
CATALOG_APP_ID_OFFSET = 35_000_000
JOBS_DB_PATH = os.path.join(_data_dir(), "jobs.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Add columns introduced after older DBs were created (CREATE IF NOT EXISTS is a no-op)."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(recruiter_jobs)")
    rj_cols = {row[1] for row in cur.fetchall()}
    if rj_cols and "is_premium" not in rj_cols:
        cur.execute("ALTER TABLE recruiter_jobs ADD COLUMN is_premium INTEGER DEFAULT 0")


def init_auth_db():
    conn = _get_conn()
    cur  = conn.cursor()
    for sql in [
        CREATE_USERS, CREATE_RECRUITER_JOBS, CREATE_APPLICATIONS,
        CREATE_SAVED_JOBS, CREATE_SUBSCRIPTIONS, CREATE_USER_JOB_EVENTS,
        CREATE_SEEKER_PROFILES, CREATE_JOB_ALERTS, CREATE_ALERT_SENT_JOBS, CREATE_APPLICATION_TRACKER,
        CREATE_APPLICATION_NOTES, CREATE_CATALOG_APPLICATIONS, CREATE_CATALOG_APPLICATION_NOTES,
    ]:
        cur.execute(sql)
    _migrate_schema(conn)
    conn.commit()
    conn.close()


# ── Password helpers (bcrypt) ─────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Hash with bcrypt (work factor 12). Returns a utf-8 string."""
    salt   = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode("utf-8")


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode("utf-8"))


def _validate_password(password: str) -> str | None:
    """Returns an error message or None if password is valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    return None


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _create_token(user_id: int, role: str, ttl: int) -> str:
    payload = {
        "sub":  str(user_id),
        "role": role,
        "iat":  int(time.time()),
        "exp":  int(time.time()) + ttl,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def create_access_token(user_id: int, role: str) -> str:
    return _create_token(user_id, role, ACCESS_TTL)


def create_refresh_token(user_id: int, role: str) -> str:
    return _create_token(user_id, role, REFRESH_TTL)


def verify_token(token: str) -> dict | None:
    """Returns decoded payload or None if expired/invalid."""
    return _decode_token(token)


# ── Email helper ──────────────────────────────────────────────────────────────

def _gen_token() -> str:
    return secrets.token_urlsafe(32)


def _send_email(to: str, subject: str, body: str):
    if not SMTP_USER or not SMTP_PASS:
        print(f"\n[DEV EMAIL] To: {to}\nSubject: {subject}\n{body}\n")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, FROM_EMAIL, to
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(FROM_EMAIL, to, msg.as_string())


def send_html_email(to: str, subject: str, html_body: str) -> None:
    """Send HTML mail (job digests, etc.). Uses SMTP if configured, otherwise logs to console."""
    _send_email(to, subject, html_body)


# ── Auth operations ───────────────────────────────────────────────────────────

def register_user(name: str, email: str, password: str,
                  role: str, company_name: str = "") -> dict:
    if not _validate_email(email):
        return {"ok": False, "message": "Invalid email address."}

    err = _validate_password(password)
    if err:
        return {"ok": False, "message": err}

    if role not in ("job_seeker", "recruiter"):
        return {"ok": False, "message": "Role must be job_seeker or recruiter."}

    token   = _gen_token()
    expiry  = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    # In developer mode (no SMTP configured), auto-verify users so login works
    # without email round-trips.
    dev_mode = not SMTP_USER or not SMTP_PASS
    verified = 1 if dev_mode else 0
    verify_token = None if dev_mode else token
    token_expiry = None if dev_mode else expiry

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO users (name, email, password_hash, role, company_name,
                                  verified, verify_token, token_expiry)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name.strip(), email.lower().strip(), _hash_password(password),
             role, company_name.strip(), verified, verify_token, token_expiry),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return {"ok": False, "message": "Email already registered."}
    finally:
        conn.close()

    if dev_mode:
        return {"ok": True, "message": "Registered successfully. Dev mode: email verification skipped."}

    link = f"{APP_URL}?verify_token={token}&email={email}"
    _send_email(
        email,
        "Verify your SkillMatch account",
        f"<p>Hi {name},</p><p>Click to verify your account: <a href='{link}'>{link}</a></p>",
    )
    return {"ok": True, "message": "Registered! Check your email to verify your account."}


def verify_email(email: str, token: str) -> dict:
    conn = _get_conn()
    row  = conn.execute(
        "SELECT id, verify_token, token_expiry FROM users WHERE email = ?",
        (email.lower().strip(),),
    ).fetchone()

    if not row:
        conn.close()
        return {"ok": False, "message": "User not found."}

    if row["verify_token"] != token:
        conn.close()
        return {"ok": False, "message": "Invalid verification token."}

    expiry = datetime.fromisoformat(row["token_expiry"])
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expiry:
        conn.close()
        return {"ok": False, "message": "Verification link expired. Please register again."}

    conn.execute("UPDATE users SET verified = 1, verify_token = NULL WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Email verified! You can now log in."}


def login_user(email: str, password: str) -> dict:
    conn = _get_conn()
    row  = conn.execute(
        "SELECT id, name, password_hash, role, company_name, verified FROM users WHERE email = ?",
        (email.lower().strip(),),
    ).fetchone()
    conn.close()

    if not row:
        return {"ok": False, "message": "Invalid email or password."}

    # Timing-safe: always call checkpw even if not found (prevents timing oracle)
    if not _check_password(password, row["password_hash"]):
        return {"ok": False, "message": "Invalid email or password."}

    if not row["verified"]:
        return {"ok": False, "message": "Please verify your email before logging in."}

    user = {
        "id":           row["id"],
        "name":         row["name"],
        "email":        email,
        "role":         row["role"],
        "company_name": row["company_name"] or "",
    }
    return {
        "ok":            True,
        "user":          user,
        "access_token":  create_access_token(row["id"], row["role"]),
        "refresh_token": create_refresh_token(row["id"], row["role"]),
        "message":       "Logged in successfully.",
    }


def get_user_by_id(user_id: int) -> dict | None:
    conn = _get_conn()
    row  = conn.execute(
        "SELECT id, name, email, role, company_name, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Recruiter operations (unchanged from v1 except added is_premium) ──────────

# Seeker APIs use jobs.db ids; recruiter postings use ids >= this base so they do not collide.
RECRUITER_LISTING_ID_BASE = 10_000_000


def decode_recruiter_listing_id(job_id: int) -> int:
    """Map public listing id to recruiter_jobs.id for DB rows keyed by recruiter job."""
    if job_id >= RECRUITER_LISTING_ID_BASE:
        return job_id - RECRUITER_LISTING_ID_BASE
    return job_id


def normalize_recruiter_job_public(row: sqlite3.Row | dict) -> dict:
    """Shape recruiter_jobs rows like jobs.db + public id for seeker UI."""
    d = dict(row)
    d.pop("from_recruiter", None)
    rid = int(d["id"])
    d["id"] = RECRUITER_LISTING_ID_BASE + rid
    d["listing_source"] = "recruiter"
    d["apply_platform"] = d.get("apply_platform") or "Recruiter listing"
    d["source_website"] = d.get("source_website") or ""
    return d


def list_public_recruiter_jobs_filtered(
    title_substring: str | None = None,
    location: str | None = None,
    work_mode: str | None = None,
    job_type: str | None = None,
    limit: int = 120,
) -> list[dict]:
    """Active recruiter listings, optional filters (same conventions as main jobs search)."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM recruiter_jobs WHERE COALESCE(is_active, 1) = 1
           ORDER BY COALESCE(is_premium, 0) DESC, posted_date DESC LIMIT ?""",
        (max(limit * 4, 200),),
    ).fetchall()
    conn.close()

    ts = (title_substring or "").strip().lower()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        jt = (d.get("job_title") or "")
        if ts and ts not in jt.lower():
            continue

        if location and str(location).lower() not in ("any", "all", ""):
            loc = (d.get("location") or "").lower()
            needle = str(location).lower()
            if loc != "remote" and needle not in loc:
                continue

        if work_mode and str(work_mode).lower() not in ("any", "all", ""):
            if str(d.get("work_mode") or "").lower() != str(work_mode).lower():
                continue

        if job_type and str(job_type).lower() not in ("any", "all", ""):
            if str(d.get("job_type") or "").lower() != str(job_type).lower():
                continue

        out.append(normalize_recruiter_job_public(d))
        if len(out) >= limit:
            break

    return out


def list_recruiter_jobs_for_alert(
    keywords: str | None,
    location: str | None,
    work_mode: str | None,
    job_type: str | None,
    exclude_public_ids: set[int],
    limit: int,
) -> list[dict]:
    """
    Active recruiter listings matching alert-style filters (keywords in title/skills/description).
    Returns public-shaped jobs (id >= RECRUITER_LISTING_ID_BASE). Respects exclude_public_ids.
    """
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM recruiter_jobs WHERE COALESCE(is_active, 1) = 1
           ORDER BY COALESCE(is_premium, 0) DESC, posted_date DESC LIMIT ?""",
        (max(limit * 6, 160),),
    ).fetchall()
    conn.close()

    kw = (keywords or "").strip().lower()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        jid_pub = int(d["id"]) + RECRUITER_LISTING_ID_BASE
        if jid_pub in exclude_public_ids:
            continue

        jt = (d.get("job_title") or "").lower()
        rs = (d.get("required_skills") or "").lower()
        desc = (d.get("description") or "").lower()
        if kw and kw not in jt and kw not in rs and kw not in desc:
            continue

        if location and str(location).lower() not in ("any", "all", ""):
            loc = (d.get("location") or "").lower()
            needle = str(location).lower()
            if loc != "remote" and needle not in loc:
                continue

        if work_mode and str(work_mode).lower() not in ("any", "all", ""):
            if str(d.get("work_mode") or "").lower() != str(work_mode).lower():
                continue

        if job_type and str(job_type).lower() not in ("any", "all", ""):
            if str(d.get("job_type") or "").lower() != str(job_type).lower():
                continue

        out.append(normalize_recruiter_job_public(d))
        if len(out) >= limit:
            break

    return out


def recruiter_post_job(recruiter_id: int, data: dict) -> dict:
    conn = _get_conn()
    recruiter = conn.execute(
        "SELECT name, role FROM users WHERE id = ?", (recruiter_id,)
    ).fetchone()
    if not recruiter or recruiter["role"] != "recruiter":
        conn.close()
        return {"ok": False, "message": "Recruiter not found."}

    conn.execute(
        """INSERT INTO recruiter_jobs
           (recruiter_id, job_title, company, location, work_mode, job_type,
            description, required_skills, salary_range, apply_link, is_premium)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (recruiter_id, data["job_title"], recruiter["name"],
         data["location"], data["work_mode"], data["job_type"],
         data.get("description", ""), data.get("required_skills", ""),
         data.get("salary_range", ""), data["apply_link"],
         int(data.get("is_premium", False))),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Job posted successfully."}


def recruiter_get_jobs(recruiter_id: int) -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM recruiter_jobs WHERE recruiter_id = ? ORDER BY posted_date DESC",
        (recruiter_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recruiter_delete_job(job_id: int, recruiter_id: int) -> dict:
    conn = _get_conn()
    conn.execute(
        "DELETE FROM recruiter_jobs WHERE id = ? AND recruiter_id = ?",
        (job_id, recruiter_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Job deleted."}


def get_recruiter_applications(recruiter_id: int) -> list:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT a.*, rj.job_title
           FROM applications a
           JOIN recruiter_jobs rj ON a.job_id = rj.id
           WHERE rj.recruiter_id = ?
           ORDER BY a.applied_at DESC""",
        (recruiter_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_application_status(app_id: int, status: str, recruiter_id: int) -> dict:
    valid = {"pending", "verified", "shortlisted", "rejected", "hired"}
    if status not in valid:
        return {"ok": False, "message": f"Status must be one of: {', '.join(valid)}"}
    conn = _get_conn()
    conn.execute(
        """UPDATE applications SET status = ?
           WHERE id = ? AND recruiter_id = ?""",
        (status, app_id, recruiter_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"Status updated to {status}."}


# ── Applicant operations ──────────────────────────────────────────────────────

def _submit_recruiter_application(recruiter_job_id: int, name: str, email: str,
                                  resume_text: str, cover_letter: str) -> dict:
    conn = _get_conn()
    job = conn.execute(
        "SELECT recruiter_id, job_title FROM recruiter_jobs WHERE id = ? AND is_active = 1",
        (recruiter_job_id,),
    ).fetchone()
    if not job:
        conn.close()
        return {"ok": False, "message": "Job not found or no longer active."}

    existing = conn.execute(
        "SELECT id FROM applications WHERE job_id = ? AND applicant_email = ?",
        (recruiter_job_id, email.lower().strip()),
    ).fetchone()
    if existing:
        conn.close()
        return {"ok": False, "message": "You have already applied for this job."}

    token  = _gen_token()
    expiry = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    conn.execute(
        """INSERT INTO applications
           (job_id, recruiter_id, applicant_name, applicant_email,
            resume_text, cover_letter, verify_token, token_expiry)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (recruiter_job_id, job["recruiter_id"], name.strip(), email.lower().strip(),
         resume_text, cover_letter, token, expiry),
    )
    app_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    link = f"{APP_URL}?verify_application={token}&app_id={app_id}"
    _send_email(
        email,
        f"Confirm your application for {job['job_title']}",
        f"<p>Hi {name},</p>"
        f"<p>Click to confirm your application: <a href='{link}'>{link}</a></p>",
    )
    return {"ok": True, "message": "Application submitted! Check your email to confirm."}


def _submit_catalog_application(catalog_job_id: int, name: str, email: str,
                                resume_text: str, cover_letter: str) -> dict:
    if catalog_job_id >= RECRUITER_LISTING_ID_BASE:
        return {"ok": False, "message": "Invalid job id."}
    if not os.path.exists(JOBS_DB_PATH):
        return {"ok": False, "message": "Job catalog unavailable."}
    cj = sqlite3.connect(JOBS_DB_PATH)
    cj.row_factory = sqlite3.Row
    row = cj.execute(
        "SELECT id, job_title, company FROM jobs WHERE id = ?", (catalog_job_id,)
    ).fetchone()
    cj.close()
    if not row:
        return {"ok": False, "message": "Job not found."}

    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM catalog_applications WHERE applicant_email = ? AND catalog_job_id = ?",
        (email.lower().strip(), catalog_job_id),
    ).fetchone()
    if existing:
        conn.close()
        return {"ok": False, "message": "You have already recorded an application for this job."}

    conn.execute(
        """INSERT INTO catalog_applications
           (applicant_email, applicant_name, catalog_job_id, job_title, company, resume_text, cover_letter)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            email.lower().strip(),
            name.strip(),
            catalog_job_id,
            row["job_title"],
            row["company"] or "",
            resume_text or "",
            cover_letter or "",
        ),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Application added to your dashboard."}


def submit_application(job_id: int, name: str, email: str,
                       resume_text: str, cover_letter: str) -> dict:
    if job_id >= RECRUITER_LISTING_ID_BASE:
        return _submit_recruiter_application(
            decode_recruiter_listing_id(job_id), name, email, resume_text, cover_letter
        )
    return _submit_catalog_application(job_id, name, email, resume_text, cover_letter)

def verify_application(app_id: int, token: str) -> dict:
    conn = _get_conn()
    row  = conn.execute(
        "SELECT verify_token, token_expiry FROM applications WHERE id = ?",
        (app_id,),
    ).fetchone()
    if not row or row["verify_token"] != token:
        conn.close()
        return {"ok": False, "message": "Invalid token."}

    expiry = datetime.fromisoformat(row["token_expiry"])
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expiry:
        conn.close()
        return {"ok": False, "message": "Confirmation link expired."}

    conn.execute(
        "UPDATE applications SET status = 'verified', verify_token = NULL WHERE id = ?",
        (app_id,),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Application confirmed!"}


def get_seeker_applications(email: str) -> list:
    em = email.lower().strip()
    conn = _get_conn()
    rows_r = conn.execute(
        """SELECT a.id, a.job_id, rj.job_title, rj.company, a.status, a.applied_at,
                  at.stage, at.reminder_date, 'recruiter' AS app_source
           FROM applications a
           JOIN recruiter_jobs rj ON a.job_id = rj.id
           LEFT JOIN application_tracker at ON at.application_id = a.id
           WHERE a.applicant_email = ?""",
        (em,),
    ).fetchall()
    rows_c = conn.execute(
        f"""SELECT (ca.id + {CATALOG_APP_ID_OFFSET}) AS id, ca.catalog_job_id AS job_id,
                   ca.job_title, ca.company, 'verified' AS status, ca.applied_at,
                   ca.stage, ca.reminder_date, 'catalog' AS app_source
            FROM catalog_applications ca
            WHERE ca.applicant_email = ?""",
        (em,),
    ).fetchall()
    conn.close()
    merged = [dict(r) for r in rows_r] + [dict(r) for r in rows_c]
    merged.sort(key=lambda x: str(x.get("applied_at") or ""), reverse=True)
    return merged


# ── Saved jobs ────────────────────────────────────────────────────────────────

def save_job(user_id: int, job_id: int) -> dict:
    conn = _get_conn()
    rid = decode_recruiter_listing_id(job_id)
    try:
        conn.execute(
            "INSERT INTO saved_jobs (user_id, job_id) VALUES (?, ?)",
            (user_id, rid),
        )
        conn.commit()
        return {"ok": True, "message": "Job saved."}
    except sqlite3.IntegrityError:
        return {"ok": False, "message": "Job already saved."}
    finally:
        conn.close()


def unsave_job(user_id: int, job_id: int) -> dict:
    conn = _get_conn()
    rid = decode_recruiter_listing_id(job_id)
    conn.execute(
        "DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?",
        (user_id, rid),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Job removed from saved."}


def get_saved_jobs(user_id: int) -> list:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT j.*, 1 as from_recruiter
           FROM saved_jobs s
           JOIN recruiter_jobs j ON s.job_id = j.id
           WHERE s.user_id = ?
           ORDER BY s.saved_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [normalize_recruiter_job_public(r) for r in rows]


def log_user_job_event(user_id: int, job_id: int, event_type: str) -> dict:
    valid = {"view", "save", "unsave", "apply", "click_apply"}
    if event_type not in valid:
        return {"ok": False, "message": f"event_type must be one of: {', '.join(sorted(valid))}"}
    conn = _get_conn()
    conn.execute(
        "INSERT INTO user_job_events (user_id, job_id, event_type) VALUES (?, ?, ?)",
        (user_id, job_id, event_type),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


def get_user_job_event_boosts(user_id: int) -> dict[int, int]:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT job_id, event_type, COUNT(*) as c
           FROM user_job_events
           WHERE user_id = ?
           GROUP BY job_id, event_type""",
        (user_id,),
    ).fetchall()
    conn.close()
    weight = {"view": 1, "click_apply": 2, "save": 3, "apply": 4, "unsave": -2}
    boosts: dict[int, int] = {}
    for r in rows:
        jid = int(r["job_id"])
        boosts[jid] = boosts.get(jid, 0) + int(r["c"]) * weight.get(r["event_type"], 0)
    return boosts


def upsert_seeker_profile(
    user_id: int,
    resume_text: str = "",
    normalized_skills: list[str] | None = None,
    preferred_locations: list[str] | None = None,
    target_roles: list[str] | None = None,
) -> dict:
    conn = _get_conn()
    conn.execute(
        """INSERT INTO seeker_profiles
           (user_id, resume_text, normalized_skills, preferred_locations, target_roles, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET
               resume_text=excluded.resume_text,
               normalized_skills=excluded.normalized_skills,
               preferred_locations=excluded.preferred_locations,
               target_roles=excluded.target_roles,
               updated_at=datetime('now')""",
        (
            user_id,
            resume_text or "",
            json.dumps(normalized_skills or []),
            json.dumps(preferred_locations or []),
            json.dumps(target_roles or []),
        ),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Profile updated."}


def get_seeker_profile(user_id: int) -> dict:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM seeker_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {"ok": True, "profile": None}
    profile = dict(row)
    for k in ("normalized_skills", "preferred_locations", "target_roles"):
        try:
            profile[k] = json.loads(profile.get(k) or "[]")
        except Exception:
            profile[k] = []
    return {"ok": True, "profile": profile}


def upsert_job_alert(
    user_id: int,
    cadence: str = "weekly",
    location: str | None = None,
    work_mode: str | None = None,
    job_type: str | None = None,
    keywords: str | None = None,
    is_active: bool = True,
) -> dict:
    if cadence not in {"daily", "weekly"}:
        return {"ok": False, "message": "cadence must be daily or weekly"}
    conn = _get_conn()
    conn.execute(
        """INSERT INTO job_alerts (user_id, cadence, location, work_mode, job_type, keywords, is_active, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET
             cadence=excluded.cadence,
             location=excluded.location,
             work_mode=excluded.work_mode,
             job_type=excluded.job_type,
             keywords=excluded.keywords,
             is_active=excluded.is_active,
             updated_at=datetime('now')""",
        (user_id, cadence, location, work_mode, job_type, keywords, int(is_active)),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Alert preferences saved."}


def get_job_alert(user_id: int) -> dict:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM job_alerts WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return {"ok": True, "alert": dict(row) if row else None}


def update_application_tracker(application_id: int, stage: str, reminder_date: str | None = None) -> dict:
    valid = {"applied", "screening", "interview", "offer", "rejected"}
    if stage not in valid:
        return {"ok": False, "message": f"stage must be one of: {', '.join(sorted(valid))}"}
    if application_id >= CATALOG_APP_ID_OFFSET:
        cid = application_id - CATALOG_APP_ID_OFFSET
        conn = _get_conn()
        n = conn.execute("UPDATE catalog_applications SET stage = ?, reminder_date = ? WHERE id = ?", (stage, reminder_date, cid)).rowcount
        conn.commit()
        conn.close()
        if not n:
            return {"ok": False, "message": "Application not found."}
        return {"ok": True, "message": "Application tracker updated."}
    conn = _get_conn()
    conn.execute(
        """INSERT INTO application_tracker (application_id, stage, reminder_date, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(application_id) DO UPDATE SET
              stage=excluded.stage,
              reminder_date=excluded.reminder_date,
              updated_at=datetime('now')""",
        (application_id, stage, reminder_date),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Application tracker updated."}


def add_application_note(application_id: int, note: str) -> dict:
    if not note.strip():
        return {"ok": False, "message": "note cannot be empty"}
    if application_id >= CATALOG_APP_ID_OFFSET:
        cid = application_id - CATALOG_APP_ID_OFFSET
        conn = _get_conn()
        conn.execute(
            "INSERT INTO catalog_application_notes (catalog_application_id, note) VALUES (?, ?)",
            (cid, note.strip()),
        )
        conn.commit()
        conn.close()
        return {"ok": True, "message": "Note added."}
    conn = _get_conn()
    conn.execute(
        "INSERT INTO application_notes (application_id, note) VALUES (?, ?)",
        (application_id, note.strip()),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Note added."}


def delete_seeker_application(app_id: int, email: str) -> dict:
    """Remove an application row owned by the seeker (recruiter listing or catalog job)."""
    em = email.lower().strip()
    if not em:
        return {"ok": False, "message": "email required."}
    if app_id >= CATALOG_APP_ID_OFFSET:
        cid = app_id - CATALOG_APP_ID_OFFSET
        conn = _get_conn()
        row = conn.execute(
            "SELECT id FROM catalog_applications WHERE id = ? AND LOWER(applicant_email) = ?",
            (cid, em),
        ).fetchone()
        if not row:
            conn.close()
            return {"ok": False, "message": "Application not found."}
        conn.execute(
            "DELETE FROM catalog_application_notes WHERE catalog_application_id = ?",
            (cid,),
        )
        conn.execute("DELETE FROM catalog_applications WHERE id = ?", (cid,))
        conn.commit()
        conn.close()
        return {"ok": True, "message": "Application removed."}
    conn = _get_conn()
    row = conn.execute(
        "SELECT id FROM applications WHERE id = ? AND LOWER(applicant_email) = ?",
        (app_id, em),
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "message": "Application not found."}
    conn.execute("DELETE FROM application_notes WHERE application_id = ?", (app_id,))
    conn.execute("DELETE FROM application_tracker WHERE application_id = ?", (app_id,))
    conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Application removed."}


if __name__ == "__main__":
    init_auth_db()
    print("auth.db initialised with v2 schema.")
