#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Creator:  Joanthan Neeser                                         #
# Date:     15.12.2022                                              #
# Version:  2.3  													#
# License:	GNU GENERAL PUBLIC LICENSE V3							#                                          
#####################################################################

import numpy as np
import scipy.optimize 

from .section_sim import HeatEquationSolver
from .coolant import Coolant, saturation_properties
from .stress import WallStress


# Boiling of ethanol beyond the critical heat flux at high pressure, from figure 6 of Meyer, Linne and Rousar (NASA TM-1998-206612): above
# 250 psia the wall did not go into film boiling at the CHF. After a first temperature excursion at about constant heat flux, the heat flux
# kept rising with the wall temperature up to a second excursion at about 1.55 times the CHF (35 bar, 11 m/s, SDA-3C ethanol, 2.4 mm tube)
POST_CHF_P_MIN    = 17e5                    # lowest coolant pressure with this behaviour [Pa], film boiling and burnout below
POST_CHF_DT_FLAT  = 45.0                    # first temperature excursion of the wall at the CHF [K]
POST_CHF_DT_SLOPE = 295.0                   # rise of the wall temperature for an additional heat flux of one CHF [K]
POST_CHF_LIMIT    = 1.55                    # heat flux of the second excursion, relative to the CHF [-]


class HeatTransfer():
    def __init__(self, cea, gas, geometry, material, coolant, cooling_geometry, m_dot, m_dot_coolant, T_amb, output, settings2D, model='standard-bartz', cool_model='gnielinski', eta_c_star=0.92, film=False, boiling=False, chf_model='meyer', post_chf='fallback'):
        """[summary]
        Class to calculate heat tranfer coefficients and radiative heat transfer at arbitrary locations along the chamber contour.
		These functions are passed to the 2D thermal simulation, after which the program advances to the next chamber section. Several options are 
		available for coolant and heat transfer models. Coolant flow properties stored as total conditions, and use a 'thermo' 
		Mixture object to update coolant properties. Hot gas properties from CEA and taken at total chamber conditions. 
		Temperature and pressure of the gas are determined using isentropic expansion.        
        Material thermal condutivity can be temperature dependent.
        USE SI UNITS (sorry freedom lovers)
        """
        self.cea = cea                       			# NASA CEA object 
        self.gas = gas                      			# isentropic gas object 
        self.geometry = geometry             			# engine contour
        self.material = material             			# material object
        self.coolant = coolant               			# themro Mixture object
        self.m_dot = m_dot                   			# total mass flow
        self.m_dot_coolant = m_dot_coolant   			# coolant mass flow [kg/s]
        self.model = model                   			# hot gas side heat transfer model
        self.cool_model = cool_model		 			# coolant side heat transfer model
        self.eta_c_star = eta_c_star       			# combustion efficiency
        self.cooling_geometry = cooling_geometry	 	# cooling channel geometry class

        self.A_c = cooling_geometry.A_c					# cooling channel area [m^2]
        self.D_h = cooling_geometry.D_h				    # cooling channel hydraulic diameter [m]

        self.film = film
        self.boiling = boiling                          # nucleate boiling at the cooling channel walls
        self.chf_model = chf_model                      # critical heat flux correlation
        self.post_chf  = post_chf                       # boiling beyond the CHF: 'fallback' (forced convection only) or 'meyer' (post-CHF branch of ethanol at high pressure)

        if post_chf not in ('fallback', 'meyer'):
            raise ValueError('Invalid post-CHF treatment. Select: "fallback" or "meyer"')
        if post_chf == 'meyer' and coolant.names[np.argmax(coolant.zs * coolant.Ms)] != 'Ethanol':
            raise ValueError('The "meyer" post-CHF treatment was measured with ethanol and is only valid for coolants based on ethanol, select "fallback" instead')

        self.T_amb = T_amb								# ambient temperature [K], must be float!!!
        self.boltzmann = 5.67e-8						# stefan boltzmann constant

        self.out = output								# output class
        self.settings2D = settings2D					# settings for 2D thermal sim

        self.stress = WallStress(material, cooling_geometry, T_amb)    # wall stress analysis, wall is free of thermal stress at ambient temperature



    def heat_trans_coeff_gas(self, T_wall, idx):
        # get hot gas properties for this chamber location. CEA properties assumed constant, with isentropic gas properties being taken at local point
        gamma = self.cea.gamma
        mu    = self.cea.mu
        cp    = self.cea.Cp
        Pr    = self.cea.Pr
        T_s   = self.gas.T_s[idx]
        p_s   = self.gas.p_s[idx]
        M     = self.gas.M[idx]
        T_aw  = self.gas.T_aw[idx]

        # local geometrical properties 
        local_area  = np.pi * self.geometry[idx,1]**2
        throat_area = np.pi * np.amin(self.geometry[:,1])**2
        D_t         = 2 * np.amin(self.geometry[:,1])
        
        cstar = self.cea.chamber_pressure * throat_area / self.m_dot
        
        # hot gas temperature estimate used for the cinjarev correlation
        T_hg       = T_s + 0.9*(T_aw * self.eta_c_star**2 - T_s)

        # in case of film 
        # stanton number correction without film cooling is 1.0
        St_St0 = 1.0
        eta    = 0.0
        if self.film != False:
            # Reduced heat transfer under the liquid films and effectiveness of the gaseous films downstream of them. The convective heat of the
            # combustion gas evaporates a liquid film and does not reach the wall under it: the wall faces coolant at saturation temperature,
            # as it does where the gaseous film starts (effectiveness of 1)
            St_St0 = self.film.St_St0[idx]
            eta    = 1.0 if self.film.liquid[idx] else self.film.eta[idx]

        # Nusselt number correlation for the combustion gases
        if self.model == 'standard-bartz':
            # standard bartz correlation, mostly applicable for larger engines. Tends to oveerpredict heat flux near the troat, especially in smaller engines
            sigma  = ((0.5 * T_wall/self.cea.Tc * (1+(gamma-1)/2 * M**2) + 0.5)**(0.68) * (1+(gamma-1)/2 * M**2)**(0.12))**(-1)
            halpha = 0.026/(D_t**0.2) * (mu**0.2)*cp/(Pr**0.6) * (self.gas.p_t/cstar)**0.8 * (throat_area/local_area)**0.9 * sigma

        elif self.model == 'modified-bartz':
            # modified bartz correlation, mostly applicable for larger engines. Tends to oveerpredict heat flux near the troat, especially in smaller engines
            T_f    = 0.5 * T_wall + 0.28 * T_s + 0.22 * T_aw
            G      = self.m_dot/local_area
            halpha = 0.026 * G**0.8/(D_t)**0.2 * mu**0.2*cp/Pr**0.6 * (self.cea.Tc/T_f)**0.68

        elif self.model == 'cinjarev':
            # cinjarev correlation, more useful for medium to small scale motors
            halpha = 0.01975 * self.cea.k**0.18 * (self.m_dot*cp)**0.82 / (2*self.geometry[idx,1])**1.82 * (T_hg/T_wall)**0.35

        else:
            raise ValueError('Invalid heat transfer method. Select: "standard-bartz", "modified-bartz" or "cinjarev"')



        # Are you using additives like PDMS or TEOS? Then you should reduce factor_test by the specific amount your additive reduces flux by
        # For 1% TEOS, you can expect roughly a 25% flux reduction.


        # the gaseous film lowers the gas temperature at the wall towards the temperature of the coolant vapour
        if eta > 0:
            T_hg = T_hg - eta * (T_hg - self.film.T_film[idx])

        return halpha * St_St0, T_hg
        
        
    def friction_factor(self, idx, Re):
        # Darcy Friction Factor from the Colebrook equation. Use surface roughness given in Material Class
        surface_roughness = self.material.roughness
        return scipy.optimize.fsolve(lambda f: -2 * np.log10(surface_roughness / (3.7 * self.D_h[idx]) + 2.51 / (Re * np.sqrt(f))) -1 / np.sqrt(f), 0.001)[0]


    def curvature_factor(self, idx):
        # Curvature of helical cooling channels: centrifugal forces drive secondary flows (Dean vortices) across the channel. Ratio of the friction
        # factor of the curved channel to the straight one after Ito (1959), [Re (r/R)^2]^0.05 with the half width r = D_h/2 and the radius of
        # curvature R, for turbulent flow. Held at 1 below Re (r/R)^2 = 1, which includes straight channels
        return max(self.Re * (self.D_h[idx] / (2 * self.cooling_geometry.R_curv[idx]))**2, 1.0)**0.05


    def pressure_drop(self, idx):
        # using Darcy Friction Factor to determine pressure drop, increased by the curvature of helical channels
        fd = self.friction_factor(idx, self.Re) * self.curvature_factor(idx)
        dp = fd * self.section_length[idx] / self.D_h[idx] * 0.5 * self.coolant.rho * self.v_coolant**2

        return dp, fd

        
    def radiation(self, idx):
        # simple radiation model based on h2o and co2 emissions
        R_c = self.geometry[idx,1]					# chamber radius

        p_h2o = self.cea.mole_fractions['H2O'][0] * self.gas.p_s[idx]
        # radiative heat flux of water molecules 
        q_rad = 5.74 * (p_h2o/1e5*R_c)**0.3 * (self.gas.T_s[idx]/100)**3.5

        # check if CO2 is present in the exhaust
        if 'CO2' in self.cea.mole_fractions:
            p_co2 = self.cea.mole_fractions['CO2'][0] * self.gas.p_s[idx]
            # radiative heat flux of co2 molecules 
            q_rad += 4 * (p_co2/1e5*R_c)**0.3 * (self.gas.T_s[idx]/100)**3.5
    
        return q_rad


    def nusselt_gnielinski(self, Pr, idx, laminar_branch=True):
        # Gnielinski correlation extended to laminar and transitional flow, see Gnielinski (2013), 'On heat transfer in tubes'.
        # The turbulent correlation on its own goes to zero at Re = 1000 and can not be used below Re = 4000.
        # Without the laminar branch the turbulent correlation is used down to Re = 2300 and held at its value there for lower Re,
        # for rough channels which become turbulent at lower Re than smooth tubes

        def turbulent(Re):
            fd = self.friction_factor(idx, Re)
            return (fd/8) * (Re - 1000)*Pr / (1 + 12.7*(fd/8)**0.5 * (Pr**(2/3) - 1))

        def laminar(Re):
            # local Nusselt number of developing laminar flow at constant wall temperature (lower than for constant heat flux).
            # Distance from the channel inlet is limited to one hydraulic diameter, the correlation is singular at the inlet
            Gz   = Re * Pr * self.D_h[idx] / max(self.channel_length, self.D_h[idx])
            Nu_2 = 1.077 * Gz**(1/3)
            Nu_3 = 0.5 * (2 / (1 + 22*Pr))**(1/6) * Gz**0.5
            return (3.66**3 + 0.7**3 + (Nu_2 - 0.7)**3 + Nu_3**3)**(1/3)

        if not laminar_branch:
            return turbulent(max(self.Re, 2300))

        if self.Re <= 2300:
            return laminar(self.Re)

        elif self.Re >= 4000:
            return turbulent(self.Re)

        else:
            # linear interpolation between laminar flow at Re = 2300 and turbulent flow at Re = 4000
            gamma = (self.Re - 2300) / (4000 - 2300)
            return (1 - gamma) * laminar(2300) + gamma * turbulent(4000)


    def heat_trans_coeff_coolant(self, T_wall_coolant, idx, wall=None):
        # wall: 'bottom', 'top' or 'side' wall of the cooling channel, only matters for the curvature of helical channels
        # coolant flow velocity based on bulk properteis
        self.v_coolant = self.m_dot_coolant / (self.coolant.rho * self.A_c[idx])
        self.Re = self.coolant.rho * self.v_coolant * self.D_h[idx] / self.coolant.mu
		
		# temperature approximation in the near wall fluid film using a logarithmic mean for log temperature profile
        def get_near_wall_fluid():
            T_avg = (T_wall_coolant - self.coolant.T) / np.log(T_wall_coolant / self.coolant.T)
            fluid = Coolant(IDs=self.coolant.IDs, ws=self.coolant.ws, T=T_avg, P=self.coolant.P)
            return fluid

		# thermodynamic properties of the near wall fluid, Pr implementation of thermo does not work reliably for mixtures near their critical point. Uses gaseouse Pr if liquid Pr returns 'None'
        if self.coolant.phase == 'l':
            Pr = self.coolant.Pr
            Cp = self.coolant.Cp
            mu = self.coolant.mu

        elif self.coolant.phase == 'g':
            near_wall_coolant = get_near_wall_fluid()
            Pr = near_wall_coolant.Pr
            Cp = near_wall_coolant.Cp
            mu = near_wall_coolant.mu

        else:
            raise ValueError('Coolant is neither gaseous, nor liquid. Thermo implementation not suitable for supercritical fluids')
        
        # coolant thermal conductivity
        k  = Cp * mu / Pr

        # Nusselt number correlations for the coolant side 
        if self.cool_model == 'dittus-boelter':
            # Dittus-Boelter equation (valid for Re > 1e4 and 0.7 < Pr < 16700)
            near_wall_coolant = get_near_wall_fluid()
            Nu = 0.027 * self.Re**0.8 * Pr**0.33 * (self.coolant.mu / near_wall_coolant.mu)**(0.14)		

        elif self.cool_model == 'dittus-boelter-simple':
            # Dittus-Boelter equation without viscosity correction (valid for Re > 1e4 and 0.7 < Pr < 160)
            Nu = 0.023 * self.Re**0.8 * Pr**0.4

        elif self.cool_model == 'gnielinski':
            # Gnielinski correlation (valid for Re < 5e6 and 0.5 < Pr < 2000), includes laminar and transitional flow
            Nu = self.nusselt_gnielinski(Pr, idx)

        elif self.cool_model == 'gnielinski-rough':
            # Gnielinski turbulent correlation with the friction factor of the rough channel, no laminar flow (valid for Pr 0.5 to 2000)
            Nu = self.nusselt_gnielinski(Pr, idx, laminar_branch=False)

        else:
            raise ValueError('Invalid heat transfer method. Select: "dittus-boelter", "dittus-boelter-simple", "gnielinski" or "gnielinski-rough"')
        
        # convert Nusselt number to heat transfer coefficient
        halpha = Nu * k / self.D_h[idx]

        # Helical channels are curved around the chamber axis. The secondary flow drives the coolant towards the concave top wall, where the
        # turbulence is enhanced, and away from the convex bottom wall on the hot gas side, where it is damped: Nusselt number multiplied and
        # divided by the curvature factor, after Taylor. The side walls keep the value of a straight channel
        if wall == 'top':
            halpha = halpha * self.curvature_factor(idx)
        elif wall == 'bottom':
            halpha = halpha / self.curvature_factor(idx)

        if halpha < 0:
            raise ValueError('Negative heat transfer coefficient, check applicability of cooling model to Reynolds number range')

        # check if halpha is an array or a float (artifact of the pressure drop dependence or fluid model)
        if isinstance(halpha, float):
            return halpha
        else:
            return halpha[0]


    def heat_flux_boiling(self, T_wall, halpha_c):
        # Heat flux into the coolant at the faces of the cooling channel walls with the temperatures T_wall, halpha_c is the heat transfer coefficient
        # of forced convection at these faces. Walls above the saturation temperature are cooled by subcooled nucleate boiling, after Liu and
        # Winterton (1991): forced convection and nucleate pool boiling (Cooper) are added as the root of the sum of squares, with the boiling
        # suppressed by the flow. With the post-CHF branch, faces beyond the CHF of the section follow the boiling of ethanol at high pressure
        # measured by Meyer et al. instead. Returns the heat flux and its derivative with respect to the wall temperature
        sat    = self.sat
        P_r    = self.coolant.P / sat.P_crit
        cooper = 55 * P_r**0.12 * (-np.log10(P_r))**(-0.55) * self.coolant.MW**(-0.5)
        S      = 1 / (1 + 0.055 * self.Re**0.16)
        q_chf  = self.q_chf_post

        def nucleate(T_wall, h):
            q    = h * (T_wall - self.coolant.T)
            boil = T_wall > sat.T_bubble
            q_fc = q[boil]
            q_b  = np.maximum(q_fc, 1.0)

            # the pool boiling heat transfer coefficient depends on the heat flux itself, this iteration always converges
            for i in range(40):
                h_pool  = cooper * q_b**0.67
                # mixtures boil worse than pure fluids, since the volatile component has to diffuse to the wall: correction of Thome and Shakir (1987)
                # with the boiling range of the mixture and a mass transfer coefficient of 0.0003 m/s. No effect for pure fluids
                h_pool /= 1 + h_pool / q_b * sat.dT_bp * (1 - np.exp(-q_b / (sat.rho_l * sat.Hvap * 0.0003)))
                q_b     = np.sqrt(q_fc**2 + (S * h_pool * (T_wall[boil] - sat.T_bubble))**2)

            q[boil] = q_b
            return q

        def heat_flux(T_wall):
            q = nucleate(T_wall, halpha_c)
            if q_chf is None:
                return q

            over = q > q_chf
            if np.any(over):
                # wall temperature at which nucleate boiling reaches the CHF at these faces, by bisection
                h, lo, hi = halpha_c[over], np.full(np.sum(over), sat.T_bubble), T_wall[over].copy()
                for i in range(40):
                    mid    = 0.5 * (lo + hi)
                    above  = nucleate(mid, h) > q_chf
                    hi, lo = np.where(above, mid, hi), np.where(above, lo, mid)
                T_chf = 0.5 * (lo + hi)

                # post-CHF branch: constant heat flux during the first temperature excursion, then rising linearly with the wall temperature
                q[over] = np.minimum(q[over], q_chf * np.maximum(1.0, 1 + (T_wall[over] - T_chf - POST_CHF_DT_FLAT) / POST_CHF_DT_SLOPE))
            return q

        dT    = 0.01
        q     = heat_flux(T_wall)
        slope = (heat_flux(T_wall + dT) - q) / dT

        # Beyond the CHF the tangent of the boiling curve flips between the steep nucleate branch and the shallow post-CHF branch from one
        # iteration to the next. There the secant to the bubble point is used instead: it never predicts boiling heat flux below the bubble
        # point, so the next iterate can not fall into forced convection only and jump back up again
        if q_chf is not None:
            post        = q > q_chf * (1 - 1e-9)
            slope[post] = q[post] / np.maximum(T_wall[post] - sat.T_bubble, 1.0)

        return q, slope


    def critical_heat_flux(self, halpha_c, idx):
        # Critical heat flux (CHF) of the subcooled coolant. Above it a vapour film separates the coolant from the wall and nucleate boiling breaks down
        sat    = self.sat
        dT_sub = max(sat.T_bubble - self.coolant.T, 0.0)
        ethanol = self.coolant.names[np.argmax(self.coolant.zs * self.coolant.Ms)] == 'Ethanol'      # ethanol is the main component of the coolant by mass

        if self.chf_model == 'meyer':
            # Correlation of Meyer, Linne and Rousar (NASA TM-1998-206612) for ethanol with the product of velocity and subcooling, measured in heated
            # tubes of 2.4 mm diameter at 10 to 48 bar, 3 to 23 m/s and 18 to 200 K subcooling (within 20 %). In units of ft/s, F, psia and BTU/in^2/s.
            # The coolant only enters with its saturation temperature: CHF of a mixture with water is expected to be higher than predicted
            if not ethanol:
                raise ValueError('The "meyer" critical heat flux correlation is only valid for coolants based on ethanol, select "gambill" or "hall-mudawar" instead')
            V_dT_sub = (self.v_coolant / 0.3048) * (dT_sub * 1.8)
            F_P      = max(1.17 - 8.56e-4 * self.coolant.P / 6894.76, 0.0)
            return (0.1003 + 0.05264 * np.sqrt(V_dT_sub)) * F_P * 1.6353e6

        elif self.chf_model == 'gambill':
            # Superposition of Gambill (1963) for any coolant: CHF of pool boiling (Kutateladze, with the increase by subcooling) plus the heat flux
            # of forced convection to the subcooled coolant, here with the wall at saturation temperature. Uses the properties of the coolant
            # mixture at saturation. On the conservative side: 44 % below the ethanol measurements of Meyer et al. on average
            pool  = 0.15 * sat.Hvap * sat.rho_g * (sat.sigma * 9.81 * (sat.rho_l - sat.rho_g) / sat.rho_g**2)**0.25
            pool *= 1 + (sat.rho_l / sat.rho_g)**0.923 * sat.dH_sub / (25 * sat.Hvap)
            return pool + halpha_c * dT_sub

        elif self.chf_model == 'hall-mudawar':
            # Correlation of Hall and Mudawar (2000) for subcooled water in tubes of 0.25 to 15 mm diameter: boiling number as a function of the Weber
            # number, the density ratio and the subcooling. Uses the properties of the coolant mixture at saturation and the hydraulic diameter of the channel.
            # It is too high for ethanol: on the tests of Meyer et al. by a factor of 0.8 * dT_sub^0.25 / v^0.2 [K, m/s], which is 1.6 on average.
            # For coolants based on ethanol the result is divided by this factor (subcooling of at least 18 K as in the tests), which reproduces
            # the tests with a scatter of 12 %. The correlation is not too high for water, so this is probably on the safe side for mixtures with water
            G     = self.coolant.rho * self.v_coolant
            We    = G**2 * self.D_h[idx] / (sat.rho_l * sat.sigma)
            q_chf = 0.0722 * We**(-0.312) * (sat.rho_l / sat.rho_g)**(-0.644) * (1 + 0.9 * (sat.rho_l / sat.rho_g)**0.724 * sat.dH_sub / sat.Hvap) * G * sat.Hvap
            if ethanol:
                q_chf /= 0.8 * max(dT_sub, 18.0)**0.25 / self.v_coolant**0.2
            return q_chf

        else:
            raise ValueError('Invalid critical heat flux method. Select: "meyer", "gambill" or "hall-mudawar"')


    def section_heat_flux(self, idx):
        self.q_rad = self.radiation(idx)
        
        # solve 2D section temperature profile, passes functions for heat transfer coefficients for temperature dependence of boundary conditions
                
        print('SOLVING Section Number	', len(self.geometry[:,1]) - idx, ' / ', len(self.geometry[:,1]))
        
        # the coolant can only boil at the walls if it is a liquid below its critical pressure
        self.sat = self.coolant.saturation() if self.boiling and self.coolant.phase == 'l' else None
        boiling  = self.heat_flux_boiling if self.sat is not None else None

        # with the post-CHF branch, the boiling curve needs the CHF of this section before the section is solved. Above 17 bar only
        self.q_chf_post = None
        if self.sat is not None and self.post_chf == 'meyer' and self.coolant.P > POST_CHF_P_MIN:
            self.q_chf_post = self.critical_heat_flux(self.heat_trans_coeff_coolant(self.coolant.T + 1.0, idx, 'bottom'), idx)

        solver = HeatEquationSolver(idx, self.gas, self.material, self.cooling_geometry, self.heat_trans_coeff_gas, self.heat_trans_coeff_coolant, self.q_rad, self.coolant.T, self.T_amb, self.out.folder_path, self.settings2D, boiling, film=self.film)
        solver.run_sim()

        # heat flux into the coolant with nucleate boiling, compared to the critical heat flux: the mean over the bottom of the channel, where the
        # heat from the hot gas side enters the coolant. The highest local heat flux, in the corner of the channel, grows with mesh refinement
        # and is only saved for information
        self.q_c_max    = solver.q_c_max
        self.q_c_bottom = solver.q_c_bottom_mean
        self.T_sat     = np.nan
        self.q_chf     = np.nan
        self.chf_state = 0                              # 0: below the CHF, 1: on the post-CHF branch, 2: solved again without boiling
        if self.sat is not None:
            self.T_sat = self.sat.T_bubble
            self.q_chf = self.critical_heat_flux(solver.halpha_c_bottom, idx)

            # highest heat flux at the channel bottom which boiling can carry: the CHF, or the second excursion of the post-CHF branch
            limit = POST_CHF_LIMIT if self.q_chf_post is not None else 1.0

            if solver.coolant_wall_temp > self.T_sat and self.q_c_bottom > limit * self.q_chf:
                # Boiling can not carry this heat flux. The heat transfer beyond it is not modelled: the section is solved again with
                # forced convection only, so that boiling is not counted on where it breaks down. Film boiling can give much hotter walls
                print('Heat flux at the channel bottom ', round(self.q_c_bottom / 1e6, 2), ' > ', round(limit, 2), ' x CHF of ', round(self.q_chf / 1e6, 2), ' [MW/m^2], section is solved again without nucleate boiling')
                self.chf_exceeded.append(idx)
                self.chf_state      = 2
                solver.boiling_func = None
                solver.run_sim()

            elif self.q_chf_post is not None and self.q_c_bottom > self.q_chf * (1 - 1e-6):
                self.post_chf_sections.append(idx)
                self.chf_state = 1

        self.T_wall_c  = solver.coolant_wall_temp       # highest wall temperature of the cooling channel

        self.T_wall_i  = solver.inner_wall_temp	    # inner wall temperature taken as maximum temperature of the 2D profile
        self.halpha    = solver.halpha			    # heat transfer coefficients taken as the of the boundary conditions of the 2D solver at the last timestep
        self.halpha_c  = solver.halpha_c_bottom		# average heat transfer coefficient at bottom wall
        self.T_hg      = solver.T_hg
        self.field     = solver.field                   # temperature field of the section for the 3D plot

        # total heat flux into the inner chamber wall
        self.q 		   = np.mean(solver.q_chamber)

        # radiation leaving to ambient
        self.q_rad_out = np.mean(solver.q_outer)

        # wall temperatures and stresses with the coolant pressure at the inlet of the section
        self.wall_stress = self.stress.section(idx, solver, self.coolant.P, self.gas.p_s[idx])
		
        # ensure that FiPy output object is actually a float, multiplied by the number of channels for total area. Q_c is per length of the channel
        Q = float(solver.Q_c) * self.section_length[idx] * self.cooling_geometry.n_channels

 
        # update cooling fluid and pressure. Expected temperature rise and pressure drop 
        dT             = Q / (self.m_dot_coolant * self.coolant.Cp) 
        dp, _          = self.pressure_drop(idx)

        # Evaporation of the coolant itself is not modelled. Where the coolant reaches its saturation temperature it is kept just below it as a liquid
        if self.sat is not None:
            T_sat = saturation_properties(self.coolant.names, tuple(self.coolant.zs), self.coolant.P - dp)[0]
            if self.coolant.T + dT > T_sat - 0.1:
                dT = T_sat - 0.1 - self.coolant.T
                self.bulk_boiling.append(idx)
        
        # recalcualte cooling fluid properties, such as density, Pr, Cp etc. 
        self.coolant   = Coolant(IDs=self.coolant.IDs, ws=self.coolant.ws, T=(self.coolant.T+dT), P=(self.coolant.P-dp))
        
        
    def run(self, progress=None):
        # progress: optional function called after every section with (number of sections solved, total number of sections, index of the
        # section), used by the desktop app to show the run while it is going. It can raise an exception to stop the run
        # arrays for section length and area in between the 2D sections solved in the thermal sim
        self.section_length     = np.ndarray(len(self.geometry[:,1]))     # length of the cooling channels in each section [m]
        self.channel_length     = 0                                      # distance travelled by the coolant since the channel inlet [m]
        self.chf_exceeded       = []                                     # sections in which boiling can not carry the heat flux, solved again without boiling
        self.post_chf_sections  = []                                     # sections beyond the CHF on the post-CHF branch
        self.bulk_boiling       = []                                     # sections in which the coolant itself reaches its saturation temperature

        # determine the section length and inner chamber surface area in each section
        for i in range(len(self.geometry[:,1])):
        # section number 0 at the injector!!!
			
            if self.settings2D.start_idx == -1:
				# for coolant entering at the bottom of the cooling channels, use idx as inverse of i 
                idx = len(self.geometry[:,1]) - i - 1
			
            elif self.settings2D.start_idx == 0:
				# in case coolant starts at injector side
                idx = i
			
            else:
                raise ValueError('Invalid starting point for cooling fluid, select -1 or 0 for nozzle or injector side, respectively')

            if i == 0:
                self.section_length[idx] = 0
                
            else:
                # length of the contour between the section the coolant comes from and this one, helical channels are longer by 1 / cos(beta)
                prev  = idx + 1 if self.settings2D.start_idx == -1 else idx - 1
                x_len = (self.geometry[prev,0] - self.geometry[idx,0])**2
                y_len = (self.geometry[prev,1] - self.geometry[idx,1])**2

                self.section_length[idx] = np.sqrt(x_len + y_len) / np.cos(self.cooling_geometry.beta[idx])

            self.channel_length += self.section_length[idx]

            # solve section heat transfer and temperature field and update coolant properties
            self.section_heat_flux(idx)

            # film cooling ports in the chamber wall take their coolant from the cooling channels, less coolant is left for the rest of the channel
            if self.film != False:
                self.m_dot_coolant -= self.film.m_dot_ports[idx]

            # write to output class
            self.out.halpha[idx]    = self.halpha
            self.out.halpha_c[idx]  = self.halpha_c
            self.out.q_rad[idx]     = self.q_rad
            self.out.q[idx]         = self.q
            self.out.T_wall_i[idx]  = self.T_wall_i
            self.out.T_c[idx]       = self.coolant.T
            self.out.P_c[idx]       = self.coolant.P
            self.out.Re[idx]	    = self.Re
            self.out.T_hg[idx]	    = self.T_hg 
            self.out.v_coolant[idx] = self.v_coolant
            self.out.T_wall_c[idx]  = self.T_wall_c
            self.out.T_sat[idx]     = self.T_sat
            self.out.q_c_max[idx]   = self.q_c_max
            self.out.q_chf[idx]     = self.q_chf
            self.out.q_c_bottom[idx] = self.q_c_bottom
            self.out.chf_state[idx]  = self.chf_state
            self.out.fields[idx]     = self.field

            for key, value in self.wall_stress.items():
                if key == 'regime':
                    self.out.regime[idx] = value
                else:
                    getattr(self.out, key)[idx] = value

            if progress is not None:
                progress(i + 1, len(self.geometry[:,1]), idx)

        if self.boiling:
            x = self.geometry[sorted(self.chf_exceeded), 0] * 1e3
            x_post = self.geometry[sorted(self.post_chf_sections), 0] * 1e3
            print('')
            if len(x_post) > 0:
                print('Beyond the critical heat flux in ', len(x_post), ' of ', len(self.geometry[:,1]), ' sections, between x = ', round(x_post[0], 1), ' and ', round(x_post[-1], 1), ' [mm]')
                print('These sections are on the post-CHF branch of ethanol at high pressure (Meyer et al.), up to ', POST_CHF_LIMIT, ' times the CHF')
            if len(x) > 0:
                print('WARNING: boiling can not carry the heat flux in ', len(x), ' of ', len(self.geometry[:,1]), ' sections, between x = ', round(x[0], 1), ' and ', round(x[-1], 1), ' [mm]')
                print('Wall temperatures in these sections are calculated without nucleate boiling. With film boiling they can be much higher')
            elif len(x_post) == 0 and np.any(np.isfinite(self.out.q_chf)):
                print('Critical heat flux is not exceeded, highest heat flux at the channel bottom is ', round(np.nanmax(self.out.q_c_bottom / self.out.q_chf) * 100), ' % of the critical heat flux')

            if len(self.bulk_boiling) > 0:
                print('WARNING: the coolant itself reaches its saturation temperature at x = ', round(self.geometry[self.bulk_boiling[0], 0] * 1e3, 1), ' [mm] and is kept there as a liquid')
                print('Two-phase flow in the cooling channels is not modelled, results downstream of this point are not valid')

        if np.any(self.cooling_geometry.beta > 0):
            contour = np.sum(np.hypot(np.diff(self.geometry[:,0]), np.diff(self.geometry[:,1])))
            print('')
            print('Helical cooling channels: the coolant flows ', round(self.channel_length * 1e3, 1), ' [mm] along the channels, ', round(self.channel_length / contour, 2), ' times the length of the contour,')
            print('and turns ', round(self.cooling_geometry.twist[-1] / (2 * np.pi), 2), ' times around the chamber axis')

        # write to file in output folder
        self.out.write_csv()
        self.out.write_fields()


