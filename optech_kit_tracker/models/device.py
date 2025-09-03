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

def refresh_device_from_api(device: dict, payload: dict) -> dict:
    """
    Update a device in-place from an API payload.
    Returns:
      {
        "status": "updated" | "no_change",
        "updated_fields": [...],
        "tamper_changed": bool,
        "tamper": "TAMPERED" | "OK" | "UNKNOWN",
        "connectivity_changed": bool,
        "connectivity": "ONLINE" | "OFFLINE" | "UNKNOWN",
      }
    """
    changed_fields = []

    # Keep prior values to compute change flags
    prev_tamper = device.get("tamper_status")
    prev_conn   = device.get("connectivity")

    # ---- Position
    pos = payload.get("position") or {}
    for k in ("lat", "lon"):
        v = pos.get(k)
        if v is not None and v != device.get(k):
            device[k] = v
            changed_fields.append(k)

    # ---- Last seen
    ts = payload.get("timestamp")
    if ts and ts != device.get("last_seen"):
        device["last_seen"] = ts
        changed_fields.append("last_seen")

    # ---- Battery
    batt = payload.get("battery")
    try:
        batt_i = int(batt) if batt is not None else None
    except (TypeError, ValueError):
        batt_i = None
    if batt_i != device.get("battery_pct"):
        device["battery_pct"] = batt_i
        changed_fields.append("battery_pct")

    # ---- Tamper
    tampered = payload.get("tampered")
    if tampered is True:
        tamper_status = "TAMPERED"
    elif tampered is False:
        tamper_status = "OK"
    else:
        tamper_status = "UNKNOWN"
    if tamper_status != device.get("tamper_status"):
        device["tamper_status"] = tamper_status
        changed_fields.append("tamper_status")

    # ---- Connectivity
    online = payload.get("online")
    if online is True:
        conn = "ONLINE"
    elif online is False:
        conn = "OFFLINE"
    else:
        conn = device.get("connectivity", "UNKNOWN")
    if conn != device.get("connectivity"):
        device["connectivity"] = conn
        changed_fields.append("connectivity")

    pl = payload.get("payload") or {}
    ptype = (pl.get("type") or "").lower()

    # If API gives a real URL, prefer it
    direct_url = pl.get("url") or pl.get("thumbnail_url")
    if isinstance(direct_url, str) and direct_url.startswith(("http://", "https://")):
        if direct_url != device.get("last_image_url"):
            device["last_image_url"] = direct_url
            changed_fields.append("last_image_url")

    # Always capture an image-id if present (for fragments)
    img_id = pl.get("id")
    if img_id and img_id != device.get("last_image_id"):
        device["last_image_id"] = img_id
        changed_fields.append("last_image_id")

    # ---- Event log (bounded)
    if "event_log" not in device or not isinstance(device["event_log"], list):
        device["event_log"] = []
    device["event_log"].append({
        "ts": ts or utils.today_iso_date(),
        "type": "API_REFRESH",
        "payload_type": ptype or payload.get("type"),
    })
    if len(device["event_log"]) > 50:
        device["event_log"] = device["event_log"][-50:]

    result = {
        "status": "updated" if changed_fields else "no_change",
        "updated_fields": changed_fields,
        "tamper_changed": False,
        "tamper": device.get("tamper_status"),
        "connectivity_changed": False,
        "connectivity": device.get("connectivity"),
    }
    return result

