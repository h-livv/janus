"""Xsuite transport pipeline: receive experiment parameters → execute stages.

This module owns orchestration only. It does not invent scientific parameters;
every experiment-specific value must be supplied by the caller (the experiment).
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Optional

import numpy as np
import xtrack as xt

from transport.io import SeedArrays, load_geant4_seeds
from transport.xsuite import (
    line_config_hash,
    run_transport,
    seeds_to_xparticles,
    write_transport_output,
)


def _apply_momentum_slice(seeds: SeedArrays, momentum_slice) -> SeedArrays:
    """Filter seeds by total momentum. ``momentum_slice`` is (p_min, p_max) in GeV/c."""
    if momentum_slice is None:
        return seeds
    p_min_gev, p_max_gev = momentum_slice
    p_min = float(p_min_gev) * 1e3
    p_max = float(p_max_gev) * 1e3
    if seeds.momenta_mevc is None:
        raise ValueError("momentum_slice requires momenta_mevc on seed arrays")
    p_abs = np.linalg.norm(seeds.momenta_mevc, axis=1)
    mask = (p_abs >= p_min) & (p_abs <= p_max)
    if not np.any(mask):
        raise ValueError(f"No particles in momentum_slice={momentum_slice} GeV/c")
    return SeedArrays(
        positions=seeds.positions[mask],
        velocities=seeds.velocities[mask],
        gammas=seeds.gammas[mask],
        charges=seeds.charges[mask],
        momenta_mevc=seeds.momenta_mevc[mask],
        start_z=seeds.start_z[mask] if seeds.start_z is not None else None,
        source_path=seeds.source_path,
    )


def run(
    *,
    line: xt.Line,
    particle: str,
    count: Optional[int],
    momentum_slice,
    num_turns: int,
    output_name: str,
    output_dir: str,
    seeds: Optional[SeedArrays] = None,
    p0c_eV: Optional[float] = None,
    write_npz: bool = True,
    run_outputs_dir: Optional[str] = None,
):
    """Track particles through an Xsuite line and write transported NPZ output.

    All scientific parameters are required from the experiment. This function
    only loads (if needed), filters, converts, tracks, and writes.
    """
    if seeds is None:
        seeds = load_geant4_seeds()
    seeds = _apply_momentum_slice(seeds, momentum_slice)

    # Charge selection follows the experiment's particle species.
    charge_filter = particle.lower() if particle.lower() in ("antiproton", "proton") else "any"

    xparticles, conversion_meta = seeds_to_xparticles(
        seeds,
        species=particle,
        charge_filter=charge_filter,
        p0c_eV=p0c_eV,
        n_particles=count,
    )
    line.particle = xparticles
    bl_hash = line_config_hash(line)

    result = run_transport(
        line,
        xparticles,
        conversion_meta,
        source_path=seeds.source_path,
        beamline_hash=bl_hash,
        num_turns=num_turns,
    )

    if run_outputs_dir is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_outputs_dir = os.path.join(output_dir, f"run_{timestamp}")

    if write_npz:
        output_path = write_transport_output(
            result,
            run_outputs_dir,
            experiment_name=output_name,
        )
        print(f"[Transport] Wrote transported NPZ: {output_path}")
        from transport.analysis import analyze
        diagnostics = analyze(output_path)
        print(f"[Analysis] Wrote diagnostics: {', '.join(Path(p).name for p in diagnostics.values())}")

    print(
        f"[Transport] Tracked {conversion_meta.n_particles} particle(s) through "
        f"{len(line.elements)} element(s)."
    )
    return result, run_outputs_dir
