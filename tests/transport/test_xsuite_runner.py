"""Tests for Xsuite transport runner and pipeline output."""

import json
from pathlib import Path

import numpy as np
import xtrack as xt

from transport.io import SeedArrays, load_seed_npz
from transport.pipeline import run
from transport.xsuite import line_config_hash, run_transport, seeds_to_xparticles, write_transport_output


def _drift_seeds(px_mevc=35.8):
    positions = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    momenta = np.array([[px_mevc, 0.0, 3580.0]], dtype=np.float32)
    return SeedArrays(
        positions=positions,
        velocities=np.zeros((1, 3), dtype=np.float32),
        gammas=np.array([3.82], dtype=np.float32),
        charges=np.array([-1], dtype=np.int8),
        momenta_mevc=momenta,
        start_z=positions[:, 2].copy(),
    )


def test_drift_preserves_px_and_offsets_x():
    seeds = _drift_seeds(px_mevc=35.8)
    particles, meta = seeds_to_xparticles(
        seeds, species="antiproton", charge_filter="antiproton"
    )
    line = xt.Line(elements=[xt.Drift(length=10.0)])
    line.particle = particles
    result = run_transport(
        line,
        particles,
        meta,
        beamline_hash=line_config_hash(line),
        num_turns=1,
    )
    p0_mevc = meta.p0c_eV / 1e6
    expected_px = 35.8 / p0_mevc
    assert np.isclose(result.particles.px[0], expected_px)
    assert result.particles.x[0] > 0.0


def test_write_transport_output_shape(tmp_path):
    seeds = _drift_seeds()
    particles, meta = seeds_to_xparticles(
        seeds, species="antiproton", charge_filter="antiproton"
    )
    line = xt.Line(elements=[xt.Drift(length=1.0)])
    line.particle = particles
    result = run_transport(line, particles, meta, num_turns=1)
    out = write_transport_output(result, str(tmp_path), experiment_name="test")
    data = np.load(out)
    assert "x" in data
    assert "px" in data
    assert "alive_mask" in data
    assert "p0c_eV" in data
    assert "start_z" in data
    meta_json = json.loads(str(data["metadata_json"]))
    assert meta_json["engine"] == "xsuite"


def test_pipeline_file_seeds_integration(tmp_path):
    """End-to-end: NPZ file → pipeline.run → transported NPZ."""
    path = tmp_path / "geant4_like.npz"
    positions = np.array([[0.001, 0.0, 0.5]], dtype=np.float32)
    np.savez(
        path,
        positions=positions,
        velocities=np.array([[0.0, 0.0, 2.99492818e8]], dtype=np.float32),
        gammas=np.array([3.82], dtype=np.float32),
        charges=np.array([-1], dtype=np.int8),
        momenta_mevc=np.array([[0.0, 0.0, 3580.0]], dtype=np.float32),
        start_z=positions[:, 2],
    )
    seeds = load_seed_npz(path)
    line = xt.Line(elements=[xt.Drift(length=2.0)])
    result, out_dir = run(
        line=line,
        particle="antiproton",
        count=None,
        momentum_slice=None,
        num_turns=1,
        output_name="integration",
        output_dir=str(tmp_path / "out"),
        seeds=seeds,
        run_outputs_dir=str(tmp_path / "out"),
    )
    assert result.output_path is not None
    assert Path(result.output_path).name == "transported_particles.npz"
    with np.load(result.output_path) as data:
        assert data["x"].shape == (1,)
        assert "metadata_json" in data
    out = Path(out_dir)
    assert (out / "summary.txt").exists()
    assert (out / "beam_xy.png").exists()
