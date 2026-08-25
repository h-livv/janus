# Transport Guide

How to run Janus beam transport: topology instructions → construct beamline → inherit Geant4 particles → track → write NPZ.

Collision remains the shape to copy (`Simulation` + `run.py`). Transport is the same idea for Xsuite: one `Transport` object and `python transport/run.py`.

**Related:** [architecture](../ARCHITECTURE.md) · [collision guide](collision_guide.md) · [transport validation](../validation/transport_validation.md) · [PHYSICS.md](../PHYSICS.md)

---

## Prerequisites

```bash
pip install -r requirements.txt
```

| Path | Needs |
|------|--------|
| Tests / synthetic arrays | Python deps only |
| `python transport/run.py` | At least one `data/collision/*/simulation.root` ([collision guide](collision_guide.md)) |

---

## Quick start

```bash
# Requires data/collision/*/simulation.root
python transport/run.py
```

That loads [transport/config.json](../../transport/config.json), constructs the line, inherits the newest collision `Seeds` tree, tracks, and writes:

```text
data/transport/run_<timestamp>/
├── transported_particles.npz
├── topology.json
├── beam_xy.png
├── phase_space.png
├── momentum_histogram.png
└── beamline.png
```

Edit `transport/config.json` (or override attributes in Python) and re-run.

---

## The five stages

```text
Topology instructions → Construct beamline → Inherit particle data → Forward simulation → Output data
```

| Stage | Method | Role |
|-------|--------|------|
| 1. Topology | `load_topology()` | JSON → `beamline.elements` + cuts |
| 2. Construct | `construct_beamline()` | element list → `xt.Line` |
| 3. Inherit | `inherit_particles()` | one Geant4 `Seeds` file → arrays |
| 4–5. Track + write | `run()` | convert, `line.track`, NPZ + `topology.json` + plots |

`run()` does stages 2–5. It inherits only if `positions` / `momenta_mevc` / `charges` are unset, so a study can inherit once and loop construct + run.

### Config (topology instructions)

```json
{
  "beamline": [
    {"type": "Drift", "length": 5.0},
    {"type": "Quadrupole", "length": 1.0, "k1": 0.5},
    {"type": "Drift", "length": 2.0},
    {"type": "Quadrupole", "length": 1.0, "k1": -0.5}
  ],
  "particle": "antiproton",
  "count": 10000,
  "momentum_slice": [3.48, 3.68],
  "aperture_diameter": 0.04,
  "num_turns": 1,
  "source": null,
  "output_dir": "data/transport"
}
```

| Field | Meaning |
|-------|---------|
| `beamline` | Ordered element dicts (`type` plus `length`, and `k1` or `angle` as needed) |
| `particle` | `antiproton` or `proton` (charge selection at run) |
| `count` | Max particles to track (`null` = all selected) |
| `momentum_slice` | `(p_min, p_max)` in **GeV/c**, or `null` |
| `aperture_diameter` | Circular vacuum-pipe diameter in **meters**, or `null` for no aperture |
| `num_turns` | Xsuite tracking turns |
| `source` | Path to one Geant4 `simulation.root` (`Seeds` tree). `null` = newest under `data/collision/`. Not an Xsuite particle generator. Unused if arrays are already set. |
| `output_dir` | Parent directory for `run_<timestamp>/` folders |

Supported element types: `Drift`, `Quadrupole`, `Bend` (alias `SBend`). Unknown types raise. Add a type in `ELEMENT_BUILDERS` inside `transport/interface.py`.

Python overrides work like collision (`sim.beam.count = ...`):

```python
from transport.interface import Transport

t = Transport()
t.load_topology()
t.count = 500
t.beamline.elements[1]["k1"] = 0.3
t.run()
```

### Synthetic particles (no Geant4)

Set the three arrays; `inherit_particles()` is then a no-op:

```python
import numpy as np
from transport.interface import Transport

t = Transport()
t.beamline.elements = [{"type": "Drift", "length": 10.0}]
t.positions = np.array([[0.001, 0.0, 0.0]])
t.momenta_mevc = np.array([[0.0, 0.0, 3580.0]])
t.charges = np.array([-1], dtype=np.int8)
t.output_dir = "data/transport"
t.run()
```

Default collision config uses `"record_mode": "Hit"`: `Seeds` are Target→Chamber boundary states. See [collision validation](../validation/collision_validation.md).

---

## Outputs

| File | Contents |
|------|----------|
| `transported_particles.npz` | Final `x, px, y, py, zeta, delta, state, p0c_eV, mass0_eV, q0` |
| `topology.json` | Beamline + cuts + source actually used |
| `beam_xy.png` | Transverse profile \(x\)–\(y\) |
| `phase_space.png` | Horizontal phase space \(x\)–\(p_x/p_0\) |
| `momentum_histogram.png` | Absolute momentum spectrum |
| `beamline.png` | Element schematic from topology |

After `run()`, `t.particles` is the in-memory `xpart.Particles` object. Future studies compute observables from that or from the NPZ. Metrics and provenance are not written by `run()`.

---

## Future studies (not a Janus package)

A sweep is a loop, the same idea as [collision/run_batches.py](../../collision/run_batches.py):

```python
t = Transport()
t.load_topology()
t.inherit_particles()
for k1 in k1_values:
    t.beamline.elements[1]["k1"] = k1
    t.construct_beamline()
    t.run()
    # study owns metrics: use t.particles
```

Do not add `transport/studies/`, grid generators, or CSV export until a real campaign needs them.

---

## End-to-end production workflow

1. **Build Geant4 engine** — [geant4_installation.md](geant4_installation.md)
2. **Configure and run collision** — [collision_guide.md](collision_guide.md)
3. **Validate collision output**

   ```bash
   python collision/validation/validate.py
   python collision/validation/physical_validation.py
   ```

4. **Edit** `transport/config.json` (or override in Python)
5. **Run transport:** `python transport/run.py`
6. **Inspect** `data/transport/run_<timestamp>/`

---

## Related docs

- [Architecture](../ARCHITECTURE.md) — layout and data contracts
- [Collision guide](collision_guide.md) — run Geant4 studies
- [Geant4 installation](geant4_installation.md) — build the collision engine
- [Transport validation](../validation/transport_validation.md) — stage tests
- [Collision validation](../validation/collision_validation.md) — Geant4 Phases 1–4
- [Physics](../PHYSICS.md) — physical models
- [Roadmap](../Janus_Architectural_Roadmap.md) — future research infrastructure
