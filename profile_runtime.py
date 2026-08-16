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
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "WITNESS"
PROFILE_SCHEMA = 1
PROFILE_FILE = "profile.json"
PENDING_IMPORT_FILE = ".pending_legacy_import.json"
IMPORT_HISTORY_FILE = "import_history.json"
BACKUP_DIR = "Backups"
CRASH_DIR = "crash_reports"
RESTORE_STAGING_DIR = ".restore_staging"
SESSION_FILE = ".session_active.json"
BACKUP_KEEP = 7
BACKUP_MIN_INTERVAL_HOURS = 12

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

# Small/critical directories included in automatic rotating backups. Large media
# stays out of automatic backups so startup remains fast; explicit Profile Export
# can include it. API secrets are never placed in backups/exports.
AUTO_BACKUP_DIRS = ("recaps", "day_breakdown_data", "insight_data", "journals")

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
        # Restore archives are extracted into a disposable staging folder.
        # Remove only that staging copy after the next-launch import completes.
        try:
            restore_root = (target / RESTORE_STAGING_DIR).resolve()
            resolved = source.resolve()
            if restore_root in resolved.parents:
                shutil.rmtree(resolved, ignore_errors=True)
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



def _safe_zip_member(name: str) -> bool:
    """Reject absolute/traversal paths before extracting a restore archive."""
    raw = str(name or "").replace("\\", "/")
    if not raw or raw.startswith("/"):
        return False
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    return bool(parts) and ".." not in parts


def _snapshot_database(source: Path, destination: Path) -> bool:
    """Create a transaction-consistent SQLite snapshot, even while WITNESS is open."""
    if not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=5)
        dst = sqlite3.connect(str(destination), timeout=5)
        try:
            src.backup(dst)
        finally:
            dst.close(); src.close()
        return True
    except Exception:
        try:
            shutil.copy2(source, destination)
            return True
        except Exception:
            return False


def _iter_export_paths(root: Path, *, include_media: bool) -> list[Path]:
    excluded_names = {
        "secrets.json", SESSION_FILE, PENDING_IMPORT_FILE,
    }
    excluded_dirs = {BACKUP_DIR, CRASH_DIR, RESTORE_STAGING_DIR, ".backup_tmp", "Updates", "release-quarantine"}
    out: list[Path] = []
    for child in root.iterdir() if root.exists() else []:
        if child.name in excluded_names or child.name in excluded_dirs:
            continue
        if child.name == "witness.db":
            continue
        if child.is_file():
            out.append(child)
            continue
        if child.is_dir():
            if not include_media and child.name not in AUTO_BACKUP_DIRS:
                continue
            for path in child.rglob("*"):
                if path.is_file():
                    out.append(path)
    return out


def _write_profile_archive(root: Path, destination: Path, *, reason: str,
                           include_media: bool) -> dict:
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = root / ".backup_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_snapshot = tmp_dir / f"witness-{uuid.uuid4().hex}.db"
    db_ok = _snapshot_database(root / "witness.db", db_snapshot)
    manifest = {
        "format": "WITNESS_PROFILE_BACKUP_V1",
        "created_at": _utc_now(),
        "reason": reason,
        "include_media": bool(include_media),
        "secrets_included": False,
    }
    tmp_zip = destination.with_name(destination.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2))
            if db_ok:
                zf.write(db_snapshot, "witness.db")
            for path in _iter_export_paths(root, include_media=include_media):
                try:
                    if path.resolve() in {destination, tmp_zip.resolve(), db_snapshot.resolve()}:
                        continue
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                if rel == "backup_manifest.json":
                    continue
                zf.write(path, rel)
        os.replace(tmp_zip, destination)
    finally:
        try:
            db_snapshot.unlink(missing_ok=True)
            tmp_zip.unlink(missing_ok=True)
            if tmp_dir.exists() and not any(tmp_dir.iterdir()):
                tmp_dir.rmdir()
        except Exception:
            pass
    return {**manifest, "path": str(destination), "database_included": bool(db_ok)}


def _backup_files(root: Path) -> list[Path]:
    folder = root / BACKUP_DIR
    if not folder.exists():
        return []
    return sorted((p for p in folder.glob("witness-backup-*.zip") if p.is_file()),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def create_backup(*, reason="manual", force=True, max_backups=BACKUP_KEEP) -> dict:
    """Create a compact rotating local backup of critical WITNESS state.

    Backups intentionally exclude `secrets.json` and large media folders. Use
    `export_profile()` for a user-requested full portable export.
    """
    root = data_dir().resolve()
    if not (root / "witness.db").exists():
        return {"created": False, "reason": "no database yet", "path": ""}
    existing = _backup_files(root)
    if not force and existing:
        age = time.time() - existing[0].stat().st_mtime
        if age < BACKUP_MIN_INTERVAL_HOURS * 3600:
            return {"created": False, "reason": "recent backup exists", "path": str(existing[0])}
    folder = root / BACKUP_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = folder / f"witness-backup-{stamp}.zip"
    result = _write_profile_archive(root, target, reason=str(reason), include_media=False)
    result["created"] = True
    for old in _backup_files(root)[max(1, int(max_backups)):]:
        try:
            old.unlink()
        except Exception:
            pass
    return result


def maybe_create_startup_backup(*, force=False, reason="startup") -> dict:
    return create_backup(reason=reason, force=bool(force), max_backups=BACKUP_KEEP)


def backup_status() -> dict:
    files = _backup_files(data_dir().resolve())
    latest = files[0] if files else None
    return {
        "count": len(files),
        "latest": str(latest) if latest else "",
        "latest_name": latest.name if latest else "",
        "latest_at": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec="minutes") if latest else "",
        "folder": str((data_dir() / BACKUP_DIR).resolve()),
    }


def open_backups_folder() -> None:
    folder = (data_dir() / BACKUP_DIR).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(folder))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


def export_profile(destination, *, include_media=True) -> dict:
    """Write a portable profile archive. API secrets are intentionally excluded."""
    dest = Path(destination).expanduser().resolve()
    if dest.suffix.lower() != ".zip":
        dest = dest.with_suffix(".zip")
    result = _write_profile_archive(data_dir().resolve(), dest, reason="user_export",
                                    include_media=bool(include_media))
    result["created"] = True
    return result


def stage_backup_restore(archive) -> dict:
    """Safely extract a WITNESS backup and stage its recognized data for next launch."""
    source = Path(archive).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Backup file was not found.")
    root = data_dir().resolve()
    staging = root / RESTORE_STAGING_DIR / uuid.uuid4().hex
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(source, "r") as zf:
            members = zf.infolist()
            if not members or any(not _safe_zip_member(x.filename) for x in members):
                raise ValueError("That ZIP contains an unsafe path and cannot be restored.")
            names = {x.filename.replace("\\", "/") for x in members}
            if "witness.db" not in names and not any(name.rstrip("/") in LEGACY_FILES for name in names):
                raise ValueError("That ZIP does not look like a WITNESS profile backup.")
            for member in members:
                if member.is_dir():
                    continue
                # Never restore a secret from an archive into the active profile.
                normalized = member.filename.replace("\\", "/")
                if normalized == "secrets.json" or normalized.endswith("/secrets.json"):
                    continue
                target = (staging / normalized).resolve()
                if staging not in target.parents and target != staging:
                    raise ValueError("Unsafe backup path.")
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        entries = _legacy_entries(staging)
        if not entries:
            raise ValueError("No restorable WITNESS profile data was found in that backup.")
        payload = stage_legacy_import(staging)
        payload["backup_archive"] = str(source)
        return payload
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def start_session() -> dict:
    payload = {"pid": os.getpid(), "started_at": _utc_now(), "app_dir": str(app_dir() or "")}
    _write_json_atomic(data_dir() / SESSION_FILE, payload)
    return payload


def end_session() -> None:
    try:
        (data_dir() / SESSION_FILE).unlink(missing_ok=True)
    except Exception:
        pass


def write_crash_report(exc_type, exc, tb) -> str:
    folder = data_dir() / CRASH_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = folder / f"crash-{stamp}.txt"
    try:
        text = "WITNESS crash report\n" + _utc_now() + "\n\n" + "".join(
            traceback.format_exception(exc_type, exc, tb))
        path.write_text(text, encoding="utf-8", errors="replace")
        return str(path)
    except Exception:
        return ""


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

    previous_unclean = (target / SESSION_FILE).is_file()
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

    # Back up critical state before the DB is opened. A previous unclean session
    # forces a fresh recovery snapshot; normal launches are rate-limited.
    auto_backup = None
    try:
        old_active = _ACTIVE
        _ACTIVE = {"app_dir": str(source), "data_dir": str(target), "profile_id": profile["profile_id"]}
        auto_backup = maybe_create_startup_backup(
            force=previous_unclean, reason="crash-recovery" if previous_unclean else "startup")
    except Exception as ex:
        auto_backup = {"created": False, "reason": f"backup error: {ex}", "path": ""}
    finally:
        _ACTIVE = old_active
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
        "previous_unclean_shutdown": bool(previous_unclean),
        "startup_backup": auto_backup,
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
        "previous_unclean_shutdown": bool((_ACTIVE or {}).get("previous_unclean_shutdown", False)),
        "startup_backup": (_ACTIVE or {}).get("startup_backup"),
        "backup": backup_status(),
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
