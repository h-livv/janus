"""
Simulation configuration — compatibility view built from Experiment.

Temporary compatibility adapter.

Bridges the new Experiment architecture with legacy transport and
visualization APIs.

Will be removed once all downstream consumers operate directly on
resolved Experiment objects.
"""

from dataclasses import dataclass

import numpy as np

from transport.physics.particle_data import mass_of


@dataclass
class SimulationConfig:
    case_type: str
    lattice: object
    R_init: np.ndarray
    V_init: np.ndarray
    gamma_init: np.ndarray
    charges: np.ndarray
    dt: float
    max_steps: int
    max_steps_conv: int
    use_mock_data: bool = True
    mass: np.ndarray = None
    species: str = "proton"


def load_geant4_initial_conditions(charge_filter="any", momentum_slice=None):
    from transport.io.data_io import extract_cern_ad_seeds, get_latest_run_file

    latest_file = get_latest_run_file(
        outputs_dir_name="interactions/runs", target_filename="simulation.root"
    )
    R, V, gamma, all_charges = extract_cern_ad_seeds([latest_file])

    if charge_filter == "antiproton":
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


def build_simulation_config_from_experiment(experiment):
    from transport.experiment.resolver import experiment_to_simulation_config
    return experiment_to_simulation_config(experiment)


def validation_case_for_config(config):
    from transport.validation.registry import case_for_config, initialize_registries
    initialize_registries()
    return case_for_config(config)


def apply_reference_context(validation_case, config):
    """Legacy hook; declarative cases embed reference context at build time."""
    pass


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
