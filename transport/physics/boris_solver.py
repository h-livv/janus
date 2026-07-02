import numpy as np

# Physical Constants
C_LIGHT   = 299792458.0          # m/s
E_CHARGE  = 1.602176634e-19      # C
M_P_KG    = 1.67262192369e-27    # kg
M_P_MEV   = 938.2720813          # MeV/c^2


def apply_aperture_losses(R, alive_mask, lattice):
    """
    Mark particles outside the active element aperture as lost.
    Delegates boundary evaluation to the lattice element interface.
    """
    inside = lattice.inside_aperture(R[:, 0], R[:, 1], R[:, 2])
    return alive_mask & inside


def positions_for_render(R, alive_mask):
    """Export transport positions; lost particles are NaN for the renderer."""
    out = R.astype(np.float32)
    out[~alive_mask] = np.nan
    return out


def boris_velocity_push(R, V, gamma, dt, alive_mask, lattice, charges=None):
    """
    Relativistic Boris velocity update only; R is used for field evaluation.
    """
    if not np.any(alive_mask):
        return V, gamma

    V_alive = V[alive_mask]
    R_alive = R[alive_mask]
    gamma_alive = gamma[alive_mask]

    Bx, By, Bz = lattice.get_field(R_alive[:, 0], R_alive[:, 1], R_alive[:, 2])
    B_alive = np.column_stack((Bx, By, Bz))

    if charges is None:
        q_over_m = np.full(len(R_alive), -E_CHARGE / M_P_KG)
    else:
        q_over_m = (charges[alive_mask].astype(np.float64) * E_CHARGE) / M_P_KG

    # 1. Electric field acceleration half-step: u_minus = gamma^n * v + q_over_m * E^n * (dt / 2)
    # (Currently E = 0, but structured for future extensions)
    u_minus = gamma_alive[:, np.newaxis] * V_alive

    u_minus_sq = np.sum(u_minus**2, axis=1)
    gamma_minus = np.sqrt(1.0 + u_minus_sq / C_LIGHT**2)

    # 2. Magnetic rotation step
    t = q_over_m[:, np.newaxis] * B_alive * (dt / 2.0) / gamma_minus[:, np.newaxis]
    t_sq = np.sum(t**2, axis=1)[:, np.newaxis]
    s = 2.0 * t / (1.0 + t_sq)

    u_prime = u_minus + np.cross(u_minus, t)
    u_plus = u_minus + np.cross(u_prime, s)

    # 3. Electric field acceleration second half-step: u_new = u_plus + q_over_m * E^n * (dt / 2)
    u_new = u_plus

    u_new_sq = np.sum(u_new**2, axis=1)
    gamma_new = np.sqrt(1.0 + u_new_sq / C_LIGHT**2)
    V_new = u_new / gamma_new[:, np.newaxis]

    v_mag_sq = np.sum(V_new**2, axis=1)
    too_fast = v_mag_sq >= (0.999 * C_LIGHT)**2
    if np.any(too_fast):
        v_mag = np.sqrt(v_mag_sq[too_fast])
        V_new[too_fast] = (V_new[too_fast] / v_mag[:, np.newaxis]) * (0.999 * C_LIGHT)
        v_cap_sq = np.sum(V_new[too_fast]**2, axis=1)
        gamma_new[too_fast] = 1.0 / np.sqrt(1.0 - v_cap_sq / C_LIGHT**2)

    V[alive_mask] = V_new
    gamma[alive_mask] = gamma_new

    return V, gamma


def relativistic_boris_step(R, V, gamma, dt, alive_mask, lattice, charges=None):
    """
    Perform a staggered Leapfrog integration step using the relativistic Boris solver.
    Input R is at t^n, and V is at t^{n-1/2}.
    Output R is at t^{n+1}, and V is at t^{n+1/2}.
    Gamma is updated dynamically inside the step.
    """
    if not np.any(alive_mask):
        return R, V, gamma

    V, gamma = boris_velocity_push(R, V, gamma, dt, alive_mask, lattice, charges)

    V_alive = V[alive_mask]
    R_alive = R[alive_mask]
    R_new = R_alive + V_alive * dt
    R[alive_mask] = R_new

    return R, V, gamma

def track_particles(R_init, V_init, gamma_init, charges, lattice, dt, max_steps):
    """
    Track a set of particles through a lattice using a staggered Leapfrog Boris scheme.
    """
    N = len(R_init)
    R = R_init.copy()
    V = V_init.copy()
    
    # Compute self-consistent relativistic gamma from V to avoid input rounding mismatches
    v_mag_sq = np.sum(V**2, axis=1)
    gamma = 1.0 / np.sqrt(1.0 - v_mag_sq / C_LIGHT**2)
    alive_mask = np.ones(N, dtype=bool)

    # Stagger initial velocity backward by dt/2 to obtain V^{-1/2}
    V, gamma = boris_velocity_push(R, V, gamma, -dt / 2.0, alive_mask, lattice, charges)
    alive_mask = apply_aperture_losses(R, alive_mask, lattice)

    diagnostics = {
        "step": [],
        "time": [],
        "position": [],
        "momentum": [],
        "gamma": [],
        "field": [],
        "element": [],
        "alive": []
    }

    t = 0.0
    for step in range(max_steps):
        if not np.any(alive_mask):
            break

        # Save old values before updating
        V_old = V.copy()
        R_old = R.copy()
        gamma_old = gamma.copy()

        # Perform the Boris push: updates R^n -> R^{n+1} and V^{n-1/2} -> V^{n+1/2}
        R, V, gamma = relativistic_boris_step(R, V, gamma, dt, alive_mask, lattice, charges)

        # Synchronize diagnostics to integer step t^n via averaging
        V_sync = (V_old + V) / 2.0
        gamma_sync = (gamma_old + gamma) / 2.0
        mom_sync = gamma_sync[:, np.newaxis] * M_P_MEV * (V_sync / C_LIGHT)

        Bx, By, Bz = lattice.get_field(R_old[:, 0], R_old[:, 1], R_old[:, 2])
        fields = np.column_stack((Bx, By, Bz))

        element_names = []
        for idx in range(N):
            el = lattice.get_element_at_z(R_old[idx, 2])
            element_names.append(type(el).__name__ if el else "None")

        # Record diagnostics at t^n
        diagnostics["step"].append(step)
        diagnostics["time"].append(t)
        diagnostics["position"].append(R_old.copy())
        diagnostics["momentum"].append(mom_sync.copy())
        diagnostics["gamma"].append(gamma_sync.copy())
        diagnostics["field"].append(fields.copy())
        diagnostics["element"].append(element_names)
        diagnostics["alive"].append(alive_mask.copy())

        alive_mask = apply_aperture_losses(R, alive_mask, lattice)

        t += dt

    # Unstagger final velocity to t^N
    V_final = V.copy()
    R_temp = R.copy()
    _, V_final, gamma_final = relativistic_boris_step(R_temp, V_final, gamma, dt / 2.0, alive_mask, lattice, charges)
    mom_final = gamma_final[:, np.newaxis] * M_P_MEV * (V_final / C_LIGHT)

    Bx, By, Bz = lattice.get_field(R[:, 0], R[:, 1], R[:, 2])
    fields = np.column_stack((Bx, By, Bz))
    element_names = []
    for idx in range(N):
        el = lattice.get_element_at_z(R[idx, 2])
        element_names.append(type(el).__name__ if el else "None")

    diagnostics["step"].append(max_steps)
    diagnostics["time"].append(t)
    diagnostics["position"].append(R.copy())
    diagnostics["momentum"].append(mom_final.copy())
    diagnostics["gamma"].append(gamma_final.copy())
    diagnostics["field"].append(fields.copy())
    diagnostics["element"].append(element_names)
    diagnostics["alive"].append(alive_mask.copy())

    for key in ["step", "time", "position", "momentum", "gamma", "field", "alive"]:
        diagnostics[key] = np.array(diagnostics[key])

    return R, V_final, alive_mask, diagnostics


def run_visual_physics_loop(R_init, V_init, gamma_init, charges, lattice, dt, shared_mem_name, sync_queue, stop_event):
    """
    Dedicated loop for updating the shared memory buffer during visual tracking.
    """
    from multiprocessing.shared_memory import SharedMemory
    shm = SharedMemory(name=shared_mem_name)
    N = len(R_init)
    shared_array = np.ndarray((2, N, 3), dtype=np.float32, buffer=shm.buf)
    
    R = R_init.copy()
    V = V_init.copy()
    
    v_mag_sq = np.sum(V**2, axis=1)
    gamma = 1.0 / np.sqrt(1.0 - v_mag_sq / C_LIGHT**2)
    alive_mask = np.ones(N, dtype=bool)
    
    # Stagger initial velocity backward by dt/2 to obtain V^{-1/2}
    V, gamma = boris_velocity_push(R, V, gamma, -dt / 2.0, alive_mask, lattice, charges)
    alive_mask = apply_aperture_losses(R, alive_mask, lattice)

    buffer_index = 0
    step = 0
    emission_rate = 1  # Emit every step for smooth trajectory rendering

    shared_array[buffer_index] = positions_for_render(R, alive_mask)
    try:
        sync_queue.put(buffer_index, block=False)
    except Exception:
        pass
    buffer_index = 1 - buffer_index
    
    import time
    
    while not stop_event.is_set():
        if not np.any(alive_mask):
            break
            
        R, V, gamma = relativistic_boris_step(R, V, gamma, dt, alive_mask, lattice, charges)
        
        alive_mask = apply_aperture_losses(R, alive_mask, lattice)

        if step % emission_rate == 0:
            shared_array[buffer_index] = positions_for_render(R, alive_mask)
            try:
                sync_queue.put(buffer_index, block=False)
            except Exception:
                pass
            buffer_index = 1 - buffer_index
            
        step += 1
        # Throttle physics slightly to make it visible and not end instantly
        time.sleep(0.005)
        
    shm.close()

