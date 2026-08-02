import xtrack as xt

from transport.io import single_particle_seeds
from transport.pipeline import run


def main():
    line = xt.Line(elements=[xt.Bend(length=10.0, angle=0.01)])
    particle = "antiproton"
    count = 1
    name = "dipole"

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
        seeds=seeds,
        name=name,
    )


if __name__ == "__main__":
    main()
