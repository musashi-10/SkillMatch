import html
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import auth as auth_module

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DATA = os.path.abspath(os.getenv("SKILLMATCH_DATA_DIR", _ROOT))
AUTH_DB = os.path.join(_DATA, "auth.db")
JOBS_DB = os.path.join(_DATA, "jobs.db")

_DIGEST_LIMIT = 15


def _fetch_active_alerts_with_email():
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT ja.*, u.email AS user_email, u.name AS user_name
        FROM job_alerts ja
        JOIN users u ON u.id = ja.user_id
        WHERE ja.is_active = 1
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _sent_job_ids_for_user(user_id: int) -> set[int]:
    conn = sqlite3.connect(AUTH_DB)
    cur = conn.execute(
        "SELECT job_id FROM alert_sent_jobs WHERE user_id = ?",
        (user_id,),
    )
    out = {int(r[0]) for r in cur.fetchall()}
    conn.close()
    return out


def _cadence_allows_send(alert: dict) -> bool:
    """Require ≥1 day (daily) or ≥7 days (weekly) since last successful digest."""
    raw = alert.get("last_sent_at")
    if not raw:
        return True
    try:
        last = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - last
    cadence = (alert.get("cadence") or "weekly").lower()
    if cadence == "daily":
        return delta >= timedelta(days=1)
    return delta >= timedelta(days=7)


def _query_catalog_jobs_for_alert(alert: dict, exclude_ids: set[int], limit: int) -> list[dict]:
    conn = sqlite3.connect(JOBS_DB)
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM jobs WHERE 1=1"
    params: list = []
    if alert.get("location"):
        sql += " AND LOWER(location) LIKE ?"
        params.append(f"%{str(alert['location']).lower()}%")
    if alert.get("work_mode"):
        sql += " AND LOWER(work_mode) = ?"
        params.append(str(alert["work_mode"]).lower())
    if alert.get("job_type"):
        sql += " AND LOWER(job_type) = ?"
        params.append(str(alert["job_type"]).lower())
    if alert.get("keywords"):
        sql += " AND (LOWER(job_title) LIKE ? OR LOWER(COALESCE(required_skills,'')) LIKE ?)"
        kw = f"%{str(alert['keywords']).lower()}%"
        params.extend([kw, kw])
    if exclude_ids:
        ph = ",".join("?" * len(exclude_ids))
        sql += f" AND id NOT IN ({ph})"
        params.extend(sorted(exclude_ids))
    sql += " ORDER BY posted_date DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _merged_new_jobs_for_alert(alert: dict, exclude_ids: set[int]) -> list[dict]:
    """Catalog (jobs.db) + company-posted listings, newest first, capped for one digest."""
    fetch_each = max(_DIGEST_LIMIT * 2, 24)
    catalog = _query_catalog_jobs_for_alert(alert, exclude_ids, fetch_each)
    try:
        recruiter = auth_module.list_recruiter_jobs_for_alert(
            alert.get("keywords"),
            alert.get("location"),
            alert.get("work_mode"),
            alert.get("job_type"),
            exclude_ids,
            fetch_each,
        )
    except Exception:
        recruiter = []
    merged = catalog + recruiter
    merged.sort(key=lambda j: str(j.get("posted_date") or ""), reverse=True)
    return merged[:_DIGEST_LIMIT]


def _filter_prefs_line(alert: dict) -> str:
    parts = []
    if alert.get("keywords"):
        parts.append(f"keywords “{alert['keywords']}”")
    if alert.get("location"):
        parts.append(f"location {alert['location']}")
    if alert.get("work_mode"):
        parts.append(alert["work_mode"])
    if alert.get("job_type"):
        parts.append(alert["job_type"])
    return ", ".join(parts) if parts else "your saved criteria"


def _build_digest_html(name: str, jobs: list[dict], alert: dict) -> str:
    raw_greeting = name.strip().split()[0] if name and name.strip() else "there"
    greeting = html.escape(raw_greeting)
    prefs = html.escape(_filter_prefs_line(alert))
    rows = []
    for j in jobs:
        title = html.escape(str(j.get("job_title") or "Job"))
        company = html.escape(str(j.get("company") or ""))
        loc = html.escape(str(j.get("location") or ""))
        link = html.escape(str(j.get("apply_link") or "#"), quote=True)
        sub = f"{company} · {loc}" if loc else company
        src = j.get("listing_source") == "recruiter"
        badge = (
            '<span style="font-size:11px;font-weight:600;color:#6929C4;margin-left:6px">Company post</span>'
            if src
            else '<span style="font-size:11px;color:#525252;margin-left:6px">Job board</span>'
        )
        rows.append(
            f'<tr><td style="padding:12px 0;border-bottom:1px solid #eee">'
            f'<a href="{link}" style="color:#0F62FE;font-weight:600">{title}</a>{badge}<br>'
            f'<span style="color:#525252;font-size:14px">{sub}</span></td></tr>'
        )
    return f"""\
<html><body style="font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#161616;max-width:560px">
<p>Hi {greeting},</p>
<p>We found <strong>{len(jobs)}</strong> new listing(s) for you (job board + company posts on SkillMatch) matching {prefs}:</p>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">{"".join(rows)}</table>
<p style="margin-top:20px;font-size:14px;color:#525252">You will not see these jobs again in future digests. Adjust your alert under Job Alerts in the app anytime.</p>
<p style="font-size:14px;color:#525252">— SkillMatch</p>
</body></html>"""


def _record_sent_jobs(user_id: int, job_ids: list[int]) -> None:
    conn = sqlite3.connect(AUTH_DB)
    now = datetime.now(timezone.utc).isoformat()
    for jid in job_ids:
        conn.execute(
            """INSERT OR IGNORE INTO alert_sent_jobs (user_id, job_id, sent_at)
               VALUES (?, ?, ?)""",
            (user_id, jid, now),
        )
    conn.commit()
    conn.close()


def _touch_alert_sent(user_id: int) -> None:
    conn = sqlite3.connect(AUTH_DB)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE job_alerts SET last_sent_at = ?, updated_at = ? WHERE user_id = ?""",
        (now, now, user_id),
    )
    conn.commit()
    conn.close()


def run_alert_cycle():
    """
    For each active alert: respect cadence, collect new jobs (job board + employer posts),
    send one HTML digest, record job ids, update last_sent_at only when mail went out.
    """
    alerts = _fetch_active_alerts_with_email()
    emails_sent = 0
    skipped_cadence = 0
    skipped_no_new = 0
    details = []

    for a in alerts:
        uid = int(a["user_id"])
        entry = {
            "user_id": uid,
            "new_matches": 0,
            "emailed": False,
            "skip_reason": None,
        }

        if not _cadence_allows_send(a):
            entry["skip_reason"] = "cadence"
            skipped_cadence += 1
            details.append(entry)
            continue

        already = _sent_job_ids_for_user(uid)
        matches = _merged_new_jobs_for_alert(a, already)
        entry["new_matches"] = len(matches)

        if not matches:
            entry["skip_reason"] = "no_new_matches"
            skipped_no_new += 1
            details.append(entry)
            continue

        email = (a.get("user_email") or "").strip()
        if not email:
            entry["skip_reason"] = "no_email"
            details.append(entry)
            continue

        subject = f"SkillMatch: {len(matches)} new job{'s' if len(matches) != 1 else ''} for you"
        html = _build_digest_html(a.get("user_name") or "", matches, a)
        try:
            auth_module.send_html_email(email, subject, html)
        except Exception as ex:
            entry["skip_reason"] = f"send_failed:{ex!s}"
            details.append(entry)
            continue

        ids = [int(j["id"]) for j in matches if j.get("id") is not None]
        _record_sent_jobs(uid, ids)
        _touch_alert_sent(uid)
        entry["emailed"] = True
        emails_sent += 1
        details.append(entry)

    return {
        "ok": True,
        "alerts_checked": len(alerts),
        "alerts_processed": len(alerts),
        "emails_sent": emails_sent,
        "alerts_with_matches": emails_sent,
        "skipped_cadence": skipped_cadence,
        "skipped_no_new_matches": skipped_no_new,
        "details": details,
    }
