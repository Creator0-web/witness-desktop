"""Isolated synthetic history for exercising WITNESS before real data exists.

This module is development/demo support, not part of the canonical scoring
rules. Synthetic XP enters the normal immutable ledger with source
``synthetic_demo`` so every Ghost/record/level/calendar query sees the exact
same data shape as real actions. Synthetic analytics features live in the
separate ``demo_daily_features`` table; they never pollute raw telemetry.

``clear()`` removes only rows/files created by this demo fixture and restores
the pre-demo rolling-level state. Real user XP, notes, videos and telemetry are
left alone.
"""
from __future__ import annotations

import json
import math
import os
import random
from datetime import date, datetime, time as dtime, timedelta

import db
import game_engine

DEMO_SOURCE = "synthetic_demo"
DEMO_MODE_KEY = "demo_mode"
DEMO_MANIFEST_KEY = "demo_manifest_v1"
DEMO_LEVEL_BACKUP_KEY = "demo_level_backup_v1"

DEFAULTS = [
    ("Cold Calls", 10, "repeatable"),
    ("Booked Job", 500, "repeatable"),
    ("Workout", 150, "once_daily"),
    ("Focus Work", 100, "timed"),
]


def _local_ts(day: date, hour: int, minute: int, second: int = 0) -> float:
    return datetime.combine(day, dtime(hour, minute, second)).timestamp()


def _find_or_create_demo_activities():
    existing = game_engine.list_activities(False)
    by_name = {a["name"].casefold(): a for a in existing}
    created = []
    out = {}
    next_order = max([a.get("sort_order", 0) for a in existing] + [-1]) + 1
    for name, xp, kind in DEFAULTS:
        a = by_name.get(name.casefold())
        if a:
            if not a["active"]:
                a = game_engine.update_activity(a["id"], active=True)
            out[name] = a
            continue
        aid = game_engine.create_activity(name, xp, kind, True, next_order)
        next_order += 1
        created.append(aid)
        out[name] = db.get_scoring_activity(aid)
    return out, created


def _event(activity, day, hour, minute, quantity, score_xp):
    ts = _local_ts(day, hour, minute)
    return db.log_xp_event(
        ts, day.isoformat(), activity["id"], activity["name"], "activity",
        float(quantity), int(score_xp), int(score_xp), int(score_xp), 1.0,
        None, DEMO_SOURCE,
        json.dumps({"demo": True, "fixture": "v1"}))


def _generate_day(day, idx, activities, now_dt):
    """Generate one deterministic but imperfect day; return summary stats."""
    seed = int(day.strftime("%Y%m%d")) + 731
    rng = random.Random(seed)
    weekday = day.weekday()
    weekend = weekday >= 5

    # Slow upward drift across four weeks, but with real-looking bad days.
    trend = 0.72 + idx * 0.018
    wobble = rng.uniform(0.82, 1.16)
    if idx in (5, 12, 18):
        wobble *= 0.58
    if weekend:
        wobble *= 0.63
    effort = trend * wobble

    calls = max(4, int(round((24 if weekend else 42) * effort + rng.randint(-5, 7))))
    bookings = max(0, int(round((0.5 if weekend else 1.35) * effort + rng.uniform(-0.55, 0.8))))
    if idx in (9, 20, 25):
        bookings += 2  # memorable record spikes
    focus_minutes = max(30, int(round((95 if weekend else 190) * effort / 15) * 15))
    workout = (idx % 3 != 1 and not (weekend and idx % 2))

    # Better days start somewhat earlier; enough variation for analytics.
    start_hour = 9.45 - min(1.25, idx * 0.035) + rng.uniform(-0.35, 0.28)
    start_hour = max(7.15, min(10.15, start_hour))
    start_h = int(start_hour)
    start_m = int(round((start_hour - start_h) * 60))

    # Calls spread through the workday, making the Ghost genuinely replay.
    call_times = []
    span_min = 7 * 60 + 15
    for n in range(calls):
        offset = int((n / max(1, calls - 1)) * span_min) + rng.randint(-6, 6)
        total = start_h * 60 + start_m + max(0, offset)
        h, m = min(18, total // 60), total % 60
        call_times.append((h, m))

    booking_slots = [(11, 18), (14, 8), (16, 47), (17, 36)]
    focus_slots = [(start_h, min(59, start_m + 8)), (13, 5)]
    workout_slot = (18, 10)

    is_today = day == now_dt.date()
    cutoff = now_dt.hour * 60 + now_dt.minute if is_today else 24 * 60

    inserted_calls = 0
    for h, m in call_times:
        if h * 60 + m > cutoff:
            continue
        _event(activities["Cold Calls"], day, h, m, 1, activities["Cold Calls"]["xp_value"])
        inserted_calls += 1

    inserted_bookings = 0
    for h, m in booking_slots[:bookings]:
        if h * 60 + m > cutoff:
            continue
        _event(activities["Booked Job"], day, h, m, 1, activities["Booked Job"]["xp_value"])
        inserted_bookings += 1

    # Split focus into two timestamped timed entries, preserving minutes as quantity.
    remaining_focus = focus_minutes
    focus_inserted = 0
    for slot_i, (h, m) in enumerate(focus_slots):
        if remaining_focus <= 0 or h * 60 + m > cutoff:
            continue
        mins = min(remaining_focus, 90 if slot_i == 0 else remaining_focus)
        score = int(round(activities["Focus Work"]["xp_value"] * mins / 60.0))
        _event(activities["Focus Work"], day, h, m, mins, score)
        focus_inserted += mins
        remaining_focus -= mins

    workout_inserted = False
    if workout and workout_slot[0] * 60 + workout_slot[1] <= cutoff:
        _event(activities["Workout"], day, workout_slot[0], workout_slot[1], 1,
               activities["Workout"]["xp_value"])
        workout_inserted = True

    score = game_engine.daily_score(day)
    # Synthetic analysis features deliberately correlate with the explicit score
    # but are not perfect, so the Insights screen shows believable signal rather
    # than mathematically identical relationships.
    score_scale = min(1.0, score / 2300.0) if score else 0.0
    tracked = max(80.0, 240 + focus_inserted + inserted_calls * 1.2 + rng.uniform(-25, 30))
    flagged = max(2.0, min(42.0, 30 - score_scale * 21 + rng.uniform(-5, 5)))
    engagement = max(35.0, min(96.0, 58 + score_scale * 31 + rng.uniform(-7, 6)))
    sales_minutes = max(0.0, inserted_calls * 1.5 + inserted_bookings * 20 + rng.uniform(-8, 10))
    focus_metric = max(0.0, focus_inserted + rng.uniform(-12, 16))
    comms = max(0.0, 25 + inserted_calls * 0.55 + rng.uniform(-10, 12))
    break_min = max(8.0, 95 - score_scale * 58 + rng.uniform(-12, 12))
    revenue = max(0.0, inserted_bookings * (250 + rng.randint(0, 240)))

    first_scored = None
    events = db.xp_events_for_day(day.isoformat())
    demo_events = [e for e in events if e.get("source") == DEMO_SOURCE and e.get("score_xp", 0) > 0]
    if demo_events:
        dt = datetime.fromtimestamp(demo_events[0]["ts"])
        first_scored = dt.hour + dt.minute / 60

    db.save_demo_daily_feature(day.isoformat(), {
        "first_scored_hour": first_scored,
        "arrival_hour": start_hour - rng.uniform(0.08, 0.22),
        "tracked_minutes": tracked,
        "flagged_pct": flagged,
        "engagement_pct": engagement,
        "sales_minutes": sales_minutes,
        "focus_minutes": focus_metric,
        "comms_minutes": comms,
        "break_minutes": break_min,
        "revenue": revenue,
    })
    return score


def seed(days=28):
    """Seed/reseed a four-week demo history and return a compact summary."""
    clear(restore_level=False)
    activities, created = _find_or_create_demo_activities()

    original_level = db.game_state_get(game_engine.LEVEL_STATE_KEY)
    if original_level is not None:
        db.game_state_set(DEMO_LEVEL_BACKUP_KEY, original_level)
    else:
        db.game_state_delete(DEMO_LEVEL_BACKUP_KEY)

    now_dt = datetime.now()
    start = now_dt.date() - timedelta(days=max(14, int(days)) - 1)
    demo_days = []
    scores = []
    for idx in range((now_dt.date() - start).days + 1):
        d = start + timedelta(days=idx)
        demo_days.append(d.isoformat())
        scores.append(_generate_day(d, idx, activities, now_dt))
        # Calendar's hourly-history layer already has its own isolated
        # synthetic format. Populate it too so clicking demo days is useful.
        try:
            import day_breakdown
            day_breakdown.synth_seed_day(d.isoformat())
        except Exception:
            pass

    manifest = {"days": demo_days, "created_activity_ids": created}
    db.game_state_set(DEMO_MANIFEST_KEY, json.dumps(manifest))
    db.game_state_set(DEMO_MODE_KEY, "1")
    # Reset the rolling state so level_status is derived from the demo history,
    # while the original state remains backed up for clear().
    db.game_state_delete(game_engine.LEVEL_STATE_KEY)
    level = game_engine.level_status()
    return {
        "active": True,
        "days": len(demo_days),
        "events": len(db.query("SELECT id FROM xp_events WHERE source=?", (DEMO_SOURCE,))),
        "highest_day": max(scores) if scores else 0,
        "level": level,
    }


def clear(restore_level=True):
    """Remove only synthetic fixture data. Real history is untouched."""
    raw = db.game_state_get(DEMO_MANIFEST_KEY)
    try:
        manifest = json.loads(raw) if raw else {}
    except Exception:
        manifest = {}

    removed_events = db.delete_xp_events_by_source(DEMO_SOURCE)
    # Level transitions that occur while demo mode is active are tagged with
    # the same source so clearing the fixture cannot pollute real progression.
    try:
        db.delete_level_events_by_source(DEMO_SOURCE)
    except Exception:
        pass
    db.clear_demo_daily_features()

    # Remove only hourly-history documents that are still marked synthetic.
    try:
        import day_breakdown
        for day_s in manifest.get("days", []):
            try:
                doc = day_breakdown.load_day(day_s)
                if doc and doc.get("synthetic"):
                    path = day_breakdown._path(day_s)
                    if os.path.exists(path):
                        os.remove(path)
            except Exception:
                pass
    except Exception:
        pass

    for aid in manifest.get("created_activity_ids", []):
        try:
            game_engine.deactivate_activity(int(aid))
        except Exception:
            pass

    if restore_level:
        backup = db.game_state_get(DEMO_LEVEL_BACKUP_KEY)
        if backup is None:
            db.game_state_delete(game_engine.LEVEL_STATE_KEY)
        else:
            db.game_state_set(game_engine.LEVEL_STATE_KEY, backup)
    db.game_state_delete(DEMO_LEVEL_BACKUP_KEY)
    db.game_state_delete(DEMO_MANIFEST_KEY)
    db.game_state_set(DEMO_MODE_KEY, "0")
    return {"active": False, "removed_events": removed_events}


def status():
    active = db.game_state_get(DEMO_MODE_KEY, "0") == "1"
    raw = db.game_state_get(DEMO_MANIFEST_KEY)
    try:
        manifest = json.loads(raw) if raw else {}
    except Exception:
        manifest = {}
    return {
        "active": active,
        "days": len(manifest.get("days", [])),
        "events": len(db.query("SELECT id FROM xp_events WHERE source=?", (DEMO_SOURCE,))),
    }
