import os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('Agg')

# Physical Constants
M_PBAR = 938.2720813  # MeV/c^2
C_LIGHT = 299792458.0 # m/s

def setup_plot_style():
    plt.style.use('seaborn-v0_8-whitegrid')
    matplotlib.rcParams.update({
        'font.size': 12, 'axes.labelsize': 14, 'axes.titlesize': 16,
        'figure.dpi': 300, 'savefig.dpi': 300, 'savefig.bbox': 'tight'
    })

def run_reference_particle_diagnostic(machine, config_dict, base_out_dir):
    """
    Injects a single ideal reference particle (x=0, y=0, x'=0, y'=0) at the 
    nominal design momentum and tracks it through the lattice to evaluate 
    absolute orbit drift and coordinate-system alignment.
    """
    from transport.dependencies.diagnostics_tracker import run_diagnostic_tracking, get_element_name
    
    print("\n[Reference Diagnostic] Initializing Ideal On-Axis Particle...")
    
    # 1. Determine Nominal Momentum
    p_gevc = config_dict.get("config", {}).get("reference_p_gevc", 3.5752)
    if p_gevc is None: 
        p_gevc = config_dict.get("reference_p_gevc", 3.5752)
        
    P_mevc = p_gevc * 1000.0
    E_total = np.sqrt(P_mevc**2 + M_PBAR**2)
    gamma = E_total / M_PBAR
    v_mag = (P_mevc * C_LIGHT) / E_total
    
    # 2. Initialize Single Ideal Particle
    R_init = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    V_init = np.array([[0.0, 0.0, v_mag]], dtype=np.float32)
    gamma_init = np.array([gamma], dtype=np.float32)
    charges = np.array([-1], dtype=np.int8)  # Antiproton
    
    # 3. Track using existing Boris engine
    print(f"[Reference Diagnostic] Tracking nominal {p_gevc:.4f} GeV/c particle...")
    _, _, _, snapshots, _, checkpoints = run_diagnostic_tracking(
        R_init, V_init, gamma_init, charges, machine, config_dict
    )
    
    # 4. Prepare Output Directory
    out_dir = os.path.join(base_out_dir, "reference_orbit_diagnostic")
    os.makedirs(out_dir, exist_ok=True)
    setup_plot_style()
    
    # 5. Extract Data
    data = []
    z_arr, x_arr, y_arr, xp_arr, yp_arr = [], [], [], [], []
    local_x_arr, dx_arr, dyp_arr = [], [], []
    
    prev_x, prev_y, prev_xp, prev_yp = 0.0, 0.0, 0.0, 0.0
    
    for idx, (cp_name, cp_z) in enumerate(checkpoints):
        if cp_name not in snapshots: continue
        snap = snapshots[cp_name]
        
        # Only 1 particle exists
        x = snap["x"][0]
        y = snap["y"][0]
        pz_safe = snap["pz"][0] if snap["pz"][0] != 0 else 1e-12
        xp = snap["px"][0] / pz_safe
        yp = snap["py"][0] / pz_safe
        p_tot = snap["p_total"][0]
        alive = snap["alive"][0]
        
        # Local Coordinates (Subtract continuous reference curve)
        x_ref, _ = machine.get_reference_trajectory(cp_z)
        local_x = x - x_ref
        
        # Incremental changes
        dx, dy = x - prev_x, y - prev_y
        dxp, dyp = xp - prev_xp, yp - prev_yp
        
        data.append({
            "element_idx": idx, "element_name": cp_name,
            "z": cp_z, "x": x, "y": y, "xp": xp, "yp": yp,
            "local_x": local_x, "dx": dx, "dy": dy, "dxp": dxp, "dyp": dyp,
            "momentum": p_tot, "alive": alive
        })
        
        z_arr.append(cp_z)
        x_arr.append(x); y_arr.append(y)
        xp_arr.append(xp); yp_arr.append(yp)
        local_x_arr.append(local_x)
        
        prev_x, prev_y, prev_xp, prev_yp = x, y, xp, yp

    # --- Save CSV ---
    df = pd.DataFrame(data)
    df.to_csv(os.path.join(out_dir, "reference_orbit.csv"), index=False)
    
    z_arr = np.array(z_arr)
    
    # --- Plot 1: Reference Orbit (Global) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(z_arr, x_arr, marker='o', label='Global X', linewidth=2)
    ax.plot(z_arr, y_arr, marker='s', label='Global Y', linewidth=2)
    ax.axhline(0.0, color='black', linestyle='--', linewidth=1.5)
    ax.set_title("Ideal Reference Orbit (Global Coordinates)")
    ax.set_xlabel("Cumulative Z [m]")
    ax.set_ylabel("Transverse Position [m]")
    ax.legend()
    plt.savefig(os.path.join(out_dir, "reference_orbit.png"))
    plt.close()
    
    # --- Plot 2: Reference Angles ---
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(z_arr, xp_arr, marker='o', label="X' (Horizontal)", color='blue')
    ax.plot(z_arr, yp_arr, marker='s', label="Y' (Vertical)", color='red')
    ax.axhline(0.0, color='black', linestyle='--', linewidth=1.5)
    ax.set_title("Ideal Reference Trajectory Angles")
    ax.set_xlabel("Cumulative Z [m]")
    ax.set_ylabel("Angle [rad]")
    ax.legend()
    plt.savefig(os.path.join(out_dir, "reference_angles.png"))
    plt.close()
    
    # --- Plot 3: Incremental Kicks ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    ax1.bar(df["element_name"], df["dxp"], color='blue', alpha=0.7)
    ax1.set_title("Incremental Angular Kicks (Δx') per Element")
    ax1.set_ylabel("Δx' [rad]")
    ax1.axhline(0.0, color='black', linewidth=1)
    
    ax2.bar(df["element_name"], df["dyp"], color='red', alpha=0.7)
    ax2.set_title("Incremental Angular Kicks (Δy') per Element")
    ax2.set_ylabel("Δy' [rad]")
    ax2.axhline(0.0, color='black', linewidth=1)
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "reference_kicks.png"))
    plt.close()
    
    # --- Plot 5: Global vs Local Coordinates ---
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(z_arr, x_arr, marker='o', label='Global Cartesian X', color='navy', linestyle='--')
    ax.plot(z_arr, local_x_arr, marker='s', label='Local Curvilinear X (Beam Frame)', color='mediumseagreen', linewidth=2)
    ax.axhline(0.0, color='black', linestyle='-', linewidth=1.5)
    ax.set_title("Coordinate Frame Comparison: Global vs Local")
    ax.set_xlabel("Cumulative Z [m]")
    ax.set_ylabel("Horizontal Position [m]")
    ax.legend()
    plt.savefig(os.path.join(out_dir, "global_vs_local.png"))
    plt.close()

    # --- Plot 4: Dipole Consistency Report ---
    report_path = os.path.join(out_dir, "dipole_consistency_report.txt")
    B_rho = P_mevc / (C_LIGHT * 1e-9)  # Magnetic rigidity [T-m]
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"DIPOLE CONSISTENCY REPORT\n")
        f.write(f"Nominal Momentum: {P_mevc:.2f} MeV/c\n")
        f.write(f"Magnetic Rigidity (B*rho): {B_rho:.4f} T-m\n")
        f.write("-" * 60 + "\n")
        
        for name in df["element_name"]:
            # Find the element in the machine
            el_obj = None
            for e in machine.prism_elements + machine.matching_elements + machine.fodo_elements:
                if type(e).__name__ != "Drift" and get_element_name(e, e.z_start if not hasattr(e, 'z_start_abs') else e.z_start_abs) == name:
                    el_obj = e
                    break
                    
            if el_obj and type(el_obj).__name__ in ["SelectorDipole", "Dipole"]:
                L = el_obj.L
                By = el_obj.By if type(el_obj).__name__ == "Dipole" else -el_obj.By # Handle negative polarity hardcode
                
                # Math expectation
                expected_bend = By * L / B_rho
                
                # Simulation reality
                row = df[df["element_name"] == name].iloc[0]
                actual_bend = row["dxp"]
                diff_pct = abs((actual_bend - expected_bend) / expected_bend) * 100 if expected_bend != 0 else 0
                
                f.write(f"Element: {name} ({type(el_obj).__name__})\n")
                f.write(f"  Field (By)    : {By:.4f} T\n")
                f.write(f"  Length (L)    : {L:.4f} m\n")
                f.write(f"  Expected Bend : {expected_bend:.6f} rad\n")
                f.write(f"  Actual Bend   : {actual_bend:.6f} rad\n")
                f.write(f"  Difference    : {diff_pct:.2f}%\n")
                f.write("-" * 60 + "\n")
                
    print(f"[Reference Diagnostic] Complete. Results saved to {out_dir}")