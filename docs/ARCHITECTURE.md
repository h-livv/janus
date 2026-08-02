# Janus Transport Architecture

## Current status

Janus is an orchestration layer around two external engines:

| Stage | Owner | Janus role |
|-------|-------|------------|
| Particle production | Geant4 (`engine/`, `interactions/`) | Configure, run, validate, extract seeds |
| Beam transport | Xsuite (`xpart` / `xtrack`) | Convert seeds, build/run `xt.Line`, write NPZ |
| Diagnostics | Janus (`transport/analysis/`) | Plots + summary from transported NPZ |
| Optimization | Planned | Consume transported NPZ |

There is no custom Boris integrator, no YAML transport config, and no interactive visualization in the transport path.

```text
Geant4 collision run
↓
interactions/runs/<run>/simulation.root
↓
transport/io.py  →  NPZ seed cache
↓
transport/experiments/<name>.py  (Python variables + xt.Line)
↓
transport/pipeline.run(...)
↓
Xsuite tracking
↓
transported_particles.npz + analysis products
```

---

## Repository layout

```text
janus/
├── engine/                 # C++ Geant4 simulation engine
├── interactions/           # Geant4 Python orchestration + collision validation
├── transport/
│   ├── main.py             # CLI: select experiment module
│   ├── pipeline.py         # run(line=..., particle=..., ...)
│   ├── io.py               # ROOT → NPZ seeds, species table
│   ├── xsuite.py           # Seeds → Particles, track, write NPZ
│   ├── analysis/           # NPZ diagnostics
│   └── experiments/        # One script per study
├── tests/transport/
├── docs/
│   └── transport_guide.md  # How to write and run experiments
└── requirements.txt
```

---

## How to run

See the full guide: [transport_guide.md](transport_guide.md).

```bash
pip install -r requirements.txt
python -m transport.main --experiment drift
python -m transport.main --experiment geant4_antiproton
```

Experiments are Python modules under `transport/experiments/`. Each exposes `main()`.

---

## Data contracts

### Seed NPZ (Geant4 → transport)

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

NPZ fields include final `x`, `px`, `y`, `py`, `zeta`, `delta`, `state`, `alive_mask`, `p0c_eV`, `mass0_eV`, `q0`, `start_z`, and `metadata_json` (species, beamline elements, source path).

---

## Xsuite coordinate mapping

Janus converts seeds once in `transport/xsuite.py`:

- `x`, `y` — transverse position [m]
- `px`, `py` — \(p_{x,y}/p_0\)
- `zeta` — 0 at injection (seed time not mapped)
- `delta` — \(|p|/p_0 - 1\)
- `p0c` — median \(|p|c\) unless overridden

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

Primary packages: `xsuite`, `numpy`, `uproot`, `matplotlib`.
