import numpy as np
import time
from transport.dependencies.lattice import (
    Lattice,
    Drift, Quadrupole, Dipole, MagneticHorn,
    SelectorDipole, AcceptanceAperture,
)

# ---------------------------------------------------------------------------
# Physical Constants
# ---------------------------------------------------------------------------
C_LIGHT   = 299792458.0          # m/s
E_CHARGE  = 1.602176634e-19      # C
M_P_KG    = 1.67262192369e-27    # kg
M_PBAR_SI = M_P_KG               # antiproton mass == proton mass
Q_PBAR_SI = -E_CHARGE            # antiproton charge (legacy scalar)


# ---------------------------------------------------------------------------
# Charge-Aware Relativistic Boris Integrator
# ---------------------------------------------------------------------------

def relativistic_boris_step(R, V, gamma, dt, alive_mask, machine, charges=None):
    """
    Single Boris push for all alive particles.

    Parameters
    ----------
    charges : np.ndarray of int8, shape (N,), values {-1, +1}
        Per-particle charge in units of elementary charge.
        If None, all particles are treated as antiprotons (q = -1).
    """
    if not np.any(alive_mask):
        return R, V

    # ── Magnetic field at alive-particle positions ───────────────────────
    B_alive = machine.get_B_field(R[alive_mask])  # (N_alive, 3)

    # ── Per-particle q/m ratio ───────────────────────────────────────────
    if charges is None:
        # Backward compat: scalar antiproton q/m broadcast over all alive
        q_over_m_alive = np.full(int(np.sum(alive_mask)),
                                 Q_PBAR_SI / M_PBAR_SI, dtype=np.float64)
    else:
        # charges[alive_mask] has values -1 or +1
        q_over_m_alive = (charges[alive_mask].astype(np.float64)
                          * E_CHARGE / M_PBAR_SI)   # negative for pbar

    V_alive     = V[alive_mask]
    gamma_alive = gamma[alive_mask]

    u = gamma_alive[:, np.newaxis] * V_alive

    # Boris rotation half-angles (per-particle q/m broadcasts over xyz)
    t     = q_over_m_alive[:, np.newaxis] * B_alive * (dt / 2.0) / gamma_alive[:, np.newaxis]
    t_sq  = np.sum(t**2, axis=1)[:, np.newaxis]

    # If |t| > 1.0, the rotation angle is too large for the timestep.
    # Flag these as dead to prevent NaN propagation.
    unstable_mask = t_sq > 1.0
    if np.any(unstable_mask):
        alive_mask[unstable_mask] = False
        # Optional: Log a warning that dt is too large for the current B-field
    
    s     = 2.0 * t / (1.0 + t_sq)

    u_prime = u + np.cross(u, t)
    u_plus  = u + np.cross(u_prime, s)

    V_new = u_plus / gamma_alive[:, np.newaxis]

    # ── Safety clamp: |v| < 0.999 c ─────────────────────────────────────
    v_mag_sq      = np.sum(V_new**2, axis=1)
    mask_too_fast = v_mag_sq >= (0.999 * C_LIGHT)**2
    if np.any(mask_too_fast):
        v_mag = np.sqrt(v_mag_sq[mask_too_fast])
        V_new[mask_too_fast] = (V_new[mask_too_fast]
                                / v_mag[:, np.newaxis]) * (0.999 * C_LIGHT)

    R_new = R[alive_mask] + V_new * dt

    V[alive_mask] = V_new
    R[alive_mask] = R_new

    return R, V


# ---------------------------------------------------------------------------
# Zone-Aware Boundary Detection
# ---------------------------------------------------------------------------

def _check_boundaries_three_zone(R, alive_mask, machine, r_pipe,
                                  passed_aperture_mask, death_causes,
                                  annihilation_queue=None, headless=False,
                                  charges=None):
    """
    Apply collision / aperture / exit tests zone-by-zone for the new
    three-zone lattice.  Returns updated alive_mask; mutates arrays in-place.
    """
    z_vals = R[:, 2]
    x_vals = R[:, 0]
    y_vals = R[:, 1]

    half_cw = machine.dipole_chamber_width  / 2.0
    half_ch = machine.dipole_chamber_height / 2.0

    # ── Zone 1: Target/Horn Chamber (0 → 0.5) ───────────────────────────
    in_chamber = (z_vals >= 0.0) & (z_vals < 0.5)
    outside_chamber = (
        ((np.abs(x_vals) >= half_cw) | (np.abs(y_vals) >= half_ch))
        & in_chamber & alive_mask
    )
    if np.any(outside_chamber):
        _kill_particles(outside_chamber, R, alive_mask, death_causes,
                        "Chamber wall", annihilation_queue, headless, charges)

    # ── Downstream Circular Pipe (z >= 0.5 → fodo_end_z) ────────────────
    in_pipe = (z_vals >= 0.5) & (z_vals < machine.fodo_end_z)
    x_ref, _ = machine.get_reference_trajectory(z_vals)
    r_match_sq = machine.matching_aperture_radius**2
    
    is_inside = np.zeros_like(alive_mask, dtype=bool)
    
    # 1. Straight pipe before dipole: 0.5 <= z < 8.5
    before_dipole = (z_vals >= 0.5) & (z_vals < 8.5)
    if np.any(before_dipole):
        # Orbit-centered aperture check
        dx = x_vals[before_dipole] - x_ref[before_dipole]
        dy = y_vals[before_dipole]
        is_inside[before_dipole] = (dx**2 + dy**2 < r_match_sq)
    
    # 2. Racetrack chamber inside selector dipole: 8.5 <= z < machine.prism_end_z
    inside_dipole = (z_vals >= 8.5) & (z_vals < machine.prism_end_z)
    if np.any(inside_dipole):
        x_ref_dip = x_ref[inside_dipole]
        x_vals_dip = x_vals[inside_dipole]
        y_vals_dip = y_vals[inside_dipole]
        
        # Orbit-centered aperture check
        dx = x_vals_dip - x_ref_dip
        dy = y_vals_dip
        is_inside[inside_dipole] = (
            ((dy**2 < r_match_sq) & (x_vals_dip >= x_ref_dip) & (x_vals_dip <= -x_ref_dip)) |
            (dx**2 + dy**2 < r_match_sq) |
            ((x_vals_dip + x_ref_dip)**2 + dy**2 < r_match_sq)
        )
        
    # 3. Antiproton pipe after selector dipole: z >= machine.prism_end_z
    after_dipole = (z_vals >= machine.prism_end_z)
    if np.any(after_dipole):
        # Orbit-centered aperture check
        dx = x_vals[after_dipole] - x_ref[after_dipole]
        dy = y_vals[after_dipole]
        is_inside[after_dipole] = (dx**2 + dy**2 < r_match_sq)
        
    outside_pipe = (~is_inside) & in_pipe & alive_mask

    if np.any(outside_pipe):
        _kill_particles(outside_pipe, R, alive_mask, death_causes,
                        "Pipe wall", annihilation_queue, headless, charges)

    # 1c. Acceptance aperture (checked once per particle when z crosses plane)
    if machine.aperture is not None:
        just_crossed = (~passed_aperture_mask) & (z_vals >= machine.aperture.z_plane) & alive_mask
        if np.any(just_crossed):
            x_ref_ap, _ = machine.get_reference_trajectory(machine.aperture.z_plane)
            dx      = x_vals[just_crossed] - x_ref_ap
            dy      = y_vals[just_crossed]
            r_from  = np.sqrt(dx**2 + dy**2)
            fails   = r_from > machine.aperture.radius

            failed_global = np.zeros_like(alive_mask)
            jc_indices    = np.where(just_crossed)[0]
            failed_global[jc_indices[fails]] = True
            failed_global &= alive_mask

            if np.any(failed_global):
                _kill_particles(failed_global, R, alive_mask, death_causes,
                                "Aperture rejected", annihilation_queue, headless, charges)

            # Mark all just-crossed particles as aperture-checked
            passed_aperture_mask[just_crossed] = True

    # ── Transport exit (z >= fodo_end_z) ─────────────────────────────────
    # Collector Ring injection plane is at fodo_end_z
    exited = (z_vals >= machine.fodo_end_z) & alive_mask
    if np.any(exited):
        for idx in np.where(exited)[0]:
            if "Survived" not in death_causes:
                death_causes["Survived"] = [0, 0]
            elif isinstance(death_causes["Survived"], int):
                death_causes["Survived"] = [death_causes["Survived"], 0]
            
            chg = charges[idx] if charges is not None else -1
            if chg == -1:
                death_causes["Survived"][0] += 1
            else:
                death_causes["Survived"][1] += 1
        alive_mask[exited] = False
        if not headless:
            for idx in np.where(exited)[0]:
                R[idx] = np.nan

    return alive_mask



def _kill_particles(mask, R, alive_mask, death_causes,
                    cause, annihilation_queue, headless, charges=None):
    """Mark particles as dead; push annihilation events to the renderer queue."""
    indices = np.where(mask)[0]
    for idx in indices:
        if not alive_mask[idx]:
            continue
        if cause is not None:
            if cause not in death_causes:
                death_causes[cause] = [0, 0]
            elif isinstance(death_causes[cause], int):
                death_causes[cause] = [death_causes[cause], 0]

            chg = charges[idx] if charges is not None else -1
            if chg == -1:
                death_causes[cause][0] += 1
            else:
                death_causes[cause][1] += 1

        alive_mask[idx] = False
        if not headless and annihilation_queue is not None:
            annihilation_queue.put(R[idx].copy())
        if not headless:
            R[idx] = np.nan


# ---------------------------------------------------------------------------
# Main Physics Loop
# ---------------------------------------------------------------------------

def run_physics_loop(R, V, gamma, shm_name, sync_queue, annihilation_queue,
                     stop_event, config_dict, machine,
                     headless=False, headless_time_ns=150.0,
                     charges=None):
    """
    Dedicated CPU process for particle physics.

    Parameters
    ----------
    charges : np.ndarray of int8, shape (N,), values {-1, +1}
        Per-particle charge in elementary-charge units.  None → all pbar.
    """
    r_pipe        = config_dict.get("R_PIPE", 0.10)

    # Initialise death-cause dictionary
    death_causes = {"Dump": [0, 0], "Chamber wall": [0, 0], "Aperture rejected": [0, 0],
                    "Pipe wall": [0, 0], "Survived": [0, 0]}

    # ── HEADLESS MODE ─────────────────────────────────────────────────────
    if headless:
        dt = 50e-12
        N  = R.shape[0]
        alive_mask           = np.ones(N, dtype=bool)
        passed_aperture_mask = np.zeros(N, dtype=bool)

        time_required  = headless_time_ns * 1e-9
        required_steps = int(time_required / dt)

        for step in range(required_steps):
            if not np.any(alive_mask):
                break

            # Recompute gamma before each step
            v_mag_sq = np.sum(V[alive_mask]**2, axis=1)
            v_mag_sq = np.clip(v_mag_sq, 0, (0.999 * C_LIGHT)**2)
            gamma[alive_mask] = 1.0 / np.sqrt(1.0 - v_mag_sq / C_LIGHT**2)

            try:
                R, V = relativistic_boris_step(
                    R, V, gamma, dt, alive_mask, machine, charges
                )

                if np.any(np.isnan(R[alive_mask])) or np.any(np.isinf(R[alive_mask])):
                    print(f"\n[Physics Exploded!] Step {step}: NaN/Inf in alive particles.")
                    return R, V, alive_mask, death_causes

                # Recompute gamma after step
                v_mag_sq = np.sum(V[alive_mask]**2, axis=1)
                v_mag_sq = np.clip(v_mag_sq, 0, (0.999 * C_LIGHT)**2)
                gamma[alive_mask] = 1.0 / np.sqrt(1.0 - v_mag_sq / C_LIGHT**2)

            except Exception as e:
                print(f"\n[Physics Runtime Error] Step {step}: {e}")
                return R, V, alive_mask, death_causes

            # Boundary checks
            _check_boundaries_three_zone(
                R, alive_mask, machine, r_pipe,
                passed_aperture_mask, death_causes,
                annihilation_queue=None, headless=True,
                charges=charges
            )

        return R, V, alive_mask, death_causes

    # ── VISUAL MODE ───────────────────────────────────────────────────────
    print("[Physics] Engine started.")
    try:
        from multiprocessing import shared_memory

        dt            = config_dict.get("dt_visual", 2e-12)
        emission_rate = config_dict.get("emission_rate", 2)

        shm          = shared_memory.SharedMemory(name=shm_name)
        N            = R.shape[0]
        shared_array = np.ndarray((2, N, 3), dtype=np.float32, buffer=shm.buf)

        buffer_index         = 0
        step                 = 0
        alive_mask           = np.ones(N, dtype=bool)
        passed_aperture_mask = np.zeros(N, dtype=bool)
        all_dead_reported    = False

        while not stop_event.is_set():
            if not np.any(alive_mask) and not all_dead_reported:
                print("\n[!] FATAL: Total Beam Loss. All particles have been lost!\n")
                all_dead_reported = True

            # Physics integration
            R, V = relativistic_boris_step(
                R, V, gamma, dt, alive_mask, machine, charges
            )

            # Boundary checks
            _check_boundaries_three_zone(
                R, alive_mask, machine, r_pipe,
                passed_aperture_mask, death_causes,
                annihilation_queue=annihilation_queue, headless=False,
                charges=charges
            )

            # Emit to renderer at configured rate
            if step % emission_rate == 0:
                shared_array[buffer_index] = R.astype(np.float32)
                sync_queue.put(buffer_index)
                buffer_index = 1 - buffer_index

            step += 1

    except Exception as e:
        print(f"[Physics] Error: {e}")
    finally:
        shm.close()
        print("[Physics] Engine stopped.")
