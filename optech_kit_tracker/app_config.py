import json
from pathlib import Path
CONFIG_FILE = Path.home() / ".optechtracker.json"


DEFAULTS = {
    "api_url": "https://kit-tracker.peacemosquitto.workers.dev/",
    "api_token": "Bearer 63T-nAch05-p3W5-lIn60t",
    "media_base": ""                
}

POLL_INTERVAL_MS = 5000
ALERT_DEBOUNCE_MS = 800
MAP_KEEP_ALIVE_MS = 50

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULTS, **(data or {})}
        except Exception:
            pass
    return DEFAULTS.copy()

def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
