import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import pandas as pd

from .ui_common import HeaderFrame
from .storage import get_df, save_df, next_id, safe_int, safe_float, load_json
from .config import REASONS_FILE, PARTS_FILE, TOOL_CONFIG_FILE

class ToolChangerUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        body = tk.Frame(self, bg=controller.colors["bg"], padx=20, pady=20)
        body.pack(fill="both", expand=True)

        style = {"bg": controller.colors["bg"], "fg": controller.colors["fg"]}

        tk.Label(body, text="Tool Changer Entry", font=("Arial", 16, "bold"), **style).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))

        # Line
        tk.Label(body, text="Line:", **style).grid(row=1, column=0, sticky="e", pady=5)
        self.line_cb = ttk.Combobox(body, values=["U725", "JL"], state="readonly", width=20)
        self.line_cb.current(0)
        self.line_cb.grid(row=1, column=1, sticky="w")
        self.line_cb.bind("<<ComboboxSelected>>", self.update_machines)

        # Shift
        tk.Label(body, text="Shift:", **style).grid(row=2, column=0, sticky="e", pady=5)
        self.shift_cb = ttk.Combobox(body, values=["1st", "2nd", "3rd"], state="readonly", width=20)
        self.shift_cb.current(0)
        self.shift_cb.grid(row=2, column=1, sticky="w")

        # Machine
        tk.Label(body, text="Machine:", **style).grid(row=3, column=0, sticky="e", pady=5)
        self.mach_cb = ttk.Combobox(body, state="readonly", width=20)
        self.mach_cb.grid(row=3, column=1, sticky="w")
        self.mach_cb.bind("<<ComboboxSelected>>", self.update_tools)

        # Part
        tk.Label(body, text="Part #:", **style).grid(row=4, column=0, sticky="e", pady=5)
        parts = load_json(PARTS_FILE, [])
        self.part_cb = ttk.Combobox(body, values=parts, width=20)  # allow typing
        self.part_cb.grid(row=4, column=1, sticky="w")

        # Tool
        tk.Label(body, text="Tool #:", **style).grid(row=5, column=0, sticky="e", pady=5)
        self.tool_cb = ttk.Combobox(body, state="readonly", width=20)
        self.tool_cb.grid(row=5, column=1, sticky="w")
        self.tool_cb.bind("<<ComboboxSelected>>", self.update_stock_display)

        self.stock_lbl = tk.Label(body, text="Stock: N/A", fg="blue", bg=controller.colors["bg"], font=("Arial", 10, "bold"))
        self.stock_lbl.grid(row=5, column=2, sticky="w", padx=10)

        # Reason
        tk.Label(body, text="Reason:", **style).grid(row=6, column=0, sticky="e", pady=5)
        reasons = load_json(REASONS_FILE, [])
        self.reason_cb = ttk.Combobox(body, values=reasons, state="readonly", width=28)
        self.reason_cb.grid(row=6, column=1, sticky="w")

        # Downtime
        tk.Label(body, text="Downtime (min):", **style).grid(row=7, column=0, sticky="e", pady=5)
        self.down_entry = tk.Entry(body, width=10)
        self.down_entry.insert(0, "0")
        self.down_entry.grid(row=7, column=1, sticky="w")

        # Defects?
        self.defect_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            body, text="Were defects produced?", variable=self.defect_var, command=self.toggle_defect,
            bg=controller.colors["bg"], fg=controller.colors["fg"], font=("Arial", 12)
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.defect_frame = tk.Frame(body, borderwidth=1, relief="solid", padx=10, pady=10, bg=controller.colors["bg"])
        tk.Label(self.defect_frame, text="Defect Qty:", **style).pack(anchor="w")
        self.qty_entry = tk.Entry(self.defect_frame)
        self.qty_entry.insert(0, "0")
        self.qty_entry.pack(fill="x", pady=5)

        self.sort_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.defect_frame, text="Was sort done?", variable=self.sort_var,
                       bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(anchor="w")

        tk.Label(self.defect_frame, text="Defect Reason:", **style).pack(anchor="w", pady=(10, 0))
        self.defect_reason = tk.Entry(self.defect_frame)
        self.defect_reason.pack(fill="x", pady=5)

        # Submit
        tk.Button(
            body, text="SUBMIT ENTRY", command=self.submit,
            bg="#28a745", fg="white", font=("Arial", 14, "bold"), height=2
        ).grid(row=10, column=0, columnspan=3, pady=20, sticky="we")

        self.update_machines()

    def update_machines(self, event=None):
        line = self.line_cb.get()
        if line == "U725":
            machs = [f"Machine {i}" for i in range(1, 10)]
        else:
            machs = [f"Machine {i}" for i in range(1, 9)] + ["FF1", "FF2", "FF3"]
        self.mach_cb["values"] = machs
        self.mach_cb.set("")
        self.tool_cb.set("")
        self.stock_lbl.config(text="Stock: N/A")

    def update_tools(self, event=None):
        line = self.line_cb.get()
        machine = self.mach_cb.get()
        if not machine:
            return

        tools = []
        if line == "U725":
            tools = [str(i) for i in range(1, 24)] + ["60"]
        elif line == "JL":
            if machine.startswith("Machine"):
                num = int(machine.split(" ")[1])
                if 1 <= num <= 4:
                    tools = ["2", "4", "5", "9", "10", "11", "15", "16", "25", "26", "40"]
                elif 5 <= num <= 8:
                    tools = ["2", "5", "6", "10", "11", "16", "21", "23", "25", "26", "27", "40"]
            elif machine.startswith("FF"):
                tools = [str(i) for i in range(201, 216)] + ["60"]

        try:
            tools.sort(key=int)
        except Exception:
            tools.sort()

        self.tool_cb["values"] = tools

    def update_stock_display(self, event=None):
        tool = self.tool_cb.get()
        cfg = load_json(TOOL_CONFIG_FILE, {})
        key = f"Tool {tool}"
        if key in cfg:
            self.stock_lbl.config(text=f"Stock: {cfg[key].get('stock', 'N/A')}")
        else:
            self.stock_lbl.config(text="Stock: N/A")

    def toggle_defect(self):
        if self.defect_var.get():
            self.defect_frame.grid(row=9, column=0, columnspan=2, sticky="we", pady=10)
        else:
            self.defect_frame.grid_remove()

    def submit(self):
        if not self.mach_cb.get() or not self.tool_cb.get() or not self.reason_cb.get():
            messagebox.showwarning("Missing Info", "Select Machine, Tool, and Reason")
            return

        downtime = safe_int(self.down_entry.get(), 0)

        cfg = load_json(TOOL_CONFIG_FILE, {})
        tool_key = f"Tool {self.tool_cb.get()}"
        cost = 0.0

        # Inventory decrement (if configured)
        if tool_key in cfg:
            cost = safe_float(cfg[tool_key].get("cost", 0), 0.0)
            stock = safe_int(cfg[tool_key].get("stock", 0), 0)
            if stock <= 0:
                if not messagebox.askyesno("Stock Warning", f"{tool_key} is out of stock! Submit anyway?"):
                    return
            else:
                cfg[tool_key]["stock"] = stock - 1
                from .storage import save_json
                save_json(TOOL_CONFIG_FILE, cfg)

        df, filename = get_df()  # current month
        now = datetime.now()

        defects = "Yes" if self.defect_var.get() else "No"
        defect_qty = safe_int(self.qty_entry.get(), 0)
        sort = "Yes" if self.sort_var.get() else "No"
        defect_reason = self.defect_reason.get().strip() if self.defect_var.get() else ""

        new_row = {
            "ID": next_id(df),
            "Date": now.strftime("%Y-%m-%d"),
            "Time": now.strftime("%H:%M:%S"),
            "Shift": self.shift_cb.get(),
            "Line": self.line_cb.get(),
            "Machine": self.mach_cb.get(),
            "Part_Number": self.part_cb.get(),
            "Tool_Num": str(self.tool_cb.get()),
            "Reason": self.reason_cb.get(),
            "Downtime_Mins": downtime,
            "Cost": float(cost),
            "Tool_Changer": self.controller.user,
            "Defects_Present": defects,
            "Defect_Qty": defect_qty,
            "Sort_Done": sort,
            "Defect_Reason": defect_reason,
            "Quality_Verified": "Pending",
            "Quality_User": "",
            "Quality_Time": "",
            "Leader_Sign": "Pending",
            "Leader_User": "",
            "Leader_Time": "",
            "Serial_Numbers": ""
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_df(df, filename)

        messagebox.showinfo("Saved", f"Entry saved.\nTool cost: ${cost:,.2f}")

        # reset defect UI
        self.defect_var.set(False)
        self.toggle_defect()
        self.qty_entry.delete(0, "end"); self.qty_entry.insert(0, "0")
        self.sort_var.set(False)
        self.defect_reason.delete(0, "end")
        self.update_stock_display()
