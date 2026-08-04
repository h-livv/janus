"""Structured transport observables from in-memory transport outputs.

Metrics are defined over ``TransportResult`` (or equivalent arrays). NPZ files
are a persistence mechanism; offline recomputation uses a thin adapter.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from transport.xsuite import TransportResult

SCHEMA_VERSION = "1.0"


@dataclass
class TransportMetrics:
    """Scientific observables from a single transport execution."""

    schema_version: str
    experiment_name: str
    species: str
    generated_count: int
    transported_count: int
    beam_losses: int
    transmission: float
    rms_x_m: float
    rms_y_m: float
    mean_momentum_gevc: float
    momentum_spread_gevc: float
    centroid_x_m: float
    centroid_y_m: float
    emit_x_m: float
    emit_y_m: float
    p0c_gevc: float
    source_path: Optional[str]
    beamline_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _momentum_gev_from_arrays(p0c_eV: float, delta: np.ndarray) -> np.ndarray:
    return float(p0c_eV) * (1.0 + delta) / 1.0e9


def _emittance_m(x: np.ndarray, px: np.ndarray) -> float:
    if len(x) < 2:
        return float("nan")
    mx = float(np.mean(x))
    mpx = float(np.mean(px))
    xx = float(np.mean((x - mx) ** 2))
    pxpx = float(np.mean((px - mpx) ** 2))
    xpx = float(np.mean((x - mx) * (px - mpx)))
    val = xx * pxpx - xpx ** 2
    if val <= 0:
        return 0.0
    return float(np.sqrt(val))


def _compute_from_arrays(
    *,
    x: np.ndarray,
    y: np.ndarray,
    px: np.ndarray,
    py: np.ndarray,
    delta: np.ndarray,
    alive_mask: np.ndarray,
    p0c_eV: float,
    species: str,
    experiment_name: str,
    source_path: Optional[str],
    beamline_hash: str,
) -> TransportMetrics:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    px = np.asarray(px, dtype=np.float64)
    py = np.asarray(py, dtype=np.float64)
    delta = np.asarray(delta, dtype=np.float64)
    alive = np.asarray(alive_mask, dtype=bool)

    n_generated = int(len(x))
    n_transported = int(np.sum(alive))
    beam_losses = n_generated - n_transported
    transmission = (n_transported / n_generated) if n_generated else 0.0
    p_gev = _momentum_gev_from_arrays(p0c_eV, delta)

    if n_transported:
        xa, ya = x[alive], y[alive]
        pxa, pya = px[alive], py[alive]
        pa = p_gev[alive]
        mean_p = float(np.mean(pa))
        std_p = float(np.std(pa))
        rms_x = float(np.sqrt(np.mean(xa ** 2)))
        rms_y = float(np.sqrt(np.mean(ya ** 2)))
        centroid_x = float(np.mean(xa))
        centroid_y = float(np.mean(ya))
        emit_x = _emittance_m(xa, pxa)
        emit_y = _emittance_m(ya, pya)
    else:
        mean_p = std_p = rms_x = rms_y = float("nan")
        centroid_x = centroid_y = float("nan")
        emit_x = emit_y = float("nan")

    return TransportMetrics(
        schema_version=SCHEMA_VERSION,
        experiment_name=experiment_name,
        species=species,
        generated_count=n_generated,
        transported_count=n_transported,
        beam_losses=beam_losses,
        transmission=transmission,
        rms_x_m=rms_x,
        rms_y_m=rms_y,
        mean_momentum_gevc=mean_p,
        momentum_spread_gevc=std_p,
        centroid_x_m=centroid_x,
        centroid_y_m=centroid_y,
        emit_x_m=emit_x,
        emit_y_m=emit_y,
        p0c_gevc=float(p0c_eV) / 1.0e9,
        source_path=source_path,
        beamline_hash=beamline_hash,
    )


def compute_transport_metrics(
    result: TransportResult,
    experiment_name: str,
) -> TransportMetrics:
    """Compute metrics from an in-memory transport result."""
    p = result.particles
    meta = result.conversion_meta
    alive_mask = np.asarray(p.state) > 0
    return _compute_from_arrays(
        x=np.asarray(p.x),
        y=np.asarray(p.y),
        px=np.asarray(p.px),
        py=np.asarray(p.py),
        delta=np.asarray(p.delta),
        alive_mask=alive_mask,
        p0c_eV=meta.p0c_eV,
        species=meta.species,
        experiment_name=experiment_name,
        source_path=result.source_path,
        beamline_hash=result.beamline_hash,
    )


def metrics_from_npz(npz_path: str | Path) -> TransportMetrics:
    """Offline adapter: recompute metrics from a persisted transported NPZ."""
    path = Path(npz_path)
    with np.load(path, allow_pickle=False) as data:
        meta = json.loads(str(data["metadata_json"]))
        return _compute_from_arrays(
            x=data["x"],
            y=data["y"],
            px=data["px"],
            py=data["py"],
            delta=data["delta"],
            alive_mask=data["alive_mask"],
            p0c_eV=float(np.asarray(data["p0c_eV"])),
            species=str(meta.get("species", "unknown")),
            experiment_name=str(meta.get("experiment_name", path.stem)),
            source_path=meta.get("source_path"),
            beamline_hash=str(meta.get("beamline_hash", "")),
        )


def write_metrics(metrics: TransportMetrics, output_dir: str | Path) -> str:
    """Serialize metrics to ``metrics.json`` beside run outputs."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "metrics.json"
    out_path.write_text(json.dumps(metrics.to_dict(), indent=2) + "\n")
    return str(out_path)


def load_metrics(path: str | Path) -> TransportMetrics:
    """Load metrics from ``metrics.json``."""
    data = json.loads(Path(path).read_text())
    return TransportMetrics(**data)
