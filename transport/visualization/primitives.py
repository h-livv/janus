import numpy as np
from vispy.scene.visuals import Box, Tube, Line
from vispy.visuals.transforms import MatrixTransform

COL_PIPE = (0.05, 0.10, 0.15, 0.30)
COL_PIPE_WIRE = (0.20, 0.40, 0.60, 0.80)
COL_DIPOLE_FIELD = (0.30, 0.00, 0.80, 0.10)
COL_QUADRUPOLE_FIELD = (0.30, 0.00, 0.80, 0.10)
COL_DRIFT = (0.04, 0.12, 0.22, 0.12)
COL_APERTURE = (0.00, 1.00, 0.50, 1.00)


def tube_segment(view, z0, z1, radius, color, x0=0.0, y0=0.0, x1=None, y1=None):
    if x1 is None:
        x1 = x0
    if y1 is None:
        y1 = y0
    pts = np.zeros((5, 3), dtype=np.float32)
    pts[:, 0] = np.linspace(x0, x1, 5)
    pts[:, 1] = np.linspace(y0, y1, 5)
    pts[:, 2] = np.linspace(z0, z1, 5)
    tube = Tube(points=pts, radius=radius, closed=False, color=color, parent=view.scene)
    if len(color) > 3 and color[3] < 1.0:
        tube.set_gl_state("translucent", depth_mask=False)
    return tube


def ring(view, cx, cy, cz, radius, color, n=40):
    theta = np.linspace(0, 2 * np.pi, n + 1, endpoint=True)
    pts = np.column_stack([
        cx + radius * np.cos(theta),
        cy + radius * np.sin(theta),
        np.full(n + 1, cz, dtype=np.float32),
    ]).astype(np.float32)
    return Line(pos=pts, connect="strip", color=color, parent=view.scene)


def box_at(view, width, height, depth, cx, cy, cz, color, edge_color):
    box = Box(
        width=width,
        height=depth,
        depth=height,
        color=color,
        edge_color=edge_color,
        parent=view.scene,
    )
    box.transform = MatrixTransform()
    box.transform.translate((cx, cy, cz))
    if len(color) > 3 and color[3] < 1.0:
        box.set_gl_state("translucent", depth_mask=False)
    return box


def draw_pipe_wireframe(view, z0, z1, radius, step=0.5):
    ring_r = radius * 1.02
    theta = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    segments = []
    for z in np.arange(z0, z1 + step, step):
        for k in range(len(theta)):
            t1 = theta[k]
            t2 = theta[(k + 1) % len(theta)]
            segments.append([ring_r * np.cos(t1), ring_r * np.sin(t1), z])
            segments.append([ring_r * np.cos(t2), ring_r * np.sin(t2), z])
    if segments:
        Line(
            pos=np.array(segments, dtype=np.float32),
            connect="segments",
            color=COL_PIPE_WIRE,
            parent=view.scene,
        )


def draw_aperture_rings(view, z0, z1, radius, cx=0.0, cy=0.0):
    ring(view, cx, cy, z0, radius, COL_APERTURE)
    ring(view, cx, cy, z1, radius, COL_APERTURE)
