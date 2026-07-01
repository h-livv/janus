import numpy as np

def calculate_momentum_drift(diagnostics):
    """
    Computes the maximum relative change in momentum magnitude |p| 
    over the duration of the simulation for all particles while they are alive.
    """
    # momentum shape: (n_steps, N, 3)
    # alive shape: (n_steps, N)
    mom_mag = np.linalg.norm(diagnostics["momentum"], axis=2) # (n_steps, N)
    alive = diagnostics["alive"] # (n_steps, N)
    
    N_particles = mom_mag.shape[1]
    max_drifts = []
    
    for i in range(N_particles):
        alive_steps = alive[:, i]
        if not np.any(alive_steps):
            continue
        p_alive = mom_mag[alive_steps, i]
        if len(p_alive) < 2:
            continue
        p_init = p_alive[0]
        if p_init == 0:
            continue
        drifts = np.abs(p_alive - p_init) / p_init
        max_drifts.append(np.max(drifts))
        
    return np.max(max_drifts) if max_drifts else 0.0

def calculate_energy_drift(diagnostics):
    """
    Computes the maximum relative change in gamma over the duration 
    of the simulation for all particles while they are alive.
    """
    gamma = diagnostics["gamma"] # (n_steps, N)
    alive = diagnostics["alive"] # (n_steps, N)
    
    N_particles = gamma.shape[1]
    max_drifts = []
    
    for i in range(N_particles):
        alive_steps = alive[:, i]
        if not np.any(alive_steps):
            continue
        g_alive = gamma[alive_steps, i]
        if len(g_alive) < 2:
            continue
        g_init = g_alive[0]
        drifts = np.abs(g_alive - g_init) / g_init
        max_drifts.append(np.max(drifts))
        
    return np.max(max_drifts) if max_drifts else 0.0
