import sys
import numpy as np
import multiprocessing as mp
from multiprocessing.shared_memory import SharedMemory

# Use PyQt5 backend
import vispy
vispy.use('PyQt5')
from vispy import scene
from vispy.color import ColorArray
from vispy.visuals.transforms import MatrixTransform
from vispy.scene.visuals import Box, Tube, Line, Text


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_COL_ANTIPROTON   = np.array([0.00, 0.80, 1.00])   # electric cyan
_COL_PROTON       = np.array([1.00, 0.18, 0.08])   # hot red
_COL_HORN         = (0.4, 0.1, 0.9, 0.18)
_COL_PIPE         = (0.05, 0.10, 0.15, 0.30)
_COL_PIPE_WIRE    = (0.20, 0.40, 0.60, 0.80)
_COL_SEP_CHAMBER  = (0.04, 0.12, 0.22, 0.00)
_COL_SEP_EDGE     = (0.30, 0.60, 0.90, 0.70)
_COL_DIPOLE_FIELD = (0.30, 0.00, 0.80, 0.10)
_COL_DUMP         = (0.12, 0.12, 0.12, 0.35)
_COL_DUMP_EDGE    = (0.70, 0.35, 0.05, 1.00)
_COL_APERTURE     = (0.00, 1.00, 0.50, 1.00)
_COL_MATCH_F      = (1.00, 0.70, 0.00, 0.82)   # amber  — focusing
_COL_MATCH_D      = (0.00, 0.60, 1.00, 0.82)   # cobalt — defocusing
_COL_FODO_F       = (0.15, 0.90, 0.30, 0.85)   # green  — focusing
_COL_FODO_D       = (0.95, 0.15, 0.15, 0.85)   # red    — defocusing
_COL_TARGET_CORE  = (1.00, 0.00, 0.50, 1.00)
_COL_TARGET_GLOW  = (1.00, 0.00, 0.50, 0.18)


def _tube5(view, z0, z1, radius, color, x0=0.0, y0=0.0, x1=None, y1=None):
    """Helper: 5-point Tube to avoid VisPy tangent-calculation bugs.

    NOTE: shading must NOT be set to None here. When shading=None, VisPy's
    Tube mesh drops into an unlit path that ignores the color= argument and
    renders the geometry black/invisible. Omitting shading (default='smooth')
    enables the lit path that correctly applies the RGBA color.
    """
    if x1 is None: x1 = x0
    if y1 is None: y1 = y0
    pts = np.zeros((5, 3), dtype=np.float32)
    pts[:, 0] = np.linspace(x0, x1, 5)
    pts[:, 1] = np.linspace(y0, y1, 5)
    pts[:, 2] = np.linspace(z0, z1, 5)
    t = Tube(points=pts, radius=radius, closed=False,
             color=color, parent=view.scene)
    if len(color) > 3 and color[3] < 1.0:
        t.set_gl_state('translucent', depth_mask=False)
    return t


def _ring(view, cx, cy, cz, radius, color, n=40):
    """Helper: Draw a circle as a closed Line strip in the x-y plane."""
    theta = np.linspace(0, 2 * np.pi, n + 1, endpoint=True)
    pts   = np.column_stack([
        cx + radius * np.cos(theta),
        cy + radius * np.sin(theta),
        np.full(n + 1, cz, dtype=np.float32)
    ]).astype(np.float32)
    return Line(pos=pts, connect='strip', color=color, parent=view.scene)


def _box_at(view, width, height, depth, cx, cy, cz, color, edge_color):
    """Helper: Translated Box at (cx, cy, cz)."""
    b = Box(width=width, height=depth, depth=height,
            color=color, edge_color=edge_color, parent=view.scene)
    b.transform = MatrixTransform()
    b.transform.translate((cx, cy, cz))
    if len(color) > 3 and color[3] < 1.0:
        b.set_gl_state('translucent', depth_mask=False)
    return b


# ---------------------------------------------------------------------------
# Reference Trajectory Factory
# ---------------------------------------------------------------------------

def make_trajectory_func(acol_data):
    """
    Builds a dynamic reference trajectory interpolator based on the actual 
    JSON survey coordinates and bend angles to ensure standard compliance
    with the new lattice updates.
    """
    survey = acol_data.get("survey_coordinates", {})
    dipoles = acol_data.get("dipoles", {})
    septum = acol_data.get("septum", {})
    
    # BHZ0058 Setup
    z1 = 0.5 + survey.get("BHZ0058", 8.0)
    L1 = dipoles.get("BHZ0058", {}).get("length", 1.9513)
    z2 = z1 + L1
    theta_b1 = dipoles.get("BHZ0058", {}).get("bend_angle_deg", -5.48) * np.pi / 180.0
    
    # BHZ0088 Setup
    z3 = 0.5 + survey.get("BHZ0088", 38.0)
    L2 = dipoles.get("BHZ0088", {}).get("length", 1.9513)
    z4 = z3 + L2
    theta_b2 = dipoles.get("BHZ0088", {}).get("bend_angle_deg", 0.98) * np.pi / 180.0
    
    # SEPTUM Setup
    z5 = 0.5 + survey.get("SEPTUM", 46.0)
    L3 = septum.get("length", 1.9513)
    z6 = z5 + L3
    theta_b3 = septum.get("bend_angle_deg", -7.33) * np.pi / 180.0
    
    k1 = theta_b1 / L1 if L1 > 1e-6 else 0.0
    k2 = theta_b2 / L2 if L2 > 1e-6 else 0.0
    k3 = theta_b3 / L3 if L3 > 1e-6 else 0.0
    
    x_z1 = 0.0
    theta_z1 = 0.0
    
    theta_z2 = theta_b1
    x_z2 = x_z1 - (1.0 / k1) * np.log(np.cos(theta_z2)) if abs(k1) > 1e-6 else x_z1 + L1 * np.tan(theta_b1/2)
    
    theta_z3 = theta_z2
    x_z3 = x_z2 + (z3 - z2) * np.tan(theta_z2)
    
    theta_z4 = theta_z3 + theta_b2
    x_z4 = x_z3 - (1.0 / k2) * (np.log(np.cos(theta_z4)) - np.log(np.cos(theta_z3))) if abs(k2) > 1e-6 else x_z3 + L2 * np.tan(theta_z3 + theta_b2/2)
    
    theta_z5 = theta_z4
    x_z5 = x_z4 + (z5 - z4) * np.tan(theta_z4)
    
    theta_z6 = theta_z5 + theta_b3
    x_z6 = x_z5 - (1.0 / k3) * (np.log(np.cos(theta_z6)) - np.log(np.cos(theta_z5))) if abs(k3) > 1e-6 else x_z5 + L3 * np.tan(theta_z5 + theta_b3/2)
    
    def get_reference_trajectory(z):
        is_scalar = np.isscalar(z)
        z_arr = np.atleast_1d(z).astype(np.float64)
        x_ref = np.zeros_like(z_arr)
        theta = np.zeros_like(z_arr)
        
        mask0 = (z_arr < z1)
        x_ref[mask0] = 0.0
        theta[mask0] = 0.0
        
        mask1 = (z_arr >= z1) & (z_arr < z2)
        if np.any(mask1):
            theta[mask1] = k1 * (z_arr[mask1] - z1)
            x_ref[mask1] = x_z1 - (1.0 / k1) * np.log(np.cos(theta[mask1])) if abs(k1) > 1e-6 else x_z1 + (z_arr[mask1]-z1)*np.tan(theta[mask1]/2)
            
        mask2 = (z_arr >= z2) & (z_arr < z3)
        if np.any(mask2):
            theta[mask2] = theta_z2
            x_ref[mask2] = x_z2 + (z_arr[mask2] - z2) * np.tan(theta_z2)
            
        mask3 = (z_arr >= z3) & (z_arr < z4)
        if np.any(mask3):
            theta[mask3] = theta_z3 + k2 * (z_arr[mask3] - z3)
            x_ref[mask3] = x_z3 - (1.0 / k2) * (np.log(np.cos(theta[mask3])) - np.log(np.cos(theta_z3))) if abs(k2)>1e-6 else x_z3 + (z_arr[mask3]-z3)*np.tan(theta_z3 + (theta[mask3]-theta_z3)/2)
            
        mask4 = (z_arr >= z4) & (z_arr < z5)
        if np.any(mask4):
            theta[mask4] = theta_z4
            x_ref[mask4] = x_z4 + (z_arr[mask4] - z4) * np.tan(theta_z4)
            
        mask5 = (z_arr >= z5)
        if np.any(mask5):
            in_sep = mask5 & (z_arr < z6)
            if np.any(in_sep):
                theta[in_sep] = theta_z5 + k3 * (z_arr[in_sep] - z5)
                x_ref[in_sep] = x_z5 - (1.0 / k3) * (np.log(np.cos(theta[in_sep])) - np.log(np.cos(theta_z5))) if abs(k3)>1e-6 else x_z5 + (z_arr[in_sep]-z5)*np.tan(theta_z5+(theta[in_sep]-theta_z5)/2)
            
            beyond = mask5 & (z_arr >= z6)
            if np.any(beyond):
                theta[beyond] = theta_z6
                x_ref[beyond] = x_z6 + (z_arr[beyond] - z6) * np.tan(theta_z6)
                
        if is_scalar:
            return x_ref[0], theta[0]
        return x_ref, theta
        
    return get_reference_trajectory


# ---------------------------------------------------------------------------
# Scene builder
# ---------------------------------------------------------------------------

def _build_scene(view, canvas, fallback_r_pipe, raw_data, env_data):
    """
    Construct the static beamline geometry in the VisPy scene.
    Returns a dict of geometry metadata needed by the animation loop.
    """
    dc = raw_data.get("dipole_chamber", {})
    ms = raw_data.get("matching_section", {})
    fl = raw_data.get("fodo_lattice", {})

    is_three_zone = bool(dc)

    # ── Geant4 target / chamber geometry ────────────────────────────────
    try:
        c_width  = float(env_data.get("chamber_width",  "40.0 cm").split()[0]) / 100.0
        c_length = float(env_data.get("chamber_length", "120.0 cm").split()[0]) / 100.0
        t_width  = float(env_data.get("target_width",   "3.0 mm").split()[0])  / 1000.0
        t_length = float(env_data.get("target_length",  "55.0 cm").split()[0]) / 100.0
        t_z      = float(env_data.get("target_position", "0 0 -27.5 cm").split()[2]) / 100.0
    except Exception:
        c_width, c_length, t_width, t_length, t_z = 0.40, 1.20, 0.003, 0.55, -0.275

    t_z_start = t_z - t_length / 2.0
    t_z_end   = t_z + t_length / 2.0
    t_radius  = t_width / 2.0

    metadata = {}

    if "acol" in raw_data:
        acol = raw_data["acol"]
        survey = acol["survey_coordinates"]
        quads_cfg = acol["quadrupoles"]
        dipoles_cfg = acol["dipoles"]
        septum_cfg = acol["septum"]
        
        # Pull realistic aperture config mapped from new lattice format
        apertures_cfg = acol.get("apertures", {})
        dipole_r = apertures_cfg.get("dipole_radius", 0.044)
        quad_r   = apertures_cfg.get("quadrupole_radius", 0.095)
        septum_r = apertures_cfg.get("septum_radius", 0.05)
        horn_r   = apertures_cfg.get("horn_radius", 0.20)
        pipe_r   = apertures_cfg.get("pipe_radius", 0.10)
        
        get_ref_traj = make_trajectory_func(acol)
        
        # 1. Target Core + Glow
        _tube5(view, t_z_start, t_z_end, t_radius,           _COL_TARGET_CORE)
        _tube5(view, t_z_start, t_z_end, t_radius * 5.0,     _COL_TARGET_GLOW)
        
        # 2. Horn: z in [0.0, 0.5]
        horn_length = 0.5
        r1, r2 = 0.20, pipe_r
        pts_z = np.linspace(0.0, horn_length, 5)
        horn_pts = np.zeros((5, 3), dtype=np.float32)
        horn_pts[:, 2] = pts_z
        horn_rads = np.linspace(r1, r2, 5)
        Tube(points=horn_pts, radius=horn_rads, closed=False,
             color=_COL_HORN, parent=view.scene)
             
        # Dynamic coordinate milestones
        z1 = 0.5 + survey.get("BHZ0058", 8.0)
        prism_end_z = z1 + dipoles_cfg.get("BHZ0058", {}).get("length", 1.9513)
        total_len = 0.5 + survey.get("SEPTUM", 46.0) + septum_cfg.get("length", 1.9513)
        
        # 1. Entrance pipe (straight, z in [0.5, z1])
        ent_pts_z = np.linspace(0.5, z1, 50)
        ent_pts = np.column_stack([np.zeros_like(ent_pts_z), np.zeros_like(ent_pts_z), ent_pts_z]).astype(np.float32)
        t_ent = Tube(points=ent_pts, radius=pipe_r, closed=False,
                     color=_COL_PIPE, parent=view.scene)
        t_ent.set_gl_state('translucent', depth_mask=False)
        
        # 2. Exit pipe (curved, z in [prism_end_z, total_len])
        exit_pts_z = np.linspace(prism_end_z, total_len, 150)
        exit_pts_x, _ = get_ref_traj(exit_pts_z)
        exit_pts = np.column_stack([exit_pts_x, np.zeros_like(exit_pts_z), exit_pts_z]).astype(np.float32)
        t_exit = Tube(points=exit_pts, radius=pipe_r, closed=False,
                      color=_COL_PIPE, parent=view.scene)
        t_exit.set_gl_state('translucent', depth_mask=False)
        
        # Quadrupoles
        for name, cfg in quads_cfg.items():
            s_start = survey[name]
            z_start = 0.5 + s_start
            z_end = z_start + cfg["length"]
            g = cfg["gradient"]
            if name in ["QFO0050", "QDE0055", "QFO0090", "QDS0095"]:
                col = _COL_MATCH_F if g >= 0 else _COL_MATCH_D
            else:
                col = _COL_FODO_F if g >= 0 else _COL_FODO_D
            
            x0_ref, _ = get_ref_traj(z_start)
            x1_ref, _ = get_ref_traj(z_end)
            
            _tube5(view, z_start, z_end, quad_r * 1.65, col, x0=x0_ref, x1=x1_ref)
            _tube5(view, z_start, z_end, quad_r * 0.95, (*col[:3], 0.15), x0=x0_ref, x1=x1_ref)
            
        # Dipoles
        for name, cfg in dipoles_cfg.items():
            s_start = survey[name]
            z_start = 0.5 + s_start
            z_end = z_start + cfg["length"]
            cx_ref, _ = get_ref_traj(z_start + cfg["length"] / 2.0)
            _box_at(view,
                    width=dipole_r * 4.0, height=dipole_r * 4.0, depth=cfg["length"],
                    cx=cx_ref, cy=0.0, cz=z_start + cfg["length"] / 2.0,
                    color=_COL_DIPOLE_FIELD, edge_color=(0.4, 0.0, 0.8, 0.5))
            
        # Septum
        s_start_sep = survey["SEPTUM"]
        z_start_sep = 0.5 + s_start_sep
        z_end_sep = z_start_sep + septum_cfg["length"]
        cx_ref, _ = get_ref_traj(z_start_sep + septum_cfg["length"] / 2.0)
        _box_at(view,
                width=septum_r * 4.0, height=septum_r * 4.0, depth=septum_cfg["length"],
                cx=cx_ref, cy=0.0, cz=z_start_sep + septum_cfg["length"] / 2.0,
                color=(1.0, 0.2, 0.2, 0.3), edge_color=(1.0, 0.0, 0.0, 0.8))
                
        # Optical flow rings (wireframe) following bent trajectory
        theta_r = np.linspace(0, 2 * np.pi, 16, endpoint=False)
        ring_step = 1.0
        r = pipe_r * 1.02
        
        # Draw transversal rings
        pts_rings = []
        
        # 1. Straight entrance pipe: 0.5 <= z < z1
        for z_r in np.arange(0.5, z1, ring_step):
            for k in range(len(theta_r)):
                t1 = theta_r[k]; t2 = theta_r[(k + 1) % len(theta_r)]
                pts_rings.append([r * np.cos(t1), r * np.sin(t1), z_r])
                pts_rings.append([r * np.cos(t2), r * np.sin(t2), z_r])
                
        # 2. Racetrack encasing inside selector dipole: z1 <= z <= prism_end_z
        for z_r in np.arange(z1, prism_end_z + 0.05, 0.25):
            x_ref_val, _ = get_ref_traj(z_r)
            cx_left = x_ref_val
            cx_right = -x_ref_val
            
            # Left semicircle: pi/2 to 3*pi/2
            theta_left = np.linspace(np.pi / 2, 3 * np.pi / 2, 8)
            left_pts = []
            for t in theta_left:
                left_pts.append([cx_left + r * np.cos(t), r * np.sin(t), z_r])
                
            # Right semicircle: -pi/2 to pi/2
            theta_right = np.linspace(-np.pi / 2, np.pi / 2, 8)
            right_pts = []
            for t in theta_right:
                right_pts.append([cx_right + r * np.cos(t), r * np.sin(t), z_r])
                
            # Connect them into a closed loop
            loop = left_pts + right_pts
            for k in range(len(loop)):
                p1 = loop[k]
                p2 = loop[(k + 1) % len(loop)]
                pts_rings.append(p1)
                pts_rings.append(p2)
                
        # 3. Curved exit pipe: prism_end_z < z <= total_len
        for z_r in np.arange(prism_end_z, total_len + ring_step, ring_step):
            x_ref_val, _ = get_ref_traj(z_r)
            for k in range(len(theta_r)):
                t1 = theta_r[k]; t2 = theta_r[(k + 1) % len(theta_r)]
                pts_rings.append([x_ref_val + r * np.cos(t1), r * np.sin(t1), z_r])
                pts_rings.append([x_ref_val + r * np.cos(t2), r * np.sin(t2), z_r])
                
        Line(pos=np.array(pts_rings, dtype=np.float32),
             connect='segments', color=_COL_PIPE_WIRE, parent=view.scene)
             
        # Draw longitudinal lines wrapping around the bends
        # 1. Leftmost line (phi = pi) - always active
        long_pts_left = []
        for z_r in np.arange(0.5, total_len + 0.1, 0.5):
            if z_r <= z1:
                long_pts_left.append([-r, 0.0, z_r])
            else:
                x_ref_val, _ = get_ref_traj(z_r)
                long_pts_left.append([x_ref_val - r, 0.0, z_r])
        Line(pos=np.array(long_pts_left, dtype=np.float32),
             connect='strip', color=_COL_PIPE_WIRE, parent=view.scene)
             
        # 2. Rightmost line (phi = 0) - ends at prism_end_z
        long_pts_right = []
        for z_r in np.arange(0.5, prism_end_z + 0.05, 0.2):
            if z_r <= z1:
                long_pts_right.append([r, 0.0, z_r])
            else:
                x_ref_val, _ = get_ref_traj(z_r)
                long_pts_right.append([-x_ref_val + r, 0.0, z_r])
        Line(pos=np.array(long_pts_right, dtype=np.float32),
             connect='strip', color=_COL_PIPE_WIRE, parent=view.scene)
             
        # 3. Top lines (phi = pi/2)
        # Left side top (0.5 to total_len)
        long_pts_top_l = []
        for z_r in np.arange(0.5, total_len + 0.1, 0.5):
            if z_r <= z1:
                long_pts_top_l.append([0.0, r, z_r])
            else:
                x_ref_val, _ = get_ref_traj(z_r)
                long_pts_top_l.append([x_ref_val, r, z_r])
        Line(pos=np.array(long_pts_top_l, dtype=np.float32),
             connect='strip', color=_COL_PIPE_WIRE, parent=view.scene)
             
        # Right side top (z1 to prism_end_z)
        long_pts_top_r = []
        for z_r in np.arange(z1, prism_end_z + 0.05, 0.1):
            x_ref_val, _ = get_ref_traj(z_r)
            long_pts_top_r.append([-x_ref_val, r, z_r])
        Line(pos=np.array(long_pts_top_r, dtype=np.float32),
             connect='strip', color=_COL_PIPE_WIRE, parent=view.scene)
             
        # 4. Bottom lines (phi = 3*pi/2)
        # Left side bottom (0.5 to total_len)
        long_pts_bot_l = []
        for z_r in np.arange(0.5, total_len + 0.1, 0.5):
            if z_r <= z1:
                long_pts_bot_l.append([0.0, -r, z_r])
            else:
                x_ref_val, _ = get_ref_traj(z_r)
                long_pts_bot_l.append([x_ref_val, -r, z_r])
        Line(pos=np.array(long_pts_bot_l, dtype=np.float32),
             connect='strip', color=_COL_PIPE_WIRE, parent=view.scene)
             
        # Right side bottom (z1 to prism_end_z)
        long_pts_bot_r = []
        for z_r in np.arange(z1, prism_end_z + 0.05, 0.1):
            x_ref_val, _ = get_ref_traj(z_r)
            long_pts_bot_r.append([-x_ref_val, -r, z_r])
        Line(pos=np.array(long_pts_bot_r, dtype=np.float32),
             connect='strip', color=_COL_PIPE_WIRE, parent=view.scene)
             
        metadata.update({
            "horn_length":   horn_length,
            "is_three_zone": True,
            "chamber_L":     10.4513,
            "fodo_start":    38.5,
            "fodo_end":      total_len,
        })
        return metadata

    # ── Legacy logic (Maintained for safety) ─────────────────────────────
    horn_length = 0.0
    if is_three_zone:
        # Horn always occupies the first 0.5 m of Zone 1
        horn_length = 0.5
        r1, r2 = 0.20, fallback_r_pipe
        pts_z = np.linspace(0.0, horn_length, 5)
        horn_pts = np.zeros((5, 3), dtype=np.float32)
        horn_pts[:, 2] = pts_z
        horn_rads = np.linspace(r1, r2, 5)
        Tube(points=horn_pts, radius=horn_rads, closed=False,
             color=_COL_HORN, parent=view.scene)
    else:
        # Legacy: find horn from injection_elements list
        inj_els  = raw_data.get("lattice", {}).get("injection_elements", [])
        z_cursor = 0.0
        for el in inj_els:
            if el.get('type') == 'MagneticHorn':
                L  = el.get('L', 0.50)
                horn_length = L
                r1, r2 = 0.20, fallback_r_pipe
                pts_z = np.linspace(z_cursor, z_cursor + L, 5)
                horn_pts = np.zeros((5, 3), dtype=np.float32)
                horn_pts[:, 2] = pts_z
                horn_rads = np.linspace(r1, r2, 5)
                Tube(points=horn_pts, radius=horn_rads, closed=False,
                     color=_COL_HORN, parent=view.scene)
            z_cursor += el.get('L', 0.0)

    metadata = {"horn_length": horn_length}

    if is_three_zone:
        chamber_L = dc.get("length", 10.0)
        chamber_W = dc.get("width",  3.0)
        chamber_H = dc.get("height", 3.0)

        sep_chamber = _box_at(view,
                              width=chamber_W, height=chamber_H, depth=chamber_L,
                              cx=0.0, cy=0.0, cz=chamber_L / 2.0,
                              color=_COL_SEP_CHAMBER, edge_color=_COL_SEP_EDGE)

        _box_at(view,
                width=chamber_W * 0.95, height=chamber_H * 0.95,
                depth=chamber_L - horn_length,
                cx=0.0, cy=0.0, cz=horn_length + (chamber_L - horn_length) / 2.0,
                color=_COL_DIPOLE_FIELD, edge_color=(0.4, 0.0, 0.8, 0.2))

        dump_cfg    = dc.get("dump", {})
        dump_L      = dump_cfg.get("length",     2.0)
        dump_W      = dump_cfg.get("width",      1.0)
        dump_H      = dump_cfg.get("height",     1.0)
        dump_z_ctr  = dump_cfg.get("position_z", 6.0)
        dump_x_off  = dump_cfg.get("x_offset",   0.0)
        _box_at(view,
                width=dump_W, height=dump_H, depth=dump_L,
                cx=dump_x_off, cy=0.0, cz=dump_z_ctr,
                color=_COL_DUMP, edge_color=_COL_DUMP_EDGE)

        aper_r    = dc.get("acceptance_aperture_radius",  0.10)
        aper_x    = dc.get("acceptance_aperture_x_offset", -0.5)
        aper_z    = chamber_L
        _ring(view, cx=aper_x, cy=0.0, cz=aper_z,
              radius=aper_r, color=_COL_APERTURE)

        _ring(view, cx=aper_x, cy=0.0, cz=aper_z - 0.05,
              radius=aper_r * 1.3, color=(*_COL_APERTURE[:3], 0.35))

        arrow_pts = np.array([
            [0.0,  0.0, aper_z],
            [aper_x, 0.0, aper_z]
        ], dtype=np.float32)
        Line(pos=arrow_pts, connect='strip',
             color=(0.0, 1.0, 0.5, 0.5), parent=view.scene)

        match_r = ms.get("aperture_radius", 0.15)
        ms_start = ms.get("start_z", 10.0)
        ms_end   = ms.get("end_z",   25.0)

        _tube5(view, ms_start, ms_end, match_r, _COL_PIPE, x0=aper_x, x1=aper_x)

        for qd in ms.get("quadrupoles", []):
            q_z  = qd.get("z",        0.0)
            q_L  = qd.get("length",   0.5)
            q_g  = qd.get("gradient", 0.0)
            col  = _COL_MATCH_F if q_g >= 0 else _COL_MATCH_D
            _tube5(view, q_z, q_z + q_L, match_r * 1.60, col, x0=aper_x, x1=aper_x)
            _tube5(view, q_z, q_z + q_L, match_r * 0.95,
                   (*col[:3], 0.15), x0=aper_x, x1=aper_x)

        fodo_start = fl.get("start_z",    25.0)
        fodo_end   = fl.get("end_z",       50.0)
        cell_L     = fl.get("cell_length",  4.0)
        quad_L_f   = fl.get("quad_length",  0.5)
        drift_L_f  = fl.get("drift_length", 1.5)

        _tube5(view, fodo_start, fodo_end, fallback_r_pipe, _COL_PIPE, x0=aper_x, x1=aper_x)

        n_cells = int((fodo_end - fodo_start) / cell_L)
        for i in range(n_cells):
            cell_z = fodo_start + i * cell_L

            qf_z0 = cell_z
            qf_z1 = cell_z + quad_L_f
            _tube5(view, qf_z0, qf_z1, fallback_r_pipe * 1.65, _COL_FODO_F, x0=aper_x, x1=aper_x)

            qd_z0 = cell_z + quad_L_f + drift_L_f
            qd_z1 = qd_z0 + quad_L_f
            _tube5(view, qd_z0, qd_z1, fallback_r_pipe * 1.65, _COL_FODO_D, x0=aper_x, x1=aper_x)

        theta_r   = np.linspace(0, 2 * np.pi, 16, endpoint=False)
        ring_step = 1.0

        def _make_ring_grid(z_start, z_end, outer_r):
            pts = []
            r = outer_r * 1.02
            for z_r in np.arange(z_start, z_end + ring_step, ring_step):
                for k in range(len(theta_r)):
                    t1 = theta_r[k]; t2 = theta_r[(k + 1) % len(theta_r)]
                    pts.append([aper_x + r * np.cos(t1), r * np.sin(t1), z_r])
                    pts.append([aper_x + r * np.cos(t2), r * np.sin(t2), z_r])
            for t_ang in [0, np.pi / 2, np.pi, 3 * np.pi / 2]:
                pts.append([aper_x + r * np.cos(t_ang), r * np.sin(t_ang), z_start])
                pts.append([aper_x + r * np.cos(t_ang), r * np.sin(t_ang), z_end])
            return np.array(pts, dtype=np.float32)

        Line(pos=_make_ring_grid(ms_start, ms_end, match_r),
             connect='segments', color=_COL_PIPE_WIRE, parent=view.scene)

        Line(pos=_make_ring_grid(fodo_start, fodo_end, fallback_r_pipe),
             connect='segments', color=_COL_PIPE_WIRE, parent=view.scene)

        metadata.update({
            "is_three_zone": True,
            "chamber_L":     chamber_L,
            "fodo_start":    fodo_start,
            "fodo_end":      fodo_end,
        })

    else:
        pipe_start = horn_length
        _tube5(view, pipe_start, 1000.0, fallback_r_pipe, _COL_PIPE)

        ring_r   = fallback_r_pipe * 1.02
        ring_zs  = np.arange(pipe_start, 1000.0, 1.0)
        theta_r  = np.linspace(0, 2 * np.pi, 16, endpoint=False)
        grid_pts = []
        for z_r in ring_zs:
            for k in range(len(theta_r)):
                t1 = theta_r[k]
                t2 = theta_r[(k + 1) % len(theta_r)]
                grid_pts.append([ring_r * np.cos(t1), ring_r * np.sin(t1), z_r])
                grid_pts.append([ring_r * np.cos(t2), ring_r * np.sin(t2), z_r])
        for t_ang in [0, np.pi / 2, np.pi, 3 * np.pi / 2]:
            grid_pts.append([ring_r * np.cos(t_ang), ring_r * np.sin(t_ang), pipe_start])
            grid_pts.append([ring_r * np.cos(t_ang), ring_r * np.sin(t_ang), 1000.0])
        grid_pts = np.array(grid_pts, dtype=np.float32)
        Line(pos=grid_pts, connect='segments',
             color=_COL_PIPE_WIRE, parent=view.scene)

        _box_at(view,
                width=c_width, height=c_width, depth=c_length,
                cx=0.0, cy=0.0, cz=0.0,
                color=(0.05, 0.10, 0.15, 0.15),
                edge_color=(0.30, 0.50, 0.70, 0.80))

        metadata.update({"is_three_zone": False})

    return metadata


# ---------------------------------------------------------------------------
# Renderer entry point
# ---------------------------------------------------------------------------

def run_renderer(shared_mem_name, sync_queue, stop_event, N, W,
                 annihilation_queue, r_pipe=0.05,
                 raw_data=None, env_data=None, charges=None):
    """
    Runs the VisPy rendering window in a separate process.

    Parameters
    ----------
    raw_data  : dict  — full parsed config.json (all zones)
    env_data  : dict  — Geant4 environment geometry overrides
    charges   : np.ndarray of int8, shape (N,), values {-1, +1}
                Assigned once at startup; drives per-species colours.
    """
    if raw_data  is None: raw_data  = {}
    if env_data  is None: env_data  = {}
    if charges   is None: charges   = np.full(N, -1, dtype=np.int8)

    # Re-attach to shared memory
    shm          = SharedMemory(name=shared_mem_name)
    buffer_shape = (2, N, 3)
    shared_array = np.ndarray(buffer_shape, dtype=np.float32, buffer=shm.buf)

    # Ring buffer for motion trails
    trail_positions = np.zeros((W, N, 3), dtype=np.float32)
    current_head    = 0

    # ── Pre-build per-species base colour arrays (static, assigned once) ─
    # Shape: (N, 3) — RGB only; alpha added per frame
    base_rgb = np.zeros((N, 3), dtype=np.float32)
    pbar_mask = charges == -1
    prot_mask = charges == +1
    total_pbar = int(np.sum(pbar_mask))
    base_rgb[pbar_mask] = _COL_ANTIPROTON
    base_rgb[prot_mask] = _COL_PROTON

    # Pre-allocated flat colour buffer for the trail markers
    flat_colors = np.zeros((W * N, 4), dtype=np.float32)

    # ── VisPy canvas ─────────────────────────────────────────────────────
    canvas = scene.SceneCanvas(
        keys='interactive', show=True,
        title="Janus — Antimatter Transport Pipeline",
        vsync=True
    )
    view = canvas.central_widget.add_view()
    view.camera = scene.TurntableCamera(up='y', distance=4.0, center=(0.0, 0.0, 5.0))

    # ── Build static scene geometry ───────────────────────────────────────
    geo = _build_scene(view, canvas, r_pipe, raw_data, env_data)

    # Particle markers (instantiated after scene geometry to render on top)
    markers = scene.visuals.Markers(parent=view.scene)

    # Annihilation burst markers
    explosion_markers = scene.visuals.Markers(parent=view.scene)
    explosion_markers.set_gl_state('translucent', depth_test=False)
    active_bursts = []

    # ── HUD ───────────────────────────────────────────────────────────────
    hud_text = Text('', parent=canvas.scene, color='white', bold=True, font_size=14)
    hud_text.pos = canvas.size[0] // 2, 24

    @canvas.events.resize.connect
    def on_resize(event):
        hud_text.pos = event.physical_size[0] // 2, 24

    # ── Timer callback (runs at ~60 FPS) ──────────────────────────────────
    def on_timer(event):
        nonlocal current_head, active_bursts

        if stop_event.is_set():
            canvas.close()
            return

        # ── Annihilation bursts ───────────────────────────────────────────
        while True:
            try:
                coord    = annihilation_queue.get_nowait()
                n_sparks = 5
                phi      = np.random.uniform(0, 2 * np.pi, n_sparks)
                cos_th   = np.random.uniform(-1, 1, n_sparks)
                u        = np.random.uniform(0, 1, n_sparks)
                sin_th   = np.sqrt(1 - cos_th**2)
                r_spark  = 0.005 * np.cbrt(u)
                vel      = np.column_stack([
                    r_spark * sin_th * np.cos(phi),
                    r_spark * sin_th * np.sin(phi),
                    r_spark * cos_th
                ]).astype(np.float32)
                pos = np.tile(coord, (n_sparks, 1)).astype(np.float32)
                active_bursts.append({'pos': pos, 'vel': vel,
                                      'age': 0, 'max_age': 60})
            except mp.queues.Empty:
                break

        # Update and render bursts
        exp_pos, exp_col, alive_b = [], [], []
        for burst in active_bursts:
            burst['pos'] += burst['vel']
            burst['age'] += 1
            if burst['age'] < burst['max_age']:
                alive_b.append(burst)
                exp_pos.append(burst['pos'])
                alpha = 0.5 * (1.0 - burst['age'] / burst['max_age'])
                exp_col.append(np.full((len(burst['pos']), 4),
                                       [0.5, 0.1, 0.3, alpha], dtype=np.float32))
        active_bursts[:] = alive_b
        if exp_pos:
            explosion_markers.set_data(
                pos=np.concatenate(exp_pos),
                face_color=np.concatenate(exp_col),
                edge_color=None, size=10.0)
        else:
            explosion_markers.set_data(pos=np.empty((0, 3), dtype=np.float32))

        # ── Drain sync queue to get latest frame ─────────────────────────
        latest_idx = None
        while True:
            try:
                latest_idx = sync_queue.get_nowait()
            except mp.queues.Empty:
                break

        if latest_idx is not None:
            new_positions = shared_array[latest_idx].copy()
            trail_positions[current_head] = new_positions

            # Rebuild colour buffer per trail age, preserving species hue
            for age in range(W):
                idx   = (current_head - age) % W
                alpha = max(0.0, 1.0 - float(age) / W)

                flat_colors[idx * N: (idx + 1) * N, :3] = base_rgb
                flat_colors[idx * N: (idx + 1) * N,  3] = alpha

            markers.set_data(
                pos        = trail_positions.reshape(-1, 3),
                face_color = flat_colors,
                edge_color = None,
                size       = 7.0
            )
            current_head = (current_head + 1) % W

            # Camera tracking: follow beam centroid
            if not np.all(np.isnan(new_positions[:, 2])):
                center_z = float(np.nanmean(new_positions[:, 2]))
                view.camera.center = (0.0, 0.0, center_z)

                current_N   = int(np.sum(~np.isnan(new_positions[:, 2])))
                n_pbar_live = int(np.sum(~np.isnan(new_positions[pbar_mask, 2])))
                n_prot_live = int(np.sum(~np.isnan(new_positions[prot_mask, 2])))
                
                # Calculate p-bar specific survival rate safely
                pbar_survival = (n_pbar_live / total_pbar * 100.0) if total_pbar > 0 else 0.0

                hud_text.text = (
                    f"Distance: {center_z:.2f} m   |   "
                    f"p-bar Alive: {n_pbar_live}/{total_pbar} ({pbar_survival:.1f}%)   |   "
                    f"p Alive: {n_prot_live}"
                )

    timer = vispy.app.Timer('auto', connect=on_timer, start=True)

    try:
        print("[Renderer] Starting VisPy application (PyQt5 backend)…")
        vispy.app.run()
    finally:
        shm.close()
        stop_event.set()
        print("[Renderer] VisPy window closed.")