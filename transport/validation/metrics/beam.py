"""Beam-level statistical metrics for composite lattice validation."""

import numpy as np

from transport.validation.reporting.lattice_annotations import lattice_elements_payload
from transport.validation.metrics.base import Metric, MetricResult, MetricScope, ReferenceRequirement
from transport.validation.references.numerical import find_exit_states_with_momentum


def _lattice_z_exit(context: ValidationContext) -> float:
    lattice = context.lattice
    return lattice.z_start + lattice.total_length


def _alive_mask_at(diagnostics, step: int) -> np.ndarray:
    return diagnostics.alive[step].astype(bool)


def _alive_positions_at(diagnostics, step: int) -> np.ndarray:
    alive = _alive_mask_at(diagnostics, step)
    return diagnostics.position[step, alive]


def _alive_momenta_at(diagnostics, step: int) -> np.ndarray:
    alive = _alive_mask_at(diagnostics, step)
    return diagnostics.momentum[step, alive]


def _plane_emittance(pos: np.ndarray, mom: np.ndarray, axis: int) -> float:
    """RMS emittance in one transverse plane (pos axis index 0=x, 1=y)."""
    if len(pos) < 2:
        return 0.0
    q = pos[:, axis]
    pz = np.maximum(np.abs(mom[:, 2]), 1e-30)
    qp = mom[:, axis] / pz
    mean_q2 = float(np.mean(q ** 2))
    mean_qp2 = float(np.mean(qp ** 2))
    mean_q_qp = float(np.mean(q * qp))
    return float(np.sqrt(max(mean_q2 * mean_qp2 - mean_q_qp ** 2, 0.0)))


def _rms_envelope(pos: np.ndarray) -> tuple[float, float]:
    if len(pos) == 0:
        return 0.0, 0.0
    return float(np.std(pos[:, 0])), float(np.std(pos[:, 1]))


def _reached_exit(diagnostics, z_exit: float) -> np.ndarray:
    """True for particles whose trajectory crossed the lattice exit plane."""
    n = diagnostics.n_particles
    reached = np.zeros(n, dtype=bool)
    for step in range(diagnostics.n_steps):
        pos = diagnostics.position[step]
        reached |= pos[:, 2] >= z_exit - 1e-9
    return reached


def _transmission_series(diagnostics, z_exit: float) -> np.ndarray:
    n_init = diagnostics.n_particles
    if n_init == 0:
        return np.zeros(diagnostics.n_steps)
    series = []
    for step in range(diagnostics.n_steps):
        alive = diagnostics.alive[step]
        z = diagnostics.position[step, :, 2]
        inside = z <= z_exit + 1e-9
        series.append(float(np.sum(alive & inside)) / n_init)
    return np.asarray(series)


def _exit_phase_space(context: ValidationContext) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z_exit = _lattice_z_exit(context)
    diag = context.diagnostics.to_dict()
    r_exit, p_exit = find_exit_states_with_momentum(diag, z_exit)
    reached = _reached_exit(context.diagnostics, z_exit)
    return r_exit, p_exit, reached


class CentroidMetric(Metric):
    @property
    def name(self) -> str:
        return "centroid_x"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        r_exit, _, reached = _exit_phase_space(context)
        if not np.any(reached):
            return MetricResult(value=0.0)
        value = float(np.mean(r_exit[reached, 0]))
        return MetricResult(value=value)


class RmsSizeMetric(Metric):
    @property
    def name(self) -> str:
        return "rms_x"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        r_exit, _, reached = _exit_phase_space(context)
        x = r_exit[reached, 0]
        value = float(np.std(x)) if len(x) > 1 else 0.0
        return MetricResult(value=value)


class ExitCentroidMetric(Metric):
    @property
    def name(self) -> str:
        return "exit_centroid"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        r_exit, _, reached = _exit_phase_space(context)
        if not np.any(reached):
            return MetricResult(value=0.0)
        centroid = np.mean(r_exit[reached], axis=0)
        value = float(np.linalg.norm(centroid[:2]))
        return MetricResult(value=value)


class ExitDirectionMetric(Metric):
    @property
    def name(self) -> str:
        return "exit_direction"

    @property
    def unit(self) -> str:
        return "rad"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        _, p_exit, reached = _exit_phase_space(context)
        if not np.any(reached):
            return MetricResult(value=0.0)
        mom = p_exit[reached]
        pz = np.maximum(np.abs(mom[:, 2]), 1e-30)
        xp = np.mean(mom[:, 0] / pz)
        yp = np.mean(mom[:, 1] / pz)
        value = float(np.hypot(xp, yp))
        return MetricResult(value=value)


class TransmissionMetric(Metric):
    def __init__(self, include_plot: bool = True):
        self._include_plot = include_plot

    @property
    def name(self) -> str:
        return "transmission"

    @property
    def unit(self) -> str:
        return "fraction"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        diag = context.diagnostics
        z_exit = _lattice_z_exit(context)
        reached = _reached_exit(diag, z_exit)
        value = float(np.mean(reached))
        plot = None
        if self._include_plot:
            series = _transmission_series(diag, z_exit)
            plot = {
                "plot_type": "transmission",
                "title": f"Beam Transmission ({context.case_metadata.get('name', '')})",
                "xlabel": "Time (ns)",
                "ylabel": "Survival Fraction",
                "curves": [
                    {
                        "x": diag.time * 1e9,
                        "y": series,
                        "label": "Transmission",
                        "color": "green",
                    }
                ],
            }
        return MetricResult(value=value, plot_payload=plot)


class ParticleLossMetric(Metric):
    @property
    def name(self) -> str:
        return "particle_loss"

    @property
    def unit(self) -> str:
        return "fraction"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        diag = context.diagnostics
        z_exit = _lattice_z_exit(context)
        reached = _reached_exit(diag, z_exit)
        transmission = float(np.mean(reached))
        value = 1.0 - transmission
        series = 1.0 - _transmission_series(diag, z_exit)
        plot = {
            "plot_type": "loss",
            "title": f"Particle Loss ({context.case_metadata.get('name', '')})",
            "xlabel": "Time (ns)",
            "ylabel": "Loss Fraction",
            "curves": [
                {
                    "x": diag.time * 1e9,
                    "y": series,
                    "label": "Loss",
                    "color": "crimson",
                }
            ],
        }
        return MetricResult(value=value, plot_payload=plot)


class ExitStateAgreementMetric(Metric):
    """Ensemble spread of exit transverse phase space (composition consistency)."""

    @property
    def name(self) -> str:
        return "exit_state_agreement"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        r_exit, p_exit, reached = _exit_phase_space(context)
        if not np.any(reached):
            return MetricResult(value=float("inf"))
        pos = r_exit[reached, :2]
        mom = p_exit[reached]
        pz = np.maximum(np.abs(mom[:, 2]), 1e-30)
        angles = np.column_stack((mom[:, 0] / pz, mom[:, 1] / pz))
        pos_spread = float(np.hypot(np.std(pos[:, 0]), np.std(pos[:, 1])))
        angle_spread = float(np.hypot(np.std(angles[:, 0]), np.std(angles[:, 1])))
        value = pos_spread + angle_spread
        return MetricResult(value=value)


class BeamEnvelopeMetric(Metric):
    @property
    def name(self) -> str:
        return "beam_envelope"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        diag = context.diagnostics
        z_exit = _lattice_z_exit(context)
        rms_x, rms_y, z_centroid = [], [], []
        for step in range(diag.n_steps):
            pos = diag.position[step]
            inside = pos[:, 2] <= z_exit + 1e-9
            if not np.any(inside):
                break
            rx, ry = _rms_envelope(pos[inside])
            rms_x.append(rx)
            rms_y.append(ry)
            z_centroid.append(float(np.mean(pos[inside, 2])))
        r_exit, _, reached = _exit_phase_space(context)
        if np.any(reached):
            rx, ry = _rms_envelope(r_exit[reached])
            value = float(np.hypot(rx, ry))
        else:
            value = float(np.hypot(rms_x[-1], rms_y[-1])) if rms_x else 0.0
        plot = {
            "plot_type": "envelope",
            "title": f"Beam Envelope ({context.case_metadata.get('name', '')})",
            "xlabel": "Longitudinal Position z (m)",
            "ylabel": "RMS Size (m)",
            "lattice_elements": lattice_elements_payload(context.lattice),
            "curves": [
                {"x": z_centroid, "y": rms_x, "label": "RMS x", "color": "blue"},
                {"x": z_centroid, "y": rms_y, "label": "RMS y", "color": "red"},
            ],
        }
        return MetricResult(value=value, plot_payload=plot)


class HorizontalEmittanceDriftMetric(Metric):
    @property
    def name(self) -> str:
        return "horizontal_emittance_drift"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.NONE

    def compute(self, context: ValidationContext) -> MetricResult:
        return _emittance_drift_result(context, axis=0, plane="Horizontal")


class VerticalEmittanceDriftMetric(Metric):
    @property
    def name(self) -> str:
        return "vertical_emittance_drift"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.NONE

    def compute(self, context: ValidationContext) -> MetricResult:
        return _emittance_drift_result(context, axis=1, plane="Vertical")


def _emittance_drift_result(context: ValidationContext, axis: int, plane: str) -> MetricResult:
    diag = context.diagnostics
    z_exit = _lattice_z_exit(context)
    eps_series = []
    z_centroid = []
    for step in range(diag.n_steps):
        pos = diag.position[step]
        mom = diag.momentum[step]
        inside = pos[:, 2] <= z_exit + 1e-9
        if not np.any(inside):
            break
        eps_series.append(_plane_emittance(pos[inside], mom[inside], axis))
        z_centroid.append(float(np.mean(pos[inside, 2])))

    pos0 = diag.position[0]
    mom0 = diag.momentum[0]
    eps_init = _plane_emittance(pos0, mom0, axis)

    r_exit, p_exit, reached = _exit_phase_space(context)
    if np.any(reached):
        eps_final = _plane_emittance(r_exit[reached], p_exit[reached], axis)
        if z_centroid:
            z_centroid[-1] = z_exit
        if eps_series:
            eps_series[-1] = eps_final
        else:
            eps_series = [eps_init, eps_final]
            z_centroid = [float(np.mean(pos0[:, 2])), z_exit]
    else:
        eps_final = eps_series[-1] if eps_series else eps_init

    value = abs(eps_final - eps_init) / max(eps_init, 1e-30)
    eps0 = max(eps_init, 1e-30)
    rel_eps_series = [(eps - eps_init) / eps0 for eps in eps_series]
    plot = {
        "plot_type": "emittance",
        "title": f"{plane} Emittance Drift ({context.case_metadata.get('name', '')})",
        "xlabel": "Longitudinal Position z (m)",
        "ylabel": r"Relative Emittance Change $(\varepsilon - \varepsilon_0)/\varepsilon_0$",
        "lattice_elements": lattice_elements_payload(context.lattice),
        "curves": [
            {
                "x": z_centroid,
                "y": rel_eps_series,
                "label": rf"{plane} $(\varepsilon - \varepsilon_0)/\varepsilon_0$",
                "color": "purple" if axis == 0 else "darkorange",
            }
        ],
    }
    return MetricResult(value=value, plot_payload=plot)


class EmittanceMetric(Metric):
    """Legacy exit emittance metric (Level 3 stub)."""

    @property
    def name(self) -> str:
        return "emittance_x"

    @property
    def unit(self) -> str:
        return "m.rad"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.MOMENT_PROPAGATION

    def compute(self, context: ValidationContext) -> MetricResult:
        r_exit, p_exit, reached = _exit_phase_space(context)
        if not np.any(reached):
            return MetricResult(value=0.0)
        value = _plane_emittance(r_exit[reached], p_exit[reached], axis=0)
        return MetricResult(value=value)
