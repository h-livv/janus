# Collision Experiment Guide

How to configure and run Geant4 target-bombardment studies in Janus, and where outputs land for transport.

**Prerequisites:** a built Janus Geant4 engine — see [Geant4 installation](geant4_installation.md).

**Related:** [architecture](../ARCHITECTURE.md) · [collision validation](../validation/collision_validation.md) · [transport guide](transport_guide.md)

---

## Quick start

From the repository root:

```bash
# Optional: Python deps for packaging summaries / validation
pip install -r requirements.txt
pip install uproot awkward particle matplotlib   # if not already installed

python interactions/run.py
```

Orchestration lives in `interactions/interface.py`. It launches `engines/geant4/build/janus`, then packages ROOT outputs.

For headless / batch runs, set `"interactive": false` in `interactions/config.json` (see below).

---

## Configuration

All collision scientific and run parameters live in `interactions/config.json`.

### Environment (geometry / materials)

| Key | Typical role |
|-----|----------------|
| `world_material` | World volume material (e.g. `G4_Galactic`) |
| `chamber_material` | Chamber material |
| `target_shape` | `Cylinder`, `Box`, or `Sphere` |
| `target_material` | e.g. `G4_Ir` |
| `target_width` / `target_length` | Target size |
| `target_position` | Target placement |

### Beam

| Key | Typical role |
|-----|----------------|
| `particle` | Primary species (e.g. `proton`) |
| `count` | Number of primaries |
| `profile` | `Flat`, `Gaussian`, or `Point` |
| `energy_mean` / `energy_dist` | Beam energy |
| `direction` / `offset` | Beam aiming |

### Output

| Key | Default | Notes |
|-----|---------|-------|
| `filter` | `"All"` | Or `"Antimatter"` |
| `drop_light_particles` | `false` | Drop light secondaries when true |
| `save_secondaries` | `true` | |
| `record_mode` | `"Hit"` | `"Hit"` = Target→Chamber boundary; `"Birth"` = \(t=0\) birth states |

### Run settings

| Key | Default | Notes |
|-----|---------|-------|
| `interactive` | `true` | Set `false` for headless / CI / batches |
| `physics_list` | `FTFP_BERT` | Or `QGSP_BIC` |
| `threads` | study-specific | Geant4 worker threads |
| `seed` | `null` | RNG seed when set |

Edit the JSON, then re-run `python interactions/run.py`. Defaults in code also exist inside `Simulation` if the file is missing, but production studies should use the config file.

---

## Running a single study

```bash
python interactions/run.py
```

1. Loads `interactions/config.json`.
2. Writes a Geant4 macro and executes `engines/geant4/build/janus`.
3. Geant4 writes intermediate ROOT files under project `temp/` (`temp/simulation`, `temp/validation`).
4. The Python interface moves them into a timestamped run directory (below).

---

## Multi-batch runs

For long production campaigns (many identical batches with unique names):

```bash
python interactions/run_batches.py
```

This repeatedly loads the baseline config, overrides particle count / naming, and runs headless. Adjust batch count and events-per-batch in the script itself before launching.

---

## Where output lands

```text
data/interactions/<run_name>/
├── simulation.root          # Seeds tree → transport input
├── validation.root          # Validation tree → collision checks
├── <run_name>_config.json
└── particle_summary.txt
```

| File | Tree | Role |
|------|------|------|
| `simulation.root` | `Seeds` | Secondary kinematics for transport |
| `validation.root` | `Validation` | Per-event conservation / quantum checks |

`record_mode` controls what `Seeds` means:

| Mode | Meaning |
|------|---------|
| `"Hit"` (**default**) | Kinematics at Target → Chamber crossing |
| `"Birth"` | \(t=0\) birth kinematics of secondaries |

Transport injects particles at the beamline entrance regardless; `start_z` is metadata.

---

## Validate before transport

```bash
# Phases 1–3 (validation.root)
python interactions/validation/validate.py

# Phase 4 plots (validation.root + simulation.root)
python interactions/validation/physical_validation.py
```

If paths are omitted, scripts pick the newest `data/interactions/run_*` directory.

Details: [collision validation](../validation/collision_validation.md).

---

## Next: transport

Once `data/interactions/*/simulation.root` exists:

```bash
python transport/run.py
```

Or set synthetic arrays on `Transport` with no Geant4 run — see [transport guide](transport_guide.md).
