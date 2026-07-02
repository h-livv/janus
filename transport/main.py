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
VISUALIZATION_ENABLED = True  # Toggle to True to launch 3D OpenGL Viewport
ELEMENT_TYPE = "dipole"          # Options: "drift", "dipole", "all"
USE_MOCK_DATA = True         # Toggle to True to use tame mock coordinates/velocities
# ───────────────────────────────────────────────────────────────────────────

def main():
    # Inject project root to sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    if not VISUALIZATION_ENABLED:
        print("[Main] Visualization disabled. Carrying out validation tests normally...")
        from transport.validation.validator import Validator
        from transport.validation.cases.drift import DriftValidation
        from transport.validation.cases.dipole import DipoleValidation

        cases = []
        if ELEMENT_TYPE.lower() in ["drift", "all"]:
            cases.append(DriftValidation())
        if ELEMENT_TYPE.lower() in ["dipole", "all"]:
            cases.append(DipoleValidation())

        if USE_MOCK_DATA:
            print("[Main] Overriding case parameters with tame mock data...")
            def make_mock_initial_particles(case_instance):
                def mock_initial_particles():
                    R_init = np.array([[0.0, 0.0, 0.0]], dtype=np.float64)
                    V_init = np.array([[0.0, 0.0, 100.0]], dtype=np.float64)
                    gamma_init = np.array([1.0], dtype=np.float64)
                    charges = np.array([-1], dtype=np.int8)
                    
                    # Set essential properties for lattice construction and analytical validation
                    case_instance.z_start = 0.0
                    case_instance.charge = -1
                    case_instance.v_mag = 100.0
                    case_instance.gamma = 1.0
                    case_instance.B_rho = (1.0 * 1.67262192369e-27 * 100.0) / 1.602176634e-19
                    case_instance.theta_entry = 0.0
                    return R_init, V_init, gamma_init, charges
                return mock_initial_particles
            
            for case in cases:
                case.initial_particles = make_mock_initial_particles(case)
                case.dt = 1e-3
                case.max_steps = 150
                case.max_steps_conv = 80

        if not cases:
            print(f"[-] Error: Unknown ELEMENT_TYPE '{ELEMENT_TYPE}'")
            sys.exit(1)

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_outputs_dir = os.path.join("transport", "validation", "outputs", f"run_{timestamp}")
        print(f"[Validator] Outputs for this run will be saved in: {run_outputs_dir}\n")

        overall_passed = True
        for case in cases:
            case_name = case.name.lower().replace("validation", "")
            case_dir = os.path.join(run_outputs_dir, case_name)
            os.makedirs(case_dir, exist_ok=True)
            report_file_path = os.path.join(case_dir, "report.txt")

            passed, metrics, report = Validator.run(case, case.dt, case.max_steps, run_outputs_dir=run_outputs_dir)
            print(report)
            print()
            if not passed:
                overall_passed = False

            with open(report_file_path, "w") as f:
                f.write(report)
                f.write("\n\n")

            converged, errors, report_conv = Validator.run_convergence(case, case.dt, case.max_steps_conv, run_outputs_dir=run_outputs_dir)
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

    else:
        print(f"[Main] Visualization enabled. Launching 3D Viewport for: {ELEMENT_TYPE}...")
        from transport.validation.cases.drift import DriftValidation
        from transport.validation.cases.dipole import DipoleValidation
        from transport.visualization.viewport import run_renderer
        from transport.physics.boris_solver import run_visual_physics_loop

        if ELEMENT_TYPE.lower() == "drift":
            case = DriftValidation()
            raw_data = {}
        elif ELEMENT_TYPE.lower() == "dipole":
            case = DipoleValidation()
            raw_data = {
                "dipole_chamber": {
                    "length": 5.0,
                    "width": 1.0,
                    "height": 1.0,
                    "acceptance_aperture_radius": 0.05,
                    "acceptance_aperture_x_offset": 0.0,
                    "dump": {
                        "length": 0.0,
                        "width": 0.0,
                        "height": 0.0,
                        "position_z": 999.0,
                        "x_offset": 0.0
                    }
                }
            }
            case.aperture_radius = raw_data["dipole_chamber"]["acceptance_aperture_radius"]
        else:
            print(f"[-] Error: ELEMENT_TYPE must be 'drift' or 'dipole' to visualize.")
            sys.exit(1)

        if USE_MOCK_DATA:
            R_init = np.array([[0.0, 0.0, 0.0]], dtype=np.float64)
            V_init = np.array([[0.0, 0.0, 100.0]], dtype=np.float64)
            gamma_init = np.array([1.0], dtype=np.float64)
            charges = np.array([-1], dtype=np.int8)
            dt = 1e-3
        else:
            R_init, V_init, gamma_init, charges = case.initial_particles()
            dt = case.dt

        lattice = case.build_lattice()

        # Build a beam of 100 slightly perturbed particles for visualization
        N = 100
        R_beam = np.tile(R_init, (N, 1))
        V_beam = np.tile(V_init, (N, 1))
        
        # Add slight spatial and velocity perturbations
        rng = np.random.default_rng(42)
        R_beam[:, 0] += rng.normal(0.0, 0.0015, N)
        R_beam[:, 1] += rng.normal(0.0, 0.0015, N)
        if USE_MOCK_DATA:
            V_beam[:, 0] += rng.normal(0.0, 1.5, N)
            V_beam[:, 1] += rng.normal(0.0, 1.5, N)
        else:
            V_beam[:, 0] += rng.normal(0.0, 1.5e6, N)
            V_beam[:, 1] += rng.normal(0.0, 1.5e6, N)
        
        charges_beam = np.tile(charges, N)
        gamma_beam = np.tile(gamma_init, N)

        # Setup shared memory IPC
        buffer_bytes = 2 * N * 3 * 4
        shm = SharedMemory(create=True, size=buffer_bytes)
        shared_mem_name = shm.name

        sync_queue = mp.Queue(maxsize=5)
        annihilation_queue = mp.Queue()
        stop_event = mp.Event()

        # Hide Geant4 environment chamber/target markers to focus on the validation element
        env_data = {
            "chamber_width": "1.0 m",
            "chamber_length": "5.0 m",
            "target_width": "0.0 mm",
            "target_length": "0.0 m",
            "target_position": "0 0 999.0 m"
        }

        # Spawn tracking physics thread and OpenGL renderer thread
        physics_proc = mp.Process(
            target=run_visual_physics_loop,
            args=(R_beam, V_beam, gamma_beam, charges_beam, lattice, dt,
                  shared_mem_name, sync_queue, stop_event)
        )

        renderer_proc = mp.Process(
            target=run_renderer,
            args=(shared_mem_name, sync_queue, stop_event, N, 1,
                  annihilation_queue, 0.05, raw_data, env_data, charges_beam)
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

if __name__ == "__main__":
    main()
