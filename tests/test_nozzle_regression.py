import os
from types import SimpleNamespace

import numpy as np
import pytest

from thrust_chamber_designer.core.design import Design
from thrust_chamber_designer.nozzle.sizing import size_nozzle

GOLDEN = os.path.join(os.path.dirname(__file__), 'golden')


def test_moc_matches_original_solver():
    # default case of the original nozzle solver (main.run and solver_standard with the defaults of Parameters.py), with the
    # combustion properties it got from rocketcea and CEA, so only the solver itself is compared
    old = np.load(os.path.join(GOLDEN, 'moc_golden.npz'))
    chem = SimpleNamespace(Tc=float(old['Tc']), cstar_eq=float(old['Cstr']), gamma_throat=float(old['g_throat']),
                           MW_throat=8.314 / float(old['Rs']) * 1000, gamma_exit=float(old['g_exit']))
    design = Design()
    result = size_nozzle(chem, design.operating, design.chamber, design.nozzle)

    assert result.converged
    np.testing.assert_allclose(result.mdot, float(old['mdot']), rtol=1e-9)
    np.testing.assert_allclose(result.throat_radius, float(old['y_min']), rtol=1e-9)
    np.testing.assert_allclose(result.M_exit_design, float(old['M_exit']), rtol=1e-9)
    np.testing.assert_allclose(result.wall_x, old['wall_x'], rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(result.wall_y, old['wall_y'], rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(result.thrust, float(old['Thrust']), rtol=1e-9)
    np.testing.assert_allclose(result.exit_angle, float(old['Exit_Angle']), rtol=1e-9)
    np.testing.assert_allclose(result.chamber_length, float(old['Lc']), rtol=1e-9)


def _lox_lh2(R1, R2):
    # 600 N at 150 bar into 0.1 bar: a throat of under 3 mm and a pressure ratio of 1500
    design = Design()
    design.propellants.oxidiser, design.propellants.fuel, design.propellants.fuel_concentration = "lox", "lh2", 100.0
    op = design.operating
    op.chamber_pressure, op.ambient_pressure, op.of_ratio, op.thrust = 150e5, 0.1e5, 5.3, 600.0
    design.chamber.R1, design.chamber.R2 = R1, R2
    return design


def test_sizing_at_a_large_pressure_ratio():
    # fsolve took derivatives from steps too small for the net of characteristics here and went to negative Mach numbers (NaN)
    from thrust_chamber_designer import pipeline
    design = _lox_lh2(5.0, 15.0)
    s = pipeline.design_nozzle(design).solution
    assert s.converged
    assert s.thrust == pytest.approx(design.operating.thrust, rel=1e-6)
    assert s.P_exit == pytest.approx(design.operating.ambient_pressure, rel=1e-6)
    assert s.throat_radius > 0 and s.expansion_ratio > 50


def test_convergent_that_does_not_fit_says_what_to_change():
    # the arcs of R1 and R2 need more radius than there is between the chamber and the small throat: the wall ran through the axis
    from thrust_chamber_designer import pipeline
    with pytest.raises(ValueError, match=r"convergent section does not fit.*R1 \+ R2 at most"):
        pipeline.design_nozzle(_lox_lh2(10.0, 50.0))
