"""Read proton/antiproton Seeds from one Geant4 simulation.root."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import uproot

_PDG_ANTIPROTON = -2212
_PDG_PROTON = 2212
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_simulation_root(source: str | Path | None = None) -> Path:
    """Return an explicit Seeds file, or the newest data/collision/*/simulation.root."""
    if source:
        path = Path(source)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"Seeds file not found: {path}")
        return path

    outputs = _PROJECT_ROOT / "data" / "collision"
    if not outputs.is_dir():
        raise FileNotFoundError(f"No collision outputs at {outputs}")

    files = [
        d / "simulation.root"
        for d in outputs.iterdir()
        if d.is_dir() and (d / "simulation.root").exists()
    ]
    if not files:
        raise FileNotFoundError(f"No simulation.root under {outputs}")
    return max(files, key=lambda p: p.stat().st_mtime)


def load_seeds(root_path: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parse one Seeds tree. Returns positions [m], momenta [MeV/c], charges {±1}."""
    root_path = Path(root_path)
    with uproot.open(root_path) as handle:
        if "Seeds" not in handle:
            raise ValueError(f"No Seeds tree in {root_path}")
        tree = handle["Seeds"]
        pdg = tree["pdg_code"].array(library="np")
        mask = (pdg == _PDG_ANTIPROTON) | (pdg == _PDG_PROTON)
        if not np.any(mask):
            raise ValueError(f"No protons or antiprotons in {root_path}")

        x = tree["start_x"].array(library="np")[mask] * 1e-3
        y = tree["start_y"].array(library="np")[mask] * 1e-3
        z = tree["start_z"].array(library="np")[mask] * 1e-3
        px = tree["start_px"].array(library="np")[mask]
        py = tree["start_py"].array(library="np")[mask]
        pz = tree["start_pz"].array(library="np")[mask]
        charges = np.where(pdg[mask] == _PDG_ANTIPROTON, -1, 1).astype(np.int8)

    positions = np.column_stack((x, y, z)).astype(np.float64)
    momenta = np.column_stack((px, py, pz)).astype(np.float64)
    return positions, momenta, charges
