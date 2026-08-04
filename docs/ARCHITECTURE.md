# Janus Transport Architecture

For the full end-to-end walkthrough (Geant4 → Xsuite → analysis), see **[TRANSPORT_PIPELINE.md](TRANSPORT_PIPELINE.md)**.

## Current status

Janus is an orchestration layer around two external engines:

| Stage | Owner | Janus role |
|-------|-------|------------|
| Particle production | Geant4 (`engine/`, `interactions/`) | Configure, run, validate, extract seeds |
| Beam transport | Xsuite (`xpart` / `xtrack`) | Convert seeds, track caller-built `xt.Line`, write NPZ |
| Diagnostics | Janus (`transport/analysis/`) | Plots + summary from transported NPZ |
| Optimization | Planned | Consume transported NPZ |

There is no custom Boris integrator, no YAML transport config, and no interactive visualization in the transport path.

**Single source of truth:** every scientific parameter (species, momentum window, count, turns, output name/dir, beamline, initial conditions) is defined in the experiment script under `transport/experiments/`. `pipeline.py`, `io.py`, and `xsuite.py` only execute what they are given.

```text
Geant4 collision run
↓
temp/ → interactions/runs/<run>/
        ├── simulation.root      (Seeds tree — transport input)
        ├── validation.root      (Validation tree — collision checks)
        ├── <run>_config.json
        └── particle_summary.txt
↓
transport/io.py  →  merged_seeds_cache_v6.npz (beside ROOT)
↓
transport/experiments/<name>.py  (plain variables + xt.Line)
↓
transport/pipeline.run(...)      (filter → convert → track → write)
↓
Xsuite tracking
↓
transported_particles.npz + analysis products
```

---

## Repository layout

```text
janus/
├── engine/                     # C++ Geant4 simulation engine
├── interactions/
│   ├── run.py                  # Collision entry point
│   ├── run_batches.py
│   ├── config.json
│   ├── dependencies/           # Simulation interface; packages temp/ → runs/
│   ├── runs/                   # Packaged ROOT outputs (gitignored)
│   └── validation/
│       ├── validate.py         # Phases 1–3
│       └── physical_validation.py
├── transport/
│   ├── main.py                 # CLI: select experiment module
│   ├── pipeline.py             # Orchestration only
│   ├── io.py                   # ROOT → NPZ seeds (no experiment cuts)
│   ├── xsuite.py               # Seeds → Particles, track, write NPZ
│   ├── analysis/               # NPZ diagnostics
│   └── experiments/            # One script per study (params live here)
├── tests/transport/
├── docs/
│   ├── TRANSPORT_PIPELINE.md
│   ├── transport_guide.md
│   └── ...
└── requirements.txt
```

Geant4 writes intermediate ROOT files under project `temp/` (`temp/simulation`, `temp/validation`). The Python interface moves them into `interactions/runs/<run_name>/` after the run completes.

---

## How to run

See the full guide: [transport_guide.md](transport_guide.md).

```bash
pip install -r requirements.txt
python -m transport.main --experiment drift
python -m transport.main --experiment geant4_antiproton
```

Experiments are Python modules under `transport/experiments/`. Each exposes `main()` and defines all scientific parameters as plain variables before calling `run(...)`.

---

## Data contracts

### Seed recording mode

`interactions/config.json` → `output.record_mode`:

| Mode | What `Seeds` stores |
|------|---------------------|
| `"Hit"` (default) | Kinematics at Target→Chamber boundary crossing |
| `"Birth"` | \(t=0\) birth kinematics of secondaries |

Transport injects particles at the line entrance regardless; absolute `start_z` is metadata only.

### Seed NPZ (Geant4 → transport)

Cached beside each run as `merged_seeds_cache_v6.npz` (+ `merged_seeds_manifest_v6.json`). IO extracts proton/antiproton (PDG ±2212) only and does **not** apply a momentum window — that is the experiment’s `momentum_slice`.

| Key | Shape | Units |
|-----|-------|-------|
| `positions` | (N, 3) | m |
| `velocities` | (N, 3) | m/s |
| `gammas` | (N,) | — |
| `charges` | (N,) | ±1 |
| `momenta_mevc` | (N, 3) | MeV/c |
| `start_z` | (N,) | m |

### Transported run directory

```text
transport/outputs/run_<timestamp>/
├── transported_particles.npz
├── beam_xy.png
├── phase_space.png
├── momentum_histogram.png
├── beamline.png
└── summary.txt
```

NPZ fields include final `x`, `px`, `y`, `py`, `zeta`, `delta`, `state`, `alive_mask`, `at_element`, `p0c_eV`, `mass0_eV`, `q0`, `start_z`, and `metadata_json` (species, beamline elements, source path, engine `"xsuite"`).

---

## Xsuite coordinate mapping

Janus converts seeds once in `transport/xsuite.py`:

- `x`, `y` — transverse position [m]
- `px`, `py` — \(p_{x,y}/p_0\)
- `zeta` — 0 at injection (seed time not mapped)
- `delta` — \(|p|/p_0 - 1\)
- `p0c` — median \(|p|c\) unless the experiment overrides `p0c_eV`
- `mass0` — `xt.PROTON_MASS_EV` (proton / antiproton mass)

---

## Tests

```bash
pytest tests/transport/
```

Coverage: NPZ loading, particle conversion, Line construction, tracking smoke, analysis outputs, pipeline integration.

---

## Dependencies

```bash
pip install -r requirements.txt
```

Primary packages: `xsuite`, `numpy`, `uproot`, `matplotlib`, `pytest`.

Collision validation also needs `particle` and `awkward` (see [geant4_installation.md](geant4_installation.md) and [collision_validation.md](collision_validation.md)).
