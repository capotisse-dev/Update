import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .ui_common import HeaderFrame, FilePicker, DataTable
from .storage import get_df, save_df

class LeaderUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        self.picker = FilePicker(top, self.load_pending)
        self.picker.pack(side="left")

        tk.Button(top, text="Sign Selected", command=self.sign_selected).pack(side="left", padx=10)

        cols = ["ID","Date","Time","Line","Machine","Tool_Num","Reason","Downtime_Mins","Leader_Sign","Quality_Verified"]
        self.table = DataTable(self, cols)
        self.table.pack(fill="both", expand=True, padx=10, pady=10)

        self.load_pending(self.picker.get())

    def load_pending(self, filename):
        df, _ = get_df(filename)
        pending = df[df["Leader_Sign"].fillna("Pending").astype(str).str.lower().eq("pending")]
        self._filename = filename
        self.table.load(pending)

    def sign_selected(self):
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
        df.loc[idx, "Leader_Sign"] = "Yes"
        df.loc[idx, "Leader_User"] = self.controller.user
        df.loc[idx, "Leader_Time"] = now.strftime("%Y-%m-%d %H:%M:%S")

        save_df(df, filename)
        self.load_pending(filename)
