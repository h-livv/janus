"""Machine-readable result persistence."""

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from transport.validation.case import MetricEvaluation
from transport.validation.diagnostics import SCHEMA_VERSION


class ResultStore:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_results_json(self, evaluations: list[MetricEvaluation], converged: bool = None):
        records = []
        for ev in evaluations:
            records.append({
                "name": ev.name,
                "value": ev.value,
                "unit": ev.unit,
                "scope": ev.scope,
                "is_verification": ev.is_verification,
                "status": ev.status,
                "tolerance": ev.tolerance.threshold if ev.tolerance else None,
                "skip_reason": ev.skip_reason,
            })
        payload = {"metrics": records}
        if converged is not None:
            payload["convergence_passed"] = converged
        with open(self.output_dir / "results.json", "w") as f:
            json.dump(payload, f, indent=2)

    def save_metrics_csv(self, evaluations: list[MetricEvaluation]):
        path = self.output_dir / "metrics.csv"
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "name", "value", "unit", "scope", "status", "tolerance", "is_verification",
            ])
            writer.writeheader()
            for ev in evaluations:
                writer.writerow({
                    "name": ev.name,
                    "value": ev.value,
                    "unit": ev.unit,
                    "scope": ev.scope,
                    "status": ev.status,
                    "tolerance": ev.tolerance.threshold if ev.tolerance else "",
                    "is_verification": ev.is_verification,
                })

    def save_manifest(self, case, numerical_config, particle_source_desc, seed=None,
                      species=None, mass=None):
        git_hash = _git_hash()
        mass_record = None
        if mass is not None:
            mass_record = [float(m) for m in np.asarray(mass).ravel()]
        manifest = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_name": case.name,
            "case_level": case.level,
            "diagnostics_schema_version": SCHEMA_VERSION,
            "numerical_config": {
                "dt": numerical_config.dt,
                "max_steps": numerical_config.max_steps,
                "max_steps_conv": numerical_config.max_steps_conv,
                "solver_name": numerical_config.solver_name,
            },
            "particle_source": particle_source_desc,
            "species": species,
            "mass_kg": mass_record,
            "git_hash": git_hash,
            "seed": seed,
            "case_metadata": _json_safe(case.metadata),
        }
        with open(self.output_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

    def save_report(self, text: str):
        with open(self.output_dir / "report.txt", "w") as f:
            f.write(text)


def _git_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()
                if not callable(v) and not isinstance(v, type)}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj if not callable(v)]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)
