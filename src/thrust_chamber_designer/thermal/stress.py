#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Wall stress analysis of the 2D sections                           #
# License:	GNU GENERAL PUBLIC LICENSE V3							#
#####################################################################

import numpy as np


# regimes of the Bree diagram, in the order used in the summary and the plots
REGIMES = {
    'E': 'elastic',
    'S': 'shakedown',
    'P': 'plastic cycling',
    'R': 'ratcheting',
    'C': 'plastic collapse',
}


def bree_regime(X, Y):
    # Classification after Bree for a steady primary stress and a cyclic secondary stress in an elastic - perfectly plastic material
    # X: primary stress / yield strength, Y: range of the elastically calculated secondary stress / yield strength
    if X >= 1:
        return 'C'
    if X + Y <= 1:
        return 'E'
    if Y <= 2 and X + Y / 4 <= 1:
        return 'S'
    if Y > 2 and X * Y <= 1:
        return 'P'
    return 'R'


class WallStress():
    """[Summary]
    Elastic estimate of the stresses in the chamber wall of one 2D section, from the temperature field of the thermal sim and the pressures
    of coolant and hot gas. The stresses are for steady state firing, the wall is free of stress at the reference temperature.
    Primary stresses (pressure): bending of the inner wall between the ribs and hoop membrane stress of the whole wall.
    Secondary stresses (temperature): the hot inner wall is held back by ribs and outer wall (mismatch) and the temperature difference
    through the inner wall bends it (gradient). Both are compressive at the hot gas side.
    Sections do not interact, loads from thrust, mounting, manifolds and start up or shut down transients are NOT included.
    """
    def __init__(self, material, cooling_geometry, T_ref):
        self.material         = material                 # material object
        self.cooling_geometry = cooling_geometry         # cooling channel geometry object
        self.T_ref            = T_ref                    # temperature at which the wall is free of thermal stress [K]
        self.active           = material.sig_y is not None


    def thermal_strain(self, T):
        # free thermal expansion from the reference temperature, material.a is the mean expansion coefficient up to T
        return self.material.value('a', T) * (T - self.T_ref)


    def mismatch(self, solver, r_i, r_o, t_i, t_o):
        # Stresses from the different mean temperatures of inner wall, ribs and outer wall. All three share the same axial strain.
        # The ribs carry no hoop load but tie the walls together: both move by the same radial displacement, apart from the thermal
        # expansion of the ribs, which links the hoop strains of inner and outer wall (mean radii r_i and r_o). The walls are in plane
        # stress, axial strain e_x and hoop strain of the inner wall e_h follow from zero net force in axial and hoop direction
        mat   = self.material
        T     = np.array([solver.T_inner, solver.T_outer])
        A     = np.array([solver.A_inner, solver.A_outer])
        t     = np.array([t_i, t_o])
        v     = mat.value('v', T)
        C     = mat.value('E', T) / (1 - v**2)
        e     = self.thermal_strain(T)
        E_rib = mat.value('E', solver.T_rib)
        e_rib = self.thermal_strain(solver.T_rib)

        # hoop strain of each wall = g * e_h + c
        g   = np.array([1, r_i / r_o])
        c   = np.array([0, (r_o - r_i) / r_o * e_rib])

        K   = np.array([[np.sum(A * C) + solver.A_rib * E_rib, np.sum(A * C * v * g)],
                        [np.sum(t * C * v),                    np.sum(t * C * g)]])
        f   = np.array([np.sum(A * C * ((1 + v) * e - v * c)) + solver.A_rib * E_rib * e_rib,
                        np.sum(t * C * ((1 + v) * e - c))])
        e_x, e_h = np.linalg.solve(K, f)

        sig_axial = C * ((e_x - e) + v * (g * e_h + c - e))
        sig_hoop  = C * ((g * e_h + c - e) + v * (e_x - e))

        # stresses in the inner wall
        return sig_axial[0], sig_hoop[0]


    def section(self, idx, solver, p_coolant, p_gas):
        # returns the wall temperatures and stresses of one section as a dictionary
        geom = self.cooling_geometry
        res  = {
            'dT_wall':  solver.T_wall_hot - solver.T_wall_cold,     # temperature difference through the inner wall [K]
            'T_inner':  solver.T_inner,
            'T_rib':    solver.T_rib,
            'T_outer':  solver.T_outer,
        }

        if not self.active:
            return res

        mat = self.material
        r_c = geom.geom[idx, 1]                          # inner chamber radius
        t_i = geom.t_w_i[idx]
        t_o = geom.t_w_o[idx]
        w   = geom.psi_c[idx] * (r_c + t_i)              # width of the cooling channel at the inner wall, perpendicular to the channel

        # primary stresses: the inner wall between two ribs as a beam with fixed ends under the pressure difference of coolant and hot gas
        # (highest at the ribs), and the hoop force of gas and coolant pressure carried by inner and outer wall together
        sig_p_bend     = 0.5 * abs(p_coolant - p_gas) * (w / t_i)**2
        sig_p_membrane = (p_gas * r_c + geom.psi[idx] * geom.h_c[idx] * p_coolant) / (t_i + t_o)
        sig_primary    = sig_p_bend + sig_p_membrane

        # secondary stresses at the hot gas side of the inner wall: mismatch and linear temperature gradient through the wall
        sig_axial, sig_hoop = self.mismatch(solver, r_c + t_i / 2, r_c + t_i + geom.h_c[idx] + t_o / 2, t_i, t_o)
        E        = mat.value('E', solver.T_inner)
        v        = mat.value('v', solver.T_inner)
        sig_grad = E * (self.thermal_strain(solver.T_wall_hot) - self.thermal_strain(solver.T_wall_cold)) / (2 * (1 - v))

        s_x = sig_axial - sig_grad
        s_h = sig_hoop - sig_grad
        sig_secondary = np.sqrt(s_x**2 - s_x * s_h + s_h**2)       # von Mises equivalent stress of the biaxial state

        # yield strength at the highest temperature of the hot gas side wall
        sig_y = float(mat.value('sig_y', solver.inner_wall_temp))
        X     = sig_primary / sig_y
        Y     = sig_secondary / sig_y

        res.update({
            'sig_p_bend':     sig_p_bend,
            'sig_p_membrane': sig_p_membrane,
            'sig_grad':       sig_grad,
            'sig_mis_hoop':   sig_hoop,
            'sig_mis_axial':  sig_axial,
            'sig_secondary':  sig_secondary,
            'sig_y':          sig_y,
            'X':              X,
            'Y':              Y,
            'strain_range':   sig_secondary / E,                    # elastically calculated strain range of one firing
            'regime':         bree_regime(X, Y),
        })

        return res


def x_ranges(x, sections):
    # x coordinates [mm] of the sections as text, neighbouring sections are joined to ranges
    sections = sorted(sections)
    ranges   = []
    start    = sections[0]
    for i, s in enumerate(sections):
        if i + 1 == len(sections) or sections[i + 1] != s + 1:
            ranges.append(str(round(x[start], 1)) if start == s else str(round(x[start], 1)) + ' to ' + str(round(x[s], 1)))
            if i + 1 < len(sections):
                start = sections[i + 1]

    return ', '.join(ranges)


def summary(out, material, T_ref):
    # terminal message with the results of the wall stress analysis
    x = out.geometry[:, 0] * 1e3

    def highest(arr):
        i = int(np.nanargmax(arr))
        return arr[i], '  at x = ' + str(round(x[i], 1)) + ' [mm]'

    print('')
    print('#############################################')
    print('            Wall Stress Analysis             ')
    print('#############################################')
    print('')
    print('Highest temperature difference through the inner wall:  ', round(highest(out.dT_wall)[0], 1), ' [K]', highest(out.dT_wall)[1])
    print('Highest mean temperature of the inner wall:             ', round(highest(out.T_inner)[0], 1), ' [K]', highest(out.T_inner)[1])
    print('Highest difference of inner and outer wall temperature: ', round(highest(out.T_inner - out.T_outer)[0], 1), ' [K]', highest(out.T_inner - out.T_outer)[1])

    if material.sig_y is None:
        print('')
        print('No yield strength specified for ', material.name, ' in MaterialLib.py, wall stresses are not calculated')
        print('')
        return

    primary = out.sig_p_bend + out.sig_p_membrane
    print('')
    print('Elastic stresses for steady state firing, wall free of stress at ', round(T_ref, 1), ' [K]')
    print('Highest primary stress (pressure):                      ', round(highest(primary)[0] / 1e6, 1), ' [MPa]', highest(primary)[1])
    print('Highest secondary stress (temperature):                 ', round(highest(out.sig_secondary)[0] / 1e6, 1), ' [MPa]', highest(out.sig_secondary)[1])
    print('Lowest yield strength at wall temperature:              ', round(np.nanmin(out.sig_y) / 1e6, 1), ' [MPa]', '  at x = ' + str(round(x[int(np.nanargmin(out.sig_y))], 1)) + ' [mm]')
    print('Highest strain range of one firing:                     ', round(highest(out.strain_range)[0] * 100, 3), ' [%]', highest(out.strain_range)[1])

    print('')
    print('Bree diagram, X = primary stress / yield strength, Y = secondary stress / yield strength')
    print('Highest X: ', round(highest(out.X)[0], 3), highest(out.X)[1])
    print('Highest Y: ', round(highest(out.Y)[0], 3), highest(out.Y)[1])
    print('')
    for key, name in REGIMES.items():
        sections = [i for i, regime in enumerate(out.regime) if regime == key]
        if len(sections) > 0:
            print((key + '  ' + name + ':').ljust(22), str(len(sections)).rjust(3), ' of ', len(x), ' sections,  x = ', x_ranges(x, sections), ' [mm]')

    if any(regime in ('R', 'C') for regime in out.regime):
        print('')
        print('WARNING: ratcheting or plastic collapse, the wall deforms further with every firing')
    elif 'P' in out.regime:
        print('')
        print('Plastic cycling: the wall yields in every firing, the life is limited by low cycle fatigue')
    print('')
