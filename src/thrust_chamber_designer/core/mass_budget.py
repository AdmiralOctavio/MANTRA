"""
Split of the mass flow through the throat into oxidiser, fuel that burns in the core and fuel that is injected as film coolant.

The O/F of the design is the core (combustion) O/F, the one CEA is run with. The film coolant is fuel as well and comes out of the same
feed, so the feed system and the cooling channels carry more fuel than the core O/F implies:

    fuel feed  = core fuel + film
    film       = film fraction * fuel feed      (injector face and rings of ports together)
    oxidiser   = core O/F * core fuel
    feed O/F   = oxidiser / fuel feed = core O/F * (1 - film fraction)
    throat     = oxidiser + fuel feed          (the film leaves through the nozzle too)

The nozzle is sized for the whole mass flow through the throat with the c* of the core.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class MassBudget:
    total: float                 # through the throat [kg/s]
    oxidiser: float              # [kg/s]
    fuel_core: float             # fuel that burns at the core O/F [kg/s]
    fuel_feed: float             # all fuel from the feed system, film included [kg/s]
    film_injector: float         # film from the injector face [kg/s]
    film_ports: List[float] = field(default_factory=list)    # film of each ring of ports in the chamber wall [kg/s]
    coolant: float = 0.0         # through the cooling channels [kg/s]
    of_core: float = 0.0         # combustion O/F
    of_feed: float = 0.0         # O/F of the feed system, film included

    @property
    def film(self):
        return self.film_injector + sum(self.film_ports)


def mass_budget(total, of_core, film, coolant_fraction=1.0):
    """total: mass flow through the throat [kg/s], of_core: combustion O/F, film: core.design.FilmCooling, coolant_fraction: coolant
    through the channels as a fraction of the fuel feed"""
    f = film.total_fraction
    if not 0 <= f < 1:
        raise ValueError('The film fractions must add up to at least 0 and less than 1 of the fuel feed, they add up to %g' % f)
    fuel_feed = total / (of_core * (1 - f) + 1)
    fuel_core = fuel_feed * (1 - f)
    oxidiser  = of_core * fuel_core
    return MassBudget(
        total=total,
        oxidiser=oxidiser,
        fuel_core=fuel_core,
        fuel_feed=fuel_feed,
        film_injector=film.injector_fraction * fuel_feed,
        film_ports=[port.fraction * fuel_feed for port in film.ports],
        coolant=coolant_fraction * fuel_feed,
        of_core=of_core,
        of_feed=oxidiser / fuel_feed,
    )
