"""Numerical verification metrics (convergence, stability)."""

import numpy as np

from transport.validation.case import ValidationContext
from transport.validation.metrics.base import Metric, MetricResult, MetricScope, ReferenceRequirement
from transport.validation.references.numerical import find_exit_state


class ConvergenceStudyMetric(Metric):
    """Records convergence study results; computed by engine separately."""

    @property
    def name(self) -> str:
        return "convergence_monotonic"

    @property
    def unit(self) -> str:
        return "bool"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.SINGLE

    @property
    def is_verification(self) -> bool:
        return True

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.POINTWISE_TRAJECTORY

    def compute(self, context: ValidationContext) -> MetricResult:
        return MetricResult(value=0.0)


def run_convergence_study(case, context, solver, analytical_position_fn, num_points=8, refinement_ratio=2.0):
    """Run timestep refinement study against analytical exit position."""
    num_cfg = context.numerical_config
    dt_base = num_cfg.dt
    max_steps_base = num_cfg.max_steps_conv
    ratio = refinement_ratio if refinement_ratio else num_cfg.convergence.refinement_ratio
    dts = [dt_base / (ratio ** i) for i in range(num_points)]
    steps = [int(max_steps_base * (ratio ** i)) for i in range(num_points)]
    z_exit = context.lattice.z_start + context.lattice.total_length
    errors = []
    mass = context.mass

    for dt, step_limit in zip(dts, steps):
        _, _, _, diag = solver.run(
            context.R_init, context.V_init, context.gamma_init,
            context.charges, context.lattice, dt, step_limit * 2,
            mass=mass,
        )
        r_exit_sim, t_exit, _ = find_exit_state(diag.to_dict(), z_exit)
        r_ana = analytical_position_fn(t_exit, context.R_init, context.V_init, context.charges)[0]
        errors.append(float(np.linalg.norm(r_exit_sim - r_ana)))

    is_converging = all(errors[i + 1] < errors[i] for i in range(num_points - 1)) or (errors[0] < 1e-11)

    log_dts = np.log10(dts)
    log_errors = np.log10(errors)
    slope, _ = np.polyfit(log_dts[-4:], log_errors[-4:], 1)

    plot_payload = {
        "plot_type": "convergence",
        "title": f"Timestep Convergence: {case.name}",
        "dts": dts,
        "errors": errors,
        "slope": slope,
    }
    return is_converging, errors, dts, plot_payload
