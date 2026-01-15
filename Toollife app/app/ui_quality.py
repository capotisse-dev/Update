import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .ui_common import HeaderFrame, FilePicker, DataTable
from .storage import get_df, save_df, safe_int

class QualityUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        self.picker = FilePicker(top, self.load_pending)
        self.picker.pack(side="left")

        tk.Button(top, text="Verify Selected", command=self.verify_selected).pack(side="left", padx=10)
        tk.Button(top, text="Edit Defect Fields", command=self.edit_defects).pack(side="left", padx=10)

        cols = ["ID","Date","Line","Machine","Tool_Num","Defects_Present","Defect_Qty","Sort_Done","Defect_Reason","Quality_Verified","Leader_Sign"]
        self.table = DataTable(self, cols)
        self.table.pack(fill="both", expand=True, padx=10, pady=10)

        self.load_pending(self.picker.get())

    def load_pending(self, filename):
        df, _ = get_df(filename)
        pending = df[df["Quality_Verified"].fillna("Pending").astype(str).str.lower().eq("pending")]
        self._filename = filename
        self.table.load(pending)

    def verify_selected(self):
        sel_id = self.table.selected_id()
        if not sel_id:
            messagebox.showwarning("Select", "Select a row first.")
            return

        df, filename = get_df(self._filename)
        idx = df.index[df["ID"].astype(str) == str(sel_id)]
        if len(idx) == 0:
            messagebox.showerror("Not found", "Row not found.")
            return

        now = datetime.now()
        df.loc[idx, "Quality_Verified"] = "Yes"
        df.loc[idx, "Quality_User"] = self.controller.user
        df.loc[idx, "Quality_Time"] = now.strftime("%Y-%m-%d %H:%M:%S")

        save_df(df, filename)
        self.load_pending(filename)

    def edit_defects(self):
        sel_id = self.table.selected_id()
        if not sel_id:
            messagebox.showwarning("Select", "Select a row first.")
            return

        df, filename = get_df(self._filename)
        idx = df.index[df["ID"].astype(str) == str(sel_id)]
        if len(idx) == 0:
            messagebox.showerror("Not found", "Row not found.")
            return
        i = idx[0]

        win = tk.Toplevel(self)
        win.title(f"Edit Defects - ID {sel_id}")
        win.geometry("420x320")

        tk.Label(win, text="Defects Present (Yes/No):").pack(anchor="w", padx=10, pady=(10, 0))
        dp = ttk.Combobox(win, values=["Yes", "No"], state="readonly")
        dp.set(str(df.at[i, "Defects_Present"] or "No"))
        dp.pack(fill="x", padx=10)

        tk.Label(win, text="Defect Qty:").pack(anchor="w", padx=10, pady=(10, 0))
        dq = tk.Entry(win)
        dq.insert(0, str(df.at[i, "Defect_Qty"] or "0"))
        dq.pack(fill="x", padx=10)

        tk.Label(win, text="Sort Done (Yes/No):").pack(anchor="w", padx=10, pady=(10, 0))
        sd = ttk.Combobox(win, values=["Yes", "No"], state="readonly")
        sd.set(str(df.at[i, "Sort_Done"] or "No"))
        sd.pack(fill="x", padx=10)

        tk.Label(win, text="Defect Reason:").pack(anchor="w", padx=10, pady=(10, 0))
        dr = tk.Entry(win)
        dr.insert(0, str(df.at[i, "Defect_Reason"] or ""))
        dr.pack(fill="x", padx=10)

        def save():
            df.at[i, "Defects_Present"] = dp.get()
            df.at[i, "Defect_Qty"] = safe_int(dq.get(), 0)
            df.at[i, "Sort_Done"] = sd.get()
            df.at[i, "Defect_Reason"] = dr.get().strip()

            save_df(df, filename)
            win.destroy()
            self.load_pending(filename)

        tk.Button(win, text="Save", command=save, bg="#28a745", fg="white").pack(pady=18)
