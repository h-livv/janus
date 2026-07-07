"""Declarative quadrupole validation case (Level 1)."""

import numpy as np

from transport.lattice.lattice import Quadrupole, SimpleLattice
from transport.validation.case import ValidationCase
from transport.validation.config import ConvergenceConfig, NumericalConfig, OutputConfig, Tolerance
from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric
from transport.validation.metrics.trajectory import DriftCoordinateErrorMetric
from transport.validation.references.analytical import QuadrupoleAnalyticalReference
from transport.validation.sources.single import SingleParticleSource

C_LIGHT = 299792458.0
E_CHARGE = 1.602176634e-19
M_P_KG = 1.67262192369e-27


def _quadrupole_context(config):
    lattice = config.lattice
    V_init = config.V_init
    charges = config.charges
    v_mag = float(np.linalg.norm(V_init[0]))
    gamma = float(1.0 / np.sqrt(1.0 - (v_mag / C_LIGHT) ** 2))
    z_start = lattice.z_start
    quadrupole = lattice.elements[0]
    quadrupole_length = quadrupole.L
    quadrupole_k = quadrupole.k
    charge = int(charges[0])
    m_kg = float(config.mass[0]) if getattr(config, "mass", None) is not None else M_P_KG

    v_z = abs(float(V_init[0, 2]))
    if v_z < 1e-12:
        v_z = v_mag
    if config.use_mock_data:
        B_rho = (1.0 * m_kg * v_z) / E_CHARGE
    else:
        B_rho = gamma * m_kg * v_z / E_CHARGE

    ref = QuadrupoleAnalyticalReference(
        z_start=z_start,
        quadrupole_length=quadrupole_length,
        gradient=quadrupole_k,
        B_rho=B_rho,
        charge=charge,
    )
    return ref, {
        "z_start": z_start,
        "quadrupole_length": quadrupole_length,
        "quadrupole_k": quadrupole_k,
        "B_rho": B_rho,
        "charge": charge,
    }

def build_quadrupole_case(
    lattice=None,
    R_init=None,
    V_init=None,
    gamma_init=None,
    charges=None,
    dt=1e-10,
    max_steps=500,
    max_steps_conv=150,
    use_mock_data=True,
    z_start=0.0,
    quadrupole_length=5.0,
    quadrupole_k=1.0,
    aperture_radius=None,
    config_context=None,
):
    if lattice is None:
        lattice = SimpleLattice(
            [Quadrupole(quadrupole_length, quadrupole_k, aperture_radius=aperture_radius)],
            z_start=z_start,
        )

    class _Config:
        pass

    cfg = _Config()
    cfg.lattice = lattice
    cfg.R_init = R_init
    cfg.V_init = V_init
    cfg.gamma_init = gamma_init
    cfg.charges = charges
    cfg.use_mock_data = use_mock_data

    ref, meta = _quadrupole_context(cfg if config_context is None else config_context)
    source = SingleParticleSource(R_init, V_init, gamma_init, charges)

    ctx = config_context if config_context is not None else cfg
    m_kg = float(ctx.mass[0]) if getattr(ctx, "mass", None) is not None else M_P_KG

    def analytical_position_fn(t, R_i, V_i, ch):
        return ref.position_at_time(t, R_i, V_i, ch, mass_kg=m_kg)

    return ValidationCase(
        name="QuadrupoleValidation",
        level=1,
        system_builder=lambda: lattice,
        particle_source=source,
        numerical_config=NumericalConfig(
            dt=dt, max_steps=max_steps, max_steps_conv=max_steps_conv,
            convergence=ConvergenceConfig(enabled=True, mode="self", num_points=8),
        ),
        references=[ref],
        metric_specs=[
            (MomentumConservationMetric(), Tolerance(1e-6)),
            (EnergyConservationMetric(), Tolerance(1e-6)),
            (DriftCoordinateErrorMetric("x"), Tolerance(1e-4)),
            (DriftCoordinateErrorMetric("y"), Tolerance(1e-4)),
            (DriftCoordinateErrorMetric("z"), Tolerance(1e-6)),
        ],
        output_config=OutputConfig(),
        metadata={
            "element": "quadrupole",
            "validation_profile": "analytical",
            "analytical_position_fn": analytical_position_fn,
            **meta,
        },
    )


def build_quadrupole_case_from_config(config):
    return build_quadrupole_case(
        lattice=config.lattice,
        R_init=config.R_init,
        V_init=config.V_init,
        gamma_init=config.gamma_init,
        charges=config.charges,
        dt=config.dt,
        max_steps=config.max_steps,
        max_steps_conv=config.max_steps_conv,
        use_mock_data=config.use_mock_data,
        z_start=config.lattice.z_start,
        quadrupole_length=config.lattice.elements[0].L,
        quadrupole_k=config.lattice.elements[0].k,
        aperture_radius=config.lattice.elements[0].aperture_radius,
        config_context=config,
    )
