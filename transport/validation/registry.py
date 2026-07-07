"""Lightweight registries for cases, metrics, references, and sources."""

from typing import Callable, Dict

from transport.lattice.registry import register_builtin_elements


class Registry:
    def __init__(self, label: str):
        self.label = label
        self._entries: Dict[str, Callable] = {}

    def register(self, name: str, factory: Callable):
        self._entries[name.lower()] = factory

    def get(self, name: str):
        key = name.lower()
        if key not in self._entries:
            raise KeyError(f"Unknown {self.label}: '{name}'. Available: {list(self._entries)}")
        return self._entries[key]()

    def build(self, name: str, **kwargs):
        key = name.lower()
        if key not in self._entries:
            raise KeyError(f"Unknown {self.label}: '{name}'. Available: {list(self._entries)}")
        return self._entries[key](**kwargs)

    def list_names(self):
        return sorted(self._entries.keys())


case_registry = Registry("case")
metric_registry = Registry("metric")
reference_registry = Registry("reference")
source_registry = Registry("source")
convergence_registry = Registry("convergence")
solver_registry = Registry("solver")


_case_config_builders = {}


def register_case(name: str, factory: Callable, config_factory: Callable = None):
    case_registry.register(name, factory)
    if config_factory:
        _case_config_builders[name.lower()] = config_factory

    
def case_for_config(config):
    from transport.validation.profiles import apply_validation_profile, validation_tier

    key = config.case_type.lower()
    if key not in _case_config_builders:
        raise KeyError(f"No config factory for case '{key}'")
    case = _case_config_builders[key](config)
    if validation_tier(config.case_type) != "analytical":
        case = apply_validation_profile(case, config)
    return case


def register_builtin_cases():
    from transport.validation.cases.drift import build_drift_case, build_drift_case_from_config
    from transport.validation.cases.dipole import build_dipole_case, build_dipole_case_from_config
    from transport.validation.cases.drift_dipole import (
        build_drift_dipole_case,
        build_drift_dipole_case_from_config,
    )
    from transport.validation.cases.drift_quadrupole import (
        build_drift_quadrupole_case,
        build_drift_quadrupole_case_from_config,
    )
    from transport.validation.cases.fodo import build_fodo_case, build_fodo_case_from_config
    from transport.validation.cases.acol import build_acol_case, build_acol_case_from_config
    from transport.validation.cases.solenoid import build_solenoid_case
    from transport.validation.cases.horn import build_horn_case
    from transport.validation.cases.gaussian_beam import build_gaussian_beam_case

    from transport.validation.cases.quadrupole import build_quadrupole_case, build_quadrupole_case_from_config

    register_case("drift", build_drift_case, build_drift_case_from_config)
    register_case("dipole", build_dipole_case, build_dipole_case_from_config)
    register_case("drift_dipole", build_drift_dipole_case, build_drift_dipole_case_from_config)
    register_case("quadrupole", build_quadrupole_case, build_quadrupole_case_from_config)
    register_case("drift_quadrupole", build_drift_quadrupole_case, build_drift_quadrupole_case_from_config)
    register_case("fodo", build_fodo_case, build_fodo_case_from_config)
    register_case("acol", build_acol_case, build_acol_case_from_config)
    case_registry.register("solenoid", build_solenoid_case)
    case_registry.register("horn", build_horn_case)
    case_registry.register("gaussian_beam", build_gaussian_beam_case)


def register_builtin_metrics():
    from transport.validation.metrics.beam import (
        BeamEnvelopeMetric,
        CentroidMetric,
        EmittanceMetric,
        ExitCentroidMetric,
        ExitDirectionMetric,
        ExitStateAgreementMetric,
        HorizontalEmittanceDriftMetric,
        ParticleLossMetric,
        RmsSizeMetric,
        TransmissionMetric,
        VerticalEmittanceDriftMetric,
    )
    from transport.validation.metrics.conservation import EnergyConservationMetric, MomentumConservationMetric
    from transport.validation.metrics.trajectory import (
        BendAngleErrorMetric, CyclotronRadiusErrorMetric, DriftCoordinateErrorMetric,
    )

    metric_registry.register("momentum_conservation", MomentumConservationMetric)
    metric_registry.register("energy_conservation", EnergyConservationMetric)
    metric_registry.register("x_error", lambda: DriftCoordinateErrorMetric("x"))
    metric_registry.register("y_error", lambda: DriftCoordinateErrorMetric("y"))
    metric_registry.register("z_error", lambda: DriftCoordinateErrorMetric("z"))
    metric_registry.register("cyclotron_radius_error", CyclotronRadiusErrorMetric)
    metric_registry.register("bend_angle_error", BendAngleErrorMetric)
    metric_registry.register("centroid_x", CentroidMetric)
    metric_registry.register("rms_x", RmsSizeMetric)
    metric_registry.register("transmission", TransmissionMetric)
    metric_registry.register("beam_envelope", BeamEnvelopeMetric)
    metric_registry.register("exit_centroid", ExitCentroidMetric)
    metric_registry.register("exit_direction", ExitDirectionMetric)
    metric_registry.register("exit_state_agreement", ExitStateAgreementMetric)
    metric_registry.register("particle_loss", ParticleLossMetric)
    metric_registry.register("horizontal_emittance_drift", HorizontalEmittanceDriftMetric)
    metric_registry.register("vertical_emittance_drift", VerticalEmittanceDriftMetric)
    metric_registry.register("emittance_x", EmittanceMetric)


def register_builtin_references():
    from transport.validation.references.analytical import DriftAnalyticalReference, StubAnalyticalReference
    from transport.validation.references.experimental import ExperimentalReference
    from transport.validation.references.external import ExternalSimulationReference
    from transport.validation.references.numerical import NumericalReference
    from transport.validation.references.transfer_matrix import TransferMatrixReference

    reference_registry.register("drift_analytical", DriftAnalyticalReference)
    reference_registry.register("stub_analytical", StubAnalyticalReference)
    reference_registry.register("transfer_matrix", TransferMatrixReference)
    reference_registry.register("numerical", NumericalReference)
    reference_registry.register("experimental", ExperimentalReference)
    reference_registry.register("external", ExternalSimulationReference)


def register_builtin_sources():
    from transport.validation.sources.file import FileParticleSource
    from transport.validation.sources.gaussian_beam import GaussianBeamSource
    from transport.validation.sources.geant4 import Geant4ParticleSource
    from transport.validation.sources.single import SingleParticleSource

    source_registry.register("single", SingleParticleSource)
    source_registry.register("mock", SingleParticleSource)
    source_registry.register("geant4", Geant4ParticleSource)
    source_registry.register("gaussian_beam", GaussianBeamSource)
    source_registry.register("file", FileParticleSource)


def register_builtin_convergence():
    from transport.validation.convergence.analytical import AnalyticalConvergence
    from transport.validation.convergence.self_convergence import SelfConvergence

    convergence_registry.register("analytical", AnalyticalConvergence)
    convergence_registry.register("self", SelfConvergence)


def register_builtin_solvers():
    from transport.validation.solver import BorisSolverAdapter

    solver_registry.register("boris", BorisSolverAdapter)


def initialize_registries():
    register_builtin_elements()
    register_builtin_cases()
    register_builtin_metrics()
    register_builtin_references()
    register_builtin_sources()
    register_builtin_convergence()
    register_builtin_solvers()
