import webbrowser
from tkinter import messagebox, simpledialog, filedialog
from typing import Optional

from storage.json_store import init_store, load_data, save_data, import_device_json, upsert_device_from_api
from models.device import create_device
from services.api_client import fetch_payloads, build_media_url
from app_config import load_config, save_config
import utils

# Import for Load Last Image
import socket, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote, unquote
import requests



# --- module "globals" ---
root = None
tatree = None
details_text = None
img_btn = None
edit_btn = None
del_btn = None
save_var = None
total_var = None

devices = []
POLL_MS = 10_000

def init_handlers(_root, _tatree, _details_text, _img_btn, _edit_btn, _del_btn, _save_var, _total_var, poll_ms: int = 10_000):
    global root, tatree, details_text, img_btn, edit_btn, del_btn, save_var, total_var, devices, POLL_MS
    root, tatree, details_text = _root, _tatree, _details_text
    img_btn, edit_btn, del_btn = _img_btn, _edit_btn, _del_btn
    save_var, total_var = _save_var, _total_var
    POLL_MS = poll_ms

    init_store()
    devices = load_data()
    refresh_device_list()
    refresh_total_device()
    on_selection_change()
    _image_proxy.start()
    


# ---------- helpers ----------
class _ImageProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):  # quiet logs
        pass

    def do_GET(self):
        path = unquote(self.path or "")
        if not path.startswith("/img/"):
            self.send_error(404); return

        image_id = path[len("/img/"):]  # can be an ID or full URL
        url = build_media_url(image_id)
        if not url:
            self.send_error(400, "Cannot resolve image URL"); return

        try:
            r = requests.get(url, headers=_auth_header(), stream=True, timeout=20)
        except Exception as e:
            self.send_error(502, f"Upstream error: {e}"); return

        if not r.ok:
            self.send_error(r.status_code, r.text[:200]); return

        ctype = r.headers.get("content-type", "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        for chunk in r.iter_content(64 * 1024):
            if chunk:
                self.wfile.write(chunk)

class _ImageProxy:
    def __init__(self):
        self.httpd = None
        self.port = None
        self.thread = None

    def start(self):
        if self.httpd:
            return
        s = socket.socket()
        s.bind(("127.0.0.1", 0))          # OS picks a free port
        _, self.port = s.getsockname()
        s.close()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), _ImageProxyHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def base_url(self):
        return f"http://127.0.0.1:{self.port}" if self.port else None

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self.thread = None
            self.port = None

_image_proxy = _ImageProxy()


def row_values(d: dict):
    name = d.get("device_name") or d.get("name") or "(unnamed)"
    dtype = d.get("device_type", "") or ""
    batt = "" if d.get("battery_pct") is None else f"{d['battery_pct']}%"
    tamper = d.get("tamper_status", "UNKNOWN")
    status = d.get("connectivity", "UNKNOWN")
    last_seen = d.get("last_seen") or ""
    return (name, dtype, batt, tamper, status, last_seen)

def insert_row(d: dict):
    tatree.insert("", "end", iid=d["id"], values=row_values(d))

def show_details(d: Optional[dict]):
    details_text.configure(state="normal")
    details_text.delete("1.0", "end")
    if not d:
        details_text.insert("1.0", "Select a device to see details.")
    else:
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
            f"Last Image: {d.get('last_image_url','')}",
            f"Notes: {d.get('notes','')}",
        ]
        details_text.insert("1.0", "\n".join(info))
    details_text.configure(state="disabled")

def refresh_total_device():
    total_var.set(f"Total Devices: {len(devices)}")

def refresh_device_list():
    global devices
    devices = load_data()
    for iid in tatree.get_children():
        tatree.delete(iid)
    for d in devices:
        insert_row(d)

def add_btn_clicked():
    name = simpledialog.askstring("Add a Device", "Please enter a name for your device", parent=root)
    if name is None: return
    name = name.strip()
    if not name:
        messagebox.showerror("Add Device", "Please enter a name.", parent=root)
        return

    device_type = simpledialog.askstring("Device Type", "Please enter a type", parent=root)
    if device_type is None: return
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
        messagebox.showinfo("Too many", "Greedy", parent=root); return
    iid = selected_items[0]
    device = next((d for d in devices if d.get("id") == iid), None)
    if not device: return

    name = simpledialog.askstring("Edit Device", "Please specify the Device name", initialvalue=device.get("name", ""), parent=root)
    if name is None: return
    name = name.strip()
    if not name:
        messagebox.showerror("Edit Device", "Please enter a name.", parent=root); return
    device["name"] = name; device["device_name"] = name
    tatree.item(iid, values=row_values(device))

    device_type = simpledialog.askstring("Device Type", "Please enter the device type", initialvalue=device.get("device_type", ""), parent=root)
    if device_type is None: return
    device["device_type"] = device_type.strip() or "No device type"

    tatree.item(iid, values=row_values(device))
    show_details(device)
    save_data(devices)

def del_btn_clicked():
    selected_items = tatree.selection()
    if len(selected_items) != 1:
        messagebox.showinfo("We are showing you this", "Select one device.", parent=root); return
    iid = selected_items[0]
    device = next((d for d in devices if d.get("id") == iid), None)
    if not device: return
    ok = messagebox.askyesno("Delete", "Delete this device?", parent=root)
    if not ok: return

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
    if not paths: return

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

    msg = f"Created: {summary['created']}\nUpdated: {summary['updated']}\nNo change: {summary['no_change']}"
    if errors:
        msg += "\n\nErrors:\n- " + "\n- ".join(errors[:5])
        if len(errors) > 5:
            msg += f"\n… and {len(errors)-5} more"
    messagebox.showinfo("API sync complete", msg, parent=root)

def open_last_image_for_selected():
    sel = tatree.selection()
    if not sel:
        messagebox.showinfo("Last image", "Select a device first.", parent=root)
        return

    d = next((x for x in devices if x.get("id") == sel[0]), None)
    if not d:
        return

    ref = d.get("last_image_url")
    if not ref:
        messagebox.showinfo("Last image", "No image recorded for this device yet.", parent=root)
        return

    # Always use the local proxy so the Authorization header is attached.
    _image_proxy.start()  # no-op if already running
    local_url = f"{_image_proxy.base_url()}/img/{quote(str(ref))}"
    webbrowser.open(local_url)



def open_settings():
    cfg = load_config()
    api = simpledialog.askstring("Settings", "API URL", initialvalue=cfg.get("api_url",""), parent=root)
    if api is None: return
    tok = simpledialog.askstring("Settings", "API Token (leave blank if none)", initialvalue=cfg.get("api_token",""), parent=root)
    if tok is None: return
    media = simpledialog.askstring("Settings", "Media Base URL (optional, for image IDs)", initialvalue=cfg.get("media_base",""), parent=root)
    if media is None: return
    cfg.update({"api_url": api.strip(), "api_token": tok.strip(), "media_base": media.strip()})
    save_config(cfg)
    messagebox.showinfo("Settings", "Saved. Use Refresh from API to apply.", parent=root)

def on_selection_change(event=None):
    selected = tatree.selection()
    if len(selected) == 1:
        edit_btn.config(state="normal")
        del_btn.config(state="normal")
        iid = selected[0]
        device = next((d for d in devices if d.get("id") == iid), None)
        show_details(device)
        has_img = bool(device and device.get("last_image_url"))
        img_btn.config(state="normal" if has_img else "disabled")
    else:
        edit_btn.config(state="disabled")
        del_btn.config(state="disabled")
        img_btn.config(state="disabled")
        show_details(None)

def poll_api():
    try:
        payloads = fetch_payloads()
        for p in payloads:
            upsert_device_from_api(p)
        refresh_device_list()
    except Exception:
        pass
    finally:
        root.after(POLL_MS, poll_api)

def start_polling(ms: int):
    global POLL_MS
    POLL_MS = ms
    root.after(POLL_MS, poll_api)

def _auth_header():
    tok = (load_config().get("api_token") or "").strip()
    if not tok:
        return {}
    return {"Authorization": tok if tok.lower().startswith("bearer ")
            else f"Bearer {tok}"}