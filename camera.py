"""Webcam presence detection. Tries camera slots 0-2. Stores the latest
frame in shared state so other systems (mirror, etc.) can use it without
opening a second camera connection.

Pushes 'greet' events when you sit down or return from away.
No frames are saved to disk — detection only.
"""
import threading
import time

import config
import db


class PresenceWatcher(threading.Thread):
    def __init__(self, state, events=None):
        super().__init__(daemon=True)
        self.state = state
        self.events = events

    def _open_camera(self, cv2):
        for idx in (0, 1, 2):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    return cap
                cap.release()
        return None

    def run(self):
        try:
            import cv2
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            cap = self._open_camera(cv2)
            if cap is None:
                raise RuntimeError("no working camera")
        except Exception:
            self.state["camera_ok"] = False
            self.state["present"] = True
            self.state["last_frame"] = None
            return

        self.state["camera_ok"] = True
        last_seen = time.time()
        left_at = None
        present = None

        while not self.state.get("stop"):
            ok, frame = cap.read()
            if not ok:
                # camera may have been grabbed — try to reopen
                cap.release()
                time.sleep(2)
                try:
                    cap = self._open_camera(cv2)
                    if cap is None:
                        time.sleep(5)
                        continue
                    ok, frame = cap.read()
                    if not ok:
                        continue
                except Exception:
                    time.sleep(5)
                    continue

            # store latest frame for mirror/other uses
            self.state["last_frame"] = frame.copy()

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
            if len(cascade.detectMultiScale(gray, 1.2, 4)) > 0:
                last_seen = time.time()

            now_present = (time.time() - last_seen) < config.AWAY_AFTER_SEC

            if present is None:
                present = now_present
                self.state["present"] = present
                db.log_presence("arrived" if present else "left")
                if present and self.events is not None:
                    self.events.put(("greet", "first"))
            elif now_present != present:
                present = now_present
                self.state["present"] = present
                db.log_presence("arrived" if present else "left")
                if not present:
                    left_at = time.time()
                elif self.events is not None and left_at and \
                        time.time() - left_at > 180:
                    self.events.put(("greet", "return"))

            time.sleep(config.CAMERA_POLL_SEC)

        cap.release()
