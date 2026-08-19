"""
database.py — SQLite persistence layer for GhostMail.
Stores job metadata and per-recipient failure logs.
"""

import sqlite3
import json
import time
import os
import logging
from contextlib import contextmanager

from runtime_paths import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(DATA_DIR, "ghostmail.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'running',
    provider        TEXT NOT NULL DEFAULT '',
    total           INTEGER NOT NULL DEFAULT 0,
    success_count   INTEGER NOT NULL DEFAULT 0,
    failed_count    INTEGER NOT NULL DEFAULT 0,
    processed       INTEGER NOT NULL DEFAULT 0,
    subject_template TEXT NOT NULL DEFAULT '',
    from_email      TEXT NOT NULL DEFAULT '',
    from_name       TEXT NOT NULL DEFAULT '',
    interval_secs   INTEGER NOT NULL DEFAULT 4,
    current_email   TEXT NOT NULL DEFAULT '',
    error           TEXT,
    created_at      REAL,
    completed_at    REAL,
    updated_at      REAL
);

CREATE TABLE IF NOT EXISTS job_failures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL,
    email       TEXT NOT NULL,
    error       TEXT NOT NULL DEFAULT '',
    created_at  REAL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL DEFAULT 'single',
    status      TEXT NOT NULL DEFAULT 'pending',
    send_at     REAL NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',
    linked_job  TEXT,
    error       TEXT,
    sent_at     REAL,
    cancelled_at REAL,
    created_at  REAL,
    updated_at  REAL
);

CREATE TABLE IF NOT EXISTS provider_keys (
    provider    TEXT PRIMARY KEY,
    api_key     TEXT NOT NULL DEFAULT '',
    updated_at  REAL
);
"""


def init_db():
    """Initialize the database and create tables if they don't exist."""
    with _get_conn() as conn:
        conn.executescript(SCHEMA)
    logger.info(f"Database initialized at {DB_PATH}")


@contextmanager
def _get_conn():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
#  JOBS
# ═══════════════════════════════════════════════════════════════════════

def create_job(
    job_id: str,
    provider: str,
    total: int,
    subject_template: str,
    from_email: str = "",
    from_name: str = "",
    interval_secs: int = 4,
) -> dict:
    """Create a new job record."""
    now = time.time()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO jobs
               (id, status, provider, total, subject_template,
                from_email, from_name, interval_secs, created_at, updated_at)
               VALUES (?, 'running', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, provider, total, subject_template, from_email, from_name, interval_secs, now, now),
        )
    return get_job(job_id)


def get_job(job_id: str) -> dict | None:
    """Retrieve a single job by ID."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_dict(row) if row else None


def get_all_jobs(limit: int | None = 50) -> list[dict]:
    """Retrieve jobs ordered by creation time (newest first)."""
    with _get_conn() as conn:
        if limit is None:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_dict(r) for r in rows]


def update_job(job_id: str, **kwargs):
    """Update specific fields on a job record."""
    kwargs["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())
    with _get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values + [job_id])


def complete_job(
    job_id: str,
    success_count: int,
    failed_count: int,
    processed: int,
    error: str = None,
):
    """Mark a job as completed."""
    now = time.time()
    if error:
        status = "failed"
    elif failed_count > 0:
        status = "completed_with_errors"
    else:
        status = "completed"
    update_job(
        job_id,
        status=status,
        success_count=success_count,
        failed_count=failed_count,
        processed=processed,
        completed_at=now,
        current_email="Finished",
        error=error,
    )


def pause_job(job_id: str) -> bool:
    """Mark a job as paused. Returns True if job was running."""
    job = get_job(job_id)
    if job and job["status"] == "running":
        update_job(job_id, status="paused")
        return True
    return False


def resume_job(job_id: str) -> bool:
    """Mark a job as running again. Returns True if job was paused."""
    job = get_job(job_id)
    if job and job["status"] == "paused":
        update_job(job_id, status="running")
        return True
    return False


def cancel_job(job_id: str) -> bool:
    """Mark a job as cancelled. Returns True if job was running/paused."""
    job = get_job(job_id)
    if job and job["status"] in ("running", "paused"):
        update_job(job_id, status="cancelled", completed_at=time.time())
        return True
    return False


def delete_job(job_id: str) -> bool:
    """Delete a job and its failure records."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM job_failures WHERE job_id = ?", (job_id,))
        result = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return result.rowcount > 0


def log_failure(job_id: str, email: str, error: str):
    """Log a single recipient failure."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO job_failures (job_id, email, error, created_at) VALUES (?, ?, ?, ?)",
            (job_id, email, error, time.time()),
        )


def get_failures(job_id: str, limit: int = 200) -> list[dict]:
    """Retrieve failure records for a job."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT email, error, created_at FROM job_failures WHERE job_id = ? ORDER BY id LIMIT ?",
            (job_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════
#  SCHEDULED JOBS
# ═══════════════════════════════════════════════════════════════════════

def create_scheduled_job(sched_id: str, job_type: str, send_at: float, payload: dict) -> dict:
    """Create a scheduled job."""
    now = time.time()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO scheduled_jobs
               (id, type, status, send_at, payload, created_at, updated_at)
               VALUES (?, ?, 'pending', ?, ?, ?, ?)""",
            (sched_id, job_type, send_at, json.dumps(payload), now, now),
        )
    return get_scheduled_job(sched_id)


def get_scheduled_job(sched_id: str) -> dict | None:
    """Retrieve a single scheduled job by ID."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM scheduled_jobs WHERE id = ?", (sched_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("payload"), str):
            try:
                d["payload"] = json.loads(d["payload"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d


def get_all_scheduled_jobs(limit: int | None = 50) -> list[dict]:
    """Retrieve scheduled jobs ordered by send_at."""
    with _get_conn() as conn:
        if limit is None:
            rows = conn.execute("SELECT * FROM scheduled_jobs ORDER BY send_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM scheduled_jobs ORDER BY send_at DESC LIMIT ?", (limit,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("payload"), str):
                try:
                    d["payload"] = json.loads(d["payload"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result


def get_due_scheduled_jobs() -> list[dict]:
    """Get all pending jobs whose send_at <= now (atomic claim: pending → running)."""
    now = time.time()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM scheduled_jobs WHERE status = 'pending' AND send_at <= ?",
            (now,),
        ).fetchall()
        claimed = []
        for row in rows:
            conn.execute(
                "UPDATE scheduled_jobs SET status = 'running', updated_at = ? WHERE id = ? AND status = 'pending'",
                (now, row["id"]),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                claimed.append(row["id"])
        conn.commit()
    result = []
    for sid in claimed:
        job = get_scheduled_job(sid)
        if job:
            result.append(job)
    return result


def mark_scheduled_sent(sched_id: str, linked_job: str = None):
    """Mark a scheduled job as sent."""
    now = time.time()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE scheduled_jobs SET status = 'sent', sent_at = ?, linked_job = ?, updated_at = ? WHERE id = ?",
            (now, linked_job, now, sched_id),
        )


def mark_scheduled_failed(sched_id: str, error: str):
    """Mark a scheduled job as failed."""
    now = time.time()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE scheduled_jobs SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
            (error, now, sched_id),
        )


def cancel_scheduled_job(sched_id: str) -> bool:
    """Cancel a pending scheduled job."""
    now = time.time()
    with _get_conn() as conn:
        result = conn.execute(
            "UPDATE scheduled_jobs SET status = 'cancelled', cancelled_at = ?, updated_at = ? WHERE id = ? AND status = 'pending'",
            (now, now, sched_id),
        )
        return result.rowcount > 0


def update_scheduled_job(sched_id: str, send_at: float = None, payload: dict = None) -> bool:
    """Update a pending scheduled job's time or payload."""
    job = get_scheduled_job(sched_id)
    if not job or job["status"] != "pending":
        return False
    now = time.time()
    with _get_conn() as conn:
        if send_at is not None and payload is not None:
            conn.execute(
                "UPDATE scheduled_jobs SET send_at = ?, payload = ?, updated_at = ? WHERE id = ? AND status = 'pending'",
                (send_at, json.dumps(payload), now, sched_id),
            )
        elif send_at is not None:
            conn.execute(
                "UPDATE scheduled_jobs SET send_at = ?, updated_at = ? WHERE id = ? AND status = 'pending'",
                (send_at, now, sched_id),
            )
        elif payload is not None:
            conn.execute(
                "UPDATE scheduled_jobs SET payload = ?, updated_at = ? WHERE id = ? AND status = 'pending'",
                (json.dumps(payload), now, sched_id),
            )
    return True


def delete_scheduled_job(sched_id: str) -> bool:
    """Delete a scheduled job."""
    with _get_conn() as conn:
        result = conn.execute("DELETE FROM scheduled_jobs WHERE id = ?", (sched_id,))
        return result.rowcount > 0


def recover_stale_scheduled() -> int:
    """On startup, reset any 'running' scheduled jobs older than 10 min back to pending."""
    cutoff = time.time() - 600
    with _get_conn() as conn:
        result = conn.execute(
            "UPDATE scheduled_jobs SET status = 'pending', updated_at = ? WHERE status = 'running' AND updated_at < ?",
            (time.time(), cutoff),
        )
        return result.rowcount


# ═══════════════════════════════════════════════════════════════════════
#  PROVIDER KEYS (runtime API key storage)
# ═══════════════════════════════════════════════════════════════════════

def save_provider_key(provider: str, api_key: str):
    """Save or update an API key for a provider in the database."""
    now = time.time()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO provider_keys (provider, api_key, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(provider) DO UPDATE SET api_key = excluded.api_key, updated_at = excluded.updated_at""",
            (provider.lower(), api_key, now),
        )


def get_provider_key(provider: str) -> str | None:
    """Retrieve a stored API key for a provider."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT api_key FROM provider_keys WHERE provider = ?",
            (provider.lower(),),
        ).fetchone()
        return row["api_key"] if row else None


def get_all_provider_keys() -> dict[str, str]:
    """Retrieve all stored provider API keys."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT provider, api_key FROM provider_keys").fetchall()
        return {r["provider"]: r["api_key"] for r in rows}


def delete_provider_key(provider: str) -> bool:
    """Delete a stored API key for a provider."""
    with _get_conn() as conn:
        result = conn.execute("DELETE FROM provider_keys WHERE provider = ?", (provider.lower(),))
        return result.rowcount > 0


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else {}
