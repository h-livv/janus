"""Single-particle source from explicit arrays."""

import numpy as np

from transport.physics.particle_data import mass_of
from transport.validation.sources.base import ParticleBatch, ParticleSource


def _species_mass(species, n):
    mass_kg = mass_of(species)
    return np.full(n, mass_kg, dtype=np.float64)


class SingleParticleSource(ParticleSource):
    def __init__(self, R, V, gamma, charges, metadata=None):
        self.R = np.asarray(R, dtype=np.float64)
        self.V = np.asarray(V, dtype=np.float64)
        self.gamma = np.asarray(gamma, dtype=np.float64)
        self.charges = np.asarray(charges)
        self._metadata = metadata or {}

    def generate(self) -> ParticleBatch:
        species = self._metadata.get("species", "proton")
        n = len(self.R)
        return ParticleBatch(
            R=self.R.copy(),
            V=self.V.copy(),
            gamma=self.gamma.copy(),
            charges=self.charges.copy(),
            mass=_species_mass(species, n),
            species=species,
            metadata={
                "source_type": "single",
                "n_particles": n,
                "species": species,
                **self._metadata,
            },
        )

    @property
    def description(self) -> str:
        return f"SingleParticleSource(N={len(self.R)})"
