import os
import json
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np

def plot_initial_phase_space(run_dir, R_init, V_init, alive_mask):
    """
    Plots the initial phase space of the particle beam.
    """
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
    
    dead_mask = ~alive_mask
    
    # Subplot 1: X Phase Space
    ax1.scatter(R_init[dead_mask, 0], V_init[dead_mask, 0], color='red', alpha=0.5, label='Dead', s=10)
    ax1.scatter(R_init[alive_mask, 0], V_init[alive_mask, 0], color='green', alpha=1.0, label='Alive', s=10)
    ax1.set_title("X Phase Space")
    ax1.set_xlabel("X Position [m]")
    ax1.set_ylabel("X Velocity [m/s]")
    ax1.grid(True)
    ax1.legend()
    
    # Subplot 2: Y Phase Space
    ax2.scatter(R_init[dead_mask, 1], V_init[dead_mask, 1], color='red', alpha=0.5, label='Dead', s=10)
    ax2.scatter(R_init[alive_mask, 1], V_init[alive_mask, 1], color='green', alpha=1.0, label='Alive', s=10)
    ax2.set_title("Y Phase Space")
    ax2.set_xlabel("Y Position [m]")
    ax2.set_ylabel("Y Velocity [m/s]")
    ax2.grid(True)
    ax2.legend()
    
    # Subplot 3: Z Phase Space
    ax3.scatter(R_init[dead_mask, 2], V_init[dead_mask, 2], color='red', alpha=0.5, label='Dead', s=10)
    ax3.scatter(R_init[alive_mask, 2], V_init[alive_mask, 2], color='green', alpha=1.0, label='Alive', s=10)
    ax3.set_title("Z Phase Space")
    ax3.set_xlabel("Z Position [m]")
    ax3.set_ylabel("Z Velocity [m/s]")
    ax3.grid(True)
    ax3.legend()
    
    plt.suptitle("Initial Phase Space")
    plt.tight_layout()
    plt.savefig(os.path.join(run_dir, "initial_phase_space.png"))
    plt.close()

def setup_run_directory(base_dir):
    os.makedirs(base_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(base_dir, f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir

def generate_report_filter(run_dir, history, raw_data, best_params, train_survival=None, val_survival=None, pbar_proton_stats=None):
    # 1. Update JSON config
    if "dipole_chamber" in raw_data:
        raw_data["dipole_chamber"]["field_strength"] = float(best_params[1])
        raw_data["dipole_chamber"]["acceptance_aperture_radius"] = float(best_params[2])
        
    config_path = os.path.join(run_dir, "optimized_config.json")
    with open(config_path, "w") as f:
        json.dump(raw_data, f, indent=4)
        
    # 2. Plot Loss vs Iteration
    plt.figure()
    plt.plot(history["cost"], marker="o")
    plt.title("Cost vs Iteration")
    plt.xlabel("Iteration")
    plt.ylabel("Cost")
    plt.yscale("symlog")
    plt.grid(True)
    plt.savefig(os.path.join(run_dir, "loss_vs_iteration.png"))
    plt.close()
    
    # 3. Plot parameters and survival rates
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    iterations = np.arange(len(history["cost"]))
    
    # Plot horn current in kA on ax1
    if "horn_I" in history:
        ax1.plot(iterations, np.array(history["horn_I"]) / 1000.0, label="Horn Current (kA)", color="blue")
    # Plot dipole field By on ax1
    if "dipole_By" in history:
        ax1.plot(iterations, history["dipole_By"], label="Dipole Field (T)", color="cyan")
    # Plot aperture radius on ax1
    if "aperture_r" in history:
        ax1.plot(iterations, history["aperture_r"], label="Aperture Radius (m)", color="magenta")
        
    # Plot pbar survival and proton survival on ax2
    if "survival_pbar" in history:
        ax2.plot(iterations, history["survival_pbar"], label="pbar Survival Rate", color="green", linestyle="--")
    if "survival_proton" in history:
        ax2.plot(iterations, history["survival_proton"], label="proton Survival Rate", color="red", linestyle=":")
        
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Parameters (Horn in kA, B in T, r in m)")
    ax2.set_ylabel("Survival Rate")
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    
    plt.title("Parameter Evolution and Survival Rates")
    plt.grid(True)
    plt.savefig(os.path.join(run_dir, "survival_rate_vs_params.png"))
    plt.close()
    
    # 4. Write summary markdown
    summary_path = os.path.join(run_dir, "summary.md")
    with open(summary_path, "w") as f:
        f.write("# Dipole Filter Optimization Run Summary\n\n")
        f.write(f"**Best Horn Current:** {best_params[0]:.2f} A\n")
        f.write(f"**Best Dipole B field (By):** {best_params[1]:.4f} T\n")
        f.write(f"**Best Aperture Radius:** {best_params[2]:.4f} m\n\n")
        f.write(f"**Final Cost:** {history['cost'][-1]:.4f}\n\n")
        
        if train_survival is not None and val_survival is not None:
            f.write(f"**Training pbar Survival Rate:** {train_survival[0]:.2%}\n")
            f.write(f"**Training proton Survival Rate:** {train_survival[1]:.2%}\n")
            f.write(f"**Validation pbar Survival Rate:** {val_survival[0]:.2%}\n")
            f.write(f"**Validation proton Survival Rate:** {val_survival[1]:.2%}\n\n")
        else:
            if "survival_pbar" in history:
                f.write(f"**Final pbar Survival Rate:** {history['survival_pbar'][-1]:.2%}\n")
            if "survival_proton" in history:
                f.write(f"**Final proton Survival Rate:** {history['survival_proton'][-1]:.2%}\n\n")
        
        if pbar_proton_stats is not None:
            f.write(f"initial antiproton count: {pbar_proton_stats.get('initial_pbar', 0)}\n")
            f.write(f"antiprotons survived: {pbar_proton_stats.get('survived_pbar', 0)}\n")
            f.write(f"antiprotons annihilated: {pbar_proton_stats.get('annihilated_pbar', 0)}\n")
            f.write(f"initial proton count: {pbar_proton_stats.get('initial_proton', 0)}\n")
            f.write(f"positive particles survived: {pbar_proton_stats.get('survived_proton', 0)}\n")
            f.write(f"positive particles annihilated: {pbar_proton_stats.get('annihilated_proton', 0)}\n\n")
            
        f.write("## Updates\n")
        f.write("The `optimized_config.json` file is ready to replace the main config.\n")
        
    print(f"[Optimization] Run saved to {run_dir}")
