"""Particle source strategy interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class ParticleBatch:
    R: np.ndarray
    V: np.ndarray
    gamma: np.ndarray
    charges: np.ndarray
    mass: np.ndarray = None
    species: str = "proton"
    metadata: dict = field(default_factory=dict)


class ParticleSource(ABC):
    @abstractmethod
    def generate(self) -> ParticleBatch:
        pass

    @property
    def description(self) -> str:
        return type(self).__name__
