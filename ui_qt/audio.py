"""Restrained Windows sound feedback for the Qt presentation layer.

Sounds are intentionally low-amplitude and asynchronous. Failure is silent: audio
must never block scoring or make the UI feel less responsive.
"""
from __future__ import annotations

import os

from . import prefs

BASE = os.path.join(os.path.dirname(__file__), "assets", "sounds")
_FILES = {
    "xp": "xp.wav",
    "overtake": "overtake.wav",
    "record": "record.wav",
    "level": "level.wav",
    "danger": "danger.wav",
    "core": "core.wav",
}


def enabled() -> bool:
    return bool(prefs.get("sound_feedback", True))


def set_enabled(value: bool):
    prefs.set_value("sound_feedback", bool(value))


def play(kind: str):
    if not enabled():
        return
    filename = _FILES.get(str(kind))
    if not filename:
        return
    path = os.path.join(BASE, filename)
    if not os.path.exists(path):
        return
    try:
        import winsound
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        winsound.PlaySound(path, flags)
    except Exception:
        # WITNESS remains fully usable on non-Windows/dev environments.
        pass
