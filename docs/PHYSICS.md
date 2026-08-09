# Janus Physics Model

## Overview

Janus is a stochastic simulation framework for modeling the production, transport, and optimization of antiproton beams.

The framework is divided into distinct physical stages corresponding to the real-world antimatter production pipeline:

```text
Proton Beam
    ↓
Target Collision
    ↓
Secondary Particle Production
    ↓
Magnetic Collection
    ↓
Momentum Selection
    ↓
Beam Transport
    ↓
(Deceleration)
    ↓
(Cooling)
    ↓
(Trapping)
```

This document describes the physical models currently implemented within Janus, together with their governing equations, assumptions, and simplifications.

---

# Fundamental Physics

Particle transport and interactions are governed by:

## Relativistic Energy

$$
E^2 = (pc)^2 + (mc^2)^2
$$

where:

* $E$ = total energy
* $p$ = momentum
* $m$ = rest mass
* $c$ = speed of light



## Momentum Conservation

$$
\sum \vec{p}_{\text{initial}}
=

\sum \vec{p}_{\text{final}}
$$


## Energy Conservation

$$
\sum E_{\text{initial}}
=

\sum E_{\text{final}}
$$



## Lorentz Force

Charged particles moving through electromagnetic fields obey

$$
\frac{d\vec{p}}{dt}
=

q(\vec{E}+\vec{v}\times\vec{B})
$$

For Janus beamline transport, particle advancement is performed by **Xsuite** (`xtrack`/`xpart`). Janus converts Geant4 seed phase space into Xsuite coordinates; callers build `xtrack.Line` objects with native Xsuite elements. Electromagnetic field models inside supported elements are those provided by Xsuite.

In the current configuration,

$$
\vec{E}=0
$$

so transport is governed by magnetic elements (drift, quadrupole, bend). Magnetic horn elements are not yet wired through an Xsuite field-map adapter.


# 1. Target Collision

## Physical Purpose

A high-energy proton beam strikes a dense target.

The collision produces secondary particles through hadronic interactions:

* pions
* kaons
* protons
* antiprotons
* antineutrons
* hyperons
* other secondaries

The target stage provides the initial phase-space distribution consumed by transport experiments (`xtrack.Line`). With the default collision `record_mode` of `"Hit"`, transport seeds are Target→Chamber boundary states; `"Birth"` records \(t=0\) production kinematics instead.

## Governing Equations

The interaction physics is handled directly by Geant4.

Conservation laws are enforced event-by-event:

### Energy

$$
\sum E_{\text{initial}}
=

\sum E_{\text{final}}
$$

### Momentum

$$
\sum \vec p_{\text{initial}}
=

\sum \vec p_{\text{final}}
$$

### Charge

$$
\sum q_{\text{initial}}
=

\sum q_{\text{final}}
$$

### Baryon Number

$$
\sum B_{\text{initial}}
=

\sum B_{\text{final}}
$$


## Assumptions

* Geant4 is treated as the source of truth.
* Nuclear interaction models are not reimplemented.
* Particle production cross sections are inherited from Geant4 physics lists.
* Material effects are handled by Geant4.


## Simplifications

* Janus only consumes the generated particle distributions.
* No custom collision model is used.
* Detector response is not simulated.


# 2. Transport

Beamline transport is delegated to **Xsuite**. Janus owns only:

* Geant4 ROOT → NPZ seed extraction (`transport/io.py`) — load only; no experiment cuts
* Conversion of seed arrays into `xpart.Particles` (`transport/xsuite.py`)
* Packaging of transported NPZ output for optimization
* Experiment scripts under `experiments/transport/` that define every scientific parameter

Beamlines are constructed in Python with native Xsuite elements (`xt.Drift`, `xt.Quadrupole`, `xt.Bend`, …). Particle coordinates use the Xsuite convention: transverse positions `x`, `y` [m]; normalized momenta `px`, `py`; longitudinal phase `zeta` (set to 0 at injection); momentum deviation `delta`. Reference mass uses `xt.PROTON_MASS_EV` for both proton and antiproton ensembles.

The physical models below describe the accelerator elements relevant to antimatter collection. Their tracking maps are provided by Xsuite, not by Janus. Horn and higher-order correctors remain conceptual until wired through Xsuite field-map elements.



# Magnetic Horn

## Physical Purpose

The magnetic horn collects charged secondaries emerging from the target.

Low-angle particles are focused toward the transport axis.

The horn greatly increases capture efficiency.


## Governing Equations

The horn field is approximated as

$$
B_\phi(r)
=

\frac{\mu_0 I}{2\pi r}
$$

where:

* $I$ = horn current
* $r$ = radial distance from axis

Particle motion follows

$$
\frac{d\vec p}{dt}
=

q(\vec v\times\vec B)
$$



## Assumptions

* Cylindrical symmetry.
* Steady-state current.
* Idealized conductor geometry.



## Simplifications

* No skin effects.
* No current pulse dynamics.
* No conductor heating.
* No field-map interpolation.



# Drift Zone

## Physical Purpose

A drift region allows particles to propagate without active magnetic focusing.

Momentum-dependent divergence naturally develops.


## Governing Equations

No external force:

$$
\frac{d\vec p}{dt}=0
$$

Therefore

$$
\vec p = \text{constant}
$$

and

$$
\vec x(t)
=

\vec x_0+\vec v t
$$



## Assumptions

* Perfect vacuum.
* No residual magnetic field.


## Simplifications

* No scattering.
* No energy loss.
* No gas interactions.


# Dipole Magnet

## Physical Purpose

Dipoles provide momentum selection.

Particles with different momentum follow different trajectories.

This allows antiproton filtering.



## Governing Equations

Radius of curvature:

$$
R
=

\frac{p}{qB}
$$

Equivalent accelerator form:

$$
p[\text{GeV}/c]
=

0.2998, B[\text{T}], R[\text{m}]
$$



## Assumptions

* Uniform magnetic field.
* Hard-edge boundaries.


## Simplifications

* No fringe fields.
* No field errors.
* No hysteresis.



# Quadrupole Magnet

## Physical Purpose

Quadrupoles focus the beam in one plane while defocusing it in the orthogonal plane.

They provide transverse beam control.



## Governing Equations

Field model:

$$
B_x = G y
$$

$$
B_y = G x
$$

where

$$
G=\frac{\partial B}{\partial x}
$$

is the gradient.

The focusing strength is

$$
k
=

\frac{qG}{p}
$$

Beam envelope evolution is approximately

$$
x'' + kx = 0
$$

for the focusing plane.



## Assumptions

* Linear magnetic field.
* Small transverse displacement.



## Simplifications

* No higher-order multipoles.
* No alignment errors.
* No fringe fields.



# Sextupole Magnet

## Physical Purpose

Sextupoles correct chromatic aberrations.

Particles of different momentum experience different focusing strengths; sextupoles compensate for this effect.



## Governing Equations

Field expansion:

$$
B_x
=

Sxy
$$

$$
B_y
=

\frac{S}{2}(x^2-y^2)
$$

where

$$
S
=

\frac{\partial^2 B}{\partial x^2}
$$

is the sextupole strength.


## Assumptions

* Ideal sextupole field.
* Small beam offsets.


## Simplifications

* No magnet imperfections.
* No saturation effects.


# Current Scope

**Implemented today**

* Target production (Geant4: `engines/geant4/` + `interactions/`)
* Collision-stage validation (`interactions/validation/`)
* NPZ seed extraction from Geant4 ROOT output (`transport/io.py`)
* Xsuite-backed drift, quadrupole, and bend transport via Python experiment scripts
* Automatic post-transport diagnostics (`transport/analysis/`)

**Not yet implemented**

* Magnetic horn as an Xsuite field-map element
* Cooling, deceleration, trapping, and global optimization

For how to define and run a transport study, see [transport guide](guides/transport_guide.md).


# Philosophy

Janus is not intended to reproduce every microscopic accelerator effect.

Instead, it seeks to capture the dominant beam-physics mechanisms that determine antimatter yield, transport efficiency, momentum selection, and beamline optimization while remaining computationally tractable for large-scale parameter studies and optimization workflows.
