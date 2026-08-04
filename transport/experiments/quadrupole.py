"""Smoke test: single antiproton through a quadrupole."""

import xtrack as xt

from transport.io import single_particle_seeds
from transport.pipeline import run


def main():
    line = xt.Line(elements=[xt.Quadrupole(length=1.0, k1=0.5)])

    particle = "antiproton"
    count = 1
    momentum_slice = None
    num_turns = 1
    output_name = "quadrupole"
    output_dir = "transport/outputs"

    seeds = single_particle_seeds(
        particle=particle,
        position=[0.001, 0.0, 0.0],
        velocity=[0.0, 0.0, 299492818.0],
        gamma=3.82,
    )

    run(
        line=line,
        particle=particle,
        count=count,
        momentum_slice=momentum_slice,
        num_turns=num_turns,
        output_name=output_name,
        output_dir=output_dir,
        seeds=seeds,
    )


if __name__ == "__main__":
    main()
