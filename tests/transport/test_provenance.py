"""Tests for per-run provenance records."""

from pathlib import Path

from transport.provenance import (
    build_run_provenance,
    canonicalize_params,
    fingerprint_params,
    fingerprint_source,
    load_run_provenance,
    write_run_provenance,
)


def test_canonicalize_params_stable():
    a = canonicalize_params({"b": 2, "a": [1, 2]})
    b = canonicalize_params({"a": [1, 2], "b": 2})
    assert a == b


def test_fingerprint_params_deterministic():
    fp1 = fingerprint_params({"k1": 0.5, "length": 10.0})
    fp2 = fingerprint_params({"length": 10.0, "k1": 0.5})
    assert fp1 == fp2
    fp3 = fingerprint_params({"k1": 0.6, "length": 10.0})
    assert fp3 != fp1


def test_fingerprint_source_missing():
    assert fingerprint_source(None) is None
    assert fingerprint_source("/nonexistent/path/file.root") is None


def test_write_and_load_provenance(tmp_path):
    provenance = build_run_provenance(
        run_id="run_test",
        experiment_name="prov_test",
        parameters={"num_turns": 1, "particle": "antiproton"},
        beamline_hash="hash123",
        source_path=None,
        random_seed=42,
        output_artifacts={"transported_particles_npz": str(tmp_path / "out.npz")},
        metrics_path=str(tmp_path / "metrics.json"),
    )
    path = write_run_provenance(provenance, tmp_path)
    loaded = load_run_provenance(path)
    assert loaded["run_id"] == "run_test"
    assert loaded["parameter_fingerprint"] == provenance["parameter_fingerprint"]
    assert Path(path).name == "provenance.json"


def test_missing_git_commit_graceful():
    provenance = build_run_provenance(
        run_id="run_test",
        experiment_name="prov_test",
        parameters={"x": 1},
        beamline_hash="h",
    )
    assert "git_commit" in provenance
