# Janus Architectural Roadmap

For the **current** pipeline and repository layout, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Objective

Transition Janus from a transport simulation pipeline into a
reproducible computational research framework for studying the
**production-to-injection** stage of the antimatter pipeline.

------------------------------------------------------------------------

# Current State

## Completed

-   Geant4 production engine with collision validation (Phases 1–4).
-   Geant4 → Janus → Xsuite transport pipeline.
-   Experiment-driven configuration (`experiments/transport/`).
-   Transport diagnostics, structured metrics, provenance.
-   Study / sweep framework (`transport/studies/`) with CSV export.
-   Directory layout separating engines, capabilities, examples, and `data/`.

The remaining work is **not additional simulation physics**, but
**research infrastructure** (optimization, exploration, and an independent lab that depends on Janus).

------------------------------------------------------------------------

# Guiding Philosophy

Janus should **not** become another particle-tracking engine.

Instead:

-   **Geant4** owns particle production.
-   **Xsuite** owns beam dynamics and transport.
-   **Janus** owns:
    -   orchestration,
    -   reproducibility,
    -   scientific studies,
    -   analysis,
    -   optimization workflows.

The goal is to answer scientific questions, not replace mature
simulation software.

------------------------------------------------------------------------

# Phase 1 --- Freeze the Architecture

## Goal

Stabilize interfaces and stop restructuring.

## Tasks

-   Finalize the module hierarchy.
-   Freeze data contracts.
-   Keep experiment scripts as the single source of scientific
    parameters.
-   Only modify architecture when required by new research.

**Deliverable:** A stable framework suitable for long-term development.

------------------------------------------------------------------------

# Phase 2 --- Metrics API

## Goal

Produce scientific observables instead of only figures.

## Implement

``` python
TransportMetrics(
    transmission,
    beam_losses,
    rms_x,
    rms_y,
    momentum_spread,
    emit_x,
    emit_y,
    beam_centroid,
)
```

Every simulation should produce a structured metrics object.

Plots become a presentation layer built on top of these metrics.

------------------------------------------------------------------------

# Phase 3 --- Study Framework

## Goal

Move from running simulations to running computational experiments.

Introduce a generic `Study` abstraction.

Examples include:

-   Parameter sweeps
-   Grid search
-   Random sampling
-   Latin Hypercube sampling
-   Bayesian optimization (future)
-   Multi-objective optimization (future)

Each study should:

1.  Generate parameter sets.
2.  Execute simulations.
3.  Collect metrics.
4.  Aggregate results.
5.  Export datasets and figures.

The simulation pipeline should remain unchanged regardless of the study
type.

------------------------------------------------------------------------

# Phase 4 --- Provenance & Reproducibility

Automatically fingerprint every run.

Record:

-   Run ID
-   Git commit
-   Experiment name
-   Parameters
-   Random seed
-   Geant4 version
-   Xsuite version
-   Runtime
-   Output metrics

Every figure and dataset should be reproducible from this information.

------------------------------------------------------------------------

# Phase 5 --- Validation

Do **not** revalidate Geant4 or Xsuite.

Validate only the parts owned by Janus.

This includes:

-   Coordinate transformations
-   Unit conversions
-   Geant4 → Janus → Xsuite interface
-   Acceptance/filtering logic
-   End-to-end workflow against published benchmarks where appropriate

------------------------------------------------------------------------

# Transition to Research

Once the previous phases are complete, stop adding infrastructure.

The workflow becomes:

``` text
Literature Review
        ↓
Research Question
        ↓
Study Definition
        ↓
Parameter Sweep / Sampling
        ↓
Simulation
        ↓
Metrics
        ↓
Analysis
        ↓
Scientific Conclusions
        ↓
Publication
```

------------------------------------------------------------------------

# Candidate Research Questions

-   How do target geometry and beamline acceptance jointly affect usable
    antiproton yield?
-   Which parameters dominate downstream transport efficiency?
-   What trade-offs exist between transmission, beam quality, and
    momentum spread?
-   Which regions of parameter space maximize **usable** antiprotons
    rather than total production?

------------------------------------------------------------------------

# Implementation Priority

  Priority   Implementation           Purpose
  ---------- ------------------------ ---------------------------------
  1          Freeze architecture      Stable foundation
  2          Metrics API              Scientific observables
  3          Study framework          Computational experiments
  4          Run fingerprinting       Reproducibility
  5          Interface validation     Trustworthy workflow
  6          Sensitivity studies      Identify influential parameters
  7          Optimization             Explore the design space
  8          Research & publication   Answer scientific questions

------------------------------------------------------------------------

# Long-Term Vision

``` text
Research Question
        │
        ▼
Study
        │
        ▼
Simulation Pipeline
        │
        ▼
Metrics
        │
        ▼
Analysis
        │
        ▼
Scientific Insight
```

Janus should ultimately be viewed as a **computational research
platform** that orchestrates established simulation tools to investigate
questions about antimatter production and transport, rather than as
another particle simulation engine.
