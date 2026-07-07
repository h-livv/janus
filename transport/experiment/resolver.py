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
        from transport.lattice.lattice import SimpleLattice
        lattice = SimpleLattice(lattice.elements, z_start=float(batch.R[0, 2]))
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
    ps = experiment.particle_source
    if ps.type.lower() == "geant4" and ps.n_particles != 1:
        raise ValueError(
            "Geant4 validation and convergence require n_particles: 1. "
            "Set n_particles to 1 for validation, or enable outputs.visualization "
            "to visualize multiple Geant4 particles."
        )
    initialize_registries()
    config = experiment_to_simulation_config(experiment)
    if len(config.lattice.elements) > 1 and ps.n_particles < 2:
        raise ValueError(
            "Composite lattice validation requires n_particles >= 2. "
            "Use particle_source type 'gaussian_beam' with n_particles >= 2."
        )
    case = case_for_config(config)
    case.particle_source = build_particle_source(experiment.particle_source)
    case.numerical_config = experiment.numerical
    case.output_config = experiment.outputs
    if experiment.validation.metrics:
        case.metric_specs = build_metric_specs(experiment.validation.metrics)
    return case
