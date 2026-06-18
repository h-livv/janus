import argparse
import sys
import os
import h5py
import numpy as np
import matplotlib.pyplot as plt
import os
import glob

def main():
    parser = argparse.ArgumentParser(description="Janus Physical Validation Suite (Phase 4)")
    parser.add_argument("val_hdf5", type=str, nargs='?', help="Path to the validation.hdf5 file (optional)")
    parser.add_argument("sim_hdf5", type=str, nargs='?', help="Path to the simulation.hdf5 file (optional)")
    args = parser.parse_args()

    val_path = args.val_hdf5
    sim_path = args.sim_hdf5

    if not val_path or not sim_path:
        runs = glob.glob("outputs/run_*")
        if not runs:
            print("Fatal Error: No output directories found in outputs/ and no files provided.")
            sys.exit(1)
        latest_run = max(runs, key=os.path.getmtime)
        val_path = val_path or os.path.join(latest_run, "validation.hdf5")
        sim_path = sim_path or os.path.join(latest_run, "simulation.hdf5")
        print(f"[*] Auto-detected latest run for missing arguments.")
        print(f"    Validation: {val_path}")
        print(f"    Simulation: {sim_path}")

    try:
        val_f = h5py.File(val_path, 'r')
        sim_f = h5py.File(sim_path, 'r')
    except Exception as e:
        print(f"Fatal Error: Could not open HDF5 files. Details: {e}")
        sys.exit(1)

    run_name = os.path.basename(os.path.dirname(val_path))
    output_dir = os.path.join("validation", "validation_outputs", run_name)
    os.makedirs(output_dir, exist_ok=True)

    def find_dataset(name, node):
        if isinstance(node, h5py.Dataset) and (name in node.name):
            return node
        elif isinstance(node, h5py.Group):
            for key in node:
                res = find_dataset(name, node[key])
                if res is not None:
                    return res
        return None

    # Load validation data
    out_E_ds = find_dataset("outgoing_E/pages", val_f) or find_dataset("outgoing_E", val_f)
    out_px_ds = find_dataset("outgoing_px/pages", val_f) or find_dataset("outgoing_px", val_f)
    out_py_ds = find_dataset("outgoing_py/pages", val_f) or find_dataset("outgoing_py", val_f)
    out_pz_ds = find_dataset("outgoing_pz/pages", val_f) or find_dataset("outgoing_pz", val_f)
    out_pdg_ds = find_dataset("outgoing_pdg/pages", val_f) or find_dataset("outgoing_pdg", val_f)

    if not all([out_E_ds, out_px_ds, out_pdg_ds]):
        print("Fatal Error: Missing expected datasets in validation HDF5 file.")
        sys.exit(1)

    out_E = out_E_ds[:]
    out_px = out_px_ds[:]
    out_py = out_py_ds[:]
    out_pz = out_pz_ds[:]
    out_pdg = out_pdg_ds[:]

    n_events = len(out_E)

    # Load simulation seeds data
    trackID_ds = find_dataset("default_ntuples/Seeds/track_id/pages", sim_f) or find_dataset("track_id", sim_f)
    z_ds = find_dataset("default_ntuples/Seeds/start_z/pages", sim_f) or find_dataset("start_z", sim_f)

    if not all([trackID_ds, z_ds]):
        print("Fatal Error: Missing expected datasets in simulation HDF5 file. Checked for track_id and start_z.")
        sys.exit(1)
        
    trackID_arr = trackID_ds[:]
    z_arr = z_ds[:]

    print(f"========== JANUS PHYSICAL VALIDATION (PHASE 4) ==========")
    
    # Flatten arrays for particle-level plotting
    all_pdgs = np.concatenate(out_pdg)
    all_E = np.concatenate(out_E)
    all_px = np.concatenate(out_px)
    all_py = np.concatenate(out_py)
    all_pz = np.concatenate(out_pz)
    
    # -------------------------------------------------------------------------
    # Scheme 1: Transverse vs. Longitudinal Momentum
    # -------------------------------------------------------------------------
    # Filter for charged pions (pdg 211, -211)
    pion_mask = (all_pdgs == 211) | (all_pdgs == -211)
    pion_px = all_px[pion_mask]
    pion_py = all_py[pion_mask]
    pion_pz = all_pz[pion_mask]
    
    p_T = np.sqrt(pion_px**2 + pion_py**2)
    p_L = pion_pz
    
    plt.figure(figsize=(8, 6))
    plt.hist2d(p_L, p_T, bins=50, cmap='viridis', cmin=1)
    plt.colorbar(label='Count')
    plt.xlabel('Longitudinal Momentum $p_L$ (MeV/c)')
    plt.ylabel('Transverse Momentum $p_T$ (MeV/c)')
    plt.title('Phase 4: Transverse vs Longitudinal Momentum (Charged Pions)')
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, 'phase4_pT_vs_pL.png'), dpi=300)
    plt.close()
    print("[+] Scheme 1 Completed: Saved pT vs pL distribution.")

    # -------------------------------------------------------------------------
    # Scheme 2: Multiplicity Distribution
    # -------------------------------------------------------------------------
    def count_charged_pions(pdg_array):
        return np.sum((pdg_array == 211) | (pdg_array == -211))
        
    pion_counts = np.vectorize(count_charged_pions, otypes=[np.int32])(out_pdg)
    
    # Filter out elastic events (where there are only ~2 particles: proton + target)
    inelastic_mask = np.array([len(arr) > 2 for arr in out_pdg])
    if np.any(inelastic_mask):
        inelastic_pion_counts = pion_counts[inelastic_mask]
        
        plt.figure(figsize=(8, 6))
        # Ensure bins cover the integer range perfectly
        max_count = np.max(inelastic_pion_counts)
        bins = np.arange(-0.5, max_count + 1.5, 1)
        plt.hist(inelastic_pion_counts, bins=bins, color='skyblue', edgecolor='black')
        plt.xlabel('Charged Pion Multiplicity per Inelastic Event')
        plt.ylabel('Frequency')
        plt.title('Phase 4: Multiplicity Distribution')
        plt.grid(True, alpha=0.3, axis='y')
        plt.savefig(os.path.join(output_dir, 'phase4_multiplicity.png'), dpi=300)
        plt.close()
        print("[+] Scheme 2 Completed: Saved multiplicity distribution.")
    else:
        print("[-] Scheme 2 Skipped: No inelastic events found.")

    # -------------------------------------------------------------------------
    # Scheme 3: Energy Spectra (Neutrons)
    # -------------------------------------------------------------------------
    neutron_mask = (all_pdgs == 2112)
    neutron_E = all_E[neutron_mask]
    neutron_mass = 939.565 # MeV
    neutron_KE = neutron_E - neutron_mass
    
    # Filter invalid kinetic energies
    neutron_KE = neutron_KE[neutron_KE > 0]
    
    if len(neutron_KE) > 0:
        plt.figure(figsize=(8, 6))
        # Use log spacing for kinetic energy to capture both evaporation (1-10 MeV) and cascade (>100 MeV)
        bins = np.logspace(np.log10(max(0.1, np.min(neutron_KE))), np.log10(np.max(neutron_KE)), 50)
        plt.hist(neutron_KE, bins=bins, color='salmon', edgecolor='black')
        plt.xscale('log')
        plt.yscale('log')
        plt.xlabel('Neutron Kinetic Energy (MeV)')
        plt.ylabel('Frequency')
        plt.title('Phase 4: Neutron Kinetic Energy Spectrum\n(Evaporation vs Cascade)')
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(output_dir, 'phase4_energy_spectra.png'), dpi=300)
        plt.close()
        print("[+] Scheme 3 Completed: Saved neutron energy spectra.")
    else:
        print("[-] Scheme 3 Skipped: No neutrons generated.")

    # -------------------------------------------------------------------------
    # Scheme 4: Interaction Vertex Distribution
    # -------------------------------------------------------------------------
    # Ntuple 1 contains flat arrays of scalars, not nested arrays.
    all_trackID = trackID_arr
    all_z = z_arr
    
    # Look for birth positions of all non-primary particles (trackID > 1)
    # These represent the exact interaction vertex where the collision shatter occurred.
    secondary_mask = (all_trackID > 1)
    secondary_z = all_z[secondary_mask]
    
    if len(secondary_z) > 0:
        plt.figure(figsize=(8, 6))
        plt.hist(secondary_z, bins=50, color='lightgreen', edgecolor='black')
        plt.xlabel('Vertex Z-Coordinate (mm)')
        plt.ylabel('Number of Secondaries Born')
        plt.title('Phase 4: Interaction Vertex Z-Distribution\n(Exponential Decay profile through target)')
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(output_dir, 'phase4_vertex_distribution.png'), dpi=300)
        plt.close()
        print("[+] Scheme 4 Completed: Saved interaction vertex distribution.")
    else:
        print("[-] Scheme 4 Skipped: No secondary particles tracked.")

    print("\n[+] Phase 4 Physical Validation Successfully Completed.")

if __name__ == "__main__":
    main()
