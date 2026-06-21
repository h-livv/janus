# Initial Exploration of an Optimization Framework for Janus Particle Transport

## Objective

The objective of this study is to develop and evaluate an optimization framework for antiproton transport within Janus.

The transport system consists of a simplified magnetic optics lattice designed to capture and focus the highly divergent antiproton beam emerging from the production target. The primary goal is to maximize particle transmission through the transport pipe while maintaining acceptable beam quality.

---

## Transport Architecture

### Magnetic Horn

The magnetic horn provides the initial focusing stage immediately downstream of the production target.

Responsibilities:

* Reduce transverse beam divergence
* Focus charged particles toward the beam axis
* Direct particles into the transport channel

Optimization Variables:

* Horn current

---

### Drifts

Drift regions model free-space particle propagation between magnetic elements.

Responsibilities:

* Allow beam evolution in the absence of external fields
* Expose natural beam divergence

Optimization Variables:

* None

---

### Quadrupoles

Quadrupole magnets provide alternating focusing and defocusing forces in orthogonal transverse directions.

Responsibilities:

* Refocus divergent particles
* Steer the beam toward the transport axis
* Reduce beam size within the pipe aperture

Optimization Variables:

* Magnetic field gradients

---

## Physical Assumptions

To isolate transport dynamics from higher-order effects, the following simplifications were adopted:

* Deterministic particle transport
* No particle-particle interactions
* No residual-gas scattering
* No particle-material interactions after target extraction
* Idealized magnetic field models
* Fixed antiproton momentum window of

  3.57 GeV/c ± 0.5 GeV/c

These assumptions allow the study to focus exclusively on beam optics and transport efficiency.

---

## Optimization Objective

The primary objective is maximizing antiproton survival through the transport lattice.

Secondary objectives include:

* Minimizing beam divergence
* Minimizing RMS beam size
* Producing stable transport solutions that generalize across particle populations

The optimization process therefore balances transmission efficiency and beam quality.

---

## Phase 1 — Local Transport Optimization

This phase investigated whether a minimal lattice could be optimized using only two quadrupoles.

Configuration:

* Two quadrupoles (K1, K2)
* 15 extracted antiprotons

Optimization Method:

* SciPy Nelder-Mead

Loss Function:

* Penalized particle loss
* Rewarded forward transport distance

### Observations

The optimizer repeatedly became trapped in local minima due to the highly discontinuous objective landscape created by particle survival.

Additionally, two quadrupoles did not provide sufficient control authority to effectively capture the highly divergent antiproton distribution.

### Results

Survival rates frequently stagnated at:

* 1–2 surviving particles out of 15
* Approximately 13% transmission efficiency

This demonstrated that local optimization alone was insufficient for the transport problem.

---

## Phase 2 — Global Beamline Optimization

The transport lattice was expanded to include:

* Magnetic horn
* Four quadrupoles

The search space increased from two dimensions to five dimensions.

### Optimization Method

A hybrid optimization strategy was introduced:

#### Stage 1 — Global Exploration

Differential Evolution (DE)

Parameter Bounds:

* Horn Current: [-400 kA, 400 kA]
* Quadrupoles: [-15, 15]

#### Stage 2 — Local Refinement

Nelder-Mead optimization initialized using the best Differential Evolution solution.

### Observations

Contrary to expectations, the optimizer did not converge toward the maximum available horn current.

Instead, it consistently favored a significantly lower value:

* Optimal horn current ≈ -224.9 kA

This suggests that excessive focusing degraded downstream transport performance.

### Results

Survival improved substantially:

* 8 surviving particles out of 15
* 53.3% transmission efficiency

The introduction of global exploration successfully escaped the local minima that dominated Phase 1.

---

## Phase 3 — Generalization and Robustness

The primary objective of this phase was preventing overfitting to a small particle subset.

### Dataset

A population of 293 extracted antiprotons was randomly partitioned:

* Training Set: 205 particles (70%)
* Validation Set: 88 particles (30%)

### Metric Revision

The previous percentile-based beam metric was replaced with a strict RMS beam size:

RMS = √(mean(r²))

### Updated Objective

A squared loss penalty was introduced to strongly penalize particle loss:

Total Cost =
(loss_rate² × 10⁸)
+
(RMS_beam_size × 10⁴)

### Results

Training:

* 70 / 205 survivors
* 34.15% transmission efficiency

Validation:

* 22 / 88 survivors
* 25.00% transmission efficiency

Although absolute survival decreased relative to the toy example, the optimizer began producing solutions that generalized across independent particle populations.

---

## Phase 4 — Full-Scale Beamline Optimization

The final study utilized a realistic antiproton population extracted from the production simulation.

### Dataset

* 1,459 antiprotons

* Momentum filtered at

  3.57 GeV/c ± 0.5 GeV/c

* Injected into a constrained transport pipe of radius:

  0.10 m

### Objective Function

The optimization objective was revised to prioritize transmission efficiency above all other metrics:

Cost =
-(N_survivors × 10⁶)
+
(RMS_beam_size × 10⁴)

### Optimal Configuration

Horn Current:

* -242,934 A

Quadrupole Gradients:

* K1 = 6.24
* K2 = -5.04
* K3 = 2.81
* K4 = 2.00

### Results

Training Set:

* 554 / 1021 survivors
* 54.26% transmission efficiency

Validation Set:

* 234 / 438 survivors
* 53.42% transmission efficiency

The close agreement between training and validation performance suggests that the optimized transport configuration generalizes effectively across the extracted antiproton distribution.

---

## Conclusion

A deterministic transport model consisting of a magnetic horn and quadrupole beamline was successfully optimized using a hybrid Differential Evolution + Nelder-Mead strategy.

Key findings include:

* Local optimization alone is insufficient for highly discontinuous transport landscapes.
* Global exploration is essential for identifying high-quality beamline configurations.
* Excessive horn currents do not necessarily maximize transport efficiency.
* Train-validation evaluation is critical for preventing overfitting to specific particle populations.

The final optimized lattice achieved:

* Training Survival Rate: 54.26%
* Validation Survival Rate: 53.42%

These results establish a strong baseline for future Janus transport studies involving realistic magnetic field models, stochastic interactions, cooling systems, trap injection, and full antimatter storage pipelines.
