# services/api_client.py
import os
import requests
from app_config import load_config

API_URL   = os.getenv("OPTECH_API_URL", "https://kit-tracker.peacemosquitto.workers.dev")
API_TOKEN = os.getenv("OPTECH_API_TOKEN", "")

def _auth_header():
    cfg_token = (load_config().get("api_token") or "").strip()
    token = (API_TOKEN or cfg_token).strip()
    if not token:
        return {}
    return {"Authorization": token if token.lower().startswith("bearer ")
            else f"Bearer {token}"}

def fetch_payloads():
    headers = _auth_header()
    resp = requests.get(API_URL, headers=headers, timeout=8)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []

# ---------- NEW: robust image URL resolver ----------

def _is_image_url(url: str) -> bool:
    """True if the URL responds with Content-Type: image/* (using auth)."""
    try:
        r = requests.head(url, headers=_auth_header(), timeout=6, allow_redirects=True)
        if not r.ok:
            return False
        ct = (r.headers.get("content-type") or "").lower()
        return ct.startswith("image/")
    except Exception:
        return False

# services/api_client.py (only this function needs replacing)
from app_config import load_config
import os

API_URL   = os.getenv("OPTECH_API_URL", "https://kit-tracker.peacemosquitto.workers.dev")

def build_media_url(image_id_or_url: str) -> str | None:
    """
    Resolve an image ref to a URL, without verifying it up-front.
    Priority:
      1) If ref is already a full URL -> return as-is.
      2) If Settings has Media Base URL -> <media_base>/<id>.
      3) Fallback guess under the API URL -> <api>/media/<id>.
    """
    if not image_id_or_url:
        return None

    s = str(image_id_or_url).strip()
    if s.startswith(("http://", "https://")):
        return s

    cfg = load_config()
    media_base = (cfg.get("media_base") or "").rstrip("/")
    if media_base:
        return f"{media_base}/{s}"

    api_base = (cfg.get("api_url") or API_URL).rstrip("/")
    # If your backend uses a different path (e.g., /images/<id>), change "media" below:
    return f"{api_base}/media/{s}"

