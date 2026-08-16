"""Accountability export. Sends a daily or weekly summary email to
someone who matters — business coach, accountability partner, friend.

Uses Gmail SMTP (most common). User sets credentials once in config.
"""
import smtplib
import os
from email.mime.text import MIMEText
from datetime import date

import config
import db
import data
import score as score_mod

# ── Config: set these in config.py or environment variables ──────────
# EXPORT_EMAIL_TO = "coach@example.com"
# EXPORT_EMAIL_FROM = "you@gmail.com"
# EXPORT_EMAIL_PASSWORD = "your-app-password"  (use Gmail App Password)
# EXPORT_ENABLED = True


def is_configured():
    """Check if export is set up."""
    return bool(
        getattr(config, "EXPORT_ENABLED", False) and
        getattr(config, "EXPORT_EMAIL_TO", "") and
        getattr(config, "EXPORT_EMAIL_FROM", "") and
        getattr(config, "EXPORT_EMAIL_PASSWORD", "")
    )


def send_daily():
    """Send today's accountability summary."""
    if not is_configured():
        return False, "Export not configured — see config.py"

    summary = db.today_summary()
    s = score_mod.today_score()
    streak, _, avg7 = score_mod.streak_info()
    d = data.load()
    tasks = data.get_tasks()
    done = sum(1 for t in tasks if t.get("done"))

    # build the email
    subject = f"WITNESS Daily: {s}% — {date.today().strftime('%b %d')}"

    body = (
        f"WITNESS DAILY ACCOUNTABILITY REPORT\n"
        f"{'=' * 40}\n\n"
        f"Date: {date.today().strftime('%A, %B %d, %Y')}\n"
        f"Focus Score: {s}%\n"
        f"Streak: {streak} days above 70%\n"
        f"7-Day Average: {avg7}%\n\n"
        f"Tasks: {done}/{len(tasks)} completed\n"
    )
    for t in tasks:
        status = "✓" if t.get("done") else "○"
        body += f"  {status} {t.get('by', '')} — {t['text']}\n"

    body += (
        f"\nTime tracked: {summary['minutes_tracked']} min\n"
        f"Time drifting: {summary['minutes_flagged']} min\n"
        f"Red-line events: {summary['redline_events']}\n"
        f"SOS events: {len(summary['sos_events'])}\n\n"
        f"Top apps:\n"
    )
    for app, mins in list(summary["per_app_minutes"].items())[:8]:
        body += f"  {app}: {mins} min\n"

    m = d["money"]
    gap = m["target_monthly"] - m["current_monthly"]
    body += (
        f"\nMoney: ${m['current_monthly']}/mo → ${m['target_monthly']}/mo "
        f"(gap: ${gap})\n"
    )

    # send via metrics if available
    try:
        metrics = data.get_metrics()
        b = metrics.get("business", {})
        body += (
            f"\nBusiness: {b.get('calls_made', 0)} calls, "
            f"{b.get('leads_contacted', 0)} leads, "
            f"{b.get('bookings', 0)} bookings\n"
        )
    except Exception:
        pass

    body += f"\n{'=' * 40}\nSent automatically by WITNESS"

    return _send(subject, body)


def send_weekly(review_text):
    """Send weekly review."""
    if not is_configured():
        return False, "Export not configured"

    subject = f"WITNESS Weekly Review — {date.today().strftime('%b %d')}"
    return _send(subject, review_text)


def _send(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.EXPORT_EMAIL_FROM
        msg["To"] = config.EXPORT_EMAIL_TO

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.EXPORT_EMAIL_FROM,
                         config.EXPORT_EMAIL_PASSWORD)
            server.send_message(msg)
        return True, f"Sent to {config.EXPORT_EMAIL_TO}"
    except Exception as e:
        return False, f"Send failed: {e}"
