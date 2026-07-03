# Janus

### A framework for simulating antimatter production, transport, and optimization.
Janus is a computational framework for modeling the antimatter pipeline, integrating Geant4-based particle production, deterministic charged-particle transport, and hierarchical validation, with ongoing development toward beamline optimization, cooling, and particle trapping.<br>

Janus follows a validation-first development philosophy: every numerical method and physical model is independently verified before being incorporated into larger transport systems or optimization studies.

---

## Bombardment of a Tungsten cylinder with protons accelerated to 26 GeV

<img width="500" height="400" alt="bombardment" src="https://github.com/user-attachments/assets/3d2de231-3db6-4768-8cbb-384f577c836a" />

<br>

---

## Documentation

- [Installation](docs/geant4_installation) - Building Geant4 and setting up Janus
- [Physics](docs/PHYSICS.md) - Physics, architecture and philosophy behind the project
- [Collision Validation](docs/collision_validation.md) - Validation methodology and benchmark results for the collision engine
- [Transport Validation](docs/transport_validation.md) - Validation studies for the transport solver and lattice elements


---

## Validation Studies

`validation/` automatically verifies the physical accuracy of the generated outputs before the batch moves further down the pipeline.

- **`validate.py`:** Evaluates event-by-event fundamental physics laws.
  * Kinematic conservation (Energy/Momentum)
  * Quantum Number conservation (Charge/Baryon)
  * Statistical sanity checks (Total antinucleons, global Baryon conservation)

- **`physical_validation.py`:** Generates diagnostic physics plots saved directly to `validation_outputs/`.
  * Momentum mapping
  * Pion multiplicity
  * Vertex distribution
  * Energy spectra

Detailed validation study with outputs is available in [docs/collision_validation.md](docs/collision_validation.md)<br>

The validation framework verifies conservation laws, statistical benchmarks, and phenomenological observables before generated datasets are propagated into downstream transport and optimization studies.

---

## Transport Validation

`transport/validation` verifies the numerical accuracy of the transport solver before beam-level optimization studies.

Validation currently includes:

- Analytical validation of individual lattice elements
- Boris integrator conservation tests
- Timestep convergence studies

Planned validation includes:

- Composite lattice validation
- Beam validation

Optimization studies are performed only after the underlying numerical methods and physical models have been independently validated.

Transport validation studies are continuously updated in [docs/transport_validation.md](docs/transport_validation.md)

---

## Current Capabilities

### Geant4 Simulation Engine
- Configurable target, materials, and geometry
- Custom beam profiles and energy distributions
- Physics list selection (FTFP_BERT, QGSP_BIC)
- Secondary particle generation and filtering
- Multithreaded batch execution

### Dataset Generation
- Automated simulation orchestration
- ROOT and NPZ dataset generation
- Large-scale Monte Carlo runs
- Species and momentum filtering pipelines

### Transport Pipeline
- Relativistic Boris particle pusher
- Modular lattice framework
    - Drift spaces
    - Dipoles
    - Extensible beamline elements
- Hierarchical transport validation
- Analytical verification of lattice elements
- Second-order convergence verification

---

## Module overview


```
janus/
├── docs/                         # Physics, validation, and setup documentation
│
├── engine/                       # C++ Geant4 collision engine
│   ├── include/, src/            # Detector geometry, physics, event generation
│   ├── macros/                   # Geant4 macro scripts
│   └── janus.cc                  # Simulation entry point
│
├── collision/                    # Collision run orchestration
│   ├── run.py, run_batches.py    # Single and batch execution
│   ├── config.json               # Default run configuration
│   └── dependencies/             # Pipeline utilities and Geant4 interface
│
├── runs/                         # Geant4 output (ROOT datasets)
│
├── transport/                    # Deterministic transport framework
│   ├── main.py                   # Experiment runner (YAML → validate or visualize)
│   ├── experiment/               # Experiment schema, loader, example YAMLs
│   ├── io/                       # ROOT I/O and seed extraction
│   ├── physics/                  # Boris integrator, particle data
│   ├── lattice/                  # Beamline elements and element registry
│   ├── validation/               # Validation engine, cases, metrics, reporting
│   └── visualization/            # VisPy 3D viewport
│
└── validation/                   # Collision-stage validation scripts
    ├── validate.py               # Conservation and sanity checks
    └── physical_validation.py    # Diagnostic plots and benchmarks
```


---

## Roadmap

### Validation

- Composite lattice validation
- Beam validation

### Transport Physics

- Quadrupoles
- Composite beamlines
- Solenoids
- Magnetic horns
- Deceleration
- Cooling
- Trapping

### Optimization

- Geant4 production
- Beam transport
- Beam optics
- End-to-end pipeline optimization

---

## Acknowledgements

The core collision engine of Janus is built upon the Geant4 simulation toolkit:

[Recent Developments in Geant4](https://www.sciencedirect.com/science/article/pii/S0168900216306957), J. Allison et al., Nucl. Instrum. Meth. A 835 (2016) 186-225<br>
[Geant4 Developments and Applications](https://ieeexplore.ieee.org/document/1610988), J. Allison et al., IEEE Trans. Nucl. Sci. 53 (2006) 270-278<br>
[Geant4 - A Simulation Toolkit](https://www.sciencedirect.com/science/article/abs/pii/S0168900203013688), S. Agostinelli et al., Nucl. Instrum. Meth. A 506 (2003) 250-303
