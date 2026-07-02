import numpy as np
from transport.physics.boris_solver import track_particles, C_LIGHT
from transport.validation.metrics import calculate_momentum_drift, calculate_energy_drift


def _find_exit_state(diagnostics, z_exit):
    pos = diagnostics["position"][:, 0]
    times = diagnostics["time"]

    for i in range(1, len(times)):
        z_old = pos[i - 1, 2]
        z_new = pos[i, 2]
        if z_old < z_exit and z_new >= z_exit:
            alpha = (z_exit - z_old) / (z_new - z_old)
            r_old = pos[i - 1]
            r_new = pos[i]
            x_exit = r_old[0] + alpha * (r_new[0] - r_old[0])
            y_exit = r_old[1] + alpha * (r_new[1] - r_old[1])
            t_exit = times[i - 1] + alpha * (times[i] - times[i - 1])
            return np.array([x_exit, y_exit, z_exit]), t_exit, True

    return pos[-1], times[-1], False


class Validator:
    @staticmethod
    def run(case, dt, max_steps, run_outputs_dir=None, diagnostics=None, lattice=None, R_init=None):
        """
        Validates transport diagnostics against analytical reference.
        Requires diagnostics, lattice, and R_init from the transport pipeline.
        """
        if diagnostics is None or lattice is None or R_init is None:
            raise ValueError("diagnostics, lattice, and R_init are required")

        analytical = case.analytical_solution(diagnostics)

        metrics = {
            "momentum_conservation": calculate_momentum_drift(diagnostics),
            "energy_conservation": calculate_energy_drift(diagnostics),
        }
        metrics.update(case.evaluate(diagnostics, analytical))

        if run_outputs_dir is not None:
            from transport.validation.plots import generate_conservation_and_error_plots
            generate_conservation_and_error_plots(case, diagnostics, analytical, run_outputs_dir)

        tolerances = {
            "momentum_conservation": 1e-6,
            "energy_conservation": 1e-6,
        }
        tolerances.update(case.get_tolerances())

        passed = True
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append(f"VALIDATION REPORT: {case.name}")
        report_lines.append("=" * 60)
        report_lines.append(f"Number of Particles: {len(R_init)}")
        for idx, el in enumerate(lattice.elements):
            el_name = type(el).__name__
            ap_radius = f"{el.aperture_radius} m" if el.aperture_radius is not None else "Infinite"
            field_details = ""
            if hasattr(el, "By"):
                field_details = f" | By = {el.By} T"
            report_lines.append(
                f"Element {idx+1}: {el_name} | Length: {el.L:.3f} m | Aperture: {ap_radius}{field_details}"
            )
        report_lines.append("-" * 60)

        for metric_name, value in metrics.items():
            tol = tolerances.get(metric_name)
            if tol is not None:
                metric_passed = value <= tol
                status = "PASS" if metric_passed else "FAIL"
                if not metric_passed:
                    passed = False
                report_lines.append(f"{metric_name:<25} ({value:.3e} <= {tol:.3e})   {status}")
            else:
                report_lines.append(f"{metric_name:<25} ({value:.3e})               INFO")

        report_lines.append("-" * 60)
        report_lines.append(f"Overall Result: {'PASS' if passed else 'FAIL'}")
        report_lines.append("=" * 60)

        return passed, metrics, "\n".join(report_lines)

    @staticmethod
    def run_convergence(case, config, run_outputs_dir=None, num_points=8):
        """
        Runs convergence checks using the same transport pipeline as production runs.
        """
        dt_base = config.dt
        max_steps_base = config.max_steps_conv
        dts = [dt_base / (2.0**i) for i in range(num_points)]
        steps = [int(max_steps_base * (2**i)) for i in range(num_points)]
        z_exit = config.lattice.z_start + config.lattice.total_length
        errors = []

        for dt, step_limit in zip(dts, steps):
            _, _, _, diagnostics = track_particles(
                config.R_init,
                config.V_init,
                config.gamma_init,
                config.charges,
                config.lattice,
                dt,
                step_limit * 2,
            )
            r_exit_sim, t_exit, _ = _find_exit_state(diagnostics, z_exit)
            r_ana = case.analytical_position(
                t_exit, config.R_init, config.V_init, config.charges
            )[0]
            errors.append(np.linalg.norm(r_exit_sim - r_ana))

        is_converging = all(errors[i + 1] < errors[i] for i in range(num_points - 1)) or (
            errors[0] < 1e-11
        )

        if run_outputs_dir is not None:
            from transport.validation.plots import plot_convergence
            plot_convergence(case, dts, errors, run_outputs_dir)

        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append(f"CONVERGENCE REPORT: {case.name}")
        report_lines.append("=" * 60)
        for i in range(num_points):
            label = f"dt/{2**i}" if i > 0 else "dt"
            report_lines.append(f"{label:<5} ({dts[i]:.3e}) Error: {errors[i]:.6e}")
        report_lines.append("-" * 60)
        report_lines.append(f"Monotonic Convergence: {'PASS' if is_converging else 'FAIL'}")
        report_lines.append("=" * 60)

        return is_converging, errors, "\n".join(report_lines)
