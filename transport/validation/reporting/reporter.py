"""Text report generation."""

from transport.validation.case import MetricEvaluation
from transport.validation.config import ComparisonDirection, PassCriteria


class Reporter:
    @staticmethod
    def render_validation_report(case, lattice, n_particles, evaluations: list[MetricEvaluation]) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append(f"VALIDATION REPORT: {case.name}")
        lines.append("=" * 60)
        lines.append(f"Number of Particles: {n_particles}")
        for idx, el in enumerate(lattice.elements):
            el_name = type(el).__name__
            ap_radius = f"{el.aperture_radius} m" if el.aperture_radius is not None else "Infinite"
            field_details = ""
            if hasattr(el, "By"):
                field_details = f" | By = {el.By} T"
            lines.append(
                f"Element {idx + 1}: {el_name} | Length: {el.L:.3f} m | Aperture: {ap_radius}{field_details}"
            )
        lines.append("-" * 60)

        for ev in evaluations:
            if ev.status == "skipped":
                lines.append(f"{ev.name:<25} SKIPPED ({ev.skip_reason})")
                continue
            if ev.tolerance is not None and not ev.tolerance.informational:
                tol = ev.tolerance.threshold
                status = "PASS" if ev.status == "passed" else "FAIL"
                lines.append(f"{ev.name:<25} ({ev.value:.3e} <= {tol:.3e})   {status}")
            else:
                lines.append(f"{ev.name:<25} ({ev.value:.3e})               INFO")

        lines.append("-" * 60)
        passed = Reporter._aggregate_pass(evaluations, case.output_config.pass_criteria)
        lines.append(f"Overall Result: {'PASS' if passed else 'FAIL'}")
        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def render_convergence_report(case, dts, errors, converged: bool) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append(f"CONVERGENCE REPORT: {case.name}")
        lines.append("=" * 60)
        for i, (dt, err) in enumerate(zip(dts, errors)):
            label = f"dt/{2 ** i}" if i > 0 else "dt"
            lines.append(f"{label:<5} ({dt:.3e}) Error: {err:.6e}")
        lines.append("-" * 60)
        lines.append(f"Monotonic Convergence: {'PASS' if converged else 'FAIL'}")
        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def _aggregate_pass(evaluations, criteria: PassCriteria) -> bool:
        actionable = [e for e in evaluations if e.status not in ("skipped", "info")]
        if not actionable:
            return True
        if criteria == PassCriteria.ALL_MUST_PASS:
            return all(e.status == "passed" for e in actionable)
        return any(e.status == "passed" for e in actionable)
