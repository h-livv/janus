"""Experiment configuration schema."""

from dataclasses import dataclass, field
from typing import Optional

from transport.validation.config import (
    ComparisonDirection,
    NumericalConfig,
    OutputConfig,
    PassCriteria,
)


@dataclass
class ElementSpec:
    type: str
    params: dict = field(default_factory=dict)


@dataclass
class LatticeSpec:
    z_start: float = 0.0
    elements: list = field(default_factory=list)


@dataclass
class ParticleSourceSpec:
    type: str
    species: str = "proton"
    charge_filter: str = "any"
    n_particles: int = 1
    momentum_slice: Optional[list] = None
    position: Optional[list] = None
    velocity: Optional[list] = None
    gamma: Optional[float] = None
    pos_sigma: float = 0.0
    vel_sigma: float = 0.0
    rng_seed: int = 42
    path: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class MetricSpec:
    name: str
    tolerance: float
    direction: ComparisonDirection = ComparisonDirection.LE
    informational: bool = False


@dataclass
class ValidationSpec:
    metrics: Optional[list] = None
    pass_criteria: PassCriteria = PassCriteria.ALL_MUST_PASS


@dataclass
class ExperimentMeta:
    name: str
    level: int
    case: str
    output_dir: str = "transport/validation/outputs"


@dataclass
class Experiment:
    meta: ExperimentMeta
    particle_source: ParticleSourceSpec
    lattice: LatticeSpec
    numerical: NumericalConfig
    validation: ValidationSpec
    outputs: OutputConfig

    @property
    def name(self):
        return self.meta.name

    @property
    def level(self):
        return self.meta.level

    @property
    def case(self):
        return self.meta.case

    @property
    def output_dir(self):
        return self.meta.output_dir

    @classmethod
    def from_dict(cls, data: dict) -> "Experiment":
        from transport.experiment.loader import parse_experiment_dict
        return parse_experiment_dict(data)
