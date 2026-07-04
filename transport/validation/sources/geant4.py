"""Geant4 ROOT particle source via data_io."""

import numpy as np

from transport.physics.particle_data import mass_of
from transport.validation.sources.base import ParticleBatch, ParticleSource


class Geant4ParticleSource(ParticleSource):
    def __init__(self, charge_filter=None, particle_index=0, outputs_dir="interactions/runs",
                 target_filename="simulation.root", species="antiproton",
                 momentum_slice=None, n_particles=1):
        self.charge_filter = charge_filter
        self.particle_index = particle_index
        self.outputs_dir = outputs_dir
        self.target_filename = target_filename
        self.species = species
        self.momentum_slice = momentum_slice
        self.n_particles = int(n_particles)

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

        R_init = R[sel].astype(np.float64)
        V_init = V[sel].astype(np.float64)
        gamma_init = gamma[sel].astype(np.float64)
        charges_init = charges[sel]
        mass_kg = mass_of(self.species)

        return ParticleBatch(
            R=R_init, V=V_init, gamma=gamma_init, charges=charges_init,
            mass=np.full(len(sel), mass_kg, dtype=np.float64),
            species=self.species,
            metadata={
                "source_type": "geant4",
                "n_particles": len(sel),
                "root_file": str(latest_file),
                "charge_filter": self.charge_filter,
                "species": self.species,
            },
        )

    @property
    def description(self) -> str:
        return f"Geant4ParticleSource(filter={self.charge_filter}, species={self.species})"
