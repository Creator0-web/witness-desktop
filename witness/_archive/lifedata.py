"""Life data. Captures structured daily data points that build a
comprehensive picture of the user over weeks/months.

Data is captured conversationally by the brain and stored here.
Over time this becomes the richest dataset for personalized advice.
"""
import json
import os
from datetime import date, timedelta, datetime
from collections import defaultdict

LIFE_FILE = "life_data.json"


def _load():
    try:
        with open(LIFE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"days": {}}


def _save(d):
    try:
        with open(LIFE_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    except Exception:
        pass


def log_day_field(field, value):
    """Log a field for today. Fields: sleep_hours, sleep_quality (1-10),
    energy_morning, energy_afternoon, energy_evening (1-10),
    exercise (str description or False), meals (str),
    social (str - who they talked to), mood (1-10),
    key_learning (str), key_decision (str), gratitude (str),
    obstacles (str), tomorrow_intention (str)."""
    d = _load()
    today = date.today().isoformat()
    if today not in d["days"]:
        d["days"][today] = {}
    d["days"][today][field] = value
    d["days"][today]["_updated"] = datetime.now().isoformat()
    _save(d)


def get_today():
    d = _load()
    return d["days"].get(date.today().isoformat(), {})


def get_recent(days=14):
    """Get last N days of life data."""
    d = _load()
    result = {}
    for i in range(days):
        day = (date.today() - timedelta(days=i)).isoformat()
        if day in d["days"]:
            result[day] = d["days"][day]
    return result


def analyze_patterns():
    """Deep pattern analysis across all captured life data."""
    d = _load()
    if len(d["days"]) < 7:
        return {"status": "need_data",
                "message": f"Only {len(d['days'])} days captured. "
                           "Need 7+ for pattern analysis."}

    import db
    scores = dict(db.recent_scores(60))
    insights = []

    # sleep vs performance
    sleep_scores = []
    for day, info in d["days"].items():
        if "sleep_hours" in info and day in scores:
            sleep_scores.append((info["sleep_hours"], scores[day]))
    if len(sleep_scores) >= 5:
        good_sleep = [s for h, s in sleep_scores if h >= 7]
        bad_sleep = [s for h, s in sleep_scores if h < 7]
        if good_sleep and bad_sleep:
            avg_good = int(sum(good_sleep) / len(good_sleep))
            avg_bad = int(sum(bad_sleep) / len(bad_sleep))
            insights.append({
                "type": "sleep",
                "finding": f"7+ hours sleep: {avg_good}% avg score. "
                           f"Under 7: {avg_bad}%. "
                           f"Impact: {avg_good - avg_bad} points.",
                "action": "Protect your sleep — it's your biggest lever."
                          if avg_good - avg_bad > 10 else ""
            })

    # exercise vs performance
    ex_scores = {"yes": [], "no": []}
    for day, info in d["days"].items():
        if day in scores:
            exercised = bool(info.get("exercise"))
            ex_scores["yes" if exercised else "no"].append(scores[day])
    if len(ex_scores["yes"]) >= 3 and len(ex_scores["no"]) >= 3:
        avg_ex = int(sum(ex_scores["yes"]) / len(ex_scores["yes"]))
        avg_no = int(sum(ex_scores["no"]) / len(ex_scores["no"]))
        insights.append({
            "type": "exercise",
            "finding": f"Exercise days: {avg_ex}% avg. No exercise: {avg_no}%. "
                       f"Impact: {avg_ex - avg_no} points.",
            "action": "Schedule exercise before your first work block."
                      if avg_ex > avg_no else ""
        })

    # mood vs performance
    mood_scores = []
    for day, info in d["days"].items():
        if "mood" in info and day in scores:
            mood_scores.append((info["mood"], scores[day]))
    if len(mood_scores) >= 5:
        high_mood = [s for m, s in mood_scores if m >= 7]
        low_mood = [s for m, s in mood_scores if m < 5]
        if high_mood and low_mood:
            insights.append({
                "type": "mood",
                "finding": f"High mood days: {int(sum(high_mood)/len(high_mood))}% avg. "
                           f"Low mood: {int(sum(low_mood)/len(low_mood))}%.",
                "action": ""
            })

    # energy patterns
    energy_data = {"morning": [], "afternoon": [], "evening": []}
    for day, info in d["days"].items():
        for period in energy_data:
            key = f"energy_{period}"
            if key in info:
                energy_data[period].append(info[key])
    filled = {k: v for k, v in energy_data.items() if len(v) >= 5}
    if len(filled) >= 2:
        avgs = {k: round(sum(v)/len(v), 1) for k, v in filled.items()}
        peak = max(avgs, key=avgs.get)
        insights.append({
            "type": "energy_curve",
            "finding": f"Energy peaks in the {peak} "
                       f"(avg {avgs[peak]}/10). "
                       + ", ".join(f"{k}: {v}" for k, v in avgs.items()),
            "action": f"Schedule your hardest work in the {peak}."
        })

    # social connection vs performance
    social_scores = {"connected": [], "isolated": []}
    for day, info in d["days"].items():
        if day in scores:
            has_social = bool(info.get("social"))
            key = "connected" if has_social else "isolated"
            social_scores[key].append(scores[day])
    if len(social_scores["connected"]) >= 3 and len(social_scores["isolated"]) >= 3:
        avg_c = int(sum(social_scores["connected"]) / len(social_scores["connected"]))
        avg_i = int(sum(social_scores["isolated"]) / len(social_scores["isolated"]))
        if abs(avg_c - avg_i) >= 8:
            insights.append({
                "type": "social",
                "finding": f"Days with social connection: {avg_c}%. "
                           f"Isolated days: {avg_i}%.",
                "action": "Build in at least one real conversation per day."
            })

    return {"status": "ok", "insights": insights,
            "days_captured": len(d["days"])}


def build_context():
    """Build context string for the brain with recent life data."""
    recent = get_recent(7)
    if not recent:
        return ""

    lines = ["LIFE DATA (last 7 days):"]
    for day in sorted(recent.keys(), reverse=True):
        info = recent[day]
        parts = []
        if "sleep_hours" in info:
            parts.append(f"sleep: {info['sleep_hours']}h")
        if "mood" in info:
            parts.append(f"mood: {info['mood']}/10")
        if "exercise" in info:
            parts.append(f"exercise: {info['exercise']}")
        if "energy_morning" in info:
            parts.append(f"energy AM: {info['energy_morning']}/10")
        if "social" in info:
            parts.append(f"social: {info['social']}")
        if "key_learning" in info:
            parts.append(f"learned: {info['key_learning']}")
        if "obstacles" in info:
            parts.append(f"obstacle: {info['obstacles']}")
        if parts:
            lines.append(f"  [{day}] {' | '.join(parts)}")

    return "\n".join(lines) if len(lines) > 1 else ""
