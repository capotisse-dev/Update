# app/ui_master_data.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .storage import load_json, save_json, safe_float
from .config import TOOL_CONFIG_FILE, PARTS_FILE, COST_CONFIG_FILE


def _normalize_parts_store(store):
    """
    Accept either:
      - {"parts":[...]}  (preferred)
      - [...]            (legacy)
    Always return {"parts":[...]}.
    """
    if isinstance(store, list):
        return {"parts": store}
    if isinstance(store, dict):
        # Optional legacy shape: {"data":[...]}
        if "parts" not in store and isinstance(store.get("data"), list):
            return {"parts": store["data"]}
        store.setdefault("parts", [])
        if not isinstance(store["parts"], list):
            store["parts"] = []
        return store
    return {"parts": []}


def _normalize_tool_store(store):
    """
    Accept either:
      - {"tools": {...}} (preferred)
      - {...}            (legacy tools dict)
    Always return {"tools": {...}}.
    """
    if isinstance(store, dict):
        if "tools" in store and isinstance(store["tools"], dict):
            return store
        # If it looks like a tool map, wrap it
        return {"tools": store}
    return {"tools": {}}
    
def _normalize_cost_store(store):
    """
    Ensure cost config has a dict scrap_cost_by_part.
    """
    if not isinstance(store, dict):
        store = {}
    store.setdefault("scrap_cost_by_part", {})
    if not isinstance(store["scrap_cost_by_part"], dict):
        store["scrap_cost_by_part"] = {}
    store.setdefault("scrap_cost_default", 0.0)
    return store



def _normalize_parts_store(store):
    """
    Accept:
      - {"parts":[...]}  (preferred)
      - [...]            (legacy)
      - {"parts":["PN1","PN2"]} (bad legacy)
    Ensure all entries are dicts:
      {"part_number": "...", "name": "", "lines": []}
    """
    # Wrap list into dict
    if isinstance(store, list):
        store = {"parts": store}

    # If it's not a dict, return empty
    if not isinstance(store, dict):
        return {"parts": []}

    # Optional legacy: {"data":[...]}
    if "parts" not in store and isinstance(store.get("data"), list):
        store = {"parts": store["data"]}

    parts = store.get("parts", [])
    if not isinstance(parts, list):
        parts = []

    cleaned = []
    for item in parts:
        # If item is a string like "PN123"
        if isinstance(item, str):
            cleaned.append({"part_number": item.strip(), "name": "", "lines": []})
            continue

        # If item is a dict, normalize keys
        if isinstance(item, dict):
            pn = (item.get("part_number") or item.get("pn") or item.get("part") or "").strip()
            nm = (item.get("name") or "").strip()
            ln = item.get("lines") or []
            if isinstance(ln, str):
                ln = [x.strip() for x in ln.split(",") if x.strip()]
            if not isinstance(ln, list):
                ln = []
            cleaned.append({"part_number": pn, "name": nm, "lines": ln})
            continue

        # Ignore anything else (numbers, None, etc.)

    # Drop empty part_numbers
    cleaned = [p for p in cleaned if p.get("part_number")]

    return {"parts": cleaned}



class MasterDataUI(tk.Frame):
    """
    Super/Admin Master Data:
      - Tool pricing
      - Parts + line assignments
      - Scrap pricing by part
    Robust against legacy JSON shapes.
    """

    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        tab_tools = tk.Frame(nb, bg=controller.colors["bg"])
        tab_parts = tk.Frame(nb, bg=controller.colors["bg"])
        tab_scrap = tk.Frame(nb, bg=controller.colors["bg"])

        nb.add(tab_tools, text="Tool Pricing")
        nb.add(tab_parts, text="Parts & Lines")
        nb.add(tab_scrap, text="Scrap Pricing")

        # Stores (loaded in refresh functions)
        self.tool_store = {"tools": {}}
        self.parts_store = {"parts": []}
        self.cost_store = {"scrap_cost_by_part": {}, "scrap_cost_default": 0.0}

        self._build_tool_pricing(tab_tools)
        self._build_parts(tab_parts)
        self._build_scrap(tab_scrap)

    # -------------------- TOOL PRICING --------------------
    def _build_tool_pricing(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Tool Pricing",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_tools).pack(side="right")
        tk.Button(top, text="Save", command=self.save_tools).pack(side="right", padx=8)

        form = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=6)
        form.pack(fill="x")

        self.tool_id = tk.StringVar()
        self.tool_name = tk.StringVar()
        self.tool_cost = tk.StringVar()

        tk.Label(form, text="Tool #", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=0, sticky="w")
        tk.Entry(form, textvariable=self.tool_id, width=16).grid(row=0, column=1, padx=8)

        tk.Label(form, text="Name", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=2, sticky="w")
        tk.Entry(form, textvariable=self.tool_name, width=30).grid(row=0, column=3, padx=8)

        tk.Label(form, text="Unit Cost ($)", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=4, sticky="w")
        tk.Entry(form, textvariable=self.tool_cost, width=12).grid(row=0, column=5, padx=8)

        tk.Button(form, text="Add / Update", command=self.add_update_tool).grid(row=0, column=6, padx=10)
        tk.Button(form, text="Delete Selected", command=self.delete_selected_tool).grid(row=0, column=7, padx=6)

        cols = ("tool", "name", "unit_cost")
        self.tool_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.tool_tree.heading(c, text=c.upper())
            self.tool_tree.column(c, width=240 if c != "unit_cost" else 140)
        self.tool_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_tools()

    def refresh_tools(self):
        for i in self.tool_tree.get_children():
            self.tool_tree.delete(i)

        raw = load_json(TOOL_CONFIG_FILE, {"tools": {}})
        self.tool_store = _normalize_tool_store(raw)

        tools = self.tool_store.get("tools", {}) or {}
        for t in sorted(tools.keys()):
            self.tool_tree.insert("", "end", values=(
                t,
                tools[t].get("name", ""),
                tools[t].get("unit_cost", 0.0),
            ))

    def add_update_tool(self):
        tid = self.tool_id.get().strip()
        if not tid:
            messagebox.showerror("Error", "Tool # is required.")
            return

        name = self.tool_name.get().strip()
        cost = safe_float(self.tool_cost.get(), 0.0)

        self.tool_store.setdefault("tools", {})
        self.tool_store["tools"][tid] = {"name": name, "unit_cost": cost}

        self.tool_id.set("")
        self.tool_name.set("")
        self.tool_cost.set("")
        self.refresh_tools()

    def delete_selected_tool(self):
        sel = self.tool_tree.selection()
        if not sel:
            return
        tool = self.tool_tree.item(sel[0], "values")[0]
        if not tool:
            return
        if not messagebox.askyesno("Confirm", f"Delete tool '{tool}'?"):
            return
        self.tool_store.setdefault("tools", {})
        self.tool_store["tools"].pop(tool, None)
        self.refresh_tools()

    def save_tools(self):
        save_json(TOOL_CONFIG_FILE, self.tool_store)
        messagebox.showinfo("Saved", "Tool pricing saved.")

    # -------------------- PARTS & LINES --------------------
    def _build_parts(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Parts & Line Assignment",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_parts).pack(side="right")
        tk.Button(top, text="Save", command=self.save_parts).pack(side="right", padx=8)

        form = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=6)
        form.pack(fill="x")

        self.part_no = tk.StringVar()
        self.part_name = tk.StringVar()
        self.part_lines = tk.StringVar()

        tk.Label(form, text="Part #", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=0, sticky="w")
        tk.Entry(form, textvariable=self.part_no, width=18).grid(row=0, column=1, padx=8)

        tk.Label(form, text="Name", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=2, sticky="w")
        tk.Entry(form, textvariable=self.part_name, width=30).grid(row=0, column=3, padx=8)

        tk.Label(form, text="Lines (comma sep)", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=4, sticky="w")
        tk.Entry(form, textvariable=self.part_lines, width=28).grid(row=0, column=5, padx=8)

        tk.Button(form, text="Add / Update", command=self.add_update_part).grid(row=0, column=6, padx=10)
        tk.Button(form, text="Delete Selected", command=self.delete_selected_part).grid(row=0, column=7, padx=6)

        cols = ("part_number", "name", "lines")
        self.part_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.part_tree.heading(c, text=c.upper())
            self.part_tree.column(c, width=260 if c != "lines" else 420)
        self.part_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_parts()

    def refresh_parts(self):
        for i in self.part_tree.get_children():
            self.part_tree.delete(i)

        raw = load_json(PARTS_FILE, {"parts": []})
        self.parts_store = _normalize_parts_store(raw)
        # Auto-heal file format once it loads correctly
        save_json(PARTS_FILE, self.parts_store

        for p in self.parts_store.get("parts", []):
            self.part_tree.insert("", "end", values=(
                p.get("part_number", ""),
                p.get("name", ""),
                ", ".join(p.get("lines", []) or []),
            ))

    def add_update_part(self):
        pn = self.part_no.get().strip()
        if not pn:
            messagebox.showerror("Error", "Part # is required.")
            return

        name = self.part_name.get().strip()
        lines = [x.strip() for x in (self.part_lines.get() or "").split(",") if x.strip()]

        store = self.parts_store or {"parts": []}
        store = _normalize_parts_store(store)
        parts = store.get("parts", [])

        for p in parts:
            if p.get("part_number") == pn:
                p["name"] = name
                p["lines"] = lines
                self.parts_store = store
                self.part_no.set("")
                self.part_name.set("")
                self.part_lines.set("")
                self.refresh_parts()
                return

        parts.append({"part_number": pn, "name": name, "lines": lines})
        store["parts"] = parts
        self.parts_store = store

        self.part_no.set("")
        self.part_name.set("")
        self.part_lines.set("")
        self.refresh_parts()

    def delete_selected_part(self):
        sel = self.part_tree.selection()
        if not sel:
            return
        pn = self.part_tree.item(sel[0], "values")[0]
        if not pn:
            return
        if not messagebox.askyesno("Confirm", f"Delete part '{pn}'?"):
            return

        store = _normalize_parts_store(self.parts_store)
        store["parts"] = [p for p in store.get("parts", []) if p.get("part_number") != pn]
        self.parts_store = store
        self.refresh_parts()

    def save_parts(self):
        # Always save in canonical dict format
        save_json(PARTS_FILE, _normalize_parts_store(self.parts_store))
        messagebox.showinfo("Saved", "Parts saved.")

    # -------------------- SCRAP PRICING --------------------
    def _build_scrap(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Scrap Pricing (by Part)",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_scrap).pack(side="right")
        tk.Button(top, text="Save", command=self.save_scrap).pack(side="right", padx=8)

        form = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=6)
        form.pack(fill="x")

        self.scrap_part = tk.StringVar()
        self.scrap_cost = tk.StringVar()

        tk.Label(form, text="Part #", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=0, sticky="w")
        tk.Entry(form, textvariable=self.scrap_part, width=18).grid(row=0, column=1, padx=8)

        tk.Label(form, text="Scrap Cost ($)", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=2, sticky="w")
        tk.Entry(form, textvariable=self.scrap_cost, width=12).grid(row=0, column=3, padx=8)

        tk.Button(form, text="Add / Update", command=self.add_update_scrap).grid(row=0, column=4, padx=10)
        tk.Button(form, text="Delete Selected", command=self.delete_selected_scrap).grid(row=0, column=5, padx=6)

        cols = ("part_number", "scrap_cost")
        self.scrap_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.scrap_tree.heading(c, text=c.upper())
            self.scrap_tree.column(c, width=260)
        self.scrap_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_scrap()

    def refresh_scrap(self):
        for i in self.scrap_tree.get_children():
            self.scrap_tree.delete(i)

        raw = load_json(COST_CONFIG_FILE, {})
        self.cost_store = _normalize_cost_store(raw)

        m = self.cost_store.get("scrap_cost_by_part", {}) or {}
        for pn in sorted(m.keys()):
            self.scrap_tree.insert("", "end", values=(pn, m[pn]))

    def add_update_scrap(self):
        pn = self.scrap_part.get().strip()
        if not pn:
            messagebox.showerror("Error", "Part # is required.")
            return

        cost = safe_float(self.scrap_cost.get(), 0.0)
        self.cost_store = _normalize_cost_store(self.cost_store)
        self.cost_store["scrap_cost_by_part"][pn] = cost

        self.scrap_part.set("")
        self.scrap_cost.set("")
        self.refresh_scrap()

    def delete_selected_scrap(self):
        sel = self.scrap_tree.selection()
        if not sel:
            return
        pn = self.scrap_tree.item(sel[0], "values")[0]
        if not pn:
            return
        if not messagebox.askyesno("Confirm", f"Delete scrap price for '{pn}'?"):
            return
        self.cost_store = _normalize_cost_store(self.cost_store)
        self.cost_store["scrap_cost_by_part"].pop(pn, None)
        self.refresh_scrap()

    def save_scrap(self):
        save_json(COST_CONFIG_FILE, _normalize_cost_store(self.cost_store))
        messagebox.showinfo("Saved", "Scrap pricing saved.")
