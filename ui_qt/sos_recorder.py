from __future__ import annotations

"""Native WITNESS SOS recording studio.

This is deliberately a delivery-layer feature. It records user-created reset
videos locally and saves the accepted recording into ``sos_videos/``. It does
not change drift detection or any Layer-1 protection behavior.

Three capture modes are supported through Qt Multimedia:
- webcam + microphone
- selected screen + microphone
- selected screen + microphone with a live webcam overlay that is physically
  placed on the captured screen (square or triangle)

The screen-mode stop controller asks Windows to exclude that tiny control
window from supported capture APIs. That is a best-effort presentation detail;
recording never depends on the exclusion succeeding.
"""

import ctypes
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPolygon, QRegion
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from . import theme

try:
    from PySide6.QtMultimedia import (
        QAudioInput, QCamera, QMediaCaptureSession, QMediaDevices,
        QMediaFormat, QMediaRecorder, QScreenCapture,
    )
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_RECORDING_AVAILABLE = True
except Exception:  # pragma: no cover - only exercised on incomplete Qt installs
    QAudioInput = QCamera = QMediaCaptureSession = QMediaDevices = None
    QMediaFormat = QMediaRecorder = QScreenCapture = QVideoWidget = None
    MULTIMEDIA_RECORDING_AVAILABLE = False


SOS_DIR = Path("sos_videos")


def _fmt_duration(ms: int) -> str:
    total = max(0, int(ms) // 1000)
    return f"{total // 60:02d}:{total % 60:02d}"


def _safe_slug(text: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "recording"


def _exclude_window_from_capture(widget: QWidget) -> bool:
    """Best-effort Windows-only WDA_EXCLUDEFROMCAPTURE for recorder controls."""
    if os.name != "nt":
        return False
    try:
        # Windows 10 2004+: intended specifically for on-screen recording controls.
        WDA_EXCLUDEFROMCAPTURE = 0x00000011
        hwnd = int(widget.winId())
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
    except Exception:
        return False


class RecordingControl(QWidget):
    stop_requested = Signal()

    def __init__(self, screen, parent=None):
        # Intentionally top-level so minimizing/hiding the studio does not hide it.
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                        Qt.WindowType.WindowStaysOnTopHint)
        self.setObjectName("RecordingControl")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        box = QFrame(self); box.setObjectName("RecControlBox")
        box.setStyleSheet(
            "QFrame#RecControlBox{background:#0a0c0f;border:1px solid #3b2529;border-radius:11px;}"
            "QLabel{background:transparent;}"
        )
        lay = QHBoxLayout(box); lay.setContentsMargins(12, 8, 9, 8); lay.setSpacing(8)
        self.time = QLabel("● REC  00:00")
        self.time.setStyleSheet("color:#ff6b73;font-size:13px;font-weight:900;")
        stop = QPushButton("STOP")
        stop.setObjectName("Danger")
        stop.clicked.connect(self.stop_requested.emit)
        lay.addWidget(self.time); lay.addWidget(stop)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(box)
        self.adjustSize()
        self._screen = screen

    def showEvent(self, event):
        super().showEvent(event)
        _exclude_window_from_capture(self)
        self.position_on_screen()

    def position_on_screen(self):
        screen = self._screen or QGuiApplication.primaryScreen()
        if not screen:
            return
        g = screen.availableGeometry()
        self.move(g.right() - self.width() - 20, g.top() + 20)


class CameraOverlay(QWidget):
    """A real on-screen camera preview; screen capture records this as pixels."""

    def __init__(self, video_widget, screen, *, shape="square", corner="bottom-right"):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                        Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._screen = screen
        self._shape = shape
        self._corner = corner
        self.resize(270, 205)
        outer = QVBoxLayout(self); outer.setContentsMargins(4, 4, 4, 4)
        frame = QFrame(); frame.setObjectName("CameraOverlayFrame")
        frame.setStyleSheet(
            "QFrame#CameraOverlayFrame{background:#030405;border:2px solid #d7dde2;border-radius:12px;}"
        )
        fl = QVBoxLayout(frame); fl.setContentsMargins(2, 2, 2, 2)
        fl.addWidget(video_widget)
        outer.addWidget(frame)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_shape()
        self.position_on_screen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_shape()

    def _apply_shape(self):
        if self._shape == "triangle":
            # Upright triangle, intentionally bold and consistent with WITNESS branding.
            from PySide6.QtCore import QPoint
            p = QPolygon([QPoint(0, self.height()), QPoint(self.width(), self.height()),
                          QPoint(self.width() // 2, 0)])
            self.setMask(QRegion(p))
        else:
            self.clearMask()

    def position_on_screen(self):
        screen = self._screen or QGuiApplication.primaryScreen()
        if not screen:
            return
        g = screen.availableGeometry(); m = 26
        if self._corner == "top-left":
            x, y = g.left() + m, g.top() + m
        elif self._corner == "top-right":
            x, y = g.right() - self.width() - m, g.top() + m
        elif self._corner == "bottom-left":
            x, y = g.left() + m, g.bottom() - self.height() - m
        else:
            x, y = g.right() - self.width() - m, g.bottom() - self.height() - m
        self.move(x, y)


class SOSRecorderDialog(QDialog):
    """Record a local WITNESS video and submit it to SOS or a calendar day.

    ``destination`` is intentionally only a storage/presentation choice. The
    actual capture engine is shared so daily videos and SOS videos never drift
    into separate recorder implementations.
    """

    saved = Signal(str)

    MODE_CAMERA = "Webcam + Mic"
    MODE_SCREEN = "Screen + Mic"
    MODE_COMBINED = "Screen + Camera + Mic"

    def __init__(self, parent=None, *, destination="sos", target_day=None):
        super().__init__(parent)
        self.destination = "daily" if str(destination).lower() == "daily" else "sos"
        self.target_day = str(target_day or "") if self.destination == "daily" else ""
        self._daily = self.destination == "daily"
        self.setWindowTitle("WITNESS · DAILY VIDEO STUDIO" if self._daily else "WITNESS · SOS RECORDING STUDIO")
        # Modeless on purpose: screen-record mode hides the studio and leaves a
        # small independent STOP control that must remain clickable while the
        # user works in another application.
        self.setModal(False)
        self.resize(900, 690)
        self.setMinimumSize(780, 610)
        self.setObjectName("SOSRecorderDialog")
        self.setStyleSheet(
            "QDialog#SOSRecorderDialog{background:#080a0c;}"
            "QFrame#StudioCard{background:#0d1013;border:1px solid #22282e;border-radius:12px;}"
            "QFrame#PreviewFrame{background:#020304;border:1px solid #20262b;border-radius:10px;}"
            "QLabel{background:transparent;}"
        )

        self._session = None
        self._recorder = None
        self._audio = None
        self._camera = None
        self._screen_capture = None
        self._preview_session = None
        self._overlay_camera = None
        self._overlay_widget = None
        self._control = None
        self._draft_dir = None
        self._recorded_path = None
        self._recording = False
        self._stopping = False
        self._recorder_error = ""
        self._saved = False

        outer = QVBoxLayout(self); outer.setContentsMargins(22, 20, 22, 20); outer.setSpacing(12)
        hero = QFrame(); hero.setObjectName("StudioCard")
        hl = QVBoxLayout(hero); hl.setContentsMargins(18, 15, 18, 15); hl.setSpacing(4)
        kicker = QLabel("DAILY VIDEO MEMORY" if self._daily else "PERSONAL RESET VIDEO"); kicker.setObjectName("Eyebrow")
        if self._daily:
            title = QLabel(f"Record a memory for {self.target_day or 'this day'} without leaving WITNESS.")
            detail = QLabel("Everything stays local. Record, stop, then Submit. The accepted clip is attached directly to this calendar day.")
        else:
            title = QLabel("Record the message you want WITNESS to put in front of you when it matters.")
            detail = QLabel("Everything stays local. Record, stop, then Submit. WITNESS will add the accepted video directly to your SOS library.")
        title.setStyleSheet("font-size:20px;font-weight:900;"); title.setWordWrap(True)
        detail.setObjectName("Secondary"); detail.setWordWrap(True)
        hl.addWidget(kicker); hl.addWidget(title); hl.addWidget(detail); outer.addWidget(hero)

        mode_row = QHBoxLayout(); mode_row.setSpacing(8)
        self.mode_group = QButtonGroup(self); self.mode_group.setExclusive(True)
        self.mode_buttons = {}
        for idx, label in enumerate((self.MODE_CAMERA, self.MODE_SCREEN, self.MODE_COMBINED)):
            b = QPushButton(label.upper()); b.setCheckable(True); b.setObjectName("Primary" if idx == 0 else "")
            b.setChecked(idx == 0); self.mode_group.addButton(b); self.mode_buttons[label] = b; mode_row.addWidget(b)
            b.clicked.connect(self._mode_changed)
        mode_row.addStretch(1); outer.addLayout(mode_row)

        settings = QFrame(); settings.setObjectName("StudioCard")
        sl = QHBoxLayout(settings); sl.setContentsMargins(14, 10, 14, 10); sl.setSpacing(10)
        sl.addWidget(QLabel("SCREEN"))
        self.screen_combo = QComboBox(); sl.addWidget(self.screen_combo, 1)
        sl.addWidget(QLabel("CAM SHAPE"))
        self.shape_combo = QComboBox(); self.shape_combo.addItem("Square", "square"); self.shape_combo.addItem("Triangle", "triangle")
        sl.addWidget(self.shape_combo)
        sl.addWidget(QLabel("CORNER"))
        self.corner_combo = QComboBox()
        for text, value in (("Bottom Right", "bottom-right"), ("Bottom Left", "bottom-left"),
                            ("Top Right", "top-right"), ("Top Left", "top-left")):
            self.corner_combo.addItem(text, value)
        sl.addWidget(self.corner_combo)
        outer.addWidget(settings)

        self.preview_frame = QFrame(); self.preview_frame.setObjectName("PreviewFrame")
        pl = QVBoxLayout(self.preview_frame); pl.setContentsMargins(8, 8, 8, 8)
        self.preview_stack = QStackedWidget(); pl.addWidget(self.preview_stack)
        self.camera_preview = QVideoWidget() if MULTIMEDIA_RECORDING_AVAILABLE else QLabel("Camera unavailable")
        self.camera_preview.setMinimumHeight(330)
        self.preview_stack.addWidget(self.camera_preview)
        self.screen_preview = QLabel("SCREEN CAPTURE\n\nWhen recording starts, this studio hides and WITNESS records the selected display + microphone.\nA tiny STOP control remains visible; WITNESS asks Windows not to include that control in the capture.")
        self.screen_preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.screen_preview.setWordWrap(True); self.screen_preview.setObjectName("Secondary")
        self.preview_stack.addWidget(self.screen_preview)
        outer.addWidget(self.preview_frame, 1)

        bottom = QHBoxLayout(); bottom.setSpacing(8)
        self.status = QLabel("READY")
        self.status.setObjectName("Secondary")
        self.timer_label = QLabel("00:00"); self.timer_label.setStyleSheet("font-size:18px;font-weight:900;")
        bottom.addWidget(self.status, 1); bottom.addWidget(self.timer_label)
        self.rerecord_btn = QPushButton("RE-RECORD"); self.rerecord_btn.clicked.connect(self.reset_draft); self.rerecord_btn.hide()
        self.start_btn = QPushButton("● START RECORDING"); self.start_btn.setObjectName("Danger"); self.start_btn.clicked.connect(self.start_recording)
        self.stop_btn = QPushButton("■ STOP"); self.stop_btn.setObjectName("Danger"); self.stop_btn.clicked.connect(self.stop_recording); self.stop_btn.hide()
        self.submit_btn = QPushButton("SUBMIT TO DAY" if self._daily else "SUBMIT TO SOS"); self.submit_btn.setObjectName("Primary"); self.submit_btn.clicked.connect(self.submit_recording); self.submit_btn.setEnabled(False)
        bottom.addWidget(self.rerecord_btn); bottom.addWidget(self.start_btn); bottom.addWidget(self.stop_btn); bottom.addWidget(self.submit_btn)
        outer.addLayout(bottom)

        self._duration_timer = QTimer(self); self._duration_timer.setInterval(250); self._duration_timer.timeout.connect(self._sync_duration)
        self._load_screens()
        self._mode_changed()
        self._start_camera_preview()
        if not MULTIMEDIA_RECORDING_AVAILABLE:
            self.status.setText("Qt Multimedia recording support is unavailable in this build.")
            self.start_btn.setEnabled(False)

    # ---------- device / preview setup ----------
    def _load_screens(self):
        self.screen_combo.clear()
        screens = list(QGuiApplication.screens())
        primary = QGuiApplication.primaryScreen()
        for index, screen in enumerate(screens):
            name = screen.name() or f"Display {index + 1}"
            geom = screen.geometry()
            suffix = " · PRIMARY" if screen is primary else ""
            self.screen_combo.addItem(f"{name} · {geom.width()}×{geom.height()}{suffix}", screen)
            if screen is primary:
                self.screen_combo.setCurrentIndex(index)

    def _selected_mode(self):
        for label, button in self.mode_buttons.items():
            if button.isChecked():
                return label
        return self.MODE_CAMERA

    def _selected_screen(self):
        return self.screen_combo.currentData() or QGuiApplication.primaryScreen()

    def _mode_changed(self):
        mode = self._selected_mode()
        combined = mode == self.MODE_COMBINED
        screen_mode = mode in (self.MODE_SCREEN, self.MODE_COMBINED)
        self.screen_combo.setEnabled(screen_mode)
        self.shape_combo.setEnabled(combined)
        self.corner_combo.setEnabled(combined)
        self.preview_stack.setCurrentWidget(self.screen_preview if screen_mode else self.camera_preview)
        for label, button in self.mode_buttons.items():
            button.setObjectName("Primary" if label == mode else "")
            button.style().unpolish(button); button.style().polish(button)
        if mode == self.MODE_CAMERA:
            self._start_camera_preview()
        elif not self._recording:
            self._stop_camera_preview()

    def _default_camera_device(self):
        if not MULTIMEDIA_RECORDING_AVAILABLE:
            return None
        try:
            dev = QMediaDevices.defaultVideoInput()
            return None if dev.isNull() else dev
        except Exception:
            return None

    def _default_audio_device(self):
        if not MULTIMEDIA_RECORDING_AVAILABLE:
            return None
        try:
            dev = QMediaDevices.defaultAudioInput()
            return None if dev.isNull() else dev
        except Exception:
            return None

    def _start_camera_preview(self):
        if not MULTIMEDIA_RECORDING_AVAILABLE or self._recording:
            return
        if self._camera is not None:
            return
        dev = self._default_camera_device()
        if dev is None:
            self.status.setText("No webcam detected. Screen + Mic is still available.")
            return
        try:
            self._preview_session = QMediaCaptureSession(self)
            self._camera = QCamera(dev, self)
            self._preview_session.setCamera(self._camera)
            self._preview_session.setVideoOutput(self.camera_preview)
            self._camera.errorOccurred.connect(lambda _e, msg: self._set_error("Camera", msg))
            self._camera.start()
            self.status.setText("CAMERA READY")
        except Exception as ex:
            self._set_error("Camera", str(ex))

    def _stop_camera_preview(self):
        if self._camera is not None:
            try: self._camera.stop()
            except Exception: pass
        self._camera = None
        self._preview_session = None

    # ---------- recording ----------
    def _prepare_recorder(self):
        prefix = "witness-daily-recording-" if self._daily else "witness-sos-recording-"
        self._draft_dir = Path(tempfile.mkdtemp(prefix=prefix))
        self._session = QMediaCaptureSession(self)
        self._recorder = QMediaRecorder(self)
        self._session.setRecorder(self._recorder)
        self._recorder.errorOccurred.connect(self._on_recorder_error)
        self._recorder.durationChanged.connect(lambda _ms: self._sync_duration())
        self._recorder.recorderStateChanged.connect(self._on_recorder_state)

        audio_dev = self._default_audio_device()
        if audio_dev is not None:
            self._audio = QAudioInput(audio_dev, self)
            self._session.setAudioInput(self._audio)
        else:
            self._audio = None

        # Ask Qt's FFmpeg backend for its best supported video+audio encoding.
        fmt = QMediaFormat()
        try:
            fmt.setFileFormat(QMediaFormat.FileFormat.MPEG4)
            fmt.setVideoCodec(QMediaFormat.VideoCodec.H264)
            fmt.setAudioCodec(QMediaFormat.AudioCodec.AAC)
            if not fmt.isSupported(QMediaFormat.ConversionMode.Encode):
                fmt = QMediaFormat()
                fmt.resolveForEncoding(QMediaFormat.ResolveFlags.RequiresVideo)
        except Exception:
            # Older/alternate Qt builds can still resolve unspecified settings at record().
            pass
        try: self._recorder.setMediaFormat(fmt)
        except Exception: pass
        try: self._recorder.setQuality(QMediaRecorder.Quality.HighQuality)
        except Exception: pass
        try: self._recorder.setVideoFrameRate(30.0)
        except Exception: pass
        # Directory output lets Qt choose an extension matching the actual codec/container.
        self._recorder.setOutputLocation(QUrl.fromLocalFile(str(self._draft_dir.resolve())))

    def start_recording(self):
        if self._recording or not MULTIMEDIA_RECORDING_AVAILABLE:
            return
        self.reset_draft(clean_only=True)
        mode = self._selected_mode()
        if mode in (self.MODE_CAMERA, self.MODE_COMBINED) and self._default_camera_device() is None:
            QMessageBox.warning(self, "Camera unavailable", "No webcam is available. Choose SCREEN + MIC or connect a camera.")
            return
        self._stop_camera_preview()
        try:
            self._prepare_recorder()
            screen = self._selected_screen()
            if mode == self.MODE_CAMERA:
                dev = self._default_camera_device()
                self._camera = QCamera(dev, self)
                self._session.setCamera(self._camera)
                self._session.setVideoOutput(self.camera_preview)
                self._camera.errorOccurred.connect(lambda _e, msg: self._set_error("Camera", msg))
                self._camera.start()
                self.preview_stack.setCurrentWidget(self.camera_preview)
            else:
                self._screen_capture = QScreenCapture(self)
                self._screen_capture.setScreen(screen)
                self._screen_capture.errorOccurred.connect(lambda _e, msg: self._set_error("Screen capture", msg))
                self._session.setScreenCapture(self._screen_capture)
                self._screen_capture.start()
                if mode == self.MODE_COMBINED:
                    self._start_overlay_camera(screen)

            self._recording = True
            self._stopping = False
            self._recorder_error = ""
            self.start_btn.hide(); self.rerecord_btn.hide(); self.submit_btn.setEnabled(False)
            if mode == self.MODE_CAMERA:
                self.stop_btn.show()
                self._begin_recording_now()
            else:
                self.stop_btn.hide()
                self._show_screen_control(screen)
                # The control and optional camera overlay are created first. Hide the
                # studio, let Windows repaint the selected screen, then start encoding
                # so the recording does not open with a flash of the studio itself.
                self.status.setText("PREPARING SCREEN CAPTURE…")
                self.hide()
                QTimer.singleShot(280, self._begin_recording_now)
        except Exception as ex:
            self._cleanup_capture_objects()
            QMessageBox.critical(self, "Recording error", str(ex))
            self.status.setText("Recording could not start.")
            self.start_btn.show()


    def _begin_recording_now(self):
        if not self._recording or self._stopping or self._recorder is None:
            return
        try:
            self._recorder.record()
            self.status.setText("● RECORDING" + (" · microphone unavailable" if self._audio is None else ""))
            self.status.setStyleSheet("color:#ff6b73;font-weight:900;")
            self._duration_timer.start()
        except Exception as ex:
            self._cleanup_capture_objects()
            self._recording = False
            self._stopping = False
            self.show(); self.raise_(); self.activateWindow()
            QMessageBox.critical(self, "Recording error", str(ex))
            self.status.setText("Recording could not start.")
            self.start_btn.show()

    def _start_overlay_camera(self, screen):
        dev = self._default_camera_device()
        self._overlay_camera = QCamera(dev, self)
        self._preview_session = QMediaCaptureSession(self)
        self._preview_session.setCamera(self._overlay_camera)
        vw = QVideoWidget()
        self._preview_session.setVideoOutput(vw)
        shape = self.shape_combo.currentData() or "square"
        corner = self.corner_combo.currentData() or "bottom-right"
        self._overlay_widget = CameraOverlay(vw, screen, shape=shape, corner=corner)
        self._overlay_camera.start()
        self._overlay_widget.show()
        self._overlay_widget.raise_()

    def _show_screen_control(self, screen):
        self._control = RecordingControl(screen)
        self._control.stop_requested.connect(self.stop_recording)
        self._control.show(); self._control.raise_()

    def _sync_duration(self):
        ms = 0
        if self._recorder is not None:
            try: ms = int(self._recorder.duration())
            except Exception: ms = 0
        text = _fmt_duration(ms)
        self.timer_label.setText(text)
        if self._control is not None:
            self._control.time.setText(f"● REC  {text}")

    def stop_recording(self):
        if not self._recording or self._stopping:
            return
        self._stopping = True
        self.status.setText("FINISHING RECORDING…")
        if self._control is not None:
            self._control.hide()
        try:
            if self._recorder is not None:
                self._recorder.stop()
        except Exception as ex:
            self._set_error("Recorder", str(ex))
        try:
            if self._screen_capture is not None:
                self._screen_capture.stop()
        except Exception:
            pass
        try:
            if self._camera is not None:
                self._camera.stop()
        except Exception:
            pass
        try:
            if self._overlay_camera is not None:
                self._overlay_camera.stop()
        except Exception:
            pass
        if self._overlay_widget is not None:
            self._overlay_widget.hide()
        # recorderStateChanged is authoritative; timeout is a safety fallback.
        QTimer.singleShot(3000, self._finish_stop_if_needed)

    def _finish_stop_if_needed(self):
        if self._stopping:
            self._finalize_recording()

    def _on_recorder_state(self, state):
        if not self._stopping or self._recorder is None:
            return
        try:
            if state == QMediaRecorder.RecorderState.StoppedState:
                self._finalize_recording()
        except Exception:
            pass

    def _on_recorder_error(self, _error, error_string):
        self._recorder_error = str(error_string or "Unknown recorder error")
        self._set_error("Recorder", self._recorder_error)

    def _set_error(self, source, message):
        msg = str(message or "unknown error")
        self.status.setText(f"{source.upper()} ERROR · {msg[:140]}")
        self.status.setStyleSheet(f"color:{theme.RED};font-weight:800;")

    def _finalize_recording(self):
        if not self._stopping:
            return
        self._stopping = False
        self._recording = False
        self._duration_timer.stop()
        recorded = None
        if self._recorder is not None:
            try:
                url = self._recorder.actualLocation()
                if url and url.isLocalFile():
                    p = Path(url.toLocalFile())
                    if p.is_file() and p.stat().st_size > 0:
                        recorded = p
            except Exception:
                pass
        if recorded is None and self._draft_dir and self._draft_dir.is_dir():
            candidates = sorted((p for p in self._draft_dir.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                recorded = candidates[0]
        self._recorded_path = recorded
        self._cleanup_capture_objects(keep_draft=True)
        self.show(); self.raise_(); self.activateWindow()
        self.stop_btn.hide(); self.start_btn.hide(); self.rerecord_btn.show()
        self.status.setStyleSheet("")
        if self._recorder_error:
            self.status.setText("Recording stopped with an encoder error. Re-record before submitting.")
            self.submit_btn.setEnabled(False)
        elif recorded and recorded.is_file():
            size_mb = recorded.stat().st_size / (1024 * 1024)
            target = "SUBMIT TO DAY" if self._daily else "SUBMIT TO SOS"
            self.status.setText(f"RECORDING READY · {size_mb:.1f} MB · click {target}")
            self.submit_btn.setEnabled(True)
        else:
            self.status.setText("No video file was produced. Re-record and check camera/microphone permissions.")
            self.submit_btn.setEnabled(False)

    def _cleanup_capture_objects(self, keep_draft=False):
        if self._control is not None:
            try: self._control.close()
            except Exception: pass
        if self._overlay_widget is not None:
            try: self._overlay_widget.close()
            except Exception: pass
        for obj in (self._screen_capture, self._camera, self._overlay_camera):
            if obj is not None:
                try: obj.stop()
                except Exception: pass
        self._control = None; self._overlay_widget = None
        self._screen_capture = None; self._camera = None; self._overlay_camera = None
        self._session = None; self._preview_session = None; self._audio = None
        if not keep_draft:
            self._recorder = None

    def reset_draft(self, clean_only=False):
        if self._recording:
            return
        old_dir = self._draft_dir
        self._recorded_path = None; self._recorder = None; self._recorder_error = ""
        self._draft_dir = None
        if old_dir:
            shutil.rmtree(old_dir, ignore_errors=True)
        if clean_only:
            return
        self.timer_label.setText("00:00")
        self.status.setText("READY")
        self.status.setStyleSheet("")
        self.start_btn.show(); self.stop_btn.hide(); self.rerecord_btn.hide(); self.submit_btn.setEnabled(False)
        self._mode_changed()

    def submit_recording(self):
        src = self._recorded_path
        if not src or not src.is_file():
            target = "this calendar day" if self._daily else "SOS"
            QMessageBox.warning(self, "No recording", f"Record a video before submitting it to {target}.")
            return
        try:
            if self._daily:
                if not self.target_day:
                    raise ValueError("No calendar day was selected for this recording.")
                # Keep the existing calendar-video archive as the single source
                # of truth. It handles day folders and duplicate file names.
                import video_memories
                dest = Path(video_memories.add_video(self.target_day, str(src)))
                message = f"Video attached to {self.target_day}."
            else:
                SOS_DIR.mkdir(parents=True, exist_ok=True)
                mode = _safe_slug(self._selected_mode())
                stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                suffix = src.suffix.lower() or ".mp4"
                dest = SOS_DIR / f"witness-reset-{stamp}-{mode}{suffix}"
                n = 2
                while dest.exists():
                    dest = SOS_DIR / f"witness-reset-{stamp}-{mode}-{n}{suffix}"
                    n += 1
                shutil.move(str(src), str(dest))
                message = "Your reset video is now in the SOS library and will be available to the protection player."

            self._saved = True
            self.saved.emit(str(dest.resolve()))
            if self._draft_dir:
                shutil.rmtree(self._draft_dir, ignore_errors=True)
            self._draft_dir = None
            self._recorded_path = None
            QMessageBox.information(self, "Saved to WITNESS", message)
            self.accept()
        except Exception as ex:
            QMessageBox.critical(self, "Save recording", str(ex))

    def reject(self):
        if self._recording:
            choice = QMessageBox.question(self, "Stop recording?", "Recording is still active. Stop and discard it?",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                return
            self.stop_recording()
            QTimer.singleShot(350, self.reject)
            return
        self.reset_draft(clean_only=True)
        super().reject()

    def closeEvent(self, event):
        if self._recording:
            event.ignore(); self.reject(); return
        self.reset_draft(clean_only=True)
        super().closeEvent(event)
