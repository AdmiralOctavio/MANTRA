import os

import numpy as np
import pytest

GOLDEN = os.path.join(os.path.dirname(__file__), 'golden')


@pytest.mark.slow
def test_example_matches_pyrocket(tmp_path):
    # the PyRocket example case on a coarse grid, compared with sim_data.csv of the same case run with the original PyRocket code
    # (config.py with step_size = 0.008, cell_size = 0.3 * t_w_i, save_fig and print_result off)
    from thrust_chamber_designer.thermal import example_config

    config = example_config.build(save_path=str(tmp_path), step_size=0.008, cell_size=0.3 * 0.9e-3, save_fig=False, print_result=False)
    example_config.run(config)

    golden = os.path.join(GOLDEN, 'thermal_coarse_sim_data.csv')
    new = np.genfromtxt(tmp_path / 'sim_data.csv', delimiter=',', skip_header=1)
    old = np.genfromtxt(golden, delimiter=',', skip_header=1)
    assert new.shape == old.shape
    # The results are not identical on every platform: the 2D sections are meshed by gmsh, whose mesh can differ slightly with the
    # floating point of the platform, and the sections are solved to a tolerance of 0.05 K. On Linux runners this moves the wall
    # temperatures by a few hundredths of a kelvin and other results by up to about 0.5 %. The limits are well above that and well
    # below a change of the model
    with open(golden) as f:
        header = [h.strip() for h in f.readline().split(',')]
    numeric = [c for c in range(old.shape[1]) if c != 30]          # column 30 is the Bree regime as text
    temperature = [c for c in numeric if header[c].endswith('[K]') and '/' not in header[c]]
    other = [c for c in numeric if c not in temperature]
    np.testing.assert_allclose(new[:, temperature], old[:, temperature], rtol=0, atol=0.5, equal_nan=True)
    np.testing.assert_allclose(new[:, other], old[:, other], rtol=2e-2, atol=1e-6, equal_nan=True)
