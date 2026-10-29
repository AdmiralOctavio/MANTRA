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

The chamber axis is the x axis, lengths are in mm. The channels are open at both ends of the chamber, for manifolds to be added in CAD.
"""

import re

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


def create_step(cooling_geom, filepath, fillet=0.0, separate=True, n_channels=None, fillet_points=25, name="Cooling jacket"):
    """Writes the cooling jacket to filepath (.step) and returns a list of notes on the geometry.

    cooling_geom: CoolingGeometry after channel_geometry(); fillet: fillet radius of the channel corners [m], made smaller where the
    channel is too small for it; separate: inner wall, outer wall and ribs as parts of their own, otherwise one jacket; n_channels:
    number of channels and ribs in the model, all of them by default (fewer is quicker for a look); name: name of the assembly."""
    import gmsh

    cg = cooling_geom
    x = cg.geom[:,0] * 1e3
    r_c = cg.geom[:,1] * 1e3
    r_i, r_o = cg.r_i * 1e3, cg.r_o * 1e3
    r_out = r_o + cg.t_w_o * 1e3
    th_c = cg.psi_c / 2                                        # half angle of the channel, perpendicular to it
    beta, twist = cg.beta, cg.twist
    n_total = int(cg.n_channels)
    if n_total < 3:
        raise ValueError('The STEP model needs at least 3 cooling channels')
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

    def point(i, rho, theta, t):
        # point of the cross section at station i perpendicular to the channel, at radius rho and angle theta from the centre of the
        # channel. In the plane of constant x the channel is wider by 1 / cos(beta) around the axis, and turned by t
        phi = t + theta / np.cos(beta[i])
        return occ.addPoint(x[i], rho * np.cos(phi), rho * np.sin(phi))

    def corner(i, t, bottom, s, to_side):
        # corner of the channel centred at the angle t at station i: on the bottom or top, on the side s (+1 or -1). Returns the point
        # where it starts, the point where it ends and the fillet between them (None without fillet), from the arc to the side of the
        # channel or the other way round
        r, fi, tc = (r_i[i] if bottom else r_o[i]), f[i], th_c[i]
        if fi <= 0:
            p = point(i, r, s * tc, t)
            return p, p, None
        up = 1 if bottom else -1
        rho_f = r + up * fi                                          # radius of the centre of the fillet
        phi_f = s * (tc - np.arcsin(fi / rho_f))                     # angle of the centre of the fillet
        start, end = (r, phi_f), (np.sqrt(rho_f**2 - fi**2), s * tc)  # on the arc and on the side
        if not to_side:
            start, end = end, start
        if beta[i] == 0:
            # a circular arc in the plane of the section for axial channels
            c = occ.addPoint(x[i], rho_f * np.cos(t + phi_f), rho_f * np.sin(t + phi_f))
            a, b = (point(i, rho, th, t) for rho, th in (start, end))
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
            rho, phi = np.hypot(px, py), t + np.arctan2(px, py) / np.cos(beta[i])
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
        a, b = (point(i, rho, th, t) for rho, th in (start, end))
        inner = [occ.addPoint(x[i], *q) for q in (P[0] + la * T0, P[-1] - lb * T3)]
        return a, b, occ.addBezier([a] + inner + [b])

    def loop(i, corners, joins, add=occ.addWire):
        # closed wire (or curve loop) through the corners, joined by arcs about the axis ('arc') or straight lines ('line')
        centre = occ.addPoint(x[i], 0, 0)
        curves = []
        for k, (c, join) in enumerate(zip(corners, joins)):
            if c[2] is not None:
                curves.append(c[2])
            a, b = c[1], corners[(k + 1) % len(corners)][0]
            curves.append(occ.addCircleArc(a, centre, b) if join == 'arc' else occ.addLine(a, b))
        return add(curves)

    def channel(i, k=0, add=occ.addWire):
        # counterclockwise from the bottom right corner, with channel k centred on the angle of the twist and k pitches
        t = twist[i] + k * pitch
        corners = [corner(i, t, True, 1, True), corner(i, t, False, 1, False), corner(i, t, False, -1, True), corner(i, t, True, -1, False)]
        return loop(i, corners, ['line', 'arc', 'line', 'arc'], add)

    def rib(i):
        # the rib between the channel at the twist and the next channel: up the side of the next channel, along the top back to the
        # first channel, down its side and along the bottom to the next channel again
        t = twist[i]
        corners = [corner(i, t + pitch, True, -1, True), corner(i, t + pitch, False, -1, False), corner(i, t, False, 1, True),
                   corner(i, t, True, 1, False)]
        return loop(i, corners, ['line', 'arc', 'line', 'arc'])

    def revolved(r1, r2):
        # wall between the radii r1 and r2 along the chamber, revolved about the x axis
        p = lambda curve, end: gmsh.model.getBoundary([(1, curve)], oriented=False)[end][1]
        inner = occ.addSpline([occ.addPoint(xi, ri, 0) for xi, ri in zip(x, r1)])
        outer = occ.addSpline([occ.addPoint(xi, ri, 0) for xi, ri in zip(x, r2)])
        occ.synchronize()
        ends = [occ.addLine(p(inner, 0), p(outer, 0)), occ.addLine(p(inner, 1), p(outer, 1))]
        profile = occ.addPlaneSurface([occ.addCurveLoop([inner, ends[1], -outer, -ends[0]])])
        return [dt for dt in occ.revolve([(2, profile)], 0, 0, 0, 1, 0, 0, 2 * np.pi) if dt[0] == 3]

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

    def jacket():
        # the gas side and the outside revolved about the axis, the faces of the channels and the end faces with the openings of the
        # channels, sewn together
        faces = lofted(channel, solid=False)
        for r in (r_c, r_out):
            curve = occ.addSpline([occ.addPoint(xi, ri, 0) for xi, ri in zip(x, r)])
            faces += [dt for dt in occ.revolve([(1, curve)], 0, 0, 0, 1, 0, 0, 2 * np.pi) if dt[0] == 2]
        for i in (0, len(x) - 1):
            # circles about the axis starting on the y axis like the revolved faces
            rings = [occ.addCurveLoop([occ.addCircle(x[i], 0, 0, r, zAxis=[1, 0, 0], xAxis=[0, 1, 0])]) for r in (r_out[i], r_c[i])]
            openings = [channel(i, k, occ.addCurveLoop) for k in range(n_channels)]
            faces.append((2, occ.addPlaneSurface(rings + openings)))
        return [(3, occ.addVolume([occ.addSurfaceLoop([tag for _, tag in faces], sewing=True)]))]

    try:
        if separate:
            parts = (INNER, OUTER, RIBS, CHANNELS)
            bodies = [revolved(r_c, r_i), revolved(r_o, r_out), lofted(rib), lofted(channel)]
        else:
            parts = (JACKET, CHANNELS)
            bodies = [jacket(), lofted(channel)]
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
