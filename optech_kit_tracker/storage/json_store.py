from pathlib import Path
import json
from typing import Union
from models.device import create_device_from_api, refresh_device_from_api

DATA_FILE = Path(__file__).parent.joinpath("devices.json").resolve()

def init_store():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")

def load_data():
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_data(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def import_device_json(path: Union[str, Path]):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return [upsert_device_from_api(data)]
    elif isinstance(data, list):
        return [upsert_device_from_api(obj) for obj in data]
    else:
        raise ValueError("Unsupported JSON; expected object or list.")

def import_device_json_dir(dir_path: Union[str, Path]):
    actions = {"created":0, "updated":0, "no_change":0}
    for p in Path(dir_path).glob("*.json"):
        for res in import_device_json(p):
            actions[res["action"]] += 1
    return actions

# storage/json_store.py
def upsert_device_from_api(payload: dict):
    devices = load_data()
    serial = payload.get("serial")
    if not serial:
        raise ValueError("Payload missing 'serial' – cannot upsert.")
    model  = payload.get("model")

    existing = next((d for d in devices
                     if d.get("serial_number") == serial and (not model or d.get("model") == model)), None)

    if existing:
        before_tamper = existing.get("tamper_status")
        before_conn   = existing.get("connectivity")
        result = refresh_device_from_api(existing, payload)  # "updated" | "no_change"
        action = "updated" if result == "updated" else "no_change"
        after_tamper = existing.get("tamper_status")
        after_conn   = existing.get("connectivity")
    else:
        new_dev = create_device_from_api(payload)
        devices.append(new_dev)
        action = "created"
        before_tamper = before_conn = None
        after_tamper = new_dev.get("tamper_status")
        after_conn   = new_dev.get("connectivity")

    save_data(devices)
    return {
        "action": action,
        "serial": serial,
        "tamper_changed": before_tamper != after_tamper if existing else False,
        "connectivity_changed": before_conn != after_conn if existing else False,
        "tamper": after_tamper,
        "connectivity": after_conn,
    }

