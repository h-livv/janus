import os
import numpy as np
import matplotlib.pyplot as plt

def generate_conservation_and_error_plots(case, diagnostics, analytical, run_outputs_dir):
    """
    Generates unified conservation and error plots for any validation case.
    Saves plots into: run_outputs_dir/case_name/
    """
    case_name = case.name.lower().replace("validation", "")
    element_outputs_dir = os.path.join(run_outputs_dir, case_name)
    os.makedirs(element_outputs_dir, exist_ok=True)

    t = diagnostics["time"]
    mom = diagnostics["momentum"][:, 0] # assume 1st particle
    gamma = diagnostics["gamma"][:, 0]

    # --- 1. Conservation Plot ---
    mom_mag = np.linalg.norm(mom, axis=1)
    p_rel_drift = np.abs(mom_mag - mom_mag[0]) / (mom_mag[0] if mom_mag[0] != 0 else 1e-12)
    g_rel_drift = np.abs(gamma - gamma[0]) / (gamma[0] if gamma[0] != 0 else 1e-12)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t * 1e9, p_rel_drift + 1e-18, label="Momentum Drift", color="blue", alpha=0.8)
    ax.plot(t * 1e9, g_rel_drift + 1e-18, label="Energy Drift (Gamma)", color="red", linestyle="--", alpha=0.8)
    ax.set_yscale("log")
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Relative Drift")
    ax.set_title(f"Conservation of Momentum & Energy ({case.name})")
    ax.legend()
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(element_outputs_dir, "conservation.png"), dpi=150)
    plt.close()

    # --- 2. Custom Error Plot ---
    error_data = case.get_custom_error_data(diagnostics, analytical)
    if error_data:
        fig, ax = plt.subplots(figsize=(8, 5))
        curves = error_data.get("curves", [])
        if curves:
            for curve in curves:
                ax.plot(curve["x"], curve["y"], label=curve.get("label"), color=curve.get("color"))
        else:
            ax.text(0.5, 0.5, "No tracking data available for error plotting", ha='center', va='center')
            
        ax.set_xlabel(error_data.get("xlabel", "Time (ns)"))
        ax.set_ylabel(error_data.get("ylabel", "Error"))
        ax.set_title(error_data.get("title", "Error vs Time"))
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(element_outputs_dir, "error.png"), dpi=150)
        plt.close()


def plot_convergence(case, dts, errors, run_outputs_dir):
    """
    Generates an error vs timestep plot for any validation case convergence run.
    """
    case_name = case.name.lower().replace("validation", "")
    element_outputs_dir = os.path.join(run_outputs_dir, case_name)
    os.makedirs(element_outputs_dir, exist_ok=True)

    # Now we plot log(error) vs log(dt) for all 4 timesteps
    log_dts = np.log10(dts)
    log_errors = np.log10(errors)
    
    # Calculate convergence slope via linear fit using the best 4 refined points (smallest timesteps)
    slope, intercept = np.polyfit(log_dts[-4:], log_errors[-4:], 1)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(log_dts, log_errors, marker="o", color="darkorange", linewidth=2, 
            label=f"Boris Step Error (Slope = {slope:.2f})")
    ax.set_xlabel("log(Timestep dt)")
    ax.set_ylabel("log(Error)")
    ax.set_title(f"Timestep Convergence: {case.name}")
    
    # Annotate with a text box
    textstr = f"Convergence Slope: {slope:.2f}"
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)
    
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(os.path.join(element_outputs_dir, "timestep_convergence.png"), dpi=150)
    plt.close()
