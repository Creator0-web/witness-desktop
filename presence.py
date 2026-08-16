"""Presence engine — makes Witness feel alive by noticing things
unprompted. Runs every 2-3 minutes, observes micro-patterns in
the activity stream, and occasionally comments. The key word is
'occasionally' — a real observer doesn't narrate everything.

Observations it can make:
- Deep focus streaks ("50 min locked in — longest this week")
- Rapid app switching ("3 switches in 30 sec — restless?")
- Repeated open/close ("opened Gmail 4 times without staying")
- Time awareness ("it's almost lunch", "getting late")
- Pace changes (sudden shift from focused to scattered)
- Late starts on scheduled blocks
- Long breaks / return comments
- New/unfamiliar apps
- Window title observations ("looks like you're working on a proposal")
"""
import threading
import time
import random
import json
from datetime import datetime, date
from collections import Counter

import config
import db
import data
import ai


class PresenceEngine(threading.Thread):
    def __init__(self, state, convo_callback):
        super().__init__(daemon=True)
        self.state = state
        self.convo = convo_callback
        self.last_comment = 0
        self.last_titles = []
        self.focus_start = None
        self.seen_apps = set()
        self.commented_topics = set()  # avoid repeating observations

    def run(self):
        time.sleep(60)  # 1 min warmup
        while not self.state.get("stop"):
            try:
                if self.state.get("present"):
                    self._observe()
            except Exception:
                pass
            # vary the interval so it feels human, not clockwork
            time.sleep(random.randint(120, 240))

    def _observe(self):
        now = time.time()
        # don't comment too often — max every 4 minutes
        if now - self.last_comment < 240:
            return

        # gather recent activity (last 3 minutes)
        recent = self._recent_activity(180)
        if not recent:
            return

        observation = self._find_observation(recent)
        if observation:
            self.last_comment = now
            self.convo(observation)

    def _recent_activity(self, seconds):
        """Get raw activity data from last N seconds."""
        cutoff = time.time() - seconds
        day = date.today().isoformat()
        try:
            rows = db._conn.execute(
                "SELECT ts, process, title, flagged FROM activity "
                "WHERE day=? AND ts>=? ORDER BY ts",
                (day, cutoff)).fetchall()
            return rows
        except Exception:
            return []

    def _find_observation(self, recent):
        """Look for something worth commenting on. Returns a string or None."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        apps = [r[1] for r in recent]
        titles = [r[2] for r in recent]
        app_counts = Counter(apps)
        unique_apps = len(set(apps))
        total = len(recent)

        if total < 5:
            return None

        # 1. DEEP FOCUS: same app for a long time
        dominant_app = app_counts.most_common(1)[0]
        if dominant_app[1] / total > 0.85 and total > 20:
            # been on one app for 3+ min straight
            focus_min = (total * config.WINDOW_POLL_SEC) // 60
            if focus_min >= 3 and "deep_focus" not in self.commented_topics:
                self.commented_topics.add("deep_focus")
                return self._ai_observe(
                    f"User has been focused on {dominant_app[0]} for "
                    f"{focus_min}+ minutes straight. Briefly acknowledge "
                    f"the focus — one line, don't interrupt the flow.")
            # reset after 20 min so it can comment again
            if focus_min >= 20:
                self.commented_topics.discard("deep_focus")

        # 2. RAPID SWITCHING: many different apps in short time
        if unique_apps >= 5 and total <= 20:
            if "switching" not in self.commented_topics:
                self.commented_topics.add("switching")
                app_list = ", ".join(a for a, _ in app_counts.most_common(4))
                return self._ai_observe(
                    f"User rapidly switched between {unique_apps} apps in "
                    f"under 2 minutes ({app_list}). Ask if they're looking "
                    f"for something or feeling scattered. One line.")

        # 3. REPEATED OPEN/CLOSE: same app appearing in bursts
        for app, count in app_counts.most_common(3):
            if count >= 4 and unique_apps >= 3:
                appearances = [i for i, a in enumerate(apps) if a == app]
                gaps = [appearances[i+1] - appearances[i]
                        for i in range(len(appearances)-1)]
                if any(g > 2 for g in gaps):  # opened, left, came back
                    key = f"repeat_{app}"
                    if key not in self.commented_topics:
                        self.commented_topics.add(key)
                        return self._ai_observe(
                            f"User keeps opening {app}, leaving, and coming "
                            f"back — {count} times in the last few minutes. "
                            f"Observe this pattern briefly. One line.")

        # 4. TIME AWARENESS
        time_key = f"time_{hour}"
        if time_key not in self.commented_topics:
            if hour == 12 and minute < 15:
                self.commented_topics.add(time_key)
                return self._ai_observe(
                    "It's noon. Make a brief comment about lunch/midday "
                    "energy — acknowledge the time naturally. One line.")
            elif hour >= 20 and minute < 15:
                self.commented_topics.add(time_key)
                return self._ai_observe(
                    f"It's {now.strftime('%I:%M %p')}. Getting late. Brief "
                    "comment about wrapping up or asking how much longer "
                    "they plan to go. One line.")
            elif hour >= 6 and hour < 7 and minute < 15:
                self.commented_topics.add(time_key)
                return self._ai_observe(
                    "User is at the computer early (before 7am). Brief "
                    "comment noticing the early start. One line.")

        # 5. LATE START on schedule block
        d = data.load()
        now_str = now.strftime("%H:%M")
        for blk in d["schedule"]:
            # 15 min past block start
            start_h, start_m = blk["start"].split(":")
            late_time = f"{start_h}:{int(start_m)+15:02d}" if int(start_m) < 45 \
                else f"{int(start_h)+1:02d}:{int(start_m)-45:02d}"
            if late_time <= now_str < blk["end"]:
                key = f"late_{blk['start']}"
                if key not in self.commented_topics:
                    # check if they've been doing relevant work
                    profile, days = db.get_profile(blk["label"])
                    if profile and days >= 2:
                        top_apps = list(profile.keys())[:3]
                        on_task = any(a in apps for a in top_apps)
                        if not on_task:
                            self.commented_topics.add(key)
                            return self._ai_observe(
                                f"Schedule block '{blk['label']}' started at "
                                f"{blk['start']} but user hasn't shifted into "
                                f"their usual apps for it yet. Gently note "
                                f"the late start. One line.")

        # 6. WINDOW TITLE OBSERVATIONS (interesting content noticed)
        interesting_titles = [t for t in titles[-5:]
                              if len(t) > 10
                              and not any(x in t.lower() for x in
                                         ["witness", "untitled", "new tab"])]
        if interesting_titles and random.random() < 0.15:
            title = interesting_titles[-1][:60]
            key = f"title_{title[:20]}"
            if key not in self.commented_topics:
                self.commented_topics.add(key)
                return self._ai_observe(
                    f"User's current window: '{title}'. If this reveals "
                    f"something worth a brief human comment (working on "
                    f"something specific, researching something), make one "
                    f"natural observation. If it's boring/generic, output "
                    f"SKIP. One line max.")

        # 7. Reset commented topics periodically so observations can repeat
        if random.random() < 0.05:
            old = {"deep_focus", "switching"}
            self.commented_topics -= old

        return None

    def _ai_observe(self, instruction):
        """Ask AI to make a brief observation."""
        try:
            line = ai._ask(config.FAST_MODEL, (
                f"{ai._PERSONA}\n"
                f"Current time: {ai._est_now()}\n"
                f"User context:\n{data.goal_context()}\n\n"
                f"You are watching their screen. {instruction}\n"
                "Sound like a person who's been sitting nearby all day — "
                "casual, brief, human. Not an alert or notification. "
                "If the instruction says output SKIP when boring, output "
                "only the word SKIP. Otherwise output only the spoken line."
            ), 60)
            if line and "SKIP" not in line:
                return line
        except Exception:
            pass
        return None
