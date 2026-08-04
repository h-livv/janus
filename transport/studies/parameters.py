"""Parameter set generators for transport studies."""

from __future__ import annotations

import itertools
from typing import Any, Callable, Dict, List, Tuple

import numpy as np

ParameterSet = Dict[str, Any]
Bounds = Dict[str, Tuple[float, float]]


def grid_search(param_grid: dict[str, list]) -> list[ParameterSet]:
    """Cartesian product of discrete parameter values."""
    if not param_grid:
        return [{}]
    keys = sorted(param_grid.keys())
    values = [param_grid[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def random_search(
    param_bounds: Bounds,
    n_samples: int,
    seed: int = 0,
) -> list[ParameterSet]:
    """Uniform random samples within ``(low, high)`` bounds per parameter."""
    rng = np.random.default_rng(seed)
    keys = sorted(param_bounds.keys())
    samples: list[ParameterSet] = []
    for _ in range(int(n_samples)):
        row: ParameterSet = {}
        for key in keys:
            low, high = param_bounds[key]
            row[key] = float(rng.uniform(low, high))
        samples.append(row)
    return samples


def latin_hypercube(
    param_bounds: Bounds,
    n_samples: int,
    seed: int = 0,
) -> list[ParameterSet]:
    """Latin Hypercube samples for moderate-dimensional parameter spaces."""
    rng = np.random.default_rng(seed)
    keys = sorted(param_bounds.keys())
    n = int(n_samples)
    if n <= 0:
        return []

    samples: list[ParameterSet] = []
    for key in keys:
        low, high = param_bounds[key]
        # Stratified uniforms in [0, 1], then permuted per dimension.
        strata = (rng.permutation(n) + rng.random(n)) / n
        if not samples:
            samples = [{key: float(low + s * (high - low))} for s in strata]
        else:
            for i, s in enumerate(strata):
                samples[i][key] = float(low + s * (high - low))
    return samples


def as_generator(fn: Callable[..., list[ParameterSet]], **kwargs) -> Callable[[], list[ParameterSet]]:
    """Wrap a generator function for use with ``run_study``."""

    def _generate() -> list[ParameterSet]:
        return fn(**kwargs)

    return _generate
