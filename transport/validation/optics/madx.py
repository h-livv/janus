"""Optional MAD-X optics backend (cpymad)."""

from __future__ import annotations

import shutil
from typing import Optional

import numpy as np

from transport.lattice.lattice import Dipole, Drift, Quadrupole
from transport.validation.optics.base import (
    OpticsBackend,
    OpticsEnvelope,
    OpticsTransferMatrix,
    OpticsTwiss,
)


# Rest masses [GeV/c²] for MAD-X BEAM command
_MASS_GEV = {
    "proton": 0.9382720813,
    "antiproton": 0.9382720813,
    "electron": 0.00051099895,
    "positron": 0.00051099895,
    "muon+": 0.1056583755,
    "muon-": 0.1056583755,
    "pion+": 0.13957039,
    "pion-": 0.13957039,
}


def _madx_particle_name(species: str, charge: float) -> str:
    key = (species or "proton").lower()
    if key in ("proton", "antiproton", "electron", "positron"):
        return key
    if key.startswith("muon"):
        return "muplus" if charge > 0 else "muminus"
    if key.startswith("pion"):
        return "piplus" if charge > 0 else "piminus"
    return "proton"


class MadxBackend(OpticsBackend):
    """
    MAD-X comparison backend.

    Uses ``cpymad`` when installed. If MAD-X is unavailable, ``available()``
    is False and comparison metrics become informational no-ops / fall back.
    """

    def __init__(self):
        self._madx = None
        self._madx_cls = None
        self._probe_error: Optional[str] = None
        self._probe()

    def _probe(self) -> None:
        try:
            from cpymad.madx import Madx  # type: ignore

            self._madx_cls = Madx
            self._madx = "cpymad"
            self._probe_error = None
        except Exception as exc:  # pragma: no cover - optional dependency
            self._madx_cls = None
            self._madx = None
            which = shutil.which("madx") or shutil.which("madx-linux64")
            if which:
                # Executable present but no cpymad binding — Twiss API needs cpymad.
                self._probe_error = f"madx found at {which} but cpymad is not installed"
            else:
                self._probe_error = f"MAD-X unavailable ({exc})"

    @property
    def name(self) -> str:
        return "madx"

    def available(self) -> bool:
        return self._madx == "cpymad" and self._madx_cls is not None

    def transfer_matrix(self, lattice, particle_state: dict) -> Optional[OpticsTransferMatrix]:
        tw = self.twiss(lattice, particle_state)
        if tw is None:
            return None
        # MAD-X table does not always expose full 4×4 R; leave to linear fallback.
        return None

    def envelope(self, lattice, particle_state: dict) -> Optional[OpticsEnvelope]:
        tw = self.twiss(lattice, particle_state)
        if tw is None:
            return None
        ex = float(particle_state.get("emittance_x", 0.0))
        ey = float(particle_state.get("emittance_y", 0.0))
        return OpticsEnvelope(
            z=tw.z.copy(),
            sigma_x=np.sqrt(np.maximum(tw.beta_x * ex, 0.0)),
            sigma_y=np.sqrt(np.maximum(tw.beta_y * ey, 0.0)),
            metadata={"backend": self.name, "from": "twiss"},
        )

    def twiss(self, lattice, particle_state: dict) -> Optional[OpticsTwiss]:
        if not self.available():
            return None
        try:
            return self._twiss_cpymad(lattice, particle_state)
        except Exception as exc:  # pragma: no cover - depends on MAD-X install
            del exc
            return None

    def _twiss_cpymad(self, lattice, particle_state: dict) -> OpticsTwiss:
        Madx = self._madx_cls
        madx = Madx(stdout=False)

        b_rho = float(particle_state.get("B_rho", 1.0))
        q = float(particle_state.get("charge", 1.0))
        gamma = float(particle_state.get("gamma", 1.0))
        species = str(particle_state.get("species", "proton"))
        mass_gev = float(particle_state.get("mass_gev", _MASS_GEV.get(species.lower(), 0.9382720813)))
        energy_gev = max(gamma * mass_gev, mass_gev + 1e-9)
        pc_gev = float(np.sqrt(max(energy_gev**2 - mass_gev**2, 0.0)))
        particle = _madx_particle_name(species, q)

        # Initial Twiss from tracked beam (or defaults).
        bx0 = float(particle_state.get("beta_x", 1.0))
        ax0 = float(particle_state.get("alpha_x", 0.0))
        by0 = float(particle_state.get("beta_y", 1.0))
        ay0 = float(particle_state.get("alpha_y", 0.0))

        madx.command.beam(particle=particle, energy=energy_gev, pc=pc_gev)
        lines = ["seq: sequence, l={:.12g};".format(float(lattice.total_length))]
        # Place elements by centre (MAD-X sequence convention).
        for i, el in enumerate(lattice.elements):
            at = 0.5 * (float(el.z_start) + float(el.z_end)) - float(lattice.z_start)
            name = f"el{i}"
            if isinstance(el, Drift):
                madx.command.drift(name, l=float(el.L))
            elif isinstance(el, Quadrupole):
                # Match Janus α = q G / Bρ used by the linear backend.
                k1 = q * float(el.k) / b_rho if abs(b_rho) > 1e-30 else 0.0
                madx.command.quadrupole(name, l=float(el.L), k1=k1)
            elif isinstance(el, Dipole):
                # Thin-sector approximation: angle ≈ By * L / Bρ (charge folded into k0-like).
                angle = q * float(el.By) * float(el.L) / b_rho if abs(b_rho) > 1e-30 else 0.0
                madx.command.sbend(name, l=float(el.L), angle=angle)
            else:
                madx.command.drift(name, l=float(el.L))
            lines.append(f"{name}, at={at:.12g};")
        lines.append("endsequence;")
        madx.input("\n".join(lines))
        madx.command.use(sequence="seq")
        madx.command.twiss(
            sequence="seq",
            betx=bx0,
            alfx=ax0,
            bety=by0,
            alfy=ay0,
        )

        table = madx.table.twiss
        s = np.asarray(table.s, dtype=np.float64) + float(lattice.z_start)
        betx = np.asarray(table.betx, dtype=np.float64)
        alfx = np.asarray(table.alfx, dtype=np.float64)
        bety = np.asarray(table.bety, dtype=np.float64)
        alfy = np.asarray(table.alfy, dtype=np.float64)
        # Prefer table columns when present; else reconstruct γ = (1+α²)/β.
        gamx = (
            np.asarray(table.gamx, dtype=np.float64)
            if hasattr(table, "gamx")
            else (1.0 + alfx**2) / np.maximum(betx, 1e-30)
        )
        gamy = (
            np.asarray(table.gamy, dtype=np.float64)
            if hasattr(table, "gamy")
            else (1.0 + alfy**2) / np.maximum(bety, 1e-30)
        )

        return OpticsTwiss(
            z=s,
            beta_x=betx,
            alpha_x=alfx,
            gamma_x=gamx,
            beta_y=bety,
            alpha_y=alfy,
            gamma_y=gamy,
            metadata={
                "backend": self.name,
                "particle": particle,
                "energy_gev": energy_gev,
                "pc_gev": pc_gev,
                "probe_error": self._probe_error,
            },
        )
