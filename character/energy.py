"""Energy jar. A composite life-force score (0-100) that factors in:
- Days since last red-line event (builds exponentially)
- Manual Activity completion rate (daily contribution)
- Exercise / health habits
- Productivity streak
- Drains from red-line events, inactivity, broken patterns

Learns over time what activities correlate with high vs low energy
and suggests actions to keep the jar full.
"""
import math
from datetime import date, timedelta, datetime

import db
import data
import config


def calculate():
    """Calculate current energy level (0-100). Returns dict with
    total, breakdown, and level name."""

    # 1. CLEAN DAYS — biggest factor, builds exponentially
    days_clean = _days_since_redline()
    # logarithmic curve: day 1=5, day 7=25, day 14=40, day 30=55, day 60=65
    if days_clean >= 1:
        clean_score = min(65, 5 + 20 * math.log2(1 + days_clean))
    else:
        clean_score = 0

    # 2. TODAY'S PRODUCTIVITY — manual Activities done
    tasks = data.get_tasks()
    if tasks:
        done = sum(1 for t in tasks if t.get("done"))
        task_pct = done / len(tasks)
    else:
        task_pct = 0
    task_score = task_pct * 15  # max 15 points

    # 3. HEALTH — exercise, sleep (from metrics + morning check-in)
    health_score = 0
    try:
        m = data.get_metrics()
        p = m.get("personal", {})
        if p.get("workout"):
            health_score += 8
        if p.get("water_glasses", 0) >= 6:
            health_score += 3
        if p.get("meditation"):
            health_score += 4
    except Exception:
        pass

    # 4. STREAK MOMENTUM — consecutive good days
    scores = db.recent_scores(14)
    good_streak = 0
    for _, s in reversed(scores):
        if s >= 60:
            good_streak += 1
        else:
            break
    streak_bonus = min(10, good_streak * 2)  # max 10 points

    # 5. DRAIN — recent red-line events pull energy down hard
    recent_redlines = _redlines_last_n_days(3)
    drain = min(30, recent_redlines * 15)  # each recent event costs 15

    # composite
    total = clean_score + task_score + health_score + streak_bonus - drain
    total = max(0, min(100, int(total)))

    # level names
    if total >= 85:
        level = "PEAK"
        color = "#57cc99"
    elif total >= 70:
        level = "STRONG"
        color = "#6ba3be"
    elif total >= 50:
        level = "BUILDING"
        color = "#d4943a"
    elif total >= 30:
        level = "RECOVERING"
        color = "#c77a4b"
    else:
        level = "DEPLETED"
        color = "#c74b50"

    return {
        "total": total,
        "level": level,
        "color": color,
        "clean_days": days_clean,
        "clean_score": int(clean_score),
        "task_score": int(task_score),
        "health_score": int(health_score),
        "streak_bonus": int(streak_bonus),
        "drain": int(drain),
        "breakdown": (
            f"Clean: {days_clean}d (+{int(clean_score)}) | "
            f"Activities: +{int(task_score)} | "
            f"Health: +{int(health_score)} | "
            f"Streak: +{int(streak_bonus)} | "
            f"Drain: -{int(drain)}"
        ),
    }


def suggest_action():
    """Based on current energy state, suggest the highest-impact action."""
    e = calculate()

    if e["clean_days"] < 3:
        return ("Every hour clean rebuilds your baseline. "
                "Focus on getting through today — the energy compounds.")
    if e["health_score"] < 5:
        return ("Exercise is your biggest lever right now. "
                "A workout would add 8 points to the jar immediately.")
    if e["task_score"] < 5:
        return ("The jar fills when you move the mission forward. "
                "Check off one activity and watch it rise.")
    if e["streak_bonus"] < 4:
        return ("String together 3 good days and momentum kicks in. "
                "Today could be day 1 of the next streak.")
    if e["total"] >= 80:
        return ("You're in peak territory. This is rare — protect it. "
                "Don't waste this energy on anything that doesn't matter.")
    return "Steady. Keep the routine. The jar fills itself when you show up."


def _days_since_redline():
    """Days since last red-line event."""
    try:
        row = db._conn.execute(
            "SELECT day FROM redlines ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        if row:
            last = datetime.strptime(row[0], "%Y-%m-%d").date()
            return (date.today() - last).days
        return 0  # no history = fresh start, day 0
    except Exception:
        return 0


def _redlines_last_n_days(n):
    """Count red-line events in last n days."""
    since = (date.today() - timedelta(days=n)).isoformat()
    try:
        row = db._conn.execute(
            "SELECT COUNT(*) FROM redlines WHERE day >= ?",
            (since,)).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def set_clean_start(days_ago=0):
    """Manually log a red-line event N days ago to set the clean counter.
    Called when user reports a past relapse via chat."""
    from datetime import timedelta
    import time as _time
    event_date = (date.today() - timedelta(days=days_ago)).isoformat()
    event_ts = _time.time() - (days_ago * 86400)
    try:
        db._conn.execute(
            "INSERT INTO redlines VALUES (?,?,?)",
            (event_ts, event_date, "self-reported past event"))
        db._conn.commit()
    except Exception:
        pass
