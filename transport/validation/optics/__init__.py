"""Modular linear-optics comparison backends (MAD-X and built-in)."""

from __future__ import annotations

from transport.validation.optics.base import (
    OpticsBackend,
    OpticsEnvelope,
    OpticsTransferMatrix,
    OpticsTwiss,
)

__all__ = [
    "OpticsBackend",
    "OpticsEnvelope",
    "OpticsTransferMatrix",
    "OpticsTwiss",
    "get_optics_backend",
]


def get_optics_backend(preferred: str = "auto") -> OpticsBackend:
    """
    Resolve a comparison backend.

    preferred:
        ``madx`` — require MAD-X / cpymad
        ``linear`` — built-in thick-lens Drift/Quadrupole matrices
        ``auto`` — MAD-X if available, else linear
    """
    key = (preferred or "auto").lower()
    if key in ("madx", "auto"):
        from transport.validation.optics.madx import MadxBackend

        madx = MadxBackend()
        if madx.available():
            return madx
        if key == "madx":
            return madx  # unavailable stub; callers check available()
    from transport.validation.optics.linear import LinearOpticsBackend

    return LinearOpticsBackend()
