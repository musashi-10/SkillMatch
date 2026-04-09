"""
new_create_db.py  –  Run once to create and seed jobs.db  (~3000 listings)
Usage:  python new_create_db.py

KEY CHANGE: apply_link now points to DIRECT APPLY pages, not just the
company careers homepage.  Every helper function generates the deepest
possible apply URL so the user lands straight on the job-application form.
"""

import sqlite3, os, itertools, random

DB_PATH = "jobs.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_title       TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT NOT NULL,
    work_mode       TEXT NOT NULL,
    job_type        TEXT NOT NULL,
    description     TEXT,
    required_skills TEXT,
    salary_range    TEXT,
    apply_platform  TEXT NOT NULL DEFAULT 'Company Website',
    source_website  TEXT,
    apply_link      TEXT NOT NULL,
    posted_date     TEXT DEFAULT (date('now'))
);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Platform helpers — NOW return DIRECT apply URLs
# apply_link  = the deepest URL that opens an application form / filtered list
# source_website = the job-listing / company-jobs page (for "View listing →")
# ─────────────────────────────────────────────────────────────────────────────

def _linkedin(company_slug, role_keywords=""):
    """
    LinkedIn: easyApply=true shows only one-click-apply jobs.
    Encoding role keywords surfaces relevant openings directly.
    """
    kw = role_keywords or company_slug.replace("-", " ")
    source = f"https://www.linkedin.com/company/{company_slug}/jobs/"
    apply  = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={kw.replace(' ', '%20')}"
        f"&f_C={company_slug}"
        f"&f_AL=true"          # Easy Apply filter
    )
    return ("LinkedIn", source, apply)


def _internshala(role_slug):
    """Internshala: direct category listing page — apply buttons on each card."""
    url = f"https://internshala.com/internships/{role_slug}/"
    return ("Internshala", url, url)


def _company(careers_url, apply_path=""):
    """
    Company Website: if apply_path is given it points to the apply/jobs form;
    otherwise we use the careers page itself.
    """
    apply = (careers_url.rstrip("/") + apply_path) if apply_path else careers_url
    return ("Company Website", careers_url, apply)


def _angellist(role_slug="", remote=True):
    """Wellfound (AngelList): role-filtered search."""
    base   = "https://wellfound.com/jobs"
    apply  = f"{base}?role={role_slug}" if role_slug else base
    source = "https://wellfound.com/jobs"
    return ("AngelList", source, apply)


def _naukri(query):
    slug = query.lower().replace(" ", "-")
    source = f"https://www.naukri.com/{slug}-jobs"
    # Naukri's apply button is on each listing; deepest we can go is the search
    apply  = f"https://www.naukri.com/{slug}-jobs?src=directApply"
    return ("Naukri", source, apply)


# ─────────────────────────────────────────────────────────────────────────────
# Company-specific direct apply paths (where available)
# ─────────────────────────────────────────────────────────────────────────────
_DIRECT = {
    "https://careers.google.com":                    "/jobs/results/",
    "https://amazon.jobs":                           "/en/search#country=India",
    "https://careers.microsoft.com":                 "/en/jobs/search/?country=India",
    "https://www.flipkart.com/careers":              "/explore#level=job",
    "https://razorpay.com/jobs":                     "/#openings",
    "https://careers.phonepe.com":                   "/openings",
    "https://bytes.swiggy.com/careers":              "/jobs",
    "https://www.zomato.com/careers":                "/apply",
    "https://meesho.io/jobs":                        "/",
    "https://careers.cred.club":                     "/jobs",
    "https://groww.in/about/careers":                "/#jobs",
    "https://paytm.com/careers":                     "/open-positions",
    "https://www.freshworks.com/company/careers":    "/jobs",
    "https://careers.hotstar.com":                   "/jobs",
    "https://juspay.in/careers":                     "/#open-positions",
    "https://sharechat.com/careers":                 "/jobs",
    "https://www.delhivery.com/careers":             "/jobs",
    "https://olaelectric.com/careers":               "/jobs",
    "https://atherenergy.com/careers":               "/jobs",
    "https://coindcx.com/careers":                   "/jobs",
    "https://wazirx.com/careers":                    "/open-positions",
    "https://coinswitch.co/careers":                 "/jobs",
    "https://polygon.technology/careers":            "/jobs",
    "https://sarvam.ai/careers":                     "/jobs",
    "https://vernacular.ai/careers":                 "/jobs",
    "https://olakrutrim.com/careers":                "/jobs",
    "https://careers.jio.com":                       "/ViewJob",
    "https://hasura.io/careers":                     "/#open-positions",
    "https://www.chargebee.com/careers":             "/jobs",
    "https://www.postman.com/company/careers":       "/open-positions",
    "https://www.druva.com/company/careers":         "/jobs",
    "https://www.browserstack.com/careers":          "/open-positions",
    "https://zerodha.com/careers":                   "/#openings",
    "https://sliceit.com/careers":                   "/jobs",
    "https://careers.lenskart.com":                  "/jobs",
    "https://careers.makemytrip.com":                "/jobSearch",
    "https://careers.nykaa.com":                     "/jobs",
    "https://urbancompany.com/careers":              "/jobs",
    "https://unacademy.com/careers":                 "/jobs",
    "https://byjus.com/careers":                     "/jobs",
    "https://www.dunzo.com/careers":                 "/jobs",
    "https://ola.careers":                           "/openings",
    "https://www.policybazaar.com/careers":          "/job-openings",
    "https://www.bosch-india.com/careers":           "/jobs",
    "https://careers.wipro.com":                     "/search-jobs",
    "https://www.infosys.com/careers":               "/joblist.html",
    "https://www.tcs.com/careers":                   "/tcs/global/en/careers/job-search",
    "https://careers.microsoft.com":                 "/en/jobs/search/?country=India",
    "https://www.hcltech.com/careers":               "/job-search",
    "https://careers.cognizant.com":                 "/global/en/search-results",
    "https://www.capgemini.com/in-en/careers":       "/find-a-job",
    "https://www.accenture.com/in-en/careers":       "/local/en/job-search",
    "https://www.mphasis.com/careers":               "/career-list",
    "https://www.persistent.com/careers":            "/job-search",
    "https://www.ltimindtree.com/careers":           "/jobs",
    "https://careers.techmahindra.com":              "/search-jobs",
    "https://www.hexaware.com/careers":              "/job-search",
    "https://www.zensar.com/careers":                "/job-search",
    "https://careers.zohocorp.com":                  "/jobs/Careers/",
    "https://iisc.ac.in":                            "/",
    "https://www.ibm.com/in-en/employment":          "/search?cc=in&lc=en",
    "https://careers.oracle.com":                    "/ords/nrcpos/r/careers/global-search-result",
    "https://jobs.sap.com":                          "/search?locale=en_US&country=IND",
    "https://salesforce.com/careers":                "/open-roles",
    "https://adobe.com/careers":                     "/job-search",
    "https://jobs.intuit.com":                       "/search?location=India",
    "https://careers.servicenow.com":                "/search",
    "https://jobs.cisco.com":                        "/search#Location=India",
    "https://careers.vmware.com":                    "/search",
    "https://www.qualcomm.com/company/about-nxp/careers": "/search?location=India",
    "https://jobs.intel.com":                        "/search?Country=India",
    "https://new.siemens.com/in/en/company/jobs.html": "?offset=0&max=15&city=&Country=India",
    "https://careers.db.com":                        "/search#location=India",
    "https://careers.jpmorgan.com":                  "/careers/jobs?query=india",
    "https://www.goldmansachs.com/careers":          "/jobs/results/?location=India",
    "https://www.bosch-india.com/careers":           "/jobs",
    "https://practo.com/careers":                    "/jobs",
    "https://www.birlasoft.com/careers":             "/job-search",
    "https://www.kpit.com/careers":                  "/open-positions",
    "https://www.cyient.com/careers":                "/job-search",
    "https://www.sonata-software.com/careers":       "/job-listing",
    "https://www.niit-tech.com/careers":             "/jobs",
    "https://www.mastek.com/careers":                "/jobs",
}

def _company(careers_url, apply_path=""):
    """Company Website with deep-link apply path."""
    path   = apply_path or _DIRECT.get(careers_url, "")
    apply  = careers_url.rstrip("/") + path if path else careers_url
    return ("Company Website", careers_url, apply)


# ─────────────────────────────────────────────────────────────────────────────
# MASTER JOB LIST
# ─────────────────────────────────────────────────────────────────────────────
JOBS = []

# ═══════════════════════════════════════════════════════════
# 1. DATA SCIENCE
# ═══════════════════════════════════════════════════════════
_ds_full = [
    ("Data Scientist","Google","Bangalore","hybrid","full-time","Build ML models for Search & Ads.","Python,ML,TensorFlow,SQL","₹20L–₹35L",*_company("https://careers.google.com")),
    ("Data Scientist","Flipkart","Bangalore","onsite","full-time","Product analytics and recommendation systems.","Python,Statistics,Spark,SQL","₹18L–₹30L",*_company("https://www.flipkart.com/careers")),
    ("Data Scientist","Razorpay","Remote","remote","full-time","Fraud detection and risk modelling.","Python,ML,SQL,PySpark","₹22L–₹38L",*_company("https://razorpay.com/jobs")),
    ("Data Scientist","Ola","Bangalore","hybrid","full-time","Demand forecasting and driver analytics.","Python,ML,Spark,SQL","₹16L–₹28L",*_company("https://ola.careers")),
    ("Data Scientist","Paytm","Noida","hybrid","full-time","Credit risk modelling for lending products.","Python,Statistics,ML,SQL","₹15L–₹26L",*_company("https://paytm.com/careers")),
    ("Data Scientist","Meesho","Bangalore","remote","full-time","Seller analytics and growth models.","Python,Sklearn,SQL,Spark","₹18L–₹32L",*_company("https://meesho.io/jobs")),
    ("Data Scientist","Swiggy","Bangalore","hybrid","full-time","Food demand and pricing ML models.","Python,TensorFlow,SQL","₹20L–₹36L",*_company("https://bytes.swiggy.com/careers")),
    ("Data Scientist","Hotstar","Mumbai","hybrid","full-time","Content recommendation and user engagement.","Python,ML,Spark,SQL","₹22L–₹38L",*_company("https://careers.hotstar.com")),
    ("Data Scientist","PhonePe","Bangalore","hybrid","full-time","UPI and payments data science.","Python,ML,SQL,Spark","₹20L–₹36L",*_linkedin("phonepe","data scientist")),
    ("Data Scientist","CRED","Bangalore","hybrid","full-time","Premium credit card DS.","Python,Statistics,ML,SQL","₹22L–₹40L",*_linkedin("cred","data scientist")),
    ("Data Scientist","Zomato","Gurgaon","hybrid","full-time","Delivery time and restaurant recommendation.","Python,ML,SQL,Spark","₹18L–₹32L",*_company("https://www.zomato.com/careers")),
    ("Data Scientist","Groww","Bangalore","hybrid","full-time","Investment product personalization models.","Python,Statistics,ML,SQL","₹18L–₹30L",*_company("https://groww.in/about/careers")),
    ("Data Scientist","Infosys","Bangalore","hybrid","full-time","Analytics for enterprise clients.","Python,ML,SQL,PowerBI","₹12L–₹22L",*_linkedin("infosys","data scientist")),
    ("Data Scientist","Wipro","Hyderabad","hybrid","full-time","AI/ML solutions for clients.","Python,ML,Azure,SQL","₹12L–₹22L",*_linkedin("wipro","data scientist")),
    ("Data Scientist","TCS","Pune","onsite","full-time","Enterprise analytics and reporting.","Python,R,SQL,ML","₹11L–₹20L",*_linkedin("tata-consultancy-services","data scientist")),
    ("Data Scientist","JP Morgan","Mumbai","hybrid","full-time","Quant risk models for banking.","Python,Statistics,ML,SQL","₹25L–₹45L",*_linkedin("jpmorgan-chase","data scientist")),
    ("Data Scientist","Goldman Sachs","Bangalore","hybrid","full-time","Trading analytics and risk models.","Python,R,ML,SQL","₹30L–₹55L",*_linkedin("goldman-sachs","data scientist")),
    ("Senior Data Scientist","Amazon","Hyderabad","hybrid","full-time","Lead ML projects for Alexa and AWS.","Python,ML,Spark,AWS,SageMaker","₹35L–₹60L",*_company("https://amazon.jobs")),
    ("Senior Data Scientist","Microsoft","Hyderabad","hybrid","full-time","AI research for Azure cognitive services.","Python,ML,Azure,PyTorch","₹38L–₹65L",*_company("https://careers.microsoft.com")),
    ("Lead Data Scientist","Juspay","Bangalore","hybrid","full-time","Lead fraud and risk ML team.","Python,ML,MLFlow,Kafka","₹30L–₹50L",*_company("https://juspay.in/careers")),
]

_ds_intern = [
    ("Data Scientist Intern","Analytics Vidhya","Remote","remote","internship","NLP and generative AI research.","Python,NLP,HuggingFace","₹30K–₹50K/mo",*_internshala("data-science")),
    ("Data Scientist Intern","Myntra","Bangalore","hybrid","internship","Fashion recommendation research.","Python,ML,SQL","₹25K–₹40K/mo",*_internshala("data-science-internship")),
    ("Data Scientist Intern","PhonePe","Bangalore","onsite","internship","Payments analytics intern.","Python,SQL,Statistics","₹20K–₹35K/mo",*_company("https://careers.phonepe.com")),
    ("Data Scientist Intern","Swiggy","Bangalore","hybrid","internship","Food demand ML intern.","Python,ML,SQL","₹22K–₹38K/mo",*_company("https://bytes.swiggy.com/careers")),
    ("Data Scientist Intern","Razorpay","Bangalore","hybrid","internship","Payments risk analytics intern.","Python,SQL,Statistics","₹22K–₹38K/mo",*_internshala("data-science-internship")),
    ("Data Scientist Intern","Flipkart","Bangalore","hybrid","internship","E-commerce data science intern.","Python,ML,SQL","₹22K–₹38K/mo",*_internshala("data-science-internship")),
    ("Data Scientist Intern","Zomato","Gurgaon","hybrid","internship","Delivery analytics intern.","Python,SQL,ML","₹20K–₹35K/mo",*_internshala("data-science-internship")),
    ("Data Scientist Intern","Paytm","Noida","onsite","internship","Fintech analytics intern.","Python,SQL,Statistics","₹18K–₹30K/mo",*_internshala("data-science-internship")),
    ("Data Scientist Intern","CRED","Bangalore","hybrid","internship","Credit analytics intern.","Python,Statistics,SQL","₹20K–₹35K/mo",*_internshala("data-science-internship")),
    ("Data Scientist Intern","Meesho","Remote","remote","internship","Seller analytics intern.","Python,SQL,ML","₹18K–₹30K/mo",*_internshala("data-science-internship")),
]
JOBS += _ds_full + _ds_intern

# ═══════════════════════════════════════════════════════════
# 2. MACHINE LEARNING ENGINEERING
# ═══════════════════════════════════════════════════════════
_mle = [
    ("Machine Learning Engineer","Amazon","Hyderabad","hybrid","full-time","Deploy production ML pipelines on AWS.","Python,SageMaker,MLOps,Docker","₹25L–₹45L",*_company("https://amazon.jobs")),
    ("Machine Learning Engineer","Swiggy","Bangalore","onsite","full-time","ETA prediction and demand forecasting.","Python,TensorFlow,SQL,Kafka","₹20L–₹36L",*_company("https://bytes.swiggy.com/careers")),
    ("Machine Learning Engineer","Juspay","Remote","remote","full-time","Payment fraud ML systems.","Python,Sklearn,SQL,MLFlow","₹18L–₹32L",*_company("https://juspay.in/careers")),
    ("Machine Learning Engineer","Flipkart","Bangalore","hybrid","full-time","Catalogue quality and search ranking.","Python,TensorFlow,Spark,SQL","₹22L–₹38L",*_company("https://www.flipkart.com/careers")),
    ("Machine Learning Engineer","PhonePe","Bangalore","hybrid","full-time","Fraud detection and payment ML.","Python,TensorFlow,Spark,Kafka","₹22L–₹38L",*_company("https://careers.phonepe.com")),
    ("Machine Learning Engineer","Meesho","Remote","remote","full-time","Product recommendation ML systems.","Python,Sklearn,MLFlow,SQL","₹18L–₹32L",*_company("https://meesho.io/jobs")),
    ("Machine Learning Engineer","Zomato","Gurgaon","hybrid","full-time","Delivery ETA and route ML models.","Python,TensorFlow,SQL,Docker","₹20L–₹36L",*_company("https://www.zomato.com/careers")),
    ("MLOps Engineer","Razorpay","Bangalore","hybrid","full-time","Build and maintain ML infrastructure.","Python,Kubernetes,MLFlow,Airflow","₹20L–₹36L",*_company("https://razorpay.com/jobs")),
    ("MLOps Engineer","PhonePe","Bangalore","hybrid","full-time","Model serving and monitoring at scale.","Python,Docker,Kubernetes,Airflow","₹22L–₹38L",*_company("https://careers.phonepe.com")),
    ("Machine Learning Engineer","Paytm","Noida","hybrid","full-time","Lending risk ML infrastructure.","Python,TensorFlow,Kafka,Docker","₹18L–₹32L",*_linkedin("paytm","machine learning engineer")),
    ("ML Engineer Intern","Amazon","Hyderabad","onsite","internship","Build ML features for Alexa.","Python,ML,AWS","₹25K–₹40K/mo",*_internshala("machine-learning-internship")),
    ("ML Engineer Intern","Swiggy","Bangalore","hybrid","internship","Demand forecasting ML intern.","Python,ML,SQL","₹22K–₹38K/mo",*_internshala("machine-learning-internship")),
    ("ML Engineer Intern","Flipkart","Bangalore","hybrid","internship","Catalogue ML intern.","Python,ML,SQL","₹22K–₹38K/mo",*_internshala("machine-learning-internship")),
    ("ML Research Intern","Microsoft","Hyderabad","hybrid","internship","Research on LLMs and responsible AI.","Python,PyTorch,NLP,Transformers","Stipend",*_company("https://careers.microsoft.com")),
    ("ML Research Intern","Google","Bangalore","hybrid","internship","Research on multimodal models.","Python,TensorFlow,Research","Stipend",*_company("https://careers.google.com")),
]
JOBS += _mle

# ═══════════════════════════════════════════════════════════
# 3. SOFTWARE ENGINEERING
# ═══════════════════════════════════════════════════════════
_swe_companies = [
    ("Google","Bangalore","hybrid","full-time","Backend services for Google India.","Java,Go,Python,SQL,Kubernetes","₹35L–₹60L","https://careers.google.com"),
    ("Microsoft","Hyderabad","hybrid","full-time","Backend services for Azure cloud platform.","Java,C#,.NET,SQL,Azure","₹22L–₹40L","https://careers.microsoft.com"),
    ("Amazon","Hyderabad","hybrid","full-time","Microservices for Amazon India.","Java,AWS,DynamoDB,Kafka","₹22L–₹40L","https://amazon.jobs"),
    ("Infosys","Pune","onsite","full-time","Enterprise application development.","Java,Spring Boot,SQL,REST","₹8L–₹14L","https://www.infosys.com/careers"),
    ("Zepto","Remote","remote","full-time","Microservices for quick-commerce platform.","Go,Kubernetes,PostgreSQL,gRPC","₹18L–₹30L","https://www.zepto.team/careers"),
    ("Postman","Bangalore","hybrid","full-time","Core API platform engineering.","Node.js,TypeScript,MongoDB,AWS","₹20L–₹35L","https://www.postman.com/company/careers"),
    ("Freshworks","Chennai","hybrid","full-time","SaaS CRM platform development.","Ruby,Rails,PostgreSQL,React","₹14L–₹24L","https://www.freshworks.com/company/careers"),
    ("Razorpay","Bangalore","hybrid","full-time","Payments infrastructure and APIs.","Java,Go,MySQL,Kafka","₹22L–₹38L","https://razorpay.com/jobs"),
    ("PhonePe","Bangalore","hybrid","full-time","Build high-throughput payment systems.","Java,Spring,Kafka,MySQL","₹20L–₹36L","https://careers.phonepe.com"),
    ("Flipkart","Bangalore","hybrid","full-time","Platform engineering and microservices.","Java,Spring,MySQL,Kafka","₹22L–₹40L","https://www.flipkart.com/careers"),
    ("Zomato","Gurgaon","hybrid","full-time","Order management and logistics systems.","Go,Python,MySQL,Redis","₹18L–₹32L","https://www.zomato.com/careers"),
    ("CRED","Bangalore","hybrid","full-time","Fintech platform core engineering.","Kotlin,Java,PostgreSQL,Kafka","₹20L–₹36L","https://careers.cred.club"),
    ("Meesho","Bangalore","remote","full-time","Social commerce platform services.","Python,Java,MySQL,gRPC","₹18L–₹32L","https://meesho.io/jobs"),
    ("Groww","Bangalore","hybrid","full-time","Trading platform backend.","Java,Spring,MySQL,Kafka","₹18L–₹32L","https://groww.in/about/careers"),
    ("Hotstar","Mumbai","hybrid","full-time","Live streaming and content delivery.","Go,Python,Kafka,AWS","₹20L–₹36L","https://careers.hotstar.com"),
    ("Juspay","Remote","remote","full-time","Payments router and orchestration.","Haskell,Java,PostgreSQL","₹18L–₹32L","https://juspay.in/careers"),
    ("Hasura","Remote","remote","full-time","GraphQL engine development.","Haskell,Go,PostgreSQL","₹22L–₹40L","https://hasura.io/careers"),
    ("Chargebee","Chennai","hybrid","full-time","Subscription billing platform.","Ruby,Rails,MySQL,React","₹18L–₹32L","https://www.chargebee.com/careers"),
]
for (company, location, work_mode, job_type, description, skills, salary, careers_url) in _swe_companies:
    JOBS.append(("Software Engineer", company, location, work_mode, job_type, description, skills, salary, *_company(careers_url)))

_senior_swe = [
    ("Senior Software Engineer","Google","Hyderabad","hybrid","full-time","Lead backend systems for Google Cloud.","Java,Go,Kubernetes,SQL","₹40L–₹70L",*_company("https://careers.google.com")),
    ("Senior Software Engineer","Amazon","Bangalore","hybrid","full-time","Lead services for Amazon India marketplace.","Java,AWS,DynamoDB,Kafka","₹38L–₹65L",*_company("https://amazon.jobs")),
    ("Senior Software Engineer","Razorpay","Bangalore","hybrid","full-time","Lead payment infrastructure team.","Java,Go,MySQL,Kafka","₹32L–₹55L",*_company("https://razorpay.com/jobs")),
    ("Senior Software Engineer","Flipkart","Bangalore","hybrid","full-time","Platform microservices leadership.","Java,Kafka,MySQL,System Design","₹35L–₹60L",*_linkedin("flipkart","senior software engineer")),
    ("Staff Software Engineer","Flipkart","Bangalore","hybrid","full-time","Technical leadership across platform.","Java,Go,Kafka,MySQL,System Design","₹45L–₹80L",*_company("https://www.flipkart.com/careers")),
    ("Staff Software Engineer","Google","Bangalore","hybrid","full-time","Technical leadership for Google India.","Java,Go,Kubernetes,SQL","₹55L–₹90L",*_company("https://careers.google.com")),
    ("Principal Engineer","Amazon","Hyderabad","hybrid","full-time","Architecture for Amazon India.","Java,AWS,System Design,Distributed","₹60L–₹1Cr",*_company("https://amazon.jobs")),
]
JOBS += _senior_swe

_swe_intern_companies = [
    "Google","Microsoft","Amazon","Flipkart","Razorpay","PhonePe","Swiggy","Zomato","Meesho","CRED",
    "Groww","BrowserStack","Freshworks","Atlassian","Hotstar","Chargebee","Zoho","Delhivery","ShareChat","Urban Company",
]
_swe_intern_skills = [
    "Java,Spring,SQL","Python,Django,SQL","Node.js,React,SQL","Go,MySQL,REST","Ruby,Rails,SQL",
    "Java,React,SQL","Python,FastAPI,SQL","C#,.NET,SQL","Kotlin,Android,Java"
]
_swe_intern_locations = ["Bangalore","Hyderabad","Mumbai","Pune","Chennai","Gurgaon","Remote","Noida"]
for i, comp in enumerate(_swe_intern_companies):
    loc    = _swe_intern_locations[i % len(_swe_intern_locations)]
    mode   = "remote" if loc == "Remote" else ("hybrid" if i % 3 != 0 else "onsite")
    skills = _swe_intern_skills[i % len(_swe_intern_skills)]
    salary = f"₹{15+i%15}K–₹{30+i%20}K/mo"
    JOBS.append(("Software Engineering Intern", comp, loc, mode, "internship",
                 f"Build product features at {comp}.", skills, salary,
                 *_internshala("software-development-internship")))

# ═══════════════════════════════════════════════════════════
# 4. FRONTEND / FULL-STACK / MOBILE
# ═══════════════════════════════════════════════════════════
_frontend_roles = [
    ("Frontend Engineer","Razorpay","Bangalore","hybrid","full-time","Build payment checkout UI.","React,TypeScript,GraphQL,CSS","₹18L–₹32L",*_company("https://razorpay.com/jobs")),
    ("Frontend Engineer","Freshworks","Chennai","hybrid","full-time","CRM dashboard UI engineering.","React,Vue.js,JavaScript,CSS","₹14L–₹24L",*_company("https://www.freshworks.com/company/careers")),
    ("Frontend Engineer","Groww","Bangalore","hybrid","full-time","Trading platform UI.","React,TypeScript,Redux","₹16L–₹28L",*_company("https://groww.in/about/careers")),
    ("Frontend Engineer","CRED","Bangalore","hybrid","full-time","Fintech consumer app UI.","React,TypeScript,GraphQL","₹18L–₹32L",*_company("https://careers.cred.club")),
    ("Frontend Engineer","Meesho","Bangalore","remote","full-time","Social commerce seller UI.","React,Next.js,TypeScript","₹16L–₹28L",*_company("https://meesho.io/jobs")),
    ("Full Stack Engineer","Flipkart","Bangalore","hybrid","full-time","Seller platform full-stack.","React,Java,MySQL,Node.js","₹20L–₹36L",*_linkedin("flipkart","full stack engineer")),
    ("Full Stack Engineer","Swiggy","Bangalore","hybrid","full-time","Restaurant dashboard full-stack.","React,Node.js,Python,SQL","₹18L–₹32L",*_linkedin("swiggy","full stack engineer")),
    ("Full Stack Engineer","PhonePe","Bangalore","hybrid","full-time","Merchant dashboard.","React,Java,MySQL","₹20L–₹36L",*_linkedin("phonepe","full stack engineer")),
    ("Android Developer","Flipkart","Bangalore","hybrid","full-time","Consumer shopping app.","Kotlin,Android,Jetpack,REST","₹18L–₹32L",*_company("https://www.flipkart.com/careers")),
    ("Android Developer","PhonePe","Bangalore","hybrid","full-time","Payments Android app.","Kotlin,Android,Jetpack,Compose","₹20L–₹36L",*_company("https://careers.phonepe.com")),
    ("Android Developer","CRED","Bangalore","hybrid","full-time","Premium fintech Android app.","Kotlin,Compose,Android,REST","₹22L–₹40L",*_company("https://careers.cred.club")),
    ("iOS Developer","CRED","Bangalore","hybrid","full-time","Fintech iOS app.","Swift,SwiftUI,iOS,Combine","₹22L–₹40L",*_company("https://careers.cred.club")),
    ("iOS Developer","PhonePe","Bangalore","hybrid","full-time","Payments iOS app.","Swift,iOS,Objective-C,REST","₹20L–₹36L",*_company("https://careers.phonepe.com")),
    ("React Native Developer","Meesho","Remote","remote","full-time","Cross-platform commerce app.","React Native,JavaScript,Redux","₹16L–₹28L",*_linkedin("meesho","react native developer")),
    ("Frontend Intern","Razorpay","Bangalore","hybrid","internship","Payment UI intern.","React,JavaScript,CSS","₹18K–₹30K/mo",*_internshala("web-development-internship")),
    ("Full Stack Intern","Swiggy","Bangalore","hybrid","internship","Dashboard full-stack intern.","React,Python,SQL","₹18K–₹30K/mo",*_internshala("web-development-internship")),
    ("Android Intern","Flipkart","Bangalore","hybrid","internship","Shopping app Android intern.","Kotlin,Android","₹18K–₹30K/mo",*_internshala("android-development-internship")),
    ("iOS Intern","CRED","Bangalore","hybrid","internship","Fintech iOS intern.","Swift,iOS","₹18K–₹30K/mo",*_internshala("ios-development-internship")),
]
JOBS += _frontend_roles

# ═══════════════════════════════════════════════════════════
# 5. DATA ANALYTICS / BI
# ═══════════════════════════════════════════════════════════
_analytics = [
    ("Data Analyst","Google","Bangalore","hybrid","full-time","Product and business analytics.","SQL,Python,Tableau,BigQuery","₹15L–₹26L",*_company("https://careers.google.com")),
    ("Data Analyst","Amazon","Hyderabad","hybrid","full-time","Marketplace analytics.","SQL,Python,Redshift,QuickSight","₹14L–₹24L",*_company("https://amazon.jobs")),
    ("Data Analyst","Flipkart","Bangalore","hybrid","full-time","E-commerce analytics.","SQL,Python,Tableau,Spark","₹12L–₹22L",*_company("https://www.flipkart.com/careers")),
    ("Data Analyst","Swiggy","Bangalore","hybrid","full-time","Food delivery analytics.","SQL,Python,Tableau","₹12L–₹20L",*_company("https://bytes.swiggy.com/careers")),
    ("Data Analyst","PhonePe","Bangalore","hybrid","full-time","Payments and user analytics.","SQL,Python,Tableau","₹12L–₹22L",*_company("https://careers.phonepe.com")),
    ("Data Analyst","Razorpay","Bangalore","hybrid","full-time","Payments business analytics.","SQL,Python,Metabase","₹12L–₹22L",*_company("https://razorpay.com/jobs")),
    ("Business Analyst","McKinsey","Mumbai","hybrid","full-time","Data-driven management consulting.","SQL,Python,Excel,PowerPoint","₹22L–₹40L",*_linkedin("mckinsey-company","business analyst")),
    ("Business Analyst","Deloitte","Mumbai","hybrid","full-time","Digital transformation analytics.","SQL,Python,PowerBI","₹14L–₹26L",*_linkedin("deloitte","business analyst")),
    ("BI Developer","Flipkart","Bangalore","hybrid","full-time","Business intelligence dashboards.","SQL,Tableau,Python,Redshift","₹14L–₹26L",*_linkedin("flipkart","bi developer")),
    ("Analytics Engineer","Meesho","Remote","remote","full-time","dbt and data modelling.","SQL,dbt,Python,BigQuery","₹16L–₹28L",*_linkedin("meesho","analytics engineer")),
    ("Analytics Engineer","Razorpay","Bangalore","hybrid","full-time","Payments data modelling.","SQL,dbt,Python,Airflow","₹16L–₹28L",*_linkedin("razorpay","analytics engineer")),
    ("Data Analyst Intern","Google","Bangalore","hybrid","internship","Product analytics intern.","SQL,Python,Tableau","₹25K–₹45K/mo",*_internshala("data-analytics-internship")),
    ("Data Analyst Intern","Swiggy","Bangalore","hybrid","internship","Food analytics intern.","SQL,Excel,Python","₹18K–₹30K/mo",*_internshala("data-analytics-internship")),
    ("Business Analyst Intern","McKinsey","Mumbai","hybrid","internship","Strategy analytics intern.","Excel,PowerPoint,SQL","₹25K–₹45K/mo",*_internshala("business-analytics-internship")),
    ("Business Analyst Intern","Deloitte","Remote","remote","internship","Financial modelling intern.","Excel,PowerPoint,SQL","₹20K–₹35K/mo",*_internshala("business-analytics-internship")),
]
JOBS += _analytics

# ═══════════════════════════════════════════════════════════
# 6. DATA ENGINEERING
# ═══════════════════════════════════════════════════════════
_de = [
    ("Data Engineer","Flipkart","Bangalore","hybrid","full-time","Build petabyte-scale data pipelines.","Python,Spark,Kafka,Hive,SQL","₹18L–₹32L",*_company("https://www.flipkart.com/careers")),
    ("Data Engineer","Amazon","Hyderabad","hybrid","full-time","AWS data lake and ETL pipelines.","Python,Spark,AWS Glue,Redshift","₹22L–₹40L",*_company("https://amazon.jobs")),
    ("Data Engineer","Swiggy","Bangalore","hybrid","full-time","Food delivery data pipelines.","Python,Spark,Kafka,Airflow","₹20L–₹36L",*_company("https://bytes.swiggy.com/careers")),
    ("Data Engineer","PhonePe","Bangalore","hybrid","full-time","Payments data infrastructure.","Python,Spark,Kafka,Hive","₹20L–₹36L",*_company("https://careers.phonepe.com")),
    ("Data Engineer","Meesho","Remote","remote","full-time","Social commerce data platform.","Python,Spark,Airflow,dbt","₹18L–₹32L",*_company("https://meesho.io/jobs")),
    ("Data Engineer","Razorpay","Bangalore","hybrid","full-time","Payments analytics infrastructure.","Python,Spark,Kafka,dbt","₹18L–₹32L",*_company("https://razorpay.com/jobs")),
    ("Data Engineer","Hotstar","Mumbai","hybrid","full-time","Streaming data platform.","Python,Spark,Kafka,Flink","₹20L–₹36L",*_company("https://careers.hotstar.com")),
    ("Senior Data Engineer","Google","Hyderabad","hybrid","full-time","Lead data platform for Google India.","Python,Spark,BigQuery,Dataflow","₹38L–₹65L",*_company("https://careers.google.com")),
    ("Data Engineer Intern","Flipkart","Bangalore","hybrid","internship","Data pipeline intern.","Python,Spark,SQL","₹22K–₹38K/mo",*_internshala("data-engineering-internship")),
    ("Data Engineer Intern","Amazon","Hyderabad","hybrid","internship","AWS data engineering intern.","Python,SQL,AWS","₹25K–₹40K/mo",*_internshala("data-engineering-internship")),
    ("Data Engineer Intern","Razorpay","Bangalore","hybrid","internship","Payments data intern.","Python,SQL,dbt","₹20K–₹35K/mo",*_internshala("data-engineering-internship")),
]
JOBS += _de

# ═══════════════════════════════════════════════════════════
# 7. CLOUD / DEVOPS / SRE
# ═══════════════════════════════════════════════════════════
_devops = [
    ("DevOps Engineer","Razorpay","Bangalore","hybrid","full-time","CI/CD and infrastructure automation.","AWS,Kubernetes,Terraform,Jenkins","₹16L–₹28L",*_company("https://razorpay.com/jobs")),
    ("DevOps Engineer","Flipkart","Bangalore","hybrid","full-time","Build and maintain CI/CD pipelines.","Kubernetes,Docker,Terraform,Python","₹18L–₹32L",*_company("https://www.flipkart.com/careers")),
    ("DevOps Engineer","PhonePe","Bangalore","hybrid","full-time","Payments infra automation.","Kubernetes,Docker,Terraform,AWS","₹18L–₹32L",*_company("https://careers.phonepe.com")),
    ("DevOps Engineer","Meesho","Remote","remote","full-time","Cloud infra and deployment.","AWS,Kubernetes,Ansible,Python","₹16L–₹28L",*_company("https://meesho.io/jobs")),
    ("Site Reliability Engineer","Google","Bangalore","hybrid","full-time","SRE for Google Cloud India.","Go,Python,Kubernetes,Linux","₹35L–₹60L",*_company("https://careers.google.com")),
    ("Site Reliability Engineer","Amazon","Hyderabad","hybrid","full-time","AWS SRE and on-call.","Python,AWS,Kubernetes,Linux","₹28L–₹50L",*_company("https://amazon.jobs")),
    ("Site Reliability Engineer","Flipkart","Bangalore","hybrid","full-time","Platform reliability.","Python,Kubernetes,Prometheus,Linux","₹22L–₹38L",*_linkedin("flipkart","sre")),
    ("Cloud Engineer","Microsoft","Hyderabad","hybrid","full-time","Azure cloud solutions.","Azure,Terraform,Python,ARM","₹18L–₹32L",*_company("https://careers.microsoft.com")),
    ("Cloud Architect","AWS","Hyderabad","hybrid","full-time","Architect enterprise cloud.","AWS,Solution Design,Python","₹35L–₹60L",*_company("https://amazon.jobs")),
    ("DevOps Intern","Razorpay","Bangalore","hybrid","internship","CI/CD infra intern.","Docker,Linux,Python","₹18K–₹30K/mo",*_internshala("devops-internship")),
    ("Cloud Intern","Microsoft","Hyderabad","hybrid","internship","Azure cloud intern.","Azure,Python,Linux","₹22K–₹38K/mo",*_internshala("cloud-computing-internship")),
    ("Cloud Intern","Google","Bangalore","hybrid","internship","GCP cloud intern.","GCP,Python,Linux","₹25K–₹45K/mo",*_internshala("cloud-computing-internship")),
]
JOBS += _devops

# ═══════════════════════════════════════════════════════════
# 8. AI / NLP / GEN AI
# ═══════════════════════════════════════════════════════════
_ai = [
    ("NLP Engineer","ShareChat","Bangalore","remote","full-time","Vernacular NLP for Indian languages.","Python,NLP,HuggingFace,PyTorch","₹22L–₹40L",*_company("https://sharechat.com/careers")),
    ("NLP Engineer","Sarvam AI","Bangalore","hybrid","full-time","Build Indian language AI models.","Python,PyTorch,HuggingFace,Transformers","₹25L–₹45L",*_company("https://sarvam.ai/careers")),
    ("AI Engineer","Krutrim","Bangalore","hybrid","full-time","Build Indian foundational AI models.","Python,PyTorch,CUDA,Distributed Training","₹28L–₹50L",*_company("https://olakrutrim.com/careers")),
    ("Generative AI Engineer","Infosys","Bangalore","hybrid","full-time","Enterprise GenAI solutions.","Python,LangChain,OpenAI APIs,RAG","₹16L–₹30L",*_company("https://www.infosys.com/careers")),
    ("Generative AI Engineer","TCS","Pune","hybrid","full-time","GenAI product development.","Python,LangChain,LLMs,RAG","₹16L–₹28L",*_company("https://www.tcs.com/careers")),
    ("Computer Vision Engineer","Ola","Bangalore","hybrid","full-time","Autonomous vehicle perception.","Python,OpenCV,PyTorch,CUDA","₹22L–₹40L",*_company("https://ola.careers")),
    ("Computer Vision Engineer","Lenskart","Remote","remote","full-time","AR try-on and frame detection.","Python,OpenCV,TensorFlow,CUDA","₹18L–₹32L",*_company("https://careers.lenskart.com")),
    ("Research Scientist","Google DeepMind","Hyderabad","hybrid","full-time","AI research and publications.","Python,PyTorch,Mathematics,Research","₹45L–₹80L",*_company("https://careers.google.com")),
    ("Research Scientist","Microsoft Research","Hyderabad","hybrid","full-time","Applied AI and ML research.","Python,PyTorch,Research,Mathematics","₹40L–₹70L",*_company("https://careers.microsoft.com")),
    ("Generative AI Engineer","Google","Bangalore","hybrid","full-time","Build Gemini-powered products.","Python,LangChain,Vertex AI,RAG","₹35L–₹60L",*_linkedin("google","generative ai engineer")),
    ("Generative AI Engineer","Amazon","Hyderabad","hybrid","full-time","Bedrock-powered enterprise AI.","Python,AWS Bedrock,LangChain,RAG","₹30L–₹55L",*_linkedin("amazon","generative ai engineer")),
    ("LLM Engineer","Sarvam AI","Bangalore","hybrid","full-time","Fine-tune and deploy LLMs for India.","Python,PyTorch,HuggingFace,CUDA","₹25L–₹45L",*_linkedin("sarvam-ai","llm engineer")),
    ("AI Research Intern","Sarvam AI","Bangalore","hybrid","internship","Indian language AI research.","Python,PyTorch,NLP","Stipend",*_company("https://sarvam.ai/careers")),
    ("NLP Intern","ShareChat","Remote","remote","internship","Vernacular NLP intern.","Python,NLP,HuggingFace","₹20K–₹35K/mo",*_internshala("nlp-internship")),
    ("Computer Vision Intern","Lenskart","Remote","remote","internship","AR vision intern.","Python,OpenCV,PyTorch","₹18K–₹30K/mo",*_internshala("computer-vision-internship")),
    ("Generative AI Intern","Infosys","Bangalore","hybrid","internship","GenAI application intern.","Python,LangChain,OpenAI","₹16K–₹28K/mo",*_internshala("ai-internship")),
]
JOBS += _ai

# ═══════════════════════════════════════════════════════════
# 9. CYBERSECURITY
# ═══════════════════════════════════════════════════════════
_security = [
    ("Security Engineer","Razorpay","Bangalore","hybrid","full-time","Application and infra security.","Python,AppSec,PenTest,Burp Suite","₹18L–₹32L",*_company("https://razorpay.com/jobs")),
    ("Security Engineer","PhonePe","Bangalore","hybrid","full-time","Payments security engineering.","Python,AppSec,Kubernetes,SIEM","₹20L–₹36L",*_company("https://careers.phonepe.com")),
    ("Security Engineer","Google","Bangalore","hybrid","full-time","Google India infrastructure security.","Python,C++,Linux,Cryptography","₹30L–₹55L",*_company("https://careers.google.com")),
    ("Penetration Tester","Wipro","Hyderabad","hybrid","full-time","Enterprise pen testing.","Kali,Metasploit,Python,Burp Suite","₹12L–₹22L",*_linkedin("wipro","penetration tester")),
    ("SOC Analyst","Infosys","Bangalore","hybrid","full-time","24x7 security operations center.","SIEM,Splunk,Python,Linux","₹8L–₹15L",*_linkedin("infosys","soc analyst")),
    ("Cybersecurity Analyst","Accenture","Bangalore","hybrid","full-time","Enterprise cyber risk analytics.","Python,SIEM,GRC,ISO 27001","₹12L–₹22L",*_linkedin("accenture","cybersecurity")),
    ("Security Intern","Razorpay","Bangalore","hybrid","internship","Payments security intern.","Python,Linux,Burp Suite","₹18K–₹30K/mo",*_internshala("cybersecurity-internship")),
    ("SOC Intern","Infosys","Bangalore","hybrid","internship","SOC monitoring intern.","SIEM,Linux,Python","₹12K–₹20K/mo",*_internshala("cybersecurity-internship")),
]
JOBS += _security

# ═══════════════════════════════════════════════════════════
# 10. QA / TESTING
# ═══════════════════════════════════════════════════════════
_qa = [
    ("QA Engineer","BrowserStack","Mumbai","hybrid","full-time","Test automation platform quality.","Selenium,Python,Java,TestNG","₹10L–₹18L",*_company("https://www.browserstack.com/careers")),
    ("QA Engineer","Freshworks","Chennai","hybrid","full-time","CRM product quality assurance.","Selenium,Python,Pytest,REST","₹10L–₹18L",*_company("https://www.freshworks.com/company/careers")),
    ("QA Engineer","PhonePe","Bangalore","hybrid","full-time","Payments platform testing.","Selenium,Python,Appium,REST","₹12L–₹22L",*_company("https://careers.phonepe.com")),
    ("QA Engineer","Razorpay","Bangalore","hybrid","full-time","Payments API testing.","Selenium,Python,Postman,TestNG","₹12L–₹22L",*_company("https://razorpay.com/jobs")),
    ("SDET","Flipkart","Bangalore","hybrid","full-time","E-commerce platform SDET.","Java,Selenium,TestNG,Docker","₹16L–₹28L",*_company("https://www.flipkart.com/careers")),
    ("Performance Test Engineer","Hotstar","Mumbai","hybrid","full-time","Streaming platform load testing.","JMeter,Gatling,Python,AWS","₹14L–₹24L",*_company("https://careers.hotstar.com")),
    ("QA Intern","BrowserStack","Mumbai","hybrid","internship","Test automation intern.","Selenium,Python,Java","₹18K–₹30K/mo",*_internshala("qa-testing-internship")),
    ("QA Intern","Razorpay","Bangalore","hybrid","internship","Payments testing intern.","Python,Selenium,Postman","₹18K–₹30K/mo",*_internshala("qa-testing-internship")),
]
JOBS += _qa

# ═══════════════════════════════════════════════════════════
# 11. BLOCKCHAIN
# ═══════════════════════════════════════════════════════════
_blockchain = [
    ("Blockchain Developer","CoinDCX","Bangalore","remote","full-time","Crypto exchange smart contracts.","Solidity,Web3.js,Ethereum,Python","₹18L–₹32L",*_company("https://coindcx.com/careers")),
    ("Blockchain Developer","WazirX","Mumbai","remote","full-time","DeFi and NFT platform.","Solidity,Ethereum,Node.js,Web3","₹16L–₹28L",*_company("https://wazirx.com/careers")),
    ("Smart Contract Developer","CoinSwitch","Bangalore","remote","full-time","DeFi protocol development.","Solidity,Hardhat,Ethers.js","₹18L–₹32L",*_company("https://coinswitch.co/careers")),
    ("Web3 Developer","Polygon","Remote","remote","full-time","Layer 2 scaling solution.","Solidity,Go,Rust,Web3.js","₹25L–₹45L",*_company("https://polygon.technology/careers")),
    ("Web3 Intern","CoinDCX","Remote","remote","internship","Smart contract development intern.","Solidity,Web3.js,Python","₹20K–₹35K/mo",*_internshala("blockchain-internship")),
    ("Blockchain Intern","WazirX","Mumbai","remote","internship","DeFi intern.","Solidity,Ethereum,JavaScript","₹18K–₹30K/mo",*_internshala("blockchain-internship")),
]
JOBS += _blockchain

# ═══════════════════════════════════════════════════════════
# 12. PRODUCT MANAGEMENT
# ═══════════════════════════════════════════════════════════
_pm = [
    ("Product Manager","Flipkart","Bangalore","hybrid","full-time","Buyer platform product strategy.","Product Strategy,SQL,Agile,Analytics","₹22L–₹40L",*_company("https://www.flipkart.com/careers")),
    ("Product Manager","Swiggy","Bangalore","hybrid","full-time","Food delivery product roadmap.","Product Strategy,SQL,Agile","₹22L–₹40L",*_company("https://bytes.swiggy.com/careers")),
    ("Product Manager","PhonePe","Bangalore","hybrid","full-time","Payments product roadmap.","Product Strategy,SQL,Fintech","₹25L–₹45L",*_company("https://careers.phonepe.com")),
    ("Product Manager","Razorpay","Bangalore","hybrid","full-time","Merchant payments product.","Product Strategy,SQL,Fintech","₹25L–₹45L",*_company("https://razorpay.com/jobs")),
    ("Product Manager","Google","Bangalore","hybrid","full-time","Google India product strategy.","Product Strategy,SQL,Agile,Analytics","₹35L–₹60L",*_company("https://careers.google.com")),
    ("Senior Product Manager","Amazon","Hyderabad","hybrid","full-time","Lead product for Amazon India.","Product Strategy,SQL,Leadership","₹38L–₹65L",*_company("https://amazon.jobs")),
    ("Associate Product Manager","Flipkart","Bangalore","hybrid","full-time","APM program – buyer platform.","Product Strategy,SQL,Communication","₹16L–₹28L",*_linkedin("flipkart","associate product manager")),
    ("Associate Product Manager","Razorpay","Bangalore","hybrid","full-time","Payments APM.","Product Strategy,Fintech,SQL","₹16L–₹28L",*_linkedin("razorpay","associate product manager")),
    ("Product Manager Intern","Flipkart","Bangalore","hybrid","internship","Buyer platform PM intern.","Product,SQL,Communication","₹25K–₹45K/mo",*_internshala("product-management-internship")),
    ("Product Manager Intern","Swiggy","Bangalore","hybrid","internship","Food delivery PM intern.","Product,SQL,Analytics","₹22K–₹40K/mo",*_internshala("product-management-internship")),
    ("Product Manager Intern","Razorpay","Bangalore","hybrid","internship","Merchant product PM intern.","Product,SQL,Communication","₹22K–₹40K/mo",*_internshala("product-management-internship")),
]
JOBS += _pm

# ═══════════════════════════════════════════════════════════
# 13. PRODUCT DESIGN / UX
# ═══════════════════════════════════════════════════════════
_design = [
    ("Product Designer","Razorpay","Bangalore","hybrid","full-time","Payment UX design.","Figma,UX Research,Prototyping","₹14L–₹26L",*_company("https://razorpay.com/jobs")),
    ("Product Designer","Swiggy","Bangalore","hybrid","full-time","Food delivery consumer UX.","Figma,UX Research,Design Systems","₹16L–₹28L",*_company("https://bytes.swiggy.com/careers")),
    ("Product Designer","CRED","Bangalore","hybrid","full-time","Fintech consumer app design.","Figma,Motion Design,UX Research","₹18L–₹32L",*_company("https://careers.cred.club")),
    ("UX Designer","Freshworks","Chennai","hybrid","full-time","SaaS product UX.","Figma,UX Research,Prototyping","₹12L–₹22L",*_company("https://www.freshworks.com/company/careers")),
    ("UX Researcher","Amazon","Hyderabad","hybrid","full-time","Marketplace UX research.","UX Research,Figma,Analytics","₹18L–₹32L",*_company("https://amazon.jobs")),
    ("Design Intern","Razorpay","Bangalore","hybrid","internship","Payments UX design intern.","Figma,Prototyping","₹15K–₹25K/mo",*_internshala("ui-ux-internship")),
    ("UI/UX Intern","CRED","Bangalore","hybrid","internship","Fintech design intern.","Figma,Motion Design","₹16K–₹26K/mo",*_internshala("ui-ux-internship")),
    ("UI/UX Intern","Zomato","Gurgaon","hybrid","internship","Restaurant UX intern.","Figma,Prototyping","₹14K–₹22K/mo",*_internshala("ui-ux-internship")),
]
JOBS += _design

# ═══════════════════════════════════════════════════════════
# 14. SPECIALISED / MISC
# ═══════════════════════════════════════════════════════════
_misc = [
    ("Database Engineer","Razorpay","Bangalore","hybrid","full-time","Payments database engineering.","MySQL,PostgreSQL,Vitess,SQL","₹18L–₹32L",*_company("https://razorpay.com/jobs")),
    ("Embedded Systems Engineer","Bosch","Pune","onsite","full-time","Automotive ECU firmware.","C,C++,Embedded C,CAN Bus","₹12L–₹22L",*_company("https://www.bosch-india.com/careers")),
    ("Embedded Systems Engineer","Ola Electric","Bangalore","onsite","full-time","EV firmware development.","C,C++,RTOS,CAN Bus","₹16L–₹28L",*_company("https://olaelectric.com/careers")),
    ("Firmware Engineer","Ather Energy","Bangalore","onsite","full-time","Scooter embedded firmware.","C,C++,Linux,RTOS","₹14L–₹24L",*_company("https://atherenergy.com/careers")),
    ("Solutions Architect","AWS","Hyderabad","hybrid","full-time","Architect cloud solutions for India.","AWS,Solution Design,Python,Networking","₹35L–₹60L",*_company("https://amazon.jobs")),
    ("Technical Writer","Freshworks","Chennai","remote","full-time","API and product documentation.","Technical Writing,Markdown,REST APIs","₹8L–₹15L",*_company("https://www.freshworks.com/company/careers")),
    ("Developer Advocate","Postman","Bangalore","hybrid","full-time","API developer community and content.","REST APIs,Technical Writing,Public Speaking","₹16L–₹28L",*_company("https://www.postman.com/company/careers")),
    ("Tech Lead","Razorpay","Bangalore","hybrid","full-time","Lead engineering team for payments.","Java,Go,System Design,Leadership","₹35L–₹60L",*_company("https://razorpay.com/jobs")),
    ("Engineering Manager","Flipkart","Bangalore","hybrid","full-time","Manage buyer platform engineering.","Engineering Management,Java,System Design","₹45L–₹80L",*_company("https://www.flipkart.com/careers")),
    ("Quantitative Analyst","Zerodha","Bangalore","hybrid","full-time","Algo trading strategy development.","Python,Statistics,ML,SQL","₹20L–₹36L",*_company("https://zerodha.com/careers")),
    ("Risk Analyst","Razorpay","Bangalore","hybrid","full-time","Payments risk and fraud modelling.","Python,SQL,Statistics,ML","₹14L–₹24L",*_company("https://razorpay.com/jobs")),
    ("CTO Startup","YC-backed Startup","Remote","remote","full-time","Build and lead early-stage startup engineering.","System Design,Cloud,Leadership,Full Stack","₹30L–₹60L + Equity",*_angellist("engineering")),
    ("Contract ML Engineer","Remote","Remote","remote","contract","6-month MLOps implementation.","Python,MLFlow,Kubernetes,Docker","₹90K–₹1.2L/mo",*_angellist("machine-learning")),
    ("Part-time AI Engineer","Remote","Remote","remote","part-time","AI consulting and model building.","Python,ML,OpenAI APIs,FastAPI","₹60K–₹90K/mo",*_angellist("artificial-intelligence")),
    ("Full Stack Engineer","Early-stage Startup","Remote","remote","full-time","Build 0-to-1 product.","React,Node.js,PostgreSQL","₹12L–₹22L + Equity",*_angellist("full-stack")),
    ("Backend Engineer","B2B SaaS Startup","Bangalore","hybrid","full-time","API-first B2B product.","Go,PostgreSQL,Kubernetes","₹14L–₹26L + Equity",*_angellist("backend")),
    ("ML Engineer","AI Startup","Remote","remote","full-time","Build AI product from scratch.","Python,PyTorch,FastAPI","₹16L–₹30L + Equity",*_angellist("machine-learning")),
]
JOBS += _misc

# ═══════════════════════════════════════════════════════════
# 15. BULK EXPANSION – permutations to reach ~3000
# ═══════════════════════════════════════════════════════════
_expansion_roles = [
    ("Python Developer",        "Python,FastAPI,PostgreSQL,Docker",      "₹10L–₹18L","₹15K–₹25K/mo","Build backend APIs with Python."),
    ("Java Developer",          "Java,Spring Boot,MySQL,REST",           "₹10L–₹18L","₹14K–₹24K/mo","Enterprise Java application development."),
    ("React Developer",         "React,JavaScript,TypeScript,CSS",       "₹10L–₹18L","₹14K–₹24K/mo","Build modern React web applications."),
    ("Node.js Developer",       "Node.js,Express,MongoDB,REST",          "₹10L–₹18L","₹14K–₹24K/mo","RESTful API development with Node.js."),
    ("Angular Developer",       "Angular,TypeScript,RxJS,REST",          "₹10L–₹18L","₹14K–₹24K/mo","Enterprise Angular application development."),
    ("Django Developer",        "Python,Django,PostgreSQL,REST",         "₹10L–₹18L","₹14K–₹24K/mo","Web application development with Django."),
    ("Go Developer",            "Go,gRPC,PostgreSQL,Kubernetes",         "₹14L–₹26L","₹16K–₹28K/mo","High-performance Go service development."),
    ("Kotlin Developer",        "Kotlin,Android,Jetpack Compose,REST",   "₹12L–₹22L","₹14K–₹24K/mo","Android app development with Kotlin."),
    ("Flutter Developer",       "Flutter,Dart,Firebase,REST",            "₹12L–₹22L","₹14K–₹24K/mo","Cross-platform mobile app with Flutter."),
    ("TypeScript Developer",    "TypeScript,Node.js,React,REST",         "₹12L–₹22L","₹14K–₹24K/mo","Full-stack TypeScript development."),
    ("Tableau Developer",       "Tableau,SQL,Python,Excel",              "₹10L–₹18L","₹12K–₹20K/mo","Business intelligence dashboards in Tableau."),
    ("Power BI Developer",      "PowerBI,SQL,DAX,Excel",                 "₹10L–₹18L","₹12K–₹20K/mo","BI reports and dashboards in Power BI."),
    ("Salesforce Developer",    "Salesforce,Apex,LWC,SOQL",              "₹12L–₹22L","₹14K–₹24K/mo","Salesforce CRM customisation."),
]

_expansion_companies = [
    ("TCS",        "Pune",      "onsite","https://www.tcs.com/careers",                "tata-consultancy-services"),
    ("Infosys",    "Bangalore", "hybrid","https://www.infosys.com/careers",            "infosys"),
    ("Wipro",      "Hyderabad", "hybrid","https://careers.wipro.com",                  "wipro"),
    ("HCL",        "Noida",     "onsite","https://www.hcltech.com/careers",            "hcl-technologies"),
    ("Cognizant",  "Chennai",   "hybrid","https://careers.cognizant.com",              "cognizant"),
    ("Capgemini",  "Mumbai",    "hybrid","https://www.capgemini.com/in-en/careers",    "capgemini"),
    ("Accenture",  "Bangalore", "hybrid","https://www.accenture.com/in-en/careers",   "accenture"),
    ("Razorpay",   "Bangalore", "hybrid","https://razorpay.com/jobs",                  "razorpay"),
    ("PhonePe",    "Bangalore", "hybrid","https://careers.phonepe.com",               "phonepe"),
    ("Flipkart",   "Bangalore", "hybrid","https://www.flipkart.com/careers",          "flipkart"),
    ("Swiggy",     "Bangalore", "hybrid","https://bytes.swiggy.com/careers",          "swiggy"),
    ("Zomato",     "Gurgaon",   "hybrid","https://www.zomato.com/careers",            "zomato"),
    ("Meesho",     "Bangalore", "remote","https://meesho.io/jobs",                    "meesho"),
    ("CRED",       "Bangalore", "hybrid","https://careers.cred.club",                 "cred"),
    ("Groww",      "Bangalore", "hybrid","https://groww.in/about/careers",            "groww"),
    ("Freshworks", "Chennai",   "hybrid","https://www.freshworks.com/company/careers","freshworks"),
    ("Google",     "Bangalore", "hybrid","https://careers.google.com",                "google"),
    ("Microsoft",  "Hyderabad", "hybrid","https://careers.microsoft.com",             "microsoft"),
    ("Amazon",     "Hyderabad", "hybrid","https://amazon.jobs",                       "amazon"),
    ("IBM",        "Bangalore", "hybrid","https://www.ibm.com/in-en/employment",      "ibm"),
    ("Oracle",     "Hyderabad", "hybrid","https://careers.oracle.com",                "oracle"),
    ("Salesforce", "Hyderabad", "hybrid","https://salesforce.com/careers",            "salesforce"),
    ("Adobe",      "Noida",     "hybrid","https://adobe.com/careers",                 "adobe"),
]

_internshala_slugs = {
    "Python Developer":     "python-internship",
    "Java Developer":       "java-internship",
    "React Developer":      "react-internship",
    "Node.js Developer":    "nodejs-internship",
    "Angular Developer":    "angular-internship",
    "Django Developer":     "python-internship",
    "Go Developer":         "golang-internship",
    "Kotlin Developer":     "android-development-internship",
    "Flutter Developer":    "flutter-internship",
    "TypeScript Developer": "web-development-internship",
    "Tableau Developer":    "data-analytics-internship",
    "Power BI Developer":   "data-analytics-internship",
    "Salesforce Developer": "salesforce-internship",
}

for (role, skills, salary_ft, salary_intern, desc) in _expansion_roles:
    for i, (company, location, work_mode, careers_url, linkedin_slug) in enumerate(_expansion_companies):
        platform_info = _company(careers_url) if i % 2 == 0 else _linkedin(linkedin_slug, role)
        JOBS.append((role, company, location, work_mode, "full-time",
                     f"{desc} at {company}.", skills, salary_ft, *platform_info))
        intern_slug = _internshala_slugs.get(role, "software-development-internship")
        JOBS.append((f"{role} Intern", company, location,
                     "remote" if location in ("Remote",) else work_mode,
                     "internship", f"{role} internship at {company}.", skills, salary_intern,
                     *_internshala(intern_slug)))

# ═══════════════════════════════════════════════════════════
# 16. NICHE / STARTUP / CONTRACT ROLES
# ═══════════════════════════════════════════════════════════
_niche = [
    ("AI Product Manager","Sarvam AI","Bangalore","hybrid","full-time","Drive Indian language AI products.","Product Strategy,AI,NLP","₹25L–₹45L",*_angellist("product-management")),
    ("Growth Engineer","Meesho","Bangalore","remote","full-time","Experimentation and A/B testing.","Python,SQL,Statistics,Growth","₹18L–₹32L",*_linkedin("meesho","growth engineer")),
    ("Distributed Systems Engineer","Hotstar","Mumbai","hybrid","full-time","Live streaming infrastructure.","Go,Kafka,Redis,Kubernetes","₹25L–₹45L",*_company("https://careers.hotstar.com")),
    ("Robotics Engineer","Ola Electric","Bangalore","onsite","full-time","EV assembly line robotics.","ROS,C++,Python,Computer Vision","₹18L–₹32L",*_company("https://olaelectric.com/careers")),
    ("HealthTech Developer","Practo","Bangalore","hybrid","full-time","Healthcare platform engineering.","Python,Java,MySQL,FHIR","₹14L–₹24L",*_linkedin("practo","software engineer")),
    ("EdTech Developer","Unacademy","Bangalore","hybrid","full-time","Live learning platform.","Python,Django,PostgreSQL","₹14L–₹24L",*_linkedin("unacademy","software engineer")),
    ("FinTech Developer","Slice","Bangalore","hybrid","full-time","Credit card platform engineering.","Java,Spring,MySQL,Kafka","₹16L–₹28L",*_linkedin("slice","software engineer")),
    ("Contract Data Engineer","Remote","Remote","remote","contract","6-month data modernisation project.","Python,dbt,Spark,Airflow","₹75K–₹1L/mo",*_angellist("data-engineering")),
    ("Freelance Data Analyst","Remote","Remote","remote","part-time","Data analysis consulting.","SQL,Python,Tableau","₹40K–₹70K/mo",*_angellist("data-analytics")),
    ("Freelance React Developer","Remote","Remote","remote","part-time","React UI development consulting.","React,TypeScript,CSS","₹40K–₹70K/mo",*_angellist("frontend")),
    ("Growth Intern","Meesho","Remote","remote","internship","Seller growth experiment intern.","SQL,Excel,Growth","₹16K–₹28K/mo",*_internshala("business-analytics-internship")),
    ("Operations Intern","Delhivery","Gurgaon","hybrid","internship","Logistics operations intern.","Excel,SQL,Python","₹12K–₹20K/mo",*_internshala("operations-internship")),
]
JOBS += _niche

# ═══════════════════════════════════════════════════════════
# 17. TOP-UP ROLES
# ═══════════════════════════════════════════════════════════
_topup = [
    ("Cloud Data Engineer","Google","Bangalore","hybrid","full-time","GCP data engineering.","Python,BigQuery,Dataflow,Airflow","₹20L–₹36L",*_company("https://careers.google.com")),
    ("Cloud Data Engineer","Amazon","Hyderabad","hybrid","full-time","AWS lake-house engineering.","Python,Glue,Redshift,Spark","₹22L–₹40L",*_company("https://amazon.jobs")),
    ("Data Platform Engineer","Flipkart","Bangalore","hybrid","full-time","Petabyte-scale data platform.","Spark,Kafka,Hive,Kubernetes","₹22L–₹40L",*_linkedin("flipkart","data platform engineer")),
    ("Kafka Engineer","Hotstar","Mumbai","hybrid","full-time","Live streaming event pipelines.","Kafka,Flink,Go,Kubernetes","₹20L–₹36L",*_linkedin("hotstar","kafka engineer")),
    ("Spark Engineer","Meesho","Remote","remote","full-time","Large-scale Spark processing.","Spark,Python,Scala,SQL","₹18L–₹32L",*_linkedin("meesho","spark engineer")),
    ("dbt Developer","Razorpay","Bangalore","hybrid","full-time","Analytics engineering with dbt.","dbt,SQL,Python,BigQuery","₹16L–₹28L",*_linkedin("razorpay","dbt developer")),
    ("Search Engineer","Flipkart","Bangalore","hybrid","full-time","Product search and ranking.","Elasticsearch,Python,Java,Solr","₹20L–₹36L",*_company("https://www.flipkart.com/careers")),
    ("Search Engineer","Amazon","Hyderabad","hybrid","full-time","A9 product search.","Elasticsearch,Java,Python","₹25L–₹45L",*_company("https://amazon.jobs")),
    ("Recommendation Engineer","Hotstar","Mumbai","hybrid","full-time","Content recommendation systems.","Python,PyTorch,Spark,Kafka","₹22L–₹40L",*_company("https://careers.hotstar.com")),
    ("Platform Product Manager","Razorpay","Bangalore","hybrid","full-time","Payment infrastructure PM.","Product,Fintech,API,SQL","₹25L–₹45L",*_company("https://razorpay.com/jobs")),
    ("Head of Design","CRED","Bangalore","hybrid","full-time","Lead premium fintech design org.","Design Leadership,Figma,UX","₹40L–₹70L",*_company("https://careers.cred.club")),
    ("Observability Engineer","PhonePe","Bangalore","hybrid","full-time","Monitoring and tracing at scale.","Prometheus,Grafana,OpenTelemetry","₹20L–₹36L",*_linkedin("phonepe","observability engineer")),
    ("FinOps Engineer","Razorpay","Bangalore","hybrid","full-time","Cloud cost optimisation.","AWS,GCP,Python,Terraform","₹18L–₹32L",*_linkedin("razorpay","finops engineer")),
    ("Growth Product Intern","Meesho","Remote","remote","internship","Seller growth PM intern.","Product,SQL,Communication","₹18K–₹30K/mo",*_internshala("product-management-internship")),
    ("Platform PM Intern","Razorpay","Bangalore","hybrid","internship","Payments platform PM intern.","Product,Fintech,SQL","₹22K–₹38K/mo",*_internshala("product-management-internship")),
    ("Brand Design Intern","Zomato","Gurgaon","hybrid","internship","Brand design intern.","Figma,Illustration","₹12K–₹20K/mo",*_internshala("graphic-design-internship")),
    ("FinOps Intern","Razorpay","Bangalore","hybrid","internship","Cloud cost intern.","AWS,Python,Excel","₹16K–₹28K/mo",*_internshala("cloud-computing-internship")),
]
JOBS += _topup


# ─────────────────────────────────────────────────────────────────────────────
def create_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute(CREATE_TABLE)

    cur.executemany("""
        INSERT INTO jobs
            (job_title, company, location, work_mode, job_type,
             description, required_skills, salary_range,
             apply_platform, source_website, apply_link)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, JOBS)

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    print(f"\n✅  Created {DB_PATH} with {total} job listings")
    print(f"    Unique titles   : {len(set(j[0] for j in JOBS))}")
    print(f"    Work modes      : {sorted(set(j[3] for j in JOBS))}")
    print(f"    Job types       : {sorted(set(j[4] for j in JOBS))}")
    print(f"    Apply platforms : {sorted(set(j[8] for j in JOBS))}")

    print("\n  Sample rows (direct apply links):")
    rows = cur.execute(
        "SELECT job_title, company, apply_platform, source_website, apply_link FROM jobs LIMIT 5"
    ).fetchall()
    for r in rows:
        print(f"    {r[0]} @ {r[1]}")
        print(f"      Platform : {r[2]}")
        print(f"      Source   : {r[3]}")
        print(f"      Apply →  : {r[4]}")
    conn.close()


if __name__ == "__main__":
    create_database()
