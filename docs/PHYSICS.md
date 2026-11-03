# Janus physics model

Janus combines a Geant4 target-interaction simulation with a handwritten classical transport model. These stages represent different physics: Geant4 handles stochastic particle production in matter; Janus's transport code advances selected charged particles through externally specified fields.

## Particle transport

The transport model integrates the relativistic Lorentz equation

\[
\frac{d\mathbf p}{dt}=q(\mathbf E+\mathbf v\times\mathbf B),
\qquad \mathbf p=\gamma m\mathbf v,
\qquad \gamma=(1-v^2/c^2)^{-1/2}.
\]

The implementation is in `transport/physics/boris_solver.py`. It uses a staggered relativistic Boris leapfrog update: electric half-kicks surround a magnetic rotation, followed by a position advance. The algorithm is implemented in Janus rather than delegated to Xsuite. Its accuracy depends on the timestep, field model, element boundaries, and assumptions encoded in each validation case.

The built-in lattice fields in `transport/lattice/lattice.py` are:

- **Drift:** \(\mathbf E=\mathbf B=0\).
- **Dipole:** uniform vertical magnetic field \(B_y\).
- **Quadrupole:** linear transverse field, with gradient set by the element configuration.
- **Magnetic horn:** azimuthal field from an idealized axial current, \(B_\varphi=\mu_0 I/(2\pi r)\), restricted to its configured radial region.

The elements also define apertures and hard longitudinal boundaries. These are idealized field models; fringe fields and realistic field maps are not implied by the element names.

## Collision and transport boundary

The C++ engine in `engine/` uses Geant4 for proton-target interactions and writes ROOT data. The `Seeds` tree is read by `transport/io/`; transport then evolves the recorded phase-space coordinates through the configured lattice. Collision validation checks event-level conservation and diagnostic distributions, while transport validation checks the integrator and beamline model independently.

The tracker uses prescribed fields. It does not evolve the fields self-consistently, include collective space charge, or modify the Geant4 interaction model. Geant4 collision outputs and transport inputs also carry unit conventions; the ROOT reader is responsible for converting those values into SI quantities used by the integrator.

## Validation scope

The historical validation campaign compares elementary trajectories with analytical results, monitors energy and momentum behavior, checks timestep convergence, and evaluates composite lattices and beam observables. The archived methods, criteria, results, and figures are in [transport validation](validation/transport_validation.md). Those results are historical outputs from the development campaign and have not been recomputed as part of restoring the handwritten implementation to `main`.
