"""Configuration dataclasses for validation runs."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ComparisonDirection(str, Enum):
    LE = "le"
    GE = "ge"
    ABS_LE = "abs_le"


class PassCriteria(str, Enum):
    ALL_MUST_PASS = "all_must_pass"
    ANY = "any"


@dataclass
class Tolerance:
    threshold: float
    direction: ComparisonDirection = ComparisonDirection.LE
    informational: bool = False


@dataclass
class ConvergenceConfig:
    enabled: bool = True
    num_points: int = 8
    refinement_ratio: float = 2.0
    use_self_convergence: bool = False
    mode: str = "analytical"


@dataclass
class NumericalConfig:
    dt: float
    max_steps: int
    max_steps_conv: int
    convergence: ConvergenceConfig = field(default_factory=ConvergenceConfig)
    solver_name: str = "boris"


@dataclass
class OutputConfig:
    emit_report: bool = True
    emit_json: bool = True
    emit_csv: bool = True
    emit_manifest: bool = True
    emit_plots: bool = True
    visualization: bool = False
    output_dir: Optional[str] = None
    pass_criteria: PassCriteria = PassCriteria.ALL_MUST_PASS
