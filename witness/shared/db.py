"""SQLite storage. v1-compatible; adds sos + daily_scores tables."""
import sqlite3
import threading
import time
from datetime import datetime, date, timedelta

import config

_lock = threading.Lock()
_conn = None


def init():
    global _conn
    _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    with _lock:
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS activity (
                ts REAL, day TEXT, process TEXT, title TEXT, flagged INTEGER
            );
            CREATE TABLE IF NOT EXISTS presence (ts REAL, day TEXT, event TEXT);
            CREATE TABLE IF NOT EXISTS checkins (
                ts REAL, day TEXT, kind TEXT, question TEXT, answer TEXT
            );
            CREATE TABLE IF NOT EXISTS redlines (ts REAL, day TEXT, title TEXT);
            CREATE TABLE IF NOT EXISTS sos (
                ts REAL, day TEXT, trigger TEXT, outcome TEXT
            );
            CREATE TABLE IF NOT EXISTS daily_scores (
                day TEXT PRIMARY KEY, score INTEGER
            );
            CREATE TABLE IF NOT EXISTS patterns (
                day TEXT, block_label TEXT, app TEXT, seconds INTEGER,
                UNIQUE(day, block_label, app)
            );
            CREATE TABLE IF NOT EXISTS learned_profiles (
                block_label TEXT, app TEXT, avg_pct REAL, sample_days INTEGER,
                UNIQUE(block_label, app)
            );
            CREATE TABLE IF NOT EXISTS notes (
                ts REAL, day TEXT, text TEXT
            );
            CREATE TABLE IF NOT EXISTS input_activity (
                ts REAL, day TEXT, active INTEGER
            );
            CREATE TABLE IF NOT EXISTS revenue_events (
                ts REAL, day TEXT, amount REAL, note_text TEXT
            );

            -- Canonical V1 game/scoring backend. These are additive and do
            -- not replace the raw activity/presence tables above.
            CREATE TABLE IF NOT EXISTS scoring_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                xp_value INTEGER NOT NULL DEFAULT 10,
                kind TEXT NOT NULL DEFAULT 'repeatable',
                active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_ts REAL NOT NULL,
                updated_ts REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS xp_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                day TEXT NOT NULL,
                activity_id INTEGER,
                activity_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                base_xp INTEGER NOT NULL DEFAULT 0,
                score_xp INTEGER NOT NULL DEFAULT 0,
                level_xp INTEGER NOT NULL DEFAULT 0,
                level_multiplier REAL NOT NULL DEFAULT 1.0,
                reverses_event_id INTEGER,
                source TEXT NOT NULL DEFAULT 'manual',
                metadata TEXT
            );
            CREATE TABLE IF NOT EXISTS game_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS level_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                day TEXT NOT NULL,
                event_type TEXT NOT NULL,
                from_level INTEGER,
                to_level INTEGER,
                rating INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'state_machine',
                metadata TEXT
            );
            CREATE TABLE IF NOT EXISTS demo_daily_features (
                day TEXT PRIMARY KEY,
                first_scored_hour REAL,
                arrival_hour REAL,
                tracked_minutes REAL,
                flagged_pct REAL,
                engagement_pct REAL,
                sales_minutes REAL,
                focus_minutes REAL,
                comms_minutes REAL,
                break_minutes REAL,
                revenue REAL
            );
            CREATE INDEX IF NOT EXISTS idx_xp_events_day_ts
                ON xp_events(day, ts);
            CREATE INDEX IF NOT EXISTS idx_xp_events_activity_day
                ON xp_events(activity_id, day);
            CREATE INDEX IF NOT EXISTS idx_xp_events_reverses
                ON xp_events(reverses_event_id);
            CREATE INDEX IF NOT EXISTS idx_level_events_day_ts
                ON level_events(day, ts);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_level_events_transition_dedupe
                ON level_events(day, event_type, from_level, to_level, source);
            """
        )
        # Additive migration -- safe to run every startup. SQLite has
        # no "ADD COLUMN IF NOT EXISTS", so these just fail silently
        # if already applied (existing installs upgrading from before
        # Stripe sync existed will pick this up automatically).
        for stmt in (
            "ALTER TABLE revenue_events ADD COLUMN source TEXT",
            "ALTER TABLE revenue_events ADD COLUMN external_id TEXT",
        ):
            try:
                _conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        _conn.commit()


def _now():
    return time.time(), date.today().isoformat()


def log_activity(process, title, flagged):
    ts, day = _now()
    with _lock:
        _conn.execute("INSERT INTO activity VALUES (?,?,?,?,?)",
                      (ts, day, process, title, int(flagged)))
        _conn.commit()


def log_presence(event):
    ts, day = _now()
    with _lock:
        _conn.execute("INSERT INTO presence VALUES (?,?,?)", (ts, day, event))
        _conn.commit()


def log_checkin(kind, question, answer):
    ts, day = _now()
    with _lock:
        _conn.execute("INSERT INTO checkins VALUES (?,?,?,?,?)",
                      (ts, day, kind, question, answer))
        _conn.commit()


def log_redline(title):
    ts, day = _now()
    with _lock:
        _conn.execute("INSERT INTO redlines VALUES (?,?,?)", (ts, day, title))
        _conn.commit()


def log_sos(trigger, outcome):
    ts, day = _now()
    with _lock:
        _conn.execute("INSERT INTO sos VALUES (?,?,?,?)",
                      (ts, day, trigger, outcome))
        _conn.commit()


def log_note(text):
    """One-way note for today. Kept as the convenience API used by older
    callers; the Calendar uses log_note_for_day() so any selected day can
    hold notes beside its videos and activity history."""
    return log_note_for_day(date.today().isoformat(), text)


def log_note_for_day(day, text):
    """Store a note on an explicit YYYY-MM-DD calendar day.

    The timestamp is anchored to that selected date while keeping the current
    local clock time, so notes added retrospectively still sort/display like
    notes belonging to that day rather than today's date.
    """
    text = str(text).strip()
    if not text:
        return False
    try:
        selected = datetime.strptime(day, "%Y-%m-%d")
        now = datetime.now()
        ts = selected.replace(hour=now.hour, minute=now.minute,
                              second=now.second, microsecond=now.microsecond).timestamp()
    except Exception:
        ts = time.time()
    with _lock:
        _conn.execute("INSERT INTO notes VALUES (?,?,?)", (ts, day, text))
        _conn.commit()
    return True


def notes_for_day(day):
    """Returns [(ts, text), ...] for the given day, oldest first."""
    with _lock:
        return _conn.execute(
            "SELECT ts, text FROM notes WHERE day=? ORDER BY ts",
            (day,)).fetchall()


def days_with_notes_in_month(year, month):
    """Return day numbers that contain at least one note in a month."""
    prefix = f"{int(year):04d}-{int(month):02d}-"
    with _lock:
        rows = _conn.execute(
            "SELECT DISTINCT day FROM notes WHERE day LIKE ?",
            (prefix + "%",)).fetchall()
    out = set()
    for (day_str,) in rows:
        try:
            out.add(int(str(day_str)[8:10]))
        except (TypeError, ValueError):
            pass
    return out


def log_input(active):
    """Keyboard/mouse activity, logged every ~2s by core/inputmon.py.
    Independent of which window is focused -- catches real hands-on-
    keyboard activity vs. just having a work app open."""
    ts, day = _now()
    with _lock:
        _conn.execute("INSERT INTO input_activity VALUES (?,?,?)",
                      (ts, day, int(bool(active))))
        _conn.commit()


def replace_revenue_events_for_day(day, events):
    """events: list of (amount, note_text). Deletes existing NOTE-
    sourced revenue_events for this day first (never touches
    Stripe-synced rows, even if both exist for the same day), so
    re-running the daily distiller never double-counts note-based
    entries against themselves."""
    ts, _ = _now()
    with _lock:
        _conn.execute(
            "DELETE FROM revenue_events WHERE day=? "
            "AND (source='note' OR source IS NULL)", (day,))
        for amount, note_text in events:
            _conn.execute(
                "INSERT INTO revenue_events (ts, day, amount, note_text, source) "
                "VALUES (?,?,?,?,?)",
                (ts, day, float(amount), note_text, "note"))
        _conn.commit()


def sync_stripe_event(ts, day, amount, description, external_id) -> bool:
    """Logs one Stripe charge as a revenue event. Idempotent --
    returns False without inserting if this external_id (Stripe's
    charge ID) has already been synced, True if it inserted a new
    row. Safe to call repeatedly with the same charges."""
    with _lock:
        existing = _conn.execute(
            "SELECT 1 FROM revenue_events WHERE external_id=?",
            (external_id,)).fetchone()
        if existing:
            return False
        _conn.execute(
            "INSERT INTO revenue_events "
            "(ts, day, amount, note_text, source, external_id) "
            "VALUES (?,?,?,?,?,?)",
            (ts, day, float(amount), description, "stripe", external_id))
        _conn.commit()
        return True


def revenue_events_since(days):
    """All revenue events in the trailing `days` days, oldest first."""
    cutoff = time.time() - days * 86400
    with _lock:
        return _conn.execute(
            "SELECT ts, day, amount, note_text FROM revenue_events "
            "WHERE ts >= ? ORDER BY ts", (cutoff,)).fetchall()


def revenue_events_all():
    with _lock:
        return _conn.execute(
            "SELECT ts, day, amount, note_text FROM revenue_events "
            "ORDER BY ts").fetchall()


def save_score(day, score):
    with _lock:
        _conn.execute(
            "INSERT INTO daily_scores VALUES (?,?) "
            "ON CONFLICT(day) DO UPDATE SET score=excluded.score",
            (day, int(score)))
        _conn.commit()


def today_raw():
    """Raw counts used for live focus score."""
    day = date.today().isoformat()
    with _lock:
        total, flagged = _conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(flagged),0) FROM activity WHERE day=?",
            (day,)).fetchone()
        redl = _conn.execute(
            "SELECT COUNT(*) FROM redlines WHERE day=?", (day,)).fetchone()[0]
    return {"samples": total, "flagged": flagged, "redlines": redl}


def recent_scores(days=14):
    since = (date.today() - timedelta(days=days)).isoformat()
    with _lock:
        rows = _conn.execute(
            "SELECT day, score FROM daily_scores WHERE day>=? ORDER BY day",
            (since,)).fetchall()
    return rows


def today_summary():
    day = date.today().isoformat()
    with _lock:
        acts = _conn.execute(
            "SELECT ts, process, title, flagged FROM activity WHERE day=? "
            "ORDER BY ts", (day,)).fetchall()
        checks = _conn.execute(
            "SELECT ts, kind, question, answer FROM checkins WHERE day=? "
            "ORDER BY ts", (day,)).fetchall()
        soss = _conn.execute(
            "SELECT ts, trigger, outcome FROM sos WHERE day=?", (day,)).fetchall()
        redl = _conn.execute(
            "SELECT COUNT(*) FROM redlines WHERE day=?", (day,)).fetchone()[0]

    per_app, flagged_sec = {}, 0
    for _, proc, _, fl in acts:
        per_app[proc] = per_app.get(proc, 0) + config.WINDOW_POLL_SEC
        if fl:
            flagged_sec += config.WINDOW_POLL_SEC

    fmt = lambda ts: datetime.fromtimestamp(ts).strftime("%H:%M")
    return {
        "day": day,
        "minutes_tracked": int(sum(per_app.values()) / 60),
        "minutes_flagged": int(flagged_sec / 60),
        "redline_events": redl,
        "sos_events": [{"time": fmt(t), "trigger": tr, "outcome": o}
                       for t, tr, o in soss],
        "per_app_minutes": {k: int(v / 60) for k, v in
                            sorted(per_app.items(), key=lambda x: -x[1])
                            if v >= 60},
        "checkins": [{"time": fmt(t), "kind": k, "question": q, "answer": a}
                     for t, k, q, a in checks],
        "sample_titles": list({t for _, _, t, _ in acts if t})[:30],
    }


def log_pattern_block(block_label, app_seconds: dict):
    """Store app usage for a schedule block. app_seconds: {app: total_sec}"""
    day = date.today().isoformat()
    with _lock:
        for app, secs in app_seconds.items():
            _conn.execute(
                "INSERT INTO patterns VALUES (?,?,?,?) "
                "ON CONFLICT(day, block_label, app) DO UPDATE SET "
                "seconds=seconds+excluded.seconds",
                (day, block_label, app, int(secs)))
        _conn.commit()


def get_recent_activity(seconds_back=300):
    """Get app usage from the last N seconds of activity log."""
    cutoff = time.time() - seconds_back
    day = date.today().isoformat()
    with _lock:
        rows = _conn.execute(
            "SELECT process, COUNT(*) FROM activity "
            "WHERE day=? AND ts>=? GROUP BY process ORDER BY COUNT(*) DESC",
            (day, cutoff)).fetchall()
    total = sum(c for _, c in rows)
    if total == 0:
        return {}
    return {proc: round(count / total * 100) for proc, count in rows}


def rebuild_profiles():
    """Rebuild learned profiles from all pattern history."""
    with _lock:
        # get total seconds per block per app per day
        rows = _conn.execute(
            "SELECT block_label, app, day, seconds FROM patterns"
        ).fetchall()
    if not rows:
        return

    # aggregate: per block+app, average percentage across days
    from collections import defaultdict
    block_totals = defaultdict(lambda: defaultdict(list))
    day_totals = defaultdict(lambda: defaultdict(float))

    for block, app, day, secs in rows:
        block_totals[(block, day)][app] += secs
        day_totals[block][day] += secs

    profiles = defaultdict(lambda: {"total_pct": [], "days": set()})
    for (block, day), apps in block_totals.items():
        total = sum(apps.values())
        if total < 30:
            continue
        for app, secs in apps.items():
            pct = (secs / total) * 100
            profiles[(block, app)]["total_pct"].append(pct)
            profiles[(block, app)]["days"].add(day)

    with _lock:
        _conn.execute("DELETE FROM learned_profiles")
        for (block, app), info in profiles.items():
            avg = sum(info["total_pct"]) / len(info["total_pct"])
            _conn.execute(
                "INSERT INTO learned_profiles VALUES (?,?,?,?)",
                (block, app, round(avg, 1), len(info["days"])))
        _conn.commit()


def get_profile(block_label):
    """Get learned app profile for a schedule block.
    Returns {app: avg_pct} and sample_days count."""
    with _lock:
        rows = _conn.execute(
            "SELECT app, avg_pct, sample_days FROM learned_profiles "
            "WHERE block_label=? ORDER BY avg_pct DESC",
            (block_label,)).fetchall()
    if not rows:
        return {}, 0
    profile = {app: pct for app, pct, _ in rows}
    days = max(d for _, _, d in rows)
    return profile, days



# ── V1 game/scoring backend storage ─────────────────────────────────────

def save_scoring_activity(name, xp_value, kind="repeatable", active=True,
                          sort_order=0, activity_id=None):
    """Create or update a manual scoring activity. Returns its integer id.

    Kinds are validated by shared/game_engine.py; this layer deliberately
    stays storage-focused and accepts the normalized value it is given.
    """
    now = time.time()
    name = str(name).strip()
    if not name:
        raise ValueError("Activity name cannot be blank")
    with _lock:
        if activity_id is None:
            cur = _conn.execute(
                "INSERT INTO scoring_activities "
                "(name,xp_value,kind,active,sort_order,created_ts,updated_ts) "
                "VALUES (?,?,?,?,?,?,?)",
                (name, int(xp_value), str(kind), int(bool(active)),
                 int(sort_order), now, now))
            activity_id = cur.lastrowid
        else:
            _conn.execute(
                "UPDATE scoring_activities SET name=?, xp_value=?, kind=?, "
                "active=?, sort_order=?, updated_ts=? WHERE id=?",
                (name, int(xp_value), str(kind), int(bool(active)),
                 int(sort_order), now, int(activity_id)))
        _conn.commit()
    return int(activity_id)


def get_scoring_activity(activity_id):
    with _lock:
        row = _conn.execute(
            "SELECT id,name,xp_value,kind,active,sort_order,created_ts,updated_ts "
            "FROM scoring_activities WHERE id=?", (int(activity_id),)).fetchone()
    if not row:
        return None
    keys = ("id", "name", "xp_value", "kind", "active", "sort_order",
            "created_ts", "updated_ts")
    out = dict(zip(keys, row))
    out["active"] = bool(out["active"])
    return out


def list_scoring_activities(active_only=True):
    sql = ("SELECT id,name,xp_value,kind,active,sort_order,created_ts,updated_ts "
           "FROM scoring_activities")
    params = ()
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY sort_order, id"
    with _lock:
        rows = _conn.execute(sql, params).fetchall()
    keys = ("id", "name", "xp_value", "kind", "active", "sort_order",
            "created_ts", "updated_ts")
    out = []
    for row in rows:
        d = dict(zip(keys, row))
        d["active"] = bool(d["active"])
        out.append(d)
    return out


def deactivate_scoring_activity(activity_id):
    with _lock:
        _conn.execute(
            "UPDATE scoring_activities SET active=0, updated_ts=? WHERE id=?",
            (time.time(), int(activity_id)))
        _conn.commit()


def log_xp_event(ts, day, activity_id, activity_name, event_type,
                 quantity, base_xp, score_xp, level_xp,
                 level_multiplier=1.0, reverses_event_id=None,
                 source="manual", metadata=None):
    """Append one immutable scoring-ledger event and return its id."""
    with _lock:
        cur = _conn.execute(
            "INSERT INTO xp_events "
            "(ts,day,activity_id,activity_name,event_type,quantity,base_xp,"
            "score_xp,level_xp,level_multiplier,reverses_event_id,source,metadata) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (float(ts), str(day), activity_id, str(activity_name),
             str(event_type), float(quantity), int(base_xp), int(score_xp),
             int(level_xp), float(level_multiplier), reverses_event_id,
             str(source), metadata))
        _conn.commit()
        return int(cur.lastrowid)


def get_xp_event(event_id):
    with _lock:
        row = _conn.execute(
            "SELECT id,ts,day,activity_id,activity_name,event_type,quantity,"
            "base_xp,score_xp,level_xp,level_multiplier,reverses_event_id,"
            "source,metadata FROM xp_events WHERE id=?",
            (int(event_id),)).fetchone()
    if not row:
        return None
    keys = ("id", "ts", "day", "activity_id", "activity_name",
            "event_type", "quantity", "base_xp", "score_xp", "level_xp",
            "level_multiplier", "reverses_event_id", "source", "metadata")
    return dict(zip(keys, row))


def xp_events_between(start_ts, end_ts, activity_id=None):
    sql = ("SELECT id,ts,day,activity_id,activity_name,event_type,quantity,"
           "base_xp,score_xp,level_xp,level_multiplier,reverses_event_id,"
           "source,metadata FROM xp_events WHERE ts>=? AND ts<=?")
    params = [float(start_ts), float(end_ts)]
    if activity_id is not None:
        sql += " AND activity_id=?"
        params.append(int(activity_id))
    sql += " ORDER BY ts,id"
    with _lock:
        rows = _conn.execute(sql, tuple(params)).fetchall()
    keys = ("id", "ts", "day", "activity_id", "activity_name",
            "event_type", "quantity", "base_xp", "score_xp", "level_xp",
            "level_multiplier", "reverses_event_id", "source", "metadata")
    return [dict(zip(keys, row)) for row in rows]


def xp_events_for_day(day, up_to_ts=None, activity_id=None):
    sql = ("SELECT id,ts,day,activity_id,activity_name,event_type,quantity,"
           "base_xp,score_xp,level_xp,level_multiplier,reverses_event_id,"
           "source,metadata FROM xp_events WHERE day=?")
    params = [str(day)]
    if up_to_ts is not None:
        sql += " AND ts<=?"
        params.append(float(up_to_ts))
    if activity_id is not None:
        sql += " AND activity_id=?"
        params.append(int(activity_id))
    sql += " ORDER BY ts,id"
    with _lock:
        rows = _conn.execute(sql, tuple(params)).fetchall()
    keys = ("id", "ts", "day", "activity_id", "activity_name",
            "event_type", "quantity", "base_xp", "score_xp", "level_xp",
            "level_multiplier", "reverses_event_id", "source", "metadata")
    return [dict(zip(keys, row)) for row in rows]


def latest_unreversed_activity_event(activity_id, day):
    """Newest positive activity event on a day that has not been reversed."""
    with _lock:
        row = _conn.execute(
            "SELECT e.id,e.ts,e.day,e.activity_id,e.activity_name,e.event_type,"
            "e.quantity,e.base_xp,e.score_xp,e.level_xp,e.level_multiplier,"
            "e.reverses_event_id,e.source,e.metadata "
            "FROM xp_events e WHERE e.activity_id=? AND e.day=? "
            "AND e.event_type='activity' AND e.score_xp>0 "
            "AND NOT EXISTS (SELECT 1 FROM xp_events r "
            "WHERE r.reverses_event_id=e.id AND r.event_type='reversal') "
            "ORDER BY e.ts DESC,e.id DESC LIMIT 1",
            (int(activity_id), str(day))).fetchone()
    if not row:
        return None
    keys = ("id", "ts", "day", "activity_id", "activity_name",
            "event_type", "quantity", "base_xp", "score_xp", "level_xp",
            "level_multiplier", "reverses_event_id", "source", "metadata")
    return dict(zip(keys, row))


def event_has_reversal(event_id):
    with _lock:
        row = _conn.execute(
            "SELECT 1 FROM xp_events WHERE reverses_event_id=? "
            "AND event_type='reversal' LIMIT 1", (int(event_id),)).fetchone()
    return bool(row)


def game_state_get(key, default=None):
    with _lock:
        row = _conn.execute("SELECT value FROM game_state WHERE key=?",
                            (str(key),)).fetchone()
    return row[0] if row else default


def game_state_set(key, value):
    with _lock:
        _conn.execute(
            "INSERT INTO game_state(key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(key), str(value)))
        _conn.commit()


def game_state_delete(key):
    with _lock:
        _conn.execute("DELETE FROM game_state WHERE key=?", (str(key),))
        _conn.commit()


def log_level_event(ts, day, event_type, from_level, to_level, rating,
                    source="state_machine", metadata=None):
    """Append one permanent level transition/milestone event."""
    with _lock:
        cur = _conn.execute(
            "INSERT OR IGNORE INTO level_events "
            "(ts,day,event_type,from_level,to_level,rating,source,metadata) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (float(ts), str(day), str(event_type),
             None if from_level is None else int(from_level),
             None if to_level is None else int(to_level),
             int(rating), str(source), metadata))
        _conn.commit()
        return int(cur.lastrowid)


def level_events_all():
    with _lock:
        rows = _conn.execute(
            "SELECT id,ts,day,event_type,from_level,to_level,rating,source,metadata "
            "FROM level_events ORDER BY ts,id").fetchall()
    keys = ("id", "ts", "day", "event_type", "from_level", "to_level",
            "rating", "source", "metadata")
    return [dict(zip(keys, row)) for row in rows]


def delete_level_events_by_source(source):
    """Demo cleanup helper; real level history is otherwise append-only."""
    with _lock:
        cur = _conn.execute("DELETE FROM level_events WHERE source=?", (str(source),))
        _conn.commit()
        return int(cur.rowcount or 0)


def close():
    """Close the SQLite connection. Mostly useful for isolated tests/tools."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def query(sql, params=()):
    """Generic read-only query helper. Used by insight/raw_stats.py to
    read the raw log tables without adding new table-specific functions
    here every time the insight pipeline needs a new number."""
    with _lock:
        return _conn.execute(sql, params).fetchall()


# ── Synthetic/demo support (isolated from real telemetry) ───────────────

def save_demo_daily_feature(day, feature):
    """Store one synthetic analytics feature row.

    Demo telemetry deliberately lives in its own table instead of being
    inserted into the real activity/presence/input tables, so demo mode can
    be erased cleanly without risking real history.
    """
    keys = ("first_scored_hour", "arrival_hour", "tracked_minutes",
            "flagged_pct", "engagement_pct", "sales_minutes",
            "focus_minutes", "comms_minutes", "break_minutes", "revenue")
    vals = [feature.get(k) for k in keys]
    with _lock:
        _conn.execute(
            "INSERT INTO demo_daily_features "
            "(day,first_scored_hour,arrival_hour,tracked_minutes,flagged_pct,"
            "engagement_pct,sales_minutes,focus_minutes,comms_minutes,"
            "break_minutes,revenue) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET "
            "first_scored_hour=excluded.first_scored_hour,"
            "arrival_hour=excluded.arrival_hour,"
            "tracked_minutes=excluded.tracked_minutes,"
            "flagged_pct=excluded.flagged_pct,"
            "engagement_pct=excluded.engagement_pct,"
            "sales_minutes=excluded.sales_minutes,"
            "focus_minutes=excluded.focus_minutes,"
            "comms_minutes=excluded.comms_minutes,"
            "break_minutes=excluded.break_minutes,revenue=excluded.revenue",
            (str(day), *vals))
        _conn.commit()


def demo_daily_feature(day):
    with _lock:
        row = _conn.execute(
            "SELECT first_scored_hour,arrival_hour,tracked_minutes,flagged_pct,"
            "engagement_pct,sales_minutes,focus_minutes,comms_minutes,"
            "break_minutes,revenue FROM demo_daily_features WHERE day=?",
            (str(day),)).fetchone()
    if not row:
        return None
    keys = ("first_scored_hour", "arrival_hour", "tracked_minutes",
            "flagged_pct", "engagement_pct", "sales_minutes",
            "focus_minutes", "comms_minutes", "break_minutes", "revenue")
    return dict(zip(keys, row))


def clear_demo_daily_features():
    with _lock:
        _conn.execute("DELETE FROM demo_daily_features")
        _conn.commit()


def delete_xp_events_by_source(source):
    """Delete only explicitly synthetic/non-user ledger rows by source.

    This is intentionally not used for ordinary undo/history editing. Real
    scoring history remains append-only; the function exists solely so the
    optional demo fixture can be removed as a unit.
    """
    with _lock:
        cur = _conn.execute("DELETE FROM xp_events WHERE source=?", (str(source),))
        _conn.commit()
        return int(cur.rowcount or 0)
