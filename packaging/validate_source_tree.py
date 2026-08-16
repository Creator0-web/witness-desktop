"""Fail a desktop release if stale legacy files can shadow canonical modules.

The project historically kept many modules at the repository root.  They now
live under shared/, core/, character/, insight/ and _archive/.  A dirty source
checkout can therefore look valid in Git while still make PyInstaller resolve
an old root-level module such as db.py.  Release builds run this check before
PyInstaller so that condition cannot ship again.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

# These names have canonical homes in subfolders and must not exist at root.
FORBIDDEN_ROOT_SHADOWS = {
    "ai.py", "blocker.py", "camera.py", "camtest.py", "chat.py",
    "chattest.py", "config.py", "correlations.py", "data.py", "db.py",
    "difficulty.py", "export.py", "finance.py", "habits.py", "journal.py",
    "lifedata.py", "memory.py", "mic.py", "patterns.py", "pipeline.py",
    "presence.py", "score.py", "stats_engine.py", "strategist.py",
    "timeutil.py", "tracker.py", "video_memories.py", "voice.py",
    "weekly.py", "xp_triggers.py",
}

FORBIDDEN_DATA = {
    "witness.db", "witness_data.json", "secrets.json", "profile.json",
    "import_history.json", ".pending_legacy_import.json", ".session_active.json",
    "progression.json", "conversation.json", "xp_triggers.json", "xp_triggers_fired.json",
    "ui_settings.json", "vision_history.json", "trail_history.json", "stats_model.json",
    "life_data.json", "block_lock.txt",
}
FORBIDDEN_RUNTIME_DIRS = {
    "recaps", "sos_videos", "video_memories", "day_breakdown_data", "insight_data",
    "journals", "Backups", "crash_reports", ".restore_staging", ".backup_tmp",
}


def main() -> int:
    problems: list[str] = []

    for name in sorted(FORBIDDEN_ROOT_SHADOWS):
        if (ROOT / name).is_file():
            problems.append(f"stale root module: {name}")

    for name in sorted(FORBIDDEN_DATA):
        if (ROOT / name).exists():
            problems.append(f"personal/runtime artifact in source root: {name}")
    for name in sorted(FORBIDDEN_RUNTIME_DIRS):
        if (ROOT / name).exists():
            problems.append(f"personal/runtime directory in source root: {name}/")

    for p in ROOT.rglob("__pycache__"):
        if ".git" not in p.parts:
            problems.append(f"python cache directory: {p.relative_to(ROOT)}")
    for p in ROOT.rglob("*.pyc"):
        if ".git" not in p.parts:
            problems.append(f"compiled Python cache: {p.relative_to(ROOT)}")

    canonical_db = ROOT / "shared" / "db.py"
    if not canonical_db.is_file():
        problems.append("missing canonical shared/db.py")
    else:
        text = canonical_db.read_text(encoding="utf-8", errors="replace")
        for token in ("def game_state_get", "def game_state_set",
                      "def list_scoring_activities", "def log_xp_event"):
            if token not in text:
                problems.append(f"shared/db.py missing required API token: {token}")

    if problems:
        print("WITNESS release source validation FAILED:", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        print("Run packaging/clean_repository.ps1, review the deletions, then commit.",
              file=sys.stderr)
        return 2

    print("WITNESS release source validation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
