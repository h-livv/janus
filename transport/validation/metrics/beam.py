"""Beam-level statistical metrics (Level 3 stubs)."""

import numpy as np

from transport.validation.case import ValidationContext
from transport.validation.metrics.base import Metric, MetricResult, MetricScope, ReferenceRequirement


class CentroidMetric(Metric):
    @property
    def name(self) -> str:
        return "centroid_x"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        pos = context.diagnostics.position[-1]
        alive = context.diagnostics.alive[-1]
        x_alive = pos[alive, 0]
        value = float(np.mean(x_alive)) if len(x_alive) > 0 else 0.0
        return MetricResult(value=value)


class RmsSizeMetric(Metric):
    @property
    def name(self) -> str:
        return "rms_x"

    @property
    def unit(self) -> str:
        return "m"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        pos = context.diagnostics.position[-1]
        alive = context.diagnostics.alive[-1]
        x_alive = pos[alive, 0]
        value = float(np.std(x_alive)) if len(x_alive) > 1 else 0.0
        return MetricResult(value=value)


class TransmissionMetric(Metric):
    @property
    def name(self) -> str:
        return "transmission"

    @property
    def unit(self) -> str:
        return "fraction"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    def compute(self, context: ValidationContext) -> MetricResult:
        n_init = context.diagnostics.n_particles
        n_surv = int(np.sum(context.diagnostics.alive[-1]))
        value = n_surv / n_init if n_init > 0 else 0.0
        return MetricResult(value=value)


class EmittanceMetric(Metric):
    @property
    def name(self) -> str:
        return "emittance_x"

    @property
    def unit(self) -> str:
        return "m.rad"

    @property
    def scope(self) -> MetricScope:
        return MetricScope.BEAM

    @property
    def reference_requirement(self) -> ReferenceRequirement:
        return ReferenceRequirement.MOMENT_PROPAGATION

    def compute(self, context: ValidationContext) -> MetricResult:
        pos = context.diagnostics.position[-1, :, 0]
        mom = context.diagnostics.momentum[-1]
        px = mom[:, 0] / mom[:, 2]  # x' approximation
        xx = np.mean(pos ** 2)
        xpxp = np.mean(px ** 2)
        xxp = np.mean(pos * px)
        value = float(np.sqrt(max(xx * xpxp - xxp ** 2, 0.0)))
        return MetricResult(value=value)
