# Janus Architecture Milestones & Development Log

This document serves as a historical record of the major architectural milestones, system designs, and significant findings during the development of the **Janus** physics simulation and antimatter transport pipeline.

## 1. Core Data Pipeline & Strict Physics Validation
**Date:** June 18, 2026

### Architectural Milestones
* **HDF5 Data Migration:** Completely refactored the C++ Geant4 extraction pipeline. Transitioned from a custom, thread-locked CSV concatenator to Geant4's native thread-safe `G4AnalysisManager`. Output was cleanly separated into two distinct Ntuples: "Simulation" (seeds for transport) and "Validation" (event-by-event kinematics).
* **4-Phase Fatal Gatekeeper (`validate.py`):** Established a strict Python validation suite to guarantee physics integrity before allowing the downstream transport engine to run.
  * *Phase 1:* Vectorized verification of Energy-Momentum conservation.
  * *Phases 2-4:* Additional strict bounding and collision physics checks. 

### Observations & Results
* *Initial Energy Leak:* Discovered a major "Double-Count Trap" where validation data for outgoing particles was captured inside Geant4's `SteppingAction`, leading to a single particle being counted multiple times (e.g., 26 GeV proton falsely yielding 400 GeV). Fixed by moving the capture logic out of the stepping phase.

---

## 2. Decoupled VisPy Rendering & Relativistic Boris Integrator
**Date:** June 20, 2026

### Architectural Milestones
* **Relativistic Boris Integrator:** Built a custom physics engine leveraging fully vectorized `numpy` operations to handle ultra-relativistic antiprotons (>0.95c) without Python `for` loops.
* **Asynchronous Multi-Process Pipeline:** Strictly decoupled physics from visualization.
  * **Module 1:** Data Ingestion (HDF5).
  * **Module 2:** Physics Integration.
  * **Module 3:** GPU Rendering (`vispy` with PyQt5 backend).
* **Shared Memory IPC:** Used Python's `multiprocessing.shared_memory` to create a lock-free double-buffering system allowing the physics engine to run natively at high frequencies while the VisPy renderer updates the viewport asynchronously.

### Observations & Results
* *Coordinate Calibration:* Early render attempts resulted in missing beams and out-of-bounds rendering. Implemented a zero-field calibration mode to properly sync the physics coordinate system with the OpenGL viewport bounds.
* *Annihilation Rendering:* Created visual particle-burst queues to realistically show particles interacting with the FODO vacuum chamber walls in real time.

---

## 3. Dynamic Lattice Loader & Magnetic Horn Integration
**Date:** June 20, 2026

### Architectural Milestones
* **JSON-Driven Lattice Loader:** Evolved away from hardcoded spatial mathematics (e.g., `z % 3.0`) to a dynamic, object-oriented `LatticeLoader`. Elements like Drifts, Quadrupoles, and Sextupoles are now fully configurable via external JSON.
* **Geometry Integrity Tracking:** Implemented global coordinate geometry updating (`update_geometry()`) to auto-calculate the z-boundaries of sequential magnetic elements.
* **Magnetic Horn Implementation:** Added a custom non-linear azimuthal magnetic field ($B_\phi = \frac{\mu_0 I}{2 \pi r}$) to act as a collector at the injection point (Z=0), mimicking the actual antimatter factory target-horn layout at CERN.

### Observations & Results
* *Cone Intersection:* Visualizing the horn required precise tuning of alpha channels and depth mapping in VisPy to ensure particles could be tracked as they passed through the intense magnetic gradients inside the translucent horn chamber.

---

## 4. Autonomous Beam Optics Optimization Suite
**Date:** June 20, 2026

### Architectural Milestones
* **Headless Execution Bypass:** Patched the `boris_solver.py` to support `headless=True` to run optimizations at maximum CPU speed without invoking the VisPy GUI rendering.
* **Hybrid Optimization Pipeline (`optimize_k1_k2.py`):** 
  * *Stage 1 (Global):* `scipy.optimize.differential_evolution` mapped to find robust operational regions.
  * *Stage 2 (Local):* Nelder-Mead algorithm for fine-tuned precision using the best global seed as the $x_0$ guess.
* **Sensitivity Analyzer (`sensitivity.py`):** Implemented a One-At-a-Time (OAT) perturbation system to calculate sensitivity indices ($S_i$), effectively filtering out "noise" parameters.
* **Machine Learning Anti-Overfitting:** Integrated a dynamic Train/Validation split directly into the objective function to ensure the magnetic lattice didn't just overfit to a small set of seeds from a single HDF5 event.

### Observations & Results
* *Scoring Window Fix:* Found that scoring the beam variance too early (inside the matching section) was punishing the optimizer for natural beam focusing. Adjusted the evaluation window strictly to regions past the injection length to allow the envelope to breathe.

---

## 5. Massive Batch Execution & Pipeline Hardening
**Date:** June 21, 2026

### Architectural Milestones
* **Batch Execution Script (`run_batches.py`):** Structured the Python pipeline to handle long-running, multi-million particle simulation suites completely autonomously.
* **Concurrency Safety:** Hardened the temporary file tracking and output unique-naming systems to guarantee zero data overlap or corruption during heavy multi-threading operations.

### Observations & Results
* The system is now robust enough to be left completely unattended overnight while processing massive collision and transportation batches with 100% data integrity.

---

## 6. Comprehensive Diagnostics & Scale-Up Physics Breakthrough
**Date:** June 21, 2026

### Architectural Milestones
* **HDF5 Ingestion Caching:** Implemented an `.npz` caching system in `data_io.py`. After the first massive multi-batch HDF5 parse (~72GB), the exact $3.57 \text{ GeV/c}$ filtered phase-space vectors are cached, reducing subsequent pipeline spin-up times from 25+ minutes down to 3 seconds.
* **Diagnostic Plotting Suite:** Developed a robust, automated matplotlib backend module (`diagnostics.py`) to generate deep-physics deliverables per run, including:
  * KDE Momentum Distributions
  * Transverse Phase-Space Ellipses
  * Spatial Dispersion Profiles
  * Chamber/Pipe Wall Loss Maps
  * $1\sigma$/$3\sigma$ Beam Envelope propagation
* **Optimization Race Condition Fix:** Identified and patched a multithreaded overwrite collision inside the Differential Evolution `evaluate_injection.py` memory tracker by securely wrapping it in a strict `multiprocessing.Lock()`.
* **Pure Survival Cost Function:** Overhauled the optimization loss logic to forcefully weight absolute particle survival exponentially higher than theoretical RMS beam size: `-(num_survivors * 1e6) + (rms_beam_size * 1e4)`.

### Observations & Results
* *The 53% Transmission Breakthrough:* By eliminating the geometric bug at the FODO boundary, properly isolating 1,459 true antiprotons, and aggressively optimizing the Magnetic Horn and Quadrupole Doublet with the thread-safe survival cost function, the pipeline's overall transmission efficiency successfully leaped from an abysmal **0.41%** up to a robust **53.42%**. The capture hardware is perfectly synchronized with the FODO lattice for this momentum slice.
