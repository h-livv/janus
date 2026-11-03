"""Composite drift+dipole case stub (Level 2)."""

from transport.lattice.lattice import Dipole, Drift, SimpleLattice
from transport.validation.case import ValidationCase
from transport.validation.config import ConvergenceConfig, NumericalConfig, OutputConfig, Tolerance
from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric
from transport.validation.references.transfer_matrix import TransferMatrixReference
from transport.validation.sources.single import SingleParticleSource


def build_drift_dipole_case(
    lattice=None,
    R_init=None, V_init=None, gamma_init=None, charges=None,
    z_start=0.0, drift_length=5.0, dipole_length=5.0, dipole_by=1.0,
    dt=1e-10, max_steps=1000, max_steps_conv=300,
):
    if lattice is None:
        lattice = SimpleLattice(
            [
                Drift(drift_length),
                Dipole(dipole_length, dipole_by),
            ],
            z_start=z_start,
        )
    source = SingleParticleSource(R_init, V_init, gamma_init, charges)

    return ValidationCase(
        name="DriftDipoleValidation",
        level=2,
        system_builder=lambda: lattice,
        particle_source=source,
        numerical_config=NumericalConfig(
            dt=dt, max_steps=max_steps, max_steps_conv=max_steps_conv,
            convergence=ConvergenceConfig(enabled=False),
        ),
        references=[TransferMatrixReference(name="composite_transfer_matrix")],
        metric_specs=[
            (MomentumConservationMetric(), Tolerance(1e-6)),
            (EnergyConservationMetric(), Tolerance(1e-6)),
        ],
        output_config=OutputConfig(),
        metadata={"element": "drift_dipole", "stub": True},
    )


def build_drift_dipole_case_from_config(config):
    return build_drift_dipole_case(
        lattice=config.lattice,
        R_init=config.R_init,
        V_init=config.V_init,
        gamma_init=config.gamma_init,
        charges=config.charges,
        dt=config.dt,
        max_steps=config.max_steps,
        max_steps_conv=config.max_steps_conv,
        z_start=config.lattice.z_start,
    )
