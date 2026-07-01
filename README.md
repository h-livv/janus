# Janus

A stochastic framework for simulating and optimizing particle generation, with a focus on antimatter systems. <br>

---

## Bombardment of a Tungsten cylinder with protons accelerated to 26 GeV

<img width="500" height="400" alt="bombardment" src="https://github.com/user-attachments/assets/3d2de231-3db6-4768-8cbb-384f577c836a" />

<br>


---

## Documentation

- [Physics](docs/PHYSICS.md) - Physics, architecture and philosophy behind the project
- [Collision Validation](docs/collision_validation.md) - Validation methodology and benchmark results for the collision engine
- [Transport Validation](docs/transport_validation.md) - Validation studies for the transport solver and lattice elements
- [Installation](docs/geant4_installation) - Building Geant4 and setting up Janus

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

The validation framework verifies that the Janus physics engine satisfies conservation laws, statistical benchmarks, and phenomenological observables, providing confidence in generated datasets before transport and optimization studies.

---

## Transport Validation

`transport/validation` verifies the numerical accuracy of the transport solver before beam-level optimization studies.

Validation currently includes:

- Analytical validation of individual lattice elements
- Boris integrator conservation tests
- Timestep convergence studies

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
- Modular and physics-agnostic lattice structure
  * Drift spaces
  * Dipoles
  * Quadrupoles
  * Extensible beamline elements
- Validated Drift and Dipole elements
- Validation and convergence studies

---

## Module overview


```
janus/
├── README.md                # Project documentation
│
├── docs/                    # Documentation directory
│
├── engine/                  # C++ Geant4 Simulation Engine
│   ├── CMakeLists.txt       # CMake configuration
│   ├── build/               # Build directory containing compiled binaries
│   ├── include/             # C++ header files (.hh)
│   ├── janus.cc             # Main entry point for the simulation
│   ├── macros/              # Geant4 macro scripts (.mac)
│   └── src/                 # C++ source code (.cc)
│
├── collision/               # Collision simulation runner & pipeline
│   ├── config.json          # Default configuration for collision runs
│   ├── run.py               # Script to run a single collision configuration
│   ├── run_batches.py       # Script to execute multiple batches consecutively
│   └── dependencies/        # Collision pipeline logic and interface utilities
│
├── transport/               # Transport simulation and validation
│   ├── main.py              # Main file to run the simulation
│   ├── io                   # Data management
│   ├── physics              # Solver and timestepping
│   ├── lattice              # The lattice
│   ├── visualization        # Visualization interface
│   └── validation           # Transport solver, lattice, diagnostics, and viewport logic
│
└── validation               # Automated test and validation scripts
    ├── physical_validation.py
    └── validate.py
```


---

## Roadmap

- Validation
  * Single-structure validation
  * Composite lattice validation
  * Beam analysis and validation

- Optimization
  * Geant4 particle production
  * Transport elements
  * Beam optics

- Higher-level transport
  * Deceleration
  * Cooling
  * Trapping

- Higher-level and global optimization
---

## Acknowledgements

The core collision engine of Janus is built upon the Geant4 simulation toolkit:

[Recent Developments in Geant4](https://www.sciencedirect.com/science/article/pii/S0168900216306957), J. Allison et al., Nucl. Instrum. Meth. A 835 (2016) 186-225<br>
[Geant4 Developments and Applications](https://ieeexplore.ieee.org/document/1610988), J. Allison et al., IEEE Trans. Nucl. Sci. 53 (2006) 270-278<br>
[Geant4 - A Simulation Toolkit](https://www.sciencedirect.com/science/article/abs/pii/S0168900203013688), S. Agostinelli et al., Nucl. Instrum. Meth. A 506 (2003) 250-303
