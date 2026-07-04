"""Analytical reference solutions."""

import numpy as np

from transport.validation.case import ValidationContext
from transport.validation.references.base import (
    ReferenceCapability,
    ReferenceResult,
    ReferenceSolution,
    ReferenceType,
)

C_LIGHT = 299792458.0
E_CHARGE = 1.602176634e-19
M_P_KG = 1.67262192369e-27


class DriftAnalyticalReference(ReferenceSolution):
    @property
    def name(self) -> str:
        return "drift_analytical"

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.ANALYTICAL

    @property
    def capabilities(self) -> set:
        return {ReferenceCapability.POINTWISE_TRAJECTORY, ReferenceCapability.SUMMARY_OBSERVABLES}

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        diag = context.diagnostics.to_dict()
        t = diag["time"]
        R0 = diag["position"][0, 0]
        if len(t) > 1 and t[1] > 0:
            V0 = (diag["position"][1, 0] - R0) / t[1]
        else:
            V0 = context.V_init[0]

        x_expected = R0[0] + V0[0] * t
        y_expected = R0[1] + V0[1] * t
        z_expected = R0[2] + V0[2] * t

        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            pointwise_trajectory={"x": x_expected, "y": y_expected, "z": z_expected, "t": t},
            summary_observables={"type": "drift"},
            metadata={"V0": V0, "R0": R0},
        )

    @staticmethod
    def position_at_time(t, R_init, V_init):
        return R_init + V_init * t


class DipoleAnalyticalReference(ReferenceSolution):
    def __init__(self, z_start: float, dipole_length: float, dipole_by: float, B_rho: float,
                 theta_entry: float, charge: int, gamma: float):
        self.z_start = z_start
        self.dipole_length = dipole_length
        self.dipole_by = dipole_by
        self.B_rho = B_rho
        self.theta_entry = theta_entry
        self.charge = charge
        self.gamma = gamma

    @property
    def name(self) -> str:
        return "dipole_analytical"

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.ANALYTICAL

    @property
    def capabilities(self) -> set:
        return {ReferenceCapability.POINTWISE_TRAJECTORY, ReferenceCapability.SUMMARY_OBSERVABLES}

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        By = self.dipole_by
        R_analytical = self.B_rho / By
        L = self.dipole_length
        arg = np.sin(self.theta_entry) - (self.charge * By * L / self.B_rho)
        theta_exit = np.arcsin(arg)
        theta_analytical = theta_exit - self.theta_entry

        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            summary_observables={
                "cyclotron_radius": R_analytical,
                "bend_angle": theta_analytical,
            },
            metadata={
                "z_start": self.z_start,
                "dipole_length": L,
                "By": By,
            },
        )

    def position_at_time(self, t, R_init, V_init, charges, mass_kg=None):
        m = mass_kg if mass_kg is not None else M_P_KG
        omega_c = (charges[0] * E_CHARGE * self.dipole_by) / (self.gamma * m)
        x0, y0, z0 = R_init[0]
        vx0, vy0, vz0 = V_init[0]
        if abs(omega_c) < 1e-12:
            return R_init + V_init * t
        x_t = x0 + (vx0 / omega_c) * np.sin(omega_c * t) - (vz0 / omega_c) * (1.0 - np.cos(omega_c * t))
        y_t = y0 + vy0 * t
        z_t = z0 + (vz0 / omega_c) * np.sin(omega_c * t) + (vx0 / omega_c) * (1.0 - np.cos(omega_c * t))
        return np.array([[x_t, y_t, z_t]])


class StubAnalyticalReference(ReferenceSolution):
    """Placeholder for undeclared analytical references."""

    def __init__(self, name: str = "stub_analytical"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.ANALYTICAL

    @property
    def capabilities(self) -> set:
        return set()

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=set(),
            metadata={"stub": True},
        )
