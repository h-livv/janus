"""Numerical first-order transfer matrix estimation from particle tracking."""

from __future__ import annotations

import numpy as np

from transport.physics.boris_solver import C_LIGHT, track_particles
from transport.validation.references.numerical import find_exit_states_with_momentum
from transport.validation.stats.beam import slopes_from_momentum


def phase_space_4(pos: np.ndarray, mom: np.ndarray) -> np.ndarray:
    """Build (N, 4) array of (x, x', y, y')."""
    slopes = slopes_from_momentum(mom)
    return np.column_stack((pos[:, 0], slopes[:, 0], pos[:, 1], slopes[:, 1]))


def estimate_transfer_matrix_from_ensemble(
    pos_in: np.ndarray,
    mom_in: np.ndarray,
    pos_out: np.ndarray,
    mom_out: np.ndarray,
) -> np.ndarray:
    """
    Least-squares estimate of R from entrance/exit phase-space samples.

    Solves X_f ≈ R X_i (affine: demean both sides first so the orbit offset
    does not bias the linear map).
    """
    xi = phase_space_4(pos_in, mom_in)
    xf = phase_space_4(pos_out, mom_out)
    if len(xi) < 5:
        return np.eye(4)
    xi_c = xi - np.mean(xi, axis=0)
    xf_c = xf - np.mean(xf, axis=0)
    # R such that xf_c.T ≈ R @ xi_c.T  ⇒  R = xf_c.T @ pinv(xi_c.T)
    R, *_ = np.linalg.lstsq(xi_c, xf_c, rcond=None)
    return R.T


def estimate_transfer_matrix(
    lattice,
    R0: np.ndarray,
    V0: np.ndarray,
    gamma0: np.ndarray,
    charges: np.ndarray,
    mass: np.ndarray,
    dt: float,
    max_steps: int,
    delta_pos: float = 1e-6,
    delta_angle: float = 1e-6,
) -> np.ndarray:
    """
    Estimate the 4×4 transverse transfer matrix R = ∂X_f / ∂X_i by
    finite-difference tracking of a reference particle plus four probes.

    State vector: X = (x, x', y, y') with x' = v_x / v_z.
    """
    r_ref = np.asarray(R0[0], dtype=np.float64).copy()
    v_ref = np.asarray(V0[0], dtype=np.float64).copy()
    vz = float(v_ref[2])
    if abs(vz) < 1e-30:
        return np.eye(4)

    def _track(r, v):
        speed2 = float(np.dot(v, v))
        beta2 = speed2 / C_LIGHT**2
        g = np.array([1.0 / np.sqrt(max(1.0 - beta2, 1e-30))])
        _, _, _, diag = track_particles(
            r.reshape(1, 3),
            v.reshape(1, 3),
            g,
            charges[:1],
            lattice,
            dt,
            max_steps,
            mass=mass[:1],
        )
        z_exit = lattice.z_start + lattice.total_length
        rf, pf = find_exit_states_with_momentum(diag, z_exit)
        pz = max(abs(float(pf[0, 2])), 1e-30)
        return np.array(
            [
                float(rf[0, 0]),
                float(pf[0, 0] / pz),
                float(rf[0, 1]),
                float(pf[0, 1] / pz),
            ],
            dtype=np.float64,
        )

    x0 = np.array(
        [r_ref[0], v_ref[0] / vz, r_ref[1], v_ref[1] / vz],
        dtype=np.float64,
    )
    xf0 = _track(r_ref, v_ref)

    deltas = np.array([delta_pos, delta_angle, delta_pos, delta_angle], dtype=np.float64)
    R = np.zeros((4, 4), dtype=np.float64)
    for i in range(4):
        x_p = x0.copy()
        x_p[i] += deltas[i]
        r_p = r_ref.copy()
        v_p = v_ref.copy()
        r_p[0] = x_p[0]
        r_p[1] = x_p[2]
        v_p[0] = x_p[1] * vz
        v_p[1] = x_p[3] * vz
        v_xy2 = v_p[0] ** 2 + v_p[1] ** 2
        v_ref2 = float(np.dot(v_ref, v_ref))
        v_p[2] = np.sign(vz) * np.sqrt(max(v_ref2 - v_xy2, 1e-6))
        xf = _track(r_p, v_p)
        R[:, i] = (xf - xf0) / deltas[i]
    return R


def relative_matrix_error(R_num: np.ndarray, R_ref: np.ndarray) -> dict:
    diff = R_num - R_ref
    fro_ref = float(np.linalg.norm(R_ref, ord="fro"))
    fro_diff = float(np.linalg.norm(diff, ord="fro"))
    return {
        "frobenius_diff": fro_diff,
        "frobenius_relative": fro_diff / max(fro_ref, 1e-30),
        "max_abs_diff": float(np.max(np.abs(diff))),
        "diff": diff,
    }
