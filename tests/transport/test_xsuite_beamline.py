"""Tests for Xsuite Line construction via the public Python API."""

import xtrack as xt


def test_build_drift_line():
    line = xt.Line(elements=[xt.Drift(length=5.0)])
    assert len(line.elements) == 1
    assert isinstance(line.elements[0], xt.Drift)
    assert line.elements[0].length == 5.0


def test_build_quadrupole_and_bend():
    line = xt.Line(
        elements=[
            xt.Quadrupole(length=1.0, k1=0.5),
            xt.Bend(length=2.0, angle=0.01),
        ]
    )
    assert isinstance(line.elements[0], xt.Quadrupole)
    assert line.elements[0].k1 == 0.5
    assert isinstance(line.elements[1], xt.Bend)
    assert line.elements[1].angle == 0.01
