import os
import time
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional
from tkinter import messagebox, simpledialog, filedialog
from storage.json_store import (
    init_store, load_data, save_data, import_device_json, upsert_device_from_api
)
from models.device import create_device
from services.api_client import fetch_payloads
from app_config import load_config, save_config
import utils

# --- module "globals" ---
root = None
tatree = None
details_text = None
img_btn = None
edit_btn = None
del_btn = None
save_var = None
total_var = None
alerts_list = None
map_widget = None     
_map_markers = []
last_selected_iid = None
_suppress_select_events = False
last_alert_bell_ts = 0 


devices = []
POLL_MS = 10_000


DEFAULT_RTSP_URL = os.getenv("OPTECH_RTSP_URL", "rtsp://192.168.8.185:8554/cam")

def init_handlers(
    _root, _tatree, _details_text,
    _img_btn, _edit_btn, _del_btn,
    _save_var, _total_var,
    poll_ms: int = 10_000,
    _alerts_list=None,
    _map_widget=None
):
    global root, tatree, details_text, img_btn, edit_btn, del_btn
    global save_var, total_var, devices, POLL_MS, alerts_list, map_widget

    root, tatree, details_text = _root, _tatree, _details_text
    img_btn, edit_btn, del_btn = _img_btn, _edit_btn, _del_btn
    save_var, total_var = _save_var, _total_var
    POLL_MS = poll_ms
    alerts_list = _alerts_list
    map_widget = _map_widget

    init_store()
    devices = load_data()
    refresh_device_list()
    refresh_total_device()
    on_selection_change()

    try:
        _configure_tree_tags()
    except Exception:
        pass

    try:
        update_map_markers()           
    except Exception:
        pass


# ---------- helpers ----------

def _compute_row_tags(d: dict) -> list[str]:
   
    conn = (d.get("connectivity") or "").strip().upper()
    tamp = (d.get("tamper_status") or "").strip().upper()

    tags: list[str] = []
    if conn == "OFFLINE":
        tags.append("offline")
    if tamp == "TAMPERED":
        tags.append("tampered")

    # Precedence: the LAST tag wins for conflicting options.
    # Ensure 'tampered' overrides 'offline' if both are present.
    if "tampered" in tags:
        tags = [t for t in tags if t != "tampered"] + ["tampered"]

    return tags or ["normal"]


def _configure_tree_tags():
    # call this once in init
    try:
        tatree.tag_configure("normal")
        tatree.tag_configure("offline", background="#FFEAEA", foreground="#8B0000")   # light red row
        tatree.tag_configure("tampered", background="#FFF6CC", foreground="#6B4E00")  # light amber row
    except Exception:
        pass


def _configure_tree_tags():
    tatree.tag_configure("normal")
    tatree.tag_configure("offline", background="#FFEAEA", foreground="#8B0000")   # light red
    tatree.tag_configure("tampered", background="#FFF6CC", foreground="#6B4E00")  # light amber
    
def _push_alert(msg: str):
    """Append a red, timestamped alert to the Alerts panel."""
    if not alerts_list:
        return
    ts = time.strftime("%H:%M:%S")
    alerts_list.insert(0, f"[{ts}] {msg}")
    try:
        alerts_list.itemconfig(0, foreground="red")
    except Exception:
        pass
    # keep size in check
    if alerts_list.size() > 300:
        alerts_list.delete(300, "end")

def center_map_on_current_selection():
    """Center the map on the currently selected (or last selected) device."""
    if map_widget is None:
        return

    # Prefer current selection, else fallback to remembered iid
    sel = tatree.selection()
    iid = sel[0] if sel else None
    if not iid:
        try:
            iid = last_selected_iid  # defined earlier selection-preserve patch
        except NameError:
            iid = None

    if not iid:
        return

    dev = next((d for d in devices if d.get("id") == iid), None)
    if dev:
        center_map_on_device(dev, zoom=13)


def on_notebook_tab_changed(event):
    """
    When user switches to the 'Map' tab, center on the selected device.
    (Relies on the tab text being 'Map' as added in app.py.)
    """
    try:
        nb = event.widget  # ttk.Notebook
        tab_text = nb.tab(nb.select(), "text")
        if (tab_text or "").strip().lower() == "map":
            center_map_on_current_selection()
    except Exception:
        pass


def _device_has_image_events(d: dict) -> bool:
    """
    Returns True if recent events/payloads look like the device is providing images.
    Heuristic: any event payload.type starting with 'image'.
    Falls back to device_type hint for camera-like things.
    """

    for ev in reversed(d.get("event_log", [])):
        top = ev.get("payload") or {}
        inner = top.get("payload") or {}
        t = (inner.get("type") or top.get("type") or "").lower()
        if t.startswith("image"):
            return True

    dtype = (d.get("device_type") or "").lower()
    if dtype in {"camera", "uav", "drone"}:
        return True
    return False


def _grab_rtsp_snapshot(rtsp_url: str, warmup_frames: int = 12, timeout_s: int = 10) -> Path:
    """
    Grab a single frame from an RTSP stream using OpenCV (FFmpeg backend).
    Returns a temp JPG path or raises RuntimeError with a clear message.
    """
    try:
        import cv2
    except ImportError:
        raise RuntimeError("OpenCV (cv2) is not installed. Run: pip install opencv-python")

    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise RuntimeError("OpenCV could not open RTSP stream (check URL/credentials/camera)")

    start = time.time()
    ok, frame = False, None

    for _ in range(max(1, warmup_frames)):
        ok, frame = cap.read()
        if ok:
            break
        if time.time() - start > timeout_s:
            break
    cap.release()

    if not ok or frame is None:
        raise RuntimeError("Couldn't read a frame from RTSP (check codec/network)")

    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("Failed to encode JPG")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(buf.tobytes())
        return Path(tmp.name)


def row_values(d: dict):
    name = d.get("device_name") or d.get("name") or "(unnamed)"
    dtype = d.get("device_type", "") or ""
    batt = "" if d.get("battery_pct") is None else f"{d['battery_pct']}%"
    tamper = d.get("tamper_status", "UNKNOWN")
    status = d.get("connectivity", "UNKNOWN")
    last_seen = d.get("last_seen") or ""
    return (name, dtype, batt, tamper, status, last_seen)


def insert_row(d: dict):
    tatree.insert("", "end", iid=d["id"], values=row_values(d), tags=_compute_row_tags(d))


def show_details(d: Optional[dict]):
    details_text.configure(state="normal")
    details_text.delete("1.0", "end")
    if not d:
        details_text.insert("1.0", "Select a device to see details.")
    else:
        stream = d.get("stream_url") or DEFAULT_RTSP_URL
        info = [
            f"Name: {d.get('device_name') or d.get('name')}",
            f"Type: {d.get('device_type','')}",
            f"Model: {d.get('model','')}",
            f"Serial: {d.get('serial_number','')}",
            f"Operation: {d.get('kit_id','')}",
            f"Battery: {d.get('battery_pct') if d.get('battery_pct') is not None else ''}",
            f"Tamper: {d.get('tamper_status','UNKNOWN')}",
            f"Status: {d.get('connectivity','UNKNOWN')}",
            f"Last Seen: {d.get('last_seen','')}",
            f"GPS: {d.get('lat')}, {d.get('lon')}",
            f"Stream: {stream or '(none)'}",
            f"Notes: {d.get('notes','')}",
        ]
        details_text.insert("1.0", "\n".join(info))
    details_text.configure(state="disabled")


def refresh_total_device():
    total_var.set(f"Total Devices: {len(devices)}")


def refresh_device_list():
    """Repaint table from disk while preserving selection, scroll and map center."""
    global devices, _suppress_select_events, last_selected_iid

    # remember selection to keep
    current_sel = tatree.selection()
    wanted_iid = current_sel[0] if current_sel else last_selected_iid

    # remember scroll so doesn't jump to top
    try:
        y0, _ = tatree.yview()
    except Exception:
        y0 = None

    # load from disk; if read fails, keep previous in-memory devices
    try:
        loaded = load_data()
        if isinstance(loaded, list) and loaded is not None:
            devices = loaded
    except Exception:
        pass

    _suppress_select_events = True
    try:
        # clear & reinsert
        tatree.delete(*tatree.get_children())
        for d in devices:
            if isinstance(d, dict) and d.get("id"):
                insert_row(d)

        # restore scroll
        if y0 is not None:
            try:
                tatree.yview_moveto(y0)
            except Exception:
                pass

        # restore selection if possible
        dev = None
        if wanted_iid and tatree.exists(wanted_iid):
            tatree.selection_set(wanted_iid)
            tatree.focus(wanted_iid)
            tatree.see(wanted_iid)
            dev = next((x for x in devices if x.get("id") == wanted_iid), None)

        # update buttons/details
        if dev:
            show_details(dev)
            edit_btn.config(state="normal"); del_btn.config(state="normal")
            has_rtsp = bool(dev.get("stream_url") or DEFAULT_RTSP_URL)
            imaging = _device_has_image_events(dev)
            img_btn.config(state="normal" if (has_rtsp and imaging) else "disabled")
            # keep map centered on selection AFTER markers exist
            try:
                center_map_on_device(dev, zoom=13)
            except Exception:
                pass
        else:
            edit_btn.config(state="disabled"); del_btn.config(state="disabled")
            img_btn.config(state="disabled")
            show_details(None)

    finally:
        _suppress_select_events = False

    # footer count
    refresh_total_device()



def _map_available() -> bool:
    return map_widget is not None

def _marker_color_for(d: dict) -> str:
    tamp = (d.get("tamper_status") or "").strip().upper()
    conn = (d.get("connectivity") or "").strip().upper()
    if tamp == "TAMPERED":
        return "orange"
    if conn == "OFFLINE":
        return "red"
    return "green"

def _device_latlon(d: dict):
    lat, lon = d.get("lat"), d.get("lon")
    try:
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)
    except Exception:
        return None

def update_map_markers(center_on_device: dict | None = None):
    """Redraw markers without touching map center/zoom (unless centering is requested)."""
    if not _map_available():
        return

    # Clear previous markers
    for m in list(_map_markers):
        try:
            m.delete()
        except Exception:
            pass
    _map_markers.clear()

    # Re-add markers
    for d in devices:
        ll = _device_latlon(d)
        if not ll:
            continue
        lat, lon = ll
        name = d.get("device_name") or d.get("name") or "Device"
        color = _marker_color_for(d)
        try:
            marker = map_widget.set_marker(
                lat, lon, text=name,
                marker_color_circle=color, marker_color_outside="black"
            )
            _map_markers.append(marker)
        except Exception:
            pass

    # Only recenter if explicitly asked to center on a specific device
    if center_on_device:
        try:
            center_map_on_device(center_on_device, zoom=13)
        except Exception:
            pass


def center_map_on_device(d: dict, zoom: int = 13):
    """Center the map on a specific device (if it has coordinates)."""
    if not _map_available():
        return
    ll = _device_latlon(d)
    if not ll:
        return
    lat, lon = ll
    try:
        map_widget.set_position(lat, lon)
        map_widget.set_zoom(zoom)
    except Exception:
        pass

# ---------- CRUD actions ----------

def add_btn_clicked():
    name = simpledialog.askstring("Add a Device", "Please enter a name for your device", parent=root)
    if name is None:
        return
    name = name.strip()
    if not name:
        messagebox.showerror("Add Device", "Please enter a name.", parent=root)
        return

    device_type = simpledialog.askstring("Device Type", "Please enter a type", parent=root)
    if device_type is None:
        return
    device_type = (device_type or "").strip() or "No type"

    existing_ids = {d.get("id") for d in devices}
    device_id = utils.make_id("hb")
    while device_id in existing_ids:
        device_id = utils.make_id("hb")

    d = create_device(device_id, name, device_type)
    d.setdefault("device_name", d.get("name"))
    devices.append(d)
    save_data(devices)

    insert_row(d)
    tatree.selection_set(d["id"]); tatree.focus(d["id"]); tatree.see(d["id"])
    show_details(d)
    refresh_total_device()


def edit_btn_clicked():
    selected_items = tatree.selection()
    if len(selected_items) != 1:
        messagebox.showinfo("Too many", "Greedy", parent=root)
        return
    iid = selected_items[0]
    device = next((d for d in devices if d.get("id") == iid), None)
    if not device:
        return

    name = simpledialog.askstring("Edit Device", "Please specify the Device name", initialvalue=device.get("name", ""), parent=root)
    if name is None:
        return
    name = name.strip()
    if not name:
        messagebox.showerror("Edit Device", "Please enter a name.", parent=root)
        return
    device["name"] = name
    device["device_name"] = name
    tatree.item(iid, values=row_values(device))

    device_type = simpledialog.askstring("Device Type", "Please enter the device type", initialvalue=device.get("device_type", ""), parent=root)
    if device_type is None:
        return
    device["device_type"] = device_type.strip() or "No device type"

    tatree.item(iid, values=row_values(device))
    tatree.item(iid, tags=_compute_row_tags(device))
    show_details(device)
    save_data(devices)


def del_btn_clicked():
    selected_items = tatree.selection()
    if len(selected_items) != 1:
        messagebox.showinfo("We are showing you this", "Select one device.", parent=root)
        return
    iid = selected_items[0]
    device = next((d for d in devices if d.get("id") == iid), None)
    if not device:
        return
    ok = messagebox.askyesno("Delete", "Delete this device?", parent=root)
    if not ok:
        return

    devices.remove(device)
    tatree.delete(iid)
    refresh_total_device()
    on_selection_change()
    save_data(devices)


def save_btn_clicked():
    try:
        global devices
        devices = load_data()
        save_data(devices)
    except Exception as e:
        messagebox.showerror("Save error", str(e), parent=root)
    else:
        save_var.set("Saved just now")
        root.after(8_000, lambda: save_var.set(""))


def on_import_json_clicked():
    paths = filedialog.askopenfilenames(
        title="Import Device JSON…",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    if not paths:
        return

    summary = {"created": 0, "updated": 0, "no_change": 0}
    errors = []
    for p in paths:
        try:
            results = import_device_json(p)
            for res in results:
                summary[res["action"]] = summary.get(res["action"], 0) + 1
        except Exception as e:
            errors.append(f"{p}: {e}")

    refresh_device_list()
    msg = f"Created: {summary['created']}\nUpdated: {summary['updated']}\nNo change: {summary['no_change']}"
    if errors:
        msg += "\n\nErrors:\n- " + "\n- ".join(errors[:5])
        if len(errors) > 5:
            msg += f"\n… and {len(errors)-5} more"
    messagebox.showinfo("Import complete", msg, parent=root)
    


def on_refresh_api_clicked():
    try:
        payloads = fetch_payloads()
    except Exception as e:
        messagebox.showerror("API error", f"Failed to fetch from API:\n{e}", parent=root)
        return

    summary = {"created": 0, "updated": 0, "no_change": 0}
    errors = []
    alerts = []

    for p in payloads:
        try:
            res = upsert_device_from_api(p)
            action = res.get("action", "no_change")
            summary[action] = summary.get(action, 0) + 1

            if res.get("tamper_changed") and res.get("tamper") == "TAMPERED":
                alerts.append(f"{p.get('model','?')} {p.get('serial','?')}: TAMPERED")
            if res.get("connectivity_changed") and res.get("connectivity") == "OFFLINE":
                alerts.append(f"{p.get('model','?')} {p.get('serial','?')}: OFFLINE")
        except Exception as e:
            errors.append(str(e))

    refresh_device_list()

    if alerts:
        messagebox.showwarning("Alerts", "\n".join(alerts), parent=root)
        for m in alerts:
            _push_alert(m)


    msg = f"Created: {summary['created']}\nUpdated: {summary['updated']}\nNo change: {summary['no_change']}"
    if errors:
        msg += "\n\nErrors:\n- " + "\n- ".join(errors[:5])
        if len(errors) > 5:
            msg += f"\n… and {len(errors)-5} more"
    messagebox.showinfo("API sync complete", msg, parent=root)


def open_device_snapshot():
    sel = tatree.selection()
    if not sel:
        messagebox.showinfo("Live snapshot", "Select a device first.", parent=root)
        return
    d = next((x for x in devices if x.get("id") == sel[0]), None)
    if not d:
        return

    if not _device_has_image_events(d):
        messagebox.showinfo("Live snapshot", "This device has not been sending images.", parent=root)
        return

    rtsp = (d.get("stream_url") or DEFAULT_RTSP_URL or "").strip()
    if not rtsp:
        messagebox.showinfo("Live snapshot", "No RTSP URL configured and no default set.", parent=root)
        return

    img_btn.config(state="disabled")

    def work():
        try:
            img_path = _grab_rtsp_snapshot(rtsp)
            uri = Path(img_path).as_uri()
            root.after(0, lambda: webbrowser.open(uri))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Live snapshot", f"Failed to capture frame:\n{e}", parent=root))
        finally:
            root.after(0, lambda: img_btn.config(state="normal"))

    import threading
    threading.Thread(target=work, daemon=True).start()



# ---------- Settings / selection / polling ----------

def open_settings():
    cfg = load_config()
    api = simpledialog.askstring("Settings", "API URL", initialvalue=cfg.get("api_url",""), parent=root)
    if api is None:
        return
    tok = simpledialog.askstring("Settings", "API Token (leave blank if none)", initialvalue=cfg.get("api_token",""), parent=root)
    if tok is None:
        return
    media = simpledialog.askstring("Settings", "Media Base URL (optional, for image IDs)", initialvalue=cfg.get("media_base",""), parent=root)
    if media is None:
        return
    cfg.update({"api_url": api.strip(), "api_token": tok.strip(), "media_base": media.strip()})
    save_config(cfg)
    messagebox.showinfo("Settings", "Saved. Use Refresh from API to apply.", parent=root)


def on_selection_change(event=None):
    if _suppress_select_events:
        return

    selected = tatree.selection()
    if len(selected) == 1:
        # remember selection
        global last_selected_iid
        last_selected_iid = selected[0]

        edit_btn.config(state="normal")
        del_btn.config(state="normal")
        iid = selected[0]
        device = next((d for d in devices if d.get("id") == iid), None)
        show_details(device)

        has_rtsp = bool(device and (device.get("stream_url") or DEFAULT_RTSP_URL))
        imaging = bool(device and _device_has_image_events(device))
        img_btn.config(state="normal" if (has_rtsp and imaging) else "disabled")
    else:
        edit_btn.config(state="disabled")
        del_btn.config(state="disabled")
        img_btn.config(state="disabled")
        show_details(None)



def poll_api():
    alerts = []
    try:
        payloads = fetch_payloads()
        for p in payloads:
            try:
                res = upsert_device_from_api(p)

                # Only alert on *changes* to negative states
                if res.get("tamper_changed") and (res.get("tamper") == "TAMPERED"):
                    model = p.get("model", "?"); serial = p.get("serial", "?")
                    alerts.append(f"{model} {serial}: TAMPERED")

                if res.get("connectivity_changed") and (res.get("connectivity") == "OFFLINE"):
                    model = p.get("model", "?"); serial = p.get("serial", "?")
                    alerts.append(f"{model} {serial}: OFFLINE")

            except Exception:
                # Continue polling other payloads
                pass

        # Refresh table so state colors/tags (if you added them) remain accurate
        refresh_device_list()


    except Exception:
        # swallow transient API errors — panel is for device alerts, not network noise
        pass
    finally:
        if alerts:
            # Log to Alerts panel (non-blocking)
            for msg in alerts:
                _push_alert(msg)

            # Throttle the bell (once every 10s max)
            global last_alert_bell_ts
            now = time.time()
            if now - last_alert_bell_ts > 10:
                try:
                    root.bell()
                except Exception:
                    pass
                last_alert_bell_ts = now

            # Brief, non-blocking status flash instead of a modal popup
            try:
                save_var.set(f"{len(alerts)} new alert(s)")
                root.after(6000, lambda: save_var.set(""))
            except Exception:
                pass

        root.after(POLL_MS, poll_api)



def start_polling(ms: int):
    global POLL_MS
    POLL_MS = ms
    root.after(POLL_MS, poll_api)