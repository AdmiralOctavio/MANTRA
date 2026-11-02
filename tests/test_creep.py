import numpy as np
import pytest

from thrust_chamber_designer.thermal.creep import LarsonMiller, reference_stress
from thrust_chamber_designer.thermal.materials import MATERIALS, GRCop42, IN718


def test_reference_stress_limits():
    # half the elastic bending stress for bending alone (fixed ends collapse at twice the load of first yield), the membrane stress alone
    assert reference_stress(100e6, 0.0) == pytest.approx(50e6)
    assert reference_stress(0.0, 30e6) == pytest.approx(30e6)
    assert 50e6 < reference_stress(100e6, 30e6) < 130e6


def test_rupture_time_and_strength_are_inverse():
    lm = LarsonMiller(20, [19000, 22000], [800e6, 300e6], factor=0.9)
    T = 950.0
    t, flag = lm.rupture_time(500e6, T)
    assert flag == 0
    assert lm.rupture_strength(t, T) == pytest.approx(500e6, rel=1e-9)
    # the factor scales the stress of the data
    assert lm.rupture_strength(t, T) / LarsonMiller(20, [19000, 22000], [800e6, 300e6]).rupture_strength(t, T) == pytest.approx(0.9)


def test_extrapolation_flags_and_limits():
    lm = LarsonMiller(20, [19000, 22000], [800e6, 300e6])
    t_low, flag = lm.rupture_time(100e6, 900.0)
    assert flag == 1 and t_low > lm.rupture_time(300e6, 900.0)[0]
    # above the highest stress of the data without a tensile strength: no data, ruptures at once
    assert lm.rupture_time(900e6, 900.0) == (0.0, 2)
    assert lm.rupture_strength(1e-3, 900.0) == pytest.approx(800e6)
    # with a tensile strength the curve is extended up to it
    t, flag = lm.rupture_time(900e6, 900.0, sig_u=1000e6)
    assert flag == 2 and t > 0
    assert lm.rupture_time(1000e6, 900.0, sig_u=1000e6)[0] == 0.0
    assert lm.rupture_strength(1e-9, 900.0, sig_u=1000e6) == pytest.approx(1000e6)
    assert lm.rupture_time(0.0, 900.0)[0] == np.inf


def test_in718_reproduces_the_rupture_table():
    # 1000 h at 1200 F (922 K) under 85 ksi for wrought bar, the printed material at 0.9 times the stress
    t, flag = IN718.creep.rupture_time(0.9 * 85 * 6.894757e6, (1200 - 32) / 1.8 + 273.15)
    assert flag == 0
    assert t == pytest.approx(1000, rel=0.05)


@pytest.mark.parametrize("T_C, sig_MPa, t_h", [(800, 10.0, 851), (800, 21.7, 7.5), (650, 35.0, 108), (650, 60.3, 2.55),
                                               (500, 75.7, 404), (500, 129.9, 2.96)])
def test_grcop42_matches_nasa_creep_lives(T_C, sig_MPa, t_h):
    # ends of the creep life lines of extruded GRCop-42 in figure 11 of AIAA-2019-4228, within 15 % of the life
    t, _ = GRCop42.creep.rupture_time(GRCop42.creep.factor * sig_MPa * 1e6, T_C + 273.15)
    assert t == pytest.approx(t_h, rel=0.15)


def test_curves_fall_with_stress():
    for m in MATERIALS.values():
        if m.creep is not None:
            assert np.all(np.diff(m.creep.log_sig) < 0), m.name
