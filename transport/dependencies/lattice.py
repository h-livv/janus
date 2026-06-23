import numpy as np
import json
import sys


class GeometryError(Exception):
    pass


# ---------------------------------------------------------------------------
# Base Element
# ---------------------------------------------------------------------------

class Element:
    def __init__(self, L, aperture_radius=None, x_center=0.0):
        self.L = L

        self.z_start = 0.0
        self.z_end   = 0.0

        self.aperture_radius = aperture_radius

        self.x_center = x_center

    def get_field(self, x, y, z):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Generic / Legacy Elements
# ---------------------------------------------------------------------------

class Drift(Element):
    def __init__(self, L, aperture_radius=None):
        super().__init__(L, aperture_radius)
    
    def get_field(self, x, y, z):
        return np.zeros_like(x), np.zeros_like(x)


class Dipole(Element):
    def __init__(self, L, Bx, By, aperture_radius=None, x_center=0.0):
        super().__init__(L, aperture_radius, x_center)
        self.Bx = Bx
        self.By = By
        
    def get_field(self, x, y, z):
        # Invert to compensate for the integrator's positive cross-product convention
        return np.full_like(x, self.Bx), np.full_like(y, self.By)


class Quadrupole(Element):
    def __init__(self, L, K, B_rho, aperture_radius=None, x_center=0.0):
        super().__init__(L, aperture_radius, x_center)
        self.K = K
        self.g = K * B_rho  # gradient in T/m

    def get_field(self, x, y, z):
        x_local = x - self.x_center

        Bx = -self.g*y
        By = -self.g*x_local

        return Bx,By


class MagneticHorn(Element):
    def __init__(self, L, I, r_throat=0.03, z_throat=0.25, a1=-0.17, a2=0.17, aperture_radius=None):
        super().__init__(L, aperture_radius)
        self.I = I
        self.r_throat = r_throat
        self.z_throat = z_throat
        self.a1 = a1
        self.a2 = a2
        self.mu_0 = 4.0 * np.pi * 1e-7

    def get_field(self, x, y, z):
        # Local conductor radius tapering linearly along z
        z_clipped = np.clip(z, self.z_start, self.z_end)
        z_local = z_clipped - self.z_start
        
        R_z = np.where(
            z_local < self.z_throat,
            np.sqrt(
                self.a1 * (z_local - self.z_throat)
                + self.r_throat**2
            ),
            np.sqrt(
                self.a2 * (z_local - self.z_throat)
                + self.r_throat**2
            )
        )

        arg = np.where(
            z_local < self.z_throat,
            self.a1 * (z_local - self.z_throat) + self.r_throat**2,
            self.a2 * (z_local - self.z_throat) + self.r_throat**2
        )

        R_z = np.sqrt(np.maximum(arg, 1e-8))

        # Radial position
        r_sq = x**2 + y**2
        r = np.sqrt(r_sq)

        # Smooth exponential regularization to avoid singularity at r -> 0
        # B_theta = (mu_0 * I) / (2 * pi * r) * (1 - exp(-r^2 / R(z)^2))
        u = r_sq / R_z**2
        
        r_safe = np.where(r > 1e-5, r, 1.0)
        factor = np.where(
            r > 1e-5,
            (1.0 - np.exp(-u)) / r_safe,
            (r / R_z**2) * (1.0 - 0.5 * u)
        )
        
        B_theta = (self.mu_0 * self.I) / (2.0 * np.pi) * factor

        # Compute Cartesian components Bx and By
        Bx = np.where(r > 1e-5, -B_theta * (y / r_safe), 0.0)
        By = np.where(r > 1e-5, B_theta * (x / r_safe), 0.0)

        # Boundary: If outside Z-range, return exactly 0
        mask = (z < self.z_start) | (z > self.z_end)
        Bx[mask] = 0.0
        By[mask] = 0.0

        return Bx, By


# ---------------------------------------------------------------------------
# Zone 1 — Prism Elements
# ---------------------------------------------------------------------------

class SelectorDipole(Element):
    """
    Uniform vertical selector dipole spanning the main separation chamber.

    Field: By > 0 (positive vertical, pointing up).

    Lorentz force on particles moving primarily in +z with By > 0:
      F_x = q * v_z * B_y   (from v × B, selecting x-component)

    Consequences:
      - Antiprotons (q = -1): F_x < 0  →  deflect toward  -x  (left side)
      - Protons     (q = +1): F_x > 0  →  deflect toward  +x  (right side)
      - Neutrals    (q =  0): no force →  continue straight into dump

    The AcceptanceAperture is placed on the LEFT side (-x) to intercept
    the antiproton-deflected beam.
    """
    def __init__(self, L, By, aperture_radius=None, x_center=0.0):
        super().__init__(L, aperture_radius, x_center)
        self.By = By  # T, positive

    def get_field(self, x, y, z):
        # Return -self.By to align positive field parameter with -x deflection for antiprotons (q < 0)
        return np.zeros_like(x), np.full_like(y, -self.By)





class AcceptanceAperture:
    """
    Thin acceptance plane at the downstream face of the dipole chamber.

    Particles that cross z >= z_plane and are NOT within `radius` of
    (x_offset, 0) are killed by the physics solver.

    With By > 0 and q = -1, antiprotons deflect toward -x, so the
    aperture is placed at x_offset < 0 (left side of the beam dump).
    """
    def __init__(self, z_plane, radius, x_offset):
        self.z_plane  = z_plane   # m — absolute z of the aperture face
        self.radius   = radius    # m — acceptance radius
        self.x_offset = x_offset  # m — centre x of aperture (negative = left)


# ---------------------------------------------------------------------------
# Three-Zone Lattice
# ---------------------------------------------------------------------------

class Lattice:
    """
    Three-zone beamline:

      Zone 1 – Prism       (0 m → prism_end_z)
        MagneticHorn + SelectorDipole; BeamDump + AcceptanceAperture
        for boundary logic.

      Zone 2 – Matching    (matching_start_z → matching_end_z)
        4–6 independently tunable quadrupoles at absolute z positions.

      Zone 3 – Periodic FODO  (fodo_start_z → fodo_end_z)
        Conventional QF-Drift-QD-Drift cells, wrapped periodically.
    """

    def __init__(self,
                 prism_elements, matching_elements, fodo_elements,
                 prism_end_z, matching_start_z, matching_end_z,
                 fodo_start_z, fodo_end_z, fodo_cell_length,
                 aperture=None,
                 dipole_chamber_width=3.0, dipole_chamber_height=3.0,
                 matching_aperture_radius=0.15,
                 bend_angles=None):

        self.prism_elements    = prism_elements
        self.matching_elements = matching_elements
        self.fodo_elements     = fodo_elements

        self.prism_end_z         = prism_end_z
        self.matching_start_z    = matching_start_z
        self.matching_end_z      = matching_end_z
        self.fodo_start_z        = fodo_start_z
        self.fodo_end_z          = fodo_end_z
        
        self.bend_angles = bend_angles if bend_angles is not None else {}
        self.fodo_cell_length    = fodo_cell_length

        self.aperture = aperture  # AcceptanceAperture | None

        self.dipole_chamber_width    = dipole_chamber_width
        self.dipole_chamber_height   = dipole_chamber_height
        self.matching_aperture_radius = matching_aperture_radius

        self.total_L       = fodo_end_z
        self.is_three_zone = True
        self.is_acol       = True

        self.inj_L = fodo_end_z

        self.injection_elements = []
        for el in (self.prism_elements + self.matching_elements):
            if not isinstance(el, Drift):
                self.injection_elements.append(el)
        for el in self.fodo_elements:
            if not isinstance(el, Drift):
                self.injection_elements.append(el)

        # Assign absolute z coordinates to Prism elements sequentially
        z_cursor = 0.0
        for el in self.prism_elements:
            if el.L < 0:
                raise GeometryError("Negative element length encountered in Prism")
            el.z_start  = z_cursor
            z_cursor   += el.L
            el.z_end    = z_cursor

        # Matching element coordinates come from config (already absolute)
        # FODO element coordinates are relative to cell start (0-based)

    # ------------------------------------------------------------------
    # JSON factory
    # ------------------------------------------------------------------

    @classmethod
    def load_from_json(cls, filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)

        if "config" not in data:
            print("[Lattice] ERROR: 'config' key missing from JSON schema.")
            sys.exit(1)

        if "acol" not in data:
            print("[Lattice] ERROR: Missing required 'acol' key in schema. Only ACOL-inspired lattice is supported.")
            sys.exit(1)

        p_gevc  = data["config"].get("reference_p_gevc", 3.57)
        c_light = 299792458.0
        B_rho   = (p_gevc * 1e9) / c_light  # magnetic rigidity [T·m]

        print("\n--- LATTICE PHYSICS VARS ---")
        print("Momentum raw =", p_gevc * 1e9, "eV/c")
        print("p_gevc =", p_gevc, "GeV/c")
        print("B_rho =", B_rho, "T-m")
        print("----------------------------\n")

        acol = data["acol"]
        survey = acol["survey_coordinates"]
        quads_cfg = acol["quadrupoles"]
        dipoles_cfg = acol["dipoles"]
        septum_cfg = acol["septum"]
        aperture_r = acol.get("aperture_radius", 0.10)
        
        # Get realistic aperture values from config
        apertures_cfg = acol.get("apertures", {})
        dipole_radius = apertures_cfg.get("dipole_radius", 0.044)
        quad_radius = apertures_cfg.get("quadrupole_radius", 0.095)
        septum_radius = apertures_cfg.get("septum_radius", 0.05)
        horn_radius = apertures_cfg.get("horn_radius", 0.20)
        pipe_radius = apertures_cfg.get("pipe_radius", 0.10)
        
        # Target is at z=0, Horn is from z=0 to z=0.5
        horn_L = 0.50
        horn_I = data["config"].get("horn_current", -242934.66740974569)
        if "horn_current" in acol:
            horn_I = acol["horn_current"]
        horn = MagneticHorn(horn_L, horn_I, aperture_radius=horn_radius)
        
        # Zone 1 (Prism): Target to end of BHZ0058
        # Elements: Horn, QFO0050, QDE0055, BHZ0058, plus drifts computed from survey.
        prism_elements = [horn]
        
        # QFO0050 starts at s = 0.0 (z = 0.5)
        qfo0050_cfg = quads_cfg["QFO0050"]
        qfo0050 = Quadrupole(qfo0050_cfg["length"], qfo0050_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        prism_elements.append(qfo0050)
        
        # QDE0055 starts at s = 5.0 - compute drift from survey
        drift_0050_0055 = survey["QDE0055"] - survey["QFO0050"] - qfo0050_cfg["length"]
        prism_elements.append(Drift(drift_0050_0055))
        qde0055_cfg = quads_cfg["QDE0055"]
        qde0055 = Quadrupole(qde0055_cfg["length"], qde0055_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        prism_elements.append(qde0055)
        
        # BHZ0058 starts at s = 8.0 - compute drift from survey
        drift_0055_0058 = survey["BHZ0058"] - survey["QDE0055"] - qde0055_cfg["length"]
        prism_elements.append(Drift(drift_0055_0058))
        bhz0058_cfg = dipoles_cfg["BHZ0058"]
        theta_rad_0058 = bhz0058_cfg["bend_angle_deg"] * np.pi / 180.0
        By_0058 = (theta_rad_0058 * B_rho) / bhz0058_cfg["length"]
        selector = SelectorDipole(bhz0058_cfg["length"], abs(By_0058), aperture_radius=dipole_radius)
        prism_elements.append(selector)
        
        prism_end_z = 0.5 + survey["BHZ0058"] + bhz0058_cfg["length"]
        
        # Zone 2 (Matching): QFO0060 to QDE0085 - compute all drifts from survey
        matching_elements = []
        
        # QFO0060 starts at s = 10.0 - compute drift from survey
        drift_0058_0060 = survey["QFO0060"] - survey["BHZ0058"] - bhz0058_cfg["length"]
        matching_elements.append(Drift(drift_0058_0060))
        qfo0060_cfg = quads_cfg["QFO0060"]
        qfo0060 = Quadrupole(qfo0060_cfg["length"], qfo0060_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        matching_elements.append(qfo0060)
        
        # QDE0065 starts at s = 15.0 - compute drift from survey
        drift_0060_0065 = survey["QDE0065"] - survey["QFO0060"] - qfo0060_cfg["length"]
        matching_elements.append(Drift(drift_0060_0065))
        qde0065_cfg = quads_cfg["QDE0065"]
        qde0065 = Quadrupole(qde0065_cfg["length"], qde0065_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        matching_elements.append(qde0065)
        
        # QFO0070 starts at s = 20.0 - compute drift from survey
        drift_0065_0070 = survey["QFO0070"] - survey["QDE0065"] - qde0065_cfg["length"]
        matching_elements.append(Drift(drift_0065_0070))
        qfo0070_cfg = quads_cfg["QFO0070"]
        qfo0070 = Quadrupole(qfo0070_cfg["length"], qfo0070_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        matching_elements.append(qfo0070)
        
        # QDE0075 starts at s = 25.0 - compute drift from survey
        drift_0070_0075 = survey["QDE0075"] - survey["QFO0070"] - qfo0070_cfg["length"]
        matching_elements.append(Drift(drift_0070_0075))
        qde0075_cfg = quads_cfg["QDE0075"]
        qde0075 = Quadrupole(qde0075_cfg["length"], qde0075_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        matching_elements.append(qde0075)
        
        # QFO0080 starts at s = 30.0 - compute drift from survey
        drift_0075_0080 = survey["QFO0080"] - survey["QDE0075"] - qde0075_cfg["length"]
        matching_elements.append(Drift(drift_0075_0080))
        qfo0080_cfg = quads_cfg["QFO0080"]
        qfo0080 = Quadrupole(qfo0080_cfg["length"], qfo0080_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        matching_elements.append(qfo0080)
        
        # QDE0085 starts at s = 35.0 - compute drift from survey
        drift_0080_0085 = survey["QDE0085"] - survey["QFO0080"] - qfo0080_cfg["length"]
        matching_elements.append(Drift(drift_0080_0085))
        qde0085_cfg = quads_cfg["QDE0085"]
        qde0085 = Quadrupole(qde0085_cfg["length"], qde0085_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        matching_elements.append(qde0085)
        
        # Drift to start of Zone 3 (BHZ0088 starts at s = 38.0) - compute from survey
        drift_0085_0088 = survey["BHZ0088"] - survey["QDE0085"] - qde0085_cfg["length"]
        matching_elements.append(Drift(drift_0085_0088))
        
        matching_start_z = 10.4513
        matching_end_z   = 0.5 + survey["BHZ0088"]
        
        # Assign absolute coordinates to matching elements
        z_cursor = matching_start_z
        for el in matching_elements:
            el.z_start = z_cursor
            z_cursor += el.L
            el.z_end = z_cursor
            
        # Zone 3 (FODO cell elements relative to cell start):
        bhz0088_cfg = dipoles_cfg["BHZ0088"]
        theta_rad_0088 = bhz0088_cfg["bend_angle_deg"] * np.pi / 180.0
        By_0088 = (theta_rad_0088 * B_rho) / bhz0088_cfg["length"]
        bhz0088 = Dipole(bhz0088_cfg["length"], 0.0, By_0088, aperture_radius=dipole_radius)
        bhz0088.z_start = 0.0
        bhz0088.z_end   = bhz0088_cfg["length"]
        
        # Compute drift from survey
        drift_88_90 = survey["QFO0090"] - survey["BHZ0088"] - bhz0088_cfg["length"]
        drift_88_90_el = Drift(drift_88_90)
        drift_88_90_el.z_start = bhz0088.z_end
        drift_88_90_el.z_end   = bhz0088.z_end + drift_88_90
        
        qfo0090_cfg = quads_cfg["QFO0090"]
        qfo0090 = Quadrupole(qfo0090_cfg["length"], qfo0090_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        qfo0090.z_start = drift_88_90_el.z_end
        qfo0090.z_end   = qfo0090.z_start + qfo0090_cfg["length"]
        
        # Compute drift from survey
        drift_90_95 = survey["QDS0095"] - survey["QFO0090"] - qfo0090_cfg["length"]
        drift_90_95_el = Drift(drift_90_95)
        drift_90_95_el.z_start = qfo0090.z_end
        drift_90_95_el.z_end   = qfo0090.z_end + drift_90_95
        
        qds0095_cfg = quads_cfg["QDS0095"]
        qds0095 = Quadrupole(qds0095_cfg["length"], qds0095_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
        qds0095.z_start = drift_90_95_el.z_end
        qds0095.z_end   = qds0095.z_start + qds0095_cfg["length"]
        
        # Add QFS50 quadrupole (missing matching quad)
        if "QFS50" in quads_cfg:
            qfs50_cfg = quads_cfg["QFS50"]
            drift_95_50 = survey["QFS50"] - survey["QDS0095"] - qds0095_cfg["length"]
            drift_95_50_el = Drift(drift_95_50)
            drift_95_50_el.z_start = qds0095.z_end
            drift_95_50_el.z_end   = qds0095.z_end + drift_95_50
            
            qfs50 = Quadrupole(qfs50_cfg["length"], qfs50_cfg["gradient"] / B_rho, B_rho, aperture_radius=quad_radius)
            qfs50.z_start = drift_95_50_el.z_end
            qfs50.z_end   = qfs50.z_start + qfs50_cfg["length"]
            
            drift_50_sep = survey["SEPTUM"] - survey["QFS50"] - qfs50_cfg["length"]
            drift_50_sep_el = Drift(drift_50_sep)
            drift_50_sep_el.z_start = qfs50.z_end
            drift_50_sep_el.z_end   = qfs50.z_end + drift_50_sep
        else:
            # Fallback if QFS50 not in config
            drift_95_sep = survey["SEPTUM"] - survey["QDS0095"] - qds0095_cfg["length"]
            drift_95_sep_el = Drift(drift_95_sep)
            drift_95_sep_el.z_start = qds0095.z_end
            drift_95_sep_el.z_end   = qds0095.z_end + drift_95_sep
            qfs50 = None
            drift_50_sep_el = None
        
        sep_cfg = septum_cfg
        theta_rad_sep = sep_cfg["bend_angle_deg"] * np.pi / 180.0
        By_sep = (theta_rad_sep * B_rho) / sep_cfg["length"]
        septum = Dipole(sep_cfg["length"], 0.0, By_sep, aperture_radius=septum_radius)
        
        if qfs50 is not None:
            septum.z_start = drift_50_sep_el.z_end
        else:
            septum.z_start = drift_95_sep_el.z_end
        septum.z_end   = septum.z_start + sep_cfg["length"]
        
        # Build FODO element list
        if qfs50 is not None:
            fodo_elements = [bhz0088, drift_88_90_el, qfo0090, drift_90_95_el, qds0095, drift_95_50_el, qfs50, drift_50_sep_el, septum]
        else:
            fodo_elements = [bhz0088, drift_88_90_el, qfo0090, drift_90_95_el, qds0095, drift_95_sep_el, septum]
        
        fodo_start_z = 0.5 + survey["BHZ0088"]
        fodo_end_z   = 0.5 + survey["SEPTUM"] + sep_cfg["length"]
        fodo_cell_L  = fodo_end_z - fodo_start_z
        
        aperture_obj = AcceptanceAperture(
            z_plane  = prism_end_z,
            radius   = aperture_r,
            x_offset = 0.0
        )
        
        machine = cls(
            prism_elements           = prism_elements,
            matching_elements        = matching_elements,
            fodo_elements            = fodo_elements,
            prism_end_z              = prism_end_z,
            matching_start_z         = matching_start_z,
            matching_end_z           = matching_end_z,
            fodo_start_z             = fodo_start_z,
            fodo_end_z               = fodo_end_z,
            fodo_cell_length         = fodo_cell_L,
            aperture                 = aperture_obj,
            dipole_chamber_width     = 3.0,
            dipole_chamber_height    = 3.0,
            matching_aperture_radius = aperture_r,
            bend_angles              = None
        )
        
        # Inject the parsed magnetic rigidity to drive the exact analytical orbit mapper
        machine.B_rho = B_rho
        
        aperture_x, _ = machine.get_reference_trajectory(prism_end_z)
        machine.aperture.x_offset = aperture_x
        
        machine._print_acol_summary(B_rho)
        machine._print_reference_orbit_diagnostics()
        machine._save_lattice_csv()
        
        return machine, data["config"]

    def _print_acol_summary(self, B_rho):
        print("\n" + "="*110)
        print("                                CERN ACOL INJECTION LATTICE SUMMARY")
        print("="*110)
        
        all_elements = []
        for el in self.prism_elements:
            all_elements.append((el, el.z_start, el.z_end))
        for el in self.matching_elements:
            all_elements.append((el, el.z_start, el.z_end))
        for el in self.fodo_elements:
            all_elements.append((el, el.z_start + self.fodo_start_z, el.z_end + self.fodo_start_z))
            
        print(f"{'Element':<12} | {'Type':<15} | {'Start s (m)':<12} | {'End s (m)':<12} | {'Length (m)':<10} | {'Grad (T/m)':<10} | {'Field (T)':<10} | {'Aper (m)':<8}")
        print("-" * 110)
        
        max_aperture = 0.0
        dipole_bends = []
        quad_gradients = []
        
        for idx, (el, z_start, z_end) in enumerate(all_elements):
            el_type = type(el).__name__
            name = f"{el_type}_{idx}"
            
            s_start = z_start - 0.5
            s_end = z_end - 0.5
            length = el.L
            
            grad_val = 0.0
            field_val = 0.0
            aper_val = 0.10
            
            if el_type == "MagneticHorn":
                name = "Horn"
                aper_val = 0.20
            elif el_type == "Drift":
                name = "Drift"
            elif el_type == "Quadrupole":
                if abs(s_start - 0.0) < 0.1: name = "QFO0050"
                elif abs(s_start - 5.0) < 0.1: name = "QDE0055"
                elif abs(s_start - 10.0) < 0.1: name = "QFO0060"
                elif abs(s_start - 15.0) < 0.1: name = "QDE0065"
                elif abs(s_start - 20.0) < 0.1: name = "QFO0070"
                elif abs(s_start - 25.0) < 0.1: name = "QDE0075"
                elif abs(s_start - 30.0) < 0.1: name = "QFO0080"
                elif abs(s_start - 35.0) < 0.1: name = "QDE0085"
                elif abs(s_start - 40.0) < 0.1: name = "QFO0090"
                elif abs(s_start - 45.0) < 0.1: name = "QDS0095"
                else: name = "Quadrupole"
                
                grad_val = el.g
                quad_gradients.append(f"{name}: {grad_val:.4f} T/m")
            elif el_type == "SelectorDipole":
                name = "BHZ0058"
                field_val = -el.By
                angle_deg = (field_val * length / B_rho) * 180.0 / np.pi
                dipole_bends.append(f"{name}: {angle_deg:.2f}°")
            elif el_type == "Dipole":
                if abs(s_start - 38.0) < 0.5:
                    name = "BHZ0088"
                elif abs(s_start - 46.0) < 0.5:
                    name = "SEPTUM"
                else:
                    name = "Dipole"
                field_val = el.By
                angle_deg = (field_val * length / B_rho) * 180.0 / np.pi
                dipole_bends.append(f"{name}: {angle_deg:.2f}°")
                
            if el_type != "Drift":
                max_aperture = max(max_aperture, aper_val)
                
            print(f"{name:<12} | {el_type:<15} | {s_start:<12.4f} | {s_end:<12.4f} | {length:<10.4f} | {grad_val:<10.4f} | {field_val:<10.4f} | {aper_val:<8.3f}")
            
        print("-" * 110)
        print(f"Total transfer-line length: {self.total_L - 0.5:.4f} m (from QFO0050 to septum exit)")
        print(f"Maximum aperture: {max_aperture:.3f} m")
        print(f"Dipole bend angles: {', '.join(dipole_bends)}")
        print(f"Quadrupole gradients: {', '.join(quad_gradients)}")
        print(f"Collector injection location: z = {self.total_L:.4f} m (s = {self.total_L - 0.5:.4f} m)")
        print("="*110 + "\n")

    def _save_lattice_csv(self):
        import csv
        import os
        
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs")
        os.makedirs(output_dir, exist_ok=True)
        
        csv_path = os.path.join(output_dir, "lattice_dump.csv")
        
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Element', 'Type', 'z_start', 'z_end', 'x_center', 'Length', 'Aperture'])
            
            # 1. Get reference orbit for all element centers
            z_centers = []
            for el in self.prism_elements + self.matching_elements:
                z_centers.append((el.z_start + el.z_end) / 2.0)
            for el in self.fodo_elements:
                z_centers.append(self.fodo_start_z + (el.z_start + el.z_end) / 2.0)
            
            x_refs = []
            if z_centers:
                z_centers_arr = np.array(z_centers)
                x_refs, _ = self.get_reference_trajectory(z_centers_arr)
            
            # 2. Export with the evaluated x_ref instead of the default 0.0
            idx = 0
            for el in self.prism_elements:
                el_type = type(el).__name__
                aperture = el.aperture_radius if hasattr(el, 'aperture_radius') and el.aperture_radius is not None else 0.10
                writer.writerow([f"{el_type}_{idx}", el_type, el.z_start, el.z_end, x_refs[idx], el.L, aperture])
                idx += 1
            
            for el in self.matching_elements:
                el_type = type(el).__name__
                aperture = el.aperture_radius if hasattr(el, 'aperture_radius') and el.aperture_radius is not None else 0.10
                writer.writerow([f"{el_type}_{idx}", el_type, el.z_start, el.z_end, x_refs[idx], el.L, aperture])
                idx += 1
            
            for el in self.fodo_elements:
                el_type = type(el).__name__
                aperture = el.aperture_radius if hasattr(el, 'aperture_radius') and el.aperture_radius is not None else 0.10
                z_start_abs = self.fodo_start_z + el.z_start
                z_end_abs = self.fodo_start_z + el.z_end
                writer.writerow([f"{el_type}_{idx}", el_type, z_start_abs, z_end_abs, x_refs[idx], el.L, aperture])
                idx += 1
        
        print(f"[Lattice] CSV dump saved to: {csv_path}")

    def _print_reference_orbit_diagnostics(self):
        """Print reference orbit diagnostics at every element boundary."""
        print("\n" + "="*110)
        print("                            REFERENCE ORBIT DIAGNOSTICS")
        print("="*110)
        print(f"{'Element':<15} | {'z (m)':<10} | {'theta (deg)':<12} | {'x_ref (m)':<12}")
        print("-" * 110)
        
        # Collect all element boundaries
        boundaries = []
        
        # Prism elements
        for el in self.prism_elements:
            if type(el).__name__ != "Drift":
                boundaries.append((type(el).__name__, el.z_start))
                boundaries.append((type(el).__name__, el.z_end))
        
        # Matching elements
        for el in self.matching_elements:
            if type(el).__name__ != "Drift":
                boundaries.append((type(el).__name__, el.z_start))
                boundaries.append((type(el).__name__, el.z_end))
        
        # FODO elements
        for el in self.fodo_elements:
            if type(el).__name__ != "Drift":
                z_start_abs = self.fodo_start_z + el.z_start
                z_end_abs = self.fodo_start_z + el.z_end
                boundaries.append((type(el).__name__, z_start_abs))
                boundaries.append((type(el).__name__, z_end_abs))
        
        # Sort by z position
        boundaries.sort(key=lambda x: x[1])
        
        # Print diagnostics at each boundary
        for name, z in boundaries:
            x_ref, theta = self.get_reference_trajectory(z)
            theta_deg = theta * 180.0 / np.pi
            print(f"{name:<15} | {z:<10.4f} | {theta_deg:<12.4f} | {x_ref:<12.4f}")
        
        print("="*110 + "\n")
        
        # Print specific dipole exit angles
        print("DIPOLE EXIT ANGLES:")
        print("-" * 50)
        
        # Find BHZ0058 exit
        for el in self.prism_elements:
            if type(el).__name__ == "SelectorDipole":
                x_ref, theta = self.get_reference_trajectory(el.z_end)
                theta_deg = theta * 180.0 / np.pi
                print(f"theta_after_BHZ0058: {theta_deg:.4f} deg at z = {el.z_end:.4f} m, x_ref = {x_ref:.4f} m")
                break
        
        # Find BHZ0088 exit
        for el in self.fodo_elements:
            if type(el).__name__ == "Dipole" and el.z_start < 40.0:
                z_exit = self.fodo_start_z + el.z_end
                x_ref, theta = self.get_reference_trajectory(z_exit)
                theta_deg = theta * 180.0 / np.pi
                print(f"theta_after_BHZ0088: {theta_deg:.4f} deg at z = {z_exit:.4f} m, x_ref = {x_ref:.4f} m")
                break
        
        # Find SEPTUM exit
        for el in self.fodo_elements:
            if type(el).__name__ == "Dipole" and el.z_start > 40.0:
                z_exit = self.fodo_start_z + el.z_end
                x_ref, theta = self.get_reference_trajectory(z_exit)
                theta_deg = theta * 180.0 / np.pi
                print(f"theta_after_Septum:  {theta_deg:.4f} deg at z = {z_exit:.4f} m, x_ref = {x_ref:.4f} m")
                break
        
        print("-" * 50 + "\n")

    # ------------------------------------------------------------------
    # Reference Trajectory and Magnetic field dispatch
    # ------------------------------------------------------------------

    def get_reference_trajectory(self, z):
        """
        Computes the exact piecewise reference trajectory x_ref(z) and angle theta(z)
        by dynamically extracting the true tracked fields from the dipoles and 
        calculating exact Cartesian circular arcs.
        """
        is_scalar = np.isscalar(z)
        z_arr = np.atleast_1d(z).astype(np.float64)
        x_ref = np.zeros_like(z_arr)
        theta = np.zeros_like(z_arr)
        
        if not hasattr(self, 'B_rho'):
            self.B_rho = 11.916 

        dipoles = []
        for el in self.prism_elements:
            if type(el).__name__ == "SelectorDipole":
                dipoles.append((el.z_start, el.z_end, -el.By)) # Selector forces negative
            elif type(el).__name__ == "Dipole":
                dipoles.append((el.z_start, el.z_end, el.By))
                
        for el in self.fodo_elements:
            if type(el).__name__ == "Dipole":
                dipoles.append((self.fodo_start_z + el.z_start, self.fodo_start_z + el.z_end, el.By))
                
        dipoles.sort(key=lambda x: x[0])
        
        segments = []
        cz, cx, cth = 0.0, 0.0, 0.0
        
        for d_z1, d_z2, d_By in dipoles:
            if d_z1 > cz:
                segments.append({'type': 'drift', 'z1': cz, 'z2': d_z1, 'x1': cx, 'theta': cth})
                cx = cx + (d_z1 - cz) * np.tan(cth)
                cz = d_z1
                
            rho = float('inf') if d_By == 0 else (self.B_rho / d_By)
            
            # FIXED: Correct normal vectors for center of curvature
            xc = cx + rho * np.cos(cth)
            zc = cz - rho * np.sin(cth)
            
            segments.append({'type': 'arc', 'z1': d_z1, 'z2': d_z2, 'xc': xc, 'zc': zc, 'rho': rho})
            
            # State at dipole exit
            cth = np.arcsin(np.clip((d_z2 - zc) / rho, -1.0, 1.0))
            arg = np.maximum(0.0, rho**2 - (d_z2 - zc)**2)
            
            # FIXED: Correct root subtraction to match physical bend direction
            cx = xc - np.sign(rho) * np.sqrt(arg)
            cz = d_z2
            
        segments.append({'type': 'drift', 'z1': cz, 'z2': float('inf'), 'x1': cx, 'theta': cth})
        
        for seg in segments:
            mask = (z_arr >= seg['z1']) & (z_arr < seg['z2'])
            if not np.any(mask): 
                continue
                
            zm = z_arr[mask]
            if seg['type'] == 'drift':
                theta[mask] = seg['theta']
                x_ref[mask] = seg['x1'] + (zm - seg['z1']) * np.tan(seg['theta'])
            else:
                rho, xc, zc = seg['rho'], seg['xc'], seg['zc']
                theta[mask] = np.arcsin(np.clip((zm - zc) / rho, -1.0, 1.0))
                arg = np.maximum(0.0, rho**2 - (zm - zc)**2)
                
                # FIXED: Correct root subtraction to match physical bend direction
                x_ref[mask] = xc - np.sign(rho) * np.sqrt(arg)
                
        return (x_ref[0], theta[0]) if is_scalar else (x_ref, theta)

    def get_B_field(self, positions):
        """
        Return the magnetic field B = (Bx, By, 0) at each particle position.
        Field is evaluated purely by z-zone membership; no charge dependency
        here — charge-dependent forces are handled in the Boris integrator.
        """
        N = positions.shape[0]
        B = np.zeros((N, 3), dtype=np.float32)
        if N == 0:
            return B

        x = positions[:, 0].copy()
        #x = positions[:, 0]
        y = positions[:, 1]
        z = positions[:, 2]

        # Shift x coordinate relative to the continuous reference trajectory x_ref(z)
        x_ref, _ = self.get_reference_trajectory(z)
        x -= x_ref

        # ── Zone 1: Prism (0 → prism_end_z) ────────────────────────────
        for el in self.prism_elements:
            mask = (z >= el.z_start) & (z < el.z_end)
            if not np.any(mask):
                continue
            Bx, By = el.get_field(x[mask], y[mask], z[mask])

            # Smooth horn field at exit to prevent impulsive kick artefacts
            if isinstance(el, MagneticHorn):
                buffer   = 0.01
                z_sub    = z[mask]
                scale    = np.ones_like(z_sub)
                in_buf   = z_sub >= (el.z_end - buffer)
                scale[in_buf] = (el.z_end - z_sub[in_buf]) / buffer
                Bx *= scale
                By *= scale

            B[mask, 0] = Bx
            B[mask, 1] = By

        # ── Zone 2: Matching quadrupoles ────────────────────────────────
        in_matching = (z >= self.matching_start_z) & (z < self.matching_end_z)
        if np.any(in_matching):
            for el in self.matching_elements:
                mask = in_matching & (z >= el.z_start) & (z < el.z_end)
                if not np.any(mask):
                    continue
                Bx, By = el.get_field(x[mask], y[mask], z[mask])
                B[mask, 0] = Bx
                B[mask, 1] = By

        # ── Zone 3: Periodic FODO ───────────────────────────────────────
        in_fodo = (z >= self.fodo_start_z) & (z < self.fodo_end_z)
        if np.any(in_fodo):
            global_indices = np.where(in_fodo)[0]
            #z_local = (z[in_fodo] - self.fodo_start_z) % self.fodo_cell_length
            z_local = z[in_fodo] - self.fodo_start_z
            for el in self.fodo_elements:
                mask_el = (z_local >= el.z_start) & (z_local < el.z_end)
                if not np.any(mask_el):
                    continue
                gidx = global_indices[mask_el]
                Bx, By = el.get_field(x[gidx], y[gidx], z[gidx])
                B[gidx, 0] = Bx
                B[gidx, 1] = By

        return B
