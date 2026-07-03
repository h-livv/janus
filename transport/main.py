import argparse
import os
import sys

DEFAULT_EXPERIMENT = os.path.join(
    os.path.dirname(__file__), "experiment", "examples", "dipole.yaml"
)


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    parser = argparse.ArgumentParser(description="Run a transport validation experiment.")
    parser.add_argument(
        "--experiment",
        default=DEFAULT_EXPERIMENT,
        help="Path to experiment YAML file (default: dipole example)",
    )
    args = parser.parse_args()

    from transport.experiment.loader import load_experiment
    from transport.pipeline import run_experiment

    experiment = load_experiment(args.experiment)
    print(f"[Main] Running experiment: {experiment.name} ({args.experiment})")
    passed, run_outputs_dir = run_experiment(experiment)

    if passed:
        print("\nSTATUS: PASS")
        sys.exit(0)
    print("\nSTATUS: FAIL")
    sys.exit(1)


if __name__ == "__main__":
    main()
