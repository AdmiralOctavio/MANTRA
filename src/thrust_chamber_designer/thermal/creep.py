#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Creep rupture screening of the 2D sections                        #
# License:	GNU GENERAL PUBLIC LICENSE V3							#
#####################################################################

import numpy as np


# where the rupture life of a section comes from, in the order used in the summary and the plots
FLAGS = {
    0: 'within the data',
    1: 'below the lowest stress of the data (longer than tested)',
    2: 'above the highest stress of the data (shorter than tested)',
}


class LarsonMiller():
    """[Summary]
    Stress rupture of a material as a Larson-Miller curve: LMP = T * (C + log10(t_r)) with the temperature T [K] and the time to rupture
    t_r [h]. The rupture stress is given at points of the LMP and interpolated linearly in log(stress).
    Outside the data the curve is extended with the slope of its ends. Towards higher stresses (shorter times) it goes no further than
    the short time tensile strength, or, for materials without a tensile strength over temperature, no further than the highest stress
    of the data. factor scales the rupture stress of the data, e.g. for printed parts when the data are of wrought material.
    """
    def __init__(self, C, LMP, sig, factor=1.0, T_range=None, source=''):
        order        = np.argsort(LMP)
        self.C       = C                                            # Larson-Miller constant
        self.LMP     = np.asarray(LMP, dtype=float)[order]          # Larson-Miller parameter of the points [K]
        self.log_sig = np.log10(np.asarray(sig, dtype=float)[order]) # rupture stress of the points [Pa], decreasing with the LMP
        self.factor  = factor                                       # rupture stress of the part / rupture stress of the data
        self.T_range = T_range                                      # lowest and highest test temperature of the data [K]
        self.source  = source                                       # short note on the data for the summary


    def slope(self, end):
        # d log10(stress) / d LMP at the low (0) or high (-1) LMP end of the data
        i = [0, 1] if end == 0 else [-2, -1]
        return (self.log_sig[i[1]] - self.log_sig[i[0]]) / (self.LMP[i[1]] - self.LMP[i[0]])


    def lmp(self, sig):
        # Larson-Miller parameter at which the part ruptures under the stress sig [Pa] and the flag of FLAGS
        s = np.log10(sig / self.factor)
        if s > self.log_sig[0]:
            return self.LMP[0] + (s - self.log_sig[0]) / self.slope(0), 2
        if s < self.log_sig[-1]:
            return self.LMP[-1] + (s - self.log_sig[-1]) / self.slope(-1), 1
        return np.interp(-s, -self.log_sig, self.LMP), 0


    def rupture_time(self, sig, T, sig_u=None):
        # time to rupture [h] under the stress sig [Pa] at the temperature T [K] and the flag of FLAGS. sig_u: short time tensile strength
        # at T [Pa], None if not known
        if sig <= 0:
            return np.inf, 0
        sig_max = sig_u if sig_u is not None else self.factor * 10**self.log_sig[0]
        if sig >= sig_max:
            return 0.0, 2
        P, flag = self.lmp(sig)
        return 10**min(P / T - self.C, 300.0), flag


    def rupture_strength(self, t, T, sig_u=None):
        # stress [Pa] at which the part ruptures after the time t [h] at the temperature T [K]
        P = T * (self.C + np.log10(t))
        if P < self.LMP[0]:
            if sig_u is None:
                return self.factor * 10**self.log_sig[0]
            return min(self.factor * 10**(self.log_sig[0] + (P - self.LMP[0]) * self.slope(0)), sig_u)
        if P > self.LMP[-1]:
            s = self.log_sig[-1] + (P - self.LMP[-1]) * self.slope(-1)
        else:
            s = np.interp(P, self.LMP, self.log_sig)
        sig = self.factor * 10**s
        return min(sig, sig_u) if sig_u is not None else sig


def reference_stress(sig_bend, sig_membrane):
    # Reference stress of the primary stresses for creep rupture (R5 / reference stress method): the yield strength scaled with the load
    # over the limit load. sig_bend is the elastic bending stress of the inner wall between two ribs (beam with fixed ends), which
    # collapses with hinges at both ends and in the middle at twice the load of its first yield, sig_membrane the hoop membrane stress. With the
    # interaction M / M_p + (N / N_p)^2 = 1 of a rectangular section the limit load gives
    # sig_ref = sig_bend / 4 + sqrt(sig_bend^2 / 16 + sig_membrane^2): half the elastic bending stress for bending alone, the membrane
    # stress for a membrane alone. Creep redistributes the peak of the elastic bending stress, the reference stress governs the rupture
    return sig_bend / 4 + np.sqrt(sig_bend**2 / 16 + sig_membrane**2)


def summary(out, material, firing_time, firings):
    # terminal message with the results of the creep rupture screening
    from .stress import x_ranges
    x = out.geometry[:, 0] * 1e3
    creep = getattr(material, 'creep', None)
    t_total = firing_time * firings

    print('')
    print('#############################################')
    print('          Creep Rupture Screening            ')
    print('#############################################')
    print('')

    if creep is None:
        print('No creep rupture data for ', material.name, ' in materials.py, creep is not screened')
        print('')
        return

    print('Firings: ', firings, ' x ', round(firing_time, 2), ' [s] = ', round(t_total, 1), ' [s] at steady state wall temperature')
    print('Data: ', creep.source)
    if creep.factor != 1:
        print('Rupture stress of the data scaled by ', creep.factor, ' for the printed material')

    i = int(np.nanargmax(out.sig_ref))
    print('')
    print('Highest reference stress (pressure):                    ', round(out.sig_ref[i] / 1e6, 1), ' [MPa]  at x = ', round(x[i], 1), ' [mm]')
    i = int(np.nanargmin(out.t_rupture))
    print('Shortest time to creep rupture:                         ', '%.3g' % out.t_rupture[i], ' [h]  at x = ', round(x[i], 1), ' [mm]')
    i = int(np.nanargmax(out.creep_damage))
    print('Highest life fraction (firing time / rupture time):    ', '%.3g' % out.creep_damage[i], '  at x = ', round(x[i], 1), ' [mm]')
    if creep.T_range is not None:
        print('Test temperatures of the data: ', round(creep.T_range[0]), ' to ', round(creep.T_range[1]), ' [K], hot gas side wall: ',
              round(np.nanmin(out.T_wall_i)), ' to ', round(np.nanmax(out.T_wall_i)), ' [K]')

    print('')
    for flag, text in FLAGS.items():
        sections = [j for j in range(len(x)) if out.creep_flag[j] == flag]
        if len(sections) > 0:
            print(('Rupture life ' + text + ':').ljust(78), str(len(sections)).rjust(3), ' of ', len(x), ' sections,  x = ', x_ranges(x, sections), ' [mm]')

    failed = [j for j in range(len(x)) if out.creep_damage[j] >= 1]
    if len(failed) > 0:
        print('')
        print('WARNING: creep rupture within the firing time in ', len(failed), ' sections,  x = ', x_ranges(x, failed), ' [mm]')
    elif np.nanmax(out.creep_damage) > 0.1:
        print('')
        print('The life fraction is above 0.1: with the scatter of creep data (a factor of 10 in life is common) creep may limit the life')
    print('Thermal stresses relax by creep and cycle the wall plastically: see the thermal ratcheting and cyclic life below')
    print('')
