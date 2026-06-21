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
from transport.optimization.dependencies.evaluate_injection import evaluate_beam
from transport.optimization.dependencies.utils import setup_run_directory, generate_report, plot_initial_phase_space



def main():
    config_path = os.path.abspath("transport/config.json") # Ensure path is correct
    machine, config_dict = Lattice.load_from_json(config_path)
    
    # Setup Particles
    from transport.dependencies.data_io import extract_cern_ad_seeds, get_run_files
    hdf5_paths = get_run_files(outputs_dir_name="runs", target_filename="simulation.hdf5")
    R, V, gamma, charges = extract_cern_ad_seeds(hdf5_paths)
    
    # --- Train / Validation Split ---
    train_ratio = 0.7
    N_total = R.shape[0]
    indices = np.arange(N_total)
    rng = np.random.RandomState(42)
    rng.shuffle(indices)
    
    split_idx = int(N_total * train_ratio)
    train_idx = indices[:split_idx]
    val_idx = indices[split_idx:]
    
    R_train, V_train, gamma_train, charges_train = R[train_idx], V[train_idx], gamma[train_idx], charges[train_idx]
    R_val, V_val, gamma_val, charges_val = R[val_idx], V[val_idx], gamma[val_idx], charges[val_idx]
    
    print(f"[Main] Split {N_total} particles into {len(train_idx)} train and {len(val_idx)} validation.")
    
    horn_idx = next(idx for idx, el in enumerate(machine.injection_elements) if type(el).__name__ == "MagneticHorn")
    quad_indices = [idx for idx, el in enumerate(machine.injection_elements) 
                    if type(el).__name__ == "Quadrupole"][:4]
    B_rho = (config_dict.get("reference_p_gevc", 3.57) * 1e9) / 299792458.0
    
    # Initialize robust history
    history = {"cost": [], "survival": []}
    
    def callback_func(xk, convergence):
        """Evaluates the best config per generation to populate the plot history in the main thread."""
        evaluate_beam(xk, R_train, V_train, gamma_train, machine, config_dict, quad_indices, horn_idx, B_rho, history=history, charges=charges_train)
 
    from multiprocessing import Manager
    manager = Manager()
    tracker = manager.dict({'best_survivors': 0, 'best_params': None, 'best_cost': float('inf')})
    lock = manager.Lock()
    
    obj_func = partial(
        evaluate_beam, 
        R_init=R_train, V_init=V_train, gamma_init=gamma_train, 
        machine=machine, config_dict=config_dict, 
        quad_indices=quad_indices, horn_idx=horn_idx, B_rho=B_rho, 
        tracker=tracker, lock=lock, history=history, charges=charges_train
    )
    
    # Bounds for parameters: [Horn_I (Amps), K1, K2, K3, K4]
    # Horn is capped at -400kA magnitude
    bounds = [(-400000.0, 400000.0), (-15.0, 15.0), (-15.0, 15.0), (-15.0, 15.0), (-15.0, 15.0)]
    
    print("[Optimizer] Stage 1: Starting Global Search (Differential Evolution)...")
    
    try:
        result = differential_evolution(
            obj_func, 
            bounds, 
            strategy='best1bin', 
            maxiter=30,
            popsize=15,
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
    
    # Retrieve best from tracker to ensure we start from the true best, even if DE got stuck
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
    print(f"Optimal K-values: {final_best_params[1:]}")
    print(f"Best Cost: {tracker['best_cost']:.4e}")
    
    # --- STAGE 3: Final Validation ---
    machine.injection_elements[horn_idx].I = final_best_params[0]
    for i, idx in enumerate(quad_indices):
        machine.injection_elements[idx].K = final_best_params[i+1]
        machine.injection_elements[idx].g = final_best_params[i+1] * B_rho

    from transport.dependencies.boris_solver import run_physics_loop
    
    _, _, alive_mask_train, _ = run_physics_loop(R_train.copy(), V_train.copy(), gamma_train.copy(), None, None, None, None, config_dict, machine, headless=True, charges=charges_train)
    train_survival = np.sum(alive_mask_train) / len(alive_mask_train)
    
    _, _, alive_mask_val, _ = run_physics_loop(R_val.copy(), V_val.copy(), gamma_val.copy(), None, None, None, None, config_dict, machine, headless=True, charges=charges_val)
    val_survival = np.sum(alive_mask_val) / len(alive_mask_val)
    
    print(f"\n--- Model Performance ---")
    print(f"Training Survival Rate: {train_survival * 100:.2f}% ({np.sum(alive_mask_train)}/{len(alive_mask_train)})")
    print(f"Validation Survival Rate: {val_survival * 100:.2f}% ({np.sum(alive_mask_val)}/{len(alive_mask_val)})")
    
    # Calculate detailed species statistics on the full dataset
    charges_full = np.concatenate([charges_train, charges_val])
    alive_full = np.concatenate([alive_mask_train, alive_mask_val])
    
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
        
    generate_report(run_dir, history, raw_data, final_best_params, train_survival=train_survival, val_survival=val_survival, pbar_proton_stats=pbar_proton_stats)
    
    # Plot initial phase space
    R_full = np.vstack([R_train, R_val])
    V_full = np.vstack([V_train, V_val])
    plot_initial_phase_space(run_dir, R_full, V_full, alive_full)

if __name__ == "__main__":
    main()