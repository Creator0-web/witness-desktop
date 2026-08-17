"""Screen vision v3 — rapid browser screen guard.

The objective of this layer is prevention, not ordinary productivity nudging:
while a supported browser is foreground, scan the visible screen quickly enough
that sexual/explicit material cannot sit on screen for minutes before WITNESS
reacts. WindowTracker still handles title-keyword red lines independently.

The guard keeps the old two-FLAG confirmation to reduce false positives, but
uses a short confirmation delay and does not exempt nominally "safe" websites
from pixel scanning. A normal work page should be classified SAFE from pixels.
"""
import threading
import time
import io
import base64
import os
import json
from datetime import date, datetime
from collections import defaultdict

import config
import db

# ── Trust configuration ─────────────────────────────────────────────────
# browsers and their default trust level
DEFAULT_TRUST = {
    "chrome.exe": "safe",       # has blocker installed
    "msedge.exe": "cautious",
    "firefox.exe": "cautious",
    "brave.exe": "cautious",    # used for music but also risk
    "opera.exe": "cautious",
    "vivaldi.exe": "cautious",
}

# Rapid protection cadence. Trust is still recorded for incident history, but
# no supported browser is allowed a multi-minute blind window anymore.
SCAN_INTERVALS = {
    "safe": 20,
    "cautious": 20,
    "danger": 15,
}
STARTUP_DELAY_SEC = 3
CONFIRM_DELAY_SEC = 4

# incognito/private window indicators
PRIVATE_INDICATORS = [
    "incognito", "inprivate", "private browsing",
    "private window", "private tab",
]

# Legacy safe-title vocabulary retained for compatibility/history only.
# v3 intentionally does NOT skip these titles: pixel protection must still work
# if explicit material appears inside a normally-safe site.
SAFE_TITLES = [
    "google docs", "google sheets", "google drive", "gmail",
    "booking koala", "vonage", "thumbtack", "calendar",
    "github", "stackoverflow", "stack overflow",
    "claude", "anthropic", "chatgpt",
    "microsoft", "office", "outlook", "word", "excel",
    "witness", "spotify", "youtube music", "pandora",
    "apple music", "amazon", "ebay", "walmart",
    "facebook", "messenger", "whatsapp", "discord",
    "slack", "zoom", "teams", "skype",
    "wikipedia", "maps", "weather", "news",
    "linkedin", "indeed", "bank", "chase", "paypal",
    "stripe", "shopify", "canva", "figma",
    "netflix", "hulu", "disney",
    "gohighlevel", "highlevel",
]

# cost protection
MAX_SCANS_PER_DAY = 1500    # rapid mode; only foreground browser time consumes scans
HISTORY_FILE = "vision_history.json"
INCIDENT_THRESHOLD = 3       # flags before browser moves to DANGER


class ScreenVision(threading.Thread):
    def __init__(self, state, nuclear_callback):
        super().__init__(daemon=True)
        self.state = state
        self.trigger_nuclear = nuclear_callback
        self.scans_today = 0
        self.scan_date = date.today().isoformat()
        self.last_scan = 0
        self.browser_incidents = self._load_history()
        self.consecutive_flags = 0  # need 2 in a row to trigger
        self.state["vision_status"] = "STARTING"
        self.state["vision_last_scan"] = 0.0
        self.state["vision_last_result"] = "WAITING"
        self.state["vision_last_error"] = ""
        self.state["vision_scans_today"] = 0

    def _load_history(self):
        """Load incident counts per browser."""
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.browser_incidents, f)
        except Exception:
            pass

    def _get_trust(self, app, title):
        """Determine trust level for current browser + context."""
        app_lower = app.lower()
        title_lower = title.lower()

        # incognito/private = ALWAYS danger
        if any(p in title_lower for p in PRIVATE_INDICATORS):
            return "danger"

        # check incident history — 3+ flags = permanent danger
        incidents = self.browser_incidents.get(app_lower, 0)
        if incidents >= INCIDENT_THRESHOLD:
            return "danger"

        # default trust level
        return DEFAULT_TRUST.get(app_lower, "cautious")

    def _is_browser(self, app):
        return app.lower() in DEFAULT_TRUST

    def _is_safe_title(self, title):
        title_lower = title.lower()
        return any(safe in title_lower for safe in SAFE_TITLES)

    def run(self):
        time.sleep(STARTUP_DELAY_SEC)
        self.state["vision_status"] = "ACTIVE"
        while not self.state.get("stop"):
            try:
                self._tick()
            except Exception as ex:
                self.state["vision_status"] = "ERROR"
                self.state["vision_last_error"] = str(ex)[:180]
            time.sleep(1)  # cheap eligibility check; network scans obey intervals above

    def _tick(self):
        # reset daily counter
        today = date.today().isoformat()
        if today != self.scan_date:
            self.scans_today = 0
            self.scan_date = today

        # cost cap
        if self.scans_today >= MAX_SCANS_PER_DAY:
            return

        if not self.state.get("present"):
            return

        app = self.state.get("current_app", "")
        title = self.state.get("current_title", "")

        # only scan browsers
        if not self._is_browser(app):
            return

        # Do not skip pixels based on page title. The previous adaptive guard could
        # leave Chrome/work/social pages unscanned for minutes or forever; that is
        # incompatible with rapid red-line protection.

        # get trust level and check interval
        trust = self._get_trust(app, title)
        interval = SCAN_INTERVALS[trust]

        now = time.time()
        if now - self.last_scan < interval:
            return

        # time to scan
        self.last_scan = now
        self.scans_today += 1
        self.state["vision_status"] = "SCANNING"
        self.state["vision_last_scan"] = now
        self.state["vision_scans_today"] = self.scans_today

        screenshot_b64 = self._capture()
        if not screenshot_b64:
            self.state["vision_status"] = "ERROR"
            self.state["vision_last_result"] = "CAPTURE ERROR"
            self.state["vision_last_error"] = "Could not capture the active screen."
            return

        is_nsfw = self._analyze(screenshot_b64)
        if is_nsfw is None:
            return

        self.state["vision_status"] = "ACTIVE"
        self.state["vision_last_result"] = "FLAG" if is_nsfw else "SAFE"
        self.state["vision_last_error"] = ""

        if is_nsfw:
            self.consecutive_flags += 1
            if self.consecutive_flags >= 2:
                # confirmed — two scans in a row flagged it
                app_lower = app.lower()
                self.browser_incidents[app_lower] = \
                    self.browser_incidents.get(app_lower, 0) + 1
                self._save_history()
                db.log_redline(f"VISION [{trust}]: {title[:60]}")
                self.trigger_nuclear(app, title)
                self.consecutive_flags = 0
            # Single flag: confirm quickly. This keeps the old two-FLAG safety
            # while keeping total response comfortably below the old multi-minute
            # blind windows.
            self.last_scan = time.time() - (SCAN_INTERVALS[trust] - CONFIRM_DELAY_SEC)
        else:
            self.consecutive_flags = 0

    def _capture(self):
        """Take a screenshot, return as base64 JPEG."""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            max_w = 1280
            if img.width > max_w:
                ratio = max_w / img.width
                new_size = (max_w, int(img.height * ratio))
                img = img.resize(new_size, getattr(__import__('PIL.Image',
                    fromlist=['LANCZOS']), 'LANCZOS',
                    img.resize.__code__.co_varnames and 1))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=55)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            try:
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    raw = sct.grab(monitor)
                    from PIL import Image
                    img = Image.frombytes("RGB", raw.size, raw.bgra,
                                         "raw", "BGRX")
                    max_w = 1280
                    if img.width > max_w:
                        ratio = max_w / img.width
                        img = img.resize((max_w, int(img.height * ratio)))
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=55)
                    return base64.b64encode(buf.getvalue()).decode()
            except Exception:
                return None

    def _analyze(self, image_b64):
        """Send to Claude Vision for NSFW detection."""
        try:
            import anthropic
            client = anthropic.Anthropic()

            response = client.messages.create(
                model=config.FAST_MODEL,
                max_tokens=10,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            }
                        },
                        {
                            "type": "text",
                            "text": (
                                "Is there sexually suggestive or explicit "
                                "content visible on this screen? "
                                "FLAG means: nudity, pornography, women in "
                                "bikinis or lingerie as the main content, "
                                "try-on haul videos, sexual poses, erotic "
                                "content, suggestive thumbnails that are "
                                "clearly sexual bait, or any content "
                                "primarily designed to be sexually arousing.\n"
                                "SAFE means: normal websites, work tools, "
                                "documents, spreadsheets, email, social media "
                                "feeds without sexual content, news, coding, "
                                "business apps, music players, normal photos "
                                "of clothed people, normal youtube videos, "
                                "shopping sites, any text-heavy page.\n"
                                "If the screen shows a work tool, document, "
                                "email, or business app — always SAFE.\n"
                                "Answer ONLY one word: FLAG or SAFE."
                            ),
                        }
                    ]
                }]
            )

            answer = response.content[0].text.strip().upper()
            return "FLAG" in answer

        except Exception as ex:
            # A failed API request must not masquerade as a SAFE screen. Surface it
            # to the Qt protection badge/settings so detection failures are visible.
            self.state["vision_status"] = "ERROR"
            self.state["vision_last_result"] = "API ERROR"
            self.state["vision_last_error"] = str(ex)[:180]
            return None
