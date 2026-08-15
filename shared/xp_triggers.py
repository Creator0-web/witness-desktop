"""Dynamic XP triggers. Defined and edited entirely through the
Settings > XP Triggers menu panel -- never requires touching code to
add, remove, or change one. Each trigger watches an existing data
source (notes, revenue, focus score, arrival time) for a simple
condition; when it fires, XP goes through the real progression.py
system (progression.award_xp()), not a separate parallel score.

Storage: xp_triggers.json (definitions) + xp_triggers_fired.json
(which triggers already fired on which day, so nothing double-fires).
"""
import json
import os
from datetime import date, datetime

DEFS_PATH = "xp_triggers.json"
FIRED_PATH = "xp_triggers_fired.json"

TYPES = {
    "note_keyword": "Condition value = the word/phrase to look for, e.g. cold call. Only fires if you actually type this into Daily Notes that day -- it can't detect the activity itself, only what you write about it.",
    "revenue_received": "Condition value = minimum $ amount. Leave blank for any payment, or type a number like 100 for $100+.",
    "focus_score_above": "Condition value = minimum score (0-100), e.g. 80",
    "arrived_before": "Condition value = time in 24h HH:MM, e.g. 08:00",
    "category_minutes": "Pick a category below, condition value = minimum minutes, e.g. 20. Fully automatic -- based on what the hourly tracker already categorizes your screen time as, no typing required.",
}

CATEGORIES = ["Sales", "Hiring", "Design", "Comms", "Focus Work"]


def _read(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write(path, data_obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data_obj, f, indent=2)


def list_triggers() -> list:
    return _read(DEFS_PATH).get("triggers", [])


def save_trigger(trigger: dict):
    """trigger needs: id (existing to edit, or omit/None to create new),
    name, type, param, xp, active."""
    doc = _read(DEFS_PATH)
    triggers = doc.get("triggers", [])
    if trigger.get("id"):
        for i, t in enumerate(triggers):
            if t["id"] == trigger["id"]:
                triggers[i] = trigger
                break
        else:
            triggers.append(trigger)
    else:
        trigger["id"] = str(max([int(t["id"]) for t in triggers], default=0) + 1)
        triggers.append(trigger)
    doc["triggers"] = triggers
    _write(DEFS_PATH, doc)
    return trigger["id"]


def delete_trigger(trigger_id: str):
    doc = _read(DEFS_PATH)
    doc["triggers"] = [t for t in doc.get("triggers", [])
                        if t["id"] != trigger_id]
    _write(DEFS_PATH, doc)


def _already_fired(day: str, trigger_id: str) -> bool:
    fired = _read(FIRED_PATH)
    return trigger_id in fired.get(day, [])


def _mark_fired(day: str, trigger_id: str):
    fired = _read(FIRED_PATH)
    fired.setdefault(day, [])
    if trigger_id not in fired[day]:
        fired[day].append(trigger_id)
    _write(FIRED_PATH, fired)


def _check_condition(trigger: dict, day: str) -> bool:
    import db
    t = trigger["type"]
    param = trigger.get("param", "")

    if t == "note_keyword":
        notes = db.notes_for_day(day)
        kw = param.lower().strip()
        return any(kw in text.lower() for _, text in notes)

    if t == "revenue_received":
        param_clean = (param or "").strip()
        try:
            min_amt = float(param_clean) if param_clean else 0
        except ValueError:
            min_amt = 0
        rows = db.query("SELECT amount FROM revenue_events WHERE day=?", (day,))
        return any(amt >= min_amt for (amt,) in rows)

    if t == "focus_score_above":
        try:
            threshold = float(param)
        except ValueError:
            return False
        rows = db.query("SELECT score FROM daily_scores WHERE day=?", (day,))
        return bool(rows and rows[0][0] >= threshold)

    if t == "arrived_before":
        try:
            target = datetime.strptime(param.strip(), "%H:%M").time()
        except ValueError:
            return False
        rows = db.query(
            "SELECT ts FROM presence WHERE day=? AND event='arrived' "
            "ORDER BY ts", (day,))
        for (ts,) in rows:
            if datetime.fromtimestamp(ts).time() <= target:
                return True
        return False

    if t == "category_minutes":
        try:
            min_minutes = float(param)
        except ValueError:
            return False
        category = trigger.get("category", "")
        if not category:
            return False
        import day_breakdown
        doc = day_breakdown.load_day(day)
        if not doc:
            return False
        total_minutes = 0
        for hour in doc.get("hours", []):
            for app in hour.get("apps", []):
                if app.get("category") == category:
                    total_minutes += app.get("duration_min", 0)
        return total_minutes >= min_minutes

    return False


def check_all(day: str = None) -> list:
    """Evaluates every active trigger against `day` (default: today),
    awards XP for any that fire and haven't already fired that day.
    Returns the list of trigger names that fired just now. Safe to
    call repeatedly -- already-fired triggers are skipped."""
    day = day or date.today().isoformat()
    fired_now = []
    for trigger in list_triggers():
        if not trigger.get("active", True):
            continue
        tid = trigger["id"]
        if _already_fired(day, tid):
            continue
        try:
            if _check_condition(trigger, day):
                import progression
                progression.award_xp(reason=f"trigger:{trigger['name']}",
                                     custom_amount=int(trigger.get("xp", 10)))
                _mark_fired(day, tid)
                fired_now.append(trigger["name"])
        except Exception:
            pass
    return fired_now
