"""Reference solution strategy interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np

from transport.validation.case import ValidationContext


class ReferenceType(str, Enum):
    ANALYTICAL = "analytical"
    TRANSFER_MATRIX = "transfer_matrix"
    NUMERICAL = "numerical"
    EXPERIMENTAL = "experimental"
    EXTERNAL = "external"


class ReferenceCapability(str, Enum):
    POINTWISE_TRAJECTORY = "pointwise_trajectory"
    SUMMARY_OBSERVABLES = "summary_observables"
    MOMENT_PROPAGATION = "moment_propagation"
    BOUNDARY_STATES = "boundary_states"


@dataclass
class ReferenceResult:
    reference_type: ReferenceType
    capabilities: set
    pointwise_trajectory: Optional[dict] = None
    summary_observables: Optional[dict] = None
    moment_propagation: Optional[Any] = None
    boundary_states: Optional[list] = None
    metadata: dict = field(default_factory=dict)


class ReferenceSolution(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def reference_type(self) -> ReferenceType:
        pass

    @property
    @abstractmethod
    def capabilities(self) -> set:
        pass

    @abstractmethod
    def resolve(self, context: ValidationContext) -> ReferenceResult:
        pass

    def has_capability(self, cap: ReferenceCapability) -> bool:
        return cap in self.capabilities or cap.value in self.capabilities
