# Transport Validation

**Current status:** Transport tracking is performed by **Xsuite**. Janus validates only its five-stage boundary (topology → construct → inherit → track → write), not Xsuite element physics.

Scientific parameters live in `transport/config.json` or on `Transport`. Tests use synthetic arrays or a tiny written `Seeds` tree; they do not require a Geant4 run.

## What Janus tests

1. `load_topology` fills `beamline.elements` and run cuts
2. `construct_beamline` maps `Drift` / `Quadrupole` / `Bend` (unknown types fail)
3. `inherit_particles` from one ROOT `Seeds` tree; no-op when arrays are already set
4. `run` tracks and writes `transported_particles.npz` + `topology.json`
5. Inherit once, mutate topology, construct + run again (study pattern)

## Running tests

```bash
pip install -r requirements.txt
pytest tests/transport/ -v
```

| Test module | Validates |
|-------------|-----------|
| `test_transport.py` | All five stages and the study loop pattern |

## Validation boundary

Janus does **not** re-validate:

- Geant4 hadronic physics
- Xsuite element physics or tracking maps

Janus **does** validate:

- Topology JSON → `xt.Line`
- Unit and coordinate conversions at the Geant4 → Xsuite boundary
- Species / momentum / count selection
- Transported NPZ schema and `topology.json`

## Manual smoke runs

```bash
# Requires data/interactions/*/simulation.root
python transport/run.py
```

Expect under `data/transport/run_<timestamp>/`:

- `transported_particles.npz`
- `topology.json`

Synthetic (no Geant4) smoke lives in `pytest tests/transport/`.
