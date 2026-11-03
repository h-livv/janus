"""Resolve Experiment to runtime objects."""

import numpy as np

from transport.experiment.schema import Experiment
from transport.lattice.registry import build_lattice
from transport.physics.particle_data import charge_of, mass_of
from transport.simulation_config import SimulationConfig
from transport.validation.config import Tolerance
from transport.validation.registry import (
    case_for_config,
    initialize_registries,
    metric_registry,
    source_registry,
)


def build_particle_source(spec):
    source_type = spec.type.lower()
    species = spec.species
    metadata = {"species": species}

    if source_type in ("single", "mock"):
        if spec.position is None or spec.velocity is None:
            raise ValueError(f"particle_source type '{source_type}' requires position and velocity")
        R = np.array([spec.position], dtype=np.float64)
        V = np.array([spec.velocity], dtype=np.float64)
        gamma = np.array([spec.gamma if spec.gamma is not None else 1.0], dtype=np.float64)
        charges = np.array([charge_of(species)], dtype=np.int8)
        from transport.validation.sources.single import SingleParticleSource
        return SingleParticleSource(R, V, gamma, charges, metadata=metadata)

    if source_type == "geant4":
        from transport.validation.sources.geant4 import Geant4ParticleSource
        return Geant4ParticleSource(
            charge_filter=spec.charge_filter,
            species=species,
            momentum_slice=spec.momentum_slice,
            n_particles=spec.n_particles,
            offset=spec.offset,
        )

    if source_type == "gaussian_beam":
        if spec.position is None or spec.velocity is None:
            raise ValueError("gaussian_beam requires position and velocity center")
        R_center = np.array(spec.position, dtype=np.float64)
        V_center = np.array(spec.velocity, dtype=np.float64)
        gamma = np.array([spec.gamma if spec.gamma is not None else 1.0], dtype=np.float64)
        charges = np.array([charge_of(species)], dtype=np.int8)
        from transport.validation.sources.gaussian_beam import GaussianBeamSource
        return GaussianBeamSource(
            R_center, V_center, gamma, charges, spec.n_particles,
            pos_sigma=spec.pos_sigma, vel_sigma=spec.vel_sigma,
            rng_seed=spec.rng_seed, metadata=metadata,
        )

    if source_type == "file":
        if not spec.path:
            raise ValueError("file particle source requires path")
        return source_registry.build("file", path=spec.path)

    available = source_registry.list_names()
    raise KeyError(f"Unknown particle source type '{spec.type}'. Available: {available}")


def build_metric_specs(metric_specs):
    specs = []
    for ms in metric_specs:
        metric = metric_registry.get(ms.name)
        tol = Tolerance(
            threshold=ms.tolerance,
            direction=ms.direction,
            informational=ms.informational,
        )
        specs.append((metric, tol))
    return specs


def experiment_to_simulation_config(experiment: Experiment) -> SimulationConfig:
    source = build_particle_source(experiment.particle_source)
    batch = source.generate()
    lattice = build_lattice(experiment.lattice)
    if experiment.particle_source.type.lower() == "geant4" and len(batch.R):
        from transport.validation.sources.geant4 import place_geant4_beam_in_lattice
        # Rigid translation only: keep Geant4 velocities and COM-relative layout.
        batch = place_geant4_beam_in_lattice(
            batch,
            lattice,
            offset=experiment.particle_source.offset,
        )
    use_mock = experiment.particle_source.type.lower() in ("single", "mock")
    return SimulationConfig(
        case_type=experiment.case,
        lattice=lattice,
        R_init=batch.R,
        V_init=batch.V,
        gamma_init=batch.gamma,
        charges=batch.charges,
        mass=batch.mass,
        species=batch.species,
        dt=experiment.numerical.dt,
        max_steps=experiment.numerical.max_steps,
        max_steps_conv=experiment.numerical.max_steps_conv,
        use_mock_data=use_mock,
    )


def validation_case_from_experiment(experiment: Experiment):
    """
    Build a ValidationCase from an Experiment.

    Particle-count rules:
    - Single-element (analytical) Geant4 validation: n_particles must be 1.
    - Composite lattices (len(elements) > 1): at least 2 particles from
      ``gaussian_beam`` or ``geant4`` (beam diagnostics).
    """
    ps = experiment.particle_source
    initialize_registries()
    lattice_preview = build_lattice(experiment.lattice)
    n_elements = len(lattice_preview.elements)
    is_geant4 = ps.type.lower() == "geant4"

    if is_geant4 and n_elements == 1 and ps.n_particles != 1:
        raise ValueError(
            "Single-element Geant4 validation requires n_particles: 1 "
            "(analytical trajectory metrics are single-particle). "
            "For multi-particle Geant4 beam validation use a composite lattice "
            "(more than one element) with n_particles >= 2, or enable "
            "outputs.visualization."
        )

    config = experiment_to_simulation_config(experiment)
    n_generated = len(config.R_init)

    if n_elements > 1 and n_generated < 2:
        raise ValueError(
            "Composite lattice validation requires at least 2 particles "
            f"(got {n_generated}). Use particle_source type 'gaussian_beam' or "
            "'geant4' with n_particles >= 2, and ensure enough seeds survive "
            "Geant4 charge/momentum filters."
        )

    case = case_for_config(config)
    source = build_particle_source(experiment.particle_source)
    if is_geant4:
        from transport.validation.sources.geant4 import LatticePlacedParticleSource
        # Ensure validation regenerates with the same rigid pipeline placement.
        source = LatticePlacedParticleSource(
            source,
            config.lattice,
            offset=ps.offset,
        )
    case.particle_source = source
    case.numerical_config = experiment.numerical
    case.output_config = experiment.outputs
    if experiment.validation.metrics:
        case.metric_specs = build_metric_specs(experiment.validation.metrics)
    return case
