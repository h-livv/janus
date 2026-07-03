import sys
import os
import numpy as np
import multiprocessing as mp
from multiprocessing.shared_memory import SharedMemory

# Ensure start method is spawn for VisPy/PyQt5 compatibility
if __name__ == "__main__":
    try:
        mp.set_start_method('spawn', force=True)
    except RuntimeError:
        pass

# ── Settings ───────────────────────────────────────────────────────────────
VISUALIZE = True               # True: 3D viewport; False: headless transport + validation
ELEMENT_TYPE = "dipole"          # Options: "drift", "dipole", "all"
USE_MOCK_DATA = False           # True: tame mock coordinates/velocities

Z_START = 0.0
APERTURE_RADIUS = 100.0

# Drift element
DRIFT_LENGTH = 100.0
DRIFT_DT = 1e-10
DRIFT_MAX_STEPS = 500
DRIFT_MAX_STEPS_CONV = 300

# Dipole element
DIPOLE_LENGTH = 1000.0
DIPOLE_BY = 0.5
DIPOLE_DT = 1e-10
DIPOLE_MAX_STEPS = 500
DIPOLE_MAX_STEPS_CONV = 150

# Mock transport parameters
MOCK_DT = 1e-8
MOCK_MAX_STEPS = 150
MOCK_MAX_STEPS_CONV = 80
MOCK_R_INIT = np.array([[-4.5, 0.0, 25.0]], dtype=np.float64)
MOCK_V_INIT = np.array([[0.0, 0.0, 5000000.0]], dtype=np.float64)
MOCK_GAMMA_INIT = np.array([1.0], dtype=np.float64)
MOCK_CHARGES = np.array([-1], dtype=np.int8)

# Visualization beam
VIS_BEAM_N = 1000
VIS_BEAM_POS_SIGMA = 0.15
VIS_BEAM_VEL_SIGMA_MOCK = 1.5
VIS_BEAM_VEL_SIGMA_REAL = 1.5e6
VIS_BEAM_RNG_SEED = 42
VIS_TRAIL_LENGTH = 200
# ───────────────────────────────────────────────────────────────────────────


def build_config(case_type):
    from transport.simulation_config import build_simulation_config

    return build_simulation_config(
        case_type,
        USE_MOCK_DATA,
        z_start=Z_START,
        aperture_radius=APERTURE_RADIUS,
        drift_length=DRIFT_LENGTH,
        drift_dt=DRIFT_DT,
        drift_max_steps=DRIFT_MAX_STEPS,
        drift_max_steps_conv=DRIFT_MAX_STEPS_CONV,
        dipole_length=DIPOLE_LENGTH,
        dipole_by=DIPOLE_BY,
        dipole_dt=DIPOLE_DT,
        dipole_max_steps=DIPOLE_MAX_STEPS,
        dipole_max_steps_conv=DIPOLE_MAX_STEPS_CONV,
        mock_dt=MOCK_DT,
        mock_max_steps=MOCK_MAX_STEPS,
        mock_max_steps_conv=MOCK_MAX_STEPS_CONV,
        mock_r_init=MOCK_R_INIT,
        mock_v_init=MOCK_V_INIT,
        mock_gamma_init=MOCK_GAMMA_INIT,
        mock_charges=MOCK_CHARGES,
    )


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    if VISUALIZE:
        if ELEMENT_TYPE.lower() not in ("drift", "dipole"):
            print(f"[-] Error: ELEMENT_TYPE must be 'drift' or 'dipole' to visualize.")
            sys.exit(1)

        print(f"[Main] Visualization enabled. Launching 3D Viewport for: {ELEMENT_TYPE}...")
        from transport.visualization.viewport import run_renderer
        from transport.physics.boris_solver import run_visual_physics_loop
        from transport.simulation_config import expand_beam

        config = build_config(ELEMENT_TYPE.lower())
        if len(config.R_init) == 1:
            vel_sigma = VIS_BEAM_VEL_SIGMA_MOCK if USE_MOCK_DATA else VIS_BEAM_VEL_SIGMA_REAL
            R_beam, V_beam, gamma_beam, charges_beam = expand_beam(
                config,
                VIS_BEAM_N,
                VIS_BEAM_POS_SIGMA,
                vel_sigma,
                VIS_BEAM_RNG_SEED,
            )
        else:
            R_beam = config.R_init.copy()
            V_beam = config.V_init.copy()
            gamma_beam = config.gamma_init.copy()
            charges_beam = config.charges.copy()
        N = len(R_beam)

        buffer_bytes = 2 * N * 3 * 4
        shm = SharedMemory(create=True, size=buffer_bytes)
        shared_mem_name = shm.name
        sync_queue = mp.Queue(maxsize=5)
        stop_event = mp.Event()

        physics_proc = mp.Process(
            target=run_visual_physics_loop,
            args=(R_beam, V_beam, gamma_beam, charges_beam, config.lattice, config.dt,
                  shared_mem_name, sync_queue, stop_event),
        )
        renderer_proc = mp.Process(
            target=run_renderer,
            args=(shared_mem_name, sync_queue, stop_event, N, VIS_TRAIL_LENGTH,
                  config.lattice, charges_beam, None),
        )

        try:
            physics_proc.start()
            renderer_proc.start()
            renderer_proc.join()
            stop_event.set()
            physics_proc.join(timeout=2.0)
            if physics_proc.is_alive():
                physics_proc.terminate()
        except KeyboardInterrupt:
            stop_event.set()
            renderer_proc.terminate()
            physics_proc.terminate()
        finally:
            shm.close()
            shm.unlink()
        return

    print("[Main] Visualization disabled. Running headless transport...")
    from transport.pipeline import run_headless_suite

    case_types = []
    if ELEMENT_TYPE.lower() in ("drift", "all"):
        case_types.append("drift")
    if ELEMENT_TYPE.lower() in ("dipole", "all"):
        case_types.append("dipole")
    if not case_types:
        print(f"[-] Error: Unknown ELEMENT_TYPE '{ELEMENT_TYPE}'")
        sys.exit(1)

    overall_passed, _ = run_headless_suite(case_types, build_config)
    if overall_passed:
        print("\nSTATUS: PASS")
        sys.exit(0)
    else:
        print("\nSTATUS: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
