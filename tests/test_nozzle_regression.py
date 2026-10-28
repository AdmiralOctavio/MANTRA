import os
from types import SimpleNamespace

import numpy as np

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
