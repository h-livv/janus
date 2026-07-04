"""
Headless and validation pipeline orchestration.
Transport runs once; validation consumes diagnostics only.
"""
import datetime
import os

from transport.simulation_config import validation_case_for_config
from transport.validation.engine import ValidationEngine
from transport.validation.solver import BorisSolverAdapter


def run_transport(config, solver=None, mass=None):
    solver = solver or BorisSolverAdapter()
    kwargs = {}
    if mass is not None:
        kwargs["mass"] = mass
    return solver.run(
        config.R_init,
        config.V_init,
        config.gamma_init,
        config.charges,
        config.lattice,
        config.dt,
        config.max_steps,
        **kwargs,
    )


def run_validation_reports(config, run_outputs_dir, solver=None):
    validation_case = validation_case_for_config(config)
    mass = getattr(config, "mass", None)
    _, _, _, diagnostics = run_transport(config, solver=solver, mass=mass)

    engine = ValidationEngine(solver=solver)
    result = engine.run(
        validation_case,
        run_outputs_dir=run_outputs_dir,
        prebuilt_lattice=config.lattice,
        prebuilt_diagnostics=diagnostics,
    )

    report_file_path = os.path.join(
        run_outputs_dir,
        validation_case.name.lower().replace("validation", ""),
        "report.txt",
    )

    passed = result["passed"]
    converged = result["converged"] if result["converged"] is not None else True
    return passed, converged, result["report"], result["convergence_report"], report_file_path


def run_experiment(experiment, run_outputs_dir=None, print_reports=True):
    from transport.experiment.resolver import validation_case_from_experiment
    from transport.validation.registry import initialize_registries, solver_registry

    initialize_registries()
    validation_case = validation_case_from_experiment(experiment)
    solver = solver_registry.build(experiment.numerical.solver_name)

    if run_outputs_dir is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_outputs_dir = os.path.join(experiment.output_dir, f"run_{timestamp}")
    print(f"[Validator] Outputs for this run will be saved in: {run_outputs_dir}\n")

    batch = validation_case.particle_source.generate()
    mass = batch.mass
    lattice = validation_case.build_system()
    _, _, _, diagnostics = solver.run(
        batch.R,
        batch.V,
        batch.gamma,
        batch.charges,
        lattice,
        experiment.numerical.dt,
        experiment.numerical.max_steps,
        mass=mass,
    )

    engine = ValidationEngine(solver=solver)
    result = engine.run(
        validation_case,
        run_outputs_dir=run_outputs_dir,
        prebuilt_lattice=lattice,
        prebuilt_diagnostics=diagnostics,
    )

    if print_reports:
        print(result["report"])
        print()
        if result["convergence_report"]:
            print(result["convergence_report"])
            print()
        print("-" * 60)

    passed = result["passed"]
    converged = result["converged"] if result["converged"] is not None else True
    return passed and converged, run_outputs_dir


def run_headless_suite(case_types, build_config_fn, print_reports=True):
    from transport.validation.registry import initialize_registries
    initialize_registries()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_outputs_dir = os.path.join("transport", "validation", "outputs", f"run_{timestamp}")
    print(f"[Validator] Outputs for this run will be saved in: {run_outputs_dir}\n")

    overall_passed = True
    for case_type in case_types:
        config = build_config_fn(case_type)
        passed, converged, report, report_conv, _ = run_validation_reports(
            config, run_outputs_dir
        )
        if print_reports:
            print(report)
            print()
            if report_conv:
                print(report_conv)
                print()
            print("-" * 60)
        if not passed or not converged:
            overall_passed = False

    return overall_passed, run_outputs_dir


def run_visualization(experiment):
    import multiprocessing as mp
    from multiprocessing.shared_memory import SharedMemory

    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    from transport.experiment.resolver import experiment_to_simulation_config
    from transport.physics.boris_solver import run_visual_physics_loop
    from transport.simulation_config import expand_beam
    from transport.visualization.viewport import run_renderer
    from transport.validation.registry import initialize_registries

    initialize_registries()
    config = experiment_to_simulation_config(experiment)
    source_type = experiment.particle_source.type.lower()

    if source_type in ("gaussian_beam", "geant4") or len(config.R_init) > 1:
        R_beam = config.R_init.copy()
        V_beam = config.V_init.copy()
        gamma_beam = config.gamma_init.copy()
        charges_beam = config.charges.copy()
    else:
        vel_sigma = 1.5 if config.use_mock_data else 1.5e6
        R_beam, V_beam, gamma_beam, charges_beam = expand_beam(
            config, 1000, 0.15, vel_sigma, 42,
        )

    n_particles = len(R_beam)
    trail_length = 200
    buffer_bytes = 2 * n_particles * 3 * 4
    shm = SharedMemory(create=True, size=buffer_bytes)
    shared_mem_name = shm.name
    sync_queue = mp.Queue(maxsize=5)
    stop_event = mp.Event()

    physics_proc = mp.Process(
        target=run_visual_physics_loop,
        args=(
            R_beam, V_beam, gamma_beam, charges_beam,
            config.lattice, config.dt, shared_mem_name, sync_queue, stop_event,
        ),
    )
    renderer_proc = mp.Process(
        target=run_renderer,
        args=(
            shared_mem_name, sync_queue, stop_event, n_particles, trail_length,
            config.lattice, charges_beam, None,
        ),
    )

    try:
        physics_proc.start()
        renderer_proc.start()
        renderer_proc.join()
        stop_event.set()
        physics_proc.join(timeout=2.0)
        if physics_proc.is_alive():
            physics_proc.terminate()
    except KeyboardInterrupt:
        stop_event.set()
        renderer_proc.terminate()
        physics_proc.terminate()
    finally:
        shm.close()
        shm.unlink()
