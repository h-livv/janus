"""ACOL-inspired minimal lattice validation (Level 2).

Minimal layout: injection drift + short FODO arc (ACOL used 28 FODO cells).
"""

from transport.validation.cases.composite import (
    build_composite_lattice_case,
    composite_case_from_config,
)


def build_acol_case(
    lattice=None,
    R_init=None,
    V_init=None,
    gamma_init=None,
    charges=None,
    dt=1e-10,
    max_steps=10000,
    max_steps_conv=500,
    use_mock_data=True,
    config_context=None,
):
    if lattice is None:
        raise ValueError("ACOL validation requires a pre-built lattice from YAML")

    return build_composite_lattice_case(
        name="AcolValidation",
        level=2,
        element_label="acol",
        lattice=lattice,
        R_init=R_init,
        V_init=V_init,
        gamma_init=gamma_init,
        charges=charges,
        dt=dt,
        max_steps=max_steps,
        max_steps_conv=max_steps_conv,
        use_mock_data=use_mock_data,
        config_context=config_context,
    )


def build_acol_case_from_config(config):
    return composite_case_from_config(
        config,
        name="AcolValidation",
        level=2,
        element_label="acol",
    )
