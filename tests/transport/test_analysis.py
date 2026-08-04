"""Tests for post-transport NPZ analysis diagnostics."""

from pathlib import Path

import numpy as np
import xtrack as xt

from transport.analysis import analyze
from transport.io import SeedArrays
from transport.pipeline import run
from transport.xsuite import run_transport, seeds_to_xparticles, write_transport_output


def _seeds(n=20):
    rng = np.random.default_rng(0)
    positions = np.zeros((n, 3), dtype=np.float32)
    positions[:, 0] = rng.normal(0.0, 1e-3, n)
    positions[:, 1] = rng.normal(0.0, 1e-3, n)
    momenta = np.zeros((n, 3), dtype=np.float32)
    momenta[:, 0] = rng.normal(0.0, 10.0, n)
    momenta[:, 2] = 3580.0 + rng.normal(0.0, 20.0, n)
    return SeedArrays(
        positions=positions,
        velocities=np.zeros((n, 3), dtype=np.float32),
        gammas=np.full(n, 3.82, dtype=np.float32),
        charges=np.full(n, -1, dtype=np.int8),
        momenta_mevc=momenta,
        start_z=positions[:, 2].copy(),
    )


def test_analyze_writes_all_diagnostics(tmp_path):
    seeds = _seeds()
    particles, meta = seeds_to_xparticles(
        seeds, species="antiproton", charge_filter="antiproton"
    )
    line = xt.Line(elements=[xt.Drift(length=2.0), xt.Quadrupole(length=1.0, k1=0.2)])
    line.particle = particles
    result = run_transport(line, particles, meta, num_turns=1)
    npz = write_transport_output(result, str(tmp_path), experiment_name="ana")
    assert Path(npz).name == "transported_particles.npz"

    outs = analyze(npz)
    for key, filename in [
        ("beam_xy", "beam_xy.png"),
        ("phase_space", "phase_space.png"),
        ("momentum_histogram", "momentum_histogram.png"),
        ("beamline", "beamline.png"),
        ("summary", "summary.txt"),
    ]:
        path = Path(outs[key])
        assert path.name == filename
        assert path.exists()
        assert path.stat().st_size > 0

    text = Path(outs["summary"]).read_text()
    assert "Particle species" in text
    assert "Transmission efficiency" in text
    assert "RMS beam size x" in text


def test_pipeline_auto_runs_analysis(tmp_path):
    seeds = _seeds(n=5)
    line = xt.Line(elements=[xt.Drift(length=1.0)])
    result, out_dir = run(
        line=line,
        particle="antiproton",
        count=None,
        momentum_slice=None,
        num_turns=1,
        output_name="pipe_ana",
        output_dir=str(tmp_path / "out"),
        seeds=seeds,
        run_outputs_dir=str(tmp_path / "out"),
    )
    out = Path(out_dir)
    assert (out / "transported_particles.npz").exists()
    assert (out / "beam_xy.png").exists()
    assert (out / "phase_space.png").exists()
    assert (out / "momentum_histogram.png").exists()
    assert (out / "beamline.png").exists()
    assert (out / "summary.txt").exists()
    assert result.output_path is not None
