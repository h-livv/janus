"""Metric strategy interface and result types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from transport.validation.case import ValidationContext


class MetricScope(str, Enum):
    SINGLE = "single"
    COMPOSITE = "composite"
    BEAM = "beam"
    ANY = "any"


class ReferenceRequirement(str, Enum):
    NONE = "none"
    POINTWISE_TRAJECTORY = "pointwise_trajectory"
    SUMMARY_OBSERVABLES = "summary_observables"
    MOMENT_PROPAGATION = "moment_propagation"
    BOUNDARY_STATES = "boundary_states"


@dataclass
class MetricResult:
    value: float
    per_particle: Optional[np.ndarray] = None
    plot_payload: Optional[dict] = None


class Metric(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def unit(self) -> str:
        pass

    @property
    @abstractmethod
    def scope(self) -> MetricScope:
        pass

    @property
    def is_verification(self) -> bool:
        return False

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.NONE

    @abstractmethod
    def compute(self, context: ValidationContext) -> MetricResult:
        pass

    def is_applicable(self, context: ValidationContext) -> tuple[bool, Optional[str]]:
        n = context.diagnostics.n_particles
        if self.scope == MetricScope.SINGLE and n != 1:
            return False, f"scope=single requires N=1, got N={n}"
        if self.scope == MetricScope.BEAM and n < 2:
            return False, f"scope=beam requires N>=2, got N={n}"
        req = self.reference_requirement
        if req == ReferenceRequirement.NONE:
            return True, None
        for ref_result in context.resolved_references.values():
            caps = getattr(ref_result, "capabilities", set())
            cap_values = {c.value if hasattr(c, "value") else str(c) for c in caps}
            if req.value in cap_values:
                return True, None
        return False, f"no reference provides capability '{req.value}'"
