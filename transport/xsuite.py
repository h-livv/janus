"""Janus adapters around Xsuite: NPZ seeds → Particles, track, write NPZ output.

Particle conversion and tracking call Xsuite directly. This module only owns
unit/coordinate mapping and output packaging.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import xpart as xp
import xtrack as xt

from transport.io import SeedArrays, charge_of

_MEVC_TO_EV = 1.0e6
_C_LIGHT = 299792458.0


@dataclass
class ParticleConversionMeta:
    species: str
    q0: float
    mass0_eV: float
    p0c_eV: float
    n_particles: int
    start_z: np.ndarray


@dataclass
class TransportResult:
    particles: xp.Particles
    line: xt.Line
    conversion_meta: ParticleConversionMeta
    beamline_hash: str
    source_path: Optional[str]
    output_path: Optional[str] = None
    monitor_data: dict[str, Any] = field(default_factory=dict)


def _resolve_momenta_mevc(seeds: SeedArrays, species: str) -> np.ndarray:
    if seeds.momenta_mevc is not None:
        return seeds.momenta_mevc.astype(np.float64)
    from transport.io import mass_of
    m_kg = mass_of(species)
    p_si = seeds.gammas[:, np.newaxis] * m_kg * seeds.velocities
    return (p_si * _C_LIGHT / 1e6).astype(np.float64)


def seeds_to_xparticles(
    seeds: SeedArrays,
    species: str = "antiproton",
    charge_filter: str = "any",
    p0c_eV: Optional[float] = None,
    n_particles: Optional[int] = None,
) -> tuple[xp.Particles, ParticleConversionMeta]:
    """Convert validated seed arrays into xpart.Particles for Xsuite tracking."""
    if seeds.positions.size == 0:
        raise ValueError("Cannot build Xsuite particles from an empty seed selection")

    charges = seeds.charges
    mask = np.ones(len(charges), dtype=bool)
    expected_charge = charge_of(species)

    if charge_filter == "antiproton":
        mask &= charges == -1
    elif charge_filter == "proton":
        mask &= charges == 1
    elif charge_filter == "any":
        mask &= np.isin(charges, (-1, 1))
    else:
        raise ValueError(f"Unsupported charge_filter '{charge_filter}'")

    if not np.any(mask):
        raise ValueError(f"No particles matched charge_filter='{charge_filter}'")

    sel_charges = charges[mask]
    if not np.all(sel_charges == sel_charges[0]):
        raise ValueError("Mixed charge signs in selection; single-species ensemble required")
    if int(sel_charges[0]) != expected_charge:
        raise ValueError(
            f"Selected charge {int(sel_charges[0])} inconsistent with species '{species}' "
            f"(expected {expected_charge})"
        )

    filtered = SeedArrays(
        positions=seeds.positions[mask],
        velocities=seeds.velocities[mask],
        gammas=seeds.gammas[mask],
        charges=sel_charges,
        momenta_mevc=seeds.momenta_mevc[mask] if seeds.momenta_mevc is not None else None,
        start_z=seeds.start_z[mask] if seeds.start_z is not None else seeds.positions[mask, 2],
        source_path=seeds.source_path,
    )

    positions = filtered.positions
    momenta_mevc = _resolve_momenta_mevc(filtered, species)

    if n_particles is not None and n_particles > 0:
        n = min(int(n_particles), len(positions))
        positions = positions[:n]
        momenta_mevc = momenta_mevc[:n]
        sel_charges = sel_charges[:n]
        filtered.start_z = filtered.start_z[:n]

    p_abs_mevc = np.linalg.norm(momenta_mevc, axis=1)
    if not np.all(np.isfinite(p_abs_mevc)) or np.any(p_abs_mevc <= 0):
        raise ValueError("Non-finite or non-positive momentum in seed selection")

    if p0c_eV is None:
        p0c_eV = float(np.median(p_abs_mevc) * _MEVC_TO_EV)
    else:
        p0c_eV = float(p0c_eV)

    p0_mevc = p0c_eV / _MEVC_TO_EV
    px = momenta_mevc[:, 0] / p0_mevc
    py = momenta_mevc[:, 1] / p0_mevc
    delta = p_abs_mevc / p0_mevc - 1.0

    mass0_eV = float(xt.PROTON_MASS_EV)
    q0 = float(expected_charge)

    particles = xp.Particles(
        mass0=mass0_eV,
        q0=q0,
        p0c=p0c_eV,
        x=positions[:, 0].astype(np.float64),
        px=px.astype(np.float64),
        y=positions[:, 1].astype(np.float64),
        py=py.astype(np.float64),
        zeta=np.zeros(len(positions), dtype=np.float64),
        delta=delta.astype(np.float64),
    )

    start_z = filtered.start_z.copy()
    meta = ParticleConversionMeta(
        species=species,
        q0=q0,
        mass0_eV=mass0_eV,
        p0c_eV=p0c_eV,
        n_particles=len(positions),
        start_z=start_z,
    )
    return particles, meta


def line_config_hash(line: xt.Line) -> str:
    """Stable hash of an xtrack.Line for output metadata."""
    payload = []
    for el in line.elements:
        entry = {"type": el.__class__.__name__}
        if hasattr(el, "length"):
            entry["length"] = float(el.length)
        if hasattr(el, "k1"):
            entry["k1"] = float(el.k1)
        if hasattr(el, "angle"):
            entry["angle"] = float(el.angle)
        payload.append(entry)
    encoded = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def run_transport(
    line: xt.Line,
    particles: xp.Particles,
    conversion_meta: ParticleConversionMeta,
    *,
    source_path: Optional[str] = None,
    beamline_hash: str = "",
    num_turns: int = 1,
) -> TransportResult:
    """Track particles through an Xsuite line."""
    if line.particle is None:
        line.particle = particles
    line.build_tracker()
    line.track(particles, num_turns=int(num_turns))
    return TransportResult(
        particles=particles,
        line=line,
        conversion_meta=conversion_meta,
        beamline_hash=beamline_hash or line_config_hash(line),
        source_path=source_path,
    )


def write_transport_output(
    result: TransportResult,
    output_dir: str,
    *,
    experiment_name: str = "transport",
    beamline_summary: Optional[list[dict]] = None,
) -> str:
    """Write transported particle state to an optimization-ready NPZ file."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "transported_particles.npz")

    p = result.particles
    meta = result.conversion_meta

    alive_mask = np.asarray(p.state) > 0

    if beamline_summary is None:
        beamline_summary = []
        for el in result.line.elements:
            entry = {"type": el.__class__.__name__}
            if hasattr(el, "length"):
                entry["length"] = float(el.length)
            if hasattr(el, "k1"):
                entry["k1"] = float(el.k1)
            if hasattr(el, "angle"):
                entry["angle"] = float(el.angle)
            beamline_summary.append(entry)

    metadata = {
        "experiment_name": experiment_name,
        "source_path": result.source_path,
        "seed_count": int(meta.n_particles),
        "species": meta.species,
        "q0": meta.q0,
        "mass0_eV": meta.mass0_eV,
        "p0c_eV": meta.p0c_eV,
        "beamline_hash": result.beamline_hash,
        "beamline_elements": beamline_summary,
        "engine": "xsuite",
    }

    np.savez(
        output_path,
        x=np.asarray(p.x, dtype=np.float64),
        px=np.asarray(p.px, dtype=np.float64),
        y=np.asarray(p.y, dtype=np.float64),
        py=np.asarray(p.py, dtype=np.float64),
        zeta=np.asarray(p.zeta, dtype=np.float64),
        delta=np.asarray(p.delta, dtype=np.float64),
        state=np.asarray(p.state, dtype=np.int32),
        at_element=np.asarray(p.at_element, dtype=np.int32),
        alive_mask=alive_mask.astype(np.bool_),
        p0c_eV=np.array(meta.p0c_eV, dtype=np.float64),
        mass0_eV=np.array(meta.mass0_eV, dtype=np.float64),
        q0=np.array(meta.q0, dtype=np.float64),
        start_z=np.asarray(meta.start_z, dtype=np.float64),
        metadata_json=np.array(json.dumps(metadata)),
    )
    result.output_path = output_path
    return output_path
