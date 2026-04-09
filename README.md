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

- Python 3.8+
- pip

## Installation

cd job_recommend  
pip install -r requirements.txt  

## GitHub & Render

See DEPLOY.md for deployment steps.

## Setup

python new_create_db.py  

## Run

python run.py  

OR manually:

Backend:
uvicorn main12:app --host 127.0.0.1 --port 8000 --reload  

Frontend:
streamlit run app.py  