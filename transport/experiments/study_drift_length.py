"""Example parameter sweep: drift length study using the study framework."""

from __future__ import annotations

import xtrack as xt

from transport.analysis.metrics import load_metrics
from transport.io import single_particle_seeds
from transport.pipeline import run
from transport.studies import grid_search, run_study


def _experiment_factory(params: dict, run_outputs_dir: str):
    length = float(params["drift_length"])
    line = xt.Line(elements=[xt.Drift(length=length)])

    seeds = single_particle_seeds(
        particle="antiproton",
        position=[0.001, 0.0, 0.0],
        velocity=[0.0, 0.0, 299492818.0],
        gamma=3.82,
    )

    result, actual_dir = run(
        line=line,
        particle="antiproton",
        count=1,
        momentum_slice=None,
        num_turns=1,
        output_name="drift_length_study",
        output_dir="transport/outputs",
        seeds=seeds,
        run_outputs_dir=run_outputs_dir,
    )
    metrics = load_metrics(f"{actual_dir}/metrics.json")
    return result, actual_dir, metrics


def main():
    def parameter_generator():
        return grid_search({"drift_length": [5.0, 10.0, 15.0]})

    csv_path = run_study(
        parameter_generator=parameter_generator,
        experiment_factory=_experiment_factory,
        study_output_dir="transport/outputs/study_drift_length",
        study_name="drift_length",
    )
    print(f"[Study] Wrote {csv_path}")


if __name__ == "__main__":
    main()
