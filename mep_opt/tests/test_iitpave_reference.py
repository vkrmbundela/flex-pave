"""
Validation against the ORIGINAL IITPAVE software output
=======================================================
This pins the native Burmister solver to a *real recorded run* of the original
IITPAVE Fortran program, captured in:

    IIT Pave - Original/IIT P/IITPAVE/IITPAVE.IN   (input)
    IIT Pave - Original/IIT P/IITPAVE/IITPAVE.out  (output)

Case: 4 layers, E = 2000/2000/209/80 MPa, mu = 0.35/0.35/0.35/0.40,
thicknesses 50/100/250 mm, single-wheel load 20000 N @ 0.56 MPa, DUAL wheel,
analysis points (z=150, r=155) and (z=400, r=155).

IITPAVE prints each interface point twice: the plain row uses the layer ABOVE
the interface, the "L" row uses the layer BELOW it (the lower side). This is
the program's own evidence that vertical strain eps_z is DISCONTINUOUS across a
layer interface — and that the subgrade rutting strain must be read on the
LOWER (subgrade) side. Compare:
    z=400 (top of subgrade): eps_z = -3.140e-4 (granular side, plain row)
                             eps_z = -4.706e-4 (subgrade side, "L" row)
The rutting criterion uses the -4.706e-4 (L) value.

All design-relevant quantities (stresses, strains, deflection) match IITPAVE to
well under 1.5%. The only quantity that differs is the shear stress TaoRZ at the
dual-wheel symmetry axis: IITPAVE reports ~2x the single-wheel value (it does
not apply the symmetry sign-flip), whereas the native solver returns the
true-elasticity value (~0 at the axis). TaoRZ is not used by any IRC:37
criterion; it is excluded from the match assertions and covered separately.
"""

import pytest

from mep_opt.solver.legacy_bridge import run_bridge_from_stack

LAYERS = [
    {"modulus": 2000, "poisson": 0.35, "thickness": 50},
    {"modulus": 2000, "poisson": 0.35, "thickness": 100},
    {"modulus": 209,  "poisson": 0.35, "thickness": 250},
    {"modulus": 80,   "poisson": 0.40, "thickness": 0},
]
LOAD = {"load": 20000, "pressure": 0.56, "is_dual": True, "spacing": 310}

# Real IITPAVE.out rows. Keys: (depth, side) where side 'U' = upper layer row,
# 'L' = lower layer ("L") row. Components in IITPAVE units (MPa, mm, strain).
IITPAVE = {
    ("150", "U"): dict(SigmaZ=-0.1011,    SigmaT=0.5171,     SigmaR=0.2387,
                       DispZ=0.4415, epZ=-0.1828e-3, epT=0.2345e-3, epR=0.4656e-4),
    ("150", "L"): dict(SigmaZ=-0.1011,    SigmaT=0.5287e-2,  SigmaR=-0.2381e-1,
                       DispZ=0.4415, epZ=-0.4527e-3, epT=0.2345e-3, epR=0.4656e-4),
    ("400", "U"): dict(SigmaZ=-0.3826e-1, SigmaT=0.4243e-1,  SigmaR=0.3576e-1,
                       DispZ=0.3518, epZ=-0.3140e-3, epT=0.2072e-3, epR=0.1641e-3),
    ("400", "L"): dict(SigmaZ=-0.3825e-1, SigmaT=0.4837e-3,  SigmaR=-0.1987e-2,
                       DispZ=0.3518, epZ=-0.4706e-3, epT=0.2072e-3, epR=0.1640e-3),
}
# Probe just inside the correct layer to force the U / L side.
PROBE_Z = {("150", "U"): 149.9, ("150", "L"): 150.1,
           ("400", "U"): 399.9, ("400", "L"): 400.1}

# Design-relevant components (TaoRZ deliberately excluded — see module docstring).
COMPONENTS = [
    ("SigmaZ", "sigma_z"), ("SigmaT", "sigma_t"), ("SigmaR", "sigma_r"),
    ("DispZ", "disp_z"), ("epZ", "eps_z"), ("epT", "eps_t"), ("epR", "eps_r"),
]

TOL = 0.015  # 1.5% vs the original IITPAVE output


@pytest.mark.parametrize("key", list(IITPAVE.keys()))
def test_native_matches_original_iitpave(key):
    """Native solver reproduces the original IITPAVE output to within 1.5%."""
    res = run_bridge_from_stack(LAYERS, LOAD, [{"z": PROBE_Z[key], "r": 155}])[0]
    ref = IITPAVE[key]
    for ref_name, nat_name in COMPONENTS:
        expected = ref[ref_name]
        got = res[nat_name]
        if abs(expected) < 1e-6:           # near-zero component: absolute check
            assert abs(got) < 5e-4, f"{key} {ref_name}: {got} not ~0"
        else:
            err = abs(got - expected) / abs(expected)
            assert err < TOL, (
                f"{key} {ref_name}: native {got:.5e} vs IITPAVE {expected:.5e} "
                f"({err*100:.2f}% > {TOL*100:.1f}%)"
            )


def test_subgrade_rutting_strain_is_the_lower_side_value():
    """
    The rutting strain is eps_z on the SUBGRADE side (IITPAVE 'L' row), which is
    ~1.5x the granular-side value. This is the original software's own proof of
    the interface discontinuity the optimizer must respect.
    """
    upper = run_bridge_from_stack(LAYERS, LOAD, [{"z": 399.9, "r": 155}])[0]  # granular
    lower = run_bridge_from_stack(LAYERS, LOAD, [{"z": 400.1, "r": 155}])[0]  # subgrade
    assert abs(lower["eps_z"]) == pytest.approx(0.4706e-3, rel=0.015)
    assert abs(upper["eps_z"]) == pytest.approx(0.3140e-3, rel=0.02)
    # The subgrade-side strain (the rutting strain) is materially larger.
    assert abs(lower["eps_z"]) > 1.4 * abs(upper["eps_z"])
