"""Analytical-reference convergence strategy."""

from transport.validation.convergence.base import ConvergenceStrategy
from transport.validation.metrics.numerical import run_convergence_study


class AnalyticalConvergence(ConvergenceStrategy):
    def run(self, case, context, solver):
        analytical_fn = case.metadata.get("analytical_position_fn")
        if analytical_fn is None:
            return None
        num_cfg = context.numerical_config
        return run_convergence_study(
            case,
            context,
            solver,
            analytical_fn,
            num_points=num_cfg.convergence.num_points,
            refinement_ratio=num_cfg.convergence.refinement_ratio,
        )
