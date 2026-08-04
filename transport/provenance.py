"""Minimal per-run provenance records for reproducibility."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "1.0"


def canonicalize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable, stably ordered parameter dict."""
    def _normalize(value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [_normalize(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _normalize(v) for k, v in sorted(value.items())}
        if isinstance(value, (int, float, str, bool)) or value is None:
            return value
        return str(value)

    return {str(k): _normalize(v) for k, v in sorted(params.items())}


def fingerprint_params(params: dict[str, Any]) -> str:
    encoded = json.dumps(canonicalize_params(params), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def fingerprint_source(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    stat = p.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def get_git_commit() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def get_package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in ("numpy", "xtrack", "xpart"):
        try:
            mod = __import__(name)
            versions[name] = str(getattr(mod, "__version__", "unknown"))
        except ImportError:
            versions[name] = "not_installed"
    return versions


def build_run_provenance(
    *,
    run_id: str,
    experiment_name: str,
    parameters: dict[str, Any],
    beamline_hash: str,
    source_path: Optional[str] = None,
    random_seed: Optional[int] = None,
    output_artifacts: Optional[dict[str, str]] = None,
    metrics_path: Optional[str] = None,
) -> dict[str, Any]:
    """Build a minimal provenance record for one transport run."""
    canonical = canonicalize_params(parameters)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment_name": experiment_name,
        "parameters": canonical,
        "parameter_fingerprint": fingerprint_params(parameters),
        "random_seed": random_seed,
        "git_commit": get_git_commit(),
        "source_path": source_path,
        "source_fingerprint": fingerprint_source(source_path),
        "beamline_hash": beamline_hash,
        "package_versions": get_package_versions(),
        "output_artifacts": output_artifacts or {},
        "metrics_path": metrics_path,
    }


def write_run_provenance(provenance: dict[str, Any], output_dir: str | Path) -> str:
    """Write ``provenance.json`` beside normal run outputs."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "provenance.json"
    out_path.write_text(json.dumps(provenance, indent=2) + "\n")
    return str(out_path)


def load_run_provenance(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def make_run_id(output_dir: str | Path) -> str:
    """Derive a stable run ID from the output directory name."""
    name = Path(output_dir).name
    if name.startswith("run_"):
        return name
    return f"run_{name}"
