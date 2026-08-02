"""Tests for Janus NPZ seed loading boundary."""

import numpy as np
import pytest

from transport.io import SeedArrays, load_seed_npz


def _write_seed_npz(path, *, with_momenta=True):
    positions = np.array([[0.001, 0.0, 1.0], [0.002, 0.0, 2.0]], dtype=np.float32)
    velocities = np.array(
        [[0.0, 0.0, 2.99e8], [0.0, 0.0, 2.99e8]], dtype=np.float32
    )
    gammas = np.array([3.8, 3.8], dtype=np.float32)
    charges = np.array([-1, -1], dtype=np.int8)
    kwargs = dict(positions=positions, velocities=velocities, gammas=gammas, charges=charges)
    if with_momenta:
        kwargs["momenta_mevc"] = np.array(
            [[0.0, 0.0, 3580.0], [0.0, 0.0, 3580.0]], dtype=np.float32
        )
        kwargs["start_z"] = positions[:, 2]
    np.savez(path, **kwargs)


def test_load_seed_npz_required_keys(tmp_path):
    path = tmp_path / "seeds.npz"
    _write_seed_npz(path)
    seeds = load_seed_npz(path)
    assert isinstance(seeds, SeedArrays)
    assert seeds.positions.shape == (2, 3)
    assert seeds.momenta_mevc is not None
    assert seeds.start_z is not None


def test_load_seed_npz_missing_key_raises(tmp_path):
    path = tmp_path / "bad.npz"
    np.savez(path, positions=np.zeros((1, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="missing required keys"):
        load_seed_npz(path)


def test_load_seed_npz_empty_raises(tmp_path):
    path = tmp_path / "empty.npz"
    np.savez(
        path,
        positions=np.zeros((0, 3), dtype=np.float32),
        velocities=np.zeros((0, 3), dtype=np.float32),
        gammas=np.zeros((0,), dtype=np.float32),
        charges=np.zeros((0,), dtype=np.int8),
    )
    with pytest.raises(ValueError, match="zero particles"):
        load_seed_npz(path)


def test_load_seed_npz_legacy_without_momenta(tmp_path):
    path = tmp_path / "legacy.npz"
    _write_seed_npz(path, with_momenta=False)
    seeds = load_seed_npz(path)
    assert seeds.momenta_mevc is None
    assert seeds.start_z is not None
