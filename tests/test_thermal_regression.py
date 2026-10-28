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

    new = np.genfromtxt(tmp_path / 'sim_data.csv', delimiter=',', skip_header=1)
    old = np.genfromtxt(os.path.join(GOLDEN, 'thermal_coarse_sim_data.csv'), delimiter=',', skip_header=1)
    assert new.shape == old.shape
    numeric = [c for c in range(old.shape[1]) if c != 30]          # column 30 is the Bree regime as text
    np.testing.assert_allclose(new[:, numeric], old[:, numeric], rtol=1e-6, atol=1e-6, equal_nan=True)
