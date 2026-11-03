"""File-based particle source (NPZ/JSON stub)."""

import json
from pathlib import Path

import numpy as np

from transport.validation.sources.base import ParticleBatch, ParticleSource


class FileParticleSource(ParticleSource):
    def __init__(self, path: str):
        self.path = Path(path)

    def generate(self) -> ParticleBatch:
        if not self.path.exists():
            raise FileNotFoundError(f"Particle source file not found: {self.path}")
        if self.path.suffix == ".npz":
            data = np.load(self.path)
            species = str(data["species"]) if "species" in data.files else "proton"
            from transport.physics.particle_data import mass_of
            n = len(data["R"])
            return ParticleBatch(
                R=data["R"], V=data["V"], gamma=data["gamma"], charges=data["charges"],
                mass=np.full(n, mass_of(species), dtype=np.float64),
                species=species,
                metadata={"source_type": "file", "path": str(self.path), "species": species},
            )
        if self.path.suffix == ".json":
            with open(self.path) as f:
                data = json.load(f)
            from transport.physics.particle_data import mass_of
            species = data.get("species", "proton")
            n = len(data["R"])
            return ParticleBatch(
                R=np.array(data["R"], dtype=np.float64),
                V=np.array(data["V"], dtype=np.float64),
                gamma=np.array(data["gamma"], dtype=np.float64),
                charges=np.array(data["charges"]),
                mass=np.full(n, mass_of(species), dtype=np.float64),
                species=species,
                metadata={"source_type": "file", "path": str(self.path), "species": species},
            )
        raise ValueError(f"Unsupported particle source format: {self.path.suffix}")

    @property
    def description(self) -> str:
        return f"FileParticleSource({self.path})"
