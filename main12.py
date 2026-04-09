
"""
main12.py  –  FastAPI backend  (v6 – upgraded prediction + match scoring)

NEW:
- /predict → Top-3 predictions with confidence, overlap, explanation
- /jobs/match_score → Skill match % for each job
"""

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import uvicorn, sqlite3, os, re, logging, random

# ✅ UPDATED IMPORT
from src.pipeline import integretion, predict_scored
from src.resume_tools import extract_resume_text, extract_resume_bytes, extract_skills_and_roles
from src.alerts import run_alert_cycle
import auth as auth_module

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))


def _app_data_dir() -> str:
    return os.path.abspath(os.getenv("SKILLMATCH_DATA_DIR", APP_ROOT))


DB_PATH = os.path.join(_app_data_dir(), "jobs.db")
app = FastAPI(title="SkillMatch API", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure auth schema migrations are applied at startup.
auth_module.init_auth_db()

# ── Models ────────────────────────────────────────────────────────────────────
class SkillInput(BaseModel):
    text: str

class JobSearchRequest(BaseModel):
    job_title:  str
    location:   Optional[str] = None
    work_mode:  Optional[str] = None
    job_type:   Optional[str] = None

class JobResult(BaseModel):
    id:              int
    job_title:       str
    company:         str
    location:        str
    work_mode:       str
    job_type:        str
    description:     Optional[str]
    required_skills: Optional[str]
    salary_range:    Optional[str]
    apply_platform:  Optional[str]
    source_website:  Optional[str]
    apply_link:      str
    posted_date:     Optional[str]
    listing_source:  Optional[str] = None  # "recruiter" vs default catalog (jobs.db)
    is_premium:      Optional[int] = None

# Auth models
class RegisterRequest(BaseModel):
    name:         str
    email:        str
    password:     str
    role:         str
    company_name: Optional[str] = ""

class VerifyEmailRequest(BaseModel):
    email: str
    token: str

class LoginRequest(BaseModel):
    email:    str
    password: str

# Recruiter models
class RecruiterJobRequest(BaseModel):
    recruiter_id:   int
    job_title:      str
    location:       str
    work_mode:      str
    job_type:       str
    description:    Optional[str] = ""
    required_skills:Optional[str] = ""
    salary_range:   Optional[str] = ""
    apply_link:     str

class DeleteJobRequest(BaseModel):
    recruiter_id: int

class ApplicationRequest(BaseModel):
    job_id:       int
    name:         str
    email:        str
    resume_text:  Optional[str] = ""
    cover_letter: Optional[str] = ""

class VerifyApplicationRequest(BaseModel):
    app_id: int
    token:  str

class UpdateApplicationStatus(BaseModel):
    status:       str
    recruiter_id: int

# NEW model for match score
class MatchScoreRequest(BaseModel):
    user_skills: str
    job_required_skills: str

class RecommendRequest(BaseModel):
    skills: str
    user_id: Optional[int] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    job_type: Optional[str] = None
    limit: int = 20

class SaveJobRequest(BaseModel):
    user_id: int
    job_id: int

class JobEventRequest(BaseModel):
    user_id: int
    job_id: int
    event_type: str

class ResumeParseRequest(BaseModel):
    user_id: int
    file_path: str

class ProfileUpdateRequest(BaseModel):
    user_id: int
    resume_text: Optional[str] = ""
    normalized_skills: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    target_roles: Optional[List[str]] = None

class AlertSettingsRequest(BaseModel):
    user_id: int
    cadence: str = "weekly"
    location: Optional[str] = None
    work_mode: Optional[str] = None
    job_type: Optional[str] = None
    keywords: Optional[str] = None
    is_active: bool = True

class TrackerUpdateRequest(BaseModel):
    stage: str
    reminder_date: Optional[str] = None

class AddNoteRequest(BaseModel):
    note: str

# ── DB helper ─────────────────────────────────────────────────────────────────
def get_conn():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="jobs.db not found.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _merge_recruiter_listings(
    jobs: list[dict],
    *,
    title_substring: Optional[str],
    location,
    work_mode,
    job_type,
    max_recruiter: int = 80,
) -> list[dict]:
    """Append active recruiter posts (public ids) for the same seeker filters."""
    seen = {int(j.get("id", 0)) for j in jobs}
    try:
        extra = auth_module.list_public_recruiter_jobs_filtered(
            title_substring, location, work_mode, job_type, limit=max_recruiter
        )
    except Exception as e:
        logger.warning("recruiter listings merge skipped: %s", e)
        return jobs
    for j in extra:
        jid = int(j.get("id", 0))
        if jid not in seen:
            seen.add(jid)
            jobs.append(j)
    return jobs


def query_jobs(job_title, location, work_mode, job_type, limit=30):
    try:
        conn = get_conn()
    except HTTPException:
        return []
    cur = conn.cursor()

    def run_query(loc, wm, jt):
        sql    = "SELECT * FROM jobs WHERE LOWER(job_title) LIKE ?"
        params = [f"%{job_title.lower()}%"]

        if loc and loc.lower() not in ("any", "all", ""):
            sql += " AND (LOWER(location) LIKE ? OR LOWER(location) = 'remote')"
            params.append(f"%{loc.lower()}%")

        if wm and wm.lower() not in ("any", "all", ""):
            sql += " AND LOWER(work_mode) = ?"
            params.append(wm.lower())

        if jt and jt.lower() not in ("any", "all", ""):
            sql += " AND LOWER(job_type) = ?"
            params.append(jt.lower())

        sql += " ORDER BY posted_date DESC LIMIT ?"
        params.append(limit)

        return cur.execute(sql, params).fetchall()

    rows = run_query(location, work_mode, job_type)

    if not rows and location and location.lower() not in ("any", "all", ""):
        rows = run_query(None, work_mode, job_type)

    if not rows:
        rows = run_query(None, None, None)

    conn.close()
    out = [dict(r) for r in rows]
    _merge_recruiter_listings(
        out,
        title_substring=job_title,
        location=location,
        work_mode=work_mode,
        job_type=job_type,
        max_recruiter=max(limit, 50),
    )
    out.sort(key=lambda j: str(j.get("posted_date") or ""), reverse=True)
    cap = min(len(out), max(limit * 2, limit + 20))
    return out[:cap]


def _append_job_filters(sql: str, params: list, location, work_mode, job_type) -> tuple[str, list]:
    """Add location / work_mode / job_type filters (same rules as query_jobs)."""
    if location and str(location).lower() not in ("any", "all", ""):
        sql += " AND (LOWER(location) LIKE ? OR LOWER(location) = 'remote')"
        params.append(f"%{str(location).lower()}%")

    if work_mode and str(work_mode).lower() not in ("any", "all", ""):
        sql += " AND LOWER(work_mode) = ?"
        params.append(str(work_mode).lower())

    if job_type and str(job_type).lower() not in ("any", "all", ""):
        sql += " AND LOWER(job_type) = ?"
        params.append(str(job_type).lower())

    return sql, params


def query_jobs_for_recommend(
    predicted_roles: list[str],
    user_skill_tokens: set[str],
    location,
    work_mode,
    job_type,
    limit: int,
    min_pool: int = 20,
) -> list[dict]:
    """
    Candidate jobs for /jobs/recommend: OR-match top predicted role titles (avoids 0 results
    when the #1 role label is missing from job_title in the DB), then broaden using
    required_skills tokens, then all jobs matching filters.
    """
    try:
        conn = get_conn()
    except HTTPException:
        return []
    cur = conn.cursor()

    def run_with_filters(base_sql: str, base_params: list, loc, wm, jt, lim: int):
        sql, params = _append_job_filters(base_sql, list(base_params), loc, wm, jt)
        sql += " ORDER BY posted_date DESC LIMIT ?"
        params.append(lim)
        return cur.execute(sql, params).fetchall()

    seen: set[int] = set()
    merged: list[dict] = []

    def add_rows(rows):
        for r in rows:
            d = dict(r)
            jid = int(d.get("id", 0))
            if jid and jid not in seen:
                seen.add(jid)
                merged.append(d)

    fetch_limit = max(limit * 4, min_pool * 2, 60)

    # Unique role strings from model (top predictions may include roles not present as titles)
    role_patterns = []
    for role in (predicted_roles or [])[:5]:
        r = (role or "").strip()
        if r and r.lower() not in ("unknown",):
            role_patterns.append(r)
    # De-dupe preserving order
    uniq_roles = list(dict.fromkeys(role_patterns))

    loc_chain = [location]
    if location and str(location).lower() not in ("any", "all", ""):
        loc_chain.append(None)

    for loc in loc_chain:
        if len(merged) >= min_pool:
            break
        if not uniq_roles:
            break
        or_parts = ["LOWER(job_title) LIKE ?"] * len(uniq_roles)
        sql = "SELECT * FROM jobs WHERE (" + " OR ".join(or_parts) + ")"
        params = [f"%{r.lower()}%" for r in uniq_roles]
        rows = run_with_filters(sql, params, loc, work_mode, job_type, fetch_limit)
        add_rows(rows)

    # Broader title keywords for common ML/data synonyms (short fragments still match titles)
    synonyms = []
    for r in uniq_roles:
        rl = r.lower()
        if "data analyst" in rl or rl == "data analyst":
            synonyms.extend(["data scientist", "business analyst", "bi developer", "analytics"])
        if "machine learning" in rl or "ml engineer" in rl:
            synonyms.extend(["data scientist", "ml engineer", "machine learning"])
    synonym_patterns = list(dict.fromkeys([s for s in synonyms if s]))[:8]
    if len(merged) < min_pool and synonym_patterns:
        for loc in loc_chain:
            if len(merged) >= min_pool:
                break
            or_parts = ["LOWER(job_title) LIKE ?"] * len(synonym_patterns)
            sql = "SELECT * FROM jobs WHERE (" + " OR ".join(or_parts) + ")"
            params = [f"%{p}%" for p in synonym_patterns]
            rows = run_with_filters(sql, params, loc, work_mode, job_type, fetch_limit)
            add_rows(rows)

    # Match user skill tokens against required_skills / description / title
    tokens = sorted(t for t in user_skill_tokens if len(t) >= 3)[:10]
    if len(merged) < min_pool and tokens:
        for loc in loc_chain:
            if len(merged) >= min_pool:
                break
            or_parts = []
            params: list = []
            for t in tokens:
                or_parts.append(
                    "(LOWER(COALESCE(required_skills,'')) LIKE ? OR "
                    "LOWER(COALESCE(description,'')) LIKE ? OR "
                    "LOWER(job_title) LIKE ?)"
                )
                p = f"%{t}%"
                params.extend([p, p, p])
            sql = "SELECT * FROM jobs WHERE (" + " OR ".join(or_parts) + ")"
            rows = run_with_filters(sql, params, loc, work_mode, job_type, fetch_limit)
            add_rows(rows)

    # Last resort: any jobs matching preference filters (ranking uses skill overlap)
    if len(merged) < min_pool:
        for loc in loc_chain:
            if len(merged) >= min_pool:
                break
            sql = "SELECT * FROM jobs WHERE 1=1"
            rows = run_with_filters(sql, [], loc, work_mode, job_type, fetch_limit)
            add_rows(rows)

    conn.close()
    _merge_recruiter_listings(
        merged,
        title_substring=None,
        location=location,
        work_mode=work_mode,
        job_type=job_type,
        max_recruiter=min_pool + 40,
    )
    merged.sort(key=lambda j: str(j.get("posted_date") or ""), reverse=True)
    return merged[: fetch_limit]


# ── UPDATED PREDICT ROUTE ─────────────────────────────────────────────────────
@app.post("/predict")
def predict(data: SkillInput):
    try:
        results = predict_scored(data.text, top_n=3)

        return {
            "top_prediction": results[0]["role"] if results else "Unknown",
            "results": results
        }

    except Exception as e:
        logger.error(f"/predict error: {e}")
        return {
            "error": str(e),
            "top_prediction": None,
            "results": []
        }

# ── NEW MATCH SCORE ROUTE ─────────────────────────────────────────────────────
@app.post("/jobs/match_score")
def match_score(req: MatchScoreRequest):
    user_skills = req.user_skills.lower()
    job_skills  = req.job_required_skills.lower()

    job_tokens = set(re.findall(r"\b\w{3,}\b", job_skills))

    stop = {"and","the","for","with","you","our","are","have","will",
            "can","not","use","all","any","new","get","set","how"}

    job_tokens -= stop

    if not job_tokens:
        return {"match_score": 0, "matched": [], "missing": []}

    matched = [t for t in job_tokens if t in user_skills]
    missing = [t for t in job_tokens if t not in user_skills]

    score = int(round(len(matched) / len(job_tokens) * 100))

    return {
        "match_score": score,
        "matched": sorted(matched)[:8],
        "missing": sorted(missing)[:8],
    }

def _extract_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#\-.]{1,}\b", (text or "").lower()))
    stop = {
        "and", "the", "for", "with", "you", "our", "are", "have", "will", "can",
        "not", "use", "all", "any", "new", "get", "set", "how", "this", "that"
    }
    return {t for t in tokens if t not in stop and len(t) >= 3}

def _recency_score(posted_date: Optional[str]) -> int:
    if not posted_date:
        return 50
    try:
        dt = datetime.strptime(posted_date[:10], "%Y-%m-%d").date()
        days_old = (date.today() - dt).days
        if days_old <= 3:
            return 100
        if days_old <= 7:
            return 90
        if days_old <= 14:
            return 75
        if days_old <= 30:
            return 60
        return 40
    except Exception:
        return 50


def _build_recommend_explain(job: dict) -> str:
    """Short, human-readable rationale for /jobs/recommend ranking (UI + trust)."""
    parts: list[str] = []
    bd = job.get("score_breakdown") or {}
    matched = job.get("matched_skills") or []
    if matched:
        tail = "…" if len(matched) > 6 else ""
        shown = ", ".join(matched[:6])
        parts.append(f"Skills that overlap with this role: {shown}{tail}.")
    if bd.get("title_bonus"):
        parts.append("The job title lines up with one of your model’s predicted roles.")
    bb = bd.get("behavior_boost") or 0
    if bb > 0:
        parts.append("Ranked higher because of recent views, saves, or applications.")
    elif bb < 0:
        parts.append("Your past activity slightly adjusted this ranking.")
    if bd.get("listing_boost"):
        parts.append("Employer-posted role on SkillMatch, not only third-party job-board scrapes.")
    if (bd.get("recency") or 0) >= 90:
        parts.append("Fresh listing (posted within roughly the last two weeks).")
    if not parts:
        parts.append(
            f"Score blends skill fit ({job.get('match_score', 0)}%), posting freshness, and your activity."
        )
    return " ".join(parts)


@app.post("/jobs/recommend")
def recommend_jobs(req: RecommendRequest):
    try:
        prediction_results = predict_scored(req.skills, top_n=3)
        top_role = prediction_results[0]["role"] if prediction_results else ""

        user_tokens = _extract_tokens(req.skills)
        role_names = [p["role"] for p in prediction_results] if prediction_results else []
        jobs = query_jobs_for_recommend(
            role_names,
            user_tokens,
            req.location,
            req.work_mode,
            req.job_type,
            limit=max(req.limit * 3, 30),
            min_pool=max(15, req.limit),
        )

        boosts = auth_module.get_user_job_event_boosts(req.user_id) if req.user_id else {}
        ranked = []
        for job in jobs:
            title = (job.get("job_title") or "").lower()
            job_skill_tokens = _extract_tokens(job.get("required_skills") or "")

            overlap = len(user_tokens & job_skill_tokens)
            base = int(round((overlap / max(len(job_skill_tokens), 1)) * 100)) if job_skill_tokens else 0
            # Recruiter posts often have sparse required_skills; match against title + description too
            if job.get("listing_source") == "recruiter" and user_tokens:
                text_blob = f"{job.get('job_title') or ''} {job.get('description') or ''} {job.get('required_skills') or ''}"
                text_tok = _extract_tokens(text_blob)
                alt = len(user_tokens & text_tok)
                if alt:
                    blended = int(round(alt / max(len(user_tokens), 1) * 100))
                    base = max(base, min(blended, 85))

            title_bonus = 0
            if title:
                for p in prediction_results or []:
                    rlow = (p.get("role") or "").lower()
                    if rlow and rlow in title:
                        title_bonus = 12
                        break
            recency = _recency_score(job.get("posted_date"))
            behavior_boost = boosts.get(int(job.get("id", 0)), 0)
            listing_boost = 12 if job.get("listing_source") == "recruiter" else 0
            final_score = int(round((base * 0.66) + title_bonus + (recency * 0.16) + behavior_boost + listing_boost))
            final_score = max(0, min(100, final_score))

            matched = sorted(list(user_tokens & job_skill_tokens))[:8]
            if not matched and user_tokens and job.get("listing_source") == "recruiter":
                text_blob = f"{job.get('job_title') or ''} {job.get('description') or ''} {job.get('required_skills') or ''}"
                matched = sorted(list(user_tokens & _extract_tokens(text_blob)))[:8]

            row = {
                **job,
                "recommendation_score": final_score,
                "matched_skills": matched,
                "match_score": base,
                "score_breakdown": {
                    "skill_overlap": base,
                    "title_bonus": title_bonus,
                    "recency": recency,
                    "behavior_boost": behavior_boost,
                    "listing_boost": listing_boost,
                },
            }
            row["recommend_explain"] = _build_recommend_explain(row)
            ranked.append(row)

        ranked.sort(key=lambda j: (j["recommendation_score"], j.get("posted_date") or ""), reverse=True)
        top_ranked = ranked[: max(1, min(req.limit, 50))]

        return {
            "top_prediction": top_role or "Unknown",
            "predictions": prediction_results,
            "jobs": top_ranked,
        }
    except Exception as e:
        logger.error(f"/jobs/recommend error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/saved_jobs")
def save_job(req: SaveJobRequest):
    res = auth_module.save_job(req.user_id, req.job_id)
    auth_module.log_user_job_event(req.user_id, req.job_id, "save")
    return res

@app.delete("/saved_jobs")
def unsave_job(req: SaveJobRequest):
    res = auth_module.unsave_job(req.user_id, req.job_id)
    auth_module.log_user_job_event(req.user_id, req.job_id, "unsave")
    return res

@app.get("/saved_jobs/{user_id}")
def list_saved_jobs(user_id: int):
    return auth_module.get_saved_jobs(user_id)

@app.post("/jobs/event")
def track_job_event(req: JobEventRequest):
    return auth_module.log_user_job_event(req.user_id, req.job_id, req.event_type)

@app.post("/profile/parse_resume")
async def parse_resume(user_id: int = Form(...), resume_file: UploadFile = File(...)):
    content = await resume_file.read()
    text = extract_resume_bytes(resume_file.filename or "", content)
    extracted = extract_skills_and_roles(text)
    auth_module.upsert_seeker_profile(
        user_id,
        resume_text=text,
        normalized_skills=extracted.get("skills", []),
        target_roles=extracted.get("roles", []),
    )
    return {"ok": True, "profile": extracted, "resume_text": text[:5000]}

@app.post("/profile")
def upsert_profile(req: ProfileUpdateRequest):
    return auth_module.upsert_seeker_profile(
        req.user_id,
        req.resume_text or "",
        req.normalized_skills or [],
        req.preferred_locations or [],
        req.target_roles or [],
    )

@app.get("/profile/{user_id}")
def get_profile(user_id: int):
    return auth_module.get_seeker_profile(user_id)

@app.post("/alerts")
def upsert_alert(req: AlertSettingsRequest):
    return auth_module.upsert_job_alert(
        req.user_id, req.cadence, req.location, req.work_mode, req.job_type, req.keywords, req.is_active
    )

@app.get("/alerts/{user_id}")
def get_alert(user_id: int):
    return auth_module.get_job_alert(user_id)

@app.post("/alerts/run")
def run_alerts_now():
    return run_alert_cycle()

@app.patch("/applications/{app_id}/tracker")
def update_tracker(app_id: int, req: TrackerUpdateRequest):
    return auth_module.update_application_tracker(app_id, req.stage, req.reminder_date)

@app.post("/applications/{app_id}/notes")
def add_note(app_id: int, req: AddNoteRequest):
    return auth_module.add_application_note(app_id, req.note)

@app.delete("/applications/{app_id}")
def delete_seeker_app(app_id: int, email: str = Query(..., description="Logged-in seeker email")):
    return auth_module.delete_seeker_application(app_id, email)

# ── JOB ROUTES ────────────────────────────────────────────────────────────────
@app.post("/jobs/search", response_model=List[JobResult])
def search_jobs(req: JobSearchRequest):
    try:
        return query_jobs(req.job_title, req.location, req.work_mode, req.job_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/filters")
def get_filters():
    conn  = get_conn()
    cur   = conn.cursor()

    locs  = [r[0] for r in cur.execute("SELECT DISTINCT location FROM jobs ORDER BY location").fetchall()]
    modes = [r[0] for r in cur.execute("SELECT DISTINCT work_mode FROM jobs ORDER BY work_mode").fetchall()]
    types = [r[0] for r in cur.execute("SELECT DISTINCT job_type FROM jobs ORDER BY job_type").fetchall()]
    plats = [r[0] for r in cur.execute("SELECT DISTINCT apply_platform FROM jobs ORDER BY apply_platform").fetchall()]

    conn.close()
    return {"locations": locs, "work_modes": modes, "job_types": types, "platforms": plats}


@app.get("/jobs/stats")
def get_stats():
    conn = get_conn()
    cur  = conn.cursor()

    total       = cur.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    by_type     = dict(cur.execute("SELECT job_type, COUNT(*) FROM jobs GROUP BY job_type").fetchall())
    by_mode     = dict(cur.execute("SELECT work_mode, COUNT(*) FROM jobs GROUP BY work_mode").fetchall())
    by_platform = dict(cur.execute("SELECT apply_platform, COUNT(*) FROM jobs GROUP BY apply_platform").fetchall())

    top_titles = [r[0] for r in cur.execute(
        "SELECT job_title, COUNT(*) c FROM jobs GROUP BY job_title ORDER BY c DESC LIMIT 10"
    ).fetchall()]

    conn.close()

    return {
        "total": total,
        "by_type": by_type,
        "by_mode": by_mode,
        "by_platform": by_platform,
        "top_titles": top_titles
    }


@app.get("/jobs/random", response_model=List[JobResult])
def get_random_jobs(n: int = Query(default=6, ge=1, le=20)):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM jobs ORDER BY RANDOM() LIMIT ?", (n,)).fetchall()
    conn.close()
    pool = [dict(r) for r in rows]
    _merge_recruiter_listings(
        pool, title_substring=None, location=None, work_mode=None, job_type=None, max_recruiter=n * 8
    )
    random.shuffle(pool)
    return pool[:n]


@app.get("/jobs/title/{title_slug}", response_model=List[JobResult])
def jobs_by_title(title_slug: str, limit: int = Query(default=20, ge=1, le=50)):
    conn = get_conn()
    needle = title_slug.replace("-", " ").lower()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE LOWER(job_title) LIKE ? ORDER BY posted_date DESC LIMIT ?",
        (f"%{needle}%", limit)
    ).fetchall()
    conn.close()
    out = [dict(r) for r in rows]
    _merge_recruiter_listings(
        out,
        title_substring=needle,
        location=None,
        work_mode=None,
        job_type=None,
        max_recruiter=limit + 20,
    )
    out.sort(key=lambda j: str(j.get("posted_date") or ""), reverse=True)
    return out[: max(limit * 2, limit + 10)]

# ── AUTH ROUTES ───────────────────────────────────────────────────────────────
@app.post("/auth/register")
def register(req: RegisterRequest):
    return auth_module.register_user(
        req.name, req.email, req.password, req.role, req.company_name or ""
    )

@app.post("/auth/verify")
def verify_email(req: VerifyEmailRequest):
    return auth_module.verify_email(req.email, req.token)

@app.post("/auth/login")
def login(req: LoginRequest):
    return auth_module.login_user(req.email, req.password)

# ── RECRUITER ROUTES ──────────────────────────────────────────────────────────
@app.post("/recruiter/jobs")
def post_job(req: RecruiterJobRequest):
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    return auth_module.recruiter_post_job(req.recruiter_id, payload)

@app.get("/recruiter/jobs/{recruiter_id}")
def get_recruiter_jobs(recruiter_id: int):
    return auth_module.recruiter_get_jobs(recruiter_id)

@app.delete("/recruiter/jobs/{job_id}")
def delete_job(job_id: int, req: DeleteJobRequest):
    return auth_module.recruiter_delete_job(job_id, req.recruiter_id)

@app.get("/recruiter/applications/{recruiter_id}")
def get_applications(recruiter_id: int):
    return auth_module.get_recruiter_applications(recruiter_id)

@app.patch("/recruiter/applications/{app_id}")
def update_app_status(app_id: int, req: UpdateApplicationStatus):
    return auth_module.update_application_status(app_id, req.status, req.recruiter_id)

@app.get("/recruiter/candidates/{recruiter_id}")
def ranked_candidates(recruiter_id: int):
    apps = auth_module.get_recruiter_applications(recruiter_id)
    jobs = {j["id"]: j for j in auth_module.recruiter_get_jobs(recruiter_id)}

    def _tokens(s: str) -> set[str]:
        return set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#\-.]{1,}\b", (s or "").lower()))

    ranked = []
    for a in apps:
        job = jobs.get(a.get("job_id"), {})
        req_tokens = _tokens(job.get("required_skills", ""))
        cv_tokens = _tokens(a.get("resume_text", ""))
        overlap = sorted(list(req_tokens & cv_tokens))
        fit = int(round((len(overlap) / max(len(req_tokens), 1)) * 100)) if req_tokens else 0
        ranked.append({**a, "fit_score": fit, "missing_skills": sorted(list(req_tokens - cv_tokens))[:8], "matched_skills": overlap[:8]})
    ranked.sort(key=lambda x: x["fit_score"], reverse=True)
    return ranked

# ── APPLICANT ROUTES ──────────────────────────────────────────────────────────
@app.post("/apply")
def apply(req: ApplicationRequest):
    return auth_module.submit_application(
        req.job_id, req.name, req.email, req.resume_text or "", req.cover_letter or ""
    )

@app.post("/apply/verify")
def verify_app(req: VerifyApplicationRequest):
    return auth_module.verify_application(req.app_id, req.token)

@app.get("/apply/history/{email}")
def get_seeker_history(email: str):
    return auth_module.get_seeker_applications(email)


@app.get("/", include_in_schema=False)
async def serve_index():
    path = os.path.join(APP_ROOT, "index.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(path, media_type="text/html; charset=utf-8")


# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main12:app", host="127.0.0.1", port=8000, reload=True)

