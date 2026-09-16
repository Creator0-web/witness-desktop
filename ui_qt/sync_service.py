"""Qt wrapper around shared/sync_engine.py.

All network and merge work runs off the GUI thread. The service is intentionally
small so the hosted provider can be swapped later without touching the shell.
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

import sync_engine
import profile_runtime


class SyncService(QObject):
    status_changed = Signal(dict)
    data_changed = Signal(dict)
    operation_finished = Signal(str, dict)
    error = Signal(str, str)
    _worker_ok = Signal(str, dict)
    _worker_error = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._lock = threading.Lock()
        self._worker_ok.connect(self._finish_ok)
        self._worker_error.connect(self._finish_error)
        self._timer = QTimer(self)
        self._timer.timeout.connect(lambda: self.sync_now(manual=False))
        self._timer.start(sync_engine.SYNC_INTERVAL_SECONDS * 1000)
        QTimer.singleShot(2200, lambda: self.sync_now(manual=False))
        self.emit_status()

    def emit_status(self):
        info = sync_engine.public_status()
        info["busy"] = bool(self._busy)
        self.status_changed.emit(info)

    def _start(self, operation: str, worker):
        with self._lock:
            if self._busy:
                if operation != "sync":
                    self.error.emit(operation, "WITNESS Sync is already working. Try again in a moment.")
                return False
            self._busy = True
        self.emit_status()

        def run():
            try:
                result = dict(worker() or {})
            except Exception as ex:
                try:
                    sync_engine.record_error(str(ex))
                except Exception:
                    pass
                self._worker_error.emit(str(operation), str(ex))
                return
            self._worker_ok.emit(str(operation), result)

        threading.Thread(target=run, name=f"witness-{operation}", daemon=True).start()
        return True

    def _finish_ok(self, operation, result):
        with self._lock:
            self._busy = False
        self.emit_status()
        if int(result.get("changed", 0) or 0) > 0 or operation in ("create", "link"):
            self.data_changed.emit(dict(result))
        self.operation_finished.emit(str(operation), dict(result))

    def _finish_error(self, operation, message):
        with self._lock:
            self._busy = False
        self.emit_status()
        self.error.emit(str(operation), str(message))

    def sync_now(self, manual=True):
        if not sync_engine.is_linked():
            if manual:
                self.error.emit("sync", "This device is not linked to a WITNESS Sync profile yet.")
            return False
        return self._start("sync_manual" if manual else "sync", sync_engine.sync_once)

    def create_profile(self, url, publishable_key):
        def worker():
            out = sync_engine.create_profile(url, publishable_key)
            first = sync_engine.sync_once()
            return {**out, **first, "link_code": sync_engine.encode_link_code()}
        return self._start("create", worker)

    def link_profile(self, code):
        def worker():
            # Linking is replacement, not a blind merge. A compact safety backup
            # is created first so a user cannot accidentally destroy a local run.
            profile_runtime.create_backup(reason="before-sync-link", force=True)
            out = sync_engine.link_profile(code, replace_local=True)
            first = sync_engine.sync_once()
            return {**out, **first, "link_code": sync_engine.encode_link_code()}
        return self._start("link", worker)

    def unlink_local(self):
        try:
            sync_engine.unlink_local()
        except Exception as ex:
            self.error.emit("unlink", str(ex)); return
        self.emit_status()
        self.operation_finished.emit("unlink", {"ok": True})
