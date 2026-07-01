import sys
import os

# Automatically resolve and inject project root into sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import datetime
from transport.validation.validator import Validator
from transport.validation.cases.drift import DriftValidation
from transport.validation.cases.dipole import DipoleValidation

def main():
    print("=" * 60)
    print("JANUS TRANSPORT VALIDATION SUITE")
    print("=" * 60)
    
    # Generate unique outputs directory for this run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_outputs_dir = os.path.join("transport", "validation", "outputs", f"run_{timestamp}")
    print(f"[Validator] Outputs for this run will be saved in: {run_outputs_dir}\n")

    # 1. Define and instantiate cases
    cases = [
        DriftValidation(),
        DipoleValidation(),
    ]
    
    overall_passed = True
    
    # 2. Iterate through cases
    for case in cases:
        case_name = case.name.lower().replace("validation", "")
        case_dir = os.path.join(run_outputs_dir, case_name)
        os.makedirs(case_dir, exist_ok=True)
        report_file_path = os.path.join(case_dir, "report.txt")

        # Run generic validation
        passed, metrics, report = Validator.run(
            case, case.dt, case.max_steps, run_outputs_dir=run_outputs_dir
        )
        print(report)
        print()
        if not passed:
            overall_passed = False
        with open(report_file_path, "w") as f:
            f.write(report)
            f.write("\n\n")
            
        # Run convergence test and plot
        converged, errors, report_conv = Validator.run_convergence(
            case, case.dt, case.max_steps_conv, run_outputs_dir=run_outputs_dir
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
