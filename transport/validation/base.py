class ValidationCase:
    def __init__(self, name, dt=1e-10, max_steps=500, max_steps_conv=150):
        self.name = name
        self.dt = dt
        self.max_steps = max_steps
        self.max_steps_conv = max_steps_conv
        self.z_start = 0.0

    def get_custom_error_data(self, diagnostics, analytical):
        """
        Returns a dict describing custom error curves to plot.
        To be overridden by subclasses.
        """
        return {}

    def build_lattice(self):
        """
        Returns a SimpleLattice instance.
        """
        raise NotImplementedError

    def initial_particles(self):
        """
        Returns:
          R_init (np.ndarray of shape (N, 3)),
          V_init (np.ndarray of shape (N, 3)),
          gamma_init (np.ndarray of shape (N,)),
          charges (np.ndarray of shape (N,))
        """
        raise NotImplementedError

    def analytical_solution(self, diagnostics):
        """
        Returns a dictionary of expected results or analytical profiles.
        """
        return {}

    def analytical_position(self, t, R_init, V_init, charges):
        """
        Returns the analytical position of the particle at time t.
        R_init shape: (N, 3), V_init shape: (N, 3)
        Returns: numpy array of shape (N, 3)
        """
        raise NotImplementedError

    def evaluate(self, diagnostics, analytical):
        """
        Computes case-specific metrics.
        Returns a dict of metrics.
        """
        return {}

    def get_tolerances(self):
        """
        Returns a dict of tolerances for case-specific metrics.
        """
        return {}
