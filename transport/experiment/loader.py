"""YAML experiment loader."""

import yaml

from transport.experiment.schema import (
    ElementSpec,
    Experiment,
    ExperimentMeta,
    LatticeSpec,
    MetricSpec,
    ParticleSourceSpec,
    ValidationSpec,
)
from transport.validation.config import (
    ComparisonDirection,
    ConvergenceConfig,
    NumericalConfig,
    OutputConfig,
    PassCriteria,
)


def load_experiment(path: str) -> Experiment:
    with open(path) as f:
        data = yaml.safe_load(f)
    return Experiment.from_dict(data)


def _parse_lattice_elements(lat: dict) -> list[dict]:
    """Expand declarative lattice blocks into flat element dicts."""
    has_elements = bool(lat.get("elements"))
    has_repeat = "repeat" in lat
    has_fodo = "fodo" in lat

    if sum([has_elements, has_repeat, has_fodo]) > 1:
        raise ValueError(
            "Lattice config is ambiguous: use only one of 'elements', 'repeat', or 'fodo'"
        )

    if has_fodo:
        from transport.lattice.patterns import expand_fodo_elements

        fodo = lat["fodo"]
        return expand_fodo_elements(
            total_length=fodo["length"],
            quadrupole_length=fodo["quadrupole_length"],
            drift_length=fodo.get("drift_length", fodo.get("drift", 0.0)),
            k=fodo["k"],
            aperture_radius=fodo.get("aperture"),
            prefix=fodo.get("prefix"),
            suffix=fodo.get("suffix"),
        )

    if has_repeat:
        from transport.lattice.patterns import expand_repeat_elements

        repeat = lat["repeat"]
        return expand_repeat_elements(
            total_length=repeat["length"],
            cell=repeat["cell"],
            prefix=repeat.get("prefix"),
            suffix=repeat.get("suffix"),
            aperture_radius=repeat.get("aperture"),
        )

    return list(lat.get("elements", []))


def parse_experiment_dict(data: dict) -> Experiment:
    exp = data.get("experiment", {})
    ps = data.get("particle_source", {})
    lat = data.get("lattice", {})
    num = data.get("numerical", {})
    val = data.get("validation", {})
    out = data.get("outputs", {})

    conv = num.get("convergence", {})
    mode = conv.get("mode", "analytical")
    if conv.get("use_self_convergence"):
        mode = "self"
    convergence = ConvergenceConfig(
        enabled=conv.get("enabled", True),
        num_points=conv.get("num_points", 8),
        refinement_ratio=conv.get("refinement_ratio", 2.0),
        use_self_convergence=(mode == "self"),
        mode=mode,
    )

    numerical = NumericalConfig(
        dt=float(num["dt"]),
        max_steps=int(num["max_steps"]),
        max_steps_conv=int(num["max_steps_conv"]),
        convergence=convergence,
        solver_name=num.get("solver", "boris"),
    )

    raw_elements = _parse_lattice_elements(lat)

    elements = []
    for el in raw_elements:
        el_copy = dict(el)
        el_type = el_copy.pop("type")
        elements.append(ElementSpec(type=el_type, params=el_copy))

    lattice = LatticeSpec(
        z_start=float(lat.get("z_start", 0.0)),
        elements=elements,
    )

    particle_source = ParticleSourceSpec(
        type=ps["type"],
        species=ps.get("species", "proton"),
        charge_filter=ps.get("charge_filter", "any"),
        n_particles=int(ps.get("n_particles", 1)),
        momentum_slice=ps.get("momentum_slice"),
        position=ps.get("position"),
        velocity=ps.get("velocity"),
        gamma=ps.get("gamma"),
        pos_sigma=float(ps.get("pos_sigma", 0.0)),
        vel_sigma=float(ps.get("vel_sigma", 0.0)),
        rng_seed=int(ps.get("rng_seed", 42)),
        path=ps.get("path"),
    )

    metrics = None
    if val.get("metrics"):
        metrics = []
        for m in val["metrics"]:
            direction = ComparisonDirection(m.get("direction", "le"))
            metrics.append(MetricSpec(
                name=m["name"],
                tolerance=float(m["tolerance"]),
                direction=direction,
                informational=m.get("informational", False),
            ))

    pass_criteria = PassCriteria(val.get("pass_criteria", "all_must_pass"))

    validation = ValidationSpec(metrics=metrics, pass_criteria=pass_criteria)

    outputs = OutputConfig(
        emit_report=out.get("report", True),
        emit_json=out.get("json", True),
        emit_csv=out.get("csv", True),
        emit_manifest=out.get("manifest", True),
        emit_plots=out.get("plots", True),
        visualization=out.get("visualization", False),
        output_dir=exp.get("output_dir"),
        pass_criteria=pass_criteria,
    )

    meta = ExperimentMeta(
        name=exp["name"],
        level=int(exp.get("level", 1)),
        case=exp["case"],
        output_dir=exp.get("output_dir", "transport/validation/outputs"),
    )

    return Experiment(
        meta=meta,
        particle_source=particle_source,
        lattice=lattice,
        numerical=numerical,
        validation=validation,
        outputs=outputs,
    )
