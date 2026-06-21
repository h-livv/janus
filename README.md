# Janus

A stochastic framework for simulating and optimizing particle generation, with a focus on antimatter systems. <br>

---

## Bombardment of a Tungsten cylinder with protons accelerated to 26 GeV

<img width="500" height="400" alt="bombardment" src="https://github.com/user-attachments/assets/3d2de231-3db6-4768-8cbb-384f577c836a" />

<br>

---

<<<<<<< HEAD
=======
## Transport pipeline featuring magnetic filtration

<img width="500" height="400" alt="pipeline" src="" />

---

>>>>>>> recovery-branch
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

Detailed validation study with outputs is available in [docs/validation_study.md](docs/validation_study.md).<br><br>
<<<<<<< HEAD
This study verifies that the Janus physics engine satisfies conservation laws, statistical benchmarks, and phenomenological validation criteria, providing confidence in the generated data for downstream applications.
=======
The validation framework verifies conservation laws, statistical benchmarks, and phenomenological observables, providing confidence in generated datasets before transport and optimization studies.

---

## Transport Optimization studies

[docs/optimization_exploration.md](docs/optimization_exploration.md) consists of an inital optimization framework for antiproton transport withing Janus.<br>

A deterministic transport model consisting of a magnetic horn and quadrupoles was successfully optimized and generalized using a hybrid Differential Evolution + Nelder-Mead strategy.<br>

Observations:
* Local optimization alone is insufficient for highly discontinuous transport landscapes.
* Global exploration is essential for identifying high-quality beamline configurations.
* Excessive horn currents do not necessarily maximize transport efficiency.

Results:
* The model was trained on momentum-cut ~1000 antiprotons and tested on ~400 antiprotons with unseen trajectories.
* Achieved **54.26%** survival on the training set and **53.42%** on the testing set.

These results establish a strong baseline for future Janus transport studies involving realistic magnetic field models, stochastic interactions, cooling systems, trap injection, and full antimatter storage pipelines.
>>>>>>> recovery-branch

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
- HDF5 and NPZ dataset generation
- Large-scale Monte Carlo runs
- Species and momentum filtering pipelines

### Transport Pipeline
- Relativistic Boris particle tracking
- Magnetic horn
- Dipoles, quadrupoles, drifts, and septa
- ACOL-inspired antiproton injection lattice
- Beam loss and aperture modelling

### Optimization & Diagnostics
- Injection efficiency optimization
- Beam envelope and phase-space diagnostics
- Dispersion and loss-map analysis
- Interactive beamline visualization

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
<<<<<<< HEAD
├── interface/               # Python interface and data pipeline
│   ├── config.json          # Default configuration for runs
│   ├── run.py               # Script to run a single configuration
│   ├── run_batches.py       # Script to execute multiple batches consecutively
│   └── dependencies/        # Sub-module containing pipeline logic
│
├── outputs/                 # Directory containing packaged simulation runs
│
└── validation/              # Automated test and validation scripts
    ├── physical_validation.py
    ├── validate.py
    └── validation_outputs/
=======
├── collision/               # Collision simulation runner & pipeline
│   ├── config.json          # Default configuration for collision runs
│   ├── run.py               # Script to run a single collision configuration
│   ├── run_batches.py       # Script to execute multiple batches consecutively
│   └── dependencies/        # Collision pipeline logic and interface utilities
│
├── transport/               # Transport simulation runner & pipeline
│   ├── config.json          # Default configuration for transport runs
│   ├── config_headless.json # Headless configuration for transport runs
│   ├── main.py              # Main entry point for transport simulation
│   └── dependencies/        # Transport solver, lattice, diagnostics, and viewport logic
│       ├── boris_solver.py  # Boris algorithm solver
│       ├── data_io.py       # I/O utilities for transport datasets
│       ├── diagnostics.py   # Simulation diagnostics
│       ├── lattice.py       # Lattice and field definitions
│       └── viewport.py      # Visualization viewport interface
│
└── validation               # Automated test and validation scripts
    ├── physical_validation.py
    └── validate.py

>>>>>>> recovery-branch
```

---

## Roadmap

- Implementation of higher-level antimatter transport and storage pipeline:
<<<<<<< HEAD
  * Magnetic Filtration
  * Cooling
  * Trapping
- Implementation of optimization algorithms to study antimatter yield
=======
  * Beam analysis
  * Stochastic and Electron Cooling
  * Trapping
- Continued development of optimization frameworks for transport efficiency and antimatter yield
>>>>>>> recovery-branch

---

## Acknowledgements

The core physics engine of Janus is built upon the Geant4 simulation toolkit. If you utilize this framework for academic or research purposes, ensure you cite the following resources:

[Recent Developments in Geant4](https://www.sciencedirect.com/science/article/pii/S0168900216306957), J. Allison et al., Nucl. Instrum. Meth. A 835 (2016) 186-225<br>
[Geant4 Developments and Applications](https://ieeexplore.ieee.org/document/1610988), J. Allison et al., IEEE Trans. Nucl. Sci. 53 (2006) 270-278<br>
[Geant4 - A Simulation Toolkit](https://www.sciencedirect.com/science/article/abs/pii/S0168900203013688), S. Agostinelli et al., Nucl. Instrum. Meth. A 506 (2003) 250-303
