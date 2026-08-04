"""Tests for structured transport metrics."""

from pathlib import Path

import numpy as np
import pytest
import xtrack as xt

from transport.analysis.metrics import (
    compute_transport_metrics,
    load_metrics,
    metrics_from_npz,
    write_metrics,
)
from transport.io import SeedArrays
from transport.xsuite import run_transport, seeds_to_xparticles, write_transport_output


def _seeds(n=10):
    rng = np.random.default_rng(0)
    positions = np.zeros((n, 3), dtype=np.float32)
    positions[:, 0] = rng.normal(0.0, 1e-3, n)
    positions[:, 1] = rng.normal(0.0, 1e-3, n)
    momenta = np.zeros((n, 3), dtype=np.float32)
    momenta[:, 2] = 3580.0 + rng.normal(0.0, 20.0, n)
    return SeedArrays(
        positions=positions,
        velocities=np.zeros((n, 3), dtype=np.float32),
        gammas=np.full(n, 3.82, dtype=np.float32),
        charges=np.full(n, -1, dtype=np.int8),
        momenta_mevc=momenta,
        start_z=positions[:, 2].copy(),
    )


def test_compute_transport_metrics_from_result(tmp_path):
    seeds = _seeds(n=5)
    particles, meta = seeds_to_xparticles(
        seeds, species="antiproton", charge_filter="antiproton"
    )
    line = xt.Line(elements=[xt.Drift(length=2.0)])
    line.particle = particles
    result = run_transport(line, particles, meta, num_turns=1)
    metrics = compute_transport_metrics(result, "metrics_test")

    assert metrics.generated_count == 5
    assert metrics.transported_count == 5
    assert metrics.transmission == 1.0
    assert metrics.beam_losses == 0
    assert metrics.rms_x_m > 0
    assert metrics.mean_momentum_gevc > 3.0


def test_metrics_npz_adapter_matches_in_memory(tmp_path):
    seeds = _seeds(n=3)
    particles, meta = seeds_to_xparticles(
        seeds, species="antiproton", charge_filter="antiproton"
    )
    line = xt.Line(elements=[xt.Drift(length=1.0)])
    line.particle = particles
    result = run_transport(line, particles, meta, num_turns=1)
    in_memory = compute_transport_metrics(result, "adapter_test")
    npz = write_transport_output(result, str(tmp_path), experiment_name="adapter_test")
    from_npz = metrics_from_npz(npz)

    assert from_npz.transmission == in_memory.transmission
    assert from_npz.generated_count == in_memory.generated_count
    assert np.isclose(from_npz.rms_x_m, in_memory.rms_x_m)


def test_metrics_zero_survivors():
    x = np.array([0.0, 0.0])
    y = np.array([0.0, 0.0])
    px = np.array([0.0, 0.0])
    py = np.array([0.0, 0.0])
    delta = np.array([0.0, 0.0])
    alive = np.array([False, False])
    from transport.analysis.metrics import _compute_from_arrays

    metrics = _compute_from_arrays(
        x=x,
        y=y,
        px=px,
        py=py,
        delta=delta,
        alive_mask=alive,
        p0c_eV=3.58e9,
        species="antiproton",
        experiment_name="empty",
        source_path=None,
        beamline_hash="abc",
    )
    assert metrics.transported_count == 0
    assert metrics.transmission == 0.0
    assert np.isnan(metrics.rms_x_m)


def test_write_and_load_metrics(tmp_path):
    seeds = _seeds(n=2)
    particles, meta = seeds_to_xparticles(
        seeds, species="antiproton", charge_filter="antiproton"
    )
    line = xt.Line(elements=[xt.Drift(length=1.0)])
    line.particle = particles
    result = run_transport(line, particles, meta, num_turns=1)
    metrics = compute_transport_metrics(result, "io_test")
    path = write_metrics(metrics, tmp_path)
    loaded = load_metrics(path)
    assert loaded.transmission == metrics.transmission
    assert Path(path).name == "metrics.json"
