# Transport guide

Janus transport is a handwritten relativistic particle tracker. A YAML experiment selects the lattice, particle source, numerical timestep, validation case, and output behavior. The tracker itself is in `transport/physics/boris_solver.py`; built-in magnetic elements are in `transport/lattice/lattice.py`.

## Run a built-in case

From the repository root:

```bash
python -m pip install -r requirements.txt
python transport/main.py --experiment transport/experiment/configs/fodo.yaml
```

The runner resolves the YAML configuration, constructs its lattice and particle source, advances particles with the Boris solver, evaluates configured metrics, and writes reports and plots. For a self-contained case that does not need a Geant4 run, use a Gaussian-beam configuration such as `fodo.yaml`.

## Configure an experiment

The built-in configurations are in `transport/experiment/configs/`. `fodo.yaml` uses a generated Gaussian beam and can run without collision data. Configurations such as `dipole.yaml` and `drift.yaml` use Geant4 seed input and need a matching `Seeds` ROOT file. The experiment YAMLs specify:

- lattice element types and parameters;
- particle species and initial state or ROOT source;
- timestep and maximum integration steps;
- validation references, metrics, tolerances, and convergence settings;
- output and optional visualization settings.

The loader and schema are in `transport/experiment/`. Cases can be run directly by passing their YAML path with `--experiment`.

## Geant4 seed input

To transport particles produced by the collision simulation, set the experiment's source to the `simulation.root` file from a collision run. Janus reads the `Seeds` tree through `transport/io/data_io.py`; the reader converts the stored positions and momenta to the units expected by the transport model. Confirm the source's recording mode and particle selection when interpreting results. Collision execution is described in the [collision guide](collision_guide.md).

## Elements and model assumptions

Built-in elements are drift, dipole, quadrupole, and magnetic horn. Their fields, hard longitudinal boundaries, and aperture checks are defined in `transport/lattice/lattice.py`. These are idealized prescribed-field models. In particular, the code does not supply fringe-field maps, self-consistent electromagnetic fields, or collective space-charge forces.

## Validation records

The validation framework is in `transport/validation/`. It includes analytical single-particle checks, conservation metrics, convergence comparisons, composite-lattice and beam metrics, and transfer-matrix / Twiss comparisons. The archived evidence and stated criteria are in [transport validation](../validation/transport_validation.md). The documented figures and numerical results are from the historical development campaign; running the present case configurations writes new local outputs and does not change that archived record.
