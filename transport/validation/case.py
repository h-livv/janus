"""Declarative validation case and standardized context."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

from transport.validation.config import NumericalConfig, OutputConfig, Tolerance
from transport.validation.diagnostics import Diagnostics


@dataclass
class ValidationContext:
    """Read-only bundle passed to metrics and references."""

    diagnostics: Diagnostics
    lattice: Any
    R_init: np.ndarray
    V_init: np.ndarray
    gamma_init: np.ndarray
    charges: np.ndarray
    mass: np.ndarray
    particle_source_metadata: dict
    resolved_references: dict
    numerical_config: NumericalConfig
    case_metadata: dict = field(default_factory=dict)


@dataclass
class MetricEvaluation:
    name: str
    value: float
    unit: str
    scope: str
    is_verification: bool
    tolerance: Optional[Tolerance]
    status: str  # passed, failed, skipped, info
    per_particle: Optional[np.ndarray] = None
    plot_payload: Optional[dict] = None
    skip_reason: Optional[str] = None


@dataclass
class ValidationCase:
    """Declarative bundle: system, source, references, metrics, outputs."""

    name: str
    level: int
    system_builder: Callable[[], Any]
    particle_source: Any
    numerical_config: NumericalConfig
    references: list
    metric_specs: list  # list of (metric, tolerance) tuples
    output_config: OutputConfig = field(default_factory=OutputConfig)
    metadata: dict = field(default_factory=dict)

    def build_system(self):
        return self.system_builder()
