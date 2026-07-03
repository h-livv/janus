# Janus Transport Framework — Seam-Elimination Milestone

## Design Specification: Centralized Experiments, Composite Lattices, Multi-Species, Pluggable Convergence, and Full Registry-Driven Extension

---

## Executive Summary

The prior review concluded that Janus can grow primarily through extension along the validation-methodology axis, but that three localized seams and several smaller gaps still force source edits: (1) a branchy config/entry layer (`simulation_config.py`, `main.py`), (2) proton-mass and Cartesian assumptions in the physics substrate, and (3) an eager diagnostics model (explicitly out of scope for this milestone). This specification patches the *first two* families of seams plus the specific gaps the review flagged — dead convergence config, missing element registry, and the magnetostatic-only field interface — **without redesigning the validation engine, metrics, references, diagnostics, reporting, plotting, or the solver abstraction.**

The unifying move is to make an **Experiment** — an external, declarative description (recommended: YAML) parsed into typed config objects — the single source of truth, and to make **lattice elements**, **particle species/mass**, and **convergence strategies** flow through the same registry + strategy composition the framework already uses. After this milestone, adding a lattice element, particle species, validation case, or convergence strategy requires only *implement + register*; running a new study requires only editing a YAML file.

Two changes reach (minimally) into the physics kernel: per-particle mass and an additive `em_field` interface. Both are backward-compatible extensions (defaults preserve current behavior), not redesigns.

---

## Architectural Context

Findings from the review that directly motivate each requested improvement (summary only):

- **Req 1 (Centralized config):** The entry layer still hardcodes per-element numeric blocks and dispatch. `simulation_config._numerical_params` and `main.py` constant blocks mean new studies require Python edits.
- **Req 2 (Composite lattices):** `SimpleLattice` already accepts arbitrary element lists, but `simulation_config.build_lattice` can only produce single drift/dipole lattices, and cases each build their own lattice. Composite beamlines cannot be expressed declaratively.
- **Req 3 (Multi-species):** `boris_solver.py` hardcodes `M_P_KG`/`M_P_MEV`; `references/analytical.py` re-hardcodes `M_P_KG`; `ParticleBatch` carries no mass. Species metadata is written by sources but never consumed.
- **Req 4 (Self-convergence):** `ConvergenceConfig.use_self_convergence` and `refinement_ratio` are defined but never read; convergence in `engine.py` is gated on `case.metadata["analytical_position_fn"]`, so reference-free convergence is impossible.
- **Req 5 (Hardcoded drift/dipole):** Branching persists in `simulation_config.build_lattice`, `_numerical_params`, `load_geant4_initial_conditions` (charge filter keyed off `case_type`), and `main.py`.
- **Req 6 (Registries):** `case/metric/reference/source` registries exist; **no element registry and no convergence registry** exist.
- **Req 7 (EM field):** `Element.field` returns B only; `boris_solver` sets `E_alive = 0`. RF/deceleration/cooling on the roadmap will force a later interface break unless E is admitted now.
- **Req 8 (Experiment identity):** `SimulationConfig` is conceptually a simulation config, not an experiment; it omits source/validation/output declarations that a scientific experiment record should own.

The seams are all *outside* the validation engine. This milestone confirms that boundary by leaving the engine's orchestration loop intact.

---

## Design Objectives

1. Changing a validation study requires **zero** Python edits — only an experiment file.
2. Arbitrary beamlines are expressed by **listing elements**; validation/diagnostics/metrics/reporting/plotting consume them unchanged.
3. Any charged species is supported by **declaring the species**; mass/charge flow from source → solver → references → metrics.
4. Convergence supports **analytical and self-convergence** as pluggable strategies; new strategies need no engine edits.
5. New lattice elements and cases require **implement + register**, nothing more.
6. The field interface admits **E and B** now, with E defaulting to zero, so no later interface break.
7. The framework revolves around a first-class **Experiment**.

Non-objectives (explicitly preserved): engine loop, metric ABC, reference ABC, `Diagnostics` structure, reporter, plot generator, `Solver` protocol.

---

## Design Strategy (Phase 2)

### 1. Centralized Experiment Configuration

- **Objective:** One authoritative, declarative description of an entire experiment.
- **Ownership:** A new `transport/experiment/` package owns parsing and validation. The in-memory representation **reuses existing dataclasses** (`NumericalConfig`, `ConvergenceConfig`, `OutputConfig`, `Tolerance`) and adds `ParticleSourceSpec`, `LatticeSpec`, `ElementSpec`, and a top-level `Experiment`.
- **Responsibilities:** Load external file → validate against schema → construct typed `Experiment` → hand to existing `case_for_config`-style resolution.
- **Dependencies:** Depends on `config.py`, the registries, and the element registry (Req 2/6). Nothing depends *back* on it except `main.py`.
- **Affected modules:** `main.py` (becomes a thin runner), `simulation_config.py` (its branching functions are superseded).
- **Public interfaces:** `Experiment`, `load_experiment(path)`, `Experiment.from_dict(...)`.

### 2. Generalized Composite Lattice Support

- **Objective:** Declarative lattices of arbitrary length/order.
- **Ownership:** A new `element_registry` (name → element factory) plus a `build_lattice(LatticeSpec)` builder. `SimpleLattice` is unchanged.
- **Responsibilities:** The builder resolves each `ElementSpec.type` through the element registry, passing element-specific kwargs verbatim; `SimpleLattice` already assigns `z_start/z_end`.
- **Dependencies:** Element registry; lattice module (read-only).
- **Affected modules:** `registry.py` (add registry), one new lattice-builder function; `cases/` composite/generic case reads its lattice from the experiment rather than building its own.
- **Public interfaces:** `element_registry`, `build_lattice(spec)`.

Downstream subsystems already generalize: `Reporter.render_validation_report` iterates `lattice.elements` generically; conservation metrics are `MetricScope.ANY`; the plot generator is payload-driven. So composite support is *additive* — no changes to validation/diagnostics/reporting/plotting.

### 3. Multi-Species Transport

- **Objective:** Remove proton-specific assumptions.
- **Ownership of species/mass:** A new authoritative `physics/particle_data.py` table mapping species → (mass_kg, mass_MeV, charge_sign). The **particle source** owns assigning species and mass to the batch.
- **Propagation:** `ParticleBatch` gains `mass` (array, kg) and `species` (labels). `Solver.run` gains an **optional** `mass` parameter (default = proton mass array) so the `Solver` protocol stays backward-compatible. `ValidationContext` gains `mass`. Analytical references and metrics read mass from context instead of module constants.
- **Interaction with Boris solver:** `track_particles` uses per-particle mass in the velocity push and in the momentum diagnostic (currently `M_P_MEV`). This is an extension of the concrete solver, not the abstraction.
- **Interaction with references/metrics:** `DipoleAnalyticalReference` computes `B_rho`/`omega_c` from context mass; trajectory metrics that need mass read it from context. Diagnostics structure is unchanged (momentum is still stored; only its computation becomes mass-correct).

### 4. Complete Self-Convergence

- **Objective:** Both analytical and self-convergence, pluggable.
- **Ownership:** A new `validation/convergence/` package with a `ConvergenceStrategy` interface and two implementations (`AnalyticalConvergence`, `SelfConvergence`), selected via `ConvergenceConfig.mode` and resolved through a new `convergence_registry`.
- **Responsibilities:** `AnalyticalConvergence` reproduces today's behavior (needs `analytical_position_fn` or a POINTWISE_TRAJECTORY reference). `SelfConvergence` runs a refinement ladder and compares successive solutions (Cauchy/Richardson), requiring no reference. Both honor `refinement_ratio`.
- **Engine touch:** The engine replaces its inline gate with a single call to the resolved strategy. This is a minimal modification, not a redesign of the loop.

### 5. Remove Hardcoded Drift/Dipole

- **Objective:** No element names outside element implementations + registration.
- **Strategy:** The experiment loader + element registry supersede `build_lattice`'s branch; numerical params come straight from the experiment (`_numerical_params` deleted); charge filtering moves to the source spec (`load_geant4_initial_conditions` takes an explicit filter from config, not `case_type`). `main.py` loses per-element constants.

### 6. Registry-Driven Extension

- **Objective:** Uniform implement + register.
- **Strategy:** Add `element_registry` and `convergence_registry`; register both in `initialize_registries`. Keep `case/metric/reference/source` as-is. **No auto-discovery/plugins** — explicit registration in `initialize_registries` is retained (the review endorsed this minimalism). A `solver_registry` is *optional* and recommended only to let the experiment select a solver by name (`NumericalConfig.solver_name` already exists but is unused).

### 7. Future-Proof EM Field Interface

- **Objective:** Admit E now without breaking existing elements.
- **Strategy (additive):** Add `Element.em_field(x,y,z) -> (E, B)` with a **base-class default** that returns `E=0` and delegates B to the existing `field`. Add `SimpleLattice.get_em_field`. `boris_solver` queries `get_em_field` and uses the returned E (currently zeros). Existing `Drift`/`Dipole` are untouched; they inherit the default. Ownership stays: element owns field, lattice aggregates, solver consumes.

### 8. Experiment Identity

- **Objective:** Adopt `Experiment` as the top-level concept.
- **Strategy:** `Experiment` becomes the object passed from entry point to case resolution. `SimulationConfig` is retained as a thin compatibility view (or reconstructed from `Experiment`) so the existing `build_*_case_from_config` factories keep working during migration. Terminology matches the scientific workflow: source + lattice + numerics + validation + outputs.

---

## Integration Analysis (Phase 3)

**Unchanged (must not be touched):**
- `validation/engine.py` orchestration loop (one added call site for convergence strategy is the only edit).
- `validation/metrics/base.py` and all metric ABCs; `references/base.py`; `diagnostics.py` structure; `reporting/*`; `solver.py` `Solver` protocol + `BorisSolverAdapter` signature shape.
- `lattice/SimpleLattice` construction/geometry.

**Extend (add fields/methods, backward-compatible):**
- `validation/config.py` — add `ConvergenceConfig.mode`; add `ParticleSourceSpec`, `LatticeSpec`, `ElementSpec`, `Experiment` (or place these in the new `experiment/` package importing from config).
- `validation/registry.py` — add `element_registry`, `convergence_registry` (+ optional `solver_registry`); register builtins.
- `sources/base.py` — `ParticleBatch` gains `mass`, `species`; `ParticleSource` implementations set them.
- `validation/case.py` — `ValidationContext` gains `mass`.
- `lattice/lattice.py` — add `Element.em_field` default + `SimpleLattice.get_em_field`.
- `references/analytical.py` — read mass from context.

**Modify (small, targeted):**
- `physics/boris_solver.py` — accept optional per-particle `mass`; query `get_em_field`; use mass in momentum diagnostic. (Extension of concrete solver.)
- `validation/engine.py` — replace inline convergence gate with resolved `ConvergenceStrategy` call.
- `validation/solver.py` `BorisSolverAdapter.run` — forward optional mass (default proton) to `track_particles`.
- `simulation_config.py` — replace branching builders with experiment-driven equivalents (or thin shims over the new loader).

**New modules:**
- `transport/experiment/__init__.py`, `transport/experiment/loader.py`, `transport/experiment/schema.py` (dataclasses + validation).
- `transport/physics/particle_data.py`.
- `transport/validation/convergence/__init__.py`, `base.py`, `analytical.py`, `self_convergence.py`.
- `transport/lattice/registry.py` (element factories) *or* fold element registration into `validation/registry.py` (see Alternatives).
- Example experiment files under `transport/experiment/examples/` (`drift.yaml`, `dipole.yaml`, `drift_dipole.yaml`).

Preference honored: every requirement is satisfied by **extending** existing abstractions; the only genuinely new packages are the experiment loader, the particle-data table, and the convergence strategies — each corresponding to a capability the framework lacks entirely.

---

## Design Alternatives (Phase 4)

### A. Configuration format

| Option | Advantages | Disadvantages |
|---|---|---|
| **Python config object (status quo)** | No parser; full expressiveness | Requires source edits — violates Req 1 |
| **JSON** | Stdlib; ubiquitous | No comments; poor for hand-authoring scientific configs |
| **TOML** | Stdlib read (`tomllib`, 3.11+); typed; comments | Awkward for deeply nested/repeated lattice element lists |
| **YAML (recommended)** | Best ergonomics for nested + ordered lists; comments; standard in accelerator/ML tooling | Adds `PyYAML` dependency; must guard with `safe_load` |

**Recommendation: YAML** as the external authoritative format, parsed into the existing typed dataclasses via a validating loader. This gives declarative studies (Req 1/2) while preserving the current in-memory config objects (no redesign). Ordered element lists — essential for beamlines — read naturally in YAML.

### B. Species/mass ownership

| Option | Advantages | Disadvantages |
|---|---|---|
| **Mass only on batch** | Minimal | Loses species identity for reporting/manifest |
| **External particle-data file** | Data-driven | Over-engineered; another file to load |
| **`particle_data.py` table + batch carries mass & species (recommended)** | Single authoritative source; trivial; manifest-friendly | New (small) module |

**Recommendation:** `particle_data.py` table; sources resolve species → mass; batch carries both.

### C. EM field interface

| Option | Advantages | Disadvantages |
|---|---|---|
| **Change `field` signature to return (E,B)** | One method | Breaks every existing element + `get_field` callers now |
| **Additive `em_field` with default E=0 (recommended)** | Zero breakage; existing elements inherit default; opt-in E | Two methods coexist transitionally |

**Recommendation:** additive `em_field`. Avoids the very interface break Req 7 seeks to prevent, at essentially no cost.

### D. Convergence

| Option | Advantages | Disadvantages |
|---|---|---|
| **Flag-based branch in engine** | Small | Adds branching to the engine; not extensible |
| **Strategy + `convergence_registry` (recommended)** | New strategies without engine edits; honors existing config fields | One small package |

**Recommendation:** strategy pattern + registry.

### E. Element registration location

| Option | Advantages | Disadvantages |
|---|---|---|
| **Element registry inside `validation/registry.py`** | One registry hub | Couples lattice registration to validation package |
| **`lattice/registry.py` (recommended)** | Registry lives with the elements it registers; validation imports it | One more module |

**Recommendation:** `lattice/registry.py`, imported by `initialize_registries`, keeping ownership local to the lattice subsystem.

---

## Recommended Design

Adopt: **YAML experiment files** → validating **loader** → typed **`Experiment`** (reusing existing config dataclasses); a **lattice element registry** + declarative `build_lattice`; a **`particle_data` table** with mass/species carried on `ParticleBatch` and `ValidationContext` and consumed by an extended `track_particles`; a **pluggable convergence strategy** package + registry wired into the engine via a single call; an **additive `em_field`** interface defaulting E to zero; and **`Experiment`** as the top-level concept, with `SimulationConfig` retained transitionally.

This satisfies all eight requirements while touching the engine at exactly one call site and leaving every protected subsystem structurally intact.

---

## Implementation Blueprint (Phase 5)

### Stage 0 — Foundations (no behavior change)
1. Add `physics/particle_data.py` with species table (antiproton, proton, electron, positron, muon±, pion±) → (mass_kg, mass_MeV, charge_sign).
2. Add `mass` + `species` fields to `ParticleBatch`; default population = proton for existing sources (backward compatible).
3. Add `mass` to `ValidationContext`; engine populates it from `batch.mass`.

### Stage 1 — EM field interface (no behavior change)
4. Add `Element.em_field(x,y,z)` default returning `(zeros, self.field(...))`; add `SimpleLattice.get_em_field` mirroring `get_field`.
5. Extend `track_particles`/`boris_velocity_push` to (a) accept optional `mass` (default proton array) and use it in the push and momentum diagnostic, and (b) query `get_em_field` and apply returned E (still zero today). Update `BorisSolverAdapter.run` to forward mass.
6. Update `DipoleAnalyticalReference` and mass-dependent metrics to read mass from context.

### Stage 2 — Element registry + declarative lattice
7. Add `lattice/registry.py` with `element_registry` and factories for `drift`, `dipole` (kwargs match `Element` constructors).
8. Add `build_lattice(LatticeSpec)` resolving `ElementSpec.type` via the registry.

### Stage 3 — Convergence strategies
9. Add `validation/convergence/` with `ConvergenceStrategy` base, `AnalyticalConvergence` (ports `run_convergence_study`), `SelfConvergence` (refinement ladder + Richardson order estimate, reference-free), honoring `refinement_ratio`.
10. Add `convergence_registry`; add `ConvergenceConfig.mode` (`analytical` | `self`); default `analytical` for existing cases.
11. Engine: replace the `analytical_position_fn` gate with `convergence_registry.get(mode).run(...)`. Emit the same convergence plot payload/report.

### Stage 4 — Experiment configuration + loader
12. Add `experiment/schema.py`: `ElementSpec`, `LatticeSpec`, `ParticleSourceSpec`, `Experiment` (embedding existing `NumericalConfig`/`ConvergenceConfig`/`OutputConfig` and a metric/tolerance list).
13. Add `experiment/loader.py`: `load_experiment(path)` (YAML `safe_load` → validate → `Experiment`), with clear error messages for unknown element/source/metric/case names (list registry contents).
14. Add a resolution path `experiment → ValidationCase`: source spec → source (via `source_registry`), lattice spec → lattice (via `element_registry`), metrics list → `(metric, tolerance)` via `metric_registry`, references per case default or config.
15. Add example YAMLs reproducing current drift/dipole/`drift_dipole`.

### Stage 5 — Remove branching + Experiment identity
16. Replace `simulation_config.build_lattice`/`_numerical_params` with experiment-driven construction; move charge filtering into `ParticleSourceSpec`.
17. Make `main.py` a thin runner: `python -m transport.main --experiment path.yaml` → load → run engine → print/emit. Retain a default experiment file so the no-arg path still works.
18. Register `element_registry` and `convergence_registry` (and optional `solver_registry`) in `initialize_registries`.

### Required configuration schema (authoritative)

```yaml
experiment:
  name: dipole_level1
  level: 1
  case: dipole            # or "generic"/"composite" to derive metrics from config
  output_dir: transport/validation/outputs

particle_source:
  type: geant4            # single | mock | gaussian_beam | geant4
  species: antiproton
  charge_filter: antiproton
  n_particles: 1
  momentum_slice: [3480, 3680]   # MeV/c, geant4 only
  # single/mock: position/velocity/gamma
  # gaussian_beam: center, pos_sigma, vel_sigma, rng_seed

lattice:
  z_start: 0.0
  elements:
    - {type: drift,  length: 5.0,  aperture: 0.1}
    - {type: dipole, length: 5.0,  by: 1.0, aperture: 0.1}

numerical:
  dt: 1.0e-10
  max_steps: 500
  max_steps_conv: 150
  convergence: {enabled: true, mode: analytical, num_points: 8, refinement_ratio: 2.0}
  solver: boris

validation:
  metrics:                       # optional; omitted => case defaults
    - {name: momentum_conservation, tolerance: 1.0e-6, direction: le}
    - {name: bend_angle_error,      tolerance: 1.0e-2, direction: le}
  pass_criteria: all_must_pass

outputs: {report: true, json: true, csv: true, manifest: true, plots: true, visualization: false}
```

---

## Migration Plan

1. **Stages 0–1 are behavior-preserving** (defaults = proton, E = 0); land and verify drift/dipole reproduce current numbers first.
2. **Dual path during transition:** keep `SimulationConfig` and `build_*_case_from_config`; `Experiment` initially constructs a `SimulationConfig`-equivalent so existing case factories keep working.
3. **Ship example YAMLs** that reproduce the current drift, dipole, and `drift_dipole` studies; use them as regression baselines against pre-milestone `results.json`.
4. **Flip `main.py`** to the experiment runner with a default experiment path so the zero-argument invocation still runs.
5. **Deprecate** `simulation_config._numerical_params`, per-element `main.py` constants, and the case_type charge-filter branch once examples pass.
6. **Manifest** should record species and resolved masses for provenance.

---

## Potential Risks

- **YAML dependency / unsafe load:** mitigate with `PyYAML` `safe_load` and strict schema validation.
- **Solver signature change:** keep `mass` optional with a proton default so the `Solver` protocol and existing callers remain valid.
- **Momentum diagnostic correctness:** momentum currently uses `M_P_MEV`; switching to per-particle mass changes values for non-proton species (intended) but must be verified to leave proton results bit-stable.
- **Self-convergence robustness:** order estimation is noisy near round-off; require a minimum error floor and a fit window (as the analytical path already does) and document expected order per integrator.
- **Registry name collisions:** element/case/metric names share a lowercase namespace; loader must fail loudly with available-name listings.
- **Over-configuration:** a large schema can overwhelm; mitigate with sensible defaults so minimal experiments stay short, and validate/report unknown keys rather than silently ignoring them.
- **`em_field` dual-method drift:** document that elements override `field` (B) unless they need E; revisit collapsing to one method only if/when E becomes common (out of scope now).

---

## Implementation Contract

### New modules to create
- `transport/experiment/__init__.py`
- `transport/experiment/schema.py` — `ElementSpec`, `LatticeSpec`, `ParticleSourceSpec`, `Experiment`.
- `transport/experiment/loader.py` — `load_experiment(path)`, `Experiment.from_dict`.
- `transport/experiment/examples/{drift,dipole,drift_dipole}.yaml`.
- `transport/physics/particle_data.py` — species → (mass_kg, mass_MeV, charge_sign).
- `transport/lattice/registry.py` — `element_registry`, `build_lattice(spec)`, drift/dipole factories.
- `transport/validation/convergence/{__init__,base,analytical,self_convergence}.py`.

### Existing modules to extend
- `transport/validation/config.py` — `ConvergenceConfig.mode`; house or import experiment dataclasses.
- `transport/validation/registry.py` — add `element_registry`, `convergence_registry` (optional `solver_registry`); register builtins in `initialize_registries`.
- `transport/validation/sources/base.py` — `ParticleBatch.mass`, `ParticleBatch.species`.
- `transport/validation/sources/*` — populate mass/species from `particle_data`.
- `transport/validation/case.py` — `ValidationContext.mass`.
- `transport/lattice/lattice.py` — `Element.em_field` default; `SimpleLattice.get_em_field`.
- `transport/validation/references/analytical.py` — mass from context.

### Existing modules to modify
- `transport/physics/boris_solver.py` — optional per-particle mass; `get_em_field` query + apply E; mass-correct momentum diagnostic.
- `transport/validation/solver.py` — `BorisSolverAdapter.run` forwards optional mass (proton default).
- `transport/validation/engine.py` — one call site: resolve and invoke `ConvergenceStrategy` instead of the `analytical_position_fn` gate.
- `transport/simulation_config.py` — replace branching builders with experiment-driven construction; charge filter from source spec.
- `transport/main.py` — thin experiment runner (`--experiment`), default experiment retained.

### Public interfaces to add
- `Experiment`, `load_experiment(path)`.
- `element_registry`, `build_lattice(spec)`.
- `ConvergenceStrategy` (base) + `convergence_registry`.
- `particle_data` lookup (`mass_of(species)`, `charge_of(species)`).
- `Element.em_field`, `SimpleLattice.get_em_field`.
- `ParticleBatch.mass`, `ParticleBatch.species`, `ValidationContext.mass`.

### Experiment configuration schema
As specified above (experiment / particle_source / lattice / numerical / validation / outputs), YAML authoritative, validated into typed dataclasses reusing existing `NumericalConfig`, `ConvergenceConfig`, `OutputConfig`, `Tolerance`.

### Registry updates
- Add `element_registry` (drift, dipole; future elements add-only).
- Add `convergence_registry` (`analytical`, `self`).
- Optional `solver_registry` (`boris`) to honor `numerical.solver`.
- Register all in `initialize_registries`; no auto-discovery/plugins.

### Validation updates
- Engine resolves convergence via strategy (analytical unchanged; self-convergence now functional).
- Composite/generic case reads lattice + metric list from the experiment; conservation metrics (`ANY` scope) and reporter/plot generator already handle multi-element lattices with no change.
- Metrics/references read mass from context; proton results remain bit-stable.

### Documentation updates
- `docs/transport_validation.md` — add an "Experiment Configuration" section (schema + example YAMLs) and a "Multi-Species" note.
- Short authoring guide: "Adding a lattice element = implement `Element` subclass + register in `lattice/registry.py`"; "Adding a convergence strategy = implement + register."
- `README.md` module overview: mention `transport/experiment/` and the YAML-driven runner.

### Acceptance criteria
- A new validation study (including an arbitrary composite beamline) runs from a YAML file with **no** Python edits.
- Adding a lattice element, particle species, or convergence strategy requires only implement + register; no edits to engine, `simulation_config.py`, or `main.py`.
- Drift and dipole experiments reproduce pre-milestone `results.json` values (proton path bit-stable).
- A non-proton species (e.g., electron) transports with correct mass in the Boris push and momentum diagnostic, sourced from `particle_data`.
- `numerical.convergence.mode: self` produces a convergence study and report with **no** analytical reference; `mode: analytical` matches current output.
- `boris_solver` consumes `lattice.get_em_field`; with all elements E=0, results are unchanged; a test element returning nonzero E measurably alters the trajectory.
- No element names or `case_type` branches remain in `simulation_config.py` or `main.py`.
- `element_registry` and `convergence_registry` are populated in `initialize_registries`; unknown names fail with available-name listings.
- Manifest records species and resolved mass.

This specification is scoped strictly to the identified seams, preserves every protected subsystem, and converts Janus from "primarily extension-driven" to "extension-driven end to end" for the validation, lattice, species, and convergence axes.
