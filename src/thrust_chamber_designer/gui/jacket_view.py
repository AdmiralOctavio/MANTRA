"""
Picture of the cooling jacket on the Cooling tab: a piece of the wall with a few channels, cut at a section of the chamber and drawn
in space with the wall half transparent, so that the channels show inside it, with its sizes written on the cut. Next to it the whole
chamber with the coolant in its channels under a closeout of glass, which shows the number of channels, their splits and the helix.

The pictures are drawn by a small renderer of its own: quads in space, shaded by a light, sorted from the back to the front and
painted over each other (painter's algorithm). They are rendered once at twice the size and scaled down, which smooths the edges
without seams between the quads, and kept until the geometry, the theme or the view changes. Drag a picture to turn it.
"""

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import plot_style

LIGHT = np.array([-0.42, 0.66, 0.62]) / np.linalg.norm([-0.42, 0.66, 0.62])     # from the upper left, in front of the picture
HALF = (LIGHT + np.array([0.0, 0.0, 1.0])) / np.linalg.norm(LIGHT + np.array([0.0, 0.0, 1.0]))


def _rgb(color):
    # red, green, blue (0 to 255) of a colour by its name, or as they are
    if isinstance(color, np.ndarray):
        return color
    c = QColor(color)
    return np.array([c.red(), c.green(), c.blue()], dtype=float)


def _mix(a, b, t):
    return _rgb(a) * (1 - t) + _rgb(b) * t


def rotation(yaw, pitch, base=None):
    """View of the scene: the base orientation turned by yaw around the upright axis of the picture, then tipped by pitch [deg]"""
    a, b = np.radians(yaw), np.radians(pitch)
    ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    return rx @ ry @ (np.eye(3) if base is None else base)


def polar(x, r, phi):
    """Points around the chamber axis: x along the axis, radius r, angle phi from the upright"""
    x, r, phi = np.broadcast_arrays(x, r, phi)
    return np.stack((x, r * np.cos(phi), r * np.sin(phi)), axis=-1)


class Scene:
    """Quads and lines in space. render() paints them back to front into an image."""

    def __init__(self):
        self.quads, self.looks, self.lines = [], [], []

    def surface(self, grid, color, alpha=1.0, fresnel=0.0, gloss=0.0, bias=0.0, around_axis=None, flat=False):
        """A sheet of points (n, m, 3) as quads. fresnel: the sheet gets more opaque where it is seen at a flat angle, like glass.
        around_axis: for sheets around the chamber axis, 'cull' leaves out the side away from the viewer, a number darkens it (the
        inside of the chamber, seen through its end). bias moves it to the front (> 0) in the order of painting. flat: no shading."""
        g = np.asarray(grid, dtype=float)
        q = np.stack((g[:-1, :-1], g[1:, :-1], g[1:, 1:], g[:-1, 1:]), axis=2).reshape(-1, 4, 3)
        look = np.zeros((len(q), 9))
        look[:, 0:3] = _rgb(color)
        look[:, 3], look[:, 4], look[:, 5], look[:, 6] = alpha, fresnel, gloss, bias
        look[:, 7] = {None: 0.0, "cull": -1.0}.get(around_axis, around_axis)
        look[:, 8] = 1.0 if flat else 0.0
        self.quads.append(q)
        self.looks.append(look)

    def line(self, points, color, width=1.0, alpha=1.0, bias=0.0):
        self.lines.append((np.asarray(points, dtype=float), _rgb(color), width, alpha, bias))

    def render(self, width, height, view, margins=(16, 16, 16, 16), scale=2, perspective=5.0):
        """Image (width x height pixels) of the scene seen with the rotation view, fitted between the margins (left, top, right,
        bottom). scale: the image is painted this many times larger and scaled down. Returns the image and project(points), which
        gives the pixels and the depth of points in space, to write and draw over the image."""
        image = QImage(max(int(width * scale), 1), max(int(height * scale), 1), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        quads = np.concatenate(self.quads) if self.quads else np.zeros((0, 4, 3))
        looks = np.concatenate(self.looks) if self.looks else np.zeros((0, 9))
        points = np.concatenate([quads.reshape(-1, 3)] + [line[0] for line in self.lines]) if len(quads) or self.lines else np.zeros((1, 3))
        centre = 0.5 * (points.min(axis=0) + points.max(axis=0))
        size = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0))) or 1.0
        eye = perspective * size

        def turn(p):
            v = (np.asarray(p, dtype=float) - centre) @ view.T
            f = eye / (eye - v[..., 2])
            return np.stack((v[..., 0] * f, -v[..., 1] * f, v[..., 2]), axis=-1)

        flat = turn(points)
        lo, hi = flat[:, :2].min(axis=0), flat[:, :2].max(axis=0)
        left, top, right, bottom = margins
        zoom = min((width - left - right) / max(hi[0] - lo[0], 1e-9), (height - top - bottom) / max(hi[1] - lo[1], 1e-9))
        shift = np.array([left + 0.5 * (width - left - right), top + 0.5 * (height - top - bottom)]) - zoom * 0.5 * (lo + hi)

        def project(p):
            t = turn(p)
            return np.concatenate((t[..., :2] * zoom + shift, t[..., 2:]), axis=-1)

        project.bounds = tuple(lo * zoom + shift) + tuple(hi * zoom + shift)          # left, top, right, bottom of the picture

        items = []                                      # (depth, kind, index)
        if len(quads):
            v = (quads - centre) @ view.T
            normal = np.cross(v[:, 2] - v[:, 0], v[:, 3] - v[:, 1])
            normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
            normal *= np.where(normal[:, 2:3] < 0, -1.0, 1.0)           # both sides of a sheet are lit
            # side of the chamber a quad is on: the radius through its middle, towards (> 0) or away from the viewer
            middle = quads.mean(axis=1)
            radial = np.stack((np.zeros(len(middle)), middle[:, 1], middle[:, 2]), axis=1)
            away = (radial @ view.T)[:, 2] / np.maximum(np.linalg.norm(radial, axis=1), 1e-12)
            keep = ~((looks[:, 7] < 0) & (away < -0.12))
            diffuse = np.clip(normal @ LIGHT, 0, 1)
            shade = np.where(looks[:, 8] > 0, 1.0, 0.5 + 0.58 * diffuse)
            shade *= np.where((looks[:, 7] > 0) & (away < 0), looks[:, 7], 1.0)
            shine = looks[:, 5] * np.clip(normal @ HALF, 0, 1) ** 40 * (looks[:, 8] == 0)
            rgb = np.clip(looks[:, 0:3] * shade[:, None] + 235.0 * shine[:, None], 0, 255)
            alpha = looks[:, 3] + (1 - looks[:, 3]) * looks[:, 4] * (1 - normal[:, 2]) ** 2.2
            rgba = np.concatenate((rgb, 255 * np.clip(alpha, 0, 1)[:, None]), axis=1).astype(int).tolist()
            pixels = (project(quads)[..., :2] * scale).tolist()
            depth = v[:, :, 2].mean(axis=1) + looks[:, 6] * size
            items += [(depth[i], 0, i) for i in np.flatnonzero(keep)]
        segments = []
        for points_, color, w, a, bias in self.lines:
            t = project(points_)
            for i in range(len(t) - 1):
                items.append((0.5 * (t[i, 2] + t[i + 1, 2]) + bias * size, 1, len(segments)))
                segments.append((t[i, 0] * scale, t[i, 1] * scale, t[i + 1, 0] * scale, t[i + 1, 1] * scale, color, w * scale, a))
        items.sort(key=lambda item: item[0])

        p = QPainter(image)
        p.setPen(Qt.PenStyle.NoPen)
        pen = None
        for _, kind, i in items:
            if kind == 0:
                if pen is not None:
                    p.setPen(Qt.PenStyle.NoPen)
                    pen = None
                p.setBrush(QColor(*rgba[i]))
                a, b, c, d = pixels[i]
                p.drawConvexPolygon([QPointF(*a), QPointF(*b), QPointF(*c), QPointF(*d)])
            else:
                x0, y0, x1, y1, color, w, a = segments[i]
                key = (tuple(color), w, a)
                if pen != key:
                    line_pen = QPen(QColor(int(color[0]), int(color[1]), int(color[2]), int(255 * a)), w)
                    line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(line_pen)
                    pen = key
                p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        p.end()
        if scale != 1:
            image = image.scaled(int(width), int(height), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return image, project


class JacketView(QWidget):
    """The cut piece of the jacket and the whole chamber, see the top of the file. set_geometry() gives it the contour and the
    channels, set_station() the section of the cut, set_theme() the look of plot_style."""

    STATIONS = 72           # sections of the picture of the whole chamber
    AROUND = 72             # quads around the chamber

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.theme = "light"
        self.contour = None                 # x, r [m] and the twist of the channels [rad] along the contour, None without a nozzle
        self.channels = None
        self.station = 0.0                  # x of the cut [m]
        self.message = ""
        self.angles = {"cut": [-30.0, 17.0], "chamber": [-32.0, 18.0]}     # yaw, pitch of the two pictures [deg]
        self._images = {}                   # name: (key, image, project)
        self._drag = None

    # ── what is shown ────────────────────────────────────────────────────
    def set_theme(self, theme):
        if theme != self.theme:
            self.theme = theme
            self._images.clear()
            self.update()

    def set_geometry(self, x, r, channels, message=""):
        """x, r: contour of the chamber [m], None if there is none yet (message is shown then). channels: core.design.Channels"""
        self.message = message
        self._images.clear()
        if x is None:
            self.contour = None
            self.update()
            return
        x, r = np.asarray(x, dtype=float), np.asarray(r, dtype=float)
        keep = np.concatenate(([True], np.diff(x) > 1e-9))          # the contour can hold a point twice
        x, r = x[keep], r[keep]
        self.channels = channels
        beta = np.radians(channels.helix_angle(x)) if channels.helical else np.zeros_like(x)
        r_m = r + channels.inner_wall(x) + 0.5 * channels.height(x)
        # angle of the channels around the axis, as in thermal.geometry: they advance by tan(beta) / r per length of the contour
        ds = np.hypot(np.diff(x), np.diff(r))
        twist = np.concatenate(([0.0], np.cumsum(0.5 * (np.tan(beta[1:]) / r_m[1:] + np.tan(beta[:-1]) / r_m[:-1]) * ds)))
        self.contour = (x, r, twist)
        self.station = float(np.clip(self.station, x[0], x[-1]))
        self.update()

    def set_station(self, x):
        if self.contour is not None:
            x = float(np.clip(x, self.contour[0][0], self.contour[0][-1]))
        if x != self.station:
            self.station = x
            self._images.pop("cut", None)
            self.update()

    def _at(self, x):
        """Sizes of the jacket at the axial positions x [m]: dict of arrays, lengths in mm"""
        cx, cr, ct = self.contour
        ch = self.channels
        x = np.asarray(x, dtype=float)
        r = np.interp(x, cx, cr) * 1e3
        t_i, h_c = ch.inner_wall(x) * 1e3 * np.ones_like(x), ch.height(x) * 1e3 * np.ones_like(x)
        n = np.maximum(ch.count(x), 1)
        beta = np.radians(ch.helix_angle(x)) * np.ones_like(x) if ch.helical else np.zeros_like(x)
        return {"x": x * 1e3, "r": r, "r_i": r + t_i, "r_o": r + t_i + h_c, "r_out": r + t_i + h_c + ch.outer_wall * 1e3, "n": n,
                "half": np.pi * ch.fill_factor(x) * np.ones_like(x) / n, "twist": np.interp(x, cx, ct), "beta": beta, "t_i": t_i, "h_c": h_c}

    def sizes(self):
        """Sizes at the cut for the labels, in mm: width and rib at the bottom of the channel, perpendicular to it as in the thermal
        model"""
        g = self._at(np.array([self.station]))
        n, beta = int(g["n"][0]), float(g["beta"][0])
        width = 2 * g["half"][0] * np.cos(beta) * g["r_i"][0]
        rib = (2 * np.pi / n - 2 * g["half"][0]) * np.cos(beta) * g["r_i"][0]
        return {"n": n, "width": width, "rib": rib, "height": g["h_c"][0], "inner": g["t_i"][0], "outer": self.channels.outer_wall * 1e3,
                "helix": np.degrees(beta)}

    # ── the two scenes ───────────────────────────────────────────────────
    def _look(self):
        return plot_style.palette(self.theme)["jacket"]

    def _chamber_scene(self):
        look = self._look()
        cx, cr, _ = self.contour
        s = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(cx), np.diff(cr)))))
        x = np.interp(np.linspace(0, s[-1], self.STATIONS), s, cx)
        # a section on each side of every change of the number of channels, so that the channels end and start there
        eps = 1e-6
        for x_s, _, _ in self.channels.changes():
            if cx[0] < x_s * 1e-3 < cx[-1]:
                x = np.concatenate((x, [x_s * 1e-3 - eps, x_s * 1e-3 + eps]))
        g = self._at(np.unique(x))
        around = np.linspace(0, 2 * np.pi, self.AROUND + 1)
        scene = Scene()
        wall, coolant = look["wall"], look["coolant"]
        edges = look.get("edges", 0.0)
        scene.surface(polar(g["x"][:, None], g["r_i"][:, None], around[None, :]), wall, 1.0 if not edges else 0.5, gloss=look["gloss"] * 0.5,
                      around_axis=0.55)
        scene.surface(polar(g["x"][:, None], g["r_out"][:, None], around[None, :]), wall, look["glass"], fresnel=0.55, gloss=look["gloss"],
                      around_axis="cull", bias=0.002)
        for end in (0, -1):
            ring = polar(g["x"][end], np.array([g["r_i"][end], g["r_out"][end]])[:, None], around[None, :])
            scene.surface(ring, wall, 0.95 if not edges else 0.6, gloss=0.0)
            for radius in (g["r_i"][end], g["r_out"][end]):
                scene.line(polar(g["x"][end], radius, around), _mix(wall, "#ffffff", 0.35), 0.8, 0.5 + 0.5 * edges, bias=0.004)
        # the coolant: a box per channel on the inner wall, in runs of sections with the same number of channels
        starts = np.concatenate(([0], np.flatnonzero(np.diff(g["n"])) + 1, [len(g["n"])]))
        for a, b in zip(starts[:-1], starts[1:]):
            if b - a < 2:
                continue
            n = int(g["n"][a])
            centre = g["twist"][a:b, None] + 2 * np.pi * np.arange(n)[None, :] / n
            half = g["half"][a:b, None]
            xs, r_i, r_o = g["x"][a:b, None], g["r_i"][a:b, None], g["r_o"][a:b, None]
            parts = max(1, int(np.ceil(np.degrees(2 * half.max()) / 9)))
            for k in range(parts):
                lo, hi = centre - half + 2 * half * k / parts, centre - half + 2 * half * (k + 1) / parts
                self._ribbons(scene, polar(xs, r_o, lo), polar(xs, r_o, hi), coolant, 0.92, look["gloss"] * 0.7, 0.001)
            for side in (centre - half, centre + half):
                self._ribbons(scene, polar(xs, r_i, side), polar(xs, r_o, side), _mix(coolant, "#000000", 0.18), 0.92, 0.0, 0.001)
            if edges:
                for side in (centre - half, centre + half):
                    for k in range(n):
                        scene.line(polar(xs[:, 0], r_o[:, 0], side[:, k]), _mix(coolant, "#ffffff", 0.3), 0.7, edges, bias=0.003)
        return scene

    @staticmethod
    def _ribbons(scene, a, b, color, alpha, gloss, bias):
        # strips between the curves a and b (sections, channels, 3): one sheet per channel, all as one set of quads
        q = np.stack((a[:-1], a[1:], b[1:], b[:-1]), axis=2).reshape(-1, 4, 3)
        look = np.zeros((len(q), 9))
        look[:, 0:3] = _rgb(color)
        look[:, 3], look[:, 5], look[:, 6], look[:, 7] = alpha, gloss, bias, -1.0             # -1: not drawn on the far side
        scene.quads.append(q)
        scene.looks.append(look)

    def _cut_scene(self):
        """The piece of the wall behind the cut: up to three channels wide and about half as long. Returns the scene, the base of its
        view and what the labels need."""
        look = self._look()
        cx, cr, _ = self.contour
        here = self._at(np.array([self.station]))
        n = int(here["n"][0])
        shown = min(3, n)
        pitch = 2 * np.pi / n
        span = shown * pitch
        # behind the cut the piece runs upstream, or downstream where the chamber or the run of channels ends too soon upstream
        zone = [cx[0], cx[-1]]
        for x_s, _, _ in self.channels.changes():
            if x_s * 1e-3 <= self.station:
                zone[0] = max(zone[0], x_s * 1e-3)
            else:
                zone[1] = min(zone[1], x_s * 1e-3 - 1e-6)
        length = 0.5 * min(span, 2.2) * here["r_out"][0] * 1e-3
        upstream = self.station - zone[0] >= min(length, zone[1] - self.station)
        length = max(min(length, self.station - zone[0] if upstream else zone[1] - self.station), 1e-5)
        g = self._at(self.station + (-1 if upstream else 1) * np.linspace(0, length, 14))
        x = (g["x"] - g["x"][0])[:, None]
        turn = (g["twist"] - g["twist"][0])[:, None]
        half = g["half"][:, None]
        r, r_i, r_o, r_out = (g[k][:, None] for k in ("r", "r_i", "r_o", "r_out"))
        centres = (np.arange(shown) - 0.5 * (shown - 1)) * pitch
        full = shown == n                      # the piece is the whole ring: no cut faces on its sides
        steps = lambda angle: max(2, int(np.ceil(np.degrees(angle) / 4)))

        def sheet(radius, lo, hi):
            t = np.linspace(0, 1, steps(float(np.max(hi - lo))) + 1)[None, :]
            return polar(x, radius, turn + lo + (hi - lo) * t)

        def face(i, r_a, r_b, lo, hi):
            t = np.linspace(0, 1, steps(float(hi - lo)) + 1)[None, :]
            return polar(x[i, 0], np.array([r_a[i, 0], r_b[i, 0]])[:, None], turn[i, 0] + lo + (hi - lo) * t)

        scene = Scene()
        wall, coolant = look["wall"], look["coolant"]
        edges = look.get("edges", 0.0)
        soft = 0.55 if edges else 1.0                    # the display of light of the LCARS theme is thinner all over
        ink = _mix(wall, "#000000", 0.55) if not edges else _mix(wall, "#ffffff", 0.2)
        scene.surface(sheet(r, -span / 2, span / 2), _mix(wall, "#000000", 0.25), 0.9 * soft, gloss=0.0)
        scene.surface(sheet(r_out, -span / 2, span / 2), wall, (look["glass"] + 0.14) * soft, fresnel=0.5, gloss=look["gloss"], bias=0.004)
        if not full:
            for edge in (-span / 2, span / 2):
                scene.surface(np.concatenate((polar(x, r, turn + edge), polar(x, r_out, turn + edge)), axis=1), wall, 0.5 * soft)
        for c in centres:
            scene.surface(sheet(r_i, c - half, c + half), _mix(coolant, "#000000", 0.2), 0.6 * soft)
            scene.surface(sheet(r_o, c - half, c + half), coolant, 0.5 * soft, gloss=look["gloss"] * 0.6, bias=0.002)
            for side in (c - half, c + half):
                scene.surface(np.concatenate((polar(x, r_i, turn + side), polar(x, r_o, turn + side)), axis=1),
                              _mix(coolant, "#000000", 0.1), 0.55 * soft, bias=0.001)
                scene.line(polar(x[:, 0], r_o[:, 0], (turn + side)[:, 0]), _mix(coolant, "#ffffff", 0.45), 0.9, 0.55 + 0.45 * edges, bias=0.003)
        # the two ends: wall and the openings of the channels. The cut itself is solid, the far end lets the light through
        h0 = float(half[0, 0])
        for i, (alpha, bias) in ((0, (0.96 * (0.75 if edges else 1.0), 0.006)), (-1, (0.55 * soft, -0.002))):
            hi_ = float(half[i, 0])
            bounds = [-span / 2] + [b for c in centres for b in (c - hi_, c + hi_)] + [span / 2]
            for k in range(len(bounds) - 1):
                lo, hi = bounds[k], bounds[k + 1]
                if hi - lo < 1e-9:
                    continue
                if k % 2 == 0:
                    scene.surface(face(i, r, r_out, lo, hi), wall, alpha, flat=True, bias=bias)
                else:
                    scene.surface(face(i, r, r_i, lo, hi), wall, alpha, flat=True, bias=bias)
                    scene.surface(face(i, r_o, r_out, lo, hi), wall, alpha, flat=True, bias=bias)
                    scene.surface(face(i, r_i, r_o, lo, hi), _mix(coolant, "#ffffff", 0.25), alpha, flat=True, bias=bias)
        # outlines of the cut: the wall and the openings of the channels
        arc = lambda radius, lo, hi: polar(0.0, radius, np.linspace(lo, hi, steps(hi - lo) + 1))
        r0, ri0, ro0, rout0 = float(r[0, 0]), float(r_i[0, 0]), float(r_o[0, 0]), float(r_out[0, 0])
        outline = np.concatenate((arc(r0, -span / 2, span / 2), arc(rout0, span / 2, -span / 2), arc(r0, -span / 2, -span / 2)[:1]))
        scene.line(outline, ink, 1.3, 0.9, bias=0.012)
        for c in centres:
            opening = np.concatenate((arc(ri0, c - h0, c + h0), arc(ro0, c + h0, c - h0), arc(ri0, c - h0, c - h0)[:1]))
            scene.line(opening, _mix(coolant, "#000000", 0.5) if not edges else _mix(coolant, "#ffffff", 0.4), 1.1, 0.9, bias=0.012)
        for edge in (-span / 2, span / 2):
            scene.line(polar(x[:, 0], r_out[:, 0], turn[:, 0] + edge), ink, 1.0, 0.6, bias=0.01)
        # viewer on the side of the cut: downstream of it if the piece runs upstream
        base = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], dtype=float) if upstream else np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], dtype=float)
        info = {"r": r0, "r_i": ri0, "r_o": ro0, "r_out": rout0, "half": h0, "span": span, "pitch": pitch, "centres": centres, "shown": shown}
        return scene, base, info

    # ── painting ─────────────────────────────────────────────────────────
    def _panes(self):
        """Rectangles of the cut and of the whole chamber: side by side, or the chamber under the cut in a narrow widget"""
        w, h = self.width(), self.height()
        if w >= 1.5 * h:
            split = int(0.56 * w)
            return QRectF(0, 0, split, h), QRectF(split, 0, w - split, h)
        split = int(0.6 * h)
        return QRectF(0, 0, w, split), QRectF(0, split, w, h - split)

    def _image(self, name, rect):
        ratio = self.devicePixelRatioF()
        scale = 1 if self._drag is not None else 2          # quicker while the picture is turned
        key = (int(rect.width()), int(rect.height()), tuple(self.angles[name]), scale, ratio)
        cached = self._images.get(name)
        if cached is not None and cached[0] == key:
            return cached[1:]
        if name == "cut":
            scene, base, info = self._cut_scene()
            margins = (122, 48, 30, 50)
        else:
            scene, base, info = self._chamber_scene(), None, None
            margins = (20, 44, 20, 30)
        view = rotation(*self.angles[name], base)
        image, project = scene.render(rect.width() * ratio, rect.height() * ratio, view, tuple(m * ratio for m in margins), scale)
        image.setDevicePixelRatio(ratio)
        to_widget = lambda points: project(points) / np.array([ratio, ratio, 1.0])
        to_widget.bounds = tuple(v / ratio for v in project.bounds)
        self._images[name] = (key, image, to_widget, info, view)
        return image, to_widget, info, view

    def paintEvent(self, event):
        look = self._look()
        palette = plot_style.palette(self.theme)
        ink = QColor(look["ink"])
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        gradient = QLinearGradient(0, 0, 0, self.height())
        colors = look["background"]
        for i, color in enumerate(colors):
            gradient.setColorAt(i / (len(colors) - 1), QColor(color))
        p.setPen(QPen(QColor(palette.get("frame", "#c5cad3")), 1))
        p.setBrush(gradient)
        p.drawRect(frame)
        capitals = self.theme == "lcars"
        text = lambda s: s.upper() if capitals else s
        if self.contour is None:
            p.setPen(QColor(palette.get("empty", "#8a93a3")))
            font = p.font()
            font.setPointSizeF(font.pointSizeF() * 1.15)
            p.setFont(font)
            p.drawText(frame, Qt.AlignmentFlag.AlignCenter, text(self.message))
            p.end()
            return
        try:
            cut_rect, chamber_rect = self._panes()
            cut, chamber = self._image("cut", cut_rect), self._image("chamber", chamber_rect)
        except Exception as e:                       # sizes that can not be drawn: the tab goes on working
            p.setPen(ink)
            p.drawText(frame, Qt.AlignmentFlag.AlignCenter, text("The jacket can not be drawn: %s" % e))
            p.end()
            return
        for rect, (image, project, info, view) in ((cut_rect, cut), (chamber_rect, chamber)):
            self._shadow(p, rect, project.bounds, look["shadow"])
            p.drawImage(rect.topLeft(), image)
        self._cut_labels(p, cut_rect, cut[1], cut[2], ink, text)
        self._chamber_labels(p, chamber_rect, chamber[1], chamber[3], ink, QColor(look["accent"]), text)
        # a thin line between the two pictures
        faint = QColor(ink)
        faint.setAlphaF(0.18)
        p.setPen(QPen(faint, 1))
        if chamber_rect.left() > 0:
            p.drawLine(QPointF(chamber_rect.left(), 10), QPointF(chamber_rect.left(), self.height() - 10))
        else:
            p.drawLine(QPointF(10, chamber_rect.top()), QPointF(self.width() - 10, chamber_rect.top()))
        p.end()

    def _shadow(self, p, rect, bounds, strength):
        # soft shadow on the ground under the picture, for the themes with a light background
        if strength <= 0:
            return
        left, top, right, bottom = bounds
        radius = 0.42 * (right - left)
        centre = QPointF(rect.left() + 0.5 * (left + right), min(rect.top() + bottom + 0.1 * (bottom - top) + 8, rect.bottom() - 12))
        gradient = QRadialGradient(centre, radius)
        gradient.setColorAt(0, QColor(20, 40, 70, int(255 * strength)))
        gradient.setColorAt(1, QColor(20, 40, 70, 0))
        p.save()
        p.translate(centre)
        p.scale(1.0, 0.13)
        p.translate(-centre)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gradient)
        p.drawEllipse(centre, radius, radius)
        p.restore()

    def _title(self, p, rect, ink, title, lines):
        font = p.font()
        bold = type(font)(font)
        bold.setBold(True)
        p.setFont(bold)
        p.setPen(ink)
        p.drawText(QRectF(rect.left() + 12, rect.top() + 8, rect.width() - 24, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        p.setFont(font)
        soft = QColor(ink)
        soft.setAlphaF(0.75)
        p.setPen(soft)
        p.drawText(QRectF(rect.left() + 12, rect.top() + 25, rect.width() - 24, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lines)

    def _cut_labels(self, p, rect, project, info, ink, text):
        """Sizes on the cut: the walls and the height of the channel on its left edge, width of the channel and of the rib under it"""
        s = self.sizes()
        throat = abs(self.station - self.contour[0][int(np.argmin(self.contour[1]))]) < 1e-9
        self._title(p, rect, ink, text("Section at x = %.1f mm%s" % (self.station * 1e3 + 0.0, ", the throat" if throat else "")),
                    text("%d channels%s" % (s["n"], ", helix %.0f deg, sizes perpendicular to the channels" % s["helix"] if s["helix"] > 0 else "")))
        offset = np.array([rect.left(), rect.top()])
        at = lambda radius, angle: project(polar(0.0, radius, angle))[..., :2] + offset
        span, h0, c0 = info["span"], info["half"], info["centres"][len(info["centres"]) // 2]
        pen = QPen(ink, 1)
        p.setPen(pen)
        metrics = p.fontMetrics()

        # the edge of the cut that is on the left of the picture
        edge = -span / 2 if at(info["r_out"], -span / 2)[0] < at(info["r_out"], span / 2)[0] else span / 2
        radii = [info["r"], info["r_i"], info["r_o"], info["r_out"]]
        marks = [at(radius, edge) for radius in radii]
        x_line = min(m[0] for m in marks) - 12
        for m in marks:
            p.drawLine(QPointF(m[0] - 3, m[1]), QPointF(x_line - 4, m[1]))
        p.drawLine(QPointF(x_line, marks[0][1]), QPointF(x_line, marks[-1][1]))
        names = (("Inner wall", s["inner"]), ("Height", s["height"]), ("Outer wall", s["outer"]))
        middles = [0.5 * (marks[i][1] + marks[i + 1][1]) for i in range(3)]
        # the lines of text keep their distance where the wall is thin in the picture
        spacing = metrics.height() + 1
        rows = list(middles)
        order = np.argsort(middles)
        for a, b in zip(order[:-1], order[1:]):
            rows[b] = max(rows[b], rows[a] + spacing)
        shift = (sum(middles) - sum(rows)) / 3
        for (name, value), middle, row in zip(names, middles, rows):
            row += shift
            label = text("%s %.2f mm" % (name, value))
            p.drawLine(QPointF(x_line, middle), QPointF(x_line - 7, row))
            p.drawText(QRectF(rect.left() + 2, row - spacing / 2, x_line - 10 - rect.left() - 2, spacing),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)

        # width of the middle channel and of the rib next to it, on arcs under the gas side of the wall: the width is written on the
        # left of its arc and the rib, on the side of the channel that is on the right of the picture, on the right of its arc
        gap = 0.16 * (info["r_out"] - info["r"])
        below = info["r"] - 2.2 * gap
        right = 1 if at(info["r"], c0 + h0)[0] > at(info["r"], c0 - h0)[0] else -1
        items = [("Width", s["width"], c0 - right * h0, c0 + right * h0, -1)]
        if info["shown"] > 1:
            items.append(("Rib", s["rib"], c0 + right * h0, c0 + right * (info["pitch"] - h0), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for name, value, lo, hi, side in items:
            for angle in (lo, hi):
                p.drawLine(QPointF(*at(info["r_i"] if name == "Width" or angle == lo else info["r"], angle)), QPointF(*at(below - gap, angle)))
            arc = at(below, np.linspace(lo, hi, 12))
            path = QPainterPath(QPointF(*arc[0]))
            for point in arc[1:]:
                path.lineTo(QPointF(*point))
            p.drawPath(path)
            label = text("%s %.2f mm" % (name, value))
            width = metrics.horizontalAdvance(label) + 4
            end = at(below - gap, lo if side < 0 else hi)
            box = QRectF(end[0] - 6 - width if side < 0 else end[0] + 6, end[1] - 0.5 * metrics.height(), width, metrics.height() + 2)
            # on a plate of the background, the label can lie over the far end of the piece
            plate = QColor(self._look()["background"][-1])
            plate.setAlphaF(0.72)
            p.fillRect(box.adjusted(-2, 0, 2, 0), plate)
            p.drawText(box, Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignRight if side < 0 else Qt.AlignmentFlag.AlignLeft), label)

    def _chamber_labels(self, p, rect, project, view, ink, accent, text):
        ch = self.channels
        counts = [ch.n] + [b for _, _, b in ch.changes()]
        self._title(p, rect, ink, text("Coolant in the jacket"),
                    text(" → ".join("%d" % n for n in counts) + " channels, injector to exit" if len(counts) > 1 else "%d channels" % counts[0]))
        # ring around the chamber where the cut is: the half towards the viewer, with the channels of the cut marked on it
        g = self._at(np.array([self.station]))
        around = np.linspace(0, 2 * np.pi, 181)
        ring = polar(g["x"][0], g["r_out"][0] * 1.035, around)
        radial = np.stack((np.zeros(len(around)), np.cos(around), np.sin(around)), axis=1)
        front = (radial @ view.T)[:, 2] > -0.02
        pixels = project(ring)[:, :2] + np.array([rect.left(), rect.top()])
        shown = min(3, int(g["n"][0])) * 2 * np.pi / int(g["n"][0])
        middle = np.angle(np.exp(1j * (around - g["twist"][0])))
        marked = np.abs(middle) <= shown / 2
        for mask, width in ((front, 1.6), (front & marked, 4.0)):
            pen = QPen(accent, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            for i in range(len(around) - 1):
                if mask[i] and mask[i + 1]:
                    p.drawLine(QPointF(*pixels[i]), QPointF(*pixels[i + 1]))
        soft = QColor(ink)
        soft.setAlphaF(0.55)
        p.setPen(soft)
        p.drawText(QRectF(rect.left() + 12, rect.bottom() - 24, rect.width() - 24, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   text("Drag to turn"))

    # ── turning the pictures with the mouse ──────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.contour is not None:
            cut_rect, _ = self._panes()
            name = "cut" if cut_rect.contains(event.position()) else "chamber"
            self._drag = (name, event.position(), list(self.angles[name]))
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            name, start, angles = self._drag
            d = event.position() - start
            self.angles[name] = [angles[0] + 0.4 * d.x(), float(np.clip(angles[1] + 0.4 * d.y(), -85, 85))]
            self.update()

    def mouseReleaseEvent(self, event):
        if self._drag is not None:
            self._drag = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()                    # once more at the full quality

    def mouseDoubleClickEvent(self, event):
        # back to the views the pictures start with
        self.angles = {"cut": [-30.0, 17.0], "chamber": [-32.0, 18.0]}
        self.update()
