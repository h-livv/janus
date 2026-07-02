import numpy as np
from transport.validation.base import ValidationCase
from transport.lattice.lattice import SimpleLattice, Dipole

from transport.io.data_io import get_latest_run_file, extract_cern_ad_seeds

# Constants
C_LIGHT   = 299792458.0
E_CHARGE  = 1.602176634e-19
M_P_KG    = 1.67262192369e-27
M_P_MEV   = 938.2720813

class DipoleValidation(ValidationCase):
    def __init__(self):
        super().__init__("DipoleValidation", dt=1e-10, max_steps=500, max_steps_conv=150)
        # Initialize placeholders, updated dynamically in initial_particles
        self.p_gevc = 3.5752
        self.P_mevc = self.p_gevc * 1000.0
        self.E_total = np.sqrt(self.P_mevc**2 + M_P_MEV**2)
        self.gamma = self.E_total / M_P_MEV
        self.v_mag = (self.P_mevc * C_LIGHT) / self.E_total
        self.B_rho = (self.P_mevc * 1e6) / C_LIGHT
        self.aperture_radius = None

    def get_custom_error_data(self, diagnostics, analytical):
        t = diagnostics["time"]
        pos = diagnostics["position"][:, 0]
        alive = diagnostics["alive"][:, 0]
        
        mask = (pos[:, 2] > self.z_start) & (pos[:, 2] <= self.z_start + 5.0) & alive
        x_track = pos[mask, 0]
        z_track = pos[mask, 2]
        
        curves = []
        if len(x_track) > 3:
            R_sim = self.fit_circle(x_track, z_track)
            A = np.column_stack((2*x_track, 2*z_track, np.ones_like(x_track)))
            Y = x_track**2 + z_track**2
            w, _, _, _ = np.linalg.lstsq(A, Y, rcond=None)
            Xc, Zc = w[0], w[1]
            radial_dist = np.sqrt((pos[:, 0] - Xc)**2 + (pos[:, 2] - Zc)**2)
            r_err = np.abs(radial_dist - R_sim)
            curves.append({"x": t[mask] * 1e9, "y": r_err[mask], "label": "Radial Deviation from Circle Fit", "color": "purple"})
            
        return {
            "title": "Dipole Orbit Circular Fit Deviations",
            "ylabel": "Radial Deviation (m)",
            "xlabel": "Time (ns)",
            "curves": curves
        }

    def build_lattice(self):
        # We define a long dipole for Test 2 (cyclotron radius) 
        # and a shorter dipole for Test 6 (bend angle).
        # We can dynamically change the dipole parameters or return a standard one.
        # Let's use a 5.0m dipole with By = 1.0 T.
        # This will bend the antiproton by a measurable angle.
        return SimpleLattice(
            [Dipole(length=5.0, By=1.0, aperture_radius=self.aperture_radius)],
            z_start=self.z_start,
        )

    def initial_particles(self):
        latest_file = get_latest_run_file(outputs_dir_name="runs", target_filename="simulation.root")
        R, V, gamma, charges = extract_cern_ad_seeds([latest_file])
        
        # Select first antiproton (or first particle if no antiprotons)
        mask = (charges == -1)
        if not np.any(mask):
            mask = (charges == 1)
        if not np.any(mask):
            raise ValueError("No charged particles found in simulation.root")
            
        idx = np.where(mask)[0][0]
        
        R_init = R[idx:idx+1].astype(np.float64)
        V_init = V[idx:idx+1].astype(np.float64)
        gamma_init = gamma[idx:idx+1].astype(np.float64)
        charges_init = charges[idx:idx+1]
        
        self.z_start = R_init[0, 2]
        self.v_mag = np.linalg.norm(V_init[0])
        
        # Recompute gamma perfectly consistently with V_init to avoid precision plateaus
        self.gamma = 1.0 / np.sqrt(1.0 - (self.v_mag / C_LIGHT)**2)
        
        v_perp = np.sqrt(V_init[0, 0]**2 + V_init[0, 2]**2)
        self.B_rho = self.gamma * M_P_KG * v_perp / E_CHARGE
        
        self.theta_entry = np.arctan2(V_init[0, 0], V_init[0, 2])
        self.charge = charges_init[0]
        
        return R_init, V_init, gamma_init, charges_init

    def analytical_position(self, t, R_init, V_init, charges):
        omega_c = (charges[0] * E_CHARGE * 1.0) / (self.gamma * M_P_KG)
        x0, y0, z0 = R_init[0]
        vx0, vy0, vz0 = V_init[0]
        
        if abs(omega_c) < 1e-12:
            return R_init + V_init * t
            
        x_t = x0 + (vx0 / omega_c) * np.sin(omega_c * t) - (vz0 / omega_c) * (1.0 - np.cos(omega_c * t))
        y_t = y0 + vy0 * t
        z_t = z0 + (vz0 / omega_c) * np.sin(omega_c * t) + (vx0 / omega_c) * (1.0 - np.cos(omega_c * t))
        
        return np.array([[x_t, y_t, z_t]])

    def analytical_solution(self, diagnostics):
        # Cyclotron radius: R = B_rho / B
        # For our 1.0 T field: R = B_rho
        R_analytical = self.B_rho / 1.0
        
        # Bending angle: theta = asin(sin(theta_entry) - q * B * L / p_perp) - theta_entry
        By = 1.0
        L = 5.0
        arg = np.sin(self.theta_entry) - (self.charge * By * L / self.B_rho)
        theta_exit = np.arcsin(arg)
        theta_analytical = theta_exit - self.theta_entry
        
        return {
            "cyclotron_radius": R_analytical,
            "bend_angle": theta_analytical
        }

    def fit_circle(self, x, z):
        """
        Algebraic least-squares fit for a circle (x-Xc)^2 + (z-Zc)^2 = R^2
        """
        # Formulate as: A * w = Y
        # where w = [Xc, Zc, C], C = R^2 - Xc^2 - Zc^2
        # A = [2*x, 2*z, 1], Y = x^2 + z^2
        A = np.column_stack((2*x, 2*z, np.ones_like(x)))
        Y = x**2 + z**2
        w, _, _, _ = np.linalg.lstsq(A, Y, rcond=None)
        
        Xc, Zc, C = w[0], w[1], w[2]
        R = np.sqrt(C + Xc**2 + Zc**2)
        return R

    def evaluate(self, diagnostics, analytical):
        # 1. Extract trajectory
        pos = diagnostics["position"][:, 0] # (n_steps, 3)
        mom = diagnostics["momentum"][:, 0] # (n_steps, 3)
        alive = diagnostics["alive"][:, 0]
        
        # Filter only when particle was inside the dipole (z_start <= z <= z_start + 5.0) and alive
        z_start = self.z_start
        z_end = self.z_start + 5.0
        mask = (pos[:, 2] > z_start) & (pos[:, 2] <= z_end) & alive
        x_track = pos[mask, 0]
        z_track = pos[mask, 2]
        
        # 2. Fit cyclotron radius
        if len(x_track) > 3:
            R_sim = self.fit_circle(x_track, z_track)
        else:
            R_sim = 0.0
            
        R_err = abs(R_sim - analytical["cyclotron_radius"]) / analytical["cyclotron_radius"]
        
        # 3. Deflection angle at exit
        # Find the last step where the particle was alive (right before it exited the dipole/pipe)
        alive_idxs = np.where(alive)[0]
        if len(alive_idxs) > 0:
            last_alive_idx = alive_idxs[-1]
            px_exit = mom[last_alive_idx, 0]
            pz_exit = mom[last_alive_idx, 2]
            theta_exit = np.arctan2(px_exit, pz_exit)
            
            px_entry = mom[0, 0]
            pz_entry = mom[0, 2]
            theta_entry = np.arctan2(px_entry, pz_entry)
            
            theta_sim = theta_exit - theta_entry
        else:
            theta_sim = 0.0
            
        # Bend angle error comparing magnitude of simulated bend vs analytical bend
        theta_err = abs(abs(theta_sim) - abs(analytical["bend_angle"])) / abs(analytical["bend_angle"])
        
        return {
            "cyclotron_radius_error": R_err,
            "bend_angle_error": theta_err
        }

    def get_tolerances(self):
        return {
            "cyclotron_radius_error": 1e-4,
            "bend_angle_error": 1e-2
        }
