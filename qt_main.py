"""WITNESS PySide6 desktop shell — v7.57.3 Factory Reset Reliability + Triangle Branding.

This is a deliberate parallel frontend during the migration away from Tkinter.
It reads/writes the exact same canonical SQLite/game_engine backend established in v7.43.
The legacy main.py remains a fallback/reference UI. The Qt app now starts the frozen
active-window tracker plus the rapid ScreenVision guard and delivers their protection through modern Qt surfaces. Both entry points now activate the same per-Windows-user data profile.
"""
import os
import sys

BASE = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
import profile_runtime
PROFILE = profile_runtime.activate(BASE)
for sub in ("core", "character", "shared", "_archive", "insight"):
    path = os.path.join(BASE, sub)
    if path not in sys.path:
        sys.path.insert(0, path)


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WITNESS.Desktop")
        except Exception:
            pass

    try:
        import secrets_store
        secrets_store.load_all()
    except Exception:
        pass

    import db
    import game_engine
    # Packaging contract: the canonical DB module is shared/db.py.  A stale
    # legacy root-level db.py used to be able to shadow it in a contaminated
    # source/install folder, producing a cryptic AttributeError at startup.
    required_db_api = ("game_state_get", "game_state_set",
                       "list_scoring_activities", "log_xp_event")
    missing_db_api = [name for name in required_db_api if not hasattr(db, name)]
    if missing_db_api:
        origin = getattr(db, "__file__", "<frozen module>")
        raise RuntimeError(
            "WITNESS loaded the wrong database module from " + str(origin) +
            ". Missing canonical DB API: " + ", ".join(missing_db_api))
    db.init()
    init_result = game_engine.initialize()
    if PROFILE.get("factory_reset_applied"):
        level = dict(init_result.get("level") or {})
        if int(level.get("current_level", 1) or 1) != 1 or int(level.get("rating", 0) or 0) != 0:
            raise RuntimeError(
                "Factory reset verification failed: the new profile did not start at Level 1 / 0 XP."
            )

    # Crash recovery is deliberately local and non-destructive: keep a session
    # marker, write a traceback on uncaught Python exceptions, and let the next
    # launch surface the existing rotating backup rather than auto-overwriting data.
    def _witness_excepthook(exc_type, exc, tb):
        try:
            profile_runtime.write_crash_report(exc_type, exc, tb)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)
    sys.excepthook = _witness_excepthook
    profile_runtime.start_session()

    try:
        from pathlib import Path
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Run install.bat, then try again.")
        raise

    from ui_qt.shell import WitnessMainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("WITNESS")
    app.setOrganizationName("WITNESS")
    resource_root = Path(getattr(sys, "_MEIPASS", BASE))
    icon_path = resource_root / "ui_qt" / "assets" / "branding" / "witness.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.aboutToQuit.connect(profile_runtime.end_session)
    smoke_test = "--smoke-test" in sys.argv
    win = WitnessMainWindow(start_protection=not smoke_test)
    app.aboutToQuit.connect(win.shutdown)
    if smoke_test:
        marker = os.environ.get("WITNESS_SMOKE_MARKER", "").strip()
        if marker:
            try:
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("ok\n")
            except OSError:
                return 97
        # Used by the Windows release pipeline. Offscreen Qt constructs the real
        # shell/backend and exits quickly without creating a distributable DB.
        win.hide()
        QTimer.singleShot(250, app.quit)
        try:
            return app.exec()
        finally:
            profile_runtime.end_session()
    win.show()
    try:
        return app.exec()
    finally:
        profile_runtime.end_session()


if __name__ == "__main__":
    raise SystemExit(main())
