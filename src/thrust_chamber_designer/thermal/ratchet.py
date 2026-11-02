#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Thermal ratcheting and cyclic life of the 2D sections             #
# License:	GNU GENERAL PUBLIC LICENSE V3							#
#####################################################################

import numpy as np

PSI = 6894.757          # [Pa]

# failure mode of the Porowski ligament life, in the order used in the summary and the plots
MODES = {
    0: 'tensile instability of the thinned ligament',
    1: 'low cycle fatigue',
    2: 'creep rupture',
    3: 'no damage within 1e7 firings',
}

# where the cyclic results come from, in the order used in the summary and the plots
FLAGS = {
    0: 'within the data',
    1: 'creep law or fatigue curve extrapolated',
    2: 'plastic ratcheting (core stress above yield)',
}

# F(r) of the deflection of a clamped beam in Norton creep, table I of NASA CR-168261 (r = 1 is the elastic beam)
F_TABLE = (np.arange(1, 11), np.array([0.250, 0.206, 0.170, 0.148, 0.133, 0.122, 0.114, 0.105, 0.100, 0.093]))


class NortonCreep():
    """[Summary]
    Minimum (steady state) creep rate as a power law of the stress at each test temperature, rate = A_i * sig^n_i, fitted to points of the
    data. Within the stresses of the data log10(rate) is interpolated linearly in 1 / T (Arrhenius) between the test temperatures and
    extrapolated beyond them with the slope of the two nearest, never falling with temperature. Outside the stresses of the data the rate is
    extended with one exponent for all temperatures, the lowest of the data below and the highest above (the higher rate in both cases),
    since power laws of different exponents cross far from the data. Extrapolated results are flagged. Primary creep is not included, which
    underestimates the creep strain of short firings.
    """
    def __init__(self, data, source=''):
        # data: {T [K]: (stresses [Pa], minimum creep rates [1/s])}, at least two temperatures
        self.T      = np.array(sorted(data), dtype=float)
        fits        = [np.polyfit(np.log10(np.asarray(data[T][0], dtype=float)), np.log10(np.asarray(data[T][1], dtype=float)), 1) for T in sorted(data)]
        self.n      = np.array([f[0] for f in fits])         # stress exponent at each temperature
        self.log_A  = np.array([f[1] for f in fits])         # log10(rate [1/s]) at 1 Pa
        sig         = np.concatenate([np.asarray(data[T][0], dtype=float) for T in data])
        self.sig_range = (sig.min(), sig.max())              # lowest and highest stress of the data [Pa]
        self.source = source                                 # short note on the data for the summary


    def _in_T(self, values, T):
        # values at the test temperatures interpolated linearly in 1 / T, extrapolated with the slope of the two nearest temperatures
        x, xs = -1 / float(T), -1 / self.T
        i = int(np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2))
        slope = (values[i + 1] - values[i]) / (xs[i + 1] - xs[i])
        if x < xs[0] or x > xs[-1]:
            slope = np.maximum(slope, 0)
        return values[i] + (x - xs[i]) * slope


    def rate(self, sig, T):
        # minimum creep rate [1/s] under the stress sig [Pa] at the temperature T [K]
        s    = np.log10(np.maximum(np.asarray(sig, dtype=float), 1e-30))
        lo, hi = np.log10(self.sig_range)
        sc   = np.clip(s, lo, hi)
        logs = np.array([la + n * sc for la, n in zip(self.log_A, self.n)])
        ext  = np.where(s < lo, self.n.min() * (s - lo), np.where(s > hi, self.n.max() * (s - hi), 0.0))
        return 10**np.minimum(self._in_T(logs, T) + ext, 10.0)


    def exponent(self, T):
        # stress exponent at the temperature T [K], held at the end values outside the test temperatures
        return float(np.interp(-1 / T, -1 / self.T, self.n))


    def extrapolated(self, sig, T):
        # True where the stress or the temperature is outside the data
        return bool(T < self.T[0] - 1 or T > self.T[-1] + 1 or np.any(np.asarray(sig) < self.sig_range[0]) or np.any(np.asarray(sig) > self.sig_range[1]))


class FatigueCurve():
    """[Summary]
    Total strain range of fully reversed, strain controlled fatigue tests against the cycles to failure. curves gives the strain range as a
    function of the cycles at each test temperature; the cycles to failure at a strain range are interpolated in log10(cycles) between the
    temperatures and held at the nearest curve outside. Outside the tested lives and temperatures the life is extrapolated and flagged.
    """
    def __init__(self, curves, N_range, T_range=None, source=''):
        # curves: {T [K]: function of the cycles to failure giving the total strain range [-]}, N_range: shortest and longest life tested
        self.T       = np.array(sorted(curves), dtype=float)
        self.log_N   = np.linspace(0, 10, 501)
        self.log_eps = [np.log10(curves[T](10**self.log_N)) for T in sorted(curves)]
        self.N_range = N_range
        self.T_range = T_range if T_range is not None else (self.T[0], self.T[-1])
        self.source  = source


    def cycles(self, eps, T):
        # cycles to failure at the total strain range eps [-] and the temperature T [K]
        x = -np.log10(np.maximum(np.asarray(eps, dtype=float), 1e-12))
        log_N = np.array([np.interp(x, -le, self.log_N) for le in self.log_eps])
        if len(self.T) == 1:
            return 10**log_N[0]
        i = np.clip(np.searchsorted(self.T, T) - 1, 0, len(self.T) - 2)
        f = np.clip((T - self.T[i]) / (self.T[i + 1] - self.T[i]), 0, 1)
        return 10**(log_N[i] + f * (log_N[i + 1] - log_N[i]))


    def extrapolated(self, N, T):
        # True where the life or the temperature is outside the tests
        return bool(T < self.T_range[0] - 1 or T > self.T_range[1] + 1 or np.any(np.asarray(N) < self.N_range[0]) or np.any(np.asarray(N) > self.N_range[1]))


def core_stress(X, Y):
    # Elastic core stress / yield strength of O'Donnell and Porowski for a sustained primary stress X and a cyclic secondary stress range Y,
    # both normalised by the yield strength (Bree model): Z of the effective creep stress diagram of ASME III Div. 5, HBB-T-1332 (test B-1).
    # Regime E (X + Y <= 1): X. Regime S1 ((1 - X) Y <= 1): 1 + Y - 2 sqrt((1 - X) Y). Regimes S2 and P: X Y. Z >= 1 is plastic ratcheting
    # (Porowski and O'Donnell, Creep ratcheting bounds from extended elastic core concept, ORNL / OSTI 6027412, eqs. 6 and 7)
    if X >= 1 or X + Y <= 1:
        return X
    if (1 - X) * Y <= 1:
        return 1 + Y - 2 * np.sqrt((1 - X) * Y)
    return X * Y


def core_ratchet(material, X, Y, sig_y_cold, T, firing_time, firings):
    # creep ratchet strain of the elastic core over all firings at 1.25 times the core stress (test B-1), with the minimum creep rate at the
    # highest wall temperature T [K]; firings until the strain limit of 1 % of the base metal, 0 in the plastic ratcheting regime
    Z     = core_stress(X, Y)
    sig_c = Z * sig_y_cold
    rate  = float(material.norton.rate(1.25 * sig_c, T))
    eps   = rate * firing_time
    flag  = 1 if material.norton.extrapolated(1.25 * sig_c, T) else 0
    if Z >= 1 or sig_c > material.value('sig_y', T):
        flag = 2
    return {
        'Z':            Z,
        'sig_core':     sig_c,
        'eps_ratchet':  eps * firings,                                   # creep ratchet strain of all firings [-]
        'N_ratchet':    0.0 if Z >= 1 else (0.01 / eps if eps > 0 else np.inf),
        'ratchet_flag': flag,
    }


def ligament_life(material, eps_mis, eps_grad, dp, t_w, w_ch, w_rib, T_lig, T_hot, T_ref, firing_time):
    """[Summary]
    Cycles to failure of the inner wall between two ribs (the ligament) after Porowski et al. (NASA CR-165585, 1981, plastic) and Badlani et
    al. (NASA CR-168261, 1983, with creep), J. Spacecraft and Rockets 22 (1985): the ligament yields in compression when firing, its stress
    relaxes by creep, and it yields in tension at shut down. The hoop plastic strains of both halves of the cycle bend the ligament the same
    way under the pressure, so it bulges into the chamber and thins at the middle of the channel every firing ("doghouse" failure). Life is
    the first of tensile instability of the thinned ligament and fatigue plus creep rupture damage (linear sum).
    eps_mis: thermal strain of the ligament minus that of the closeout, eps_grad: thermal strain difference through the ligament, dp: coolant
    minus gas pressure [Pa], t_w: ligament thickness, w_ch: channel width, w_rib: rib width [m], T_lig: mean ligament temperature, T_hot:
    highest hot gas side temperature, T_ref: temperature at shut down [K], firing_time [s]
    """
    mat    = material
    E, v   = float(mat.value('E', T_lig)), float(mat.value('v', T_lig))
    Sy_h   = float(mat.value('sig_y', T_lig))
    Sy_c   = float(mat.value('sig_y', T_ref))
    Su_c   = float(mat.value('sig_u', T_ref))
    Sy     = (Sy_h + Sy_c) / 2
    dp     = abs(dp)
    H      = t_w / 2
    l, w   = w_ch, w_rib
    r      = mat.norton.exponent(T_lig)
    q      = 0.2 * max(Su_c / Sy_c - 1, 0.0)**0.6                    # strain hardening exponent estimated from Su / Sy (NASA LeRC)

    # relaxation of the compressive stress during the firing: to about zero above 1000 psi, else uniaxial relaxation in Norton creep (eq. 6)
    if dp >= 1000 * PSI:
        dsig_c = Sy_h
    else:
        rate   = float(mat.norton.rate(Sy_h, T_lig))
        dsig_c = Sy_h - Sy_h * (1 + (r - 1) * E * rate * firing_time / Sy_h)**(1 / (1 - r))

    # hoop plastic strain range of the ligament held by the closeout (eq. 1) and the correction for the bending of the gradient (eq. 2),
    # nothing ratchets if the ligament does not yield
    de_mis  = abs(eps_mis) - (Sy_h + Sy_c) / E + dsig_c / E
    de_grad = E * eps_grad**2 / (12 * (1 - v)**2 * Sy)
    eps_pl  = 2 * (de_mis + de_grad) if de_mis > 0 else 0.0

    # deflection of the middle of the ligament per firing: plastic bending from the hoop strain with curvature eps_pl / H (eq. 16), shear,
    # and creep of the clamped beam under the pressure (eq. 24)
    if eps_pl > 0:
        R  = H / eps_pl
        d1 = 2 * R * (1 - np.sqrt(1 - min(l / 4 / R, 1.0)**2))
    else:
        d1 = 0.0
    d2    = eps_pl * dp * l**2 / (4 * H * Sy)
    F     = np.interp(r, *F_TABLE)
    d3    = firing_time * l**2 / (4 * H) * float(mat.norton.rate(dp * l**2 / (16 * H**2), T_lig)) * F
    delta = d1 + d2 + d3
    thin  = delta * w / (l + w)                                      # thinning of the middle of the ligament per firing [m], linear model

    t_cr   = 2 * H * np.exp(-q)                                      # thickness at tensile instability (eq. 46)
    N_inst = (2 * H - t_cr) / thin if thin > 0 else np.inf

    # damage per firing over the firings while the ligament thins: fatigue with the local strain range at the thinnest section (eqs. 27-31),
    # creep rupture under the redistributed bending stress at the middle of the channel when it redistributes within the firing (eqs. 32, 33).
    # Beyond the instability the thickness is held at the critical one, so that both lives can be compared
    N      = np.logspace(0, 7, 400)
    N_th   = np.minimum(N, N_inst)
    t_min  = 2 * H - N_th * thin
    t_max  = 2 * H + N_th * delta * w * l / (l + w)**2
    tau    = t_max / t_min
    k      = (q - 1) / q
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.where(tau > 1 + 1e-9, k * (tau - 1) / (tau**k - 1), 1.0)
    e1     = abs(eps_mis) * ratio
    e2     = abs(eps_mis)
    de_eq  = 2 / np.sqrt(3) * np.sqrt(e1**2 + e1 * e2 + e2**2)
    N_f    = mat.fatigue.cycles(de_eq, T_lig)
    d_fat  = 1 / N_f

    sig_in = dp * (l + w / 2)**2 / (4 * t_min**2)                    # elastic bending stress at the middle of the channel
    sig_ss = (1 - 0.2354 * (1 - 1 / r)) * sig_in                      # redistributed (steady creep) stress, F of figure 10
    with np.errstate(divide='ignore'):
        t_ss = 2.3 * (sig_in / E) / (r * mat.norton.rate(sig_ss, T_lig))
    t_r    = np.array([mat.creep.rupture_time(s, T_hot)[0] for s in sig_ss]) * 3600
    with np.errstate(divide='ignore'):
        d_cr = np.where((0.1 * t_ss < firing_time) & (sig_ss > 0), firing_time / t_r, 0.0)

    d      = d_fat + d_cr
    D      = d[0] + np.concatenate([[0], np.cumsum(0.5 * (d[1:] + d[:-1]) * np.diff(N))])
    N_dam  = float(np.interp(1, D, N)) if D[-1] >= 1 else np.inf
    N_life = min(N_inst, N_dam)

    j = min(np.searchsorted(N, min(N_life, N[-1])), len(N) - 1)
    if not np.isfinite(N_life):
        mode = 3
    elif N_inst <= N_dam:
        mode = 0
    else:
        mode = 2 if d_cr[j] > d_fat[j] else 1

    flag = 1 if mat.fatigue.extrapolated(N_f[j], T_lig) or mat.norton.extrapolated(Sy_h, T_lig) else 0
    return {
        'eps_pl_cycle':     eps_pl,
        'thinning':         thin,
        'N_instability':    N_inst,
        'N_fatigue_creep':  N_dam,
        'N_life':           N_life,
        'life_mode':        mode,
        'life_flag':        flag,
    }


def summary(out, material, firing_time, firings):
    # terminal message with the results of the ratcheting and cyclic life checks
    from .stress import x_ranges
    x = out.geometry[:, 0] * 1e3

    print('')
    print('#############################################')
    print('     Thermal Ratcheting and Cyclic Life      ')
    print('#############################################')
    print('')

    if getattr(material, 'norton', None) is None or getattr(material, 'fatigue', None) is None or material.sig_y is None:
        print('No creep rate or fatigue data for ', material.name, ' in materials.py, ratcheting and cyclic life are not evaluated')
        print('')
        return

    print('Firings: ', firings, ' x ', round(firing_time, 2), ' [s]')
    print('Creep rates: ', material.norton.source)
    print('Fatigue: ', material.fatigue.source)

    def lowest(arr):
        if np.all(np.isnan(arr)):
            return None
        i = int(np.nanargmin(arr))
        return arr[i], i

    print('')
    print('1) Elastic core stress (O\'Donnell-Porowski, ASME III Div. 5 test B-1), creep ratchet strain of the core, limit 1 %')
    i = int(np.nanargmax(out.Z))
    print('Highest core stress parameter Z:                        ', round(out.Z[i], 3), '  (', round(out.sig_core[i] / 1e6, 1), ' [MPa])  at x = ', round(x[i], 1), ' [mm]')
    i = int(np.nanargmax(out.eps_ratchet))
    print('Highest creep ratchet strain of all firings:            ', '%.3g' % (out.eps_ratchet[i] * 100), ' [%]  at x = ', round(x[i], 1), ' [mm]')
    N_op = lowest(out.N_ratchet)
    print('Fewest firings to 1 % ratchet strain:                   ', '%.3g' % N_op[0], '  at x = ', round(x[N_op[1]], 1), ' [mm]')

    print('')
    print('2) Ligament life (Porowski et al., NASA CR-165585 / CR-168261): bulging and thinning of the inner wall between the ribs')
    i = int(np.nanargmax(out.eps_pl_cycle))
    print('Highest hoop plastic strain per firing:                 ', '%.3g' % (out.eps_pl_cycle[i] * 100), ' [%]  at x = ', round(x[i], 1), ' [mm]')
    i = int(np.nanargmax(out.thinning))
    print('Highest thinning per firing:                            ', '%.3g' % (out.thinning[i] * 1e6), ' [um]  at x = ', round(x[i], 1), ' [mm]')
    N_pw = lowest(out.N_life)
    print('Fewest firings to failure:                              ', '%.3g' % N_pw[0], '  at x = ', round(x[N_pw[1]], 1), ' [mm],  ', MODES[int(out.life_mode[N_pw[1]])])
    N_su = lowest(out.N_life_startup)
    i = int(np.nanargmax(out.eps_pl_startup))
    print('Start-up bound, closeout still at the shut down temperature while the inner wall is at its steady temperature:')
    print('  highest hoop plastic strain per firing:               ', '%.3g' % (out.eps_pl_startup[i] * 100), ' [%]  at x = ', round(x[i], 1), ' [mm]')
    print('  fewest firings to failure:                            ', '%.3g' % N_su[0], '  at x = ', round(x[N_su[1]], 1), ' [mm],  ', MODES[int(out.startup_mode[N_su[1]])])
    print('  The real start up lies between the steady state and this bound, depending on how far the closeout lags the inner wall')

    print('')
    for flag, text in FLAGS.items():
        for name, flags in (('Core stress', out.ratchet_flag), ('Ligament life', out.life_flag)):
            sections = [j for j in range(len(x)) if flags[j] == flag]
            if len(sections) > 0 and flag > 0:
                print((name + ', ' + text + ':').ljust(78), str(len(sections)).rjust(3), ' of ', len(x), ' sections,  x = ', x_ranges(x, sections), ' [mm]')

    if N_pw[0] < firings:
        print('')
        print('WARNING: the ligament fails within the ', firings, ' firings at ', len([j for j in range(len(x)) if out.N_life[j] < firings]), ' sections')
    elif N_su[0] < firings:
        print('')
        print('WARNING: the ligament may fail within the ', firings, ' firings if the closeout lags the inner wall at start up, at ',
              len([j for j in range(len(x)) if out.N_life_startup[j] < firings]), ' sections')
    if N_op[0] < firings:
        print('')
        print('WARNING: the core creeps by more than 1 % within the ', firings, ' firings')
    if N_su[0] < 10 * firings or N_op[0] < 10 * firings:
        print('Fatigue lives scatter by a factor of 2 to 3 and creep rates by a factor of 10: design for at least 4 to 10 times the firings')
    print('Both checks are simplified bounds for screening, not a life prediction. Hardening that slows the thinning is not credited')
    print('')
