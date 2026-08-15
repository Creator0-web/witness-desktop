"""Local storage for API keys, entered through the app's
Settings > Integrations panel instead of a manual `setx` in
PowerShell.

Plain JSON, at secrets.json in the active local WITNESS profile folder. This is PLAIN TEXT
storage -- the same level of protection a Windows environment variable
already has (also effectively plaintext, readable to anything running
as your user account), just easier to manage from inside the app
instead of a terminal.

IMPORTANT, for both the person and any future AI session working on
this profile: secrets.json contains real API keys in plain text once
any are saved. Never zip, share, upload, commit, or paste its contents
anywhere -- including into a chat with an AI assistant. If exporting or sharing
profile data for help, delete or exclude secrets.json
first. An AI session should never ask to see this file's contents.

Design: INTEGRATIONS below is a small registry -- name, env var key,
help text, and (optionally) a cheap live-verification function. Adding
a new integration (Whoop, Fitbit, etc.) later means adding one entry
here; the Settings > Integrations panel in main.py loops over this
list and builds the UI for whichever integrations exist, with no
per-integration UI code needed.
"""
import json
import os

PATH = "secrets.json"


def _verify_anthropic():
    """Minimal, cheap live call to confirm the key actually works, not
    just that something was typed in. Costs a handful of tokens."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return False, "No key set."
    try:
        import config
        import ai
        out = ai._ask(config.FAST_MODEL, "Reply with exactly: OK", 5)
        if out and "OK" in out.upper():
            return True, "Verified."
        return False, "No valid response -- check the key."
    except Exception as e:
        return False, str(e)


def _verify_stripe():
    """stripe.Balance.retrieve() is a lightweight, side-effect-free
    call -- good for confirming a key works without pulling any real
    payment data."""
    key = os.environ.get("STRIPE_API_KEY")
    if not key:
        return False, "No key set."
    try:
        import stripe
        stripe.api_key = key
        stripe.Balance.retrieve()
        return True, "Verified."
    except ImportError:
        return False, "stripe package not installed (pip install stripe)."
    except Exception as e:
        return False, str(e)


INTEGRATIONS = [
    {"name": "Anthropic (Claude)", "env_key": "ANTHROPIC_API_KEY",
     "help": "Required for the character to respond and for daily/"
             "weekly analysis. Get a key at console.anthropic.com.",
     "verify": _verify_anthropic},
    {"name": "Stripe", "env_key": "STRIPE_API_KEY",
     "help": "Optional. Powers real revenue tracking instead of "
             "note-based guessing. Use a READ-ONLY restricted key "
             "from your Stripe dashboard, not your full secret key.",
     "verify": _verify_stripe},
    # Add future integrations (Whoop, Fitbit, etc.) here -- name,
    # env_key, help text, and an optional "verify" function
    # (signature: () -> (bool, str)). No UI code needed elsewhere.
]


def load_all():
    """Call once, as early as possible at app startup -- populates
    os.environ from secrets.json so every existing os.environ.get(...)
    call across the app (ai.py, stripe_sync.py, future integrations)
    keeps working completely unchanged, whether the key came from a
    real environment variable or was pasted into Settings."""
    if not os.path.exists(PATH):
        return
    try:
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
        for key, value in data.items():
            if value:
                os.environ[key] = value
    except Exception:
        pass


def _read_file():
    if not os.path.exists(PATH):
        return {}
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def set_key(env_key: str, value: str):
    """Saves a key to secrets.json and makes it live immediately in
    the current process (os.environ) -- no restart needed."""
    data = _read_file()
    data[env_key] = value
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.environ[env_key] = value


def clear_key(env_key: str):
    data = _read_file()
    data.pop(env_key, None)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.environ.pop(env_key, None)


def is_set(env_key: str) -> bool:
    return bool(os.environ.get(env_key))
