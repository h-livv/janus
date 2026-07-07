"""Self-convergence (reference-finest grid) strategy."""

import numpy as np

from transport.validation.convergence.base import ConvergenceStrategy
from transport.validation.references.numerical import find_exit_states


def refinement_converged(errors: list[float], min_ratio: float = 2.0) -> bool:
    """
    Return True when the coarsest run differs from the finest grid by at least
    ``min_ratio``, i.e. timestep refinement measurably reduces exit error.
    """
    if not errors:
        return True
    if len(errors) == 1:
        return True
    coarse = errors[0]
    fine = errors[-2] if len(errors) > 1 else errors[-1]
    if coarse < 1e-11:
        return True
    return coarse > fine and coarse >= min_ratio * max(fine, 1e-30)


class SelfConvergence(ConvergenceStrategy):
    def run(self, case, context, solver):
        num_cfg = context.numerical_config
        dt_base = num_cfg.dt
        max_steps_base = num_cfg.max_steps_conv
        ratio = num_cfg.convergence.refinement_ratio
        num_points = num_cfg.convergence.num_points
        dts = [dt_base / (ratio ** i) for i in range(num_points)]
        steps = [int(max_steps_base * (ratio ** i)) for i in range(num_points)]
        z_exit = context.lattice.z_start + context.lattice.total_length

        exit_states = []
        mass = context.mass
        for dt, step_limit in zip(dts, steps):
            _, _, _, diag = solver.run(
                context.R_init,
                context.V_init,
                context.gamma_init,
                context.charges,
                context.lattice,
                dt,
                step_limit * 2,
                mass=mass,
            )
            exit_states.append(find_exit_states(diag.to_dict(), z_exit))

        r_finest = exit_states[-1]
        errors = [
            float(np.linalg.norm(r - r_finest)) for r in exit_states
        ]

        is_converging = refinement_converged(errors)

        plot_payload = {
            "plot_type": "convergence",
            "title": f"Timestep Refinement: {case.name}",
            "dts": dts,
            "errors": errors,
            "show_slope": False,
            "plot_scale": "linear"
            if case.metadata.get("validation_profile") in ("beam_optics", "simple_composite")
            else "loglog",
        }
        return is_converging, errors, dts, plot_payload
