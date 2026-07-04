"""Self-convergence (Cauchy/Richardson) strategy — reference-free."""

import numpy as np

from transport.validation.convergence.base import ConvergenceStrategy
from transport.validation.references.numerical import find_exit_state


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

        exit_positions = []
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
            r_exit, _, _ = find_exit_state(diag.to_dict(), z_exit)
            exit_positions.append(r_exit)

        errors = []
        for i in range(len(exit_positions) - 1):
            errors.append(float(np.linalg.norm(exit_positions[i] - exit_positions[i + 1])))
        if not errors:
            errors = [0.0]
        while len(errors) < num_points:
            errors.append(errors[-1])
        errors = errors[:num_points]

        is_converging = (
            all(errors[i + 1] < errors[i] for i in range(len(errors) - 1))
            if len(errors) > 1
            else True
        ) or (errors[0] < 1e-11 if errors else True)

        log_dts = np.log10(dts)
        log_errors = np.log10([max(e, 1e-30) for e in errors])
        fit_n = min(4, len(dts))
        slope, _ = np.polyfit(log_dts[-fit_n:], log_errors[-fit_n:], 1)

        plot_payload = {
            "plot_type": "convergence",
            "title": f"Timestep Convergence: {case.name}",
            "dts": dts,
            "errors": errors,
            "slope": slope,
        }
        return is_converging, errors, dts, plot_payload
