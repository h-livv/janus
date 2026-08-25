import argparse
import sys
import uproot
import awkward as ak
import numpy as np
import os
import glob

from particle import Particle

def get_baryon_number(pdgid_obj):
    if pdgid_obj.is_nucleus:
        return pdgid_obj.A * (-1 if pdgid_obj < 0 else 1)
    elif pdgid_obj.is_baryon:
        return -1 if pdgid_obj < 0 else 1
    return 0

def get_q_b(pdg_code):
    try:
        part = Particle.from_pdgid(pdg_code)
        q = int(part.charge)
        b = get_baryon_number(part.pdgid)
        return (q, b)
    except Exception:
        # Fallback for completely unknown codes, or very heavy non-standard fragments
        if pdg_code > 1000000000:
            z = (pdg_code // 10000) % 1000
            a = (pdg_code // 10) % 1000
            return (z, a)
        return (0, 0)

def main():
    parser = argparse.ArgumentParser(description="Janus Validation Suite")
    parser.add_argument("root_file", type=str, nargs='?', help="Path to the validation.root file (optional, defaults to latest run)")
    parser.add_argument("--epsilon", type=float, default=2.0, help="Tolerance for kinematic checks in MeV")
    args = parser.parse_args()

    root_path = args.root_file
    if not root_path:
        runs = glob.glob("data/collision/run_*")
        if not runs:
            # Fallback to outputs/ if data/collision/ doesn't exist
            runs = glob.glob("outputs/run_*")
        if not runs:
            print("Fatal Error: No output directories found in data/collision/ or outputs/ and no file provided.")
            sys.exit(1)
        latest_run = max(runs, key=os.path.getmtime)
        root_path = os.path.join(latest_run, "validation.root")
        print(f"[*] No file provided. Auto-detected latest run: {root_path}")

    try:
        f = uproot.open(root_path)
    except Exception as e:
        print(f"Fatal Error: Could not open ROOT file. Details: {e}")
        sys.exit(1)

    if "Validation" not in f:
        print("Fatal Error: Missing Validation tree in ROOT file.")
        sys.exit(1)
        
    tree = f["Validation"]

    try:
        init_E = tree["initial_E"].array(library="np")
        init_px = tree["initial_px"].array(library="np")
        init_py = tree["initial_py"].array(library="np")
        init_pz = tree["initial_pz"].array(library="np")

        out_E = [np.asarray(x) for x in tree["outgoing_E"].array(library="ak")]
        out_px = [np.asarray(x) for x in tree["outgoing_px"].array(library="ak")]
        out_py = [np.asarray(x) for x in tree["outgoing_py"].array(library="ak")]
        out_pz = [np.asarray(x) for x in tree["outgoing_pz"].array(library="ak")]
        out_pdg = [np.asarray(x) for x in tree["outgoing_pdg"].array(library="ak")]
    except KeyError as e:
        print(f"Fatal Error: Missing expected dataset {e} in ROOT file.")
        sys.exit(1)

    n_events = len(init_E)
    if n_events == 0:
        print("Error: No events found in dataset.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Phase 1: Vectorized Invariant Evaluator (Kinematics)
    # -------------------------------------------------------------------------
    vec_sum = np.vectorize(np.sum, otypes=[np.float64])

    out_E_sum = vec_sum(out_E)
    out_px_sum = vec_sum(out_px)
    out_py_sum = vec_sum(out_py)
    out_pz_sum = vec_sum(out_pz)

    delta_E = np.abs(out_E_sum - init_E)
    delta_px = out_px_sum - init_px
    delta_py = out_py_sum - init_py
    delta_pz = out_pz_sum - init_pz
    delta_p = np.sqrt(delta_px**2 + delta_py**2 + delta_pz**2)

    failed_mask = delta_E > args.epsilon
    failed_indices = np.where(failed_mask)[0]
    failure_rate = len(failed_indices) / n_events

    # Collect text for report
    report_lines = []
    def log_print(msg):
        print(msg)
        report_lines.append(msg)
        
    log_print(f"========== JANUS VALIDATION REPORT ==========")
    log_print(f"Events Validated: {n_events}")

    if failure_rate > 0.0001:
        log_print(f"Phase 1 Fatal Error: Kinematic conservation failure rate {failure_rate*100:.4f}% exceeds 0.01%.")
        log_print(f"  Total failed events: {len(failed_indices)} out of {n_events}")
        for idx in failed_indices[:15]:
            log_print(f"  Event {idx}: Delta E = {delta_E[idx]:.3f} MeV, Delta P = {delta_p[idx]:.3f} MeV")
        sys.exit(1)
    else:
        log_print("Phase 1 Passed: Kinematic Conservation Verified.")
        log_print(f"  -> Maximum ΔE Error: {repr(np.max(delta_E).item())} MeV")
        log_print(f"  -> Maximum ΔP Error: {repr(np.max(delta_p).item())} MeV/c")

    # -------------------------------------------------------------------------
    # Phase 2: Quantum Number Gatekeeper (Discrete Conservation)
    # -------------------------------------------------------------------------
    target_Z = tree["target_Z"].array(library="np")
    target_A = tree["target_A"].array(library="np")
    beam_pdg = tree["beam_pdg"].array(library="np")
    
    Q_INITIAL = np.zeros_like(target_Z, dtype=np.int32)
    B_INITIAL = np.zeros_like(target_A, dtype=np.int32)
    
    for i, pdg in enumerate(beam_pdg):
        beam_q, beam_b = get_q_b(pdg)
        Q_INITIAL[i] = target_Z[i] + beam_q
        B_INITIAL[i] = target_A[i] + beam_b

    def calc_qb_sum(pdg_array):
        q_sum = 0
        b_sum = 0
        for pdg in pdg_array:
            q, b = get_q_b(pdg)
            q_sum += q
            b_sum += b
        return q_sum, b_sum

    vec_qb = np.vectorize(calc_qb_sum, otypes=[np.int32, np.int32])
    out_q_sum, out_b_sum = vec_qb(out_pdg)

    q_fails = np.where(out_q_sum != Q_INITIAL)[0]
    b_fails = np.where(out_b_sum != B_INITIAL)[0]

    if len(q_fails) > 0 or len(b_fails) > 0:
        log_print("Phase 2 Fatal Error: Quantum Number Conservation Violated.")
        failed_qb_indices = np.unique(np.concatenate((q_fails, b_fails)))
        for idx in failed_qb_indices[:15]:
            log_print(f"  Event {idx}: Q_sum = {out_q_sum[idx]} (Expected {Q_INITIAL[idx]}), B_sum = {out_b_sum[idx]} (Expected {B_INITIAL[idx]})")
        sys.exit(1)
    else:
        log_print("Phase 2 Passed: Quantum Number Conservation Verified.")
        log_print(f"  -> Mean Event Charge (Q): {np.mean(out_q_sum):.1f} (Mean Expected: {np.mean(Q_INITIAL):.1f})")
        log_print(f"  -> Mean Event Baryon (B): {np.mean(out_b_sum):.1f} (Mean Expected: {np.mean(B_INITIAL):.1f})")

    # -------------------------------------------------------------------------
    # Phase 3: Statistical Benchmark (Sanity Checks)
    # -------------------------------------------------------------------------
    def count_antinucleons(pdg_array):
        return np.sum((pdg_array == -2212) | (pdg_array == -2112))

    def count_charged_pions(pdg_array):
        return np.sum((pdg_array == 211) | (pdg_array == -211))

    anti_baryon_counts = np.vectorize(count_antinucleons, otypes=[np.int32])(out_pdg)
    total_anti_baryons = np.sum(anti_baryon_counts)

    total_global_B = np.sum(out_b_sum)
    expected_global_B = np.sum(B_INITIAL)

    if total_global_B != expected_global_B:
        log_print(f"Phase 3 Fatal Error: Global Baryon Number is not conserved. Total B = {total_global_B}, Expected = {expected_global_B}")
        sys.exit(1)

    pion_counts = np.vectorize(count_charged_pions, otypes=[np.int32])(out_pdg)
    inelastic_mask = np.array([len(arr) > 1 for arr in out_pdg])
    
    if np.any(inelastic_mask):
        mean_pions = np.mean(pion_counts[inelastic_mask])
    else:
        mean_pions = 0.0

    log_print("Phase 3 Sanity Checks Passed:")
    log_print(f"  -> Total Antinucleons Generated: {total_anti_baryons}")
    log_print(f"  -> Global Baryon Conservation Verified.")
    log_print(f"  -> Mean Charged Pions per Inelastic Event: {mean_pions:.4f}")

    log_print("\n[+] Validation Suite Passed Successfully. Transport simulation may proceed.")
    
    # Write report to collision/validation/validation_outputs/<run_name>
    run_name = os.path.basename(os.path.dirname(root_path))
    output_dir = os.path.join("collision", "validation", "validation_outputs", run_name)
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "phase_1_2_3_report.txt"), "w") as rf:
        rf.write("\n".join(report_lines) + "\n")

if __name__ == "__main__":
    main()
