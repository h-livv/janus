# Collision Validation

High-energy Monte Carlo engines such as Geant4 are stochastic and hard to benchmark by eye. Janus therefore validates collision output **before** transport consumes it.

This document describes the **implemented** Janus collision validation: what each script checks, which ROOT files it needs, and how to run it.

---

## Two data streams

Geant4 writes two ROOT files per run (staged under `temp/`, then packaged into `data/interactions/<run_name>/`):

| File | Tree | Role |
|------|------|------|
| `validation.root` | `Validation` | Per-event initial / outgoing kinematics for conservation checks |
| `simulation.root` | `Seeds` | Secondary kinematics for transport (and Phase 4 spatial plots) |

### Seed recording mode

`interactions/config.json` → `output.record_mode`:

| Mode | Meaning |
|------|---------|
| `"Hit"` (**default**) | Record kinematics when a particle crosses Target → Chamber |
| `"Birth"` | Record \(t=0\) birth kinematics of secondaries |

Transport and Phase 4 both read `Seeds`. With the default Hit mode, those are chamber-entry states, not necessarily production vertices.

---

## How to run

From the repository root, after at least one completed collision run:

```bash
# Phases 1–3: conservation / quantum / sanity (validation.root)
python interactions/validation/validate.py
# or: python interactions/validation/validate.py path/to/validation.root

# Phase 4: phenomenological plots (needs both ROOT files)
python interactions/validation/physical_validation.py
# or: python interactions/validation/physical_validation.py path/to/validation.root path/to/simulation.root
```

If paths are omitted, both scripts pick the newest directory under `data/interactions/run_*`.

**Extra Python deps** (not all are in `requirements.txt`):

```bash
pip install uproot awkward particle matplotlib
```

---

## Phases 1–3 — `validate.py`

Reads **`validation.root`** only. Fails hard if kinematic or quantum conservation is violated beyond tolerance.

### Phase 1: Kinematic invariants

Compares total outgoing energy and momentum to the recorded initial state. If \(|\Delta E|\) or \(|\Delta p|\) exceeds `--epsilon` (default 2 MeV), the suite aborts.

> **Janus note:** Heavy target fragments can leave a sub-threshold residual. The engine absorbs that residual into the heaviest target fragment so 4-momentum is preserved exactly for the check.

### Phase 2: Quantum numbers

Checks event-by-event conservation of charge \(Q\) and baryon number \(B\), including dynamic target isotope deduction from the fragment set.

### Phase 3: Statistical sanity

Reports macroscopic counters for human inspection — it does **not** compare yields to theoretical caps or fail on multiplicity bounds:

- Total antinucleons generated
- Global baryon conservation check
- Mean charged pions per inelastic event

### Example terminal output (100k events)

```
========== JANUS VALIDATION REPORT ==========
Events Validated: 100000
Phase 1 Passed: Kinematic Conservation Verified.
  -> Maximum ΔE Error: 3.2014213502407074e-10 MeV
  -> Maximum ΔP Error: 2.1845111499714025e-11 MeV/c
Phase 2 Passed: Quantum Number Conservation Verified.
  -> Mean Event Charge (Q): 75.0 (Mean Expected: 75.0)
  -> Mean Event Baryon (B): 184.9 (Mean Expected: 184.9)
Phase 3 Sanity Checks Passed:
  -> Total Antinucleons Generated: 430
  -> Global Baryon Conservation Verified.
  -> Mean Charged Pions per Inelastic Event: 4.0194

[+] Validation Suite Passed Successfully. Transport simulation may proceed.
```

---

## Phase 4 — `physical_validation.py`

Reads **both** `validation.root` and `simulation.root`. Produces diagnostic plots for visual review — there is **no** automated pass/fail against exponential fits or distribution templates.

Outputs go to:

```text
interactions/validation/validation_outputs/<run_name>/
├── phase4_pT_vs_pL.png
├── phase4_multiplicity.png
├── phase4_energy_spectra.png
└── phase4_vertex_z.png
```

| Plot | What it shows |
|------|----------------|
| \(p_T\) vs \(p_L\) | Charged-pion transverse vs longitudinal momentum (2D density) |
| Multiplicity | Charged-pion multiplicity per inelastic event |
| Energy spectra | Kinetic-energy spectra (e.g. neutrons) |
| Vertex \(z\) | Histogram of seed \(z\) positions from `Seeds` |

Illustrative snapshots (from an earlier 100k-event study) are also kept under `docs/assets/collision_val/` for the README / docs gallery; live runs write the `phase4_*.png` names above.

---

## Relation to transport

After Phases 1–3 pass (and Phase 4 looks sensible), define and run a transport experiment:

```bash
python -m transport.main --experiment geant4_antiproton
```

Transport reads **`simulation.root` / `Seeds`** only (via `transport/io.py`). Momentum and species selection are experiment parameters — see [transport guide](../guides/transport_guide.md).
