#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Creator:  Joanthan Neeser                                         #
# Date:     15.12.2022                                              #
# Version:  2.3  													#
# License:	GNU GENERAL PUBLIC LICENSE V3			                #
#                                                                   #
#####################################################################

from .chemistry import add_new_propellant

# A blend is a dict of species names from the NASA CEA thermo database and their weight percentages.
# Liquids carry the suffix (L), e.g. 'C2H5OH(L)', 'O2(L)', 'H2O2(L)'. A name without suffix is the gas, e.g. 'N2O'

# ethanol blends
ethanol90 = {'C2H5OH(L)': 90, 'H2O(L)': 10}
ethanol80 = {'C2H5OH(L)': 80, 'H2O(L)': 20}
ethanol70 = {'C2H5OH(L)': 70, 'H2O(L)': 30}


# methanol blends
methanol80 = {'CH3OH(L)': 80, 'H2O(L)': 20}
methanol85 = {'CH3OH(L)': 85, 'H2O(L)': 15}
methanol90 = {'CH3OH(L)': 90, 'H2O(L)': 10}

# Example of oxidiser blends. Works the same way as for fuels
# Hydrogen Peroxide
peroxide98 = {'H2O2(L)': 98, 'H2O(L)': 2}
peroxide96 = {'H2O2(L)': 96, 'H2O(L)': 4}
peroxide94 = {'H2O2(L)': 94, 'H2O(L)': 6}
peroxide90 = {'H2O2(L)': 90, 'H2O(L)': 10}


# Examples of adding new propellants, which are not in the thermo database
# input is the name, the atoms in the molecule and the enthalpy of formation at 298.15 K [J/mol]
# aniline
add_new_propellant('aniline', {'C': 6, 'H': 7, 'N': 1}, 31.3e3)
aniline = {'aniline': 100}


# furfurylalcohol
add_new_propellant('furfurylalcohol', {'C': 5, 'H': 6, 'O': 2}, -276.2e3)
furfurylalcohol = {'furfurylalcohol': 100}
