"""Conservation metrics wrapping existing drift functions."""

import numpy as np

from transport.validation.case import ValidationContext
from transport.validation.metrics.base import Metric, MetricResult, MetricScope
from transport.validation.metrics import legacy as legacy_metrics
from transport.validation.reporting.lattice_annotations import lattice_elements_payload
from transport.validation.stats.beam import longitudinal_series


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
    """
    Single conservation figure.

    N=1: relative drifts of |p| and γ for the tracked particle.
    N≥2: beam-averaged |p|, γ, and kinetic proxy vs z (compressed summary).
    """
    diag = context.diagnostics
    n = diag.n_particles
    if n >= 2 and len(context.lattice.elements) > 2:
        series = longitudinal_series(context)
        if len(series["z"]) == 0:
            return _single_particle_conservation_plot(context, particle_index=0)
        p0 = max(abs(float(series["mean_p"][0])), 1e-30)
        g0 = max(abs(float(series["mean_gamma"][0])), 1e-30)
        ke0 = max(abs(float(series["mean_kinetic_proxy"][0])), 1e-30)
        return {
            "plot_type": "conservation",
            "title": f"Beam Conservation ({context.case_metadata.get('name', '')})",
            "xlabel": "Longitudinal Position z (m)",
            "ylabel": "Relative Change from Entrance",
            "lattice_elements": lattice_elements_payload(context.lattice),
            "curves": [
                {
                    "x": series["z"],
                    "y": np.abs(series["mean_p"] - series["mean_p"][0]) / p0 + 1e-18,
                    "label": r"⟨|p|⟩ drift",
                    "color": "blue",
                },
                {
                    "x": series["z"],
                    "y": np.abs(series["mean_gamma"] - series["mean_gamma"][0]) / g0 + 1e-18,
                    "label": r"⟨γ⟩ drift",
                    "color": "red",
                    "linestyle": "--",
                },
                {
                    "x": series["z"],
                    "y": np.abs(series["mean_kinetic_proxy"] - series["mean_kinetic_proxy"][0]) / ke0
                    + 1e-18,
                    "label": r"⟨T⟩ proxy drift",
                    "color": "green",
                    "linestyle": ":",
                },
            ],
            "log_y": True,
        }
    return _single_particle_conservation_plot(context, particle_index=0)


def _single_particle_conservation_plot(context: ValidationContext, particle_index: int = 0) -> dict:
    diag = context.diagnostics.to_dict()
    t = diag["time"]
    i = particle_index
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
            {
                "x": t * 1e9,
                "y": g_rel_drift + 1e-18,
                "label": "Energy Drift (Gamma)",
                "color": "red",
                "linestyle": "--",
            },
        ],
        "log_y": True,
    }
