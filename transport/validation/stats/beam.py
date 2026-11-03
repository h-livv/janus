"""Reusable beam statistics computed from Diagnostics / ValidationContext."""

from __future__ import annotations

import numpy as np

from transport.validation.case import ValidationContext
from transport.validation.references.numerical import find_exit_states_with_momentum


def lattice_z_exit(context: ValidationContext) -> float:
    lattice = context.lattice
    return float(lattice.z_start + lattice.total_length)


def plane_covariance(pos: np.ndarray, mom: np.ndarray, axis: int) -> tuple[np.ndarray, float]:
    """
    RMS covariance Σ and geometric emittance ε = √(det Σ) in one transverse plane.

    axis:
        0 -> horizontal (x)
        1 -> vertical   (y)

    Returns
        Sigma : (2, 2) array [[<q²>, <qq'>,], [<qq'>, <q'²>]]
        emittance : √(det Σ)
    """
    if len(pos) < 2:
        return np.zeros((2, 2), dtype=np.float64), 0.0

    q = pos[:, axis].astype(np.float64)
    pz = np.maximum(np.abs(mom[:, 2]), 1e-30)
    qp = mom[:, axis] / pz

    q = q - np.mean(q)
    qp = qp - np.mean(qp)

    s11 = float(np.mean(q * q))
    s22 = float(np.mean(qp * qp))
    s12 = float(np.mean(q * qp))
    sigma = np.array([[s11, s12], [s12, s22]], dtype=np.float64)
    det = s11 * s22 - s12 * s12
    return sigma, float(np.sqrt(max(det, 0.0)))


def twiss_from_covariance(sigma: np.ndarray, emittance: float | None = None) -> dict:
    """Courant–Snyder parameters from a 2×2 RMS covariance matrix."""
    sigma = np.asarray(sigma, dtype=np.float64)
    if emittance is None:
        det = float(sigma[0, 0] * sigma[1, 1] - sigma[0, 1] * sigma[1, 0])
        emittance = float(np.sqrt(max(det, 0.0)))
    eps = max(float(emittance), 1e-30)
    return {
        "beta": float(sigma[0, 0] / eps),
        "alpha": float(-sigma[0, 1] / eps),
        "gamma": float(sigma[1, 1] / eps),
        "emittance": float(emittance),
    }


def plane_twiss(pos: np.ndarray, mom: np.ndarray, axis: int) -> dict:
    """β, α, γ and ε for one transverse plane from a particle sample."""
    sigma, eps = plane_covariance(pos, mom, axis)
    out = twiss_from_covariance(sigma, eps)
    out["Sigma"] = sigma
    return out


def plane_emittance(pos: np.ndarray, mom: np.ndarray, axis: int) -> float:
    """
    RMS geometric emittance in one transverse plane.

    axis:
        0 -> horizontal (x)
        1 -> vertical   (y)
    """
    _, eps = plane_covariance(pos, mom, axis)
    return eps


def rms_envelope(pos: np.ndarray) -> tuple[float, float]:
    if len(pos) == 0:
        return 0.0, 0.0
    return float(np.std(pos[:, 0])), float(np.std(pos[:, 1]))


def rms_size_3d(pos: np.ndarray) -> tuple[float, float, float]:
    if len(pos) == 0:
        return 0.0, 0.0, 0.0
    return (
        float(np.std(pos[:, 0])),
        float(np.std(pos[:, 1])),
        float(np.std(pos[:, 2])),
    )


def slopes_from_momentum(mom: np.ndarray) -> np.ndarray:
    pz = np.maximum(np.abs(mom[:, 2]), 1e-30)
    return np.column_stack((mom[:, 0] / pz, mom[:, 1] / pz))


def rms_divergence(mom: np.ndarray) -> tuple[float, float]:
    if len(mom) < 2:
        return 0.0, 0.0
    slopes = slopes_from_momentum(mom)
    return float(np.std(slopes[:, 0])), float(np.std(slopes[:, 1]))


def momentum_spread(mom: np.ndarray) -> dict:
    """Δp/p statistics from momentum vectors (MeV/c)."""
    if len(mom) == 0:
        return {"mean_p": 0.0, "rms_p": 0.0, "delta_p_over_p_rms": 0.0, "p_mag": np.array([])}
    p_mag = np.linalg.norm(mom, axis=1)
    mean_p = float(np.mean(p_mag))
    rms_p = float(np.std(p_mag))
    return {
        "mean_p": mean_p,
        "rms_p": rms_p,
        "delta_p_over_p_rms": float(rms_p / max(abs(mean_p), 1e-30)),
        "p_mag": p_mag,
    }


def _reached_exit(diagnostics, z_exit: float) -> np.ndarray:
    n = diagnostics.n_particles
    reached = np.zeros(n, dtype=bool)
    for step in range(diagnostics.n_steps):
        reached |= diagnostics.position[step, :, 2] >= z_exit - 1e-9
    return reached


def transmission_fraction(context: ValidationContext) -> float:
    z_exit = lattice_z_exit(context)
    return float(np.mean(_reached_exit(context.diagnostics, z_exit)))


def transmission_series(diagnostics, z_exit: float) -> np.ndarray:
    n_init = diagnostics.n_particles
    if n_init == 0:
        return np.zeros(diagnostics.n_steps)
    series = []
    for step in range(diagnostics.n_steps):
        alive = diagnostics.alive[step]
        z = diagnostics.position[step, :, 2]
        inside = z <= z_exit + 1e-9
        series.append(float(np.sum(alive & inside)) / n_init)
    return np.asarray(series, dtype=np.float64)


def exit_phase_space(context: ValidationContext) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z_exit = lattice_z_exit(context)
    diag = context.diagnostics.to_dict()
    r_exit, p_exit = find_exit_states_with_momentum(diag, z_exit)
    reached = _reached_exit(context.diagnostics, z_exit)
    return r_exit, p_exit, reached


def entrance_phase_space(context: ValidationContext) -> tuple[np.ndarray, np.ndarray]:
    diag = context.diagnostics
    alive = diag.alive[0].astype(bool)
    return diag.position[0, alive].copy(), diag.momentum[0, alive].copy()


def longitudinal_series(context: ValidationContext, max_steps: int | None = None):
    """
    Beam observables vs mean longitudinal position for particles still inside
    the lattice aperture volume (z <= z_exit).
    """
    diag = context.diagnostics
    z_exit = lattice_z_exit(context)
    n = diag.n_steps if max_steps is None else min(diag.n_steps, int(max_steps))

    z_c, sx, sy, sz = [], [], [], []
    sxp, syp, eps_x, eps_y = [], [], [], []
    bx, ax, gx = [], [], []
    by, ay, gy = [], [], []
    dpp, mean_p, mean_g, mean_ke = [], [], [], []
    transm = []

    n_init = max(diag.n_particles, 1)
    for step in range(n):
        pos = diag.position[step]
        mom = diag.momentum[step]
        gam = diag.gamma[step]
        alive = diag.alive[step].astype(bool)
        inside = alive & (pos[:, 2] <= z_exit + 1e-9)
        if not np.any(inside):
            break
        p = pos[inside]
        m = mom[inside]
        g = gam[inside]
        rx, ry, rz = rms_size_3d(p)
        dxp, dyp = rms_divergence(m)
        spread = momentum_spread(m)
        tw_x = plane_twiss(p, m, 0)
        tw_y = plane_twiss(p, m, 1)
        z_c.append(float(np.mean(p[:, 2])))
        sx.append(rx)
        sy.append(ry)
        sz.append(rz)
        sxp.append(dxp)
        syp.append(dyp)
        eps_x.append(tw_x["emittance"])
        eps_y.append(tw_y["emittance"])
        bx.append(tw_x["beta"])
        ax.append(tw_x["alpha"])
        gx.append(tw_x["gamma"])
        by.append(tw_y["beta"])
        ay.append(tw_y["alpha"])
        gy.append(tw_y["gamma"])
        dpp.append(spread["delta_p_over_p_rms"])
        mean_p.append(spread["mean_p"])
        mean_g.append(float(np.mean(g)))
        # Kinetic energy proxy in MeV: (γ-1) m c²; use proton mass scale via γ only.
        mean_ke.append(float(np.mean(g - 1.0)))
        transm.append(float(np.sum(alive)) / n_init)

    return {
        "z": np.asarray(z_c, dtype=np.float64),
        "sigma_x": np.asarray(sx, dtype=np.float64),
        "sigma_y": np.asarray(sy, dtype=np.float64),
        "sigma_z": np.asarray(sz, dtype=np.float64),
        "sigma_xp": np.asarray(sxp, dtype=np.float64),
        "sigma_yp": np.asarray(syp, dtype=np.float64),
        "emittance_x": np.asarray(eps_x, dtype=np.float64),
        "emittance_y": np.asarray(eps_y, dtype=np.float64),
        "beta_x": np.asarray(bx, dtype=np.float64),
        "alpha_x": np.asarray(ax, dtype=np.float64),
        "gamma_x": np.asarray(gx, dtype=np.float64),
        "beta_y": np.asarray(by, dtype=np.float64),
        "alpha_y": np.asarray(ay, dtype=np.float64),
        "gamma_y": np.asarray(gy, dtype=np.float64),
        "delta_p_over_p": np.asarray(dpp, dtype=np.float64),
        "mean_p": np.asarray(mean_p, dtype=np.float64),
        "mean_gamma": np.asarray(mean_g, dtype=np.float64),
        "mean_kinetic_proxy": np.asarray(mean_ke, dtype=np.float64),
        "transmission": np.asarray(transm, dtype=np.float64),
    }


def per_element_losses(context: ValidationContext) -> dict:
    """
    Attribute particle losses to lattice elements using the diagnostics
    ``alive`` mask and longitudinal position at the death step.

    Particles that reach the lattice exit and are subsequently marked not-alive
    (downstream of the lattice) are treated as transmitted, not lost.
    """
    diag = context.diagnostics
    elements = list(context.lattice.elements)
    n_el = len(elements)
    losses = np.zeros(n_el, dtype=np.int64)
    n_init = diag.n_particles
    z_exit = lattice_z_exit(context)
    if n_init == 0 or diag.n_steps < 2:
        return {
            "labels": [type(el).__name__ for el in elements],
            "z_start": [float(el.z_start) for el in elements],
            "z_end": [float(el.z_end) for el in elements],
            "losses": losses,
            "cumulative_transmission": np.ones(n_el, dtype=np.float64),
            "n_initial": n_init,
            "n_lost_total": 0,
        }

    transmitted = _reached_exit(diag, z_exit)
    previously_alive = diag.alive[0].astype(bool).copy()
    for step in range(1, diag.n_steps):
        alive = diag.alive[step].astype(bool)
        died = previously_alive & ~alive & ~transmitted
        if np.any(died):
            z_die = diag.position[step - 1, died, 2]
            for z in z_die:
                if z > z_exit + 1e-9:
                    continue
                assigned = False
                for i, el in enumerate(elements):
                    if el.z_start - 1e-12 <= z <= el.z_end + 1e-12:
                        losses[i] += 1
                        assigned = True
                        break
                if not assigned and n_el > 0:
                    if z < elements[0].z_start:
                        losses[0] += 1
                    else:
                        losses[-1] += 1
        previously_alive = alive

    cum_lost = np.cumsum(losses)
    cum_tx = (n_init - cum_lost) / max(n_init, 1)
    return {
        "labels": [type(el).__name__ for el in elements],
        "z_start": [float(el.z_start) for el in elements],
        "z_end": [float(el.z_end) for el in elements],
        "losses": losses,
        "cumulative_transmission": cum_tx.astype(np.float64),
        "n_initial": n_init,
        "n_lost_total": int(np.sum(losses)),
    }
