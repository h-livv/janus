# Janus architecture

Janus contains two scientific stages: Geant4 models target interactions, and a handwritten Python transport implementation advances selected charged particles through prescribed beamline fields. The stages exchange particle data through ROOT files. Janus does not delegate transport to Xsuite.

## Data flow

```text
Proton beam and target configuration
                ↓
     C++ Geant4 collision engine
                ↓
     ROOT output (Seeds tree)
                ↓
ROOT reader → particle phase-space arrays
                ↓
 lattice field model + relativistic Boris pusher
                ↓
 diagnostics, validation reports, and figures
```

The collision stage is configured and run through `collision/`. Its `Seeds` tree provides particle species, charge, position, and momentum for transport. The handwritten tracker in `transport/physics/boris_solver.py` updates relativistic particle velocities in the fields exposed by `transport/lattice/lattice.py`; the lattice applies element boundaries and apertures. Validation cases in `transport/validation/` compare those results with analytical or numerical references.

## Main modules

| Module | Responsibility |
|---|---|
| `engine/` | Geant4 geometry, primary beam, interactions, and recorded output |
| `collision/` | Geant4 run orchestration, ROOT packaging, and collision checks |
| `transport/io/` | Reading and describing particle data from ROOT |
| `transport/physics/` | Relativistic Boris integration and particle constants |
| `transport/lattice/` | Drift, dipole, quadrupole, and horn fields; apertures; lattice composition |
| `transport/experiment/` | YAML experiment schema, built-in cases, and run configuration |
| `transport/validation/` | Solver adapter, metrics, references, convergence, reporting, and validation plots |
| `transport/visualization/` | Optional interactive 3D visualization |

## Numerical ownership and limits

Janus implements charged-particle tracking under prescribed electromagnetic fields. It does not implement Geant4's hadronic interaction physics, solve Maxwell's equations, or model collective space-charge fields. Magnetic-lattice transport assumes zero electric field in the supplied built-in elements. The pusher is a staggered relativistic Boris scheme; the validation framework measures its behavior against declared references and tolerances.

Validation results and their scope are documented in [transport validation](validation/transport_validation.md). Collision checks are documented separately in [collision validation](validation/collision_validation.md). Historical report values and plots describe the development campaign and are not evidence that the archived checkout has been freshly rerun.

## Running

```bash
python -m pip install -r requirements.txt
python transport/main.py --experiment transport/experiment/configs/dipole.yaml
```

Geant4-seeded cases need a collision output file. Self-contained analytical validation cases can be run without Geant4. The interactive viewer additionally requires VisPy and a compatible GUI backend.
