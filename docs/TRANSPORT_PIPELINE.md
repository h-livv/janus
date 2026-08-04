# Janus Transport Pipeline

**Audience:** contributors who know Geant4 and particle physics, but not Janus or Xsuite.

**Scope:** the transport path as implemented today — from Geant4 seed production through Xsuite tracking to analysis products.

**Related docs:** [ARCHITECTURE.md](ARCHITECTURE.md) (summary), [transport_guide.md](transport_guide.md) (how to run studies), [PHYSICS.md](PHYSICS.md) (physical models).

---

## 1. Executive Summary

Janus does not implement its own particle tracker. It orchestrates two external engines:

| Stage | Engine | Janus role |
|-------|--------|------------|
| Particle production | Geant4 | Configure, run, validate; extract seed kinematics |
| Beam transport | Xsuite | Convert seeds → `xpart.Particles`; track through `xtrack.Line` |
| Diagnostics | Janus | Read transported NPZ; write plots and summary |

The complete transport workflow is:

```text
Geant4 collision
↓
temp/ → interactions/runs/<run>/simulation.root   (Seeds tree)
↓
transport/io.py                           (ROOT → seed NPZ cache v6)
↓
SeedArrays                                (in-memory seed container)
↓
experiment supplies scientific params + xt.Line
↓
pipeline.run → momentum_slice → seeds_to_xparticles → track
↓
transported_particles.npz
↓
transport/analysis                        (plots + summary.txt)
```

A transport “configuration” is an ordinary Python script under `transport/experiments/`. It constructs an `xtrack.Line`, sets **every** scientific parameter as plain variables (`particle`, `count`, `momentum_slice`, `num_turns`, `output_name`, `output_dir`, …), and calls `pipeline.run(...)`. Those values are the single source of truth.

There is no YAML transport config, no custom Boris integrator, and no interactive 3D visualization in this path.

---

## 2. End-to-End Data Flow

Execution order for a Geant4-seeded study (e.g. `geant4_antiproton`):

| # | Stage | Input | Output | Owner | Purpose |
|---|-------|-------|--------|-------|---------|
| 0 | Geant4 run | `interactions/config.json` | `simulation.root` + `validation.root` | `engine/` + `interactions/` | Produce secondaries; package `temp/` → `runs/` |
| 1 | CLI / experiment | `--experiment` name | call to `run(...)` with all params | `main.py`, `experiments/` | Select study; define params; build `xt.Line` |
| 2 | Load seeds | latest ROOT (or v6 cache) | `SeedArrays` | `io.py` | Extract p/p̄ seed pool (no momentum cut) |
| 3 | Momentum slice | experiment `(p_min, p_max)` GeV/c | filtered `SeedArrays` | `pipeline.py` | Experiment kinematic selection |
| 4 | Particle conversion | `SeedArrays` | `xpart.Particles` + meta | `xsuite.py` | Map to Xsuite coordinates |
| 5 | Attach reference | `Particles`, `Line` | `line.particle = …` | `pipeline.py` | Give the line a reference particle |
| 6 | Track | `Line`, `Particles` | updated `Particles` | Xsuite via `run_transport` | Propagate through elements |
| 7 | Write NPZ | `TransportResult` | `transported_particles.npz` | `xsuite.py` | Persist final state |
| 8 | Analyze | transported NPZ | PNGs + `summary.txt` | `analysis/` | Diagnostics for the run |

Smoke experiments (`drift`, `quadrupole`, `dipole`) skip stages 0 and the ROOT path: they pass synthetic `SeedArrays` via `seeds=...`.

---

## 3. Geant4 Output

### Outside transport

These remain in the collision stage and are **not** part of the transport package:

- C++ Geant4 engine (`engine/`)
- Run orchestration (`interactions/run.py`, `run_batches.py`, `config.json`, `dependencies/`)
- Collision validation (`interactions/validation/validate.py`, `physical_validation.py`)

Geant4 first writes under project `temp/`; the Python interface moves outputs into `interactions/runs/<run_name>/` (`simulation.root`, `validation.root`, config snapshot, `particle_summary.txt`).

Transport begins only after a ROOT file with a `Seeds` tree exists.

### What transport consumes

Primary artifact:

```text
interactions/runs/<run_name>/simulation.root
```

Janus reads the ROOT group/tree **`Seeds`** via `uproot` (implemented in `transport/io.py` :: `_parse_single_root`).

| ROOT branch | Meaning | Units in ROOT |
|-------------|---------|---------------|
| `pdg_code` | PDG ID | integer |
| `start_x`, `start_y`, `start_z` | Birth position | mm |
| `start_px`, `start_py`, `start_pz` | Birth momentum | MeV/c |

### Filtering at extraction (guaranteed by implementation)

`_parse_single_root` keeps only:

1. **Species pool:** PDG `±2212` (proton / antiproton)

It does **not** apply a momentum window. Momentum selection is an experiment
parameter (`momentum_slice`) applied later in `pipeline.run`.

What those kinematics mean depends on `output.record_mode` in `interactions/config.json`:

| Mode | `Seeds` content |
|------|-----------------|
| `"Hit"` (default) | Target→Chamber boundary crossing |
| `"Birth"` | \(t=0\) secondary birth |

Then it converts:

| Quantity | Conversion |
|----------|------------|
| Position | mm → m (`× 1e-3`) |
| Momentum | kept as MeV/c |
| Gamma | \(E / m\) with \(m = 938.2720813\) MeV/\(c^2\) |
| Velocity | \(\vec{v} = \vec{p}\,c / E\) [m/s] |
| Charge | antiproton → −1, proton → +1 |

### Seed NPZ cache

Extracted arrays are cached beside the ROOT file:

```text
merged_seeds_cache_v6.npz
merged_seeds_manifest_v6.json
```

The manifest fingerprints ROOT files (size + mtime). Unchanged files are not re-parsed; new batches are merged incrementally. This behavior is implemented in `extract_cern_ad_seeds`.

| Seed NPZ key | Shape | Units | Required |
|--------------|-------|-------|----------|
| `positions` | (N, 3) | m | yes |
| `velocities` | (N, 3) | m/s | yes |
| `gammas` | (N,) | — | yes |
| `charges` | (N,) | ±1 | yes |
| `momenta_mevc` | (N, 3) | MeV/c | preferred (v6) |
| `start_z` | (N,) | m | optional metadata |

**Coordinate convention at this boundary:** Cartesian lab frame from Geant4 seed positions (Hit or Birth per `record_mode`). Absolute `start_z` is preserved as metadata; it does **not** shift the Xsuite beamline (particles are injected at the line entrance).

Older caches named `merged_seeds_cache_v4.npz` / `v5` are ignored; only `v6` is read. Set `DATAIO_VERBOSE=1` to enable `[DataIO]` extraction logs.

---

## 4. Transport Entry Point

### CLI

```bash
python -m transport.main --experiment <name>
```

`transport/main.py`:

1. Adds the project root to `sys.path`
2. Lists `transport/experiments/*.py` (excluding `__init__.py` and `_`-prefixed names)
3. Imports `transport.experiments.<name>`
4. Calls `module.main()`

There is no registry object — discovery is a directory listing.

### Experiment script

Example production study (`experiments/geant4_antiproton.py`):

1. Build `line = xt.Line(elements=[...])`
2. Set every scientific parameter as plain variables (`particle`, `count`, `momentum_slice`, `num_turns`, `output_name`, `output_dir`)
3. Call `run(...)` with those values; omit `seeds` → Geant4 load

Example smoke study (`experiments/drift.py`):

1. Build synthetic seeds with `single_particle_seeds(...)`
2. Build a one-element `xt.Line`
3. Call `run(..., seeds=seeds)` with the same explicit parameters

### Central orchestrator

All experiments converge on `transport.pipeline.run`. That function owns load → filter → convert → track → write → analyze. It does **not** invent scientific defaults.

---

## 5. NPZ Loading

### In-memory representation

Seeds are carried as a `SeedArrays` dataclass (`transport/io.py`):

| Field | Type | Role |
|-------|------|------|
| `positions` | float32 (N, 3) | \(x,y,z\) [m] |
| `velocities` | float32 (N, 3) | [m/s]; legacy fallback if momenta missing |
| `gammas` | float32 (N,) | Lorentz factor |
| `charges` | int8 (N,) | ±1 |
| `momenta_mevc` | float32 (N, 3) or None | preferred momentum [MeV/c] |
| `start_z` | float32 (N,) or None | original Geant4 \(z\) |
| `source_path` | str or None | ROOT or NPZ path |

**Why this shape:** it is a thin, array-oriented DTO between Geant4 extraction and Xsuite conversion. It is not an Xsuite object and not a particle class hierarchy.

### Load paths

| Function | When used |
|----------|-----------|
| `load_geant4_seeds()` | Default in `run()` when `seeds is None` — latest `simulation.root` via `extract_cern_ad_seeds` |
| `load_seed_npz(path)` | Explicit NPZ file (tests / file sources) |
| `single_particle_seeds(...)` | Synthetic smoke seeds |

`load_seed_npz` validates required keys, shapes, finiteness, and charge signs before returning `SeedArrays`.

### Experiment momentum filter

Before conversion, `_apply_momentum_slice` restricts seeds to the experiment's
`(p_min, p_max)` in **GeV/c** (converted to MeV/c internally). If the experiment
passes `momentum_slice=None`, no momentum filter is applied.

---

## 6. Xsuite Overview

### What Xsuite is

[Xsuite](https://xsuite.readthedocs.io/) is a CERN Python toolkit for accelerator beam dynamics. It provides lattice description, particle ensembles, and compiled tracking maps for CPU/GPU contexts.

Janus uses it as the **only** transport engine: no custom Lorentz integrator remains in the repository.

### Libraries Janus imports

Janus imports two Xsuite packages (via the `xsuite` dependency):

#### xtrack

| | |
|--|--|
| **Purpose** | Lattice elements and tracking |
| **Key objects used** | `xt.Line`, `xt.Drift`, `xt.Quadrupole`, `xt.Bend`; also `xt.PROTON_MASS_EV` |
| **How Janus uses it** | Experiments build `xt.Line` directly; `run_transport` calls `line.build_tracker()` and `line.track(particles, num_turns=...)` |

#### xpart

| | |
|--|--|
| **Purpose** | Particle ensemble containers |
| **Key object used** | `xp.Particles` |
| **How Janus uses it** | `seeds_to_xparticles` constructs one `Particles` object with reference quantities and per-particle coordinates |

No other Xsuite modules (MAD-X import, Twiss matching, collective effects, etc.) appear in the current Janus transport code.

---

## 7. Particle Conversion

Implemented in `transport/xsuite.py` :: `seeds_to_xparticles`.

### Step-by-step (guaranteed by implementation)

```text
SeedArrays
↓
charge / species filter
↓
optional count truncation
↓
resolve momenta_mevc
↓
choose p0c (median |p| × 1e6 → eV, unless overridden)
↓
map to x, px, y, py, zeta, delta
↓
xp.Particles(...)
```

### Filtering

| Rule | Behavior |
|------|----------|
| `charge_filter == "antiproton"` | keep `charges == -1` |
| `charge_filter == "proton"` | keep `charges == 1` |
| `charge_filter == "any"` | keep ±1 |
| Mixed signs after filter | **error** — single-species ensemble required |
| Charge vs `species` | must match `charge_of(species)` |

In `pipeline.run`, `charge_filter` is set from `particle` when `particle` is `"antiproton"` or `"proton"`.

### Momentum resolution

1. Prefer `seeds.momenta_mevc`
2. Else reconstruct from `gamma`, `mass_of(species)`, `velocities` (legacy path)

Absolute momentum: \(p = |\vec{p}|\) in MeV/c.

Reference momentum:

\[
p_0c\ [\mathrm{eV}] = \mathrm{median}(p)\,[\mathrm{MeV}/c] \times 10^6
\]

unless `p0c_eV` is passed explicitly.

### Coordinate mapping

| Xsuite field | Source | Units / meaning |
|--------------|--------|-----------------|
| `x` | `positions[:, 0]` | m |
| `y` | `positions[:, 1]` | m |
| `px` | \(p_x / p_0\) | dimensionless (normalized) |
| `py` | \(p_y / p_0\) | dimensionless |
| `zeta` | **0 for all particles** | longitudinal coordinate unused at injection |
| `delta` | \(p / p_0 - 1\) | relative momentum deviation |
| `mass0` | `xt.PROTON_MASS_EV` | eV/\(c^2\) (proton mass constant) |
| `q0` | `charge_of(species)` | elementary charge units |
| `p0c` | median / override | eV |

**Why each conversion exists:**

- Xsuite tracks with \(s\) as independent variable and normalized transverse momenta — not Geant4’s absolute Cartesian momenta.
- A single reference \(p_0\) defines the rigidity scale for the ensemble.
- `zeta = 0` because Geant4 seed time is not mapped in the current implementation (stated in conversion code).
- Absolute Geant4 `start_z` is kept in `ParticleConversionMeta.start_z` for output metadata only — it does not enter `Particles` coordinates.

### Return value

`(particles, ParticleConversionMeta)` where meta stores species, `q0`, `mass0_eV`, `p0c_eV`, `n_particles`, and `start_z`.

---

## 8. Beamline Construction

### Representation

The beamline is an **`xtrack.Line`**: an ordered list of Xsuite element objects.

Janus does **not** wrap elements in custom classes. Experiments construct the line:

```python
line = xt.Line(elements=[
    xt.Drift(length=5.0),
    xt.Quadrupole(length=1.0, k1=0.5),
    xt.Drift(length=2.0),
    xt.Quadrupole(length=1.0, k1=-0.5),
])
```

### Elements used in current experiments

| Element | Xsuite class | Typical parameters | Used in |
|---------|--------------|--------------------|---------|
| Drift | `xt.Drift` | `length` [m] | all examples |
| Quadrupole | `xt.Quadrupole` | `length`, `k1` [m⁻²] | quadrupole, geant4_antiproton |
| Bend / dipole | `xt.Bend` | `length`, `angle` [rad] | dipole |

### Magnetic horn

**Not implemented** in the current transport path. There is no horn element construction in `experiments/` or `xsuite.py`. Physics documentation describes horn fields conceptually; tracking would require an Xsuite field-map element that is not wired today.

### Why experiments build `xt.Line` directly

Guaranteed by the present architecture:

- No YAML → schema → builder chain
- No Janus element registry
- The experiment script *is* the configuration

`line_config_hash(line)` hashes element type and selected parameters (`length`, `k1`, `angle`) for output metadata only — it does not construct the line.

---

## 9. Tracking

Implemented in `transport/xsuite.py` :: `run_transport`.

### Call sequence (exact)

```text
if line.particle is None:
    line.particle = particles
line.build_tracker()
line.track(particles, num_turns=int(num_turns))
```

`pipeline.run` sets `line.particle = xparticles` before calling `run_transport`.

### Conceptual Xsuite behavior

At a high level (library operation, not a physics derivation):

1. **`build_tracker`** — compiles / prepares tracking kernels for the line’s elements on the active context (CPU by default in Janus; no custom context is passed).
2. **`track`** — advances each particle through the ordered elements once per turn for `num_turns` (supplied by the experiment — typically a single pass through a transfer line, not a storage ring).
3. Element maps update the particle coordinates in place (`x`, `px`, `y`, `py`, `zeta`, `delta`, and status fields such as `state`, `at_element`).

Janus does not inspect intermediate element-by-element monitors in the current code. Final particle arrays after `track` are what get written to disk.

### Return

A `TransportResult` holding the (mutated) `Particles`, the `Line`, conversion meta, beamline hash, and optional `source_path`.

---

## 10. Transport Output

Written by `write_transport_output` to:

```text
<run_outputs_dir>/transported_particles.npz
```

Default run directory: `transport/outputs/run_<YYYYMMDD_HHMMSS>/`.

Per-run artifacts also include `metrics.json` and `provenance.json` (see sections 11–12).

### Arrays in transported NPZ

| Key | Meaning |
|-----|---------|
| `x`, `y` | Final transverse positions [m] |
| `px`, `py` | Final normalized momenta |
| `zeta`, `delta` | Final longitudinal / momentum deviation |
| `state` | Xsuite particle state codes |
| `at_element` | Element index at stop |
| `alive_mask` | `state > 0` |
| `p0c_eV`, `mass0_eV`, `q0` | Reference scalars |
| `start_z` | Original Geant4 \(z\) [m] (metadata) |
| `metadata_json` | JSON string with experiment name, species, source path, beamline elements, hash, `"engine": "xsuite"` |

### Seed NPZ vs transported NPZ

| | Seed NPZ | Transported NPZ |
|--|----------|-----------------|
| Origin | Geant4 seed kinematics (Hit or Birth) | After Xsuite tracking |
| Coordinates | Cartesian \(x,y,z\), \(\vec{p}\) MeV/c | Xsuite \(x,p_x,\ldots\) |
| Purpose | Input to conversion | Optimization / analysis input |
| Filename | `merged_seeds_cache_v6.npz` (beside ROOT) | `transported_particles.npz` (run dir) |

---

## 11. Metrics and Analysis Pipeline

Triggered automatically when `write_npz=True` (default):

```text
write_transport_output(...)
↓
compute_transport_metrics(TransportResult)
↓
metrics.json + provenance.json
↓
transport.analysis.analyze(npz_path, metrics=...)
```

Metrics are defined over in-memory `TransportResult`; NPZ is persistence. Offline recomputation uses `metrics_from_npz(...)`.

| Output | Source |
|--------|--------|
| `metrics.json` | `TransportMetrics` from transport result |
| `provenance.json` | Run parameters, fingerprints, artifact paths |
| Plots + `summary.txt` | Presentation layer from metrics and NPZ arrays |

## 12. Analysis products

All plot products are derived from the transported NPZ — tracking is not re-run (`analysis/plots.py`). Summary text is generated from `TransportMetrics`, not independent formulas.

| Output | Function | Source fields |
|--------|----------|---------------|
| `beam_xy.png` | `plot_beam_xy` | alive `x`,`y` (plotted in mm) |
| `phase_space.png` | `plot_phase_space` | alive `x` vs `px` |
| `momentum_histogram.png` | `plot_momentum_histogram` | \(p = p_0c(1+\delta)/10^9\) GeV/c |
| `beamline.png` | `plot_beamline` | `metadata.beamline_elements` |
| `summary.txt` | `write_summary` | counts, transmission, mean/std \(p\), RMS \(x,y\) |

Summary quantities (as implemented):

- **Generated particles:** number of particles in the NPZ (tracked ensemble)
- **Transported particles:** `sum(alive_mask)`
- **Transmission:** transported / generated
- **RMS beam size:** \(\sqrt{\langle x^2\rangle}\), \(\sqrt{\langle y^2\rangle}\) over alive particles [m]

---

## 12. Complete Call Graph

Production path (`geant4_antiproton`):

```text
python -m transport.main --experiment geant4_antiproton
↓
main.main()
↓
importlib → transport.experiments.geant4_antiproton
↓
geant4_antiproton.main()
    builds xt.Line
    calls pipeline.run(line=..., particle=..., count=..., momentum_slice=...,
                       num_turns=..., output_name=..., output_dir=...)
↓
pipeline.run
    ├─ load_geant4_seeds()
    │     └─ get_latest_run_file()
    │     └─ extract_cern_ad_seeds([root])
    │           └─ _parse_single_root / NPZ cache
    ├─ _apply_momentum_slice(...)
    ├─ seeds_to_xparticles(...)
    ├─ line.particle = xparticles
    ├─ line_config_hash(line)
    ├─ run_transport(line, particles, ...)
    │     ├─ line.build_tracker()
    │     └─ line.track(particles, num_turns=...)
    ├─ write_transport_output(...) → transported_particles.npz
    └─ analyze(npz_path)
          ├─ plot_beam_xy
          ├─ plot_phase_space
          ├─ plot_momentum_histogram
          ├─ plot_beamline
          └─ write_summary
```

Smoke path (`drift`) differs only in that `seeds=single_particle_seeds(...)` is passed, so `load_geant4_seeds` is skipped.

---

## 13. Repository Structure

```text
transport/
├── main.py           # CLI discovery + import experiment.main()
├── pipeline.py       # run(): load, filter, convert, track, write, analyze
├── io.py             # ROOT↔NPZ seed boundary; SeedArrays; species table
├── xsuite.py         # seeds_to_xparticles; run_transport; write_transport_output
├── analysis/
│   ├── __init__.py   # exports analyze
│   └── plots.py      # NPZ-only diagnostics
└── experiments/
    ├── drift.py
    ├── quadrupole.py
    ├── dipole.py
    └── geant4_antiproton.py
```

| Module | Owns |
|--------|------|
| `main.py` | Experiment selection only |
| `experiments/*` | **Single source of truth** for scientific params + `xt.Line` + `run(...)` |
| `pipeline.py` | Orchestration only (no scientific defaults) |
| `io.py` | Geant4 ROOT extraction / seed NPZ cache / synthetic seeds (load only) |
| `xsuite.py` | Conversion, tracking, transported NPZ (transport only) |
| `analysis/` | Post-processing from transported NPZ |

Outside transport but upstream:

| Path | Role |
|------|------|
| `engine/` | Geant4 C++ collision engine |
| `interactions/run.py`, `dependencies/` | Configure/run Geant4; package `temp/` → `runs/` |
| `interactions/validation/` | Collision Phases 1–3 (`validate.py`) and Phase 4 (`physical_validation.py`) |

---

## 14. Design Philosophy

As realized in the current tree:

1. **Geant4 owns production; Xsuite owns tracking.** Janus does not reimplement hadronic physics or magnetic maps for standard magnets.
2. **Experiments are Python, not YAML.** A study is a script that builds `xt.Line`, defines every scientific parameter, and calls `run`. Schema/loader/builder layers were removed.
3. **Single source of truth.** Species, momentum window, count, turns, and outputs live only in the experiment file. Pipeline/IO/Xsuite do not invent them.
4. **Prefer direct Xsuite objects.** No Janus `Drift`/`Dipole` classes, no element factories, no solver adapters.
5. **Thin boundary layer.** `SeedArrays` and `seeds_to_xparticles` exist only to bridge Geant4 units/coordinates to Xsuite.
6. **Small surface area.** Transport is a handful of modules; the obsolete custom Boris integrator and Janus-owned tracking validation were deleted. Collision validation under `interactions/validation/` remains separate.
7. **Analysis is offline and automatic.** Diagnostics read the NPZ written after tracking; they do not participate in propagation.

---

## 15. Future Extension Points

Without changing the present architecture, natural attachment points are:

| Extension | Where |
|-----------|--------|
| New beamline studies | New file under `transport/experiments/` |
| New Xsuite elements (e.g. horn field map) | Construct in the experiment’s `xt.Line`; tracking stays in `run_transport` |
| Extra diagnostics | New functions in `analysis/plots.py` called from `analyze` |
| Optimization | Consume `transported_particles.npz` (and optionally `summary.txt`) downstream |
| Alternate seed sources | Produce `SeedArrays` and pass `seeds=` into `run` |

---

## Quick reference: how to run

```bash
pip install -r requirements.txt
python -m transport.main --experiment drift                 # synthetic smoke
python -m transport.main --experiment geant4_antiproton     # needs Geant4 ROOT
```

See [transport_guide.md](transport_guide.md) for writing a new experiment script.
