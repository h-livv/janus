"""Versioned diagnostics contract wrapping the Boris solver output schema."""

from dataclasses import dataclass
from typing import Any

import numpy as np

SCHEMA_VERSION = "1.0.0"

_REQUIRED_KEYS = ("step", "time", "position", "momentum", "gamma", "field", "element", "alive")


@dataclass(frozen=True)
class Diagnostics:
    """Formal wrapper for transport diagnostics arrays."""

    schema_version: str
    step: np.ndarray
    time: np.ndarray
    position: np.ndarray
    momentum: np.ndarray
    gamma: np.ndarray
    field: np.ndarray
    element: list
    alive: np.ndarray

    @property
    def n_steps(self) -> int:
        return len(self.time)

    @property
    def n_particles(self) -> int:
        return self.position.shape[1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "time": self.time,
            "position": self.position,
            "momentum": self.momentum,
            "gamma": self.gamma,
            "field": self.field,
            "element": self.element,
            "alive": self.alive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Diagnostics":
        missing = [k for k in _REQUIRED_KEYS if k not in data]
        if missing:
            raise ValueError(f"Diagnostics missing required keys: {missing}")
        return cls(
            schema_version=SCHEMA_VERSION,
            step=np.asarray(data["step"]),
            time=np.asarray(data["time"]),
            position=np.asarray(data["position"]),
            momentum=np.asarray(data["momentum"]),
            gamma=np.asarray(data["gamma"]),
            field=np.asarray(data["field"]),
            element=data["element"],
            alive=np.asarray(data["alive"]),
        )
