"""Lattice element labels and boundaries for longitudinal plots."""

from transport.lattice.lattice import Dipole, Drift, Quadrupole


def element_display_label(element) -> str:
    if isinstance(element, Drift):
        return "Drift"
    if isinstance(element, Dipole):
        return "Dipole"
    if isinstance(element, Quadrupole):
        return "QF" if element.k > 0 else "QD"
    return type(element).__name__


def lattice_elements_payload(lattice) -> list[dict]:
    return [
        {
            "z_start": float(el.z_start),
            "z_end": float(el.z_end),
            "label": element_display_label(el),
        }
        for el in lattice.elements
    ]


def uses_longitudinal_position(payload: dict) -> bool:
    if payload.get("lattice_elements"):
        return True
    xlabel = payload.get("xlabel", "")
    return "longitudinal" in xlabel.lower() or xlabel.strip().endswith("z (m)")
