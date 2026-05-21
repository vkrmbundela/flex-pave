"""Tests for IRC:SP:59 geosynthetic MIF reinforcement (Saride 2021)."""

import pytest

from mep_opt.solver.geosynthetic import get_mif, MIF_TABLE, list_geogrid_types, NONE_OPTION
from mep_opt.solver.irc37 import build_layer_stack, SubgradeInput, BituminousLayerInput
from mep_opt.solver.solver_facade import run_solver, set_solver_backend, SolverBackend


# --- MIF lookup ---------------------------------------------------------------

def test_mif_exact_table_values():
    # Validated against the lecture deck table.
    assert get_mif(10, "PP30") == 3.13
    assert get_mif(30, "PET30") == 2.06   # deck's worked example
    assert get_mif(50, "PET60") == 2.00
    assert get_mif(70, "PP30") == 1.50


def test_mif_linear_interpolation():
    # PP30 between Mrs=30 (1.88) and Mrs=50 (1.60) at Mrs=40 → midpoint 1.74.
    assert get_mif(40, "PP30") == pytest.approx(1.74, abs=1e-9)


def test_mif_clamps_outside_table():
    # Below smallest / above largest tabulated Mrs → hold nearest value.
    assert get_mif(5, "PP30") == 3.13
    assert get_mif(100, "PP30") == 1.50


def test_mif_none_and_unknown_return_unity():
    assert get_mif(30, None) == 1.0
    assert get_mif(30, NONE_OPTION) == 1.0
    assert get_mif(30, "NOPE") == 1.0


def test_mif_monotonic_with_subgrade_and_geogrid():
    # Weaker subgrade → larger uplift; stronger geogrid → larger uplift.
    assert get_mif(10, "PP30") > get_mif(50, "PP30")
    assert get_mif(50, "PET60") > get_mif(50, "PP30")


def test_geogrid_types_listing_includes_none_and_all_grids():
    ids = {g["id"] for g in list_geogrid_types()}
    assert NONE_OPTION in ids
    assert set(MIF_TABLE).issubset(ids)


# --- Effect on the layer stack & solver --------------------------------------

def _stack(geogrid):
    sub = SubgradeInput(cbr=8.0)
    bit = [BituminousLayerInput("BC", 40, 1250, 0.35),
           BituminousLayerInput("DBM", 60, 1250, 0.35)]
    gran = [
        {"thickness": 250, "layer_type": "WMM", **({"geogrid": geogrid} if geogrid else {})},
        {"thickness": 200, "layer_type": "GSB"},
    ]
    return build_layer_stack(sub, gran, bit)


def test_geogrid_uplifts_base_modulus():
    plain = _stack(None)
    grid = _stack("PET60")
    # Plain collapses to a single composite granular row; the geogrid breaks
    # the collapse and uplifts the reinforced base — so the max granular
    # modulus must be higher with the grid.
    plain_max_gran = max(l["modulus"] for l in plain[2:-1])
    grid_max_gran = max(l["modulus"] for l in grid[2:-1])
    assert grid_max_gran > plain_max_gran


def test_geogrid_reduces_critical_strains():
    set_solver_backend(SolverBackend.NATIVE)
    load = {"load": 20000, "pressure": 0.56, "is_dual": True, "spacing": 310}
    pts = [{"z": 99.9, "r": 0}, {"z": 449.9, "r": 0}]  # bit bottom, subgrade top
    plain = run_solver(_stack(None), load, pts)
    grid = run_solver(_stack("PET60"), load, pts)
    assert abs(grid[0]["eps_t"]) < abs(plain[0]["eps_t"])   # fatigue strain drops
    assert abs(grid[1]["eps_z"]) <= abs(plain[1]["eps_z"])  # rutting strain drops
