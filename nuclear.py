"""Nuclear red-line response system. When a red-line site is detected:
1. Kill the browser immediately
2. Block all red-line sites via hosts file (2 hours)
3. Webcam mirror — show the user their own face
4. Auto-launch SOS video cascade
5. Send accountability notification (text only)
6. Log everything for pattern learning

This is the "bulletproof" layer. Not a popup. Not a suggestion. Action.
"""
import os
import subprocess
import threading
import time
import random
from datetime import datetime

import config
import db
import blocker

# browsers to kill
BROWSER_PROCESSES = [
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "iexplore.exe",
]

# physical redirect suggestions (escalating)
REDIRECTS = [
    "Stand up right now. Walk to another room. 60 seconds.",
    "Go outside. Feet on the ground. Sun on your face. 5 minutes.",
    "Get on the treadmill. Run until the urge passes. It will pass.",
    "Cold water on your face. 30 seconds. It resets the nervous system.",
    "Do 20 pushups right now. Move the energy somewhere real.",
    "Call someone. Dylan, your coach, anyone. Human connection beats this.",
]


def kill_browsers():
    """Kill all running browser processes immediately."""
    killed = []
    for proc in BROWSER_PROCESSES:
        try:
            result = subprocess.run(
                ["taskkill", "/f", "/im", proc],
                capture_output=True, timeout=5,
                creationflags=0x08000000)
            if result.returncode == 0:
                killed.append(proc.replace(".exe", ""))
        except Exception:
            pass
    return killed


def capture_webcam_frame(state=None):
    """Get the latest webcam frame from shared state (no second camera open).
    Returns image or None."""
    if state is not None and state.get("last_frame") is not None:
        return state["last_frame"].copy()
    return None


def send_accountability_alert():
    """Send text-only notification to accountability partner."""
    try:
        import export
        if not export.is_configured():
            return False, "Export not configured"

        now = datetime.now().strftime("%I:%M %p on %A, %B %d")
        import smtplib
        from email.mime.text import MIMEText

        subject = "WITNESS — Red Line Alert"
        body = (
            f"This is an automated alert from WITNESS.\n\n"
            f"A red-line event was detected at {now}.\n\n"
            f"The browser was automatically closed and sites blocked.\n"
            f"The SOS intervention system was activated.\n\n"
            f"No further details are included. If you have questions, "
            f"ask them directly.\n\n"
            f"— WITNESS"
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.EXPORT_EMAIL_FROM
        msg["To"] = config.EXPORT_EMAIL_TO

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.EXPORT_EMAIL_FROM,
                         config.EXPORT_EMAIL_PASSWORD)
            server.send_message(msg)
        return True, f"Alert sent to {config.EXPORT_EMAIL_TO}"
    except Exception as e:
        return False, str(e)


def get_redirect(attempt_number):
    """Get escalating physical redirect suggestion."""
    idx = min(attempt_number, len(REDIRECTS) - 1)
    return REDIRECTS[idx]


# ── Intervention effectiveness tracking ─────────────────────────────────
def log_intervention(intervention_type, stopped):
    """Log whether an intervention worked (user stopped) or was bypassed."""
    try:
        db._conn.execute(
            "INSERT INTO sos VALUES (?,?,?,?)",
            (time.time(), datetime.now().strftime("%Y-%m-%d"),
             f"redline_intervention:{intervention_type}",
             "stopped" if stopped else "bypassed"))
        db._conn.commit()
    except Exception:
        pass


def get_effective_interventions():
    """Analyze which interventions have historically worked."""
    try:
        rows = db._conn.execute(
            "SELECT trigger, outcome FROM sos "
            "WHERE trigger LIKE 'redline_intervention:%'"
        ).fetchall()
        stats = {}
        for trigger, outcome in rows:
            itype = trigger.replace("redline_intervention:", "")
            if itype not in stats:
                stats[itype] = {"stopped": 0, "bypassed": 0}
            stats[itype][outcome] = stats[itype].get(outcome, 0) + 1
        return stats
    except Exception:
        return {}
