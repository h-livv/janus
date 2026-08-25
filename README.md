# Janus

### A framework for simulating antimatter production, transport, and optimization.

Janus models the antimatter pipeline as:

**Geant4 particle production → inherit Seeds → Xsuite beam transport → NPZ output**

---

## Research Question

Which parameters most strongly influence antiproton production yield, and can sensitivity analysis and optimization reveal non-obvious relationships between them?

---

## Current System

<img width="800" height="400" alt="janus_cropped" src="https://github.com/user-attachments/assets/36a93bff-578b-4129-a98c-88e6da6515d0" />

26 GeV proton bombardment of a tungsten target

---

## Computational Pipeline

```
  Geant4 Engine (engines/geant4/)
       │
       ▼
  collision/  →  simulation.root (Seeds) + validation.root
       │
       ▼
  transport/config.json  →  topology instructions
       │
       ▼
  Transport: construct beamline → inherit particles → track → NPZ
       │
       ▼
  data/transport/run_*/  (NPZ + topology.json + plots)
```
---

## Current status

| Stage | Status |
|-------|--------|
| Geant4 target bombardment | Implemented (`engines/geant4/`, `collision/`) |
| Collision validation (Phases 1–3) | Implemented (`collision/validation/validate.py`) |
| Collision phenomenology (Phase 4) | Implemented (`collision/validation/physical_validation.py`) |
| ROOT → array inherit | Implemented (`transport/io.py`) |
| Five-stage Xsuite transport | Implemented (`transport/interface.py`) |
| Topology JSON (drift, quadrupole, bend, aperture) | Implemented (`transport/config.json`) |
| Magnetic horn via Xsuite field map | Not yet |
| Cooling / trapping / optimization | Planned |

---


## How to run transport

Topology lives in `transport/config.json`. Entry is `python transport/run.py`.

```bash
pip install -r requirements.txt

# Requires data/collision/*/simulation.root
python transport/run.py
```

Override fields in Python or edit the JSON. Full instructions: [docs/guides/transport_guide.md](docs/guides/transport_guide.md).

Outputs land in `data/transport/run_<timestamp>/` (`transported_particles.npz`, `topology.json`, diagnostic PNGs).


---


## Validation

**Collision** — Phases 1–3 check conservation laws on `validation.root`; Phase 4 plots emergent distributions from both ROOT files. See [docs/validation/collision_validation.md](docs/validation/collision_validation.md).

```bash
python collision/validation/validate.py
python collision/validation/physical_validation.py
```

**Transport** — Janus does not re-validate Xsuite element physics. It tests topology → construct → inherit → track → write:

```bash
pytest tests/transport/
```

See [docs/validation/transport_validation.md](docs/validation/transport_validation.md).

---

## Module overview

```
janus/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PHYSICS.md
│   ├── Janus_Architectural_Roadmap.md
│   ├── guides/                 # install, collision, transport how-tos
│   ├── validation/             # collision + transport validation
│   └── assets/
├── engines/
│   └── geant4/                 # C++ Geant4 collision engine
├── collision/               # Run orchestration + collision validation
│   ├── run.py                  # Entry: python collision/run.py
│   ├── run_batches.py          # Multi-batch runner
│   ├── config.json             # Collision study parameters
│   ├── interface.py            # Simulation interface (moves temp/ → data/)
│   ├── analyze.py              # Particle summary after a run
│   └── validation/
│       ├── validate.py         # Phases 1–3 (validation.root)
│       └── physical_validation.py  # Phase 4 plots
├── transport/
│   ├── interface.py            # Beamline + Transport (five stages)
│   ├── io.py                   # One ROOT Seeds parse
│   ├── run.py                  # load_topology(); run()
│   ├── plots.py                # Diagnostic PNGs after a run
│   └── config.json             # Default topology + cuts
├── data/                       # Generated artifacts (gitignored)
│   ├── collision/           # Packaged ROOT outputs
│   └── transport/              # Transport run outputs
├── tests/transport/
└── requirements.txt
```

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — full pipeline, repository layout, data contracts
- [Geant4 installation](docs/guides/geant4_installation.md) — install Geant4 and build the Janus engine
- [Collision guide](docs/guides/collision_guide.md) — configure and run collision experiments
- [Transport guide](docs/guides/transport_guide.md) — topology, inherit Geant4 Seeds, track
- [Physics](docs/PHYSICS.md) — physical models
- [Collision validation](docs/validation/collision_validation.md) — Geant4 validation (Phases 1–4)
- [Transport validation](docs/validation/transport_validation.md) — Xsuite boundary tests
- [Architectural roadmap](docs/Janus_Architectural_Roadmap.md) — future research infrastructure

---

## Roadmap

- Magnetic horn via Xsuite field maps
- Cooling and deceleration stages
- Trap injection
- End-to-end pipeline optimization

Longer-term research-infrastructure plans: [docs/Janus_Architectural_Roadmap.md](docs/Janus_Architectural_Roadmap.md).

---

## Acknowledgements

The core interaction engine of Janus is built upon the Geant4 simulation toolkit:

[Recent Developments in Geant4](https://www.sciencedirect.com/science/article/pii/S0168900216306957), J. Allison et al., Nucl. Instrum. Meth. A 835 (2016) 186-225<br>
[Geant4 Developments and Applications](https://ieeexplore.ieee.org/document/1610988), J. Allison et al., IEEE Trans. Nucl. Sci. 53 (2006) 270-278<br>
[Geant4 - A Simulation Toolkit](https://www.sciencedirect.com/science/article/abs/pii/S0168900203013688), S. Agostinelli et al., Nucl. Instrum. Meth. A 506 (2003) 250-303

The transport pipeline is built upon the Xsuite environment:

G. Iadarola, R. De Maria, S. Łopaciuk, A. Abramov, X. Buffat, D. Demetriadou, L. Deniau, P. Hermes, P. Kicsiny, P. Kruyt, A. Latina, L. Mether, K. Paraschou, G. Sterbini, F. F. Van Der Veken, P. Belanger, P. Niedermayer, D. Di Croce, T. Pieloni, L. Van Riesen-Haupt, M. Seidel. ["Xsuite: An Integrated Beam Physics Simulation Framework,”](https://inspirehep.net/literature/2705250) JACoW HB2023 (2024), TUA2I1.
