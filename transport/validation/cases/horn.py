"""Magnetic horn validation case stub (Level 2)."""

from transport.lattice.lattice import Drift, SimpleLattice
from transport.validation.case import ValidationCase
from transport.validation.config import ConvergenceConfig, NumericalConfig, OutputConfig, Tolerance
from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric
from transport.validation.references.experimental import ExperimentalReference
from transport.validation.sources.single import SingleParticleSource


def build_horn_case(
    R_init=None, V_init=None, gamma_init=None, charges=None,
    z_start=0.0, length=1.0, dt=1e-10, max_steps=500,
):
    lattice = SimpleLattice([Drift(length)], z_start=z_start)
    source = SingleParticleSource(R_init, V_init, gamma_init, charges)

    return ValidationCase(
        name="HornValidation",
        level=2,
        system_builder=lambda: lattice,
        particle_source=source,
        numerical_config=NumericalConfig(
            dt=dt, max_steps=max_steps, max_steps_conv=max_steps,
            convergence=ConvergenceConfig(enabled=False),
        ),
        references=[ExperimentalReference(name="horn_experimental")],
        metric_specs=[
            (MomentumConservationMetric(), Tolerance(1e-6)),
            (EnergyConservationMetric(), Tolerance(1e-6)),
        ],
        output_config=OutputConfig(),
        metadata={"element": "horn", "stub": True},
    )
