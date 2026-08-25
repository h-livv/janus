# Janus Architecture

Janus is an orchestration layer for antimatter production and beam transport. It does not reimplement hadronic physics or magnetic tracking: **Geant4** owns particle production, **Xsuite** owns beam transport, and Janus owns configuration, seed inherit, and the five-stage transport object.

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
transport/config.json            (topology instructions)
↓
Transport
    load_topology()
    construct_beamline()         → xt.Line
    inherit_particles()          → positions, momenta, charges
    run()                        → track + write
↓
data/transport/run_<timestamp>/
        ├── transported_particles.npz
        └── topology.json
```

| Stage | Owner | Janus role |
|-------|-------|------------|
| Particle production | Geant4 (`engines/geant4/`, `interactions/`) | Configure, run, validate, package ROOT |
| Topology | `transport/config.json` + `Transport.beamline` | Element list and run cuts |
| Construct | `Transport.construct_beamline()` | Map topology → `xt.Line` |
| Inherit | `transport/io.py` | One `Seeds` tree → arrays (p/p̄ only; no momentum cut) |
| Track | Xsuite | `line.track(...)` |
| Output | `Transport.run()` | NPZ + `topology.json` |

Studies, metrics, and plots are **callers** of `Transport`, not modules inside it. A future sweep is a Python loop that mutates topology and calls `run()` again.

There is no custom Boris integrator, no YAML, and no automatic diagnostics in the transport path.

---

## Conceptual layout

| Concern | Location |
|---------|----------|
| Computational engines | `engines/geant4/` (in-repo Geant4 app); Xsuite as external library |
| Scientific capabilities | `interactions/` (collisions), `transport/` (beam transport) |
| Generated artifacts | `data/interactions/`, `data/transport/` |
| Validation | `interactions/validation/`, `tests/transport/` |

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
│   ├── interface.py            # Beamline + Transport (five stages)
│   ├── io.py                   # One ROOT Seeds parse
│   ├── run.py                  # load_topology(); run()
│   └── config.json             # Default topology + cuts
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

### 1. Topology instructions

`transport/config.json` (or Python overrides on `Transport`) holds an ordered element list plus run cuts: `particle`, `count`, `momentum_slice` (GeV/c), `num_turns`, `source`, `output_dir`.

This is data, not an `xt.Line`. A study later changes a field (for example `k1`) and reconstructs.

### 2. Construct beamline

`construct_beamline()` maps each element dict through a small type map (`Drift`, `Quadrupole`, `Bend` / `SBend`) to Xsuite objects. Unknown types fail loudly. Adding a magnet type is a local registry change.

### 3. Inherit particle data

Transport reads **one** `data/interactions/*/simulation.root` → tree **`Seeds`** (explicit `source` or the newest file).

| ROOT branch | Meaning | Units in ROOT |
|-------------|---------|---------------|
| `pdg_code` | PDG ID | integer |
| `start_x`, `start_y`, `start_z` | Position | mm |
| `start_px`, `start_py`, `start_pz` | Momentum | MeV/c |

IO keeps proton / antiproton (PDG ±2212) and converts mm→m. Momentum windows and species selection happen at `run()`, so inherit can run once and be reused across topologies.

Synthetic tests set `positions`, `momenta_mevc`, and `charges` on `Transport` and skip ROOT.

### 4. Forward simulation

`run()` converts selected arrays to `xpart.Particles`:

- `x`, `y` — transverse position [m]
- `px`, `py` — \(p_{x,y}/p_0\)
- `zeta` — 0 at injection
- `delta` — \(|p|/p_0 - 1\)
- `p0c` — median \(|p|c\) of the selected ensemble
- `mass0` — `xt.PROTON_MASS_EV`

Then `line.build_tracker()` and `line.track(...)`. Each `run()` builds a fresh line and a fresh particle ensemble from the inherited arrays.

### 5. Output data

Each run writes under `data/transport/run_<timestamp>/`.

### Call graph

```text
python transport/run.py
→ Transport.load_topology()
→ Transport.run()
    ├─ construct_beamline()
    ├─ inherit_particles()      # skipped if arrays already set
    ├─ convert + line.track
    └─ write NPZ + topology.json
```

---

## Data contracts

### Seed recording mode

`interactions/config.json` → `output.record_mode`:

| Mode | What `Seeds` stores |
|------|---------------------|
| `"Hit"` (default) | Kinematics at Target→Chamber boundary crossing |
| `"Birth"` | \(t=0\) birth kinematics of secondaries |

Transport injects particles at the line entrance regardless of absolute `start_z`.

### Transported run directory

```text
data/transport/run_<timestamp>/
├── transported_particles.npz
└── topology.json
```

NPZ fields: `x`, `px`, `y`, `py`, `zeta`, `delta`, `state`, `p0c_eV`, `mass0_eV`, `q0`.

`topology.json` is the instructions actually used (beamline + cuts + source). It is the study-facing record, not a provenance subsystem.

### Frozen public contracts

| Contract | Owner |
|----------|-------|
| `Beamline` + `Transport` | `transport/interface.py` |
| `load_topology` / `construct_beamline` / `inherit_particles` / `run` | `transport/interface.py` |
| Default topology JSON | `transport/config.json` |
| Transported NPZ keys | `Transport._write_output` |
| `topology.json` | same run directory |

---

## Design principles

1. **Geant4 owns production; Xsuite owns tracking.** Janus does not reimplement hadronic physics or standard magnet maps.
2. **Five named stages.** Topology is data; construct, inherit, track, and write are separate methods so a future study can inherit once and loop the rest.
3. **Thin inherit.** One ROOT file → three arrays. No seed cache, no public `SeedArrays`.
4. **Studies are callers.** Parameter sweeps belong in scripts that use `Transport`, not in a `transport/studies/` package.
5. **Generated data stays out of source trees.** Simulation products live under `data/`.

---

## How to run (quick reference)

```bash
pip install -r requirements.txt

# Collision (requires built Geant4 engine)
python interactions/run.py

# Transport (requires data/interactions/*/simulation.root)
python transport/run.py

# Tests (synthetic particles; no Geant4 required)
pytest tests/transport/
```

Full instructions: [Geant4 install](guides/geant4_installation.md) · [collision guide](guides/collision_guide.md) · [transport guide](guides/transport_guide.md).

---

## Dependencies

```bash
pip install -r requirements.txt
```

Primary packages: `xsuite`, `numpy`, `uproot`, `matplotlib`, `pytest`. Collision validation also needs `particle` and `awkward`.
