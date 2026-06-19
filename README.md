# Janus

A stochastic framework for simulating and optimizing particle generation, with a focus on antimatter systems. <br>

---

## Bombardment of a Tungsten cylinder with protons accelerated to 26 GeV

<img width="500" height="400" alt="image" src="https://github.com/user-attachments/assets/3d2de231-3db6-4768-8cbb-384f577c836a" />

<br>

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

Detailed validation study with outputs is available in [docs/validation_study.md](docs/validation_study.md)

---

## Current Capabilities

Environment configurations
- World, Chamber, and Target material
- Target shape, width, and position

Beam configuration
- Particle (Proton, Neutron, etc.)
- Particle count
- Beam profile and radius
- Direction and offset
- Energy distribution

Output filters
- Antimatter
- Light particle filtration
- Save secondaries
- Record mode (Birth, Hit, Track)

Run settings
- Interactive mode
- Customizable physics list (FTFP_BERT, QGSP_BIC)
- Production and tracking cuts
- Custom seed
- Custom thread input

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
```

---

## Roadmap

- Implementation of higher-level antimatter transport and storage pipeline:
  * Magnetic Filtration
  * Cooling
  * Trapping
- Implementation of optimization algorithms to study antimatter yield

---

## Acknowledgements

The core physics engine of Janus is built upon the Geant4 simulation toolkit. If you utilize this framework for academic or research purposes, ensure you cite the following resources:

[Recent Developments in Geant4](https://www.sciencedirect.com/science/article/pii/S0168900216306957), J. Allison et al., Nucl. Instrum. Meth. A 835 (2016) 186-225<br>
[Geant4 Developments and Applications](https://ieeexplore.ieee.org/document/1610988), J. Allison et al., IEEE Trans. Nucl. Sci. 53 (2006) 270-278<br>
[Geant4 - A Simulation Toolkit](https://www.sciencedirect.com/science/article/abs/pii/S0168900203013688), S. Agostinelli et al., Nucl. Instrum. Meth. A 506 (2003) 250-303
