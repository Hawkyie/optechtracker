import utils

def create_device(device_id: str, name: str, device_type: str, serial_number: str | None = None):
    return {
        "id": device_id,
        "name": name,          
        "device_name": name,
        "device_type": device_type,
        "serial_number": serial_number,
        "created_at": utils.today_iso_date(),

        "model": None, "kit_id": None, "notes": None,
        "lat": None, "lon": None, "accuracy_m": None,
        "battery_pct": None,
        "tamper_status": "UNKNOWN",
        "connectivity": "UNKNOWN",
        "last_seen": None,
        "last_image_url": None,
        "stream_url": None,

        "event_log": []
    }

def create_device_from_api(data: dict):
    pos = data.get("position", {})
    return {
        "id": utils.make_id(),
        "device_name": f"{data.get('model','Unknown')} ({data.get('serial','-')})",
        "device_type": data.get("type"),
        "model": data.get("model"),
        "serial_number": data.get("serial"),
        "kit_id": data.get("op"),
        "notes": data.get("description"),
        "created_at": utils.today_iso_date(),

        "lat": utils.to_float(pos.get("lat")),
        "lon": utils.to_float(pos.get("lon")),
        "accuracy_m": None,
        "battery_pct": utils.to_int(data.get("battery")),
        "tamper_status": ("TAMPERED" if data.get("tampered") is True
                          else "OK" if data.get("tampered") is False
                          else "UNKNOWN"),
        "connectivity": ("ONLINE" if data.get("online") is True
                         else "OFFLINE" if data.get("online") is False
                         else "UNKNOWN"),
        "last_seen": data.get("timestamp"),
        "last_image_url": None,
        "stream_url": None,

        "event_log": [{"ts": data.get("timestamp"), "type": "IMPORT", "payload": data}]
    }

def refresh_device_from_api(device: dict, payload: dict) -> str:
    pos = payload.get("position", {})
    changed = False
    def set_if_changed(key, val):
        nonlocal changed
        if val is not None and device.get(key) != val:
            device[key] = val
            changed = True

    set_if_changed("lat", utils.to_float(pos.get("lat")))
    set_if_changed("lon", utils.to_float(pos.get("lon")))
    set_if_changed("battery_pct", utils.to_int(payload.get("battery")))
    set_if_changed("last_seen", payload.get("timestamp"))

    new_tamper = ("TAMPERED" if payload.get("tampered") is True
                  else "OK" if payload.get("tampered") is False
                  else "UNKNOWN")
    new_conn = ("ONLINE" if payload.get("online") is True
                else "OFFLINE" if payload.get("online") is False
                else "UNKNOWN")
    set_if_changed("tamper_status", new_tamper)
    set_if_changed("connectivity", new_conn)

    device.setdefault("event_log", []).append({
        "ts": payload.get("timestamp") or utils.now_iso_datetime(),
        "type": "STATUS",
        "payload": payload
    })
    return "updated" if changed else "no_change"
