#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Comparison of the critical heat flux correlations used in         #
# RegenCooling.py with the ethanol tests of Meyer, Linne and Rousar #
#####################################################################

# Shows where the numbers quoted for the critical heat flux (CHF) methods come from: the scatter of 'meyer', the 44 % of 'gambill' and the
# factor 0.8 * dT_sub^0.25 / v^0.2 by which 'hall-mudawar' is divided for ethanol. None of these numbers is taken from the literature, they
# follow from evaluating the published correlations at the conditions of the published tests. Run with: python PyRocket-main/ValidateCHF.py
#
# Tests:        M. L. Meyer, D. L. Linne, D. C. Rousar, Forced Convection Boiling and Critical Heat Flux of Ethanol in Electrically Heated Tube
#               Tests, NASA/TM-1998-206612 (AIAA-98-1055), table III. Ethanol with 5 % isopropyl alcohol in tubes of 0.093 in inner diameter
# Correlations: 'meyer' is equations (1) to (3) of the same report
#               D. D. Hall, I. Mudawar, Critical heat flux (CHF) for water flow in tubes - II. Subcooled CHF correlations,
#               Int. J. Heat Mass Transfer 43 (2000) 2605-2640, table 4, correlation for outlet conditions
#               W. R. Gambill, Generalized prediction of burnout heat flux for flowing, subcooled, wetting liquids,
#               Chem. Eng. Prog. Symp. Ser. 59 (1963) 71-87. Reference and constants as remembered from textbooks, NOT checked against the original
# Properties:   pure ethanol from CoolProp, through the same functions as in the simulation

import numpy as np
from CoolProp.CoolProp import PropsSI

from .coolant import Coolant


# table III of the report: test number, pressure [psia], velocity [ft/s], velocity times subcooling [F ft/s], measured CHF [BTU/in^2/s]
tests = np.array([
    [1, 206, 9.7, 825, 1.57],      [2, 222, 15.8, 1348, 2.28],    [3, 219, 21.2, 2622, 2.62],    [4, 214, 20.5, 796, 1.21],
    [5, 221, 28.2, 1010, 1.64],    [6, 204, 48.1, 2304, 2.94],    [7, 199, 28.2, 3585, 3.31],    [8, 224, 56.8, 9395, 5.47],
    [9, 204, 9.9, 1484, 1.78],     [10, 214, 19.5, 3585, 2.88],   [11, 259, 39.4, 8679, 4.37],   [12, 223, 74.1, 18340, 6.99],
    [13, 555, 36.6, 12600, 3.97],  [14, 531, 55.0, 18390, 6.11],  [15, 514, 73.8, 24230, 8.67],  [16, 220, 15.3, 1797, 2.25],
    [17, 228, 20.5, 2408, 2.98],   [18, 202, 62.4, 3309, 3.69],   [19, 205, 28.2, 1145, 1.76],   [20, 202, 20.2, 667, 1.28],
    [21, 365, 36.6, 10900, 4.75],  [22, 218, 38.3, 7483, 5.40],   [23, 514, 37.0, 12290, 4.17],  [24, 209, 63.4, 16190, 6.43],
    [25, 211, 73.3, 19160, 7.08],  [26, 471, 36.7, 12110, 4.03],  [27, 336, 38.2, 11500, 4.54],  [28, 280, 39.0, 9291, 4.53],
    [29, 299, 54.4, 16310, 5.53],  [30, 299, 21.3, 6183, 2.96],   [31, 319, 76.7, 20740, 7.55],  [32, 297, 23.2, 3553, 3.52],
    [33, 703, 32.0, 10720, 3.18],  [34, 606, 35.5, 12850, 3.84],  [35, 167, 56.2, 11670, 5.87],  [36, 144, 58.0, 11530, 6.06],
    [37, 233, 29.6, 5954, 3.74],   [38, 208, 37.2, 5458, 4.28],
])

D      = 0.093 * 0.0254                              # inner diameter of the tubes [m]
P      = tests[:,1] * 6894.76                        # pressure [Pa]
v      = tests[:,2] * 0.3048                         # velocity [m/s]
dT_sub = tests[:,3] / tests[:,2] / 1.8               # subcooling [K], from the product with the velocity which the report used for its correlation
q_exp  = tests[:,4] * 1.6353e6                       # measured CHF [W/m^2]

x_o     = np.ndarray(len(tests))                     # thermodynamic quality of the subcooled ethanol
meyer   = np.ndarray(len(tests))
gambill = np.ndarray(len(tests))
hall    = np.ndarray(len(tests))

for i in range(len(tests)):
    coolant = Coolant(['Ethanol'], [1.0], T=PropsSI('T', 'P', P[i], 'Q', 0, 'Ethanol') - dT_sub[i], P=P[i])
    sat     = coolant.saturation()
    x_o[i]  = -sat.dH_sub / sat.Hvap

    meyer[i] = (0.1003 + 0.05264 * np.sqrt(tests[i,3])) * (1.17 - 8.56e-4 * tests[i,1]) * 1.6353e6

    # forced convection in the smooth tube with the Gnielinski correlation
    Re         = coolant.rho * v[i] * D / coolant.mu
    fd         = (0.79 * np.log(Re) - 1.64)**(-2)
    halpha_c   = (fd/8) * (Re - 1000) * coolant.Pr / (1 + 12.7 * (fd/8)**0.5 * (coolant.Pr**(2/3) - 1)) * coolant.k / D
    pool       = 0.15 * sat.Hvap * sat.rho_g * (sat.sigma * 9.81 * (sat.rho_l - sat.rho_g) / sat.rho_g**2)**0.25
    gambill[i] = pool * (1 + (sat.rho_l / sat.rho_g)**0.923 * sat.dH_sub / (25 * sat.Hvap)) + halpha_c * dT_sub[i]

    # Hall and Mudawar as published, without the correction for ethanol
    G       = coolant.rho * v[i]
    We      = G**2 * D / (sat.rho_l * sat.sigma)
    hall[i] = 0.0722 * We**(-0.312) * (sat.rho_l / sat.rho_g)**(-0.644) * (1 - 0.9 * (sat.rho_l / sat.rho_g)**0.724 * x_o[i]) * G * sat.Hvap

# error of Hall and Mudawar as a function of velocity and subcooling: least squares fit of ln(predicted / measured)
ratio     = hall / q_exp
fit       = np.linalg.lstsq(np.c_[np.ones(len(tests)), np.log(v), np.log(dT_sub)], np.log(ratio), rcond=None)[0]
corrected = hall / (0.8 * dT_sub**0.25 / v**0.2)     # as used in RegenCooling.py

print('test  P [bar]  v [m/s]  dT_sub [K]   x_o   CHF [MW/m^2]   predicted / measured: meyer  gambill  hall-mudawar  hall-mudawar corrected')
for i in np.argsort(dT_sub):
    print('%3d %8.1f %8.1f %9.0f %8.2f %10.2f %31.2f %8.2f %10.2f %15.2f' % (tests[i,0], P[i]/1e5, v[i], dT_sub[i], x_o[i], q_exp[i]/1e6, meyer[i]/q_exp[i], gambill[i]/q_exp[i], ratio[i], corrected[i]/q_exp[i]))

print('')
print('predicted / measured                 mean   scatter   lowest  highest   tests within 20 %')
for name, r in (('meyer', meyer / q_exp), ('gambill', gambill / q_exp), ('hall-mudawar as published', ratio), ('hall-mudawar / ' + str(round(np.mean(ratio), 2)), ratio / np.mean(ratio)), ('hall-mudawar corrected', corrected / q_exp)):
    print('%-32s %8.2f %8.2f %8.2f %8.2f %10d' % (name, np.mean(r), np.std(r), np.min(r), np.max(r), np.sum(np.abs(r - 1) < 0.2)))

print('')
print('hall-mudawar as published, mean of predicted / measured:')
print('  subcooling below 50 K:   ', round(np.mean(ratio[dT_sub < 50]), 2), ' (', np.sum(dT_sub < 50), ' tests)')
print('  subcooling 50 to 150 K:  ', round(np.mean(ratio[(dT_sub >= 50) & (dT_sub <= 150)]), 2), ' (', np.sum((dT_sub >= 50) & (dT_sub <= 150)), ' tests)')
print('  subcooling above 150 K:  ', round(np.mean(ratio[dT_sub > 150]), 2), ' (', np.sum(dT_sub > 150), ' tests)')
print('  inside its range of validity (x_o from -1.00 to -0.05):  ', round(np.mean(ratio[x_o >= -1]), 2), ' (', np.sum(x_o >= -1), ' tests)')
print('  fit: predicted / measured = ', round(np.exp(fit[0]), 2), ' * v^', round(fit[1], 2), ' * dT_sub^', round(fit[2], 2), '  [m/s, K]')
