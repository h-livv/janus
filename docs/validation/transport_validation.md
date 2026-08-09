# Transport Validation

**Current status:** Transport tracking is performed by **Xsuite**. Janus validates only its integration boundaries, metrics, studies, provenance, and automatic diagnostics — not Xsuite element physics.

There is no YAML transport config and no Janus-owned tracking integrator to validate. Scientific parameters belong in experiment scripts; tests exercise the load → convert → track → write → metrics → provenance → analyze path with explicit arguments.

## What Janus tests

1. NPZ seed loading (`transport/io.py`)
2. Conversion into `xpart.Particles` (`transport/xsuite.py`)
3. Pipeline NPZ + metrics + provenance + analysis product generation
4. Smoke tracking through a minimal `xtrack.Line`
5. Structured metrics from in-memory `TransportResult` and NPZ adapter
6. Study parameter generators and CSV export
7. Per-run provenance fingerprinting

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
| `test_analysis.py` | Diagnostic plots, summary, metrics |
| `test_metrics.py` | `TransportMetrics` from result and NPZ adapter |
| `test_provenance.py` | `provenance.json` and fingerprints |
| `test_studies.py` | Parameter generators and study CSV |
| `test_contracts.py` | Stable public interface contracts |

## Validation boundary

Janus does **not** re-validate:

- Geant4 hadronic physics
- Xsuite element physics or tracking maps

Janus **does** validate:

- Unit and coordinate conversions at the Geant4 → Xsuite boundary
- NPZ seed and transported NPZ schemas
- Metrics definitions and alive-particle masking
- Provenance determinism for canonical parameters
- Study aggregation without external Geant4 files

## Manual smoke runs

```bash
# Synthetic single-particle drift (no Geant4 required)
python -m transport.main --experiment drift

# Geant4 seeds (requires data/interactions/*/simulation.root)
python -m transport.main --experiment geant4_antiproton

# Parameter sweep example
python -m experiments.transport.study_drift_length
```

Expect under `data/transport/run_<timestamp>/`:

- `transported_particles.npz`
- `metrics.json`
- `provenance.json`
- `beam_xy.png`, `phase_space.png`, `momentum_histogram.png`, `beamline.png`
- `summary.txt`

Study outputs write `study_results.csv` under the study output directory.

Seed-extraction logs (normally quiet):

```bash
DATAIO_VERBOSE=1 python -m transport.main --experiment geant4_antiproton
```

## Writing a new study

Transport configurations are Python experiment scripts, not YAML files.
Computational studies use `transport/studies/` with a Parameter Generator and an Experiment Factory.
See [transport guide](../guides/transport_guide.md).
