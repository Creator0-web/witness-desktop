"""Break enforcement and progressive difficulty.

Breaks: after 90 min continuous focus, enforces a 10-min break.
         Not optional — the break IS the productivity tool.

Difficulty: target score rises with your progress over weeks.
            Week 1: 50%, Week 3: 65%, Week 6: 75%.
            Adjusts based on actual performance.
"""
import time
import threading
from datetime import date

import config
import db


# ── Break enforcement ───────────────────────────────────────────────────
class BreakEnforcer(threading.Thread):
    def __init__(self, state, convo_callback):
        super().__init__(daemon=True)
        self.state = state
        self.convo = convo_callback
        self.focus_start = None
        self.on_break = False
        self.break_end = 0

    def run(self):
        time.sleep(120)
        while not self.state.get("stop"):
            try:
                self._check()
            except Exception:
                pass
            time.sleep(30)

    def _check(self):
        now = time.time()

        # if on enforced break, check if it's over
        if self.on_break:
            if now >= self.break_end:
                self.on_break = False
                self.focus_start = None
                self.convo("Break's over. Back in the chair — next 90 "
                           "minutes start now.")
            return

        if not self.state.get("present"):
            # away = natural break, reset timer
            self.focus_start = None
            return

        # check recent drift — if they've been clean, they're focusing
        raw = db.today_raw()
        if raw["samples"] < 10:
            return

        recent_clean = (raw["samples"] - raw["flagged"]) / raw["samples"]

        if recent_clean > 0.85:
            # focused
            if self.focus_start is None:
                self.focus_start = now
            elif now - self.focus_start >= 90 * 60:
                # 90 min of focus — enforce break
                self.on_break = True
                self.break_end = now + 10 * 60
                self.convo(
                    "90 minutes of focus — that's a full cycle. Stand up, "
                    "walk around, get water. 10 minutes. Not optional — "
                    "this is what protects your energy for the next block.")
        else:
            # drifting resets the focus timer (they took an informal break)
            self.focus_start = None


# ── Progressive difficulty ──────────────────────────────────────────────
def get_target():
    """Return the current target score based on how many days of data exist."""
    scores = db.recent_scores(90)
    days_active = len(scores)
    avg = int(sum(s for _, s in scores) / len(scores)) if scores else 0

    # base targets by phase
    if days_active < 7:
        base = 50
        phase = "Week 1 — building the habit"
    elif days_active < 14:
        base = 55
        phase = "Week 2 — finding rhythm"
    elif days_active < 21:
        base = 60
        phase = "Week 3 — consistency"
    elif days_active < 30:
        base = 65
        phase = "Month 1 — raising the bar"
    elif days_active < 45:
        base = 70
        phase = "Month 1.5 — performing"
    elif days_active < 60:
        base = 75
        phase = "Month 2 — elite territory"
    else:
        base = 80
        phase = "Month 3 — finishing strong"

    # adjust: if they're consistently above target, push higher
    if avg > base + 10 and days_active >= 7:
        base = min(90, avg - 5)
        phase += " (adjusted up — you earned it)"
    # if struggling, ease slightly
    elif avg < base - 15 and days_active >= 7:
        base = max(40, avg + 5)
        phase += " (adjusted — steady progress)"

    return base, phase, days_active


def difficulty_context():
    """String for AI prompts about current difficulty level."""
    target, phase, days = get_target()
    return (f"Day {days} of the journey. Phase: {phase}. "
            f"Current target: {target}%. "
            f"Hold them to this standard — it should feel achievable but "
            f"not easy. If they're above it consistently, acknowledge growth.")
