"""Qt bridge for the dependency-free update manager.

All network and file download work stays off the GUI thread. Signal delivery
returns to Qt's event loop so the Arena remains responsive.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

import update_manager


class UpdateService(QObject):
    checked = Signal(object)
    available = Signal(object)
    progress = Signal(int)
    downloaded = Signal(str, object)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checking = False
        self._downloading = False

    def check(self, *, silent: bool = True):
        if self._checking:
            return
        self._checking = True

        def worker():
            try:
                result = update_manager.check_latest()
                self.checked.emit(result)
                if result.get("available"):
                    self.available.emit(result)
            except Exception as ex:
                if not silent:
                    self.error.emit(str(ex))
            finally:
                self._checking = False

        threading.Thread(target=worker, name="witness-update-check", daemon=True).start()

    def download(self, release: dict):
        if self._downloading:
            return
        self._downloading = True

        def worker():
            try:
                path = update_manager.download_update(
                    release, progress=lambda p: self.progress.emit(int(p)))
                self.downloaded.emit(str(path), release)
            except Exception as ex:
                self.error.emit(str(ex))
            finally:
                self._downloading = False

        threading.Thread(target=worker, name="witness-update-download", daemon=True).start()
