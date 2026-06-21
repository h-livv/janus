import numpy as np
from transport.dependencies.boris_solver import run_physics_loop

FAIL_PENALTY = 1e15  # Absolute failure threshold
DEATH_PENALTY = 1e6  # Penalty per dead particle
GRADIENT_PENALTY = 1e5 # Penalty based on Z-distance
SURVIVAL_REWARD = 1e8 # Reward per alive particle


def evaluate_beam(params, R_init, V_init, gamma_init, machine, config_dict, quad_indices, horn_idx, B_rho, history=None, tracker=None, lock=None, charges=None):
    # 1. Apply params (5D) to Horn and Quadrupoles
    machine.injection_elements[horn_idx].I = params[0]
    
    for i, idx in enumerate(quad_indices):
        machine.injection_elements[idx].K = params[i+1]
        machine.injection_elements[idx].g = params[i+1] * B_rho
    
    # 2. Reset state
    R = R_init.copy()
    V = V_init.copy()
    gamma = gamma_init.copy()
    
    # 3. Integration
    R_final, V_final, alive_mask, _ = run_physics_loop(
        R, V, gamma, None, None, None, None, config_dict, machine, headless=True, charges=charges
    )



    # Safety: Absolute Failure
    if np.isnan(R_final).any() or np.isnan(V_final).any():
        return FAIL_PENALTY
    
    # 4. Calculation
    radii = np.sqrt(R_final[:, 0]**2 + R_final[:, 1]**2)
    dead_mask = ~alive_mask
    num_survivors = np.sum(alive_mask)

    # Penalty calculation
    survival_rate = num_survivors / len(alive_mask)
    loss_rate = 1.0 - survival_rate
    
    survivors = alive_mask & (R_final[:, 2] > machine.inj_L)
    if np.sum(survivors) > 0:
        radii_survivors = radii[survivors]
        rms_beam_size = np.sqrt(np.mean(radii_survivors**2))
    else:
        rms_beam_size = 1.0 # large penalty if none survive that far
        
    # The primary goal is to MAXIMIZE survival. So we make survival the heaviest negative cost.
    # If survivors are tied, we break the tie by MINIMIZING the rms_beam_size.
    total_cost = -(num_survivors * 1e6) + (rms_beam_size * 1e4)
    
    # 5. History Tracking
    if history is not None:
        if "horn_I" not in history:
            history["horn_I"] = []
        history["horn_I"].append(params[0])
        
        for i, param in enumerate(params[1:]):
            if f"k{i+1}" not in history:
                history[f"k{i+1}"] = []
            history[f"k{i+1}"].append(param)
        history["survival"].append(num_survivors / len(alive_mask))
        history["cost"].append(total_cost)
        
    # GLOBAL MEMORY TRACKER:
    # If this specific evaluation is the best we've ever seen, SAVE IT.
    is_new_best = False
    if tracker is not None and lock is not None:
        with lock:
            if num_survivors > tracker['best_survivors'] or (num_survivors == tracker['best_survivors'] and total_cost < tracker['best_cost']):
                tracker['best_survivors'] = num_survivors
                tracker['best_params'] = params.copy()
                tracker['best_cost'] = total_cost
                is_new_best = True
                print(f"[MEMORY] New personal best! Survivors: {num_survivors} (Cost: {total_cost:.4e})")
            
    print(f"Eval: [{', '.join([f'{p:.2f}' for p in params])}] -> Cost: {total_cost:.4e} (Alive: {num_survivors})")

    if np.sum(~alive_mask) > 0 and tracker is not None:
        count = tracker.get('eval_count', 0)
        tracker['eval_count'] = count + 1
        
        if count < 5 or is_new_best:
            dead_mask = ~alive_mask
            if np.sum(dead_mask) > 0:
                dead_pos_mean = np.mean(R_init[dead_mask], axis=0)
                dead_vel_mean = np.mean(V_init[dead_mask], axis=0)
            else:
                dead_pos_mean = np.array([0.0, 0.0, 0.0])
                dead_vel_mean = np.array([0.0, 0.0, 0.0])
                
            if np.sum(alive_mask) > 0:
                alive_pos_mean = np.mean(R_init[alive_mask], axis=0)
                alive_vel_mean = np.mean(V_init[alive_mask], axis=0)
            else:
                alive_pos_mean = np.array([0.0, 0.0, 0.0])
                alive_vel_mean = np.array([0.0, 0.0, 0.0])
            
            print(f"\n--- Particle Failure Diagnostic (Eval #{count}) ---")
            print(f"Dead Count: {np.sum(dead_mask)} / {len(alive_mask)}")
            print(f"Dead Pos Mean (X,Y,Z): {dead_pos_mean}")
            print(f"Alive Pos Mean (X,Y,Z): {alive_pos_mean}")
            print(f"Dead Vel Mean (Vx,Vy,Vz): {dead_vel_mean}")
            print(f"Alive Vel Mean (Vx,Vy,Vz): {alive_vel_mean}")
            print(f"-----------------------------------\n")


    return total_cost