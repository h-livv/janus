"""Series error helpers for optics comparison metrics."""

from __future__ import annotations

import numpy as np


def series_comparison_errors(y_janus: np.ndarray, y_ref: np.ndarray) -> dict:
    """
    RMS relative, max absolute, and max relative error between two 1-D series.

    Relative errors use |y_ref| in the denominator (floored).
    """
    yj = np.asarray(y_janus, dtype=np.float64)
    yr = np.asarray(y_ref, dtype=np.float64)
    if len(yj) == 0 or len(yr) == 0 or len(yj) != len(yr):
        return {
            "rms_relative": float("nan"),
            "max_absolute": float("nan"),
            "max_relative": float("nan"),
        }
    abs_err = np.abs(yj - yr)
    denom = np.maximum(np.abs(yr), 1e-30)
    rel = abs_err / denom
    return {
        "rms_relative": float(np.sqrt(np.mean(rel**2))),
        "max_absolute": float(np.max(abs_err)),
        "max_relative": float(np.max(rel)),
    }


def combine_plane_errors(err_x: dict, err_y: dict) -> dict:
    """Combine horizontal/vertical error dicts into a summary metric payload."""
    return {
        "x": err_x,
        "y": err_y,
        "rms_relative": float(np.nanmean([err_x["rms_relative"], err_y["rms_relative"]])),
        "max_absolute": float(np.nanmax([err_x["max_absolute"], err_y["max_absolute"]])),
        "max_relative": float(np.nanmax([err_x["max_relative"], err_y["max_relative"]])),
    }
