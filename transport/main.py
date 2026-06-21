import os
import sys
import json
import os
os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import numpy as np
import multiprocessing as mp
from multiprocessing.shared_memory import SharedMemory

from transport.dependencies.lattice import Lattice
from transport.dependencies.data_io import extract_cern_ad_seeds

def main():
    parser = argparse.ArgumentParser(description="Janus Visualization Pipeline")
    default_config = os.path.join(os.path.dirname(__file__), "config.json")
    parser.add_argument('--config', type=str, default=default_config, help='Path to JSON lattice configuration')
    args = parser.parse_args()

    print(f"[Main] Initializing Janus Pipeline with config: {args.config}")

    # 1. Load Configuration & Validate
    try:
        # Load raw JSON to preserve full structural context for the visual renderer
        with open(args.config, 'r') as f:
            raw_data = json.load(f)

        machine, config_dict = Lattice.load_from_json(args.config)
    except Exception as e:
        print(f"[Main] Critical Error loading configuration: {e}")
        return

    # 2. Setup Seed Data + Charges
    beam_dist = config_dict.get("beam_distribution", {})
    use_npz   = beam_dist.get("use_npz", False) or beam_dist.get("use_hdf5", False)

    if use_npz:
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            npz_path = os.path.join(project_root, "runs", "simulation_raw.npz")
            print(f"[Main] Loading seeds from NPZ: {npz_path}")
            
            data = np.load(npz_path)
            pdg_code = data['pdg_code']
            
            pbar_indices = np.where(pdg_code == -2212)[0]
            proton_indices = np.where(pdg_code == 2212)[0]
            
            rng = np.random.RandomState(42)
            selected_pbar = rng.choice(pbar_indices, size=min(50, len(pbar_indices)), replace=False)
            selected_proton = rng.choice(proton_indices, size=min(100, len(proton_indices)), replace=False)
            
            selected_idx = np.concatenate([selected_pbar, selected_proton])
            rng.shuffle(selected_idx)
            
            # Extract coordinates (convert from mm to meters)
            x_m = data['start_x'][selected_idx] * 1e-3
            y_m = data['start_y'][selected_idx] * 1e-3
            z_m = data['start_z'][selected_idx] * 1e-3
            R = np.column_stack((x_m, y_m, z_m)).astype(np.float32)
            
            # Extract momentum (MeV/c) and compute velocity/gamma
            px = data['start_px'][selected_idx]
            py = data['start_py'][selected_idx]
            pz = data['start_pz'][selected_idx]
            P_mevc = np.column_stack((px, py, pz))
            
            M_PBAR = 938.2720813
            c_light = 299792458.0
            p_sq = np.sum(P_mevc**2, axis=1)
            E_total = np.sqrt(p_sq + M_PBAR**2)
            gamma = (E_total / M_PBAR).astype(np.float32)
            V = (P_mevc * (c_light / E_total[:, np.newaxis])).astype(np.float32)
            
            charges = np.where(pdg_code[selected_idx] == -2212, -1, 1).astype(np.int8)
            
            n_pbar = int(np.sum(charges == -1))
            n_prot = int(np.sum(charges == +1))
            print(f"[Main] Loaded {n_pbar} antiprotons and {n_prot} protons from NPZ.")
            geant4_env = {}
        except Exception as e:
            print(f"[Main] Critical Error: 'use_npz' is True but could not load seeds ({e}).")
            return
    else:
        geant4_env = {}
        mock = beam_dist.get("mock", {})
        N    = mock.get("N_particles", 50)

        # Charge ratio: antiprotons and protons only — no neutrals
        charge_cfg   = mock.get("charge_ratio", {"antiproton": 0.6, "proton": 0.4})
        n_antiproton = max(1, int(round(N * charge_cfg.get("antiproton", 0.6))))
        n_proton     = N - n_antiproton

        charges = np.concatenate([
            np.full(n_antiproton, -1, dtype=np.int8),
            np.full(n_proton,     +1, dtype=np.int8)
        ])
        np.random.shuffle(charges)  # randomise species order

        R = np.zeros((N, 3), dtype=np.float32)
        R[:, 0] = np.random.normal(mock.get("mu_x", 0.0), mock.get("sigma_x", 0.05), N)
        R[:, 1] = np.random.normal(mock.get("mu_y", 0.0), mock.get("sigma_y", 0.05), N)

        V = np.zeros((N, 3), dtype=np.float32)
        V[:, 0] = np.random.normal(mock.get("mu_vx", 0.0), mock.get("sigma_vx", 5000.0),    N)
        V[:, 1] = np.random.normal(mock.get("mu_vy", 0.0), mock.get("sigma_vy", 5000.0),    N)
        V[:, 2] = np.random.normal(mock.get("mu_vz", 284802835.0), mock.get("sigma_vz", 10000.0), N)

        c_light  = 299792458.0
        v_mag_sq = np.sum(V**2, axis=1)
        v_mag_sq = np.clip(v_mag_sq, 0.0, (0.999 * c_light)**2)
        gamma    = (1.0 / np.sqrt(1.0 - v_mag_sq / c_light**2)).astype(np.float32)

        print(f"[Main] Generated {N} mock particles "
              f"({n_antiproton} antiprotons, {n_proton} protons).")

    # Apply Calibration Mode (Forces transverse velocities to zero)
    if config_dict.get("config", {}).get("calibration_mode", False) or config_dict.get("calibration_mode", False):
        V[:, 0] = 0.0
        V[:, 1] = 0.0
        V[:,2]=284802835.0
        c_light  = 299792458.0
        v_mag_sq = np.sum(V**2, axis=1)
        v_mag_sq = np.clip(v_mag_sq, 0.0, (0.999 * c_light)**2)
        gamma    = (1.0 / np.sqrt(1.0 - v_mag_sq / c_light**2)).astype(np.float32)
        print("[Main] CALIBRATION MODE ENABLED: Transverse velocities forced to 0.0.")

    # 3. Execution
    mode = config_dict.get("mode", "visual")

    from transport.dependencies.boris_solver import run_physics_loop

    if mode == "headless":
        print("[Main] Mode: HEADLESS DIAGNOSTIC RUN")
        headless_time_ns = config_dict.get("headless_time_ns", 150.0)
        print(f"[Main] Starting physics simulation for {headless_time_ns} ns…")

        R_final, V_final, alive_mask, death_causes = run_physics_loop(
            R, V, gamma, None, None, None, None, config_dict, machine,
            headless=True, headless_time_ns=headless_time_ns,
            charges=charges
        )

        # Statistics
        total_particles = len(alive_mask)
        alive_count     = int(np.sum(alive_mask))
        dead_count      = total_particles - alive_count

        if alive_count > 0:
            distance = np.mean(R_final[alive_mask, 2])
        else:
            distance = np.nanmax(R_final[:, 2])

        # Output directory
        import datetime
        timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        runs_path    = os.path.join(os.path.dirname(__file__), "runs")
        os.makedirs(runs_path, exist_ok=True)
        unique_dir   = os.path.join(runs_path, f"run_{timestamp}")
        os.makedirs(unique_dir, exist_ok=True)

        # Report
        n_pbar_init = int(np.sum(charges == -1))
        n_pbar_survived = int(np.sum((charges == -1) & alive_mask))
        n_pbar_annihilated = n_pbar_init - n_pbar_survived
        rate_pbar = n_pbar_survived / n_pbar_init if n_pbar_init > 0 else 0.0

        n_prot_init = int(np.sum(charges == 1))
        n_prot_survived = int(np.sum((charges == 1) & alive_mask))
        n_prot_annihilated = n_prot_init - n_prot_survived
        rate_prot = n_prot_survived / n_prot_init if n_prot_init > 0 else 0.0

        report_path = os.path.join(unique_dir, "report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"Time: {headless_time_ns} ns\n")
            f.write(f"Distance traveled: {distance:.4f} m\n")
            f.write(f"Particles alive: {alive_count}\n")
            f.write(f"Particles died: {dead_count}\n")
            f.write("Cause of loss:\n")
            
            # Species-specific cause of loss formatting: {pbar}, {proton}
            dump_lost = death_causes.get("Dump", [0, 0])
            cw_lost = death_causes.get("Chamber wall", [0, 0])
            filt_lost = death_causes.get("Aperture rejected", [0, 0])
            pw_lost = death_causes.get("Pipe wall", [0, 0])
            surv_stat = death_causes.get("Survived", [0, 0])
            
            f.write(f"Dump: {dump_lost[0]}, {dump_lost[1]}\n")
            f.write(f"Chamber wall: {cw_lost[0]}, {cw_lost[1]}\n")
            f.write(f"Filtration: {filt_lost[0]}, {filt_lost[1]}\n")
            f.write(f"Pipe wall: {pw_lost[0]}, {pw_lost[1]}\n")
            f.write(f"Survived: {surv_stat[0]}, {surv_stat[1]}\n")
            
            # Add charge-resolved survival table at every major element
            major_elements = [("Target", -0.1)]
            if getattr(machine, 'is_acol', False):
                all_elements = []
                for el in machine.prism_elements:
                    all_elements.append((el, el.z_start, el.z_end))
                for el in machine.matching_elements:
                    all_elements.append((el, el.z_start, el.z_end))
                for el in machine.fodo_elements:
                    all_elements.append((el, el.z_start + machine.fodo_start_z, el.z_end + machine.fodo_start_z))
                    
                for el, z_start, z_end in all_elements:
                    el_type = type(el).__name__
                    s_start = z_start - 0.5
                    
                    if el_type == "MagneticHorn":
                        major_elements.append(("Lens", z_end))
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
                        else: continue
                        major_elements.append((name, z_end))
                    elif el_type == "SelectorDipole":
                        major_elements.append(("BHZ0058", z_end))
                    elif el_type == "Dipole":
                        if abs(s_start - 38.0) < 0.5:
                            major_elements.append(("BHZ0088", z_end))
                        elif abs(s_start - 46.0) < 0.5:
                            major_elements.append(("Septum", z_end))
            else:
                for idx, el in enumerate(machine.prism_elements):
                    if type(el).__name__ != "Drift":
                        major_elements.append((f"{type(el).__name__}_{idx}", el.z_end))
                for idx, el in enumerate(machine.matching_elements):
                    if type(el).__name__ != "Drift":
                        major_elements.append((f"{type(el).__name__}_M{idx}", el.z_end))
                for idx, el in enumerate(machine.fodo_elements):
                    if type(el).__name__ != "Drift":
                        major_elements.append((f"{type(el).__name__}_P{idx}", el.z_end))
            
            f.write("\n")
            f.write("Element      p̄     p\n")
            f.write("------------------------\n")
            for name, z_end in major_elements:
                if name == "Target":
                    pbar_cnt = n_pbar_init
                    prot_cnt = n_prot_init
                else:
                    pbar_cnt = int(np.sum((charges == -1) & (R_final[:, 2] >= z_end)))
                    prot_cnt = int(np.sum((charges == 1) & (R_final[:, 2] >= z_end)))
                f.write(f"{name:<12}{pbar_cnt:>3}{prot_cnt:>8}\n")
            f.write("\n")
            
            f.write(f"initial antiproton count: {n_pbar_init}\n")
            f.write(f"antiprotons survived: {n_pbar_survived}\n")
            f.write(f"antiprotons annihilated: {n_pbar_annihilated}\n")
            f.write(f"antiproton survival rate: {rate_pbar:.4f}\n")
            f.write(f"initial proton count: {n_prot_init}\n")
            f.write(f"positive particles survived: {n_prot_survived}\n")
            f.write(f"positive particles annihilated: {n_prot_annihilated}\n")
            f.write(f"positive particles survival rate: {rate_prot:.4f}\n")

        print(f"\n[Main] Headless run complete. Report saved to: {report_path}")

        # Diagnostics
        from transport.dependencies.diagnostics import generate_all_diagnostics

        c_light  = 299792458.0
        v_mag_sq = np.sum(V_final**2, axis=1)
        v_mag_sq = np.clip(v_mag_sq, 0.0, (0.999 * c_light)**2)
        gamma_f  = 1.0 / np.sqrt(1.0 - v_mag_sq / c_light**2)

        M_PBAR  = 938.2720813
        P_final = (gamma_f[:, np.newaxis] * M_PBAR * V_final) / c_light

        data_6D    = np.column_stack((R_final, P_final))
        pbar_mask  = (charges == -1)
        pbar_data  = data_6D[pbar_mask]
        pbar_dead  = data_6D[(~alive_mask) & pbar_mask]
        r_pipe     = config_dict.get("R_PIPE", 0.10)

        generate_all_diagnostics(pbar_data, pbar_dead, unique_dir, pipe_radius=r_pipe)

    else:
        print("[Main] Mode: VISUAL GPU RENDERING")
        from transport.dependencies.viewport import run_renderer

        N            = R.shape[0]
        buffer_bytes = 2 * N * 3 * 4
        shm          = SharedMemory(create=True, size=buffer_bytes)
        shared_mem_name = shm.name

        sync_queue         = mp.Queue(maxsize=5)
        annihilation_queue = mp.Queue()
        stop_event         = mp.Event()

        # Extract visual properties from raw_data
        r_pipe = raw_data.get("config", {}).get("R_PIPE", 0.05)

        physics_proc = mp.Process(
            target=run_physics_loop,
            args=(R, V, gamma, shared_mem_name, sync_queue,
                  annihilation_queue, stop_event,
                  config_dict, machine),
            kwargs={"charges": charges}
        )

        renderer_proc = mp.Process(
            target=run_renderer,
            args=(shared_mem_name, sync_queue, stop_event, N, 1,
                  annihilation_queue, r_pipe, raw_data, geant4_env, charges)
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
            print("[Main] Caught KeyboardInterrupt. Shutting down…")
            stop_event.set()
            renderer_proc.terminate()
            physics_proc.terminate()
        finally:
            shm.close()
            shm.unlink()
            print("[Main] SharedMemory unlinked. Shutdown complete.")


if __name__ == "__main__":
    # Ensure clean separation on all OSes
    mp.set_start_method('spawn')
    main()