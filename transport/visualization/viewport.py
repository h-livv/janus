import numpy as np
import multiprocessing as mp
from multiprocessing.shared_memory import SharedMemory

import vispy
vispy.use("PyQt5")
from vispy import scene
from vispy.scene.visuals import Text

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

    trail_positions = np.full((W, N, 3), np.nan, dtype=np.float32)
    current_head = 0

    base_rgb = np.zeros((N, 3), dtype=np.float32)
    pbar_mask = charges == -1
    prot_mask = charges == +1
    total_pbar = int(np.sum(pbar_mask))
    base_rgb[pbar_mask] = _COL_ANTIPROTON
    base_rgb[prot_mask] = _COL_PROTON

    alphas = np.exp(-np.linspace(50.0, 0.0, W)).astype(np.float32)
    alphas /= alphas.max()

    trail_colors = np.empty((W, N, 4), dtype=np.float32)

    for age in range(W):
        trail_colors[age, :, :3] = base_rgb
        trail_colors[age, :, 3] = alphas[age]

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

    markers = scene.visuals.Markers(parent=view.scene)
    markers.set_gl_state(
    blend=True,
    depth_test=False,
    blend_func=("src_alpha", "one_minus_src_alpha"),
)
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

        ordered_positions = np.concatenate(
            (
                trail_positions[current_head + 1:],
                trail_positions[:current_head + 1],
            ),
            axis=0,
        )


        flat_pos = ordered_positions.reshape(-1, 3)

        flat_colors = trail_colors.reshape(-1, 4)

        '''for age in range(W):
            start = age * N
            end = (age + 1) * N

            flat_colors[start:end, :3] = base_rgb
            flat_colors[start:end, 3] = alphas[age]'''

        valid = ~np.isnan(flat_pos).any(axis=1)

        if np.any(valid):
            markers.set_data(
                pos=flat_pos[valid],
                face_color=flat_colors[valid],
                edge_color=None,
                size=10.0,
            )
        else:
            markers.set_data(pos=np.empty((0, 3), dtype=np.float32))

        current_head = (current_head + 1) % W

        live_mask = ~np.isnan(new_positions).any(axis=1)
        if np.any(live_mask):
            center_z = float(np.nanmean(new_positions[live_mask, 2]))
            view.camera.center = (0.0, 0.0, center_z)
            n_pbar_live = int(np.sum(live_mask & pbar_mask))
            pbar_survival = (n_pbar_live / total_pbar * 100.0) if total_pbar > 0 else 0.0
            hud_text.text = (
                f"Distance: {center_z:.2f} m   |   "
                f"p-bar Alive: {n_pbar_live}/{total_pbar} ({pbar_survival:.1f}%)"
            )

    timer = vispy.app.Timer("auto", connect=on_timer, start=True)

    try:
        print("[Renderer] Starting VisPy application (PyQt5 backend)…")
        vispy.app.run()
    finally:
        shm.close()
        stop_event.set()
        print("[Renderer] VisPy window closed.")