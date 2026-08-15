"""Trail learning. Tracks the sequence of apps/sites visited before
every red-line event. After 3+ events, builds a "drift trail" pattern
and intervenes when it detects the early stages — BEFORE the explicit
content appears.

Example learned trail:
  chrome(work) → reddit → instagram → searching → explicit
After learning, it intervenes at the reddit→instagram stage:
  "I've seen this pattern before. You know where this goes."
"""
import json
import os
import time
import threading
from datetime import date, datetime
from collections import Counter

import config
import db

TRAIL_FILE = "trail_history.json"
TRAIL_WINDOW = 600  # look back 10 minutes before each incident
MIN_INCIDENTS = 3   # need this many events before pattern is reliable


def _load_trails():
    try:
        with open(TRAIL_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"incidents": [], "pattern": []}


def _save_trails(data):
    try:
        with open(TRAIL_FILE, "w") as f:
            json.dump(data, f, indent=1)
    except Exception:
        pass


def record_incident():
    """Called when a red-line event occurs. Records the trail of apps/sites
    visited in the 10 minutes before this moment."""
    cutoff = time.time() - TRAIL_WINDOW
    day = date.today().isoformat()

    try:
        rows = db._conn.execute(
            "SELECT process, title FROM activity "
            "WHERE day=? AND ts>=? ORDER BY ts",
            (day, cutoff)).fetchall()
    except Exception:
        return

    # build simplified trail: unique apps/title-keywords in order
    trail = []
    seen = set()
    for proc, title in rows:
        # simplify: just app name + domain-like keywords from title
        key = proc.lower().replace(".exe", "")
        title_words = title.lower().split()
        # extract domain-like words
        for w in title_words:
            if "." in w or any(site in w for site in
                              ["reddit", "instagram", "youtube", "twitter",
                               "tiktok", "facebook", "tumblr", "discord"]):
                key = w.split("/")[0].split("?")[0]
                break

        if key not in seen:
            seen.add(key)
            trail.append(key)

    data = _load_trails()
    data["incidents"].append({
        "date": datetime.now().isoformat(),
        "trail": trail[-15:]  # last 15 unique steps
    })

    # keep last 20 incidents
    data["incidents"] = data["incidents"][-20:]

    # rebuild pattern from all incidents
    if len(data["incidents"]) >= MIN_INCIDENTS:
        data["pattern"] = _find_common_trail(data["incidents"])

    _save_trails(data)


def _find_common_trail(incidents):
    """Find apps/sites that commonly appear before red-line events."""
    # count how often each app appears in trails
    app_freq = Counter()
    for inc in incidents:
        for app in inc["trail"]:
            app_freq[app] += 1

    total = len(incidents)
    # apps appearing in 50%+ of trails are part of the pattern
    pattern = [app for app, count in app_freq.most_common(20)
               if count >= total * 0.5
               and app not in ("unknown", "explorer", "witness",
                               "pythonw", "cmd", "powershell")]
    return pattern[:10]


def check_trail(recent_apps):
    """Check if current app activity matches the learned drift trail.
    recent_apps: list of recent app/title strings.
    Returns (is_drifting: bool, confidence: float, message: str)
    """
    data = _load_trails()
    pattern = data.get("pattern", [])

    if len(pattern) < 2 or len(data.get("incidents", [])) < MIN_INCIDENTS:
        return False, 0, ""

    # how many pattern apps appear in recent activity?
    recent_set = set(a.lower().replace(".exe", "") for a in recent_apps)
    matches = [p for p in pattern if p in recent_set]
    confidence = len(matches) / len(pattern)

    if confidence >= 0.4:  # 40%+ of the trail is present
        trail_str = " → ".join(matches)
        return True, confidence, trail_str

    return False, 0, ""


def get_pattern_summary():
    """Get human-readable summary of learned pattern."""
    data = _load_trails()
    pattern = data.get("pattern", [])
    incidents = data.get("incidents", [])

    if not pattern:
        return f"No trail pattern learned yet ({len(incidents)}/{MIN_INCIDENTS} incidents recorded)."

    return (f"Learned drift trail ({len(incidents)} incidents): "
            f"{' → '.join(pattern)}")


class TrailWatcher(threading.Thread):
    """Monitors current activity against learned drift trails.
    When the early stages of a trail are detected, warns before
    the user reaches explicit content."""

    def __init__(self, state, convo_callback, escalate_vision):
        super().__init__(daemon=True)
        self.state = state
        self.convo = convo_callback
        self.escalate_vision = escalate_vision
        self.last_warning = 0
        self.warned_this_session = False

    def run(self):
        time.sleep(180)  # 3 min startup
        while not self.state.get("stop"):
            try:
                self._check()
            except Exception:
                pass
            time.sleep(30)

    def _check(self):
        now = time.time()

        # don't warn more than once every 10 minutes
        if now - self.last_warning < 600:
            return

        # get recent apps from last 5 minutes
        cutoff = now - 300
        day = date.today().isoformat()
        try:
            rows = db._conn.execute(
                "SELECT process, title FROM activity "
                "WHERE day=? AND ts>=? ORDER BY ts",
                (day, cutoff)).fetchall()
        except Exception:
            return

        if len(rows) < 5:
            return

        recent = list(set(f"{proc} {title}".lower()
                         for proc, title in rows))

        is_drifting, confidence, trail = check_trail(recent)

        if is_drifting and confidence >= 0.4:
            self.last_warning = now

            # increase vision scan frequency immediately
            self.escalate_vision()

            if confidence >= 0.7:
                # high confidence — strong warning
                self.convo(
                    f"I've seen this pattern before: {trail}. "
                    f"Last {len(_load_trails().get('incidents', []))} times "
                    f"this trail ended at a red line. Close it now — "
                    f"you're still in control at this step.")
            else:
                # moderate confidence — gentle flag
                self.convo(
                    f"Noticing a familiar pattern: {trail}. "
                    f"Just flagging it — you know where this has gone before.")
