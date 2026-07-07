"""Validation profile selection: analytical, simple composite, beam optics."""

from transport.lattice.lattice import Dipole
from transport.validation.config import ComparisonDirection, Tolerance
from transport.validation.metrics.beam import (
    BeamEnvelopeMetric,
    ExitCentroidMetric,
    ExitDirectionMetric,
    ExitStateAgreementMetric,
    HorizontalEmittanceDriftMetric,
    ParticleLossMetric,
    TransmissionMetric,
    VerticalEmittanceDriftMetric,
)
from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric

SIMPLE_COMPOSITE_CASES = frozenset({"drift_dipole", "drift_quadrupole"})
BEAM_OPTICS_CASES = frozenset({"fodo", "acol"})


def validation_tier(case_type: str) -> str:
    key = case_type.lower()
    if key in SIMPLE_COMPOSITE_CASES:
        return "simple_composite"
    if key in BEAM_OPTICS_CASES:
        return "beam_optics"
    return "analytical"


def is_composite_lattice(config) -> bool:
    return len(config.lattice.elements) > 1


def _has_dipole(lattice) -> bool:
    return any(isinstance(el, Dipole) for el in lattice.elements)


def simple_composite_metric_specs(lattice=None):
    """Two-element assemblies: conservation, exit-state agreement, beam diagnostics."""
    horizontal_tol = (
        Tolerance(threshold=0.0, informational=True)
        if lattice is not None and _has_dipole(lattice)
        else Tolerance(0.05)
    )
    return [
        (MomentumConservationMetric(), Tolerance(1e-6)),
        (EnergyConservationMetric(), Tolerance(1e-6)),
        (ExitStateAgreementMetric(), Tolerance(0.05)),
        (ExitCentroidMetric(), Tolerance(threshold=0.0, informational=True)),
        (ExitDirectionMetric(), Tolerance(threshold=0.0, informational=True)),
        (TransmissionMetric(include_plot=False), Tolerance(threshold=0.95, direction=ComparisonDirection.GE)),
        (BeamEnvelopeMetric(), Tolerance(threshold=0.0, informational=True)),
        (HorizontalEmittanceDriftMetric(), horizontal_tol),
        (VerticalEmittanceDriftMetric(), Tolerance(0.05)),
    ]


def beam_optics_metric_specs(lattice=None):
    """FODO / ACOL: full beam diagnostics including envelope, emittance, losses."""
    horizontal_tol = (
        Tolerance(threshold=0.0, informational=True)
        if lattice is not None and _has_dipole(lattice)
        else Tolerance(0.05)
    )
    return [
        (MomentumConservationMetric(), Tolerance(1e-6)),
        (EnergyConservationMetric(), Tolerance(1e-6)),
        (ExitCentroidMetric(), Tolerance(threshold=0.0, informational=True)),
        (ExitDirectionMetric(), Tolerance(threshold=0.0, informational=True)),
        (TransmissionMetric(), Tolerance(threshold=0.95, direction=ComparisonDirection.GE)),
        (ParticleLossMetric(), Tolerance(threshold=0.05)),
        (BeamEnvelopeMetric(), Tolerance(threshold=0.0, informational=True)),
        (HorizontalEmittanceDriftMetric(), horizontal_tol),
        (VerticalEmittanceDriftMetric(), Tolerance(0.05)),
    ]


def apply_validation_profile(case, config):
    """Apply tier-appropriate metrics for composite / beam-optics cases."""
    tier = validation_tier(config.case_type)
    case.references = []
    case.metric_specs = (
        simple_composite_metric_specs(config.lattice)
        if tier == "simple_composite"
        else beam_optics_metric_specs(config.lattice)
    )
    case.metadata = {
        k: v
        for k, v in case.metadata.items()
        if k != "analytical_position_fn"
    }
    case.metadata["validation_profile"] = tier
    case.metadata["n_elements"] = len(config.lattice.elements)
    case.metadata.setdefault("total_length", config.lattice.total_length)
    return case


# Backward-compatible aliases
def beam_metric_specs(lattice=None):
    return beam_optics_metric_specs(lattice)


def apply_beam_profile(case, config):
    return apply_validation_profile(case, config)
