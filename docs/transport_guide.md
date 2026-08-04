# Transport Experiment Guide

This guide explains how to define a transport study and run it in Janus.

Janus does **not** use YAML or JSON experiment configs for transport.
A configuration is an ordinary Python script under `transport/experiments/`.

Every scientific parameter lives in that script — nowhere else.
The pipeline, IO, and Xsuite layers only execute what they are given.

---

## Prerequisites

From the repository root:

```bash
pip install -r requirements.txt
```

For Geant4-seeded studies you also need:

1. A built Geant4 Janus engine (`engine/`)
2. At least one completed collision run under `interactions/runs/*/simulation.root`

Smoke studies such as `drift` do not require Geant4 output.

---

## Quick start

```bash
# Single-particle drift smoke test
python -m transport.main --experiment drift

# Quadrupole / bend smoke tests
python -m transport.main --experiment quadrupole
python -m transport.main --experiment dipole

# Geant4 antiproton seeds through a short FODO-like line
python -m transport.main --experiment geant4_antiproton
```

You can also execute a script directly:

```bash
python -m transport.experiments.drift
```

Outputs appear in:

```text
transport/outputs/run_<timestamp>/
```

---

## What an experiment script is

An experiment script:

1. Builds an `xtrack.Line` from Xsuite elements
2. Sets every scientific parameter as plain Python variables
3. Calls `run(...)` with those values

Minimal Geant4-seeded example:

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
    output_name = "my_study"
    output_dir = "transport/outputs"

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

Save this as `transport/experiments/my_study.py`, then:

```bash
python -m transport.main --experiment my_study
```

`main.py` discovers every `*.py` module in `transport/experiments/` (except `__init__.py`).
Each module must define `main()`.

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

- **Geant4 (production):** omit `seeds`. Janus loads the latest `interactions/runs/*/simulation.root` and caches proton/antiproton seed arrays (`merged_seeds_cache_v6.npz`). IO applies **no** momentum cut. The experiment’s `particle`, `momentum_slice`, and `count` select the beam.
- **Synthetic (smoke tests):** build seeds with `transport.io.single_particle_seeds(...)` and pass `seeds=...` (see `transport/experiments/drift.py`).

Default collision config uses `"record_mode": "Hit"`: `Seeds` are Target→Chamber boundary states, not necessarily \(t=0\) birth. See [collision_validation.md](collision_validation.md).

`momentum_slice` requires `momenta_mevc` on the seed arrays (present in v6 caches). Older caches without that key will error — delete stale `merged_seeds_cache_v4.npz` / `v5` files if needed; only `v6` is read.

To see `[DataIO]` extraction logs:

```bash
DATAIO_VERBOSE=1 python -m transport.main --experiment geant4_antiproton
```

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
transport/outputs/run_<timestamp>/
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
| `metrics.json` | Structured observables (`transmission`, RMS sizes, momentum spread, etc.) |
| `provenance.json` | Run ID, parameters, fingerprints, artifact paths |
| `beam_xy.png` | Transverse profile \(x\)–\(y\) |
| `phase_space.png` | Horizontal phase space \(x\)–\(p_x/p_0\) |
| `momentum_histogram.png` | Absolute momentum spectrum |
| `beamline.png` | Static element schematic |
| `summary.txt` | Human-readable summary from `TransportMetrics` |

Diagnostics are produced automatically by `transport.analysis`.

---

## Computational studies

Parameter sweeps use `transport/studies/`:

```text
Study → Parameter Generator → Experiment Factory → pipeline.run(...)
```

The Study orchestrates many runs and writes `study_results.csv`. The Experiment Factory remains responsible for building `xt.Line` and calling `run(...)`.

Example:

```bash
python -m transport.experiments.study_drift_length
```

Study CSV rows reference per-run `metrics.json` and `provenance.json` paths.

---

## End-to-end production workflow

1. **Configure and run Geant4** (`interactions/config.json`, then `python interactions/run.py`). Set `"interactive": false` for headless runs.

2. **Validate collision output:**

   ```bash
   python interactions/validation/validate.py              # Phases 1–3
   python interactions/validation/physical_validation.py   # Phase 4 plots
   ```

   See [collision_validation.md](collision_validation.md).

3. **Write or edit a transport experiment** under `transport/experiments/`.
   All scientific parameters go in that file.

4. **Run transport:**

   ```bash
   python -m transport.main --experiment my_study
   ```

5. **Inspect** `transport/outputs/run_<timestamp>/summary.txt` and the PNG diagnostics.

---

## Checklist for a new study

1. Create `transport/experiments/<name>.py`
2. Define `line`, `particle`, `count`, `momentum_slice`, `num_turns`, `output_name`, `output_dir`
3. Implement `main()` that calls `run(...)` with those values
4. Run `python -m transport.main --experiment <name>`
5. Confirm outputs under `transport/outputs/run_*/`

---

## Related docs

- [Transport pipeline](TRANSPORT_PIPELINE.md) — authoritative end-to-end walkthrough
- [Architecture](ARCHITECTURE.md) — pipeline layout and NPZ schemas
- [Transport validation](transport_validation.md) — tests and smoke checks
- [Physics](PHYSICS.md) — physical models
- [Geant4 installation](geant4_installation.md) — building the collision engine
- [Collision validation](collision_validation.md) — Geant4 validation
