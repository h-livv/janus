"""Declarative lattice patterns (repeat cells, FODO presets)."""

from __future__ import annotations


def _element_length(spec: dict) -> float:
    return float(spec["length"])


def _apply_aperture(spec: dict, aperture_radius: float | None) -> dict:
    out = dict(spec)
    if aperture_radius is not None and "aperture" not in out and "aperture_radius" not in out:
        out["aperture"] = aperture_radius
    return out


def cell_length(cell: list[dict]) -> float:
    if not cell:
        raise ValueError("Repeat cell must contain at least one element")
    return sum(_element_length(el) for el in cell)


def expand_repeat_elements(
    total_length: float,
    cell: list[dict],
    prefix: list[dict] | None = None,
    suffix: list[dict] | None = None,
    aperture_radius: float | None = None,
) -> list[dict]:
    """
    Tile ``cell`` over ``total_length``.

    Optional ``prefix`` / ``suffix`` elements are placed before / after the
    repeated block. Any leftover length inside the repeat region becomes a
    closing drift.
    """
    total_length = float(total_length)
    if total_length <= 0:
        raise ValueError(f"Repeat total length must be positive, got {total_length}")

    prefix = prefix or []
    suffix = suffix or []
    prefix_len = sum(_element_length(el) for el in prefix)
    suffix_len = sum(_element_length(el) for el in suffix)
    repeat_region = total_length - prefix_len - suffix_len
    if repeat_region <= 0:
        raise ValueError(
            f"Repeat region length must be positive after prefix/suffix "
            f"(total={total_length}, prefix={prefix_len}, suffix={suffix_len})"
        )

    unit = cell_length(cell)
    n_repeats = int(repeat_region // unit)
    if n_repeats < 1:
        raise ValueError(
            f"Repeat region {repeat_region} m is shorter than one cell ({unit} m). "
            "Increase length or shorten the cell definition."
        )

    remainder = repeat_region - n_repeats * unit
    elements: list[dict] = [_apply_aperture(el, aperture_radius) for el in prefix]
    for _ in range(n_repeats):
        elements.extend(_apply_aperture(el, aperture_radius) for el in cell)
    if remainder > 1e-9:
        elements.append(
            _apply_aperture({"type": "drift", "length": remainder}, aperture_radius)
        )
    elements.extend(_apply_aperture(el, aperture_radius) for el in suffix)
    return elements


def fodo_cell(
    k: float,
    quadrupole_length: float,
    drift_length: float,
    aperture_radius: float | None = None,
) -> list[dict]:
    """One FODO half-cell pair: QF (+k) – drift – QD (−k) – drift."""
    k_mag = abs(float(k))
    ql = float(quadrupole_length)
    dl = float(drift_length)
    aperture = {"aperture": aperture_radius} if aperture_radius is not None else {}
    return [
        {"type": "quadrupole", "length": ql, "k": k_mag, **aperture},
        {"type": "drift", "length": dl, **aperture},
        {"type": "quadrupole", "length": ql, "k": -k_mag, **aperture},
        {"type": "drift", "length": dl, **aperture},
    ]


def expand_fodo_elements(
    total_length: float,
    quadrupole_length: float,
    drift_length: float,
    k: float,
    aperture_radius: float | None = None,
    prefix: list[dict] | None = None,
    suffix: list[dict] | None = None,
) -> list[dict]:
    """Expand a FODO lattice by repeating the standard QF–D–QD–D cell."""
    cell = fodo_cell(k, quadrupole_length, drift_length, aperture_radius)
    return expand_repeat_elements(
        total_length=total_length,
        cell=cell,
        prefix=prefix,
        suffix=suffix,
        aperture_radius=aperture_radius,
    )


def repeat_summary(
    total_length: float,
    cell: list[dict],
    prefix: list[dict] | None = None,
    suffix: list[dict] | None = None,
) -> dict:
    prefix = prefix or []
    suffix = suffix or []
    prefix_len = sum(_element_length(el) for el in prefix)
    suffix_len = sum(_element_length(el) for el in suffix)
    unit = cell_length(cell)
    repeat_region = float(total_length) - prefix_len - suffix_len
    n_repeats = int(repeat_region // unit)
    remainder = repeat_region - n_repeats * unit
    return {
        "n_repeats": n_repeats,
        "cell_length": unit,
        "prefix_length": prefix_len,
        "suffix_length": suffix_len,
        "remainder_drift": remainder,
    }
