from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve, QPointF, QRectF, Qt, QTimer, Signal, QVariantAnimation,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from . import theme


def card(strong=False):
    f = QFrame()
    f.setObjectName("CardStrong" if strong else "Card")
    return f


def label(text="", object_name=None, alignment=None):
    w = QLabel(text)
    if object_name:
        w.setObjectName(object_name)
    if alignment is not None:
        w.setAlignment(alignment)
    return w


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget:
            widget.deleteLater()
        elif child_layout:
            clear_layout(child_layout)


class AnimatedNumberLabel(QLabel):
    """A QLabel that eases between integer values instead of snapping.

    The first value renders immediately; later changes animate. This is delivery
    only -- the canonical score remains whatever the backend returned.
    """

    def __init__(self, text="0", parent=None):
        super().__init__(text, parent)
        self._display_value = 0
        self._target_value = 0
        self._suffix = ""
        self._signed = False
        self._initialized = False
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self._finish)

    def _format(self, value):
        value = int(round(float(value)))
        if self._signed and value > 0:
            body = f"+{value:,}"
        else:
            body = f"{value:,}"
        return body + self._suffix

    def _on_value(self, value):
        self._display_value = int(round(float(value)))
        super().setText(self._format(self._display_value))

    def _finish(self):
        self._display_value = self._target_value
        super().setText(self._format(self._target_value))

    def set_number(self, value, suffix="", signed=False, animate=True, duration=420):
        value = int(round(float(value or 0)))
        self._suffix = str(suffix)
        self._signed = bool(signed)
        if not self._initialized or not animate or value == self._display_value:
            self._anim.stop()
            self._target_value = value
            self._display_value = value
            self._initialized = True
            super().setText(self._format(value))
            return
        self._initialized = True
        self._anim.stop()
        self._anim.setDuration(max(90, int(duration)))
        self._anim.setStartValue(self._display_value)
        self._anim.setEndValue(value)
        self._target_value = value
        self._anim.start()


class SmoothProgressBar(QProgressBar):
    """Progress bar with eased value changes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(360)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda v: super(SmoothProgressBar, self).setValue(int(v)))
        self._initialized = False

    def set_target_value(self, value, animate=True, duration=360):
        value = max(self.minimum(), min(self.maximum(), int(value)))
        if not self._initialized or not animate or value == self.value():
            self._anim.stop()
            super().setValue(value)
            self._initialized = True
            return
        self._initialized = True
        self._anim.stop()
        self._anim.setDuration(max(90, int(duration)))
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(value)
        self._anim.start()


class Badge(QFrame):
    def __init__(self, top, bottom, accent=None, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricTile")
        self.setMinimumWidth(116)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(3)
        self.top_lbl = QLabel(str(top).upper())
        self.top_lbl.setObjectName("Eyebrow")
        self.bottom_lbl = QLabel(str(bottom))
        self.bottom_lbl.setStyleSheet(
            f"font-size: 17px; font-weight: 850; color: {accent or theme.TEXT};")
        lay.addWidget(self.top_lbl)
        lay.addWidget(self.bottom_lbl)

    def set_values(self, top, bottom, accent=None):
        self.top_lbl.setText(str(top).upper())
        self.bottom_lbl.setText(str(bottom))
        self.bottom_lbl.setStyleSheet(
            f"font-size: 17px; font-weight: 850; color: {accent or theme.TEXT};")


class RankAvatar(QWidget):
    clicked = Signal()
    """Small evolving player emblem driven only by the canonical level state.

    This is intentionally abstract rather than a literal 3D character: the figure,
    rank chevrons and outer ring become more substantial as levels rise. It gives
    progression a visual identity without introducing asset/deployment complexity.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 1
        self.name = "Recruit"
        self._flash = 0.0
        self.setFixedSize(58, 58)
        self.setToolTip("Open Character")
        self._flash_anim = QVariantAnimation(self)
        self._flash_anim.setDuration(850)
        self._flash_anim.setStartValue(1.0)
        self._flash_anim.setEndValue(0.0)
        self._flash_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._flash_anim.valueChanged.connect(self._set_flash)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def _set_flash(self, value):
        self._flash = float(value)
        self.update()

    def set_level(self, level, name=""):
        level = max(1, int(level or 1))
        changed = level != self.level
        self.level = level
        self.name = str(name or self.name)
        self.setToolTip(f"Level {self.level} · {self.name}")
        self.update()
        return changed

    def celebrate(self):
        self._flash_anim.stop()
        self._flash_anim.setStartValue(1.0)
        self._flash_anim.setEndValue(0.0)
        self._flash_anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(3, 3, -3, -3)
        center = r.center()

        # quiet body / halo
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.GREEN_DARK))
        p.drawEllipse(r)

        # outer rank ring: more segments become solid as the player advances
        ring = QRectF(r).adjusted(2, 2, -2, -2)
        segments = 5
        filled = min(segments, self.level)
        for i in range(segments):
            pen = QPen(QColor(theme.GREEN if i < filled else theme.BORDER_STRONG), 2.6)
            if i >= filled:
                pen.setStyle(Qt.PenStyle.DotLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(ring, int((90 - i * 72 - 58) * 16), int(50 * 16))

        # stylized head + shoulders; it becomes visually stronger at higher tiers
        p.setPen(Qt.PenStyle.NoPen)
        body = QColor(theme.GREEN)
        body.setAlpha(205 + min(50, self.level * 8))
        p.setBrush(body)
        head_r = 5.0 + min(1.6, self.level * 0.25)
        p.drawEllipse(QPointF(center.x(), center.y() - 7), head_r, head_r)
        shoulders = QPainterPath()
        shoulders.moveTo(center.x() - 14, center.y() + 14)
        shoulders.quadTo(center.x() - 12, center.y() + 1, center.x(), center.y() + 1)
        shoulders.quadTo(center.x() + 12, center.y() + 1, center.x() + 14, center.y() + 14)
        shoulders.closeSubpath()
        p.drawPath(shoulders)

        # rank chevrons make progression readable even at tiny size
        p.setPen(QPen(QColor(theme.TEXT), 1.8))
        base_y = r.bottom() - 7
        for i in range(min(3, max(0, self.level - 1))):
            y = base_y - i * 4
            p.drawLine(QPointF(center.x() - 5, y - 2), QPointF(center.x(), y))
            p.drawLine(QPointF(center.x(), y), QPointF(center.x() + 5, y - 2))

        if self._flash > 0:
            glow = QColor(theme.GOLD)
            glow.setAlpha(int(150 * self._flash))
            p.setPen(QPen(glow, 2.0 + 3.0 * self._flash))
            p.setBrush(Qt.BrushStyle.NoBrush)
            pad = 1 + (1.0 - self._flash) * 5
            p.drawEllipse(QRectF(r).adjusted(-pad, -pad, pad, pad))


class BattleBar(QWidget):
    """Two-lane race bar with eased movement and a subtle live endpoint pulse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.you = 0.0
        self.ghost = 0.0
        self.ghost_final = 0.0
        self.record = 0.0
        self._target = (0.0, 0.0, 0.0, 0.0)
        self._initialized = False
        self._pulse_phase = 0.0
        self._impact_phase = 1.0
        self._impact_color = QColor(theme.GREEN)
        self.setMinimumHeight(92)
        self.setMaximumHeight(102)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(480)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._animate_fraction)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._pulse_timer.start(90)

        self._impact_anim = QVariantAnimation(self)
        self._impact_anim.setDuration(520)
        self._impact_anim.setStartValue(0.0)
        self._impact_anim.setEndValue(1.0)
        self._impact_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._impact_anim.valueChanged.connect(self._impact_tick)

    def _pulse_tick(self):
        if not self.isVisible():
            return
        self._pulse_phase = (self._pulse_phase + 0.28) % (math.pi * 2)
        self.update()

    def _animate_fraction(self, value):
        t = float(value)
        for name, a, b in zip(
                ("you", "ghost", "ghost_final", "record"), self._from, self._target):
            setattr(self, name, a + (b - a) * t)
        self.update()

    def _impact_tick(self, value):
        self._impact_phase = float(value)
        self.update()

    def impact(self, accent=None):
        """A short visual shockwave after a confirmed score event."""
        self._impact_color = QColor(accent or theme.GREEN)
        self._impact_phase = 0.0
        self._impact_anim.stop()
        self._impact_anim.setStartValue(0.0)
        self._impact_anim.setEndValue(1.0)
        self._impact_anim.start()

    def set_values(self, you, ghost, ghost_final=0, record=0, animate=True):
        target = tuple(max(0.0, float(v or 0)) for v in (you, ghost, ghost_final, record))
        if not self._initialized or not animate:
            self.you, self.ghost, self.ghost_final, self.record = target
            self._target = target
            self._initialized = True
            self.update()
            return
        if target == self._target:
            return
        self._anim.stop()
        self._from = (self.you, self.ghost, self.ghost_final, self.record)
        self._target = target
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        left, right = 7, 7
        top = 22
        w = max(10, r.width() - left - right)
        scale = max(1.0, self.you, self.ghost, self.ghost_final, self.record)

        def x(value):
            return left + w * max(0.0, float(value)) / scale

        track = QColor("#1d252c")
        ghost_c = QColor(theme.GHOST)
        live_c = QColor(theme.GREEN if self.you >= self.ghost else theme.RED)

        # Top/live lane.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(left, top, w, 17), 8.5, 8.5)
        live_end = max(left + 3, x(self.you))
        p.setBrush(live_c)
        p.drawRoundedRect(QRectF(left, top, max(3, live_end-left), 17), 8.5, 8.5)

        # A restrained glow around the live endpoint makes a static score feel alive.
        if self.you > 0:
            pulse = (math.sin(self._pulse_phase) + 1.0) / 2.0
            glow = QColor(live_c)
            glow.setAlpha(int(38 + pulse * 55))
            p.setBrush(glow)
            radius = 5.0 + pulse * 2.5
            p.drawEllipse(QPointF(live_end, top + 8.5), radius, radius)
            p.setBrush(live_c)
            p.drawEllipse(QPointF(live_end, top + 8.5), 3.0, 3.0)

            if self._impact_phase < 1.0:
                ring = QColor(self._impact_color)
                ring.setAlpha(int(150 * (1.0 - self._impact_phase)))
                radius = 5.0 + 22.0 * self._impact_phase
                p.setPen(QPen(ring, max(1.0, 2.6 * (1.0 - self._impact_phase))))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(live_end, top + 8.5), radius, radius)
                p.setPen(Qt.PenStyle.NoPen)

        # Bottom/ghost lane.
        ghost_top = top + 35
        p.setBrush(track)
        p.drawRoundedRect(QRectF(left, ghost_top, w, 9), 4.5, 4.5)
        faded = QColor(ghost_c)
        faded.setAlpha(165)
        p.setBrush(faded)
        p.drawRoundedRect(QRectF(left, ghost_top, max(2, x(self.ghost)-left), 9), 4.5, 4.5)

        # Same-day historical finish line.
        if self.ghost_final:
            gx = x(self.ghost_final)
            pen = QPen(QColor("#808a92"), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(gx, top-5), QPointF(gx, ghost_top+15))

        # Record target only belongs on the live lane.
        if self.record:
            rx = x(self.record)
            p.setPen(QPen(QColor(theme.GOLD), 2))
            p.drawLine(QPointF(rx, top-3), QPointF(rx, top+21))

        p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        p.setPen(QColor(theme.TEXT_2))
        p.drawText(QRectF(left, 1, 110, 16), Qt.AlignmentFlag.AlignLeft, "YOU · LIVE")
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(left, ghost_top+13, 130, 16), Qt.AlignmentFlag.AlignLeft,
                   "GHOST · SAME CLOCK")
        p.drawText(QRectF(r.width()-100, ghost_top+13, 92, 16), Qt.AlignmentFlag.AlignRight,
                   f"{scale/1000:.1f}K" if scale >= 1000 else str(int(scale)))


class Sparkline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.setMinimumHeight(145)
        self.setMaximumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_rows(self, rows):
        self.rows = list(rows or [])
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        ml, mr, mt, mb = 43, 14, 12, 24
        pw, ph = max(1, r.width()-ml-mr), max(1, r.height()-mt-mb)
        vals = [int(x.get("score_xp", 0)) for x in self.rows]
        ghosts = [int(x.get("ghost_xp", 0)) for x in self.rows]
        ymax = max([1] + vals + ghosts)

        p.setPen(QPen(QColor("#222b32"), 1))
        for frac in (0, .5, 1):
            y = mt + ph * frac
            p.drawLine(QPointF(ml, y), QPointF(r.width()-mr, y))

        def point(i, v):
            n = max(1, len(self.rows)-1)
            return QPointF(ml + pw*i/n, mt + ph*(1-max(0, v)/ymax))

        if len(self.rows) > 1:
            ghost_path = QPainterPath(point(0, ghosts[0]))
            live_path = QPainterPath(point(0, vals[0]))
            for i in range(1, len(self.rows)):
                ghost_path.lineTo(point(i, ghosts[i]))
                live_path.lineTo(point(i, vals[i]))
            gp = QPen(QColor("#667079"), 1.8)
            gp.setStyle(Qt.PenStyle.DashLine)
            p.setPen(gp)
            p.drawPath(ghost_path)
            p.setPen(QPen(QColor(theme.GREEN), 2.3))
            p.drawPath(live_path)

            # Latest-point marker: enough motion/identity without adding color noise.
            latest = point(len(vals)-1, vals[-1])
            p.setPen(Qt.PenStyle.NoPen)
            glow = QColor(theme.GREEN); glow.setAlpha(70)
            p.setBrush(glow); p.drawEllipse(latest, 6.0, 6.0)
            p.setBrush(QColor(theme.GREEN)); p.drawEllipse(latest, 2.8, 2.8)

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(0, mt-4, ml-7, 18), Qt.AlignmentFlag.AlignRight, f"{ymax:,}")
        p.drawText(QRectF(0, mt+ph-9, ml-7, 18), Qt.AlignmentFlag.AlignRight, "0")
        if self.rows:
            for idx in sorted({0, len(self.rows)//2, len(self.rows)-1}):
                row = self.rows[idx]
                pos = point(idx, 0)
                p.drawText(QRectF(pos.x()-35, r.height()-20, 70, 16),
                           Qt.AlignmentFlag.AlignCenter, row.get("weekday", ""))


class ActivityCard(QFrame):
    action = Signal(int, str)
    undo = Signal(int)

    def __init__(self, activity, record=None, parent=None):
        super().__init__(parent)
        self.setObjectName("ActivityCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.activity_id = int(activity["id"])
        self.kind = activity["kind"]
        self.setMinimumWidth(148)
        self.setMaximumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 13, 14, 12)
        lay.setSpacing(6)

        self.title_lbl = QLabel("")
        self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 850;")
        self.title_lbl.setWordWrap(True)
        lay.addWidget(self.title_lbl)

        self.xp_lbl = QLabel("")
        self.xp_lbl.setStyleSheet(f"color: {theme.GREEN}; font-weight: 750;")
        lay.addWidget(self.xp_lbl)

        self.action_button = QPushButton("")
        self.action_button.setObjectName("Primary")
        self.action_button.setMinimumHeight(38)
        self.action_button.clicked.connect(self._emit_action)
        lay.addWidget(self.action_button)

        stats = QHBoxLayout()
        self.today_lbl = QLabel("")
        self.today_lbl.setObjectName("Secondary")
        stats.addWidget(self.today_lbl)
        stats.addStretch(1)
        self.record_lbl = QLabel("")
        self.record_lbl.setObjectName("Muted")
        stats.addWidget(self.record_lbl)
        lay.addLayout(stats)

        self.undo_button = QPushButton("Undo last")
        self.undo_button.setFlat(True)
        self.undo_button.setStyleSheet(
            f"QPushButton {{color:{theme.MUTED}; border:none; background:transparent; padding:1px;}}"
            f"QPushButton:hover {{color:{theme.TEXT_2};}}")
        self.undo_button.clicked.connect(lambda: self.undo.emit(self.activity_id))
        lay.addWidget(self.undo_button, 0, Qt.AlignmentFlag.AlignRight)

        self._action_name = "increment"
        self.update_data(activity, record)

    def _emit_action(self):
        self.action.emit(self.activity_id, self._action_name)

    def update_data(self, activity, record=None):
        """Update live counts/record state without destroying the widget.

        Arena refreshes every couple of seconds. Rebuilding every Activity card
        on every tick created needless layout churn and delayed animations on
        slower Windows machines. Static roster changes still rebuild the card;
        ordinary scoring only updates these existing labels/buttons.
        """
        self.kind = activity["kind"]
        self.title_lbl.setText(str(activity["name"]).upper())
        xp = int(activity.get("xp_value", 0) or 0)
        unit = "/hr" if self.kind == "timed" else ""
        self.xp_lbl.setText(f"+{xp:,} XP{unit}")

        today = activity.get("today", {})
        units = float(today.get("units", 0) or 0)
        if self.kind == "timed":
            self._action_name = "minutes"
            self.action_button.setText("+15m")
            self.action_button.setEnabled(True)
            today_text = f"{int(round(units))} min"
        elif self.kind == "once_daily":
            self._action_name = "once"
            done = bool(today.get("complete"))
            self.action_button.setText("DONE ✓" if done else "COMPLETE")
            self.action_button.setDisabled(done)
            today_text = "Done" if done else "Not yet"
        else:
            self._action_name = "increment"
            self.action_button.setText("+1")
            self.action_button.setEnabled(True)
            today_text = f"x{int(units) if units.is_integer() else units:g}"
        self.today_lbl.setText(f"TODAY  {today_text}")

        if record:
            best = float(record.get("best_units", 0) or 0)
            if self.kind == "timed":
                rec_txt = f"BEST {int(round(best))}m"
            else:
                rec_txt = f"BEST {int(best) if best.is_integer() else best:g}"
            self.record_lbl.setText(rec_txt)
            self.record_lbl.show()
        else:
            self.record_lbl.clear()
            self.record_lbl.hide()

        self.undo_button.setVisible(units > 0)

    def flash_success(self):
        """Briefly energize the card after a confirmed backend score event."""
        self.setStyleSheet(
            f"QFrame#ActivityCard {{background:#122019; border:1px solid {theme.GREEN}; "
            "border-radius:12px;}}")
        QTimer.singleShot(260, lambda: self.setStyleSheet(""))
