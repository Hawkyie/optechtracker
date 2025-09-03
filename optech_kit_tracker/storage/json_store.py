from pathlib import Path
from typing import Union
from models.device import create_device_from_api, refresh_device_from_api
import os, tempfile, shutil, json
from json import JSONDecodeError

DATA_FILE = Path(__file__).parent.joinpath("devices.json").resolve()

def init_store():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")

def load_data():
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8")) or []
    except JSONDecodeError:
        # back up the corrupt file once
        bad = DATA_FILE.with_suffix(".json.corrupt")
        try:
            shutil.copy2(DATA_FILE, bad)
        except Exception:
            pass
        return []
    except Exception:
        return []

def save_data(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(DATA_FILE.parent), prefix=DATA_FILE.name, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, DATA_FILE)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

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

def upsert_device_from_api(payload: dict):
    devices = load_data()

    serial = payload.get("serial")
    if not serial:
        raise ValueError("Payload missing 'serial' – cannot upsert.")
    model = payload.get("model")

    existing = next(
        (d for d in devices
         if d.get("serial_number") == serial and (not model or d.get("model") == model)),
        None
    )

    # default result shape in case refresh/create doesn't return flags
    res = {
        "status": "no_change",
        "updated_fields": [],
        "tamper_changed": False,
        "tamper": None,
        "connectivity_changed": False,
        "connectivity": None,
    }

    if existing:
        r = refresh_device_from_api(existing, payload) or {}
        res.update(r)
        action = res.get("status", "no_change")
    else:
        new_dev = create_device_from_api(payload)
        devices.append(new_dev)
        action = "created"
        # Fill flags from the newly created device's current state
        res.update({
            "tamper": new_dev.get("tamper_status"),
            "connectivity": new_dev.get("connectivity"),
        })

    save_data(devices)

    # Preserve the original return contract but now include the refresh flags, too
    return {
        "action": action,
        "serial": serial,
        **res,
    }


