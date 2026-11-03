"""Trajectory comparison metrics."""

from typing import Optional

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
            {"x": t * 1e9, "y": abs(pos[:, 0] - traj["x"]), "label": "X Error", "color": "blue"},
            {"x": t * 1e9, "y": abs(pos[:, 1] - traj["y"]), "label": "Y Error", "color": "green"},
            {"x": t * 1e9, "y": abs(pos[:, 2] - traj["z"]), "label": "Z Error", "color": "red"},
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


class HornMomentumKickMetric(Metric):
    @property
    def name(self) -> str:
        return "horn_momentum_kick_error"

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
        expected = float(ref.summary_observables["expected_radial_kick"])

        meta = context.case_metadata
        z_start = float(meta.get("z_start", context.lattice.z_start))
        z_end = z_start + float(meta.get("horn_length", context.lattice.total_length))
        delta_pr_sim = _horn_radial_kick_from_diagnostics(
            context.diagnostics, context.R_init[0], z_start, z_end
        )
        if not np.isfinite(delta_pr_sim):
            return MetricResult(value=float("inf"))

        if abs(expected) < 1e-30:
            value = abs(delta_pr_sim)
        else:
            value = abs(delta_pr_sim - expected) / abs(expected)

        R0 = context.R_init[0]
        r0 = float(np.linalg.norm(R0[:2]))
        rhat = R0[:2] / r0
        plot = _horn_momentum_plot(context, expected, rhat)
        return MetricResult(value=value, plot_payload=plot)


class HornRadiusSweepMetric(Metric):
    """
    Sweep injection radii across the horn annulus and verify Δp_r ∝ 1/r.

    Runs independent single-particle transports at several radii. The metric
    value is the relative RMS residual of a through-origin fit
    Δp_r = a / r (equivalently, constancy of Δp_r · r).
    """

    @property
    def name(self) -> str:
        return "horn_delta_p_inv_r"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.ANY

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.NONE

    def is_applicable(self, context: ValidationContext) -> tuple[bool, Optional[str]]:
        meta = context.case_metadata
        if meta.get("element") != "horn":
            return False, "horn radius sweep requires element=horn"
        if "inner_radius" not in meta or "outer_radius" not in meta:
            return False, "horn radius sweep requires inner_radius and outer_radius"
        return True, None

    def compute(self, context: ValidationContext) -> MetricResult:
        from transport.validation.solver import BorisSolverAdapter

        meta = context.case_metadata
        inner = float(meta["inner_radius"])
        outer = float(meta["outer_radius"])
        z_start = float(meta.get("z_start", context.lattice.z_start))
        horn_length = float(meta.get("horn_length", context.lattice.total_length))
        z_end = z_start + horn_length
        n_radii = int(meta.get("horn_radius_sweep_points", 6))
        n_radii = max(n_radii, 3)

        # Stay clear of the conductors where the ideal 1/r field model ends.
        r_lo = inner * 1.15
        r_hi = outer * 0.90
        if r_hi <= r_lo:
            r_lo = inner * 1.05
            r_hi = outer * 0.95
        if r_hi <= r_lo:
            return MetricResult(value=float("inf"))

        radii = np.linspace(r_lo, r_hi, n_radii)
        V0 = np.asarray(context.V_init[0], dtype=np.float64).copy()
        # Purely longitudinal injection so measured Δp_r is the horn kick.
        V0[0] = 0.0
        V0[1] = 0.0
        charge = int(context.charges[0])
        mass = float(context.mass[0])
        num = context.numerical_config
        solver = BorisSolverAdapter()

        delta_pr = []
        for r in radii:
            R = np.array([[r, 0.0, z_start]], dtype=np.float64)
            V = np.array([V0], dtype=np.float64)
            v_mag = float(np.linalg.norm(V0))
            from transport.physics.boris_solver import C_LIGHT
            gamma = np.array(
                [1.0 / np.sqrt(max(1.0 - (v_mag / C_LIGHT) ** 2, 1e-30))],
                dtype=np.float64,
            )
            charges = np.array([charge], dtype=np.int8)
            mass_arr = np.array([mass], dtype=np.float64)
            _, _, _, diag = solver.run(
                R, V, gamma, charges, context.lattice, num.dt, num.max_steps, mass=mass_arr
            )
            kick = _horn_radial_kick_from_diagnostics(diag, R[0], z_start, z_end)
            if not np.isfinite(kick):
                return MetricResult(value=float("inf"))
            delta_pr.append(kick)

        radii = np.asarray(radii, dtype=np.float64)
        delta_pr = np.asarray(delta_pr, dtype=np.float64)
        inv_r = 1.0 / radii

        # Through-origin fit Δp = a / r  ⇒  a = Σ(Δp/r) / Σ(1/r²) in least squares
        # for model y = a x with x=1/r, y=Δp.
        a_fit = float(np.sum(delta_pr * inv_r) / np.sum(inv_r ** 2))
        delta_pr_fit = a_fit * inv_r
        resid = delta_pr - delta_pr_fit
        rms_data = float(np.sqrt(np.mean(delta_pr ** 2)))
        rms_resid = float(np.sqrt(np.mean(resid ** 2)))
        value = rms_resid / rms_data if rms_data > 0 else float("inf")

        # Also report constancy of Δp·r (same physics).
        product = delta_pr * radii

        plot = {
            "plot_type": "horn_radius_sweep",
            "title": "Horn Radial Kick Scaling (Δp ∝ 1/r)",
            "radii": radii,
            "inv_r": inv_r,
            "delta_pr": delta_pr,
            "delta_pr_fit": delta_pr_fit,
            "product": product,
            "fit_slope": a_fit,
            "residual_rms_relative": value,
        }
        return MetricResult(value=value, plot_payload=plot)


def _horn_radial_kick_from_diagnostics(diagnostics, R0, z_start, z_end) -> float:
    mom = diagnostics.momentum
    alive = diagnostics.alive
    pos = diagnostics.position
    alive_idxs = np.where(alive[:, 0])[0]
    if len(alive_idxs) == 0:
        return float("nan")

    z = pos[:, 0, 2]
    in_horn = alive_idxs[(z[alive_idxs] >= z_start) & (z[alive_idxs] <= z_end)]
    if len(in_horn) < 2:
        first, last = int(alive_idxs[0]), int(alive_idxs[-1])
    else:
        first, last = int(in_horn[0]), int(in_horn[-1])

    r0 = float(np.linalg.norm(R0[:2]))
    if r0 < 1e-12:
        return float("nan")
    rhat = R0[:2] / r0
    pr0 = float(np.dot(mom[first, 0, :2], rhat))
    prf = float(np.dot(mom[last, 0, :2], rhat))
    return prf - pr0


def _horn_momentum_plot(context, expected, rhat):
    diag = context.diagnostics.to_dict()
    t = diag["time"]
    mom = diag["momentum"][:, 0]
    pr = mom[:, 0] * rhat[0] + mom[:, 1] * rhat[1]
    return {
        "plot_type": "error",
        "title": "Horn Radial Momentum",
        "xlabel": "Time (ns)",
        "ylabel": "Radial Momentum (MeV/c)",
        "curves": [
            {
                "x": t * 1e9,
                "y": pr,
                "label": "Simulated p_r",
                "color": "blue",
            },
            {
                "x": np.array([t[0], t[-1]]) * 1e9,
                "y": np.array([pr[0], pr[0] + expected]),
                "label": "Analytical Δp_r",
                "color": "red",
            },
        ],
    }
