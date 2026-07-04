"""Generic validation engine — case/element/count/reference agnostic."""

import numpy as np

from transport.validation.case import MetricEvaluation, ValidationCase, ValidationContext
from transport.validation.config import ComparisonDirection, PassCriteria
from transport.validation.reporting.plot_generator import PlotGenerator
from transport.validation.reporting.reporter import Reporter
from transport.validation.reporting.result_store import ResultStore
from transport.validation.solver import BorisSolverAdapter


class ValidationEngine:
    def __init__(self, solver=None):
        self.solver = solver or BorisSolverAdapter()

    def run(self, case: ValidationCase, run_outputs_dir: str = None,
            prebuilt_lattice=None, prebuilt_batch=None, prebuilt_diagnostics=None):
        lattice = prebuilt_lattice or case.build_system()
        batch = prebuilt_batch or case.particle_source.generate()
        num_cfg = case.numerical_config

        if prebuilt_diagnostics is not None:
            diagnostics = prebuilt_diagnostics
        else:
            mass = batch.mass
            if mass is None:
                from transport.physics.boris_solver import M_P_KG
                mass = np.full(len(batch.R), M_P_KG)
            _, _, _, diagnostics = self.solver.run(
                batch.R, batch.V, batch.gamma, batch.charges,
                lattice, num_cfg.dt, num_cfg.max_steps,
                mass=mass,
            )

        mass = batch.mass
        if mass is None:
            from transport.physics.boris_solver import M_P_KG
            mass = np.full(len(batch.R), M_P_KG)

        resolved_refs = {}
        context = ValidationContext(
            diagnostics=diagnostics,
            lattice=lattice,
            R_init=batch.R,
            V_init=batch.V,
            gamma_init=batch.gamma,
            charges=batch.charges,
            mass=mass,
            particle_source_metadata=batch.metadata,
            resolved_references={},
            numerical_config=num_cfg,
            case_metadata={"name": case.name, **case.metadata},
        )

        for ref in case.references:
            resolved_refs[ref.name] = ref.resolve(context)
        context = ValidationContext(
            diagnostics=diagnostics,
            lattice=lattice,
            R_init=batch.R,
            V_init=batch.V,
            gamma_init=batch.gamma,
            charges=batch.charges,
            mass=mass,
            particle_source_metadata=batch.metadata,
            resolved_references=resolved_refs,
            numerical_config=num_cfg,
            case_metadata={"name": case.name, **case.metadata},
        )

        evaluations = []
        plot_payloads = []
        for metric, tolerance in case.metric_specs:
            applicable, skip_reason = metric.is_applicable(context)
            if not applicable:
                evaluations.append(MetricEvaluation(
                    name=metric.name, value=float("nan"), unit=metric.unit,
                    scope=metric.scope.value, is_verification=metric.is_verification,
                    tolerance=tolerance, status="skipped", skip_reason=skip_reason,
                ))
                continue
            result = metric.compute(context)
            status = self._apply_tolerance(result.value, tolerance)
            if result.plot_payload:
                plot_payloads.append(result.plot_payload)
            evaluations.append(MetricEvaluation(
                name=metric.name, value=result.value, unit=metric.unit,
                scope=metric.scope.value, is_verification=metric.is_verification,
                tolerance=tolerance, status=status,
                per_particle=result.per_particle, plot_payload=result.plot_payload,
            ))

        converged = None
        conv_report = ""
        conv_plot = None
        if num_cfg.convergence.enabled:
            from transport.validation.registry import convergence_registry
            mode = num_cfg.convergence.mode
            if num_cfg.convergence.use_self_convergence:
                mode = "self"
            strategy = convergence_registry.get(mode)
            conv_result = strategy.run(case, context, self.solver)
            if conv_result is not None:
                converged, errors, dts, conv_plot = conv_result
                conv_report = Reporter.render_convergence_report(case, dts, errors, converged)
                if conv_plot:
                    plot_payloads.append(conv_plot)

        report = Reporter.render_validation_report(case, lattice, len(batch.R), evaluations)
        passed = Reporter._aggregate_pass(evaluations, case.output_config.pass_criteria)
        if converged is not None and not converged:
            passed = False

        if run_outputs_dir is not None and case.output_config.emit_report:
            case_subdir = _case_output_dir(run_outputs_dir, case.name)
            store = ResultStore(case_subdir)
            full_report = report
            if conv_report:
                full_report += "\n\n" + conv_report
            store.save_report(full_report)
            if case.output_config.emit_json:
                store.save_results_json(evaluations, converged)
            if case.output_config.emit_csv:
                store.save_metrics_csv(evaluations)
            if case.output_config.emit_manifest:
                store.save_manifest(
                    case, num_cfg, case.particle_source.description,
                    species=batch.species, mass=batch.mass,
                )
            if case.output_config.emit_plots and plot_payloads:
                PlotGenerator(run_outputs_dir, case.name).generate(plot_payloads)

        return {
            "passed": passed,
            "converged": converged,
            "evaluations": evaluations,
            "report": report,
            "convergence_report": conv_report,
            "diagnostics": diagnostics,
            "lattice": lattice,
            "batch": batch,
        }

    @staticmethod
    def _apply_tolerance(value, tolerance) -> str:
        import math
        if tolerance is None or tolerance.informational:
            return "info"
        if not math.isfinite(value):
            return "failed"
        if tolerance.direction == ComparisonDirection.LE:
            return "passed" if value <= tolerance.threshold else "failed"
        if tolerance.direction == ComparisonDirection.GE:
            return "passed" if value >= tolerance.threshold else "failed"
        return "passed" if abs(value) <= tolerance.threshold else "failed"


def _case_output_dir(run_outputs_dir, case_name):
    import os
    sub = case_name.lower().replace("validation", "")
    path = os.path.join(run_outputs_dir, sub)
    os.makedirs(path, exist_ok=True)
    return path
