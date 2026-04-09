"""
Trim jobs so each category has at most TARGET_PER_CATEGORY rows.
Deletes synthetic rows first (BalanceTech / (Balanced) / balancetech.dev), then
highest id. Iterates until all categories are capped (handles multi-category rows).

After capping, shared rows can leave some categories below target; use --refill
to run balance_jobs.py in the same process.

Run:
  python cap_jobs.py [--dry-run] [--refill]
"""
from __future__ import annotations

import argparse
import sqlite3

from balance_jobs import CATEGORIES, DB_PATH, TARGET_PER_CATEGORY


def _is_synthetic(company: str, job_title: str, apply_link: str) -> bool:
    c = (company or "").lower()
    t = (job_title or "").lower()
    a = (apply_link or "").lower()
    return (
        "balancetech-" in c
        or "(balanced)" in t
        or "balancetech.dev" in a
    )


def count_cat(cur: sqlite3.Cursor, where_sql: str) -> int:
    return int(cur.execute(f"SELECT COUNT(*) FROM jobs WHERE {where_sql}").fetchone()[0])


def pick_ids_to_delete(cur: sqlite3.Cursor, where_sql: str, excess: int) -> list[int]:
    if excess <= 0:
        return []
    cur.execute(
        f"SELECT id, company, job_title, apply_link FROM jobs WHERE {where_sql}"
    )
    rows = cur.fetchall()
    scored: list[tuple[int, int]] = []
    for row in rows:
        jid = int(row[0])
        syn = 1 if _is_synthetic(row[1], row[2], row[3]) else 0
        scored.append((jid, syn))
    # Delete synthetic first, then higher id first
    scored.sort(key=lambda x: (-x[1], -x[0]))
    return [x[0] for x in scored[:excess]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--refill",
        action="store_true",
        help="After cap, run balance_jobs to bring underfilled categories up to target",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    total_deleted = 0
    rounds = 0
    max_rounds = 50

    while rounds < max_rounds:
        rounds += 1
        over: list[tuple[str, str, int]] = []
        for name, where_sql in CATEGORIES:
            n = count_cat(cur, where_sql)
            if n > TARGET_PER_CATEGORY:
                over.append((name, where_sql, n))

        if not over:
            break

        to_delete: set[int] = set()
        for name, where_sql, n in over:
            excess = n - TARGET_PER_CATEGORY
            ids = pick_ids_to_delete(cur, where_sql, excess)
            to_delete.update(ids)

        if not to_delete:
            break

        if args.dry_run and total_deleted == 0:
            print(f"Target per category: {TARGET_PER_CATEGORY}")
            for name, where_sql in CATEGORIES:
                n = count_cat(cur, where_sql)
                flag = " OVER" if n > TARGET_PER_CATEGORY else ""
                print(f"  {name}: {n}{flag}")
            print(f"First round would delete {len(to_delete)} unique row(s).")
            conn.close()
            return

        for jid in to_delete:
            cur.execute("DELETE FROM jobs WHERE id = ?", (jid,))
            total_deleted += 1

        conn.commit()

    remaining = cur.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()

    if args.dry_run:
        return

    print(f"Deleted {total_deleted} job row(s) in {rounds} round(s). Remaining total: {remaining}")
    conn2 = sqlite3.connect(DB_PATH)
    c2 = conn2.cursor()
    for name, where_sql in CATEGORIES:
        n = c2.execute(f"SELECT COUNT(*) FROM jobs WHERE {where_sql}").fetchone()[0]
        flag = " !!" if n > TARGET_PER_CATEGORY else ""
        print(f"  {name}: {n}{flag}")
    conn2.close()

    if args.refill and not args.dry_run:
        from balance_jobs import run_balance

        print("--- refill (balance) ---")
        run_balance(dry_run=False)


if __name__ == "__main__":
    main()
