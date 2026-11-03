"""Declarative drift validation case (Level 1)."""

from transport.lattice.lattice import Drift, SimpleLattice
from transport.validation.case import ValidationCase
from transport.validation.config import ConvergenceConfig, NumericalConfig, OutputConfig, Tolerance
from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric
from transport.validation.metrics.trajectory import DriftCoordinateErrorMetric
from transport.validation.references.analytical import DriftAnalyticalReference
from transport.validation.sources.single import SingleParticleSource


def build_drift_case(
    lattice=None,
    R_init=None,
    V_init=None,
    gamma_init=None,
    charges=None,
    dt=1e-10,
    max_steps=500,
    max_steps_conv=300,
    drift_length=10.0,
    z_start=0.0,
    aperture_radius=None,
):
    if lattice is None:
        lattice = SimpleLattice(
            [Drift(drift_length, aperture_radius=aperture_radius)], z_start=z_start
        )
    z_start = lattice.z_start
    source = SingleParticleSource(R_init, V_init, gamma_init, charges)

    return ValidationCase(
        name="DriftValidation",
        level=1,
        system_builder=lambda: lattice,
        particle_source=source,
        numerical_config=NumericalConfig(
            dt=dt, max_steps=max_steps, max_steps_conv=max_steps_conv,
            convergence=ConvergenceConfig(enabled=True, num_points=8),
        ),
        references=[DriftAnalyticalReference()],
        metric_specs=[
            (MomentumConservationMetric(), Tolerance(1e-6)),
            (EnergyConservationMetric(), Tolerance(1e-6)),
            (DriftCoordinateErrorMetric("x"), Tolerance(1e-6)),
            (DriftCoordinateErrorMetric("y"), Tolerance(1e-6)),
            (DriftCoordinateErrorMetric("z"), Tolerance(1e-6)),
        ],
        output_config=OutputConfig(),
        metadata={
            "element": "drift",
            "z_start": z_start,
            "analytical_position_fn": lambda t, R, V, ch: DriftAnalyticalReference.position_at_time(t, R, V),
        },
    )


def build_drift_case_from_config(config):
    return build_drift_case(
        lattice=config.lattice,
        R_init=config.R_init,
        V_init=config.V_init,
        gamma_init=config.gamma_init,
        charges=config.charges,
        dt=config.dt,
        max_steps=config.max_steps,
        max_steps_conv=config.max_steps_conv,
        drift_length=config.lattice.elements[0].L,
        z_start=config.lattice.z_start,
        aperture_radius=config.lattice.elements[0].aperture_radius,
    )
