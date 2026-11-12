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

from .creep import LarsonMiller
from .ratchet import NortonCreep, FatigueCurve


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
		self.creep = None			# creep rupture as a LarsonMiller curve, None if not specified (no creep rupture screening)
		self.norton = None			# minimum creep rate as a NortonCreep law, None if not specified (no ratcheting and cyclic life)
		self.fatigue = None			# strain controlled fatigue life as a FatigueCurve, None if not specified (no ratcheting and cyclic life)

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
# creep rupture: typical stress rupture strength of wrought bar, annealed at 982 C and aged at 718 / 621 C, for 100 h and 1000 h at 593, 649, 704
# and 760 C (Rolled Alloys, alloy 718 bulletin 1718USe), as a Larson-Miller curve with C = 20 (fits as well as the best C of 22).
# ESTIMATE: 0.9 times the stress for L-PBF parts. Solution annealed and aged L-PBF 718 reaches about the rupture life of wrought material at
# 650 C, with more scatter, lower creep ductility and much lower notch rupture life; as built or directly aged parts are weaker
IN718.creep = LarsonMiller(20, [19063, 19929, 20285, 21207, 21507, 22485, 22729, 23762], np.array([1172, 896, 758, 586, 517, 379, 303, 172])*1e6,
                           factor=0.9, T_range=(866, 1033), source='wrought IN718 bar, 593 to 760 C, 100 and 1000 h (Rolled Alloys)')
# minimum creep rate: steady state creep rates of wrought IN718 (aged 760 / 650 C, heat treatment A, which meets the commercial tensile
# requirements) at 650, 704 and 760 C, table III of R.W. Hayes, Creep deformation of Inconel alloy 718 in the 650 C to 760 C temperature
# regime, Superalloys 718, 625 and various derivatives (TMS 1991) 549-562. No creep rate data of printed IN718 were found
IN718.norton = NortonCreep({923.15:  (np.array([551, 620, 689, 724])*1e6, np.array([1.3e-6, 3.0e-6, 1.39e-5, 4.4e-5]) / 3600),
                            977.15:  (np.array([483, 517, 551, 620])*1e6, np.array([7.5e-6, 1.4e-5, 1.64e-4, 2.93e-4]) / 3600),
                            1033.15: (np.array([276, 345, 483])*1e6,      np.array([1.8e-6, 1.42e-5, 8.0e-4]) / 3600)},
                           source='wrought IN718, 650 to 760 C, 276 to 724 MPa (Hayes, Superalloys 1991)')
# fatigue: Manson-Coffin-Basquin fits of strain controlled tests (R = -1, 0.33 Hz) of wrought IN718 at 360, 550 and 650 C, table IV of
# J.Z. Xie, Low cycle fatigue and fatigue crack growth behaviors of alloy IN718, Superalloys 718, 625 and various derivatives (TMS 1991)
# 491-500: strain amplitude = sig_f / E (2 N)^b + eps_f (2 N)^c, checked against the test points of table III. E from the library
IN718.fatigue = FatigueCurve({T: (lambda N, s=s, b=b, e=e, c=c, E=float(IN718.value('E', T)): 2 * (s / E * (2 * N)**b + e * (2 * N)**c))
                              for T, s, b, e, c in [(633.15, 1630e6, -0.0651, 1.56, -0.8248), (823.15, 1546e6, -0.0729, 0.731, -0.7408),
                                                    (923.15, 1476e6, -0.0840, 0.184, -0.6047)]},
                             N_range=(6, 34270), source='wrought IN718, 360 to 650 C, 6 to 34000 cycles (Xie, Superalloys 1991)')

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
# creep rupture: ITER grade CuCrZr (cold worked, solution annealed and aged sheet) at 500 C, fit of the stress against the rupture time from
# 147 MPa / 4.7 h to 87 MPa / 530 h, read from figure 8a of Wang et al., Mater. Sci. Eng. A 2020 (ORNL, OSTI 1606845). ESTIMATE: the data
# are of one temperature, C = 20 is assumed. CuCrZr overages and softens above about 400 C, so the curve can not be carried over to other
# temperatures with confidence. Creep at 500 C is grain boundary sliding with a threshold stress of about 80 MPa. ESTIMATE: 0.9 times the
# stress for L-PBF parts, no rupture data of printed CuCrZr was found
CuCr1Zr.creep = LarsonMiller(20, [15983, 17569], np.array([147, 87])*1e6, factor=0.9, T_range=(773, 773),
                             source='ITER grade CuCrZr sheet, 500 C only, 4.7 to 530 h (Wang et al. 2020, ORNL)')
# yield and ultimate strength: average fits of solution annealed and aged (SAA) CuCrZr from 20 to 700 C, eqs. 3 and 5 of K. Zhang, E.
# Gaganidze, M. Gorley, Development of the material property handbook and database of CuCrZr, Fusion Eng. Des. (KIT / IPP / UKAEA):
# YS = -2.2847e-4 T^2 - 0.13931 T + 292.19 [MPa], UTS = -0.42631 T + 413.45 [MPa], T in C. Wrought material, aged L-PBF parts are similar
T_C = np.array([20, 100, 200, 300, 400, 500, 600, 700])
CuCr1Zr.temperature_dependent('sig_y', (-2.2847e-4 * T_C**2 - 0.13931 * T_C + 292.19)*1e6, T_C + 273.15)
CuCr1Zr.temperature_dependent('sig_u', (-0.42631 * T_C + 413.45)*1e6, T_C + 273.15)
# minimum creep rate: steady creep laws rate = A sig^n exp(-197 kJ/mol / R T) of table II of G. Li, B.G. Thomas, J.F. Stubbins, Modeling
# creep and fatigue of copper alloys, Metall. Mater. Trans. A 31 (2000) 2491: Cu-0.65Cr-0.1Zr at 216 C (A = 2.82e-22, n = 14, 183 to
# 282 MPa) and Cu-0.45Cr-0.19Zr at 300 C (Gorynin, A = 1.80e-2, n = 5.3, 110 to 213 MPa, the faster of the two 300 C laws where they
# overlap), as points at the ends of their stress ranges, and the minimum creep rates of ITER grade CuCrZr at 500 C read from figure 8b of
# Wang et al., Mater. Sci. Eng. A 2020 (ORNL). The lots differ in heat treatment, so the temperature dependence between them is uncertain
CuCr1Zr.norton = NortonCreep({489.15: (np.array([183, 282])*1e6, [1.22e-11, 5.2e-9]),
                              573.15: (np.array([110, 213])*1e6, [1.32e-9, 4.38e-8]),
                              773.15: (np.array([90, 110, 125])*1e6, [8.0e-10, 3.9e-9, 1.5e-8])},
                             source='CuCrZr, 216 to 500 C, 90 to 282 MPa (Li, Thomas, Stubbins 2000; Wang et al. 2020)')
# fatigue: Coffin-Manson fit of strain controlled tests of SAA CuCrZr from room temperature to 500 C (about 300 to 2e5 cycles), eq. 7 of
# Zhang et al. (handbook above): strain amplitude = 3.5286 N^-0.26199 [%]. The 500 C tests lie below the fit by a factor of 2 to 3 in life,
# so lives above 400 C are flagged as extrapolated
CuCr1Zr.fatigue = FatigueCurve({573.15: lambda N: 2 * 3.5286e-2 * N**-0.26199}, N_range=(300, 2e5), T_range=(293, 673),
                               source='SAA CuCrZr, RT to 400 C, 300 to 2e5 cycles (Zhang et al., CuCrZr handbook)')

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
# creep rupture: creep lives of extruded GRCop-42 at 500, 650 and 800 C, read from the vector data of figure 11 of Gradl et al., AIAA-2019-4228
# (10 to 130 MPa, 2.5 to 850 h). The three temperatures fall on one Larson-Miller curve with C = 15.5 (rms 0.003 in log(stress)), the
# points are of a quadratic fit. ESTIMATE: 0.9 times the stress for L-PBF + HIP parts, no rupture data of printed GRCop-42 was found.
# The creep of the GRCop alloys is governed by the copper matrix, porosity of 1 to 2 % lowered the creep strength of a failed printed chamber
GRCop42.creep = LarsonMiller(15.5, [12350, 13000, 14000, 15000, 16000, 17000, 18000, 19000, 19780], np.array([130.8, 105.2, 75.1, 53.4, 37.8, 26.7, 18.8, 13.1, 9.9])*1e6,
                             factor=0.9, T_range=(773, 1073), source='extruded GRCop-42, 500 to 800 C, 2.5 to 850 h (Gradl et al., AIAA-2019-4228)')
# minimum creep rate: creep rate lines of extruded GRCop-42 at 500, 650 and 800 C, read from the vector data of figure 10 of the same paper
# (ends of the lines, stress exponents 11.6, 8.9 and 6.1)
GRCop42.norton = NortonCreep({773.15:  (np.array([75.8, 130.0])*1e6, [2.26e-8, 1.16e-5]),
                              923.15:  (np.array([35.0, 60.3])*1e6,  [8.05e-8, 1.03e-5]),
                              1073.15: (np.array([10.0, 21.8])*1e6,  [1.74e-8, 1.97e-6])},
                             source='extruded GRCop-42, 500 to 800 C, 10 to 130 MPa (Gradl et al., AIAA-2019-4228)')
# fatigue: strain controlled tests (R = -1) of wrought GRCop-42 pooled from room temperature to 600 C (no significant temperature effect),
# line of figure 2 of the same paper read from its vector data: total strain range 1.965 % at 588 cycles to 0.603 % at 20500 cycles.
# Below 0.7 % the specimens normally did not fail
GRCop42.fatigue = FatigueCurve({673.15: lambda N: 0.01965 * (N / 588)**-0.3324}, N_range=(588, 20528), T_range=(293, 873),
                               source='wrought GRCop-42, RT to 600 C, 600 to 20500 cycles (Gradl et al., AIAA-2019-4228)')

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
# creep rupture: L-PBF 316L (as built) at 550, 600 and 650 C, 175 to 300 MPa, Larson-Miller curve with C = 17 as in Wang et al., J. Nucl.
# Mater. 2021 (ORNL, OSTI 1764454), fitted to the points of their figure 5. Printed 316L ruptures earlier than wrought 316 SS
SS316L_creep = LarsonMiller(17, [19000, 21000], np.array([294, 176])*1e6, T_range=(823, 923),
                            source='L-PBF 316L, 550 to 650 C, 175 to 300 MPa (Wang et al. 2021, ORNL)')
SS316L.creep = SS316L_creep

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
SS14404.creep = SS316L_creep		# 1.4404 is the EN number of 316L

# mechanical properties, creep rates and fatigue of 316L, for SS316L and SS14404 alike
SS316L_creep_rate = NortonCreep(
    # minimum creep rates of L-PBF 316L (as built) at 550, 600 and 650 C, read from the vector data of figure 6 of Wang et al. 2021 (ORNL, as above)
    {823.15: (np.array([250, 275, 275, 300])*1e6, [6.29e-9, 3.49e-8, 3.12e-8, 1.72e-7]),
     873.15: (np.array([200, 225, 250])*1e6, [1.15e-8, 4.79e-8, 2.40e-7]),
     923.15: (np.array([175, 175, 200, 200, 225, 225])*1e6, [6.53e-8, 6.73e-8, 2.64e-7, 2.58e-7, 1.24e-6, 1.41e-6])},
    source='L-PBF 316L, 550 to 650 C, 175 to 300 MPa (Wang et al. 2021, ORNL)')
# fatigue: best fit curve of austenitic stainless steels in air of NUREG/CR-6909 (Chopra, Argonne, for the US NRC): ln(N) = 6.891 - 1.920
# ln(eps_a - 0.112) with the strain amplitude eps_a in %. Wrought material, data mostly from room temperature to about 400 C: higher
# temperatures are flagged as extrapolated. Rough as built surfaces and porosity of printed parts lower the life further
SS316L_fatigue = FatigueCurve({573.15: lambda N: 2 * (0.112 + np.exp((6.891 - np.log(N)) / 1.920)) / 100}, N_range=(10, 1e6), T_range=(293, 673),
                              source='wrought austenitic stainless steels in air, RT to 400 C (NUREG/CR-6909)')
for m in (SS316L, SS14404):
    # modulus and mean thermal expansion from 20 C of 1.4404 from EN 10088-1 (reference data up to 500 C). ESTIMATE: poisson ratio 0.3
    m.v = 0.3
    m.temperature_dependent('E', np.array([200, 194, 186, 179, 172, 165])*1e9, np.array([20, 100, 200, 300, 400, 500]) + 273.15)
    m.temperature_dependent('a', np.array([16.0, 16.0, 16.5, 17.0, 17.5, 18.0])*1e-6, np.array([20, 100, 200, 300, 400, 500]) + 273.15)
    # yield and ultimate strength of as built L-PBF 316L along the build direction from 20 to 700 C, read from the vector data of figure 7
    # of Dryepondt et al., Microstructure and high temperature tensile properties of 316L fabricated by laser powder-bed fusion, Addit.
    # Manuf. 2021 (ORNL, OSTI 1817598). Stress relief above about 600 C lowers the yield strength
    m.temperature_dependent('sig_y', np.array([424, 372, 331, 280, 238])*1e6, np.array([20, 200, 400, 600, 700]) + 273.15)
    m.temperature_dependent('sig_u', np.array([614, 448, 407, 357, 277])*1e6, np.array([20, 200, 400, 600, 700]) + 273.15)
    m.norton = SS316L_creep_rate
    m.fatigue = SS316L_fatigue


# AlSi10Mg, L-PBF, stress relieved. As built AlSi10Mg overages within minutes above about 250 C, so a hot wall ends up in a
# softened condition close to this one whatever the delivery state
k = 140					        # thermal conductivity [W/m/K] at 20 C
Cp = 730					    # specific heat [J/kg/K] at 20 C
rho = 2680						# density [kg/m^3] at 20 C, EOS gives a minimum of 2670 for L-PBF parts
v = 0.33                       	# poiosson ratio, ESTIMATE: usual value of aluminium alloys, no AlSi10Mg data found
E = 72e9						# youngs modulus [Pa] at room temperature, Lehmhus et al. 2022 (see below)
a = 20e-6						# thermal expasion coefficinent [1/K], mean value from 25 to 100 C, EOS data sheet
sig_u = 280e6                  	# ultimate strength [Pa] at room temperature, Lehmhus et al. 2022
sig_y = 166e6                  	# yield strength [Pa] at room temperature, Lehmhus et al. 2022
eps = 0.8						# thermal emissivity
roughness = 5e-5				# effective roughness height [m], estimate
alpha = k / rho / Cp			# thermal diffusivity [m^2/s]
AlSi10Mg = Material('AlSi10Mg', alpha, k, rho, Cp, v, E, a, eps, sig_u, roughness, sig_y)
# variable material properties from https://backend.orbit.dtu.dk/ws/portalfiles/portal/222710402/Thermal_properties_JMEP_postprint.pdf
# assuming heat treated and 99.5% theoretical density. EOS gives 155 to 165 W/m/K after stress relief or T6, 100 to 110 as built
AlSi10Mg.thermal_conductivity(np.array([140, 144, 149]), np.array([25, 200, 400])+273.15)
# mean (secant) thermal expansion coefficient from 25 C to the temperature, ASTM E228, EOS Aluminium AlSi10Mg data sheet (EOS M 290, 30 um)
AlSi10Mg.temperature_dependent('a', np.array([20, 22, 27])*1e-6, np.array([100, 200, 300]) + 273.15)
# tensile properties of L-PBF AlSi10Mg (EOS M290, 60 um, build platform at 200 C, stress relieved 2 h at 350 C on the platform, as built
# surface) tested at RT, 125, 250 and 450 C, vertically built samples (polar angle 0), table A2 of D. Lehmhus et al., High-temperature
# mechanical properties of stress-relieved AlSi10Mg produced via laser powder bed fusion additive manufacturing, Materials 15 (2022) 7386.
# Horizontally built samples have about 12 % less yield strength at RT and the same from 125 C on. Short time tests (strain rate 1e-3 1/s,
# 20 min soak): the strength falls steeply between 250 and 450 C, and longer exposure above about 200 C lowers it further
AlSi10Mg.temperature_dependent('sig_y', np.array([165.9, 155.0, 133.0, 32.5])*1e6, np.array([20, 125, 250, 450]) + 273.15)
AlSi10Mg.temperature_dependent('sig_u', np.array([280.2, 249.7, 162.8, 34.4])*1e6, np.array([20, 125, 250, 450]) + 273.15)
# youngs modulus from the same tensile tests (no value at 450 C). ESTIMATE: quasi static moduli read from tensile curves fall faster with
# temperature than the dynamic modulus, so the thermal stresses at 250 C may be somewhat underestimated
AlSi10Mg.temperature_dependent('E', np.array([71.9, 70.4, 55.7])*1e9, np.array([20, 125, 250]) + 273.15)
# creep rupture: constant load creep tests of as deposited L-PBF AlSi10Mg (SLM500, 50 um, built along the load) at 150, 175, 205 and 225 C,
# 110 to 283 MPa, minimum creep rates read from figure 7 of C. Paoletti et al., Modelling the creep behavior of an AlSi10Mg alloy produced by
# additive manufacturing, Mater. Sci. Eng. A 799 (2021) 140138 (stress exponents 15 to 21). No rupture times are tabulated. ESTIMATE: rupture
# times from the Monkman-Grant product rate x t_r = 0.023 of the two complete creep curves of figure 6a (175 C, 170 and 200 MPa, 0.0230 and
# 0.0227), giving 0.04 to 780 h. The 22 points fall on one Larson-Miller curve with C = 25 (rms 0.016 in log(stress)), the points are of a
# quadratic fit. ESTIMATE: 0.85 times the stress for stress relieved parts: at 225 C AlSi10Mg stress relieved 2 h at 300 C (Uzan et al.,
# Addit. Manuf. 24 (2018) 257, figure 10 of Paoletti et al.) creeps at the rate of the as deposited alloy under 0.78 to 0.91 times the stress,
# assumed the same at the other temperatures. The as deposited alloy softens during the tests above about 150 C
AlSi10Mg.creep = LarsonMiller(25, [10120, 10700, 11290, 11880, 12470, 13060, 13650], np.array([289.7, 252.7, 217.9, 186.2, 157.6, 132.2, 109.9])*1e6,
                              factor=0.85, T_range=(423, 498), source='as deposited L-PBF AlSi10Mg, 150 to 225 C, 0.04 to 780 h (Paoletti et al. 2021)')
# minimum creep rate: one law rate = A sig^17.0 exp(-213 kJ/mol / R T) fitted to all 22 points of figure 7 of Paoletti et al. as above
# (rms 0.33 decades, the 150 C set alone scatters by a factor of 10), as points at the ends of the stresses of each test temperature. Fits of
# each temperature give exponents of 21, 16, 17 and 15, but the fall from 205 to 225 C is within the scatter and would turn the exponent
# negative when extrapolated to higher temperatures. Stresses times 0.85 for stress relieved parts (ESTIMATE, as for the rupture curve)
AlSi10Mg.norton = NortonCreep({423.15: (0.85 * np.array([200.0, 283.2])*1e6, [3.66e-8, 1.35e-5]),
                               448.15: (0.85 * np.array([150.3, 240.0])*1e6, [8.35e-9, 2.37e-5]),
                               478.15: (0.85 * np.array([125.1, 202.5])*1e6, [1.33e-8, 4.76e-5]),
                               498.15: (0.85 * np.array([110.0, 187.5])*1e6, [1.29e-8, 1.11e-4])},
                              source='as deposited L-PBF AlSi10Mg, 150 to 225 C, 110 to 283 MPa (Paoletti et al. 2021), x 0.85 stress')
# fatigue: strain controlled tests (R = -1, room temperature, machined and polished) of L-PBF AlSi10Mg (built vertically, 30 um) stress
# relieved 2 h at 300 C, strain amplitudes 0.1 to 1.5 %, figure 4b of R. Fernandes et al., Effect of post-processing heat treatment on cyclic
# plastic behaviour of AlSi10Mg aluminium alloy processed by LPBF, Procedia Struct. Integr. 42 (2022) 992. Coffin-Manson-Basquin fit with a
# two part plastic line, constants recovered from the vector data of the fitted lines: strain amplitude [%] = 0.6107 (2N)^-0.1199 + 3.7157
# (2N)^-0.2520 below 757 reversals, 111.45 (2N)^-0.7651 above. Within a factor of 1.3 of the test lives, except the longest test (2.2e6
# reversals, the fit gives 1.8 times its life). No elevated temperature data: all hot wall temperatures are flagged as extrapolated, and
# aluminium alloys soften cyclically and lose fatigue life above about 150 C
AlSi10Mg.fatigue = FatigueCurve({293.15: lambda N: 2 * (0.6107 * (2 * N)**-0.1199 + np.where(2 * N < 757, 3.7157 * (2 * N)**-0.2520, 111.45 * (2 * N)**-0.7651)) / 100},
                                N_range=(45, 1.12e6), T_range=(293, 293),
                                source='stress relieved L-PBF AlSi10Mg, RT only, 45 to 1.1e6 cycles (Fernandes et al. 2022)')



# all materials of the library by name, for the choice in the design file and the desktop app
MATERIALS = {m.name: m for m in (Ti6Al4V, IN718, CuCr1Zr, GRCop42, SS316L, SS14404, AlSi10Mg)}
