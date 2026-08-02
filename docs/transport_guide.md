# Transport Experiment Guide

This guide explains how to define a transport study and run it in Janus.

Janus does **not** use YAML or JSON experiment configs for transport.
A configuration is an ordinary Python script under `transport/experiments/`.

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

List and run a built-in experiment:

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
2. Sets plain Python variables (`particle`, `count`, `momentum_slice`, …)
3. Calls `run(...)`

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
    name = "my_study"

    run(
        line=line,
        particle=particle,
        count=count,
        momentum_slice=momentum_slice,
        name=name,
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

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `line` | Caller-built `xtrack.Line` | required |
| `particle` | Species name; also selects charge (`antiproton` → −1, `proton` → +1) | `"antiproton"` |
| `count` | Max particles to track (`None` = all selected seeds) | `None` |
| `momentum_slice` | Optional `(p_min, p_max)` in **GeV/c** | `None` |
| `name` | Label stored in output metadata | `"transport"` |
| `output_dir` | Parent directory for run folders | `"transport/outputs"` |
| `seeds` | Optional seed arrays; if omitted, load latest Geant4 run | `None` |
| `num_turns` | Xsuite tracking turns through the line | `1` |
| `p0c_eV` | Optional reference momentum override [eV] | median of seeds |
| `write_npz` | Write NPZ + analysis products | `True` |

### Seed sources

- **Geant4 (production):** omit `seeds`. Janus loads the latest `interactions/runs/*/simulation.root`, caches NPZ seeds, and filters by `particle` / `momentum_slice` / `count`.
- **Synthetic (smoke tests):** build seeds with `transport.io.single_particle_seeds(...)` and pass `seeds=...` (see `transport/experiments/drift.py`).

---

## Building the beamline

Use Xsuite elements directly. Common ones:

```python
xt.Drift(length=10.0)                 # meters
xt.Quadrupole(length=1.0, k1=0.5)     # k1 in m^-2
xt.Bend(length=2.0, angle=0.01)       # angle in radians
```

Compose them:

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
├── beam_xy.png
├── phase_space.png
├── momentum_histogram.png
├── beamline.png
└── summary.txt
```

| File | Contents |
|------|----------|
| `transported_particles.npz` | Final Xsuite coordinates, alive mask, reference `p0c`, metadata |
| `beam_xy.png` | Transverse profile \(x\)–\(y\) |
| `phase_space.png` | Horizontal phase space \(x\)–\(p_x/p_0\) |
| `momentum_histogram.png` | Absolute momentum spectrum |
| `beamline.png` | Static element schematic |
| `summary.txt` | Species, counts, transmission, mean/std momentum, RMS sizes |

Diagnostics are produced automatically by `transport.analysis` from the NPZ. You do not need a separate plotting command.

---

## End-to-end production workflow

1. **Configure and run Geant4** (collision stage):

   ```bash
   # edit interactions/config.json as needed
   python interactions/run.py
   ```

2. **Validate collision output** (optional but recommended):

   ```bash
   python interactions/validation/validate.py
   ```

3. **Write or edit a transport experiment** under `transport/experiments/`.

4. **Run transport**:

   ```bash
   python -m transport.main --experiment my_study
   ```

5. **Inspect** `transport/outputs/run_<timestamp>/summary.txt` and the PNG diagnostics.

---

## Checklist for a new study

1. Create `transport/experiments/<name>.py`
2. Define `line`, `particle`, `count`, optional `momentum_slice`
3. Implement `main()` that calls `run(...)`
4. Run `python -m transport.main --experiment <name>`
5. Confirm outputs under `transport/outputs/run_*/`

---

## Related docs

- [Architecture](ARCHITECTURE.md) — pipeline layout and NPZ schemas
- [Transport validation](transport_validation.md) — tests and smoke checks
- [Physics](PHYSICS.md) — physical models
- [Geant4 installation](geant4_installation.md) — building the collision engine
