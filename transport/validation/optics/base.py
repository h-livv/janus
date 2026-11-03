"""Optics comparison base types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class OpticsEnvelope:
    z: np.ndarray
    sigma_x: np.ndarray
    sigma_y: np.ndarray
    metadata: dict = field(default_factory=dict)


@dataclass
class OpticsTransferMatrix:
    """4x4 transverse transfer matrix (x, x', y, y')."""

    matrix: np.ndarray
    metadata: dict = field(default_factory=dict)


@dataclass
class OpticsTwiss:
    """Courant–Snyder parameters along the lattice."""

    z: np.ndarray
    beta_x: np.ndarray
    alpha_x: np.ndarray
    gamma_x: np.ndarray
    beta_y: np.ndarray
    alpha_y: np.ndarray
    gamma_y: np.ndarray
    metadata: dict = field(default_factory=dict)


class OpticsBackend(ABC):
    """External or analytic linear-optics provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def available(self) -> bool:
        pass

    def transfer_matrix(self, lattice, particle_state: dict) -> Optional[OpticsTransferMatrix]:
        return None

    def envelope(self, lattice, particle_state: dict) -> Optional[OpticsEnvelope]:
        return None

    def twiss(self, lattice, particle_state: dict) -> Optional[OpticsTwiss]:
        return None
