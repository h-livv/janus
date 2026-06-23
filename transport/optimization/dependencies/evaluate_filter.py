import numpy as np
import copy
from transport.dependencies.boris_solver import run_physics_loop

FAIL_PENALTY = 1e15  # Absolute failure threshold

def evaluate_beam_filter(params, R_init, V_init, gamma_init, charges, machine, config_dict, horn_idx, selector_idx, history=None, tracker=None, lock=None):
    
    # 1. Create a fully isolated sandbox for this specific worker
    local_machine = copy.deepcopy(machine)
    
    # 2. Apply the optimizer's parameters to the LOCAL copy
    horn_I, dipole_By, aperture_x_offset = params
    
    # --- HARD BOUNDARY ENFORCEMENT ---
    if not (-400000.0 <= horn_I <= 400000.0) or \
       not (0.0 <= dipole_By <= 2.0) or \
       not (-0.3 <= aperture_x_offset <= 0.3):
        return 1e15 # Return an "infinite" cost to repel the simplex

    if horn_I > 390000 or horn_I < -390000:
        print(f"[Warning] Optimizer pushing Horn Current to boundary: {horn_I:.0f} A")
    if dipole_By > 1.9 or dipole_By < 0.1:
        print(f"[Warning] Optimizer pushing Dipole field to boundary: {dipole_By:.3f} T")
    if aperture_x_offset > 0.28 or aperture_x_offset < -0.28:
        print(f"[Warning] Optimizer pushing Aperture X-Offset to boundary: {aperture_x_offset:.3f} m")
    
    local_machine.prism_elements[horn_idx].I = horn_I
    local_machine.prism_elements[selector_idx].By = dipole_By
    if local_machine.aperture is not None:
        local_machine.aperture.x_offset = aperture_x_offset

    # 3. Pass the LOCAL machine into the physics loop
    R_final, _, _, _ = run_physics_loop(
        R_init.copy(), V_init.copy(), gamma_init.copy(), None, None, None, None, 
        config_dict, local_machine, headless=True, charges=charges
    )
    
    # 1. Apply params (3D) to Horn, Dipole and Aperture
    machine.prism_elements[horn_idx].I = params[0]
    machine.prism_elements[selector_idx].By = params[1]
    if machine.aperture is not None:
        machine.aperture.x_offset = params[2]
        
    # 2. Reset state
    R = R_init.copy()
    V = V_init.copy()
    gamma = gamma_init.copy()
    
    # 3. Run physics loop
    R_final, V_final, alive_mask, _ = run_physics_loop(
        R, V, gamma, None, None, None, None, config_dict, machine, headless=True, charges=charges
    )
    
    # Safety check for absolute failure
    if np.isnan(R_final).any() or np.isnan(V_final).any():
        return FAIL_PENALTY
        
    # 4. Identify survivors at the z = 10.0 m plane
    z_final = R_final[:, 2]
    x_final = R_final[:, 0]
    y_final = R_final[:, 1]
    
    # A particle survived if it crossed z >= 10.0 and was within the aperture
    dx_ap = x_final - machine.aperture.x_offset if machine.aperture is not None else x_final
    dy_ap = y_final
    r_from = np.sqrt(dx_ap**2 + dy_ap**2)
    
    aperture_r = machine.aperture.radius if machine.aperture is not None else 1.0
    survived_mask = (z_final >= 10.0) & (r_from <= aperture_r)
    
    # Separate antiprotons (q = -1) and protons (q = 1)
    pbar_mask = (charges == -1)
    proton_mask = (charges == 1)
    
    surviving_pbar_mask = survived_mask & pbar_mask
    surviving_proton_mask = survived_mask & proton_mask
    
    num_pbar_survivors = np.sum(surviving_pbar_mask)
    num_proton_survivors = np.sum(surviving_proton_mask)
    
    target_pbar = np.sum(pbar_mask)
    target_proton = np.sum(proton_mask)
    
    pbar_survival_rate = num_pbar_survivors / target_pbar if target_pbar > 0 else 0.0
    proton_survival_rate = num_proton_survivors / target_proton if target_proton > 0 else 0.0
    
    # Calculate RMS beam size for surviving antiprotons relative to the aperture center
    if num_pbar_survivors > 0:
        rms_beam_size = np.sqrt(np.mean(dx_ap[surviving_pbar_mask]**2 + dy_ap[surviving_pbar_mask]**2))
    else:
        rms_beam_size = 1.0  # large penalty if none survive
        
    # 5. Hybrid squared loss function calculation
    alpha = 1000.0
    beta = 500.0
    total_cost = alpha * (1.0 - pbar_survival_rate)**2 + beta * rms_beam_size + (num_proton_survivors * 1e6)
    
    # 6. Populate history in main thread (if history dict provided)
    if history is not None:
        if "horn_I" not in history:
            history["horn_I"] = []
        if "dipole_By" not in history:
            history["dipole_By"] = []
        if "aperture_x_offset" not in history:
            history["aperture_x_offset"] = []
        if "survival_pbar" not in history:
            history["survival_pbar"] = []
        if "survival_proton" not in history:
            history["survival_proton"] = []
        if "cost" not in history:
            history["cost"] = []
            
        history["horn_I"].append(params[0])
        history["dipole_By"].append(params[1])
        history["aperture_x_offset"].append(params[2])
        history["survival_pbar"].append(pbar_survival_rate)
        history["survival_proton"].append(proton_survival_rate)
        history["cost"].append(total_cost)
        
    # 7. Global memory tracker (thread-safe)
    is_new_best = False
    if tracker is not None and lock is not None:
        with lock:
            if num_pbar_survivors > tracker['best_survivors'] or (num_pbar_survivors == tracker['best_survivors'] and total_cost < tracker['best_cost']):
                tracker['best_survivors'] = num_pbar_survivors
                tracker['best_params'] = params.copy()
                tracker['best_cost'] = total_cost
                is_new_best = True
                print(f"[MEMORY] New personal best! pbar Survivors: {num_pbar_survivors}/{target_pbar} (proton Survivors: {num_proton_survivors}/{target_proton}, Cost: {total_cost:.4f})")
                
    print(f"Eval: [{params[0]:.2f} A, {params[1]:.4f} T, {params[2]:.4f} m] -> Cost: {total_cost:.4e} (pbar: {num_pbar_survivors}, proton: {num_proton_survivors})")
    
    # Failure diagnostics on new best
    if np.sum(~survived_mask) > 0 and tracker is not None:
        count = tracker.get('eval_count', 0)
        tracker['eval_count'] = count + 1
        
        if count < 5 or is_new_best:
            dead_mask = ~survived_mask
            
            # Print failure diagnostics for antiprotons
            dead_pbar_mask = dead_mask & pbar_mask
            alive_pbar_mask = surviving_pbar_mask
            
            if np.sum(dead_pbar_mask) > 0:
                dead_pos_mean = np.mean(R_init[dead_pbar_mask], axis=0)
                dead_vel_mean = np.mean(V_init[dead_pbar_mask], axis=0)
            else:
                dead_pos_mean = np.array([0.0, 0.0, 0.0])
                dead_vel_mean = np.array([0.0, 0.0, 0.0])
                
            if np.sum(alive_pbar_mask) > 0:
                alive_pos_mean = np.mean(R_init[alive_pbar_mask], axis=0)
                alive_vel_mean = np.mean(V_init[alive_pbar_mask], axis=0)
            else:
                alive_pos_mean = np.array([0.0, 0.0, 0.0])
                alive_vel_mean = np.array([0.0, 0.0, 0.0])
                
            print(f"\n--- Antiproton Failure Diagnostic (Eval #{count}) ---")
            print(f"Dead pbar: {np.sum(dead_pbar_mask)} / {target_pbar}")
            print(f"Dead Pos Mean (X,Y,Z): {dead_pos_mean}")
            print(f"Alive Pos Mean (X,Y,Z): {alive_pos_mean}")
            print(f"Dead Vel Mean (Vx,Vy,Vz): {dead_vel_mean}")
            print(f"Alive Vel Mean (Vx,Vy,Vz): {alive_vel_mean}")
            print(f"-----------------------------------\n")
            
    return total_cost