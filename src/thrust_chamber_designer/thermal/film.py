###############################################################################
#                         Liquid Film Cooling Model					          #
# Basic 0D analytical film cooling model based energy balance by Shine et al. #
#                                                                   	      #
# Creator:  Joanthan Neeser                                        		      #
# Date:     06.02.2022                                             		      #
# Version:  1.1 														      #                                      
###############################################################################


import numpy as np
from scipy import optimize

from .coolant import saturation_properties


class FilmCooling():
	def __init__(self, cea, gas, coolant, geometry, m_dot, ports):
		# Film cooling by rings of coolant injection ports along the chamber contour. Every entry of ports is one ring, given as
		# [x coordinate, coolant mass flow, injection velocity, port diameter]. m_dot is the total mass flow including the film coolant
		self.cea       = cea
		self.gas       = gas
		self.coolant   = coolant
		self.geometry  = geometry
		self.m_dot     = m_dot

		x  = self.geometry[:,0]
		dx = x[1] - x[0]

		# rings are placed at the closest point of the contour and sorted from the injector to the nozzle. Rings without mass flow are left out
		self.ports = []
		for x_port, m_dot_c, v_c, d_inj in ports:
			if m_dot_c == 0.0:
				continue
			if not x[0] - dx <= x_port <= x[-1] + dx:
				raise ValueError('Film cooling ports at x = ' + str(x_port) + ' m are outside of the chamber contour, which reaches from x = ' + str(round(x[0], 4)) + ' m to ' + str(round(x[-1], 4)) + ' m')
			self.ports.append([np.argmin(np.abs(x - x_port)), m_dot_c, v_c, d_inj])
		self.ports.sort(key=lambda port: port[0])

		# the film at each point of the contour belongs to the last ring passed: it has the injection velocity of this ring, and the combustion
		# gas flows without the coolant of this ring and of the rings further downstream
		self.v_c         = np.zeros(len(x))
		self.m_dot_g     = np.ones(len(x)) * (self.m_dot - sum(port[1] for port in self.ports))
		# coolant taken from the cooling channels at each point of the contour. Film from the injector face comes from the injector manifold instead
		self.m_dot_ports = np.zeros(len(x))
		for idx, m_dot_c, v_c, d_inj in self.ports:
			self.v_c[idx:]     = v_c
			self.m_dot_g[idx:] = self.m_dot - sum(port[1] for port in self.ports if port[0] >= idx)
			if idx > 0:
				self.m_dot_ports[idx] += m_dot_c

		# The film boils at the static pressure of the combustion gas: bubble point temperature of the coolant mixture and enthalpy needed to
		# heat the injected coolant and evaporate it completely [J/kg], at each point of the contour
		self.T_sat      = np.zeros(len(x))
		self.dH_fg_star = np.zeros(len(x))
		for i, p_s in enumerate(self.gas.p_s):
			sat = saturation_properties(self.coolant.names, tuple(self.coolant.zs), float(p_s))
			if sat is None:
				raise ValueError('Film cooling needs a liquid film: the chamber pressure is above the critical pressure of the coolant')
			self.T_sat[i]      = sat[0]
			self.dH_fg_star[i] = sat[5] - self.coolant.h

		# Turbulence correction factor
		e_t = 0.1		# using highest value found for small GOx/H2 engines found in literature
		self.K_t = 1 + 4 * e_t


	def gas_flow(self, idx):
		# chamber diameter and density, velocity and Reynolds number of the combustion gas at a point of the contour
		d     = 2 * self.geometry[idx,1]
		rho_g = self.gas.p_s[idx] / (self.cea.R * self.gas.T_s[idx])
		v_g   = self.m_dot_g[idx] / rho_g / (np.pi * d**2 / 4)
		Re_g  = v_g * d * rho_g / self.cea.mu

		return d, rho_g, v_g, Re_g


	def coolant_flow(self, idx, m_dot_c, v_c, d_inj):
		# liquid mass flow of a ring of ports which stays on the wall
		d, rho_g, v_g, Re_g = self.gas_flow(idx)

		# coolant flow Reynolds number
		Re_c = v_c * d_inj * self.coolant.rho / self.coolant.mu

		# calcualte entrainment factor E
		We = rho_g * v_g**2 * d / self.coolant.sigma * ((self.coolant.rho - rho_g)/rho_g)**0.25
		a  = 2.31e-4 * Re_c**(-0.35)

		Re_c_film = 250 * np.log(Re_c) - 1265
		Em = 1 - Re_c_film / Re_c
		E = Em * np.tanh(a * We**1.25)

		# liquid mass flow accounting for loss of entrained flwo
		return m_dot_c * (1 - E)


	def radiation(self, idx):
		# simple radiation model based on h2o and co2 emissions
		R_c = self.geometry[idx,1]					# chamber radius

		p_h2o = self.cea.mole_fractions['H2O'][0] * self.gas.p_s[idx]
		# radiative heat flux of water molecules
		q_rad = 5.74 * (p_h2o / 1e5 * R_c)**0.3 * (self.gas.T_s[idx]/100)**3.5

		# check if CO2 is present in the exhaust
		if 'CO2' in self.cea.mole_fractions:
			p_co2 = self.cea.mole_fractions['CO2'][0] * self.gas.p_s[idx]
			# radiative heat flux of co2 molecules
			q_rad += 4 * (p_co2/1e5 * R_c)**0.3 * (self.gas.T_s[idx]/100)**3.5

		return q_rad


	def stanton_number(self, idx):
		# Stanton number correction and evaporation rate of the liquid film at a point of the contour
		d, rho_g, v_g, Re_g = self.gas_flow(idx)
		G_m   = rho_g * (v_g - self.v_c[idx])
		q_rad = self.radiation(idx)

		# gaseous films from further upstream lower the gas temperature at the wall
		T_g = self.gas.T_aw[idx] - self.eta[idx] * (self.gas.T_aw[idx] - self.T_film[idx])

		# darcy friction factor
		func = lambda f: 1.93 * np.log(Re_g * np.sqrt(f)) - 0.537 - 1 / (np.sqrt(f))
		fr = optimize.newton(func, 0.001)

		# Unmodified stanton number
		St = 0.5 * fr * (1.2 + 11.8 * np.sqrt(0.5*fr) * (self.cea.Pr - 1) * (self.cea.Pr**(-1/3)))**(-1)
		h_alpha = St * G_m * self.cea.Cp * self.K_t
		F_St = self.cea.Cp / self.dH_fg_star[idx] * ((T_g - self.T_sat[idx]) + q_rad / h_alpha)

		# Stanton number correction
		k_m = (self.cea.MW / self.coolant.MW)**0.6
		St_St0 = np.log(1 + F_St * k_m) / (F_St * k_m)

		# coolant evaporation rate per wall area
		h_alpha_film = St * St_St0 * G_m * self.cea.Cp * self.K_t
		m_v = (q_rad + h_alpha_film * (T_g - self.T_sat[idx])) / self.dH_fg_star[idx]

		return St_St0, m_v


	def calculate(self):
		# Marches along the wall from the injector to the nozzle exit. The coolant of a ring of ports forms a liquid film, which evaporates
		# with the local conditions of the combustion gas and continues as a gaseous film from where the wall falls dry.
		# Coolant injected into a liquid film adds to it
		x  = self.geometry[:,0]
		r  = self.geometry[:,1]
		ds = np.sqrt(np.diff(x)**2 + np.diff(r)**2)
		s  = np.append(0, np.cumsum(ds))						# distance along the wall from the injector face

		self.St_St0 = np.ones(len(x))							# Stanton number correction under a liquid film, 1.0 where the wall is dry
		self.eta    = np.zeros(len(x))							# effectiveness of the gaseous films
		self.liquid = np.zeros(len(x), dtype=bool)				# points of the contour where the wall is covered by a liquid film
		self.T_film = np.copy(self.T_sat)						# coolant temperature at the wall: boiling liquid film, or its vapour as it left the liquid film
		self.x_dry  = [x[-1]] * len(self.ports)					# end of the liquid film of each ring of ports

		m_dot_l = 0.0											# liquid mass flow on the wall
		m_dot_v = 0.0											# coolant mass flow of the liquid film, without the liquid lost by entrainment
		wet     = []											# rings of ports which feed the liquid film

		for i in range(len(x)):
			for j, (idx, m_dot_c, v_c, d_inj) in enumerate(self.ports):
				if idx == i:
					gamma    = self.coolant_flow(i, m_dot_c, v_c, d_inj)
					m_dot_l += gamma
					m_dot_v += gamma
					wet.append(j)

			if m_dot_l == 0.0:
				continue

			self.liquid[i] = True
			self.T_film[i] = self.T_sat[i]
			self.St_St0[i], m_v = self.stanton_number(i)

			# liquid film reaches the nozzle exit
			if i == len(x) - 1:
				break

			# coolant evaporated up to the next point of the contour
			m_v_next   = self.stanton_number(i + 1)[1]
			m_dot_evap = np.pi * (m_v * r[i] + m_v_next * r[i+1]) * ds[i]

			if m_dot_evap < m_dot_l:
				m_dot_l -= m_dot_evap
			else:
				# the wall falls dry before the next point
				s_dry = s[i] + ds[i] * m_dot_l / m_dot_evap
				for j in wet:
					self.x_dry[j] = np.interp(s_dry, s, x)

				# gaseous films of several rings are combined as proposed by Sellers: each film cools the gas left at the wall by the films upstream
				self.eta = 1 - (1 - self.eta) * (1 - self.gas_film(s, r, s_dry, m_dot_v, self.m_dot_g[i], self.T_sat[i]))
				self.T_film[i+1:] = self.T_sat[i]
				m_dot_l, m_dot_v, wet = 0.0, 0.0, []


	def gas_film(self, s, r, s_dry, m_dot_v, m_dot_g, T_v):
		# Effectiveness of the gaseous film downstream of the liquid film, where the evaporated coolant mixes with the combustion gas.
		# Turbulent boundary layer model of Librizzi and Cresci (see Goldstein, Film Cooling, 1971): the boundary layer starts with the
		# mass flow of the coolant vapour and grows by entrainment of combustion gas. The mixing is increased by the same turbulence
		# factor as the evaporation of the liquid film. Reactions between the coolant and the combustion gas are not considered
		eta = np.zeros(len(s))

		# combustion gas mass flow passing over the film per coolant mass flow, integrated along the wall from the end of the liquid film
		swept = 2 * m_dot_g / m_dot_v * np.append(0, np.cumsum(np.diff(s) * 0.5 * (1 / r[1:] + 1 / r[:-1])))
		swept = swept - np.interp(s_dry, s, swept)

		gas = swept > 0
		xi  = self.K_t * swept[gas] * (m_dot_v / (2 * np.pi * r[gas] * self.cea.mu))**(-0.25)

		eta[gas] = 1 / (1 + self.cea.Cp / self.coolant.Cp_vapour(T_v) * (0.329 * (4.01 + xi)**0.8 - 1))

		return eta


	def output_msg(self):
		for (idx, m_dot_c, v_c, d_inj), x_dry in zip(self.ports, self.x_dry):
			print('Film cooling ports at x = ', round(self.geometry[idx,0] * 1e3, 1), ' [mm], liquid film ends at x = ', round(x_dry * 1e3, 1), ' [mm]')
		if max(self.x_dry, default=-np.inf) > self.geometry[np.argmin(self.geometry[:,1]), 0]:
			print('WARNING: the liquid film reaches the throat. Break up of the film by the accelerating gas is not modelled, wall temperatures under it can be much higher')
		print('')
