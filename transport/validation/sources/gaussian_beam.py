"""Gaussian beam particle source."""

import numpy as np

from transport.physics.particle_data import mass_of
from transport.validation.sources.base import ParticleBatch, ParticleSource


class GaussianBeamSource(ParticleSource):
    def __init__(self, R_center, V_center, gamma, charges, n_particles,
                 pos_sigma=0.0, vel_sigma=0.0, rng_seed=42, metadata=None):
        self.R_center = np.asarray(R_center, dtype=np.float64).reshape(1, 3)
        self.V_center = np.asarray(V_center, dtype=np.float64).reshape(1, 3)
        self.gamma = np.asarray(gamma, dtype=np.float64)
        self.charges = np.asarray(charges)
        self.n_particles = n_particles
        self.pos_sigma = pos_sigma
        self.vel_sigma = vel_sigma
        self.rng_seed = rng_seed
        self._metadata = metadata or {}

    def generate(self) -> ParticleBatch:
        rng = np.random.default_rng(self.rng_seed)
        R = np.tile(self.R_center, (self.n_particles, 1))
        V = np.tile(self.V_center, (self.n_particles, 1))
        R[:, 0] += rng.normal(0.0, self.pos_sigma, self.n_particles)
        R[:, 1] += rng.normal(0.0, self.pos_sigma, self.n_particles)
        V[:, 0] += rng.normal(0.0, self.vel_sigma, self.n_particles)
        V[:, 1] += rng.normal(0.0, self.vel_sigma, self.n_particles)
        gamma = np.tile(self.gamma, self.n_particles) if np.ndim(self.gamma) == 0 else np.tile(self.gamma, self.n_particles)
        charges = np.tile(self.charges, self.n_particles)
        species = self._metadata.get("species", "proton")
        mass_kg = mass_of(species)
        return ParticleBatch(
            R=R, V=V, gamma=gamma, charges=charges,
            mass=np.full(self.n_particles, mass_kg, dtype=np.float64),
            species=species,
            metadata={
                "source_type": "gaussian_beam",
                "n_particles": self.n_particles,
                "pos_sigma": self.pos_sigma,
                "vel_sigma": self.vel_sigma,
                "rng_seed": self.rng_seed,
                "species": species,
                **self._metadata,
            },
        )

    @property
    def description(self) -> str:
        return f"GaussianBeamSource(N={self.n_particles}, sigma_r={self.pos_sigma})"
