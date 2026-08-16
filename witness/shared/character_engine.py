"""Character-state projection for the PySide6 WITNESS Avatar page.

This module is intentionally *not* a second scoring system. It reads the
canonical game ledger / level state and translates proven behavior into a
visual character state: charge, earned traits, protection shield progress and
environment unlocks. None of these values award XP or change Ghost/level math.

The first avatar renderer is a lightweight 2.5D/vector presentation so the
interaction model can be proven without adding a 3D-engine dependency. A true
3D renderer can replace the visual layer later while keeping this contract.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import time

import db
import game_analytics
import game_engine

ENV_KEY = "character_environment_v1"

ENVIRONMENTS = [
    {"id": "training", "name": "Training Room", "unlock_level": 1,
     "description": "Neutral performance arena."},
    {"id": "winter", "name": "Winter", "unlock_level": 2,
     "description": "Snow, cold air and a visible shiver."},
    {"id": "tropical", "name": "Tropical", "unlock_level": 3,
     "description": "Palm silhouettes, warm air and ocean light."},
    {"id": "desert", "name": "Desert", "unlock_level": 4,
     "description": "Dunes, heat and drifting dust."},
    {"id": "city", "name": "City Night", "unlock_level": 5,
     "description": "Rain, skyline and dark city lights."},
]


def _as_date(value=None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def environment_catalog(peak_level=None) -> list[dict]:
    if peak_level is None:
        peak_level = game_engine.level_status().get("peak_level", 1)
    peak_level = int(peak_level or 1)
    return [dict(e, unlocked=peak_level >= int(e["unlock_level"]))
            for e in ENVIRONMENTS]


def selected_environment(peak_level=None) -> str:
    catalog = environment_catalog(peak_level)
    unlocked = {e["id"] for e in catalog if e["unlocked"]}
    selected = str(db.game_state_get(ENV_KEY, "training") or "training")
    if selected not in unlocked:
        selected = "training"
    return selected


def set_environment(environment_id: str) -> str:
    level = game_engine.level_status()
    catalog = environment_catalog(level.get("peak_level", 1))
    allowed = {e["id"] for e in catalog if e["unlocked"]}
    env = str(environment_id or "training")
    if env not in allowed:
        raise ValueError("That environment is still locked.")
    db.game_state_set(ENV_KEY, env)
    return env


def _charge_from_dashboard(snap: dict) -> dict:
    battle = snap.get("daily_battle", {})
    records = snap.get("records", {})
    current = max(0, int(battle.get("you", 0) or 0))
    ghost_finish = max(0, int(battle.get("ghost_final", 0) or 0))
    prior_record = max(0, int(records.get("daily_all_time_before", 0) or 0))
    # Early accounts still need a visible charge arc before a meaningful Ghost
    # or personal record exists, hence the deliberately modest 1,000-XP floor.
    target = max(1000, ghost_finish, prior_record)
    raw_pct = current / max(1, target) * 100.0
    pct = max(0, min(100, int(round(raw_pct))))
    if raw_pct >= 100:
        state = "OVERCHARGED"
    elif raw_pct >= 75:
        state = "SURGING"
    elif raw_pct >= 50:
        state = "CHARGED"
    elif raw_pct >= 25:
        state = "BUILDING"
    else:
        state = "DORMANT"
    return {
        "current_xp": current,
        "target_xp": target,
        "percent": pct,
        "raw_percent": round(raw_pct, 1),
        "state": state,
        "overcharged": raw_pct >= 100,
    }


def _monitoring_day(day: date) -> tuple[bool, bool, dict]:
    """Return (tracked, clean, details) for protection/shield purposes.

    We refuse to call an unobserved day "clean". A clean day needs actual
    monitoring evidence and no flagged drift samples, red-line or SOS events.
    Demo telemetry is respected only while explicit demo mode is active.
    """
    ds = day.isoformat()
    activity_rows = db.query(
        "SELECT COUNT(*), COALESCE(SUM(flagged),0) FROM activity WHERE day=?", (ds,))
    input_rows = db.query("SELECT COUNT(*) FROM input_activity WHERE day=?", (ds,))
    redlines = db.query("SELECT COUNT(*) FROM redlines WHERE day=?", (ds,))
    sos = db.query("SELECT COUNT(*) FROM sos WHERE day=?", (ds,))
    activity_count = int(activity_rows[0][0] or 0) if activity_rows else 0
    flagged = int(activity_rows[0][1] or 0) if activity_rows else 0
    input_count = int(input_rows[0][0] or 0) if input_rows else 0
    redline_count = int(redlines[0][0] or 0) if redlines else 0
    sos_count = int(sos[0][0] or 0) if sos else 0

    demo = None
    if db.game_state_get("demo_mode", "0") == "1" and not (activity_count or input_count):
        try:
            demo = db.demo_daily_feature(ds)
        except Exception:
            demo = None
    tracked = bool(activity_count or input_count or demo)
    if demo and not activity_count:
        # Demo fixture's flagged_pct represents observed drift samples.
        flagged = 1 if float(demo.get("flagged_pct") or 0) > 0 else 0
    clean = tracked and flagged == 0 and redline_count == 0 and sos_count == 0
    return tracked, clean, {
        "flagged_samples": flagged,
        "redlines": redline_count,
        "sos": sos_count,
    }


def protection_shield(reference_day=None, lookback=120) -> dict:
    """Consecutive *observed* days without drift/red-line/SOS breaches."""
    today = _as_date(reference_day)
    cursor = today
    tracked_today, _, _ = _monitoring_day(today)
    # The morning should not destroy yesterday's earned streak just because the
    # tracker has not collected a sample yet today.
    if not tracked_today:
        cursor -= timedelta(days=1)

    streak = 0
    last_break = None
    for _ in range(max(1, int(lookback))):
        tracked, clean, details = _monitoring_day(cursor)
        if not tracked:
            last_break = {"day": cursor.isoformat(), "reason": "not monitored"}
            break
        if not clean:
            reasons = []
            if details["flagged_samples"]:
                reasons.append("drift")
            if details["redlines"]:
                reasons.append("red-line")
            if details["sos"]:
                reasons.append("SOS")
            last_break = {"day": cursor.isoformat(), "reason": ", ".join(reasons) or "breach"}
            break
        streak += 1
        cursor -= timedelta(days=1)

    thresholds = [14, 30, 60, 90]
    tier = sum(1 for x in thresholds if streak >= x)
    next_target = next((x for x in thresholds if streak < x), None)
    if next_target is None:
        progress = 100
    else:
        prev = thresholds[tier - 1] if tier > 0 else 0
        progress = int(round((streak - prev) / max(1, next_target - prev) * 100))
    return {
        "clean_days": streak,
        "unlocked": streak >= 14,
        "tier": tier,
        "name": f"SHIELD {tier}" if tier else "SHIELD CHARGING",
        "next_target": next_target,
        "progress": max(0, min(100, progress)),
        "last_break": last_break,
        "tracking_today": tracked_today,
    }


def _trait_tier(value: int) -> str:
    if value >= 100:
        return "ELITE"
    if value >= 75:
        return "STRONG"
    if value >= 50:
        return "PROVEN"
    if value >= 25:
        return "BUILDING"
    return "FORMING"


def _persistence_trait(reference_day=None) -> dict:
    end = _as_date(reference_day)
    start = end - timedelta(days=59)
    comeback_wins = 0
    d = start + timedelta(days=1)
    while d <= end:
        prev = d - timedelta(days=1)
        prev_score = game_engine.daily_score(prev)
        prev_ghost = game_engine.daily_score(prev - timedelta(days=7))
        score = game_engine.daily_score(d)
        ghost = game_engine.daily_score(d - timedelta(days=7))
        prev_lost = prev_score < prev_ghost and (prev_score > 0 or prev_ghost > 0)
        won = score > ghost and (score > 0 or ghost > 0)
        if prev_lost and won:
            comeback_wins += 1
        d += timedelta(days=1)
    value = min(100, comeback_wins * 20)
    return {"id": "persistence", "name": "PERSISTENCE", "value": value,
            "tier": _trait_tier(value),
            "evidence": f"{comeback_wins} comeback win{'s' if comeback_wins != 1 else ''} after a losing day."}


def _momentum_trait(reference_day=None) -> dict:
    end = _as_date(reference_day)
    streak = game_engine.daily_win_streak(end).get("display_if_day_ended_now", 0)
    value = min(100, int(streak) * 15)
    return {"id": "momentum", "name": "MOMENTUM", "value": value,
            "tier": _trait_tier(value),
            "evidence": f"Current fight streak: {int(streak)} day{'s' if int(streak) != 1 else ''}."}


def _production_trait(reference_day=None) -> dict:
    end = _as_date(reference_day)
    score_map = dict(game_engine.all_daily_scores())
    current = sum(int(score_map.get((end - timedelta(days=i)).isoformat(), 0)) for i in range(7))
    if not score_map:
        best = 0
    else:
        first = min(_as_date(d) for d in score_map)
        best = 0
        cursor = first
        while cursor <= end:
            total = sum(int(score_map.get((cursor - timedelta(days=i)).isoformat(), 0)) for i in range(7))
            best = max(best, total)
            cursor += timedelta(days=1)
    value = min(100, int(round(current / max(1, best) * 100))) if best else 0
    return {"id": "production", "name": "PRODUCTION", "value": value,
            "tier": _trait_tier(value),
            "evidence": f"Last 7 days: {current:,} XP · best rolling 7: {best:,} XP."}


def _focus_trait(reference_day=None) -> dict:
    end = _as_date(reference_day)
    try:
        rows = game_analytics.dataset(14, end)
    except Exception:
        rows = []
    focus_days = [float(r.get("focus_minutes") or 0) for r in rows if r.get("has_telemetry")]
    if focus_days:
        avg = sum(focus_days) / len(focus_days)
        value = min(100, int(round(avg / 120.0 * 100)))
        evidence = f"Observed Focus Work: {avg:.0f} min/day across {len(focus_days)} tracked days."
    else:
        # If computer telemetry is unavailable, user-defined timed Focus
        # Activities can still provide a transparent manual signal.
        start = end - timedelta(days=13)
        rows2 = db.query(
            "SELECT COALESCE(SUM(quantity),0) FROM xp_events WHERE day>=? AND day<=? "
            "AND LOWER(activity_name) LIKE '%focus%' AND event_type='activity'",
            (start.isoformat(), end.isoformat()))
        mins = float(rows2[0][0] or 0) if rows2 else 0.0
        avg = mins / 14.0
        value = min(100, int(round(avg / 120.0 * 100))) if mins else 0
        evidence = (f"Manual Focus activity: {mins:.0f} min across 14 days."
                    if mins else "No Focus telemetry yet.")
    return {"id": "focus", "name": "FOCUS", "value": value,
            "tier": _trait_tier(value), "evidence": evidence}


def attributes(reference_day=None, shield=None) -> list[dict]:
    shield = shield or protection_shield(reference_day)
    discipline_value = min(100, int(round(shield["clean_days"] / 14.0 * 100)))
    discipline = {
        "id": "discipline", "name": "DISCIPLINE", "value": discipline_value,
        "tier": _trait_tier(discipline_value),
        "evidence": f"{shield['clean_days']}/14 clean monitored days toward the first shield.",
    }
    return [
        _persistence_trait(reference_day),
        discipline,
        _momentum_trait(reference_day),
        _production_trait(reference_day),
        _focus_trait(reference_day),
    ]


def live_state(now_ts=None) -> dict:
    now_ts = time.time() if now_ts is None else float(now_ts)
    snap = game_engine.dashboard_snapshot(now_ts)
    level = snap["level"]
    envs = environment_catalog(level.get("peak_level", 1))
    return {
        "generated_ts": now_ts,
        "level": level,
        "charge": _charge_from_dashboard(snap),
        "environment": selected_environment(level.get("peak_level", 1)),
        "environments": envs,
        "battle": snap.get("daily_battle", {}),
    }


def snapshot(now_ts=None) -> dict:
    live = live_state(now_ts)
    shield = protection_shield()
    live["shield"] = shield
    live["attributes"] = attributes(shield=shield)
    return live
