"""Five-stage transport: topology → construct → inherit → track → write."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import xpart as xp
import xtrack as xt

from transport.io import find_simulation_root, load_seeds

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.json"
_CHARGE = {"antiproton": -1, "proton": 1}


def _drift(spec: dict) -> xt.Drift:
    return xt.Drift(length=float(spec["length"]))


def _quadrupole(spec: dict) -> xt.Quadrupole:
    return xt.Quadrupole(length=float(spec["length"]), k1=float(spec["k1"]))


def _bend(spec: dict) -> xt.Bend:
    return xt.Bend(length=float(spec["length"]), angle=float(spec["angle"]))


ELEMENT_BUILDERS = {
    "Drift": _drift,
    "Quadrupole": _quadrupole,
    "Bend": _bend,
    "SBend": _bend,
}


class Beamline:
    """Topology instructions — an ordered list of element dicts, not an xt.Line."""

    def __init__(self):
        self.elements: list[dict] = []


class Transport:
    def __init__(self):
        self.beamline = Beamline()
        self.particle = "antiproton"
        self.count: Optional[int] = None
        self.momentum_slice = None
        self.num_turns = 1
        self.source = None
        self.output_dir = "data/transport"

        self.positions = None
        self.momenta_mevc = None
        self.charges = None

        self.line = None
        self.particles = None
        self.output_path = None

    def load_topology(self, path=None) -> None:
        """Stage 1: JSON → beamline + run fields."""
        filepath = Path(path) if path is not None else _DEFAULT_CONFIG
        if not filepath.is_absolute():
            candidate = _PROJECT_ROOT / filepath
            filepath = candidate if candidate.exists() else Path(__file__).resolve().parent / filepath
        with open(filepath, "r", encoding="utf-8") as handle:
            config = json.load(handle)

        if "beamline" in config:
            if not isinstance(config["beamline"], list):
                raise ValueError("beamline must be a list of element dicts")
            self.beamline.elements = copy.deepcopy(config["beamline"])
        if "particle" in config:
            self.particle = config["particle"]
        if "count" in config:
            self.count = config["count"]
        if "momentum_slice" in config:
            slice_ = config["momentum_slice"]
            self.momentum_slice = tuple(slice_) if slice_ is not None else None
        if "num_turns" in config:
            self.num_turns = int(config["num_turns"])
        if "source" in config:
            self.source = config["source"]
        if "output_dir" in config:
            self.output_dir = config["output_dir"]

    def construct_beamline(self) -> xt.Line:
        """Stage 2: topology → xt.Line."""
        if not self.beamline.elements:
            raise ValueError("beamline has no elements")
        elements = [_element_from_spec(spec) for spec in self.beamline.elements]
        self.line = xt.Line(elements=elements)
        return self.line

    def inherit_particles(self) -> None:
        """Stage 3: Geant4 Seeds → arrays. No-op if arrays are already set."""
        filled = (
            self.positions is not None,
            self.momenta_mevc is not None,
            self.charges is not None,
        )
        if all(filled):
            return
        if any(filled):
            raise ValueError("positions, momenta_mevc, and charges must be set together")
        root = find_simulation_root(self.source)
        self.positions, self.momenta_mevc, self.charges = load_seeds(root)
        self.source = str(root)

    def run(self) -> Path:
        """Stages 2–5. Inherit only if arrays are unset. Return NPZ path."""
        self.construct_beamline()
        self.inherit_particles()
        positions, momenta, charges = self._select_ensemble()
        self.particles = self._to_xparticles(positions, momenta, charges)
        self.line.particle = self.particles
        self.line.build_tracker()
        self.line.track(self.particles, num_turns=int(self.num_turns))
        return self._write_output()

    def _select_ensemble(self):
        positions = np.asarray(self.positions, dtype=np.float64)
        momenta = np.asarray(self.momenta_mevc, dtype=np.float64)
        charges = np.asarray(self.charges)
        if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) == 0:
            raise ValueError("positions must be a non-empty (N, 3) array")
        if momenta.shape != positions.shape:
            raise ValueError("momenta_mevc must match positions")
        if charges.shape != (len(positions),):
            raise ValueError("charges must have shape (N,)")

        species = self.particle.lower()
        if species not in _CHARGE:
            raise ValueError(f"Unsupported particle {self.particle!r}; use proton or antiproton")
        mask = charges == _CHARGE[species]

        if self.momentum_slice is not None:
            p_min, p_max = self.momentum_slice
            p_abs = np.linalg.norm(momenta, axis=1)
            mask &= (p_abs >= float(p_min) * 1e3) & (p_abs <= float(p_max) * 1e3)

        if not np.any(mask):
            raise ValueError("No particles remain after species / momentum selection")

        positions, momenta, charges = positions[mask], momenta[mask], charges[mask]
        if self.count is not None and int(self.count) > 0:
            n = min(int(self.count), len(positions))
            positions, momenta, charges = positions[:n], momenta[:n], charges[:n]
        return positions, momenta, charges

    def _to_xparticles(self, positions, momenta, charges) -> xp.Particles:
        p_abs = np.linalg.norm(momenta, axis=1)
        if not np.all(np.isfinite(p_abs)) or np.any(p_abs <= 0):
            raise ValueError("Non-finite or non-positive momentum")
        p0c_eV = float(np.median(p_abs) * 1e6)
        p0_mevc = p0c_eV / 1e6
        q0 = float(_CHARGE[self.particle.lower()])
        return xp.Particles(
            mass0=float(xt.PROTON_MASS_EV),
            q0=q0,
            p0c=p0c_eV,
            x=positions[:, 0],
            px=(momenta[:, 0] / p0_mevc),
            y=positions[:, 1],
            py=(momenta[:, 1] / p0_mevc),
            zeta=np.zeros(len(positions), dtype=np.float64),
            delta=(p_abs / p0_mevc - 1.0),
        )

    def _write_output(self) -> Path:
        run_dir = _new_run_dir(self._resolve_output_dir())
        run_dir.mkdir(parents=True, exist_ok=True)
        p = self.particles
        npz_path = run_dir / "transported_particles.npz"
        np.savez(
            npz_path,
            x=np.asarray(p.x, dtype=np.float64),
            px=np.asarray(p.px, dtype=np.float64),
            y=np.asarray(p.y, dtype=np.float64),
            py=np.asarray(p.py, dtype=np.float64),
            zeta=np.asarray(p.zeta, dtype=np.float64),
            delta=np.asarray(p.delta, dtype=np.float64),
            state=np.asarray(p.state, dtype=np.int32),
            p0c_eV=np.array(float(np.asarray(p.p0c).reshape(-1)[0]), dtype=np.float64),
            mass0_eV=np.array(float(np.asarray(p.mass0).reshape(-1)[0]), dtype=np.float64),
            q0=np.array(float(np.asarray(p.q0).reshape(-1)[0]), dtype=np.float64),
        )
        topology_path = run_dir / "topology.json"
        topology_path.write_text(json.dumps(self._topology_record(), indent=2) + "\n", encoding="utf-8")
        self.output_path = npz_path
        print(f"[Transport] Wrote {npz_path}")
        return npz_path

    def _topology_record(self) -> dict:
        slice_ = self.momentum_slice
        if slice_ is not None:
            slice_ = [float(slice_[0]), float(slice_[1])]
        return {
            "beamline": copy.deepcopy(self.beamline.elements),
            "particle": self.particle,
            "count": self.count,
            "momentum_slice": slice_,
            "num_turns": int(self.num_turns),
            "source": self.source,
            "output_dir": str(self.output_dir),
        }

    def _resolve_output_dir(self) -> Path:
        path = Path(self.output_dir)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path


def _element_from_spec(spec: dict):
    if not isinstance(spec, dict) or "type" not in spec:
        raise ValueError(f"beamline element must be a dict with 'type', got {spec!r}")
    kind = spec["type"]
    builder = ELEMENT_BUILDERS.get(kind)
    if builder is None:
        supported = ", ".join(sorted(set(ELEMENT_BUILDERS)))
        raise ValueError(f"Unknown element type {kind!r}. Supported: {supported}")
    try:
        return builder(spec)
    except KeyError as exc:
        raise ValueError(f"{kind} element missing field {exc.args[0]!r}") from exc


def _new_run_dir(output_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"run_{stamp}"
    if not run_dir.exists():
        return run_dir
    index = 1
    while True:
        candidate = output_root / f"run_{stamp}_{index}"
        if not candidate.exists():
            return candidate
        index += 1
