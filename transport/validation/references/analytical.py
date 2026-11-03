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
M_P_MEV = 938.2720813


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
        R0 = context.R_init[0]
        V0 = context.V_init[0]

        x_expected = R0[0] + V0[0] * diag["time"]
        y_expected = R0[1] + V0[1] * diag["time"]
        z_expected = R0[2] + V0[2] * diag["time"]

        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            pointwise_trajectory={"x": x_expected, "y": y_expected, "z": z_expected, "t": diag["time"]},
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
        L = self.dipole_length
        # Signed cyclotron radius used by circle-fit metrics: R = Bρ / B_y.
        R_analytical = self.B_rho / By
        # Sector dipole: Δθ = q B L / Bρ, θ_exit = θ_entry − Δθ.
        delta_theta = self.charge * By * L / self.B_rho
        theta_exit = self.theta_entry - delta_theta
        bend_angle = theta_exit - self.theta_entry


        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            summary_observables={
                "cyclotron_radius": R_analytical,
                "bend_angle": bend_angle,
            },
            metadata={
                "z_start": self.z_start,
                "dipole_length": L,
                "By": By,
            },
        )

    def position_at_time(self, t, R_init, V_init, charges, mass_kg=None):
        """
        Circular arc in a uniform vertical dipole field.

        Arc length s = v_xz t, tangent angle θ(s) = θ_entry − s / R with
        signed radius R = Bρ / (q B_y). Motion in y is uniform.
        """
        t_arr = np.atleast_1d(np.asarray(t, dtype=np.float64))
        x0, y0, z0 = np.asarray(R_init[0], dtype=np.float64)
        vx0, vy0, vz0 = np.asarray(V_init[0], dtype=np.float64)
        q = float(charges[0])
        By = float(self.dipole_by)
        v_xz = float(np.hypot(vx0, vz0))

        if abs(q * By) < 1e-30 or v_xz < 1e-30 or abs(self.B_rho) < 1e-30:
            return np.column_stack([
                x0 + vx0 * t_arr,
                y0 + vy0 * t_arr,
                z0 + vz0 * t_arr,
            ])

        # R = Bρ / (q B): matches Δθ = q B L / Bρ = L / R.
        R = self.B_rho / (q * By)
        theta0 = float(np.arctan2(vx0, vz0))
        s = v_xz * t_arr
        theta = theta0 - s / R

        # Circular arc in the x–z plane (uniform B_y).
        x = x0 - R * (np.cos(theta0) - np.cos(theta))
        z = z0 + R * (np.sin(theta0) - np.sin(theta))
        y = y0 + vy0 * t_arr
        return np.column_stack([x, y, z])

class QuadrupoleAnalyticalReference(ReferenceSolution):
    def __init__(
        self,
        z_start: float,
        quadrupole_length: float,
        gradient: float,
        B_rho: float,
        charge: int,
        sync_dt: float | None = None,
    ):
        self.z_start = z_start
        self.quadrupole_length = quadrupole_length
        self.gradient = gradient
        self.B_rho = B_rho
        self.charge = charge
        # Match Boris track_particles initial half-step V(t=-dt/2) when set.
        self.sync_dt = sync_dt

    @property
    def name(self) -> str:
        return "quadrupole_analytical"

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
        m_kg = float(context.mass[0]) if context.mass is not None else M_P_KG
        pos = self.position_at_time(
            t, context.R_init, context.V_init, context.charges, mass_kg=m_kg
        )
        k = (self.charge * self.gradient) / self.B_rho

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
                "focusing_strength": k,
                "quadrupole_length": self.quadrupole_length,
            },
            metadata={
                "z_start": self.z_start,
                "gradient": self.gradient,
            },
        )

    def position_at_time(
        self,
        t,
        R_init,
        V_init,
        charges,
        mass_kg=None,
    ):
        """
        Paraxial trajectory for the Janus quadrupole field B = (G y, G x, 0)
        applied only while the particle is inside [z_start, z_start + L].

        Lorentz force F = q_C (v × B) with q_C = q e yields

            α = q G / Bρ
            d²x/ds² = -α x
            d²y/ds² = +α y

        with s the longitudinal coordinate inside the magnet and
        Bρ = γ m v_z / e (set by the validation case to match Boris).

        Lab time uses |v| conservation:
            v_z(s) = |v| / sqrt(1 + x'^2 + y'^2),
            t = t_enter + ∫ ds / v_z(s).

        When ``sync_dt`` is set, both ``|v|`` and the focusing strength
        ``α = qG/Bρ`` are taken after the same Boris half-step ``V(t=-dt/2)``
        used by ``track_particles``. Transverse initial conditions
        ``(x, y, v_x, v_y)`` remain the physical IC so the half-step does not
        seed spurious amplitude; only the longitudinal invariants that enter
        ``κ`` are synchronized.
        """
        t_arr = np.atleast_1d(np.asarray(t, dtype=np.float64))
        R0 = np.asarray(R_init, dtype=np.float64)
        V_ic = np.asarray(V_init, dtype=np.float64)
        q_arr = np.asarray(charges)

        x0, y0, z0 = R0[0]
        vx0, vy0, vz_ic = V_ic[0]
        v_mag = float(np.linalg.norm(V_ic[0]))
        q = float(q_arr[0])
        G = float(self.gradient)
        B_rho_eff = float(self.B_rho)

        m_kg = float(mass_kg) if mass_kg is not None else M_P_KG
        if self.sync_dt is not None and abs(self.sync_dt) > 0.0:
            from transport.lattice.lattice import Quadrupole, SimpleLattice
            from transport.physics.boris_solver import boris_velocity_push

            lat = SimpleLattice(
                [Quadrupole(self.quadrupole_length, self.gradient)],
                z_start=self.z_start,
            )
            gamma = np.array([
                1.0 / np.sqrt(max(1.0 - (v_mag / C_LIGHT) ** 2, 1e-30))
            ])
            alive = np.ones(1, dtype=bool)
            mass = np.array([m_kg], dtype=np.float64)
            V_hs, g_hs = boris_velocity_push(
                np.array(R0, copy=True),
                np.array(V_ic, copy=True),
                gamma,
                -0.5 * float(self.sync_dt),
                alive,
                lat,
                q_arr,
                mass,
            )
            # Longitudinal sync: |v| for timing and Bρ for κ must match Boris
            # after the leapfrog half-step (transverse IC unchanged).
            v_mag = float(np.linalg.norm(V_hs[0]))
            vz_hs = float(V_hs[0, 2])
            gamma_hs = float(g_hs[0])
            if abs(vz_hs) > 1e-30:
                B_rho_eff = gamma_hs * m_kg * abs(vz_hs) / E_CHARGE

        z_entry = float(self.z_start)
        L = float(self.quadrupole_length)
        z_exit = z_entry + L

        # Default free-drift (also used upstream / zero-field limits).
        out = np.column_stack([
            x0 + vx0 * t_arr,
            y0 + vy0 * t_arr,
            z0 + vz_ic * t_arr,
        ])

        if abs(vz_ic) < 1e-30 or v_mag < 1e-30:
            return out

        alpha = (q * G) / B_rho_eff
        if abs(alpha) < 1e-12:
            return out

        if (vz_ic > 0 and z0 >= z_exit) or (vz_ic < 0 and z0 <= z_entry):
            return out

        omega = np.sqrt(abs(alpha))

        if z_entry <= z0 <= z_exit:
            t_enter = 0.0
            s_max = (z_exit - z0) if vz_ic > 0 else (z0 - z_entry)
            x_e, y_e, z_e = x0, y0, z0
            vx_e, vy_e = vx0, vy0
        else:
            t_enter = (z_entry - z0) / vz_ic if vz_ic > 0 else (z_exit - z0) / vz_ic
            if t_enter < 0:
                return out
            s_max = L
            x_e = x0 + vx0 * t_enter
            y_e = y0 + vy0 * t_enter
            z_e = z0 + vz_ic * t_enter
            vx_e, vy_e = vx0, vy0

        if s_max <= 0:
            return out

        xp_e = vx_e / vz_ic
        yp_e = vy_e / vz_ic

        def _state_at_s(s):
            s = np.asarray(s, dtype=np.float64)
            if alpha > 0:
                x = x_e * np.cos(omega * s) + (xp_e / omega) * np.sin(omega * s)
                y = y_e * np.cosh(omega * s) + (yp_e / omega) * np.sinh(omega * s)
                xp = -x_e * omega * np.sin(omega * s) + xp_e * np.cos(omega * s)
                yp = y_e * omega * np.sinh(omega * s) + yp_e * np.cosh(omega * s)
            else:
                x = x_e * np.cosh(omega * s) + (xp_e / omega) * np.sinh(omega * s)
                y = y_e * np.cos(omega * s) + (yp_e / omega) * np.sin(omega * s)
                xp = x_e * omega * np.sinh(omega * s) + xp_e * np.cosh(omega * s)
                yp = -y_e * omega * np.sin(omega * s) + yp_e * np.cos(omega * s)
            return x, y, xp, yp

        n_tab = max(128, int(np.ceil(abs(s_max) / 0.02)) + 1)
        s_tab = np.linspace(0.0, s_max, n_tab)
        _, _, xp_tab, yp_tab = _state_at_s(s_tab)
        vz_tab = v_mag / np.sqrt(1.0 + xp_tab**2 + yp_tab**2)
        inv_vz = 1.0 / np.maximum(vz_tab, 1e-30)
        tau_tab = np.concatenate(
            [[0.0], np.cumsum(0.5 * (inv_vz[1:] + inv_vz[:-1]) * np.diff(s_tab))]
        )
        t_leave = t_enter + float(tau_tab[-1])

        x_f, y_f, xp_f, yp_f = _state_at_s(s_max)
        vz_f = float(v_mag / np.sqrt(1.0 + xp_f**2 + yp_f**2))
        vx_f = float(xp_f * vz_f)
        vy_f = float(yp_f * vz_f)
        z_f = z_e + np.sign(vz_ic) * s_max

        # Upstream: free drift at IC velocity (already in out).
        inside = (t_arr > t_enter) & (t_arr <= t_leave)
        after = t_arr > t_leave

        if np.any(inside):
            tau = t_arr[inside] - t_enter
            s = np.interp(tau, tau_tab, s_tab)
            x, y, xp, yp = _state_at_s(s)
            out[inside, 0] = x
            out[inside, 1] = y
            out[inside, 2] = z_e + np.sign(vz_ic) * s

        if np.any(after):
            dt_after = t_arr[after] - t_leave
            out[after, 0] = x_f + vx_f * dt_after
            out[after, 1] = y_f + vy_f * dt_after
            out[after, 2] = z_f + np.sign(vz_ic) * vz_f * dt_after

        return out

class HornAnalyticalReference(ReferenceSolution):
    def __init__(
        self,
        z_start: float,
        horn_length: float,
        current: float,
    ):
        self.z_start = z_start
        self.horn_length = horn_length
        self.current = current

    @property
    def name(self) -> str:
        return "horn_analytical"

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.ANALYTICAL

    @property
    def capabilities(self) -> set:
        return {
            ReferenceCapability.SUMMARY_OBSERVABLES,
        }

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        MU0 = 4.0 * np.pi * 1e-7

        R0 = context.R_init[0]
        V0 = context.V_init[0]

        q = float(context.charges[0])  # elementary-charge units
        m = float(context.mass[0])

        x0, y0, _ = R0
        r0 = np.hypot(x0, y0)

        if r0 < 1e-12:
            raise ValueError("Analytical horn reference undefined on axis.")

        # Impulse for paraxial transit at nearly constant r (SI):
        # (v × B)_ρ = -v_z B_φ  ⇒  Δp_ρ = -q_C B_φ L
        # with B_φ = μ₀ I / (2 π r) and q_C = q * e.
        # Diagnostics store momentum as γ m_MeV (v/c) [MeV/c], so convert:
        # Δp[MeV/c] = Δp_SI * c / (e * 1e6).
        delta_pr = (
            -q
            * MU0
            * self.current
            * self.horn_length
            * C_LIGHT
            / (2.0 * np.pi * r0 * 1.0e6)
        )

        v = float(np.linalg.norm(V0))
        gamma = float(1.0 / np.sqrt(max(1.0 - (v / C_LIGHT) ** 2, 1e-30)))
        mass_mev = m * (M_P_MEV / M_P_KG)
        p = gamma * mass_mev * (v / C_LIGHT)  # MeV/c
        theta = delta_pr / p if p > 0 else 0.0

        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            pointwise_trajectory=None,
            summary_observables={
                "expected_radial_kick": float(delta_pr),
                "expected_exit_angle": float(theta),
                "initial_radius": float(r0),
                "horn_length": self.horn_length,
                "current": self.current,
                "momentum_unit": "MeV/c",
            },
            metadata={
                "z_start": self.z_start,
            },
        )


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
