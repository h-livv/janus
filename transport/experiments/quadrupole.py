import xtrack as xt

from transport.io import single_particle_seeds
from transport.pipeline import run


def main():
    line = xt.Line(elements=[xt.Quadrupole(length=1.0, k1=0.5)])
    particle = "antiproton"
    count = 1
    name = "quadrupole"

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
        seeds=seeds,
        name=name,
    )


if __name__ == "__main__":
    main()
