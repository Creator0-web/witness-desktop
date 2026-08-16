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
            """
        )
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
