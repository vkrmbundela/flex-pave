// Shared IRC:37-2018 helpers for the frontend (advanced panels).
// Mirrors mep_opt/solver/irc37.py so the dashboard's client-side previews
// use the same relationships as the backend optimizer.

// Effective resilient modulus of the subgrade (MPa) from CBR (%).
//   MRS = 10 * CBR            for CBR <= 5 %      (IRC:37-2018 Eq. 6.1)
//   MRS = 17.6 * CBR^0.64     for CBR > 5 %       (IRC:37-2018 Eq. 6.2)
//   capped at 100 MPa for design                 (IRC:37-2018 Cl. 6.4.2)
// The advanced panels previously used a flat `CBR * 10`, which is only valid
// for CBR <= 5 % and over-stiffens the subgrade for typical CBR (6-10 %).
export function subgradeModulusFromCBR(cbr) {
  const c = Number(cbr) || 0;
  const mr = c <= 5 ? 10 * c : 17.6 * Math.pow(c, 0.64);
  return Math.min(mr, 100);
}

// Bituminous mix types (IRC fatigue uses the BOTTOM bituminous layer modulus).
const BITUMINOUS = new Set(['BC', 'DBM', 'BM', 'SDBC', 'SMA']);

function classify(layer) {
  return String(layer?.type || layer?.name || '').toUpperCase().trim();
}

// Resilient modulus (MPa) of the BOTTOM bituminous layer, for the fatigue
// criterion (IRC:37-2018 §3.6.2). Falls back to the first/last layer's E when
// no layer is clearly bituminous.
export function bottomBituminousModulus(layers, numLayers) {
  if (!Array.isArray(layers) || layers.length === 0) return 1250;
  const n = numLayers ?? layers.length;
  let mod = null;
  for (let i = 0; i < n && i < layers.length; i++) {
    const t = classify(layers[i]);
    if ([...BITUMINOUS].some((b) => t.includes(b))) {
      mod = Number(layers[i].E) || mod;   // keep the deepest bituminous layer
    }
  }
  return mod ?? (Number(layers[0]?.E) || 1250);
}

// Cumulative design traffic in MSA (IRC:37-2018 §4 / cumulative_msa()):
//   N = 365 * A * D * F * ((1+r)^n - 1) / r  / 1e6
// where A = CVPD, D = lane distribution factor, F = VDF, r = growth, n = life.
// The advanced panels previously fed raw CVPD in as "MSA", which massively
// over-states the traffic (e.g. 800 CVPD -> "800 MSA").
export function cumulativeMSA({ cvpd, growthRate = 0.05, designLife = 20, ldf = 0.75, vdf = 2.5 }) {
  const A = Number(cvpd) || 0;
  const r = Number(growthRate);
  const n = Number(designLife) || 0;
  const D = Number(ldf);
  const F = Number(vdf);
  const factor = Math.abs(r) < 1e-10 ? n : ((1 + r) ** n - 1) / r;
  return (365 * A * D * F * factor) / 1e6;
}
