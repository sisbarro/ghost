"""
providers.py — Email provider abstraction layer.
Supports the two production providers used by GhostMail: Resend and ZeptoMail.
Uses stdlib urllib so the app has zero C-extension email dependencies.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)


def _normalize_attachments(attachments: list[dict] | None) -> list[dict]:
    """Drop empty attachment placeholders before calling provider APIs."""
    cleaned = []
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        filename = str(attachment.get("filename") or attachment.get("name") or "").strip()
        content = attachment.get("content")
        path = str(attachment.get("path") or "").strip()
        if not filename:
            continue
        if isinstance(content, str):
            content = content.strip()
        if not content and not path:
            continue
        cleaned.append({**attachment, "filename": filename, "content": content, "path": path})
    return cleaned


def _html_to_text(html: str) -> str:
    """Create a plain-text fallback from HTML for providers that accept both bodies."""
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class APIError(Exception):
    """Raised when an email-provider API returns a non-2xx status."""

    def __init__(self, status_code: int, body: str, message: str):
        self.status_code = status_code
        self.body = body
        self.message = message
        super().__init__(message)


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @abstractmethod
    def send(
        self,
        from_addr: str,
        from_name: str,
        to_addr: str,
        to_name: str,
        subject: str,
        html_body: str,
        attachments: list[dict] = None,
        cc: list = None,
        bcc: list = None,
    ):
        """
        Send a single email. Returns the provider's response dict.
        Raises APIError on provider failure.
        """

    @staticmethod
    def _post_json(url: str, headers: dict, payload: dict, timeout: int = 30):
        """POST JSON to *url*; returns parsed response body. Raises APIError on non-2xx."""
        data = json.dumps(payload).encode("utf-8")
        hdrs = {"User-Agent": "GhostMail/1.4", **headers}
        req = Request(url, data=data, headers=hdrs, method="POST")
        try:
            resp = urlopen(req, timeout=timeout)
            return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise APIError(e.code, body, _extract_message(body))
        except URLError as e:
            raise APIError(0, str(e), "Network error — check your connection.")

    @staticmethod
    def _get_json(url: str, headers: dict, timeout: int = 30):
        """GET *url*; returns parsed JSON response. Raises APIError on non-2xx."""
        hdrs = {"User-Agent": "GhostMail/1.4", **headers}
        req = Request(url, headers=hdrs)
        try:
            resp = urlopen(req, timeout=timeout)
            return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise APIError(e.code, body, _extract_message(body))
        except URLError as e:
            raise APIError(0, str(e), "Network error — check your connection.")

    def get_verified_domains(self) -> list[dict]:
        """
        Query the provider API for verified/allowed sending domains.
        Returns list of dicts: [{"domain": "example.com", "status": "verified"}, ...]
        """
        return []


def _extract_message(raw: str) -> str:
    """Best-effort extraction of a human-readable message from a JSON error body."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            msg = data.get("message") or data.get("error")
            if isinstance(msg, str):
                return msg
            if isinstance(msg, dict):
                return msg.get("message", str(msg))
            details = data.get("details")
            if isinstance(details, list):
                return "; ".join(d.get("message", str(d)) for d in details)
        return str(data)
    except Exception:
        return raw[:300] if raw else "Unknown error"


# ═══════════════════════════════════════════════════════════════════════
#  RESEND
# ═══════════════════════════════════════════════════════════════════════

class ResendProvider(EmailProvider):
    """Resend (resend.com) email provider."""

    ENDPOINT = "https://api.resend.com/emails"
    DOMAINS_ENDPOINT = "https://api.resend.com/domains"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Resend API key is required.")
        self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @property
    def name(self) -> str:
        return "Resend"

    def get_verified_domains(self) -> list[dict]:
        """Fetch verified domains from Resend API (GET /domains)."""
        try:
            resp = self._get_json(self.DOMAINS_ENDPOINT, self._headers)
            domains = resp.get("data") if isinstance(resp, dict) else resp
            return [
                {
                    "domain": d.get("name"),
                    "status": d.get("status", "unknown"),
                    "region": d.get("region"),
                }
                for d in (domains or [])
                if isinstance(d, dict)
            ]
        except (APIError, Exception) as e:
            logger.warning(f"Resend domain fetch failed: {e}")
            return []

    def send(
        self,
        from_addr,
        from_name,
        to_addr,
        to_name,
        subject,
        html_body,
        attachments=None,
        cc=None,
        bcc=None,
    ):
        sender = f"{from_name} <{from_addr}>" if from_name else from_addr
        to_value = f"{to_name} <{to_addr}>" if to_name else to_addr
        payload = {
            "from": sender,
            "to": [to_value],
            "subject": subject,
            "html": html_body,
        }
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        safe_attachments = _normalize_attachments(attachments)
        if safe_attachments:
            payload["attachments"] = [
                {"filename": a["filename"], "content": a["content"]}
                for a in safe_attachments
            ]
        return self._post_json(self.ENDPOINT, self._headers, payload)


# ═══════════════════════════════════════════════════════════════════════
#  ZEPTOMAIL
# ═══════════════════════════════════════════════════════════════════════

class ZeptoMailProvider(EmailProvider):
    """ZeptoMail (Zoho) email provider."""

    ENDPOINT = "https://api.zeptomail.com/v1.1/email"
    BOUNCE_ADDR_ENDPOINT = "https://api.zeptomail.com/v1.1/bounceaddress"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("ZeptoMail API key is required.")
        self.api_key = api_key
        self._headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

    @property
    def name(self) -> str:
        return "ZeptoMail"

    def get_verified_domains(self) -> list[dict]:
        """Attempt to discover verified domains from ZeptoMail bounce addresses."""
        try:
            resp = self._get_json(self.BOUNCE_ADDR_ENDPOINT, self._headers)
            seen = set()
            result = []
            addresses = resp.get("data") if isinstance(resp, dict) else resp
            if isinstance(addresses, list):
                for entry in addresses:
                    if isinstance(entry, dict):
                        domain = None
                        for key in ("bounce_address", "bounceAddress"):
                            addr = entry.get(key)
                            if isinstance(addr, (str, dict)):
                                email = addr if isinstance(addr, str) else addr.get("address") or addr.get("email", "")
                                if "@" in str(email):
                                    domain = str(email).split("@")[-1].strip().lower()
                                    break
                        if domain and domain not in seen:
                            seen.add(domain)
                            result.append({"domain": domain, "status": "verified"})
            return result
        except (APIError, Exception) as e:
            logger.warning(f"ZeptoMail domain fetch failed: {e}")
            return []

    def send(
        self,
        from_addr,
        from_name,
        to_addr,
        to_name,
        subject,
        html_body,
        attachments=None,
        cc=None,
        bcc=None,
    ):
        from_payload = {"address": from_addr}
        if from_name:
            from_payload["name"] = from_name

        to_payload = {"address": to_addr}
        if to_name:
            to_payload["name"] = to_name

        payload = {
            "from": from_payload,
            "to": [{"email_address": to_payload}],
            "subject": subject,
            "htmlbody": html_body,
        }

        text_body = _html_to_text(html_body)
        if text_body:
            payload["textbody"] = text_body

        if cc:
            payload["cc"] = [{"email_address": {"address": c}} for c in cc if c]
        if bcc:
            payload["bcc"] = [{"email_address": {"address": b}} for b in bcc if b]
        safe_attachments = _normalize_attachments(attachments)
        if safe_attachments:
            payload["attachments"] = [
                {
                    "name": a["filename"],
                    "content": a["content"],
                    "mime_type": a.get("mimetype", "application/octet-stream"),
                }
                for a in safe_attachments
            ]
        return self._post_json(self.ENDPOINT, self._headers, payload)


# ═══════════════════════════════════════════════════════════════════════
#  PROVIDER REGISTRY & FACTORY
# ═══════════════════════════════════════════════════════════════════════

PROVIDERS = {
    "resend": ResendProvider,
    "zeptomail": ZeptoMailProvider,
}

# Metadata for each provider (used by frontend)
PROVIDER_META = {
    "resend":   {"label": "Resend",   "icon": "bolt",                  "color": "yellow"},
    "zeptomail":{"label": "ZeptoMail","icon": "envelope-circle-check", "color": "blue"},
}


def create_provider(provider_name: str, api_key: str) -> EmailProvider:
    """
    Factory function to instantiate the correct provider.

    Args:
        provider_name: 'resend' or 'zeptomail'
        api_key: The API key for that provider
    """
    cls = PROVIDERS.get(provider_name.lower())
    if cls is None:
        raise ValueError(f"Unknown provider '{provider_name}'. Supported: {', '.join(PROVIDERS.keys())}")
    return cls(api_key)
