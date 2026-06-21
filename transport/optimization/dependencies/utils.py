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

def generate_report(run_dir, history, raw_data, best_params, train_survival=None, val_survival=None, pbar_proton_stats=None):
    # 1. Update JSON config
    injection = raw_data.get("lattice", {}).get("injection_elements", [])
    
    # Horn is first param
    horn_updated = False
    quad_count = 0
    for el in injection:
        if el.get("type") == "MagneticHorn" and not horn_updated:
            el["I"] = float(best_params[0])
            horn_updated = True
        elif el.get("type") == "Quadrupole":
            if quad_count < len(best_params) - 1:
                el["K"] = float(best_params[quad_count + 1])
            quad_count += 1
            if quad_count == len(best_params) - 1:
                break
                
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
    
    # 3. Plot K vs Survival Rate
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    for i in range(len(best_params)):
        if f"k{i+1}" in history:
            ax1.plot(history[f"k{i+1}"], label=f"K{i+1}")
    ax2.plot(history["survival"], label="Survival Rate", color="black", linestyle="--")
    
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("K Values")
    ax2.set_ylabel("Survival Rate")
    fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.9))
    plt.title("Parameter Evolution and Survival Rate")
    plt.savefig(os.path.join(run_dir, "survival_rate_vs_k.png"))
    plt.close()
    
    # 4. Write summary markdown
    summary_path = os.path.join(run_dir, "summary.md")
    with open(summary_path, "w") as f:
        f.write("# Optimization Run Summary\n\n")
        f.write(f"**Best Horn Current:** {best_params[0]:.2f} A\n")
        for i, val in enumerate(best_params[1:]):
            f.write(f"**Best K{i+1}:** {val:.4f}\n")
        f.write(f"**Final Cost:** {history['cost'][-1]:.4f}\n")
        if train_survival is not None and val_survival is not None:
            f.write(f"**Training Survival Rate:** {train_survival:.2%}\n")
            f.write(f"**Validation Survival Rate:** {val_survival:.2%}\n\n")
        else:
            f.write(f"**Final Survival Rate:** {history['survival'][-1]:.2%}\n\n")
        
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

def main_plot():
    import sys
    os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.path.append(project_root)
    
    from transport.dependencies.lattice import Lattice
    from transport.dependencies.data_io import extract_cern_ad_seeds, get_latest_run_file
    from transport.dependencies.boris_solver import run_physics_loop
    
    config_path = os.path.abspath(os.path.join(project_root, "transport/config.json"))
    machine, config_dict = Lattice.load_from_json(config_path)
    
    hdf5_path = get_latest_run_file(outputs_dir_name="runs")
    print(f"Loading seeds from {hdf5_path}...")
    R, V, gamma, _ = extract_cern_ad_seeds(hdf5_path)
    
    print("Running a fast headless physics evaluation to determine particle fate...")
    R_final, V_final, alive_mask, _ = run_physics_loop(
        R.copy(), V.copy(), gamma.copy(), None, None, None, None, config_dict, machine, headless=True
    )
    
    runs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs")
    run_dir = setup_run_directory(runs_dir)
    
    print(f"Plotting initial phase space to {run_dir}...")
    plot_initial_phase_space(run_dir, R, V, alive_mask)
    print("Done!")

if __name__ == "__main__":
    main_plot()
