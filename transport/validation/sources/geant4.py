"""Geant4 ROOT particle source via data_io."""

import numpy as np

from transport.physics.particle_data import mass_of
from transport.validation.sources.base import ParticleBatch, ParticleSource


def _as_offset(offset) -> np.ndarray:
    if offset is None:
        return np.zeros(3, dtype=np.float64)
    arr = np.asarray(offset, dtype=np.float64).reshape(-1)
    if arr.size != 3:
        raise ValueError(f"Geant4 offset must be a length-3 [dx, dy, dz], got {offset!r}")
    return arr


def place_geant4_beam_in_lattice(
    batch: ParticleBatch,
    lattice,
    offset=None,
) -> ParticleBatch:
    """
    Place Geant4 seeds into a lattice with rigid translations only.

    Preserves:
    - all velocities, gamma, charges, and mass
    - every particle's offset from the beam centre of mass (R_i - R_com)

    Steps:
    1. Align beam COM to the lattice axis and the most-upstream particle to
       lattice.z_start (all particles start inside the pipeline).
    2. Apply an optional extra rigid ``offset`` [dx, dy, dz] in metres.
    """
    if batch.R is None or len(batch.R) == 0:
        return batch

    R = np.asarray(batch.R, dtype=np.float64)
    com = np.mean(R, axis=0)
    min_z = float(np.min(R[:, 2]))
    align_delta = np.array(
        [
            -float(com[0]),
            -float(com[1]),
            float(lattice.z_start) - min_z,
        ],
        dtype=np.float64,
    )
    user_offset = _as_offset(offset)
    delta = align_delta + user_offset
    R_placed = R + delta

    metadata = dict(batch.metadata or {})
    metadata["placement"] = {
        "mode": "rigid_com_preserving",
        "align_delta": align_delta.tolist(),
        "offset": user_offset.tolist(),
        "delta": delta.tolist(),
        "com_before": com.tolist(),
        "lattice_z_start": float(lattice.z_start),
    }
    return ParticleBatch(
        R=R_placed,
        V=np.asarray(batch.V, dtype=np.float64).copy(),
        gamma=np.asarray(batch.gamma, dtype=np.float64).copy(),
        charges=np.asarray(batch.charges).copy(),
        mass=None if batch.mass is None else np.asarray(batch.mass, dtype=np.float64).copy(),
        species=batch.species,
        metadata=metadata,
    )


class LatticePlacedParticleSource(ParticleSource):
    """Wraps a source and rigidly places its batch into a lattice on generate()."""

    def __init__(self, inner: ParticleSource, lattice, offset=None):
        self.inner = inner
        self.lattice = lattice
        self.offset = offset

    def generate(self) -> ParticleBatch:
        return place_geant4_beam_in_lattice(
            self.inner.generate(),
            self.lattice,
            offset=self.offset,
        )

    @property
    def description(self) -> str:
        return f"LatticePlaced({self.inner.description})"


class Geant4ParticleSource(ParticleSource):
    def __init__(
        self,
        charge_filter=None,
        particle_index=0,
        outputs_dir="data/collision",
        target_filename="simulation.root",
        species="antiproton",
        momentum_slice=None,
        n_particles=1,
        offset=None,
    ):
        self.charge_filter = charge_filter
        self.particle_index = particle_index
        self.outputs_dir = outputs_dir
        self.target_filename = target_filename
        self.species = species
        self.momentum_slice = momentum_slice
        self.n_particles = int(n_particles)
        self.offset = None if offset is None else _as_offset(offset)

    def generate(self) -> ParticleBatch:
        from transport.io.data_io import get_latest_run_file, extract_cern_ad_seeds

        latest_file = get_latest_run_file(
            outputs_dir_name=self.outputs_dir, target_filename=self.target_filename
        )
        R, V, gamma, charges = extract_cern_ad_seeds([latest_file])

        if self.charge_filter == "antiproton":
            mask = charges == -1
            if not np.any(mask):
                mask = charges == 1
        elif self.charge_filter == "any":
            mask = np.ones(len(charges), dtype=bool)
        else:
            mask = np.ones(len(charges), dtype=bool)

        if self.momentum_slice is not None:
            p_min, p_max = self.momentum_slice
            mom = np.linalg.norm(V, axis=1) * gamma  # approximate; data_io already filters
            mask = mask & (mom >= p_min) & (mom <= p_max)

        indices = np.where(mask)[0]
        if len(indices) == 0:
            raise ValueError("No particles matched Geant4 source filters")

        n = min(self.n_particles, len(indices))
        if n == 1:
            pick = indices[self.particle_index] if self.particle_index < len(indices) else indices[0]
            sel = np.array([pick])
        else:
            sel = indices[:n]

        # Exact Geant4 seed kinematics — no resampling or velocity changes.
        R_init = R[sel].astype(np.float64).copy()
        V_init = V[sel].astype(np.float64).copy()
        gamma_init = gamma[sel].astype(np.float64).copy()
        charges_init = charges[sel].copy()
        mass_kg = mass_of(self.species)

        return ParticleBatch(
            R=R_init,
            V=V_init,
            gamma=gamma_init,
            charges=charges_init,
            mass=np.full(len(sel), mass_kg, dtype=np.float64),
            species=self.species,
            metadata={
                "source_type": "geant4",
                "n_particles": len(sel),
                "root_file": str(latest_file),
                "charge_filter": self.charge_filter,
                "species": self.species,
                "offset": None if self.offset is None else self.offset.tolist(),
            },
        )

    @property
    def description(self) -> str:
        return f"Geant4ParticleSource(filter={self.charge_filter}, species={self.species})"
