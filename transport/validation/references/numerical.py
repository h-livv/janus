"""High-resolution / self-convergence numerical reference."""

import numpy as np

from transport.validation.case import ValidationContext
from transport.validation.references.base import (
    ReferenceCapability,
    ReferenceResult,
    ReferenceSolution,
    ReferenceType,
)


class NumericalReference(ReferenceSolution):
    def __init__(self, name: str = "numerical"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.NUMERICAL

    @property
    def capabilities(self) -> set:
        return {ReferenceCapability.POINTWISE_TRAJECTORY}

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            pointwise_trajectory={"stub": True},
            metadata={"mode": "numerical_reference"},
        )


def find_exit_state(diagnostics, z_exit, particle_idx=0):
    """Interpolate exit position at z_exit for a single particle."""
    pos = diagnostics["position"][:, particle_idx]
    times = diagnostics["time"]
    for i in range(1, len(times)):
        z_old = pos[i - 1, 2]
        z_new = pos[i, 2]
        if z_old < z_exit and z_new >= z_exit:
            alpha = (z_exit - z_old) / (z_new - z_old)
            r_old = pos[i - 1]
            r_new = pos[i]
            x_exit = r_old[0] + alpha * (r_new[0] - r_old[0])
            y_exit = r_old[1] + alpha * (r_new[1] - r_old[1])
            t_exit = times[i - 1] + alpha * (times[i] - times[i - 1])
            return np.array([x_exit, y_exit, z_exit]), t_exit, True
    return pos[-1], times[-1], False
