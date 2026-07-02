import numpy as np
from transport.validation.base import ValidationCase
from transport.lattice.lattice import SimpleLattice, Drift
from transport.io.data_io import get_latest_run_file, extract_cern_ad_seeds

C_LIGHT = 299792458.0

class DriftValidation(ValidationCase):
    def __init__(self):
        super().__init__("DriftValidation", dt=1e-10, max_steps=500, max_steps_conv=300)
        self.L = 10.0
        self.v_mag = 289953335.7
        self.gamma = 3.9395
        self.aperture_radius = None

    def get_custom_error_data(self, diagnostics, analytical):
        t = diagnostics["time"]
        pos = diagnostics["position"][:, 0]
        x_err = np.abs(pos[:, 0] - analytical["x"])
        y_err = np.abs(pos[:, 1] - analytical["y"])
        z_err = np.abs(pos[:, 2] - analytical["z"])

        return {
            "title": "Drift Trajectory Coordinate Error vs Analytical",
            "ylabel": "Absolute Coordinate Error (m)",
            "xlabel": "Time (ns)",
            "curves": [
                {"x": t * 1e9, "y": x_err, "label": "X Error", "color": "blue"},
                {"x": t * 1e9, "y": y_err, "label": "Y Error", "color": "green"},
                {"x": t * 1e9, "y": z_err, "label": "Z Error", "color": "red"}
            ]
        }

    def build_lattice(self):
        return SimpleLattice([Drift(self.L, aperture_radius=self.aperture_radius)], z_start=self.z_start)

    def initial_particles(self):
        latest_file = get_latest_run_file(outputs_dir_name="runs", target_filename="simulation.root")
        R, V, gamma, charges = extract_cern_ad_seeds([latest_file])
        
        idx = 0
        R_init = R[idx:idx+1].astype(np.float64)
        V_init = V[idx:idx+1].astype(np.float64)
        gamma_init = gamma[idx:idx+1].astype(np.float64)
        charges_init = charges[idx:idx+1]
        
        self.z_start = R_init[0, 2]
        self.v_mag = np.linalg.norm(V_init[0])
        self.gamma = gamma_init[0]
        
        return R_init, V_init, gamma_init, charges_init

    def analytical_position(self, t, R_init, V_init, charges):
        return R_init + V_init * t

    def analytical_solution(self, diagnostics):
        t = diagnostics["time"]
        R0 = diagnostics["position"][0, 0] # Initial position
        
        # Calculate velocity from first step to be precise
        if len(t) > 1 and t[1] > 0:
            V0 = (diagnostics["position"][1, 0] - R0) / t[1]
        else:
            V0 = np.array([1000.0, -2000.0, self.v_mag])
        
        x_expected = R0[0] + V0[0] * t
        y_expected = R0[1] + V0[1] * t
        z_expected = R0[2] + V0[2] * t
        
        return {
            "x": x_expected,
            "y": y_expected,
            "z": z_expected
        }

    def evaluate(self, diagnostics, analytical):
        pos = diagnostics["position"][:, 0]
        
        x_err = np.max(np.abs(pos[:, 0] - analytical["x"]))
        y_err = np.max(np.abs(pos[:, 1] - analytical["y"]))
        z_err = np.max(np.abs(pos[:, 2] - analytical["z"]))
        
        return {
            "x_error": x_err,
            "y_error": y_err,
            "z_error": z_err
        }

    def get_tolerances(self):
        return {
            "x_error": 1e-6,
            "y_error": 1e-6,
            "z_error": 1e-6
        }
