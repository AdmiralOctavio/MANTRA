"""
All inputs of a thrust chamber design in one place: propellants, operating point, chamber and nozzle shape, film cooling, coolant,
cooling channels, wall material and the settings of the thermal simulation. A Design is saved to and loaded from a JSON project file.

Units are SI, except for the lengths of the chamber shape and the x coordinates of the film ports and profiles, which are in mm like
in the Method of Characteristics solver and the plots.
"""

import json
from dataclasses import MISSING, dataclass, field, asdict, fields, is_dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class Profile:
    """A quantity along the chamber: a constant, or points (x [mm], value) which are interpolated linearly and held constant beyond
    the first and the last point. Replaces the lambda functions of x in PyRocket's config.py, which can not be saved in a file."""
    value: float = 0.0
    points: List[Tuple[float, float]] = field(default_factory=list)

    def __call__(self, x_m):
        # x_m: axial coordinate of the chamber contour [m]
        x_m = np.asarray(x_m, dtype=float)
        if not self.points:
            return np.full_like(x_m, self.value)
        xp, fp = np.array(sorted(self.points), dtype=float).T
        return np.interp(x_m * 1e3, xp, fp)

    def as_input(self):
        # PyRocket's CoolingGeometry takes a float or a function of x [m]
        return float(self.value) if not self.points else self


@dataclass
class Propellants:
    oxidiser: str = "n2o"                  # key of core.propellants.OXIDISERS
    fuel: str = "ethanol"                  # key of core.propellants.FUELS
    fuel_concentration: float = 80.0       # wt% fuel in a fuel-water blend, ignored for fuels that are not blended with water


@dataclass
class OperatingPoint:
    chamber_pressure: float = 34e5         # [Pa]
    ambient_pressure: float = 101325.0     # [Pa]
    of_ratio: float = 4.4                  # core (combustion) O/F, without the film coolant
    thrust: float = 600.0                  # target thrust [N]
    eta_c_star: float = 0.875              # c* (combustion) efficiency, used by the nozzle sizing and the thermal model
    eta_nozzle: float = 0.985              # nozzle efficiency on the exit velocity


@dataclass
class ChamberShape:
    contraction_ratio: float = 16.0        # A_chamber / A_throat
    slope: float = 45.0                    # convergent half angle [deg]
    R1: float = 10.0                       # throat (upstream) radius [mm]
    R2: float = 50.0                       # chamber inlet radius of the convergent [mm]
    lstar_sizing: bool = True              # True: chamber length derived from L*; False: manual length below
    # metres; chosen between the propellant's short (min) and elongated (max) L* (core.propellants.lstar_range)
    lstar: float = 1.0                     # characteristic length L* [m]
    length: float = 83.02                  # total chamber length from the injector to the throat [mm], if lstar_sizing is False


@dataclass
class NozzleSettings:
    refinement: int = 100                  # number of characteristics, more is finer and slower
    shorten: float = 0.75                  # fraction of the full length nozzle that is kept (truncation)


@dataclass
class FilmPort:
    x: float = -20.0                       # axial position of the ring of ports on the chamber contour [mm]
    fraction: float = 0.1                  # film mass flow as a fraction of the fuel feed
    velocity: float = 10.0                 # injection velocity [m/s]
    diameter: float = 0.4e-3               # port diameter [m]


@dataclass
class FilmCooling:
    # film from the injector face, as a fraction of the fuel feed. The film is part of the fuel feed, not of the combustion: the core
    # O/F stays at OperatingPoint.of_ratio and the feed O/F is lower
    injector_fraction: float = 0.0
    injection_velocity: float = 10.0       # [m/s]
    injector_diameter: float = 0.4e-3      # [m]
    ports: List[FilmPort] = field(default_factory=list)   # rings of ports in the chamber wall, fed from the cooling channels

    @property
    def total_fraction(self):
        return self.injector_fraction + sum(port.fraction for port in self.ports)


@dataclass
class Coolant:
    fluids: List[str] = field(default_factory=lambda: ["Ethanol", "Water"])   # CoolProp fluid names
    mass_fractions: List[float] = field(default_factory=lambda: [0.8, 0.2])
    fuel_fraction: float = 1.0             # coolant mass flow through the channels as a fraction of the fuel feed
    inlet_temperature: float = 288.0       # [K]
    inlet_pressure: float = 45e5           # [Pa]
    start: str = "nozzle"                  # where the coolant enters the channels: "nozzle" or "injector"


@dataclass
class Channels:
    n: int = 15                                                        # number of cooling channels
    height: Profile = field(default_factory=lambda: Profile(1e-3))     # radial height h_c [m]
    fill_factor: Profile = field(default_factory=lambda: Profile(0.35))    # psi, fraction of the circumference covered by channels
    inner_wall: Profile = field(default_factory=lambda: Profile(0.9e-3))   # inner wall thickness t_w_i [m]
    outer_wall: float = 1.2e-3                                         # outer wall thickness t_w_o [m]
    helical: bool = False
    helix_angle: Profile = field(default_factory=lambda: Profile(30.0))    # angle to the chamber axis [deg]
    min_channel_size: float = 1e-3                                     # smallest channel that can be depowdered [m]


@dataclass
class ThermalSettings:
    material: str = "GRCop-42"             # name in thermal.materials.MATERIALS
    hot_gas_method: str = "cinjarev"       # 'cinjarev', 'standard-bartz' or 'modified-bartz'
    cooling_method: str = "gnielinski-rough"   # 'gnielinski', 'gnielinski-rough', 'dittus-boelter' or 'dittus-boelter-simple'
    boiling: bool = True
    chf_method: str = "hall-mudawar"       # 'meyer', 'gambill' or 'hall-mudawar'
    post_chf: str = "meyer"                # 'meyer' or 'fallback'
    ambient_temperature: float = 288.15    # [K]
    step_size: float = 2.5e-3              # step along the chamber contour [m]
    cell_size_factor: float = 0.15         # cell size of the 2D sections as a fraction of the smallest inner wall thickness
    adaptive_up: float = 1.4
    tolerance: float = 5e-2
    max_iter: int = 300
    run_time: Optional[float] = None       # None for steady state, otherwise the time of a transient run [s]
    save_section_figures: bool = False     # one png per section, slow
    anchor_throat: bool = True             # put a section exactly at the throat when the contour is resampled


@dataclass
class Design:
    name: str = "New engine"
    propellants: Propellants = field(default_factory=Propellants)
    operating: OperatingPoint = field(default_factory=OperatingPoint)
    chamber: ChamberShape = field(default_factory=ChamberShape)
    nozzle: NozzleSettings = field(default_factory=NozzleSettings)
    film: FilmCooling = field(default_factory=FilmCooling)
    coolant: Coolant = field(default_factory=Coolant)
    channels: Channels = field(default_factory=Channels)
    thermal: ThermalSettings = field(default_factory=ThermalSettings)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _from_dict(cls, data)

    def save(self, path):
        with open(path, "w") as f:
            json.dump({"format": "thrust-chamber-designer", "version": 1, "design": self.to_dict()}, f, indent=2)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data.get("design", data))


def _from_dict(cls, data):
    # builds nested dataclasses from a dict, ignores unknown keys so that older files still load
    kwargs = {}
    hints = {f.name: f for f in fields(cls)}
    for key, value in data.items():
        if key not in hints:
            continue
        default = hints[key].default_factory() if hints[key].default_factory is not MISSING else hints[key].default
        if is_dataclass(default):
            kwargs[key] = _from_dict(type(default), value)
        elif key == "ports":
            kwargs[key] = [_from_dict(FilmPort, port) for port in value]
        elif key == "points":
            kwargs[key] = [tuple(point) for point in value]
        else:
            kwargs[key] = value
    return cls(**kwargs)
