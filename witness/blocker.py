"""Site blocker. Edits Windows hosts file to make red-line and optionally
distracting sites unreachable for a timed period. Requires admin privileges
the first time — the app will prompt for elevation.

Uses a lock file so you can't undo it early even if you want to.
"""
import os
import time
import threading
import ctypes
from datetime import datetime

import config

HOSTS = r"C:\Windows\System32\drivers\etc\hosts"
MARKER_START = "# WITNESS BLOCK START"
MARKER_END = "# WITNESS BLOCK END"
LOCK_FILE = "block_lock.txt"


def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def _read_hosts():
    try:
        with open(HOSTS, "r") as f:
            return f.read()
    except Exception:
        return ""


def _write_hosts(content):
    try:
        with open(HOSTS, "w") as f:
            f.write(content)
        return True
    except PermissionError:
        return False


def _clean_hosts():
    """Remove any existing WITNESS blocks from hosts file."""
    content = _read_hosts()
    if MARKER_START not in content:
        return
    lines = content.split("\n")
    clean = []
    inside = False
    for line in lines:
        if MARKER_START in line:
            inside = True
            continue
        if MARKER_END in line:
            inside = False
            continue
        if not inside:
            clean.append(line)
    _write_hosts("\n".join(clean))


def block_sites(keywords=None, duration_min=60):
    """Block sites matching keywords for duration_min minutes.
    Returns (success: bool, message: str)."""
    if not _is_admin():
        return False, ("Site blocking needs admin access. Right-click "
                       "start_witness.bat → 'Run as administrator' to enable.")

    sites = keywords or config.RED_LINE_KEYWORDS
    # build hosts entries
    entries = []
    for kw in sites:
        # block common domain patterns
        if "." in kw:
            entries.append(f"127.0.0.1 {kw}")
            entries.append(f"127.0.0.1 www.{kw}")
        else:
            entries.append(f"127.0.0.1 {kw}.com")
            entries.append(f"127.0.0.1 www.{kw}.com")

    _clean_hosts()
    block_text = (f"\n{MARKER_START}\n" +
                  "\n".join(entries) +
                  f"\n{MARKER_END}\n")

    content = _read_hosts() + block_text
    if not _write_hosts(content):
        return False, "Could not write to hosts file."

    # write lock file
    unlock_time = time.time() + duration_min * 60
    with open(LOCK_FILE, "w") as f:
        f.write(str(unlock_time))

    # schedule unblock
    threading.Thread(target=_unblock_timer, args=(duration_min,),
                     daemon=True).start()

    # flush DNS cache
    os.system("ipconfig /flushdns >nul 2>&1")

    return True, f"Blocked {len(sites)} sites for {duration_min} minutes."


def _unblock_timer(minutes):
    time.sleep(minutes * 60)
    unblock()


def unblock():
    """Remove blocks. Only works if lock timer has expired."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                unlock_time = float(f.read().strip())
            if time.time() < unlock_time:
                remaining = int((unlock_time - time.time()) / 60)
                return False, f"Lock active. {remaining} minutes remaining."
        except Exception:
            pass
        os.remove(LOCK_FILE)
    _clean_hosts()
    os.system("ipconfig /flushdns >nul 2>&1")
    return True, "Sites unblocked."


def is_blocked():
    """Check if a block is currently active."""
    if not os.path.exists(LOCK_FILE):
        return False, 0
    try:
        with open(LOCK_FILE) as f:
            unlock_time = float(f.read().strip())
        remaining = max(0, int((unlock_time - time.time()) / 60))
        if remaining <= 0:
            unblock()
            return False, 0
        return True, remaining
    except Exception:
        return False, 0
