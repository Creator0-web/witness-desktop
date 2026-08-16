from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

import character_engine

from . import theme
from .widgets import SmoothProgressBar, card


class AvatarStage(QWidget):
    """Interactive 2.5D character stage.

    Drag horizontally to rotate, wheel to zoom. The renderer is intentionally
    asset-free for V1 so we can prove the emotional/interaction system without
    introducing a 3D-engine dependency. The state contract lives in
    shared/character_engine.py and can later feed a true 3D renderer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.environment = "training"
        self.level = 1
        self.charge = 0
        self.shield = {"unlocked": False, "progress": 0, "tier": 0}
        self.yaw = 0.0
        self.zoom = 1.0
        self._drag_x = None
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)
        self.setMouseTracking(True)
        self.setToolTip("Drag left/right to rotate · Mouse wheel to zoom")

    def set_state(self, state):
        self.environment = str(state.get("environment", self.environment))
        level = state.get("level", {})
        self.level = max(1, int(level.get("current_level", self.level) or self.level))
        self.charge = max(0, min(100, int(state.get("charge", {}).get("percent", self.charge) or 0)))
        if state.get("shield"):
            self.shield = dict(state["shield"])
        self.update()

    def _tick(self):
        if not self.isVisible():
            return
        self._phase = (self._phase + 0.055) % (math.pi * 200)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_x = event.position().x()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_x is not None:
            x = event.position().x()
            delta = x - self._drag_x
            self._drag_x = x
            self.yaw = max(-78.0, min(78.0, self.yaw + delta * 0.42))
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_x = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        step = 0.06 if event.angleDelta().y() > 0 else -0.06
        self.zoom = max(0.82, min(1.28, self.zoom + step))
        self.update()
        event.accept()

    def _draw_background(self, p: QPainter, r: QRectF):
        env = self.environment
        if env == "winter":
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, QColor("#0d1720")); grad.setColorAt(1, QColor("#18242d"))
            p.fillRect(r, QBrush(grad))
            # distant snowbank
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#cfd8dc"));
            p.drawEllipse(QRectF(r.left()-80, r.bottom()-75, r.width()+160, 125))
            for i in range(58):
                x = r.left() + ((i * 83.0 + self._phase * (12 + i % 5)) % max(1, r.width()))
                y = r.top() + ((i * 47.0 + self._phase * (26 + i % 7)) % max(1, r.height()))
                a = 90 + (i % 4) * 28
                c = QColor("#e8f0f3"); c.setAlpha(a)
                p.setBrush(c)
                size = 1.8 + (i % 3) * 0.8
                p.drawEllipse(QPointF(x, y), size, size)
            return

        if env == "tropical":
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, QColor("#0b1b1a")); grad.setColorAt(1, QColor("#173027"))
            p.fillRect(r, QBrush(grad))
            p.setBrush(QColor("#d8b968")); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(r.right()-105, r.top()+90), 34, 34)
            # water / horizon
            p.setBrush(QColor("#173a38")); p.drawRect(QRectF(r.left(), r.bottom()-112, r.width(), 112))
            sway = math.sin(self._phase * 0.75) * 7
            for side in (-1, 1):
                base_x = r.center().x() + side * (r.width() * 0.34)
                p.setPen(QPen(QColor("#334a34"), 11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(base_x, r.bottom()-45), QPointF(base_x + side*16, r.top()+135))
                p.setPen(QPen(QColor("#457352"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                crown = QPointF(base_x + side*16, r.top()+135)
                for k in range(6):
                    ang = -2.6 + k * 0.52
                    ex = crown.x() + math.cos(ang) * (62 + k % 2 * 13) + sway
                    ey = crown.y() + math.sin(ang) * 40
                    p.drawLine(crown, QPointF(ex, ey))
            return

        if env == "desert":
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, QColor("#21170e")); grad.setColorAt(1, QColor("#3a2a16"))
            p.fillRect(r, QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#5b4424")); p.drawEllipse(QRectF(r.left()-120, r.bottom()-125, r.width()*0.9, 180))
            p.setBrush(QColor("#73542b")); p.drawEllipse(QRectF(r.center().x()-80, r.bottom()-105, r.width()*0.8, 150))
            for i in range(30):
                x = r.left() + ((i * 101.0 + self._phase * (18 + i % 4)) % max(1, r.width()))
                y = r.top()+70 + ((i * 59.0 + math.sin(self._phase+i) * 35) % max(1, r.height()-130))
                c = QColor("#c69a56"); c.setAlpha(35 + (i % 4)*12)
                p.setBrush(c); p.drawEllipse(QPointF(x, y), 2.2, 1.2)
            return

        if env == "city":
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, QColor("#080c12")); grad.setColorAt(1, QColor("#111922"))
            p.fillRect(r, QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            x = r.left()-5
            idx = 0
            while x < r.right()+20:
                w = 48 + (idx % 4)*13; h = 90 + (idx*37 % 150)
                p.setBrush(QColor("#10171e")); p.drawRect(QRectF(x, r.bottom()-h, w, h))
                for wy in range(int(r.bottom()-h+18), int(r.bottom()-15), 26):
                    for wx in range(int(x+12), int(x+w-8), 22):
                        if (wx + wy + idx) % 5:
                            p.setBrush(QColor("#6a845e")); p.drawRect(QRectF(wx, wy, 5, 7))
                x += w + 4; idx += 1
            for i in range(45):
                rx = r.left() + ((i * 71 + self._phase*70) % max(1, r.width()))
                ry = r.top() + ((i * 97 + self._phase*155) % max(1, r.height()))
                p.setPen(QPen(QColor(145, 165, 180, 95), 1))
                p.drawLine(QPointF(rx, ry), QPointF(rx-5, ry+16))
            return

        # Training room: intentionally neutral so the character/charge owns attention.
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0, QColor("#0a0f13")); grad.setColorAt(1, QColor("#10181d"))
        p.fillRect(r, QBrush(grad))
        p.setPen(QPen(QColor("#1e2a31"), 1))
        horizon = r.top() + r.height()*0.62
        p.drawLine(QPointF(r.left(), horizon), QPointF(r.right(), horizon))
        for i in range(-7, 8):
            bx = r.center().x() + i*54
            p.drawLine(QPointF(r.center().x(), horizon), QPointF(bx, r.bottom()))
        for j in range(6):
            y = horizon + (j+1)*(r.bottom()-horizon)/6
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        # quiet vertical status lights
        for side in (-1, 1):
            x = r.center().x() + side*r.width()*0.37
            c = QColor(theme.GREEN); c.setAlpha(60)
            p.setPen(QPen(c, 2)); p.drawLine(QPointF(x, r.top()+100), QPointF(x, r.bottom()-60))

    def _shield_polygon(self, center_x, top_y, width, height):
        return QPolygonF([
            QPointF(center_x, top_y),
            QPointF(center_x + width*0.48, top_y + height*0.14),
            QPointF(center_x + width*0.40, top_y + height*0.70),
            QPointF(center_x, top_y + height),
            QPointF(center_x - width*0.40, top_y + height*0.70),
            QPointF(center_x - width*0.48, top_y + height*0.14),
        ])

    def _draw_avatar(self, p: QPainter, r: QRectF):
        # Environment reaction: winter shiver is deliberately small; this should
        # feel alive, not comedic.
        shiver = math.sin(self._phase * 8.0) * 2.2 if self.environment == "winter" else 0.0
        idle = math.sin(self._phase * 1.25) * 1.4
        cx = r.center().x() + shiver
        ground = r.bottom() - 45

        p.save()
        p.translate(cx, ground)
        p.scale(self.zoom, self.zoom)

        yaw_rad = math.radians(self.yaw)
        front = 0.60 + 0.40 * abs(math.cos(yaw_rad))
        face_shift = math.sin(yaw_rad) * 7.0
        body_w = 88 * front

        # ground shadow
        p.setPen(Qt.PenStyle.NoPen)
        shadow = QColor(0, 0, 0, 105)
        p.setBrush(shadow); p.drawEllipse(QRectF(-64, -12, 128, 24))

        # Charge aura reflects today's performance, not permanent level.
        if self.charge > 0:
            for ring_i in range(3):
                aura = QColor(theme.GREEN)
                alpha = int((14 + self.charge*0.42) * (1.0 - ring_i*0.22))
                aura.setAlpha(max(8, min(80, alpha)))
                p.setPen(QPen(aura, 1.2 + ring_i*1.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                pulse = math.sin(self._phase*2 + ring_i)*3
                pad = 15 + ring_i*13 + pulse
                p.drawEllipse(QRectF(-body_w*0.78-pad/2, -315-pad/2,
                                     body_w*1.56+pad, 315+pad))

        # Protection shield: faint while charging, solid after 14 clean tracked days.
        shield_progress = int(self.shield.get("progress", 0) or 0)
        shield_unlocked = bool(self.shield.get("unlocked"))
        if shield_unlocked or shield_progress > 0:
            sc = QColor(theme.GREEN if shield_unlocked else theme.GHOST)
            sc.setAlpha(120 if shield_unlocked else int(25 + shield_progress*0.45))
            p.setPen(QPen(sc, 2.2 if shield_unlocked else 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(self._shield_polygon(0, -350, 180, 350))

        # legs
        limb = QColor("#496d58" if self.level < 3 else "#5e8d70")
        p.setPen(QPen(limb, 25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-24*front, -135), QPointF(-28, -30))
        p.drawLine(QPointF(24*front, -135), QPointF(28, -30))

        # boots appear at Commando+
        if self.level >= 4:
            p.setPen(QPen(QColor("#283a31"), 31, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(-28, -43), QPointF(-31, -22))
            p.drawLine(QPointF(28, -43), QPointF(31, -22))

        # arms
        p.setPen(QPen(limb, 23, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        arm_swing = math.sin(self._phase*1.25) * 2.5
        p.drawLine(QPointF(-body_w*0.52, -245), QPointF(-body_w*0.70, -150+arm_swing))
        p.drawLine(QPointF(body_w*0.52, -245), QPointF(body_w*0.70, -150-arm_swing))

        # torso silhouette
        torso = QPainterPath()
        torso.moveTo(-body_w*0.48, -275 + idle)
        torso.quadTo(-body_w*0.63, -225, -body_w*0.38, -135)
        torso.lineTo(body_w*0.38, -135)
        torso.quadTo(body_w*0.63, -225, body_w*0.48, -275 + idle)
        torso.closeSubpath()
        body = QColor("#538064" if self.level < 3 else "#67a07b")
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(body); p.drawPath(torso)

        # rank armor grows with permanent level.
        if self.level >= 2:
            armor = QColor("#223c2d"); p.setBrush(armor)
            p.drawRoundedRect(QRectF(-body_w*0.62, -276, body_w*0.35, 35), 8, 8)
            p.drawRoundedRect(QRectF(body_w*0.27, -276, body_w*0.35, 35), 8, 8)
        if self.level >= 3:
            armor = QColor("#294a35"); p.setBrush(armor)
            p.drawRoundedRect(QRectF(-body_w*0.34, -258, body_w*0.68, 92), 12, 12)
            p.setPen(QPen(QColor(theme.GREEN), 2));
            p.drawLine(QPointF(0, -250), QPointF(0, -178))
        if self.level >= 4:
            p.setPen(QPen(QColor("#2d4e39"), 29, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(-body_w*0.68, -190), QPointF(-body_w*0.72, -154))
            p.drawLine(QPointF(body_w*0.68, -190), QPointF(body_w*0.72, -154))
        if self.level >= 5:
            # Sentinel shoulder/torso energy seam.
            seam = QColor(theme.GREEN); seam.setAlpha(180)
            p.setPen(QPen(seam, 3))
            p.drawLine(QPointF(-body_w*0.39, -267), QPointF(0, -225))
            p.drawLine(QPointF(0, -225), QPointF(body_w*0.39, -267))

        # neck/head
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#6da785"))
        p.drawRoundedRect(QRectF(-13*front, -305, 26*front, 33), 8, 8)
        head = QRectF(-30*front + face_shift*0.15, -356 + idle, 60*front, 66)
        p.drawEllipse(head)

        # face/visor shifts with yaw, making rotation readable.
        p.setPen(QPen(QColor("#16231b"), 3))
        eye_y = -330 + idle
        p.drawLine(QPointF(-8*front + face_shift, eye_y), QPointF(7*front + face_shift, eye_y))
        if self.level >= 5:
            visor = QColor(theme.GREEN); visor.setAlpha(190)
            p.setPen(QPen(visor, 4))
            p.drawLine(QPointF(-17*front + face_shift, eye_y-1), QPointF(18*front + face_shift, eye_y-1))

        # winter breath
        if self.environment == "winter":
            for j in range(3):
                breath = QColor("#dce8ec"); breath.setAlpha(max(0, 58-j*14))
                p.setBrush(breath); p.setPen(Qt.PenStyle.NoPen)
                bx = 34*front + face_shift + j*10 + (self._phase*7 % 12)
                by = -318 - j*5
                p.drawEllipse(QPointF(bx, by), 5+j*2, 3+j)

        p.restore()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        self._draw_background(p, r)
        # very subtle vignette border
        p.setPen(QPen(QColor(theme.BORDER_STRONG), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), 16, 16)
        self._draw_avatar(p, r)


class TraitRow(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricTile")
        lay = QVBoxLayout(self); lay.setContentsMargins(11, 8, 11, 8); lay.setSpacing(4)
        top = QHBoxLayout()
        self.name = QLabel("ATTRIBUTE"); self.name.setStyleSheet("font-weight:850;")
        self.tier = QLabel("FORMING"); self.tier.setObjectName("Eyebrow")
        top.addWidget(self.name); top.addStretch(1); top.addWidget(self.tier)
        self.bar = QProgressBar(); self.bar.setRange(0,100); self.bar.setTextVisible(False)
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
        self._changing_env = False
        self._trait_rows = []

        root = QWidget(); self.setWidget(root)
        outer = QVBoxLayout(root); outer.setContentsMargins(18,16,18,18); outer.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout(); title_box.setSpacing(2)
        title = QLabel("CHARACTER"); title.setObjectName("PageTitle")
        sub = QLabel("A visual record of what your behavior is turning you into."); sub.setObjectName("Muted")
        title_box.addWidget(title); title_box.addWidget(sub)
        header.addLayout(title_box); header.addStretch(1)
        self.live_badge = QLabel("LIVE STATE"); self.live_badge.setStyleSheet(
            f"color:{theme.GREEN};font-weight:850;border:1px solid #2d7241;border-radius:9px;padding:6px 10px;")
        header.addWidget(self.live_badge)
        outer.addLayout(header)

        body = QHBoxLayout(); body.setSpacing(12)

        stage_card = card(strong=True)
        sl = QVBoxLayout(stage_card); sl.setContentsMargins(12,12,12,10); sl.setSpacing(8)
        stage_top = QHBoxLayout()
        st = QLabel("AVATAR"); st.setObjectName("SectionTitle")
        self.env_name = QLabel("TRAINING ROOM"); self.env_name.setObjectName("Eyebrow")
        stage_top.addWidget(st); stage_top.addStretch(1); stage_top.addWidget(self.env_name)
        sl.addLayout(stage_top)
        self.stage = AvatarStage(); sl.addWidget(self.stage, 1)
        hint = QLabel("DRAG TO ROTATE  ·  WHEEL TO ZOOM  ·  LEVEL = EVOLUTION  ·  TODAY'S XP = CHARGE")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter); hint.setObjectName("Muted")
        sl.addWidget(hint)
        body.addWidget(stage_card, 7)

        side = QVBoxLayout(); side.setSpacing(10)

        identity = card(); il = QVBoxLayout(identity); il.setContentsMargins(14,12,14,12); il.setSpacing(5)
        eye = QLabel("CURRENT FORM"); eye.setObjectName("Eyebrow")
        self.level_lbl = QLabel("LV. 1  RECRUIT"); self.level_lbl.setStyleSheet("font-size:22px;font-weight:900;")
        self.rating_lbl = QLabel("0 rolling XP"); self.rating_lbl.setObjectName("Secondary")
        self.level_bar = SmoothProgressBar(); self.level_bar.setRange(0,1000); self.level_bar.setTextVisible(False)
        il.addWidget(eye); il.addWidget(self.level_lbl); il.addWidget(self.rating_lbl); il.addWidget(self.level_bar)
        side.addWidget(identity)

        charge = card(); cl = QVBoxLayout(charge); cl.setContentsMargins(14,12,14,12); cl.setSpacing(5)
        ce = QLabel("CURRENT CHARGE"); ce.setObjectName("Eyebrow")
        row = QHBoxLayout(); self.charge_state = QLabel("DORMANT"); self.charge_state.setStyleSheet(
            f"font-size:18px;font-weight:900;color:{theme.GREEN};")
        self.charge_pct = QLabel("0%"); self.charge_pct.setStyleSheet("font-size:18px;font-weight:900;")
        row.addWidget(self.charge_state); row.addStretch(1); row.addWidget(self.charge_pct)
        self.charge_bar = SmoothProgressBar(); self.charge_bar.setRange(0,100); self.charge_bar.setTextVisible(False)
        self.charge_meta = QLabel("0 / 1,000 XP"); self.charge_meta.setObjectName("Muted")
        cl.addWidget(ce); cl.addLayout(row); cl.addWidget(self.charge_bar); cl.addWidget(self.charge_meta)
        side.addWidget(charge)

        env = card(); el = QVBoxLayout(env); el.setContentsMargins(14,12,14,12); el.setSpacing(6)
        ee = QLabel("ENVIRONMENT"); ee.setObjectName("Eyebrow")
        self.env_combo = QComboBox(); self.env_combo.currentIndexChanged.connect(self._environment_changed)
        self.env_help = QLabel(""); self.env_help.setWordWrap(True); self.env_help.setObjectName("Muted")
        el.addWidget(ee); el.addWidget(self.env_combo); el.addWidget(self.env_help)
        side.addWidget(env)

        shield = card(); sh = QVBoxLayout(shield); sh.setContentsMargins(14,12,14,12); sh.setSpacing(5)
        se = QLabel("PROTECTION SHIELD"); se.setObjectName("Eyebrow")
        srow = QHBoxLayout(); self.shield_name = QLabel("SHIELD CHARGING"); self.shield_name.setStyleSheet("font-weight:850;")
        self.shield_days = QLabel("0 / 14 DAYS"); self.shield_days.setObjectName("Secondary")
        srow.addWidget(self.shield_name); srow.addStretch(1); srow.addWidget(self.shield_days)
        self.shield_bar = QProgressBar(); self.shield_bar.setRange(0,100); self.shield_bar.setTextVisible(False)
        self.shield_help = QLabel("Requires monitored days with no drift, red-line or SOS breaches.")
        self.shield_help.setWordWrap(True); self.shield_help.setObjectName("Muted")
        sh.addWidget(se); sh.addLayout(srow); sh.addWidget(self.shield_bar); sh.addWidget(self.shield_help)
        side.addWidget(shield)

        traits = card(); tl = QVBoxLayout(traits); tl.setContentsMargins(12,11,12,12); tl.setSpacing(7)
        th = QLabel("ATTRIBUTES"); th.setObjectName("SectionTitle")
        td = QLabel("These do not award XP. They reflect behavior WITNESS has actually observed.")
        td.setWordWrap(True); td.setObjectName("Muted")
        tl.addWidget(th); tl.addWidget(td)
        self.traits_layout = QVBoxLayout(); self.traits_layout.setSpacing(6); tl.addLayout(self.traits_layout)
        side.addWidget(traits)
        side.addStretch(1)
        body.addLayout(side, 4)
        outer.addLayout(body, 1)
        self.refresh()

    def _rebuild_environments(self, snap):
        current = str(snap.get("environment", "training"))
        envs = snap.get("environments", [])
        self._changing_env = True
        self.env_combo.clear()
        current_idx = 0
        for i, e in enumerate(envs):
            text = e["name"] if e.get("unlocked") else f"{e['name']}  ·  LOCKED AT LV.{e['unlock_level']}"
            self.env_combo.addItem(text, e["id"])
            if e["id"] == current:
                current_idx = i
        self.env_combo.setCurrentIndex(current_idx)
        self._changing_env = False
        active = next((e for e in envs if e["id"] == current), None)
        self.env_help.setText(active.get("description", "") if active else "")

    def _environment_changed(self, index):
        if self._changing_env or index < 0:
            return
        env_id = self.env_combo.itemData(index)
        envs = (self._snap or {}).get("environments", [])
        row = next((e for e in envs if e.get("id") == env_id), None)
        if row and not row.get("unlocked"):
            self.env_help.setText(f"Unlocks at Level {row['unlock_level']}. Keep climbing.")
            self._rebuild_environments(self._snap or {})
            return
        try:
            character_engine.set_environment(env_id)
        except Exception as ex:
            self.env_help.setText(str(ex)); self._rebuild_environments(self._snap or {}); return
        self.refresh()

    def _apply_live(self, live, full=False):
        if self._snap is None:
            self._snap = dict(live)
        elif full:
            self._snap = dict(live)
        else:
            # preserve slow traits/shield while updating live level/charge/env
            self._snap.update({k:v for k,v in live.items() if k not in ("attributes","shield")})
        snap = self._snap
        level = snap.get("level", {})
        self.level_lbl.setText(f"LV. {level.get('current_level',1)}  {str(level.get('name','Recruit')).upper()}")
        rating = int(level.get("rating", 0) or 0)
        nxt = level.get("next_threshold")
        if nxt:
            start = int(level.get("entry_threshold",0) or 0); end = int(nxt or 1)
            frac = (rating-start)/max(1,end-start)
            self.level_bar.set_target_value(max(0,min(1000,int(frac*1000))))
            self.rating_lbl.setText(f"{rating:,} rolling XP · {max(0,int(level.get('xp_to_next',0))):,} to next form")
        else:
            self.level_bar.set_target_value(1000); self.rating_lbl.setText(f"{rating:,} rolling XP · top V1 form")

        ch = snap.get("charge", {})
        pct = int(ch.get("percent",0) or 0)
        self.charge_state.setText(str(ch.get("state","DORMANT")))
        self.charge_pct.setText(f"{pct}%")
        self.charge_bar.set_target_value(pct)
        self.charge_meta.setText(f"{int(ch.get('current_xp',0)):,} / {int(ch.get('target_xp',1000)):,} XP today")

        env_id = snap.get("environment","training")
        env = next((e for e in snap.get("environments",[]) if e.get("id")==env_id), None)
        self.env_name.setText(str(env.get("name","Training Room")).upper() if env else "TRAINING ROOM")
        self.stage.set_state(snap)

        if full:
            self._rebuild_environments(snap)
            sh = snap.get("shield", {})
            self.shield_name.setText(str(sh.get("name","SHIELD CHARGING")))
            days = int(sh.get("clean_days",0) or 0); target = sh.get("next_target") or days
            self.shield_days.setText(f"{days} / {target} DAYS" if sh.get("next_target") else f"{days} CLEAN DAYS")
            self.shield_bar.setValue(int(sh.get("progress",0) or 0))
            if not sh.get("tracking_today"):
                self.shield_help.setText(
                    "Protection progress only counts monitored days. The current Qt shell does not yet start Layer-1 tracking by itself.")
            elif sh.get("unlocked"):
                self.shield_help.setText("Shield active. Longer clean streaks strengthen it further.")
            else:
                self.shield_help.setText("14 clean monitored days unlock the first shield.")

            attrs = snap.get("attributes", [])
            while len(self._trait_rows) < len(attrs):
                row = TraitRow(); self._trait_rows.append(row); self.traits_layout.addWidget(row)
            for i, row in enumerate(self._trait_rows):
                if i < len(attrs):
                    row.show(); row.set_trait(attrs[i])
                else:
                    row.hide()

    def refresh(self):
        try:
            snap = character_engine.snapshot()
        except Exception as ex:
            self.env_help.setText(f"Character state unavailable: {ex}")
            return
        self._apply_live(snap, full=True)

    def live_refresh(self):
        try:
            live = character_engine.live_state()
        except Exception:
            return
        self._apply_live(live, full=False)
