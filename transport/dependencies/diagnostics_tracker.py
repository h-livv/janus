import os
import sys
import copy
import logging
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import shutil

matplotlib.use('Agg')
logger = logging.getLogger("DiagnosticsTracker")

M_PBAR = 938.2720813
C_LIGHT = 299792458.0

def setup_plot_style():
    """Apply publication-quality styling to matplotlib."""
    plt.style.use('seaborn-v0_8-whitegrid')
    matplotlib.rcParams.update({
        'font.size': 12,
        'axes.labelsize': 14,
        'axes.titlesize': 16,
        'xtick.labelsize': 12,
        'ytick.labelsize': 12,
        'legend.fontsize': 12,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'grid.alpha': 0.7,
        'grid.linestyle': '--'
    })

def get_element_name(el, z_start):
    el_type = type(el).__name__
    s_start = z_start - 0.5
    if el_type == "MagneticHorn":
        return "Horn"
    elif el_type == "Quadrupole":
        if abs(s_start - 0.0) < 0.1: return "QFO0050"
        elif abs(s_start - 5.0) < 0.1: return "QDE0055"
        elif abs(s_start - 10.0) < 0.1: return "QFO0060"
        elif abs(s_start - 15.0) < 0.1: return "QDE0065"
        elif abs(s_start - 20.0) < 0.1: return "QFO0070"
        elif abs(s_start - 25.0) < 0.1: return "QDE0075"
        elif abs(s_start - 30.0) < 0.1: return "QFO0080"
        elif abs(s_start - 35.0) < 0.1: return "QDE0085"
        elif abs(s_start - 40.0) < 0.1: return "QFO0090"
        elif abs(s_start - 45.0) < 0.1: return "QDS0095"
        else: return f"Quad_{z_start:.1f}"
    elif el_type == "SelectorDipole":
        return "BHZ0058"
    elif el_type == "Dipole":
        if abs(s_start - 38.0) < 0.5:
            return "BHZ0088"
        elif abs(s_start - 46.0) < 0.5:
            return "Septum"
        else:
            return f"Dipole_{z_start:.1f}"
    elif el_type == "Drift":
        return f"Drift_{z_start:.1f}"
    else:
        return f"{el_type}_{z_start:.1f}"

def get_element_at_z(z, machine):
    if z < 0.0:
        return "Pre-target"
    if getattr(machine, 'is_acol', False):
        for el in machine.prism_elements:
            if el.z_start <= z <= el.z_end:
                return get_element_name(el, el.z_start)
        for el in machine.matching_elements:
            if el.z_start <= z <= el.z_end:
                return get_element_name(el, el.z_start)
        for el in machine.fodo_elements:
            z_s = el.z_start + machine.fodo_start_z
            z_e = el.z_end + machine.fodo_start_z
            if z_s <= z <= z_e:
                return get_element_name(el, z_s)
    return "Pipe"

def run_diagnostic_tracking(R_init, V_init, gamma_init, charges, machine, config_dict):
    """
    Step-by-step Boris solver tracking particles and taking exact plane snapshots.
    """
    from transport.dependencies.boris_solver import relativistic_boris_step, _check_boundaries_three_zone
    
    N = R_init.shape[0]
    R = R_init.copy()
    V = V_init.copy()
    gamma = gamma_init.copy()
    
    alive_mask = np.ones(N, dtype=bool)
    passed_aperture_mask = np.zeros(N, dtype=bool)
    death_causes = {"Dump": [0,0], "Chamber wall": [0,0], "Aperture rejected": [0,0], "Pipe wall": [0,0], "Survived": [0,0]}
    
    death_locations = [None] * N
    death_elements = [None] * N
    
    checkpoints = [("Target", 0.0)]
    
    if getattr(machine, 'is_acol', False):
        for el in machine.prism_elements:
            if type(el).__name__ != "Drift":
                checkpoints.append((get_element_name(el, el.z_start), el.z_end))
        for el in machine.matching_elements:
            if type(el).__name__ != "Drift":
                checkpoints.append((get_element_name(el, el.z_start), el.z_end))
        for el in machine.fodo_elements:
            if type(el).__name__ != "Drift":
                z_start = el.z_start + machine.fodo_start_z
                z_end = el.z_end + machine.fodo_start_z
                checkpoints.append((get_element_name(el, z_start), z_end))
    else:
        for idx, el in enumerate(machine.injection_elements):
            checkpoints.append((f"{type(el).__name__}_{idx}", el.z_end))
        for idx, el in enumerate(machine.periodic_elements):
            checkpoints.append((f"{type(el).__name__}_P{idx}", el.z_end))
            
    checkpoints = sorted(checkpoints, key=lambda x: x[1])
    snapshots = {}
    
    # Initial snapshot
    p_init = gamma * M_PBAR * np.sqrt(np.sum(V**2, axis=1)) / C_LIGHT
    snapshots["Target"] = {
        "x": R[:, 0].copy(), "y": R[:, 1].copy(), "z": R[:, 2].copy(),
        "vx": V[:, 0].copy(), "vy": V[:, 1].copy(), "vz": V[:, 2].copy(),
        "px": (gamma * M_PBAR * V[:, 0] / C_LIGHT).copy(),
        "py": (gamma * M_PBAR * V[:, 1] / C_LIGHT).copy(),
        "pz": (gamma * M_PBAR * V[:, 2] / C_LIGHT).copy(),
        "p_total": p_init.copy(),
        "alive": alive_mask.copy()
    }
    
    dt = 50e-12
    required_steps = int(170.0 * 1e-9 / dt)
    
    R_prev, V_prev, gamma_prev = R.copy(), V.copy(), gamma.copy()
    alive_mask_prev = alive_mask.copy()
    
    for step in range(required_steps):
        if not np.any(alive_mask):
            break
            
        v_mag_sq = np.clip(np.sum(V[alive_mask]**2, axis=1), 0, (0.999 * C_LIGHT)**2)
        gamma[alive_mask] = 1.0 / np.sqrt(1.0 - v_mag_sq / C_LIGHT**2)
        
        R_prev[alive_mask] = R[alive_mask]
        V_prev[alive_mask] = V[alive_mask]
        gamma_prev[alive_mask] = gamma[alive_mask]
        alive_mask_prev = alive_mask.copy()
        
        R, V = relativistic_boris_step(R, V, gamma, dt, alive_mask, machine, charges)
        
        _check_boundaries_three_zone(
            R, alive_mask, machine, config_dict.get("R_PIPE", 0.10),
            passed_aperture_mask, death_causes,
            annihilation_queue=None, headless=True, charges=charges
        )
        
        died_this_step = alive_mask_prev & (~alive_mask)
        if np.any(died_this_step):
            for idx in np.where(died_this_step)[0]:
                death_locations[idx] = R[idx].copy()
                death_elements[idx] = get_element_at_z(R[idx, 2], machine)
                
        for cp_name, cp_z in checkpoints:
            if cp_name == "Target": continue
            crossed = (R_prev[:, 2] < cp_z) & (R[:, 2] >= cp_z) & alive_mask_prev
            if np.any(crossed):
                if cp_name not in snapshots:
                    snapshots[cp_name] = {
                        "x": np.full(N, np.nan, dtype=np.float32), "y": np.full(N, np.nan, dtype=np.float32),
                        "z": np.full(N, np.nan, dtype=np.float32),
                        "vx": np.full(N, np.nan, dtype=np.float32), "vy": np.full(N, np.nan, dtype=np.float32),
                        "vz": np.full(N, np.nan, dtype=np.float32),
                        "px": np.full(N, np.nan, dtype=np.float32), "py": np.full(N, np.nan, dtype=np.float32),
                        "pz": np.full(N, np.nan, dtype=np.float32), "p_total": np.full(N, np.nan, dtype=np.float32),
                        "alive": np.zeros(N, dtype=bool)
                    }
                idx_c = np.where(crossed)[0]
                z_p, z_c = R_prev[idx_c, 2], R[idx_c, 2]
                frac = (cp_z - z_p) / np.where((z_c - z_p) == 0.0, 1e-12, z_c - z_p)
                
                snapshots[cp_name]["x"][idx_c] = R_prev[idx_c, 0] + frac * (R[idx_c, 0] - R_prev[idx_c, 0])
                snapshots[cp_name]["y"][idx_c] = R_prev[idx_c, 1] + frac * (R[idx_c, 1] - R_prev[idx_c, 1])
                snapshots[cp_name]["z"][idx_c] = cp_z
                snapshots[cp_name]["vx"][idx_c], snapshots[cp_name]["vy"][idx_c], snapshots[cp_name]["vz"][idx_c] = V[idx_c, 0], V[idx_c, 1], V[idx_c, 2]
                
                g_cp = gamma[idx_c]
                snapshots[cp_name]["px"][idx_c] = g_cp * M_PBAR * V[idx_c, 0] / C_LIGHT
                snapshots[cp_name]["py"][idx_c] = g_cp * M_PBAR * V[idx_c, 1] / C_LIGHT
                snapshots[cp_name]["pz"][idx_c] = g_cp * M_PBAR * V[idx_c, 2] / C_LIGHT
                snapshots[cp_name]["p_total"][idx_c] = g_cp * M_PBAR * np.sqrt(np.sum(V[idx_c]**2, axis=1)) / C_LIGHT
                snapshots[cp_name]["alive"][idx_c] = True

    return R, V, alive_mask, snapshots, death_elements, checkpoints

def generate_beam_diagnostics(R_init, V_init, gamma_init, charges, machine, config_dict, output_run_dir):
    """
    Main orchestrator for single-pass extended diagnostics.
    """
    setup_plot_style()
    N_init = R_init.shape[0]
    
    logger.info("Running diagnostic particle tracking...")
    R_final, V_final, alive_mask, snapshots, death_elements, checkpoints = run_diagnostic_tracking(
        R_init, V_init, gamma_init, charges, machine, config_dict
    )
    
    # ── Folder Setup ────────────────────────────────────────────────────────
    diag_dir = os.path.join(output_run_dir, "diagnostics")
    ps_x_dir = os.path.join(diag_dir, "phase_space_horizontal")
    ps_y_dir = os.path.join(diag_dir, "phase_space_vertical")
    
    for d in [diag_dir, ps_x_dir, ps_y_dir]:
        os.makedirs(d, exist_ok=True)

    # ── Data Extraction ─────────────────────────────────────────────────────
    summary_data = []
    z_coords, names = [], []
    
    mean_x_arr, sig_x_arr, mean_y_arr, sig_y_arr = [], [], [], []
    mean_xp_arr, sig_xp_arr, mean_yp_arr, sig_yp_arr = [], [], [], []
    eps_x_arr, beta_x_arr, alpha_x_arr, gamma_x_arr = [], [], [], []
    eps_y_arr, beta_y_arr, alpha_y_arr, gamma_y_arr = [], [], [], []
    
    survival_arr, losses_per_element = [], []
    prev_alive = N_init
    
    r_pipe = config_dict.get("config", {}).get("R_PIPE", 0.10) if "config" in config_dict else config_dict.get("R_PIPE", 0.10)

    for idx, (cp_name, cp_z) in enumerate(checkpoints):
        if cp_name not in snapshots:
            continue
            
        snap = snapshots[cp_name]
        mask = snap["alive"]
        n_alive = int(np.sum(mask))
        
        survival_arr.append((n_alive / N_init) * 100.0 if N_init > 0 else 0)
        losses_per_element.append(prev_alive - n_alive)
        prev_alive = n_alive
        
        z_coords.append(cp_z)
        names.append(cp_name)
        
        # Handle depleted beams gracefully
        if n_alive < 2:
            summary_data.append({
                "element": cp_name, "z": cp_z, "N_particles": n_alive,
                **{k: 0.0 for k in ["mean_x", "sigma_x", "mean_y", "sigma_y", 
                                    "mean_x'", "sigma_x'", "mean_y'", "sigma_y'",
                                    "epsilon_x", "epsilon_y", "beta_x", "beta_y",
                                    "alpha_x", "alpha_y", "gamma_x", "gamma_y"]},
                "transmission_fraction": (n_alive / N_init) if N_init > 0 else 0
            })
            for lst in [mean_x_arr, sig_x_arr, mean_y_arr, sig_y_arr, 
                        mean_xp_arr, sig_xp_arr, mean_yp_arr, sig_yp_arr,
                        eps_x_arr, beta_x_arr, alpha_x_arr, gamma_x_arr,
                        eps_y_arr, beta_y_arr, alpha_y_arr, gamma_y_arr]:
                lst.append(0.0)
            continue
            
        x, y = snap["x"][mask], snap["y"][mask]
        pz_safe = np.where(snap["pz"][mask] == 0, 1e-12, snap["pz"][mask])
        xp, yp = snap["px"][mask] / pz_safe, snap["py"][mask] / pz_safe

        mx, sx = np.mean(x), np.std(x)
        my, sy = np.mean(y), np.std(y)
        mxp, sxp = np.mean(xp), np.std(xp)
        myp, syp = np.mean(yp), np.std(yp)

        # Twiss X
        cov_x = np.cov(x, xp)
        eps_x = np.sqrt(np.maximum(0.0, cov_x[0,0]*cov_x[1,1] - cov_x[0,1]**2))
        bx = cov_x[0,0] / eps_x if eps_x > 0 else 0.0
        ax_t = -cov_x[0,1] / eps_x if eps_x > 0 else 0.0
        gx = cov_x[1,1] / eps_x if eps_x > 0 else 0.0

        # Twiss Y
        cov_y = np.cov(y, yp)
        eps_y = np.sqrt(np.maximum(0.0, cov_y[0,0]*cov_y[1,1] - cov_y[0,1]**2))
        by = cov_y[0,0] / eps_y if eps_y > 0 else 0.0
        ay_t = -cov_y[0,1] / eps_y if eps_y > 0 else 0.0
        gy = cov_y[1,1] / eps_y if eps_y > 0 else 0.0

        mean_x_arr.append(mx); sig_x_arr.append(sx)
        mean_y_arr.append(my); sig_y_arr.append(sy)
        mean_xp_arr.append(mxp); sig_xp_arr.append(sxp)
        mean_yp_arr.append(myp); sig_yp_arr.append(syp)
        eps_x_arr.append(eps_x); beta_x_arr.append(bx); alpha_x_arr.append(ax_t); gamma_x_arr.append(gx)
        eps_y_arr.append(eps_y); beta_y_arr.append(by); alpha_y_arr.append(ay_t); gamma_y_arr.append(gy)

        summary_data.append({
            "element": cp_name, "z": cp_z, "N_particles": n_alive,
            "mean_x": mx, "sigma_x": sx, "mean_y": my, "sigma_y": sy,
            "mean_x'": mxp, "sigma_x'": sxp, "mean_y'": myp, "sigma_y'": syp,
            "epsilon_x": eps_x, "epsilon_y": eps_y, 
            "beta_x": bx, "beta_y": by, "alpha_x": ax_t, "alpha_y": ay_t,
            "gamma_x": gx, "gamma_y": gy,
            "transmission_fraction": n_alive / N_init
        })

        # ── Per-Element Phase Space Plots ──
        for plane, pos, ang, p_dir, unit in [("Horizontal", x, xp, ps_x_dir, "X"), ("Vertical", y, yp, ps_y_dir, "Y")]:
            fig, ax = plt.subplots(figsize=(6, 5))
            if n_alive > 1000:
                hb = ax.hexbin(pos, ang, gridsize=40, cmap='inferno', norm=LogNorm(), mincnt=1)
                fig.colorbar(hb, ax=ax, label='Counts')
            else:
                ax.scatter(pos, ang, s=4, alpha=0.6, color='black')
            ax.set_title(f"{cp_name} - {plane} Phase Space")
            ax.set_xlabel(f"{unit} [m]")
            ax.set_ylabel(f"{unit}' [rad]")
            
            safe_name = cp_name.replace(" ", "_").lower()
            file_path = os.path.join(p_dir, f"{safe_name}.png")
            plt.savefig(file_path)
            
            # Save global phase space copy for final element
            if idx == len(checkpoints) - 1:
                global_path = os.path.join(diag_dir, f"phase_space_{plane.lower()}.png")
                shutil.copy(file_path, global_path)
                
            plt.close(fig)

    # ── Export CSV ──
    df = pd.DataFrame(summary_data)
    df.to_csv(os.path.join(diag_dir, "beam_summary.csv"), index=False)

    z_arr = np.array(z_coords)
    mx_arr, sx_arr = np.array(mean_x_arr), np.array(sig_x_arr)
    my_arr, sy_arr = np.array(mean_y_arr), np.array(sig_y_arr)

    # ── Global Diagnostic Plots ──
    logger.info("Generating global diagnostic plots...")
    
    # 1. RMS Size Evolution
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(z_arr, sx_arr, marker='o', label='Horizontal $\sigma_x$', color='blue')
    ax.plot(z_arr, sy_arr, marker='s', label='Vertical $\sigma_y$', color='red')
    ax.set_title("RMS Beam Size Evolution")
    ax.set_xlabel("Z [m]")
    ax.set_ylabel("RMS Size [m]")
    ax.legend()
    plt.savefig(os.path.join(diag_dir, "rms_size.png"))
    plt.close(fig)

    # 2. Emittance Evolution
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(z_arr, np.array(eps_x_arr)*1e6, marker='o', label='$\epsilon_x$', color='blue')
    ax.plot(z_arr, np.array(eps_y_arr)*1e6, marker='s', label='$\epsilon_y$', color='red')
    ax.set_title("Geometric RMS Emittance Evolution")
    ax.set_xlabel("Z [m]")
    ax.set_ylabel("Emittance [mm-mrad]")
    ax.legend()
    plt.savefig(os.path.join(diag_dir, "emittance.png"))
    plt.close(fig)

    # 3. Centroid Evolution
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(z_arr, mx_arr, marker='o', label='Mean X', color='blue')
    ax.plot(z_arr, my_arr, marker='s', label='Mean Y', color='red')
    ax.axhline(0.0, color='black', linestyle='--')
    ax.set_title("Beam Orbit Centroid")
    ax.set_xlabel("Z [m]")
    ax.set_ylabel("Position [m]")
    ax.legend()
    plt.savefig(os.path.join(diag_dir, "centroid.png"))
    plt.close(fig)

    # 4. Twiss Parameter Evolutions
    def plot_twiss(z, p_x, p_y, title, filename):
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(z, p_x, label=f'{title} X', marker='o', color='blue')
        ax.plot(z, p_y, label=f'{title} Y', marker='s', color='red')
        ax.set_title(f"Twiss {title} Evolution")
        ax.set_xlabel("Z [m]")
        ax.set_ylabel(title)
        ax.legend()
        plt.savefig(os.path.join(diag_dir, filename))
        plt.close(fig)

    plot_twiss(z_arr, beta_x_arr, beta_y_arr, "Beta", "twiss_beta.png")
    plot_twiss(z_arr, alpha_x_arr, alpha_y_arr, "Alpha", "twiss_alpha.png")
    plot_twiss(z_arr, gamma_x_arr, gamma_y_arr, "Gamma", "twiss_gamma.png")

    # 5. Transmission
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(z_arr, survival_arr, marker='o', color='green', linewidth=2)
    ax.set_title("Beam Transmission")
    ax.set_xlabel("Z [m]")
    ax.set_ylabel("Survival [%]")
    ax.set_ylim(0, 105)
    plt.savefig(os.path.join(diag_dir, "transmission.png"))
    plt.close(fig)

    # 6. Loss Map (Bar Chart)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(names, losses_per_element, color='crimson', edgecolor='black')
    ax.set_title("Particle Losses per Element")
    ax.set_ylabel("Number of Particles Lost")
    plt.xticks(rotation=45, ha='right')
    plt.savefig(os.path.join(diag_dir, "loss_map.png"))
    plt.close(fig)

    # 7. Envelope Evolution
    def plot_envelope(z, mean, sig, plane, filename):
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(z, mean, color='black', label='Centroid', linewidth=2)
        ax.fill_between(z, mean - sig, mean + sig, color='blue', alpha=0.4, label='±1σ')
        ax.fill_between(z, mean - 2*sig, mean + 2*sig, color='blue', alpha=0.2, label='±2σ')
        ax.fill_between(z, mean - 3*sig, mean + 3*sig, color='blue', alpha=0.1, label='±3σ')
        ax.axhline(r_pipe, color='red', linestyle='--', label=f'Aperture ({r_pipe*1000:.0f} mm)')
        ax.axhline(-r_pipe, color='red', linestyle='--')
        ax.set_title(f"{plane} Beam Envelope")
        ax.set_xlabel("Z [m]")
        ax.set_ylabel(f"Position [m]")
        ax.legend()
        plt.savefig(os.path.join(diag_dir, filename))
        plt.close(fig)

    plot_envelope(z_arr, mx_arr, sx_arr, "Horizontal (X)", "envelope_x.png")
    plot_envelope(z_arr, my_arr, sy_arr, "Vertical (Y)", "envelope_y.png")

    # 8. Aperture Clearance (Simplified Centroid vs Envelope)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(z_arr, mx_arr, linewidth=2, label="Beam Center (X)", color="blue")
    ax.fill_between(z_arr, mx_arr - 3*sx_arr, mx_arr + 3*sx_arr, alpha=0.3, label="±3σ Envelope", color="blue")
    ax.axhline(r_pipe, color='red', linestyle='--', label=f'Aperture ({r_pipe*1000:.0f} mm)')
    ax.axhline(-r_pipe, color='red', linestyle='--')
    ax.set_title("Beam Center Relative to Aperture Clearance")
    ax.set_xlabel("Z [m]")
    ax.set_ylabel("X Position [m]")
    ax.legend()
    plt.savefig(os.path.join(diag_dir, "aperture.png"))
    plt.close(fig)

    # 9. Divergence Diagnostics
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(z_arr, sig_xp_arr, marker='o', label="$\sigma_{x'}$", color='blue')
    ax.plot(z_arr, sig_yp_arr, marker='s', label="$\sigma_{y'}$", color='red')
    ax.set_title("RMS Angular Divergence Evolution")
    ax.set_xlabel("Z [m]")
    ax.set_ylabel("RMS Divergence [rad]")
    ax.legend()
    plt.savefig(os.path.join(diag_dir, "divergence.png"))
    plt.close(fig)

    # ── Final Global Copy ──
    output_dir_global = os.path.abspath("output/diagnostics")
    if os.path.exists(output_dir_global):
        shutil.rmtree(output_dir_global)
    shutil.copytree(diag_dir, output_dir_global, dirs_exist_ok=True)
    logger.info(f"Diagnostics complete. Clean folder structure available at: {output_dir_global}")