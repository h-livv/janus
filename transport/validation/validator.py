import numpy as np
from transport.physics.boris_solver import track_particles, relativistic_boris_step, C_LIGHT
from transport.validation.metrics import calculate_momentum_drift, calculate_energy_drift

class Validator:
    @staticmethod
    def run(case, dt, max_steps, run_outputs_dir=None, diagnostics=None, lattice=None, R_init=None):
        """
        Executes tracking on a ValidationCase and returns:
          passed (bool), metrics (dict), report (str)

        When diagnostics, lattice, and R_init are supplied, skips transport
        integration and validates the provided simulation output only.
        """
        if diagnostics is None:
            # 1. Setup particles and lattice
            R_init, V_init, gamma_init, charges = case.initial_particles()
            lattice = case.build_lattice()

            # 2. Track
            R_final, V_final, alive_mask, diagnostics = track_particles(
                R_init, V_init, gamma_init, charges, lattice, dt, max_steps
            )
        elif lattice is None or R_init is None:
            raise ValueError("lattice and R_init are required when diagnostics are provided")

        # 3. Compute analytical solution
        analytical = case.analytical_solution(diagnostics)

        # 4. Compute metrics
        metrics = {
            "momentum_conservation": calculate_momentum_drift(diagnostics),
            "energy_conservation": calculate_energy_drift(diagnostics)
        }

        # Case-specific metrics
        case_metrics = case.evaluate(diagnostics, analytical)
        metrics.update(case_metrics)

        # 4b. Generate Conservation & Error Plots
        if run_outputs_dir is not None:
            from transport.validation.plots import generate_conservation_and_error_plots
            generate_conservation_and_error_plots(case, diagnostics, analytical, run_outputs_dir)

        # 5. Check against tolerances
        tolerances = {
            "momentum_conservation": 1e-6,
            "energy_conservation": 1e-6
        }
        tolerances.update(case.get_tolerances())

        passed = True
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append(f"VALIDATION REPORT: {case.name}")
        report_lines.append("=" * 60)
        
        # Metadata
        report_lines.append(f"Number of Particles: {len(R_init)}")
        for idx, el in enumerate(lattice.elements):
            el_name = type(el).__name__
            ap_radius = f"{el.aperture_radius} m" if el.aperture_radius is not None else "Infinite"
            field_details = ""
            if hasattr(el, 'By'):
                field_details = f" | By = {el.By} T"
            report_lines.append(f"Element {idx+1}: {el_name} | Length: {el.L:.3f} m | Aperture: {ap_radius}{field_details}")
        report_lines.append("-" * 60)

        for metric_name, value in metrics.items():
            tol = tolerances.get(metric_name)
            if tol is not None:
                # Support tuple tolerance for min/max or absolute tolerance comparison
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

        report = "\n".join(report_lines)
        return passed, metrics, report

    @staticmethod
    def run_convergence(case, dt_base, max_steps_base, run_outputs_dir=None, num_points=8):
        """
        Runs convergence checks with a configurable number of timesteps.
        """
        dts = [dt_base / (2.0**i) for i in range(num_points)]
        steps = [int(max_steps_base * (2**i)) for i in range(num_points)]
        
        errors = []
        
        for dt, step_limit in zip(dts, steps):
            R_init, V_init, gamma_init, charges = case.initial_particles()
            lattice = case.build_lattice()
            
            z_exit = lattice.z_start + lattice.total_length
            
            R = R_init.copy()
            V = V_init.copy()
            v_mag_sq = np.sum(V**2, axis=1)
            gamma = 1.0 / np.sqrt(1.0 - v_mag_sq / C_LIGHT**2)
            alive_mask = np.ones(1, dtype=bool)
            
            # Stagger initial velocity backward by dt/2 to obtain V^{-1/2}
            R_temp = R_init.copy()
            _, V, gamma = relativistic_boris_step(R_temp, V, gamma, -dt / 2.0, alive_mask, lattice, charges)
            
            t = 0.0
            crossed = False
            R_exit_sim = None
            t_exit = None
            
            # Step limit is scaled up to guarantee crossing the exit plane
            for step in range(step_limit * 2):
                z_old = R[0, 2]
                R_old = R.copy()
                t_old = t
                
                # Perform the Boris push: updates V^{n-1/2} -> V^{n+1/2} and R^n -> R^{n+1}
                R, V, gamma = relativistic_boris_step(R, V, gamma, dt, alive_mask, lattice, charges)
                t += dt
                
                z_new = R[0, 2]
                
                if z_old < z_exit and z_new >= z_exit:
                    alpha = (z_exit - z_old) / (z_new - z_old)
                    x_exit = R_old[0, 0] + alpha * (R[0, 0] - R_old[0, 0])
                    y_exit = R_old[0, 1] + alpha * (R[0, 1] - R_old[0, 1])
                    t_exit = t_old + alpha * dt
                    R_exit_sim = np.array([x_exit, y_exit, z_exit])
                    crossed = True
                    break
            
            if not crossed:
                # Fallback to final position
                R_exit_sim = R[0]
                t_exit = t
                
            R_ana = case.analytical_position(t_exit, R_init, V_init, charges)[0]
            err = np.linalg.norm(R_exit_sim - R_ana)
            errors.append(err)
            
        # Verify that errors are monotonically decreasing, or are already at machine precision limit
        is_converging = all(errors[i+1] < errors[i] for i in range(num_points - 1)) or (errors[0] < 1e-11)
        
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
