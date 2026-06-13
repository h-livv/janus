# Janus

A stochastic framework for simulating and optimizing particle generation, with a focus on antimatter systems. <br>

---

## Bombardment of a Tungsten cylinder with protons accelerated to 26 GeV

<img width="500" height="400" alt="image" src="https://github.com/user-attachments/assets/3d2de231-3db6-4768-8cbb-384f577c836a" />

<br>

---

## Results

Early results already demonstrate antiproton generation from proton bombardment of dense metal targets.

<img width="700" height="219" alt="image" src="https://github.com/user-attachments/assets/6f971a6a-d240-40dd-a7f9-cf0c3764abcc" />

<br>
<br>

Other interesting observations include:
- Charmed particles such as the anti-Sigma-c, anti-Lambda-c, and D0 meson
- anti-Omega anti-baryon. <br>
<img width="700" height="98" alt="image" src="https://github.com/user-attachments/assets/16d3f475-dd70-457a-a17c-9cfb31ba9b49" />

---

## Validation Studies

Coming soon

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
- Drop light particles
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
│
├── engine/                  # Primary physics engine powered by Geant4
│   ├── src/                 # Source files
│   ├── include/             # Header files
│   ├── macros/              # Macros
│   ├── janus.cc             # Main file
├── python/             
│   ├── interface.py         # Python interface and data pipeline
│   ├── run.py               # Run the python interface
│   ├── run_batches.py       # Run multiple batches
│
└── README.md                # Project documentation
```

---

## Roadmap

- Refinement of data pipeline: shift from csv to a more efficient format.
- Implementation of antimatter production and storage pipeline entirely in python:
  * Magnetic Filtration
  * Cooling and speed reduction
  * Trapping
- Integration of machine learning to optimize antimatter production.

---

## Acknowledgements

The core physics engine of Janus is built upon the Geant4 simulation toolkit. If you utilize this framework for academic or research purposes, please ensure you cite the following foundational Geant4 papers:

[Recent Developments in Geant4](https://www.sciencedirect.com/science/article/pii/S0168900216306957), J. Allison et al., Nucl. Instrum. Meth. A 835 (2016) 186-225<br>
[Geant4 Developments and Applications](https://ieeexplore.ieee.org/document/1610988), J. Allison et al., IEEE Trans. Nucl. Sci. 53 (2006) 270-278<br>
[Geant4 - A Simulation Toolkit](https://www.sciencedirect.com/science/article/abs/pii/S0168900203013688), S. Agostinelli et al., Nucl. Instrum. Meth. A 506 (2003) 250-303
