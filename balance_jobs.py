"""
Balance synthetic job counts per tech category in jobs.db.
Run: python balance_jobs.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import date

DB_PATH = "jobs.db"
TARGET_PER_CATEGORY = 30

# (category_name, SQL WHERE clause fragment using job_title OR required_skills)
CATEGORIES: list[tuple[str, str]] = [
    ("Solana", "(LOWER(job_title) LIKE '%solana%' OR LOWER(required_skills) LIKE '%solana%')"),
    ("Blockchain", "(LOWER(job_title) LIKE '%blockchain%' OR LOWER(job_title) LIKE '%web3%' OR LOWER(required_skills) LIKE '%web3%' OR LOWER(required_skills) LIKE '%solidity%')"),
    ("Cloud", "(LOWER(job_title) LIKE '%cloud%' OR LOWER(job_title) LIKE '%aws%' OR LOWER(job_title) LIKE '%azure%' OR LOWER(job_title) LIKE '%gcp%')"),
    ("DevOps", "(LOWER(job_title) LIKE '%devops%' OR LOWER(job_title) LIKE '%sre%' OR LOWER(job_title) LIKE '%site reliability%')"),
    ("Data", "(LOWER(job_title) LIKE '%data%' OR LOWER(job_title) LIKE '%analytics%' OR LOWER(job_title) LIKE '%etl%')"),
    ("AI", "(LOWER(job_title) LIKE '%ai engineer%' OR LOWER(job_title) LIKE '%machine learning%' OR LOWER(job_title) LIKE '%mlops%' OR LOWER(job_title) LIKE '%llm%' OR LOWER(job_title) LIKE '%nlp%')"),
    ("Security", "(LOWER(job_title) LIKE '%security%' OR LOWER(job_title) LIKE '%soc %' OR LOWER(job_title) LIKE '%penetration%')"),
    ("Frontend", "(LOWER(job_title) LIKE '%frontend%' OR LOWER(job_title) LIKE '%react%' OR LOWER(job_title) LIKE '%angular%')"),
    ("Backend", "(LOWER(job_title) LIKE '%backend%' OR LOWER(job_title) LIKE '%full stack%')"),
    ("Mobile", "(LOWER(job_title) LIKE '%mobile%' OR LOWER(job_title) LIKE '%android%' OR LOWER(job_title) LIKE '%ios%' OR LOWER(job_title) LIKE '%flutter%')"),
]

TEMPLATES: dict[str, tuple[str, str, str]] = {
    "Solana": ("Solana Program Engineer (Balanced)", "rust,solana,anchor,git", "Build high-performance on-chain programs."),
    "Blockchain": ("Blockchain Protocol Engineer (Balanced)", "solidity,ethereum,web3,smart contracts", "Ship secure protocol upgrades."),
    "Cloud": ("Cloud Platform Engineer (Balanced)", "aws,terraform,kubernetes,docker,linux", "Operate multi-account cloud platforms."),
    "DevOps": ("DevOps Automation Engineer (Balanced)", "ci/cd,docker,kubernetes,terraform,linux", "Automate delivery and observability."),
    "Data": ("Data Pipeline Engineer (Balanced)", "python,spark,airflow,sql,snowflake", "Build reliable data pipelines."),
    "AI": ("Applied AI Engineer (Balanced)", "python,pytorch,llm,rag,mlops", "Ship AI features to production."),
    "Security": ("Security Operations Engineer (Balanced)", "siem,incident response,threat hunting,python", "Protect production systems."),
    "Frontend": ("Senior Frontend Engineer (Balanced)", "react,typescript,css,testing,api", "Build accessible web UIs."),
    "Backend": ("Senior Backend Engineer (Balanced)", "python,fastapi,postgresql,redis,docker", "Design scalable APIs."),
    "Mobile": ("Mobile Engineer (Balanced)", "flutter,kotlin,swift,rest api", "Ship cross-platform mobile apps."),
}

LOCATIONS = ["Bangalore", "Hyderabad", "Mumbai", "Pune", "Gurgaon", "Noida", "Chennai", "Remote"]
MODES = ["remote", "hybrid", "onsite"]
TYPES = ["full-time", "contract"]


def count_category(cur: sqlite3.Cursor, where_sql: str) -> int:
    row = cur.execute(f"SELECT COUNT(*) FROM jobs WHERE {where_sql}").fetchone()
    return int(row[0]) if row else 0


def run_balance(dry_run: bool = False) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    today = str(date.today())
    inserted = 0
    plan: list[tuple[str, int, int]] = []

    for cat, where_sql in CATEGORIES:
        current = count_category(cur, where_sql)
        need = max(0, TARGET_PER_CATEGORY - current)
        plan.append((cat, current, need))

    if dry_run:
        for cat, current, need in plan:
            print(f"{cat}: {current} -> target {TARGET_PER_CATEGORY} (would add {need})")
        conn.close()
        return

    seq = 0
    for cat, where_sql in CATEGORIES:
        current = count_category(cur, where_sql)
        need = max(0, TARGET_PER_CATEGORY - current)
        title_base, skills, desc_base = TEMPLATES[cat]

        for _ in range(need):
            seq += 1
            title = f"{title_base} #{seq}"
            company = f"BalanceTech-{cat.replace(' ', '')}-{seq % 50}"
            loc = LOCATIONS[seq % len(LOCATIONS)]
            mode = MODES[seq % len(MODES)]
            jtype = TYPES[seq % len(TYPES)]
            salary = f"₹{10 + (seq % 12)}L–₹{18 + (seq % 15)}L"
            apply_link = f"https://careers.balancetech.dev/{cat.lower()}-{seq}"
            cur.execute(
                """INSERT INTO jobs (
                    job_title, company, location, work_mode, job_type, description,
                    required_skills, salary_range, apply_platform, source_website, apply_link, posted_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    title,
                    company,
                    loc,
                    mode,
                    jtype,
                    desc_base,
                    skills,
                    salary,
                    "Company Website",
                    "https://careers.balancetech.dev",
                    apply_link,
                    today,
                ),
            )
            inserted += 1

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()

    print(f"Inserted {inserted} balanced jobs. Total rows: {total}")
    for cat, where_sql in CATEGORIES:
        c = sqlite3.connect(DB_PATH)
        n = c.execute(f"SELECT COUNT(*) FROM jobs WHERE {where_sql}").fetchone()[0]
        c.close()
        print(f"  {cat}: {n}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print plan only")
    args = parser.parse_args()
    run_balance(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
