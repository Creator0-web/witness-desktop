"""Smart phone/idle detection. When the user is present (camera) but
idle (no mouse/keyboard) for 2+ minutes, takes a webcam photo and asks
the AI what the person is doing. Responds contextually:
- On phone → comment on it
- Thinking → offer to help
- Sleeping/zoned out → gentle wake-up
- Reading something → leave them alone
"""
import threading
import time
import io
import base64
import os
from datetime import datetime

import config
import db


class PhoneDetector(threading.Thread):
    def __init__(self, state, convo_callback):
        super().__init__(daemon=True)
        self.state = state
        self.convo = convo_callback
        self.last_alert = 0
        self.phone_minutes_today = 0

    def run(self):
        time.sleep(120)
        while not self.state.get("stop"):
            try:
                self._check()
            except Exception:
                pass
            time.sleep(20)

    def _check(self):
        now = time.time()
        present = self.state.get("present", False)
        idle_sec = self.state.get("idle_seconds", 0)

        if not present:
            return

        # only check during work hours
        hour = datetime.now().hour
        if hour < 7 or hour > 21:
            return

        # need 2+ min of no input while present at desk
        if idle_sec < 120:
            return

        # don't alert more than every 8 minutes
        if now - self.last_alert < 480:
            return

        # take a webcam photo and ask AI what they're doing
        frame = self.state.get("last_frame")
        if frame is None:
            return

        description = self._analyze_posture(frame)
        if not description:
            return

        self.last_alert = now

        # the AI already determined what to say
        if description != "SKIP":
            self.convo(description)

    def _analyze_posture(self, frame):
        """Send webcam frame to AI to determine what the user is doing."""
        try:
            import cv2
            import anthropic

            # encode frame as JPEG
            frame_small = cv2.resize(frame, (320, 240))
            _, buf = cv2.imencode(".jpg", frame_small,
                                  [cv2.IMWRITE_JPEG_QUALITY, 50])
            b64 = base64.b64encode(buf.tobytes()).decode()

            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=config.FAST_MODEL,
                max_tokens=60,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            }
                        },
                        {
                            "type": "text",
                            "text": (
                                "This is a webcam photo of a person at their "
                                "desk. They haven't touched their mouse or "
                                "keyboard for over 2 minutes. What are they "
                                "most likely doing? Choose ONE:\n"
                                "- PHONE: looking down at phone in hands\n"
                                "- THINKING: leaning back, looking up/away, "
                                "hand on chin — deep thought\n"
                                "- READING: looking at screen but not typing "
                                "(reading a document)\n"
                                "- DISTRACTED: looking away, not engaged\n"
                                "- AWAY: not clearly visible or turned away\n"
                                "- RESTING: eyes closed or head down\n\n"
                                "Answer with ONLY the category word."
                            ),
                        }
                    ]
                }]
            )

            category = resp.content[0].text.strip().upper()

            if "PHONE" in category:
                self.phone_minutes_today += 2
                return (f"Looks like you're on your phone. "
                        f"About {self.phone_minutes_today} minutes of "
                        f"phone time today. Anything urgent or just drifting?")
            elif "THINKING" in category:
                return ("Looks like you're thinking something through. "
                        "Want to talk it out? Sometimes saying it helps.")
            elif "READING" in category:
                return "SKIP"  # reading is fine, leave them alone
            elif "DISTRACTED" in category:
                return ("You've been idle for a couple minutes and "
                        "look checked out. What's pulling your attention?")
            elif "RESTING" in category:
                return ("Hey. Eyes closed at the desk — need a real break? "
                        "Stand up, walk around, come back sharp.")
            elif "AWAY" in category:
                return "SKIP"
            else:
                return "SKIP"

        except Exception:
            # no API or broken camera — fall back to simple idle alert
            return None
