# Janus Architecture

Janus is an orchestration layer for antimatter production and beam transport. It does not reimplement hadronic physics or magnetic tracking: **Geant4** owns particle production, **Xsuite** owns beam transport, and Janus owns configuration, seed extraction, experiment scripts, analysis, studies, and validation.

**Related:** [collision guide](guides/collision_guide.md) · [transport guide](guides/transport_guide.md) · [PHYSICS.md](PHYSICS.md) · [roadmap](Janus_Architectural_Roadmap.md)

---

## End-to-end pipeline

```text
Geant4 collision (engines/geant4 + interactions/)
↓
temp/ → data/interactions/<run>/
        ├── simulation.root      (Seeds tree — transport input)
        ├── validation.root      (Validation tree — collision checks)
        ├── <run>_config.json
        └── particle_summary.txt
↓
transport/io.py  →  merged_seeds_cache_v6.npz (beside ROOT)
↓
experiments/transport/<name>.py  (scientific params + xt.Line)
↓
transport/pipeline.run(...)      (filter → convert → track → write)
↓
Xsuite tracking
↓
data/transport/run_<timestamp>/
        ├── transported_particles.npz
        ├── metrics.json + provenance.json
        └── plots + summary.txt
```

| Stage | Owner | Janus role |
|-------|-------|------------|
| Particle production | Geant4 (`engines/geant4/`, `interactions/`) | Configure, run, validate, package ROOT |
| Seed boundary | Janus (`transport/io.py`) | ROOT → `SeedArrays` / NPZ cache (p/p̄ only; no momentum cut) |
| Beam transport | Xsuite (`xpart` / `xtrack`) | Convert seeds, track caller-built `xt.Line`, write NPZ |
| Diagnostics | Janus (`transport/analysis/`) | Metrics, plots, summary from transport outputs |
| Studies | Janus (`transport/studies/`) | Parameter sweeps → CSV datasets |
| Optimization | Planned (future lab) | Consume study CSV + metrics |

Smoke experiments (`drift`, `quadrupole`, `dipole`) skip Geant4: they pass synthetic `SeedArrays` via `seeds=...`.

There is no custom Boris integrator, no YAML transport config, and no interactive visualization in the transport path.

**Single source of truth for transport:** every scientific parameter (species, momentum window, count, turns, output name/dir, beamline, initial conditions) lives in the experiment script under `experiments/transport/`. `pipeline.py`, `io.py`, and `xsuite.py` only execute what they are given.

---

## Conceptual layout

| Concern | Location |
|---------|----------|
| Computational engines | `engines/geant4/` (in-repo Geant4 app); Xsuite as external library via `transport/xsuite.py` |
| Scientific capabilities | `interactions/` (collisions), `transport/` (beam transport) |
| Study / sweep tooling | `transport/studies/` (framework infrastructure, not lab research) |
| Framework examples | `experiments/transport/` |
| Generated artifacts | `data/interactions/`, `data/transport/` |
| Validation | `interactions/validation/`, `tests/transport/` |

A future independent research lab may depend on Janus for engines, capabilities, studies tooling, and validation — without Janus absorbing optimization campaigns or research datasets.

---

## Repository layout

```text
janus/
├── engines/
│   └── geant4/                 # C++ Geant4 collision engine
├── interactions/
│   ├── run.py                  # Collision entry: python interactions/run.py
│   ├── run_batches.py
│   ├── config.json
│   ├── interface.py            # Drive Geant4; package temp/ → data/
│   ├── analyze.py
│   └── validation/             # Collision Phases 1–4
├── transport/
│   ├── main.py                 # CLI: --experiment <name>
│   ├── pipeline.py             # Orchestration only
│   ├── io.py                   # ROOT → NPZ seeds
│   ├── xsuite.py               # Particles conversion + tracking + NPZ write
│   ├── analysis/               # Metrics + plots + summary
│   ├── studies/                # Parameter sweeps + CSV export
│   └── provenance.py
├── experiments/
│   └── transport/              # Example scripts (params live here)
├── data/                       # Generated artifacts (gitignored)
│   ├── interactions/
│   └── transport/
├── tests/transport/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PHYSICS.md
│   ├── Janus_Architectural_Roadmap.md
│   ├── guides/
│   ├── validation/
│   └── assets/
└── requirements.txt
```

---

## Stage details

### 0. Collision (Geant4)

- Configure via `interactions/config.json`.
- Run: `python interactions/run.py` (see [collision guide](guides/collision_guide.md)).
- Geant4 writes under `temp/`; `interactions/interface.py` packages into `data/interactions/<run_name>/`.
- Validate before transport: see [collision validation](validation/collision_validation.md).

### 1. Seed extraction

Transport reads `data/interactions/*/simulation.root` → tree **`Seeds`**.

| ROOT branch | Meaning | Units in ROOT |
|-------------|---------|---------------|
| `pdg_code` | PDG ID | integer |
| `start_x`, `start_y`, `start_z` | Position | mm |
| `start_px`, `start_py`, `start_pz` | Momentum | MeV/c |

IO keeps only proton / antiproton (PDG ±2212), converts to SI / MeV/c arrays, and caches `merged_seeds_cache_v6.npz`. Momentum windows are **not** applied here — that is the experiment’s `momentum_slice`.

### 2. Experiment + orchestration

```bash
python -m transport.main --experiment <name>
```

`main.py` imports `experiments.transport.<name>` and calls `main()`. The experiment builds `xt.Line`, sets all scientific parameters, and calls `pipeline.run(...)`.

### 3. Conversion and tracking

`transport/xsuite.py` maps `SeedArrays` → `xpart.Particles`:

- `x`, `y` — transverse position [m]
- `px`, `py` — \(p_{x,y}/p_0\)
- `zeta` — 0 at injection
- `delta` — \(|p|/p_0 - 1\)
- `p0c` — median \(|p|c\) unless overridden
- `mass0` — proton / antiproton mass

Tracking uses `line.build_tracker()` and `line.track(...)`.

### 4. Outputs and analysis

Each run writes under `data/transport/run_<timestamp>/` (see Data contracts). `transport/analysis` produces metrics and plots automatically after tracking.

### Call graph (Geant4-seeded)

```text
python -m transport.main --experiment geant4_antiproton
→ experiments.transport.geant4_antiproton.main()
→ pipeline.run(...)
    ├─ load_geant4_seeds()          # or use seeds=... for mock data
    ├─ _apply_momentum_slice(...)
    ├─ seeds_to_xparticles(...)
    ├─ run_transport(...)           # Xsuite track
    ├─ write_transport_output(...)
    └─ analyze(...)
```

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
data/transport/run_<timestamp>/
├── transported_particles.npz
├── metrics.json
├── provenance.json
├── beam_xy.png
├── phase_space.png
├── momentum_histogram.png
├── beamline.png
└── summary.txt
```

NPZ fields include final `x`, `px`, `y`, `py`, `zeta`, `delta`, `state`, `alive_mask`, `at_element`, `p0c_eV`, `mass0_eV`, `q0`, `start_z`, and `metadata_json`.

### Frozen public contracts

| Contract | Owner |
|----------|-------|
| `SeedArrays` | `transport/io.py` |
| `pipeline.run(...)` | `transport/pipeline.py` |
| `TransportResult` | `transport/xsuite.py` |
| `TransportMetrics` | `transport/analysis/metrics.py` |
| Transported NPZ keys | `transport/xsuite.py` |
| Experiment scripts | `experiments/transport/` |
| Study runner | `transport/studies/runner.py` |

---

## Design principles

1. **Geant4 owns production; Xsuite owns tracking.** Janus does not reimplement hadronic physics or standard magnet maps.
2. **Experiments are Python, not YAML.** A study is a script that builds `xt.Line`, defines every scientific parameter, and calls `run`.
3. **Studies tooling stays in Janus.** `transport/studies/` generates configuration sweeps and datasets; research campaigns belong in a future lab.
4. **Thin boundary layer.** `SeedArrays` and `seeds_to_xparticles` bridge Geant4 units to Xsuite.
5. **Generated data stays out of source trees.** Simulation products live under `data/`.
6. **Analysis is offline and automatic.** Diagnostics read the NPZ written after tracking.

---

## How to run (quick reference)

```bash
pip install -r requirements.txt

# Collision (requires built Geant4 engine)
python interactions/run.py

# Transport — mock / synthetic seeds
python -m transport.main --experiment drift

# Transport — Geant4 seeds
python -m transport.main --experiment geant4_antiproton

# Tests
pytest tests/transport/
```

Full instructions: [Geant4 install](guides/geant4_installation.md) · [collision guide](guides/collision_guide.md) · [transport guide](guides/transport_guide.md).

---

## Dependencies

```bash
pip install -r requirements.txt
```

Primary packages: `xsuite`, `numpy`, `uproot`, `matplotlib`, `pytest`. Collision validation also needs `particle` and `awkward`.
