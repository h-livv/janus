"""Validation profile selection: analytical, simple composite, beam optics."""

from transport.lattice.lattice import Dipole
from transport.validation.config import ComparisonDirection, Tolerance
from transport.validation.metrics.beam import (
    BeamDivergenceMetric,
    BeamEnvelopeMetric,
    BeamRmsSizeMetric,
    ElementLossMetric,
    EnvelopeComparisonMetric,
    ExitCentroidMetric,
    ExitDirectionMetric,
    ExitStateAgreementMetric,
    GeometricEmittanceMetric,
    HorizontalEmittanceDriftMetric,
    MomentumSpreadMetric,
    ParticleLossMetric,
    PhaseSpaceMetric,
    TransferMatrixComparisonMetric,
    TransmissionMetric,
    TwissAlphaComparisonMetric,
    TwissBetaComparisonMetric,
    TwissGammaComparisonMetric,
    TwissParametersMetric,
    VerticalEmittanceDriftMetric,
)
from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric

SIMPLE_COMPOSITE_CASES = frozenset({"drift_dipole", "drift_quadrupole"})
BEAM_OPTICS_CASES = frozenset({"fodo", "acol"})


def validation_tier(case_type: str, n_elements: int | None = None) -> str:
    key = case_type.lower()
    if key in SIMPLE_COMPOSITE_CASES:
        return "simple_composite"
    if key in BEAM_OPTICS_CASES:
        return "beam_optics"
    if n_elements is not None and n_elements > 2:
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
    """FODO / ACOL / n_elements>2: full beam diagnostics including envelope, emittance, losses."""
    horizontal_tol = (
        Tolerance(threshold=0.0, informational=True)
        if lattice is not None and _has_dipole(lattice)
        else Tolerance(0.05)
    )
    info = Tolerance(threshold=0.0, informational=True)
    return [
        (MomentumConservationMetric(), Tolerance(1e-6)),
        (EnergyConservationMetric(), Tolerance(1e-6)),
        (ExitCentroidMetric(), info),
        (ExitDirectionMetric(), info),
        (TransmissionMetric(), Tolerance(threshold=0.95, direction=ComparisonDirection.GE)),
        (ParticleLossMetric(), Tolerance(threshold=0.05)),
        (BeamEnvelopeMetric(), info),
        (BeamRmsSizeMetric(), info),
        (BeamDivergenceMetric(), info),
        (GeometricEmittanceMetric(), info),
        (HorizontalEmittanceDriftMetric(), horizontal_tol),
        (VerticalEmittanceDriftMetric(), Tolerance(0.05)),
        (PhaseSpaceMetric(), info),
        (MomentumSpreadMetric(), info),
        (ElementLossMetric(), info),
        (TransferMatrixComparisonMetric(backend="auto"), info),
        (EnvelopeComparisonMetric(backend="auto"), info),
        (TwissParametersMetric(), info),
        (TwissBetaComparisonMetric(backend="auto"), info),
        (TwissAlphaComparisonMetric(backend="auto"), info),
        (TwissGammaComparisonMetric(backend="auto"), info),
    ]


def apply_validation_profile(case, config):
    """Apply tier-appropriate metrics for composite / beam-optics cases."""
    n_elements = len(config.lattice.elements)
    tier = validation_tier(config.case_type, n_elements=n_elements)
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
    case.metadata["n_elements"] = n_elements
    case.metadata.setdefault("total_length", config.lattice.total_length)
    return case


# Backward-compatible aliases
def beam_metric_specs(lattice=None):
    return beam_optics_metric_specs(lattice)


def apply_beam_profile(case, config):
    return apply_validation_profile(case, config)
