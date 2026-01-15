# app/ui_admin.py
import tkinter as tk
from tkinter import ttk, messagebox

from .ui_common import HeaderFrame
from .storage import load_json, save_json
from .config import USERS_FILE
from .ui_action_center import ActionCenterUI


class AdminUI(tk.Frame):
    """
    Admin UI (restricted):
    - NO direct editing of production data.
    - Can manage users only:
        * create users
        * set username, password, display name, role
    - Includes Action Center tab (Admin can create/assign).
    """
    ROLE_OPTIONS = [
        "Operator",
        "Tool Changer",
        "Leader",
        "Quality",
        "Top (Super User)",
        "Admin"
    ]

    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Tabs
        tab_users = tk.Frame(nb, bg=controller.colors["bg"])
        tab_actions = tk.Frame(nb, bg=controller.colors["bg"])

        nb.add(tab_users, text="User Management")
        nb.add(tab_actions, text="Action Center")

        self._build_user_management(tab_users)
        # Action Center: no extra header inside tab
        try:
            ActionCenterUI(tab_actions, controller, show_header=False).pack(fill="both", expand=True)
        except TypeError:
            ActionCenterUI(tab_actions, controller).pack(fill="both", expand=True)

    # -------------------------
    def _build_user_management(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Create Users (Admin Only)",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_users).pack(side="right")

        # Form
        form = tk.LabelFrame(
            parent,
            text="New User",
            padx=10,
            pady=10,
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        )
        form.pack(fill="x", padx=10, pady=(0, 10))

        self.var_username = tk.StringVar(value="")
        self.var_password = tk.StringVar(value="")
        self.var_name = tk.StringVar(value="")
        self.var_role = tk.StringVar(value=self.ROLE_OPTIONS[0])

        self._form_row(form, "Username", self.var_username)
        self._form_row(form, "Password", self.var_password, show="*")
        self._form_row(form, "Display Name", self.var_name)

        r = tk.Frame(form, bg=self.controller.colors["bg"])
        r.pack(fill="x", pady=4)
        tk.Label(
            r,
            text="Role",
            width=14,
            anchor="w",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        ).pack(side="left")
        ttk.Combobox(r, textvariable=self.var_role, state="readonly", values=self.ROLE_OPTIONS, width=24).pack(side="left")

        btns = tk.Frame(form)
        btns.pack(fill="x", pady=(10, 0))
        tk.Button(btns, text="Create User", command=self.create_user).pack(side="right")

        # User list (read-only display)
        listbox_frame = tk.LabelFrame(
            parent,
            text="Existing Users (read-only)",
            padx=10,
            pady=10,
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        )
        listbox_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("username", "name", "role")
        self.tree = ttk.Treeview(listbox_frame, columns=cols, show="headings", height=14)
        for c in cols:
            self.tree.heading(c, text=c.upper())
            if c == "username":
                self.tree.column(c, width=220)
            elif c == "name":
                self.tree.column(c, width=260)
            else:
                self.tree.column(c, width=180)
        self.tree.pack(fill="both", expand=True)

        note = tk.Label(
            parent,
            text="Note: User editing/deletion is intentionally disabled in this Admin UI for safety.\n"
                 "If you need edit/delete later, we can add a guarded 'Maintenance Mode' with confirmations + audit log.",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"]
        )
        note.pack(anchor="w", padx=12, pady=(0, 10))

        self.refresh_users()

    def _form_row(self, parent, label, var, show=None):
        r = tk.Frame(parent, bg=self.controller.colors["bg"])
        r.pack(fill="x", pady=4)
        tk.Label(
            r,
            text=label,
            width=14,
            anchor="w",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        ).pack(side="left")
        e = tk.Entry(r, textvariable=var, show=show) if show else tk.Entry(r, textvariable=var)
        e.pack(side="left", fill="x", expand=True)

    # -------------------------
    def refresh_users(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        users = load_json(USERS_FILE, {}) or {}
        # users format expected: { "username": { "password": "...", "role": "...", "name": "..." }, ... }

        for username in sorted(users.keys()):
            u = users.get(username, {}) or {}
            self.tree.insert("", "end", values=(
                username,
                u.get("name", ""),
                u.get("role", "")
            ))

    def create_user(self):
        username = self.var_username.get().strip()
        password = self.var_password.get().strip()
        name = self.var_name.get().strip()
        role = self.var_role.get().strip()

        if not username:
            messagebox.showerror("Error", "Username is required.")
            return
        if not password:
            messagebox.showerror("Error", "Password is required.")
            return
        if not name:
            messagebox.showerror("Error", "Display Name is required.")
            return
        if role not in self.ROLE_OPTIONS:
            messagebox.showerror("Error", "Select a valid role.")
            return

        users = load_json(USERS_FILE, {}) or {}

        if username in users:
            messagebox.showerror("Error", f"Username '{username}' already exists.")
            return

        users[username] = {
            "password": password,   # NOTE: plain text; we can hash later if you want
            "role": role,
            "name": name
        }

        save_json(USERS_FILE, users)

        # Clear inputs
        self.var_username.set("")
        self.var_password.set("")
        self.var_name.set("")
        self.var_role.set(self.ROLE_OPTIONS[0])

        messagebox.showinfo("Created", f"User '{username}' created.")
        self.refresh_users()
