"""Convergence strategy interface."""

from abc import ABC, abstractmethod


class ConvergenceStrategy(ABC):
    @abstractmethod
    def run(self, case, context, solver):
        """
        Returns (converged, errors, dts, plot_payload) or None if not applicable.
        """
        pass
