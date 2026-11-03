"""Gaussian beam validation case stub (Level 3)."""

from transport.lattice.lattice import Drift, SimpleLattice
from transport.validation.case import ValidationCase
from transport.validation.config import ConvergenceConfig, NumericalConfig, OutputConfig, Tolerance
from transport.validation.metrics.beam import CentroidMetric, RmsSizeMetric, TransmissionMetric
from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric
from transport.validation.references.transfer_matrix import TransferMatrixReference
from transport.validation.sources.gaussian_beam import GaussianBeamSource


def build_gaussian_beam_case(
    R_center=None, V_center=None, gamma=None, charges=None,
    n_particles=100, pos_sigma=0.01, vel_sigma=1e5,
    z_start=0.0, length=10.0, dt=1e-10, max_steps=500, rng_seed=42,
):
    lattice = SimpleLattice([Drift(length)], z_start=z_start)
    source = GaussianBeamSource(
        R_center, V_center, gamma, charges, n_particles,
        pos_sigma=pos_sigma, vel_sigma=vel_sigma, rng_seed=rng_seed,
    )

    return ValidationCase(
        name="GaussianBeamValidation",
        level=3,
        system_builder=lambda: lattice,
        particle_source=source,
        numerical_config=NumericalConfig(
            dt=dt, max_steps=max_steps, max_steps_conv=max_steps,
            convergence=ConvergenceConfig(enabled=False),
        ),
        references=[TransferMatrixReference(name="beam_transfer_matrix")],
        metric_specs=[
            (MomentumConservationMetric(), Tolerance(1e-6)),
            (EnergyConservationMetric(), Tolerance(1e-6)),
            (CentroidMetric(), Tolerance(threshold=1.0, informational=True)),
            (RmsSizeMetric(), Tolerance(threshold=1.0, informational=True)),
            (TransmissionMetric(), Tolerance(threshold=0.0, informational=True)),
        ],
        output_config=OutputConfig(),
        metadata={"element": "gaussian_beam", "stub": True},
    )
