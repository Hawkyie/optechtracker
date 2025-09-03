from typing import List
from datetime import date, datetime, timedelta
import uuid

def today_iso_date() -> str:
    return datetime.today().strftime("%Y-%m-%d")


def now_iso_datetime() -> str:
    return datetime.now().isoformat(timespec='seconds')


def make_id(prefix="dv"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def to_int(val, default=None):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default

def to_float(val, default=None):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
