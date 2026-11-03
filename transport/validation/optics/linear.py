"""Built-in thick-lens linear optics for Drift and Quadrupole elements."""

from __future__ import annotations

import numpy as np

from transport.lattice.lattice import Drift, Quadrupole
from transport.validation.optics.base import (
    OpticsBackend,
    OpticsEnvelope,
    OpticsTransferMatrix,
    OpticsTwiss,
)
from transport.validation.stats.beam import twiss_from_covariance


def _drift_matrix(L: float) -> np.ndarray:
    m = np.eye(4)
    m[0, 1] = L
    m[2, 3] = L
    return m


def _quad_matrix(L: float, k1: float) -> np.ndarray:
    """
    Thick quadrupole transfer matrix.

    k1 = q G / Bρ  (signed). Focusing in x when k1 > 0.
    """
    m = np.eye(4)
    if abs(k1) < 1e-30:
        return _drift_matrix(L)
    if k1 > 0:
        omega = np.sqrt(k1)
        c = np.cos(omega * L)
        s = np.sin(omega * L)
        ch = np.cosh(omega * L)
        sh = np.sinh(omega * L)
        m[0, 0] = c
        m[0, 1] = s / omega
        m[1, 0] = -omega * s
        m[1, 1] = c
        m[2, 2] = ch
        m[2, 3] = sh / omega
        m[3, 2] = omega * sh
        m[3, 3] = ch
    else:
        omega = np.sqrt(-k1)
        c = np.cos(omega * L)
        s = np.sin(omega * L)
        ch = np.cosh(omega * L)
        sh = np.sinh(omega * L)
        m[0, 0] = ch
        m[0, 1] = sh / omega
        m[1, 0] = omega * sh
        m[1, 1] = ch
        m[2, 2] = c
        m[2, 3] = s / omega
        m[3, 2] = -omega * s
        m[3, 3] = c
    return m


def propagate_sigma(sigma0: np.ndarray, R: np.ndarray) -> np.ndarray:
    """σ_out = R σ_in Rᵀ for 4×4 covariance."""
    return R @ sigma0 @ R.T


class LinearOpticsBackend(OpticsBackend):
    @property
    def name(self) -> str:
        return "linear_optics"

    def available(self) -> bool:
        return True

    def transfer_matrix(self, lattice, particle_state: dict) -> OpticsTransferMatrix:
        b_rho = float(particle_state.get("B_rho", 1.0))
        q = float(particle_state.get("charge", -1.0))
        R = np.eye(4)
        for el in lattice.elements:
            if isinstance(el, Drift):
                M = _drift_matrix(el.L)
            elif isinstance(el, Quadrupole):
                k1 = q * float(el.k) / b_rho if abs(b_rho) > 1e-30 else 0.0
                M = _quad_matrix(el.L, k1)
            else:
                M = _drift_matrix(el.L)
            R = M @ R
        return OpticsTransferMatrix(
            matrix=R,
            metadata={"backend": self.name, "B_rho": b_rho, "charge": q},
        )

    def envelope(self, lattice, particle_state: dict) -> OpticsEnvelope:
        """Propagate entrance RMS envelope with linear transfer of 2×2 blocks."""
        sigx0 = float(particle_state.get("sigma_x", 0.0))
        sigy0 = float(particle_state.get("sigma_y", 0.0))
        sigxp0 = float(particle_state.get("sigma_xp", 0.0))
        sigyp0 = float(particle_state.get("sigma_yp", 0.0))
        # Uncoupled diagonal covariance at entrance.
        sigma = np.diag([sigx0**2, sigxp0**2, sigy0**2, sigyp0**2])

        b_rho = float(particle_state.get("B_rho", 1.0))
        q = float(particle_state.get("charge", -1.0))

        z_vals = [float(lattice.z_start)]
        sx = [sigx0]
        sy = [sigy0]
        Rcum = np.eye(4)
        for el in lattice.elements:
            if isinstance(el, Drift):
                M = _drift_matrix(el.L)
            elif isinstance(el, Quadrupole):
                M = _quad_matrix(el.L, q * float(el.k) / b_rho if abs(b_rho) > 1e-30 else 0.0)
            else:
                M = _drift_matrix(el.L)
            Rcum = M @ Rcum
            sigma_el = propagate_sigma(sigma, Rcum)
            z_vals.append(float(el.z_end))
            sx.append(float(np.sqrt(max(sigma_el[0, 0], 0.0))))
            sy.append(float(np.sqrt(max(sigma_el[2, 2], 0.0))))

        return OpticsEnvelope(
            z=np.asarray(z_vals, dtype=np.float64),
            sigma_x=np.asarray(sx, dtype=np.float64),
            sigma_y=np.asarray(sy, dtype=np.float64),
            metadata={"backend": self.name},
        )

    def twiss(self, lattice, particle_state: dict) -> OpticsTwiss:
        """Propagate entrance Twiss / covariance with thick-lens transfer matrices."""
        b_rho = float(particle_state.get("B_rho", 1.0))
        q = float(particle_state.get("charge", -1.0))

        # Prefer full entrance covariance blocks when provided.
        if "Sigma_x" in particle_state and "Sigma_y" in particle_state:
            sig_x = np.asarray(particle_state["Sigma_x"], dtype=np.float64)
            sig_y = np.asarray(particle_state["Sigma_y"], dtype=np.float64)
        else:
            bx0 = float(particle_state.get("beta_x", 1.0))
            ax0 = float(particle_state.get("alpha_x", 0.0))
            gx0 = float(particle_state.get("gamma_x", (1.0 + ax0**2) / max(bx0, 1e-30)))
            by0 = float(particle_state.get("beta_y", 1.0))
            ay0 = float(particle_state.get("alpha_y", 0.0))
            gy0 = float(particle_state.get("gamma_y", (1.0 + ay0**2) / max(by0, 1e-30)))
            ex0 = float(particle_state.get("emittance_x", 1.0))
            ey0 = float(particle_state.get("emittance_y", 1.0))
            sig_x = ex0 * np.array([[bx0, -ax0], [-ax0, gx0]], dtype=np.float64)
            sig_y = ey0 * np.array([[by0, -ay0], [-ay0, gy0]], dtype=np.float64)

        sigma = np.zeros((4, 4), dtype=np.float64)
        sigma[0:2, 0:2] = sig_x
        sigma[2:4, 2:4] = sig_y

        tw0x = twiss_from_covariance(sig_x)
        tw0y = twiss_from_covariance(sig_y)
        z_vals = [float(lattice.z_start)]
        bx, ax, gx = [tw0x["beta"]], [tw0x["alpha"]], [tw0x["gamma"]]
        by, ay, gy = [tw0y["beta"]], [tw0y["alpha"]], [tw0y["gamma"]]

        Rcum = np.eye(4)
        for el in lattice.elements:
            if isinstance(el, Drift):
                M = _drift_matrix(el.L)
            elif isinstance(el, Quadrupole):
                k1 = q * float(el.k) / b_rho if abs(b_rho) > 1e-30 else 0.0
                M = _quad_matrix(el.L, k1)
            else:
                M = _drift_matrix(el.L)
            Rcum = M @ Rcum
            sigma_el = propagate_sigma(sigma, Rcum)
            twx = twiss_from_covariance(sigma_el[0:2, 0:2])
            twy = twiss_from_covariance(sigma_el[2:4, 2:4])
            z_vals.append(float(el.z_end))
            bx.append(twx["beta"])
            ax.append(twx["alpha"])
            gx.append(twx["gamma"])
            by.append(twy["beta"])
            ay.append(twy["alpha"])
            gy.append(twy["gamma"])

        return OpticsTwiss(
            z=np.asarray(z_vals, dtype=np.float64),
            beta_x=np.asarray(bx, dtype=np.float64),
            alpha_x=np.asarray(ax, dtype=np.float64),
            gamma_x=np.asarray(gx, dtype=np.float64),
            beta_y=np.asarray(by, dtype=np.float64),
            alpha_y=np.asarray(ay, dtype=np.float64),
            gamma_y=np.asarray(gy, dtype=np.float64),
            metadata={"backend": self.name},
        )
