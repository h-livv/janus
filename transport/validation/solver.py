"""Solver interface and Boris integrator adapter."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

import numpy as np

from transport.validation.diagnostics import Diagnostics


@runtime_checkable
class Solver(Protocol):
    """Uniform run-transport contract for validation."""

    def run(
        self,
        R_init: np.ndarray,
        V_init: np.ndarray,
        gamma_init: np.ndarray,
        charges: np.ndarray,
        lattice,
        dt: float,
        max_steps: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, Diagnostics]:
        ...


class BorisSolverAdapter:
    """Default solver wrapping physics.boris_solver.track_particles."""

    def run(
        self,
        R_init: np.ndarray,
        V_init: np.ndarray,
        gamma_init: np.ndarray,
        charges: np.ndarray,
        lattice,
        dt: float,
        max_steps: int,
        mass: np.ndarray = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, Diagnostics]:
        from transport.physics.boris_solver import M_P_KG, track_particles

        if mass is None:
            mass = np.full(len(R_init), M_P_KG)

        R, V, alive, raw = track_particles(
            R_init, V_init, gamma_init, charges, lattice, dt, max_steps, mass=mass
        )
        return R, V, alive, Diagnostics.from_dict(raw)


class AbstractSolver(ABC):
    @abstractmethod
    def run(
        self,
        R_init: np.ndarray,
        V_init: np.ndarray,
        gamma_init: np.ndarray,
        charges: np.ndarray,
        lattice,
        dt: float,
        max_steps: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, Diagnostics]:
        pass
