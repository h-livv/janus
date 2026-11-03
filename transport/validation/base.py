"""Legacy ValidationCase base (superseded by declarative case.py)."""

class LegacyValidationCase:
    """Original inheritance-based validation case; kept for backward compatibility."""

    def __init__(self, name, dt=1e-10, max_steps=500, max_steps_conv=150):
        self.name = name
        self.dt = dt
        self.max_steps = max_steps
        self.max_steps_conv = max_steps_conv
        self.z_start = 0.0

    def get_custom_error_data(self, diagnostics, analytical):
        return {}

    def build_lattice(self):
        raise NotImplementedError

    def initial_particles(self):
        raise NotImplementedError

    def analytical_solution(self, diagnostics):
        return {}

    def analytical_position(self, t, R_init, V_init, charges):
        raise NotImplementedError

    def evaluate(self, diagnostics, analytical):
        return {}

    def get_tolerances(self):
        return {}


# Backward-compatible alias
ValidationCase = LegacyValidationCase
