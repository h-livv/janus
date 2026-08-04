"""Tests for the transport study framework."""

from pathlib import Path

import numpy as np
import xtrack as xt

from transport.analysis.metrics import load_metrics
from transport.io import single_particle_seeds
from transport.pipeline import run
from transport.studies.export import write_study_csv
from transport.studies.parameters import grid_search, latin_hypercube, random_search
from transport.studies.runner import run_study


def test_grid_search_cartesian_product():
    samples = grid_search({"a": [1, 2], "b": [10, 20]})
    assert len(samples) == 4
    assert {"a": 1, "b": 10} in samples


def test_random_search_reproducible():
    bounds = {"x": (0.0, 1.0), "y": (-1.0, 1.0)}
    a = random_search(bounds, n_samples=5, seed=7)
    b = random_search(bounds, n_samples=5, seed=7)
    assert a == b
    assert len(a) == 5


def test_latin_hypercube_reproducible():
    bounds = {"x": (0.0, 1.0), "y": (-1.0, 1.0)}
    a = latin_hypercube(bounds, n_samples=4, seed=3)
    b = latin_hypercube(bounds, n_samples=4, seed=3)
    assert a == b
    assert len(a) == 4


def test_write_study_csv(tmp_path):
    rows = [
        {"run_index": 0, "param_k1": 0.1, "transmission": 1.0},
        {"run_index": 1, "param_k1": 0.2, "transmission": 0.9},
    ]
    path = write_study_csv(rows, tmp_path / "study_results.csv")
    text = Path(path).read_text()
    assert "param_k1" in text
    assert "transmission" in text


def test_run_study_delegates_to_experiment_factory(tmp_path):
    calls = []

    def factory(params, run_dir):
        calls.append((params, run_dir))
        seeds = single_particle_seeds(
            particle="antiproton",
            position=[0.001, 0.0, 0.0],
            velocity=[0.0, 0.0, 299492818.0],
            gamma=3.82,
        )
        length = float(params["length"])
        line = xt.Line(elements=[xt.Drift(length=length)])
        result, actual_dir = run(
            line=line,
            particle="antiproton",
            count=1,
            momentum_slice=None,
            num_turns=1,
            output_name="study_smoke",
            output_dir=str(tmp_path / "out"),
            seeds=seeds,
            run_outputs_dir=run_dir,
        )
        metrics = load_metrics(f"{actual_dir}/metrics.json")
        return result, actual_dir, metrics

    def parameter_generator():
        return grid_search({"length": [1.0, 2.0]})

    study_dir = tmp_path / "study"
    csv_path = run_study(
        parameter_generator=parameter_generator,
        experiment_factory=factory,
        study_output_dir=str(study_dir),
        study_name="smoke",
    )

    assert len(calls) == 2
    assert Path(csv_path).exists()
    csv_text = Path(csv_path).read_text()
    assert "provenance_path" in csv_text
    assert "param_length" in csv_text
    assert (study_dir / "run_0000" / "provenance.json").exists()
