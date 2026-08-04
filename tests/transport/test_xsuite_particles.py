"""Tests for Janus-to-Xsuite particle conversion."""

import numpy as np
import pytest
import xtrack as xt

from transport.io import SeedArrays
from transport.xsuite import seeds_to_xparticles


def _antiproton_seeds(n=1, px_mevc=0.0, py_mevc=0.0, pz_mevc=3580.0):
    positions = np.zeros((n, 3), dtype=np.float32)
    positions[:, 0] = 0.001
    momenta = np.tile([px_mevc, py_mevc, pz_mevc], (n, 1)).astype(np.float32)
    return SeedArrays(
        positions=positions,
        velocities=np.zeros((n, 3), dtype=np.float32),
        gammas=np.full(n, 3.82, dtype=np.float32),
        charges=np.full(n, -1, dtype=np.int8),
        momenta_mevc=momenta,
        start_z=positions[:, 2].copy(),
    )


def test_seeds_to_xparticles_coordinates():
    seeds = _antiproton_seeds(px_mevc=35.8, py_mevc=17.9)
    particles, meta = seeds_to_xparticles(
        seeds, species="antiproton", charge_filter="any"
    )

    p0_mevc = meta.p0c_eV / 1e6
    assert np.isclose(particles.x[0], 0.001)
    assert np.isclose(particles.y[0], 0.0)
    assert np.isclose(particles.px[0], 35.8 / p0_mevc)
    assert np.isclose(particles.py[0], 17.9 / p0_mevc)
    assert particles.zeta[0] == 0.0
    assert meta.q0 == -1.0
    assert meta.mass0_eV == xt.PROTON_MASS_EV


def test_seeds_to_xparticles_rejects_mixed_charge():
    seeds = SeedArrays(
        positions=np.zeros((2, 3), dtype=np.float32),
        velocities=np.zeros((2, 3), dtype=np.float32),
        gammas=np.array([3.8, 3.8], dtype=np.float32),
        charges=np.array([-1, 1], dtype=np.int8),
        momenta_mevc=np.tile([0, 0, 3580.0], (2, 1)).astype(np.float32),
        start_z=np.zeros(2, dtype=np.float32),
    )
    with pytest.raises(ValueError, match="Mixed charge"):
        seeds_to_xparticles(seeds, species="antiproton", charge_filter="any")
