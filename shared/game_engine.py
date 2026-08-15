"""WITNESS V1 self-competition / scoring engine.

This module is deliberately the *muscle*, not the presentation layer.
It owns the canonical rules for:

- configurable manual scoring Activities
- immutable, timestamped XP events (the source of truth)
- daily score and per-activity breakdowns
- live same-time ghost races against the same weekday last week
- current-week vs prior-week campaign races
- daily / weekday / weekly / activity high scores
- day-win and week-win streaks
- 14-day exponentially-decayed rolling level rating
- 85% demotion floor + 48h at-risk grace period
- 1.5x comeback credit toward the rolling level after a demotion

Important scoring separation:

``score_xp`` is the battle/high-score number and always remains the exact
amount the person configured for an Activity. A 500-XP booking is always 500
battle XP. ``level_xp`` is allowed to receive a comeback multiplier after an
actual demotion; this lets progression help a comeback without corrupting the
fairness of the ghost/high-score race.

The existing character/progression.py engine is kept alive temporarily for the
current UI. Manual events sync into it on today's real interactions, but this
module + shared/db.py are the canonical backend for the new product direction.
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

import data
import db

ACTIVITY_KINDS = ("repeatable", "once_daily", "timed")
KIND_ALIASES = {
    "r": "repeatable", "repeat": "repeatable", "repeatable": "repeatable",
    "d": "once_daily", "daily": "once_daily", "once": "once_daily",
    "once_daily": "once_daily", "checkbox": "once_daily",
    "t": "timed", "time": "timed", "timed": "timed",
}

ROLLING_DAYS = 14
DECAY_LAMBDA = 0.10
DEMOTION_FLOOR_RATIO = 0.85
AT_RISK_SECONDS = 48 * 60 * 60
COMEBACK_MULTIPLIER = 1.5

# Deliberately small V1 ladder from the person's scoring design. It can be
# expanded later without changing the event ledger or battle math.
LEVELS = [
    {"level": 1, "threshold": 0, "name": "Recruit"},
    {"level": 2, "threshold": 5000, "name": "Operative"},
    {"level": 3, "threshold": 12800, "name": "Specialist"},
    {"level": 4, "threshold": 24100, "name": "Commando"},
    {"level": 5, "threshold": 39200, "name": "Sentinel"},
]
LEVEL_STATE_KEY = "rolling_level_v1"
MIGRATION_KEY = "legacy_activities_migrated_v1"


class GameEngineError(Exception):
    pass


class ActivityAlreadyCompleted(GameEngineError):
    pass


class ActivityNotFound(GameEngineError):
    pass


class NothingToUndo(GameEngineError):
    pass


def _as_date(value=None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _day_str(value=None) -> str:
    return _as_date(value).isoformat()


def _day_start_ts(day) -> float:
    d = _as_date(day)
    return datetime.combine(d, datetime.min.time()).timestamp()


def _day_end_ts(day) -> float:
    d = _as_date(day)
    # Use local-midnight boundaries rather than +86400 so DST transition
    # days remain correct on the person's Windows machine.
    return datetime.combine(d + timedelta(days=1), datetime.min.time()).timestamp() - 0.000001


def _cutoff_on_day(day, reference_ts=None) -> float:
    """Timestamp on ``day`` with the same local clock time as reference_ts."""
    reference_ts = time.time() if reference_ts is None else float(reference_ts)
    ref = datetime.fromtimestamp(reference_ts)
    d = _as_date(day)
    return datetime.combine(d, ref.time()).timestamp()


def _week_start(day) -> date:
    d = _as_date(day)
    return d - timedelta(days=d.weekday())


def _safe_int(value, default=0, minimum=None):
    try:
        out = int(value)
    except (TypeError, ValueError):
        out = int(default)
    if minimum is not None:
        out = max(int(minimum), out)
    return out


def normalize_kind(kind) -> str:
    k = str(kind or "repeatable").strip().lower().replace("-", "_")
    normalized = KIND_ALIASES.get(k)
    if not normalized:
        raise ValueError(f"Unknown activity kind: {kind}")
    return normalized


# ── initialization / migration ──────────────────────────────────────────

def initialize() -> dict:
    """Initialize the V1 game backend and migrate the old checklist once.

    db.init() must already have run. Migration is intentionally conservative:
    only the existing manual Activities roster is copied. Automatic XP
    triggers and old generic progression bonuses are *not* imported into the
    new battle score because the new design says the user-configured manual
    Activity ledger is authoritative.
    """
    migrated = False
    if db.game_state_get(MIGRATION_KEY) != "1":
        existing = db.list_scoring_activities(active_only=False)
        if not existing:
            try:
                old_items = data.get_tasks()
            except Exception:
                old_items = []
            for order, item in enumerate(old_items):
                name = str(item.get("text", "")).strip()
                if not name:
                    continue
                xp = _safe_int(item.get("custom_xp", 10), 10, 0)
                aid = create_activity(name, xp, "repeatable", sort_order=order)
                # If this exact activity was already checked in the transitional
                # v7.41 build, preserve its score in the new ledger without
                # touching legacy progression again (it already got that XP).
                if item.get("done"):
                    awarded = _safe_int(item.get("awarded_xp", xp), xp, 0)
                    now = time.time()
                    db.log_xp_event(
                        now, date.today().isoformat(), aid, name, "activity", 1,
                        awarded, awarded, awarded, 1.0, None,
                        source="v7.41_migration",
                        metadata=json.dumps({"from": "data.tasks"}))
                migrated = True
        db.game_state_set(MIGRATION_KEY, "1")
    # Creating the level state here prevents the first UI read from feeling
    # like a migration side effect.
    level = level_status()
    return {"migrated_legacy_activities": migrated, "level": level}


# ── Activity definitions ────────────────────────────────────────────────

def create_activity(name, xp_value, kind="repeatable", active=True,
                    sort_order=0) -> int:
    kind = normalize_kind(kind)
    xp = _safe_int(xp_value, 10, 0)
    return db.save_scoring_activity(
        str(name).strip(), xp, kind, bool(active), int(sort_order))


def update_activity(activity_id, name=None, xp_value=None, kind=None,
                    active=None, sort_order=None) -> dict:
    old = db.get_scoring_activity(activity_id)
    if not old:
        raise ActivityNotFound(activity_id)
    name = old["name"] if name is None else str(name).strip()
    xp_value = old["xp_value"] if xp_value is None else _safe_int(xp_value, 10, 0)
    kind = old["kind"] if kind is None else normalize_kind(kind)
    active = old["active"] if active is None else bool(active)
    sort_order = old["sort_order"] if sort_order is None else int(sort_order)
    db.save_scoring_activity(name, xp_value, kind, active, sort_order,
                             activity_id=activity_id)
    return db.get_scoring_activity(activity_id)


def deactivate_activity(activity_id):
    if not db.get_scoring_activity(activity_id):
        raise ActivityNotFound(activity_id)
    db.deactivate_scoring_activity(activity_id)


def list_activities(active_only=True) -> list[dict]:
    return db.list_scoring_activities(active_only=active_only)


def sync_activity_roster(items: list[dict]) -> list[dict]:
    """Make the active roster match ``items`` while preserving history/IDs.

    Items may include id/name/xp_value/kind. Existing rows are matched by id
    first, then case-insensitive name. Rows removed from the editor are merely
    deactivated; historical XP events are never deleted or rewritten.
    """
    all_existing = db.list_scoring_activities(active_only=False)
    by_id = {a["id"]: a for a in all_existing}
    by_name = {a["name"].casefold(): a for a in all_existing}
    kept = set()
    result = []
    seen_names = set()
    for order, raw in enumerate(items):
        name = str(raw.get("name", raw.get("text", ""))).strip()
        if not name or name.casefold() in seen_names:
            continue
        seen_names.add(name.casefold())
        xp = _safe_int(raw.get("xp_value", raw.get("custom_xp", 10)), 10, 0)
        kind = normalize_kind(raw.get("kind", "repeatable"))
        match = None
        rid = raw.get("id")
        if rid is not None:
            try:
                match = by_id.get(int(rid))
            except (TypeError, ValueError):
                match = None
        if match is None:
            match = by_name.get(name.casefold())
        if match:
            out = update_activity(match["id"], name=name, xp_value=xp,
                                  kind=kind, active=True, sort_order=order)
        else:
            aid = create_activity(name, xp, kind, True, order)
            out = db.get_scoring_activity(aid)
        kept.add(out["id"])
        result.append(out)
    for old in all_existing:
        if old["id"] not in kept and old["active"]:
            db.deactivate_scoring_activity(old["id"])
    return result


# ── canonical event ledger ──────────────────────────────────────────────

def _sync_legacy_progression_add(name, score_xp, day):
    if day != date.today().isoformat() or score_xp <= 0:
        return
    try:
        import progression
        progression.award_activity_xp(name, score_xp)
    except Exception:
        # The new SQLite ledger is canonical. A legacy display failure must
        # never roll back or erase a real-life scoring event.
        pass


def _sync_legacy_progression_remove(name, score_xp, day):
    if day != date.today().isoformat() or score_xp <= 0:
        return
    try:
        import progression
        progression.remove_activity_xp(name, score_xp)
    except Exception:
        pass


def record_activity(activity_id, quantity=1, *, minutes=None, ts=None,
                    source="manual", sync_legacy=True) -> dict:
    """Record one manual real-life action in the immutable XP ledger.

    repeatable: ``quantity`` units, each worth the configured XP.
    once_daily: exactly one completion; a second is rejected until reversed.
    timed: configured XP is *per hour*; pass ``minutes`` (or quantity as
           minutes) and score is prorated to the nearest whole XP.
    """
    activity = db.get_scoring_activity(activity_id)
    if not activity or not activity["active"]:
        raise ActivityNotFound(activity_id)
    ts = time.time() if ts is None else float(ts)
    day = datetime.fromtimestamp(ts).date().isoformat()
    kind = activity["kind"]

    if kind == "once_daily":
        state = activity_day_state(activity_id, day)
        if state["units"] > 0:
            raise ActivityAlreadyCompleted(
                f"{activity['name']} is already complete for {day}")
        qty = 1.0
        score_xp = int(activity["xp_value"])
    elif kind == "timed":
        qty = float(minutes if minutes is not None else quantity)
        if qty <= 0:
            raise ValueError("Timed activity minutes must be > 0")
        score_xp = int(round(activity["xp_value"] * qty / 60.0))
    else:
        qty = float(quantity)
        if qty <= 0:
            raise ValueError("Activity quantity must be > 0")
        score_xp = int(round(activity["xp_value"] * qty))

    # Battle/high-score XP is exact. Comeback affects only level credit.
    before_level = level_status(now_ts=ts)
    level_mult = COMEBACK_MULTIPLIER if before_level["comeback_active"] else 1.0
    level_xp = int(round(score_xp * level_mult))
    event_id = db.log_xp_event(
        ts, day, activity["id"], activity["name"], "activity", qty,
        score_xp, score_xp, level_xp, level_mult, None, source, None)
    if sync_legacy:
        _sync_legacy_progression_add(activity["name"], score_xp, day)
    after_level = level_status(now_ts=ts)
    event = db.get_xp_event(event_id)
    event["day_total"] = daily_score(day)
    event["level"] = after_level
    return event


def reverse_event(event_id, *, ts=None, source="manual_undo",
                  sync_legacy=True) -> dict:
    """Reverse an event by appending a negative ledger row; never delete it."""
    original = db.get_xp_event(event_id)
    if not original or original["event_type"] != "activity":
        raise NothingToUndo(event_id)
    if db.event_has_reversal(event_id):
        raise NothingToUndo(f"Event {event_id} is already reversed")
    ts = time.time() if ts is None else float(ts)
    # Reversal belongs to the same scoring day as the original. If a future
    # history editor reverses an older event, anchor the reversal timestamp
    # inside that original day too, so day-based and timestamp-range queries
    # cannot disagree about the score.
    day = original["day"]
    if datetime.fromtimestamp(ts).date().isoformat() != day:
        ts = min(_day_end_ts(day), float(original["ts"]) + 0.001)
    rev_id = db.log_xp_event(
        ts, day, original["activity_id"], original["activity_name"],
        "reversal", -abs(float(original["quantity"])),
        -abs(int(original["base_xp"])), -abs(int(original["score_xp"])),
        -abs(int(original["level_xp"])), float(original["level_multiplier"]),
        int(original["id"]), source,
        json.dumps({"original_event_id": original["id"]}))
    if sync_legacy:
        _sync_legacy_progression_remove(
            original["activity_name"], abs(int(original["score_xp"])), day)
    level_status(now_ts=ts)
    out = db.get_xp_event(rev_id)
    out["day_total"] = daily_score(day)
    return out


def undo_last_activity(activity_id, day=None, *, ts=None,
                       sync_legacy=True) -> dict:
    day = _day_str(day)
    event = db.latest_unreversed_activity_event(activity_id, day)
    if not event:
        raise NothingToUndo(f"No {day} activity event to undo")
    return reverse_event(event["id"], ts=ts, sync_legacy=sync_legacy)


def activity_day_state(activity_id, day=None) -> dict:
    day = _day_str(day)
    activity = db.get_scoring_activity(activity_id)
    if not activity:
        raise ActivityNotFound(activity_id)
    events = db.xp_events_for_day(day, activity_id=activity_id)
    units = sum(float(e["quantity"]) for e in events)
    score = sum(int(e["score_xp"]) for e in events)
    level_credit = sum(int(e["level_xp"]) for e in events)
    positive_events = sum(1 for e in events if e["event_type"] == "activity")
    return {
        "activity_id": activity_id,
        "day": day,
        "kind": activity["kind"],
        "units": max(0.0, units),
        "score_xp": max(0, score),
        "level_xp": max(0, level_credit),
        "positive_events": positive_events,
        "complete": units > 0 if activity["kind"] == "once_daily" else False,
    }


def activities_snapshot(day=None) -> list[dict]:
    day = _day_str(day)
    out = []
    for activity in list_activities(True):
        row = dict(activity)
        row["today"] = activity_day_state(activity["id"], day)
        out.append(row)
    return out


# ── score queries / breakdowns ─────────────────────────────────────────

def daily_score(day=None, up_to_ts=None, *, level_credit=False) -> int:
    day = _day_str(day)
    field = "level_xp" if level_credit else "score_xp"
    events = db.xp_events_for_day(day, up_to_ts=up_to_ts)
    return int(sum(int(e[field]) for e in events))


def score_between(start_ts, end_ts, *, level_credit=False) -> int:
    field = "level_xp" if level_credit else "score_xp"
    return int(sum(int(e[field]) for e in db.xp_events_between(start_ts, end_ts)))


def daily_timeline(day=None) -> list[dict]:
    day = _day_str(day)
    running = 0
    out = []
    for e in db.xp_events_for_day(day):
        running += int(e["score_xp"])
        row = dict(e)
        row["running_score"] = running
        row["clock"] = datetime.fromtimestamp(e["ts"]).strftime("%I:%M %p").lstrip("0")
        out.append(row)
    return out


def activity_breakdown(day=None) -> list[dict]:
    day = _day_str(day)
    buckets = {}
    for e in db.xp_events_for_day(day):
        key = e["activity_id"] if e["activity_id"] is not None else e["activity_name"]
        b = buckets.setdefault(key, {
            "activity_id": e["activity_id"], "name": e["activity_name"],
            "units": 0.0, "score_xp": 0, "level_xp": 0,
        })
        b["units"] += float(e["quantity"])
        b["score_xp"] += int(e["score_xp"])
        b["level_xp"] += int(e["level_xp"])
    rows = []
    for b in buckets.values():
        b["units"] = max(0.0, b["units"])
        b["score_xp"] = max(0, b["score_xp"])
        b["level_xp"] = max(0, b["level_xp"])
        rows.append(b)
    return sorted(rows, key=lambda x: (-x["score_xp"], x["name"].lower()))


def all_daily_scores() -> list[tuple[str, int]]:
    rows = db.query(
        "SELECT day, COALESCE(SUM(score_xp),0) FROM xp_events "
        "GROUP BY day ORDER BY day")
    return [(str(day), int(score or 0)) for day, score in rows]


def all_daily_level_scores() -> list[tuple[str, int]]:
    """Daily level-credit totals used for efficient historical rating charts."""
    rows = db.query(
        "SELECT day, COALESCE(SUM(level_xp),0) FROM xp_events "
        "GROUP BY day ORDER BY day")
    return [(str(day), int(score or 0)) for day, score in rows]


def _weekly_score_map() -> dict[str, int]:
    out = defaultdict(int)
    for day_str, score in all_daily_scores():
        ws = _week_start(day_str).isoformat()
        out[ws] += int(score)
    return dict(out)


# ── live ghost competition ──────────────────────────────────────────────

def daily_battle(day=None, now_ts=None) -> dict:
    now_ts = time.time() if now_ts is None else float(now_ts)
    day_d = _as_date(day or datetime.fromtimestamp(now_ts).date())
    ghost_d = day_d - timedelta(days=7)
    current_cutoff = _cutoff_on_day(day_d, now_ts)
    ghost_cutoff = _cutoff_on_day(ghost_d, now_ts)
    you = daily_score(day_d, current_cutoff)
    ghost = daily_score(ghost_d, ghost_cutoff)
    ghost_final = daily_score(ghost_d)
    gap = you - ghost

    next_ghost = None
    for e in db.xp_events_for_day(ghost_d.isoformat()):
        if e["ts"] > ghost_cutoff:
            next_ghost = {
                "clock": datetime.fromtimestamp(e["ts"]).strftime("%I:%M %p").lstrip("0"),
                "score_xp": int(e["score_xp"]),
                "activity": e["activity_name"],
            }
            break
    return {
        "mode": "daily",
        "day": day_d.isoformat(),
        "ghost_day": ghost_d.isoformat(),
        "you": you,
        "ghost": ghost,
        "ghost_final": ghost_final,
        "gap": gap,
        "status": "ahead" if gap > 0 else ("behind" if gap < 0 else "tied"),
        "same_clock": datetime.fromtimestamp(current_cutoff).strftime("%I:%M %p").lstrip("0"),
        "next_ghost_event": next_ghost,
    }


def weekly_campaign(day=None, now_ts=None) -> dict:
    now_ts = time.time() if now_ts is None else float(now_ts)
    day_d = _as_date(day or datetime.fromtimestamp(now_ts).date())
    current_start = _week_start(day_d)
    current_cutoff = _cutoff_on_day(day_d, now_ts)
    ghost_start = current_start - timedelta(days=7)
    ghost_day = day_d - timedelta(days=7)
    ghost_cutoff = _cutoff_on_day(ghost_day, now_ts)
    you = score_between(_day_start_ts(current_start), current_cutoff)
    ghost = score_between(_day_start_ts(ghost_start), ghost_cutoff)
    ghost_final = score_between(
        _day_start_ts(ghost_start), _day_end_ts(ghost_start + timedelta(days=6)))
    gap = you - ghost

    players = []
    for offset in range(day_d.weekday() + 1):
        cur_day = current_start + timedelta(days=offset)
        old_day = cur_day - timedelta(days=7)
        if cur_day == day_d:
            cur_score = daily_score(cur_day, current_cutoff)
            old_score = daily_score(old_day, _cutoff_on_day(old_day, now_ts))
            live = True
        else:
            cur_score = daily_score(cur_day)
            old_score = daily_score(old_day)
            live = False
        players.append({
            "day": cur_day.isoformat(), "ghost_day": old_day.isoformat(),
            "weekday": cur_day.strftime("%A"), "you": cur_score,
            "ghost": old_score, "gap": cur_score - old_score,
            "status": "ahead" if cur_score > old_score else
                      ("behind" if cur_score < old_score else "tied"),
            "live": live,
        })
    return {
        "mode": "weekly",
        "week_start": current_start.isoformat(),
        "ghost_week_start": ghost_start.isoformat(),
        "you": you,
        "ghost": ghost,
        "ghost_final": ghost_final,
        "gap": gap,
        "status": "ahead" if gap > 0 else ("behind" if gap < 0 else "tied"),
        "players": players,
    }


# ── records / high-score surge ─────────────────────────────────────────

def _scores_before(day) -> list[tuple[str, int]]:
    day_s = _day_str(day)
    return [(d, s) for d, s in all_daily_scores() if d < day_s]


def records_snapshot(day=None) -> dict:
    day_d = _as_date(day)
    day_s = day_d.isoformat()
    current = daily_score(day_s)
    prior = _scores_before(day_d)
    all_time_before = max((s for _, s in prior), default=0)
    weekday_before = max(
        (s for d, s in prior if _as_date(d).weekday() == day_d.weekday()),
        default=0)

    week_start = _week_start(day_d)
    weekly = _weekly_score_map()
    current_week = weekly.get(week_start.isoformat(), 0)
    prior_weeks = [score for ws, score in weekly.items() if ws < week_start.isoformat()]
    weekly_before = max(prior_weeks, default=0)

    activity_records = []
    for a in db.list_scoring_activities(active_only=False):
        rows = db.query(
            "SELECT day, COALESCE(SUM(quantity),0), COALESCE(SUM(score_xp),0) "
            "FROM xp_events WHERE activity_id=? GROUP BY day ORDER BY day",
            (a["id"],))
        if rows:
            best = max(rows, key=lambda r: (float(r[1]), int(r[2])))
            activity_records.append({
                "activity_id": a["id"], "name": a["name"],
                "best_day": best[0], "best_units": max(0.0, float(best[1])),
                "best_score_xp": max(0, int(best[2])),
            })

    return {
        "day": day_s,
        "current_daily": current,
        "daily_all_time_before": all_time_before,
        "daily_remaining": max(0, all_time_before - current),
        "daily_record_broken": current > all_time_before and current > 0,
        "weekday_name": day_d.strftime("%A"),
        "weekday_record_before": weekday_before,
        "weekday_record_broken": current > weekday_before and current > 0,
        "current_week": current_week,
        "weekly_record_before": weekly_before,
        "weekly_remaining": max(0, weekly_before - current_week),
        "weekly_record_broken": current_week > weekly_before and current_week > 0,
        "activity_records": activity_records,
    }


def historical_record_days() -> set[str]:
    """Days that set a new all-time daily high *when they happened*."""
    best = -1
    out = set()
    for d, score in all_daily_scores():
        if score > best and score > 0:
            out.add(d)
            best = score
    return out


def historical_record_weeks() -> set[str]:
    best = -1
    out = set()
    for ws, score in sorted(_weekly_score_map().items()):
        if score > best and score > 0:
            out.add(ws)
            best = score
    return out


# ── win streaks ─────────────────────────────────────────────────────────

def daily_win_streak(day=None, now_ts=None) -> dict:
    day_d = _as_date(day)
    # Only completed days build the official streak.
    cur = day_d - timedelta(days=1)
    completed = 0
    while True:
        score = daily_score(cur)
        ghost = daily_score(cur - timedelta(days=7))
        if score > ghost and (score > 0 or ghost > 0):
            completed += 1
            cur -= timedelta(days=1)
        else:
            break
        if completed > 366:
            break
    live = daily_battle(day_d, now_ts)
    return {
        "completed": completed,
        "live_ahead": live["status"] == "ahead",
        "display_if_day_ended_now": completed + (1 if live["status"] == "ahead" else 0),
    }


def weekly_win_streak(day=None) -> int:
    current_ws = _week_start(day)
    cur = current_ws - timedelta(days=7)  # last completed week
    scores = _weekly_score_map()
    count = 0
    while True:
        this_score = scores.get(cur.isoformat(), 0)
        prev = scores.get((cur - timedelta(days=7)).isoformat(), 0)
        if this_score > prev and (this_score > 0 or prev > 0):
            count += 1
            cur -= timedelta(days=7)
        else:
            break
        if count > 104:
            break
    return count


# ── rolling level / decay / demotion ───────────────────────────────────

def rolling_rating(reference_day=None) -> dict:
    ref = _as_date(reference_day)
    components = []
    total = 0.0
    for days_ago in range(ROLLING_DAYS):
        d = ref - timedelta(days=days_ago)
        raw = daily_score(d, level_credit=True)
        weight = math.exp(-DECAY_LAMBDA * days_ago)
        weighted = raw * weight
        total += weighted
        components.append({
            "day": d.isoformat(), "days_ago": days_ago,
            "raw_level_xp": raw, "weight": round(weight, 6),
            "weighted_xp": round(weighted, 2),
        })
    return {"rating": int(round(total)), "components": components}


def _natural_level(rating: int) -> int:
    level = 1
    for tier in LEVELS:
        if rating >= tier["threshold"]:
            level = tier["level"]
    return level


def _tier(level: int) -> dict:
    level = max(1, min(len(LEVELS), int(level)))
    return LEVELS[level - 1]


def _load_level_state(rating, now_ts) -> tuple[dict, bool]:
    raw = db.game_state_get(LEVEL_STATE_KEY)
    if raw:
        try:
            state = json.loads(raw)
            return state, False
        except Exception:
            pass
    natural = _natural_level(rating)
    state = {
        "current_level": natural,
        "peak_level": natural,
        "at_risk_since": None,
        "updated_ts": now_ts,
    }
    db.game_state_set(LEVEL_STATE_KEY, json.dumps(state))
    return state, True


def _infer_at_risk_since(current_level, state_updated_ts, ref_day, now_ts):
    """Best-effort crossing time when the app was not calling the engine.

    Rolling decay changes materially at day boundaries. If WITNESS was closed
    for several days, scan those missing dates and find the first midnight at
    which the rating sat below the current level's demotion floor. This makes
    the 48h grace period continue while the app is closed instead of restarting
    every time it reopens.
    """
    floor = int(round(_tier(current_level)["threshold"] * DEMOTION_FLOOR_RATIO))
    try:
        last_dt = datetime.fromtimestamp(float(state_updated_ts))
        start = last_dt.date()
    except Exception:
        return now_ts
    ref_day = _as_date(ref_day)
    if start > ref_day:
        return now_ts
    # If the last known update was earlier today, we cannot safely claim the
    # score was below the floor since midnight; use now for same-day crossings.
    if start == ref_day:
        return now_ts
    d = start + timedelta(days=1)
    while d <= ref_day:
        if rolling_rating(d)["rating"] < floor:
            return _day_start_ts(d)
        d += timedelta(days=1)
    return now_ts


def level_status(reference_day=None, now_ts=None) -> dict:
    """Return and advance the rolling-level state machine.

    Promotion is immediate when rating crosses a tier threshold. Demotion uses
    hysteresis: rating must fall below 85% of the current tier's entry
    threshold for 48 continuous hours. One grace period can demote at most one
    tier, avoiding a single stale-app-open from cascading through many levels.
    """
    now_ts = time.time() if now_ts is None else float(now_ts)
    ref_day = _as_date(reference_day or datetime.fromtimestamp(now_ts).date())
    rating_info = rolling_rating(ref_day)
    rating = rating_info["rating"]
    state, was_new = _load_level_state(rating, now_ts)
    original_state = dict(state)
    current = max(1, min(len(LEVELS), _safe_int(state.get("current_level", 1), 1)))
    peak = max(current, min(len(LEVELS), _safe_int(state.get("peak_level", current), current)))
    at_risk_since = state.get("at_risk_since")
    try:
        at_risk_since = float(at_risk_since) if at_risk_since is not None else None
    except (TypeError, ValueError):
        at_risk_since = None

    promoted = False
    demoted = False
    natural = _natural_level(rating)
    if natural > current:
        current = natural
        peak = max(peak, current)
        at_risk_since = None
        promoted = True
    else:
        floor = int(round(_tier(current)["threshold"] * DEMOTION_FLOOR_RATIO))
        if current > 1 and rating < floor:
            if at_risk_since is None or now_ts < at_risk_since:
                at_risk_since = _infer_at_risk_since(
                    current, state.get("updated_ts", now_ts), ref_day, now_ts)
            if now_ts - at_risk_since >= AT_RISK_SECONDS:
                current -= 1
                demoted = True
                at_risk_since = None
        else:
            at_risk_since = None

    peak = max(peak, current)
    state_changed = (
        current != _safe_int(original_state.get("current_level", current), current) or
        peak != _safe_int(original_state.get("peak_level", peak), peak) or
        at_risk_since != original_state.get("at_risk_since")
    )
    try:
        last_saved_ts = float(original_state.get("updated_ts", 0) or 0)
    except (TypeError, ValueError):
        last_saved_ts = 0
    # Future UI may request dashboard_snapshot() every second. Persist level
    # state immediately on real transitions, otherwise only checkpoint every
    # five minutes to avoid pointless SQLite writes/disk churn.
    if was_new or state_changed or now_ts - last_saved_ts >= 300:
        state = {
            "current_level": current,
            "peak_level": peak,
            "at_risk_since": at_risk_since,
            "updated_ts": now_ts,
        }
        db.game_state_set(LEVEL_STATE_KEY, json.dumps(state))

    # Permanent transition history begins here. Older installs can reconstruct
    # prior threshold crossings from the immutable XP ledger; from this build
    # forward, real promotions/demotions/reclaims are also preserved explicitly.
    old_current = max(1, min(len(LEVELS),
                      _safe_int(original_state.get("current_level", current), current)))
    old_peak = max(old_current, min(len(LEVELS),
                   _safe_int(original_state.get("peak_level", old_current), old_current)))
    if not was_new and current != old_current:
        if current < old_current:
            event_type = "demotion"
        elif current <= old_peak:
            event_type = "reclaim"
        else:
            event_type = "promotion"
        source = "synthetic_demo" if db.game_state_get("demo_mode") == "1" else "state_machine"
        try:
            db.log_level_event(
                now_ts, ref_day.isoformat(), event_type, old_current, current, rating,
                source=source, metadata=json.dumps({"peak_level": peak}))
        except Exception:
            # Level state remains canonical even if the optional history row
            # cannot be written for some reason. Never block scoring/UI reads.
            pass

    tier = _tier(current)
    next_tier = _tier(current + 1) if current < len(LEVELS) else None
    floor = int(round(tier["threshold"] * DEMOTION_FLOOR_RATIO))
    at_risk = current > 1 and at_risk_since is not None and rating < floor
    remaining = None
    if at_risk:
        remaining = max(0, int(AT_RISK_SECONDS - (now_ts - at_risk_since)))
    return {
        "rating": rating,
        "rolling_days": ROLLING_DAYS,
        "decay_lambda": DECAY_LAMBDA,
        "current_level": current,
        "name": tier["name"],
        "entry_threshold": tier["threshold"],
        "demotion_floor": floor,
        "next_threshold": next_tier["threshold"] if next_tier else None,
        "xp_to_next": max(0, next_tier["threshold"] - rating) if next_tier else 0,
        "peak_level": peak,
        "at_risk": at_risk,
        "at_risk_seconds_remaining": remaining,
        "comeback_active": current < peak,
        "comeback_multiplier": COMEBACK_MULTIPLIER if current < peak else 1.0,
        "promoted_now": promoted and not was_new,
        "demoted_now": demoted,
        "components": rating_info["components"],
    }


# ── progression history / level charts ──────────────────────────────────

def rolling_rating_series(start_day=None, end_day=None) -> list[dict]:
    """Efficient day-by-day rolling Level Rating history.

    Uses one grouped ledger read, then applies the exact same 14-day
    exponential weighting as ``rolling_rating()`` in Python. This is intended
    for long-history charts, where issuing 14 SQLite queries per plotted day
    would become wasteful.
    """
    end = _as_date(end_day)
    level_rows = all_daily_level_scores()
    score_rows = dict(all_daily_scores())
    if level_rows:
        first = _as_date(level_rows[0][0])
    else:
        first = end
    start = _as_date(start_day) if start_day is not None else first
    if start > end:
        start = end
    level_map = {d: int(v) for d, v in level_rows}
    out = []
    d = start
    while d <= end:
        total = 0.0
        for days_ago in range(ROLLING_DAYS):
            dd = d - timedelta(days=days_ago)
            raw = level_map.get(dd.isoformat(), 0)
            total += raw * math.exp(-DECAY_LAMBDA * days_ago)
        rating = int(round(total))
        natural = _natural_level(rating)
        out.append({
            "day": d.isoformat(),
            "rating": rating,
            "natural_level": natural,
            "level_name": _tier(natural)["name"],
            "daily_score_xp": int(score_rows.get(d.isoformat(), 0)),
            "daily_level_xp": int(level_map.get(d.isoformat(), 0)),
        })
        d += timedelta(days=1)
    return out


def _reconstructed_level_milestones(series: list[dict]) -> list[dict]:
    """Threshold crossings recover milestone history predating level_events."""
    if not series:
        return []
    out = []
    previous = 0
    for row in series:
        rating = int(row.get("rating", 0))
        for tier in LEVELS[1:]:
            threshold = int(tier["threshold"])
            if previous < threshold <= rating:
                out.append({
                    "day": row["day"],
                    "event_type": "threshold_crossed",
                    "from_level": tier["level"] - 1,
                    "to_level": tier["level"],
                    "rating": rating,
                    "source": "reconstructed",
                    "name": tier["name"],
                })
        previous = rating
    return out


def progression_snapshot(end_day=None, now_ts=None) -> dict:
    """Chart-ready all-time + current-level progression contract.

    All-Time shows the complete rolling Level Rating story. Current-Level
    deliberately reframes the graph around the territory being defended now:
    the current tier's entry threshold is the baseline, the next tier is the
    ceiling, and the 85% demotion floor remains visible below as a danger zone.
    """
    now_ts = time.time() if now_ts is None else float(now_ts)
    end = _as_date(end_day or datetime.fromtimestamp(now_ts).date())
    series = rolling_rating_series(end_day=end)
    status = level_status(end, now_ts)
    current = int(status["current_level"])
    entry_threshold = int(status["entry_threshold"])

    permanent = []
    try:
        permanent = [dict(e) for e in db.level_events_all() if e.get("day", "") <= end.isoformat()]
    except Exception:
        permanent = []
    milestones = _reconstructed_level_milestones(series)

    # Prefer a real transition into the current tier when one exists. On older
    # data, fall back to the first immutable-ledger threshold crossing.
    entry_day = None
    entered_events = [e for e in permanent if int(e.get("to_level") or 0) == current]
    if entered_events:
        entry_day = entered_events[-1]["day"]
    if entry_day is None:
        for m in milestones:
            if int(m.get("to_level") or 0) == current:
                entry_day = m["day"]
                break
    if entry_day is None:
        entry_day = series[0]["day"] if series else end.isoformat()

    current_series = [row for row in series if row["day"] >= entry_day]
    if not current_series and series:
        current_series = [series[-1]]

    peak_row = max(series, key=lambda x: (int(x["rating"]), x["day"])) if series else {
        "day": end.isoformat(), "rating": 0}
    next_threshold = status.get("next_threshold")
    if next_threshold is not None and int(next_threshold) > entry_threshold:
        pct = (int(status["rating"]) - entry_threshold) / (int(next_threshold) - entry_threshold)
        level_progress = max(0.0, min(1.0, pct))
    else:
        level_progress = 1.0

    # Milestones for display: reconstructed historical promotions plus explicit
    # later demotion/reclaim/promotion events, de-duplicated by day/to/type.
    merged = list(milestones)
    seen = {(m.get("day"), m.get("to_level"), m.get("event_type")) for m in merged}
    for e in permanent:
        # A real persisted transition is richer than a reconstructed threshold
        # crossing for the same tier/day; show one milestone, not two dots/rows.
        merged = [m for m in merged if not (
            m.get("event_type") == "threshold_crossed" and
            m.get("day") == e.get("day") and
            int(m.get("to_level") or 0) == int(e.get("to_level") or 0))]
        key = (e.get("day"), e.get("to_level"), e.get("event_type"))
        if key in seen:
            continue
        row = dict(e)
        to_level = int(row.get("to_level") or current)
        row["name"] = _tier(to_level)["name"]
        merged.append(row); seen.add(key)
    merged.sort(key=lambda x: (x.get("day", ""), float(x.get("ts", 0) or 0)))

    return {
        "generated_ts": now_ts,
        "end_day": end.isoformat(),
        "levels": [dict(x) for x in LEVELS],
        "status": status,
        "all_time": {
            "series": series,
            "peak_rating": int(peak_row.get("rating", 0)),
            "peak_day": peak_row.get("day", end.isoformat()),
            "milestones": merged,
        },
        "current_level": {
            "level": current,
            "name": status["name"],
            "entry_day": entry_day,
            "entry_threshold": entry_threshold,
            "demotion_floor": int(status["demotion_floor"]),
            "next_threshold": int(next_threshold) if next_threshold is not None else None,
            "rating": int(status["rating"]),
            "progress": level_progress,
            "series": current_series,
        },
    }


# ── calendar/history / one-call UI contract ─────────────────────────────

def calendar_month_summary(year, month) -> dict:
    year, month = int(year), int(month)
    record_days = historical_record_days()
    record_weeks = historical_record_weeks()
    days = []
    for d, score in all_daily_scores():
        dd = _as_date(d)
        if dd.year != year or dd.month != month:
            continue
        ws = _week_start(dd).isoformat()
        days.append({
            "day": d, "day_number": dd.day, "score_xp": score,
            "is_record_day": d in record_days,
            "is_record_week": ws in record_weeks,
        })
    return {"year": year, "month": month, "days": days}


def day_summary(day) -> dict:
    d = _as_date(day)
    score = daily_score(d)
    ghost_final = daily_score(d - timedelta(days=7))
    return {
        "day": d.isoformat(),
        "score_xp": score,
        "ghost_day": (d - timedelta(days=7)).isoformat(),
        "ghost_final_xp": ghost_final,
        "gap_final": score - ghost_final,
        "activity_breakdown": activity_breakdown(d),
        "timeline": daily_timeline(d),
        "was_record_day": d.isoformat() in historical_record_days(),
        "week_start": _week_start(d).isoformat(),
        "was_record_week": _week_start(d).isoformat() in historical_record_weeks(),
    }


def performance_series(days=30, end_day=None) -> list[dict]:
    """Daily battle-score series for charts; missing days remain honest zeros."""
    end = _as_date(end_day)
    count = max(1, int(days))
    start = end - timedelta(days=count - 1)
    out = []
    d = start
    while d <= end:
        score = daily_score(d)
        ghost = daily_score(d - timedelta(days=7))
        out.append({
            "day": d.isoformat(), "weekday": d.strftime("%a"),
            "score_xp": score, "ghost_xp": ghost, "gap": score - ghost,
        })
        d += timedelta(days=1)
    return out


def week_summary(week_start=None) -> dict:
    """Completed/full-week matchup used by the Sunday closure screen.

    With no argument, returns the most recently completed Monday-Sunday week
    against the week immediately before it.
    """
    if week_start is None:
        ws = _week_start(date.today()) - timedelta(days=7)
    else:
        ws = _week_start(week_start)
    ghost_ws = ws - timedelta(days=7)
    players = []
    you = ghost = 0
    for offset in range(7):
        d = ws + timedelta(days=offset)
        gd = ghost_ws + timedelta(days=offset)
        ys = daily_score(d)
        gs = daily_score(gd)
        you += ys
        ghost += gs
        players.append({
            "day": d.isoformat(), "ghost_day": gd.isoformat(),
            "weekday": d.strftime("%A"), "you": ys, "ghost": gs,
            "gap": ys - gs,
            "status": "ahead" if ys > gs else ("behind" if ys < gs else "tied"),
        })

    prior_week_scores = {k: v for k, v in _weekly_score_map().items() if k < ws.isoformat()}
    record_before = max(prior_week_scores.values(), default=0)
    return {
        "week_start": ws.isoformat(),
        "week_end": (ws + timedelta(days=6)).isoformat(),
        "ghost_week_start": ghost_ws.isoformat(),
        "you": you, "ghost": ghost, "gap": you - ghost,
        "status": "won" if you > ghost else ("lost" if you < ghost else "tied"),
        "players": players,
        "record_before": record_before,
        "record_broken": you > record_before and you > 0,
    }


def hall_of_fame() -> dict:
    """All-time record locations for the History/Records delivery layer."""
    scores = all_daily_scores()
    best_day = None
    if scores:
        d, score = max(scores, key=lambda x: (x[1], x[0]))
        if score > 0:
            best_day = {"day": d, "score_xp": int(score)}

    weekday_records = []
    for wd in range(7):
        candidates = [(d, s) for d, s in scores if _as_date(d).weekday() == wd]
        if candidates:
            d, score = max(candidates, key=lambda x: (x[1], x[0]))
            if score > 0:
                weekday_records.append({
                    "weekday": _as_date(d).strftime("%A"),
                    "day": d, "score_xp": int(score),
                })

    weeks = _weekly_score_map()
    best_week = None
    if weeks:
        ws, score = max(weeks.items(), key=lambda x: (x[1], x[0]))
        if score > 0:
            best_week = {"week_start": ws, "score_xp": int(score)}

    activity_records = records_snapshot(date.today()).get("activity_records", [])
    return {
        "best_day": best_day,
        "best_week": best_week,
        "weekday_records": weekday_records,
        "activity_records": activity_records,
        "record_days": sorted(historical_record_days()),
        "record_weeks": sorted(historical_record_weeks()),
    }


def dashboard_snapshot(now_ts=None) -> dict:
    """Single clean contract the future polished dashboard can consume."""
    now_ts = time.time() if now_ts is None else float(now_ts)
    today = datetime.fromtimestamp(now_ts).date()
    return {
        "generated_ts": now_ts,
        "day": today.isoformat(),
        "daily_battle": daily_battle(today, now_ts),
        "weekly_campaign": weekly_campaign(today, now_ts),
        "records": records_snapshot(today),
        "streaks": {
            "daily": daily_win_streak(today, now_ts),
            "weekly_completed": weekly_win_streak(today),
        },
        "level": level_status(today, now_ts),
        "activities": activities_snapshot(today),
        "hall_of_fame": hall_of_fame(),
        "last_completed_week": week_summary(),
    }
