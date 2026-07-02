import numpy as np

class Element:
    def __init__(self, length, aperture_radius=None):
        self.L = float(length)
        self.aperture_radius = float(aperture_radius) if aperture_radius is not None else None
        self.z_start = 0.0
        self.z_end = 0.0

    def field(self, x, y, z):
        """
        Returns (Bx, By, Bz) at the supplied coordinates.
        To be overridden by subclasses. For now we assume E = 0.
        """
        return np.zeros_like(x), np.zeros_like(y), np.zeros_like(z)

    def inside_aperture(self, x, y, z):
        """
        Returns a boolean array indicating if particles are inside the aperture.
        """
        if self.aperture_radius is None:
            return np.ones_like(x, dtype=bool)
        return (x**2 + y**2) < self.aperture_radius**2

    def draw(self, view):
        """Draw static geometry for this element. Override in subclasses."""
        pass


class Drift(Element):
    def __init__(self, length, aperture_radius=None):
        super().__init__(length, aperture_radius)

    def field(self, x, y, z):
        # Drift space has zero fields
        return np.zeros_like(x), np.zeros_like(y), np.zeros_like(z)

    def draw(self, view):
        from transport.visualization.primitives import (
            COL_DRIFT,
            COL_PIPE,
            box_at,
            draw_aperture_rings,
            draw_pipe_wireframe,
            tube_segment,
        )

        z0, z1 = self.z_start, self.z_end
        cz = 0.5 * (z0 + z1)
        span = max(self.aperture_radius, 0.02) if self.aperture_radius is not None else 0.05
        box_at(
            view,
            width=span * 4.0,
            height=span * 4.0,
            depth=self.L,
            cx=0.0,
            cy=0.0,
            cz=cz,
            color=COL_DRIFT,
            edge_color=(0.30, 0.60, 0.90, 0.50),
        )
        if self.aperture_radius is not None:
            tube_segment(view, z0, z1, self.aperture_radius, COL_PIPE)
            draw_pipe_wireframe(view, z0, z1, self.aperture_radius)
            draw_aperture_rings(view, z0, z1, self.aperture_radius)


class Dipole(Element):
    def __init__(self, length, By, aperture_radius=None):
        super().__init__(length, aperture_radius)
        self.By = float(By)

    def field(self, x, y, z):
        # Uniform vertical magnetic field By when inside the boundaries
        # We assume local coordinate z is within [z_start, z_end].
        return (
        np.zeros_like(x),
        np.full_like(y, self.By),
        np.zeros_like(z),
    )

    def draw(self, view):
        from transport.visualization.primitives import (
            COL_DIPOLE_FIELD,
            COL_PIPE,
            box_at,
            draw_aperture_rings,
            draw_pipe_wireframe,
            tube_segment,
        )

        z0, z1 = self.z_start, self.z_end
        cz = 0.5 * (z0 + z1)
        span = max(self.aperture_radius, 0.02) if self.aperture_radius is not None else 0.05
        box_at(
            view,
            width=span * 4.0,
            height=span * 4.0,
            depth=self.L,
            cx=0.0,
            cy=0.0,
            cz=cz,
            color=COL_DIPOLE_FIELD,
            edge_color=(0.4, 0.0, 0.8, 0.5),
        )
        if self.aperture_radius is not None:
            tube_segment(view, z0, z1, self.aperture_radius, COL_PIPE)
            draw_pipe_wireframe(view, z0, z1, self.aperture_radius)
            draw_aperture_rings(view, z0, z1, self.aperture_radius)


class SimpleLattice:
    def __init__(self, elements, z_start=0.0):
        self.elements = list(elements)
        self.z_start = float(z_start)
        self._build()

    def _build(self):
        current_z = self.z_start
        for el in self.elements:
            el.z_start = current_z
            el.z_end = current_z + el.L
            current_z = el.z_end
        self.total_length = current_z - self.z_start

    def get_element_at_z(self, z):
        """
        Returns the active element for a given z coordinate.
        """
        for el in self.elements:
            if el.z_start <= z <= el.z_end:
                return el
        return None

    def get_field(self, x, y, z):
        """
        Queries the magnetic field for coordinates.
        Accepts numpy arrays or scalars.
        """
        # Resolve array inputs
        if isinstance(x, np.ndarray):
            Bx = np.zeros_like(x)
            By = np.zeros_like(y)
            Bz = np.zeros_like(z)
            for el in self.elements:
                mask = (z >= el.z_start) & (z <= el.z_end)
                if np.any(mask):
                    el_bx, el_by, el_bz = el.field(x[mask], y[mask], z[mask])
                    Bx[mask] = el_bx
                    By[mask] = el_by
                    Bz[mask] = el_bz
            return Bx, By, Bz
        else:
            el = self.get_element_at_z(z)
            if el:
                return el.field(x, y, z)
            return 0.0, 0.0, 0.0

    def inside_aperture(self, x, y, z):
        """
        Queries if coordinates are within the local element's aperture.
        """
        if isinstance(x, np.ndarray):
            inside = np.ones_like(x, dtype=bool)
            for el in self.elements:
                mask = (z >= el.z_start) & (z <= el.z_end)
                if np.any(mask):
                    inside[mask] = el.inside_aperture(x[mask], y[mask], z[mask])
            # If outside the entire lattice, mark as dead/outside
            outside_lattice = (z < self.z_start) | (z > self.z_start + self.total_length)
            inside[outside_lattice] = False
            return inside
        else:
            el = self.get_element_at_z(z)
            if el:
                return el.inside_aperture(x, y, z)
            return False

    def draw(self, view, elements=None):
        """
        Compose visualization for all elements or a requested subset.
        elements: None (all), list of Element instances, or list of indices.
        """
        if elements is None:
            targets = self.elements
        elif elements and isinstance(elements[0], Element):
            targets = elements
        else:
            targets = [self.elements[i] for i in elements]

        for el in targets:
            el.draw(view)
