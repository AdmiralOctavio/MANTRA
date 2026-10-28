import numpy as np
from scipy.optimize import fsolve

from . import isentropic as IT
from .moc import solve


def size_nozzle(chem, operating, chamber, nozzle, mach_guess=2.23):
    """Mass flow and design exit Mach number for the target thrust and perfect expansion to the ambient pressure, and the nozzle
    for them (moc.NozzleSolution). The mass flow is everything that goes through the throat, film coolant included, sized with the
    c* of the core combustion.

    chem: combustion properties (core.chemistry.CEA after solve_nozzle), operating, chamber, nozzle: parts of core.design.Design
    """
    def engine_residuals(variables):
        mdot_guess, mach_guess = variables

        # Ensure we use floats to prevent indexing errors
        mdot_val = float(mdot_guess)
        mach_val = float(mach_guess)

        A_t = (mdot_val * chem.cstar_eq * operating.eta_c_star) / operating.chamber_pressure
        r_t = np.sqrt(A_t / np.pi) * 1000

        result = solve(mdot_val, r_t, mach_val, chem, operating, chamber, nozzle)

        thrust_error = result.thrust - operating.thrust
        pressure_error = result.P_exit - operating.ambient_pressure # Perfectly expanded target

        return [thrust_error, pressure_error]

    # Preliminary estimate for initial mdot guess
    CF_in = IT.estimate_CF(chem.gamma_throat, 5.5, operating.chamber_pressure)
    mdot_initial = (operating.chamber_pressure * (operating.thrust / (CF_in * operating.chamber_pressure))) / chem.cstar_eq

    initial_guess = [mdot_initial, mach_guess]

    # Solve for perfect expansion and target thrust
    solution, info, ier, message = fsolve(engine_residuals, x0=initial_guess, full_output=True)
    mdot_final, mach_final = solution

    A_t_final = (mdot_final * chem.cstar_eq * operating.eta_c_star) / operating.chamber_pressure
    radius_throat_final = np.sqrt(A_t_final / np.pi) * 1000

    result = solve(mdot_final, radius_throat_final, mach_final, chem, operating, chamber, nozzle)
    result.converged = ier == 1
    result.message = message
    return result
