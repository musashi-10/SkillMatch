"""
main12.py  –  FastAPI backend  (v5 – auth + recruiter features)
  POST /predict                     → ML prediction from skills text
  POST /jobs/search                 → Query jobs.db with filters
  GET  /jobs/filters                → Available dropdown values
  GET  /jobs/stats                  → DB stats
  GET  /jobs/random                 → Random featured jobs
  GET  /jobs/title/{title}          → Jobs by title slug

  POST /auth/register               → Register user
  POST /auth/verify                 → Verify email token
  POST /auth/login                  → Login

  POST /recruiter/jobs              → Post a new job
  GET  /recruiter/jobs/{rid}        → Get recruiter's jobs
  DELETE /recruiter/jobs/{jid}      → Delete a job
  GET  /recruiter/applications/{rid}→ Get all applicants
  PATCH /recruiter/applications/{id}→ Update applicant status

  POST /apply                       → Submit application (applicant)
  POST /apply/verify                → Verify application token
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn, sqlite3, os

from src.pipeline import integretion
import auth as auth_module

DB_PATH = "jobs.db"
app = FastAPI(title="SkillMatch API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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

# Auth models
class RegisterRequest(BaseModel):
    name:         str
    email:        str
    password:     str
    role:         str          # job_seeker | recruiter
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


# ── DB helper ─────────────────────────────────────────────────────────────────
def get_conn():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="jobs.db not found.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    return [dict(r) for r in rows]


# ── Existing routes ───────────────────────────────────────────────────────────
@app.post("/predict")
def predict(data: SkillInput):
    try:
        result = integretion(data.text)
        return {"prediction": result}
    except Exception as e:
        return {"error": str(e)}


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
    conn        = get_conn()
    cur         = conn.cursor()
    total       = cur.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    by_type     = dict(cur.execute("SELECT job_type, COUNT(*) FROM jobs GROUP BY job_type").fetchall())
    by_mode     = dict(cur.execute("SELECT work_mode, COUNT(*) FROM jobs GROUP BY work_mode").fetchall())
    by_platform = dict(cur.execute("SELECT apply_platform, COUNT(*) FROM jobs GROUP BY apply_platform").fetchall())
    top_titles  = [r[0] for r in cur.execute(
        "SELECT job_title, COUNT(*) c FROM jobs GROUP BY job_title ORDER BY c DESC LIMIT 10"
    ).fetchall()]
    conn.close()
    return {"total": total, "by_type": by_type, "by_mode": by_mode,
            "by_platform": by_platform, "top_titles": top_titles}


@app.get("/jobs/random", response_model=List[JobResult])
def get_random_jobs(n: int = Query(default=6, ge=1, le=20)):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM jobs ORDER BY RANDOM() LIMIT ?", (n,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/jobs/title/{title_slug}", response_model=List[JobResult])
def jobs_by_title(title_slug: str, limit: int = Query(default=20, ge=1, le=50)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE LOWER(job_title) LIKE ? ORDER BY posted_date DESC LIMIT ?",
        (f"%{title_slug.lower()}%", limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Auth routes ───────────────────────────────────────────────────────────────
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


# ── Recruiter routes ──────────────────────────────────────────────────────────
@app.post("/recruiter/jobs")
def post_job(req: RecruiterJobRequest):
    return auth_module.recruiter_post_job(req.recruiter_id, req.dict())

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


# ── Applicant routes ──────────────────────────────────────────────────────────
@app.post("/apply")
def apply(req: ApplicationRequest):
    return auth_module.submit_application(
        req.job_id, req.name, req.email, req.resume_text or "", req.cover_letter or ""
    )

@app.post("/apply/verify")
def verify_app(req: VerifyApplicationRequest):
    return auth_module.verify_application(req.app_id, req.token)


if __name__ == "__main__":
    uvicorn.run("main12:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
