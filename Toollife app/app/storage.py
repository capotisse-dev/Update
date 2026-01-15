# app/storage.py
import os
import json
from datetime import datetime
from typing import Any, Tuple, Optional

import pandas as pd

from .config import (
    DATA_DIR,
    COLUMNS,
    month_excel_path,
)

# -----------------------------
# JSON helpers (safe writes)
# -----------------------------
def load_json(path: str, default: Any):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default
        
def parts_for_line(selected_line: str):
    from .config import PARTS_FILE
    store = load_json(PARTS_FILE, {"parts": []}) or {"parts": []}
    out = []
    for p in store.get("parts", []):
        lines = p.get("lines", []) or []
        if not selected_line or selected_line in lines:
            out.append(p.get("part_number", ""))
    return sorted([x for x in out if x])

def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


# -----------------------------
# Excel schema helpers
# -----------------------------
def ensure_df_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures df has all required columns and returns df ordered by COLUMNS.
    Missing columns are added as blank.
    Extra columns are preserved at the end.
    """
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Keep extras but put known columns first
    extras = [c for c in df.columns if c not in COLUMNS]
    df = df[COLUMNS + extras]
    return df

def ensure_excel_file(path: str) -> None:
    """
    Ensures the Excel file exists and includes all columns.
    If file doesn't exist -> create empty.
    If exists -> load + add missing columns + rewrite.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if not os.path.exists(path):
        pd.DataFrame(columns=COLUMNS).to_excel(path, index=False)
        return

    try:
        df = pd.read_excel(path)
        df = ensure_df_schema(df)
        df.to_excel(path, index=False)
    except Exception:
        # Don't overwrite a possibly corrupted file.
        # Create a rescue new file so app can continue.
        base, ext = os.path.splitext(path)
        rescue = f"{base}_RESCUE_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        pd.DataFrame(columns=COLUMNS).to_excel(rescue, index=False)


# -----------------------------
# Month file utilities
# -----------------------------
def list_month_files() -> list[str]:
    """
    Returns list of tool_life_data_YYYY_MM.xlsx files found in /data
    """
    if not os.path.exists(DATA_DIR):
        return []
    files = []
    for fn in os.listdir(DATA_DIR):
        if fn.lower().startswith("tool_life_data_") and fn.lower().endswith(".xlsx"):
            files.append(fn)
    files.sort(reverse=True)  # newest first by name
    return files

def resolve_month_path(filename: Optional[str] = None) -> str:
    """
    If filename provided (e.g., 'tool_life_data_2026_01.xlsx'), return absolute path in data dir.
    Otherwise return current month path.
    """
    if filename:
        return os.path.join(DATA_DIR, filename)
    return month_excel_path(datetime.now())


# -----------------------------
# Main data access
# -----------------------------
def get_df(filename: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    """
    Load a month Excel file into DataFrame.
    Returns (df, filename_used).
    """
    path = resolve_month_path(filename)
    ensure_excel_file(path)

    # Read again (ensure_excel_file may have created/updated it)
    df = pd.read_excel(path)
    df = ensure_df_schema(df)
    return df, os.path.basename(path)

def save_df(df: pd.DataFrame, filename: str) -> None:
    """
    Save DataFrame back to month Excel file with correct schema/column order.
    filename should be a basename like 'tool_life_data_2026_01.xlsx'
    """
    path = resolve_month_path(filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = ensure_df_schema(df)
    df.to_excel(path, index=False)


# -----------------------------
# Common converters
# -----------------------------
def safe_int(val: Any, default: int = 0) -> int:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        s = str(val).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default

def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        s = str(val).strip()
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


# -----------------------------
# ID helper
# -----------------------------
def next_id(df: pd.DataFrame) -> str:
    """
    Generates a reasonably unique ID for a new row.
    Format: YYYYMMDD-HHMMSS-XXXX
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Use row count + time as pseudo-random 4 digits
    suffix = str(len(df) % 10000).zfill(4)
    return f"{ts}-{suffix}"
