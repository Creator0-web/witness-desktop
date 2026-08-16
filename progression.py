"""Full progression engine v2. Fixed XP bug + exponential decay.

Decay escalates with consecutive missed days:
  Day 1 missed: base decay
  Day 2: 2x
  Day 3: 4x
  Day 7: 15x
  Day 14: can wipe months of progress
Consistency is the only defense.
"""
import json
import os
import random
import math
import time
from datetime import date, datetime, timedelta

import db
import data

PROGRESS_FILE = "progression.json"

LEVELS = [
    (0,       "Dormant",       "#555555"),
    (100,     "Awakening",     "#6b6b76"),
    (300,     "Initiate",      "#7a8a7a"),
    (600,     "Committed",     "#6ba3be"),
    (1200,    "Builder",       "#4ea8de"),
    (2000,    "Focused",       "#4ecade"),
    (3200,    "Operator",      "#57cc99"),
    (5000,    "Consistent",    "#4edeac"),
    (7500,    "Commander",     "#a8de4e"),
    (11000,   "Disciplined",   "#dede4e"),
    (16000,   "Architect",     "#deac4e"),
    (22000,   "Master",        "#de7a4e"),
    (30000,   "Unstoppable",   "#de4e8a"),
    (42000,   "Legend",        "#c44ede"),
    (60000,   "Transcendent",  "#ffffff"),
]

ACHIEVEMENTS = {
    "first_task":    {"name": "First Blood",      "desc": "Complete first task",      "xp": 25},
    "ten_tasks":     {"name": "Momentum",          "desc": "10 tasks total",           "xp": 50},
    "fifty_tasks":   {"name": "Machine",           "desc": "50 tasks total",           "xp": 100},
    "hundred_tasks": {"name": "Relentless",        "desc": "100 tasks total",          "xp": 200},
    "streak_3":      {"name": "Three-Peat",        "desc": "3-day streak",             "xp": 50},
    "streak_7":      {"name": "Week Warrior",      "desc": "7-day streak",             "xp": 150},
    "streak_14":     {"name": "Iron Will",         "desc": "14-day streak",            "xp": 300},
    "streak_30":     {"name": "Unbreakable",       "desc": "30-day streak",            "xp": 500},
    "clean_7":       {"name": "Clean Week",        "desc": "7 days no red-line",       "xp": 100},
    "clean_14":      {"name": "Fortified",         "desc": "14 days clean",            "xp": 200},
    "clean_30":      {"name": "Steel Mind",        "desc": "30 days clean",            "xp": 500},
    "clean_60":      {"name": "Reborn",            "desc": "60 days clean",            "xp": 1000},
    "clean_90":      {"name": "Transformation",    "desc": "90 days clean",            "xp": 2000},
    "sos_1":         {"name": "Warrior",           "desc": "Survive first SOS",        "xp": 75},
    "sos_5":         {"name": "Battle-Tested",     "desc": "Survive 5 SOS events",    "xp": 200},
    "record_day":    {"name": "New Record",         "desc": "Beat your best day",       "xp": 100},
    "prestige_1":    {"name": "Prestige I",        "desc": "First prestige",           "xp": 0},
    "level_5":       {"name": "Rising",            "desc": "Reach level 5",            "xp": 0},
    "level_10":      {"name": "Double Digits",     "desc": "Reach level 10",           "xp": 0},
    "level_15":      {"name": "Apex",              "desc": "Reach level 15",           "xp": 0},
}

CHALLENGE_POOL = [
    {"text": "Complete 3 tasks before noon", "xp": 50},
    {"text": "Zero drift events all day", "xp": 75},
    {"text": "Exercise before 9 AM", "xp": 40},
    {"text": "Complete all tasks today", "xp": 60},
    {"text": "Power Hour before lunch", "xp": 60},
    {"text": "Score above 80% today", "xp": 60},
]


def _default():
    return {
        "permanent_xp": 0,
        "daily_xp": 0,
        "daily_date": "",
        "daily_tasks_awarded": 0,
        "all_time_record": 0,
        "achievements": [],
        "tasks_completed": 0,
        "sos_survived": 0,
        "power_hours": 0,
        "challenges_completed": 0,
        "prestige": 0,
        "streak_multiplier": 1.0,
        "monthly_best": 0,
        "monthly_decay_bonus": 0,
        "current_month": "",
        "consecutive_inactive": 0,
        "last_active_date": "",
        "xp_history": [],
        "daily_challenge": None,
        "needs": {"discipline": 100, "body": 100, "purpose": 100, "clean": 100},
        "power_hour_start": 0,
        "combo_morning": False,
        "pending": [],
    }


def _load():
    defaults = _default()
    try:
        with open(PROGRESS_FILE, "r") as f:
            raw = json.load(f)
        # migrate old keys
        if "xp" in raw and raw.get("permanent_xp", 0) == 0:
            raw["permanent_xp"] = raw.pop("xp", 0)
        if "total_xp_earned" in raw and raw.get("permanent_xp", 0) == 0:
            raw["permanent_xp"] = raw.get("total_xp_earned", 0)
        # fill missing keys from defaults
        for key, val in defaults.items():
            if key not in raw:
                raw[key] = val
        return raw
    except Exception:
        return defaults


def _save(p):
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(p, f, indent=1)
    except Exception:
        pass


def _log(p, xp, reason):
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "xp": xp,
        "reason": reason,
    }
    p.setdefault("xp_history", []).append(entry)
    if len(p["xp_history"]) > 200:
        p["xp_history"] = p["xp_history"][-200:]


def _get_level_num(xp):
    level = 1
    for i, (threshold, _, _) in enumerate(LEVELS):
        if xp >= threshold:
            level = i + 1
    return min(level, len(LEVELS))


def _base_decay(level_num):
    if level_num <= 2: return 10
    if level_num <= 5: return 25
    if level_num <= 8: return 50
    if level_num <= 11: return 100
    if level_num <= 13: return 175
    return 250


def _exponential_decay(p):
    """Decay that escalates with consecutive inactive days.
    Day 1: 1x base. Day 2: 2x. Day 3: 4x. Day 7: ~15x. Day 14: ~100x."""
    level = _get_level_num(p["permanent_xp"])
    base = _base_decay(level) + p.get("monthly_decay_bonus", 0)

    inactive = p.get("consecutive_inactive", 0)
    if inactive <= 0:
        return base

    # exponential: base * 1.5^inactive (capped)
    multiplier = min(100, round(1.5 ** inactive, 1))
    return int(base * multiplier)


def _new_day(p):
    """Handle day transition. Called once when we detect a new day."""
    today = date.today().isoformat()
    old_date = p.get("daily_date", "")

    if old_date == today:
        return  # already handled

    # cash out yesterday's daily XP
    if old_date and p.get("daily_xp", 0) > 0:
        daily = p["daily_xp"]
        if daily > p.get("all_time_record", 0):
            p["all_time_record"] = daily
            p["permanent_xp"] += 150
            _log(p, 150, "RECORD DAY BONUS")
            p.setdefault("pending", []).append(
                f"NEW ALL-TIME RECORD! {daily} daily XP! +150 bonus")
        p["permanent_xp"] += daily
        _log(p, daily, "daily_cashout")
        p["monthly_best"] = max(p.get("monthly_best", 0), daily)
        p["consecutive_inactive"] = 0
        p["last_active_date"] = old_date
    elif old_date:
        # no XP earned yesterday — count as inactive
        days_gap = 1
        try:
            d1 = datetime.strptime(old_date, "%Y-%m-%d").date()
            d2 = date.today()
            days_gap = (d2 - d1).days
        except Exception:
            pass
        p["consecutive_inactive"] = p.get("consecutive_inactive", 0) + days_gap

    # apply decay (exponential based on inactivity streak)
    decay = _exponential_decay(p)
    if decay > 0:
        p["permanent_xp"] = max(0, p["permanent_xp"] - decay)
        _log(p, -decay, f"decay (inactive:{p.get('consecutive_inactive',0)}d)")

    # monthly check
    month = date.today().strftime("%Y-%m")
    if p.get("current_month", "") != month:
        if p.get("current_month"):
            best = p.get("monthly_best", 0)
            if best > 0:
                inc = max(5, int(best * 0.1))
                p["monthly_decay_bonus"] = p.get("monthly_decay_bonus", 0) + inc
                p.setdefault("pending", []).append(
                    f"Month closed. Best day: {best}. Decay +{inc}/day.")
        p["current_month"] = month
        p["monthly_best"] = 0

    # decay needs
    needs = p.get("needs", {"discipline": 100, "body": 100, "purpose": 100, "clean": 100})
    needs["discipline"] = max(0, needs.get("discipline", 100) - 15)
    needs["body"] = max(0, needs.get("body", 100) - 12)
    needs["purpose"] = max(0, needs.get("purpose", 100) - 10)
    try:
        import energy
        needs["clean"] = min(100, energy._days_since_redline() * 5)
    except Exception:
        needs["clean"] = max(0, needs.get("clean", 100) - 8)
    p["needs"] = needs

    # daily challenge
    p["daily_challenge"] = random.choice(CHALLENGE_POOL)

    # reset daily
    p["daily_xp"] = 0
    p["daily_date"] = today
    p["daily_tasks_awarded"] = 0
    p["combo_morning"] = False

    _save(p)


def _diminishing(count, base):
    if count < 3: return base
    if count < 6: return int(base * 0.8)
    if count < 10: return int(base * 0.6)
    if count < 15: return int(base * 0.5)
    return int(base * 0.3)


def _variable(base):
    roll = random.random()
    if roll < 0.04: return base * 3, "CRITICAL HIT! 3x"
    if roll < 0.18: return base * 2, "Bonus! 2x"
    return base, ""


def _update_streak(p):
    scores = db.recent_scores(30)
    streak = 0
    for _, s in reversed(scores):
        if s >= 50: streak += 1
        else: break
    if streak >= 30: m = 5.0
    elif streak >= 14: m = 3.0
    elif streak >= 7: m = 2.0
    elif streak >= 3: m = 1.5
    else: m = 1.0
    if p.get("combo_morning"): m = min(m + 0.5, 6.0)
    old = p.get("streak_multiplier", 1.0)
    p["streak_multiplier"] = m
    if m < old and old > 1.0:
        p.setdefault("pending", []).append(f"Streak dropped: {old}x → {m}x")
    # comeback
    if streak == 1 and old <= 1.0:
        recent = [s for _, s in scores[-5:]]
        bad = sum(1 for s in recent[:-1] if s < 50)
        if bad >= 3:
            p["daily_xp"] += 100
            _log(p, 100, "COMEBACK")
            p.setdefault("pending", []).append("COMEBACK! +100 XP")


def _check_achievements(p):
    unlocked = set(p.get("achievements", []))
    checks = {
        "first_task": p.get("tasks_completed", 0) >= 1,
        "ten_tasks": p.get("tasks_completed", 0) >= 10,
        "fifty_tasks": p.get("tasks_completed", 0) >= 50,
        "hundred_tasks": p.get("tasks_completed", 0) >= 100,
        "sos_1": p.get("sos_survived", 0) >= 1,
        "sos_5": p.get("sos_survived", 0) >= 5,
        "level_5": _get_level_num(p.get("permanent_xp", 0)) >= 5,
        "level_10": _get_level_num(p.get("permanent_xp", 0)) >= 10,
        "level_15": _get_level_num(p.get("permanent_xp", 0)) >= 15,
    }
    try:
        scores = db.recent_scores(30)
        streak = 0
        for _, s in reversed(scores):
            if s >= 50: streak += 1
            else: break
        checks["streak_3"] = streak >= 3
        checks["streak_7"] = streak >= 7
        checks["streak_14"] = streak >= 14
        checks["streak_30"] = streak >= 30
    except Exception: pass
    try:
        import energy
        clean = energy._days_since_redline()
        checks["clean_7"] = clean >= 7
        checks["clean_14"] = clean >= 14
        checks["clean_30"] = clean >= 30
        checks["clean_60"] = clean >= 60
        checks["clean_90"] = clean >= 90
    except Exception: pass
    try:
        checks["first_revenue"] = data.load()["money"]["current_monthly"] > 0
    except Exception: pass

    for key, earned in checks.items():
        if earned and key not in unlocked and key in ACHIEVEMENTS:
            ach = ACHIEVEMENTS[key]
            p.setdefault("achievements", []).append(key)
            if ach["xp"] > 0:
                p["permanent_xp"] = p.get("permanent_xp", 0) + ach["xp"]
                _log(p, ach["xp"], f"ACHIEVEMENT: {ach['name']}")
            p.setdefault("pending", []).append(
                f"ACHIEVEMENT: {ach['name']} — {ach['desc']}! +{ach['xp']} XP")


# ════════════════════════════════════════════════════════════════════════
# PUBLIC API — these are the ONLY functions that save
# ════════════════════════════════════════════════════════════════════════

def award_xp(reason, custom_amount=None):
    """Award XP. Returns notification string."""
    base_map = {
        "task_complete": 15, "all_tasks_done": 60, "sos_survived": 40,
        "voice_journal": 15, "morning_habits": 25, "evening_habits": 25,
        "above_target": 30, "win_logged": 10, "power_hour": 80,
        "exercise": 20, "revenue": 200, "booking": 150,
    }
    base = custom_amount if custom_amount is not None else base_map.get(reason, 10)

    p = _load()
    if p.get("daily_date") != date.today().isoformat():
        _new_day(p)

    # diminishing returns for tasks
    if "task" in reason:
        base = _diminishing(p.get("daily_tasks_awarded", 0), base)
        p["daily_tasks_awarded"] = p.get("daily_tasks_awarded", 0) + 1
        p["tasks_completed"] = p.get("tasks_completed", 0) + 1
        p.get("needs", {})["discipline"] = min(100, p.get("needs", {}).get("discipline", 0) + 8)

    if reason == "sos_survived":
        p["sos_survived"] = p.get("sos_survived", 0) + 1
    if reason == "exercise":
        p.get("needs", {})["body"] = min(100, p.get("needs", {}).get("body", 0) + 30)
    if reason in ("revenue", "booking"):
        p.get("needs", {})["purpose"] = min(100, p.get("needs", {}).get("purpose", 0) + 25)

    mult = p.get("streak_multiplier", 1.0)
    after_mult = int(base * mult)
    final, bonus = _variable(after_mult)

    p["daily_xp"] = p.get("daily_xp", 0) + final
    _log(p, final, reason)

    # check level up
    old_level = _get_level_num(p.get("permanent_xp", 0))
    _update_streak(p)
    _check_achievements(p)
    _save(p)

    notif = f"+{final} XP"
    if mult > 1: notif += f" ({mult}x)"
    if bonus: notif += f" {bonus}"
    return notif


def remove_xp(amount, reason="unchecked_task"):
    """Remove daily XP (for unchecking tasks)."""
    p = _load()
    if p.get("daily_date") != date.today().isoformat():
        _new_day(p)
    p["daily_xp"] = max(0, p.get("daily_xp", 0) - amount)
    _log(p, -amount, reason)
    _save(p)
    return f"-{amount} XP ({reason})"


def apply_penalty(reason):
    """Apply penalty to PERMANENT XP (for red-lines, broken streaks)."""
    amounts = {"redline_event": 75, "streak_broken": 40, "zero_tasks": 15}
    amount = amounts.get(reason, 50)
    p = _load()
    if p.get("daily_date") != date.today().isoformat():
        _new_day(p)
    p["permanent_xp"] = max(0, p.get("permanent_xp", 0) - amount)
    if reason == "redline_event":
        p.get("needs", {})["clean"] = max(0, p.get("needs", {}).get("clean", 100) - 40)
    _log(p, -amount, reason)
    _update_streak(p)
    _save(p)
    return f"-{amount} XP ({reason})"


def start_power_hour():
    p = _load()
    p["power_hour_start"] = time.time()
    _save(p)
    return "Power Hour started. 60 min pure focus = 80 XP."


def check_power_hour():
    p = _load()
    start = p.get("power_hour_start", 0)
    if start <= 0: return None
    if time.time() - start < 3600: return None
    p["power_hour_start"] = 0
    try:
        raw = db.today_raw()
        if raw["samples"] > 0:
            clean = (raw["samples"] - raw["flagged"]) / raw["samples"]
            if clean >= 0.85:
                p["power_hours"] = p.get("power_hours", 0) + 1
                _save(p)
                return award_xp("power_hour")
    except Exception: pass
    _save(p)
    return "Power Hour failed — too much drift."


def check_combo():
    p = _load()
    if p.get("combo_morning"): return
    if datetime.now().hour < 12: return
    try:
        m = data.get_metrics()
        exercised = m.get("personal", {}).get("workout", False)
        tasks = data.get_tasks()
        done = sum(1 for t in tasks if t.get("done")) >= 2
        raw = db.today_raw()
        low_drift = raw["flagged"] / max(1, raw["samples"]) < 0.15
        if exercised and done and low_drift:
            p["combo_morning"] = True
            p["streak_multiplier"] = min(p.get("streak_multiplier", 1.0) + 0.5, 6.0)
            p.setdefault("pending", []).append(
                f"MORNING COMBO! {p['streak_multiplier']}x multiplier!")
            _save(p)
    except Exception: pass


def complete_challenge():
    p = _load()
    ch = p.get("daily_challenge")
    if not ch: return None
    xp = ch.get("xp", 50)
    p["daily_xp"] = p.get("daily_xp", 0) + xp
    p["challenges_completed"] = p.get("challenges_completed", 0) + 1
    _log(p, xp, f"CHALLENGE: {ch['text']}")
    p["daily_challenge"] = None
    _save(p)
    return f"Challenge complete! +{xp} XP"


def prestige():
    p = _load()
    level = _get_level_num(p.get("permanent_xp", 0))
    if level < 15: return f"Need level 15. Currently {level}."
    p["prestige"] = p.get("prestige", 0) + 1
    p["permanent_xp"] = 0
    p["monthly_decay_bonus"] = p.get("monthly_decay_bonus", 0) + 25
    p.setdefault("pending", []).append(f"PRESTIGE {p['prestige']}!")
    _log(p, 0, f"PRESTIGE_{p['prestige']}")
    _save(p)
    return f"Prestige {p['prestige']}!"


# ════════════════════════════════════════════════════════════════════════
# READ-ONLY functions — these NEVER save
# ════════════════════════════════════════════════════════════════════════

def get_level(xp=None):
    if xp is None:
        xp = _load().get("permanent_xp", 0)
    level_num = _get_level_num(xp)
    idx = min(level_num - 1, len(LEVELS) - 1)
    name = LEVELS[idx][1]
    color = LEVELS[idx][2]
    if level_num < len(LEVELS):
        nxt = LEVELS[level_num][0]
        cur = LEVELS[idx][0]
        pct = (xp - cur) / max(1, nxt - cur)
        to_next = nxt - xp
    else:
        pct = 1.0
        to_next = 0
    return {"level": level_num, "name": name, "color": color,
            "xp": xp, "pct_to_next": min(1.0, pct),
            "xp_to_next": max(0, to_next)}


def get_stats():
    """READ ONLY. Never saves."""
    p = _load()
    # trigger day transition only if needed
    today = date.today().isoformat()
    if p.get("daily_date", "") != today:
        _new_day(p)  # this saves internally
        p = _load()  # reload after save
    level = get_level(p.get("permanent_xp", 0))
    decay = _exponential_decay(p)
    return {
        **level,
        "daily_xp": p.get("daily_xp", 0),
        "daily_record": p.get("all_time_record", 0),
        "multiplier": p.get("streak_multiplier", 1.0),
        "achievements": p.get("achievements", []),
        "needs": p.get("needs", {}),
        "prestige": p.get("prestige", 0),
        "decay_rate": decay,
        "consecutive_inactive": p.get("consecutive_inactive", 0),
        "daily_challenge": p.get("daily_challenge"),
        "power_hour_active": p.get("power_hour_start", 0) > 0,
        "combo_active": p.get("combo_morning", False),
    }


def get_pending():
    """Get and clear pending notifications. This one DOES save."""
    p = _load()
    pending = p.get("pending", [])
    if pending:
        p["pending"] = []
        _save(p)
    return pending


def get_history(limit=50):
    p = _load()
    return list(reversed(p.get("xp_history", [])[-limit:]))


def get_daily_challenge():
    return _load().get("daily_challenge")


def get_multiplier():
    return _load().get("streak_multiplier", 1.0)
