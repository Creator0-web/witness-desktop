"""Input monitor. Tracks mouse movement and keyboard activity to know
when the user is actively working vs truly idle. Works alongside the
window tracker — solves the "typing in Gmail for 20 min but window
title never changed" blind spot.
"""
import threading
import time
import ctypes


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class InputMonitor(threading.Thread):
    def __init__(self, state):
        super().__init__(daemon=True)
        self.state = state
        self.last_pos = (0, 0)
        self.last_input_time = time.time()

    def run(self):
        while not self.state.get("stop"):
            try:
                # check mouse position
                pt = POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                pos = (pt.x, pt.y)

                if pos != self.last_pos:
                    self.last_pos = pos
                    self.last_input_time = time.time()

                # check last input event (covers keyboard + mouse clicks)
                try:
                    class LASTINPUTINFO(ctypes.Structure):
                        _fields_ = [("cbSize", ctypes.c_uint),
                                    ("dwTime", ctypes.c_uint)]
                    lii = LASTINPUTINFO()
                    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
                    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
                    millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                    if millis < 2000:  # input in last 2 seconds
                        self.last_input_time = time.time()
                except Exception:
                    pass

                # update shared state
                idle_seconds = time.time() - self.last_input_time
                self.state["idle_seconds"] = idle_seconds
                self.state["input_active"] = idle_seconds < 30

            except Exception:
                pass
            time.sleep(2)
