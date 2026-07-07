"""Piecewise analytical trajectories through composite lattices."""

from __future__ import annotations

import numpy as np

from transport.lattice.lattice import Drift, Quadrupole
from transport.validation.case import ValidationContext
from transport.validation.references.analytical import (
    C_LIGHT,
    E_CHARGE,
    M_P_KG,
    DriftAnalyticalReference,
)
from transport.validation.references.base import (
    ReferenceCapability,
    ReferenceResult,
    ReferenceSolution,
    ReferenceType,
)


def magnetic_rigidity(V_init, charge_magnitude: float, use_mock_data: bool, mass_kg: float) -> float:
    v_mag = float(np.linalg.norm(V_init[0]))
    gamma = float(1.0 / np.sqrt(1.0 - (v_mag / C_LIGHT) ** 2))
    v_z = abs(float(V_init[0, 2]))
    if v_z < 1e-12:
        v_z = v_mag
    if use_mock_data:
        return (1.0 * mass_kg * v_z) / E_CHARGE
    return gamma * mass_kg * v_z / E_CHARGE


def _quad_state_local(
    x0,
    y0,
    z0,
    vx0,
    vy0,
    vz0,
    tau,
    gradient,
    charge,
    b_rho,
):
    """Paraxial quadrupole state after local time tau from element entry."""
    if abs(vz0) < 1e-30 or tau <= 0:
        return np.array([x0, y0, z0]), np.array([vx0, vy0, vz0])

    s = vz0 * tau
    k = (charge * gradient) / b_rho
    if abs(k) < 1e-12:
        return (
            np.array([x0 + vx0 * tau, y0 + vy0 * tau, z0 + vz0 * tau]),
            np.array([vx0, vy0, vz0]),
        )

    rootk = np.sqrt(abs(k))
    if k > 0:
        x = x0 * np.cos(rootk * s) + (vx0 / (vz0 * rootk)) * np.sin(rootk * s)
        y = y0 * np.cosh(rootk * s) + (vy0 / (vz0 * rootk)) * np.sinh(rootk * s)
        dxds = -x0 * rootk * np.sin(rootk * s) + (vx0 / vz0) * np.cos(rootk * s)
        dyds = y0 * rootk * np.sinh(rootk * s) + (vy0 / vz0) * np.cosh(rootk * s)
    else:
        x = x0 * np.cosh(rootk * s) + (vx0 / (vz0 * rootk)) * np.sinh(rootk * s)
        y = y0 * np.cos(rootk * s) + (vy0 / (vz0 * rootk)) * np.sin(rootk * s)
        dxds = x0 * rootk * np.sinh(rootk * s) + (vx0 / vz0) * np.cosh(rootk * s)
        dyds = -y0 * rootk * np.sin(rootk * s) + (vy0 / vz0) * np.cos(rootk * s)

    z = z0 + vz0 * tau
    vx = dxds * vz0
    vy = dyds * vz0
    return np.array([x, y, z]), np.array([vx, vy, vz0])


def propagate_lattice_trajectory(
    lattice,
    R_init,
    V_init,
    charges,
    t_array,
    use_mock_data: bool = True,
    mass_kg: float | None = None,
) -> np.ndarray:
    """Sample analytical positions at global times t_array (single particle)."""
    t_array = np.asarray(t_array, dtype=np.float64)
    mass = mass_kg if mass_kg is not None else M_P_KG
    charge = int(charges[0])
    b_rho = magnetic_rigidity(
        V_init, abs(charge) * E_CHARGE, use_mock_data, mass
    )

    positions = np.zeros((len(t_array), 3), dtype=np.float64)
    r = R_init[0].astype(np.float64).copy()
    v = V_init[0].astype(np.float64).copy()
    t_cursor = 0.0
    el_idx = 0
    elements = lattice.elements

    for i, t_target in enumerate(t_array):
        while t_cursor + 1e-15 < t_target:
            if el_idx >= len(elements):
                dt = t_target - t_cursor
                r = r + v * dt
                t_cursor = t_target
                break

            el = elements[el_idx]
            vz = v[2]
            if abs(vz) < 1e-30:
                dt = t_target - t_cursor
            else:
                dt_exit = (el.z_end - r[2]) / vz
                if dt_exit < 0:
                    dt_exit = 0.0
                dt = min(t_target - t_cursor, dt_exit)

            if dt <= 1e-15:
                if r[2] >= el.z_end - 1e-9:
                    el_idx += 1
                else:
                    t_cursor = t_target
                continue

            if isinstance(el, Drift):
                r = r + v * dt
            elif isinstance(el, Quadrupole):
                r, v = _quad_state_local(
                    r[0], r[1], r[2], v[0], v[1], v[2],
                    dt, el.k, charge, b_rho,
                )
            else:
                r = r + v * dt

            t_cursor += dt
            if isinstance(el, (Drift, Quadrupole)) and r[2] >= el.z_end - 1e-9:
                el_idx += 1

        positions[i] = r
    return positions


class LatticeAnalyticalReference(ReferenceSolution):
    """Analytical trajectory stitched across Drift and Quadrupole elements."""

    def __init__(self, use_mock_data: bool = True):
        self.use_mock_data = use_mock_data

    @property
    def name(self) -> str:
        return "lattice_analytical"

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.ANALYTICAL

    @property
    def capabilities(self) -> set:
        return {
            ReferenceCapability.POINTWISE_TRAJECTORY,
            ReferenceCapability.SUMMARY_OBSERVABLES,
        }

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        diag = context.diagnostics.to_dict()
        t = diag["time"]
        mass_kg = float(context.mass[0]) if context.mass is not None else M_P_KG
        pos = propagate_lattice_trajectory(
            context.lattice,
            context.R_init,
            context.V_init,
            context.charges,
            t,
            use_mock_data=self.use_mock_data,
            mass_kg=mass_kg,
        )
        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            pointwise_trajectory={
                "x": pos[:, 0],
                "y": pos[:, 1],
                "z": pos[:, 2],
                "t": t,
            },
            summary_observables={
                "n_elements": len(context.lattice.elements),
                "total_length": context.lattice.total_length,
            },
            metadata={"use_mock_data": self.use_mock_data},
        )

    def position_at_time(self, t, R_init, V_init, charges, mass_kg=None):
        """Exit position for convergence studies (single scalar t)."""
        t_arr = np.atleast_1d(np.asarray(t, dtype=np.float64))
        lattice = getattr(self, "_lattice", None)
        if lattice is None:
            raise RuntimeError("LatticeAnalyticalReference requires _lattice for exit sampling")
        pos = propagate_lattice_trajectory(
            lattice,
            R_init,
            V_init,
            charges,
            t_arr,
            use_mock_data=self.use_mock_data,
            mass_kg=mass_kg,
        )
        return pos


def make_analytical_position_fn(lattice, use_mock_data, mass_kg):
    ref = LatticeAnalyticalReference(use_mock_data=use_mock_data)
    ref._lattice = lattice

    def fn(t, R_i, V_i, ch):
        return ref.position_at_time(t, R_i, V_i, ch, mass_kg=mass_kg)

    return fn


def drift_then_free_reference_position(t, R_init, V_init, lattice):
    """Legacy helper: drift analytical only (unused in composite path)."""
    return DriftAnalyticalReference.position_at_time(t, R_init, V_init)
