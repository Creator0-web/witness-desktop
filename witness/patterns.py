"""Pattern analyzer. Runs every 5 minutes, compares current app usage
against learned profiles for the current schedule block. Three phases:
  Week 1: mostly silent, learning your patterns
  Week 2-3: calibrated, catches clear outliers
  Week 4+: refined, quiet unless something's genuinely off
"""
import threading
import time
import json
import random
from datetime import datetime

import config
import db
import data
import ai


def _current_block():
    """Return the schedule block label for right now, or None."""
    now = datetime.now().strftime("%H:%M")
    d = data.load()
    for blk in d["schedule"]:
        if blk["start"] <= now < blk["end"]:
            return blk["label"]
    return None


def _analyze(convo_callback):
    """One analysis cycle. Called every 5 minutes."""
    block = _current_block()
    if not block:
        return

    recent = db.get_recent_activity(300)
    if not recent:
        return

    app_secs = {app: int(pct / 100 * 300) for app, pct in recent.items()}
    db.log_pattern_block(block, app_secs)

    if random.random() < 0.17:
        db.rebuild_profiles()

    profile, sample_days = db.get_profile(block)

    # system apps to ignore
    IGNORE = {"explorer.exe", "taskmgr.exe", "searchhost.exe",
              "pythonw.exe", "python.exe", "cmd.exe",
              "powershell.exe", "unknown", "witness"}

    if sample_days < 3:
        # LEARNING: occasionally ask about unfamiliar apps
        unknown = [a for a in recent if recent[a] >= 15
                   and a not in profile and a.lower() not in IGNORE
                   and not any(k in a.lower() for k in IGNORE)]
        if unknown and random.random() < 0.3:
            app = unknown[0]
            convo_callback(
                f"Still learning your workflow. What do you use "
                f"{app} for? It was {recent[app]}% of the last 5 "
                f"minutes during your '{block}' block.")
        return

    # CALIBRATED: detect anomalies
    anomalies = []
    for app, cur_pct in recent.items():
        if app.lower() in IGNORE:
            continue
        normal = profile.get(app, 0)
        if cur_pct >= 20 and cur_pct > normal + 25:
            anomalies.append({"app": app, "now": cur_pct,
                              "normal": round(normal)})

    missing = []
    for app, normal in profile.items():
        if app.lower() in IGNORE:
            continue
        if normal >= 20 and recent.get(app, 0) < 5:
            missing.append({"app": app, "expected": round(normal)})

    if not anomalies and not missing:
        return  # on pattern

    # confidence threshold: more data = more willing to speak
    thresh = 0.85 if sample_days >= 14 else 0.55 if sample_days >= 7 else 0.3
    if random.random() > thresh:
        return

    ctx = {
        "block": block,
        "recent": {k: v for k, v in recent.items()
                   if k.lower() not in IGNORE},
        "normal": {k: round(v) for k, v in profile.items()
                   if v >= 5 and k.lower() not in IGNORE},
        "anomalies": anomalies,
        "missing": missing,
        "days_learned": sample_days,
    }

    try:
        line = ai._ask(config.FAST_MODEL, (
            f"{ai._PERSONA}\n"
            f"Current time: {ai._est_now()}\n"
            f"User context:\n{data.goal_context()}\n\n"
            f"Pattern analysis — block '{block}':\n"
            f"{json.dumps(ctx, indent=1)}\n\n"
            "Their recent app usage doesn't match the learned pattern. "
            "Write ONE spoken observation, max 20 words. Name the specific "
            "app. Be curious — maybe they have a reason. End with a quick "
            "question. Output only the line."), 80)
        if line:
            convo_callback(line)
    except Exception:
        pass


class PatternWatcher(threading.Thread):
    def __init__(self, state, convo_callback):
        super().__init__(daemon=True)
        self.state = state
        self.callback = convo_callback

    def run(self):
        time.sleep(120)  # 2 min warmup
        while not self.state.get("stop"):
            try:
                if self.state.get("present"):
                    _analyze(self.callback)
            except Exception:
                pass
            time.sleep(300)  # every 5 minutes
