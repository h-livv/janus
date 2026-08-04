"""Contract tests for stable Janus transport public interfaces.

These tests lock intentional public contracts, not private implementation details.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest
import xtrack as xt

from transport.io import SeedArrays, load_seed_npz
from transport.pipeline import run
from transport.xsuite import TransportResult, write_transport_output

_REQUIRED_SEED_NPZ_KEYS = ("positions", "velocities", "gammas", "charges")
_REQUIRED_TRANSPORTED_NPZ_KEYS = (
    "x",
    "px",
    "y",
    "py",
    "zeta",
    "delta",
    "state",
    "at_element",
    "alive_mask",
    "p0c_eV",
    "mass0_eV",
    "q0",
    "start_z",
    "metadata_json",
)
_REQUIRED_ANALYZE_KEYS = (
    "beam_xy",
    "phase_space",
    "momentum_histogram",
    "beamline",
    "summary",
    "metrics",
)


def test_pipeline_run_requires_scientific_parameters():
  sig = inspect.signature(run)
  required = [
      "line",
      "particle",
      "count",
      "momentum_slice",
      "num_turns",
      "output_name",
      "output_dir",
  ]
  for name in required:
      assert name in sig.parameters
      param = sig.parameters[name]
      assert param.default is inspect.Parameter.empty


def test_seed_arrays_public_fields():
  seeds = SeedArrays(
      positions=np.zeros((1, 3), dtype=np.float32),
      velocities=np.zeros((1, 3), dtype=np.float32),
      gammas=np.array([1.0], dtype=np.float32),
      charges=np.array([-1], dtype=np.int8),
  )
  assert hasattr(seeds, "positions")
  assert hasattr(seeds, "momenta_mevc")
  assert hasattr(seeds, "source_path")


def test_transported_npz_schema(tmp_path):
  from transport.xsuite import run_transport, seeds_to_xparticles

  positions = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
  momenta = np.array([[0.0, 0.0, 3580.0]], dtype=np.float32)
  seeds = SeedArrays(
      positions=positions,
      velocities=np.zeros((1, 3), dtype=np.float32),
      gammas=np.array([3.82], dtype=np.float32),
      charges=np.array([-1], dtype=np.int8),
      momenta_mevc=momenta,
      start_z=positions[:, 2].copy(),
  )
  particles, meta = seeds_to_xparticles(
      seeds, species="antiproton", charge_filter="antiproton"
  )
  line = xt.Line(elements=[xt.Drift(length=1.0)])
  line.particle = particles
  result = run_transport(line, particles, meta, num_turns=1)
  out = write_transport_output(result, str(tmp_path), experiment_name="contract")

  with np.load(out) as data:
      for key in _REQUIRED_TRANSPORTED_NPZ_KEYS:
          assert key in data


def test_analyze_output_contract(tmp_path):
  from transport.analysis import analyze
  from transport.xsuite import run_transport, seeds_to_xparticles

  positions = np.array([[0.001, 0.0, 0.0]], dtype=np.float32)
  momenta = np.array([[0.0, 0.0, 3580.0]], dtype=np.float32)
  seeds = SeedArrays(
      positions=positions,
      velocities=np.zeros((1, 3), dtype=np.float32),
      gammas=np.array([3.82], dtype=np.float32),
      charges=np.array([-1], dtype=np.int8),
      momenta_mevc=momenta,
      start_z=positions[:, 2].copy(),
  )
  particles, meta = seeds_to_xparticles(
      seeds, species="antiproton", charge_filter="antiproton"
  )
  line = xt.Line(elements=[xt.Drift(length=2.0)])
  line.particle = particles
  result = run_transport(line, particles, meta, num_turns=1)
  npz = write_transport_output(result, str(tmp_path), experiment_name="contract")

  outputs = analyze(npz)
  for key in _REQUIRED_ANALYZE_KEYS:
      assert key in outputs
      assert Path(outputs[key]).exists()


def test_load_seed_npz_contract(tmp_path):
  path = tmp_path / "seeds.npz"
  positions = np.array([[0.001, 0.0, 1.0]], dtype=np.float32)
  np.savez(
      path,
      positions=positions,
      velocities=np.zeros((1, 3), dtype=np.float32),
      gammas=np.array([3.8], dtype=np.float32),
      charges=np.array([-1], dtype=np.int8),
      momenta_mevc=np.array([[0.0, 0.0, 3580.0]], dtype=np.float32),
      start_z=positions[:, 2],
  )
  seeds = load_seed_npz(path)
  assert seeds.positions.shape == (1, 3)
  assert seeds.momenta_mevc is not None


def test_transport_result_public_fields():
  fields = {f.name for f in TransportResult.__dataclass_fields__.values()}
  assert "particles" in fields
  assert "conversion_meta" in fields
  assert "beamline_hash" in fields
  assert "source_path" in fields
