"""Smoke test: single antiproton through a bend."""

import xtrack as xt

from transport.io import single_particle_seeds
from transport.pipeline import run


def main():
    line = xt.Line(elements=[xt.Bend(length=10.0, angle=0.01)])

    particle = "antiproton"
    count = 1
    momentum_slice = None
    num_turns = 1
    output_name = "dipole"
    output_dir = "data/transport"

    seeds = single_particle_seeds(
        particle=particle,
        position=[0.0, 0.0, 0.0],
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
