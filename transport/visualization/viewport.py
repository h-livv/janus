import numpy as np
import multiprocessing as mp
from multiprocessing.shared_memory import SharedMemory

import vispy
vispy.use("PyQt5")
from vispy import scene
from vispy.scene.visuals import Text, Line

_COL_ANTIPROTON = np.array([0.00, 0.80, 1.00])
_COL_PROTON = np.array([1.00, 0.18, 0.08])


def run_renderer(shared_mem_name, sync_queue, stop_event, N, W, lattice,
                 charges=None, elements=None):
    """
    Passive VisPy renderer. Geometry comes from the lattice; particle state
    comes from the transport engine via shared memory.
    """
    if charges is None:
        charges = np.full(N, -1, dtype=np.int8)

    shm = SharedMemory(name=shared_mem_name)
    shared_array = np.ndarray((2, N, 3), dtype=np.float32, buffer=shm.buf)

    trail_positions = np.zeros((W, N, 3), dtype=np.float32)
    current_head = 0

    base_rgb = np.zeros((N, 3), dtype=np.float32)
    pbar_mask = charges == -1
    prot_mask = charges == +1
    total_pbar = int(np.sum(pbar_mask))
    base_rgb[pbar_mask] = _COL_ANTIPROTON
    base_rgb[prot_mask] = _COL_PROTON

    canvas = scene.SceneCanvas(
        keys="interactive",
        show=True,
        title="Janus — Antimatter Transport Pipeline",
        vsync=True,
    )
    view = canvas.central_widget.add_view()
    center_z = lattice.z_start + 0.5 * lattice.total_length
    view.camera = scene.TurntableCamera(
        up="y",
        distance=max(4.0, lattice.total_length * 0.8),
        center=(0.0, 0.0, center_z),
    )

    lattice.draw(view, elements=elements)

    trail_lines = [
        Line(parent=view.scene, connect="strip", width=1.5, antialias=True)
        for _ in range(N)
    ]
    markers = scene.visuals.Markers(parent=view.scene)
    hud_text = Text("", parent=canvas.scene, color="white", bold=True, font_size=14)
    hud_text.pos = canvas.size[0] // 2, 24

    @canvas.events.resize.connect
    def on_resize(event):
        hud_text.pos = event.physical_size[0] // 2, 24

    def on_timer(event):
        nonlocal current_head

        if stop_event.is_set():
            canvas.close()
            return

        latest_idx = None
        while True:
            try:
                latest_idx = sync_queue.get_nowait()
            except mp.queues.Empty:
                break

        if latest_idx is None:
            return

        new_positions = shared_array[latest_idx].copy()
        trail_positions[current_head] = new_positions

        for p in range(N):
            pts = []
            cols = []
            for age in range(W - 1, -1, -1):
                slot = (current_head - age) % W
                pos = trail_positions[slot, p]
                if np.isnan(pos).any():
                    continue
                alpha = max(0.08, 1.0 - float(age) / W)
                pts.append(pos)
                cols.append([base_rgb[p, 0], base_rgb[p, 1], base_rgb[p, 2], alpha])
            if len(pts) >= 2:
                trail_lines[p].set_data(pos=np.array(pts, dtype=np.float32),
                                        color=np.array(cols, dtype=np.float32))
                trail_lines[p].visible = True
            else:
                trail_lines[p].visible = False

        live_mask = ~np.isnan(new_positions).any(axis=1)
        if np.any(live_mask):
            markers.set_data(
                pos=new_positions[live_mask],
                face_color=base_rgb[live_mask],
                edge_color=None,
                size=7.0,
            )
        else:
            markers.set_data(pos=np.empty((0, 3), dtype=np.float32))

        current_head = (current_head + 1) % W

        if np.any(live_mask):
            center_z = float(np.nanmean(new_positions[live_mask, 2]))
            view.camera.center = (0.0, 0.0, center_z)
            n_pbar_live = int(np.sum(live_mask & pbar_mask))
            n_prot_live = int(np.sum(live_mask & prot_mask))
            pbar_survival = (n_pbar_live / total_pbar * 100.0) if total_pbar > 0 else 0.0
            hud_text.text = (
                f"Distance: {center_z:.2f} m   |   "
                f"p-bar Alive: {n_pbar_live}/{total_pbar} ({pbar_survival:.1f}%)   "
                #f"p Alive: {n_prot_live}"
            )

    vispy.app.Timer("auto", connect=on_timer, start=True)

    try:
        print("[Renderer] Starting VisPy application (PyQt5 backend)…")
        vispy.app.run()
    finally:
        shm.close()
        stop_event.set()
        print("[Renderer] VisPy window closed.")
