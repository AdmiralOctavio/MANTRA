##################################################################################
#                                                                                #
# Numerical Solver for Rocket Nozzles based off of the Method of Characteristics #
#                                                                                #
# Creator:  Flavio Cicero                                                        #
# Date:     28/02/2026                                                           #
# Version:  1.2                                                                  #
#                                                                                #
##################################################################################

# Imports

from dataclasses import dataclass

import numpy as np

from . import isentropic as IT
from .chamber import CombustionChamber

# Iterative solver file for the script. Nothing in here needs to be modified by the user
# This script contains all the sub-function definitions (such as local slopes)
# And the iterative solver algorithm.
#
# The four copies of the solver in the nozzle solver repository (solver_iteration, solver_standard, solver_crt and solver_lcars) had
# the same algorithm and differed in their plots. This is the one copy: characteristic_net() is the net of characteristics,
# wall_contour() the wall and the characteristic lines for the plots, solve() adds the chamber and the exit conditions. The plots are
# in nozzle/plots.py.


class GridField:
    def __init__(self, k_max, n_max):
        self.k_max = int(k_max)
        self.n_max = int(n_max)
        self.M = np.ones((self.k_max, self.n_max))
        self.x = np.zeros((self.k_max, self.n_max))
        self.y = np.zeros((self.k_max, self.n_max))

    def set_xy(self, k, n, x_val, y_val):
        self.x[int(k) - 1, int(n) - 1] = x_val
        self.y[int(k) - 1, int(n) - 1] = y_val

    def set_M(self, k, n, M_val):
        self.M[int(k) - 1, int(n) - 1] = M_val

    def get_M(self, k, n):
        return self.M[int(k) - 1, int(n) - 1]

    def get_xy(self, k, n):
        return self.x[int(k) - 1, int(n) - 1], self.y[int(k) - 1, int(n) - 1]

    def get_x(self, k, n):
        return self.x[int(k) - 1, int(n) - 1]

    def as_arrays(self):
        return self.x, self.y


def characteristic_net(L, mach, g, Refinement):
    """Net of characteristics of a 2D nozzle with a sharp-edged throat of half height L [mm], for the design exit Mach number mach
    and the ratio of specific heats g. Returns the grid and its size k_max, n_max."""
    # ── Parameter Definition ──────────────────────────────────────────────────
    # Parameter Definition (Do not touch)
    M_exit = mach
    v_e = IT.PM(M_exit, g)
    dv = (v_e - IT.PM(1.0, g)) / Refinement
    k_max = int(1 / 2 * v_e / dv + 1)
    n_max = int(1 / 2 * v_e / dv + 1)

    grid = GridField(k_max, n_max)

    def phi_k(k, dv):
        return (k - 1) * dv

    def v_region(k, n, dv):
        return 2 * dv * (n - 1) + (k - 1) * dv

    def slopes(k, n, dv, g):
        v_kn = v_region(k, n, dv)
        v_km1np1 = v_region(k - 1, n + 1, dv)

        M_kn = IT.PMinv(v_kn, g)
        M_km1np1 = IT.PMinv(v_km1np1, g)

        mu_kn = IT.mu(M_kn)
        mu_km1np1 = IT.mu(M_km1np1)

        Phi_k = phi_k(k, dv)
        Phi_km1 = phi_k(k - 1, dv)

        m1 = np.tan((mu_kn + mu_km1np1) / 2 + (Phi_k + Phi_km1) / 2)
        m2 = -np.tan((mu_kn + mu_km1np1) / 2 - (Phi_k + Phi_km1) / 2)
        # print(f"\n Wall k: {k_max - n + 1}")
        if k == int(k_max - n):
            return m1, np.tan(Phi_k)
        else:
            return m1, m2

    # I think this is actually the initial kernel lowk
    def coords_n1(k, dv, g, grid, L):
        n = 1
        x_km1, y_km1 = grid.get_xy(k - 1, n)
        m1, m2 = slopes(k, 1, dv, g)
        x_k1 = (L - (y_km1 - m1 * x_km1)) / (m1 - m2)
        y_k1 = y_km1 + m1 * (x_k1 - x_km1)
        # print(f"x_{k-1} = {x_km1}, y_{k-1} = {y_km1}, m1 = {m1}, m2 = {m2}")
        return x_k1, y_k1

    def coords_k1(n, dv, g, grid):
        k = 1
        x_kp1nm1, y_kp1nm1 = grid.get_xy(k + 1, n - 1)
        m1, m2 = slopes(1, n, dv, g)
        x_kn = -(y_kp1nm1 - m2 * x_kp1nm1) / m2
        y_kn = 0
        # print(f"x_{k+1},{n-1}: {x_kp1nm1}, y_{k+1},{n-1}: {y_kp1nm1}, m2: {m2}, x_{k},{n}: {x_kn}, y_{k},{n}: {y_kn}")

        return x_kn, y_kn

    def coords(k, n, dv, g, grid):
        x_kp1nm1, y_kp1nm1 = grid.get_xy(k + 1, n - 1)
        x_km1n, y_km1n = grid.get_xy(k - 1, n)

        m1, m2 = slopes(k, n, dv, g)

        x_kn = ((y_kp1nm1 - m2 * x_kp1nm1) - (y_km1n - m1 * x_km1n)) / (m1 - m2)
        y_kn = y_km1n + m1 * (x_kn - x_km1n)
        return x_kn, y_kn

    # ── Solver loop ───────────────────────────────────────────────────────
    # basically the wall points are defined as kmax, 1 -> kmax - 1, 2, ... 2, nmax - 1.
    grid.set_xy(1, 1, -L / (slopes(1, 1, dv, g)[1]), 0.0)
    for k1 in range(2, int(k_max)):
        x_k1, y_k1 = coords_n1(k1, dv, g, grid, L)
        grid.set_xy(k1, 1, x_k1, y_k1)
        # print(f"K: {k1}, N = 1, x: {x_k1}, y: {y_k1}")
    for N in range(2, n_max):
        x_k1nN, y_k1nN = coords_k1(N, dv, g, grid)
        grid.set_xy(1, N, x_k1nN, y_k1nN)
        # print(f"K: 1, N = {N}, x: {x_k1nN}, y: {y_k1nN}")

        for kN in range(2, k_max - N + 2):
            x_kN, y_kN = coords(kN, N, dv, g, grid)
            grid.set_xy(kN, N, x_kN, y_kN)
            # print(f"K: {kN}, N = {N}, x: {x_kN}, y: {y_kN}")

    return grid, k_max, n_max


def wall_contour(grid, k_max, n_max, L, SP):
    """Wall of the nozzle from the throat to the exit, truncated to the fraction SP of its full length, and the characteristic lines
    for the plots: family II, family I inside the nozzle and family I which leave through the exit."""
    wall_x = []
    wall_y = []
    family_2, family_1_internal, family_1_exit = [], [], []

    # Prints the characteristics of Family II
    for NII in range(1, int(n_max)):
        x_line = []
        y_line = []

        x_line.append(0)
        y_line.append(L)

        for NII_2 in range(1, NII + 1):
            x_NN, y_NN = grid.get_xy(NII - NII_2 + 1, NII_2)
            x_line.append(x_NN)
            y_line.append(y_NN)

            if NII == n_max - 1 and NII_2 != n_max - 1:
                wall_x.append(x_NN)
                wall_y.append(y_NN)
        family_2.append((x_line, y_line))

    split_index = int(len(wall_x) * SP)
    wall_x = wall_x[:split_index]
    wall_y = wall_y[:split_index]

    # Prints the characteristics of Family I
    for NI in range(1, n_max - 1):
        x_line = []
        y_line = []
        for KI in range(1, int(k_max) - NI + 1):
            x_kn, y_kn = grid.get_xy(KI, NI)
            x_line.append(x_kn)
            y_line.append(y_kn)
        if 0 < GridField.get_x(grid, int(k_max) - NI, NI) < wall_x[-1]:
            family_1_internal.append((x_line, y_line))
        elif GridField.get_x(grid, int(k_max) - NI, NI) >= wall_x[-1]:
            family_1_exit.append((x_line, y_line))

    return wall_x, wall_y, (family_2, family_1_internal, family_1_exit)


@dataclass
class NozzleSolution:
    wall_x: np.ndarray            # wall of the whole thrust chamber, injector to exit [mm], throat at x = 0
    wall_y: np.ndarray            # radius of the wall [mm]
    chamber_length: float         # injector to throat [mm]
    throat_radius: float          # y_min [mm]
    exit_radius: float            # y_calc, end of the truncated contour [mm]
    expansion_ratio: float        # true expansion ratio of the truncated contour
    exit_angle: float             # wall angle at the exit [deg]
    M_exit_design: float          # design exit Mach number of the net of characteristics
    M_exit: float                 # exit Mach number from the area ratio of the truncated contour, with the exit gamma
    P_c_actual: float             # chamber pressure for the mass flow and the throat [Pa]
    P_exit: float                 # [Pa]
    T_exit: float                 # [K]
    Ve: float                     # exit velocity with the nozzle efficiency [m/s]
    thrust: float                 # [N]
    thrust_momentum: float        # [N]
    thrust_pressure: float        # [N]
    C_F: float
    mdot: float                   # mass flow through the throat [kg/s]
    characteristics: tuple        # lines of the net for the plots, see wall_contour()


def solve(mdot, L, mach, chem, operating, chamber, nozzle):
    """Nozzle of throat radius L [mm] and design exit Mach number mach with the chamber in front of it, and its performance at the
    mass flow mdot [kg/s].

    chem: combustion properties with Tc, cstar_eq, gamma_throat, MW_throat and gamma_exit (core.chemistry.CEA after solve_nozzle)
    operating, chamber, nozzle: OperatingPoint, ChamberShape and NozzleSettings of core.design
    """
    g = chem.gamma_throat
    g_exit = chem.gamma_exit
    Rs = 8.314 / (chem.MW_throat / 1000)
    T_combustion = chem.Tc
    Cstr = chem.cstar_eq
    P_amb = operating.ambient_pressure

    grid, k_max, n_max = characteristic_net(L, mach, g, nozzle.refinement)
    wall_x, wall_y, characteristics = wall_contour(grid, k_max, n_max, L, nozzle.shorten)

    y_calc = wall_y[-1]

    wall_x, wall_y, Length = CombustionChamber(wall_x, wall_y, chamber.R1, chamber.R2, L, chamber)

    y_min = np.min(wall_y)

    # Exit plane = the end of the *truncated* contour. y_calc is that last
    # wall point (captured before the chamber is prepended), so every exit
    # condition below is evaluated on the geometry actually being built.
    A_exit = (y_calc / 1000) ** 2 * np.pi
    A_throat = (y_min / 1000) ** 2 * np.pi

    M_exit_characteristic = IT.AreaRatioInverse(A_exit / A_throat, g_exit, "supersonic")

    Cstr_delivered  = Cstr * operating.eta_c_star
    P_c_actual      = mdot * Cstr_delivered / A_throat
    T_c_effective   = T_combustion * operating.eta_c_star**2

    P_exit = IT.Pressure(P_c_actual, g_exit, M_exit_characteristic)
    T_exit = IT.Temperature(T_c_effective, g_exit, M_exit_characteristic)
    A = IT.LocalSoS(g_exit, Rs, T_exit)

    Ve      = A * M_exit_characteristic * operating.eta_nozzle
    Thrust  = mdot * Ve + (P_exit - P_amb) * A_exit
    C_F     = Thrust / (P_c_actual* A_throat)
    Exit_Angle = np.rad2deg(
        np.arctan2(wall_y[-1] - wall_y[-2], wall_x[-1] - wall_x[-2])
    )

    return NozzleSolution(
        wall_x=np.asarray(wall_x), wall_y=np.asarray(wall_y), chamber_length=Length, throat_radius=y_min, exit_radius=y_calc,
        expansion_ratio=A_exit / A_throat, exit_angle=Exit_Angle, M_exit_design=mach, M_exit=M_exit_characteristic,
        P_c_actual=P_c_actual, P_exit=P_exit, T_exit=T_exit, Ve=Ve, thrust=Thrust, thrust_momentum=mdot * Ve,
        thrust_pressure=(P_exit - P_amb) * A_exit, C_F=C_F, mdot=mdot, characteristics=characteristics,
    )
