"""
3D CAD model of the cooling jacket as a STEP file, as exact solids (B-rep) that open in Fusion 360, CATIA / 3DEXPERIENCE, SolidWorks
etc. and can be edited there, unlike the STL and the 3D plot, which are meshes. The file is an assembly of named and coloured parts,
with separate=True:

    Inner wall          the hot gas wall, from the contour to the bottom of the channels
    Outer wall          the closeout, from the top of the channels to the outside
    Ribs                the ribs between the channels, one body per rib
    Coolant channels    the coolant in the channels, one body per channel

and with separate=False:

    Jacket              inner wall, outer wall and ribs as one solid, with the channels as holes
    Coolant channels

The parts fill the jacket without gaps; touching faces agree to within 1e-5 mm. Where the walls and ribs are built separately their
faces are not the same surfaces though, and a boolean union of them can fail (it does in OpenCASCADE): separate=False gives the
jacket as one solid without one.

The geometry is the one of the thermal model (CoolingGeometry): the inner wall, channels and outer wall are stacked radially on the
contour, the channel sides are radial in the cross section perpendicular to the channels, and helical channels wind around the axis by
CoolingGeometry.twist. The corners of the channels can be rounded with a fillet radius against stress concentrations; the fillet is
made in the cross section perpendicular to the channel. The thermal model does not include the fillets. With fillets, the ribs reach
into the corners of the channels and end in thin lips on the inner and outer wall.

The walls are revolved about the axis, the ribs and channels are lofted through their cross sections; the jacket is sewn together
from the revolved gas side and outside, the faces of the channels and the end faces with the channel openings. No boolean operation
is needed, which would take minutes for helical channels, where long twisted faces run close to the curved walls.

Where the number of channels changes along the chamber, the ribs and channels are lofted one by one between the ribs that start and
end in the transitions, in pieces at the ends of the transitions, and the pieces of a rib or of a channel that divides are fused. The
walls are lofted through circles in the same pieces (see split_model in create_step).

The chamber axis is the x axis, lengths are in mm. The channels are open at both ends of the chamber, for manifolds to be added in CAD.
"""

import re
from collections import namedtuple
from fractions import Fraction
from math import gcd

import numpy as np

# name, colour (r, g, b from 0 to 1) and name of the bodies of the parts, in the order the solids are made
INNER = ("Inner wall", (0.80, 0.50, 0.30), "Inner wall")
OUTER = ("Outer wall", (0.65, 0.42, 0.28), "Outer wall")
RIBS = ("Ribs", (0.55, 0.35, 0.22), "Rib %d")
JACKET = ("Jacket", (0.75, 0.47, 0.29), "Jacket")
CHANNELS = ("Coolant channels", (0.30, 0.65, 0.90), "Channel %d")


def fillet_limit(cooling_geom):
    # largest fillet radius at every section [m] that leaves a straight piece of channel side and of the top and bottom of the channel.
    # The top corners are the tighter ones on the arcs: the fillet centre at r_o - f must stay within the half channel angle
    s = np.sin(cooling_geom.psi_c / 2)
    return np.minimum(cooling_geom.h_c / 2, cooling_geom.r_o * s / (1 + s))


Station = namedtuple('Station', 'x r_i r_o beta')             # where a cross section of the ribs and channels is made [mm, rad]


def create_step(cooling_geom, filepath, fillet=0.0, separate=True, n_channels=None, fillet_points=25, name="Cooling jacket",
                split_length=5e-3, min_size=0.0):
    """Writes the cooling jacket to filepath (.step) and returns a list of notes on the geometry.

    cooling_geom: CoolingGeometry after channel_geometry(); fillet: fillet radius of the channel corners [m], made smaller where the
    channel is too small for it; separate: inner wall, outer wall and ribs as parts of their own, otherwise one jacket; n_channels:
    number of channels and ribs in the model, all of them by default (fewer is quicker for a look, not where the channels split); name:
    name of the assembly; split_length: length of the transition where the number of channels changes [m], see split_model();
    min_size: smallest printable channel [m], a note says where a channel in a transition is narrower."""
    import gmsh

    cg = cooling_geom
    x = cg.geom[:,0] * 1e3
    r_c = cg.geom[:,1] * 1e3
    r_i, r_o = cg.r_i * 1e3, cg.r_o * 1e3
    r_out = r_o + cg.t_w_o * 1e3
    beta, twist = cg.beta, cg.twist
    half = cg.psi_c / 2 / np.cos(beta)                         # half angle of the channel around the axis
    counts = np.asarray(cg.n_channels, dtype=int) * np.ones(len(x), dtype=int)
    if counts.min() < 3:
        raise ValueError('The STEP model needs at least 3 cooling channels')
    split = bool(np.any(counts != counts[0]))
    if split and n_channels is not None and int(n_channels) < counts.max():
        raise ValueError('The STEP model of channels that split has all the channels')
    n_total = int(counts[0])
    n_channels = n_total if n_channels is None else int(n_channels)
    pitch = 2 * np.pi / n_total
    notes = []

    f_max = 0.9 * fillet_limit(cg)
    f = np.minimum(fillet, f_max) * 1e3
    if fillet > 0 and np.any(fillet > f_max):
        small = np.where(fillet > f_max)[0]
        notes.append("Fillet radius reduced to %.3f mm in %d of %d sections where the channel is too small for %.3f mm (x = %.1f to %.1f mm)"
                     % (f[small].min(), len(small), len(x), fillet * 1e3, x[small].min(), x[small].max()))

    initialised = gmsh.isInitialized()
    if not initialised:
        gmsh.initialize(interruptible=False)
        gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.add('cooling_jacket')
    occ = gmsh.model.occ

    def point(st, rho, phi):
        # point at the station st at radius rho and angle phi around the axis
        return occ.addPoint(st.x, rho * np.cos(phi), rho * np.sin(phi))

    def corner(st, side, fi, bottom, s, to_side):
        # corner of a channel at the station st, on the bottom or top, at the side of the channel at the angle side around the axis: s = 1
        # for the side at the larger angle, -1 for the other one. Returns the point where it starts, the point where it ends and the fillet
        # of radius fi between them (None without fillet), from the arc to the side of the channel or the other way round. The fillet is
        # made in the cross section perpendicular to the channel, where angles from the side are smaller by cos(beta) than around the axis
        r, cb = (st.r_i if bottom else st.r_o), np.cos(st.beta)
        if fi <= 0:
            p = point(st, r, side)
            return p, p, None
        up = 1 if bottom else -1
        rho_f = r + up * fi                                          # radius of the centre of the fillet
        phi_f = -s * np.arcsin(fi / rho_f)                           # angle of the centre of the fillet from the side
        start, end = (r, phi_f), (np.sqrt(rho_f**2 - fi**2), 0.0)    # on the arc and on the side
        if not to_side:
            start, end = end, start
        if st.beta == 0:
            # a circular arc in the plane of the section for axial channels
            c = point(st, rho_f, side + phi_f)
            a, b = (point(st, rho, side + th) for rho, th in (start, end))
            return a, b, occ.addCircleArc(a, c, b)
        # helical channels: the fillet is a circle perpendicular to the channel, but not in the plane of constant x. It is made a cubic
        # Bezier curve tangent to the arc and the side at its ends, fitted to the points of the fillet. The same kind of curve in every
        # section keeps the loft small: splines through the points have different knots in every section, and the loft takes them all
        cx, cy = rho_f * np.sin(phi_f), rho_f * np.cos(phi_f)
        a0, a1 = (np.arctan2(rho * np.sin(th) - cx, rho * np.cos(th) - cy) for rho, th in (start, end))
        a1 = a0 + (a1 - a0 + np.pi) % (2 * np.pi) - np.pi                       # the short way round

        def plane(ang):
            # points of the fillet in the plane of constant x, as (y, z)
            px, py = cx + fi * np.sin(ang), cy + fi * np.cos(ang)
            rho, phi = np.hypot(px, py), side + np.arctan2(px, py) / cb
            return np.column_stack((rho * np.cos(phi), rho * np.sin(phi)))

        P = plane(np.linspace(a0, a1, fillet_points))
        eps = 1e-6 * (a1 - a0)
        T0 = plane(np.array([a0 + eps]))[0] - P[0]
        T3 = P[-1] - plane(np.array([a1 - eps]))[0]
        T0, T3 = T0 / np.linalg.norm(T0), T3 / np.linalg.norm(T3)
        u = np.concatenate(([0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))))
        u = (u / u[-1])[:,None]
        # least squares for the lengths of the end tangents, the Bezier curve being linear in them
        rest = P - ((1 - u)**3 + 3 * u * (1 - u)**2) * P[0] - (3 * u**2 * (1 - u) + u**3) * P[-1]
        A = np.column_stack(((3 * u * (1 - u)**2 * T0).ravel(), (-3 * u**2 * (1 - u) * T3).ravel()))
        la, lb = np.linalg.lstsq(A, rest.ravel(), rcond=None)[0]
        a, b = (point(st, rho, side + th / cb) for rho, th in (start, end))
        inner = [occ.addPoint(st.x, *q) for q in (P[0] + la * T0, P[-1] - lb * T3)]
        return a, b, occ.addBezier([a] + inner + [b])

    def loop(st, corners, joins, add=occ.addWire):
        # closed wire (or curve loop) through the corners, joined by arcs about the axis ('arc') or straight lines ('line')
        centre = occ.addPoint(st.x, 0, 0)
        curves = []
        for k, (c, join) in enumerate(zip(corners, joins)):
            if c[2] is not None:
                curves.append(c[2])
            a, b = c[1], corners[(k + 1) % len(corners)][0]
            curves.append(occ.addCircleArc(a, centre, b) if join == 'arc' else occ.addLine(a, b))
        return add(curves)

    def channel_wire(st, left, right, f_left, f_right, add=occ.addWire):
        # channel between its sides at the angles left and right around the axis, with the fillets of the ribs on either side,
        # counterclockwise from the bottom right corner
        corners = [corner(st, right, f_right, True, 1, True), corner(st, right, f_right, False, 1, False),
                   corner(st, left, f_left, False, -1, True), corner(st, left, f_left, True, -1, False)]
        return loop(st, corners, ['line', 'arc', 'line', 'arc'], add)

    def rib_wire(st, left, right, fi):
        # rib between its sides at the angles left and right around the axis: up the side of the channel on the right, along the top
        # back to the channel on the left, down its side and along the bottom to the channel on the right again. The fillets of the
        # channel corners are part of the rib
        corners = [corner(st, right, fi, True, -1, True), corner(st, right, fi, False, -1, False), corner(st, left, fi, False, 1, True),
                   corner(st, left, fi, True, 1, False)]
        return loop(st, corners, ['line', 'arc', 'line', 'arc'])

    stations = [Station(*v) for v in zip(x, r_i, r_o, beta)]

    def channel(i, k=0, add=occ.addWire):
        # channel k, centred on the angle of the twist and k pitches
        t = twist[i] + k * pitch
        return channel_wire(stations[i], t - half[i], t + half[i], f[i], f[i], add)

    def rib(i):
        # the rib between the channel at the twist and the next channel
        t = twist[i]
        return rib_wire(stations[i], t + half[i], t + pitch - half[i], f[i])

    def revolved(r1, r2):
        # wall between the radii r1 and r2 along the chamber, revolved about the x axis
        p1, p2 = ([occ.addPoint(xi, ri, 0) for xi, ri in zip(x, r)] for r in (r1, r2))
        profile = [occ.addLine(p2[0], p1[0]), occ.addSpline(p1), occ.addLine(p1[-1], p2[-1]), -occ.addSpline(p2)]
        profile = occ.addPlaneSurface([occ.addCurveLoop(profile)])
        return [dt for dt in occ.revolve([(2, profile)], 0, 0, 0, 1, 0, 0, 2 * np.pi) if dt[0] == 3]

    def circle(xi, r, add):
        # circle about the axis starting on the y axis like the revolved faces
        return add([occ.addCircle(xi, 0, 0, r, zAxis=[1, 0, 0], xAxis=[0, 1, 0])])

    def lofted_wall(r1, r2, xs, ends):
        # wall between the radii r1 and r2 along the chamber, lofted through circles from each of the stations ends to the next like the
        # ribs and channels, so that they fit it: a loft and a spline through the same points differ near the ends of the loft
        faces = []
        for r in (r1, r2):
            for a, b in zip(ends[:-1], ends[1:]):
                faces += [dt for dt in occ.addThruSections([circle(xs[i], r[i], occ.addWire) for i in range(a, b + 1)], makeSolid=False,
                                                           makeRuled=False) if dt[0] == 2]
        for i in (0, len(xs) - 1):
            faces.append((2, occ.addPlaneSurface([circle(xs[i], r2[i], occ.addCurveLoop), circle(xs[i], r1[i], occ.addCurveLoop)])))
        return [(3, occ.addVolume([occ.addSurfaceLoop([tag for _, tag in faces], sewing=True)]))]

    def lofted(section, solid=True):
        # one rib or channel lofted through its cross sections at the stations, and turned by the channel pitch for the others. As
        # solids, or only their faces
        dim = 3 if solid else 2
        first = [dt for dt in occ.addThruSections([section(i) for i in range(len(x))], makeSolid=solid, makeRuled=False) if dt[0] == dim]
        bodies = list(first)
        for k in range(1, n_channels):
            copy = occ.copy(first)
            occ.rotate(copy, 0, 0, 0, 1, 0, 0, pitch * k)
            bodies += copy
        return bodies

    def jacket(faces, openings, xs=x, gas=r_c, outside=r_out):
        # the gas side and the outside revolved about the axis, the faces of the channels and the end faces with the openings of the
        # channels (curve loops at the first and at the last station), sewn together
        faces = list(faces)
        for r in (gas, outside):
            curve = occ.addSpline([occ.addPoint(xi, ri, 0) for xi, ri in zip(xs, r)])
            faces += [dt for dt in occ.revolve([(1, curve)], 0, 0, 0, 1, 0, 0, 2 * np.pi) if dt[0] == 2]
        for i, holes in zip((0, len(xs) - 1), openings):
            rings = [circle(xs[i], r, occ.addCurveLoop) for r in (outside[i], gas[i])]
            faces.append((2, occ.addPlaneSurface(rings + holes())))
        return [(3, occ.addVolume([occ.addSurfaceLoop([tag for _, tag in faces], sewing=True)]))]

    def split_model():
        # Channels that split: the number of channels changes between two runs of stations by a whole factor. The ribs are on one grid of
        # angles, so that the ribs of the fewer channels go on through the transition and the others start (or end) in it, in the middle of
        # a channel. Over split_length the ribs that go on change their width smoothly, and the ribs that start grow from a blunt
        # leading edge to their full width, fillets with them, so that the channel divides gradually. A channel is lofted in pieces between
        # two ribs, fused where it divides. The model repeats around the chamber: one sector is built and turned
        cuts = np.flatnonzero(np.diff(counts)) + 1
        n_run = counts[np.concatenate(([0], cuts))]                  # number of channels in each run of stations
        xm = 0.5 * (x[cuts - 1] + x[cuts])                           # centres of the transitions
        for j, (a, b) in enumerate(zip(n_run[:-1], n_run[1:])):
            if max(a, b) % min(a, b):
                raise ValueError('The %d channels do not split evenly into %d at x = %.1f mm: the STEP model needs a whole number of '
                                 'channels from each' % (min(a, b), max(a, b), xm[j]))

        # the transitions start at the first (or end at the last) section of the thermal model with the more channels and lie on that
        # side, where the thermal model has the narrower channels: the channels beside a new rib are no narrower than those it checked.
        # As long as split_length, in whole steps of the thermal model, where there is room before the neighbouring transitions and the
        # ends of the chamber
        side = np.where(n_run[1:] > n_run[:-1], 1, -1)                 # downstream for a split, upstream for a merge
        tip = np.where(side > 0, cuts, cuts - 1)                      # station where the new ribs start or end
        far = tip.copy()                                              # station at the other end of the transition
        for j in range(len(xm)):
            k = j + side[j]
            if 0 <= k < len(xm):
                room = abs(tip[k] - tip[j]) / (2 if side[k] == -side[j] else 1)
            else:
                room = len(x) - 1 - tip[j] if side[j] > 0 else tip[j]
            dx = abs(x[min(max(tip[j] + side[j], 0), len(x) - 1)] - x[tip[j]])
            wanted = max(int(round(split_length * 1e3 / dx)), 1)
            steps = min(wanted, int(0.8 * room))
            if steps < 1:
                raise ValueError('There is no room for the channel split at x = %.1f mm in the STEP model' % x[tip[j]])
            far[j] = tip[j] + side[j] * steps
            if steps < wanted:
                notes.append('The channel split at x = %.1f mm is %.1f mm long instead of %.1f mm, there is no room for more'
                             % (x[tip[j]], abs(x[far[j]] - x[tip[j]]), split_length * 1e3))
        lo, hi = x[np.minimum(tip, far)], x[np.maximum(tip, far)]
        tip, L = x[tip], hi - lo

        # stations: those of the thermal model outside the transitions, which are lofted on their own (see chunks), evenly spaced in them
        u = np.arange(17) / 16
        grid = [x[~np.any((x[:,None] > lo) & (x[:,None] < hi), axis=1)]]
        for j in range(len(xm)):
            grid.append((lo[j] + (hi[j] - lo[j]) * u)[1:-1])
        X = np.sort(np.concatenate(grid))
        p_lo, p_hi = [int(np.flatnonzero(X == v)[0]) for v in lo], [int(np.flatnonzero(X == v)[0]) for v in hi]
        zone = np.full(len(X), -1)
        for j in range(len(xm)):
            zone[p_lo[j]:p_hi[j] + 1] = j
        U = np.where(zone >= 0, (X - lo[zone]) / (hi[zone] - lo[zone]), 0.0)
        run = np.searchsorted(tip, X)                                # run of stations, outside the transitions
        RC, RI, RO, ROUT, B, TW, PSI = (np.interp(X, x, v) for v in (r_c, r_i, r_o, r_out, beta, twist, cg.psi))
        F = np.interp(X, x, f)
        for j in range(len(xm)):
            F[zone == j] = min(f[cuts[j] - 1], f[cuts[j]])
        ST = [Station(*v) for v in zip(X, RI, RO, B)]
        theta0 = np.pi / n_run[0]                                    # first rib, half a pitch from the first channel like without splits

        present = lambda q, r: (q * int(n_run[r])).denominator == 1
        # leading edge: a blunt tip of 5 % of the width, widening quickly at first and running into the full width without a kink. A
        # round (elliptic) nose widens infinitely fast at the tip, which the loft can not follow
        lead = lambda u: 0.05 + 0.95 * (1 - (1 - u)**3)

        def shape(q, p):
            # half angle around the axis and fillet radius of the rib at the angle theta0 + 2 pi q at station p. The ribs that go on
            # narrow as fast as the new ribs between them grow, which keeps the channels beside a new rib as wide as after the split
            full = lambda r: np.pi * (1 - PSI[p]) / n_run[r]
            j = zone[p]
            if j < 0:
                return full(run[p]), F[p]
            many = j + 1 if n_run[j + 1] > n_run[j] else j               # the side with more channels, where the new ribs are
            k = lead(U[p]) if many == j + 1 else lead(1 - U[p])          # how far the new ribs have grown
            if present(q, j) and present(q, j + 1):
                few = 2 * j + 1 - many
                return full(few) + (full(many) - full(few)) * k, F[p]
            return full(many) * k, F[p] * k

        # the ribs: (q, first and last station) for every run of transitions it goes through
        ribs = []
        for q in sorted({Fraction(k, int(n)) for n in set(n_run) for k in range(int(n))}):
            r = 0
            while r < len(n_run):
                if not present(q, r):
                    r += 1
                    continue
                e = r
                while e + 1 < len(n_run) and present(q, e + 1):
                    e += 1
                ribs.append((q, 0 if r == 0 else p_lo[r - 1], len(X) - 1 if e == len(n_run) - 1 else p_hi[e]))
                r = e + 1

        # the channel pieces between neighbouring ribs, from one end of a rib to the next
        breaks = sorted({0, len(X) - 1} | {p for _, p0, p1 in ribs for p in (p0, p1)})
        pieces = []                                                  # [q of the left rib, q of the right rib, first and last station]
        for p0, p1 in zip(breaks[:-1], breaks[1:]):
            active = sorted(q for q, a, b in ribs if a <= p0 and b >= p1)
            for qa, qb in zip(active, active[1:] + [active[0] + 1]):
                old = [c for c in pieces if c[:2] == [qa, qb] and c[3] == p0]
                if old:
                    old[0][3] = p1
                else:
                    pieces.append([qa, qb, p0, p1])

        def angle(q, p):
            return TW[p] + theta0 + 2 * np.pi * float(q)

        cut_at = sorted(set(p_lo) | set(p_hi))

        def chunks(section, p0, p1):
            # solids lofted through the sections from station p0 to p1, in a chunk for every transition and the stretches between them.
            # OCC fits one surface through all sections of a loft, which swings out far from the close sections of a transition when
            # the loft goes on through the sections of the thermal model
            ends = [p0] + [p for p in cut_at if p0 < p < p1] + [p1]
            return [dt for a, b in zip(ends[:-1], ends[1:])
                    for dt in occ.addThruSections([section(p) for p in range(a, b + 1)], makeSolid=True, makeRuled=False) if dt[0] == 3]

        def fused(solids):
            # one body from solids that meet at their end faces
            return occ.fuse(solids[:1], solids[1:])[0] if len(solids) > 1 else solids

        def rib_body(q, p0, p1):
            def section(p):
                h, fi = shape(q, p)
                return rib_wire(ST[p], angle(q, p) - h, angle(q, p) + h, fi)
            return fused(chunks(section, p0, p1))

        def piece_wire(c, p, add=occ.addWire):
            (ha, fa), (hb, fb) = shape(c[0] % 1, p), shape(c[1] % 1, p)
            return channel_wire(ST[p], angle(c[0], p) + ha, angle(c[1], p) - hb, fa, fb, add)

        # the narrowest channel of the model, at the bottom of the channel and perpendicular to it like in the thermal model
        w, x_w = min(((angle(c[1], p) - shape(c[1] % 1, p)[0] - angle(c[0], p) - shape(c[0] % 1, p)[0]) * RI[p] * np.cos(B[p]), X[p])
                     for c in pieces for p in range(c[2], c[3] + 1))
        if w < min_size * 1e3 * (1 - 1e-9):
            notes.append('The narrowest channel is %.2f mm wide at x = %.1f mm, less than the smallest printable channel of %.2f mm'
                         % (w, x_w, min_size * 1e3))

        def channel_bodies(c_all):
            # pieces that meet where a channel divides are one channel: fused
            group = list(range(len(c_all)))
            def root(k):
                while group[k] != k:
                    k = group[k]
                return k
            within = lambda m, a, b: (m - a) % 1 < b - a
            for k, c in enumerate(c_all):
                for l, d in enumerate(c_all):
                    if c[3] == d[2] and (within((d[0] + d[1]) / 2, c[0], c[1]) or within((c[0] + c[1]) / 2, d[0], d[1])):
                        group[root(l)] = root(k)
            bodies = []
            for g in sorted({root(k) for k in range(len(c_all))}):
                bodies += fused([dt for k, c in enumerate(c_all) if root(k) == g
                                 for dt in chunks(lambda p, c=c: piece_wire(c, p), c[2], c[3])])
            return bodies

        # one sector of the chamber, turned around it
        period = gcd(*(int(n) for n in n_run))
        sector = lambda q: q < Fraction(1, period)

        def repeated(make):
            first = make()
            bodies = list(first)
            for k in range(1, period):
                copy = occ.copy(first)
                occ.rotate(copy, 0, 0, 0, 1, 0, 0, 2 * np.pi * k / period)
                bodies += copy
            return bodies

        make_ribs = lambda: [dt for q, p0, p1 in ribs if sector(q) for dt in rib_body(q, p0, p1)]
        make_channels = lambda: channel_bodies([c for c in pieces if sector(c[0])])
        ends = lambda p: lambda: [piece_wire(c, p, occ.addCurveLoop) for c in pieces if c[2] <= p <= c[3]]

        for j in range(len(xm)):
            notes.append('The %d channels %s %d over %.1f mm at x = %.1f to %.1f mm' % (n_run[j], 'split into' if n_run[j+1] > n_run[j]
                         else 'merge into', n_run[j+1], L[j], lo[j], hi[j]))
        if separate:
            ends = [0] + cut_at + [len(X) - 1]
            return (INNER, OUTER, RIBS, CHANNELS), [lofted_wall(RC, RI, X, ends), lofted_wall(RO, ROUT, X, ends), repeated(make_ribs),
                                                    repeated(make_channels)]

        # the faces of the channels for the jacket, without their ends
        solids = repeated(make_channels)
        occ.synchronize()
        faces = gmsh.model.getBoundary(solids, combined=False, oriented=False)
        occ.remove(solids)
        box = lambda tag: occ.getBoundingBox(2, tag)
        faces = [dt for dt in faces if not (box(dt[1])[3] - box(dt[1])[0] < 1e-5 and min(abs(box(dt[1])[0] - X[[0, -1]])) < 1e-4)]
        return (JACKET, CHANNELS), [jacket(faces, (ends(0), ends(len(X) - 1)), X, RC, ROUT), repeated(make_channels)]

    try:
        if split:
            parts, bodies = split_model()
        elif separate:
            parts = (INNER, OUTER, RIBS, CHANNELS)
            bodies = [revolved(r_c, r_i), revolved(r_o, r_out), lofted(rib), lofted(channel)]
        else:
            parts = (JACKET, CHANNELS)
            ends = [lambda i=i: [channel(i, k, occ.addCurveLoop) for k in range(n_channels)] for i in (0, len(x) - 1)]
            bodies = [jacket(lofted(channel, solid=False), ends), lofted(channel)]
        # only the solids in the file, not the construction curves and points: remove keeps what is on the boundary of a solid
        for dim in (2, 1, 0):
            occ.remove(occ.getEntities(dim))
        occ.synchronize()
        gmsh.write(filepath)
    finally:
        gmsh.model.remove()
        if not initialised:
            gmsh.finalize()

    group_step_parts(filepath, name, [(part, colour, [body % (k + 1) if '%' in body else body for k in range(len(solids))])
                                      for (part, colour, body), solids in zip(parts, bodies)])
    return notes


def group_step_parts(filepath, name, parts):
    """Gives the assembly of a STEP file written by OpenCASCADE (one part per solid, named after the translator) the name of the
    assembly, and puts the solids into named and coloured parts. parts: (name of the part, (r, g, b), names of its bodies) in the order
    of the solids in the file. The first solid of every part keeps its product, the others become bodies of it."""
    with open(filepath, encoding='latin-1') as fh:
        text = fh.read()
    head, rest = text.split('DATA;', 1)
    data, tail = rest.rsplit('ENDSEC;', 1)
    ids, ents = [], {}
    for m in re.finditer(r'#(\d+)\s*=\s*(.*?);\s*(?=#\d+\s*=|$)', data, flags=re.S):
        ids.append(int(m.group(1)))
        ents[int(m.group(1))] = ' '.join(m.group(2).split())
    references = {e: [int(r) for r in re.findall(r'#(\d+)', ents[e])] for e in ids}
    referrers = {}
    for e in ids:
        for r in references[e]:
            referrers.setdefault(r, []).append(e)
    refs = lambda e: references[e]
    find = lambda kind, ref: [e for e in referrers.get(ref, []) if ents[e].startswith(kind)]

    # the solids in their order: NEXT_ASSEMBLY_USAGE_OCCURRENCE('1', ...) from the assembly to the part of the first solid, and so on
    nauo = sorted((e for e in ids if ents[e].startswith('NEXT_ASSEMBLY_USAGE_OCCURRENCE')),
                  key=lambda e: int(re.match(r"\w+\('(\d+)'", ents[e]).group(1)))
    if len(nauo) != sum(len(bodies) for _, _, bodies in parts):
        raise RuntimeError('%d solids in %s, %d expected' % (len(nauo), filepath, sum(len(b) for _, _, b in parts)))
    top_pd = refs(nauo[0])[0]
    top_product = refs(refs(top_pd)[0])[0]

    solids = []
    for e in nauo:
        pd = refs(e)[1]
        pdf = refs(pd)[0]
        product = refs(pdf)[0]
        pds = find('PRODUCT_DEFINITION_SHAPE', pd)[0]
        sdr = find('SHAPE_DEFINITION_REPRESENTATION', pds)[0]
        rep = refs(sdr)[1]
        placement = find('PRODUCT_DEFINITION_SHAPE', e)[0]
        cdsr = find('CONTEXT_DEPENDENT_SHAPE_REPRESENTATION', placement)[0]
        relation = refs(cdsr)[0]
        transform = [r for r in refs(relation) if ents[r].startswith('ITEM_DEFINED_TRANSFORMATION')]
        brep = [r for r in refs(rep) if ents[r].startswith('MANIFOLD_SOLID_BREP')]
        context = refs(rep)[-1]
        solids.append(dict(product=product, pdf=pdf, pd=pd, pds=pds, sdr=sdr, rep=rep, brep=brep, context=context,
                           structure=[e, placement, cdsr, relation] + transform + [sdr, pds, pd, pdf, product] + refs(product) + [refs(pd)[1]]
                           + find('PRODUCT_RELATED_PRODUCT_CATEGORY', product)))

    def quote(s):
        # STEP string: quotes doubled, backslashes too, and characters beyond ASCII as \X2\hhhh\X0\
        s = s.replace("\\", "\\\\").replace("'", "''")
        return "'" + ''.join(c if ord(c) < 128 else '\\X2\\%04X\\X0\\' % ord(c) for c in s if ord(c) < 0x10000) + "'"

    def rename(e, new):
        # PRODUCT('id','name',...): both strings
        ents[e] = re.sub(r"^(\w+)\('[^']*'\s*,\s*'[^']*'", lambda m: '%s(%s,%s' % (m.group(1), quote(new), quote(new)), ents[e])

    rename(top_product, name)
    new = max(ids)
    added = []
    k = 0
    for part, colour, bodies in parts:
        group = solids[k:k + len(bodies)]
        k += len(bodies)
        keep = group[0]
        rename(keep['product'], part)
        breps = []
        for solid, body in zip(group, bodies):
            for b in solid['brep']:
                ents[b] = re.sub(r"^MANIFOLD_SOLID_BREP\('[^']*'", 'MANIFOLD_SOLID_BREP(' + quote(body), ents[b])
                breps.append(b)
        # the other solids of the part become bodies of the first one, and their parts go
        items = [r for r in refs(keep['rep']) if r not in keep['brep'] and r != keep['context']]
        ents[keep['rep']] = re.sub(r"\((#[\d,#\s]*)\)", '(%s)' % ','.join('#%d' % r for r in items + breps), ents[keep['rep']], count=1)
        for solid in group[1:]:
            for e in solid['structure'] + [solid['rep']]:
                ents.pop(e, None)
        # colour of the bodies, as OpenCASCADE writes it
        style = []
        for kind, args in (('COLOUR_RGB', "'',%g,%g,%g" % colour), ('FILL_AREA_STYLE_COLOUR', "'',#{}"), ('FILL_AREA_STYLE', "'',(#{})"),
                           ('SURFACE_STYLE_FILL_AREA', '#{}'), ('SURFACE_SIDE_STYLE', "'',(#{})"), ('SURFACE_STYLE_USAGE', '.BOTH.,#{}'),
                           ('PRESENTATION_STYLE_ASSIGNMENT', '(#{})')):
            new += 1
            added.append((new, '%s(%s)' % (kind, args.format(new - 1))))
            style.append(new)
        styled = []
        for b in breps:
            new += 1
            added.append((new, "STYLED_ITEM('color',(#%d),#%d)" % (style[-1], b)))
            styled.append(new)
        new += 1
        added.append((new, "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(%s),#%d)" % (','.join('#%d' % s for s in styled),
                                                                                                 keep['context'])))

    lines = ['#%d = %s;' % (e, ents[e]) for e in ids if e in ents] + ['#%d = %s;' % a for a in added]
    with open(filepath, 'w', encoding='latin-1') as fh:
        fh.write(head + 'DATA;\n' + '\n'.join(lines) + '\nENDSEC;' + tail)
