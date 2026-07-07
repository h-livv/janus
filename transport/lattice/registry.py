"""Lattice element registry and declarative lattice builder."""

from transport.lattice.lattice import Dipole, Drift, Quadrupole, SimpleLattice


class ElementRegistry:
    def __init__(self):
        self._entries = {}

    def register(self, name, factory):
        self._entries[name.lower()] = factory

    def build(self, name, **kwargs):
        key = name.lower()
        if key not in self._entries:
            raise KeyError(f"Unknown element: '{name}'. Available: {self.list_names()}")
        return self._entries[key](**kwargs)

    def list_names(self):
        return sorted(self._entries.keys())


element_registry = ElementRegistry()


def _normalize_params(params: dict) -> dict:
    out = dict(params)
    if "aperture" in out and "aperture_radius" not in out:
        out["aperture_radius"] = out.pop("aperture")
    if "by" in out and "By" not in out:
        out["By"] = out["by"]
    return out


def _make_drift(**params):
    p = _normalize_params(params)
    return Drift(p["length"], aperture_radius=p.get("aperture_radius"))


def _make_dipole(**params):
    p = _normalize_params(params)
    return Dipole(p["length"], p["By"], aperture_radius=p.get("aperture_radius"))

def _make_quadrupole(**params):
    p = _normalize_params(params)
    return Quadrupole(p["length"], p["k"], aperture_radius=p.get("aperture_radius"))


def register_builtin_elements():
    element_registry.register("drift", _make_drift)
    element_registry.register("dipole", _make_dipole)
    element_registry.register("quadrupole", _make_quadrupole)


def build_lattice(lattice_spec):
    """Build SimpleLattice from a LatticeSpec."""
    elements = []
    for el_spec in lattice_spec.elements:
        try:
            elements.append(element_registry.build(el_spec.type, **el_spec.params))
        except KeyError:
            raise KeyError(
                f"Unknown element type '{el_spec.type}'. "
                f"Available: {element_registry.list_names()}"
            ) from None
    return SimpleLattice(elements, z_start=lattice_spec.z_start)
