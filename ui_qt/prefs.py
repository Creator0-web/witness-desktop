"""Tiny local preferences for the Qt delivery layer only.

This deliberately does not touch WITNESS scoring/configuration. The file is safe
to delete; defaults are restored on next launch.
"""
from __future__ import annotations

import json
import os

PATH = "ui_settings.json"
DEFAULTS = {
    "sound_feedback": True,
}


def load() -> dict:
    out = dict(DEFAULTS)
    try:
        if os.path.exists(PATH):
            with open(PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                out.update(raw)
    except Exception:
        pass
    return out


def get(key, default=None):
    return load().get(key, DEFAULTS.get(key, default))


def set_value(key, value):
    data = load()
    data[key] = value
    try:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
    return value
