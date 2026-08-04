"""Write aggregated study results as CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def write_study_csv(rows: list[dict[str, Any]], output_path: str | Path) -> str:
    """Write study rows to ``study_results.csv`` (or a custom path)."""
    path = Path(output_path)
    if not rows:
        path.write_text("")
        return str(path)

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)
