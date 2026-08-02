# Janus

### A framework for simulating antimatter production, transport, and optimization.

Janus models the antimatter pipeline as:

**Geant4 particle production → NPZ seeds → Xsuite beam transport → analysis / optimization**

Collision physics is handled by Geant4. Beamline tracking is handled by Xsuite. Janus owns seed I/O, experiment scripts, and lightweight post-transport diagnostics.

---

## Bombardment of a Tungsten cylinder with protons accelerated to 26 GeV

<img width="800" height="400" alt="janus_cropped" src="https://github.com/user-attachments/assets/36a93bff-578b-4129-a98c-88e6da6515d0" />

---

## Computational Pipeline

```
  Geant4 Engine (engine/)
       │
       ▼
  interactions/  →  ROOT Seeds  →  NPZ cache
       │
       ▼
  transport/experiments/*.py  →  Xsuite Line + run(...)
       │
       ▼
  transported_particles.npz + diagnostics
       │
       ▼
  Optimization (planned)
```

---

## Documentation

- [Transport guide](docs/transport_guide.md) — **how to write and run a transport experiment**
- [Architecture](docs/ARCHITECTURE.md) — repository layout and data flow
- [Physics](docs/PHYSICS.md) — physical models
- [Geant4 installation](docs/geant4_installation.md) — building the collision engine
- [Collision validation](docs/collision_validation.md) — Geant4 validation
- [Transport validation](docs/transport_validation.md) — Xsuite boundary tests

---

## How to run a transport configuration

Transport “configs” are Python scripts in `transport/experiments/`.

```bash
pip install -r requirements.txt

# Built-in smoke test (no Geant4 run required)
python -m transport.main --experiment drift

# Geant4-seeded study (requires interactions/runs/*/simulation.root)
python -m transport.main --experiment geant4_antiproton
```

To add your own study, create `transport/experiments/my_study.py` with a `main()` that builds an `xtrack.Line` and calls `run(...)`. Full instructions: [docs/transport_guide.md](docs/transport_guide.md).

Outputs land in `transport/outputs/run_<timestamp>/` (`transported_particles.npz`, plots, `summary.txt`).

---

## Current status

| Stage | Status |
|-------|--------|
| Geant4 target bombardment | Implemented (`engine/`, `interactions/`) |
| Collision validation | Implemented (`interactions/validation/`) |
| ROOT → NPZ seed extraction | Implemented (`transport/io.py`) |
| Xsuite transport (drift, quadrupole, bend) | Implemented |
| Python experiment scripts | Implemented (`transport/experiments/`) |
| Automatic NPZ diagnostics | Implemented (`transport/analysis/`) |
| Magnetic horn via Xsuite field map | Not yet |
| Cooling / trapping / optimization | Planned |

---

## Validation

**Collision** — `interactions/validation/` checks conservation laws and emergent distributions before transport. See [docs/collision_validation.md](docs/collision_validation.md).

**Transport** — Janus does not re-validate Xsuite element physics. It tests its own boundaries (NPZ load, particle conversion, output packaging, analysis):

```bash
pytest tests/transport/
```

See [docs/transport_validation.md](docs/transport_validation.md).

---

## Module overview

```
janus/
├── docs/
├── engine/                 # C++ Geant4 collision engine
├── interactions/           # Run orchestration + collision validation
│   ├── run.py
│   ├── config.json
│   ├── runs/               # Geant4 ROOT outputs (gitignored)
│   └── validation/
├── transport/
│   ├── main.py             # CLI: --experiment <name>
│   ├── pipeline.py         # run(line=..., particle=..., ...)
│   ├── io.py               # ROOT → NPZ seeds
│   ├── xsuite.py           # Particles conversion + tracking + NPZ write
│   ├── analysis/           # Plots + summary from NPZ
│   └── experiments/        # One Python script per study
├── tests/transport/
└── requirements.txt
```

---

## Roadmap

- Magnetic horn via Xsuite field maps
- Cooling and deceleration stages
- Trap injection
- End-to-end pipeline optimization

---

## Acknowledgements

The core interaction engine of Janus is built upon the Geant4 simulation toolkit:

[Recent Developments in Geant4](https://www.sciencedirect.com/science/article/pii/S0168900216306957), J. Allison et al., Nucl. Instrum. Meth. A 835 (2016) 186-225<br>
[Geant4 Developments and Applications](https://ieeexplore.ieee.org/document/1610988), J. Allison et al., IEEE Trans. Nucl. Sci. 53 (2006) 270-278<br>
[Geant4 - A Simulation Toolkit](https://www.sciencedirect.com/science/article/abs/pii/S0168900203013688), S. Agostinelli et al., Nucl. Instrum. Meth. A 506 (2003) 250-303
