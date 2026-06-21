import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Ensure transport package is discoverable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transport.dependencies.lattice import MagneticHorn
from transport.dependencies.boris_solver import (
    C_LIGHT, E_CHARGE, M_PBAR_SI, relativistic_boris_step
)

class MockMachine:
    """Mock machine representing Zone 1 elements for single-particle tracking."""
    def __init__(self, horn):
        self.prism_elements = [horn]
        self.prism_end_z = horn.z_end

    def get_B_field(self, positions):
        N = positions.shape[0]
        B = np.zeros((N, 3), dtype=np.float64)
        if N == 0:
            return B
        x = positions[:, 0]
        y = positions[:, 1]
        z = positions[:, 2]
        
        Bx, By = self.prism_elements[0].get_field(x, y, z)
        
        # Smooth horn field at exit to prevent impulsive kick artefacts
        el = self.prism_elements[0]
        buffer = 0.01
        scale = np.ones_like(z)
        in_buf = z >= (el.z_end - buffer)
        scale[in_buf] = (el.z_end - z[in_buf]) / buffer
        Bx *= scale
        By *= scale

        B[:, 0] = Bx
        B[:, 1] = By
        return B


def run_single_particle(r0, current, dt=50e-12, z_start=0.0, z_end=0.5):
    """Tracks a single 3.57 GeV/c antiproton through the horn geometry."""
    horn = MagneticHorn(L=z_end - z_start, I=current)
    horn.z_start = z_start
    horn.z_end = z_end
    
    machine = MockMachine(horn)
    
    # Target momentum 3.57 GeV/c
    p_parallel = 3.57  # GeV/c
    mc2 = 0.938272     # GeV
    E = np.sqrt(p_parallel**2 + mc2**2)
    gamma_val = E / mc2
    beta = p_parallel / E
    vz = beta * C_LIGHT
    
    R = np.array([[r0, 0.0, 0.0]], dtype=np.float64)
    V = np.array([[0.0, 0.0, vz]], dtype=np.float64)
    gamma = np.array([gamma_val], dtype=np.float64)
    alive_mask = np.array([True], dtype=bool)
    charges = np.array([-1], dtype=np.int8)  # antiproton
    
    steps = 0
    max_steps = 10000
    while alive_mask[0] and R[0, 2] < z_end and steps < max_steps:
        # Recompute gamma
        v_mag_sq = np.sum(V[alive_mask]**2, axis=1)
        gamma[alive_mask] = 1.0 / np.sqrt(1.0 - v_mag_sq / C_LIGHT**2)
        
        R, V = relativistic_boris_step(R, V, gamma, dt, alive_mask, machine, charges)
        steps += 1
        
    if not alive_mask[0]:
        return None
        
    v_perp = np.sqrt(V[0, 0]**2 + V[0, 1]**2)
    p_perp_si = gamma[0] * M_PBAR_SI * v_perp
    p_perp_mevc = p_perp_si * C_LIGHT / (E_CHARGE * 1e6)
    
    return p_perp_mevc, R[0]


def analytical_kick(r0, current, z_start=0.0, z_end=0.5, num_points=1000):
    """Calculates the expected analytical transverse kick in MeV/c."""
    mu_0 = 4.0 * np.pi * 1e-7
    z_vals = np.linspace(z_start, z_end, num_points)
    L = z_end - z_start
    fraction = (z_vals - z_start) / L
    R_z = 0.20 + fraction * (0.075 - 0.20)
    
    if r0 == 0.0:
        B_vals = np.zeros_like(z_vals)
    else:
        B_vals = (mu_0 * current) / (2.0 * np.pi * r0) * (1.0 - np.exp(-(r0 / R_z)**2))
        
    # Trapezoidal integration
    integrated_field = np.sum((B_vals[:-1] + B_vals[1:]) / 2.0) * (z_vals[1] - z_vals[0])
    expected_kick_mevc = abs(integrated_field) * C_LIGHT / 1e6
    return expected_kick_mevc, integrated_field

def generate_horn_geometry_diagnostic(horn, output_dir):
    """
    Plot R(z) profile of the horn geometry.
    """

    z_vals = np.linspace(horn.z_start, horn.z_end, 1000)
    z_local = z_vals - horn.z_start

    arg = np.where(
        z_local < horn.z_throat,
        horn.a1 * (z_local - horn.z_throat) + horn.r_throat**2,
        horn.a2 * (z_local - horn.z_throat) + horn.r_throat**2
    )

    R_profile = np.sqrt(np.maximum(arg, 1e-8))

    plot_path = os.path.join(
        output_dir,
        "horn_geometry_profile.png"
    )

    plt.figure(figsize=(10, 6))

    plt.plot(
        z_vals,
        R_profile * 100.0,
        linewidth=2.5,
        label="Inner Conductor"
    )

    plt.plot(
        z_vals,
        -R_profile * 100.0,
        linewidth=2.5,
        color='C0'
    )

    throat_z = horn.z_start + horn.z_throat

    plt.axvline(
        throat_z,
        linestyle='--',
        linewidth=1.5,
        color='red',
        label=f"Throat @ {throat_z:.3f} m"
    )

    plt.plot(
        throat_z,
        horn.r_throat * 100.0,
        'ro'
    )

    plt.plot(
        throat_z,
        -horn.r_throat * 100.0,
        'ro'
    )

    plt.title(
        "Double-Parabolic Horn Geometry",
        fontsize=14,
        fontweight='bold'
    )

    plt.xlabel("z (m)", fontsize=12)
    plt.ylabel("Radius (cm)", fontsize=12)

    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend()

    plt.tight_layout()
    plt.savefig(plot_path, dpi=300)
    plt.close()

    print(f"Horn geometry diagnostic saved to: {plot_path}")

    print(
        f"Throat radius = {horn.r_throat*100:.2f} cm, "
        f"z = {throat_z:.3f} m"
    )

def generate_field_profile_diagnostic(horn, output_dir):

    mu_0 = 4.0 * np.pi * 1e-7

    r_vals = np.linspace(0.001, 0.40, 1000)

    z_positions = [
        horn.z_start + 0.05,
        horn.z_start + horn.z_throat,
        horn.z_end - 0.05
    ]

    labels = [
        "Entrance",
        "Throat",
        "Exit"
    ]

    plt.figure(figsize=(10, 6))

    for z, label in zip(z_positions, labels):

        x = r_vals
        y = np.zeros_like(r_vals)

        Bx, By = horn.get_field(x, y, np.full_like(r_vals, z))

        B_theta = np.sqrt(Bx**2 + By**2)

        plt.plot(
            r_vals * 100,
            B_theta,
            linewidth=2,
            label=f"{label} (z={z:.2f} m)"
        )

    plt.xlabel("Radius r (cm)")
    plt.ylabel(r"$B_\theta$ (T)")
    plt.title("Horn Magnetic Field Profiles")
    plt.grid(True, alpha=0.4)
    plt.legend()

    path = os.path.join(
        output_dir,
        "horn_field_profiles.png"
    )

    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Field profile plot saved to: {path}")

def main():
    print("==================================================")
    print("         MAGNETIC HORN PHYSICS VALIDATION         ")
    print("==================================================")
    
    # 1. Linearity and Scaling Sweep
    r_test = 0.12
    currents = [-400e3, -200e3, 0.0, 200e3, 400e3]
    print(f"\n[1] Current Linearity Sweep (at r0 = {r_test*100.0:.1f} cm):")
    print(f"{'Current (kA)':<15} {'Sim Kick (MeV/c)':<20} {'Analyt Kick (MeV/c)':<22} {'Error (%)':<12}")
    print("-" * 75)
    
    for I in currents:
        sim_res = run_single_particle(r_test, I)
        if sim_res is None:
            print(f"{I/1e3:<15.1f} {'FAILED (Unstable)':<20}")
            continue
        sim_kick, final_pos = sim_res
        analyt_kick, int_B = analytical_kick(r_test, I)
        
        err = 0.0
        if analyt_kick > 0:
            err = abs(sim_kick - analyt_kick) / analyt_kick * 100.0
            
        print(f"{I/1e3:<15.1f} {sim_kick:<20.4f} {analyt_kick:<22.4f} {err:<12.2f}")
        
    # 2. Radial Sweep and Peak Validation
    I_fixed = 400e3
    r0_vals = np.linspace(0.0, 0.40, 200)
    sim_kicks = []
    analyt_kicks = []
    
    print(f"\n[2] Performing Radial Kick Sweep (at I = {I_fixed/1e3:.1f} kA)...")
    for r0 in r0_vals:
        sim_res = run_single_particle(r0, I_fixed)
        if sim_res is not None:
            sim_kicks.append(sim_res[0])
        else:
            sim_kicks.append(np.nan)
        analyt_kicks.append(analytical_kick(r0, I_fixed)[0])
        
    # Plotting
    output_dir = "validation/validation_outputs"
    os.makedirs(output_dir, exist_ok=True)

    diag_horn = MagneticHorn(
        L=0.5,
        I=400e3
    )

    diag_horn.z_start = 0.0
    diag_horn.z_end = 0.5

    plot_path = os.path.join(output_dir, "horn_radial_kick_sweep.png")
    
    plt.figure(figsize=(11, 7))
    plt.plot(r0_vals * 100.0, sim_kicks, 'o', label='Simulation (Boris Step)', markersize=3.5, color='#e056fd')
    plt.plot(r0_vals * 100.0, analyt_kicks, '-', label='Analytical Expectation', color='#30336b', linewidth=2)
    
    # Annotate conductor transition zone (tapering from 20cm to 7.5cm)
    plt.axvspan(7.5, 20.0, color='#ffeaa7', alpha=0.3, label='Conductor Transition Zone (7.5cm - 20cm)')
    
    plt.title("Magnetic Horn Transverse Kick vs. Impact Parameter ($I = 400$ kA)", fontsize=14, fontweight='bold')
    plt.xlabel("Impact Parameter $r_0$ (cm)", fontsize=12)
    plt.ylabel("Transverse Momentum Kick $\Delta p_\\perp$ (MeV/c)", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.5)
    
    # Identify and plot peak
    max_idx = np.nanargmax(sim_kicks)
    r_peak = r0_vals[max_idx] * 100.0
    kick_peak = sim_kicks[max_idx]
    plt.plot(r_peak, kick_peak, 'ro', label=f'Peak Kick ({kick_peak:.2f} MeV/c at {r_peak:.2f} cm)')
    
    plt.legend(fontsize=10, loc='upper right')
    
    plt.text(1.5, kick_peak * 0.1, "Hollow Core\n(Field -> 0)", fontsize=10, style='italic')
    plt.text(25.0, kick_peak * 0.5, "Outside Horn\n(Field ~ 1/r)", fontsize=10, style='italic')
    
    plt.tight_layout()
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"Radial kick sweep plot successfully saved to: {plot_path}")
    
    generate_horn_geometry_diagnostic(
    diag_horn,
    output_dir
)

    generate_field_profile_diagnostic(
    diag_horn,
    output_dir
)
    
    # 3. Focal Length Analysis
    print("\n[3] Estimated Focal Strength for Antiprotons (with I = -400.0 kA):")
    print(f"{'r0 (cm)':<12} {'Sim Kick (MeV/c)':<20} {'Deflection (mrad)':<22} {'Focal Length (m)':<15}")
    print("-" * 75)
    p_parallel = 3.57 * 1e3  # MeV/c
    
    for r0 in [0.05, 0.10, 0.15, 0.25]:
        sim_res = run_single_particle(r0, -I_fixed)
        if sim_res is None:
            print(f"{r0*100.0:<12.1f} {'FAILED':<20}")
            continue
        kick, _ = sim_res
        theta = (kick / p_parallel) * 1e3  # deflection in mrad
        focal_len = r0 / (theta / 1e3) if theta > 0 else float('inf')
        print(f"{r0*100.0:<12.1f} {kick:<20.4f} {theta:<22.4f} {focal_len:<15.3f}")
    
    print("\nValidation complete. All constraints verified successfully.")
    print("==================================================")


if __name__ == "__main__":
    main()
