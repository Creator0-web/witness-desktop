"""Qt delivery bridge for the proven Layer-1 protection runtime.

This module intentionally does NOT reimplement drift detection. It starts the
frozen ``core/tracker.py`` active-window tracker *and* the frozen
``core/vision.py`` ScreenVision guard used by the legacy full runtime. Their
red-line events are translated onto the Qt thread and reuse the existing
``core/nuclear.py`` + ``core/blocker.py`` response.

Only the delivery surface is modern Qt. No XP is awarded here; WITNESS scoring
remains manual and explicit.
"""
from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

# Static imports are deliberate: PyInstaller can discover the Windows runtime
# dependencies.  Development on non-Windows machines may not have pywin32, so
# tracker import is allowed to fail there without breaking the Qt shell.
try:
    from tracker import WindowTracker
except Exception:  # pragma: no cover - expected on non-Windows dev hosts
    WindowTracker = None

try:
    from vision import ScreenVision
except Exception:  # pragma: no cover - defensive packaging/runtime fallback
    ScreenVision = None

import blocker
import config
import db
import nuclear
import trail

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_AVAILABLE = True
except Exception:  # pragma: no cover - defensive fallback
    QAudioOutput = QMediaPlayer = QVideoWidget = None
    MULTIMEDIA_AVAILABLE = False


# Preserves the old full-runtime hard whitelist.  A safe work/service title that
# happens to contain a red-line word must never trigger browser termination.
NEVER_REDLINE = (
    "google drive", "google docs", "google sheets", "gmail",
    "booking koala", "vonage", "thumbtack", "calendar",
    "github", "stackoverflow", "claude", "anthropic",
    "microsoft", "office", "outlook", "word", "excel",
    "witness", "spotify", "pandora", "apple music",
    "amazon", "ebay", "walmart", "linkedin",
    "slack", "zoom", "teams", "discord", "whatsapp",
    "wikipedia", "maps", "weather", "bank", "chase",
    "paypal", "stripe", "shopify", "canva",
    "gohighlevel", "highlevel", "youtube music",
    "file explorer", "notepad", "task manager",
)

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


def sos_videos() -> list[Path]:
    root = Path(config.SOS_VIDEO_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return sorted(
        (p.resolve() for p in root.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda p: p.name.lower(),
    )


def open_sos_folder() -> None:
    root = Path(config.SOS_VIDEO_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(root))  # type: ignore[attr-defined]
        return
    import subprocess
    import sys
    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(root)])


class ProtectionRuntime(QObject):
    """Bridge frozen WindowTracker + ScreenVision protection into Qt-safe signals."""

    status_changed = Signal(str, bool)
    drift_stage = Signal(int, str, str)
    drift_checkin = Signal(str, str)
    redline_detected = Signal(str, str)
    redline_actions = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = {
            "present": True,
            "camera_ok": None,
            "stop": False,
            "muted": False,
            "current_app": "",
            "current_title": "",
            "deep_work_until": 0,
            "idle_seconds": 0,
            "input_active": True,
        }
        self.events: queue.Queue = queue.Queue()
        self.tracker = None
        self.screen_vision = None
        self._running = False
        self._redline_busy = False
        self.poll = QTimer(self)
        self.poll.setInterval(250)
        self.poll.timeout.connect(self._drain)
        self.lock_poll = QTimer(self)
        self.lock_poll.setInterval(60_000)
        self.lock_poll.timeout.connect(self._refresh_lock)

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        if os.name != "nt":
            self.status_changed.emit("PROTECTION · WINDOWS ONLY", False)
            return
        if WindowTracker is None:
            self.status_changed.emit("PROTECTION · RUNTIME MISSING", False)
            return
        try:
            self.state["stop"] = False
            self.tracker = WindowTracker(self.state, self.events)
            self.tracker.start()

            # Restore the old full-runtime screen guard exactly as it existed:
            # ScreenVision owns its adaptive trust cadence, two-flag confirmation,
            # incident history and vision prompt. Qt only supplies the callback.
            vision_ready = False
            if ScreenVision is not None and os.environ.get("ANTHROPIC_API_KEY"):
                self.screen_vision = ScreenVision(self.state, self._vision_redline)
                self.screen_vision.start()
                vision_ready = True

            self._running = True
            self.poll.start()
            self.lock_poll.start()
            self._refresh_lock()
            self.status_changed.emit(
                "PROTECTION · ACTIVE · SCREEN GUARD" if vision_ready
                else "PROTECTION · ACTIVE · TITLE ONLY",
                True,
            )
        except Exception as ex:
            self.status_changed.emit("PROTECTION · ERROR", False)
            self.redline_actions.emit({"error": str(ex)})

    def stop(self) -> None:
        self.state["stop"] = True
        self.poll.stop()
        self.lock_poll.stop()
        self._running = False

    def _refresh_lock(self) -> None:
        # Polling is important after a restart: the legacy blocker timer lived in
        # the process that originally created the lock. is_blocked() also cleans
        # an expired hosts entry, so this keeps timed locks self-healing.
        try:
            blocker.is_blocked()
        except Exception:
            pass

    def _drain(self) -> None:
        for _ in range(12):
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            try:
                self._dispatch(ev)
            except Exception:
                # Protection polling must never take down the application shell.
                continue

    def _dispatch(self, ev) -> None:
        if not isinstance(ev, tuple) or not ev:
            return
        kind = ev[0]
        if kind == "speak_escalation" and len(ev) >= 4:
            self.drift_stage.emit(int(ev[1]), str(ev[2]), str(ev[3]))
            return
        if kind != "checkin" or len(ev) < 4:
            return
        check_kind, proc, title = str(ev[1]), str(ev[2]), str(ev[3])
        if check_kind == "redline":
            self._request_redline(proc, title)
        elif check_kind in ("drift", "offtask", "routine"):
            self.drift_checkin.emit(proc, title)

    def _vision_redline(self, proc: str, title: str) -> None:
        # Called from frozen ScreenVision's worker thread after its original
        # two-consecutive-FLAG confirmation. Keep the same whitelist that the
        # legacy Tk nuclear_response() applied before browser termination.
        self._request_redline(str(proc), str(title))

    def _request_redline(self, proc: str, title: str) -> None:
        blob = f"{proc} {title}".lower()
        if any(safe in blob for safe in NEVER_REDLINE):
            return
        if self._redline_busy:
            return
        self._redline_busy = True
        self.redline_detected.emit(proc, title)
        threading.Thread(
            target=self._execute_redline, args=(proc, title), daemon=True,
            name="witness-redline",
        ).start()

    def _execute_redline(self, proc: str, title: str) -> None:
        result = {
            "process": proc,
            "title": title,
            "killed": [],
            "block_ok": False,
            "block_message": "",
        }
        try:
            try:
                trail.record_incident()
            except Exception:
                pass
            result["killed"] = nuclear.kill_browsers()
            try:
                ok, message = blocker.block_sites(duration_min=120)
                result["block_ok"] = bool(ok)
                result["block_message"] = str(message)
            except Exception as ex:
                result["block_message"] = str(ex)
            try:
                nuclear.log_intervention("browser_kill", False)
            except Exception:
                pass
        except Exception as ex:
            result["error"] = str(ex)
        finally:
            self._redline_busy = False
            self.redline_actions.emit(result)

    def mark_walked_away(self) -> None:
        try:
            nuclear.log_intervention("walked_away", True)
            db.log_sos("red-line nuclear response", "walked away — won")
        except Exception:
            pass


class DriftNotice(QDialog):
    """Small top-most drift escalation that does not interrupt normal work."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setModal(False)
        self.setFixedSize(500, 160)
        self.setObjectName("ProtectionNotice")
        self.setStyleSheet(
            "QDialog#ProtectionNotice{background:#0b0d0f;border:1px solid #663238;border-radius:10px;}"
            "QLabel{background:transparent;}"
        )
        lay = QVBoxLayout(self); lay.setContentsMargins(20, 17, 20, 17); lay.setSpacing(7)
        self.eyebrow = QLabel("DRIFT DETECTED"); self.eyebrow.setObjectName("Red")
        self.head = QLabel("Close the distraction while the choice is still easy.")
        self.head.setStyleSheet("font-size:16px;font-weight:850;")
        self.detail = QLabel(""); self.detail.setObjectName("Muted"); self.detail.setWordWrap(True)
        lay.addWidget(self.eyebrow); lay.addWidget(self.head); lay.addWidget(self.detail)
        self.hide_timer = QTimer(self); self.hide_timer.setSingleShot(True); self.hide_timer.timeout.connect(self.hide)

    def show_stage(self, stage: int, proc: str, title: str) -> None:
        stage = max(0, min(2, int(stage)))
        lines = (
            "You crossed the drift threshold. Close it now.",
            "This is becoming a pattern. Cut it before momentum builds.",
            "Final warning before WITNESS opens the intervention screen.",
        )
        self.eyebrow.setText(f"DRIFT PROTECTION · {stage + 1}/3")
        self.head.setText(lines[stage])
        clean = (title or proc or "Distracting window").strip()
        self.detail.setText(clean[:120])
        if self.parentWidget():
            g = self.parentWidget().frameGeometry()
            self.move(g.right() - self.width() - 34, g.top() + 74)
        self.show(); self.raise_(); self.activateWindow()
        self.hide_timer.start(8_000 if stage < 2 else 12_000)


class ProtectionDialog(QDialog):
    """Modern drift/red-line intervention with an embedded local SOS video."""

    walked_away = Signal()

    def __init__(self, parent=None, *, hard_lock=False, preview=False):
        super().__init__(parent)
        self.hard_lock = bool(hard_lock)
        self.preview = bool(preview)
        self._allow_close = not self.hard_lock
        self._videos = sos_videos()
        self._video_index = 0
        self._autoplay_started = False
        self.setWindowTitle("WITNESS · PROTECTION")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setModal(self.hard_lock)
        self.resize(920, 720)
        self.setMinimumSize(760, 610)
        self.setObjectName("ProtectionDialog")
        self.setStyleSheet(
            "QDialog#ProtectionDialog{background:#080a0c;}"
            "QFrame#ProtectionHero{background:#0d1013;border:1px solid #3b2529;border-radius:12px;}"
            "QFrame#VideoFrame{background:#030405;border:1px solid #20262b;border-radius:10px;}"
            "QLabel{background:transparent;}"
        )

        outer = QVBoxLayout(self); outer.setContentsMargins(24, 22, 24, 22); outer.setSpacing(13)
        hero = QFrame(); hero.setObjectName("ProtectionHero")
        hl = QVBoxLayout(hero); hl.setContentsMargins(20, 18, 20, 18); hl.setSpacing(6)
        self.kicker = QLabel("RED LINE INTERRUPTED" if hard_lock else "DRIFT INTERRUPTED")
        self.kicker.setObjectName("Red" if hard_lock else "Gold")
        self.title = QLabel(
            "The browser is being shut down. Break the sequence now."
            if hard_lock else "You have been off course long enough for WITNESS to step in."
        )
        self.title.setStyleSheet("font-size:22px;font-weight:900;")
        self.title.setWordWrap(True)
        self.source = QLabel(""); self.source.setObjectName("Muted"); self.source.setWordWrap(True)
        self.action_status = QLabel(
            "PREVIEW · no browser action will be taken."
            if preview else ("Closing browser · applying protection…" if hard_lock else "No score penalty. The only objective is to return deliberately.")
        )
        self.action_status.setObjectName("Secondary"); self.action_status.setWordWrap(True)
        hl.addWidget(self.kicker); hl.addWidget(self.title); hl.addWidget(self.source); hl.addWidget(self.action_status)
        outer.addWidget(hero)

        vf = QFrame(); vf.setObjectName("VideoFrame")
        vl = QVBoxLayout(vf); vl.setContentsMargins(8, 8, 8, 8)
        self.video_label = QLabel("")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setObjectName("Muted")
        self.video_label.setWordWrap(True)
        self.video_widget = None; self.player = None; self.audio_output = None
        if MULTIMEDIA_AVAILABLE:
            self.video_widget = QVideoWidget()
            self.video_widget.setMinimumHeight(330)
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.audio_output.setVolume(0.9)
            self.player.setAudioOutput(self.audio_output)
            self.player.setVideoOutput(self.video_widget)
            vl.addWidget(self.video_widget, 1)
        else:
            vl.addWidget(self.video_label, 1)
        vl.addWidget(self.video_label)
        outer.addWidget(vf, 1)

        controls = QHBoxLayout(); controls.setSpacing(9)
        self.next_btn = QPushButton("NEXT RESET VIDEO")
        self.next_btn.clicked.connect(self.play_next_video)
        controls.addWidget(self.next_btn)
        controls.addStretch(1)
        self.walk_btn = QPushButton("I'M WALKING AWAY" if hard_lock else "RETURN TO WORK")
        self.walk_btn.setObjectName("Primary")
        self.walk_btn.clicked.connect(self._finish)
        controls.addWidget(self.walk_btn)
        outer.addLayout(controls)

        self._update_video_empty_state()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Autoplay only after the native video surface is visible. This is more
        # reliable on Windows than arming playback from __init__, and it applies
        # to both real interventions and the Settings preview.
        if self._videos and not self._autoplay_started:
            self._autoplay_started = True
            QTimer.singleShot(120, self.play_next_video)

    def set_source(self, proc: str, title: str) -> None:
        clean = (title or proc or "Detected window").strip()
        self.source.setText(f"Detected · {clean[:160]}")

    def set_action_result(self, result: dict) -> None:
        if self.preview:
            return
        killed = result.get("killed") or []
        killed_text = "Browser closed" if killed else "Browser close attempted"
        if result.get("block_ok"):
            lock_text = "sites locked for 120 minutes"
        else:
            msg = str(result.get("block_message") or "site lock unavailable")
            lock_text = "site lock unavailable" if not msg else msg
        self.action_status.setText(f"{killed_text} · {lock_text}")

    def _update_video_empty_state(self) -> None:
        if self._videos:
            self.video_label.setText(f"{len(self._videos)} local reset video(s) ready")
            self.next_btn.setEnabled(True)
        else:
            self.video_label.setText(
                "No SOS videos yet. Add personal reset videos in SETTINGS → PROTECTION.\n"
                "The protection system still works without video."
            )
            self.next_btn.setEnabled(False)

    def play_next_video(self) -> None:
        self._videos = sos_videos()
        if not self._videos:
            self._update_video_empty_state(); return
        path = self._videos[self._video_index % len(self._videos)]
        self._video_index += 1
        self.video_label.setText(path.name)
        if self.player is not None:
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.play()
            return
        if os.name == "nt":
            try:
                os.startfile(str(path))  # type: ignore[attr-defined]
            except Exception:
                pass

    def _finish(self) -> None:
        if self.player is not None:
            self.player.stop()
        if self.hard_lock and not self.preview:
            self.walked_away.emit()
        self._allow_close = True
        self.accept()

    def reject(self) -> None:
        if self.hard_lock and not self._allow_close:
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self.hard_lock and not self._allow_close:
            event.ignore()
            return
        if self.player is not None:
            self.player.stop()
        super().closeEvent(event)
