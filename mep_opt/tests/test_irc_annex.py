"""
IRC:37-2018 Annex-II End-to-End Regression Tests
================================================
These tests pin the design pipeline to IRC:37-2018's own published worked
examples (Annex-II). They are the guard-rail for the class of defects found
in the May-2026 audit:

  * Subgrade rutting strain (eps_v) must be sampled at the TOP OF THE SUBGRADE
    (just BELOW the granular/subgrade interface), per IRC §3.6.1 — NOT on the
    granular side, which under-reported eps_v ~40% and over-estimated rutting
    life ~10x.
  * Granular modulus uses Eq. 7.1 with NO modular-ratio cap (Annex-II II.3
    uses a ratio of 3.23 uncapped -> 200 MPa).
  * Fatigue C-factor uses the project mix volumetrics (Va, Vbe), defaulting
    to the IRC Annex-II values (Va=3 %, Vbe=11.5 %) so the tool reproduces
    IRC's own design.
  * CTSB / CRL layers are part of the structural model (not silently dropped).
  * Subgrade Poisson ratio = 0.35 (IRC page 19).

Published IRC:37-2018 Annex-II reference values used below:
  Example II.3 (flexible, 131 MSA, 90% reliability):
      3-layer IITPAVE idealization: E = 3000 / 200 / 62 MPa,
      thicknesses 190 / 480 mm, Poisson 0.35 all, dual 20 kN wheels @ 0.56 MPa.
      Published: granular E = 200 MPa, eps_t = 0.000146, eps_v = 0.000243.
  Example II.4 (CTB, single 190 kN axle, 0.80 MPa):
      5-layer: E = 3000 / 450 / 5000 / 600 / 62 MPa,
      Poisson 0.35 / 0.35 / 0.25 / 0.25 / 0.35,
      thicknesses 100 / 100 / 120 / 250 mm; wheel load 190000/4 = 47500 N.
      Published: max tensile stress at bottom of CTB = 0.6995 MPa (~0.70).
"""

import pytest

from mep_opt.solver.legacy_bridge import run_bridge_from_stack
from mep_opt.solver.irc37 import (
    SubgradeInput, GranularLayerInput, BituminousLayerInput,
    build_layer_stack, check_design_adequacy, ReliabilityLevel,
)
from mep_opt.optimizer.smart_search import SmartPavementSearch
from mep_opt.optimizer.problem import OptimizationProblem
from mep_opt.solver.irc37 import TrafficInput


# Standard IRC dual-wheel axle (one set of dual wheels, 20 kN each, 310 mm).
IRC_STD_LOAD = {"load": 20000, "pressure": 0.56, "is_dual": True, "spacing": 310}


# ---------------------------------------------------------------------------
# Example II.3 — flexible pavement, the canonical IRC design
# ---------------------------------------------------------------------------

II3_LAYERS = [
    {"modulus": 3000, "poisson": 0.35, "thickness": 190},
    {"modulus": 200,  "poisson": 0.35, "thickness": 480},
    {"modulus": 62,   "poisson": 0.35, "thickness": 0},
]
II3_INTERFACE = 670.0  # top of subgrade (190 + 480)


def test_annex_ii3_fatigue_strain_matches_irc():
    """eps_t at the bottom of the bituminous layer must match IRC's 0.000146."""
    res = run_bridge_from_stack(
        II3_LAYERS, IRC_STD_LOAD,
        [{"z": 190, "r": 0}, {"z": 190, "r": 155}],
    )
    eps_t = max(max(abs(r["eps_t"]), abs(r["eps_r"])) for r in res)
    assert eps_t == pytest.approx(146e-6, rel=0.05), (
        f"IRC II.3 eps_t must be ~146 ustrain, got {eps_t*1e6:.1f}"
    )


def test_annex_ii3_rutting_strain_sampled_in_subgrade():
    """
    eps_v MUST be read just BELOW the interface (in the subgrade), giving
    IRC's ~0.000243. Sampling just ABOVE it (granular side) gives ~0.000144 —
    a 40% under-read. This is the core regression guard for the rutting bug.
    """
    sub_side = run_bridge_from_stack(
        II3_LAYERS, IRC_STD_LOAD,
        [{"z": II3_INTERFACE + 0.1, "r": 0}, {"z": II3_INTERFACE + 0.1, "r": 155}],
    )
    eps_v = max(abs(r["eps_z"]) for r in sub_side)
    assert eps_v == pytest.approx(243e-6, rel=0.06), (
        f"IRC II.3 eps_v must be ~243 ustrain, got {eps_v*1e6:.1f}"
    )

    # Sanity: the granular side is materially LOWER (the discontinuity that
    # made the original bug so damaging). If these two ever converge, the
    # layer-indexing convention has changed and the guard is void.
    gran_side = run_bridge_from_stack(
        II3_LAYERS, IRC_STD_LOAD, [{"z": II3_INTERFACE - 0.1, "r": 0}],
    )
    eps_v_gran = abs(gran_side[0]["eps_z"])
    assert eps_v_gran < 0.8 * eps_v, (
        "Granular-side eps_z should be much smaller than subgrade-side; "
        "the interface discontinuity is what the sampling fix depends on."
    )


def test_annex_ii3_optimizer_evaluate_uses_subgrade_strain():
    """
    The OPTIMIZER's own _evaluate() (the production adequacy path) must report
    eps_v ~ 0.000243, NOT the buggy ~0.000144. This is the end-to-end guard:
    it exercises the exact internal eval-point construction in smart_search.
    """
    problem = OptimizationProblem(
        traffic=TrafficInput(initial_aadt=0, commercial_vehicles_per_day=3000,
                             traffic_growth_rate=0.05, design_life_years=15),
        subgrade=SubgradeInput(cbr=7.0),          # -> ~61-62 MPa
        reliability=ReliabilityLevel.R90,
        layer_types=["DBM", "WMM"],               # IRC's 3000/200/62 idealization
        thickness_bounds={"DBM": (190, 190), "WMM": (480, 480)},
        layer_props={"DBM": {"E": 3000, "nu": 0.35}, "WMM": {"nu": 0.35}},
        wheel_type="Dual",
    )
    s = SmartPavementSearch(problem)
    out = s._evaluate([190.0, 480.0])

    assert out["eps_v"] == pytest.approx(243e-6, rel=0.07), (
        f"Optimizer eps_v must be the subgrade-side ~243 ustrain, "
        f"got {out['eps_v']*1e6:.1f} (a value near 144 means the rutting "
        f"sampling bug has regressed)"
    )
    assert out["eps_v"] > 200e-6, "Optimizer eps_v collapsed toward the buggy granular-side value"
    assert out["eps_t"] == pytest.approx(146e-6, rel=0.06)


def test_annex_ii3_fatigue_adequate_with_irc_mix():
    """
    With IRC's mix (Va=3 %, Vbe=11.5 %) the canonical 131-MSA design is
    fatigue-ADEQUATE (computed eps_t 146 < allowable 150). The old hard-coded
    Va=4 % wrongly rejected it. This pins the C-factor threading.
    """
    chk = check_design_adequacy(
        eps_t=146e-6, eps_v=243e-6, cumulative_msa=131, mix_modulus=3000,
        reliability=ReliabilityLevel.R90, air_voids=3.0, bitumen_volume=11.5,
    )
    assert chk["CDF_fatigue"] < 1.0, "IRC II.3 must pass fatigue with its own mix"
    assert chk["CDF_rutting"] < 1.0, "IRC II.3 must pass rutting"
    assert chk["overall_adequate"] is True


# ---------------------------------------------------------------------------
# Example II.4 — CTB tensile stress
# ---------------------------------------------------------------------------

def test_annex_ii4_ctb_tensile_stress_matches_irc():
    """Max tensile stress at the bottom of the CTB layer must match IRC's 0.70 MPa."""
    layers = [
        {"modulus": 3000, "poisson": 0.35, "thickness": 100},  # BC
        {"modulus": 450,  "poisson": 0.35, "thickness": 100},  # CRL @ 450
        {"modulus": 5000, "poisson": 0.25, "thickness": 120},  # CTB
        {"modulus": 600,  "poisson": 0.25, "thickness": 250},  # CTSB @ 600
        {"modulus": 62,   "poisson": 0.35, "thickness": 0},    # subgrade
    ]
    # 190 kN single axle -> wheel load = 190000/4 = 47500 N; CTB contact 0.80 MPa.
    load = {"load": 47500, "pressure": 0.80, "is_dual": True, "spacing": 310}
    res = run_bridge_from_stack(
        layers, load,
        [{"z": 320 - 0.1, "r": 0}, {"z": 320 - 0.1, "r": 155}],
    )
    sigma_t = max(max(abs(r["sigma_t"]), abs(r["sigma_r"])) for r in res)
    assert sigma_t == pytest.approx(0.6995, rel=0.05), (
        f"IRC II.4 CTB tensile stress must be ~0.70 MPa, got {sigma_t:.4f}"
    )


# ---------------------------------------------------------------------------
# Structural-stack assembly guards (CTSB / CRL / Poisson / no-cap)
# ---------------------------------------------------------------------------

def _ctb_problem():
    return OptimizationProblem(
        traffic=TrafficInput(initial_aadt=0, commercial_vehicles_per_day=300,
                             traffic_growth_rate=0.05, design_life_years=15),
        subgrade=SubgradeInput(cbr=7.0),
        layer_types=["BC", "CRL", "CTB", "CTSB"],
        thickness_bounds={"BC": (100, 100), "CRL": (100, 100),
                          "CTB": (120, 120), "CTSB": (250, 250)},
    )


def test_ctsb_is_not_dropped_from_stack():
    """A CTSB layer must appear in the structural stack with its 600 MPa modulus."""
    s = SmartPavementSearch(_ctb_problem())
    stack, _, _, ctb_depth = s._build_solver_inputs([100, 100, 120, 250])
    # total structural thickness (excl. infinite subgrade) must include CTSB
    total = sum(r["thickness"] for r in stack[:-1])
    assert total == 570, f"CTSB dropped: structural thickness {total} != 570"
    assert any(abs(r["thickness"] - 250) < 1e-6 and abs(r["modulus"] - 600) < 1
               for r in stack), "CTSB row (250 mm @ 600 MPa) missing from stack"
    assert ctb_depth == 320


def test_crack_relief_layer_gets_450_mpa():
    """The granular crack-relief layer directly above CTB must be 450 MPa (IRC p27)."""
    s = SmartPavementSearch(_ctb_problem())
    stack, _, _, _ = s._build_solver_inputs([100, 100, 120, 250])
    crl_rows = [r for r in stack if abs(r["thickness"] - 100) < 1e-6
                and abs(r["modulus"] - 450) < 1]
    assert crl_rows, "Crack-relief layer not assigned the IRC 450 MPa modulus"


def test_subgrade_poisson_default_is_035():
    """IRC:37-2018 page 19 — subgrade Poisson ratio = 0.35 (was wrongly 0.40)."""
    stack = build_layer_stack(
        SubgradeInput(cbr=7.0),
        [GranularLayerInput(thickness=480, material_type="WMM")],
        [BituminousLayerInput("DBM", 190, 3000)],
    )
    assert stack[-1]["poisson"] == 0.35


def test_granular_composite_modulus_uncapped():
    """WMM+GSB collapse to one layer at Eq. 7.1 with no cap -> ~200 MPa (II.3)."""
    stack = build_layer_stack(
        SubgradeInput(cbr=7.0),
        [GranularLayerInput(thickness=250, material_type="WMM"),
         GranularLayerInput(thickness=230, material_type="GSB")],
        [BituminousLayerInput("DBM", 190, 3000)],
    )
    # One composite granular row between bituminous and subgrade.
    gran = stack[1]
    assert abs(gran["thickness"] - 480) < 1e-6
    assert gran["modulus"] == pytest.approx(200.0, rel=0.03), (
        f"Composite granular modulus must be ~200 MPa uncapped, got {gran['modulus']:.1f}"
    )


# ---------------------------------------------------------------------------
# Reliability auto-escalation (IRC §3.7) and the unsafe-design guard
# ---------------------------------------------------------------------------

def test_reliability_auto_escalates_at_20_msa():
    """R80 must auto-escalate to R90 for design traffic >= 20 msa (IRC §3.7)."""
    high = OptimizationProblem(
        traffic=TrafficInput(initial_aadt=0, commercial_vehicles_per_day=3000,
                             traffic_growth_rate=0.05, design_life_years=15),
        subgrade=SubgradeInput(cbr=8.0),
        reliability=ReliabilityLevel.R80,
        layer_types=["BC", "DBM", "WMM", "GSB"],
        thickness_bounds={"BC": (40, 40), "DBM": (60, 60),
                          "WMM": (250, 250), "GSB": (200, 200)},
    )
    assert SmartPavementSearch(high)._reliability == ReliabilityLevel.R90

    low = OptimizationProblem(
        traffic=TrafficInput(initial_aadt=0, commercial_vehicles_per_day=120,
                             traffic_growth_rate=0.05, design_life_years=10),
        subgrade=SubgradeInput(cbr=8.0),
        reliability=ReliabilityLevel.R80,
        layer_types=["BC", "DBM", "WMM", "GSB"],
        thickness_bounds={"BC": (40, 40), "DBM": (60, 60),
                          "WMM": (250, 250), "GSB": (200, 200)},
    )
    assert low.traffic.cumulative_msa() < 20.0
    assert SmartPavementSearch(low)._reliability == ReliabilityLevel.R80


def test_advanced_modules_respect_mix_volumetrics():
    """
    The advanced Sensitivity / Monte-Carlo panels must thread Va/Vbe into the
    fatigue C-factor (not the old hard-coded 4 %). Higher air voids -> lower
    fatigue life -> higher CDF_fatigue. Proves the plumbing is connected.
    """
    from mep_opt.advanced.sensitivity import compute_sensitivity
    layers = [
        {"modulus": 3000, "poisson": 0.35, "thickness": 190},
        {"modulus": 200,  "poisson": 0.35, "thickness": 480},
        {"modulus": 62,   "poisson": 0.35, "thickness": 0},
    ]
    load = {"load": 20000, "pressure": 0.56, "is_dual": True, "spacing": 310}
    pts = [{"z": 190, "r": 0}, {"z": 190, "r": 155},
           {"z": 670.1, "r": 0}, {"z": 670.1, "r": 155}]
    roles = {"bit_bottom": [0, 1], "sub_top": [2, 3]}

    lean = compute_sensitivity(layers, load, pts, 50, 3000, 90, roles,
                               air_voids=3.0, bitumen_volume=11.5)
    rich = compute_sensitivity(layers, load, pts, 50, 3000, 90, roles,
                               air_voids=7.0, bitumen_volume=11.5)
    cdf_lean = lean[0]["deltas"][0]["CDF_f"]
    cdf_rich = rich[0]["deltas"][0]["CDF_f"]
    assert cdf_lean is not None and cdf_rich is not None
    assert cdf_rich > cdf_lean, "Higher air voids must raise fatigue CDF (Va threaded)"


def test_thin_design_correctly_fails_rutting():
    """
    A thin section at high traffic must now be correctly REJECTED on rutting.
    Before the fix the optimizer reported CDF_rutting ~0.3 (adequate) for a
    design whose true CDF_rutting was ~2.2 (it would rut out in years).
    """
    problem = OptimizationProblem(
        traffic=TrafficInput(initial_aadt=0, commercial_vehicles_per_day=4200,
                             traffic_growth_rate=0.05, design_life_years=15),
        subgrade=SubgradeInput(cbr=6.0),
        reliability=ReliabilityLevel.R90,
        layer_types=["DBM", "WMM"],
        thickness_bounds={"DBM": (130, 130), "WMM": (430, 430)},
        layer_props={"DBM": {"nu": 0.35}, "WMM": {"nu": 0.35}},
        wheel_type="Dual",
    )
    s = SmartPavementSearch(problem)
    out = s._evaluate([130.0, 430.0])
    assert out["CDF_rutting"] > 1.0, (
        f"Thin section must fail rutting; got CDF_rutting={out['CDF_rutting']:.2f}"
    )
    assert out["overall_adequate"] is False
