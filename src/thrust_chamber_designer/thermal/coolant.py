#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Coolant properties from CoolProp. Replaces the thermo Mixture     #
# object, which is not reliable for hot liquid mixtures             #
#####################################################################

import numpy as np
import CoolProp
from CoolProp.CoolProp import PropsSI, get_fluid_param_string
from functools import lru_cache
from scipy.interpolate import PchipInterpolator
from types import SimpleNamespace


# Excess viscosity of liquid ethanol-water mixtures: Redlich-Kister expansion in the ethanol mole fraction with coefficients [a, b] for a + b/T.
# Fitted to the measurements of Gonzalez et al. (J. Chem. Thermodyn. 39, 2007) at 293-298 K and Ono et al. (Fluid Phase Equilib. 407, 2016)
# at 351-476 K. Reproduces the data within 6 % for ethanol mole fractions above 0.5 and within 13 % below.
ETHANOL_WATER_VISC = np.array([[-3.5668, 1830.34], [4.2081, -2199.52], [-5.1770, 2487.52]])


@lru_cache(maxsize=None)
def get_state(names):
    # CoolProp state of a pure fluid or mixture, only created once since this is slow for mixtures
    return CoolProp.AbstractState('HEOS', '&'.join(names))


@lru_cache(maxsize=None)
def phase_envelope(names, zs):
    # Bubble and dew line of a mixture, traced once by CoolProp from low pressure up to the critical point of the mixture. A flash calculation
    # at every pressure is not used for this, since it often does not converge above 45 bar. Returns the highest pressure with two phases
    # and the temperature [K], ln of the density [kg/m^3] and enthalpy [J/kg] of the saturated liquid and of the saturated vapour as functions of ln(P)
    state = CoolProp.AbstractState('HEOS', '&'.join(names))
    state.set_mole_fractions(list(zs))
    try:
        state.build_phase_envelope('none')
    except ValueError:
        raise ValueError('CoolProp can not trace the bubble and dew line of the coolant mixture ' + ' & '.join(names))

    pe    = state.get_phase_envelope_data()
    M     = state.molar_mass()
    Q     = np.array(pe.Q)
    data  = np.array([pe.p, pe.T, pe.rhomolar_liq, pe.rhomolar_vap, pe.hmolar_liq, pe.hmolar_vap])
    lines = []

    # CoolProp marks the dew line with Q = 1 and the bubble line with Q = 0. The saturated phase with the composition of the mixture is
    # the denser one with the lower enthalpy on the bubble line and the other one on the dew line, whatever CoolProp calls them
    for Q_line, rho_sat, h_sat in ((0, np.maximum, np.minimum), (1, np.minimum, np.maximum)):
        P, T, rho_1, rho_2, h_1, h_2 = data[:, Q == Q_line]
        # each line is used up to its highest pressure and sorted by pressure
        order = np.arange(np.argmax(P) + 1) if P[0] < P[-1] else np.arange(len(P) - 1, np.argmax(P) - 1, -1)
        lines.append((P[order][-1], PchipInterpolator(np.log(P[order]), np.array([T, np.log(rho_sat(rho_1, rho_2) * M), h_sat(h_1, h_2) / M]).T[order])))

    (P_bubble, bubble), (P_dew, dew) = lines

    return float(min(P_bubble, P_dew)), bubble, dew


@lru_cache(maxsize=1024)
def saturation_properties(names, zs, P):
    # Saturated liquid and vapour of a pure fluid or mixture at pressure P: bubble and dew point temperature [K], density of liquid and vapour [kg/m^3],
    # enthalpy of liquid and vapour [J/kg] and the critical pressure [Pa]. For a mixture the liquid is at its bubble point and the vapour at its
    # dew point, both with the composition of the mixture. Returns None above the critical pressure, where there is no boiling
    if len(names) == 1:
        state = get_state(names)
        state.unspecify_phase()
        P_crit = state.p_critical()
        if P >= P_crit:
            return None
        state.update(CoolProp.PQ_INPUTS, P, 0)
        T, rho_l, h_l = state.T(), state.rhomass(), state.hmass()
        state.update(CoolProp.PQ_INPUTS, P, 1)
        return T, T, rho_l, state.rhomass(), h_l, state.hmass(), P_crit

    P_crit, bubble, dew = phase_envelope(names, zs)
    if P >= P_crit:
        return None
    T_bubble, ln_rho_l, h_l = bubble(np.log(P))
    T_dew, ln_rho_g, h_g    = dew(np.log(P))

    return float(T_bubble), float(T_dew), float(np.exp(ln_rho_l)), float(np.exp(ln_rho_g)), float(h_l), float(h_g), P_crit


def saturation_temperatures(names, zs, P):
    # bubble and dew point temperature of a mixture at pressure P. Returns None above the critical pressure or if CoolProp can not trace the bubble and dew line
    try:
        sat = saturation_properties(names, zs, P)
    except ValueError:
        return None

    return None if sat is None else sat[:2]


@lru_cache(maxsize=None)
def parachor(name):
    # Parachor of a pure fluid, which links its surface tension to the molar densities of saturated liquid and vapour (Macleod-Sugden):
    # sigma = (parachor * (rho_l - rho_g))^4. Taken from the surface tension at 0.8 times the critical temperature
    state = get_state((name,))
    state.unspecify_phase()
    state.update(CoolProp.QT_INPUTS, 0, 0.8 * state.T_critical())
    sigma, rho_l = state.surface_tension(), state.rhomolar()
    state.update(CoolProp.QT_INPUTS, 1, 0.8 * state.T_critical())

    return sigma**0.25 / (rho_l - state.rhomolar())


def pure_boiling_point(name, P):
    # boiling temperature of a pure component at pressure P, or its critical temperature above the critical pressure
    state = get_state((name,))
    state.unspecify_phase()

    if P < state.p_critical():
        state.update(CoolProp.PQ_INPUTS, P, 0)
        return state.T()
    else:
        return state.T_critical()


def pure_transport(name, T, P, phase):
    # viscosity and thermal conductivity of a pure component at the conditions of the mixture. A component which on its own would be in the
    # other phase at T and P (e.g. above its own boiling point in a liquid mixture) is evaluated at saturation instead
    state = get_state((name,))
    state.unspecify_phase()

    if T < state.T_critical():
        state.update(CoolProp.QT_INPUTS, 0 if phase == 'l' else 1, T)
        is_liquid = P > state.p()
        if is_liquid == (phase == 'l'):
            state.update(CoolProp.PT_INPUTS, P, T)
    else:
        state.update(CoolProp.PT_INPUTS, P, T)

    return state.viscosity(), state.conductivity()


class Coolant():
    def __init__(self, IDs, ws, T, P):
        """[summary]
        Coolant properties at temperature T and pressure P, for a pure fluid or a mixture with mass fractions ws. IDs are CoolProp fluid names.
        Density, heat capacity and the boiling range come from the CoolProp mixture model. CoolProp has no usable transport properties for
        mixtures, so viscosity and thermal conductivity are mixed from the pure fluid values.
        The attributes follow the naming of the thermo Mixture object. Raises a ValueError if the coolant is boiling.
        USE SI UNITS
        """
        self.IDs = list(IDs)                             # fluid names as given in config
        self.ws  = list(ws)                              # mass fractions
        self.T   = T                                     # temperature [K]
        self.P   = P                                     # pressure [Pa]

        # components with a mass fraction of zero are left out of the property calculation
        self.names = tuple(get_fluid_param_string(ID, 'name') for ID, w in zip(self.IDs, self.ws) if w > 0)
        w          = np.array([w for w in self.ws if w > 0], dtype=float)
        self.Ms    = np.array([get_state((name,)).molar_mass() for name in self.names])       # molar masses [kg/mol]
        self.zs    = w / self.Ms / np.sum(w / self.Ms)                                         # mole fractions

        state = get_state(self.names)

        if len(self.names) == 1:
            state.unspecify_phase()
            state.update(CoolProp.PT_INPUTS, P, T)
            # liquid like or gas like, also used above the critical point
            self.phase = 'l' if state.rhomolar() > state.rhomolar_critical() else 'g'
            self.mu    = state.viscosity()               # dynamic viscosity [Pa s]
            self.k     = state.conductivity()            # thermal conductivity [W/m/K]

        else:
            state.set_mole_fractions(list(self.zs))
            self.phase = self.mixture_phase()
            # phase needs to be imposed, CoolProp does not reliably find the correct density of a mixture on its own
            state.specify_phase(CoolProp.iphase_liquid if self.phase == 'l' else CoolProp.iphase_gas)
            state.update(CoolProp.PT_INPUTS, P, T)

            mu, k = np.array([pure_transport(name, T, P, self.phase) for name in self.names]).T
            if self.phase == 'l':
                self.mu = self.liquid_viscosity(mu)
                self.k  = self.liquid_conductivity(k, w)
            else:
                self.mu, self.k = self.gas_transport(mu, k)

        self.rho = state.rhomass()                       # density [kg/m^3]
        self.Cp  = state.cpmass()                        # specific heat at constant pressure [J/kg/K]
        self.h   = state.hmass()                         # specific enthalpy [J/kg]
        self.MW  = state.molar_mass() * 1e3              # molar mass [g/mol]
        self.Pr  = self.Cp * self.mu / self.k            # Prandtl number


    def mixture_phase(self):
        sat = saturation_temperatures(self.names, tuple(self.zs), self.P)

        if sat is None:
            # no bubble point found. The lowest boiling point of the pure components is used as limit for the liquid instead, which is within 1 K
            # of the bubble point for ethanol-water. Only the liquid is accepted in this case
            T_limit = min(pure_boiling_point(name, self.P) for name in self.names)
            if self.T < T_limit:
                return 'l'
            raise ValueError('Coolant is boiling or close to its critical point: T = ' + str(round(self.T, 1)) + ' K is above the liquid limit of ' + str(round(T_limit, 1)) + ' K at P = ' + str(round(self.P / 1e5, 1)) + ' bar')

        T_bubble, T_dew = sat
        if self.T <= T_bubble:
            return 'l'
        elif self.T >= T_dew:
            return 'g'
        else:
            raise ValueError('Coolant is boiling: T = ' + str(round(self.T, 1)) + ' K is above the bubble point of ' + str(round(T_bubble, 1)) + ' K at P = ' + str(round(self.P / 1e5, 1)) + ' bar')


    def liquid_viscosity(self, mu):
        # Grunberg-Nissan mixing rule (logarithmic, on mole fractions), which is the ideal mixture without an excess term
        ln_mu = np.sum(self.zs * np.log(mu))

        if set(self.names) == {'Ethanol', 'Water'}:
            # ethanol-water is up to three times more viscous than the ideal mixture at room temperature
            x      = self.zs[self.names.index('Ethanol')]
            A      = ETHANOL_WATER_VISC[:,0] + ETHANOL_WATER_VISC[:,1] / self.T
            G      = A[0] + A[1] * (2*x - 1) + A[2] * (2*x - 1)**2
            ln_mu += x * (1 - x) * max(G, 0)

        return np.exp(ln_mu)


    def liquid_conductivity(self, k, w):
        if len(k) == 2:
            # Filippov equation for binary mixtures
            return w[0] * k[0] + w[1] * k[1] - 0.72 * w[0] * w[1] * abs(k[1] - k[0])
        else:
            # DIPPR 9H mixing rule
            return np.sum(w / k**2)**(-0.5)


    def gas_transport(self, mu, k):
        # Wilke mixing rule for viscosity, same weights used for the thermal conductivity (Mason and Saxena)
        M     = self.Ms
        phi   = (1 + np.sqrt(mu[:,None] / mu[None,:]) * (M[None,:] / M[:,None])**0.25)**2 / np.sqrt(8 * (1 + M[:,None] / M[None,:]))
        denom = phi @ self.zs

        return np.sum(self.zs * mu / denom), np.sum(self.zs * k / denom)


    def saturation(self):
        # Saturated state of the coolant at its pressure for the boiling models: bubble point temperature and boiling range [K], density of the saturated
        # liquid and vapour [kg/m^3], enthalpy needed to heat the coolant to its bubble point and enthalpy of evaporation [J/kg], surface tension [N/m]
        # and critical pressure [Pa]. Returns None above the critical pressure
        sat = saturation_properties(self.names, tuple(self.zs), self.P)
        if sat is None:
            return None
        T_bubble, T_dew, rho_l, rho_g, h_l, h_g, P_crit = sat

        # The surface tension follows from the densities at saturation with the parachors of the components (Macleod-Sugden). The mixing rule
        # used for sigma further down needs every component as a liquid on its own, which fails close to the critical point of a component
        sigma = float(np.sum(self.zs * [parachor(name) for name in self.names]) * (rho_l - rho_g) / (self.MW * 1e-3))**4

        return SimpleNamespace(T_bubble=T_bubble, dT_bp=max(T_dew - T_bubble, 0.0), rho_l=rho_l, rho_g=rho_g, dH_sub=max(h_l - self.h, 0.0), Hvap=h_g - h_l,
                               sigma=sigma, P_crit=P_crit)


    # the following properties are only needed by the film cooling model

    def Cp_vapour(self, T):
        # specific heat of the coolant vapour at temperature T, taken as ideal gas [J/kg/K]. Evaluated at low pressure, where every component is a gas
        return sum(w * PropsSI('CP0MASS', 'T', T, 'P', 1000, ID) for ID, w in zip(self.IDs, self.ws) if w > 0)


    @property
    def sigma(self):
        # surface tension [N/m], mixing rule of Winterfeld, Scriven and Davis based on the volume fractions of the components
        sigma = np.ndarray(len(self.names))
        V     = np.ndarray(len(self.names))

        for i, name in enumerate(self.names):
            state = get_state((name,))
            state.unspecify_phase()
            state.update(CoolProp.QT_INPUTS, 0, self.T)
            sigma[i] = state.surface_tension()
            V[i]     = 1 / state.rhomolar()

        phi = self.zs * V / np.sum(self.zs * V)

        return np.sum(phi * np.sqrt(sigma))**2
