"""Study orchestration: parameter generation → experiment factory → pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from transport.analysis.metrics import TransportMetrics
from transport.studies.export import write_study_csv

ParameterGenerator = Callable[[], list[dict[str, Any]]]
ExperimentFactory = Callable[[dict[str, Any], str], tuple[Any, str, TransportMetrics]]
# Factory receives (params, run_outputs_dir) and returns (result, run_outputs_dir, metrics)


def run_study(
    *,
    parameter_generator: ParameterGenerator,
    experiment_factory: ExperimentFactory,
    study_output_dir: str,
    study_name: str,
) -> str:
    """
    Execute a computational study.

    The Study orchestrates many runs, aggregates outputs, and writes CSV.
    It never constructs beamlines — that remains the Experiment Factory's job.
    """
    os.makedirs(study_output_dir, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for index, params in enumerate(parameter_generator()):
        run_dir = os.path.join(study_output_dir, f"run_{index:04d}")
        os.makedirs(run_dir, exist_ok=True)

        _, actual_run_dir, metrics = experiment_factory(params, run_dir)

        provenance_path = Path(actual_run_dir) / "provenance.json"
        metrics_path = Path(actual_run_dir) / "metrics.json"
        npz_path = Path(actual_run_dir) / "transported_particles.npz"

        row: dict[str, Any] = {
            "study_name": study_name,
            "run_index": index,
            "run_output_dir": actual_run_dir,
            "npz_path": str(npz_path) if npz_path.exists() else "",
            "metrics_path": str(metrics_path) if metrics_path.exists() else "",
            "provenance_path": str(provenance_path) if provenance_path.exists() else "",
            "transmission": metrics.transmission,
            "transported_count": metrics.transported_count,
            "generated_count": metrics.generated_count,
            "rms_x_m": metrics.rms_x_m,
            "rms_y_m": metrics.rms_y_m,
            "mean_momentum_gevc": metrics.mean_momentum_gevc,
            "momentum_spread_gevc": metrics.momentum_spread_gevc,
        }
        for key, value in sorted(params.items()):
            row[f"param_{key}"] = value
        rows.append(row)

    csv_path = os.path.join(study_output_dir, "study_results.csv")
    return write_study_csv(rows, csv_path)
