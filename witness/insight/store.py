"""Storage for 'colored documents' -- the small, readable output of the
distiller. Raw logs ('white' data) stay in witness.db, completely
unchanged by anything in this module. This is deliberately just JSON
files on disk, one per day and one per week, so they're easy to open,
diff, back up, or delete by hand if something looks wrong.
"""
import json
import os

DAILY_DIR = os.path.join("insight_data", "daily")
WEEKLY_DIR = os.path.join("insight_data", "weekly")
SUGGESTIONS_DIR = os.path.join("insight_data", "suggestions")


def _ensure():
    os.makedirs(DAILY_DIR, exist_ok=True)
    os.makedirs(WEEKLY_DIR, exist_ok=True)
    os.makedirs(SUGGESTIONS_DIR, exist_ok=True)


def save_daily(doc: dict) -> str:
    _ensure()
    path = os.path.join(DAILY_DIR, f"{doc['date']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def load_daily(day: str):
    path = os.path.join(DAILY_DIR, f"{day}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_daily() -> list:
    _ensure()
    return sorted(f[:-5] for f in os.listdir(DAILY_DIR) if f.endswith(".json"))


def save_weekly(doc: dict) -> str:
    _ensure()
    path = os.path.join(WEEKLY_DIR, f"{doc['week_start']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def load_weekly(week_start: str):
    path = os.path.join(WEEKLY_DIR, f"{week_start}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_weekly() -> list:
    _ensure()
    return sorted(f[:-5] for f in os.listdir(WEEKLY_DIR) if f.endswith(".json"))


def save_suggestions(doc: dict) -> str:
    _ensure()
    path = os.path.join(SUGGESTIONS_DIR, f"{doc['date']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def load_suggestions(day: str):
    path = os.path.join(SUGGESTIONS_DIR, f"{day}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
