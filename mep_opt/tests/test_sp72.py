"""Tests for the IRC:SP:72-2015 low-volume rural road branch."""

import pytest

from mep_opt.solver import sp72


# --- Traffic categorisation ---------------------------------------------------

@pytest.mark.parametrize("esal,expected", [
    (9_000, None),       # below practical minimum
    (10_000, "T1"),      # T1 lower bound inclusive
    (30_000, "T1"),      # T1 upper inclusive
    (30_001, "T2"),
    (100_000, "T3"),
    (100_001, "T4"),
    (1_000_000, "T7"),
    (1_500_000, "T8"),
    (2_000_000, "T9"),   # SP:72 ceiling
    (2_000_001, None),   # above SP:72
])
def test_traffic_category_boundaries(esal, expected):
    assert sp72.classify_traffic(esal)[0] == expected


# --- Subgrade classification --------------------------------------------------

@pytest.mark.parametrize("cbr,label", [
    (2, "S1"), (3, "S2"), (4, "S2"), (5, "S3"),
    (6, "S3"), (7, "S4"), (9, "S4"), (10, "S5"), (15, "S5"),
])
def test_subgrade_class(cbr, label):
    assert sp72.classify_subgrade(cbr)[0] == label


def test_subgrade_clamps_outside_range():
    assert sp72.classify_subgrade(1)[0] == "S1"    # below 2 → clamp to S1
    assert sp72.classify_subgrade(25)[0] == "S5"   # above 15 → clamp to S5


# --- Regime detection ---------------------------------------------------------

def test_regime_threshold_at_2_msa():
    assert sp72.is_low_volume(2.0) is True
    assert sp72.is_low_volume(2.0001) is False
    assert sp72.is_low_volume(0.5) is True


# --- ESAL computation ---------------------------------------------------------

def test_esal_matches_growth_series():
    # Zero growth → simple multiplication.
    esal = sp72.compute_esal(cvpd=100, vdf=2.0, growth_rate=0.0,
                             design_life_years=10, lane_factor=1.0)
    assert esal == pytest.approx(100 * 2.0 * 365 * 10 * 1.0)


def test_esal_growth_increases_total():
    flat = sp72.compute_esal(100, 2.0, 0.0, 10, 0.75)
    grown = sp72.compute_esal(100, 2.0, 0.06, 10, 0.75)
    assert grown > flat


# --- Full classification + advisory ------------------------------------------

def test_classify_low_volume_blacktop_regime():
    # ~600k ESAL → low-volume, blacktop warranted, category present.
    c = sp72.classify(cvpd=200, vdf=1.0, growth_rate=0.0,
                      design_life_years=10, lane_factor=0.75, cbr=5.0)
    assert c.is_low_volume is True
    assert c.blacktop_required is True
    assert c.traffic_category is not None
    assert c.subgrade_class == "S3"
    assert any("SP:72" in a or "low-volume" in a for a in c.advisory)


def test_classify_high_volume_defers_to_irc37():
    c = sp72.classify(cvpd=2000, vdf=4.5, growth_rate=0.06,
                      design_life_years=15, lane_factor=0.75, cbr=8.0)
    assert c.is_low_volume is False
    assert any("IRC:37" in a for a in c.advisory)


def test_classify_below_blacktop_threshold_is_gravel():
    # Tiny traffic → no blacktop requirement.
    c = sp72.classify(cvpd=10, vdf=1.0, growth_rate=0.0,
                      design_life_years=10, lane_factor=1.0, cbr=4.0)
    assert c.is_low_volume is True
    assert c.blacktop_required is False
