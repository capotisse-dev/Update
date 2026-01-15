# app/action_store.py
from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import ACTIONS_FILE, NCRS_FILE, USERS_FILE
from .storage import load_json, save_json


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def get_users_map() -> Dict[str, Dict[str, Any]]:
    return load_json(USERS_FILE, {}) or {}


def list_usernames() -> List[str]:
    users = get_users_map()
    names = sorted([u for u in users.keys()])
    return names


def _ensure_actions_shape(store: Any) -> Dict[str, Any]:
    if not isinstance(store, dict):
        store = {}
    store.setdefault("version", 1)
    store.setdefault("actions", [])
    if not isinstance(store["actions"], list):
        store["actions"] = []
    return store


def _ensure_ncrs_shape(store: Any) -> Dict[str, Any]:
    if not isinstance(store, dict):
        store = {}
    store.setdefault("version", 1)
    store.setdefault("ncrs", [])
    if not isinstance(store["ncrs"], list):
        store["ncrs"] = []
    return store


def load_actions_store() -> Dict[str, Any]:
    return _ensure_actions_shape(load_json(ACTIONS_FILE, {"version": 1, "actions": []}))


def save_actions_store(store: Dict[str, Any]) -> None:
    store = _ensure_actions_shape(store)
    save_json(ACTIONS_FILE, store)


def load_ncrs_store() -> Dict[str, Any]:
    return _ensure_ncrs_shape(load_json(NCRS_FILE, {"version": 1, "ncrs": []}))


def save_ncrs_store(store: Dict[str, Any]) -> None:
    store = _ensure_ncrs_shape(store)
    save_json(NCRS_FILE, store)


def upsert_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Action schema (minimal):
    {
      "action_id", "type": "Action"|"NCR",
      "title", "severity": Low/Medium/High/Critical,
      "status": Open/In Progress/Blocked/Closed,
      "owner", "created_by", "created_at",
      "due_date", "line", "part_number",
      "related": { "ncr_id": "...", "entry_id": "..." },
      "notes"
    }
    """
    store = load_actions_store()
    actions = store["actions"]

    if not action.get("action_id"):
        action["action_id"] = new_id("A")
    action.setdefault("type", "Action")
    action.setdefault("severity", "Medium")
    action.setdefault("status", "Open")
    action.setdefault("created_at", now_iso())
    action.setdefault("notes", "")
    action.setdefault("related", {})

    found = False
    for i, a in enumerate(actions):
        if a.get("action_id") == action["action_id"]:
            actions[i] = {**a, **action, "updated_at": now_iso()}
            found = True
            break

    if not found:
        action["updated_at"] = now_iso()
        actions.append(action)

    store["actions"] = actions
    save_actions_store(store)
    return action


def set_action_status(action_id: str, status: str, closed_by: Optional[str] = None) -> None:
    store = load_actions_store()
    for a in store["actions"]:
        if a.get("action_id") == action_id:
            a["status"] = status
            a["updated_at"] = now_iso()
            if status == "Closed":
                a["closed_at"] = now_iso()
                if closed_by:
                    a["closed_by"] = closed_by
            break
    save_actions_store(store)


def upsert_ncr(ncr: Dict[str, Any]) -> Dict[str, Any]:
    """
    NCR schema (minimal):
    {
      "ncr_id", "status": Open/Contained/Verified/Closed,
      "part_number", "line", "owner",
      "description", "created_at", "created_by",
      "close_date", "related_entry_id"
    }
    """
    store = load_ncrs_store()
    ncrs = store["ncrs"]

    if not ncr.get("ncr_id"):
        ncr["ncr_id"] = new_id("NCR")
    ncr.setdefault("status", "Open")
    ncr.setdefault("created_at", now_iso())

    found = False
    for i, x in enumerate(ncrs):
        if x.get("ncr_id") == ncr["ncr_id"]:
            ncrs[i] = {**x, **ncr, "updated_at": now_iso()}
            found = True
            break
    if not found:
        ncr["updated_at"] = now_iso()
        ncrs.append(ncr)

    store["ncrs"] = ncrs
    save_ncrs_store(store)
    return ncr


def set_ncr_status(ncr_id: str, status: str) -> None:
    store = load_ncrs_store()
    for n in store["ncrs"]:
        if n.get("ncr_id") == ncr_id:
            n["status"] = status
            n["updated_at"] = now_iso()
            if status == "Closed":
                n["close_date"] = datetime.now().strftime("%Y-%m-%d")
            break
    save_ncrs_store(store)


def create_ncr_and_action(
    *,
    title: str,
    description: str,
    severity: str,
    owner: str,
    created_by: str,
    line: str = "",
    part_number: str = "",
    due_date: str = "",
    related_entry_id: str = ""
) -> Dict[str, Any]:
    """
    Creates an NCR record AND creates a linked Action Center item (type="NCR").
    """
    ncr = upsert_ncr({
        "status": "Open",
        "part_number": part_number,
        "line": line,
        "owner": owner,
        "description": description,
        "created_by": created_by,
        "related_entry_id": related_entry_id,
    })

    action = upsert_action({
        "type": "NCR",
        "title": title or f"NCR {ncr['ncr_id']}",
        "severity": severity,
        "status": "Open",
        "owner": owner,
        "created_by": created_by,
        "due_date": due_date,
        "line": line,
        "part_number": part_number,
        "related": {"ncr_id": ncr["ncr_id"], "entry_id": related_entry_id},
        "notes": description
    })

    # back-link (optional)
    ncr = upsert_ncr({**ncr, "action_id": action["action_id"]})

    return {"ncr": ncr, "action": action}
