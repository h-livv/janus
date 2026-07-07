# Janus Transport Framework Developer Guide

## Executive Summary
Janus is a particle simulation and transport repository. The repository contains a Geant4 collision engine, Python orchestration for collision runs, transport simulation code, validation infrastructure, and visualization tooling.

The current transport framework is YAML-driven. A user provides an experiment file, `transport.main` loads it into typed experiment objects, resolves particle sources and lattices, then either runs validation or launches visualization depending on `outputs.visualization`.

Validation is organized in three tiers matched to lattice complexity: **analytical** (single-element trajectory checks), **simple_composite** (two-element beam composition), and **beam_optics** (multi-cell alternating-gradient lattices). Tier selection is automatic from the experiment `case` name via `transport.validation.profiles`.

Related documentation:

- [Transport validation](transport_validation.md) — scientific validation results and methodology
- [Collision validation](collision_validation.md) — Geant4 collision-stage checks (upstream of transport)
- [Architectural changes](architectural_changes.md) — planned refactors and known technical debt
- [Physics](PHYSICS.md) — field models and integrator details

The transport stack is centered around these runtime objects:

```text
Experiment
↓
ParticleSource + LatticeSpec + NumericalConfig + OutputConfig
↓
ParticleBatch + SimpleLattice + ValidationCase
↓
BorisSolverAdapter / track_particles
↓
Diagnostics
↓
[Analytical tier]  References → trajectory + conservation metrics
[Composite tiers]  apply_validation_profile (no references) → beam metrics
↓
Report / JSON / CSV / Manifest / Plots
```

When visualization is enabled, validation is bypassed:

```text
Experiment
↓
SimulationConfig
↓
Particle arrays + SimpleLattice
↓
run_visual_physics_loop + run_renderer
```

---

## Repository Overview
```text
janus/
├── docs/                         # Project documentation (architecture, transport/collision validation)
├── engine/                       # C++ Geant4 simulation engine
│   ├── include/                  # Geant4 class headers
│   ├── src/                      # Geant4 implementation files
│   ├── macros/                   # Geant4 macro scripts
│   └── janus.cc                  # C++ executable entry point
├── interactions/                 # Python interaction-run orchestration
│   ├── run.py                      # Single-run entry point
│   ├── run_batches.py              # Batch-run driver
│   ├── runs/                       # Geant4 output directories containing simulation.root
│   ├── validation/                 # Collision-stage validation scripts
│   └── dependencies/               # Simulation interface and ROOT analysis helpers
├── transport/                    # Transport simulation, validation, and visualization
│   ├── main.py                   # YAML experiment entry point
│   ├── pipeline.py               # Validation and visualization orchestration
│   ├── experiment/               # YAML schema, loader, resolver, examples
│   ├── io/                       # ROOT and NPZ seed loading
│   ├── lattice/                  # Beamline elements, patterns, and element registry
│   ├── physics/                  # Particle data and Boris solver
│   ├── validation/               # Validation engine, profiles, cases, metrics, references, reporting
│   └── visualization/            # VisPy renderer and drawing primitives
```

Responsibilities are divided by simulation stage:

- `engine/` produces Geant4 collision outputs.
- `interactions/` configures and invokes the Geant4 executable.
- `interactions/runs/` stores generated ROOT files.
- `transport/io/` extracts transport seeds from Geant4 ROOT output.
- `transport/experiment/` turns YAML into typed experiment objects.
- `transport/lattice/` owns beamline geometry, lattice patterns (repeat/FODO expansion), and field queries.
- `transport/physics/` owns particle constants and time integration.
- `transport/validation/` owns validation cases, metrics, references, convergence, and reports.
- `transport/visualization/` owns the interactive 3D display.

---

## Transport Framework Overview
The transport framework starts at `transport/main.py`.

A user runs:

```bash
python -m transport.main --experiment experiment.yaml
```

`main.py` loads the YAML file through `transport.experiment.loader.load_experiment`. The resulting `Experiment` object contains:

- experiment identity
- particle source configuration
- lattice configuration
- numerical configuration
- validation configuration
- output configuration

The next branch is controlled by `experiment.outputs.visualization`.

If `visualization: true`, `main.py` calls `transport.pipeline.run_visualization(experiment)` and returns without running validation.

If `visualization: false`, `main.py` calls `transport.pipeline.run_experiment(experiment)`, which runs transport once, validates the diagnostics, writes outputs, and returns pass/fail status.

---

## Module Responsibilities

### Entry and Pipeline
`transport/main.py`

Owns the command-line entry point. It parses `--experiment`, loads the experiment YAML, then chooses validation or visualization based on `experiment.outputs.visualization`.

`transport/pipeline.py`

Owns high-level execution orchestration. It contains:

- `run_transport(config, solver=None, mass=None)`
- `run_validation_reports(config, run_outputs_dir, solver=None)`
- `run_experiment(experiment, run_outputs_dir=None, print_reports=True)`
- `run_headless_suite(...)`
- `run_visualization(experiment)`

`run_experiment` is the main validation path. `run_visualization` is the visualization path.

`transport/simulation_config.py`

**Transitional compatibility layer** (see [architectural changes](architectural_changes.md)). Defines `SimulationConfig`, a bridge view built from an `Experiment`. It carries resolved runtime objects such as lattice, initial arrays, timestep, max steps, mass, and species. It also contains `expand_beam`, used by visualization when a non-Geant4, non-Gaussian single-particle source needs to be expanded into a displayed beam. Planned for removal once all consumers operate directly on resolved `Experiment` objects.

---

### Experiment Package
`transport/experiment/schema.py`

Owns experiment dataclasses:

- `ElementSpec`
- `LatticeSpec`
- `ParticleSourceSpec`
- `MetricSpec`
- `ValidationSpec`
- `ExperimentMeta`
- `Experiment`

`Experiment.from_dict` delegates parsing to the loader.

`transport/experiment/loader.py`

Owns YAML loading. It uses `yaml.safe_load`, extracts top-level YAML sections, and constructs typed dataclasses. Lattice sections are expanded by `_parse_lattice_elements`, which delegates to `transport.lattice.patterns` for `repeat` and `fodo` blocks.

`transport/experiment/resolver.py`

Owns conversion from declarative experiment objects into runtime objects. It builds particle sources, lattices, metrics, `SimulationConfig`, and `ValidationCase`.

`transport/experiment/examples/*.yaml`

Contains example experiments for all validated cases:

- `drift.yaml`, `dipole.yaml`, `quadrupole.yaml` — Level 1 single-element studies
- `drift_dipole.yaml`, `drift_quadrupole.yaml` — Level 2 simple composites
- `fodo.yaml`, `acol.yaml` — Level 2 beam-optics lattices (repeat blocks)

---

### I/O
`transport/io/data_io.py`

Owns Geant4 ROOT seed extraction. It finds `simulation.root` files under `interactions/runs/`, reads the `Seeds` tree with `uproot`, extracts positions and momenta, converts units, computes velocity and gamma, filters charged proton/antiproton seeds, and caches extracted arrays into NPZ files with a manifest.

---

### Lattice
`transport/lattice/lattice.py`

Owns beamline element classes and lattice composition:

- `Element`
- `Drift`
- `Dipole`
- `Quadrupole`
- `SimpleLattice`

Elements own local field and aperture behavior. `SimpleLattice` owns ordered placement of elements along `z`.

`Quadrupole` implements a linear quadrupole field ($B_x = ky$, $B_y = kx$) with focusing strength $k$.

`transport/lattice/patterns.py`

Owns declarative lattice expansion helpers used by the YAML loader:

- `expand_repeat_elements` — tiles a `cell` over a target length with optional `prefix`/`suffix` and closing drift
- `fodo_cell` / `expand_fodo_elements` — builds standard QF–Drift–QD–Drift cells
- `repeat_summary` — metadata about repeat tiling (cell count, remainder drift)

`transport/lattice/registry.py`

Owns the element registry and declarative lattice construction. It registers `drift`, `dipole`, and `quadrupole`, then builds a `SimpleLattice` from a resolved `LatticeSpec`.

---

### Physics
`transport/physics/particle_data.py`

Owns species mass and charge lookup. Current species table includes proton, antiproton, electron, positron, muon±, and pion±.

`transport/physics/boris_solver.py`

Owns the actual transport integrator. It provides aperture-loss handling, electromagnetic field queries, relativistic Boris velocity push, timestep evolution, diagnostics recording, and a visualization-specific physics loop.

---

### Validation Core
`transport/validation/config.py`

Owns validation-related configuration dataclasses and enums:

- `ComparisonDirection`
- `PassCriteria`
- `Tolerance`
- `ConvergenceConfig`
- `NumericalConfig`
- `OutputConfig`

`transport/validation/case.py`

Owns the declarative validation runtime model:

- `ValidationContext`
- `MetricEvaluation`
- `ValidationCase`

`transport/validation/engine.py`

Owns validation execution. It runs or receives transport diagnostics, resolves references, computes metrics, runs convergence strategy, renders reports, and writes outputs.

`transport/validation/solver.py`

Owns the solver abstraction and the adapter around the Boris solver.

`transport/validation/diagnostics.py`

Owns the versioned diagnostics wrapper around raw solver output.

`transport/validation/profiles.py`

Owns validation tier selection and metric assignment for composite cases. Three tiers are defined:

| Tier | Cases | Profile key | Metrics |
|------|-------|-------------|---------|
| Analytical | `drift`, `dipole`, `quadrupole` | `analytical` | Trajectory error, conservation, analytical/self convergence |
| Simple composite | `drift_dipole`, `drift_quadrupole` | `simple_composite` | Conservation, exit-state agreement, envelope, emittance drift, transmission |
| Beam optics | `fodo`, `acol` | `beam_optics` | Full beam diagnostics including transmission, particle loss, envelope, emittance |

`validation_tier(case_type)` maps case names to tiers. `apply_validation_profile(case, config)` replaces references and metric specs for non-analytical cases. Horizontal emittance drift is informational when the lattice contains a dipole (dispersion expected).

`transport/validation/registry.py`

Owns registries for cases, metrics, references, sources, convergence strategies, and solvers.

---

### Validation Cases
`transport/validation/cases/drift.py`

Builds the drift validation case (Level 1, analytical profile).

`transport/validation/cases/dipole.py`

Builds the dipole validation case (Level 1, analytical profile).

`transport/validation/cases/quadrupole.py`

Builds the quadrupole validation case (Level 1, analytical profile with paraxial reference).

`transport/validation/cases/drift_dipole.py`

Legacy case builder stub (Level 2). The programmatic builder still carries `TransferMatrixReference`, disabled convergence, and stub metadata. **YAML-driven validation does not use these defaults**: `case_for_config` invokes this builder, then `apply_validation_profile` replaces references and metrics with the `simple_composite` tier spec. Other Level 2 cases (`drift_quadrupole`, `fodo`, `acol`) route through `composite.py` directly; `drift_dipole` remains on the legacy builder path but behaves identically at runtime after profile application.

`transport/validation/cases/drift_quadrupole.py`

Builds the drift → quadrupole composite case (Level 2).

`transport/validation/cases/fodo.py`

Builds the repeating FODO lattice case (Level 2, beam-optics profile).

`transport/validation/cases/acol.py`

Builds the minimal ACOL-inspired beamline case (Level 2, beam-optics profile).

`transport/validation/cases/composite.py`

Shared builder for composite and beam-optics cases. Creates a `ValidationCase` with self-convergence enabled, then delegates to `apply_validation_profile` for tier-appropriate metrics.

`transport/validation/cases/solenoid.py`

Defines a solenoid validation case placeholder implemented using a drift lattice.

`transport/validation/cases/horn.py`

Defines a magnetic horn validation case placeholder implemented using a drift lattice.

`transport/validation/cases/gaussian_beam.py`

Builds a Gaussian beam validation case using `GaussianBeamSource`.

---

### Metrics
`transport/validation/metrics/base.py`

Defines the metric interface, metric scope, reference requirements, and metric result type.

`transport/validation/metrics/conservation.py`

Implements momentum and energy conservation metrics.

`transport/validation/metrics/trajectory.py`

Implements drift coordinate error, cyclotron radius error, and bend angle error metrics.

`transport/validation/metrics/numerical.py`

Contains convergence-study support.

`transport/validation/metrics/beam.py`

Implements beam-level metrics for composite validation:

- `CentroidMetric`, `RmsSizeMetric` — ensemble position statistics
- `ExitCentroidMetric`, `ExitDirectionMetric` — exit-plane centroid and angle (informational)
- `ExitStateAgreementMetric` — combined exit transverse position/angle spread (simple-composite tier)
- `TransmissionMetric`, `ParticleLossMetric` — survival fraction and loss curves (beam-optics tier)
- `BeamEnvelopeMetric` — RMS $\sigma_x$, $\sigma_y$ vs longitudinal position
- `HorizontalEmittanceDriftMetric`, `VerticalEmittanceDriftMetric` — relative emittance change $(\varepsilon-\varepsilon_0)/\varepsilon_0$
- `EmittanceMetric` — absolute plane emittance

`transport/validation/metrics/legacy.py`

Contains legacy conservation calculation functions used by current conservation metrics and the legacy validator adapter.

---

### References
`transport/validation/references/base.py`

Defines the reference-solution interface, reference types, capabilities, and result objects.

`transport/validation/references/analytical.py`

Implements drift, dipole, and quadrupole analytical references, plus a stub analytical reference.

`transport/validation/references/composite.py`

Implements `LatticeAnalyticalReference` for stitched multi-element paraxial trajectories (Drift + Quadrupole assemblies). This reference is **infrastructure only** — active composite and beam-optics tiers clear references via `apply_validation_profile` and validate through beam metrics instead.

`transport/validation/references/numerical.py`

Implements a numerical reference object and `find_exit_state`.

`transport/validation/references/transfer_matrix.py`

Implements a transfer-matrix reference object.

`transport/validation/references/experimental.py`

Implements an experimental reference object.

`transport/validation/references/external.py`

Implements an external-simulation reference object.

---

### Convergence
`transport/validation/convergence/base.py`

Defines `ConvergenceStrategy`.

`transport/validation/convergence/analytical.py`

Runs convergence against an analytical position function.

`transport/validation/convergence/self_convergence.py`

Runs reference-free self-convergence by comparing refined solutions.

---

### Sources
`transport/validation/sources/base.py`

Defines `ParticleBatch` and `ParticleSource`.

`transport/validation/sources/single.py`

Creates particles from explicit arrays.

`transport/validation/sources/geant4.py`

Creates particles from Geant4 ROOT-derived seeds.

`transport/validation/sources/gaussian_beam.py`

Creates synthetic Gaussian beams around configured center position and velocity.

`transport/validation/sources/file.py`

Creates particles from `.npz` or `.json` files.

---

### Reporting
`transport/validation/reporting/reporter.py`

Creates text reports from validation and convergence results.

`transport/validation/reporting/result_store.py`

Writes `report.txt`, `results.json`, `metrics.csv`, and `manifest.json`.

`transport/validation/reporting/plot_generator.py`

Generates plots from metric plot payloads:

- conservation, error, convergence (log–log for analytical; linear for composite)
- envelope, emittance (horizontal/vertical), transmission, loss

Longitudinal plots annotate element boundaries via `_annotate_lattice_elements`.

`transport/validation/reporting/lattice_annotations.py`

Provides element display labels (Drift, QF, QD, Dipole), `lattice_elements_payload` for plot metadata, and `uses_longitudinal_position` detection.

---

### Visualization
`transport/visualization/viewport.py`

Owns the VisPy renderer. It reads shared-memory particle positions, renders trails, draws lattice geometry, and updates a HUD.

`transport/visualization/primitives.py`

Owns drawing helper functions for tubes, boxes, rings, aperture rings, and pipe wireframes.

---

### Legacy Validation
`transport/validation/base.py`

Defines `LegacyValidationCase` and aliases it as `ValidationCase`.

`transport/validation/validator.py`

Provides backward-compatible validation APIs. For current declarative cases, it delegates to `ValidationEngine`.

`transport/validation/plots.py`

Contains legacy plotting helpers for conservation/error plots and convergence plots.

---

## Class Reference

### Experiment Classes
`ElementSpec`

Represents one YAML lattice element. It stores `type` and a free-form `params` dictionary. It is created by the YAML loader and consumed by `build_lattice`.

`LatticeSpec`

Represents the full lattice section of YAML. It owns `z_start` and ordered `elements`. It is created by the loader and consumed by `transport.lattice.registry.build_lattice`.

`ParticleSourceSpec`

Represents the YAML particle source section. It owns source type, species, charge filter, particle count, optional momentum slice, explicit position/velocity/gamma, Gaussian spread settings, RNG seed, and optional file path. It is consumed by `build_particle_source`.

`MetricSpec`

Represents a metric override from YAML. It stores metric name, tolerance, comparison direction, and informational flag. It is consumed by `build_metric_specs`.

`ValidationSpec`

Stores optional metric specs and pass criteria.

`ExperimentMeta`

Stores experiment identity: name, level, case, and output directory.

`Experiment`

Top-level in-memory experiment. It owns meta, source spec, lattice spec, numerical config, validation config, and output config. It is created by `load_experiment` and consumed by `main.py`, `pipeline.py`, and `resolver.py`.

---

### Configuration Classes
`Tolerance`

Stores numeric threshold, comparison direction, and whether the metric is informational.

`ConvergenceConfig`

Stores whether convergence is enabled, number of points, refinement ratio, legacy self-convergence flag, and convergence `mode`.

`NumericalConfig`

Stores timestep, max steps, convergence settings, and solver name.

`OutputConfig`

Stores output toggles: report, JSON, CSV, manifest, plots, visualization, output directory, and pass criteria.

`SimulationConfig`

Compatibility runtime config. It owns resolved lattice, initial arrays, timestep, max steps, max convergence steps, mass, species, and case type. It is created by `experiment_to_simulation_config`. Marked for removal; see [architectural changes](architectural_changes.md).

---

### Lattice Classes
`Element`

Base element class. It owns length, aperture radius, `z_start`, and `z_end`. It provides:

- `field(x, y, z)` returning magnetic field
- `em_field(x, y, z)` returning zero electric field plus magnetic field
- `inside_aperture(x, y, z)`
- `draw(view)`

`Drift`

Element subclass with zero magnetic field. It draws a drift volume and optional aperture pipe.

`Dipole`

Element subclass with uniform vertical magnetic field `By`. It draws field volume and optional aperture pipe.

`Quadrupole`

Element subclass with linear quadrupole field ($B_x = ky$, $B_y = kx$). Focusing strength $k>0$ denotes QF; $k<0$ denotes QD. It draws a field box and optional aperture pipe.

`SimpleLattice`

Owns ordered elements. During construction, `_build` assigns each element’s `z_start` and `z_end`. It provides:

- `get_element_at_z`
- `get_field`
- `get_em_field`
- `inside_aperture`
- `draw`

It is created by `build_lattice` or validation case builders and consumed by the solver, metrics, reporter, and renderer.

`ElementRegistry`

Stores element factories by lowercase name. It is used by `build_lattice` to convert YAML element specs into concrete `Element` instances.

---

### Particle Source Classes
`ParticleBatch`

Runtime particle container. It owns:

- `R`: positions
- `V`: velocities
- `gamma`
- `charges`
- `mass`
- `species`
- `metadata`

It is created by `ParticleSource.generate` and consumed by the solver and validation engine.

`ParticleSource`

Abstract base class requiring `generate()`. It also provides a default `description`.

`SingleParticleSource`

Stores explicit arrays and returns a copied `ParticleBatch`. Used for single/mock sources and inside validation case builders.

`Geant4ParticleSource`

Loads the latest `simulation.root`, extracts seeds through `data_io`, filters them, and returns a `ParticleBatch`. It supports `charge_filter`, `momentum_slice`, `particle_index`, `species`, and `n_particles`.

For validation, `validation_case_from_experiment` requires Geant4 `n_particles` to be `1`, and composite lattices (`len(elements) > 1`) to have `n_particles >= 2`. For visualization, `experiment_to_simulation_config` can produce multiple Geant4 particles.

`GaussianBeamSource`

Creates a Gaussian beam around configured center position and velocity. It owns particle count, position sigma, velocity sigma, and RNG seed.

`FileParticleSource`

Loads particles from `.npz` or `.json` files and returns a `ParticleBatch`.

---

### Solver and Diagnostics Classes
`Solver`

Runtime protocol defining the expected solver `run` signature.

`BorisSolverAdapter`

Default solver adapter. It wraps `transport.physics.boris_solver.track_particles`, supplies default proton mass when no mass is passed, and converts raw diagnostics into `Diagnostics`.

`AbstractSolver`

ABC with the same general run method shape.

`Diagnostics`

Frozen dataclass wrapping solver output. It owns schema version, step, time, position, momentum, gamma, field, element, and alive arrays. `Diagnostics.from_dict` validates required keys and converts arrays.

---

### Validation Classes
`ValidationCase`

Declarative validation unit. It owns:

- name
- level
- system builder
- particle source
- numerical config
- references
- metric specs
- output config
- metadata

It is created by case builder functions and consumed by `ValidationEngine`.

`ValidationContext`

Read-only bundle passed into references and metrics. It contains diagnostics, lattice, initial arrays, charges, mass, particle source metadata, resolved references, numerical config, and case metadata.

`MetricEvaluation`

Stores the result of one metric after tolerance application.

`ValidationEngine`

Executes validation. It creates or receives diagnostics, resolves references, builds validation context, computes metrics, runs convergence strategy, renders reports, writes result artifacts, and returns a result dictionary.

`Validator`

Backward-compatible adapter. With current declarative `ValidationCase` objects, it delegates to `ValidationEngine`.

---

### Metric Classes
`Metric`

Abstract base class for validation metrics. It defines name, unit, scope, reference requirement, applicability checks, and `compute`.

`MetricResult`

Stores metric value, optional per-particle values, and optional plot payload.

`MomentumConservationMetric`

Computes max relative momentum drift using legacy metric logic. It also contributes a conservation plot payload.

`EnergyConservationMetric`

Computes max relative gamma drift using legacy metric logic.

`DriftCoordinateErrorMetric`

Compares drift coordinates against a pointwise reference trajectory.

`CyclotronRadiusErrorMetric`

Fits dipole trajectory points to a circle and compares radius to analytical radius.

`BendAngleErrorMetric`

Computes bend-angle error from entry and exit momentum direction.

`ConvergenceStudyMetric`

Metric placeholder for convergence; convergence itself is executed separately by the engine.

`CentroidMetric`, `RmsSizeMetric`, `TransmissionMetric`, `EmittanceMetric`

Legacy beam-level metric classes operating on final diagnostics.

`ExitStateAgreementMetric`, `ExitCentroidMetric`, `ExitDirectionMetric`

Exit-plane composition metrics for simple-composite validation.

`BeamEnvelopeMetric`, `HorizontalEmittanceDriftMetric`, `VerticalEmittanceDriftMetric`

Longitudinal beam diagnostics for composite and beam-optics tiers.

`ParticleLossMetric`

Complement of transmission ($1 - \text{transmission}$) for beam-optics cases.

---

### Reference Classes
`ReferenceSolution`

Abstract base class for reference solutions. It defines name, reference type, capabilities, and `resolve`.

`ReferenceResult`

Resolved reference data object. It can carry pointwise trajectories, summary observables, moment propagation, boundary states, and metadata.

`DriftAnalyticalReference`

Produces analytical drift trajectory from diagnostics and initial velocity.

`DipoleAnalyticalReference`

Produces dipole summary observables and has `position_at_time` for analytical convergence.

`QuadrupoleAnalyticalReference`

Produces paraxial quadrupole pointwise trajectory under constant $p_z$.

`StubAnalyticalReference`

Reference object with no capabilities.

`NumericalReference`

Reference object with pointwise-trajectory capability metadata.

`TransferMatrixReference`

Reference object carrying optional transfer matrix data.

`ExperimentalReference`

Reference object carrying optional experimental data path.

`ExternalSimulationReference`

Reference object carrying optional external simulation path.

---

### Convergence Classes
`ConvergenceStrategy`

Abstract base class with `run(case, context, solver)`.

`AnalyticalConvergence`

Looks for `case.metadata["analytical_position_fn"]`. If present, it calls `run_convergence_study`.

`SelfConvergence`

Runs a refinement ladder and compares each coarse-grid exit state to the **finest-grid** exit position (not successive pairs). For composite and beam-optics tiers, convergence plots use **linear** error-versus-$\Delta t$ axes; single-element analytical cases use log–log axes.

---

### Reporting and Visualization Classes
`Reporter`

Static report renderer for validation and convergence reports.

`ResultStore`

Writes report, JSON, CSV, and manifest files under an output directory.

`PlotGenerator`

Consumes metric plot payloads and writes PNG plots.

The visualization package does not define renderer classes. It provides `run_renderer` plus drawing helper functions.

---

## Registry Reference
The current registry implementation lives in `transport/validation/registry.py` and `transport/lattice/registry.py`.

### Generic `Registry`
Stores lowercase names mapped to factories. It supports:

- `register(name, factory)`
- `get(name)` for zero-argument factory construction
- `build(name, **kwargs)` for keyword construction
- `list_names()`

### `case_registry`
Stores validation case factories.

Registered names:

- `drift`
- `dipole`
- `drift_dipole`
- `drift_quadrupole`
- `quadrupole`
- `fodo`
- `acol`
- `solenoid`
- `horn`
- `gaussian_beam`

`case_for_config(config)` uses `_case_config_builders`, populated for all Level 1 and Level 2 validated cases:

- `drift`, `dipole`, `quadrupole`
- `drift_dipole`, `drift_quadrupole`
- `fodo`, `acol`

For composite and beam-optics cases, `case_for_config` calls `apply_validation_profile` to assign tier-appropriate metrics.

### `metric_registry`
Stores metric factories.

Registered names:

- `momentum_conservation`
- `energy_conservation`
- `x_error`
- `y_error`
- `z_error`
- `cyclotron_radius_error`
- `bend_angle_error`
- `centroid_x`
- `rms_x`
- `transmission`
- `beam_envelope`
- `exit_centroid`
- `exit_direction`
- `exit_state_agreement`
- `particle_loss`
- `horizontal_emittance_drift`
- `vertical_emittance_drift`
- `emittance_x`

YAML metric overrides are resolved through this registry by `build_metric_specs`.

### `reference_registry`
Stores reference factories.

Registered names:

- `drift_analytical`
- `stub_analytical`
- `transfer_matrix`
- `numerical`
- `experimental`
- `external`

Current case builders instantiate references directly; the registry is populated but not used by the YAML resolver for default cases.

### `source_registry`
Stores source factories.

Registered names:

- `single`
- `mock`
- `geant4`
- `gaussian_beam`
- `file`

The resolver manually handles `single`, `mock`, `geant4`, and `gaussian_beam`. It uses `source_registry.build("file", path=...)` for file sources.

### `convergence_registry`
Stores convergence strategies.

Registered names:

- `analytical`
- `self`

`ValidationEngine` looks up `num_cfg.convergence.mode` here.

### `solver_registry`
Stores solver factories.

Registered names:

- `boris`

`pipeline.run_experiment` uses `solver_registry.build(experiment.numerical.solver_name)`.

### `element_registry`
Lives in `transport/lattice/registry.py`.

Registered names:

- `drift`
- `dipole`
- `quadrupole`

`build_lattice` uses this registry to construct `SimpleLattice` from YAML `ElementSpec` objects. The loader may expand `repeat` or `fodo` blocks into flat element lists before `build_lattice` is called.

### Registration Timing
`initialize_registries()` registers all validation-side registries and calls `register_builtin_elements()`.

It is called by:

- `pipeline.run_experiment`
- `pipeline.run_visualization`
- `simulation_config.validation_case_for_config`
- `experiment.resolver.validation_case_from_experiment`

---

## Experiment System
An experiment YAML has five main sections:

```yaml
experiment:
particle_source:
lattice:
numerical:
validation:
outputs:
```

### Loader
`load_experiment(path)` opens the YAML file, calls `yaml.safe_load`, and delegates to `Experiment.from_dict`.

`Experiment.from_dict` calls `parse_experiment_dict`.

The loader supports three mutually exclusive lattice declaration styles (see `lattice` configuration below):

- flat `elements` list
- `repeat` block (cell tiling with optional prefix/suffix)
- `fodo` block (FODO cell shorthand)

`parse_experiment_dict` creates:

- `ExperimentMeta`
- `ParticleSourceSpec`
- `LatticeSpec`
- `NumericalConfig`
- `ConvergenceConfig`
- `ValidationSpec`
- `OutputConfig`
- `Experiment`

### Resolver
The resolver turns specs into runtime objects.

`build_particle_source(spec)` creates one of:

- `SingleParticleSource`
- `Geant4ParticleSource`
- `GaussianBeamSource`
- `FileParticleSource`

`experiment_to_simulation_config(experiment)`:

1. Builds the particle source.
2. Generates a `ParticleBatch`.
3. Builds the lattice.
4. For Geant4, resets lattice `z_start` to the first generated particle’s `z`.
5. Returns `SimulationConfig`.

`validation_case_from_experiment(experiment)`:

1. Rejects Geant4 validation if `n_particles != 1`.
2. Initializes registries.
3. Converts experiment to `SimulationConfig`.
4. Rejects composite lattice validation if `len(elements) > 1` and `n_particles < 2` (requires `gaussian_beam` with at least two particles).
5. Resolves the case via `case_for_config` (applies validation profile for composite/beam-optics tiers).
6. Replaces the case particle source with one built directly from the experiment source spec.
7. Replaces numerical and output config with experiment-provided config.
8. Replaces metric specs if YAML provided explicit metrics.

---

## Validation Framework
The validation framework executes around `ValidationCase`.

A `ValidationCase` contains:

- a callable that builds the lattice/system
- a particle source
- numerical parameters
- references
- metric/tolerance pairs
- output settings
- metadata

For composite and beam-optics cases, `apply_validation_profile` (in `profiles.py`) replaces case-default references and metrics with tier-appropriate specs before execution.

`ValidationEngine.run` is the central execution path.

### Validation Tiers
```text
experiment.case
↓
validation_tier(case_type)
↓
analytical | simple_composite | beam_optics
↓
apply_validation_profile (composite / beam-optics only)
↓
ValidationCase with tier-appropriate metric_specs
```

Single-element cases retain analytical references and trajectory metrics defined in their case builders. Composite cases drop analytical references and use beam diagnostics instead.

### Engine Flow
1. Choose lattice:
   - use `prebuilt_lattice`, or
   - call `case.build_system()`

2. Choose particle batch:
   - use `prebuilt_batch`, or
   - call `case.particle_source.generate()`

3. Choose diagnostics:
   - use `prebuilt_diagnostics`, or
   - run solver

4. Build an initial `ValidationContext` with empty references.

5. Resolve every reference in `case.references`.

6. Build a second `ValidationContext` containing resolved references.

7. Iterate over metric specs.

8. For each metric:
   - check applicability
   - compute value
   - apply tolerance
   - collect optional plot payload

9. If convergence is enabled:
   - look up convergence strategy
   - run convergence
   - render convergence report
   - collect convergence plot payload

10. Render validation report.

11. Aggregate pass/fail.

12. If output writing is enabled and `run_outputs_dir` is provided:
   - save report
   - save JSON
   - save CSV
   - save manifest
   - generate plots

13. Return result dictionary.

### Diagnostics
Diagnostics are arrays over time and particles:

- `step`
- `time`
- `position`
- `momentum`
- `gamma`
- `field`
- `element`
- `alive`

The solver creates raw diagnostics as a dictionary. `BorisSolverAdapter` wraps it in `Diagnostics.from_dict`.

### References
References resolve before metrics. Metrics ask the context for resolved references and use capabilities to decide applicability.

### Metrics
Metrics produce `MetricResult`. The engine converts that into `MetricEvaluation` by applying tolerance.

### Reporting
The `Reporter` renders text. `ResultStore` persists structured outputs. `PlotGenerator` turns payload dictionaries into PNG files.

---

## Transport Physics
Transport is performed by `transport/physics/boris_solver.py`.

### Lattice Traversal
Particles carry global `x, y, z` positions. The lattice is a sequence of elements along `z`.

`SimpleLattice.get_element_at_z(z)` returns the element whose `z_start <= z <= z_end`.

Array field queries loop over elements and mask particles by `z`.

### Field Queries
Elements expose:

```text
field(x, y, z) -> (Bx, By, Bz)
em_field(x, y, z) -> ((Ex, Ey, Ez), (Bx, By, Bz))
```

Current implemented elements:

- `Drift`: zero magnetic field
- `Dipole`: uniform `By`
- `Quadrupole`: linear field $B_x = ky$, $B_y = kx$

The base `Element.em_field` returns zero electric field and magnetic field from `field`.

The Boris push uses `lattice.get_em_field`.

Diagnostics currently store magnetic field from `lattice.get_field`.

### Species
Species mass and charge are resolved through `particle_data.py`.

Sources assign:

- `ParticleBatch.mass`
- `ParticleBatch.species`
- `ParticleBatch.charges`

The validation solver passes mass into `track_particles`.

### Boris Integrator
`track_particles`:

1. Copies initial `R` and `V`.
2. Resolves mass array.
3. Computes gamma from velocity.
4. Initializes all particles alive.
5. Applies a backward half-step velocity push.
6. Applies aperture losses.
7. Iterates for `max_steps`.
8. At each step:
   - stores old state
   - performs relativistic Boris step
   - synchronizes diagnostics
   - records position, momentum, gamma, field, element names, alive mask
   - applies aperture losses
   - increments time
9. Performs final velocity unstaggering.
10. Records final diagnostics.
11. Returns final `R`, final `V`, alive mask, raw diagnostics.

`boris_velocity_push` performs the relativistic velocity update using electric field, magnetic field, charge, and mass.

`relativistic_boris_step` calls velocity push, then advances position by `V * dt`.

### Aperture Losses
`apply_aperture_losses` calls `lattice.inside_aperture` and updates the alive mask. Lost particles remain in arrays but are marked dead.

### Visualization Physics Loop
`run_visual_physics_loop` uses shared memory to stream particle positions to the renderer. It repeatedly advances particles and writes renderable positions, replacing lost-particle positions with `NaN`.

---

## Configuration System

### `experiment`
Fields:

- `name`
- `level`
- `case`
- `output_dir`

These become `ExperimentMeta`.

### `particle_source`
Fields:

- `type`
- `species`
- `charge_filter`
- `n_particles`
- `momentum_slice`
- `position`
- `velocity`
- `gamma`
- `pos_sigma`
- `vel_sigma`
- `rng_seed`
- `path`

These become `ParticleSourceSpec`.

Propagation:

```text
ParticleSourceSpec
↓
build_particle_source
↓
ParticleSource
↓
ParticleBatch
↓
SimulationConfig / ValidationCase / Solver
```

### `lattice`
The lattice section accepts exactly one of three declaration styles:

**Flat elements:**

```yaml
lattice:
  z_start: 0.0
  elements:
    - {type: drift, length: 5.0, aperture: 10.0}
    - {type: quadrupole, length: 1.0, k: 0.5, aperture: 10.0}
```

**Repeat block** (cell tiling):

```yaml
lattice:
  z_start: 0.0
  repeat:
    length: 50.0
    aperture: 1.0
    prefix:
      - {type: drift, length: 5.0}
    cell:
      - {type: quadrupole, length: 1.0, k: 0.5}
      - {type: drift, length: 2.0}
      - {type: quadrupole, length: 1.0, k: -0.5}
      - {type: drift, length: 2.0}
```

**FODO shorthand:**

```yaml
lattice:
  z_start: 0.0
  fodo:
    length: 50.0
    k: 0.5
    quadrupole_length: 1.0
    drift_length: 2.0
    aperture: 1.0
```

Each element has:

- `type`
- element-specific params such as `length`, `aperture`, `by` (dipole), `k` (quadrupole)

Propagation:

```text
LatticeSpec (flat elements after loader expansion)
↓
build_lattice
↓
ElementRegistry
↓
Drift / Dipole / Quadrupole
↓
SimpleLattice
```

### `numerical`
Fields:

- `dt`
- `max_steps`
- `max_steps_conv`
- `solver`
- `convergence`

Propagation:

```text
NumericalConfig
↓
ValidationCase.numerical_config
↓
Solver run / convergence strategy
```

### `convergence`
Fields:

- `enabled`
- `mode`
- `num_points`
- `refinement_ratio`
- `use_self_convergence`

Propagation:

```text
ConvergenceConfig
↓
ValidationEngine
↓
convergence_registry
↓
AnalyticalConvergence / SelfConvergence
```

### `validation`
Fields:

- `metrics`
- `pass_criteria`

If metrics are present, the resolver builds explicit metric/tolerance pairs through `metric_registry`. If omitted, case defaults remain.

### `outputs`
Fields:

- `report`
- `json`
- `csv`
- `manifest`
- `plots`
- `visualization`

`visualization` is checked by `main.py`. If true, validation is bypassed.

---

## End-to-End Data Flow

### Analytical Validation (Level 1, Geant4 or mock)
```text
Geant4 engine
↓
interactions/runs/<run>/simulation.root
↓
transport.io.data_io.get_latest_run_file
↓
transport.io.data_io.extract_cern_ad_seeds
↓
positions, velocities, gammas, charges
↓
Geant4ParticleSource.generate (n_particles: 1)
↓
ParticleBatch
↓
Experiment resolver → ValidationCase (analytical tier)
↓
BorisSolverAdapter → track_particles → Diagnostics
↓
ValidationContext → ReferenceSolution.resolve
↓
Trajectory + conservation metrics
↓
Reporter / ResultStore / PlotGenerator
↓
report.txt, results.json, metrics.csv, manifest.json, plots
```

### Composite / Beam-Optics Validation (Level 2, Gaussian beam)
```text
YAML experiment (gaussian_beam, n_particles ≥ 2)
↓
loader._parse_lattice_elements (repeat / fodo expansion if present)
↓
build_lattice → SimpleLattice
↓
case_for_config → apply_validation_profile (references cleared)
↓
GaussianBeamSource.generate → ParticleBatch
↓
BorisSolverAdapter → track_particles → Diagnostics
↓
Beam metrics (envelope, emittance drift, transmission, loss)
↓
PlotGenerator + lattice_annotations (element boundaries on z plots)
↓
transport/validation/outputs/run_<timestamp>/<case>/
```

### ROOT / NPZ Loading
`data_io` reads ROOT branches:

- `Seeds/pdg_code`
- `Seeds/start_x`
- `Seeds/start_y`
- `Seeds/start_z`
- `Seeds/start_px`
- `Seeds/start_py`
- `Seeds/start_pz`

Positions are converted from mm to m. Momenta are used to compute total energy, gamma, and velocity. Only protons and antiprotons are retained. A momentum cut of 3480 to 3680 MeV/c is applied in `_parse_single_root`.

Extracted arrays are cached as:

```text
merged_seeds_cache_v4.npz
merged_seeds_manifest_v4.json
```

### Experiment to Validation Case
The YAML loader owns static configuration. The resolver owns executable conversion. The case builder owns default references and metrics. The validation engine owns execution.

### Validation Results
The validation engine owns generated evaluations. `Reporter` owns text formatting. `ResultStore` owns files. `PlotGenerator` owns PNG output.

### Visualization Flow
```text
Experiment
↓
experiment_to_simulation_config
↓
ParticleBatch + SimpleLattice
↓
run_visualization
↓
SharedMemory buffer + sync queue + stop event
↓
physics process: run_visual_physics_loop
↓
renderer process: run_renderer
↓
VisPy viewport
```

For Geant4 visualization, `Geant4ParticleSource` returns `n_particles` particles from ROOT-derived seeds. `run_visualization` uses them directly. It does not call `expand_beam` for Geant4.

For Gaussian beam visualization, the generated Gaussian beam is used directly.

For other single-particle sources, `expand_beam` creates a displayed beam by tiling the initial particle and adding Gaussian offsets.

---

## Dependency Graph
```text
transport.main
├── transport.experiment.loader
└── transport.pipeline
    ├── transport.experiment.resolver
    ├── transport.validation.registry
    ├── transport.validation.engine
    ├── transport.validation.solver
    ├── transport.physics.boris_solver
    ├── transport.simulation_config
    └── transport.visualization.viewport

transport.experiment.loader
├── transport.experiment.schema
├── transport.validation.config
└── transport.lattice.patterns   # repeat/fodo expansion

transport.experiment.resolver
├── transport.experiment.schema
├── transport.lattice.registry
├── transport.physics.particle_data
├── transport.simulation_config
├── transport.validation.config
├── transport.validation.registry
└── transport.validation.sources.*

transport.lattice.registry
└── transport.lattice.lattice

transport.validation.engine
├── transport.validation.case
├── transport.validation.config
├── transport.validation.profiles
├── transport.validation.reporting.*
├── transport.validation.registry   # case_for_config → profiles
└── transport.validation.solver

transport.validation.solver
├── transport.physics.boris_solver
└── transport.validation.diagnostics

transport.physics.boris_solver
└── lattice object interface: get_em_field, get_field, inside_aperture

transport.validation.metrics.*
├── transport.validation.case
├── transport.validation.metrics.base
├── transport.validation.references.*
└── transport.validation.metrics.legacy

transport.validation.references.*
└── transport.validation.case

transport.validation.sources.*
├── transport.validation.sources.base
├── transport.physics.particle_data
└── transport.io.data_io   # Geant4 source only

transport.visualization.viewport
└── transport.visualization.primitives indirectly through lattice.draw
```

Ownership boundaries in the current implementation:

- Experiment package owns configuration objects and parsing.
- Resolver owns conversion from configuration to runtime objects.
- Lattice package owns beamline elements and field interfaces.
- Physics package owns particle motion.
- Validation package owns validation semantics, tier profiles, and output artifacts.
- Visualization package owns rendering.
- I/O package owns ROOT seed extraction.

Dependency directions follow runtime flow: entrypoint depends on experiment and pipeline; pipeline depends on resolver, solver, engine, and visualization; solver depends on lattice interface but lattice does not depend on solver; metrics and references depend on validation context but not on the pipeline.

---

## Execution Timeline

### Validation Run
Command:

```bash
python -m transport.main --experiment experiment.yaml
```

Chronological flow:

1. Python imports `transport.main`.
2. `main()` inserts project root into `sys.path`.
3. `argparse` parses `--experiment`.
4. `load_experiment(path)` opens YAML and calls `yaml.safe_load`.
5. `Experiment.from_dict` calls `parse_experiment_dict`.
6. Loader builds experiment objects; `_parse_lattice_elements` expands `repeat`/`fodo` blocks if present.
7. `main.py` checks `experiment.outputs.visualization`.
8. If false, `run_experiment(experiment)` is called.
9. `run_experiment` calls `initialize_registries`.
10. Built-in elements, cases, metrics, references, sources, convergence strategies, and solvers are registered.
11. `validation_case_from_experiment` is called.
12. If source is Geant4 and `n_particles != 1`, a `ValueError` is raised.
13. `experiment_to_simulation_config` is called.
14. `build_particle_source` creates a source object.
15. Source `generate()` creates a `ParticleBatch`.
16. `build_lattice` creates elements and a `SimpleLattice`.
17. Geant4 lattices reset `z_start` to the first particle’s `z`.
18. If lattice has multiple elements and `n_particles < 2`, a `ValueError` is raised.
19. `SimulationConfig` is created.
20. `case_for_config` selects the config-backed case builder.
21. Case builder creates a `ValidationCase`.
22. For composite/beam-optics cases, `apply_validation_profile` assigns tier metrics and clears analytical references.
23. Resolver replaces case particle source, numerical config, output config, and optional metric specs.
24. `solver_registry.build(experiment.numerical.solver_name)` creates `BorisSolverAdapter`.
25. `run_experiment` calls `validation_case.particle_source.generate()`.
26. `validation_case.build_system()` returns the lattice.
27. Solver runs transport with initial arrays, lattice, dt, max steps, and mass.
28. `track_particles` advances particles and records raw diagnostics.
29. `BorisSolverAdapter` wraps diagnostics in `Diagnostics`.
30. `ValidationEngine.run` is called with prebuilt lattice and diagnostics.
31. Engine generates a new batch from the case particle source.
32. Engine builds `ValidationContext`.
33. Engine resolves references (skipped when reference list is empty).
34. Engine computes each metric.
35. Engine applies tolerances and creates `MetricEvaluation` objects.
36. If convergence is enabled, engine resolves convergence strategy and runs it.
37. Engine renders validation report (includes `Validation Profile` tier label).
38. Engine computes overall pass/fail.
39. Engine creates output case directory.
40. Engine writes report, JSON, CSV, manifest, and plots according to output settings.
41. `run_experiment` prints reports.
42. `run_experiment` returns pass/fail and output directory.
43. `main.py` prints `STATUS: PASS` or `STATUS: FAIL`.
44. Process exits with status code 0 or 1.

### Visualization Run
Command is the same, but YAML has:

```yaml
outputs:
  visualization: true
```

Chronological flow:

1. Steps 1 through 7 are the same.
2. `main.py` calls `run_visualization(experiment)` and returns afterward.
3. `run_visualization` sets multiprocessing start method to `spawn`.
4. It initializes registries.
5. It calls `experiment_to_simulation_config`.
6. Source generates particle arrays.
7. Lattice is built.
8. If source type is `geant4` or `gaussian_beam`, arrays are used directly.
9. If source is another single-particle source, `expand_beam` creates a 1000-particle display beam.
10. Shared memory is allocated for two position buffers.
11. A sync queue and stop event are created.
12. A physics process is created for `run_visual_physics_loop`.
13. A renderer process is created for `run_renderer`.
14. Physics process writes particle positions into shared memory.
15. Renderer process reads latest positions and updates VisPy markers.
16. Renderer draws lattice geometry through `lattice.draw`.
17. When renderer exits, stop event is set.
18. Physics process is joined or terminated.
19. Shared memory is closed and unlinked.

---

## Glossary
`Experiment`

Top-level in-memory representation of a YAML transport study.

`ParticleSourceSpec`

Declarative particle-source configuration from YAML.

`ParticleSource`

Runtime object that creates a `ParticleBatch`.

`ParticleBatch`

Arrays of particle positions, velocities, gamma, charges, mass, species, and metadata.

`LatticeSpec`

Declarative lattice configuration from YAML.

`Element`

One beamline component with length, aperture, field, and drawing behavior.

`SimpleLattice`

Ordered sequence of elements placed along `z`.

`SimulationConfig`

Runtime compatibility object containing resolved lattice, particle arrays, and numerical parameters.

`ValidationCase`

Executable validation definition: source, system builder, references, metrics, numerics, outputs.

`ValidationContext`

Read-only bundle passed to references and metrics.

`Diagnostics`

Versioned wrapper around solver output arrays.

`Metric`

Validation computation producing a scalar result and optional plot payload.

`ReferenceSolution`

Object that resolves analytical, numerical, transfer-matrix, experimental, or external reference data.

`ConvergenceStrategy`

Object that runs a convergence study.

`BorisSolverAdapter`

Validation-facing wrapper around the Boris transport implementation.

`track_particles`

Core transport routine that advances particles and records diagnostics.

`ResultStore`

File writer for validation artifacts.

`PlotGenerator`

Matplotlib plot writer driven by metric payload dictionaries. Supports conservation, error, convergence, envelope, emittance, transmission, and loss plot types. Annotates longitudinal plots with element-boundary markers.

`ValidationProfile` / validation tier

Automatic metric assignment keyed by experiment `case` name: `analytical`, `simple_composite`, or `beam_optics`. Defined in `transport.validation.profiles`.

`run_renderer`

VisPy renderer that displays lattice geometry and particle trails.

`Geant4 seed`

A transport initial condition extracted from a Geant4 ROOT `Seeds` tree.
