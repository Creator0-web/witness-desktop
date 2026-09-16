"""Small rotating task queue for the Arena Activity Forge.

These are intentionally different from normal Activities:
- at most five named tasks are queued at once
- every queued task shares one XP value configured in Settings
- completing a task awards canonical XP, then removes it from the queue
- the queue is stored in syncable game_state so desktop/laptop stay aligned

The XP itself is recorded through one hidden repeatable scoring Activity so the
normal immutable XP ledger, Ghost, Levels, records and cross-device XP sync all
continue to use the canonical game engine.
"""
from __future__ import annotations

import json
import time
import uuid

import db
import game_engine

TASKS_KEY = "micro_tasks_v1"
SYSTEM_ACTIVITY_NAME = "Quick Task"
DEFAULT_XP = 25
MAX_TASKS = 5
SYSTEM_SORT_ORDER = 1_000_000


def is_system_activity(activity) -> bool:
    try:
        return (
            str((activity or {}).get("name", "")).strip().casefold() == SYSTEM_ACTIVITY_NAME.casefold()
            and int((activity or {}).get("sort_order", -1)) == SYSTEM_SORT_ORDER
        )
    except Exception:
        return False


def system_activity_id():
    for activity in game_engine.list_activities(False):
        if is_system_activity(activity):
            return int(activity["id"])
    return None


def _sanitize_tasks(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        task_id = str(item.get("id") or uuid.uuid4())
        if task_id in seen:
            continue
        seen.add(task_id)
        try:
            created_ts = float(item.get("created_ts", 0) or 0)
        except Exception:
            created_ts = 0.0
        out.append({"id": task_id, "text": text[:180], "created_ts": created_ts})
        if len(out) >= MAX_TASKS:
            break
    return out


def tasks() -> list[dict]:
    raw = db.game_state_get(TASKS_KEY, "[]")
    try:
        parsed = json.loads(raw or "[]")
    except Exception:
        parsed = []
    return _sanitize_tasks(parsed)


def _save(items: list[dict]) -> list[dict]:
    clean = _sanitize_tasks(items)
    db.game_state_set(TASKS_KEY, json.dumps(clean, separators=(",", ":"), ensure_ascii=False))
    return clean


def ensure_activity() -> dict:
    found = None
    for activity in game_engine.list_activities(False):
        if is_system_activity(activity):
            found = activity
            break
    if found is None:
        aid = game_engine.create_activity(
            SYSTEM_ACTIVITY_NAME, DEFAULT_XP, "repeatable", True, SYSTEM_SORT_ORDER)
        return db.get_scoring_activity(aid)
    if not found.get("active"):
        return game_engine.update_activity(found["id"], active=True, sort_order=SYSTEM_SORT_ORDER)
    return found


def xp_value() -> int:
    activity = ensure_activity()
    return max(0, int(activity.get("xp_value", DEFAULT_XP) or 0))


def set_xp_value(value: int) -> dict:
    value = max(0, int(value))
    activity = ensure_activity()
    return game_engine.update_activity(
        activity["id"], xp_value=value, active=True, sort_order=SYSTEM_SORT_ORDER)


def add_task(text: str) -> list[dict]:
    text = str(text or "").strip()
    if not text:
        raise ValueError("Task cannot be blank.")
    current = tasks()
    if len(current) >= MAX_TASKS:
        raise ValueError(f"Quick Tasks can hold at most {MAX_TASKS} tasks at once.")
    current.append({"id": str(uuid.uuid4()), "text": text[:180], "created_ts": time.time()})
    return _save(current)


def remove_task(task_id: str) -> list[dict]:
    task_id = str(task_id or "")
    current = tasks()
    return _save([item for item in current if item["id"] != task_id])


def complete_task(task_id: str) -> tuple[dict, dict]:
    """Award one canonical Quick Task event, then remove that queue item."""
    task_id = str(task_id or "")
    current = tasks()
    task = next((item for item in current if item["id"] == task_id), None)
    if task is None:
        raise ValueError("That Quick Task is no longer in the queue.")
    activity = ensure_activity()
    event = game_engine.record_activity(activity["id"], source="micro_task")
    _save([item for item in current if item["id"] != task_id])
    return event, task


def clear_tasks() -> None:
    _save([])
