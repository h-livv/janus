"""Drift followed by quadrupole (Level 2 composite)."""

from transport.lattice.lattice import Drift, Quadrupole, SimpleLattice
from transport.validation.cases.composite import (
    build_composite_lattice_case,
    composite_case_from_config,
)


def build_drift_quadrupole_case(
    lattice=None,
    R_init=None,
    V_init=None,
    gamma_init=None,
    charges=None,
    dt=1e-10,
    max_steps=1500,
    max_steps_conv=300,
    use_mock_data=True,
    z_start=0.0,
    drift_length=2.0,
    quadrupole_length=1.0,
    quadrupole_k=0.5,
    aperture_radius=None,
    config_context=None,
):
    if lattice is None:
        lattice = SimpleLattice(
            [
                Drift(drift_length, aperture_radius=aperture_radius),
                Quadrupole(quadrupole_length, quadrupole_k, aperture_radius=aperture_radius),
            ],
            z_start=z_start,
        )

    return build_composite_lattice_case(
        name="DriftQuadrupoleValidation",
        level=2,
        element_label="drift_quadrupole",
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


def build_drift_quadrupole_case_from_config(config):
    return composite_case_from_config(
        config,
        name="DriftQuadrupoleValidation",
        level=2,
        element_label="drift_quadrupole",
    )
