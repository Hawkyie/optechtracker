# services/api_client.py
import os
import requests
from app_config import load_config

API_URL   = os.getenv("OPTECH_API_URL", "https://kit-tracker.peacemosquitto.workers.dev").rstrip("/")
API_TOKEN = os.getenv("OPTECH_API_TOKEN", "Bearer 63T-nAch05-p3W5-lIn60t")

# If you ever go back to “last image from API” flow:
MEDIA_BASE = os.getenv("OPTECH_MEDIA_BASE", "").rstrip("/")
if not MEDIA_BASE:
    MEDIA_BASE = f"{API_URL}/images"

def _auth_header():
    # prefer value in settings over env default
    cfg_token = (load_config().get("api_token") or "").strip()
    token = (cfg_token or API_TOKEN).strip()
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

# Kept for future, but handlers now use RTSP snapshots instead:
def build_media_url(image_id_or_url: str) -> str | None:
    if not image_id_or_url:
        return None
    s = str(image_id_or_url).strip()
    if s.startswith(("http://", "https://")):
        return s
    return f"{MEDIA_BASE}/{s}"
