import numpy as np
from scipy.optimize import brentq

from .chamber import check_convergent, convergent_drop
from .moc import solve


def size_nozzle(chem, operating, chamber, nozzle, mach_guess=2.23):
    """Mass flow and design exit Mach number for the target thrust and perfect expansion to the ambient pressure, and the nozzle
    for them (moc.NozzleSolution). The mass flow is everything that goes through the throat, film coolant included, sized with the
    c* of the core combustion.

    The two unknowns are found one after the other. The throat is sized for the chamber pressure at the mass flow, so the exit
    pressure depends on the design Mach number alone: it is the root of the exit pressure minus the ambient pressure, bracketed by
    stepping up from mach_guess. The thrust is then proportional to the mass flow (the contour scales with the throat), which is
    scaled to the target thrust. A Newton solve of both together (fsolve) took its derivatives from steps too small for the net of
    characteristics and jumped to negative mass flows and Mach numbers for large pressure ratios, e.g. 150 bar to 0.1 bar.

    chem: combustion properties (core.chemistry.CEA after solve_nozzle), operating, chamber, nozzle: parts of core.design.Design
    """
    throat = lambda mdot: np.sqrt(mdot * chem.cstar_eq * operating.eta_c_star / operating.chamber_pressure / np.pi) * 1000   # [mm]

    def run(mdot, mach):
        return solve(mdot, throat(mdot), mach, chem, operating, chamber, nozzle)

    # the mass flow for the target thrust with an ideal vacuum C_F of 1.8, only to have a throat of about the right size. Large enough
    # for the convergent section to fit in front of the throat, which the exit pressure (from the narrowest point of the wall) needs
    mdot = operating.thrust / (1.8 * chem.cstar_eq)
    rt_min = convergent_drop(chamber.R1, chamber.R2, chamber) / (np.sqrt(chamber.contraction_ratio) - 1)
    mdot = max(mdot, 1.1 * mdot * (rt_min / throat(mdot))**2)

    def over(mach):
        # exit pressure above the ambient pressure. NaN beyond the area ratios the exit Mach number can be found for, far below it
        p = run(mdot, mach).P_exit
        return np.nan if not np.isfinite(p) else p - operating.ambient_pressure

    # bracket: the exit pressure falls with the design Mach number
    lo, hi = 1.0 + 1e-3, max(float(mach_guess), 1.01)
    while True:
        g = over(hi)
        if not np.isfinite(g) or g < 0:
            break
        lo, hi = hi, hi * 1.25
        if hi > 50:
            raise ValueError('No nozzle expands to the ambient pressure of %.0f Pa' % operating.ambient_pressure)
    if over(lo) < 0:
        raise ValueError('The ambient pressure of %.0f Pa is too high for a supersonic nozzle at a chamber pressure of %.0f Pa'
                         % (operating.ambient_pressure, operating.chamber_pressure))
    while not np.isfinite(over(hi)):
        # too far out for the exit Mach number: halve the interval towards the last Mach number with an exit pressure
        mid = 0.5 * (lo + hi)
        g = over(mid)
        if np.isfinite(g) and g >= 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            raise ValueError('The exit Mach number can not be found for the expansion to %.0f Pa' % operating.ambient_pressure)
    mach = brentq(over, lo, hi, xtol=1e-14, rtol=1e-15)

    # thrust proportional to the mass flow, a few times for the rounding of the net
    for _ in range(4):
        mdot *= operating.thrust / run(mdot, mach).thrust
        check_convergent(chamber.R1, chamber.R2, throat(mdot), chamber)

    result = run(mdot, mach)
    error = max(abs(result.thrust / operating.thrust - 1), abs(result.P_exit / operating.ambient_pressure - 1))
    result.converged = error < 1e-6
    result.message = 'thrust and exit pressure within %.1e of the targets' % error
    return result
