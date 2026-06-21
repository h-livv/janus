import os
import logging
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import gaussian_kde

# Force headless backend
matplotlib.use('Agg')

# Set up local logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Diagnostics")

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

def _validate_data(data):
    """
    Validates and converts input data into a standardized numpy array.
    Expects data to have at least 6 columns: [x, y, z, px, py, pz].
    """
    if isinstance(data, pd.DataFrame):
        data = data.values
    if not isinstance(data, np.ndarray):
        raise ValueError("Data must be a NumPy array or pandas DataFrame.")
    if data.shape[0] == 0:
        raise ValueError("Dataset is empty.")
    if data.shape[1] < 6:
        raise ValueError(f"Dataset must contain at least 6 columns [x,y,z,px,py,pz]. Found {data.shape[1]}")
    return data

def plot_beam_envelope(data, output_dir, pipe_radius=None):
    """
    1. Beam Envelope Plot (The FODO Tunnel View)
    Visualizes beam size evolution (1 sigma and 3 sigma) along the Z axis.
    """
    try:
        data = _validate_data(data)
        x, y, z = data[:, 0], data[:, 1], data[:, 2]

        # Since data might just be the final state or initial state,
        # a true envelope requires tracking data over Z.
        # If this is a snapshot, we bin by Z to find the local envelope.
        z_bins = np.linspace(np.min(z), np.max(z), min(100, len(z)))
        z_centers = (z_bins[:-1] + z_bins[1:]) / 2
        
        x_rms, y_rms = [], []
        x_3sig, y_3sig = [], []
        
        for i in range(len(z_bins) - 1):
            mask = (z >= z_bins[i]) & (z < z_bins[i+1])
            if np.any(mask):
                x_rms.append(np.std(x[mask]))
                y_rms.append(np.std(y[mask]))
                x_3sig.append(3 * np.std(x[mask]))
                y_3sig.append(3 * np.std(y[mask]))
            else:
                x_rms.append(0)
                y_rms.append(0)
                x_3sig.append(0)
                y_3sig.append(0)
                
        x_rms, y_rms = np.array(x_rms), np.array(y_rms)
        x_3sig, y_3sig = np.array(x_3sig), np.array(y_3sig)

        setup_plot_style()
        fig, ax = plt.subplots(figsize=(10, 6))

        ax.fill_between(z_centers, x_3sig, -x_3sig, color='blue', alpha=0.1, label='X 3$\sigma$')
        ax.fill_between(z_centers, x_rms, -x_rms, color='blue', alpha=0.3, label='X 1$\sigma$')
        
        ax.plot(z_centers, y_3sig, color='red', linestyle='--', alpha=0.5, label='Y 3$\sigma$')
        ax.plot(z_centers, y_rms, color='red', linestyle='-', alpha=0.8, label='Y 1$\sigma$')
        ax.plot(z_centers, -y_3sig, color='red', linestyle='--', alpha=0.5)
        ax.plot(z_centers, -y_rms, color='red', linestyle='-', alpha=0.8)

        if pipe_radius is not None:
            ax.axhline(pipe_radius, color='black', linestyle=':', linewidth=2, label='Pipe Wall')
            ax.axhline(-pipe_radius, color='black', linestyle=':', linewidth=2)

        ax.set_title("Beam Envelope")
        ax.set_xlabel("Longitudinal Distance Z [m]")
        ax.set_ylabel("Transverse Beam Size [m]")
        ax.legend(loc='upper right')
        
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, "beam_envelope.png"))
        plt.close(fig)
        logger.info("Successfully generated beam_envelope.png")

    except Exception as e:
        logger.warning(f"Failed to generate beam envelope plot: {e}")


def plot_transverse_phase_space(data, output_dir):
    """
    2. Transverse Phase Space
    Plots X vs X' and Y vs Y' using logarithmic hexbins.
    """
    try:
        data = _validate_data(data)
        x, y = data[:, 0], data[:, 1]
        px, py, pz = data[:, 3], data[:, 4], data[:, 5]
        
        # Avoid division by zero
        pz_safe = np.where(pz == 0, 1e-12, pz)
        x_prime = px / pz_safe
        y_prime = py / pz_safe

        setup_plot_style()
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # Horizontal Phase Space
        hb1 = ax1.hexbin(x, x_prime, gridsize=50, cmap='inferno', bins='log', mincnt=1)
        ax1.set_title("Horizontal Phase Space")
        ax1.set_xlabel("X [m]")
        ax1.set_ylabel("X' [rad]")
        fig.colorbar(hb1, ax=ax1, label='log10(N)')

        # Vertical Phase Space
        hb2 = ax2.hexbin(y, y_prime, gridsize=50, cmap='inferno', bins='log', mincnt=1)
        ax2.set_title("Vertical Phase Space")
        ax2.set_xlabel("Y [m]")
        ax2.set_ylabel("Y' [rad]")
        fig.colorbar(hb2, ax=ax2, label='log10(N)')

        plt.tight_layout()
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, "transverse_phase_space.png"))
        plt.close(fig)
        logger.info("Successfully generated transverse_phase_space.png")

    except Exception as e:
        logger.warning(f"Failed to generate transverse phase space plot: {e}")


def plot_dispersion_profile(data, output_dir):
    """
    3. Longitudinal Dispersion Profile
    Plots X vs Pz using logarithmic hexbins to reveal momentum-dependent separation.
    """
    try:
        data = _validate_data(data)
        x, pz = data[:, 0], data[:, 5]

        setup_plot_style()
        fig, ax = plt.subplots(figsize=(10, 6))

        hb = ax.hexbin(pz, x, gridsize=50, cmap='viridis', bins='log', mincnt=1)
        ax.set_title("Longitudinal Dispersion Profile")
        ax.set_xlabel("Longitudinal Momentum Pz [MeV/c]")
        ax.set_ylabel("Horizontal Position X [m]")
        fig.colorbar(hb, ax=ax, label='log10(N)')

        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, "dispersion_profile.png"))
        plt.close(fig)
        logger.info("Successfully generated dispersion_profile.png")

    except Exception as e:
        logger.warning(f"Failed to generate dispersion profile plot: {e}")


def plot_loss_map(data, output_dir):
    """
    4. Loss Map (The Graveyard)
    Plots a 1D histogram of Z loss locations and a 2D cross-section of X vs Y impact points.
    Assumes `data` passed here ONLY contains lost particles!
    """
    try:
        data = _validate_data(data)
        x, y, z = data[:, 0], data[:, 1], data[:, 2]

        setup_plot_style()
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # Longitudinal Loss Histogram
        ax1.hist(z, bins=50, color='crimson', alpha=0.7, edgecolor='black')
        ax1.set_title("Longitudinal Loss Map")
        ax1.set_xlabel("Z Impact Location [m]")
        ax1.set_ylabel("Number of Lost Particles")

        # Impact Cross Section
        ax2.scatter(x, y, s=5, color='crimson', alpha=0.5)
        ax2.set_title("Impact Cross Section")
        ax2.set_xlabel("X Impact [m]")
        ax2.set_ylabel("Y Impact [m]")
        ax2.axis('equal')

        plt.tight_layout()
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, "loss_map.png"))
        plt.close(fig)
        logger.info("Successfully generated loss_map.png")

    except Exception as e:
        logger.warning(f"Failed to generate loss map plot: {e}")


def plot_momentum_distribution(data, output_dir):
    """
    5. Momentum Distribution (Peak Identification)
    Plots a histogram of P and identifies the dominant momentum peak using KDE.
    """
    try:
        data = _validate_data(data)
        px, py, pz = data[:, 3], data[:, 4], data[:, 5]
        
        # Calculate total momentum
        p_total = np.sqrt(px**2 + py**2 + pz**2)

        setup_plot_style()
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot Histogram
        counts, bins, _ = ax.hist(p_total, bins=100, density=True, color='teal', alpha=0.6, label='Data Histogram')
        
        # KDE for Peak Identification
        if len(p_total) > 1:
            kde = gaussian_kde(p_total)
            p_grid = np.linspace(np.min(p_total), np.max(p_total), 1000)
            kde_curve = kde(p_grid)
            
            # Find peak
            peak_idx = np.argmax(kde_curve)
            peak_p = p_grid[peak_idx]
            
            ax.plot(p_grid, kde_curve, color='navy', linewidth=2, label='KDE Fit')
            ax.axvline(peak_p, color='red', linestyle='--', linewidth=2, label=f'Peak: {peak_p:.2f} MeV/c')
            
            # Annotation
            ax.annotate(f"Peak Momentum:\n{peak_p:.2f} MeV/c", 
                        xy=(peak_p, kde_curve[peak_idx]), 
                        xytext=(peak_p + np.ptp(p_grid)*0.1, kde_curve[peak_idx]),
                        arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=6),
                        fontsize=12, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))

        ax.set_title("Momentum Distribution")
        ax.set_xlabel("Total Momentum P [MeV/c]")
        ax.set_ylabel("Density")
        ax.legend(loc='upper right')

        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, "momentum_distribution.png"))
        plt.close(fig)
        logger.info("Successfully generated momentum_distribution.png")

    except Exception as e:
        logger.warning(f"Failed to generate momentum distribution plot: {e}")


def generate_all_diagnostics(data, lost_data, output_dir, pipe_radius=None):
    """
    Master function to generate all five accelerator diagnostics simultaneously.
    
    Args:
        data: 6D phase space array for ALL (or surviving) particles.
        lost_data: 6D phase space array for LOST particles only.
        output_dir: String path to the save directory.
        pipe_radius: Float representing the vacuum pipe radius (optional).
    """
    logger.info(f"Generating comprehensive diagnostic suite in {output_dir}")
    
    plot_beam_envelope(data, output_dir, pipe_radius=pipe_radius)
    plot_transverse_phase_space(data, output_dir)
    plot_dispersion_profile(data, output_dir)
    
    if lost_data is not None and len(lost_data) > 0:
        plot_loss_map(lost_data, output_dir)
    else:
        logger.info("Skipping loss map: no lost particles provided.")
        
    plot_momentum_distribution(data, output_dir)
    logger.info("Diagnostic suite generation complete.")
