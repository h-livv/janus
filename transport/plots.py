"""Diagnostic plots written beside a transported NPZ. No metrics or summaries."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def write_plots(npz_path: str | Path) -> None:
    """Write beam_xy, phase_space, momentum_histogram, and beamline PNGs."""
    path = Path(npz_path)
    data = np.load(path)
    alive = np.asarray(data["state"]) > 0
    if not np.any(alive):
        alive = np.ones(len(data["x"]), dtype=bool)
    x = np.asarray(data["x"])[alive]
    y = np.asarray(data["y"])[alive]
    px = np.asarray(data["px"])[alive]
    delta = np.asarray(data["delta"], dtype=np.float64)[alive]
    p0c_eV = float(np.asarray(data["p0c_eV"]).reshape(-1)[0])
    p_gev = p0c_eV * (1.0 + delta) / 1.0e9

    topology = {}
    topo_path = path.with_name("topology.json")
    if topo_path.exists():
        topology = json.loads(topo_path.read_text(encoding="utf-8"))

    _scatter(path.with_name("beam_xy.png"), x * 1e3, y * 1e3, "x [mm]", "y [mm]", "Beam profile (x–y)", equal=True)
    _scatter(path.with_name("phase_space.png"), x * 1e3, px, "x [mm]", r"$p_x / p_0$", "Horizontal phase space")
    _histogram(path.with_name("momentum_histogram.png"), p_gev)
    _beamline(path.with_name("beamline.png"), topology.get("beamline", []))


def _scatter(out, x, y, xlabel, ylabel, title, *, equal=False):
    fig, ax = plt.subplots(figsize=(6, 6) if equal else (7, 5))
    ax.scatter(x, y, s=8, alpha=0.7, edgecolors="none")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if equal:
        ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def _histogram(out, p_gev):
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


def _beamline(out, elements):
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
    widths = [length / total for length in lengths]
    fig, ax = plt.subplots(figsize=(max(8, 1.5 * len(labels)), 2.8))
    left = 0.0
    colors = plt.cm.tab20(np.linspace(0, 1, len(labels)))
    for label, width, color in zip(labels, widths, colors):
        ax.barh(0, width, left=left, height=0.6, color=color, edgecolor="black")
        ax.text(left + width / 2, 0, label, ha="center", va="center", fontsize=9)
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
