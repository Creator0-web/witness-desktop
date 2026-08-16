"""Screen vision v2 — adaptive trust-based scanning.

Trust levels per browser:
  SAFE     = Chrome with blocker, known work apps. Scan every 5 min max.
  CAUTIOUS = Browsers used for mixed purposes (Brave, Firefox). Scan every 90s.
  DANGER   = Incognito/private mode, or browsers with incident history. Scan every 30s.

Learns from history: if a browser has been flagged 3+ times, it moves
to DANGER permanently. Cost-capped at MAX_SCANS_PER_DAY.
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

# scan intervals by trust level (seconds)
SCAN_INTERVALS = {
    "safe": 300,      # every 5 minutes
    "cautious": 90,   # every 90 seconds
    "danger": 30,     # every 30 seconds
}

# incognito/private window indicators
PRIVATE_INDICATORS = [
    "incognito", "inprivate", "private browsing",
    "private window", "private tab",
]

# safe title keywords — skip scanning entirely
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
MAX_SCANS_PER_DAY = 200     # hard cap: ~$2-3/day max
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
        time.sleep(45)  # startup delay
        while not self.state.get("stop"):
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(5)  # check every 5s, but only scan per trust interval

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

        # skip safe titles (work tools, music)
        if self._is_safe_title(title):
            return

        # get trust level and check interval
        trust = self._get_trust(app, title)
        interval = SCAN_INTERVALS[trust]

        now = time.time()
        if now - self.last_scan < interval:
            return

        # time to scan
        self.last_scan = now
        self.scans_today += 1

        screenshot_b64 = self._capture()
        if not screenshot_b64:
            return

        is_nsfw = self._analyze(screenshot_b64)

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
            # else: single flag, scan again sooner to confirm
            self.last_scan = time.time() - (SCAN_INTERVALS[trust] - 10)
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

        except Exception:
            return False
