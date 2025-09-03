# services/api_client.py
import os
import requests
from app_config import load_config
from typing import List, Dict, Any

_SESSION = requests.Session()
_TIMEOUT = 8


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

def fetch_payloads() -> List[Dict[str, Any]]:
    """
    Fetch payloads from API_URL and always return a list of dicts.
    - Uses a shared requests.Session for speed.
    - Defensive JSON parsing (non-JSON => []).
    - Normalizes {'results': [...]} and single-object dicts to a list.
    """
    headers = _auth_header()
    try:
        resp = _SESSION.get(API_URL, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        # Optional: log here instead of crashing UI
        return []

    try:
        data = resp.json()
    except ValueError:
        return []

    # Normalize to list
    if isinstance(data, dict) and "results" in data:
        data = data["results"]

    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]

    if isinstance(data, dict):
        return [data]

    return []
