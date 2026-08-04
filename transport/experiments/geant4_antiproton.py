"""Transport Geant4 antiproton seeds through a minimal collector-style line.

Requires a Geant4 run under interactions/runs/ with simulation.root.

All scientific parameters for this experiment are defined below.
"""

import xtrack as xt

from transport.pipeline import run


def main():
    line = xt.Line(
        elements=[
            xt.Drift(length=5.0),
            xt.Quadrupole(length=1.0, k1=0.5),
            xt.Drift(length=2.0),
            xt.Quadrupole(length=1.0, k1=-0.5),
        ]
    )

    particle = "antiproton"
    count = 1000
    momentum_slice = (3.48, 3.68)  # GeV/c
    num_turns = 1
    output_name = "geant4_antiproton"
    output_dir = "transport/outputs"

    run(
        line=line,
        particle=particle,
        count=count,
        momentum_slice=momentum_slice,
        num_turns=num_turns,
        output_name=output_name,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
