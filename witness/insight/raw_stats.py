"""Pure-Python stats over a day or week of raw ('white document') logs.
No AI here, no hallucination possible -- this is the ground truth that
the distiller explains in plain language. All numbers below come
straight out of witness.db (shared/db.py), which core/ is already
writing to every few seconds during normal use.
"""
from datetime import datetime, timedelta
from collections import defaultdict

import config
import db


def day_stats(day: str) -> dict:
    """day: 'YYYY-MM-DD'. Returns numeric stats only -- no text."""
    activity = db.query("SELECT ts, flagged FROM activity WHERE day=?", (day,))
    checkins = db.query("SELECT ts FROM checkins WHERE day=?", (day,))
    redlines = db.query("SELECT ts FROM redlines WHERE day=?", (day,))
    sos = db.query("SELECT ts FROM sos WHERE day=?", (day,))
    score_row = db.query("SELECT score FROM daily_scores WHERE day=?", (day,))
    note_rows = db.notes_for_day(day)
    notes = [text for _, text in note_rows]
    input_rows = db.query("SELECT active FROM input_activity WHERE day=?", (day,))

    total = len(activity)
    flagged = sum(1 for _, fl in activity if fl)

    hour_totals = defaultdict(lambda: {"total": 0, "clean": 0})
    for ts, fl in activity:
        h = datetime.fromtimestamp(ts).hour
        hour_totals[h]["total"] += 1
        if not fl:
            hour_totals[h]["clean"] += 1

    hourly_focus = {h: round(v["clean"] / v["total"] * 100, 1)
                     for h, v in hour_totals.items() if v["total"] >= 5}
    peak_hour = max(hourly_focus, key=hourly_focus.get) if hourly_focus else None
    worst_hour = min(hourly_focus, key=hourly_focus.get) if hourly_focus else None

    poll_sec = getattr(config, "WINDOW_POLL_SEC", 5)

    input_samples = len(input_rows)
    input_active = sum(1 for (a,) in input_rows if a)
    engagement_pct = (round(input_active / input_samples * 100, 1)
                       if input_samples >= 5 else None)

    return {
        "day": day,
        "samples": total,
        "minutes_tracked": round(total * poll_sec / 60, 1),
        "minutes_flagged": round(flagged * poll_sec / 60, 1),
        "focus_score": score_row[0][0] if score_row else None,
        "checkins": len(checkins),
        "redline_events": len(redlines),
        "sos_events": len(sos),
        "notes": notes,
        "engagement_pct": engagement_pct,
        "hourly_focus": hourly_focus,
        "peak_hour": peak_hour,
        "worst_hour": worst_hour,
    }


def week_stats(week_start: str) -> dict:
    """week_start: 'YYYY-MM-DD' (any day; treated as the first of a
    7-day window). Returns the 7 day_stats plus simple aggregates."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    day_list = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    daily = [day_stats(d) for d in day_list]

    scored = [d for d in daily if d["focus_score"] is not None]
    scores = [d["focus_score"] for d in scored]

    return {
        "week_start": week_start,
        "week_end": day_list[-1],
        "days": daily,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "best_day": max(scored, key=lambda d: d["focus_score"])["day"]
        if scored else None,
        "worst_day": min(scored, key=lambda d: d["focus_score"])["day"]
        if scored else None,
        "total_sos": sum(d["sos_events"] for d in daily),
        "total_redlines": sum(d["redline_events"] for d in daily),
        "days_logged": sum(1 for d in daily if d["samples"] > 0),
    }
