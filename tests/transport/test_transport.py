"""Five-stage Transport: topology, construct, inherit, track, write."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import uproot
import xtrack as xt

from transport.interface import ELEMENT_BUILDERS, Transport


def _synthetic(n=1, x=0.001, px=0.0, py=0.0, pz=3580.0, charge=-1):
    positions = np.zeros((n, 3), dtype=np.float64)
    positions[:, 0] = x
    momenta = np.tile([px, py, pz], (n, 1)).astype(np.float64)
    charges = np.full(n, charge, dtype=np.int8)
    return positions, momenta, charges


def _ready(tmp_path, *, n=1, px=0.0, py=0.0, pz=3580.0, charge=-1):
    transport = Transport()
    transport.output_dir = str(tmp_path)
    transport.beamline.elements = [{"type": "Drift", "length": 10.0}]
    transport.positions, transport.momenta_mevc, transport.charges = _synthetic(
        n=n, px=px, py=py, pz=pz, charge=charge
    )
    return transport


def _write_seeds_root(path: Path, *, n_pbar=2, n_proton=1):
    n = n_pbar + n_proton
    pdg = np.array([-2212] * n_pbar + [2212] * n_proton, dtype=np.int32)
    with uproot.recreate(path) as handle:
        handle["Seeds"] = {
            "pdg_code": pdg,
            "start_x": np.full(n, 1.0),
            "start_y": np.zeros(n),
            "start_z": np.zeros(n),
            "start_px": np.zeros(n),
            "start_py": np.zeros(n),
            "start_pz": np.full(n, 3580.0),
        }


def test_load_topology_fills_beamline(tmp_path):
    config = {
        "beamline": [
            {"type": "Drift", "length": 4.0},
            {"type": "Quadrupole", "length": 1.0, "k1": 0.2},
        ],
        "particle": "proton",
        "count": 7,
        "momentum_slice": [1.0, 2.0],
        "num_turns": 3,
        "source": "data/collision/example/simulation.root",
        "output_dir": "data/custom",
    }
    path = tmp_path / "topology.json"
    path.write_text(json.dumps(config))

    transport = Transport()
    transport.load_topology(path)

    assert transport.beamline.elements == config["beamline"]
    assert transport.particle == "proton"
    assert transport.count == 7
    assert transport.momentum_slice == (1.0, 2.0)
    assert transport.num_turns == 3
    assert transport.source == config["source"]
    assert transport.output_dir == "data/custom"


def test_load_default_config():
    transport = Transport()
    transport.load_topology()
    assert transport.beamline.elements[0]["type"] == "Drift"
    assert transport.particle == "antiproton"
    assert any(el["type"] == "Quadrupole" for el in transport.beamline.elements)


def test_construct_beamline_types_and_lengths():
    transport = Transport()
    transport.beamline.elements = [
        {"type": "Drift", "length": 5.0},
        {"type": "Quadrupole", "length": 1.0, "k1": 0.5},
        {"type": "Bend", "length": 2.0, "angle": 0.01},
    ]
    line = transport.construct_beamline()
    assert len(line.elements) == 3
    assert isinstance(line.elements[0], xt.Drift)
    assert line.elements[0].length == 5.0
    assert isinstance(line.elements[1], xt.Quadrupole)
    assert line.elements[1].k1 == 0.5
    assert isinstance(line.elements[2], xt.Bend)
    assert line.elements[2].angle == 0.01


def test_construct_unknown_type_fails():
    transport = Transport()
    transport.beamline.elements = [{"type": "Horn", "length": 1.0}]
    with pytest.raises(ValueError, match="Unknown element type"):
        transport.construct_beamline()
    assert "Drift" in ELEMENT_BUILDERS


def test_inherit_from_seeds_root(tmp_path):
    root = tmp_path / "simulation.root"
    _write_seeds_root(root, n_pbar=2, n_proton=1)
    transport = Transport()
    transport.source = str(root)
    transport.inherit_particles()
    assert len(transport.positions) == 3
    assert np.allclose(transport.positions[:, 0], 0.001)
    assert np.allclose(transport.momenta_mevc[:, 2], 3580.0)
    assert list(transport.charges) == [-1, -1, 1]
    assert transport.source == str(root)


def test_inherit_is_noop_when_arrays_set():
    transport = Transport()
    transport.positions, transport.momenta_mevc, transport.charges = _synthetic()
    transport.source = "should-not-be-opened.root"
    transport.inherit_particles()
    assert transport.source == "should-not-be-opened.root"


def test_run_tracks_drift_and_writes_npz(tmp_path):
    transport = _ready(tmp_path, px=35.8, py=17.9)
    npz_path = transport.run()

    assert npz_path.exists()
    assert npz_path.name == "transported_particles.npz"
    topology = json.loads((npz_path.parent / "topology.json").read_text())
    assert topology["beamline"][0]["type"] == "Drift"
    assert topology["particle"] == "antiproton"

    with np.load(npz_path) as data:
        for key in ("x", "px", "y", "py", "zeta", "delta", "state", "p0c_eV", "mass0_eV", "q0"):
            assert key in data
        p0_mevc = float(data["p0c_eV"]) / 1e6
        assert np.isclose(data["px"][0], 35.8 / p0_mevc, rtol=1e-5)
        assert np.isclose(data["py"][0], 17.9 / p0_mevc, rtol=1e-5)
        assert float(data["q0"]) == -1.0
        assert float(data["mass0_eV"]) == pytest.approx(xt.PROTON_MASS_EV)

    assert transport.particles is not None
    assert np.isfinite(transport.particles.x[0])
    run_dir = npz_path.parent
    for name in ("beam_xy.png", "phase_space.png", "momentum_histogram.png", "beamline.png"):
        assert (run_dir / name).exists()


def test_species_and_count_selection(tmp_path):
    transport = Transport()
    transport.output_dir = str(tmp_path)
    transport.beamline.elements = [{"type": "Drift", "length": 1.0}]
    positions = np.zeros((4, 3))
    momenta = np.tile([0.0, 0.0, 3580.0], (4, 1))
    charges = np.array([-1, -1, -1, 1], dtype=np.int8)
    transport.positions, transport.momenta_mevc, transport.charges = positions, momenta, charges
    transport.particle = "antiproton"
    transport.count = 2
    transport.run()
    assert len(transport.particles.x) == 2


def test_momentum_slice(tmp_path):
    transport = Transport()
    transport.output_dir = str(tmp_path)
    transport.beamline.elements = [{"type": "Drift", "length": 1.0}]
    positions = np.zeros((3, 3))
    momenta = np.array([[0, 0, 1000.0], [0, 0, 3580.0], [0, 0, 5000.0]])
    charges = np.full(3, -1, dtype=np.int8)
    transport.positions, transport.momenta_mevc, transport.charges = positions, momenta, charges
    transport.momentum_slice = (3.0, 4.0)
    transport.run()
    assert len(transport.particles.x) == 1
    p0_mevc = float(np.asarray(transport.particles.p0c).reshape(-1)[0]) / 1e6
    assert np.isclose(p0_mevc * (1.0 + transport.particles.delta[0]), 3580.0, rtol=1e-6)


def test_inherit_once_then_mutate_topology(tmp_path):
    transport = Transport()
    transport.output_dir = str(tmp_path)
    transport.positions, transport.momenta_mevc, transport.charges = _synthetic()
    transport.inherit_particles()
    stored = transport.positions.copy()

    paths = []
    for k1 in (0.4, 0.6):
        transport.beamline.elements = [
            {"type": "Drift", "length": 1.0},
            {"type": "Quadrupole", "length": 0.5, "k1": k1},
        ]
        transport.construct_beamline()
        paths.append(transport.run())
        assert np.allclose(transport.positions, stored)

    assert paths[0] != paths[1]
    assert all(p.exists() for p in paths)
    k1_values = [
        json.loads((p.parent / "topology.json").read_text())["beamline"][1]["k1"]
        for p in paths
    ]
    assert k1_values == [0.4, 0.6]
