import numpy as np
import pytest

from thrust_chamber_designer.thermal.creep import LarsonMiller
from thrust_chamber_designer.thermal.materials import MATERIALS, CuCr1Zr, GRCop42, IN718, SS316L, Material
from thrust_chamber_designer.thermal.ratchet import PSI, FatigueCurve, NortonCreep, core_stress, ligament_life

IN = 0.0254


def test_core_stress_regimes_join():
    # elastic: the primary stress, the S1 and S2 / P formulas touch at (1 - X) Y = 1, and Z = 1 on both ratchet boundaries of Bree
    assert core_stress(0.3, 0.5) == pytest.approx(0.3)
    assert core_stress(0.3, 0.7 + 1e-9) == pytest.approx(0.3)
    for X in (0.2, 0.5, 0.7):
        Y = 1 / (1 - X)
        assert core_stress(X, Y * (1 - 1e-9)) == pytest.approx(X * Y, rel=1e-4)
    for X in (0.6, 0.8):
        assert core_stress(X, 4 * (1 - X)) == pytest.approx(1.0)
    assert core_stress(0.25, 4.0) == pytest.approx(1.0)
    assert core_stress(0.1, 3.0) == pytest.approx(0.3)


def narloy(Sy, Su, E, v, rate_ksi):
    # constant property ligament material of the NASA examples, Norton creep rate [1/s] as a function of the stress in ksi
    m = Material('test', 1, 1, 1, 1, v, E, 1, 0.8, Su, 1e-5, Sy)
    sig = np.array([1, 40]) * 1e3 * PSI
    rate = rate_ksi(sig / 1e3 / PSI)
    m.norton = NortonCreep({900: (sig, rate), 1000: (sig, rate)})
    m.fatigue = FatigueCurve({900: lambda N: 0.03 * (N / 100)**-0.4}, N_range=(10, 1e5))
    m.creep = LarsonMiller(20, [15000, 25000], [300e6, 1e6])
    return m


def test_ligament_reproduces_nasa_cr_168261_example_1():
    # NARloy-Z, SSME pressure (3000 psi), 4 min firing, creep law 5.5225e-7 sig^6.65 per hour (sig in ksi): plastic strain 0.014454 per
    # cycle, deflection 0.0003398 in, thinning 0.000146 in per cycle and 49 cycles to tensile instability (appendix B)
    m = narloy(24.5e3 * PSI, 55e3 * PSI, 16.35e6 * PSI, 0.34, lambda s: 5.5225e-7 * s**6.65 / 3600)
    r = ligament_life(m, 9.5e-6 * 865, 9.5e-6 * 210, 3000 * PSI, 0.035 * IN, 0.0664 * IN, 0.05 * IN, 950, 950, 300, 240)
    assert r['eps_pl_cycle'] == pytest.approx(0.014454, rel=1e-3)
    assert r['thinning'] / IN == pytest.approx(0.000146, rel=0.01)
    assert r['N_instability'] == pytest.approx(49, abs=1)


def test_ligament_reproduces_nasa_cr_165585_ofhc_example():
    # OFHC copper, test chamber (547 psi), no creep: plastic strain range 0.00751, thinning 0.0001263 in per cycle, 103 cycles (appendix A)
    m = narloy(9e3 * PSI, 46e3 * PSI, 17e6 * PSI, 0.3, lambda s: 1e-40 * s)
    r = ligament_life(m, 0.00635 + 2 * 9000 / 17e6, 9.5e-6 * 200, 547 * PSI, 0.035 * IN, 0.0664 * IN, 0.05 * IN, 950, 950, 300, 3)
    assert r['eps_pl_cycle'] == pytest.approx(2 * 0.00751, rel=2e-3)
    assert r['thinning'] / IN == pytest.approx(0.0001263, rel=0.01)
    assert r['N_instability'] == pytest.approx(103, abs=1)
    assert r['life_mode'] == 0


def test_larger_mismatch_shortens_life():
    # the start-up bound (closeout still cold, larger mismatch) can only shorten the life of a library material
    T_ref, T_lig, T_close = 293, 600, 520
    th = lambda T: GRCop42.value('a', T) * (T - T_ref)
    args = (th(T_lig + 15) - th(T_lig - 15), 25e5, 0.9e-3, 1.3e-3, 2.0e-3, T_lig, T_lig + 15, T_ref, 10.0)
    steady = ligament_life(GRCop42, th(T_lig) - th(T_close), *args)
    start_up = ligament_life(GRCop42, th(T_lig), *args)
    assert steady['eps_pl_cycle'] == 0 and start_up['eps_pl_cycle'] > 0
    assert start_up['N_life'] < steady['N_life']


def test_no_ratcheting_below_yield():
    # a mismatch below twice the yield strain does not ratchet, the life is the fatigue life
    m = narloy(24.5e3 * PSI, 55e3 * PSI, 16.35e6 * PSI, 0.34, lambda s: 1e-40 * s)
    r = ligament_life(m, 0.002, 0.0005, 500 * PSI, 0.035 * IN, 0.0664 * IN, 0.05 * IN, 950, 950, 300, 10)
    assert r['eps_pl_cycle'] == 0 and r['life_mode'] in (1, 3)


@pytest.mark.parametrize("T_C, amp, N", [(360, 0.785, 1113), (550, 0.97, 611), (650, 0.648, 1220), (650, 1.395, 82)])
def test_in718_fatigue_matches_xie(T_C, amp, N):
    # test points of table III of Xie (Superalloys 1991) within a factor of 2 in life
    assert IN718.fatigue.cycles(2 * amp / 100, T_C + 273.15) == pytest.approx(N, rel=1.0)


def test_fatigue_curves_match_sources():
    assert GRCop42.fatigue.cycles(0.01965, 500) == pytest.approx(588, rel=0.01)
    assert GRCop42.fatigue.cycles(0.006034, 500) == pytest.approx(20528, rel=0.01)
    assert CuCr1Zr.fatigue.cycles(2 * 3.5286e-2 * 1000**-0.26199, 500) == pytest.approx(1000, rel=0.01)
    assert SS316L.fatigue.cycles(0.01, 500) == pytest.approx(np.exp(6.891 - 1.920 * np.log(0.5 - 0.112)), rel=0.01)


def test_creep_rates_match_sources():
    assert GRCop42.norton.rate(35e6, 923.15) == pytest.approx(8.05e-8, rel=0.01)
    assert GRCop42.norton.exponent(773.15) == pytest.approx(11.6, abs=0.1)
    assert IN718.norton.rate(620e6, 923.15) * 3600 == pytest.approx(3.0e-6, rel=1.0)
    assert CuCr1Zr.norton.rate(110e6, 773.15) == pytest.approx(3.9e-9, rel=0.3)
    assert SS316L.norton.exponent(923.15) == pytest.approx(12, abs=0.5)
    # between test temperatures the rate lies between those of the neighbours
    assert SS316L.norton.rate(225e6, 873.15) < SS316L.norton.rate(225e6, 898.15) < SS316L.norton.rate(225e6, 923.15)


def test_creep_rates_rise_with_temperature_and_stress():
    # also far outside the data, where power laws of different exponents would cross (IN718: n = 12.6 at 650 C, 15.8 at 704 C)
    T = np.linspace(400, 1100, 30)
    for m in MATERIALS.values():
        if m.norton is not None:
            for sig in (1e6, 30e6, 300e6, 1e9):
                rates = np.array([float(m.norton.rate(sig, t)) for t in T])
                assert np.all(np.diff(rates) >= 0), (m.name, sig)
            assert np.all(np.diff(m.norton.rate(np.logspace(5, 9, 30), 800)) > 0), m.name


def test_library_materials_have_complete_cyclic_data():
    for m in MATERIALS.values():
        if m.norton is not None or m.fatigue is not None:
            assert m.norton is not None and m.fatigue is not None and m.creep is not None and m.sig_y is not None, m.name
            for T in (400, 700, 900):
                assert m.value('E', T) > 1e10 and 0 < m.value('v', T) < 0.5 and 5e-6 < m.value('a', T) < 3e-5, m.name
                assert m.value('sig_u', T) > m.value('sig_y', T) > 0, m.name
