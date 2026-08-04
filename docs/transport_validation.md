# Transport Validation

**Current status:** Transport tracking is performed by **Xsuite**. Janus validates only its integration boundaries and automatic diagnostics — not Xsuite element physics.

There is no YAML transport config and no Janus-owned tracking integrator to validate. Scientific parameters belong in experiment scripts; tests exercise the load → convert → track → write → analyze path with explicit arguments.

## What Janus tests

1. NPZ seed loading (`transport/io.py`)
2. Conversion into `xpart.Particles` (`transport/xsuite.py`)
3. Pipeline NPZ + analysis product generation
4. Smoke tracking through a minimal `xtrack.Line`

## Running tests

```bash
pip install -r requirements.txt
pytest tests/transport/ -v
```

| Test module | Validates |
|-------------|-----------|
| `test_npz_loader.py` | Seed NPZ schema via `load_seed_npz` |
| `test_xsuite_particles.py` | Coordinate conversion |
| `test_xsuite_beamline.py` | Direct `xtrack.Line` construction |
| `test_xsuite_runner.py` | Tracking smoke + pipeline integration |
| `test_analysis.py` | Diagnostic plots and `summary.txt` |

## Manual smoke runs

```bash
# Synthetic single-particle drift (no Geant4 required)
python -m transport.main --experiment drift

# Geant4 seeds (requires interactions/runs/*/simulation.root)
python -m transport.main --experiment geant4_antiproton
```

Expect under `transport/outputs/run_<timestamp>/`:

- `transported_particles.npz`
- `beam_xy.png`, `phase_space.png`, `momentum_histogram.png`, `beamline.png`
- `summary.txt`

Seed-extraction logs (normally quiet):

```bash
DATAIO_VERBOSE=1 python -m transport.main --experiment geant4_antiproton
```

## Writing a new study

Transport configurations are Python experiment scripts, not YAML files.
All scientific parameters must be defined in that script.
See [transport_guide.md](transport_guide.md).
