"""Beam-level statistical metrics for composite lattice validation."""

from __future__ import annotations

import numpy as np

from transport.physics.boris_solver import E_CHARGE, M_P_KG
from transport.validation.case import ValidationContext
from transport.validation.metrics.base import Metric, MetricResult, MetricScope, ReferenceRequirement
from transport.validation.optics import get_optics_backend
from transport.validation.optics.errors import combine_plane_errors, series_comparison_errors
from transport.validation.optics.transfer_matrix import (
    estimate_transfer_matrix_from_ensemble,
    relative_matrix_error,
)
from transport.validation.reporting.lattice_annotations import lattice_elements_payload
from transport.validation.stats.beam import (
    entrance_phase_space,
    exit_phase_space,
    lattice_z_exit,
    longitudinal_series,
    momentum_spread,
    per_element_losses,
    plane_emittance,
    plane_twiss,
    rms_divergence,
    rms_envelope,
    slopes_from_momentum,
    transmission_fraction,
    transmission_series,
)


# ---------------------------------------------------------------------------
# Backward-compatible private aliases (tests / older imports)
# ---------------------------------------------------------------------------
def _lattice_z_exit(context: ValidationContext) -> float:
    return lattice_z_exit(context)


def _alive_mask_at(diagnostics, step: int) -> np.ndarray:
    return diagnostics.alive[step].astype(bool)


def _alive_positions_at(diagnostics, step: int) -> np.ndarray:
    alive = _alive_mask_at(diagnostics, step)
    return diagnostics.position[step, alive]


def _alive_momenta_at(diagnostics, step: int) -> np.ndarray:
    alive = _alive_mask_at(diagnostics, step)
    return diagnostics.momentum[step, alive]


def _plane_emittance(pos: np.ndarray, mom: np.ndarray, axis: int) -> float:
    return plane_emittance(pos, mom, axis)


def _rms_envelope(pos: np.ndarray) -> tuple[float, float]:
    return rms_envelope(pos)


def _reached_exit(diagnostics, z_exit: float) -> np.ndarray:
    n = diagnostics.n_particles
    reached = np.zeros(n, dtype=bool)
    for step in range(diagnostics.n_steps):
        reached |= diagnostics.position[step, :, 2] >= z_exit - 1e-9
    return reached


def _transmission_series(diagnostics, z_exit: float) -> np.ndarray:
    return transmission_series(diagnostics, z_exit)


def _exit_phase_space(context: ValidationContext) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return exit_phase_space(context)


def _particle_state_for_optics(context: ValidationContext) -> dict:
    """Build optics-backend inputs from the tracked beam."""
    m_kg = float(context.mass[0]) if context.mass is not None else M_P_KG
    v = np.asarray(context.V_init[0], dtype=np.float64)
    v_mag = float(np.linalg.norm(v))
    from transport.physics.boris_solver import C_LIGHT

    gamma = float(1.0 / np.sqrt(max(1.0 - (v_mag / C_LIGHT) ** 2, 1e-30)))
    vz = abs(float(v[2])) if abs(float(v[2])) > 1e-12 else v_mag
    b_rho = gamma * m_kg * vz / E_CHARGE
    pos0, mom0 = entrance_phase_space(context)
    sx, sy = rms_envelope(pos0)
    sxp, syp = rms_divergence(mom0)
    tw_x = plane_twiss(pos0, mom0, 0)
    tw_y = plane_twiss(pos0, mom0, 1)
    species = context.particle_source_metadata.get("species", "proton")
    return {
        "B_rho": b_rho,
        "charge": float(context.charges[0]),
        "sigma_x": sx,
        "sigma_y": sy,
        "sigma_xp": sxp,
        "sigma_yp": syp,
        "gamma": gamma,
        "species": species,
        "beta_x": tw_x["beta"],
        "alpha_x": tw_x["alpha"],
        "gamma_x": tw_x["gamma"],
        "emittance_x": tw_x["emittance"],
        "Sigma_x": tw_x["Sigma"],
        "beta_y": tw_y["beta"],
        "alpha_y": tw_y["alpha"],
        "gamma_y": tw_y["gamma"],
        "emittance_y": tw_y["emittance"],
        "Sigma_y": tw_y["Sigma"],
    }


# ---------------------------------------------------------------------------
# Existing beam metrics
# ---------------------------------------------------------------------------
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
        value = transmission_fraction(context)
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
        value = 1.0 - transmission_fraction(context)
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
        slopes = slopes_from_momentum(mom)
        pos_spread = float(np.hypot(np.std(pos[:, 0]), np.std(pos[:, 1])))
        angle_spread = float(np.hypot(np.std(slopes[:, 0]), np.std(slopes[:, 1])))
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
        series = longitudinal_series(context)
        r_exit, _, reached = _exit_phase_space(context)
        if np.any(reached):
            rx, ry = _rms_envelope(r_exit[reached])
            value = float(np.hypot(rx, ry))
        elif len(series["sigma_x"]):
            value = float(np.hypot(series["sigma_x"][-1], series["sigma_y"][-1]))
        else:
            value = 0.0
        plot = {
            "plot_type": "envelope",
            "title": f"Beam Envelope ({context.case_metadata.get('name', '')})",
            "xlabel": "Longitudinal Position z (m)",
            "ylabel": "RMS Size (m)",
            "lattice_elements": lattice_elements_payload(context.lattice),
            "curves": [
                {"x": series["z"], "y": series["sigma_x"], "label": "σx", "color": "blue"},
                {"x": series["z"], "y": series["sigma_y"], "label": "σy", "color": "red"},
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
    series = longitudinal_series(context)
    key = "emittance_x" if axis == 0 else "emittance_y"
    eps_series = list(series[key])
    z_centroid = list(series["z"])

    pos0, mom0 = entrance_phase_space(context)
    eps_init = _plane_emittance(pos0, mom0, axis)

    r_exit, p_exit, reached = _exit_phase_space(context)
    z_exit = _lattice_z_exit(context)
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


# ---------------------------------------------------------------------------
# Multi-lattice beam diagnostics (n_elements > 2 / beam_optics profile)
# ---------------------------------------------------------------------------
class BeamRmsSizeMetric(Metric):
    """RMS x, y, z vs longitudinal position."""

    @property
    def name(self) -> str:
        return "beam_rms_size"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        series = longitudinal_series(context)
        value = float(np.hypot(series["sigma_x"][-1], series["sigma_y"][-1])) if len(series["z"]) else 0.0
        plot = {
            "plot_type": "rms_size",
            "title": f"Beam RMS Size ({context.case_metadata.get('name', '')})",
            "xlabel": "Longitudinal Position z (m)",
            "ylabel": "RMS Size (m)",
            "lattice_elements": lattice_elements_payload(context.lattice),
            "curves": [
                {"x": series["z"], "y": series["sigma_x"], "label": "RMS x", "color": "blue"},
                {"x": series["z"], "y": series["sigma_y"], "label": "RMS y", "color": "red"},
                {
                    "x": series["z"],
                    "y": series["sigma_z"],
                    "label": "RMS z",
                    "color": "green",
                    "linestyle": "--",
                },
            ],
        }
        return MetricResult(value=value, plot_payload=plot)


class BeamDivergenceMetric(Metric):
    """RMS(x'), RMS(y') vs longitudinal position."""

    @property
    def name(self) -> str:
        return "beam_divergence"

    @property
    def unit(self) -> str:
        return "rad"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        series = longitudinal_series(context)
        value = (
            float(np.hypot(series["sigma_xp"][-1], series["sigma_yp"][-1]))
            if len(series["z"])
            else 0.0
        )
        plot = {
            "plot_type": "divergence",
            "title": f"RMS Divergence ({context.case_metadata.get('name', '')})",
            "xlabel": "Longitudinal Position z (m)",
            "ylabel": "RMS Divergence (rad)",
            "lattice_elements": lattice_elements_payload(context.lattice),
            "curves": [
                {"x": series["z"], "y": series["sigma_xp"], "label": "RMS(x')", "color": "blue"},
                {"x": series["z"], "y": series["sigma_yp"], "label": "RMS(y')", "color": "red"},
            ],
        }
        return MetricResult(value=value, plot_payload=plot)


class GeometricEmittanceMetric(Metric):
    """Absolute horizontal/vertical RMS geometric emittance vs z."""

    @property
    def name(self) -> str:
        return "geometric_emittance"

    @property
    def unit(self) -> str:
        return "m.rad"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        series = longitudinal_series(context)
        value = (
            float(np.hypot(series["emittance_x"][-1], series["emittance_y"][-1]))
            if len(series["z"])
            else 0.0
        )
        plot = {
            "plot_type": "geometric_emittance",
            "title": f"Geometric Emittance ({context.case_metadata.get('name', '')})",
            "xlabel": "Longitudinal Position z (m)",
            "ylabel": r"RMS Geometric Emittance (m·rad)",
            "lattice_elements": lattice_elements_payload(context.lattice),
            "curves": [
                {
                    "x": series["z"],
                    "y": series["emittance_x"],
                    "label": r"$\varepsilon_x$",
                    "color": "purple",
                },
                {
                    "x": series["z"],
                    "y": series["emittance_y"],
                    "label": r"$\varepsilon_y$",
                    "color": "darkorange",
                },
            ],
        }
        return MetricResult(value=value, plot_payload=plot)


class PhaseSpaceMetric(Metric):
    """Entrance / exit phase-space snapshots (x–x', y–y', x–y)."""

    @property
    def name(self) -> str:
        return "phase_space"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        pos_in, mom_in = entrance_phase_space(context)
        pos_out, mom_out, reached = _exit_phase_space(context)
        slopes_in = slopes_from_momentum(mom_in) if len(mom_in) else np.zeros((0, 2))
        if np.any(reached):
            pos_ex = pos_out[reached]
            mom_ex = mom_out[reached]
            slopes_ex = slopes_from_momentum(mom_ex)
        else:
            pos_ex = np.zeros((0, 3))
            slopes_ex = np.zeros((0, 2))

        value = float(np.std(pos_ex[:, 0])) if len(pos_ex) > 1 else 0.0
        plot = {
            "plot_type": "phase_space",
            "title": f"Phase Space ({context.case_metadata.get('name', '')})",
            "panels": [
                {
                    "xlabel": "x (m)",
                    "ylabel": "x' (rad)",
                    "title": "x vs x'",
                    "series": [
                        {
                            "x": pos_in[:, 0],
                            "y": slopes_in[:, 0],
                            "label": "Entrance",
                            "color": "C0",
                        },
                        {
                            "x": pos_ex[:, 0],
                            "y": slopes_ex[:, 0],
                            "label": "Exit",
                            "color": "C3",
                        },
                    ],
                },
                {
                    "xlabel": "y (m)",
                    "ylabel": "y' (rad)",
                    "title": "y vs y'",
                    "series": [
                        {
                            "x": pos_in[:, 1],
                            "y": slopes_in[:, 1],
                            "label": "Entrance",
                            "color": "C0",
                        },
                        {
                            "x": pos_ex[:, 1],
                            "y": slopes_ex[:, 1],
                            "label": "Exit",
                            "color": "C3",
                        },
                    ],
                },
                {
                    "xlabel": "x (m)",
                    "ylabel": "y (m)",
                    "title": "x vs y",
                    "series": [
                        {
                            "x": pos_in[:, 0],
                            "y": pos_in[:, 1],
                            "label": "Entrance",
                            "color": "C0",
                        },
                        {
                            "x": pos_ex[:, 0],
                            "y": pos_ex[:, 1],
                            "label": "Exit",
                            "color": "C3",
                        },
                    ],
                },
            ],
        }
        return MetricResult(value=value, plot_payload=plot)


class MomentumSpreadMetric(Metric):
    """Δp/p mean/RMS through the lattice plus entrance/exit histograms."""

    @property
    def name(self) -> str:
        return "momentum_spread"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        series = longitudinal_series(context)
        pos_in, mom_in = entrance_phase_space(context)
        pos_out, mom_out, reached = _exit_phase_space(context)
        spread_in = momentum_spread(mom_in)
        if np.any(reached):
            spread_out = momentum_spread(mom_out[reached])
        else:
            spread_out = {"mean_p": 0.0, "rms_p": 0.0, "delta_p_over_p_rms": 0.0, "p_mag": np.array([])}

        value = float(spread_out["delta_p_over_p_rms"])
        p_in = spread_in["p_mag"]
        p_out = spread_out["p_mag"]
        mean_ref = max(abs(spread_in["mean_p"]), 1e-30)
        dpp_in = (p_in - spread_in["mean_p"]) / mean_ref if len(p_in) else np.array([])
        dpp_out = (p_out - spread_out["mean_p"]) / max(abs(spread_out["mean_p"]), 1e-30) if len(p_out) else np.array([])

        plot = {
            "plot_type": "momentum_spread",
            "title": f"Momentum Spread ({context.case_metadata.get('name', '')})",
            "mean_in": spread_in["mean_p"],
            "mean_out": spread_out["mean_p"],
            "rms_in": spread_in["rms_p"],
            "rms_out": spread_out["rms_p"],
            "dpp_rms_in": spread_in["delta_p_over_p_rms"],
            "dpp_rms_out": spread_out["delta_p_over_p_rms"],
            "lattice_elements": lattice_elements_payload(context.lattice),
            "curves": [
                {
                    "x": series["z"],
                    "y": series["delta_p_over_p"],
                    "label": r"RMS(Δp/p)",
                    "color": "teal",
                },
                {
                    "x": series["z"],
                    "y": (
                        series["mean_p"] / max(abs(float(series["mean_p"][0])), 1e-30)
                        if len(series["mean_p"])
                        else series["mean_p"]
                    ),
                    "label": r"⟨p⟩ / ⟨p⟩₀",
                    "color": "navy",
                    "linestyle": "--",
                },
            ],
            "histograms": [
                {"values": dpp_in, "label": "Entrance Δp/p", "color": "C0"},
                {"values": dpp_out, "label": "Exit Δp/p", "color": "C3"},
            ],
        }
        return MetricResult(value=value, plot_payload=plot)


class ElementLossMetric(Metric):
    """Per-element acceptance losses and cumulative transmission."""

    @property
    def name(self) -> str:
        return "element_losses"

    @property
    def unit(self) -> str:
        return "count"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        loss_info = per_element_losses(context)
        value = float(loss_info["n_lost_total"])
        labels = [
            f"{lab}\n[{zs:.2f},{ze:.2f}]"
            for lab, zs, ze in zip(loss_info["labels"], loss_info["z_start"], loss_info["z_end"])
        ]
        plot = {
            "plot_type": "element_loss",
            "title": f"Acceptance Losses ({context.case_metadata.get('name', '')})",
            "labels": labels,
            "losses": loss_info["losses"],
            "cumulative_transmission": loss_info["cumulative_transmission"],
            "n_initial": loss_info["n_initial"],
            "z_end": loss_info["z_end"],
        }
        return MetricResult(value=value, plot_payload=plot)


class TransferMatrixComparisonMetric(Metric):
    """
    Numerical first-order R vs modular optics backend (MAD-X / linear).

    Uses ensemble least-squares from entrance→exit tracked states.
    """

    def __init__(self, backend: str = "auto"):
        self._backend_name = backend

    @property
    def name(self) -> str:
        return "transfer_matrix_comparison"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        backend = get_optics_backend(self._backend_name)
        state = _particle_state_for_optics(context)
        ref = backend.transfer_matrix(context.lattice, state) if backend.available() else None
        if ref is None:
            # Prefer MAD-X when requested; otherwise always have linear fallback.
            if self._backend_name.lower() == "madx":
                return MetricResult(value=float("nan"))
            backend = get_optics_backend("linear")
            ref = backend.transfer_matrix(context.lattice, state)

        pos_in = context.diagnostics.position[0]
        mom_in = context.diagnostics.momentum[0]
        pos_out, mom_out, reached = _exit_phase_space(context)
        if not np.any(reached) or int(np.sum(reached)) < 5:
            return MetricResult(value=float("nan"))

        R_num = estimate_transfer_matrix_from_ensemble(
            pos_in[reached], mom_in[reached], pos_out[reached], mom_out[reached]
        )
        err = relative_matrix_error(R_num, ref.matrix)
        value = float(err["frobenius_relative"])
        plot = {
            "plot_type": "transfer_matrix",
            "title": f"Transfer Matrix vs {backend.name} ({context.case_metadata.get('name', '')})",
            "backend": backend.name,
            "R_numerical": R_num,
            "R_reference": ref.matrix,
            "diff": err["diff"],
            "frobenius_relative": value,
            "frobenius_diff": err["frobenius_diff"],
            "max_abs_diff": err["max_abs_diff"],
        }
        return MetricResult(value=value, plot_payload=plot)


class EnvelopeComparisonMetric(Metric):
    """Overlay Janus σx(z), σy(z) against a modular optics backend."""

    def __init__(self, backend: str = "auto"):
        self._backend_name = backend

    @property
    def name(self) -> str:
        return "envelope_comparison"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        series = longitudinal_series(context)
        backend = get_optics_backend(self._backend_name)
        state = _particle_state_for_optics(context)
        env = backend.envelope(context.lattice, state) if backend.available() else None
        if env is None:
            if self._backend_name.lower() == "madx":
                return MetricResult(value=float("nan"))
            backend = get_optics_backend("linear")
            env = backend.envelope(context.lattice, state)

        # Compare at element boundaries by interpolating Janus series onto backend z.
        if len(series["z"]) < 2:
            return MetricResult(value=float("nan"))
        sx_j = np.interp(env.z, series["z"], series["sigma_x"])
        sy_j = np.interp(env.z, series["z"], series["sigma_y"])
        rms_err = float(
            np.sqrt(np.mean((sx_j - env.sigma_x) ** 2 + (sy_j - env.sigma_y) ** 2))
        )
        plot = {
            "plot_type": "envelope_comparison",
            "title": f"Envelope vs {backend.name} ({context.case_metadata.get('name', '')})",
            "xlabel": "Longitudinal Position z (m)",
            "ylabel": "RMS Size (m)",
            "lattice_elements": lattice_elements_payload(context.lattice),
            "backend": backend.name,
            "curves": [
                {"x": series["z"], "y": series["sigma_x"], "label": "Janus σx", "color": "blue"},
                {"x": series["z"], "y": series["sigma_y"], "label": "Janus σy", "color": "red"},
                {
                    "x": env.z,
                    "y": env.sigma_x,
                    "label": f"{backend.name} σx",
                    "color": "blue",
                    "linestyle": "--",
                },
                {
                    "x": env.z,
                    "y": env.sigma_y,
                    "label": f"{backend.name} σy",
                    "color": "red",
                    "linestyle": "--",
                },
            ],
        }
        return MetricResult(value=rms_err, plot_payload=plot)


class TwissParametersMetric(Metric):
    """Janus Courant–Snyder parameters β, α, γ vs z (three compact figures)."""

    @property
    def name(self) -> str:
        return "twiss_parameters"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        series = longitudinal_series(context)
        if len(series["z"]) == 0:
            return MetricResult(value=float("nan"))
        value = float(np.hypot(series["beta_x"][-1], series["beta_y"][-1]))
        elements = lattice_elements_payload(context.lattice)
        case = context.case_metadata.get("name", "")
        plot = {
            "plot_type": "twiss",
            "title": f"Twiss Parameters ({case})",
            "lattice_elements": elements,
            "figures": [
                {
                    "filename": "twiss_beta.png",
                    "title": f"Twiss β ({case})",
                    "ylabel": r"$\beta$ (m)",
                    "curves": [
                        {"x": series["z"], "y": series["beta_x"], "label": r"$\beta_x$", "color": "blue"},
                        {"x": series["z"], "y": series["beta_y"], "label": r"$\beta_y$", "color": "red"},
                    ],
                },
                {
                    "filename": "twiss_alpha.png",
                    "title": f"Twiss α ({case})",
                    "ylabel": r"$\alpha$",
                    "curves": [
                        {"x": series["z"], "y": series["alpha_x"], "label": r"$\alpha_x$", "color": "blue"},
                        {"x": series["z"], "y": series["alpha_y"], "label": r"$\alpha_y$", "color": "red"},
                    ],
                },
                {
                    "filename": "twiss_gamma.png",
                    "title": f"Twiss γ ({case})",
                    "ylabel": r"$\gamma$ (1/m)",
                    "curves": [
                        {"x": series["z"], "y": series["gamma_x"], "label": r"$\gamma_x$", "color": "blue"},
                        {"x": series["z"], "y": series["gamma_y"], "label": r"$\gamma_y$", "color": "red"},
                    ],
                },
            ],
        }
        return MetricResult(value=value, plot_payload=plot)


def _resolve_twiss_backend(preferred: str, lattice, state):
    backend = get_optics_backend(preferred)
    tw = backend.twiss(lattice, state) if backend.available() else None
    if tw is not None and len(tw.z) > 0:
        return backend, tw
    if preferred.lower() == "madx":
        return backend, None
    backend = get_optics_backend("linear")
    return backend, backend.twiss(lattice, state)


def _twiss_comparison_result(
    context: ValidationContext,
    family: str,
    backend_name: str,
) -> MetricResult:
    """
    Compare Janus Twiss family (beta|alpha|gamma) against optics backend.

    Interpolates the reference onto Janus longitudinal samples.
    """
    series = longitudinal_series(context)
    if len(series["z"]) < 2:
        return MetricResult(value=float("nan"))

    state = _particle_state_for_optics(context)
    backend, ref = _resolve_twiss_backend(backend_name, context.lattice, state)
    if ref is None or len(ref.z) == 0:
        return MetricResult(value=float("nan"))

    key_x = f"{family}_x"
    key_y = f"{family}_y"
    jx = series[key_x]
    jy = series[key_y]
    rx = np.interp(series["z"], ref.z, getattr(ref, key_x))
    ry = np.interp(series["z"], ref.z, getattr(ref, key_y))

    err_x = series_comparison_errors(jx, rx)
    err_y = series_comparison_errors(jy, ry)
    summary = combine_plane_errors(err_x, err_y)

    symbols = {"beta": r"\beta", "alpha": r"\alpha", "gamma": r"\gamma"}
    units = {"beta": "m", "alpha": "", "gamma": "1/m"}
    sym = symbols[family]
    unit = units[family]
    ylabel = rf"${sym}$ ({unit})" if unit else rf"${sym}$"
    case = context.case_metadata.get("name", "")

    plot = {
        "plot_type": "twiss_comparison",
        "family": family,
        "filename": f"twiss_{family}_comparison.png",
        "title": f"Twiss {family} vs {backend.name} ({case})",
        "xlabel": "Longitudinal Position z (m)",
        "ylabel": ylabel,
        "lattice_elements": lattice_elements_payload(context.lattice),
        "backend": backend.name,
        "errors": summary,
        "curves": [
            {"x": series["z"], "y": jx, "label": rf"Janus ${sym}_x$", "color": "blue"},
            {"x": series["z"], "y": jy, "label": rf"Janus ${sym}_y$", "color": "red"},
            {
                "x": series["z"],
                "y": rx,
                "label": rf"{backend.name} ${sym}_x$",
                "color": "blue",
                "linestyle": "--",
            },
            {
                "x": series["z"],
                "y": ry,
                "label": rf"{backend.name} ${sym}_y$",
                "color": "red",
                "linestyle": "--",
            },
        ],
    }
    return MetricResult(value=float(summary["rms_relative"]), plot_payload=plot)


class TwissBetaComparisonMetric(Metric):
    def __init__(self, backend: str = "auto"):
        self._backend_name = backend

    @property
    def name(self) -> str:
        return "twiss_beta_comparison"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        return _twiss_comparison_result(context, "beta", self._backend_name)


class TwissAlphaComparisonMetric(Metric):
    def __init__(self, backend: str = "auto"):
        self._backend_name = backend

    @property
    def name(self) -> str:
        return "twiss_alpha_comparison"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        return _twiss_comparison_result(context, "alpha", self._backend_name)


class TwissGammaComparisonMetric(Metric):
    def __init__(self, backend: str = "auto"):
        self._backend_name = backend

    @property
    def name(self) -> str:
        return "twiss_gamma_comparison"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        return _twiss_comparison_result(context, "gamma", self._backend_name)
