"""Shared builder for composite lattice validation."""

from transport.validation.case import ValidationCase
from transport.validation.config import ConvergenceConfig, NumericalConfig, OutputConfig
from transport.validation.profiles import apply_validation_profile, validation_tier
from transport.validation.sources.single import SingleParticleSource


def build_composite_lattice_case(
    name: str,
    level: int,
    element_label: str,
    lattice=None,
    R_init=None,
    V_init=None,
    gamma_init=None,
    charges=None,
    dt=1e-10,
    max_steps=2000,
    max_steps_conv=300,
    use_mock_data=True,
    config_context=None,
    convergence_enabled=True,
    case_type=None,
):
    class _Config:
        pass

    cfg = config_context if config_context is not None else _Config()
    if config_context is None:
        cfg.lattice = lattice
        cfg.R_init = R_init
        cfg.V_init = V_init
        cfg.gamma_init = gamma_init
        cfg.charges = charges
        cfg.use_mock_data = use_mock_data
        cfg.case_type = case_type or element_label

    source = SingleParticleSource(R_init, V_init, gamma_init, charges)
    tier = validation_tier(cfg.case_type)

    case = ValidationCase(
        name=name,
        level=level,
        system_builder=lambda: cfg.lattice,
        particle_source=source,
        numerical_config=NumericalConfig(
            dt=dt,
            max_steps=max_steps,
            max_steps_conv=max_steps_conv,
            convergence=ConvergenceConfig(
                enabled=convergence_enabled,
                mode="self",
                num_points=4,
            ),
        ),
        references=[],
        metric_specs=[],
        output_config=OutputConfig(),
        metadata={
            "element": element_label,
            "validation_profile": tier,
            "n_elements": len(cfg.lattice.elements),
            "total_length": cfg.lattice.total_length,
        },
    )
    return apply_validation_profile(case, cfg)


def composite_case_from_config(
    config,
    name: str,
    level: int,
    element_label: str,
    **kwargs,
):
    return build_composite_lattice_case(
        name=name,
        level=level,
        element_label=element_label,
        lattice=config.lattice,
        R_init=config.R_init,
        V_init=config.V_init,
        gamma_init=config.gamma_init,
        charges=config.charges,
        dt=config.dt,
        max_steps=config.max_steps,
        max_steps_conv=config.max_steps_conv,
        use_mock_data=config.use_mock_data,
        config_context=config,
        case_type=config.case_type,
        **kwargs,
    )
