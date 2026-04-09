"""
app.py  –  SkillMatch Streamlit Frontend  (v5 – Auth + Recruiter Dashboard)
"""

import streamlit as st, requests, re

API = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="SkillMatch · Job Recommender",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');
*,*::before,*::after{box-sizing:border-box}
html,body,[data-testid="stAppViewContainer"]{background:#080C14!important;color:#E8EDF5!important;font-family:'DM Sans',sans-serif!important}
[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse 80% 60% at 50% -10%,#0E2A4A 0%,#080C14 60%)!important}
#MainMenu,footer,header{visibility:hidden}
[data-testid="stDecoration"],.stDeployButton{display:none}
section[data-testid="stSidebar"]{display:none}
h1,h2,h3,h4{font-family:'Syne',sans-serif!important}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:#0d1520}::-webkit-scrollbar-thumb{background:#1e3050;border-radius:9px}
.wrap{max-width:1000px;margin:0 auto;padding:2.8rem 1.4rem 5rem}

/* Auth card */
.auth-card{background:rgba(14,24,42,.85);border:1px solid rgba(56,189,248,.2);border-radius:24px;padding:2.4rem 2.8rem;max-width:480px;margin:0 auto}
.auth-title{font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;letter-spacing:-.02em;background:linear-gradient(135deg,#E8EDF5 30%,#38BDF8 80%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:.3rem}
.auth-sub{font-size:.88rem;color:#4B6080;margin-bottom:1.6rem}
.role-pill{display:inline-flex;align-items:center;gap:.4rem;padding:.45rem 1.1rem;border-radius:999px;font-size:.82rem;font-weight:600;cursor:pointer;border:1.5px solid;transition:all .2s}
.role-seeker{background:rgba(56,189,248,.08);border-color:rgba(56,189,248,.3);color:#38BDF8}
.role-recruiter{background:rgba(99,102,241,.08);border-color:rgba(99,102,241,.3);color:#A5B4FC}

/* Shared input styles */
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:rgba(14,24,42,.8)!important;border:1.5px solid rgba(56,189,248,.18)!important;border-radius:12px!important;color:#E8EDF5!important;font-family:'DM Sans',sans-serif!important;font-size:.95rem!important;transition:border-color .25s!important}
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{border-color:rgba(56,189,248,.55)!important;box-shadow:0 0 0 3px rgba(56,189,248,.08)!important;outline:none!important}
[data-testid="stTextInput"] label,[data-testid="stTextArea"] label{color:#6B7FA3!important;font-size:.82rem!important;font-weight:500!important}
[data-testid="stSelectbox"]>div>div{background:rgba(14,24,42,.8)!important;border:1.5px solid rgba(56,189,248,.15)!important;border-radius:12px!important;color:#E8EDF5!important}
[data-testid="stSelectbox"] label{color:#6B7FA3!important;font-size:.82rem!important;font-weight:500!important}
[data-baseweb="select"] span{color:#E8EDF5!important}
[data-testid="stButton"]>button{width:100%;height:3.1rem;background:linear-gradient(135deg,#0EA5E9 0%,#2563EB 100%)!important;border:none!important;border-radius:12px!important;color:#fff!important;font-family:'Syne',sans-serif!important;font-size:.95rem!important;font-weight:700!important;cursor:pointer!important;transition:all .2s!important;box-shadow:0 4px 24px rgba(14,165,233,.28)!important}
[data-testid="stButton"]>button:hover{transform:translateY(-1px)!important;box-shadow:0 8px 32px rgba(14,165,233,.42)!important}

/* Secondary / outline button override using key pattern */
button[kind="secondary"]{background:rgba(14,24,42,.6)!important;border:1.5px solid rgba(56,189,248,.2)!important;color:#38BDF8!important;box-shadow:none!important}

.badge{display:inline-flex;align-items:center;gap:.4rem;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.25);border-radius:999px;padding:.3rem .9rem;font-size:.72rem;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#38BDF8;margin-bottom:1.4rem}
.hero-title{font-family:'Syne',sans-serif;font-size:clamp(2.2rem,5vw,3.6rem);font-weight:800;line-height:1.05;letter-spacing:-.02em;margin-bottom:.9rem;background:linear-gradient(135deg,#E8EDF5 30%,#38BDF8 80%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.hero-sub{font-size:1rem;font-weight:300;color:#6B7FA3;line-height:1.7;max-width:540px;margin-bottom:2.4rem}
.divider{height:1px;background:linear-gradient(90deg,transparent,rgba(56,189,248,.3),transparent);margin:2.2rem 0}
.sec-label{font-family:'Syne',sans-serif;font-size:.73rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#38BDF8;margin-bottom:.55rem}
.pred-card{background:linear-gradient(135deg,rgba(14,42,74,.7) 0%,rgba(8,18,34,.9) 100%);border:1px solid rgba(56,189,248,.22);border-radius:20px;padding:1.8rem 2.2rem;margin-bottom:2rem;position:relative;overflow:hidden;animation:slideUp .45s cubic-bezier(.16,1,.3,1) forwards}
.pred-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#0EA5E9,#6366F1,#0EA5E9);background-size:200%;animation:shimmer 2.5s linear infinite}
@keyframes shimmer{from{background-position:200% 0}to{background-position:-200% 0}}
@keyframes slideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.pred-eyebrow{font-size:.7rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:#38BDF8;margin-bottom:.4rem}
.pred-title{font-family:'Syne',sans-serif;font-size:1.9rem;font-weight:800;letter-spacing:-.02em;color:#E8EDF5}
.filter-bar{background:rgba(14,24,42,.5);border:1px solid rgba(56,189,248,.1);border-radius:16px;padding:1.4rem 1.6rem;margin-bottom:1.8rem}
.filter-section-title{font-family:'Syne',sans-serif;font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#4B6080;margin-bottom:1rem;padding-bottom:.5rem;border-bottom:1px solid rgba(56,189,248,.08)}
.job-card{background:rgba(10,20,36,.7);border:1px solid rgba(56,189,248,.1);border-radius:16px;padding:1.4rem 1.6rem;margin-bottom:1rem;transition:border-color .2s,transform .2s;animation:slideUp .4s cubic-bezier(.16,1,.3,1) both}
.job-card:hover{border-color:rgba(56,189,248,.32);transform:translateY(-2px)}
.job-top{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap}
.job-title-text{font-family:'Syne',sans-serif;font-size:1.05rem;font-weight:700;color:#E8EDF5;margin-bottom:.2rem}
.job-company{font-size:.88rem;color:#4B6080}
.job-badges{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.85rem}
.bt{padding:.22rem .7rem;border-radius:999px;font-size:.72rem;font-weight:600;letter-spacing:.05em}
.b-remote{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.25);color:#86EFAC}
.b-hybrid{background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.25);color:#FDE68A}
.b-onsite{background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.25);color:#C7D2FE}
.b-full{background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.2);color:#7DD3FC}
.b-part{background:rgba(167,139,250,.08);border:1px solid rgba(167,139,250,.2);color:#C4B5FD}
.b-intern{background:rgba(251,146,60,.08);border:1px solid rgba(251,146,60,.2);color:#FED7AA}
.b-contract{background:rgba(236,72,153,.08);border:1px solid rgba(236,72,153,.2);color:#FBCFE8}
.b-loc{background:rgba(56,189,248,.05);border:1px solid rgba(56,189,248,.12);color:#4B6080}
.b-platform-linkedin{background:rgba(10,102,194,.12);border:1px solid rgba(10,102,194,.3);color:#7DB3E8}
.b-platform-internshala{background:rgba(0,168,120,.1);border:1px solid rgba(0,168,120,.25);color:#6DD9B8}
.b-platform-naukri{background:rgba(255,105,0,.1);border:1px solid rgba(255,105,0,.25);color:#FFB37A}
.b-platform-angellist{background:rgba(236,72,153,.08);border:1px solid rgba(236,72,153,.2);color:#FBCFE8}
.b-platform-company{background:rgba(56,189,248,.05);border:1px solid rgba(56,189,248,.12);color:#7DD3FC}
.job-desc{font-size:.84rem;color:#4B6080;line-height:1.6;margin-top:.75rem}
.job-skills{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.65rem}
.skill-tag{background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.18);border-radius:999px;padding:.18rem .6rem;font-size:.72rem;color:#A5B4FC}
.salary{font-family:'Syne',sans-serif;font-size:.82rem;font-weight:700;color:#38BDF8;white-space:nowrap}
.apply-btn{display:inline-flex;align-items:center;gap:.35rem;background:linear-gradient(135deg,#0EA5E9,#2563EB);border:none;border-radius:9px;padding:.42rem 1rem;font-size:.8rem;font-weight:700;color:#fff;text-decoration:none;letter-spacing:.04em;transition:filter .2s,transform .2s;white-space:nowrap}
.apply-btn:hover{filter:brightness(1.12);transform:translateY(-1px)}
.no-results{text-align:center;padding:3rem 1rem;color:#3A4A63}
.stat-pill{display:inline-flex;align-items:center;gap:.3rem;background:rgba(14,24,42,.6);border:1px solid rgba(56,189,248,.12);border-radius:999px;padding:.3rem .9rem;font-size:.78rem;color:#4B6080;margin-right:.5rem;margin-bottom:.4rem}
.stat-pill b{color:#38BDF8;font-family:'Syne',sans-serif}
.err{background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);border-radius:14px;padding:1rem 1.4rem;color:#FCA5A5;font-size:.9rem;margin-top:1rem}
.ok{background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.22);border-radius:14px;padding:1rem 1.4rem;color:#86EFAC;font-size:.9rem;margin-top:.8rem}
.warn{background:rgba(251,191,36,.06);border:1px solid rgba(251,191,36,.2);border-radius:14px;padding:.8rem 1.2rem;color:#FDE68A;font-size:.84rem;margin-bottom:1rem}
.chip-row{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.6rem}
.chip{background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.22);border-radius:999px;padding:.2rem .65rem;font-size:.76rem;color:#A5B4FC}
.stats-row{display:flex;flex-wrap:wrap;gap:.6rem;margin-bottom:1.6rem}
.stats-card{background:rgba(14,24,42,.5);border:1px solid rgba(56,189,248,.1);border-radius:14px;padding:.9rem 1.2rem;flex:1;min-width:110px;text-align:center}
.stats-card .num{font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:#38BDF8}
.stats-card .lbl{font-size:.72rem;color:#4B6080;margin-top:.2rem;letter-spacing:.06em;text-transform:uppercase}
.section-header{font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700;color:#4B6080;letter-spacing:.06em;text-transform:uppercase;margin-bottom:1rem;padding-bottom:.5rem;border-bottom:1px solid rgba(56,189,248,.08)}
.fallback-note{background:rgba(56,189,248,.04);border:1px solid rgba(56,189,248,.1);border-radius:12px;padding:.7rem 1rem;font-size:.82rem;color:#4B6080;margin-bottom:1rem}
/* Recruiter */
.recruiter-job-card{background:rgba(10,20,36,.7);border:1px solid rgba(99,102,241,.15);border-radius:14px;padding:1.2rem 1.4rem;margin-bottom:.9rem}
.app-row{background:rgba(14,24,42,.5);border:1px solid rgba(56,189,248,.1);border-radius:12px;padding:1rem 1.2rem;margin-bottom:.7rem}
.status-pending{color:#FDE68A}
.status-verified{color:#86EFAC}
.status-rejected{color:#FCA5A5}
.status-shortlisted{color:#A5B4FC}
/* Nav bar */
.top-nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:2rem;padding:.75rem 1.4rem;background:rgba(14,24,42,.6);border:1px solid rgba(56,189,248,.1);border-radius:14px}
.nav-brand{font-family:'Syne',sans-serif;font-weight:800;font-size:1.1rem;color:#38BDF8}
.nav-user{font-size:.82rem;color:#4B6080}
.nav-role{font-size:.72rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;padding:.2rem .65rem;border-radius:999px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.2);color:#38BDF8;margin-left:.5rem}
</style>
""", unsafe_allow_html=True)


# ── State initialisation ───────────────────────────────────────────────────────
for k, v in [
    ("user", None), ("page", "login"),
    ("jobs", []), ("predicted", None), ("searched", False),
    ("fallback_used", False), ("stats", None), ("featured", []),
    ("rec_jobs", []), ("rec_apps", []),
    ("auth_tab", "login"), ("register_role", "job_seeker"),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── URL param: email verification ──────────────────────────────────────────────
params = st.query_params
if "verify_token" in params and "email" in params:
    r = requests.post(f"{API}/auth/verify",
                      json={"email": params["email"], "token": params["verify_token"]},
                      timeout=8)
    msg = r.json().get("message", "Verification attempted.")
    st.session_state["_verify_msg"] = msg

if "verify_application" in params and "app_id" in params:
    r = requests.post(f"{API}/apply/verify",
                      json={"app_id": int(params["app_id"]), "token": params["verify_application"]},
                      timeout=8)
    msg = r.json().get("message", "Application verification attempted.")
    st.session_state["_app_verify_msg"] = msg


# ── API helpers ───────────────────────────────────────────────────────────────
def api_predict(skills):
    try:
        r = requests.post(f"{API}/predict", json={"text": skills}, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot reach API server on port 8000."}
    except Exception as e:
        return {"error": str(e)}

def api_search(title, location, work_mode, job_type):
    try:
        r = requests.post(f"{API}/jobs/search", json={
            "job_title":  title,
            "location":   None if location  == "Any" else location,
            "work_mode":  None if work_mode  == "Any" else work_mode.lower(),
            "job_type":   None if job_type   == "Any" else job_type.lower(),
        }, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

def api_stats():
    try:
        r = requests.get(f"{API}/jobs/stats", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def api_featured(n=6):
    try:
        r = requests.get(f"{API}/jobs/random?n={n}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

def api_register(name, email, password, role, company_name=""):
    try:
        r = requests.post(f"{API}/auth/register", json={
            "name": name, "email": email, "password": password,
            "role": role, "company_name": company_name
        }, timeout=8)
        return r.json()
    except Exception as e:
        return {"ok": False, "message": str(e)}

def api_login(email, password):
    try:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=8)
        return r.json()
    except Exception as e:
        return {"ok": False, "message": str(e)}

def api_post_job(data):
    try:
        r = requests.post(f"{API}/recruiter/jobs", json=data, timeout=8)
        return r.json()
    except Exception as e:
        return {"ok": False, "message": str(e)}

def api_get_recruiter_jobs(rid):
    try:
        r = requests.get(f"{API}/recruiter/jobs/{rid}", timeout=8)
        return r.json()
    except Exception:
        return []

def api_get_applications(rid):
    try:
        r = requests.get(f"{API}/recruiter/applications/{rid}", timeout=8)
        return r.json()
    except Exception:
        return []

def api_update_app_status(app_id, status, recruiter_id):
    try:
        r = requests.patch(f"{API}/recruiter/applications/{app_id}",
                           json={"status": status, "recruiter_id": recruiter_id}, timeout=8)
        return r.json()
    except Exception as e:
        return {"ok": False, "message": str(e)}

def api_apply(job_id, name, email, resume, cover):
    try:
        r = requests.post(f"{API}/apply", json={
            "job_id": job_id, "name": name, "email": email,
            "resume_text": resume, "cover_letter": cover
        }, timeout=8)
        return r.json()
    except Exception as e:
        return {"ok": False, "message": str(e)}

def api_delete_job(job_id, recruiter_id):
    try:
        r = requests.delete(f"{API}/recruiter/jobs/{job_id}",
                            json={"recruiter_id": recruiter_id}, timeout=8)
        return r.json()
    except Exception as e:
        return {"ok": False, "message": str(e)}

def api_get_seeker_history(email):
    try:
        r = requests.get(f"{API}/apply/history/{email}", timeout=8)
        return r.json()
    except Exception:
        return []


# ── Badge / icon helpers ───────────────────────────────────────────────────────
def work_mode_badge(t):
    cls  = {"remote": "b-remote", "hybrid": "b-hybrid", "onsite": "b-onsite"}.get(t.lower(), "b-onsite")
    icon = {"remote": "🌐", "hybrid": "🏠", "onsite": "🏢"}.get(t.lower(), "📍")
    return f'<span class="bt {cls}">{icon} {t.title()}</span>'

def job_type_badge(t):
    cls  = {"full-time":"b-full","part-time":"b-part","internship":"b-intern","contract":"b-contract"}.get(t.lower(),"b-full")
    icon = {"full-time":"⏰","part-time":"🕐","internship":"🎓","contract":"📋"}.get(t.lower(),"⏰")
    return f'<span class="bt {cls}">{icon} {t.title()}</span>'

def platform_badge(p):
    if not p: return ""
    pl = p.lower()
    if "linkedin"    in pl: return '<span class="bt b-platform-linkedin">🔗 LinkedIn</span>'
    if "internshala" in pl: return '<span class="bt b-platform-internshala">🎓 Internshala</span>'
    if "naukri"      in pl: return '<span class="bt b-platform-naukri">💼 Naukri</span>'
    if "angel"       in pl: return '<span class="bt b-platform-angellist">🚀 AngelList</span>'
    return '<span class="bt b-platform-company">🏛️ Company</span>'

JOB_ICONS = {
    "data":"📊","machine":"🤖","software":"💻","frontend":"🎨","backend":"⚙️",
    "full":"🚀","security":"🔐","devops":"🛠️","analyst":"📈","engineer":"🔧",
    "scientist":"🧪","designer":"✏️","cloud":"☁️","product":"📋","android":"📱",
    "ios":"📱","nlp":"🧠","ai ":"🤖","blockchain":"⛓️","qa":"🧪","mobile":"📱",
    "python":"🐍","java":"☕","react":"⚛️","node":"🟩","flutter":"🦋",
    "mlops":"⚙️","research":"🔬","quant":"📐","risk":"⚠️","sre":"🔩","llm":"🧠",
}
def job_icon(title):
    t = title.lower()
    for kw, ic in JOB_ICONS.items():
        if kw in t: return ic
    return "💼"

def parse_skills(text):
    return [s.strip() for s in re.split(r"[,\n;]+", text) if s.strip()][:12]

def status_cls(s):
    return {"pending":"status-pending","verified":"status-verified",
            "rejected":"status-rejected","shortlisted":"status-shortlisted"}.get(s,"status-pending")


LOCATIONS  = ["Any","Bangalore","Hyderabad","Mumbai","Pune","Gurgaon","Noida","Chennai","Remote"]
WORK_MODES = ["Any","Remote","Hybrid","Onsite"]
JOB_TYPES  = ["Any","Full-time","Part-time","Internship","Contract"]


# ══════════════════════════════════════════════════════════════════════════════
# RENDER: Job card (used by both job seeker and recruiter)
# ══════════════════════════════════════════════════════════════════════════════
def render_job_card(job, i=0, show_apply_form=False, recruiter_job=False):
    skill_tags = "".join(
        f'<span class="skill-tag">{s.strip()}</span>'
        for s in (job.get("required_skills") or "").split(",") if s.strip()
    )
    plat_badge  = "" if recruiter_job else platform_badge(job.get("apply_platform"))
    source      = job.get("source_website") or ""
    source_html = f'<a href="{source}" target="_blank" style="font-size:.72rem;color:#1E3A5F;margin-left:.5rem;">View listing ↗</a>' if source and not recruiter_job else ""

    apply_link = job.get("apply_link","#")

    st.markdown(f"""
    <div class="job-card" style="animation-delay:{i*0.055}s">
        <div class="job-top">
            <div>
                <div class="job-title-text">{job_icon(job['job_title'])} &nbsp;{job['job_title']}</div>
                <div class="job-company">🏛️ &nbsp;{job['company']}</div>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:.5rem">
                <span class="salary">{job.get('salary_range') or 'Salary N/A'}</span>
                <a class="apply-btn" href="{apply_link}" target="_blank" rel="noopener">Apply Now →</a>
            </div>
        </div>
        <div class="job-badges">
            {work_mode_badge(job['work_mode'])}
            {job_type_badge(job['job_type'])}
            <span class="bt b-loc">📍 {job['location']}</span>
            {plat_badge}
            {source_html}
        </div>
        <div class="job-desc">{job.get('description', '')}</div>
        <div class="job-skills">{skill_tags}</div>
    </div>""", unsafe_allow_html=True)

    # Quick-apply form for recruiter-posted jobs
    if show_apply_form:
        with st.expander("📨 Apply to this position"):
            a_name  = st.text_input("Your Name",        key=f"an_{job['id']}")
            a_email = st.text_input("Your Email",        key=f"ae_{job['id']}")
            a_cv    = st.text_area("Paste Resume/Skills (optional)", height=80, key=f"acv_{job['id']}")
            a_cl    = st.text_area("Cover Letter (optional)",        height=80, key=f"acl_{job['id']}")
            if st.button("Submit Application", key=f"asub_{job['id']}"):
                res = api_apply(job["id"], a_name, a_email, a_cv, a_cl)
                if res.get("ok"):
                    st.markdown(f'<div class="ok">✅ {res.get("message", "Success")}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="err">⚠️ {res.get("message", res.get("detail", "Unknown error"))}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: LOGIN / REGISTER
# ══════════════════════════════════════════════════════════════════════════════
def page_auth():
    st.markdown('<div class="wrap">', unsafe_allow_html=True)

    # Show verification messages if redirected from email
    if "_verify_msg" in st.session_state:
        st.markdown(f'<div class="ok">✅ {st.session_state.pop("_verify_msg")}</div>',
                    unsafe_allow_html=True)
    if "_app_verify_msg" in st.session_state:
        st.markdown(f'<div class="ok">✅ {st.session_state.pop("_app_verify_msg")}</div>',
                    unsafe_allow_html=True)

    st.markdown('<div style="text-align:center;margin-bottom:2rem">', unsafe_allow_html=True)
    st.markdown('<div class="badge">🎯 &nbsp;SkillMatch</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title" style="font-size:2.4rem;text-align:center">Welcome Back</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;color:#4B6080;font-size:.95rem">Sign in or create an account to get started</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Tab switcher
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔑  Log In",    use_container_width=True, key="tab_login"):
            st.session_state.auth_tab = "login"
    with c2:
        if st.button("✨  Register",  use_container_width=True, key="tab_reg"):
            st.session_state.auth_tab = "register"

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── LOGIN ──
    if st.session_state.auth_tab == "login":
        with st.container():
            st.markdown('<div class="sec-label">Email</div>', unsafe_allow_html=True)
            l_email = st.text_input("", placeholder="you@example.com", key="l_email", label_visibility="collapsed")
            st.markdown('<div class="sec-label" style="margin-top:.8rem">Password</div>', unsafe_allow_html=True)
            l_pass  = st.text_input("", placeholder="••••••••", type="password", key="l_pass", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Log In →", key="do_login"):
                if not l_email or not l_pass:
                    st.markdown('<div class="err">Please fill in all fields.</div>', unsafe_allow_html=True)
                else:
                    res = api_login(l_email.strip(), l_pass)
                    if res.get("ok"):
                        st.session_state.user = res["user"]
                        st.session_state.page = "app"
                        st.rerun()
                    else:
                        st.markdown(f'<div class="err">⚠️ {res.get("message", res.get("detail", "Unknown error"))}</div>', unsafe_allow_html=True)

    # ── REGISTER ──
    else:
        st.markdown('<div style="margin-bottom:1rem">', unsafe_allow_html=True)
        st.markdown('<div class="sec-label">I am a…</div>', unsafe_allow_html=True)
        rc1, rc2 = st.columns(2)
        with rc1:
            if st.button("🔍  Job Seeker", use_container_width=True, key="role_seeker"):
                st.session_state.register_role = "job_seeker"
        with rc2:
            if st.button("🏢  Recruiter",  use_container_width=True, key="role_recruiter"):
                st.session_state.register_role = "recruiter"
        role = st.session_state.register_role
        st.markdown(f'<div style="font-size:.78rem;color:#38BDF8;margin:.4rem 0 1rem">Selected: <b>{"Job Seeker" if role=="job_seeker" else "Recruiter"}</b></div>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        r_name  = st.text_input("Full Name",     placeholder="Priya Sharma",          key="r_name")
        r_email = st.text_input("Email Address", placeholder="priya@example.com",     key="r_email")
        r_pass  = st.text_input("Password",      placeholder="Min 6 characters",      key="r_pass",  type="password")
        r_comp  = ""
        if role == "recruiter":
            r_comp = st.text_input("Company Name", placeholder="e.g. Razorpay",       key="r_comp")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create Account →", key="do_register"):
            res = api_register(r_name.strip(), r_email.strip(), r_pass, role, r_comp.strip())
            if res.get("ok"):
                st.markdown(f'<div class="ok">✅ {res.get("message", "Success")}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="err">⚠️ {res.get("message", res.get("detail", "Unknown error"))}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: JOB SEEKER DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_job_seeker():
    user = st.session_state.user

    # Nav bar
    st.markdown(f"""
    <div class="top-nav">
        <div>
            <span class="nav-brand">🎯 SkillMatch</span>
            <span class="nav-role">Job Seeker</span>
        </div>
        <div class="nav-user">👤 {user['name']} · {user['email']}</div>
    </div>""", unsafe_allow_html=True)

    # Hero
    st.markdown("""
    <div class="badge">⚡ &nbsp;AI-Powered Job Matching</div>
    <h1 class="hero-title">Discover Jobs That<br/>Match Your Skills</h1>
    <p class="hero-sub">Enter your skills — our ML model predicts your best-fit role and finds live listings with <b>direct apply links</b>.</p>
    """, unsafe_allow_html=True)

    # Stats
    if st.session_state.stats is None:
        st.session_state.stats = api_stats()
    stats = st.session_state.stats
    if stats:
        bm = stats.get("by_mode", {})
        bt = stats.get("by_type", {})
        st.markdown(f"""
        <div class="stats-row">
            <div class="stats-card"><div class="num">{stats['total']:,}</div><div class="lbl">Total Listings</div></div>
            <div class="stats-card"><div class="num">{bm.get('remote',0)}</div><div class="lbl">Remote</div></div>
            <div class="stats-card"><div class="num">{bm.get('hybrid',0)}</div><div class="lbl">Hybrid</div></div>
            <div class="stats-card"><div class="num">{bt.get('internship',0)}</div><div class="lbl">Internships</div></div>
            <div class="stats-card"><div class="num">{bt.get('contract',0)}</div><div class="lbl">Contracts</div></div>
        </div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔍 Find Jobs", "📜 Application History"])
    with tab1:
        # Skills input
        st.markdown('<div class="sec-label">Your Skills</div>', unsafe_allow_html=True)
        skills_input = st.text_area("skills", placeholder="e.g.  Python, Machine Learning, SQL, TensorFlow…",
                                    height=110, label_visibility="collapsed")
        if skills_input.strip():
            chips = parse_skills(skills_input)
            st.markdown('<div class="chip-row">' + "".join(f'<span class="chip">{s}</span>' for s in chips) + '</div>',
                        unsafe_allow_html=True)
    
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
        # Filters
        st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
        st.markdown('<div class="filter-section-title">🎛️ &nbsp;Job Preferences</div>', unsafe_allow_html=True)
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            st.markdown('<div class="sec-label">📍 Location</div>', unsafe_allow_html=True)
            sel_location  = st.selectbox("location",  LOCATIONS,  key="loc", label_visibility="collapsed")
        with fc2:
            st.markdown('<div class="sec-label">🏢 Work Mode</div>', unsafe_allow_html=True)
            sel_work_mode = st.selectbox("work mode", WORK_MODES, key="wmode", label_visibility="collapsed")
        with fc3:
            st.markdown('<div class="sec-label">💼 Job Type</div>', unsafe_allow_html=True)
            sel_job_type  = st.selectbox("job type",  JOB_TYPES,  key="jtype", label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    
        _, bc, _ = st.columns([1, 2, 1])
        with bc:
            go = st.button("⚡  Find Matching Jobs", use_container_width=True)
    
        if go:
            if not skills_input.strip():
                st.markdown('<div class="err">⚠️ Please enter at least one skill.</div>', unsafe_allow_html=True)
            else:
                with st.spinner("Analysing your skill profile…"):
                    pred = api_predict(skills_input.strip())
                if "error" in pred:
                    st.markdown(f'<div class="err">🚨 {pred["error"]}</div>', unsafe_allow_html=True)
                else:
                    # Backend returns top_prediction/results in current API contract.
                    title = pred.get("top_prediction") or pred.get("prediction", "")
                    st.session_state.predicted = title
                    with st.spinner(f"Searching jobs for '{title}'…"):
                        jobs = api_search(str(title), sel_location, sel_work_mode, sel_job_type)
                    st.session_state.jobs     = jobs
                    st.session_state.searched = True
    
        # Prediction card
        if st.session_state.predicted:
            title = st.session_state.predicted
            st.markdown(f"""
            <div class="pred-card">
                <div class="pred-eyebrow">✦ &nbsp;Predicted Role</div>
                <div class="pred-title">{job_icon(str(title))} &nbsp;{title}</div>
                <div style="font-size:.85rem;color:#4B6080;margin-top:.4rem">Showing listings matched to your predicted role — all links go directly to the apply page.</div>
            </div>""", unsafe_allow_html=True)
    
        # Job listings
        if st.session_state.searched:
            jobs = st.session_state.jobs
            st.markdown(f"""
            <div style="margin-bottom:1.4rem">
                <span class="stat-pill"><b>{len(jobs)}</b> listings found</span>
            </div>""", unsafe_allow_html=True)
            if not jobs:
                st.markdown('<div class="no-results"><div style="font-size:2.5rem">🔍</div><div style="color:#4B6080;margin-top:.5rem">No matches — try setting filters to "Any".</div></div>', unsafe_allow_html=True)
            else:
                for i, job in enumerate(jobs):
                    render_job_card(job, i)
        elif not st.session_state.searched:
            if not st.session_state.featured:
                st.session_state.featured = api_featured(6)
            featured = st.session_state.featured
            if featured:
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                st.markdown('<div class="section-header">✨ Featured Listings — enter your skills above for personalised matches</div>', unsafe_allow_html=True)
                for i, job in enumerate(featured):
                    render_job_card(job, i)
    
    with tab2:
        if st.button("🔄 Refresh History"):
            st.session_state._seeker_history = None
        if "_seeker_history" not in st.session_state or st.session_state._seeker_history is None:
            st.session_state._seeker_history = api_get_seeker_history(user["email"])
        apps = st.session_state._seeker_history
        st.markdown(f'<div style="margin-bottom:1rem"><span class="stat-pill"><b>{len(apps)}</b> application(s)</span></div>', unsafe_allow_html=True)
        if not apps:
            st.markdown('<div class="no-results"><div style="font-size:2rem">📭</div><div style="color:#4B6080;margin-top:.4rem">No applications found. Apply to jobs to see them here!</div></div>', unsafe_allow_html=True)
        for a in apps:
            scls   = status_cls(a.get("status","pending"))
            status = a.get("status","pending").title()
            st.markdown(f"""
            <div class="app-row">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
                    <div>
                        <div style="font-family:'Syne',sans-serif;font-weight:700;color:#E8EDF5">{job_icon(a.get("job_title", "Unknown Role"))} &nbsp;{a.get("job_title", "Unknown Role")}</div>
                        <div style="font-size:.82rem;color:#4B6080">🏢 {a.get("company", "Unknown Company")} &nbsp;·&nbsp; Applied: {a.get("applied_at","")[:10]}</div>
                    </div>
                    <span class="bt {scls}" style="font-size:.78rem;padding:.3rem .8rem;background:transparent;border:1px solid currentColor">{status}</span>
                </div>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: RECRUITER DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_recruiter():
    user = st.session_state.user
    rid  = user["id"]

    # Nav bar
    st.markdown(f"""
    <div class="top-nav">
        <div>
            <span class="nav-brand">🎯 SkillMatch</span>
            <span class="nav-role" style="background:rgba(99,102,241,.08);border-color:rgba(99,102,241,.3);color:#A5B4FC">Recruiter</span>
        </div>
        <div class="nav-user">🏢 {user.get('company_name','') or user['name']} · {user['email']}</div>
    </div>""", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📋 Post a Job", "💼 My Job Listings", "👥 Applicants"])

    # ── TAB 1: Post a job ─────────────────────────────────────────────────────
    with tab1:
        st.markdown('<div class="section-header" style="margin-top:1rem">Post a New Job Opening</div>', unsafe_allow_html=True)
        j_title   = st.text_input("Job Title *",    placeholder="e.g. Senior Data Scientist")
        j_loc     = st.text_input("Location *",     placeholder="e.g. Bangalore / Remote")
        jc1, jc2  = st.columns(2)
        with jc1:
            j_mode = st.selectbox("Work Mode *", ["remote","hybrid","onsite"])
        with jc2:
            j_type = st.selectbox("Job Type *",  ["full-time","part-time","internship","contract"])
        j_skills  = st.text_input("Required Skills", placeholder="Python, SQL, ML, TensorFlow")
        j_salary  = st.text_input("Salary Range",   placeholder="₹15L–₹25L")
        j_desc    = st.text_area("Job Description",  height=110,
                                  placeholder="Describe the role, responsibilities and requirements…")
        j_link    = st.text_input("Direct Apply Link *",
                                   placeholder="https://yourcompany.com/apply/role-id  ← must be direct apply URL")
        st.markdown('<div style="font-size:.75rem;color:#2A3A53;margin-bottom:.6rem">⚠️ Paste the link that opens the application form directly — not just the careers homepage.</div>',
                    unsafe_allow_html=True)

        if st.button("🚀 Post Job", use_container_width=True):
            res = api_post_job({
                "recruiter_id":   rid,
                "job_title":      j_title.strip(),
                "location":       j_loc.strip(),
                "work_mode":      j_mode,
                "job_type":       j_type,
                "required_skills":j_skills.strip(),
                "salary_range":   j_salary.strip(),
                "description":    j_desc.strip(),
                "apply_link":     j_link.strip(),
            })
            if res.get("ok"):
                st.markdown(f'<div class="ok">✅ {res.get("message", "Success")}</div>', unsafe_allow_html=True)
                st.session_state.rec_jobs = []  # force refresh
            else:
                st.markdown(f'<div class="err">⚠️ {res.get("message", res.get("detail", "Unknown error"))}</div>', unsafe_allow_html=True)

    # ── TAB 2: My listings ────────────────────────────────────────────────────
    with tab2:
        if st.button("🔄 Refresh Listings"):
            st.session_state.rec_jobs = []
        if not st.session_state.rec_jobs:
            st.session_state.rec_jobs = api_get_recruiter_jobs(rid)
        jobs = st.session_state.rec_jobs
        st.markdown(f'<div style="margin-bottom:1rem"><span class="stat-pill"><b>{len(jobs)}</b> job(s) posted</span></div>', unsafe_allow_html=True)
        if not jobs:
            st.markdown('<div class="no-results"><div style="font-size:2rem">📭</div><div style="color:#4B6080;margin-top:.4rem">No jobs posted yet. Go to "Post a Job" to get started.</div></div>', unsafe_allow_html=True)
        for i, job in enumerate(jobs):
            col_j, col_del = st.columns([9, 1])
            with col_j:
                render_job_card(job, i, recruiter_job=True)
            with col_del:
                st.markdown("<br><br><br>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_{job['id']}", help="Delete this listing"):
                    api_delete_job(job["id"], rid)
                    st.session_state.rec_jobs = []
                    st.rerun()

    # ── TAB 3: Applicants ─────────────────────────────────────────────────────
    with tab3:
        if st.button("🔄 Refresh Applicants"):
            st.session_state.rec_apps = []
        if not st.session_state.rec_apps:
            st.session_state.rec_apps = api_get_applications(rid)
        apps = st.session_state.rec_apps

        st.markdown(f'<div style="margin-bottom:1rem"><span class="stat-pill"><b>{len(apps)}</b> application(s)</span></div>', unsafe_allow_html=True)
        if not apps:
            st.markdown('<div class="no-results"><div style="font-size:2rem">📭</div><div style="color:#4B6080;margin-top:.4rem">No applications yet.</div></div>', unsafe_allow_html=True)

        # Group by job
        from collections import defaultdict
        by_job = defaultdict(list)
        for a in apps:
            by_job[a.get("job_title","Unknown Job")].append(a)

        for job_title, job_apps in by_job.items():
            with st.expander(f"💼 {job_title}  ({len(job_apps)} applicant(s))", expanded=True):
                for a in job_apps:
                    scls   = status_cls(a.get("status","pending"))
                    status = a.get("status","pending").title()
                    st.markdown(f"""
                    <div class="app-row">
                        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
                            <div>
                                <div style="font-family:'Syne',sans-serif;font-weight:700;color:#E8EDF5">{a['applicant_name']}</div>
                                <div style="font-size:.82rem;color:#4B6080">✉️ {a['applicant_email']} &nbsp;·&nbsp; Applied: {a.get('applied_at','')[:10]}</div>
                            </div>
                            <span class="bt {scls}" style="font-size:.78rem;padding:.3rem .8rem;background:transparent;border:1px solid currentColor">{status}</span>
                        </div>
                        {"<div style='margin-top:.6rem;font-size:.82rem;color:#4B6080'><b>Resume/Skills:</b> " + a.get('resume_text','—')[:200] + "</div>" if a.get('resume_text') else ""}
                        {"<div style='margin-top:.3rem;font-size:.82rem;color:#4B6080'><b>Cover Letter:</b> " + a.get('cover_letter','—')[:200] + "</div>" if a.get('cover_letter') else ""}
                    </div>""", unsafe_allow_html=True)

                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        if st.button("✅ Shortlist", key=f"sl_{a['id']}"):
                            api_update_app_status(a["id"], "shortlisted", rid)
                            st.session_state.rec_apps = []
                            st.rerun()
                    with sc2:
                        if st.button("🔍 Verify",    key=f"vf_{a['id']}"):
                            api_update_app_status(a["id"], "verified", rid)
                            st.session_state.rec_apps = []
                            st.rerun()
                    with sc3:
                        if st.button("❌ Reject",    key=f"rj_{a['id']}"):
                            api_update_app_status(a["id"], "rejected", rid)
                            st.session_state.rec_apps = []
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="wrap">', unsafe_allow_html=True)

if st.session_state.user is None:
    page_auth()
else:
    user = st.session_state.user
    # Logout button top-right corner using sidebar hack
    with st.sidebar:
        if st.button("🚪 Log Out"):
            st.session_state.user     = None
            st.session_state.page     = "login"
            st.session_state.jobs     = []
            st.session_state.predicted = None
            st.session_state.searched  = False
            st.session_state.featured  = []
            st.session_state.rec_jobs  = []
            st.session_state.rec_apps  = []
            st.rerun()

    if user["role"] == "recruiter":
        page_recruiter()
    else:
        page_job_seeker()

# Footer
st.markdown("""
<div style="text-align:center;margin-top:4rem;padding-top:2rem;border-top:1px solid rgba(56,189,248,.07)">
    <span style="font-size:.72rem;color:#1E2D42;letter-spacing:.08em">
        SKILLMATCH &nbsp;·&nbsp; Skill-Based Job Recommendation Engine &nbsp;·&nbsp;
        <span style="color:#1E3A5F">Direct Apply Links · Email Verification · Recruiter Portal</span>
    </span>
</div>""", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
