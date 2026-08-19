"""
app.py — GhostMail: Unified Email Delivery Platform.

Single Flask app supporting multiple email providers (Resend, ZeptoMail,
Mailgun, SendGrid) with SQLite persistence, runtime API key management,
rich HTML compose, bulk campaigns, scheduling, and domain awareness.
"""

import os
import re
import sys
import time
import uuid
import json
import base64
import logging
import threading
from html import escape
from html.parser import HTMLParser
from collections import Counter, deque
from functools import wraps
from io import BytesIO
from datetime import datetime

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv

import openpyxl
import xlrd

from runtime_paths import DATA_DIR
from providers import create_provider, EmailProvider, APIError, PROVIDERS, PROVIDER_META
from database import (
    DB_PATH,
    init_db,
    create_job, get_job, get_all_jobs, update_job, complete_job,
    pause_job, resume_job, cancel_job, delete_job,
    log_failure, get_failures,
    create_scheduled_job, get_scheduled_job, get_all_scheduled_jobs,
    get_due_scheduled_jobs, mark_scheduled_sent, mark_scheduled_failed,
    cancel_scheduled_job, update_scheduled_job, delete_scheduled_job,
    recover_stale_scheduled,
    save_provider_key, get_provider_key, get_all_provider_keys, delete_provider_key,
)

# ═══════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════

MAX_RECIPIENTS = 1000
DEFAULT_INTERVAL = 4
MIN_INTERVAL = 1
MAX_INTERVAL = 60

if getattr(sys, "frozen", False):
    BASEDIR = sys._MEIPASS
    RUNDIR = os.path.dirname(sys.executable)
else:
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    RUNDIR = BASEDIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(threadName)-18s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ghostmail")
APP_START_TS = time.time()
RECENT_EVENTS = deque(maxlen=250)
SCHEDULER_LAST_TICK = APP_START_TS


class _RecentLogHandler(logging.Handler):
    def emit(self, record):
        try:
            RECENT_EVENTS.append({
                "timestamp": record.created,
                "level": record.levelname,
                "logger": record.name,
                "thread": record.threadName,
                "message": record.getMessage(),
            })
        except Exception:
            pass


logging.getLogger().addHandler(_RecentLogHandler())

# User configuration takes precedence over defaults shipped beside the app.
load_dotenv(os.path.join(DATA_DIR, ".env"))
load_dotenv(os.path.join(RUNDIR, ".env"))
load_dotenv(os.path.join(BASEDIR, ".env"))

PROVIDER_NAME = os.getenv("EMAIL_PROVIDER", "zeptomail").lower()
RESEND_KEY = os.getenv("RESEND_API_KEY", "")
ZEPTO_KEY = os.getenv("ZEPTOMAIL_API_KEY", "")
DEFAULT_SENDER_NAME = os.getenv("DEFAULT_SENDER_NAME", "Ghost").strip() or "Ghost"
APP_PASSWORD = os.getenv("APP_PASSWORD", "ghost2026")
FLASK_SECRET = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

_key_map = {"resend": RESEND_KEY, "zeptomail": ZEPTO_KEY}
ACTIVE_API_KEY = _key_map.get(PROVIDER_NAME, "")

# ═══════════════════════════════════════════════════════════════════════
#  FLASK APP
# ═══════════════════════════════════════════════════════════════════════

app = Flask(
    __name__,
    static_folder=os.path.join(BASEDIR, "static"),
    template_folder=os.path.join(BASEDIR, "templates"),
)
app.secret_key = FLASK_SECRET
app.config["TEMPLATES_AUTO_RELOAD"] = True
CORS(app)

init_db()

# ── Load runtime keys from DB, fall back to .env ───────────────────
def _resolve_api_key(prov_name: str) -> str:
    """Get API key: DB-stored > .env > empty."""
    db_key = get_provider_key(prov_name)
    if db_key:
        return db_key
    return _key_map.get(prov_name, "")


def _init_provider():
    """Initialize the active provider, trying DB keys then .env keys."""
    global provider, PROVIDER_NAME, ACTIVE_API_KEY
    key = _resolve_api_key(PROVIDER_NAME)
    if key:
        try:
            provider = create_provider(PROVIDER_NAME, key)
            ACTIVE_API_KEY = key
            logger.info(f"Email provider: {provider.name}")
            return
        except ValueError as e:
            logger.error(f"Provider init error: {e}")

    # Try other providers with available keys
    for prov_name in PROVIDERS:
        k = _resolve_api_key(prov_name)
        if k:
            try:
                provider = create_provider(prov_name, k)
                PROVIDER_NAME = prov_name
                ACTIVE_API_KEY = k
                logger.info(f"Fell back to provider: {provider.name}")
                return
            except ValueError:
                continue

    logger.critical("No API key found for any provider.")
    provider = None


provider: EmailProvider | None = None
_init_provider()

# ── State ──────────────────────────────────────────────────────────
active_threads: dict[str, threading.Thread] = {}
_domain_cache: list[dict] = []
_domain_cache_ts: float = 0.0
DOMAIN_CACHE_TTL = 300  # 5 min


# ═══════════════════════════════════════════════════════════════════════
#  DOMAIN HELPERS
# ═══════════════════════════════════════════════════════════════════════

def fetch_verified_domains(force: bool = False) -> list[dict]:
    """Fetch verified domains from the active provider, with caching."""
    global _domain_cache, _domain_cache_ts
    if not provider:
        return []
    if provider.name == "ZeptoMail":
        return []
    if not force and _domain_cache and (time.time() - _domain_cache_ts < DOMAIN_CACHE_TTL):
        return _domain_cache
    try:
        d = provider.get_verified_domains()
        _domain_cache = d
        _domain_cache_ts = time.time()
        logger.info(f"Fetched {len(d)} domain(s) from {provider.name}")
        return d
    except Exception as e:
        logger.error(f"Domain fetch error: {e}")
        return _domain_cache


def is_sender_domain_allowed(sender_email: str) -> tuple[bool, str]:
    """
    Check if the sender email's domain is verified for the active provider.
    Returns (allowed, reason).
    """
    domains = fetch_verified_domains()
    if not domains:
        return True, ""  # can't validate, let provider reject
    sender_domain = sender_email.rsplit("@", 1)[-1].lower()
    verified = [
        d.get("domain", "").lower()
        for d in domains
        if d.get("status") in ("verified", "active", "not_started")
    ]
    if not verified:
        return True, ""
    if sender_domain in verified:
        return True, ""
    return False, (
        f"Domain '{sender_domain}' is not verified for {provider.name}. "
        f"Verified domains: {', '.join(verified)}. "
        f"Add and verify '{sender_domain}' in your {provider.name} dashboard, "
        f"or use a sender from a verified domain."
    )


def get_default_sender_email() -> str:
    """Pick the sender email from config, falling back only when it is missing."""
    env_sender = os.getenv("DEFAULT_SENDER_EMAIL", "").strip()
    if env_sender:
        return env_sender
    domains = fetch_verified_domains()
    for d in domains:
        if d.get("status") in ("verified", "active", "not_started"):
            domain = d.get("domain", "")
            if domain:
                return f"{DEFAULT_SENDER_NAME.lower().replace(' ', '')}@{domain}"
    return env_sender


def _sender_locked(provider_id: str | None = None) -> bool:
    return False


def _resolve_sender(
    requested_email: str = "",
    requested_name: str = "",
    provider_id: str | None = None,
) -> tuple[str, str]:
    if _sender_locked(provider_id):
        return get_default_sender_email(), DEFAULT_SENDER_NAME
    return (
        requested_email.strip() or get_default_sender_email(),
        requested_name.strip() or DEFAULT_SENDER_NAME,
    )


# ═══════════════════════════════════════════════════════════════════════
#  SCHEDULER
# ═══════════════════════════════════════════════════════════════════════

def _scheduler_loop():
    """Background loop: every 15s, check for due scheduled jobs and fire them."""
    global SCHEDULER_LAST_TICK
    logger.info("Scheduler thread started.")
    recovered = recover_stale_scheduled()
    if recovered:
        logger.info(f"Scheduler recovered {recovered} stale job(s) to pending.")
    while True:
        SCHEDULER_LAST_TICK = time.time()
        try:
            due = get_due_scheduled_jobs()
            for sj in due:
                try:
                    _fire_scheduled_job(sj)
                except Exception as e:
                    logger.error(f"Scheduler fire error [{sj.get('id')}]: {e}")
                    mark_scheduled_failed(sj["id"], str(e))
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
        time.sleep(15)


def _fire_scheduled_job(sj: dict):
    """Execute a scheduled job (single or campaign)."""
    sched_id = sj["id"]
    payload = sj.get("payload", {})
    job_type = sj.get("type", "single")
    logger.info(f"⏰ Firing scheduled job {sched_id} (type={job_type})")

    provider_id = (payload.get("_provider_id") or PROVIDER_NAME or "").lower()
    try:
        frozen_provider_id, frozen_key, scheduled_provider = _get_provider_snapshot(provider_id)
    except Exception as e:
        logger.error(f"⏰ Scheduled job {sched_id} provider error: {e}")
        mark_scheduled_failed(sched_id, str(e))
        return

    if job_type == "single":
        to_email = payload.get("to_email")
        subject = payload.get("subject")
        html_content = normalize_email_html(payload.get("html_content"))
        from_email, from_name = _resolve_sender(
            payload.get("from_email", ""),
            payload.get("from_name", ""),
            provider_id,
        )
        to_name = payload.get("to_name", "")
        job_id = f"SchedSingle-{uuid.uuid4().hex[:8]}"
        try:
            create_job(job_id, scheduled_provider.name, 1, subject, from_email, from_name, 0)
            scheduled_provider.send(from_email, from_name, to_email, to_name, subject, html_content)
            complete_job(job_id, 1, 0, 1)
            mark_scheduled_sent(sched_id, job_id)
            logger.info(f"⏰ Scheduled single send → {to_email}")
        except APIError as e:
            log_failure(job_id, to_email or "", e.message)
            complete_job(job_id, 0, 1, 1, error=e.message)
            mark_scheduled_failed(sched_id, e.message)
            logger.error(f"⏰ Scheduled single send failed: {e.message}")
        except Exception as e:
            log_failure(job_id, to_email or "", str(e))
            complete_job(job_id, 0, 1, 1, error=str(e))
            mark_scheduled_failed(sched_id, str(e))
            logger.error(f"⏰ Scheduled single send error: {e}")

    elif job_type == "campaign":
        recipients = payload.get("recipients", [])
        subject_tmpl = payload.get("subject")
        html_tmpl = normalize_email_html(payload.get("html_content"))
        interval = int(payload.get("interval", DEFAULT_INTERVAL))
        from_email_tmpl = "" if _sender_locked(provider_id) else payload.get("from_email_template", "")
        from_name_tmpl = "" if _sender_locked(provider_id) else payload.get("from_name_template", "")
        from_email_seed, from_name_seed = _resolve_sender(from_email_tmpl, from_name_tmpl, provider_id)
        job_id = f"SchedBulk-{uuid.uuid4().hex[:8]}"
        try:
            create_job(job_id, scheduled_provider.name, len(recipients), subject_tmpl, from_email_seed, from_name_seed, interval)
            thread = threading.Thread(
                target=_bulk_send_worker,
                args=(job_id, recipients, subject_tmpl, html_tmpl, interval, [], from_email_tmpl, from_name_tmpl, frozen_provider_id, frozen_key),
                name=f"SchedBulk-{job_id}",
            )
            active_threads[job_id] = thread
            thread.start()
            mark_scheduled_sent(sched_id, job_id)
            logger.info(f"⏰ Scheduled campaign fired → job {job_id} ({len(recipients)} emails)")
        except Exception as e:
            mark_scheduled_failed(sched_id, str(e))
            logger.error(f"⏰ Scheduled campaign error: {e}")


_scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="Scheduler")
_scheduler_thread.start()


# ═══════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email) -> bool:
    return bool(isinstance(email, str) and EMAIL_RE.match(email.strip()))


def normalize_column(col) -> str:
    if not isinstance(col, str):
        col = str(col)
    norm = re.sub(r"\W|^(?=\d)", "_", col).strip("_")
    return norm or f"col_{uuid.uuid4().hex[:6]}"


def process_template(template: str, context: dict) -> str:
    """Replace {{Var Name}} placeholders with context values."""
    if not isinstance(template, str) or not isinstance(context, dict):
        return template

    def _replace(m):
        key = normalize_column(m.group(1).strip())
        val = context.get(key)
        return str(val) if val is not None else m.group(0)

    return re.sub(r"{{\s*([\w\s.\-]+?)\s*}}", _replace, template)


def _parse_style_attr(style: str) -> dict[str, str]:
    result = {}
    for part in str(style or "").split(";"):
        if ":" not in part:
            continue
        name, value = part.split(":", 1)
        name = name.strip().lower()
        value = value.strip()
        if name and value:
            result[name] = value
    return result


def _style_attr(styles: dict[str, str]) -> str:
    return "; ".join(f"{name}: {value}" for name, value in styles.items()) + ";"


def _render_tag(tag: str, attrs: list[tuple[str, str | None]]) -> str:
    rendered = [tag]
    for name, value in attrs:
        if value is None:
            rendered.append(escape(name, quote=True))
        else:
            rendered.append(f'{escape(name, quote=True)}="{escape(str(value), quote=True)}"')
    return "<" + " ".join(rendered) + ">"


class _EmailHtmlNormalizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def _normalize_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
        attr_map = {name.lower(): value for name, value in attrs}
        styles = _parse_style_attr(attr_map.get("style") or "")
        classes = str(attr_map.get("class") or "")

        if tag in {"p", "div", "li"}:
            styles["margin"] = "0"
            styles.setdefault("line-height", "1.4")
        elif tag in {"ul", "ol"}:
            styles["margin"] = "0 0 0 1.25em"
            styles["padding-left"] = "1.25em"

        if "ql-align-center" in classes:
            styles["text-align"] = "center"
        elif "ql-align-right" in classes:
            styles["text-align"] = "right"
        elif "ql-align-justify" in classes:
            styles["text-align"] = "justify"

        if styles:
            replaced = False
            normalized = []
            for name, value in attrs:
                if name.lower() == "style":
                    normalized.append((name, _style_attr(styles)))
                    replaced = True
                else:
                    normalized.append((name, value))
            if not replaced:
                normalized.append(("style", _style_attr(styles)))
            return normalized
        return attrs

    def handle_starttag(self, tag, attrs):
        self.parts.append(_render_tag(tag, self._normalize_attrs(tag.lower(), attrs)))

    def handle_startendtag(self, tag, attrs):
        start = _render_tag(tag, self._normalize_attrs(tag.lower(), attrs))
        self.parts.append(start[:-1] + " />")

    def handle_endtag(self, tag):
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")


def normalize_email_html(html_content: str) -> str:
    """Make Quill block HTML render like line-by-line webmail in email clients."""
    if not isinstance(html_content, str) or not html_content.strip():
        return ""
    parser = _EmailHtmlNormalizer()
    try:
        parser.feed(html_content.strip())
        parser.close()
        return "".join(parser.parts)
    except Exception as e:
        logger.warning(f"Email HTML normalization failed: {e}")
        return html_content.strip()


def encode_attachments(files) -> list[dict]:
    """Encode uploaded files to base64 for provider payloads."""
    result = []
    for f in files:
        if not hasattr(f, "filename"):
            continue
        if not str(f.filename or "").strip():
            continue
        try:
            content = f.read()
            if not content:
                continue
            result.append({
                "filename": f.filename,
                "content": base64.b64encode(content).decode("utf-8"),
                "mimetype": f.mimetype or "application/octet-stream",
            })
        except Exception as e:
            logger.error(f"Attachment error ({f.filename}): {e}")
    return result


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template(
        "index.html",
        provider_name=provider.name if provider else "None",
        sender_email=get_default_sender_email(),
        sender_name=DEFAULT_SENDER_NAME,
        authenticated=session.get("authenticated"),
    )


# ── Auth ───────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if data.get("password") == APP_PASSWORD:
        session["authenticated"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid password."})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


# ── Config & Provider Switching ────────────────────────────────────

@app.route("/api/config")
@login_required
def get_config():
    resolved_sender = get_default_sender_email()
    all_db_keys = get_all_provider_keys()

    available = []
    for prov_id in PROVIDERS:
        meta = PROVIDER_META.get(prov_id, {})
        env_key = _key_map.get(prov_id, "")
        db_key = all_db_keys.get(prov_id, "")
        has_key = bool(env_key or db_key)
        key_source = "database" if db_key else ("env" if env_key else "none")
        available.append({
            "id": prov_id,
            "label": meta.get("label", prov_id.title()),
            "icon": meta.get("icon", "envelope"),
            "color": meta.get("color", "gray"),
            "has_key": has_key,
            "key_source": key_source,
            "key_preview": _mask_key(db_key or env_key) if has_key else "",
        })

    return jsonify({
        "success": True,
        "provider": provider.name if provider else "None",
        "provider_id": PROVIDER_NAME,
        "sender_email": resolved_sender or "",
        "sender_name": DEFAULT_SENDER_NAME,
        "sender_locked": _sender_locked(PROVIDER_NAME),
        "verified_domains": [],
        "available_providers": available,
    })


def _mask_key(key: str) -> str:
    """Show first 6 and last 4 chars of a key."""
    if not key or len(key) < 12:
        return "••••••••"
    return key[:6] + "••••" + key[-4:]


def _get_provider_snapshot(provider_id: str | None = None, api_key: str | None = None) -> tuple[str, str, EmailProvider]:
    """Freeze a provider + key at the moment a job is created or fired."""
    chosen = (provider_id or PROVIDER_NAME or "").lower()
    if chosen not in PROVIDERS:
        raise ValueError(f"Unknown provider: {chosen}")
    resolved_key = api_key or _resolve_api_key(chosen)
    if not resolved_key:
        raise ValueError(f"No API key configured for {chosen}")
    return chosen, resolved_key, create_provider(chosen, resolved_key)


def _job_kind(job: dict) -> str:
    job_id = (job.get("id") or "").lower()
    if job_id.startswith("singlesend-") or job_id.startswith("schedsingle-"):
        return "single"
    return "campaign"


def _serialize_job(job: dict | None, include_failures: bool = False) -> dict | None:
    if not job:
        return None
    data = dict(job)
    data["kind"] = _job_kind(data)
    data["failures"] = get_failures(data["id"]) if include_failures else []
    return data


def _serialize_scheduled_job(job: dict) -> dict:
    data = dict(job)
    linked_job_id = data.get("linked_job")
    linked_job = get_job(linked_job_id) if linked_job_id else None
    data["linked_job_summary"] = _serialize_job(linked_job, include_failures=False) if linked_job else None
    data["display_status"] = linked_job["status"] if linked_job else data.get("status")
    return data


def _collect_active_threads() -> list[dict]:
    snapshots = []
    stale_ids = []
    for job_id, thread in list(active_threads.items()):
        alive = thread.is_alive()
        job = get_job(job_id)
        if not alive:
            stale_ids.append(job_id)
        snapshots.append({
            "job_id": job_id,
            "thread_name": thread.name,
            "alive": alive,
            "daemon": thread.daemon,
            "job": _serialize_job(job) if job else None,
        })
    for job_id in stale_ids:
        active_threads.pop(job_id, None)
    return snapshots


def _provider_key_source(provider_id: str, db_keys: dict[str, str]) -> str:
    if db_keys.get(provider_id):
        return "database"
    if _key_map.get(provider_id, ""):
        return "env"
    return "none"


def _operations_snapshot() -> dict:
    jobs = get_all_jobs(None)
    scheduled_jobs = get_all_scheduled_jobs(None)
    db_keys = get_all_provider_keys()
    active_workers = _collect_active_threads()

    job_status_counts = Counter((job.get("status") or "unknown") for job in jobs)
    job_provider_counts = Counter((job.get("provider") or "unknown") for job in jobs)
    job_kind_counts = Counter(_job_kind(job) for job in jobs)
    scheduled_status_counts = Counter((job.get("status") or "unknown") for job in scheduled_jobs)
    scheduled_type_counts = Counter((job.get("type") or "unknown") for job in scheduled_jobs)

    provider_state = []
    for provider_id in PROVIDERS:
        meta = PROVIDER_META.get(provider_id, {})
        provider_state.append({
            "id": provider_id,
            "label": meta.get("label", provider_id.title()),
            "key_source": _provider_key_source(provider_id, db_keys),
            "configured": bool(_resolve_api_key(provider_id)),
            "history_count": job_provider_counts.get(meta.get("label", provider_id.title()), 0),
        })

    return {
        "generated_at": time.time(),
        "single_source_of_truth": {
            "database_path": DB_PATH,
            "jobs_table_count": len(jobs),
            "scheduled_table_count": len(scheduled_jobs),
            "note": "Delivery history and scheduling state are persisted in one SQLite database.",
        },
        "runtime": {
            "uptime_seconds": max(0, int(time.time() - APP_START_TS)),
            "active_provider": provider.name if provider else "None",
            "active_provider_id": PROVIDER_NAME,
            "resolved_sender_email": get_default_sender_email(),
            "resolved_sender_name": DEFAULT_SENDER_NAME,
            "scheduler_alive": _scheduler_thread.is_alive(),
            "scheduler_last_tick": SCHEDULER_LAST_TICK,
            "active_worker_count": sum(1 for worker in active_workers if worker.get("alive")),
            "domain_cache_count": len(_domain_cache),
        },
        "providers": provider_state,
        "job_counts": {
            "by_status": dict(job_status_counts),
            "by_provider": dict(job_provider_counts),
            "by_kind": dict(job_kind_counts),
        },
        "scheduled_counts": {
            "by_status": dict(scheduled_status_counts),
            "by_type": dict(scheduled_type_counts),
        },
        "active_workers": active_workers,
        "recent_jobs": [_serialize_job(job) for job in jobs[:8]],
        "recent_scheduled": [_serialize_scheduled_job(job) for job in scheduled_jobs[:8]],
        "recent_events": list(RECENT_EVENTS)[-80:],
    }


@app.route("/api/switch-provider", methods=["POST"])
@login_required
def switch_provider_route():
    """Hot-swap the active email provider at runtime, re-reading .env for fresh keys."""
    global provider, PROVIDER_NAME, ACTIVE_API_KEY, _domain_cache, _domain_cache_ts
    global RESEND_KEY, ZEPTO_KEY

    data = request.get_json()
    new_name = data.get("provider", "").lower()
    if new_name not in PROVIDERS:
        return jsonify({"success": False, "error": f"Unknown provider: {new_name}"}), 400

    # Reload .env to pick up freshly edited keys
    load_dotenv(os.path.join(RUNDIR, ".env"))
    load_dotenv(os.path.join(BASEDIR, ".env"))
    RESEND_KEY = os.getenv("RESEND_API_KEY", "")
    ZEPTO_KEY = os.getenv("ZEPTOMAIL_API_KEY", "")
    _key_map["resend"] = RESEND_KEY
    _key_map["zeptomail"] = ZEPTO_KEY

    key = _resolve_api_key(new_name)
    if not key:
        return jsonify({
            "success": False,
            "error": f"No API key configured for {new_name}. Add it via Settings or .env and switch again.",
        }), 400

    try:
        provider = create_provider(new_name, key)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    PROVIDER_NAME = new_name
    ACTIVE_API_KEY = key
    _domain_cache = []
    _domain_cache_ts = 0.0

    resolved_sender = get_default_sender_email()
    logger.info(f"Provider switched to {provider.name}")

    return jsonify({
        "success": True,
        "provider": provider.name,
        "message": f"Switched to {provider.name}.",
        "verified_domains": [],
        "sender_email": resolved_sender,
    })


# ── API Key Management ────────────────────────────────────────────

@app.route("/api/provider-keys", methods=["GET"])
@login_required
def list_provider_keys():
    """List all stored API keys (masked)."""
    all_db_keys = get_all_provider_keys()
    result = {}
    for prov_id in PROVIDERS:
        env_key = _key_map.get(prov_id, "")
        db_key = all_db_keys.get(prov_id, "")
        effective = db_key or env_key
        result[prov_id] = {
            "has_key": bool(effective),
            "key_source": "database" if db_key else ("env" if env_key else "none"),
            "key_preview": _mask_key(effective) if effective else "",
        }
    return jsonify({"success": True, "keys": result})


@app.route("/api/provider-keys/<provider_id>", methods=["POST"])
@login_required
def set_provider_key(provider_id: str):
    """Save an API key for a provider and optionally auto-switch to it."""
    provider_id = provider_id.lower()
    if provider_id not in PROVIDERS:
        return jsonify({"success": False, "error": f"Unknown provider: {provider_id}"}), 400

    data = request.get_json()
    api_key = (data.get("api_key") or "").strip()
    auto_switch = data.get("auto_switch", True)

    if not api_key:
        return jsonify({"success": False, "error": "API key cannot be empty."}), 400

    # Validate by trying to create the provider
    try:
        test_provider = create_provider(provider_id, api_key)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    # Save the key to database
    save_provider_key(provider_id, api_key)
    logger.info(f"API key saved for {provider_id}")

    # Auto-switch if requested
    if auto_switch:
        global provider, PROVIDER_NAME, ACTIVE_API_KEY, _domain_cache, _domain_cache_ts
        provider = test_provider
        PROVIDER_NAME = provider_id
        ACTIVE_API_KEY = api_key
        _domain_cache = []
        _domain_cache_ts = 0.0

        resolved_sender = get_default_sender_email()

        return jsonify({
            "success": True,
            "message": f"API key saved and switched to {test_provider.name}.",
            "switched": True,
            "provider": test_provider.name,
            "provider_id": provider_id,
            "verified_domains": [],
            "sender_email": resolved_sender,
            "key_preview": _mask_key(api_key),
        })

    return jsonify({
        "success": True,
        "message": f"API key saved for {PROVIDER_META.get(provider_id, {}).get('label', provider_id)}.",
        "switched": False,
        "key_preview": _mask_key(api_key),
    })


@app.route("/api/provider-keys/<provider_id>", methods=["DELETE"])
@login_required
def remove_provider_key(provider_id: str):
    """Remove a stored API key for a provider."""
    provider_id = provider_id.lower()
    if provider_id not in PROVIDERS:
        return jsonify({"success": False, "error": f"Unknown provider: {provider_id}"}), 400

    deleted = delete_provider_key(provider_id)
    if deleted:
        logger.info(f"API key removed for {provider_id}")
        # If removing the active provider's key, try to fall back
        if provider_id == PROVIDER_NAME:
            env_key = _key_map.get(provider_id, "")
            if not env_key:
                _init_provider()

    return jsonify({
        "success": True,
        "message": f"API key removed for {provider_id}.",
        "active_provider": provider.name if provider else "None",
    })


@app.route("/api/provider-keys/<provider_id>/test", methods=["POST"])
@login_required
def test_provider_key(provider_id: str):
    """Test an API key by fetching domains (doesn't save it)."""
    provider_id = provider_id.lower()
    if provider_id not in PROVIDERS:
        return jsonify({"success": False, "error": f"Unknown provider: {provider_id}"}), 400

    data = request.get_json()
    api_key = (data.get("api_key") or "").strip()
    if not api_key:
        return jsonify({"success": False, "error": "API key cannot be empty."}), 400

    try:
        test_prov = create_provider(provider_id, api_key)
        domains = test_prov.get_verified_domains()
        return jsonify({
            "success": True,
            "message": f"Key is valid. Found {len(domains)} domain(s).",
            "domains": domains,
        })
    except (APIError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Connection error: {e}"}), 500


# ── Domains ────────────────────────────────────────────────────────

@app.route("/api/verified-domains")
@login_required
def verified_domains_route():
    """Return the list of verified sending domains for the active provider."""
    force = request.args.get("refresh", "").lower() in ("1", "true", "yes")
    domains = fetch_verified_domains(force)
    resolved_sender = get_default_sender_email()
    return jsonify({
        "success": True,
        "provider": provider.name if provider else "None",
        "domains": domains,
        "sender_email": resolved_sender or "",
    })


@app.route("/api/operations")
@login_required
def operations_route():
    return jsonify({"success": True, "operations": _operations_snapshot()})


@app.route("/api/check-sender", methods=["POST"])
@login_required
def check_sender_route():
    """Validate whether a sender email is allowed for the active provider."""
    data = request.get_json()
    sender = data.get("email", "").strip()
    if not is_valid_email(sender):
        return jsonify({"success": False, "error": "Invalid email."})
    allowed, reason = is_sender_domain_allowed(sender)
    return jsonify({"success": True, "allowed": allowed, "reason": reason})


# ── Single Send ────────────────────────────────────────────────────

@app.route("/api/send-email", methods=["POST"])
@login_required
def send_email_route():
    if not provider:
        return jsonify({"success": False, "error": "No email provider configured."}), 500

    data = request.form
    files = request.files.getlist("attachments")

    to_email = data.get("to_email", "").strip()
    to_name = data.get("to_name", "").strip()
    subject = data.get("subject", "").strip()
    html_content = normalize_email_html(data.get("html_content", ""))

    if not all([to_email, subject, html_content]):
        return jsonify({"success": False, "error": "To, Subject, and Content are required."}), 400
    if not is_valid_email(to_email):
        return jsonify({"success": False, "error": f"Invalid email: {to_email}"}), 400

    from_email, from_name = _resolve_sender(data.get("from_email", ""), data.get("from_name", ""), PROVIDER_NAME)

    allowed, reason = is_sender_domain_allowed(from_email)
    if not allowed:
        return jsonify({"success": False, "error": reason}), 400

    attachments = encode_attachments(files)

    cc = [e.strip() for e in data.get("cc", "").split(",") if e.strip() and is_valid_email(e.strip())]
    bcc = [e.strip() for e in data.get("bcc", "").split(",") if e.strip() and is_valid_email(e.strip())]

    try:
        logger.info(f"Single send → {to_email} via {provider.name}")
        frozen_provider_id, frozen_key, single_provider = _get_provider_snapshot(PROVIDER_NAME, ACTIVE_API_KEY)
        job_id = f"SingleSend-{uuid.uuid4().hex[:8]}"
        create_job(job_id, single_provider.name, 1, subject, from_email, from_name, 0)
        single_provider.send(from_email, from_name, to_email, to_name, subject, html_content,
                             attachments=attachments, cc=cc or None, bcc=bcc or None)
        complete_job(job_id, 1, 0, 1)
        return jsonify({"success": True, "message": "Email sent."})
    except APIError as e:
        if 'job_id' in locals():
            log_failure(job_id, to_email, e.message)
            complete_job(job_id, 0, 1, 1, error=e.message)
        logger.error(f"Send failed ({e.status_code}): {e.message}")
        return jsonify({"success": False, "error": e.message}), e.status_code or 500
    except Exception as e:
        if 'job_id' in locals():
            log_failure(job_id, to_email, str(e))
            complete_job(job_id, 0, 1, 1, error=str(e))
        logger.error(f"Unexpected: {e}")
        return jsonify({"success": False, "error": "Internal error."}), 500


# ── Upload Recipients ─────────────────────────────────────────────

@app.route("/api/upload-recipients", methods=["POST"])
@login_required
def upload_recipients_route():
    file = request.files.get("file")
    if not file:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    content = file.read()
    if not content:
        return jsonify({"success": False, "error": "Empty file."}), 400

    recipients = []
    columns = []
    invalid_count = 0

    try:
        if ext == ".xlsx":
            wb = openpyxl.load_workbook(BytesIO(content), read_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows()
            h = next(rows_iter)
            raw_headers = [str(c.value or "").strip() for c in h]
            if not any(i.lower() == "email" for i in raw_headers):
                wb.close()
                return jsonify({"success": False, "error": "Missing 'Email' column."}), 400

            col_map = {i: normalize_column(h) for i, h in enumerate(raw_headers) if h}
            columns = sorted(set(col_map.values()))

            for row in rows_iter:
                vals = {col_map[i]: str(row[i].value or "").strip() for i in col_map if i < len(row)}
                email = vals.get("Email", "")
                if not email or not is_valid_email(email):
                    invalid_count += 1
                    continue
                if len(recipients) >= MAX_RECIPIENTS:
                    break
                rcpt = {normalize_column(n): vals.get(normalize_column(n), "") for n in raw_headers if n}
                recipients.append(rcpt)
            wb.close()

        elif ext == ".xls":
            book = xlrd.open_workbook(file_contents=content)
            ws = book.sheet_by_index(0)
            raw_headers = [str(ws.cell_value(0, i) or "").strip() for i in range(ws.ncols)]
            if not any(i.lower() == "email" for i in raw_headers):
                return jsonify({"success": False, "error": "Missing 'Email' column."}), 400

            col_map = {i: normalize_column(h) for i, h in enumerate(raw_headers) if h}
            columns = sorted(set(col_map.values()))

            for r in range(1, ws.nrows):
                vals = {col_map[i]: str(ws.cell_value(r, i) or "").strip() for i in col_map if i < ws.ncols}
                email = vals.get("Email", "")
                if not email or not is_valid_email(email):
                    invalid_count += 1
                    continue
                if len(recipients) >= MAX_RECIPIENTS:
                    break
                rcpt = {normalize_column(n): vals.get(normalize_column(n), "") for n in raw_headers if n}
                recipients.append(rcpt)

        elif ext == ".txt":
            columns = ["Email"]
            for line in content.decode("utf-8", "ignore").splitlines():
                email = line.strip()
                if not email:
                    continue
                if not is_valid_email(email):
                    invalid_count += 1
                    continue
                if len(recipients) >= MAX_RECIPIENTS:
                    break
                recipients.append({"Email": email})
        else:
            return jsonify({"success": False, "error": "Unsupported file type. Use .xlsx, .xls, or .txt."}), 400

        if not recipients:
            return jsonify({"success": False, "error": "No valid emails found."}), 400

        if invalid_count > 0:
            logger.info(f"Skipped {invalid_count} invalid emails in upload")

        logger.info(f"Upload: {len(recipients)} recipients, columns={columns}")

        return jsonify({
            "success": True,
            "count": len(recipients),
            "recipients": recipients,
            "columns": columns,
            "file_type": "excel" if ext in (".xlsx", ".xls") else "text",
            "invalid_skipped": invalid_count,
        })

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({"success": False, "error": "Upload processing error."}), 500


# ── Email Preview ──────────────────────────────────────────────────

@app.route("/api/preview-email", methods=["POST"])
@login_required
def preview_email_route():
    """Render a preview of the email for the first recipient."""
    data = request.get_json()
    subject_tmpl = data.get("subject", "").strip()
    html_tmpl = normalize_email_html(data.get("html_content", ""))
    recipient = data.get("recipient", {})
    from_email_tmpl = data.get("from_email", "").strip()
    from_name_tmpl = data.get("from_name", "").strip()

    context = dict(recipient) if isinstance(recipient, dict) else {}
    rendered_subject = process_template(subject_tmpl, context)
    rendered_html = normalize_email_html(process_template(html_tmpl, context))
    rendered_from = process_template(from_email_tmpl, context) if from_email_tmpl else ""
    rendered_name = process_template(from_name_tmpl, context) if from_name_tmpl else ""
    rendered_from, rendered_name = _resolve_sender(rendered_from, rendered_name, PROVIDER_NAME)

    return jsonify({
        "success": True,
        "preview": {
            "from_email": rendered_from,
            "from_name": rendered_name,
            "to_email": context.get("Email", ""),
            "subject": rendered_subject,
            "html": rendered_html,
        },
    })


# ── Bulk Send ──────────────────────────────────────────────────────

@app.route("/api/send-bulk", methods=["POST"])
@login_required
def send_bulk_route():
    if not provider:
        return jsonify({"success": False, "error": "No provider configured."}), 500

    data = request.form
    files = request.files.getlist("attachments")
    recipients_str = data.get("recipients", "")
    subject_tmpl = data.get("subject", "").strip()
    html_tmpl = normalize_email_html(data.get("html_content", ""))
    interval_str = str(data.get("interval", DEFAULT_INTERVAL))
    from_email_tmpl = "" if _sender_locked(PROVIDER_NAME) else data.get("from_email_template", "").strip()
    from_name_tmpl = "" if _sender_locked(PROVIDER_NAME) else data.get("from_name_template", "").strip()

    if not all([recipients_str, subject_tmpl, html_tmpl]):
        return jsonify({"success": False, "error": "Recipients, Subject, and Content are required."}), 400

    try:
        recipients = json.loads(recipients_str)
        if not isinstance(recipients, list) or not len(recipients):
            return jsonify({"success": False, "error": "Invalid recipients data."}), 400
    except (json.JSONDecodeError, TypeError):
        return jsonify({"success": False, "error": "Invalid recipients data."}), 400

    if len(recipients) > MAX_RECIPIENTS:
        return jsonify({"success": False, "error": f"Max {MAX_RECIPIENTS} recipients."}), 400

    interval = max(MIN_INTERVAL, min(MAX_INTERVAL, int(interval_str)))
    common_attachments = encode_attachments(files)

    job_id = f"BulkSend-{uuid.uuid4().hex[:8]}"
    from_email, from_name = _resolve_sender(from_email_tmpl, from_name_tmpl, PROVIDER_NAME)

    # Check sender domain if not a template
    if "{{" not in from_email:
        allowed, reason = is_sender_domain_allowed(from_email)
        if not allowed:
            return jsonify({"success": False, "error": reason}), 400

    try:
        frozen_provider_id, frozen_key, bulk_provider = _get_provider_snapshot(PROVIDER_NAME, ACTIVE_API_KEY)
        create_job(job_id, bulk_provider.name, len(recipients), subject_tmpl, from_email, from_name, interval)

        thread = threading.Thread(
            target=_bulk_send_worker,
            args=(job_id, recipients, subject_tmpl, html_tmpl, interval,
                  common_attachments, from_email_tmpl, from_name_tmpl, frozen_provider_id, frozen_key),
            name=f"BulkSend-{job_id}",
        )
        active_threads[job_id] = thread
        thread.start()

        est = len(recipients) * interval
        logger.info(f"Bulk job {job_id}: {len(recipients)} emails, {interval}s interval, ~{est}s est.")

        return jsonify({
            "success": True,
            "job_id": job_id,
            "message": f"Campaign started ({len(recipients)} emails).",
            "details": {"estimated_seconds": est, "interval": interval, "total": len(recipients)},
        })
    except Exception as e:
        logger.error(f"Bulk init error: {e}")
        return jsonify({"success": False, "error": "Internal error."}), 500


def _bulk_send_worker(
    job_id, recipients, subject_tmpl, html_tmpl, interval,
    attachments, from_email_tmpl, from_name_tmpl, provider_id, provider_key,
):
    """Background worker — sends emails one-by-one with pause/cancel support."""
    logger.info(f"[{job_id}] Worker started ({len(recipients)} recipients)")
    success = 0
    failed = 0
    processed = 0
    try:
        try:
            worker_provider = create_provider(provider_id, provider_key)
        except Exception as e:
            complete_job(job_id, 0, len(recipients), 0, error=str(e))
            logger.error(f"[{job_id}] Provider snapshot error: {e}")
            return

        for i, rcpt in enumerate(recipients):
            job = get_job(job_id)
            if not job:
                logger.warning(f"[{job_id}] Job deleted, stopping.")
                return

            if job["status"] == "cancelled":
                logger.info(f"[{job_id}] Cancelled at {processed}")
                break

            while job["status"] == "paused":
                time.sleep(2)
                job = get_job(job_id)
                if not job or job["status"] == "cancelled":
                    break

            if not job or job["status"] == "cancelled":
                break

            try:
                if isinstance(rcpt, dict):
                    email_addr = (rcpt.get("Email") or "").strip()
                else:
                    raise ValueError("Invalid recipient record.")
                if not email_addr or not is_valid_email(email_addr):
                    raise ValueError(f"Bad email: {email_addr}")
            except ValueError as e:
                failed += 1
                processed += 1
                log_failure(job_id, str(rcpt), str(e))
                update_job(job_id, processed=processed, failed_count=failed, current_email=str(e))
                continue

            ctx = dict(rcpt)
            subj = process_template(subject_tmpl, ctx)
            body = normalize_email_html(process_template(html_tmpl, ctx))
            from_email = process_template(from_email_tmpl, ctx).strip() if from_email_tmpl else ""
            from_name = process_template(from_name_tmpl, ctx).strip() if from_name_tmpl else ""
            from_email, from_name = _resolve_sender(from_email, from_name, provider_id)
            name = ctx.get("Name") or ctx.get("First_Name") or ""

            try:
                worker_provider.send(from_email, from_name, email_addr, name, subj, body, attachments=attachments)
                success += 1
                logger.debug(f"[{job_id}] ✓ {email_addr}")
            except APIError as e:
                failed += 1
                log_failure(job_id, email_addr, e.message)
                logger.debug(f"[{job_id}] ✗ {email_addr}: {e.message}")
            except Exception as e:
                failed += 1
                log_failure(job_id, email_addr, str(e))
                logger.error(f"[{job_id}] ✗ {email_addr}: {e}")

            processed += 1
            update_job(
                job_id,
                processed=processed,
                success_count=success,
                failed_count=failed,
                current_email=email_addr,
            )

            if i < len(recipients) - 1:
                t0 = time.time()
                while time.time() - t0 < max(interval, 1):
                    job = get_job(job_id)
                    if not job or job["status"] in ("cancelled",):
                        break
                    time.sleep(0.5)

        final_job = get_job(job_id)
        if final_job and final_job.get("status") == "cancelled":
            update_job(
                job_id,
                success_count=success,
                failed_count=failed,
                processed=processed,
                current_email="Cancelled",
            )
            logger.info(f"[{job_id}] Cancelled. ✓{success} ✗{failed}/{processed} processed")
        else:
            complete_job(job_id, success, failed, processed)
            logger.info(f"[{job_id}] Done. ✓{success} ✗{failed}/{processed} processed")
    finally:
        active_threads.pop(job_id, None)


# ── Bulk Status & Control ─────────────────────────────────────────

@app.route("/api/bulk-status/<job_id>")
@login_required
def bulk_status_route(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found."}), 404
    failures = get_failures(job_id)
    total = job["total"]
    pct = min(int(job["processed"] / total * 100), 100) if total > 0 else 0
    return jsonify({
        "success": True,
        "status": {
            **job,
            "completion_percentage": pct,
            "in_progress": job["status"] in ("running", "paused"),
            "failed_emails": [{"email": f["email"], "error": f["error"]} for f in failures],
        },
    })


@app.route("/api/job/<job_id>/pause", methods=["POST"])
@login_required
def pause_job_route(job_id):
    if pause_job(job_id):
        return jsonify({"success": True, "message": "Job paused."})
    return jsonify({"success": False, "error": "Job cannot be paused."}), 400


@app.route("/api/job/<job_id>/resume", methods=["POST"])
@login_required
def resume_job_route(job_id):
    if resume_job(job_id):
        return jsonify({"success": True, "message": "Job resumed."})
    return jsonify({"success": False, "error": "Job cannot be resumed."}), 400


@app.route("/api/job/<job_id>/cancel", methods=["POST"])
@login_required
def cancel_job_route(job_id):
    if cancel_job(job_id):
        return jsonify({"success": True, "message": "Job cancelled."})
    return jsonify({"success": False, "error": "Job cannot be cancelled."}), 400


@app.route("/api/jobs")
@login_required
def list_jobs_route():
    try:
        limit = int(request.args.get("limit", "1000"))
    except ValueError:
        limit = 1000
    jobs = get_all_jobs(limit if limit > 0 else None)
    return jsonify({"success": True, "jobs": [_serialize_job(job) for job in jobs]})


@app.route("/api/jobs/<job_id>")
@login_required
def get_job_route(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found."}), 404
    return jsonify({"success": True, "job": _serialize_job(job, include_failures=True)})


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
@login_required
def delete_job_route(job_id):
    if delete_job(job_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Job not found."}), 404


# ── Scheduled Jobs ─────────────────────────────────────────────────

@app.route("/api/schedule", methods=["POST"])
@login_required
def schedule_job_route():
    """Schedule a single email or campaign for later."""
    if not provider:
        return jsonify({"success": False, "error": "No provider configured."}), 500

    data = request.get_json()
    job_type = data.get("type", "single")
    send_at_str = data.get("send_at")

    if not send_at_str:
        return jsonify({"success": False, "error": "send_at is required."}), 400

    try:
        if send_at_str.endswith("+00:00"):
            send_at_str = send_at_str
        _dt = datetime.fromisoformat(send_at_str)
        send_at = _dt.timestamp()
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Invalid send_at: {e}"}), 400

    if send_at < time.time() + 30:
        return jsonify({"success": False, "error": "Scheduled time must be at least 30 seconds in the future."}), 400

    payload = data.get("payload", {})
    payload["_provider_id"] = PROVIDER_NAME

    if job_type == "single":
        if not all(payload.get(k) for k in ("to_email", "subject", "html_content")):
            return jsonify({"success": False, "error": "payload must include to_email, subject, html_content."}), 400
        if not is_valid_email(payload["to_email"]):
            return jsonify({"success": False, "error": f"Invalid email: {payload['to_email']}"}), 400
        payload["html_content"] = normalize_email_html(payload.get("html_content", ""))
        payload["from_email"], payload["from_name"] = _resolve_sender(
            payload.get("from_email", ""),
            payload.get("from_name", ""),
            PROVIDER_NAME,
        )

    elif job_type == "campaign":
        if not all(payload.get(k) for k in ("recipients", "subject", "html_content")):
            return jsonify({"success": False, "error": "payload must include recipients, subject, html_content."}), 400
        if not isinstance(payload.get("recipients"), list) or not payload["recipients"]:
            return jsonify({"success": False, "error": "recipients must be a non-empty list."}), 400
        payload["html_content"] = normalize_email_html(payload.get("html_content", ""))
        if _sender_locked(PROVIDER_NAME):
            payload["from_email_template"] = ""
            payload["from_name_template"] = ""
    else:
        return jsonify({"success": False, "error": f"Unknown type: {job_type}"}), 400

    sched_id = f"sched-{uuid.uuid4().hex[:8]}"
    job = create_scheduled_job(sched_id, job_type, send_at, payload)
    logger.info(f"Scheduled {job_type} job {sched_id} for {send_at}")

    return jsonify({
        "success": True,
        "job": job,
        "message": f"Scheduled for {datetime.fromtimestamp(send_at).isoformat()}",
    })


@app.route("/api/scheduled-jobs")
@login_required
def list_scheduled_jobs_route():
    try:
        limit = int(request.args.get("limit", "1000"))
    except ValueError:
        limit = 1000
    jobs = get_all_scheduled_jobs(limit if limit > 0 else None)
    return jsonify({"success": True, "jobs": [_serialize_scheduled_job(job) for job in jobs]})


@app.route("/api/scheduled-jobs/<sched_id>")
@login_required
def get_scheduled_job_route(sched_id):
    job = get_scheduled_job(sched_id)
    if not job:
        return jsonify({"success": False, "error": "Not found."}), 404
    return jsonify({"success": True, "job": _serialize_scheduled_job(job)})


@app.route("/api/scheduled-jobs/<sched_id>/cancel", methods=["POST"])
@login_required
def cancel_scheduled_job_route(sched_id):
    if cancel_scheduled_job(sched_id):
        return jsonify({"success": True, "message": "Scheduled job cancelled."})
    return jsonify({"success": False, "error": "Cannot cancel (not pending or not found)."}), 400


@app.route("/api/scheduled-jobs/<sched_id>", methods=["PUT"])
@login_required
def update_scheduled_job_route(sched_id):
    """Edit a pending scheduled job's time or payload."""
    data = request.get_json()
    send_at = None
    payload = data.get("payload")
    send_at_str = data.get("send_at")

    if send_at_str:
        try:
            if send_at_str.endswith("+00:00"):
                send_at_str = send_at_str
            _dt = datetime.fromisoformat(send_at_str)
            s = _dt.timestamp()
            if s < time.time() + 30:
                return jsonify({"success": False, "error": "Time must be > 30s in the future."}), 400
            send_at = s
        except (ValueError, TypeError) as e:
            return jsonify({"success": False, "error": f"Invalid send_at: {e}"}), 400

    if update_scheduled_job(sched_id, send_at=send_at, payload=payload):
        job = get_scheduled_job(sched_id)
        return jsonify({"success": True, "message": "Updated.", "job": job})
    return jsonify({"success": False, "error": "Cannot edit (not pending or not found)."}), 400


@app.route("/api/scheduled-jobs/<sched_id>", methods=["DELETE"])
@login_required
def delete_scheduled_job_route(sched_id):
    if delete_scheduled_job(sched_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found."}), 404


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "False").lower() in ("1", "true")
    logger.info(
        f"GhostMail starting — Provider: {provider.name if provider else 'NONE'} | Debug: {debug}"
    )
    app.run(host="0.0.0.0", port=5000, debug=debug)
