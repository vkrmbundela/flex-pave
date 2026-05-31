# IndoPave-37 Project Documentation

## Project Overview

**IndoPave-37** is a high-performance pavement analysis and optimization tool aligned with **IRC:37-2019**. It uses a **native Python multi-layer elastic (Burmister) solver** as its structural engine (the same algorithm IITPAVE implements) and a deterministic **Smart Search Optimizer** that produces four engineering archetypes (Structural, Economy, Sustainable, Premium). The zero-scroll **Engineering Cockpit Dashboard** provides interactive design exploration.

> **Solver note:** The original IIT Pave Fortran `.EXE` is **no longer used at runtime** — it has been replaced by an in-process Burmister solver (`mep_opt/solver/burmister.py`), which is what runs both on the backend and in the browser via Pyodide. The legacy-bridge modules are thin compatibility shims that route to the native solver. The native solver is validated against **IRC:37-2018 Annex-II worked examples** (see `mep_opt/tests/test_irc_annex.py`).

---

## Architecture & Technology Stack

- **Backend**: Python 3.10+ (**FastAPI**, Uvicorn)
- **Structural Solver**: **Native Python Burmister multi-layer elastic solver** (`burmister.py`, NumPy/SciPy) — in-process, thread-safe, no external executable. Runs identically on the backend and in-browser (Pyodide).
- **Numerical Support**: NumPy, SciPy
- **Frontend**: **React 19**, **Vite**, **Tailwind CSS v4**
- **Data Visualization**: **Recharts** (archetype comparison)
- **Optimization Engine**: **Smart Pavement Search** — deterministic brute-force enumeration of constructable lift sizes + four single-purpose archetypes (Structural / Economy / Sustainable / Premium). Exhaustive over the buildable space, no local-minimum risk, no external dependencies.
- **Legacy Bridge**: `iitpave_bridge.py` / `legacy_bridge.py` are compatibility shims that route all calls to the native Burmister solver (`solver_facade.py`). No Fortran `.EXE` is invoked.
- **Engine duplication**: the in-browser (Pyodide) build uses a mirrored copy of the engine under `frontend/public/py/mep_opt/`. Keep it in sync with `python tools/sync_pyodide_copy.py`; `mep_opt/tests/test_backend_sync.py` fails if the two drift.

---

## UI/UX & Design System

The platform follows a premium **Industrial Blueprint** aesthetic:
- **Themes**:
  - **Slate Engineering** (Light): High-contrast, matte white/slate corporate style.
  - **Antigravity** (Dark): Deep indigo/slate theme for technical clarity.
- **Typography**: **Poppins** (Headlines & UI elements) paired with **Inter** for data/labels.
- **Layout**: **Zero-Scroll Cockpit** with draggable splitters for a CAD-like experience, high-density data cards, and interactive cross-section previews.
- **Persistence**: Hybrid `localStorage` sync with auto-save and two-stage Reset safety (export-to-JSON).

---

## Optimization Algorithm

The optimizer (`SmartPavementSearch` in `optimizer/smart_search.py`) is a **deterministic brute-force lift enumeration with Pareto selection** — not a greedy/gradient search. It is exhaustive over a small, constructable design space, so it is fully reproducible and free of local-minimum risk.

**Step 1 — Enumerate constructable combinations.**
For each layer, take the discrete *constructable lift sizes* (MoRTH-500-aligned `DEFAULT_LIFT_SCHEDULE`, or a user override) that fall within the layer's thickness bounds. Form the Cartesian product. A typical 4-layer stack yields ~100–300 combinations (a warning fires above 50k).

**Step 2 — IRC / MoRTH pre-filter.**
Drop combinations that violate the active traffic-tier minimum thicknesses (per-layer minimums + the IRC:37-2018 page-42 CTB bituminous-bundle rule) *before* any solver call. Combinations are then sorted by ascending total thickness (or ₹/km when `optimize_by_cost`).

**Step 3 — Evaluate each design** through the native Burmister solver:
- `eps_t` (fatigue) at the **bottom of the bottom bituminous layer**;
- `eps_v` (rutting) at the **top of the subgrade** (just below the granular/subgrade interface) per IRC:37-2018 §3.6.1;
- `sigma_t` (CTB fatigue) at the bottom of the CTB layer at 0.80 MPa when a CTB is present (a second solver call).
A design is **adequate** when all applicable CDFs (fatigue + rutting + CTB) ≤ 1.0. Reliability is auto-escalated R80→R90 for ≥20 msa (IRC §3.7); the fatigue C-factor uses the bottom-mix `Va`/`Vbe`.

**Step 4 — Four archetypes.**
From the IRC-adequate set (cost and embodied CO₂ are computed for every design), return four single-purpose optima:
- **Structural** — thinnest adequate design (minimum total material; the direct solver optimum);
- **Economy** — cheapest adequate design (minimum ₹/km);
- **Sustainable** — greenest adequate design (minimum embodied CO₂/km);
- **Premium** — best *combined* optimum: minimises the equally-weighted, min-max-normalised sum of thickness + cost + CO₂.

When one design wins several objectives, its labels merge onto a single card (e.g. "Economy + Sustainable"), so the UI shows 1–4 cards — exactly as many as there are genuinely distinct optimal strategies. A cooperative wall-clock deadline returns the best designs found so far if the budget is exceeded.

---

## Solver Accuracy & Validation

Validated against **IRC:37-2018 Annex-II worked examples** and legacy benchmark cases (rps1, case2, TIHAN1):
- **Example II.3** (flexible, 131 MSA): native `eps_t` = 146 µε vs IRC 146 (−0.0%); `eps_v` = 244 µε vs IRC 243 (+0.7%).
- **Example II.4** (CTB): native max tensile stress at CTB bottom = 0.699 MPa vs IRC 0.700.
- TIHAN1 (mixed Poisson 0.35–0.45) deviates up to ~30% — a known limitation of the dual-wheel superposition; most cases are within a few percent.
- **Compliance**: Automated adequacy checks against IRC:37-2018/2019 fatigue, rutting, and CTB performance equations. Regression suite: `mep_opt/tests/test_irc_annex.py`.

---

## Commands & Usage

### 1. Build & Installation

```bash
# Backend Setup
python -m venv venv
.\venv\Scripts\activate
pip install -r mep_opt/requirements.txt

# Frontend Setup
cd frontend
npm install
```

### 2. Running Locally

You must run both the backend and frontend in separate terminals:

**Terminal 1 (Backend)**:
```bash
python -m mep_opt.web.main
```
*Runs on `http://127.0.0.1:8000`*

**Terminal 2 (Frontend)**:
```bash
cd frontend
npm run dev
```
*Runs on `http://localhost:5173`*

### 3. Testing 

```bash
# Backend Test Suite
python -m pytest mep_opt/tests/ -v

# Standalone Solver Validation
python tests/validate_solver.py
```

---

## File Structure

```
+-- frontend/                # React (Vite/Tailwind v4) Dashboard
|   +-- src/
|   |   +-- App.jsx          # Main Dashboard logic & State
|   |   +-- index.css        # Design tokens & Themes
|   +-- vite.config.js       # Tailwind configuration
+-- mep_opt/                 # Core Python Backend
|   +-- solver/
|   |   +-- iitpave_bridge.py # Compat shim → native Burmister solver (no .EXE)
|   |   +-- legacy_bridge.py  # Public API surface for bridge
|   |   +-- irc37.py          # IRC:37-2019 Design Equations
|   |   +-- materials.py      # Material property database
|   +-- optimizer/
|   |   +-- smart_search.py   # Brute-force lift enumeration + 4 archetypes
|   |   +-- problem.py        # Problem/Result data structures
|   +-- cost/                  # Cost & CO2 (LCA) estimation
|   +-- advanced/              # Sensitivity, Monte Carlo, Strain Field, Corridor
|   +-- web/
|       +-- main.py            # FastAPI Endpoints & CORS
+-- CLAUDE.md                  # This Documentation
```

---

## Core Development Guidelines

1. **Design Integrity**: All new components must support both `light` (default) and `.theme-dark` CSS classes. Use the centralized design tokens in `index.css`.
2. **Solver Dependency**: All structural analysis runs through the native Python Burmister solver (`solver_facade.run_solver`). No external `.EXE` is required on any machine. The browser (Pyodide) build uses the mirrored engine under `frontend/public/py/mep_opt/` — mirror every engine change with `python tools/sync_pyodide_copy.py`.
3. **Mathematical Accuracy**: Any solver or IRC logic change must be regression-tested against the IRC Annex-II suite (`test_irc_annex.py`) and the benchmark suite (`test_solver.py`). Critical conventions: `eps_v` at top of subgrade (below the interface); `eps_t` at bottom of bottom bituminous layer; granular modulus uncapped Eq. 7.1; subgrade ν = 0.35; dual-wheel standard axle.
4. **Optimized Responses**: Ensure all API responses handle NumPy types correctly using `_to_native()` serialization (NaN/Inf converted to null).
5. **Input Validation**: All API endpoints use Pydantic `field_validator` constraints. Bad inputs return 422 with specific messages.
6. **No Placeholders**: Use real data or generated assets for all engineering demonstrations.
