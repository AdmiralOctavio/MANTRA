#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Creator:  Joanthan Neeser                                         #
# Date:     15.12.2022                                              #
# Version:  2.3  													#
# License:	GNU GENERAL PUBLIC LICENSE V3							#                                          
#####################################################################

from scipy import interpolate
import numpy as np
from matplotlib import pyplot as plt


class Material():
	def __init__(self, name, alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness, sig_y=None):
		self.name =	name			# str of material name
		self.alpha = alpha			# thermal diffusivity [m^2/s]
		self.k = k					# thermal conductivity [W/m/K]
		self.rho = rho				# density [kg/m^3]
		self.Cp = Cp				# specific heat [J/kg/K]
		self.v = v 					# poiosson ratio
		self.E = E					# youngs modulus [Pa]
		self.a = a					# thermal expasion coefficinent [1/K]
		self.eps = eps				# Thermal emissivity 
		self.sig_u = sig_u			# Ultimate strength [Pa]
		self.roughness = roughness	# effective roughness height [m]
		self.sig_y = sig_y			# Yield strength (0.2% offset) [Pa], None if not specified (no wall stress analysis)

	def thermal_conductivity(self, k_arr, T_arr):
		self.k = interpolate.interp1d(T_arr, k_arr, kind='linear', fill_value='extrapolate')

	def temperature_dependent(self, name, arr, T_arr):
		# sets the property 'name' (e.g. 'E', 'v', 'a', 'sig_y', 'sig_u') as a function of temperature [K], constant outside of the range of the data
		setattr(self, name, interpolate.interp1d(T_arr, arr, kind='linear', bounds_error=False, fill_value=(arr[0], arr[-1])))

	def value(self, name, T):
		# property 'name' at the temperature T [K], for properties which are either a constant or a function of temperature
		prop = getattr(self, name)
		return prop(T) if callable(prop) else prop

	def plot(self, material_property, label):
		T_range = np.linspace(288, 1000, 100)
		plt.plot(T_range, material_property(T_range))
		plt.xlabel('temperature [K]')
		plt.ylabel(label)
		plt.title(self.name)
		plt.show()


# Ti-6Al-4V at room temperature
k = 6.7							# thermal conductivity [W/m/K]
Cp = 930						# specific heat [J/kg/K] at 870 C
rho = 4430						# density [kg/m^3]
v = 0.342                       # poiosson ratio
E = 114e9						# youngs modulus [Pa]
a = 9.7e-6						# thermal expasion coefficinent [1/K]
sig_u = 550e6                   # ultimate strength [Pa]
eps = 0.8						# thermal emissivity
roughness = 2e-5				# effective roughness height [m] from Materialise
alpha = k / rho / Cp			# thermal diffusivity [m^2/s]
Ti6Al4V = Material('Ti-6Al-4V', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness)

# set variable material properties from https://www.researchgate.net/publication/299647114_Developments_in_cutting_tool_technology_in_improving_machinability_of_Ti6Al4V_alloy_A_review
Ti6Al4V.thermal_conductivity(np.array([6.7, 9, 12, 15, 18]), np.array([283, 477, 700, 922, 1144]))


# IN718, L-PBF, solution annealed at 954 C and aged (718 C / 8 h, furnace cool to 621 C, 18 h in total) as in AMS 5662
k = 17.9					    # thermal conductivity [W/m/K] at 400 C
Cp = 501					    # specific heat [J/kg/K] at 400 C, VDM Alloy 718 data sheet
rho = 8220				        # density [kg/m^3], wrought and aged (Special Metals), EOS gives a minimum of 8150 for L-PBF parts
v = 0.294                      	# poiosson ratio at room temperature
E = 200e9						# youngs modulus [Pa] at room temperature
a = 13.1e-6						# thermal expasion coefficinent [1/K], mean value from 25 to 100 C
sig_u = 1375e6             		# ultimate strength [Pa] at room temperature
sig_y = 1145e6             		# yield strength [Pa] at room temperature
eps = 0.8						# thermal emissivity
roughness = 5e-5				# effective roughness height [m] from Materialize
alpha = k / rho / Cp			# thermal diffusivity [m^2/s]
IN718 = Material('IN718', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness, sig_y)

# set vairable material properties for IN718
# thermal conductivity of annealed and aged material from the Special Metals INCONEL alloy 718 bulletin (SMC-045), table 5
IN718.thermal_conductivity(np.array([11.4, 12.5, 14.4, 16.2, 17.9, 19.6, 21.3, 23.2, 25.0, 26.8, 28.7]), np.array([294, 366, 478, 589, 700, 811, 922, 1033, 1144, 1255, 1366]))
# dynamic youngs modulus and poisson ratio of annealed and aged bar from SMC-045, table 4. Wrought material, L-PBF parts can be less stiff along the build direction
IN718.temperature_dependent('E', np.array([199.9, 195.8, 190.3, 184.1, 177.9, 171.0, 163.4, 153.8, 139.3, 120.0])*1e9, np.array([294, 366, 478, 589, 700, 811, 922, 1033, 1144, 1255]))
IN718.temperature_dependent('v', np.array([0.294, 0.288, 0.280, 0.272, 0.271, 0.271, 0.283, 0.306, 0.331, 0.341]), np.array([294, 366, 478, 589, 700, 811, 922, 1033, 1144, 1255]))
# mean (secant) thermal expansion coefficient from 25 C to the temperature, measured on L-PBF parts, EOS NickelAlloy IN718 data sheet
IN718.temperature_dependent('a', np.array([13.1, 13.7, 14.1, 14.4, 14.7, 15.0, 15.5])*1e-6, np.array([373, 473, 573, 673, 773, 873, 973]))
# ESTIMATE: room temperature strength of vertically built L-PBF parts (EOS data sheet, M290, 40 um) scaled with the temperature dependence
# of wrought plate with the same aging (Haynes 718 brochure). Short time tensile values, the strength drops with long exposure above about 920 K
IN718.temperature_dependent('sig_y', np.array([1145, 1016, 996, 955, 715, 234, 65])*1e6, np.array([298, 700, 811, 922, 1033, 1144, 1255]))
IN718.temperature_dependent('sig_u', np.array([1375, 1187, 1167, 1114, 805, 290, 97])*1e6, np.array([298, 700, 811, 922, 1033, 1144, 1255]))

# CuCr1Zr 
k = 310							# thermal conductivity [W/m/K] at 400 C
Cp = 520					    # specific heat [J/kg/K] at 400 C
rho = 8900						# density [kg/m^3]
v = 0.34                       	# poiosson ratio at 400 C
E = 110e9							# youngs modulus [Pa] at 400 C
a = 17e-6							# thermal expasion coefficinent [1/K] at 400 C
sig_u = 140e6                  		# ultimate strength [Pa] at 400 C
eps = 0.8						# thermal emissivity
roughness = 0.5e-5				# effective roughness height [m] from SLM Solutions
alpha = k / rho / Cp			# thermal diffusivity [m^2/s]
CuCr1Zr = Material('CuCr1Zr', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness)

# set variable material properties for CuCr1Zr from 'Thermal Fatigue testing of CuCrZr allow for high temperature tooling applications' by Y. Birol
CuCr1Zr.thermal_conductivity(np.array([290, 292, 300, 302, 305, 310, 315, 320, 330]), np.array([273, 373, 473, 573, 673, 773, 873, 973, 1073]))

# GRCop-42 (L-PBF + HIP)
k = 320							# thermal conductivity [W/m/K] at 400 C, Chen et al. 2023 fit (multi-vendor L-PBF)
Cp = 424						# specific heat [J/kg/K] at 400 C, Chen et al. 2023 (NIST mixture estimate, not measured)
rho = 8790						# density [kg/m^3] at RT, Velo3D datasheet
v = 0.34						# poisson ratio, assumed same as Cu, no GRCop-42 data found
E = 110e9						# youngs modulus [Pa] at 400 C, ESTIMATE: RT ~121-130 GPa (DED study), scaled like Cu
a = 17.0e-6						# thermal expansion coefficient [1/K], secant 20-400 C, Chen et al. 2023
sig_u = 200e6					# ultimate strength [Pa] at 400 C, ESTIMATE, see notes
eps = 0.8						# thermal emissivity, same assumption as CuCr1Zr
roughness = 1.0e-5				# roughness [m], Ra 8-10 um as-printed, 3D Systems LT60
alpha = k / rho / Cp			# thermal diffusivity [m^2/s]
sig_y = 123e6					# yield strength [Pa] at 400 C, ESTIMATE, see below
GRCop42 = Material('GRCop-42', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness, sig_y)
GRCop42.thermal_conductivity(np.array([329, 328, 326, 324, 320, 314, 307, 297, 286]), np.array([273, 373, 473, 573, 673, 773, 873, 973, 1073]))
# ESTIMATE: no modulus over temperature found for GRCop-42. 125 GPa at room temperature (DED study, tensile tests of L-PBF parts give about 100 GPa)
# with the -40 MPa/K of pure copper. The poisson ratio stays constant
GRCop42.temperature_dependent('E', np.array([125, 117, 109, 101, 94])*1e9, np.array([300, 500, 700, 900, 1073]))
# mean (secant) thermal expansion coefficient from 25 C to the temperature: 17.0e-6 up to 400 C measured on L-PBF parts (Chen et al. 2023),
# other temperatures scaled with the expansion of wrought GRCop-42, read from figure 5 of Gradl et al., AIAA-2019-4228
GRCop42.temperature_dependent('a', np.array([16.6, 17.0, 17.3, 17.8])*1e-6, np.array([473, 673, 873, 1073]))
# ESTIMATE: room temperature strength of L-PBF + HIP parts (173 and 359 MPa, AIAA-2019-4228, table 3) scaled with the temperature dependence
# of wrought GRCop-42, read from figures 6 and 7 of the same paper
GRCop42.temperature_dependent('sig_y', np.array([173, 147, 123, 108, 87, 59, 28])*1e6, np.array([298, 473, 673, 773, 873, 973, 1073]))
GRCop42.temperature_dependent('sig_u', np.array([359, 264, 174, 136, 106, 75, 51])*1e6, np.array([298, 473, 673, 773, 873, 973, 1073]))

# SS 316L
k = 21							# Lowk asked chatgpt for this
Cp = 750
rho = 7580

k = 30							# Thermal conductivity [W/m/K] at 500 C -> Rises at higher temps
Cp = 750 						# Specific heat capacity [J/kg/K] at 500 C -> Rises at higher temps
rho = 7580 						# Density [kg/m^3] at 500 C -> Decreases slightly at higher temps
v = 1
E = 1
a = 1
sig_u = 1
eps = 0.8
roughness = 5e-5
alpha = k / rho / Cp

SS316L = Material('SS316L', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness)
SS316L.thermal_conductivity(np.array([13.8, 14.6, 15.8, 17.1, 18.6, 20.1, 21.6, 23.1, 24.6, 26.1, 27.6, 29.1, 30.6, 32.0, 33.4, 34.8, 36.2, 37.5, 38.7, 39.9, 41.0, 42.0, 42.9, 43.7, 44.4, 45.0]), np.array([
    270, 300, 350, 400, 450, 500, 550, 600, 650, 700,
    750, 800, 850, 900, 950, 1000, 1050, 1100, 1150,
    1200, 1250, 1300, 1350, 1400, 1450, 1500
]))

roughness = 5e-5				# Effective roughness height [m] from SLM Solutions - 5e-5 - 1e-4 range for 3D print.
alpha = k / rho / Cp
SS316L = Material('SS316L', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness)
# Variable material properties from chatgpt because I am very lazy and this engine will melt anyway
SS316L.thermal_conductivity(np.array([13.8, 14.6, 15.8, 17.1, 18.6, 20.1, 21.6, 23.1, 24.6, 26.1,27.6, 29.1, 30.6, 32.0, 33.4, 34.8, 36.2, 37.5, 38.7,39.9, 41.0, 42.0, 42.9, 43.7, 44.4, 45.0]), np.array([270, 300, 350, 400, 450, 500, 550, 600, 650, 700,750, 800, 850, 900, 950, 1000, 1050, 1100, 1150,1200, 1250, 1300, 1350, 1400, 1450, 1500]))

# SS 1.4404 
k = 23					        # thermal conductivity [W/m/K] at 500 C
Cp = 590					    # specific heat [J/kg/K] at 500 C
rho = 7750						# density [kg/m^3] at 500 C
v = 1                       	# poiosson ratio
E = 1							# youngs modulus [Pa]
a = 1							# thermal expasion coefficinent [1/K]
sig_u = 1                  		# ultimate strength [Pa]
eps = 0.8						# thermal emissivity
roughness = 0.9e-5				# effective roughness height [m] from Materialize
alpha = k / rho / Cp			# thermal diffusivity [m^2/s]
SS14404 = Material('SS14404', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness)
# variable material properties from 'Transient thermo-mechanical modeling of stress evolution and re-melt volume fraction in electron beam additive manufacturing process' by R.K. Adhitan
SS14404.thermal_conductivity(np.array([13.5, 16, 17.5, 19.5, 22, 23.5, 24.5, 25.5, 27, 28, 29]), np.array([273, 373, 473, 573, 673, 773, 873, 973, 1073, 1173, 1273]))


# AlSi10Mg 
k = 140					        # thermal conductivity [W/m/K] at 20 C
Cp = 730					    # specific heat [J/kg/K] at 20 C
rho = 2680						# density [kg/m^3] at 20 C
v = 1                       	# poiosson ratio
E = 1							# youngs modulus [Pa]
a = 1							# thermal expasion coefficinent [1/K]
sig_u = 1                  		# ultimate strength [Pa]
eps = 0.8						# thermal emissivity
roughness = 5e-5				# effective roughness height [m], estimate
alpha = k / rho / Cp			# thermal diffusivity [m^2/s]
AlSi10Mg = Material('AlSi10Mg', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness)
# variable material properties from https://backend.orbit.dtu.dk/ws/portalfiles/portal/222710402/Thermal_properties_JMEP_postprint.pdf
# assuming heat treated and 99.5% theoretical density
AlSi10Mg.thermal_conductivity(np.array([140, 144, 149]), np.array([25, 200, 400])+273.15)



# all materials of the library by name, for the choice in the design file and the desktop app
MATERIALS = {m.name: m for m in (Ti6Al4V, IN718, CuCr1Zr, GRCop42, SS316L, SS14404, AlSi10Mg)}
