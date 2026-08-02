"""Lightweight diagnostics for transported NPZ output.

All plots and summaries are derived from the NPZ written by the transport
pipeline. No tracking is re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _load(npz_path: str | Path):
    path = Path(npz_path)
    data = np.load(path, allow_pickle=False)
    meta = json.loads(str(data["metadata_json"]))
    return data, meta, path


def _alive(data):
    mask = np.asarray(data["alive_mask"], dtype=bool)
    return mask


def _momentum_gev(data):
    """Absolute momentum [GeV/c] from stored p0c and delta."""
    p0c_eV = float(np.asarray(data["p0c_eV"]))
    delta = np.asarray(data["delta"], dtype=np.float64)
    return p0c_eV * (1.0 + delta) / 1.0e9


def plot_beam_xy(npz_path: str | Path, output_path: str | Path | None = None) -> str:
    """Scatter plot of transverse beam profile (x vs y)."""
    data, _, path = _load(npz_path)
    alive = _alive(data)
    x = np.asarray(data["x"])[alive] * 1e3  # mm
    y = np.asarray(data["y"])[alive] * 1e3

    out = Path(output_path) if output_path else path.with_name("beam_xy.png")
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(x, y, s=8, alpha=0.7, edgecolors="none")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_title("Beam profile (x–y)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def plot_phase_space(npz_path: str | Path, output_path: str | Path | None = None) -> str:
    """Scatter plot of horizontal phase space (x vs px)."""
    data, _, path = _load(npz_path)
    alive = _alive(data)
    x = np.asarray(data["x"])[alive] * 1e3  # mm
    px = np.asarray(data["px"])[alive]

    out = Path(output_path) if output_path else path.with_name("phase_space.png")
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(x, px, s=8, alpha=0.7, edgecolors="none")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel(r"$p_x / p_0$")
    ax.set_title("Horizontal phase space")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def plot_momentum_histogram(
    npz_path: str | Path, output_path: str | Path | None = None
) -> str:
    """Histogram of absolute particle momentum."""
    data, _, path = _load(npz_path)
    alive = _alive(data)
    p_gev = _momentum_gev(data)[alive]

    out = Path(output_path) if output_path else path.with_name("momentum_histogram.png")
    fig, ax = plt.subplots(figsize=(7, 5))
    bins = min(50, max(10, int(np.sqrt(len(p_gev))))) if len(p_gev) else 10
    ax.hist(p_gev, bins=bins, histtype="stepfilled", alpha=0.75, edgecolor="black")
    ax.set_xlabel("Momentum [GeV/c]")
    ax.set_ylabel("Counts")
    ax.set_title("Momentum spectrum")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def plot_beamline(npz_path: str | Path, output_path: str | Path | None = None) -> str:
    """Simple static schematic of element order and lengths."""
    data, meta, path = _load(npz_path)
    elements = meta.get("beamline_elements", [])
    out = Path(output_path) if output_path else path.with_name("beamline.png")

    labels = []
    lengths = []
    for el in elements:
        etype = el.get("type", "Element")
        length = el.get("length")
        if length is not None:
            labels.append(f"{etype}\n({float(length):.3g} m)")
            lengths.append(max(float(length), 0.05))
        else:
            labels.append(etype)
            lengths.append(1.0)

    if not labels:
        labels = ["(empty line)"]
        lengths = [1.0]

    total = sum(lengths)
    widths = [L / total for L in lengths]

    fig, ax = plt.subplots(figsize=(max(8, 1.5 * len(labels)), 2.8))
    left = 0.0
    colors = plt.cm.tab20(np.linspace(0, 1, len(labels)))
    for label, width, color in zip(labels, widths, colors):
        ax.barh(0, width, left=left, height=0.6, color=color, edgecolor="black")
        ax.text(
            left + width / 2,
            0,
            label,
            ha="center",
            va="center",
            fontsize=9,
            wrap=True,
        )
        left += width

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.8, 0.8)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_title("Beamline overview")
    ax.set_xlabel("Relative length along beamline →")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def write_summary(npz_path: str | Path, output_path: str | Path | None = None) -> str:
    """Write a human-readable transport summary beside the NPZ."""
    data, meta, path = _load(npz_path)
    alive = _alive(data)
    x = np.asarray(data["x"], dtype=np.float64)
    y = np.asarray(data["y"], dtype=np.float64)
    p_gev = _momentum_gev(data)

    n_generated = int(len(x))
    n_transported = int(np.sum(alive))
    transmission = (n_transported / n_generated) if n_generated else 0.0

    if n_transported:
        mean_p = float(np.mean(p_gev[alive]))
        std_p = float(np.std(p_gev[alive]))
        rms_x = float(np.sqrt(np.mean(x[alive] ** 2)))
        rms_y = float(np.sqrt(np.mean(y[alive] ** 2)))
    else:
        mean_p = std_p = rms_x = rms_y = float("nan")

    out = Path(output_path) if output_path else path.with_name("summary.txt")
    lines = [
        "Transport summary",
        "=================",
        f"Experiment:              {meta.get('experiment_name', path.stem)}",
        f"Particle species:        {meta.get('species', 'unknown')}",
        f"Generated particles:     {n_generated}",
        f"Transported particles:   {n_transported}",
        f"Transmission efficiency: {transmission:.4f}",
        f"Mean momentum:           {mean_p:.6g} GeV/c",
        f"Momentum std. dev.:      {std_p:.6g} GeV/c",
        f"RMS beam size x:         {rms_x:.6g} m",
        f"RMS beam size y:         {rms_y:.6g} m",
        f"Reference p0c:           {float(np.asarray(data['p0c_eV'])) / 1e9:.6g} GeV/c",
        f"Source:                  {meta.get('source_path')}",
        f"Beamline hash:           {meta.get('beamline_hash')}",
    ]
    out.write_text("\n".join(lines) + "\n")
    return str(out)


def analyze(npz_path: str | Path) -> dict[str, str]:
    """Generate all diagnostics next to a transported NPZ file."""
    path = Path(npz_path)
    if not path.exists():
        raise FileNotFoundError(f"Transported NPZ not found: {path}")

    outputs = {
        "beam_xy": plot_beam_xy(path),
        "phase_space": plot_phase_space(path),
        "momentum_histogram": plot_momentum_histogram(path),
        "beamline": plot_beamline(path),
        "summary": write_summary(path),
    }
    return outputs
