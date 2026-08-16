"""Active-window tracker with the escalation ladder.
Emits events onto the queue:
  ("speak_escalation", stage, proc, title)   — voice line stages
  ("checkin", kind, proc, title)             — full check-in window
"""
import threading
import time

import psutil
import win32gui
import win32process

import config
import db


def _active_window():
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid).name() if pid > 0 else "unknown"
        return proc, title
    except Exception:
        return "unknown", ""


def _matches(text, keywords):
    low = text.lower()
    return any(k in low for k in keywords)


class WindowTracker(threading.Thread):
    def __init__(self, state, events):
        super().__init__(daemon=True)
        self.state = state
        self.events = events
        self.drift_started = None
        self.stage_fired = -1
        self.last_redline = 0

    def run(self):
        while not self.state.get("stop"):
            proc, title = _active_window()
            blob = f"{proc} {title}"
            redline = _matches(blob, config.RED_LINE_KEYWORDS)
            drifting = redline or _matches(blob, config.DISTRACTING_KEYWORDS)

            db.log_activity(proc, title, drifting)
            self.state["current_app"] = proc
            self.state["current_title"] = title[:60]

            now = time.time()
            mult = (config.DEEP_WORK_SPEEDUP
                    if self.state.get("deep_work_until", 0) > now else 1.0)

            if redline:
                if now - self.last_redline > 120:
                    self.last_redline = now
                    db.log_redline(title[:80])
                    self.events.put(("checkin", "redline", proc, title))
                self.drift_started = None
                self.stage_fired = -1

            elif drifting:
                if self.drift_started is None:
                    self.drift_started = now
                    self.stage_fired = -1
                mins = (now - self.drift_started) / 60
                for i, mark in enumerate(config.ESCALATE_AT_MIN):
                    if mins >= mark * mult and self.stage_fired < i:
                        self.stage_fired = i
                        self.events.put(("speak_escalation", i, proc, title))
                if mins >= config.CHECKIN_AT_MIN * mult:
                    self.events.put(("checkin", "drift", proc, title))
                    self.drift_started = None
                    self.stage_fired = -1
            else:
                self.drift_started = None
                self.stage_fired = -1

            time.sleep(config.WINDOW_POLL_SEC)
