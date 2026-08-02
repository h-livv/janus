"""CLI entry point: select an experiment module and run it."""

import argparse
import importlib
import os
import sys
from pathlib import Path


def _list_experiments():
    experiments_dir = Path(__file__).resolve().parent / "experiments"
    return sorted(
        p.stem
        for p in experiments_dir.glob("*.py")
        if p.stem != "__init__" and not p.stem.startswith("_")
    )


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    names = _list_experiments()
    parser = argparse.ArgumentParser(description="Run Xsuite-backed particle transport.")
    parser.add_argument(
        "--experiment",
        default="drift",
        choices=names,
        help="Experiment module under transport/experiments/ (default: drift)",
    )
    args = parser.parse_args()

    print(f"[Main] Running transport: {args.experiment}")
    module = importlib.import_module(f"transport.experiments.{args.experiment}")
    module.main()


if __name__ == "__main__":
    main()
