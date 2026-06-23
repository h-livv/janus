import os
import sys
import json
import numpy as np
from scipy.optimize import differential_evolution
from functools import partial

os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from transport.dependencies.lattice import Lattice
from transport.optimization.dependencies.evaluate_filter import evaluate_beam_filter
from transport.optimization.dependencies.utils_filter import setup_run_directory, generate_report_filter, plot_initial_phase_space
from transport.dependencies.boris_solver import run_physics_loop

def run_validation(R_data, V_data, gamma_data, charges_data, machine, config_dict):
    R_final, _, _, _ = run_physics_loop(
        R_data.copy(), V_data.copy(), gamma_data.copy(), None, None, None, None, config_dict, machine, headless=True, charges=charges_data
    )
    z_final = R_final[:, 2]
    x_final = R_final[:, 0]
    y_final = R_final[:, 1]
    
    dx = x_final - machine.aperture.x_offset if machine.aperture is not None else x_final
    dy = y_final
    r_from = np.sqrt(dx**2 + dy**2)
    aperture_r = machine.aperture.radius if machine.aperture is not None else 1.0
    
    survived_mask = (z_final >= 10.0) & (r_from <= aperture_r)
    
    pbar_mask = (charges_data == -1)
    proton_mask = (charges_data == 1)
    
    surviving_pbar = survived_mask & pbar_mask
    surviving_proton = survived_mask & proton_mask
    
    pbar_survival = np.sum(surviving_pbar) / np.sum(pbar_mask) if np.sum(pbar_mask) > 0 else 0.0
    proton_survival = np.sum(surviving_proton) / np.sum(proton_mask) if np.sum(proton_mask) > 0 else 0.0
    
    return pbar_survival, proton_survival, survived_mask

def main():
    config_path = os.path.abspath("transport/config.json")
    machine, config_dict = Lattice.load_from_json(config_path)
    
    # --- Setup Particles from NPZ ---
    npz_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../runs/datasets/simulation_raw.npz"))
    print(f"[Main] Loading dataset from {npz_path}...")
    
    try:
        dataset = np.load(npz_path)
        keys = dataset.files
        
        # 1. Try explicit names first
        if 'R' in keys and 'V' in keys and 'gamma' in keys and 'charges' in keys:
            R = dataset['R']
            V = dataset['V']
            gamma = dataset['gamma']
            charges = dataset['charges']
            print("[Main] Successfully loaded explicitly named arrays (R, V, gamma, charges).")
            
        # 2. Fall back to default positional names (arr_0, arr_1, etc.)
        elif len(keys) >= 4:
            print(f"[Main] Explicit names not found. Falling back to positional keys: {keys[:4]}")
            R = dataset[keys[0]]
            V = dataset[keys[1]]
            gamma = dataset[keys[2]]
            charges = dataset[keys[3]]
            
        # 3. Fail gracefully if the file is incomplete
        else:
            print(f"[!] Error: NPZ file only contains {len(keys)} arrays: {keys}. Expected 4 (R, V, gamma, charges).")
            sys.exit(1)
            
    except FileNotFoundError:
        print(f"[!] Error: Could not find {npz_path}. Please check your path.")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Error reading NPZ file: {e}")
        sys.exit(1)
    
    # --- Downsample protons to reduce dataset size for speed ---
    pbar_mask = (charges == -1)
    proton_mask = (charges == 1)
    
    N_pbar = np.sum(pbar_mask)
    N_proton = np.sum(proton_mask)
    print(f"[Main] Loaded {N_pbar} antiprotons and {N_proton} protons.")
    
    target_protons = 5000
    rng = np.random.RandomState(42)
    
    if N_proton > target_protons:
        proton_indices = np.where(proton_mask)[0]
        sampled_proton_indices = rng.choice(proton_indices, size=target_protons, replace=False)
        pbar_indices = np.where(pbar_mask)[0]
        
        keep_indices = np.concatenate([pbar_indices, sampled_proton_indices])
        rng.shuffle(keep_indices)
        
        R = R[keep_indices]
        V = V[keep_indices]
        gamma = gamma[keep_indices]
        charges = charges[keep_indices]
        print(f"[Main] Downsampled protons from {N_proton} to {target_protons}. Total particles for optimization: {len(charges)}.")
    
    # --- Correct Superluminal Velocities (Unit Mismatch Correction) ---
    gamma_clipped = np.maximum(gamma, 1.0001)
    beta = np.sqrt(1.0 - 1.0 / gamma_clipped**2)
    c_light = 299792458.0
    v_mag_correct = beta * c_light
    
    v_mags = np.sqrt(np.sum(V**2, axis=1))
    v_mags[v_mags == 0] = 1.0
    V = V * (v_mag_correct / v_mags)[:, np.newaxis]
    print(f"[Main] Corrected velocity magnitudes to physical SI units using gamma. Mean velocity is now {np.mean(v_mag_correct):.4e} m/s.")
    
    # --- Train / Validation Split ---
    train_ratio = 0.7
    N_total = R.shape[0]
    indices = np.arange(N_total)
    rng_split = np.random.RandomState(42)
    rng_split.shuffle(indices)
    
    split_idx = int(N_total * train_ratio)
    train_idx = indices[:split_idx]
    val_idx = indices[split_idx:]
    
    R_train, V_train, gamma_train, charges_train = R[train_idx], V[train_idx], gamma[train_idx], charges[train_idx]
    R_val, V_val, gamma_val, charges_val = R[val_idx], V[val_idx], gamma[val_idx], charges[val_idx]
    
    print(f"[Main] Split {N_total} particles into {len(train_idx)} train and {len(val_idx)} validation.")
    
    # --- Configure Machine to Terminate at z = 10.0 m ---
    machine.matching_start_z = 10.0
    machine.matching_end_z = 10.0
    machine.fodo_start_z = 10.0
    machine.fodo_end_z = 10.0
    
    horn_idx = next(idx for idx, el in enumerate(machine.prism_elements) if type(el).__name__ == "MagneticHorn")
    selector_idx = next(idx for idx, el in enumerate(machine.prism_elements) if type(el).__name__ == "SelectorDipole")
    
    # Initialize robust history
    history = {
        "cost": [],
        "survival": [],
        "horn_I": [],
        "dipole_By": [],
        "aperture_x_offset": [],
        "survival_pbar": [],
        "survival_proton": []
    }
    
    def callback_func(xk, convergence):
        """Evaluates the best config per generation to populate the plot history in the main thread."""
        evaluate_beam_filter(xk, R_train, V_train, gamma_train, charges_train, machine, config_dict, horn_idx, selector_idx, history=history)

    from multiprocessing import Manager
    manager = Manager()
    tracker = manager.dict({'best_survivors': 0, 'best_params': None, 'best_cost': float('inf')})
    lock = manager.Lock()
    
    obj_func = partial(
        evaluate_beam_filter,
        R_init=R_train, V_init=V_train, gamma_init=gamma_train, charges=charges_train,
        machine=machine, config_dict=config_dict,
        horn_idx=horn_idx, selector_idx=selector_idx,
        tracker=tracker, lock=lock,
    )
    
    # Bounds for parameters: [Horn_I (Amps), Dipole_By (Tesla), Aperture_X_Offset (meters)]
    bounds = [(-400000.0, 400000.0), (0.0, 2.0), (-0.3, 0.3)]
    
    print("[Optimizer] Stage 1: Starting Global Search (Differential Evolution)...")
    
    try:
        result = differential_evolution(
            obj_func,
            bounds,
            strategy='best1bin',
            maxiter=20,
            popsize=10,
            tol=0.01,
            workers=-1,
            mutation=(0.8, 1.5),
            callback=callback_func
        )
    except KeyboardInterrupt:
        print("\n[!] Global search interrupted by user.")
        
    print(f"\n--- Stage 1 Complete ---")
    
    # --- STAGE 2: Local Refinement ---
    print("\n[Optimizer] Stage 2: Starting Local Refinement (Nelder-Mead)...")
    
    best_x0 = tracker['best_params'] if tracker['best_params'] is not None else result.x
    
    try:
        from scipy.optimize import minimize
        local_result = minimize(
            obj_func,
            x0=best_x0,
            method='Nelder-Mead',
            options={'xatol': 1e-4, 'disp': True}
        )
        final_best_params = tracker['best_params'] if tracker['best_params'] is not None else local_result.x
    except Exception as e:
        print(f"\n[!] Local refinement interrupted or failed: {e}. Falling back to best known.")
        final_best_params = tracker['best_params'] if tracker['best_params'] is not None else best_x0
        
    print(f"\n--- Optimization Complete ---")
    print(f"Optimal Horn Current: {final_best_params[0]:.2f} Amps")
    print(f"Optimal Dipole field (By): {final_best_params[1]:.4f} T")
    print(f"Optimal Aperture X-Offset: {final_best_params[2]:.4f} m")
    print(f"Best Cost: {tracker['best_cost']:.4f}")
    
    # --- STAGE 3: Final Validation ---
    machine.prism_elements[horn_idx].I = final_best_params[0]
    machine.prism_elements[selector_idx].By = final_best_params[1]
    if machine.aperture is not None:
        machine.aperture.x_offset = final_best_params[2]
        
    train_pbar_surv, train_prot_surv, survived_mask_train = run_validation(
        R_train, V_train, gamma_train, charges_train, machine, config_dict
    )
    val_pbar_surv, val_prot_surv, survived_mask_val = run_validation(
        R_val, V_val, gamma_val, charges_val, machine, config_dict
    )
    
    print(f"\n--- Model Performance ---")
    print(f"Training pbar Survival Rate: {train_pbar_surv * 100:.2f}%")
    print(f"Training proton Survival Rate: {train_prot_surv * 100:.2f}%")
    print(f"Validation pbar Survival Rate: {val_pbar_surv * 100:.2f}%")
    print(f"Validation proton Survival Rate: {val_prot_surv * 100:.2f}%")
    
    charges_full = np.concatenate([charges_train, charges_val])
    alive_full = np.concatenate([survived_mask_train, survived_mask_val])
    
    n_pbar_init = int(np.sum(charges_full == -1))
    n_pbar_survived = int(np.sum((charges_full == -1) & alive_full))
    n_pbar_annihilated = n_pbar_init - n_pbar_survived

    n_prot_init = int(np.sum(charges_full == 1))
    n_prot_survived = int(np.sum((charges_full == 1) & alive_full))
    n_prot_annihilated = n_prot_init - n_prot_survived

    pbar_proton_stats = {
        "initial_pbar": n_pbar_init,
        "survived_pbar": n_pbar_survived,
        "annihilated_pbar": n_pbar_annihilated,
        "initial_proton": n_prot_init,
        "survived_proton": n_prot_survived,
        "annihilated_proton": n_prot_annihilated
    }
    
    # Save Report
    runs_dir = os.path.join(os.path.dirname(__file__), "runs")
    run_dir = setup_run_directory(runs_dir)
    
    with open(config_path, "r") as f:
        raw_data = json.load(f)
        
    generate_report_filter(
        run_dir, history, raw_data, final_best_params,
        train_survival=(train_pbar_surv, train_prot_surv),
        val_survival=(val_pbar_surv, val_prot_surv),
        pbar_proton_stats=pbar_proton_stats
    )
    
    # Plot initial phase space
    R_full = np.vstack([R_train, R_val])
    V_full = np.vstack([V_train, V_val])
    alive_full = np.concatenate([survived_mask_train, survived_mask_val])
    plot_initial_phase_space(run_dir, R_full, V_full, alive_full)

if __name__ == "__main__":
    main()