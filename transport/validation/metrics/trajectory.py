"""Trajectory comparison metrics."""

import numpy as np

from transport.validation.case import ValidationContext
from transport.validation.metrics.base import Metric, MetricResult, MetricScope, ReferenceRequirement
from transport.validation.references.base import ReferenceCapability


def _get_analytical_ref(context: ValidationContext):
    for ref in context.resolved_references.values():
        if ref.summary_observables or ref.pointwise_trajectory:
            return ref
    return None


def _fit_circle(x, z):
    A = np.column_stack((2 * x, 2 * z, np.ones_like(x)))
    Y = x ** 2 + z ** 2
    w, _, _, _ = np.linalg.lstsq(A, Y, rcond=None)
    Xc, Zc, C = w[0], w[1], w[2]
    return np.sqrt(C + Xc ** 2 + Zc ** 2), Xc, Zc


class DriftCoordinateErrorMetric(Metric):
    def __init__(self, axis: str):
        self.axis = axis

    @property
    def name(self) -> str:
        return f"{self.axis}_error"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.SINGLE

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.POINTWISE_TRAJECTORY

    def compute(self, context: ValidationContext) -> MetricResult:
        ref = _get_analytical_ref(context)
        traj = ref.pointwise_trajectory
        idx = {"x": 0, "y": 1, "z": 2}[self.axis]
        pos = context.diagnostics.position[:, :, idx]
        expected = traj[self.axis]
        errors = np.max(np.abs(pos - expected[:, np.newaxis]), axis=0)
        value = float(np.max(errors))
        plot = _drift_error_plot(context, ref)
        return MetricResult(value=value, per_particle=errors, plot_payload=plot)


class CyclotronRadiusErrorMetric(Metric):
    @property
    def name(self) -> str:
        return "cyclotron_radius_error"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.SINGLE

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.SUMMARY_OBSERVABLES

    def compute(self, context: ValidationContext) -> MetricResult:
        ref = _get_analytical_ref(context)
        R_analytical = ref.summary_observables["cyclotron_radius"]
        meta = context.case_metadata
        z_start = meta["z_start"]
        dipole_length = meta["dipole_length"]
        z_end = z_start + dipole_length

        pos = context.diagnostics.position
        alive = context.diagnostics.alive
        mask = (pos[:, 0, 2] > z_start) & (pos[:, 0, 2] <= z_end) & alive[:, 0]
        x_track = pos[mask, 0, 0]
        z_track = pos[mask, 0, 2]

        if len(x_track) > 3:
            R_sim, _, _ = _fit_circle(x_track, z_track)
        else:
            R_sim = 0.0
        value = abs(R_sim - R_analytical) / R_analytical
        plot = _dipole_radial_plot(context, meta)
        return MetricResult(value=value, plot_payload=plot)


class BendAngleErrorMetric(Metric):
    @property
    def name(self) -> str:
        return "bend_angle_error"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.SINGLE

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.SUMMARY_OBSERVABLES

    def compute(self, context: ValidationContext) -> MetricResult:
        ref = _get_analytical_ref(context)
        theta_analytical = ref.summary_observables["bend_angle"]
        mom = context.diagnostics.momentum
        alive = context.diagnostics.alive
        alive_idxs = np.where(alive[:, 0])[0]
        if len(alive_idxs) > 0:
            last_alive_idx = alive_idxs[-1]
            px_exit = mom[last_alive_idx, 0, 0]
            pz_exit = mom[last_alive_idx, 0, 2]
            theta_exit = np.arctan2(px_exit, pz_exit)
            px_entry = mom[0, 0, 0]
            pz_entry = mom[0, 0, 2]
            theta_entry = np.arctan2(px_entry, pz_entry)
            theta_sim = theta_exit - theta_entry
        else:
            theta_sim = 0.0
        value = abs(abs(theta_sim) - abs(theta_analytical)) / abs(theta_analytical)
        return MetricResult(value=value)


def _drift_error_plot(context, ref) -> dict:
    diag = context.diagnostics.to_dict()
    t = diag["time"]
    pos = diag["position"][:, 0]
    traj = ref.pointwise_trajectory
    return {
        "plot_type": "error",
        "title": "Drift Trajectory Coordinate Error vs Analytical",
        "xlabel": "Time (ns)",
        "ylabel": "Absolute Coordinate Error (m)",
        "curves": [
            {"x": t * 1e9, "y": np.abs(pos[:, 0] - traj["x"]), "label": "X Error", "color": "blue"},
            {"x": t * 1e9, "y": np.abs(pos[:, 1] - traj["y"]), "label": "Y Error", "color": "green"},
            {"x": t * 1e9, "y": np.abs(pos[:, 2] - traj["z"]), "label": "Z Error", "color": "red"},
        ],
    }


def _dipole_radial_plot(context, meta) -> dict:
    diag = context.diagnostics.to_dict()
    t = diag["time"]
    pos = diag["position"][:, 0]
    alive = diag["alive"][:, 0]
    z_start = meta["z_start"]
    dipole_length = meta["dipole_length"]
    mask = (pos[:, 2] > z_start) & (pos[:, 2] <= z_start + dipole_length) & alive
    x_track = pos[mask, 0]
    z_track = pos[mask, 2]
    curves = []
    if len(x_track) > 3:
        R_sim, Xc, Zc = _fit_circle(x_track, z_track)
        radial_dist = np.sqrt((pos[:, 0] - Xc) ** 2 + (pos[:, 2] - Zc) ** 2)
        r_err = np.abs(radial_dist - R_sim)
        curves.append({
            "x": t[mask] * 1e9, "y": r_err[mask],
            "label": "Radial Deviation from Circle Fit", "color": "purple",
        })
    return {
        "plot_type": "error",
        "title": "Dipole Orbit Circular Fit Deviations",
        "xlabel": "Time (ns)",
        "ylabel": "Radial Deviation (m)",
        "curves": curves,
    }
