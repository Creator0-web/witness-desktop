"""Persistent user data (goals, wins, money, schedule) in one JSON file."""
import json
import os
import threading
from datetime import date

import config

_lock = threading.Lock()

DEFAULT = {
    "lifestyle": "Location-independent income. Free to live anywhere. "
                 "Building something of my own.",
    "mission": "Get the remote cleaning business to consistent monthly profit "
               "in the next 90 days.",
    "goals": [
        # {"title": ..., "why": ..., "target_date": ..., "stakes": ...}
    ],
    "wins": [
        # {"date": ..., "text": ...}
    ],
    "money": {
        "target_monthly": 8000,
        "current_monthly": 0,
        "savings": 0,
        "debt": 0,
        "subscriptions": 0,
        "deadline_note": "",
    },
    "schedule": [
        {"start": "08:00", "end": "09:00", "label": "Morning routine + plan"},
        {"start": "09:00", "end": "11:00", "label": "Deep work: business"},
        {"start": "11:00", "end": "12:00", "label": "Outreach / calls"},
        {"start": "13:00", "end": "15:00", "label": "Deep work: business"},
        {"start": "15:00", "end": "16:00", "label": "Admin / learning"},
    ],
    "last_morning_checkin": "",   # ISO date of last morning check-in
    "tasks": {"date": "", "items": []},
}


def load() -> dict:
    with _lock:
        if not os.path.exists(config.DATA_PATH):
            return json.loads(json.dumps(DEFAULT))
        try:
            with open(config.DATA_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return json.loads(json.dumps(DEFAULT))
    merged = json.loads(json.dumps(DEFAULT))
    merged.update(d)
    return merged


def save(d: dict):
    with _lock:
        with open(config.DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)


def add_win(text: str):
    d = load()
    d["wins"].append({"date": date.today().isoformat(), "text": text})
    save(d)


def add_goal(title, why="", target_date="", stakes=""):
    d = load()
    d["goals"].append({"title": title, "why": why,
                       "target_date": target_date, "stakes": stakes})
    save(d)


def goal_context(d=None) -> str:
    """Compact text block describing the user's goals/stakes for AI prompts."""
    d = d or load()
    m = d["money"]
    gap = m["target_monthly"] - m["current_monthly"]
    lines = [
        f"Dream lifestyle: {d['lifestyle']}",
        f"Current mission: {d['mission']}",
        f"Money: ${m['current_monthly']}/mo now, target ${m['target_monthly']}/mo "
        f"(gap ${gap}). Savings ${m['savings']}, debt ${m['debt']}. "
        f"{m['deadline_note']}",
    ]
    for g in d["goals"][:10]:
        lines.append(
            f"Goal: {g['title']} | why: {g['why']} | by: {g['target_date']} "
            f"| stakes: {g['stakes']}"
        )
    recent_wins = d["wins"][-5:]
    if recent_wins:
        lines.append("Recent wins: " +
                     "; ".join(w["text"] for w in recent_wins))
    return "\n".join(lines)


def get_tasks():
    """Return today's manual Activities checklist.

    Compatibility note: the rest of the app historically calls these
    "tasks", so the storage key/API stay named tasks for now. The list itself
    is now persistent: activities carry forward to the next day and only
    their checked state resets. That makes this a reusable activity roster
    instead of a plan that has to be rebuilt every morning.
    """
    d = load()
    today = date.today().isoformat()
    task_doc = d.get("tasks") or {"date": "", "items": []}
    if task_doc.get("date") != today:
        carried = []
        for t in task_doc.get("items", []):
            try:
                xp = max(0, int(t.get("custom_xp", 10) or 0))
            except (TypeError, ValueError):
                xp = 10
            carried.append({
                "text": str(t.get("text", "")).strip(),
                "by": "23:59",  # retained only for legacy callers
                "done": False,
                "custom_xp": xp,
                "awarded_xp": 0,
            })
        d["tasks"] = {"date": today, "items": carried}
        save(d)
    return d["tasks"]["items"]


def set_tasks(items):
    """Save the persistent Activities roster plus today's checked state.

    `custom_xp` is intentionally preserved. Older code accidentally stripped
    it here, which made a configured XP value disappear as soon as the list
    was saved/toggled.
    """
    cleaned = []
    for t in items:
        text = str(t.get("text", "")).strip()
        if not text:
            continue
        try:
            xp = max(0, int(t.get("custom_xp", 10) or 0))
        except (TypeError, ValueError):
            xp = 10
        cleaned.append({
            "text": text,
            "by": "23:59",  # legacy compatibility; Activities are untimed
            "done": bool(t.get("done")),
            "custom_xp": xp,
            "awarded_xp": max(0, int(t.get("awarded_xp", 0) or 0))
                           if str(t.get("awarded_xp", 0) or 0).lstrip("-").isdigit()
                           else 0,
        })
    d = load()
    d["tasks"] = {"date": date.today().isoformat(), "items": cleaned}
    save(d)


def toggle_task(idx):
    items = get_tasks()
    if 0 <= idx < len(items):
        items[idx]["done"] = not items[idx]["done"]
        set_tasks(items)
    return items


# ── Business & Personal Metrics ─────────────────────────────────────────
def get_metrics():
    d = load()
    if "metrics" not in d:
        d["metrics"] = {
            "business": {
                "calls_made": 0,
                "leads_contacted": 0,
                "quotes_sent": 0,
                "bookings": 0,
                "revenue_today": 0,
            },
            "personal": {
                "water_glasses": 0,
                "workout": False,
                "reading_min": 0,
                "meditation": False,
            },
            "date": date.today().isoformat(),
        }
        save(d)
    # reset if new day
    if d["metrics"].get("date") != date.today().isoformat():
        for cat in ("business", "personal"):
            for k in d["metrics"][cat]:
                d["metrics"][cat][k] = 0 if isinstance(d["metrics"][cat][k], (int, float)) else False
        d["metrics"]["date"] = date.today().isoformat()
        save(d)
    return d["metrics"]


def update_metric(category, key, value):
    d = load()
    get_metrics()  # ensure initialized
    d["metrics"][category][key] = value
    save(d)


def metrics_summary() -> str:
    m = get_metrics()
    b = m["business"]
    p = m["personal"]
    lines = [
        f"Business: {b['calls_made']} calls, {b['leads_contacted']} leads, "
        f"{b['quotes_sent']} quotes, {b['bookings']} bookings, "
        f"${b['revenue_today']} revenue",
        f"Personal: {b.get('water_glasses', p.get('water_glasses', 0))} water, "
        f"{'✓' if p.get('workout') else '○'} workout, "
        f"{p.get('reading_min', 0)} min reading, "
        f"{'✓' if p.get('meditation') else '○'} meditation",
    ]
    return " | ".join(lines)
