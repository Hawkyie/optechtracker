import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import tkinter.font as tkfont
from storage.json_store import init_store, load_data, save_data, import_device_json, DATA_FILE, upsert_device_from_api
from models.device import create_device
from services.api_client import fetch_payloads

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

import utils

init_store()
devices = load_data()

def add_btn_clicked():
    name = simpledialog.askstring("Add a Device", "Please enter a name for your device", parent=root)
    if name is None:
        return
    name = name.strip()
    if not name:
        messagebox.showerror("Add Device", "This is not my wonky code wonking, you didn't enter a name. Do it.", parent=root)
        return
    
    device_type = simpledialog.askstring("Device Type", "Please enter a type", parent=root)
    if device_type is None:
        return
    device_type = (device_type or "").strip() or "No type"

    existing_ids = {d.get("id") for d in devices}
    device_id = utils.make_id("hb")
    while device_id in existing_ids:
        device_id = utils.make_id("hb")

    create_device_dict = create_device(device_id, name, device_type)
    create_device_dict.setdefault("device_name", create_device_dict.get("name"))

    devices.append(create_device_dict)
    insert_row(create_device_dict)

    item_id = create_device_dict["id"]
    tatree.selection_set(item_id)
    tatree.focus(item_id)
    tatree.see(item_id)
    show_details(create_device_dict)

    refresh_total_device()
    save_data(devices)


def edit_btn_clicked():
    selected_items = tatree.selection()
    if len(selected_items) !=1:
        messagebox.showinfo("Too many", "Greedy", parent=root)
        return
    iid = selected_items[0]
    device = next((d for d in devices if d.get("id") == iid), None)
    if device is None:
        return
    
    name = simpledialog.askstring("Edit Device", "Please specify the Device name", initialvalue=device.get("name", ""), parent=root)
    if name is None:
        return
    name = name.strip()
    if not name:
        messagebox.showerror("Edit Device", "This is not my wonky code wonking, you didn't enter a name. Do it.", parent=root)
        return
    device["name"] = name
    device["device_name"] = name
    tatree.item(iid, values=row_values(device))   

    device_type = simpledialog.askstring("Device Type", "Please enter the device type",
                                     initialvalue=device.get("device_type", ""), parent=root)
    if device_type is None:
        return
    device["device_type"] = device_type.strip() or "No device type"

    tatree.item(iid, values=row_values(device))
    show_details(device)
    save_data(devices)


def del_btn_clicked():
    selected_items = tatree.selection()
    if len(selected_items) !=1:
        messagebox.showinfo("We are showing you this", "You did something wrong, this is a feature not a bug", parent=root)
        return
    iid = selected_items[0]
    device = next((d for d in devices if d.get("id") == iid), None)
    if device is None:
        return
    else:
        ok = messagebox.askyesno("To delete or not to delete", "Are you sure you want to delete this device", parent=root)
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
        return
    else:
        save_var.set("Saved just now")
        root.after(10000, lambda: save_var.set(""))

        
def refresh_device_list():
    global devices
    devices = load_data()
    for iid in tatree.get_children():
        tatree.delete(iid)
    for d in devices:
        insert_row(d)
    refresh_total_device()
    on_selection_change()
        
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

    messagebox.showinfo("Import complete", msg)

def show_details(d):
    device_type_text.configure(state="normal")
    device_type_text.delete("1.0", "end")
    if not d:
        device_type_text.insert("1.0", "Select a device to see details.")
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
            f"Notes: {d.get('notes','')}",
        ]
        device_type_text.insert("1.0", "\n".join(info))
    device_type_text.configure(state="disabled")

    
def insert_row(d):
    display_name = d.get("device_name") or d.get("name") or "(unnamed)"
    battery = (f"{d['battery_pct']}%" if isinstance(d.get("battery_pct"), int) else "")
    values = (
        display_name,
        d.get("device_type",""),
        battery,
        d.get("tamper_status","UNKNOWN"),
        d.get("connectivity","UNKNOWN"),
        d.get("last_seen","") or ""
    )
    tatree.insert("", "end", iid=d["id"], values=values)
    
def on_refresh_api_clicked():
    try:
        payloads = fetch_payloads()
    except Exception as e:
        messagebox.showerror("API error", f"Failed to fetch from API:\n{e}", parent=root)
        return

    summary = {"created": 0, "updated": 0, "no_change": 0}
    errors = []

    for p in payloads:
        try:
            res = upsert_device_from_api(p)
            summary[res["action"]] = summary.get(res["action"], 0) + 1
        except Exception as e:
            errors.append(str(e))
    
    alerts = []
    for p in payloads:
        res = upsert_device_from_api(p)
    if res.get("tamper_changed") and res["tamper"] == "TAMPERED":
        alerts.append(f"{p.get('model','?')} {p.get('serial','?')}: TAMPERED")
    if res.get("connectivity_changed") and res["connectivity"] == "OFFLINE":
        alerts.append(f"{p.get('model','?')} {p.get('serial','?')}: OFFLINE")

    if alerts:
        messagebox.showwarning("Alerts", "\n".join(alerts), parent=root)


    refresh_device_list()

    msg = f"Created: {summary['created']}\nUpdated: {summary['updated']}\nNo change: {summary['no_change']}"
    if errors:
        msg += "\n\nErrors:\n- " + "\n- ".join(errors[:5])
        if len(errors) > 5:
            msg += f"\n… and {len(errors)-5} more"
    messagebox.showinfo("API sync complete", msg, parent=root)



root = tk.Tk()
tkfont.nametofont("TkDefaultFont").configure(family="Segoe UI", size=10)
tkfont.nametofont("TkTextFont").configure(family="Segoe UI", size=10)
tkfont.nametofont("TkHeadingFont").configure(family="Segoe UI", size=10, weight="bold")
tkfont.nametofont("TkMenuFont").configure(family="Segoe UI", size=10)
tkfont.nametofont("TkFixedFont").configure(family="Consolas", size=10)

root.title("OpTech Device Tracker")
root.geometry("800x800")
root.minsize(800, 800)

menubar = tk.Menu(root)
root.config(menu=menubar)
file_menu = tk.Menu(menubar)

toolbar = ttk.Frame(root)
toolbar.pack(side=tk.TOP, fill=tk.X)
btn_row = ttk.Frame(toolbar)
btn_row.pack()
add_btn = ttk.Button(btn_row,
                    text="Add Device",
                    command=add_btn_clicked,
                    cursor="hand2")
add_btn.pack(side=tk.LEFT, padx=16, pady=6)

edit_btn = ttk.Button(btn_row,
                     text="Edit",
                     state=tk.DISABLED,
                     command=edit_btn_clicked,
                     cursor="hand2")
edit_btn.pack(side=tk.LEFT, padx=16, pady=6)

del_btn = ttk.Button(btn_row,
                    text="Delete",
                    state=tk.DISABLED,
                    command=del_btn_clicked,
                    cursor="hand2")
del_btn.pack(side=tk.LEFT, padx=16, pady=6)

save_btn = ttk.Button(btn_row,
                     text="Save",
                     command=save_btn_clicked,
                     cursor="hand2")
save_btn.pack(side=tk.LEFT, padx=16, pady=6)

import_btn = ttk.Button(btn_row,
                        text="Import JSON",
                        command=on_import_json_clicked,
                        cursor="hand2")
import_btn.pack(side=tk.LEFT, padx=16, pady=6)

api_btn = ttk.Button(btn_row,
                     text="Refresh from API",
                     command=on_refresh_api_clicked,
                     cursor="hand2")
api_btn.pack(side=tk.LEFT, padx=16, pady=6)

POLL_MS = 3000

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



def on_selection_change(event=None):
    selected = tatree.selection()
    if len(selected) == 1:
        edit_btn.config(state=tk.NORMAL)
        del_btn.config(state=tk.NORMAL)
        iid = selected[0]
        device = next((d for d in devices if d.get("id") == iid), None)
        show_details(device)
    else:
        edit_btn.config(state=tk.DISABLED)
        del_btn.config(state=tk.DISABLED)
        show_details(None)

tablearea = ttk.Frame(root)
tablearea.pack(fill=tk.BOTH, expand=True)
columns = ("name", "type", "battery", "tamper", "status", "last_seen")
tatree = ttk.Treeview(tablearea, columns=columns, show="headings")
tatree.heading("name", text="Name")
tatree.heading("type", text="Type")
tatree.heading("battery", text="Battery")
tatree.heading("tamper", text="Tamper")
tatree.heading("status", text="Status")
tatree.heading("last_seen", text="Last Seen")
tatree.column("name", width=220, anchor=tk.W, stretch=True)
tatree.column("type", width=120, anchor=tk.W, stretch=False)
tatree.column("battery", width=90, anchor=tk.CENTER, stretch=False)
tatree.column("tamper", width=100, anchor=tk.CENTER, stretch=False)
tatree.column("status", width=100, anchor=tk.CENTER, stretch=False)
tatree.column("last_seen", width=160, anchor=tk.W, stretch=False)

scrollbar = ttk.Scrollbar(tablearea, orient="vertical", command=tatree.yview)
tatree.configure(yscrollcommand=scrollbar.set)

for d in devices:
    insert_row(d)
    
details = ttk.LabelFrame(root, text="Details")
details.pack(fill=tk.X, padx=8, pady=6)

device_type_text = tk.Text(details, height=5, wrap="word", borderwidth=0)
details_font = tkfont.Font(family="Segoe UI", size=10)
device_type_text.configure(state="disabled", font=details_font)
device_type_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)
device_type_scroll = ttk.Scrollbar(details, orient="vertical", command=device_type_text.yview)
device_type_text.configure(yscrollcommand=device_type_scroll.set)
device_type_scroll.pack(side=tk.RIGHT, fill=tk.Y)
tatree.bind("<<TreeviewSelect>>", on_selection_change)
on_selection_change()

tatree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

statusbar = ttk.Frame(root)
statusbar.pack( side=tk.BOTTOM, fill=tk.X)
save_var = tk.StringVar()
ttk.Label(statusbar, textvariable=save_var, anchor="w").pack(side=tk.RIGHT, padx=8, pady=4)
total_var = tk.StringVar()
ttk.Label(statusbar, textvariable=total_var, anchor="w").pack(side=tk.LEFT, padx=8, pady=4)

def refresh_total_device():
    total_var.set(f"Total Devices: {len(devices)}")

refresh_total_device()

menubar.add_cascade(
    label="File",
    menu=file_menu,
    underline=0
)

file_menu.add_command(
    label="Exit",
    command=root.destroy,
)

root.after(POLL_MS, poll_api)
root.mainloop()