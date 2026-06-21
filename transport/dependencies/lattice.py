import numpy as np
import json
import sys


class GeometryError(Exception):
    pass


# ---------------------------------------------------------------------------
# Base Element
# ---------------------------------------------------------------------------

class Element:
    def __init__(self, L):
        self.L = L
        self.z_start = 0.0
        self.z_end = 0.0

    def get_field(self, x, y, z):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Generic / Legacy Elements
# ---------------------------------------------------------------------------

class Drift(Element):
    def get_field(self, x, y, z):
        return np.zeros_like(x), np.zeros_like(x)


class Dipole(Element):
    def __init__(self, L, Bx, By):
        super().__init__(L)
        self.Bx = Bx
        self.By = By

    def get_field(self, x, y, z):
        # Uniform steering field
        return np.full_like(x, self.Bx), np.full_like(y, self.By)


class Quadrupole(Element):
    def __init__(self, L, K, B_rho):
        super().__init__(L)
        self.K = K
        self.g = K * B_rho  # gradient in T/m

    def get_field(self, x, y, z):
        return self.g * y, self.g * x


class Sextupole(Element):
    def __init__(self, L, S, B_rho):
        super().__init__(L)
        self.S = S

    def get_field(self, x, y, z):
        return 2.0 * self.S * x * y, self.S * (x**2 - y**2)


class Octupole(Element):
    def __init__(self, L, O, B_rho):
        super().__init__(L)
        self.O = O

    def get_field(self, x, y, z):
        # Extreme non-linear resonance damping field
        return self.O * (x**3 - 3.0 * x * y**2), self.O * (3.0 * x**2 * y - y**3)


class MagneticHorn(Element):
    def __init__(self, L, I, r_throat=0.03, z_throat=0.25, a1=-0.17, a2=0.17):
        super().__init__(L)
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
    def __init__(self, L, By):
        super().__init__(L)
        self.By = By  # T, positive

    def get_field(self, x, y, z):
        # Return -self.By to align positive field parameter with -x deflection for antiprotons (q < 0)
        return np.zeros_like(x), np.full_like(y, -self.By)


class BeamDump(Element):
    """
    Dense on-axis absorber. No magnetic field contribution.
    Geometry attributes are used by the physics solver for collision detection.
    """
    def __init__(self, length, width, height, z_center, x_offset=0.0):
        super().__init__(length)
        self.dump_width  = width
        self.dump_height = height
        self.z_center    = z_center
        self.x_offset    = x_offset
        self.half_w      = width  / 2.0
        self.half_h      = height / 2.0
        # z_start / z_end are set by the caller after instantiation

    def get_field(self, x, y, z):
        return np.zeros_like(x), np.zeros_like(y)


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
                 aperture=None, dump=None,
                 dipole_chamber_width=3.0, dipole_chamber_height=3.0,
                 matching_aperture_radius=0.15):

        self.prism_elements    = prism_elements
        self.matching_elements = matching_elements
        self.fodo_elements     = fodo_elements

        self.prism_end_z         = prism_end_z
        self.matching_start_z    = matching_start_z
        self.matching_end_z      = matching_end_z
        self.fodo_start_z        = fodo_start_z
        self.fodo_end_z          = fodo_end_z
        self.fodo_cell_length    = fodo_cell_length

        self.aperture = aperture  # AcceptanceAperture | None
        self.dump     = dump      # BeamDump           | None

        self.dipole_chamber_width    = dipole_chamber_width
        self.dipole_chamber_height   = dipole_chamber_height
        self.matching_aperture_radius = matching_aperture_radius

        self.total_L       = fodo_end_z
        self.is_three_zone = True
        self.is_acol       = False

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

        p_gevc  = data["config"].get("reference_p_gevc", 3.57)
        c_light = 299792458.0
        B_rho   = (p_gevc * 1e9) / c_light  # magnetic rigidity [T·m]

        # ── Legacy schema (old injection_elements / periodic_elements) ──
        if "lattice" in data and "dipole_chamber" not in data and "acol" not in data:
            print("[Lattice] Legacy schema detected — loading two-zone lattice.")
            return _LegacyLattice.load_from_json(data, B_rho), data["config"]

        # ── CERN ACOL-inspired schema ───────────────────────────────────
        if "acol" in data:
            acol = data["acol"]
            survey = acol["survey_coordinates"]
            quads_cfg = acol["quadrupoles"]
            dipoles_cfg = acol["dipoles"]
            septum_cfg = acol["septum"]
            aperture_r = acol.get("aperture_radius", 0.10)
            
            # Target is at z=0, Horn is from z=0 to z=0.5
            horn_L = 0.50
            horn_I = data["config"].get("horn_current", -242934.66740974569)
            if "horn_current" in acol:
                horn_I = acol["horn_current"]
            horn = MagneticHorn(horn_L, horn_I)
            
            # Zone 1 (Prism): Target to end of BHZ0058 (s=10.0 or z=10.4513)
            # Elements: Horn, QFO0050, QDE0055, BHZ0058, plus drifts.
            prism_elements = [horn]
            
            # QFO0050 starts at s = 0.0 (z = 0.5)
            qfo0050_cfg = quads_cfg["QFO0050"]
            qfo0050 = Quadrupole(qfo0050_cfg["length"], qfo0050_cfg["gradient"] / B_rho, B_rho)
            prism_elements.append(qfo0050)
            
            # QDE0055 starts at s = 5.0 (z = 5.5)
            prism_elements.append(Drift(4.3))
            qde0055_cfg = quads_cfg["QDE0055"]
            qde0055 = Quadrupole(qde0055_cfg["length"], qde0055_cfg["gradient"] / B_rho, B_rho)
            prism_elements.append(qde0055)
            
            # BHZ0058 starts at s = 8.0 (z = 8.5)
            prism_elements.append(Drift(2.3))
            bhz0058_cfg = dipoles_cfg["BHZ0058"]
            theta_rad_0058 = bhz0058_cfg["bend_angle_deg"] * np.pi / 180.0
            By_0058 = (theta_rad_0058 * B_rho) / bhz0058_cfg["length"]
            selector = SelectorDipole(bhz0058_cfg["length"], abs(By_0058))
            prism_elements.append(selector)
            
            prism_end_z = 0.5 + survey["BHZ0058"] + bhz0058_cfg["length"]
            
            # Zone 2 (Matching): QFO0060 to QDE0085 (starts at z = 10.4513, ends at z = 38.5)
            matching_elements = []
            
            # QFO0060 starts at s = 10.0 (z = 10.5)
            matching_elements.append(Drift(0.0487))
            qfo0060_cfg = quads_cfg["QFO0060"]
            qfo0060 = Quadrupole(qfo0060_cfg["length"], qfo0060_cfg["gradient"] / B_rho, B_rho)
            matching_elements.append(qfo0060)
            
            # QDE0065 starts at s = 15.0 (z = 15.5)
            matching_elements.append(Drift(4.3))
            qde0065_cfg = quads_cfg["QDE0065"]
            qde0065 = Quadrupole(qde0065_cfg["length"], qde0065_cfg["gradient"] / B_rho, B_rho)
            matching_elements.append(qde0065)
            
            # QFO0070 starts at s = 20.0 (z = 20.5)
            matching_elements.append(Drift(4.3))
            qfo0070_cfg = quads_cfg["QFO0070"]
            qfo0070 = Quadrupole(qfo0070_cfg["length"], qfo0070_cfg["gradient"] / B_rho, B_rho)
            matching_elements.append(qfo0070)
            
            # QDE0075 starts at s = 25.0 (z = 25.5)
            matching_elements.append(Drift(4.3))
            qde0075_cfg = quads_cfg["QDE0075"]
            qde0075 = Quadrupole(qde0075_cfg["length"], qde0075_cfg["gradient"] / B_rho, B_rho)
            matching_elements.append(qde0075)
            
            # QFO0080 starts at s = 30.0 (z = 30.5)
            matching_elements.append(Drift(4.3))
            qfo0080_cfg = quads_cfg["QFO0080"]
            qfo0080 = Quadrupole(qfo0080_cfg["length"], qfo0080_cfg["gradient"] / B_rho, B_rho)
            matching_elements.append(qfo0080)
            
            # QDE0085 starts at s = 35.0 (z = 35.5)
            matching_elements.append(Drift(4.3))
            qde0085_cfg = quads_cfg["QDE0085"]
            qde0085 = Quadrupole(qde0085_cfg["length"], qde0085_cfg["gradient"] / B_rho, B_rho)
            matching_elements.append(qde0085)
            
            # Drift to start of Zone 3 (BHZ0088 starts at s = 38.0, z = 38.5)
            matching_elements.append(Drift(2.3))
            
            matching_start_z = 10.4513
            matching_end_z   = 38.5
            
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
            bhz0088 = Dipole(bhz0088_cfg["length"], 0.0, By_0088)
            bhz0088.z_start = 0.0
            bhz0088.z_end   = bhz0088_cfg["length"]
            
            drift_88_90 = Drift(0.0487)
            drift_88_90.z_start = bhz0088.z_end
            drift_88_90.z_end   = 2.0
            
            qfo0090_cfg = quads_cfg["QFO0090"]
            qfo0090 = Quadrupole(qfo0090_cfg["length"], qfo0090_cfg["gradient"] / B_rho, B_rho)
            qfo0090.z_start = 2.0
            qfo0090.z_end   = 2.0 + qfo0090_cfg["length"]
            
            drift_90_95 = Drift(4.3)
            drift_90_95.z_start = qfo0090.z_end
            drift_90_95.z_end   = 7.0
            
            qds0095_cfg = quads_cfg["QDS0095"]
            qds0095 = Quadrupole(qds0095_cfg["length"], qds0095_cfg["gradient"] / B_rho, B_rho)
            qds0095.z_start = 7.0
            qds0095.z_end   = 7.0 + qds0095_cfg["length"]
            
            drift_95_sep = Drift(0.3)
            drift_95_sep.z_start = qds0095.z_end
            drift_95_sep.z_end   = 8.0
            
            sep_cfg = septum_cfg
            theta_rad_sep = sep_cfg["bend_angle_deg"] * np.pi / 180.0
            By_sep = (theta_rad_sep * B_rho) / sep_cfg["length"]
            septum = Dipole(sep_cfg["length"], 0.0, By_sep)
            septum.z_start = 8.0
            septum.z_end   = 8.0 + sep_cfg["length"]
            
            fodo_elements = [bhz0088, drift_88_90, qfo0090, drift_90_95, qds0095, drift_95_sep, septum]
            
            fodo_start_z = 38.5
            fodo_end_z   = 48.4513
            fodo_cell_L  = 9.9513
            
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
                dump                     = None,
                dipole_chamber_width     = 3.0,
                dipole_chamber_height    = 3.0,
                matching_aperture_radius = aperture_r
            )
            machine.is_acol = True
            
            machine._print_acol_summary(B_rho)
            
            return machine, data["config"]

        # ── New three-zone schema ────────────────────────────────────────
        for key in ("dipole_chamber", "matching_section", "fodo_lattice"):
            if key not in data:
                print(f"[Lattice] ERROR: Missing required key '{key}' in new schema.")
                sys.exit(1)

        dc = data["dipole_chamber"]
        ms = data["matching_section"]
        fl = data["fodo_lattice"]

        # -- Zone 1: Prism --
        #   Element 0: MagneticHorn (L = 0.5 m, default params from prior Geant4 run)
        horn_L = 0.50
        horn_I = -242934.66740974569
        horn   = MagneticHorn(horn_L, horn_I)

        #   Element 1: SelectorDipole fills the rest of the chamber
        chamber_L = dc.get("length", 10.0)
        dipole_L  = chamber_L - horn_L
        selector  = SelectorDipole(dipole_L, dc.get("field_strength", 1.5))

        prism_elements = [horn, selector]

        #   Beam dump (on-axis absorber)
        dump_cfg  = dc.get("dump", {})
        dump_z    = dump_cfg.get("position_z", 6.0)
        dump_L    = dump_cfg.get("length", 2.0)
        dump_obj  = BeamDump(
            length   = dump_L,
            width    = dump_cfg.get("width",  1.0),
            height   = dump_cfg.get("height", 1.0),
            z_center = dump_z,
            x_offset = dump_cfg.get("x_offset", 0.0)
        )
        dump_obj.z_start = dump_z - dump_L / 2.0
        dump_obj.z_end   = dump_z + dump_L / 2.0

        #   Acceptance aperture (left side: x_offset < 0)
        aperture_obj = AcceptanceAperture(
            z_plane  = chamber_L,
            radius   = dc.get("acceptance_aperture_radius",  0.10),
            x_offset = dc.get("acceptance_aperture_x_offset", -0.5)
        )

        # -- Zone 2: Matching quadrupoles --
        matching_start_z = ms.get("start_z", 10.0)
        matching_end_z   = ms.get("end_z",   25.0)
        matching_aperture = ms.get("aperture_radius", 0.15)

        matching_elements = []
        for qd in ms.get("quadrupoles", []):
            z_pos = qd.get("z",        0.0)
            L_q   = qd.get("length",   0.5)
            g     = qd.get("gradient", 0.0)
            K     = g / B_rho
            q_el  = Quadrupole(L_q, K, B_rho)
            q_el.z_start = z_pos
            q_el.z_end   = z_pos + L_q
            matching_elements.append(q_el)

        # -- Zone 3: FODO cell elements (relative z within a single cell) --
        fodo_start_z   = fl.get("start_z",    25.0)
        fodo_end_z     = fl.get("end_z",       50.0)
        fodo_cell_L    = fl.get("cell_length",  4.0)
        quad_L         = fl.get("quad_length",  0.5)
        drift_L        = fl.get("drift_length", 1.5)

        K_F = fl.get("focusing_gradient",   8.0) / B_rho
        K_D = fl.get("defocusing_gradient", -8.0) / B_rho

        # Build one canonical FODO cell with relative (0-based) z coords
        qf = Quadrupole(quad_L, K_F, B_rho);  qf.z_start = 0.0;              qf.z_end = quad_L
        d1 = Drift(drift_L);                   d1.z_start = quad_L;           d1.z_end = quad_L + drift_L
        qd = Quadrupole(quad_L, K_D, B_rho);  qd.z_start = quad_L + drift_L; qd.z_end = 2*quad_L + drift_L
        d2 = Drift(drift_L);                   d2.z_start = 2*quad_L + drift_L; d2.z_end = fodo_cell_L

        fodo_elements = [qf, d1, qd, d2]

        machine = cls(
            prism_elements           = prism_elements,
            matching_elements        = matching_elements,
            fodo_elements            = fodo_elements,
            prism_end_z              = chamber_L,
            matching_start_z         = matching_start_z,
            matching_end_z           = matching_end_z,
            fodo_start_z             = fodo_start_z,
            fodo_end_z               = fodo_end_z,
            fodo_cell_length         = fodo_cell_L,
            aperture                 = aperture_obj,
            dump                     = dump_obj,
            dipole_chamber_width     = dc.get("width",  3.0),
            dipole_chamber_height    = dc.get("height", 3.0),
            matching_aperture_radius = matching_aperture,
        )
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

    # ------------------------------------------------------------------
    # Reference Trajectory and Magnetic field dispatch
    # ------------------------------------------------------------------

    def get_reference_trajectory(self, z):
        """
        Compute the reference trajectory x_ref(z) and tangent angle theta(z)
        based on the physical layout and bend angles of the dipoles:
        BHZ0058 (bend angle: -5.48 deg, z range: [8.5, 10.4513] m)
        BHZ0088 (bend angle:  0.98 deg, z range: [38.5, 40.4513] m)
        SEPTUM  (bend angle: -7.33 deg, z range: [46.5, 48.4513] m)
        """
        if not getattr(self, 'is_acol', False):
            if np.isscalar(z):
                return 0.0, 0.0
            z_arr = np.atleast_1d(z)
            return np.zeros_like(z_arr), np.zeros_like(z_arr)

        is_scalar = np.isscalar(z)
        z_arr = np.atleast_1d(z).astype(np.float64)
        
        x_ref = np.zeros_like(z_arr)
        theta = np.zeros_like(z_arr)
        
        # Bending regions z start and end positions
        z1, z2 = 8.5, 10.4513
        z3, z4 = 38.5, 40.4513
        z5, z6 = 46.5, 48.4513
        
        # Bend angles in radians
        theta_b1 = -5.48 * np.pi / 180.0
        theta_b2 = 0.98 * np.pi / 180.0
        theta_b3 = -7.33 * np.pi / 180.0
        
        # Bending rate k (radians per meter)
        k1 = theta_b1 / (z2 - z1)
        k2 = theta_b2 / (z4 - z3)
        k3 = theta_b3 / (z6 - z5)
        
        # Reference states at boundary points
        x_z1 = 0.0
        theta_z1 = 0.0
        
        theta_z2 = theta_b1
        x_z2 = x_z1 - (1.0 / k1) * np.log(np.cos(theta_z2))
        
        theta_z3 = theta_z2
        x_z3 = x_z2 + (z3 - z2) * np.tan(theta_z2)
        
        theta_z4 = theta_z3 + theta_b2
        x_z4 = x_z3 - (1.0 / k2) * (np.log(np.cos(theta_z4)) - np.log(np.cos(theta_z3)))
        
        theta_z5 = theta_z4
        x_z5 = x_z4 + (z5 - z4) * np.tan(theta_z4)
        
        theta_z6 = theta_z5 + theta_b3
        x_z6 = x_z5 - (1.0 / k3) * (np.log(np.cos(theta_z6)) - np.log(np.cos(theta_z5)))
        
        # 1. z < z1 (Straight line)
        mask0 = (z_arr < z1)
        x_ref[mask0] = 0.0
        theta[mask0] = 0.0
        
        # 2. z1 <= z < z2 (Inside BHZ0058)
        mask1 = (z_arr >= z1) & (z_arr < z2)
        if np.any(mask1):
            theta[mask1] = k1 * (z_arr[mask1] - z1)
            x_ref[mask1] = x_z1 - (1.0 / k1) * np.log(np.cos(theta[mask1]))
            
        # 3. z2 <= z < z3 (Straight line at angle theta_z2)
        mask2 = (z_arr >= z2) & (z_arr < z3)
        if np.any(mask2):
            theta[mask2] = theta_z2
            x_ref[mask2] = x_z2 + (z_arr[mask2] - z2) * np.tan(theta_z2)
            
        # 4. z3 <= z < z4 (Inside BHZ0088)
        mask3 = (z_arr >= z3) & (z_arr < z4)
        if np.any(mask3):
            theta[mask3] = theta_z3 + k2 * (z_arr[mask3] - z3)
            x_ref[mask3] = x_z3 - (1.0 / k2) * (np.log(np.cos(theta[mask3])) - np.log(np.cos(theta_z3)))
            
        # 5. z4 <= z < z5 (Straight line at angle theta_z4)
        mask4 = (z_arr >= z4) & (z_arr < z5)
        if np.any(mask4):
            theta[mask4] = theta_z4
            x_ref[mask4] = x_z4 + (z_arr[mask4] - z4) * np.tan(theta_z4)
            
        # 6. z >= z5
        mask5 = (z_arr >= z5)
        if np.any(mask5):
            # Inside Septum (z5 <= z < z6)
            in_sep = mask5 & (z_arr < z6)
            if np.any(in_sep):
                theta[in_sep] = theta_z5 + k3 * (z_arr[in_sep] - z5)
                x_ref[in_sep] = x_z5 - (1.0 / k3) * (np.log(np.cos(theta[in_sep])) - np.log(np.cos(theta_z5)))
            
            # Beyond Septum exit (z >= z6)
            beyond = mask5 & (z_arr >= z6)
            if np.any(beyond):
                theta[beyond] = theta_z6
                x_ref[beyond] = x_z6 + (z_arr[beyond] - z6) * np.tan(theta_z6)
                
        if is_scalar:
            return x_ref[0], theta[0]
        return x_ref, theta

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
        y = positions[:, 1]
        z = positions[:, 2]

        # Shift x coordinate relative to the continuous reference trajectory x_ref(z)
        if getattr(self, 'is_acol', False):
            x_ref, _ = self.get_reference_trajectory(z)
            x -= x_ref
        elif getattr(self, 'aperture', None) is not None:
            # Legacy flat offset for non-ACOL
            downstream = z >= self.prism_end_z
            x[downstream] -= self.aperture.x_offset

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
            z_local = (z[in_fodo] - self.fodo_start_z) % self.fodo_cell_length
            for el in self.fodo_elements:
                mask_el = (z_local >= el.z_start) & (z_local < el.z_end)
                if not np.any(mask_el):
                    continue
                gidx = global_indices[mask_el]
                Bx, By = el.get_field(x[gidx], y[gidx], z[gidx])
                B[gidx, 0] = Bx
                B[gidx, 1] = By

        return B


# ---------------------------------------------------------------------------
# Legacy Two-Zone Lattice (backward compat — old schema only)
# ---------------------------------------------------------------------------

class _LegacyLattice:
    """
    Backward-compatible wrapper for the old injection_elements +
    periodic_elements schema.  Exposes the same interface as Lattice.
    """

    def __init__(self, injection_elements, periodic_elements):
        self.injection_elements = injection_elements
        self.periodic_elements  = periodic_elements

        # Assign absolute geometry for Injection Line
        self.inj_L = 0.0
        for el in self.injection_elements:
            if el.L < 0:
                raise GeometryError("Negative length encountered")
            el.z_start  = self.inj_L
            self.inj_L += el.L
            el.z_end    = self.inj_L

        # Assign absolute geometry for Periodic Channel
        self.per_L = 0.0
        for el in self.periodic_elements:
            if el.L < 0:
                raise GeometryError("Negative length encountered")
            el.z_start  = self.inj_L + self.per_L
            self.per_L += el.L
            el.z_end    = self.inj_L + self.per_L

        self.total_L = self.inj_L + self.per_L

        # ── Expose three-zone interface with legacy-compatible values ──
        self.prism_end_z              = self.inj_L
        self.matching_start_z         = self.inj_L
        self.matching_end_z           = self.inj_L   # empty matching section
        self.fodo_start_z             = self.inj_L
        self.fodo_end_z               = float('inf')
        self.fodo_cell_length         = self.per_L

        self.prism_elements    = injection_elements
        self.matching_elements = []
        self.fodo_elements     = periodic_elements

        self.aperture = None
        self.dump     = None

        # Legacy geometry defaults (old horn-chamber values)
        self.dipole_chamber_width     = 0.70   # = 2 × 0.35 m chamber radius
        self.dipole_chamber_height    = 0.70
        self.matching_aperture_radius = 0.10

        self.is_three_zone = False

    @classmethod
    def load_from_json(cls, data, B_rho):
        lattice_data = data["lattice"]

        def parse_element_list(el_list):
            out = []
            for el_data in el_list:
                t = el_data.get('type')
                L = el_data.get('L')
                if t == 'Quadrupole':
                    out.append(Quadrupole(L, el_data['K'], B_rho))
                elif t == 'Drift':
                    out.append(Drift(L))
                elif t == 'Dipole':
                    out.append(Dipole(L, el_data['Bx'], el_data['By']))
                elif t == 'MagneticHorn':
                    out.append(MagneticHorn(L, el_data['I']))
            return out

        inj_elements = parse_element_list(lattice_data.get('injection_elements', []))
        per_elements = parse_element_list(lattice_data.get('periodic_elements', []))
        return cls(inj_elements, per_elements)

    def get_B_field(self, positions):
        N = positions.shape[0]
        B = np.zeros((N, 3), dtype=np.float32)
        if N == 0:
            return B

        x = positions[:, 0]
        y = positions[:, 1]
        z = positions[:, 2]

        buffer = 0.01
        for el in self.injection_elements:
            mask = (z >= el.z_start) & (z < el.z_end)
            if np.any(mask):
                Bx, By = el.get_field(x[mask], y[mask], z[mask])
                if isinstance(el, MagneticHorn):
                    z_sub  = z[mask]
                    scale  = np.ones_like(z_sub)
                    in_buf = z_sub >= (el.z_end - buffer)
                    scale[in_buf] = (el.z_end - z_sub[in_buf]) / buffer
                    Bx *= scale
                    By *= scale
                B[mask, 0] = Bx
                B[mask, 1] = By

        # Infinite periodic loop past the injection line
        past_inj = z >= self.inj_L
        if np.any(past_inj):
            z_periodic = self.inj_L + ((z[past_inj] - self.inj_L) % self.per_L)
            for el in self.periodic_elements:
                mask_el = (z_periodic >= el.z_start) & (z_periodic < el.z_end)
                if np.any(mask_el):
                    global_mask = np.zeros(N, dtype=bool)
                    global_mask[past_inj] = mask_el
                    Bx, By = el.get_field(x[global_mask], y[global_mask], z[global_mask])
                    B[global_mask, 0] = Bx
                    B[global_mask, 1] = By

        return B
