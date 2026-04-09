# SkillMatch: AI-Powered Job Recommender

SkillMatch is a full-stack web application designed to connect job seekers with open roles using Machine Learning. It predicts the best-fit job role based on a user's skills and fetches live listings (or searches the local database) that match the prediction.

For recruiters, it provides a dashboard to post new jobs and view incoming applications.

## Features

- **Job Seeker Dashboard**:
  - Enter your skills to get an AI-predicted job role.
  - Search and filter jobs by Location, Work Mode, and Job Type.
  - Quick Apply for jobs posted directly by recruiters.
  - Application History tracking.
- **Recruiter Dashboard**:
  - Securely post new job openings.
  - Manage existing job listings.
  - Review applicant details, cover letters, and resumes.
  - Update application statuses (Shortlisted, Rejected, etc.).

## Prerequisites

Before running the application, make sure you have:
- **Python 3.8+** installed
- **pip** (Python package installer)

## Installation

1. **Clone the repository** (or download and extract the files).
2. **Navigate** to the project directory:
   ```bash
   cd job_recommend
   ```
3. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## GitHub & Render

See **[DEPLOY.md](./DEPLOY.md)** to push the repo and deploy with **`render.yaml`** (Docker). With `uvicorn` or Docker, open **`/`** for the web UI (same host as the API).

## Setup (Optional but recommended)

If you haven't yet, you might need to seed the initial jobs database. You can do this by running:
```bash
python new_create_db.py
```
This will generate the `jobs.db` database and populate it with sample open positions.

## Running the Application

This project consists of two servers: a **FastAPI backend** and a **Streamlit frontend**. You can start them both simultaneously using the provided runner script.

**To run the entire app:**
```bash
python run.py
```

This will automatically open your web browser to `http://localhost:8501`.

### Running Manually
If you prefer not to use `run.py`, you can run the backend and frontend in two separate terminal windows:

**Terminal 1: Start the Backend (FastAPI)**
```bash
uvicorn main12:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2: Start the Frontend (Streamlit)**
```bash
streamlit run app.py
```

## Email functionality (Developer Mode)
If you do not configure an `SMTP_USER` and `SMTP_PASS` in your environment, the app runs in **Developer Mode**. During the Job Application process, the application will print "emails" directly to Terminal 1 (your FastAPI console) instead of actually sending them across the internet.
