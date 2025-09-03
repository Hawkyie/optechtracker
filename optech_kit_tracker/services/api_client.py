# services/api_client.py
import os
import requests
from app_config import load_config

API_URL   = os.getenv("OPTECH_API_URL", "https://kit-tracker.peacemosquitto.workers.dev")
API_TOKEN = os.getenv("OPTECH_API_TOKEN", "Bearer 63T-nAch05-p3W5-lIn60t")

MEDIA_BASE = os.getenv("OPTECH_MEDIA_BASE", "").rstrip("/")
if not MEDIA_BASE:
    # If your server serves images at a different path (e.g. /media/<id>),
    # change "/images" to the right one.
    MEDIA_BASE = f"{API_URL.rstrip('/')}/images"

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
    if not image_id_or_url:
        return None
    s = str(image_id_or_url).strip()
    if s.startswith(("http://", "https://")):
        return s
    # Use the code/default media base
    return f"{MEDIA_BASE}/{s}"

# services/api_client.py
import os
from app_config import load_config

API_URL   = os.getenv("OPTECH_API_URL", "https://kit-tracker.peacemosquitto.workers.dev")

def image_url_candidates(image_id_or_url: str) -> list[str]:
    """
    Return a list of plausible URLs (most specific first) for a given image ref.
    If ref is already a full URL -> try that only.
    Otherwise, build candidates against the configured media base or API base.
    """
    if not image_id_or_url:
        return []

    s = str(image_id_or_url).strip()
    if s.startswith(("http://", "https://")):
        return [s]

    cfg       = load_config()
    media_base = (cfg.get("media_base") or "").rstrip("/")
    api_base   = (cfg.get("api_url") or API_URL).rstrip("/")
    base = media_base or api_base

    # Common server patterns — put the routes you expect near the top
    patterns = [
        "{base}/images/{id}/raw",
        "{base}/images/{id}/download",
        "{base}/images/{id}/content",
        "{base}/images/{id}",
        "{base}/image/{id}/raw",
        "{base}/image/{id}",
        "{base}/media/{id}/raw",
        "{base}/media/{id}",
        "{base}/img/{id}",
        "{base}/payloads/{id}/image",
    ]

    return [p.format(base=base.rstrip("/"), id=s) for p in patterns]


