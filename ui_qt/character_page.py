from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

import character_engine

from . import audio, theme
from .character_3d import Character3DView
from .widgets import SmoothProgressBar, card


def _asset_root() -> Path:
    """Character art location in source and frozen PyInstaller builds."""
    if getattr(sys, "frozen", False):
        frozen_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return frozen_root / "ui_qt" / "assets" / "character"
    return Path(__file__).resolve().parent / "assets" / "character"


_PIXMAP_CACHE: dict[str, QPixmap] = {}


def _pixmap(asset: str) -> QPixmap:
    key = str(asset or "")
    if key not in _PIXMAP_CACHE:
        _PIXMAP_CACHE[key] = QPixmap(str(_asset_root() / key))
    return _PIXMAP_CACHE[key]


class CharacterScene(QWidget):
    """Image-led 2.5D living portrait.

    The approved composite artwork remains the source image. V7.55 keeps the
    restrained living-portrait motion and separates Daily Charge (outer aura)
    from the user-controlled Core Reserve (inner chest light), while preserving
    cross-fades between forms. It deliberately does
    not pretend the still artwork is a rotatable 3D model.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.stage = dict(character_engine.EVOLUTION_STAGES[0])
        self._previous_stage = None
        self._transition = 1.0
        self.charge = 0
        self.reserve = {"active": False, "percent": 0, "state": "UNSET"}
        self.shield = {"unlocked": False, "progress": 0, "tier": 0}
        self._evolution_phase = -1.0
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._drag = None
        self._phase = 0.0
        self._hover_target_x = 0.0
        self._hover_target_y = 0.0
        self._hover_x = 0.0
        self._hover_y = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        # ~18 FPS is enough for ambient motion and keeps the full-frame pixmap
        # cheaper than a game-loop refresh.
        self._timer.start(55)
        self.setMouseTracking(True)
        self.setToolTip("Move to inspect · Drag to pan · Mouse wheel to zoom")

    def set_scene(self, stage: dict, state: dict, *, evolution=False):
        incoming = dict(stage or character_engine.EVOLUTION_STAGES[0])
        old_asset = str(self.stage.get("asset", ""))
        new_asset = str(incoming.get("asset", ""))
        if old_asset and new_asset and old_asset != new_asset:
            self._previous_stage = dict(self.stage)
            self._transition = 0.0
        self.stage = incoming
        self.charge = max(0, min(100, int(state.get("charge", {}).get("percent", 0) or 0)))
        if state.get("reserve"):
            self.reserve = dict(state["reserve"])
        if state.get("shield"):
            self.shield = dict(state["shield"])
        if evolution:
            self._evolution_phase = 0.0
        self.update()

    def _tick(self):
        if not self.isVisible():
            return
        self._phase = (self._phase + 0.04) % (math.pi * 1000)
        # Smooth passive parallax instead of snapping to pointer position.
        self._hover_x += (self._hover_target_x - self._hover_x) * 0.10
        self._hover_y += (self._hover_target_y - self._hover_y) * 0.10
        if self._previous_stage is not None:
            self._transition = min(1.0, self._transition + 0.055)
            if self._transition >= 1.0:
                self._previous_stage = None
        if self._evolution_phase >= 0.0:
            self._evolution_phase += 0.035
            if self._evolution_phase >= 1.0:
                self._evolution_phase = -1.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._drag is not None:
            dx = pos.x() - self._drag.x()
            dy = pos.y() - self._drag.y()
            self._drag = pos
            self.pan_x = max(-1.0, min(1.0, self.pan_x - dx / max(100.0, self.width() * 0.30)))
            self.pan_y = max(-0.7, min(0.7, self.pan_y - dy / max(100.0, self.height() * 0.34)))
        else:
            nx = (pos.x() / max(1.0, self.width()) - 0.5) * 2.0
            ny = (pos.y() / max(1.0, self.height()) - 0.5) * 2.0
            self._hover_target_x = max(-0.16, min(0.16, nx * 0.16))
            self._hover_target_y = max(-0.09, min(0.09, ny * 0.09))
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_target_x = 0.0
        self._hover_target_y = 0.0
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        step = 0.045 if event.angleDelta().y() > 0 else -0.045
        self.zoom = max(1.0, min(1.24, self.zoom + step))
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0
        self._hover_target_x = self._hover_target_y = 0.0
        self._hover_x = self._hover_y = 0.0
        self.update()
        super().mouseDoubleClickEvent(event)

    @staticmethod
    def _ease(value: float) -> float:
        value = max(0.0, min(1.0, float(value)))
        return value * value * (3.0 - 2.0 * value)

    def _draw_stage_cover(self, p: QPainter, r: QRectF, stage: dict, opacity=1.0):
        pm = _pixmap(stage.get("asset", ""))
        if pm.isNull():
            p.fillRect(r, QColor(theme.SURFACE_2))
            p.setPen(QColor(theme.TEXT_2))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "CHARACTER ART UNAVAILABLE")
            return

        iw, ih = float(pm.width()), float(pm.height())
        rw, rh = max(1.0, r.width()), max(1.0, r.height())
        base_scale = max(rw / iw, rh / ih)
        # This is intentionally tiny: it reads as breathing/camera life, not
        # obvious zooming of the entire composite image.
        breath = 1.0 + math.sin(self._phase * 0.68) * 0.0032
        scale = base_scale * self.zoom * breath
        source_w = rw / scale
        source_h = rh / scale
        extra_x = max(0.0, iw - source_w)
        extra_y = max(0.0, ih - source_h)
        inspect_x = max(-1.0, min(1.0, self.pan_x + self._hover_x))
        inspect_y = max(-0.75, min(0.75, self.pan_y + self._hover_y))
        cx = (iw / 2.0 + inspect_x * extra_x * 0.45
              + math.sin(self._phase * 0.20) * extra_x * 0.008)
        cy = (ih / 2.0 + inspect_y * extra_y * 0.38
              + math.sin(self._phase * 0.68) * extra_y * 0.006)
        sx = max(0.0, min(iw - source_w, cx - source_w / 2.0))
        sy = max(0.0, min(ih - source_h, cy - source_h / 2.0))
        src = QRectF(sx, sy, source_w, source_h)
        p.save()
        p.setOpacity(max(0.0, min(1.0, opacity)))
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(r, pm, src)
        p.restore()

    def _draw_cover(self, p: QPainter, r: QRectF):
        if self._previous_stage is None:
            self._draw_stage_cover(p, r, self.stage, 1.0)
            return
        t = self._ease(self._transition)
        self._draw_stage_cover(p, r, self._previous_stage, 1.0 - t)
        self._draw_stage_cover(p, r, self.stage, t)

    def _draw_fog(self, p: QPainter, r: QRectF, strength=1.0):
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(4):
            drift = math.sin(self._phase * (0.11 + i * 0.015) + i * 1.7)
            x = r.left() + r.width() * (0.08 + i * 0.26) + drift * r.width() * 0.06
            y = r.top() + r.height() * (0.66 + (i % 2) * 0.09)
            radius = r.width() * (0.20 + i * 0.018)
            grad = QRadialGradient(QPointF(x, y), radius)
            inner = QColor("#a8b2ac")
            inner.setAlpha(int(12 * strength))
            edge = QColor("#a8b2ac"); edge.setAlpha(0)
            grad.setColorAt(0.0, inner); grad.setColorAt(1.0, edge)
            p.setBrush(grad)
            p.drawEllipse(QPointF(x, y), radius, radius * 0.34)
        p.restore()

    def _draw_motion(self, p: QPainter, r: QRectF):
        index = int(self.stage.get("index", 1) or 1)
        if index <= 4:
            self._draw_fog(p, r, 1.0 if index <= 2 else 0.72)
            # Early chapters: slow fireflies / inner-world particles.
            p.setPen(Qt.PenStyle.NoPen)
            count = 24 if index <= 2 else 17
            for i in range(count):
                x = r.left() + ((i * 137.0 + math.sin(self._phase * 0.35 + i) * 22) % max(1.0, r.width()))
                y = r.top() + ((i * 79.0 - self._phase * (3 + i % 3)) % max(1.0, r.height()))
                alpha = 28 + (i % 5) * 11
                c = QColor("#e9c36a"); c.setAlpha(alpha)
                p.setBrush(c)
                radius = 1.0 + (i % 3) * 0.50
                p.drawEllipse(QPointF(x, y), radius, radius)
        else:
            # Civilization chapters: low mist + restrained rain. Operator and
            # beyond are a little sharper, but never a distracting storm loop.
            self._draw_fog(p, r, 0.48 if index == 5 else 0.32)
            count = 20 if index == 5 else (30 if index == 6 else 24)
            for i in range(count):
                x = r.left() + ((i * 113.0 + self._phase * (11 + i % 5)) % max(1.0, r.width()))
                y = r.top() + ((i * 71.0 + self._phase * (45 + i % 7)) % max(1.0, r.height()))
                c = QColor("#c5d1d8"); c.setAlpha(22 + (i % 4) * 8)
                p.setPen(QPen(c, 1))
                length = 7 + (i % 4) * 3
                p.drawLine(QPointF(x, y), QPointF(x - 2.0, y + length))

    def _draw_charge_aura(self, p: QPainter, r: QRectF):
        """Daily XP/Charge affects the outer energy, not the inner Reserve core."""
        pct = self.charge / 100.0
        if pct <= 0:
            return
        pulse = (math.sin(self._phase * (1.15 + pct * 0.5)) + 1.0) * 0.5
        cx = r.center().x()
        cy = r.top() + r.height() * 0.50
        radius = r.width() * (0.17 + 0.06 * pct + 0.004 * pulse)
        grad = QRadialGradient(QPointF(cx, cy), radius)
        inner = QColor(theme.GREEN); inner.setAlpha(int(3 + 13 * pct + pulse * 4 * pct))
        mid = QColor(theme.GREEN); mid.setAlpha(int(2 + 7 * pct))
        edge = QColor(theme.GREEN); edge.setAlpha(0)
        grad.setColorAt(0.0, inner); grad.setColorAt(0.55, mid); grad.setColorAt(1.0, edge)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(grad)
        p.drawEllipse(QPointF(cx, cy), radius, radius * 1.9)

    def _draw_core(self, p: QPainter, r: QRectF):
        # Inner Core is now driven by the explicit Reserve clock. Daily XP has
        # its own outer aura so a high-level person can still look depleted.
        if not self.reserve.get("active"):
            return
        pct = max(0.0, min(1.0, float(self.reserve.get("percent", 0) or 0) / 100.0))
        cx = r.left() + r.width() * 0.50
        cy = r.top() + r.height() * 0.305
        pulse = (math.sin(self._phase * (1.35 + pct * 0.45)) + 1.0) * 0.5
        radius = 18 + 38 * pct + pulse * (2.5 + 4.5 * pct)
        grad = QRadialGradient(QPointF(cx, cy), radius)
        hot = QColor("#f2c86b"); hot.setAlpha(int(15 + 66 * pct + pulse * 16 * max(.2, pct)))
        warm = QColor("#d7aa4e"); warm.setAlpha(int(7 + 28 * pct))
        edge = QColor("#efc36a"); edge.setAlpha(0)
        grad.setColorAt(0.0, hot); grad.setColorAt(0.36, warm); grad.setColorAt(1.0, edge)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(grad)
        p.drawEllipse(QPointF(cx, cy), radius, radius)

    def _draw_evolution(self, p: QPainter, r: QRectF):
        if self._evolution_phase < 0.0:
            return
        t = max(0.0, min(1.0, self._evolution_phase))
        # Brief darkness -> expanding ring -> clean reveal. This is intentionally
        # rare and only runs when the live canonical level/form changes.
        dark_alpha = int(105 * max(0.0, 1.0 - t * 2.1))
        if dark_alpha:
            shade = QColor("#020304"); shade.setAlpha(dark_alpha)
            p.fillRect(r, shade)
        cx = r.center().x(); cy = r.top() + r.height() * 0.305
        ring_t = min(1.0, t / 0.72)
        ring_r = 26 + ring_t * min(r.width(), r.height()) * 0.34
        alpha = int(185 * (1.0 - ring_t) ** 1.6)
        if alpha > 0:
            c = QColor(theme.GOLD); c.setAlpha(alpha)
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(c, 2.0 + (1.0-ring_t)*2.0))
            p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)
        if 0.18 <= t <= 0.75:
            fade = 1.0 - abs(t - 0.46) / 0.29
            c = QColor(theme.GOLD); c.setAlpha(int(max(0.0, fade) * 210))
            p.setPen(c)
            f = QFont("Segoe UI", max(12, int(r.height() * 0.026)))
            f.setBold(True); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
            p.setFont(f)
            text_r = QRectF(r.left(), r.top() + r.height() * .18, r.width(), 48)
            p.drawText(text_r, Qt.AlignmentFlag.AlignCenter, "EVOLUTION")

    def _draw_shield(self, p: QPainter, r: QRectF):
        if not self.shield.get("unlocked"):
            return
        tier = max(1, int(self.shield.get("tier", 1) or 1))
        pulse = (math.sin(self._phase * 1.35) + 1.0) * 0.5
        alpha = min(100, 30 + tier * 11 + int(pulse * 14))
        c = QColor(theme.GREEN); c.setAlpha(alpha)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(c, 1.25 + tier * 0.30))
        cx = r.center().x()
        top = r.top() + r.height() * 0.075
        left = cx - r.width() * 0.185
        right = cx + r.width() * 0.185
        shoulder_y = r.top() + r.height() * 0.19
        waist_y = r.top() + r.height() * 0.61
        bottom = r.top() + r.height() * 0.91
        path = QPainterPath(QPointF(cx, top))
        path.cubicTo(QPointF(right, shoulder_y), QPointF(right, waist_y), QPointF(cx, bottom))
        path.cubicTo(QPointF(left, waist_y), QPointF(left, shoulder_y), QPointF(cx, top))
        p.drawPath(path)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        self._draw_cover(p, r)
        self._draw_motion(p, r)
        self._draw_charge_aura(p, r)
        self._draw_core(p, r)
        self._draw_shield(p, r)
        self._draw_evolution(p, r)
        p.setPen(QPen(QColor(theme.BORDER_STRONG), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), 15, 15)


class TraitRow(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricTile")
        lay = QVBoxLayout(self); lay.setContentsMargins(11, 8, 11, 8); lay.setSpacing(4)
        top = QHBoxLayout()
        self.name = QLabel("ATTRIBUTE"); self.name.setStyleSheet("font-weight:850;")
        self.tier = QLabel("FORMING"); self.tier.setObjectName("Eyebrow")
        top.addWidget(self.name); top.addStretch(1); top.addWidget(self.tier)
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setTextVisible(False)
        self.evidence = QLabel(""); self.evidence.setWordWrap(True); self.evidence.setObjectName("Muted")
        lay.addLayout(top); lay.addWidget(self.bar); lay.addWidget(self.evidence)

    def set_trait(self, row):
        self.name.setText(str(row.get("name", "ATTRIBUTE")))
        self.tier.setText(str(row.get("tier", "FORMING")))
        self.bar.setValue(max(0, min(100, int(row.get("value", 0) or 0))))
        self.evidence.setText(str(row.get("evidence", "")))


class CharacterPage(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._snap = None
        self._trait_rows = []
        self._stage_buttons: dict[str, QToolButton] = {}
        self._view_stage_id = None

        root = QWidget(); self.setWidget(root)
        outer = QVBoxLayout(root); outer.setContentsMargins(18, 16, 18, 18); outer.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout(); title_box.setSpacing(2)
        title = QLabel("CHARACTER"); title.setObjectName("PageTitle")
        self.subtitle = QLabel("Your long-term evolution, current charge and earned protection."); self.subtitle.setObjectName("Muted")
        title_box.addWidget(title); title_box.addWidget(self.subtitle)
        header.addLayout(title_box); header.addStretch(1)
        self.live_badge = QLabel("EVOLUTION LIVE")
        self.live_badge.setObjectName("EraBadge")
        header.addWidget(self.live_badge)
        outer.addLayout(header)

        body = QHBoxLayout(); body.setSpacing(12)

        stage_card = card(strong=True)
        sl = QVBoxLayout(stage_card); sl.setContentsMargins(12, 12, 12, 10); sl.setSpacing(8)
        stage_top = QHBoxLayout()
        self.scene_mode = QLabel("CURRENT FORM"); self.scene_mode.setObjectName("Eyebrow")
        self.scene_title = QLabel("WANDERER"); self.scene_title.setObjectName("SectionTitle")
        self.world_name = QLabel("WILD PATH"); self.world_name.setObjectName("Eyebrow")
        stage_top.addWidget(self.scene_mode); stage_top.addSpacing(8); stage_top.addWidget(self.scene_title)
        stage_top.addStretch(1)
        self.view_group = QButtonGroup(self); self.view_group.setExclusive(True)
        self.portrait_btn = QPushButton("PORTRAIT"); self.portrait_btn.setObjectName("Tab"); self.portrait_btn.setCheckable(True); self.portrait_btn.setChecked(True)
        self.lab_btn = QPushButton("3D LAB"); self.lab_btn.setObjectName("Tab"); self.lab_btn.setCheckable(True)
        self.view_group.addButton(self.portrait_btn, 0); self.view_group.addButton(self.lab_btn, 1)
        self.portrait_btn.clicked.connect(lambda _=False: self._set_view_mode(0))
        self.lab_btn.clicked.connect(lambda _=False: self._set_view_mode(1))
        stage_top.addWidget(self.portrait_btn); stage_top.addWidget(self.lab_btn); stage_top.addSpacing(8); stage_top.addWidget(self.world_name)
        sl.addLayout(stage_top)
        self.scene_stack = QStackedWidget()
        self.scene = CharacterScene(); self.scene3d = Character3DView()
        self.scene_stack.addWidget(self.scene); self.scene_stack.addWidget(self.scene3d)
        sl.addWidget(self.scene_stack, 1)
        controls = QHBoxLayout()
        self.scene_hint = QLabel("MOVE FOR DEPTH  ·  DRAG TO PAN  ·  WHEEL TO ZOOM  ·  DOUBLE-CLICK TO RESET")
        self.scene_hint.setAlignment(Qt.AlignmentFlag.AlignCenter); self.scene_hint.setObjectName("Muted")
        self.auto3d_btn = QPushButton("AUTO ROTATE"); self.auto3d_btn.setCheckable(True); self.auto3d_btn.setObjectName("Tab")
        self.auto3d_btn.toggled.connect(self.scene3d.set_auto_rotate); self.auto3d_btn.setVisible(False)
        controls.addWidget(self.scene_hint, 1); controls.addWidget(self.auto3d_btn)
        sl.addLayout(controls)

        journey_head = QHBoxLayout()
        jtitle = QLabel("JOURNEY"); jtitle.setObjectName("Eyebrow")
        self.journey_help = QLabel("Current form follows your live level. Peak forms stay available as memories.")
        self.journey_help.setObjectName("Muted")
        journey_head.addWidget(jtitle); journey_head.addSpacing(8); journey_head.addWidget(self.journey_help); journey_head.addStretch(1)
        sl.addLayout(journey_head)
        self.stage_strip = QGridLayout(); self.stage_strip.setSpacing(6)
        sl.addLayout(self.stage_strip)
        body.addWidget(stage_card, 8)

        side = QVBoxLayout(); side.setSpacing(10)

        identity = card(); il = QVBoxLayout(identity); il.setContentsMargins(14, 12, 14, 12); il.setSpacing(5)
        eye = QLabel("EVOLUTION"); eye.setObjectName("Eyebrow")
        self.form_lbl = QLabel("WANDERER"); self.form_lbl.setStyleSheet("font-size:22px;font-weight:900;")
        self.form_meta = QLabel("FORM 1 / 8"); self.form_meta.setObjectName("Secondary")
        self.evo_bar = SmoothProgressBar(); self.evo_bar.setRange(0, 1000); self.evo_bar.setTextVisible(False)
        self.evo_help = QLabel(""); self.evo_help.setWordWrap(True); self.evo_help.setObjectName("Muted")
        self.level_lbl = QLabel("LV. 1 RECRUIT · 0 rolling XP"); self.level_lbl.setObjectName("Secondary")
        il.addWidget(eye); il.addWidget(self.form_lbl); il.addWidget(self.form_meta)
        il.addWidget(self.evo_bar); il.addWidget(self.evo_help); il.addWidget(self.level_lbl)
        side.addWidget(identity)

        reserve = card(); rl = QVBoxLayout(reserve); rl.setContentsMargins(14, 12, 14, 12); rl.setSpacing(5)
        re = QLabel("CORE RESERVE"); re.setObjectName("Eyebrow")
        rr = QHBoxLayout()
        self.reserve_state = QLabel("UNSET"); self.reserve_state.setStyleSheet(
            f"font-size:18px;font-weight:900;color:{theme.GOLD};")
        self.reserve_pct = QLabel("0%"); self.reserve_pct.setStyleSheet("font-size:18px;font-weight:900;")
        rr.addWidget(self.reserve_state); rr.addStretch(1); rr.addWidget(self.reserve_pct)
        self.reserve_time = QLabel("Not started"); self.reserve_time.setStyleSheet("font-size:15px;font-weight:800;")
        self.reserve_bar = SmoothProgressBar(); self.reserve_bar.setRange(0, 100); self.reserve_bar.setTextVisible(False)
        self.reserve_help = QLabel("Personal 14-day Reserve clock. It changes only the inner Core glow — never XP or Level.")
        self.reserve_help.setWordWrap(True); self.reserve_help.setObjectName("Muted")
        self.reserve_btn = QPushButton("START RESERVE"); self.reserve_btn.setObjectName("Gold")
        self.reserve_btn.clicked.connect(self._reserve_action)
        rl.addWidget(re); rl.addLayout(rr); rl.addWidget(self.reserve_time); rl.addWidget(self.reserve_bar)
        rl.addWidget(self.reserve_help); rl.addWidget(self.reserve_btn, 0, Qt.AlignmentFlag.AlignLeft)
        side.addWidget(reserve)

        charge = card(); cl = QVBoxLayout(charge); cl.setContentsMargins(14, 12, 14, 12); cl.setSpacing(5)
        ce = QLabel("CURRENT CHARGE"); ce.setObjectName("Eyebrow")
        row = QHBoxLayout(); self.charge_state = QLabel("DORMANT"); self.charge_state.setStyleSheet(
            f"font-size:18px;font-weight:900;color:{theme.GREEN};")
        self.charge_pct = QLabel("0%"); self.charge_pct.setStyleSheet("font-size:18px;font-weight:900;")
        row.addWidget(self.charge_state); row.addStretch(1); row.addWidget(self.charge_pct)
        self.charge_bar = SmoothProgressBar(); self.charge_bar.setRange(0, 100); self.charge_bar.setTextVisible(False)
        self.charge_meta = QLabel("0 / 1,000 XP"); self.charge_meta.setObjectName("Muted")
        cl.addWidget(ce); cl.addLayout(row); cl.addWidget(self.charge_bar); cl.addWidget(self.charge_meta)
        side.addWidget(charge)

        world = card(); wl = QVBoxLayout(world); wl.setContentsMargins(14, 12, 14, 12); wl.setSpacing(5)
        we = QLabel("CURRENT WORLD"); we.setObjectName("Eyebrow")
        self.world_lbl = QLabel("WILD PATH"); self.world_lbl.setStyleSheet("font-weight:850;")
        self.world_help = QLabel("The journey begins in the wild."); self.world_help.setWordWrap(True); self.world_help.setObjectName("Muted")
        self.return_btn = QPushButton("RETURN TO CURRENT FORM"); self.return_btn.setObjectName("Primary")
        self.return_btn.clicked.connect(self._return_current); self.return_btn.setVisible(False)
        wl.addWidget(we); wl.addWidget(self.world_lbl); wl.addWidget(self.world_help); wl.addWidget(self.return_btn)
        side.addWidget(world)

        shield = card(); sh = QVBoxLayout(shield); sh.setContentsMargins(14, 12, 14, 12); sh.setSpacing(5)
        se = QLabel("PROTECTION SHIELD"); se.setObjectName("Eyebrow")
        srow = QHBoxLayout(); self.shield_name = QLabel("SHIELD CHARGING"); self.shield_name.setStyleSheet("font-weight:850;")
        self.shield_days = QLabel("0 / 14 DAYS"); self.shield_days.setObjectName("Secondary")
        srow.addWidget(self.shield_name); srow.addStretch(1); srow.addWidget(self.shield_days)
        self.shield_bar = QProgressBar(); self.shield_bar.setRange(0, 100); self.shield_bar.setTextVisible(False)
        self.shield_help = QLabel("Requires monitored days with no drift, red-line or SOS breaches.")
        self.shield_help.setWordWrap(True); self.shield_help.setObjectName("Muted")
        sh.addWidget(se); sh.addLayout(srow); sh.addWidget(self.shield_bar); sh.addWidget(self.shield_help)
        side.addWidget(shield)

        traits = card(); tl = QVBoxLayout(traits); tl.setContentsMargins(12, 11, 12, 12); tl.setSpacing(7)
        th = QLabel("ATTRIBUTES"); th.setObjectName("SectionTitle")
        td = QLabel("Descriptive evidence only. Attributes never award XP.")
        td.setWordWrap(True); td.setObjectName("Muted")
        tl.addWidget(th); tl.addWidget(td)
        self.signature_lbl = QLabel("SIGNATURE · STILL FORMING")
        self.signature_lbl.setObjectName("Eyebrow")
        tl.addWidget(self.signature_lbl)
        self.traits_layout = QVBoxLayout(); self.traits_layout.setSpacing(6); tl.addLayout(self.traits_layout)
        side.addWidget(traits)
        side.addStretch(1)
        body.addLayout(side, 4)
        outer.addLayout(body, 1)
        self.refresh()

    def _set_view_mode(self, index: int):
        index = 1 if int(index) == 1 else 0
        self.scene_stack.setCurrentIndex(index)
        self.portrait_btn.setChecked(index == 0); self.lab_btn.setChecked(index == 1)
        self.auto3d_btn.setVisible(index == 1)
        if index == 1:
            self.scene_hint.setText("TRUE 3D PROTOTYPE · DRAG TO ROTATE · WHEEL TO ZOOM · DOUBLE-CLICK TO RESET")
        else:
            self.scene_hint.setText("MOVE FOR DEPTH  ·  DRAG TO PAN  ·  WHEEL TO ZOOM  ·  DOUBLE-CLICK TO RESET")

    def _clear_stage_strip(self):
        while self.stage_strip.count():
            item = self.stage_strip.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._stage_buttons.clear()

    def _rebuild_stage_strip(self, snap):
        self._clear_stage_strip()
        evo = snap.get("evolution", {})
        current_id = str(evo.get("current", {}).get("id", "wanderer"))
        demo_preview = bool(snap.get("demo_preview"))
        for stage in evo.get("stages", []):
            stage = dict(stage)
            sid = str(stage.get("id"))
            unlocked = bool(stage.get("unlocked"))
            can_view = unlocked or demo_preview
            b = QToolButton()
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setFixedHeight(86)
            b.setMinimumWidth(118)
            if can_view:
                pm = _pixmap(stage.get("asset", ""))
                if not pm.isNull():
                    b.setIcon(QIcon(pm))
                    b.setIconSize(QSize(66, 38))
            prefix = f"{int(stage.get('index', 1))}. "
            b.setText(prefix + str(stage.get("name", "FORM")).upper())
            if not can_view:
                b.setText("LOCKED\n" + prefix + str(stage.get("name", "FORM")).upper())
                b.setEnabled(False)
            if sid == current_id and self._view_stage_id is None:
                b.setChecked(True)
            if sid == self._view_stage_id:
                b.setChecked(True)
            b.setObjectName("JourneyStage")
            if can_view:
                b.clicked.connect(lambda _=False, stage_id=sid: self._view_stage(stage_id))
            pos = int(stage.get("index", 1)) - 1
            self.stage_strip.addWidget(b, pos // 4, pos % 4)
            self._stage_buttons[sid] = b

    def _view_stage(self, stage_id: str):
        snap = self._snap or {}
        evo = snap.get("evolution", {})
        current_id = str(evo.get("current", {}).get("id", "wanderer"))
        self._view_stage_id = None if stage_id == current_id else stage_id
        self._render_scene(snap)
        self._rebuild_stage_strip(snap)

    def _return_current(self):
        self._view_stage_id = None
        if self._snap:
            self._render_scene(self._snap)
            self._rebuild_stage_strip(self._snap)

    def _render_scene(self, snap, *, evolution=False):
        evo = snap.get("evolution", {})
        current = dict(evo.get("current", character_engine.EVOLUTION_STAGES[0]))
        stages = evo.get("stages", [])
        stage = current
        if self._view_stage_id:
            stage = dict(next((x for x in stages if x.get("id") == self._view_stage_id), current))
        viewing_memory = str(stage.get("id")) != str(current.get("id"))
        self.scene_mode.setText("MEMORY" if viewing_memory else "CURRENT FORM")
        self.scene_title.setText(str(stage.get("name", "WANDERER")).upper())
        self.world_name.setText(str(stage.get("world", "WILD PATH")).upper())
        self.world_lbl.setText(str(stage.get("world", "WILD PATH")).upper())
        self.world_help.setText(str(stage.get("description", "")))
        self.return_btn.setVisible(viewing_memory)
        self.scene.set_scene(stage, snap, evolution=bool(evolution and not viewing_memory))
        self.scene3d.set_scene(stage, snap)

    def _apply_live(self, live, full=False):
        if self._snap is None or full:
            self._snap = dict(live)
        else:
            self._snap.update({k: v for k, v in live.items() if k not in ("attributes", "shield")})
        snap = self._snap
        identity = snap.get("identity", {})
        name = str(identity.get("name", "") or "").strip()
        mission = str(identity.get("mission", "") or "").strip()
        if mission:
            mission_short = mission if len(mission) <= 110 else mission[:107].rstrip() + "…"
            self.subtitle.setText((name.upper() + " · " if name else "") + mission_short)
        elif name:
            self.subtitle.setText(name.upper() + " · long-term evolution, current state and earned protection.")
        else:
            self.subtitle.setText("Your long-term evolution, current state and earned protection.")
        evo = snap.get("evolution", {})
        current = evo.get("current", {})
        previous_current = getattr(self, "_current_stage_id", None)
        self._current_stage_id = str(current.get("id", "wanderer"))
        stage_changed = bool(previous_current and previous_current != self._current_stage_id)
        if stage_changed:
            self._view_stage_id = None

        self.form_lbl.setText(str(current.get("name", "WANDERER")).upper())
        self.form_meta.setText(
            f"FORM {int(evo.get('index', 1))} / {int(evo.get('count', 8))}  ·  {str(current.get('theme', 'RAW POTENTIAL'))}")
        progress = max(0.0, min(1.0, float(evo.get("progress", 0.0) or 0.0)))
        self.evo_bar.set_target_value(int(progress * 1000))
        peak_rating = int(evo.get("peak_rating", 0) or 0)
        level = snap.get("level", {})
        rating = int(level.get("rating", 0) or 0)
        next_stage = evo.get("next")
        if next_stage:
            self.evo_help.setText(
                f"Level Rating {rating:,} · {int(evo.get('rating_to_next', 0) or 0):,} to {next_stage.get('name', 'next form')} · peak {peak_rating:,}.")
        else:
            self.evo_help.setText(f"Level Rating {rating:,} · Sovereign reached · peak {peak_rating:,}.")

        self.level_lbl.setText(
            f"LV. {int(level.get('current_level', 1) or 1)} {str(level.get('name', 'Wanderer')).upper()}"
            f"  ·  {int(level.get('rating', 0) or 0):,} rolling XP")

        ch = snap.get("charge", {})
        pct = int(ch.get("percent", 0) or 0)
        self.charge_state.setText(str(ch.get("state", "DORMANT")))
        self.charge_pct.setText(f"{pct}%")
        self.charge_bar.set_target_value(pct)
        self.charge_meta.setText(
            f"{int(ch.get('current_xp', 0)):,} / {int(ch.get('target_xp', 1000)):,} XP today")

        reserve = snap.get("reserve", {})
        rpct = int(reserve.get("percent", 0) or 0)
        self.reserve_state.setText(str(reserve.get("state", "UNSET")))
        self.reserve_pct.setText(f"{rpct}%")
        self.reserve_bar.set_target_value(rpct)
        self.reserve_time.setText(str(reserve.get("display", "Not started")))
        if reserve.get("active"):
            self.reserve_btn.setText("RESET RESERVE")
            self.reserve_btn.setObjectName("")
            self.reserve_help.setText(
                f"{int(reserve.get('days',0))} days into a {int(reserve.get('target_days',14))}-day visual charge arc. "
                "Reset only when you want this personal timer to restart.")
        else:
            self.reserve_btn.setText("START RESERVE")
            self.reserve_btn.setObjectName("Gold")
            self.reserve_help.setText("Start the personal Reserve clock when you want. It never changes XP, Level or Shield.")
        self.reserve_btn.style().unpolish(self.reserve_btn); self.reserve_btn.style().polish(self.reserve_btn)

        self._render_scene(snap, evolution=stage_changed)

        if full:
            self._rebuild_stage_strip(snap)
            sh = snap.get("shield", {})
            self.shield_name.setText(str(sh.get("name", "SHIELD CHARGING")))
            days = int(sh.get("clean_days", 0) or 0); target = sh.get("next_target") or days
            self.shield_days.setText(f"{days} / {target} DAYS" if sh.get("next_target") else f"{days} CLEAN DAYS")
            self.shield_bar.setValue(int(sh.get("progress", 0) or 0))
            if not sh.get("tracking_today"):
                self.shield_help.setText(
                    "Protection only counts monitored days. Full Layer-1 tracking is still pending in the installed Qt runtime.")
            elif sh.get("unlocked"):
                self.shield_help.setText("Shield active. Longer clean streaks strengthen it further.")
            else:
                self.shield_help.setText("14 clean monitored days unlock the first shield.")

            attrs = snap.get("attributes", [])
            sig = snap.get("signature_attribute")
            self.signature_lbl.setText(
                f"SIGNATURE · {str(sig.get('name','')).upper()} · {str(sig.get('tier','')).upper()}"
                if sig else "SIGNATURE · STILL FORMING")
            while len(self._trait_rows) < len(attrs):
                row = TraitRow(); self._trait_rows.append(row); self.traits_layout.addWidget(row)
            for i, row in enumerate(self._trait_rows):
                if i < len(attrs):
                    row.show(); row.set_trait(attrs[i])
                else:
                    row.hide()

    def _reserve_action(self):
        try:
            state = character_engine.core_reserve()
            if not state.get("active"):
                character_engine.start_core_reserve()
                audio.play("core")
            else:
                answer = QMessageBox.question(
                    self, "Reset Core Reserve?",
                    "This restarts the personal Core Reserve clock at zero.\n\n"
                    "Your XP, Level, unlocked forms, Daily Charge and Protection Shield are NOT changed.\n\n"
                    "Reset Reserve now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
                character_engine.reset_core_reserve()
                audio.play("core")
            self.live_refresh()
        except Exception as ex:
            QMessageBox.critical(self, "Core Reserve", str(ex))

    def refresh(self):
        try:
            snap = character_engine.snapshot()
        except Exception as ex:
            self.world_help.setText(f"Character state unavailable: {ex}")
            return
        self._apply_live(snap, full=True)

    def live_refresh(self):
        try:
            live = character_engine.live_state()
        except Exception:
            return
        self._apply_live(live, full=False)
