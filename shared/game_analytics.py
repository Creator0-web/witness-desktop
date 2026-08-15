"""Pure-Python analysis bridge between WITNESS telemetry and game outcomes.

The scoring engine answers the user's earlier hard question -- "how does the
computer know what good means?" -- without asking AI to invent values:
``shared/game_engine.py`` defines success from the person's own manual XP
rules. This module then asks a narrower, defensible question:

    Which automatically-observed behaviors are associated with higher
    user-defined score/output days?

It never awards XP and never changes the user's score. It only builds daily
feature rows and rank correlations that a future AI/UI can explain.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import config
import db
import day_breakdown
import game_engine

MIN_CORRELATION_DAYS = 7


def _as_date(value=None):
    if value is None:
        return date.today()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _clock_decimal(ts):
    if ts is None:
        return None
    dt = datetime.fromtimestamp(float(ts))
    return dt.hour + dt.minute / 60 + dt.second / 3600


def day_features(day) -> dict:
    """One honest daily feature row from raw telemetry + canonical XP."""
    d = _as_date(day).isoformat()
    acts = db.query(
        "SELECT ts,process,title,flagged FROM activity WHERE day=? ORDER BY ts",
        (d,))
    inputs = db.query("SELECT active FROM input_activity WHERE day=?", (d,))
    arrivals = db.query(
        "SELECT ts FROM presence WHERE day=? AND event='arrived' ORDER BY ts LIMIT 1",
        (d,))
    scoring = db.query(
        "SELECT ts FROM xp_events WHERE day=? AND event_type='activity' "
        "AND score_xp>0 ORDER BY ts LIMIT 1", (d,))
    revenue = db.query(
        "SELECT COALESCE(SUM(amount),0) FROM revenue_events WHERE day=?", (d,))

    samples = len(acts)
    poll_sec = getattr(config, "WINDOW_POLL_SEC", 5)
    tracked_min = samples * poll_sec / 60.0
    flagged = sum(1 for _, _, _, fl in acts if fl)
    flagged_pct = (flagged / samples * 100.0) if samples else None

    categories = {}
    for _, proc, title, fl in acts:
        cat = day_breakdown.categorize(proc, title, fl)
        categories[cat] = categories.get(cat, 0) + poll_sec / 60.0

    engagement_pct = None
    if inputs:
        engagement_pct = sum(1 for (active,) in inputs if active) / len(inputs) * 100.0

    # Optional isolated demo features. They never enter the real telemetry
    # tables; this lets the UI/analytics be exercised immediately and then
    # wiped without touching actual tracking history. Real telemetry wins
    # whenever it exists for a day.
    demo = None
    if db.game_state_get("demo_mode", "0") == "1" and not (acts or inputs or arrivals):
        try:
            demo = db.demo_daily_feature(d)
        except Exception:
            demo = None
    if demo:
        tracked_min = float(demo.get("tracked_minutes") or 0)
        flagged_pct = demo.get("flagged_pct")
        engagement_pct = demo.get("engagement_pct")
        categories = {
            "Sales": float(demo.get("sales_minutes") or 0),
            "Focus Work": float(demo.get("focus_minutes") or 0),
            "Comms": float(demo.get("comms_minutes") or 0),
            "Break": float(demo.get("break_minutes") or 0),
        }

    breakdown = game_engine.activity_breakdown(d)
    manual_units = {b["name"]: b["units"] for b in breakdown}
    manual_xp = {b["name"]: b["score_xp"] for b in breakdown}

    return {
        "day": d,
        "score_xp": game_engine.daily_score(d),
        "level_xp": game_engine.daily_score(d, level_credit=True),
        "first_scored_hour": (_clock_decimal(scoring[0][0]) if scoring else
                              (demo.get("first_scored_hour") if demo else None)),
        "arrival_hour": (_clock_decimal(arrivals[0][0]) if arrivals else
                         (demo.get("arrival_hour") if demo else None)),
        "tracked_minutes": round(tracked_min, 2),
        "flagged_pct": round(flagged_pct, 2) if flagged_pct is not None else None,
        "engagement_pct": round(engagement_pct, 2) if engagement_pct is not None else None,
        "sales_minutes": round(categories.get("Sales", 0.0), 2),
        "focus_minutes": round(categories.get("Focus Work", 0.0), 2),
        "comms_minutes": round(categories.get("Comms", 0.0), 2),
        "break_minutes": round(categories.get("Break", 0.0), 2),
        "revenue": (round(float(revenue[0][0] or 0), 2) if revenue and float(revenue[0][0] or 0) != 0
                    else round(float(demo.get("revenue") or 0), 2) if demo else 0.0),
        "manual_units": manual_units,
        "manual_xp": manual_xp,
        "has_telemetry": bool(acts or inputs or arrivals or demo),
        "has_score": game_engine.daily_score(d) != 0,
    }


def dataset(days=60, end_day=None) -> list[dict]:
    """Tracked/scored days only; unobserved days are not invented as zeros."""
    end = _as_date(end_day)
    start = end - timedelta(days=max(1, int(days)) - 1)
    rows = []
    d = start
    while d <= end:
        row = day_features(d)
        if row["has_telemetry"] or row["has_score"]:
            rows.append(row)
        d += timedelta(days=1)
    return rows


def _ranks(values):
    """Average ranks for ties (1-based), enough for Spearman correlation."""
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    if den == 0:
        return None
    return sum(x*y for x, y in zip(dx, dy)) / den


def _spearman(xs, ys):
    return _pearson(_ranks(xs), _ranks(ys))


def _strength(r):
    a = abs(r)
    if a >= 0.70:
        return "strong"
    if a >= 0.45:
        return "moderate"
    if a >= 0.25:
        return "weak"
    return "little/none"


METRICS = {
    "arrival_hour": {"label": "arrival/start time", "lower_is_more": True},
    "first_scored_hour": {"label": "time of first scored action", "lower_is_more": True},
    "tracked_minutes": {"label": "tracked computer time", "lower_is_more": False},
    "flagged_pct": {"label": "drift/flagged percentage", "lower_is_more": False},
    "engagement_pct": {"label": "keyboard/mouse engagement", "lower_is_more": False},
    "sales_minutes": {"label": "Sales-category computer time", "lower_is_more": False},
    "focus_minutes": {"label": "Focus Work computer time", "lower_is_more": False},
    "comms_minutes": {"label": "communications time", "lower_is_more": False},
    "break_minutes": {"label": "Break-category time", "lower_is_more": False},
    "revenue": {"label": "revenue received", "lower_is_more": False},
}


def correlations(days=60, end_day=None, target="score_xp",
                 target_activity=None, min_days=MIN_CORRELATION_DAYS) -> dict:
    """Rank-correlate background behaviors with a user-defined outcome.

    ``target='score_xp'`` uses the canonical daily battle score. Supplying
    ``target_activity='Booked Job'`` instead uses that Activity's daily units,
    which is useful when the person wants analysis specifically about sales/
    bookings rather than the broader score.

    This is descriptive association, not causation. No p-values or fake
    confidence decimals are manufactured; the return includes exact sample
    counts so the delivery layer can stay honest.
    """
    rows = dataset(days, end_day)

    def target_value(row):
        if target_activity:
            return float(row.get("manual_units", {}).get(target_activity, 0.0))
        return row.get(target)

    results = []
    for key, meta in METRICS.items():
        pairs = []
        for row in rows:
            x = row.get(key)
            y = target_value(row)
            if x is None or y is None:
                continue
            pairs.append((float(x), float(y), row["day"]))
        if len(pairs) < int(min_days):
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        if len(set(xs)) < 2 or len(set(ys)) < 2:
            continue
        r = _spearman(xs, ys)
        if r is None:
            continue
        # Human-readable direction respects that an earlier clock time is a
        # *smaller* value, unlike ordinary "more X" metrics.
        if meta["lower_is_more"]:
            association = "earlier tends to align with higher output" if r < 0 else \
                          "later tends to align with higher output"
        else:
            association = "more tends to align with higher output" if r > 0 else \
                          "less tends to align with higher output"
        results.append({
            "metric": key,
            "label": meta["label"],
            "spearman_r": round(r, 3),
            "strength": _strength(r),
            "association": association,
            "sample_days": len(pairs),
            "days": [p[2] for p in pairs],
        })
    results.sort(key=lambda x: abs(x["spearman_r"]), reverse=True)
    target_label = target_activity or target
    return {
        "target": target_label,
        "days_requested": int(days),
        "tracked_days": len(rows),
        "minimum_days": int(min_days),
        "ready": len(rows) >= int(min_days),
        "correlations": results,
        "note": "Associations are descriptive, not proof of causation.",
    }
