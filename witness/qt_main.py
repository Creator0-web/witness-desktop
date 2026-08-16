"""WITNESS PySide6 visual shell — v7.52 Desktop Distribution Foundation.

This is a deliberate parallel frontend during the migration away from Tkinter.
It reads/writes the exact same canonical SQLite/game_engine backend established in v7.43.
The legacy main.py remains the fallback/reference UI while the Qt surface is proven
screen-by-screen. Both entry points now activate the same per-Windows-user data profile.
"""
import os
import sys

BASE = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
from profile_runtime import activate as _activate_profile
PROFILE = _activate_profile(BASE)
for sub in ("core", "character", "shared", "_archive", "insight"):
    path = os.path.join(BASE, sub)
    if path not in sys.path:
        sys.path.insert(0, path)


def main():
    try:
        import secrets_store
        secrets_store.load_all()
    except Exception:
        pass

    import db
    import game_engine
    db.init()
    game_engine.initialize()

    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Run install.bat, then try again.")
        raise

    from ui_qt.shell import WitnessMainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("WITNESS")
    app.setOrganizationName("WITNESS")
    win = WitnessMainWindow()
    if "--smoke-test" in sys.argv:
        # Used by the Windows release pipeline. Offscreen Qt constructs the real
        # shell/backend and exits quickly without creating a distributable DB.
        win.hide()
        QTimer.singleShot(250, app.quit)
        return app.exec()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
