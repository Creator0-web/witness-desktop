"""Dependency-free interactive 3D prototype for the WITNESS Character page.

This is intentionally a *prototype mesh*, not the final production avatar.
It uses actual 3D geometry, perspective projection and user-controlled rotation,
but renders through QPainter so the installed app does not need OpenGL/Qt3D or a
new binary dependency.  The contract is designed so a rigged GLB/FBX renderer can
replace this widget later without changing Character state semantics.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme


Vec3 = tuple[float, float, float]


def _vadd(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vsub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vmul(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Vec3) -> float:
    return math.sqrt(max(1e-12, _dot(a, a)))


def _unit(a: Vec3) -> Vec3:
    n = _norm(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def _mix(c: QColor, factor: float) -> QColor:
    factor = max(0.0, min(1.4, factor))
    return QColor(
        max(0, min(255, int(c.red() * factor))),
        max(0, min(255, int(c.green() * factor))),
        max(0, min(255, int(c.blue() * factor))),
        c.alpha(),
    )


def _box(center: Vec3, size: Vec3, color: str) -> list[tuple[list[Vec3], str]]:
    cx, cy, cz = center; sx, sy, sz = size
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz - sz / 2, cz + sz / 2
    v = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    idx = ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (3, 2, 6, 7), (1, 5, 6, 2), (0, 3, 7, 4))
    return [([v[i] for i in face], color) for face in idx]


def _tapered_box(center: Vec3, top_w: float, bottom_w: float, height: float, depth: float, color: str) -> list[tuple[list[Vec3], str]]:
    cx, cy, cz = center; y0, y1 = cy - height / 2, cy + height / 2
    b = bottom_w / 2; t = top_w / 2; d = depth / 2
    v = [(-b, y0, -d), (b, y0, -d), (t, y1, -d), (-t, y1, -d),
         (-b, y0, d), (b, y0, d), (t, y1, d), (-t, y1, d)]
    v = [(x + cx, y, z + cz) for x, y, z in v]
    idx = ((0,1,2,3),(4,7,6,5),(0,4,5,1),(3,2,6,7),(1,5,6,2),(0,3,7,4))
    return [([v[i] for i in face], color) for face in idx]


def _ellipsoid(center: Vec3, scale: Vec3, color: str, lon=10, lat=6) -> list[tuple[list[Vec3], str]]:
    cx, cy, cz = center; sx, sy, sz = scale
    rings: list[list[Vec3]] = []
    for j in range(1, lat):
        phi = -math.pi / 2 + math.pi * j / lat
        cp, sp = math.cos(phi), math.sin(phi)
        ring = []
        for i in range(lon):
            th = 2 * math.pi * i / lon
            ring.append((cx + sx * cp * math.cos(th), cy + sy * sp, cz + sz * cp * math.sin(th)))
        rings.append(ring)
    bottom = (cx, cy - sy, cz); top = (cx, cy + sy, cz)
    faces = []
    if rings:
        first = rings[0]; last = rings[-1]
        for i in range(lon):
            ni = (i + 1) % lon
            faces.append(([bottom, first[ni], first[i]], color))
            faces.append(([last[i], last[ni], top], color))
        for r0, r1 in zip(rings, rings[1:]):
            for i in range(lon):
                ni = (i + 1) % lon
                faces.append(([r0[i], r0[ni], r1[ni], r1[i]], color))
    return faces


def _cylinder_between(a: Vec3, b: Vec3, radius: float, color: str, sides=8) -> list[tuple[list[Vec3], str]]:
    axis = _unit(_vsub(b, a))
    helper = (0.0, 0.0, 1.0) if abs(axis[2]) < 0.85 else (1.0, 0.0, 0.0)
    u = _unit(_cross(axis, helper)); v = _unit(_cross(axis, u))
    ra = []; rb = []
    for i in range(sides):
        th = 2 * math.pi * i / sides
        off = _vadd(_vmul(u, radius * math.cos(th)), _vmul(v, radius * math.sin(th)))
        ra.append(_vadd(a, off)); rb.append(_vadd(b, off))
    faces = []
    for i in range(sides):
        ni = (i + 1) % sides
        faces.append(([ra[i], ra[ni], rb[ni], rb[i]], color))
    faces.append((list(reversed(ra)), color)); faces.append((rb, color))
    return faces


_STAGE = {
    1: dict(top="#c8bca3", pants="#6d5845", boot=None, accent="#355d43", jacket=None),
    2: dict(top="#bcae94", pants="#65513f", boot=None, accent="#31583f", jacket=None),
    3: dict(top="#26362f", pants="#242824", boot=None, accent="#315940", jacket=None),
    4: dict(top="#252a28", pants="#202326", boot="#171a1c", accent="#31543c", jacket="#343833"),
    5: dict(top="#171b1c", pants="#171a1c", boot="#101316", accent="#2d5039", jacket="#24292a"),
    6: dict(top="#10151a", pants="#11161a", boot="#0c1013", accent="#284c39", jacket="#151b20"),
    7: dict(top="#0b0e12", pants="#0b0e11", boot="#080a0c", accent="#244735", jacket="#12161b"),
    8: dict(top="#090b0e", pants="#090b0e", boot="#07090b", accent="#213f31", jacket="#0e1216"),
}


class Character3DView(QWidget):
    """Interactive procedural humanoid used to prove the 3D interaction model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.stage = {"index": 1, "name": "Wanderer"}
        self.state = {"charge": {"percent": 0}, "reserve": {"percent": 0}, "shield": {}}
        self.yaw = -0.10
        self.pitch = -0.03
        self._target_yaw = self.yaw
        self._target_pitch = self.pitch
        self.zoom = 1.0
        self._drag = None
        self._phase = 0.0
        self.auto_rotate = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)
        self.setToolTip("3D prototype · drag slowly to inspect · wheel to zoom · double-click to reset")

    def set_scene(self, stage: dict, state: dict):
        self.stage = dict(stage or {"index": 1, "name": "Wanderer"})
        self.state = dict(state or {})
        self.update()

    def set_auto_rotate(self, enabled: bool):
        self.auto_rotate = bool(enabled)

    def reset_view(self):
        self.yaw = -0.10; self.pitch = -0.03
        self._target_yaw = self.yaw; self._target_pitch = self.pitch
        self.zoom = 1.0
        self.update()

    def _tick(self):
        if not self.isVisible():
            return
        self._phase += 0.035
        # Rotation is deliberately weighty. Drag changes a target orientation;
        # the rendered body eases toward it rather than snapping to the cursor.
        # This gives the avatar a slower, more powerful inspection feel.
        if self.auto_rotate and self._drag is None:
            self._target_yaw += 0.0032
        self.yaw += (self._target_yaw - self.yaw) * 0.16
        self.pitch += (self._target_pitch - self.pitch) * 0.16
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            pos = event.position(); dx = pos.x() - self._drag.x(); dy = pos.y() - self._drag.y(); self._drag = pos
            # Natural object-drag direction: dragging right turns the character
            # toward the right; dragging up tilts the view upward. The v7.56.0
            # prototype felt inverted on both axes and too sensitive.
            self._target_yaw -= dx * 0.0045
            self._target_pitch = max(-0.55, min(0.42, self._target_pitch - dy * 0.0035))
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = None; self.unsetCursor()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        self.zoom = max(0.72, min(1.55, self.zoom + (0.07 if event.angleDelta().y() > 0 else -0.07)))
        self.update(); event.accept()

    def mouseDoubleClickEvent(self, event):
        self.reset_view(); super().mouseDoubleClickEvent(event)

    def _rotate(self, p: Vec3) -> Vec3:
        x, y, z = p
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        x, z = x * cy + z * sy, -x * sy + z * cy
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        y, z = y * cp - z * sp, y * sp + z * cp
        return (x, y, z)

    def _project(self, p: Vec3, rect: QRectF) -> tuple[QPointF, float]:
        x, y, z = self._rotate(p)
        cam = 5.6 + z
        focal = min(rect.width(), rect.height()) * 1.62 * self.zoom
        s = focal / max(1.7, cam)
        cx = rect.center().x(); cy = rect.center().y() + rect.height() * 0.10
        return QPointF(cx + x * s, cy - y * s), cam

    def _profile(self) -> dict:
        idx = max(1, min(8, int(self.stage.get("index", 1) or 1)))
        return dict(_STAGE[idx])

    def _mesh(self) -> list[tuple[list[Vec3], str]]:
        idx = max(1, min(8, int(self.stage.get("index", 1) or 1)))
        pr = self._profile(); faces = []
        breathe = 1.0 + math.sin(self._phase) * 0.018
        skin = "#9c6a50"; hair = "#111214"

        # Core body. The early stages are intentionally lean; later forms fill out
        # through shoulders/torso rather than becoming bulky.
        shoulder = 0.82 + min(0.13, (idx - 1) * 0.022)
        waist = 0.54 + min(0.08, (idx - 1) * 0.012)
        faces += _tapered_box((0, 0.67, 0), shoulder, waist, 1.12 * breathe, 0.38, pr["top"])
        faces += _tapered_box((0, -0.02, 0), waist, 0.60, 0.34, 0.34, pr["pants"])
        faces += _cylinder_between((-0.22, -0.17, 0), (-0.25, -1.05, 0.015), 0.17, pr["pants"])
        faces += _cylinder_between((0.22, -0.17, 0), (0.25, -1.05, 0.015), 0.17, pr["pants"])
        faces += _cylinder_between((-0.25, -1.03, 0.015), (-0.23, -1.77, 0.00), 0.145, pr["pants"])
        faces += _cylinder_between((0.25, -1.03, 0.015), (0.23, -1.77, 0.00), 0.145, pr["pants"])

        # Arms become slightly more athletic with progression.
        ar = 0.12 + min(0.025, idx * 0.003)
        faces += _cylinder_between((-shoulder/2 + 0.04, 1.05, 0), (-0.56, 0.40, 0.01), ar, pr["top"])
        faces += _cylinder_between((shoulder/2 - 0.04, 1.05, 0), (0.56, 0.40, 0.01), ar, pr["top"])
        faces += _cylinder_between((-0.56, 0.40, 0.01), (-0.49, -0.12, -0.01), ar * 0.86, skin)
        faces += _cylinder_between((0.56, 0.40, 0.01), (0.49, -0.12, -0.01), ar * 0.86, skin)
        faces += _ellipsoid((-0.49, -0.20, -0.02), (0.11, 0.14, 0.08), skin, 8, 5)
        faces += _ellipsoid((0.49, -0.20, -0.02), (0.11, 0.14, 0.08), skin, 8, 5)

        # Neck/head/hair preserve the recognizable curly silhouette.
        faces += _cylinder_between((0, 1.20, 0), (0, 1.38, 0), 0.12, skin, 8)
        faces += _ellipsoid((0, 1.61, -0.01), (0.255, 0.315, 0.225), skin, 12, 7)
        curl_centers = [(-.20,1.86,-.01),(-.11,1.94,-.02),(0,1.95,-.02),(.11,1.93,-.01),(.20,1.85,0),
                        (-.24,1.75,.02),(.24,1.75,.02),(-.14,1.80,-.18),(.14,1.81,-.18)]
        for c in curl_centers:
            faces += _ellipsoid(c, (0.10, 0.11, 0.09), hair, 7, 4)

        # Sash / continuity accent shrinks as the character becomes more refined.
        accent = pr["accent"]
        if idx <= 4:
            faces += _box((0, 0.05, -0.20), (0.70, 0.14, 0.08), accent)
            faces += _box((0.18, -0.38, -0.18), (0.13, 0.70, 0.05), accent)
        elif idx <= 6:
            faces += _box((0.20, -0.03, -0.20), (0.24, 0.08, 0.06), accent)
        else:
            faces += _box((0.18, 0.70, -0.205), (0.05, 0.42, 0.035), accent)

        # Footwear arrives with Builder.
        if pr["boot"]:
            faces += _box((-0.23, -1.78, -0.07), (0.30, 0.22, 0.48), pr["boot"])
            faces += _box((0.23, -1.78, -0.07), (0.30, 0.22, 0.48), pr["boot"])
        else:
            faces += _ellipsoid((-0.23, -1.79, -0.08), (0.15, 0.09, 0.24), skin, 8, 4)
            faces += _ellipsoid((0.23, -1.79, -0.08), (0.15, 0.09, 0.24), skin, 8, 4)

        # Progressive equipment / tailoring.
        if idx == 2:  # dagger
            faces += _box((0.34, -0.10, -0.24), (0.07, 0.42, 0.06), "#4d3a28")
        if idx == 3:  # training staff behind right side
            faces += _cylinder_between((0.38, -1.55, 0.20), (0.52, 1.45, 0.25), 0.035, "#60462d", 7)
        if idx >= 4 and pr["jacket"]:
            # Open structured layer: narrow panels leave the inner Core visible.
            faces += _tapered_box((-0.26, 0.66, -0.035), 0.28, 0.18, 1.16, 0.41, pr["jacket"])
            faces += _tapered_box((0.26, 0.66, -0.035), 0.28, 0.18, 1.16, 0.41, pr["jacket"])
        if idx == 6:
            # Tight tactical harness, not bulk.
            faces += _box((-0.26, 0.80, -0.225), (0.055, 0.62, 0.035), "#2d3338")
            faces += _box((0.26, 0.80, -0.225), (0.055, 0.62, 0.035), "#2d3338")
        if idx >= 7:
            # Clean lapel lines; visible gear disappears.
            faces += _box((-0.13, 0.82, -0.23), (0.045, 0.58, 0.028), "#2c3034")
            faces += _box((0.13, 0.82, -0.23), (0.045, 0.58, 0.028), "#2c3034")
        if idx == 8:
            # Slim Sovereign coat tails keep the athletic silhouette.
            faces += _tapered_box((-0.28, -0.20, 0.10), 0.25, 0.36, 1.65, 0.10, "#0b0e12")
            faces += _tapered_box((0.28, -0.20, 0.10), 0.25, 0.36, 1.65, 0.10, "#0b0e12")
        return faces

    def _draw_environment(self, p: QPainter, r: QRectF, idx: int):
        era = theme.era_for_level(idx)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, QColor(era["bg_2"])); grad.setColorAt(1.0, QColor(era["bg"]))
        p.fillRect(r, grad)
        p.save(); p.setPen(Qt.PenStyle.NoPen)
        if idx <= 2:
            # Jungle: shadow leaves and slow fireflies.
            leaf = QColor("#173422"); leaf.setAlpha(120); p.setBrush(leaf)
            for i in range(9):
                x = r.left() + (i % 3) * r.width() * 0.42 - r.width() * 0.10
                y = r.top() + (i // 3) * r.height() * 0.34
                p.drawEllipse(QRectF(x, y, r.width()*0.25, r.height()*0.11))
            for i in range(25):
                x = r.left() + ((i * 137 + math.sin(self._phase * .4 + i) * 21) % max(1, int(r.width())))
                y = r.top() + ((i * 79 - self._phase * (2+i%3)) % max(1, int(r.height())))
                c = QColor("#d9bc68"); c.setAlpha(45 + (i % 4)*12); p.setBrush(c)
                p.drawEllipse(QPointF(x, y), 1.2, 1.2)
        elif idx <= 4:
            # Forged: ruined/constructed vertical forms and ember points.
            pillar = QColor("#2d302d"); pillar.setAlpha(150); p.setBrush(pillar)
            for xmul, wmul, hmul in ((.05,.10,.70),(.18,.06,.48),(.78,.08,.62),(.89,.12,.78)):
                p.drawRect(QRectF(r.left()+r.width()*xmul, r.bottom()-r.height()*hmul, r.width()*wmul, r.height()*hmul))
            for i in range(18):
                x = r.left() + (i*103 % max(1,int(r.width()))); y = r.bottom() - (i*61 % max(1,int(r.height()*.45)))
                c = QColor("#b4874f"); c.setAlpha(35 + (i%3)*15); p.setBrush(c); p.drawEllipse(QPointF(x,y),1.1,1.1)
        else:
            # Noir city silhouette. Stage 5 is older/denser, 6+ progressively cleaner.
            base = r.bottom() - r.height() * 0.12
            for i in range(18):
                x = r.left() + i * r.width()/18.0
                bw = r.width()/22.0
                h = r.height() * (0.18 + ((i*37)%45)/100.0)
                c = QColor("#111820"); c.setAlpha(215); p.setBrush(c)
                p.drawRect(QRectF(x, base-h, bw, h))
                if i % 2 == 0:
                    p.setBrush(QColor(186,154,91,70));
                    for j in range(3):
                        p.drawRect(QRectF(x+bw*.25, base-h+bw*(1+j*1.7), 2.0, 2.0))
        p.restore()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1,1,-1,-1)
        idx = max(1, min(8, int(self.stage.get("index", 1) or 1)))
        self._draw_environment(p, r, idx)

        charge = max(0, min(100, int((self.state.get("charge") or {}).get("percent", 0) or 0)))
        reserve = max(0, min(100, int((self.state.get("reserve") or {}).get("percent", 0) or 0)))

        # Outer charge field behind geometry.
        if charge > 0:
            center = QPointF(r.center().x(), r.center().y() + r.height()*0.03)
            radius = min(r.width(), r.height()) * (0.27 + charge/1000.0)
            g = QRadialGradient(center, radius)
            c0 = QColor(theme.GREEN); c0.setAlpha(int(10 + charge*.28)); c1 = QColor(theme.GREEN); c1.setAlpha(0)
            g.setColorAt(0.0, c0); g.setColorAt(1.0, c1); p.setPen(Qt.PenStyle.NoPen); p.setBrush(g)
            p.drawEllipse(center, radius, radius*1.28)

        raw_faces = self._mesh(); rendered = []
        light = _unit((-0.45, 0.75, -0.75))
        for points, color in raw_faces:
            rp = [self._rotate(x) for x in points]
            depth = sum(x[2] + 5.6 for x in rp) / max(1, len(rp))
            a, b, c = rp[0], rp[1], rp[2]
            n = _unit(_cross(_vsub(b,a), _vsub(c,a)))
            shade = 0.48 + 0.52 * max(0.0, _dot(n, light))
            poly = QPolygonF([self._project(x, r)[0] for x in points])
            rendered.append((depth, poly, _mix(QColor(color), shade)))
        # Further faces first (larger z / larger camera distance).
        rendered.sort(key=lambda x: x[0], reverse=True)
        p.setPen(QPen(QColor(255,255,255,17), 0.65))
        for _, poly, color in rendered:
            p.setBrush(color); p.drawPolygon(poly)

        # Core glow is projected from the actual chest position and rotates with the body.
        core_pt, core_depth = self._project((0, 0.79, -0.25), r)
        pulse = 0.92 + math.sin(self._phase*1.5) * 0.08
        radius = (8.0 + reserve * 0.14) * pulse * self.zoom
        g = QRadialGradient(core_pt, radius * 2.6)
        inner = QColor(theme.GOLD); inner.setAlpha(int(80 + reserve*1.35)); mid = QColor(theme.GOLD); mid.setAlpha(int(28 + reserve*.42)); edge = QColor(theme.GOLD); edge.setAlpha(0)
        g.setColorAt(0.0, inner); g.setColorAt(.38, mid); g.setColorAt(1.0, edge)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(g); p.drawEllipse(core_pt, radius*2.6, radius*2.6)
        p.setBrush(QColor(245,211,119, min(240, 100+reserve))); p.drawEllipse(core_pt, max(2.4,radius*.24), max(2.4,radius*.24))

        # Face detail after the mesh keeps the prototype from reading as a mannequin.
        for x in (-0.08, 0.08):
            eye, _ = self._project((x, 1.66, -0.225), r)
            p.setBrush(QColor("#151719")); p.drawEllipse(eye, 2.0*self.zoom, 1.3*self.zoom)

        tokens = theme.current_tokens()
        p.setPen(QColor(tokens["accent"])); f = p.font(); f.setPointSize(9); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(r.left()+14, r.top()+12, r.width()-28, 22), Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
                   f"3D LAB · {str(self.stage.get('name','WANDERER')).upper()} · PROTOTYPE MESH")
        p.setPen(QColor(theme.MUTED)); f.setPointSize(8); f.setBold(False); p.setFont(f)
        p.drawText(QRectF(r.left()+14, r.bottom()-28, r.width()-28, 18), Qt.AlignmentFlag.AlignCenter,
                   "DRAG TO ROTATE · WHEEL TO ZOOM · DOUBLE-CLICK TO RESET")
