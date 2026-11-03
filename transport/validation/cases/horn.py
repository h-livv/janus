"""Horn validation case (Level 1, analytical radial-kick check)."""

from transport.lattice.lattice import Horn, SimpleLattice
from transport.validation.case import ValidationCase
from transport.validation.config import ConvergenceConfig, NumericalConfig, OutputConfig, Tolerance
from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric
from transport.validation.metrics.trajectory import HornMomentumKickMetric, HornRadiusSweepMetric
from transport.validation.references.analytical import HornAnalyticalReference
from transport.validation.sources.single import SingleParticleSource


def _horn_context(config):
    lattice = config.lattice
    horn = lattice.elements[0]
    z_start = lattice.z_start
    horn_length = horn.L
    current = horn.current
    ref = HornAnalyticalReference(
        z_start=z_start,
        horn_length=horn_length,
        current=current,
    )
    return ref, {
        "z_start": z_start,
        "horn_length": horn_length,
        "current": current,
        "inner_radius": horn.inner_radius,
        "outer_radius": horn.outer_radius,
        "horn_radius_sweep_points": 6,
    }


def build_horn_case(
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
    horn_length=1.0,
    current=250000.0,
    inner_radius=0.015,
    outer_radius=0.060,
    config_context=None,
):
    if lattice is None:
        lattice = SimpleLattice(
            [
                Horn(
                    horn_length,
                    current,
                    inner_radius,
                    outer_radius,
                )
            ],
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

    ref, meta = _horn_context(cfg if config_context is None else config_context)
    source = SingleParticleSource(R_init, V_init, gamma_init, charges)

    return ValidationCase(
        name="HornValidation",
        level=1,
        system_builder=lambda: lattice,
        particle_source=source,
        numerical_config=NumericalConfig(
            dt=dt,
            max_steps=max_steps,
            max_steps_conv=max_steps_conv,
            convergence=ConvergenceConfig(
                enabled=True,
                mode="self",
                num_points=8,
            ),
        ),
        references=[ref],
        metric_specs=[
            (MomentumConservationMetric(), Tolerance(1e-6)),
            (EnergyConservationMetric(), Tolerance(1e-6)),
            (HornMomentumKickMetric(), Tolerance(5e-2)),
            (HornRadiusSweepMetric(), Tolerance(5e-2)),
        ],
        output_config=OutputConfig(),
        metadata={
            "element": "horn",
            "validation_profile": "analytical",
            **meta,
        },
    )


def build_horn_case_from_config(config):
    horn = config.lattice.elements[0]
    return build_horn_case(
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
        horn_length=horn.L,
        current=horn.current,
        inner_radius=horn.inner_radius,
        outer_radius=horn.outer_radius,
        config_context=config,
    )


# Backward-compatible aliases
build_magnetic_horn_case = build_horn_case
build_magnetic_horn_case_from_config = build_horn_case_from_config
