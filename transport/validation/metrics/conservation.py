"""Conservation metrics wrapping existing drift functions."""

import numpy as np

from transport.validation.case import ValidationContext
from transport.validation.metrics.base import Metric, MetricResult, MetricScope, ReferenceRequirement
from transport.validation.metrics import legacy as legacy_metrics


class MomentumConservationMetric(Metric):
    @property
    def name(self) -> str:
        return "momentum_conservation"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.ANY

    @property
    def is_verification(self) -> bool:
        return True

    def compute(self, context: ValidationContext) -> MetricResult:
        value = legacy_metrics.calculate_momentum_drift(context.diagnostics.to_dict())
        plot = _combined_conservation_plot(context)
        return MetricResult(value=value, plot_payload=plot)


class EnergyConservationMetric(Metric):
    @property
    def name(self) -> str:
        return "energy_conservation"

    @property
    def unit(self) -> str:
        return "relative"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.ANY

    @property
    def is_verification(self) -> bool:
        return True

    def compute(self, context: ValidationContext) -> MetricResult:
        value = legacy_metrics.calculate_energy_drift(context.diagnostics.to_dict())
        return MetricResult(value=value)


def _combined_conservation_plot(context: ValidationContext) -> dict:
    diag = context.diagnostics.to_dict()
    t = diag["time"]
    i = 0
    mom = diag["momentum"][:, i]
    gamma = diag["gamma"][:, i]
    mom_mag = np.linalg.norm(mom, axis=1)
    p0 = mom_mag[0] if mom_mag[0] != 0 else 1e-12
    g0 = gamma[0] if gamma[0] != 0 else 1e-12
    p_rel_drift = np.abs(mom_mag - mom_mag[0]) / p0
    g_rel_drift = np.abs(gamma - gamma[0]) / g0
    return {
        "plot_type": "conservation",
        "title": f"Conservation of Momentum & Energy ({context.case_metadata.get('name', '')})",
        "xlabel": "Time (ns)",
        "ylabel": "Relative Drift",
        "curves": [
            {"x": t * 1e9, "y": p_rel_drift + 1e-18, "label": "Momentum Drift", "color": "blue"},
            {"x": t * 1e9, "y": g_rel_drift + 1e-18, "label": "Energy Drift (Gamma)",
             "color": "red", "linestyle": "--"},
        ],
        "log_y": True,
    }
