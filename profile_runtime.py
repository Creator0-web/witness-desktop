"""WITNESS local-profile bootstrap.

This module is intentionally standard-library-only and is imported *before* the
rest of WITNESS.  Its job is to separate application code from personal data.

On Windows, each Windows account gets its own profile under::

    %LOCALAPPDATA%\\WITNESS

The runtime then changes the process working directory to that profile folder.
Existing WITNESS modules can keep using their historical relative paths
(`witness.db`, `video_memories/`, `progression.json`, etc.) without touching
frozen Layer-1 code, while every user's data remains outside the program folder.

There are deliberately no usernames/passwords in V1.  Windows account isolation
is the profile boundary.  A random profile_id is generated only as a stable local
identifier for future backup/sync features; it is not an online account.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "WITNESS"
PROFILE_SCHEMA = 1
PROFILE_FILE = "profile.json"
PENDING_IMPORT_FILE = ".pending_legacy_import.json"
IMPORT_HISTORY_FILE = "import_history.json"

# Every known historical *user-data* path that older project-folder builds may
# have created.  Code/assets/docs are intentionally absent from this list.
LEGACY_FILES = (
    "witness.db",
    "witness_data.json",
    "progression.json",
    "conversation.json",
    "xp_triggers.json",
    "xp_triggers_fired.json",
    "secrets.json",
    "ui_settings.json",
    "vision_history.json",
    "trail_history.json",
    "stats_model.json",
    "life_data.json",
    "block_lock.txt",
)
LEGACY_DIRS = (
    "recaps",
    "sos_videos",
    "video_memories",
    "day_breakdown_data",
    "insight_data",
    "journals",
)

_ACTIVE: dict | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_data_dir() -> Path:
    override = os.environ.get("WITNESS_DATA_DIR", "").strip()
    if override:
        return Path(os.path.expandvars(os.path.expanduser(override))).resolve()

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return (Path(base) / APP_NAME).resolve()
        # Extremely defensive fallback for unusual Windows shells.
        return (Path.home() / "AppData" / "Local" / APP_NAME).resolve()

    # Non-Windows path exists only for development/tests.  Production is Windows.
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else (Path.home() / ".local" / "share")
    return (base / APP_NAME).resolve()


def data_dir() -> Path:
    if _ACTIVE:
        return Path(_ACTIVE["data_dir"])
    return _default_data_dir()


def app_dir() -> Path | None:
    if _ACTIVE:
        return Path(_ACTIVE["app_dir"])
    raw = os.environ.get("WITNESS_APP_DIR", "").strip()
    return Path(raw).resolve() if raw else None


def _read_json(path: Path, default=None):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def _write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def _legacy_entries(source: Path) -> list[str]:
    out = []
    if not source.exists() or not source.is_dir():
        return out
    for name in LEGACY_FILES:
        if (source / name).is_file():
            out.append(name)
    for name in LEGACY_DIRS:
        p = source / name
        if p.is_dir() and any(p.iterdir()):
            out.append(name + "/")
    return out


def legacy_entries(source) -> list[str]:
    """Return recognized legacy user-data entries in ``source``."""
    return _legacy_entries(Path(source).expanduser().resolve())


def _copy_tree_merge(source: Path, target: Path, overwrite: bool) -> int:
    copied = 0
    for root, dirs, files in os.walk(source):
        rel = Path(root).relative_to(source)
        dest_root = target / rel
        dest_root.mkdir(parents=True, exist_ok=True)
        for filename in files:
            src = Path(root) / filename
            dst = dest_root / filename
            if dst.exists() and not overwrite:
                continue
            shutil.copy2(src, dst)
            copied += 1
    return copied


def _import_legacy(source: Path, target: Path, *, overwrite: bool,
                   reason: str) -> dict:
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()
    if source == target:
        return {"source": str(source), "copied": 0, "entries": [], "reason": reason}

    entries = _legacy_entries(source)
    copied = 0
    copied_entries = []
    target.mkdir(parents=True, exist_ok=True)

    for name in LEGACY_FILES:
        src = source / name
        if not src.is_file():
            continue
        dst = target / name
        if dst.exists() and not overwrite:
            continue
        shutil.copy2(src, dst)
        copied += 1
        copied_entries.append(name)

    for name in LEGACY_DIRS:
        src = source / name
        if not src.is_dir():
            continue
        before = copied
        copied += _copy_tree_merge(src, target / name, overwrite)
        if copied > before:
            copied_entries.append(name + "/")

    result = {
        "source": str(source),
        "copied": copied,
        "entries": copied_entries,
        "recognized_entries": entries,
        "overwrite": bool(overwrite),
        "reason": reason,
        "at": _utc_now(),
    }
    if copied:
        history_path = target / IMPORT_HISTORY_FILE
        history = _read_json(history_path, [])
        if not isinstance(history, list):
            history = []
        history.append(result)
        _write_json_atomic(history_path, history[-20:])
    return result


def _apply_pending_import(target: Path) -> dict | None:
    pending_path = target / PENDING_IMPORT_FILE
    pending = _read_json(pending_path, {})
    if not isinstance(pending, dict) or not pending.get("source"):
        return None
    source = Path(str(pending["source"]))
    try:
        result = _import_legacy(source, target, overwrite=True,
                                reason="user_staged_import")
        result["pending_requested_at"] = pending.get("requested_at", "")
        return result
    finally:
        try:
            pending_path.unlink(missing_ok=True)
        except Exception:
            pass


def _load_or_create_profile(target: Path) -> tuple[dict, bool]:
    profile_path = target / PROFILE_FILE
    profile = _read_json(profile_path, {})
    created = False
    if not isinstance(profile, dict) or not profile.get("profile_id"):
        profile = {
            "schema": PROFILE_SCHEMA,
            "profile_id": str(uuid.uuid4()),
            "created_at": _utc_now(),
            "kind": "local_windows_user",
        }
        created = True
    profile["schema"] = PROFILE_SCHEMA
    profile["last_opened_at"] = _utc_now()
    _write_json_atomic(profile_path, profile)
    return profile, created


def activate(application_dir=None) -> dict:
    """Activate the current Windows user's isolated WITNESS profile.

    Call this before importing WITNESS modules that use relative data paths.
    The function is idempotent within a process.
    """
    global _ACTIVE
    if _ACTIVE is not None:
        return dict(_ACTIVE)

    source = Path(application_dir or Path(__file__).resolve().parent).resolve()
    target = _default_data_dir()
    target.mkdir(parents=True, exist_ok=True)

    pending_result = _apply_pending_import(target)

    # Automatic legacy migration is intentionally conservative: only if this
    # profile has no canonical database yet.  A clean distribution contains no
    # user-data artifacts, so a new user's first launch remains empty.
    auto_result = None
    if not (target / "witness.db").exists():
        recognized = _legacy_entries(source)
        if recognized:
            auto_result = _import_legacy(source, target, overwrite=False,
                                         reason="automatic_same_folder_upgrade")

    profile, created = _load_or_create_profile(target)
    profile["last_app_dir"] = str(source)
    if pending_result and pending_result.get("copied"):
        profile["last_import_from"] = pending_result.get("source")
        profile["last_import_at"] = pending_result.get("at")
    elif auto_result and auto_result.get("copied"):
        profile["last_import_from"] = auto_result.get("source")
        profile["last_import_at"] = auto_result.get("at")
    _write_json_atomic(target / PROFILE_FILE, profile)

    os.environ["WITNESS_APP_DIR"] = str(source)
    os.environ["WITNESS_DATA_DIR"] = str(target)
    os.environ["WITNESS_PROFILE_ID"] = profile["profile_id"]

    # This single line isolates all historical relative data paths—including
    # paths inside frozen core/—without rewriting those modules.
    os.chdir(target)

    _ACTIVE = {
        "app_dir": str(source),
        "data_dir": str(target),
        "profile_id": profile["profile_id"],
        "profile_created": created,
        "auto_migration": auto_result,
        "pending_import_applied": pending_result,
    }
    return dict(_ACTIVE)


def current_profile() -> dict:
    root = data_dir()
    profile = _read_json(root / PROFILE_FILE, {})
    if not isinstance(profile, dict):
        profile = {}
    return {
        **profile,
        "data_dir": str(root),
        "app_dir": str(app_dir() or ""),
        "pending_import": pending_import(),
    }


def pending_import() -> dict | None:
    p = data_dir() / PENDING_IMPORT_FILE
    obj = _read_json(p, {})
    return obj if isinstance(obj, dict) and obj.get("source") else None


def stage_legacy_import(source) -> dict:
    """Stage an old WITNESS folder for import on the next launch.

    Import is deferred because the current process may have witness.db open.
    The next startup applies the copy *before* db.init(), so SQLite is never
    replaced underneath an open connection.
    """
    source = Path(source).expanduser().resolve()
    target = data_dir().resolve()
    if source == target:
        raise ValueError("That folder is already the active WITNESS data folder.")
    entries = _legacy_entries(source)
    if not entries:
        raise ValueError("No recognized WITNESS user data was found in that folder.")
    payload = {
        "source": str(source),
        "entries": entries,
        "requested_at": _utc_now(),
        "mode": "replace_conflicting_profile_data_on_restart",
    }
    _write_json_atomic(target / PENDING_IMPORT_FILE, payload)
    return payload


def cancel_pending_import() -> bool:
    p = data_dir() / PENDING_IMPORT_FILE
    try:
        p.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def open_data_folder() -> None:
    path = str(data_dir())
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
