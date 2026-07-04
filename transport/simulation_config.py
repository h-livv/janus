"""
Simulation configuration built from main.py parameters.
Single source for lattice, initial conditions, and timestep settings.
"""
from dataclasses import dataclass

import numpy as np

from transport.lattice.lattice import SimpleLattice, Drift, Dipole

C_LIGHT = 299792458.0
E_CHARGE = 1.602176634e-19
M_P_KG = 1.67262192369e-27


@dataclass
class SimulationConfig:
    case_type: str
    lattice: SimpleLattice
    R_init: np.ndarray
    V_init: np.ndarray
    gamma_init: np.ndarray
    charges: np.ndarray
    dt: float
    max_steps: int
    max_steps_conv: int
    use_mock_data: bool = True


def load_geant4_initial_conditions(case_type):
    from transport.io.data_io import get_latest_run_file, extract_cern_ad_seeds

    latest_file = get_latest_run_file(
        outputs_dir_name="interactions/runs", target_filename="simulation.root"
    )
    R, V, gamma, all_charges = extract_cern_ad_seeds([latest_file])

    if case_type == "dipole":
        mask = all_charges == -1
        if not np.any(mask):
            mask = all_charges == 1
        if not np.any(mask):
            raise ValueError("No charged particles found in simulation.root")
    else:
        mask = np.ones(len(all_charges), dtype=bool)

    return (
        R[mask].astype(np.float64),
        V[mask].astype(np.float64),
        gamma[mask].astype(np.float64),
        all_charges[mask],
    )


def build_lattice(case_type, z_start, aperture_radius, drift_length, dipole_length, dipole_by):
    if case_type == "drift":
        elements = [Drift(drift_length, aperture_radius=aperture_radius)]
    else:
        elements = [Dipole(dipole_length, dipole_by, aperture_radius=aperture_radius)]
    return SimpleLattice(elements, z_start=z_start)


def build_simulation_config(
    case_type,
    use_mock_data,
    *,
    z_start,
    aperture_radius,
    drift_length,
    drift_dt,
    drift_max_steps,
    drift_max_steps_conv,
    dipole_length,
    dipole_by,
    dipole_dt,
    dipole_max_steps,
    dipole_max_steps_conv,
    mock_dt,
    mock_max_steps,
    mock_max_steps_conv,
    mock_r_init,
    mock_v_init,
    mock_gamma_init,
    mock_charges,
):
    case_type = case_type.lower()
    if case_type == "drift":
        dt = mock_dt if use_mock_data else drift_dt
        max_steps = mock_max_steps if use_mock_data else drift_max_steps
        max_steps_conv = mock_max_steps_conv if use_mock_data else drift_max_steps_conv
    elif case_type == "dipole":
        dt = mock_dt if use_mock_data else dipole_dt
        max_steps = mock_max_steps if use_mock_data else dipole_max_steps
        max_steps_conv = mock_max_steps_conv if use_mock_data else dipole_max_steps_conv
    else:
        raise ValueError(f"Unknown case_type '{case_type}'")

    if use_mock_data:
        R_init = mock_r_init.copy()
        V_init = mock_v_init.copy()
        gamma_init = mock_gamma_init.copy()
        charges = mock_charges.copy()
        lattice_z_start = z_start
    else:
        R_init, V_init, gamma_init, charges = load_geant4_initial_conditions(case_type)
        lattice_z_start = float(R_init[0, 2])

    lattice = build_lattice(
        case_type,
        lattice_z_start,
        aperture_radius,
        drift_length,
        dipole_length,
        dipole_by,
    )

    return SimulationConfig(
        case_type=case_type,
        lattice=lattice,
        R_init=R_init,
        V_init=V_init,
        gamma_init=gamma_init,
        charges=charges,
        dt=dt,
        max_steps=max_steps,
        max_steps_conv=max_steps_conv,
        use_mock_data=use_mock_data,
    )


def apply_reference_context(validation_case, config):
    """Configure a validation case for analytical reference from transport config."""
    validation_case.lattice = config.lattice
    validation_case.z_start = config.lattice.z_start
    validation_case.dt = config.dt
    validation_case.max_steps = config.max_steps
    validation_case.max_steps_conv = config.max_steps_conv
    validation_case.aperture_radius = config.lattice.elements[0].aperture_radius

    V_init = config.V_init
    charges = config.charges
    validation_case.v_mag = float(np.linalg.norm(V_init[0]))
    validation_case.gamma = float(
        1.0 / np.sqrt(1.0 - (validation_case.v_mag / C_LIGHT) ** 2)
    )

    if config.case_type == "drift":
        validation_case.L = config.lattice.elements[0].L
        return

    from transport.validation.cases.dipole import DipoleValidation
    if not isinstance(validation_case, DipoleValidation):
        return

    validation_case.charge = int(charges[0])
    if config.use_mock_data:
        validation_case.theta_entry = 0.0
        validation_case.B_rho = (1.0 * M_P_KG * validation_case.v_mag) / E_CHARGE
        return

    v_perp = float(np.sqrt(V_init[0, 0] ** 2 + V_init[0, 2] ** 2))
    validation_case.B_rho = validation_case.gamma * M_P_KG * v_perp / E_CHARGE
    validation_case.theta_entry = float(np.arctan2(V_init[0, 0], V_init[0, 2]))


def validation_case_for_config(config):
    from transport.validation.cases.drift import DriftValidation
    from transport.validation.cases.dipole import DipoleValidation

    if config.case_type == "drift":
        case = DriftValidation()
    else:
        case = DipoleValidation()
    apply_reference_context(case, config)
    return case


def expand_beam(config, n, pos_sigma, vel_sigma, rng_seed):
    rng = np.random.default_rng(rng_seed)
    R_beam = np.tile(config.R_init, (n, 1))
    V_beam = np.tile(config.V_init, (n, 1))
    R_beam[:, 0] += rng.normal(0.0, pos_sigma, n)
    R_beam[:, 1] += rng.normal(0.0, pos_sigma, n)
    V_beam[:, 0] += rng.normal(0.0, vel_sigma, n)
    V_beam[:, 1] += rng.normal(0.0, vel_sigma, n)
    charges_beam = np.tile(config.charges, n)
    gamma_beam = np.tile(config.gamma_init, n)
    return R_beam, V_beam, gamma_beam, charges_beam
