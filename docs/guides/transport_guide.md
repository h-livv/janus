# Transport Pipeline Guide

How to run and author transport studies in Janus — with **mock / synthetic seeds** or **existing Geant4 collision data**.

Janus does **not** use YAML or JSON for transport configs. A study is an ordinary Python script under `experiments/transport/`. Every scientific parameter lives in that script; `pipeline.py`, `io.py`, and `xsuite.py` only execute what they are given.

**Related:** [architecture](../ARCHITECTURE.md) · [collision guide](collision_guide.md) · [transport validation](../validation/transport_validation.md) · [PHYSICS.md](../PHYSICS.md)

---

## Prerequisites

```bash
pip install -r requirements.txt
```

| Path | Needs |
|------|--------|
| Mock / smoke (`drift`, `quadrupole`, `dipole`) | Python deps only |
| Geant4-seeded (`geant4_antiproton`, custom) | At least one `data/interactions/*/simulation.root` ([collision guide](collision_guide.md)) |

---

## Quick start

### Mock data (no Geant4)

```bash
python -m transport.main --experiment drift
python -m transport.main --experiment quadrupole
python -m transport.main --experiment dipole
```

Or run a module directly:

```bash
python -m experiments.transport.drift
```

These scripts build synthetic `SeedArrays` with `transport.io.single_particle_seeds(...)` and pass `seeds=...` into `run(...)`.

### Existing Geant4 data

```bash
# Requires data/interactions/*/simulation.root
python -m transport.main --experiment geant4_antiproton
```

Omit `seeds` in the experiment: the pipeline loads the latest collision run and applies the experiment’s `particle`, `momentum_slice`, and `count`.

Verbose seed extraction:

```bash
DATAIO_VERBOSE=1 python -m transport.main --experiment geant4_antiproton
```

Outputs appear in:

```text
data/transport/run_<timestamp>/
```

---

## What an experiment script is

1. Builds an `xtrack.Line` from Xsuite elements
2. Sets every scientific parameter as plain Python variables
3. Calls `run(...)` with those values

### Mock-data example

```python
import xtrack as xt

from transport.io import single_particle_seeds
from transport.pipeline import run


def main():
    line = xt.Line(elements=[xt.Drift(length=10.0)])

    particle = "antiproton"
    count = 1
    momentum_slice = None
    num_turns = 1
    output_name = "drift"
    output_dir = "data/transport"

    seeds = single_particle_seeds(
        particle=particle,
        position=[0.001, 0.0, 0.0],
        velocity=[0.0, 0.0, 299492818.0],
        gamma=3.82,
    )

    run(
        line=line,
        particle=particle,
        count=count,
        momentum_slice=momentum_slice,
        num_turns=num_turns,
        output_name=output_name,
        output_dir=output_dir,
        seeds=seeds,
    )


if __name__ == "__main__":
    main()
```

### Geant4-seeded example

```python
import xtrack as xt
from transport.pipeline import run


def main():
    line = xt.Line(
        elements=[
            xt.Drift(length=5.0),
            xt.Quadrupole(length=1.0, k1=0.5),
            xt.Drift(length=2.0),
            xt.Quadrupole(length=1.0, k1=-0.5),
        ]
    )

    particle = "antiproton"
    count = 1000
    momentum_slice = (3.48, 3.68)  # GeV/c
    num_turns = 1
    output_name = "geant4_antiproton"
    output_dir = "data/transport"

    run(
        line=line,
        particle=particle,
        count=count,
        momentum_slice=momentum_slice,
        num_turns=num_turns,
        output_name=output_name,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
```

Save as `experiments/transport/my_study.py`, then:

```bash
python -m transport.main --experiment my_study
```

`main.py` discovers every `*.py` module in `experiments/transport/` (except `__init__.py` and `_`-prefixed names). Each module must define `main()`.

---

## `run(...)` parameters

Scientific parameters are **required** from the experiment (no hidden defaults):

| Parameter | Meaning |
|-----------|---------|
| `line` | Caller-built `xtrack.Line` |
| `particle` | Species name; also selects charge (`antiproton` → −1, `proton` → +1) |
| `count` | Max particles to track (`None` = all selected seeds) |
| `momentum_slice` | `(p_min, p_max)` in **GeV/c**, or `None` for no cut |
| `num_turns` | Xsuite tracking turns through the line |
| `output_name` | Label stored in output metadata |
| `output_dir` | Parent directory for timestamped run folders |

Optional execution knobs (not scientific):

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `seeds` | Optional seed arrays; if omitted, load latest Geant4 run | `None` |
| `p0c_eV` | Optional reference momentum override [eV] | median of seeds |
| `write_npz` | Write NPZ + analysis products | `True` |
| `run_outputs_dir` | Exact output folder (tests); else `output_dir/run_<timestamp>` | `None` |

### Seed sources

- **Geant4 (production):** omit `seeds`. Janus loads the latest `data/interactions/*/simulation.root` and caches proton/antiproton arrays (`merged_seeds_cache_v6.npz`). IO applies **no** momentum cut. The experiment’s `particle`, `momentum_slice`, and `count` select the beam.
- **Mock / synthetic:** build seeds with `transport.io.single_particle_seeds(...)` and pass `seeds=...` (see `experiments/transport/drift.py`).

Default collision config uses `"record_mode": "Hit"`: `Seeds` are Target→Chamber boundary states, not necessarily \(t=0\) birth. See [collision validation](../validation/collision_validation.md).

`momentum_slice` requires `momenta_mevc` on the seed arrays (present in v6 caches). Older caches without that key will error — delete stale `merged_seeds_cache_v4.npz` / `v5` files if needed; only `v6` is read.

---

## Building the beamline

Use Xsuite elements directly:

```python
xt.Drift(length=10.0)                 # meters
xt.Quadrupole(length=1.0, k1=0.5)     # k1 in m^-2
xt.Bend(length=2.0, angle=0.01)       # angle in radians
```

```python
line = xt.Line(elements=[
    xt.Drift(length=5.0),
    xt.Quadrupole(length=1.0, k1=0.5),
    xt.Bend(length=2.0, angle=0.01),
])
```

Unsupported custom Janus elements (for example a magnetic horn) are not available until wired through an Xsuite field-map element.

---

## Outputs

Every successful run with `write_npz=True` writes:

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

| File | Contents |
|------|----------|
| `transported_particles.npz` | Final Xsuite coordinates, alive mask, reference `p0c`, metadata |
| `metrics.json` | Structured observables (`transmission`, RMS sizes, momentum spread, …) |
| `provenance.json` | Run ID, parameters, fingerprints, artifact paths |
| `beam_xy.png` | Transverse profile \(x\)–\(y\) |
| `phase_space.png` | Horizontal phase space \(x\)–\(p_x/p_0\) |
| `momentum_histogram.png` | Absolute momentum spectrum |
| `beamline.png` | Static element schematic |
| `summary.txt` | Human-readable summary from `TransportMetrics` |

Diagnostics are produced automatically by `transport.analysis`. Schemas: [architecture](../ARCHITECTURE.md).

---

## Computational studies

Parameter sweeps use `transport/studies/` (framework sweep / dataset tooling):

```text
Study → Parameter Generator → Experiment Factory → pipeline.run(...)
```

The Study orchestrates many runs and writes `study_results.csv`. The Experiment Factory builds `xt.Line` and calls `run(...)`.

Example (mock seeds):

```bash
python -m experiments.transport.study_drift_length
```

---

## End-to-end production workflow

1. **Build Geant4 engine** — [geant4_installation.md](geant4_installation.md)
2. **Configure and run collision** — [collision_guide.md](collision_guide.md) (`interactions/config.json`, then `python interactions/run.py`)
3. **Validate collision output:**

   ```bash
   python interactions/validation/validate.py
   python interactions/validation/physical_validation.py
   ```

4. **Write or edit** a transport experiment under `experiments/transport/`
5. **Run transport:**

   ```bash
   python -m transport.main --experiment my_study
   ```

6. **Inspect** `data/transport/run_<timestamp>/summary.txt` and the PNG diagnostics

For development without collision data, start from the mock-data path above.

---

## Checklist for a new study

1. Create `experiments/transport/<name>.py`
2. Define `line`, `particle`, `count`, `momentum_slice`, `num_turns`, `output_name`, `output_dir`
3. Choose seed source: `seeds=...` (mock) or omit `seeds` (latest Geant4 run)
4. Implement `main()` that calls `run(...)` with those values
5. Run `python -m transport.main --experiment <name>`
6. Confirm outputs under `data/transport/run_*/`

---

## Related docs

- [Architecture](../ARCHITECTURE.md) — full pipeline, layout, data contracts
- [Collision guide](collision_guide.md) — run Geant4 studies
- [Geant4 installation](geant4_installation.md) — build the collision engine
- [Transport validation](../validation/transport_validation.md) — tests and smoke checks
- [Collision validation](../validation/collision_validation.md) — Geant4 Phases 1–4
- [Physics](../PHYSICS.md) — physical models
- [Roadmap](../Janus_Architectural_Roadmap.md) — future research infrastructure
