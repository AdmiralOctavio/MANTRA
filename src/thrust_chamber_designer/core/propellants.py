from dataclasses import dataclass

from .chemistry import add_new_propellant


"""
Fuel definitions
Feel free to add your own oxidisers and fuels depending on what you need to simulate

One library for the nozzle solver and the thermal model: every oxidiser and fuel is a blend in the format of PropLibrary.py, a dict of
species names from the NASA CEA thermo database (or added with add_new_propellant) and their weight percentages. These blends go
straight into core/chemistry.py, which is the only source of combustion properties (rocketcea is not used any more).

"""


@dataclass(frozen=True)
class Oxidiser:
    name: str
    blend: dict             # species from the CEA thermo database and their weight percentages
    # Characteristic chamber length L* in metres: (short, nominal, elongated).
    # Drives combustion-chamber volume sizing in CombustionChamber.py.
    # Default L* band for this oxidiser; overridden per fuel in _LSTAR_OVERRIDES.
    Lstar_range: tuple = (1.0, 1.14, 1.27)


@dataclass(frozen=True)
class Fuel:
    name: str
    blend: dict             # species from the CEA thermo database and their weight percentages, without water
    # True: fuel can be diluted with water, concentration set on the UI slider.
    water_blend: bool = False
    coolant: tuple = ()     # CoolProp fluid names of the fuel for the cooling channels (water is added for blends), empty if unknown


OXIDISERS: dict = {
    "n2o": Oxidiser(
        name="N2O",
        blend={"N2O": 100},
        # ESTIMATE: N2O not tabulated in Sutton; N2O vaporisation tends to
        # need a longer chamber. Tune against test data if available.
        Lstar_range=(0.5, 1.0, 1.8),
    ),
    "lox": Oxidiser(
        name="LOX",
        blend={"O2(L)": 100},
        # Sutton & Biblarz: O2/LH2 L* = 0.76-1.02 m. Also used for O2/alcohol
        # (ESTIMATE: not directly tabulated; Sutton's O2/ammonia band is the same).
        Lstar_range=(0.76, 0.89, 1.02),
    ),
    "peroxide98": Oxidiser(
        name="Peroxide (98%)",
        # liquid H2O2 and water. The nozzle solver used to take the gas phase species here, which gives a higher chamber temperature
        blend={"H2O2(L)": 98, "H2O(L)": 2},
        # Sutton & Biblarz: H2O2/RP-1 L* = 1.52-1.78 m (long; slow decomposition).
        Lstar_range=(1.52, 1.65, 1.78),
    ),
}

# thermo.lib only carries gas-phase 2-propanol, and rocketcea's stock
# "Isopropanol" card also uses the gas heat of formation. Shift both to the
# liquid: dHf(l) = -318.1 kJ/mol vs dHf(g) = -272.7 kJ/mol.
# The liquid is added as a new propellant from its atoms and its enthalpy of formation, as in PropLibrary.py
add_new_propellant("isopropanol(L)", {"C": 3, "H": 8, "O": 1}, -318.1e3)

FUELS: dict = {
    "ethanol": Fuel(
        name="Ethanol",
        blend={"C2H5OH(L)": 100},
        water_blend=True,
        coolant=("Ethanol",),
    ),
    "ipa": Fuel(
        name="IPA",
        blend={"isopropanol(L)": 100},
        water_blend=True,
    ),
    "methanol": Fuel(
        name="Methanol",
        blend={"CH3OH(L)": 100},
        water_blend=True,
        coolant=("Methanol",),
    ),
    "rp1": Fuel(
        name="RP-1",
        blend={"RP-1": 100},
        coolant=("n-Dodecane",),
    ),
    "lh2": Fuel(
        name="LH2",
        blend={"H2(L)": 100},
        coolant=("Hydrogen",),
    ),
}

# (oxidiser, fuel) pairs whose L* differs from the oxidiser's default band.
_LSTAR_OVERRIDES = {
    # Sutton & Biblarz, Rocket Propulsion Elements: O2/RP-1 L* = 1.02-1.27 m.
    ("lox", "rp1"): (1.02, 1.14, 1.27),
}


def fuel_blend(fuel_key: str, fuel_conc: float = 100.0) -> dict:
    """Blend of a fuel and, for water-blendable fuels, water: fuel_conc in wt% fuel (balance water)."""
    fuel = FUELS[fuel_key]
    if not fuel.water_blend or fuel_conc >= 100:
        return dict(fuel.blend)
    blend = {species: percent * fuel_conc / 100 for species, percent in fuel.blend.items()}
    blend["H2O(L)"] = 100 - fuel_conc
    return blend


def oxidiser_blend(ox_key: str) -> dict:
    return dict(OXIDISERS[ox_key].blend)


def lstar_range(ox_key: str, fuel_key: str) -> tuple:
    """Characteristic length L* in metres: (short, nominal, elongated)."""
    return _LSTAR_OVERRIDES.get((ox_key, fuel_key), OXIDISERS[ox_key].Lstar_range)


def propellant_name(ox_key: str, fuel_key: str, fuel_conc: float = 100.0) -> str:
    fuel = FUELS[fuel_key]
    name = f"{OXIDISERS[ox_key].name} / {fuel.name}"
    if fuel.water_blend:
        name += f" ({fuel_conc:g}%)"
    return name


def default_coolant(fuel_key: str, fuel_conc: float = 100.0):
    """CoolProp fluids and mass fractions of the fuel as coolant, None if CoolProp has no fluid for it."""
    fuel = FUELS[fuel_key]
    if not fuel.coolant:
        return None
    if fuel.water_blend and fuel_conc < 100:
        return list(fuel.coolant) + ["Water"], [fuel_conc / 100, 1 - fuel_conc / 100]
    return list(fuel.coolant), [1.0]
