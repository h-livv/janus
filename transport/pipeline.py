"""
Headless and validation pipeline orchestration.
Transport runs once; validation consumes diagnostics only.
"""
import datetime
import os

from transport.physics.boris_solver import track_particles
from transport.simulation_config import validation_case_for_config
from transport.validation.validator import Validator


def run_transport(config):
    return track_particles(
        config.R_init,
        config.V_init,
        config.gamma_init,
        config.charges,
        config.lattice,
        config.dt,
        config.max_steps,
    )


def run_validation_reports(config, run_outputs_dir):
    validation_case = validation_case_for_config(config)
    _, _, _, diagnostics = run_transport(config)

    case_name = validation_case.name.lower().replace("validation", "")
    case_dir = os.path.join(run_outputs_dir, case_name)
    os.makedirs(case_dir, exist_ok=True)
    report_file_path = os.path.join(case_dir, "report.txt")

    passed, metrics, report = Validator.run(
        validation_case,
        config.dt,
        config.max_steps,
        run_outputs_dir=run_outputs_dir,
        diagnostics=diagnostics,
        lattice=config.lattice,
        R_init=config.R_init,
    )

    converged, errors, report_conv = Validator.run_convergence(
        validation_case,
        config,
        run_outputs_dir=run_outputs_dir,
    )

    with open(report_file_path, "w") as f:
        f.write(report)
        f.write("\n\n")
        f.write(report_conv)

    return passed, converged, report, report_conv, report_file_path


def run_headless_suite(case_types, build_config_fn, print_reports=True):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_outputs_dir = os.path.join("transport", "validation", "outputs", f"run_{timestamp}")
    print(f"[Validator] Outputs for this run will be saved in: {run_outputs_dir}\n")

    overall_passed = True
    for case_type in case_types:
        config = build_config_fn(case_type)
        passed, converged, report, report_conv, _ = run_validation_reports(
            config, run_outputs_dir
        )
        if print_reports:
            print(report)
            print()
            print(report_conv)
            print()
            print("-" * 60)
        if not passed or not converged:
            overall_passed = False

    return overall_passed, run_outputs_dir
