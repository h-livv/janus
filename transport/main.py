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
USE_MOCK_DATA = True           # True: tame mock coordinates/velocities

Z_START = 0.0
APERTURE_RADIUS = 10.0

# Drift element
DRIFT_LENGTH = 10.0
DRIFT_DT = 1e-6
DRIFT_MAX_STEPS = 500
DRIFT_MAX_STEPS_CONV = 300

# Dipole element
DIPOLE_LENGTH = 100.0
DIPOLE_BY = 0.01
DIPOLE_DT = 1e-10
DIPOLE_MAX_STEPS = 500
DIPOLE_MAX_STEPS_CONV = 150

# Mock transport parameters
MOCK_DT = 1e-8
MOCK_MAX_STEPS = 150
MOCK_MAX_STEPS_CONV = 80
MOCK_R_INIT = np.array([[0.0, 0.0, 10.0]], dtype=np.float64)
MOCK_V_INIT = np.array([[0.0, 0.0, 2000000.0]], dtype=np.float64)
MOCK_GAMMA_INIT = np.array([1.0], dtype=np.float64)
MOCK_CHARGES = np.array([-1], dtype=np.int8)

# Visualization beam
VIS_BEAM_N = 100
VIS_BEAM_POS_SIGMA = 0.15
VIS_BEAM_VEL_SIGMA_MOCK = 1.5
VIS_BEAM_VEL_SIGMA_REAL = 1.5e6
VIS_BEAM_RNG_SEED = 42
VIS_TRAIL_LENGTH = 150
# ───────────────────────────────────────────────────────────────────────────

C_LIGHT = 299792458.0
E_CHARGE = 1.602176634e-19
M_P_KG = 1.67262192369e-27


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from transport.lattice.lattice import SimpleLattice, Drift, Dipole
    from transport.physics.boris_solver import track_particles

    if VISUALIZE:
        if ELEMENT_TYPE.lower() not in ("drift", "dipole"):
            print(f"[-] Error: ELEMENT_TYPE must be 'drift' or 'dipole' to visualize.")
            sys.exit(1)

        print(f"[Main] Visualization enabled. Launching 3D Viewport for: {ELEMENT_TYPE}...")
        from transport.visualization.viewport import run_renderer
        from transport.physics.boris_solver import run_visual_physics_loop

        element_type = ELEMENT_TYPE.lower()
        if element_type == "drift":
            lattice = SimpleLattice(
                [Drift(DRIFT_LENGTH, aperture_radius=APERTURE_RADIUS)],
                z_start=Z_START,
            )
            dt = MOCK_DT if USE_MOCK_DATA else DRIFT_DT
        else:
            lattice = SimpleLattice(
                [Dipole(DIPOLE_LENGTH, DIPOLE_BY, aperture_radius=APERTURE_RADIUS)],
                z_start=Z_START,
            )
            dt = MOCK_DT if USE_MOCK_DATA else DIPOLE_DT

        if USE_MOCK_DATA:
            R_init = MOCK_R_INIT.copy()
            V_init = MOCK_V_INIT.copy()
            gamma_init = MOCK_GAMMA_INIT.copy()
            charges = MOCK_CHARGES.copy()
        else:
            from transport.io.data_io import get_latest_run_file, extract_cern_ad_seeds

            latest_file = get_latest_run_file(
                outputs_dir_name="runs", target_filename="simulation.root"
            )
            R, V, gamma, all_charges = extract_cern_ad_seeds([latest_file])
            if element_type == "dipole":
                mask = all_charges == -1
                if not np.any(mask):
                    mask = all_charges == 1
                if not np.any(mask):
                    raise ValueError("No charged particles found in simulation.root")
                idx = np.where(mask)[0][0]
            else:
                idx = 0
            R_init = R[idx:idx + 1].astype(np.float64)
            V_init = V[idx:idx + 1].astype(np.float64)
            gamma_init = gamma[idx:idx + 1].astype(np.float64)
            charges = all_charges[idx:idx + 1]

        N = VIS_BEAM_N
        R_beam = np.tile(R_init, (N, 1))
        V_beam = np.tile(V_init, (N, 1))
        rng = np.random.default_rng(VIS_BEAM_RNG_SEED)
        R_beam[:, 0] += rng.normal(0.0, VIS_BEAM_POS_SIGMA, N)
        R_beam[:, 1] += rng.normal(0.0, VIS_BEAM_POS_SIGMA, N)
        if USE_MOCK_DATA:
            V_beam[:, 0] += rng.normal(0.0, VIS_BEAM_VEL_SIGMA_MOCK, N)
            V_beam[:, 1] += rng.normal(0.0, VIS_BEAM_VEL_SIGMA_MOCK, N)
        else:
            V_beam[:, 0] += rng.normal(0.0, VIS_BEAM_VEL_SIGMA_REAL, N)
            V_beam[:, 1] += rng.normal(0.0, VIS_BEAM_VEL_SIGMA_REAL, N)

        charges_beam = np.tile(charges, N)
        gamma_beam = np.tile(gamma_init, N)

        buffer_bytes = 2 * N * 3 * 4
        shm = SharedMemory(create=True, size=buffer_bytes)
        shared_mem_name = shm.name
        sync_queue = mp.Queue(maxsize=5)
        stop_event = mp.Event()

        physics_proc = mp.Process(
            target=run_visual_physics_loop,
            args=(R_beam, V_beam, gamma_beam, charges_beam, lattice, dt,
                  shared_mem_name, sync_queue, stop_event),
        )
        renderer_proc = mp.Process(
            target=run_renderer,
            args=(shared_mem_name, sync_queue, stop_event, N, VIS_TRAIL_LENGTH,
                  lattice, charges_beam, None),
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
    from transport.validation.validator import Validator
    from transport.validation.cases.drift import DriftValidation
    from transport.validation.cases.dipole import DipoleValidation

    case_types = []
    if ELEMENT_TYPE.lower() in ("drift", "all"):
        case_types.append("drift")
    if ELEMENT_TYPE.lower() in ("dipole", "all"):
        case_types.append("dipole")
    if not case_types:
        print(f"[-] Error: Unknown ELEMENT_TYPE '{ELEMENT_TYPE}'")
        sys.exit(1)

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_outputs_dir = os.path.join("transport", "validation", "outputs", f"run_{timestamp}")
    print(f"[Validator] Outputs for this run will be saved in: {run_outputs_dir}\n")

    overall_passed = True
    for case_type in case_types:
        if case_type == "drift":
            validation_case = DriftValidation()
            validation_case.aperture_radius = APERTURE_RADIUS
            lattice = SimpleLattice(
                [Drift(DRIFT_LENGTH, aperture_radius=APERTURE_RADIUS)],
                z_start=Z_START,
            )
            dt = MOCK_DT if USE_MOCK_DATA else DRIFT_DT
            max_steps = MOCK_MAX_STEPS if USE_MOCK_DATA else DRIFT_MAX_STEPS
            max_steps_conv = MOCK_MAX_STEPS_CONV if USE_MOCK_DATA else DRIFT_MAX_STEPS_CONV
        else:
            validation_case = DipoleValidation()
            validation_case.aperture_radius = APERTURE_RADIUS
            lattice = SimpleLattice(
                [Dipole(DIPOLE_LENGTH, DIPOLE_BY, aperture_radius=APERTURE_RADIUS)],
                z_start=Z_START,
            )
            dt = MOCK_DT if USE_MOCK_DATA else DIPOLE_DT
            max_steps = MOCK_MAX_STEPS if USE_MOCK_DATA else DIPOLE_MAX_STEPS
            max_steps_conv = MOCK_MAX_STEPS_CONV if USE_MOCK_DATA else DIPOLE_MAX_STEPS_CONV

        if USE_MOCK_DATA:
            R_init = MOCK_R_INIT.copy()
            V_init = MOCK_V_INIT.copy()
            gamma_init = MOCK_GAMMA_INIT.copy()
            charges = MOCK_CHARGES.copy()
            validation_case.z_start = Z_START
            validation_case.v_mag = float(np.linalg.norm(V_init[0]))
            validation_case.gamma = float(gamma_init[0])
            if case_type == "dipole":
                validation_case.charge = int(charges[0])
                validation_case.theta_entry = 0.0
                validation_case.B_rho = (1.0 * M_P_KG * validation_case.v_mag) / E_CHARGE
        else:
            from transport.io.data_io import get_latest_run_file, extract_cern_ad_seeds

            latest_file = get_latest_run_file(
                outputs_dir_name="runs", target_filename="simulation.root"
            )
            R, V, gamma, all_charges = extract_cern_ad_seeds([latest_file])
            if case_type == "dipole":
                mask = all_charges == -1
                if not np.any(mask):
                    mask = all_charges == 1
                if not np.any(mask):
                    raise ValueError("No charged particles found in simulation.root")
                idx = np.where(mask)[0][0]
            else:
                idx = 0
            R_init = R[idx:idx + 1].astype(np.float64)
            V_init = V[idx:idx + 1].astype(np.float64)
            gamma_init = gamma[idx:idx + 1].astype(np.float64)
            charges = all_charges[idx:idx + 1]

            z_start = float(R_init[0, 2])
            lattice = SimpleLattice(
                [Drift(DRIFT_LENGTH, aperture_radius=APERTURE_RADIUS)]
                if case_type == "drift"
                else [Dipole(DIPOLE_LENGTH, DIPOLE_BY, aperture_radius=APERTURE_RADIUS)],
                z_start=z_start,
            )
            validation_case.z_start = z_start
            validation_case.v_mag = float(np.linalg.norm(V_init[0]))
            validation_case.gamma = float(
                1.0 / np.sqrt(1.0 - (validation_case.v_mag / C_LIGHT) ** 2)
            )
            if case_type == "dipole":
                v_perp = float(np.sqrt(V_init[0, 0] ** 2 + V_init[0, 2] ** 2))
                validation_case.B_rho = validation_case.gamma * M_P_KG * v_perp / E_CHARGE
                validation_case.theta_entry = float(
                    np.arctan2(V_init[0, 0], V_init[0, 2])
                )
                validation_case.charge = int(charges[0])

        validation_case.dt = dt
        validation_case.max_steps = max_steps
        validation_case.max_steps_conv = max_steps_conv

        _, _, _, diagnostics = track_particles(
            R_init, V_init, gamma_init, charges, lattice, dt, max_steps
        )

        case_name = validation_case.name.lower().replace("validation", "")
        case_dir = os.path.join(run_outputs_dir, case_name)
        os.makedirs(case_dir, exist_ok=True)
        report_file_path = os.path.join(case_dir, "report.txt")

        passed, metrics, report = Validator.run(
            validation_case,
            dt,
            max_steps,
            run_outputs_dir=run_outputs_dir,
            diagnostics=diagnostics,
            lattice=lattice,
            R_init=R_init,
        )
        print(report)
        print()
        if not passed:
            overall_passed = False

        with open(report_file_path, "w") as f:
            f.write(report)
            f.write("\n\n")

        converged, errors, report_conv = Validator.run_convergence(
            validation_case, dt, max_steps_conv, run_outputs_dir=run_outputs_dir
        )
        print(report_conv)
        print()
        if not converged:
            overall_passed = False

        with open(report_file_path, "a") as f:
            f.write(report_conv)

        print("-" * 60)

    if overall_passed:
        print("\nSTATUS: PASS")
        sys.exit(0)
    else:
        print("\nSTATUS: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
