import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

from gui.handlers import (
    init_handlers, add_btn_clicked, edit_btn_clicked, del_btn_clicked, save_btn_clicked,
    on_import_json_clicked, on_refresh_api_clicked, open_last_image_for_selected,
    on_selection_change, start_polling
)
from gui import handlers

def main():
    root = tk.Tk()
    try:
        tkfont.nametofont("TkDefaultFont").configure(family="Segoe UI", size=10)
        tkfont.nametofont("TkTextFont").configure(family="Segoe UI", size=10)
        tkfont.nametofont("TkHeadingFont").configure(family="Segoe UI", size=10, weight="bold")
        tkfont.nametofont("TkMenuFont").configure(family="Segoe UI", size=10)
        tkfont.nametofont("TkFixedFont").configure(family="Consolas", size=10)
    except tk.TclError:
        pass

    root.title("OpTech Device Tracker")
    root.geometry("1024x768")
    root.minsize(900, 900)

    menubar = tk.Menu(root); root.config(menu=menubar)
    file_menu = tk.Menu(menubar, tearoff=False); menubar.add_cascade(label="File", menu=file_menu, underline=0)

    toolbar = ttk.Frame(root); toolbar.pack(side=tk.TOP, fill=tk.X)
    btn_row = ttk.Frame(toolbar); btn_row.pack()

    add_btn  = ttk.Button(btn_row, text="Add Device",  command=add_btn_clicked, cursor="hand2")
    edit_btn = ttk.Button(btn_row, text="Edit",        state=tk.DISABLED, command=edit_btn_clicked, cursor="hand2")
    del_btn  = ttk.Button(btn_row, text="Delete",      state=tk.DISABLED, command=del_btn_clicked, cursor="hand2")
    save_btn = ttk.Button(btn_row, text="Save",        command=save_btn_clicked, cursor="hand2")
    imp_btn  = ttk.Button(btn_row, text="Import JSON", command=on_import_json_clicked, cursor="hand2")
    api_btn  = ttk.Button(btn_row, text="Refresh from API", command=on_refresh_api_clicked, cursor="hand2")
    img_btn = ttk.Button(btn_row,
                         text="Live Snapshot",
                         command=handlers.open_device_snapshot,   # <- call the new handler
                         state=tk.DISABLED,
                         cursor="hand2",
                         )
    img_btn.pack(side=tk.LEFT, padx=16, pady=6)


    
    for b in (add_btn, edit_btn, del_btn, save_btn, imp_btn, api_btn, img_btn):
        b.pack(side=tk.LEFT, padx=16, pady=6)

    tablearea = ttk.Frame(root); tablearea.pack(fill=tk.BOTH, expand=True)
    columns = ("name", "type", "battery", "tamper", "status", "last_seen")
    tatree = ttk.Treeview(tablearea, columns=columns, show="headings")
    for col, text, width, anchor in [
        ("name","Name",220,"w"),
        ("type","Type",120,"w"),
        ("battery","Battery",90,"center"),
        ("tamper","Tamper",100,"center"),
        ("status","Status",100,"center"),
        ("last_seen","Last Seen",160,"w"),
    ]:
        tatree.heading(col, text=text)
        tatree.column(col, width=width, anchor=getattr(tk, anchor.upper()), stretch=(col=="name"))
    scrollbar = ttk.Scrollbar(tablearea, orient="vertical", command=tatree.yview)
    tatree.configure(yscrollcommand=scrollbar.set)
    tatree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Details Area
    details = ttk.LabelFrame(root, text="Details"); details.pack(fill=tk.X, padx=8, pady=6)
    details_text = tk.Text(details, height=6, wrap="word", borderwidth=0)
    details_text.configure(state="disabled", font=tkfont.Font(family="Segoe UI", size=10))
    details_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)
    details_scroll = ttk.Scrollbar(details, orient="vertical", command=details_text.yview)
    details_text.configure(yscrollcommand=details_scroll.set)
    details_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Status Bar
    statusbar = ttk.Frame(root); statusbar.pack(side=tk.BOTTOM, fill=tk.X)
    save_var = tk.StringVar(); ttk.Label(statusbar, textvariable=save_var, anchor="w").pack(side=tk.RIGHT, padx=8, pady=4)
    total_var = tk.StringVar(); ttk.Label(statusbar, textvariable=total_var, anchor="w").pack(side=tk.LEFT, padx=8, pady=4)

    # Init and wire selection
    init_handlers(root, tatree, details_text, img_btn, edit_btn, del_btn, save_var, total_var, poll_ms=10_000)
    tatree.bind("<<TreeviewSelect>>", on_selection_change)

    # File Menu
    from gui.handlers import open_settings
    file_menu.add_command(label="Settings…", command=open_settings)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.destroy)

    start_polling(10_000)

    root.mainloop()

if __name__ == "__main__":
    main()
