import os
os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"
import h5py
import hashlib
import json
import numpy as np
from pathlib import Path

# Physical Invariants
M_PBAR = 938.2720813  # Mass of antiproton / proton in MeV/c^2
Q_PBAR = -1.0         # Elementary charge equivalent

# PDG codes of interest
_PDG_ANTIPROTON = -2212
_PDG_PROTON     =  2212

# Cache version tag — bump whenever the output schema changes to force
# invalidation of stale on-disk caches automatically.
# v4: momentum cut tightened to [3480, 3680] MeV/c
_CACHE_VERSION = "v4"

# Fixed cache filename — does not encode N so the cache survives new batches
_CACHE_FILENAME = f"merged_seeds_cache_{_CACHE_VERSION}.npz"
_MANIFEST_FILENAME = f"merged_seeds_manifest_{_CACHE_VERSION}.json"


def get_run_files(outputs_dir_name="runs", target_filename="simulation.hdf5"):
    base_dir     = Path(__file__).resolve().parent.parent.parent
    outputs_path = base_dir / outputs_dir_name

    if not outputs_path.exists() or not outputs_path.is_dir():
        raise FileNotFoundError(f"[-] Fatal: Outputs directory not found at {outputs_path}")

    target_files = []
    for d in outputs_path.iterdir():
        if d.is_dir():
            f = d / target_filename
            if f.exists():
                target_files.append(f)

    if not target_files:
        raise FileNotFoundError(f"[-] Fatal: No {target_filename} found in {outputs_path}")

    return target_files


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _normalize_path(p) -> str:
    """Convert a path to a relative POSIX-style path starting from 'runs/' to be OS-independent."""
    p_str = str(p).replace("\\", "/")
    if "runs/" in p_str:
        return "runs/" + p_str.split("runs/", 1)[1]
    return p_str


def _file_fingerprint(path: Path) -> str:
    """Return a stable fingerprint for a single HDF5 file using its mtime + size."""
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _fingerprints_match(fp1: str, fp2: str) -> bool:
    """Return True if the fingerprints match (size equal, mtime within 1 second tolerance)."""
    try:
        size1_str, mtime1_str = fp1.split(':')
        size2_str, mtime2_str = fp2.split(':')
        if size1_str != size2_str:
            return False
        # Convert nanosecond strings to float seconds and check tolerance
        t1 = float(mtime1_str) / 1e9
        t2 = float(mtime2_str) / 1e9
        return abs(t1 - t2) < 1.0
    except Exception:
        return False


def _build_manifest(hdf5_paths):
    """
    Build a dict that maps each normalized filepath string to its fingerprint.
    This is the ground truth that the cache was built from.
    """
    return {_normalize_path(p): _file_fingerprint(p) for p in hdf5_paths}


def _manifest_is_stale(manifest: dict, hdf5_paths) -> tuple[bool, list]:
    """
    Compare a stored manifest against the current set of HDF5 files.
    Returns (is_stale, new_files) where new_files are paths not yet in the cache.

    is_stale=True means the cache must be fully rebuilt (a file was modified or removed).
    is_stale=False + new_files=[] means the cache is fully up-to-date.
    is_stale=False + new_files=[...] means only incremental new files need to be merged.
    """
    # Normalize keys in stored manifest to support legacy absolute paths
    normalized_manifest = {_normalize_path(k): v for k, v in manifest.items()}
    current_fps = {_normalize_path(p): _file_fingerprint(p) for p in hdf5_paths}

    # Check for modifications or deletions of files that were previously cached
    for path_str, cached_fp in normalized_manifest.items():
        if path_str not in current_fps:
            print(f"[DataIO] Cache stale: previously cached file no longer present: {path_str}")
            return True, []
        if not _fingerprints_match(current_fps[path_str], cached_fp):
            print(f"[DataIO] Cache stale: file modified since last cache: {path_str} (cached: {cached_fp}, current: {current_fps[path_str]})")
            return True, []

    # Identify genuinely new files not present in the manifest at all
    new_files = [p for p in hdf5_paths if _normalize_path(p) not in normalized_manifest]
    return False, new_files


def _parse_single_hdf5(hdf5_filepath: Path):
    """
    Parse one HDF5 file.  Returns (positions, velocities, gammas, charges)
    as float32/int8 arrays, or None if the file has no usable data.
    """
    c_light = 299792458.0
    p_min, p_max = 3480.0, 3680.0  # ±100 MeV/c around 3580 MeV/c nominal

    with h5py.File(hdf5_filepath, 'r') as f:
        if 'default_ntuples' not in f or 'Seeds' not in f['default_ntuples']:
            return None

        group     = f['default_ntuples']['Seeds']
        pdg_array = group['pdg_code']['pages'][()]

        is_antiproton = (pdg_array == _PDG_ANTIPROTON)
        is_proton     = (pdg_array == _PDG_PROTON)
        charged_mask  = is_antiproton | is_proton

        if not np.any(charged_mask):
            print(f"[DataIO]   Skipping {hdf5_filepath.name}: no antiprotons or protons.")
            return None

        pdg_charged = pdg_array[charged_mask]

        x_m  = group['start_x']['pages'][()][charged_mask] * 1e-3
        y_m  = group['start_y']['pages'][()][charged_mask] * 1e-3
        z_m  = group['start_z']['pages'][()][charged_mask] * 1e-3

        px_mevc = group['start_px']['pages'][()][charged_mask]
        py_mevc = group['start_py']['pages'][()][charged_mask]
        pz_mevc = group['start_pz']['pages'][()][charged_mask]

    positions_raw = np.column_stack((x_m, y_m, z_m)).astype(np.float32)
    P_mevc        = np.column_stack((px_mevc, py_mevc, pz_mevc))
    p_squared     = np.sum(P_mevc**2, axis=1)
    p_total       = np.sqrt(p_squared)

    p_mask      = (p_total >= p_min) & (p_total <= p_max)
    positions_f = positions_raw[p_mask]
    P_mevc_f    = P_mevc[p_mask]
    p_sq_f      = p_squared[p_mask]
    pdg_f       = pdg_charged[p_mask]

    E_total    = np.sqrt(p_sq_f + M_PBAR**2)
    gammas     = (E_total / M_PBAR).astype(np.float32)
    velocities = (P_mevc_f * (c_light / E_total[:, np.newaxis])).astype(np.float32)
    charges    = np.where(pdg_f == _PDG_ANTIPROTON, -1, 1).astype(np.int8)

    n_pbar = int(np.sum(pdg_f == _PDG_ANTIPROTON))
    n_prot = int(np.sum(pdg_f == _PDG_PROTON))
    print(f"[DataIO]   {hdf5_filepath.name}: "
          f"{n_pbar} antiprotons + {n_prot} protons (after momentum cut)")

    return positions_f, velocities, gammas, charges


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_cern_ad_seeds(hdf5_filepaths=None):
    """
    Parse one or more Geant4 HDF5 output files and return:
      positions  : np.float32 (N, 3)  — [m]
      velocities : np.float32 (N, 3)  — [m/s]
      gammas     : np.float32 (N,)
      charges    : np.int8    (N,)    — {-1, +1} (neutrals mathematically discarded)

    Caching strategy
    ----------------
    A fixed-name .npz cache and a companion JSON manifest are stored in the
    runs/ directory.  The manifest records {filepath: (size, mtime_ns)} for
    every HDF5 file that contributed to the cache.

    On each call:
      1. Stat all HDF5 files (fast — no file reads).
      2. If cache + manifest exist and every previously seen file is unmodified:
           a. If there are NEW files (batches added since last run):
              → Parse only the new files, concatenate with cached data, save.
           b. Otherwise:
              → Return the cache directly. Zero HDF5 I/O.
      3. If any previously cached file was modified or deleted:
           → Full rebuild from all files.

    This means adding a new Geant4 batch only ever parses that one new file,
    not the entire history.
    """
    if hdf5_filepaths is None:
        hdf5_filepaths = get_run_files()
    elif not isinstance(hdf5_filepaths, list):
        hdf5_filepaths = [hdf5_filepaths]

    if not hdf5_filepaths:
        return np.array([]), np.array([]), np.array([]), np.array([], dtype=np.int8)

    # Cache lives alongside the HDF5 runs in the parent runs/ directory
    cache_dir     = hdf5_filepaths[0].parent.parent
    cache_path    = cache_dir / _CACHE_FILENAME
    manifest_path = cache_dir / _MANIFEST_FILENAME

    # ── 1. Load existing manifest (if any) ───────────────────────────────
    stored_manifest = {}
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as mf:
                stored_manifest = json.load(mf)
        except (json.JSONDecodeError, OSError):
            stored_manifest = {}

    # ── 2. Determine cache state ──────────────────────────────────────────
    cache_exists = cache_path.exists() and bool(stored_manifest)

    is_stale = True
    new_files = hdf5_filepaths
    if cache_exists:
        is_stale, new_files = _manifest_is_stale(stored_manifest, hdf5_filepaths)

    if cache_exists and not is_stale:
        if not new_files:
            print(f"[DataIO] Cache hit — loading {cache_path.name} (zero HDF5 I/O)")
            with np.load(cache_path) as data:
                return (data['positions'], data['velocities'],
                        data['gammas'],    data['charges'])
        else:
            # ── INCREMENTAL PATH: only parse the new batch(es) ───────────
            print(f"[DataIO] Incremental update — "
                  f"parsing {len(new_files)} new file(s), reusing cached data for "
                  f"{len(stored_manifest)} existing file(s).")

            with np.load(cache_path) as existing:
                cached_pos = existing['positions']
                cached_vel = existing['velocities']
                cached_gam = existing['gammas']
                cached_chg = existing['charges']

            new_pos, new_vel, new_gam, new_chg = [], [], [], []
            for fp in new_files:
                result = _parse_single_hdf5(fp)
                if result is not None:
                    new_pos.append(result[0]);  new_vel.append(result[1])
                    new_gam.append(result[2]);  new_chg.append(result[3])

            if new_pos:
                final_pos = np.concatenate([cached_pos] + new_pos,  axis=0)
                final_vel = np.concatenate([cached_vel] + new_vel,  axis=0)
                final_gam = np.concatenate([cached_gam] + new_gam,  axis=0)
                final_chg = np.concatenate([cached_chg] + new_chg,  axis=0)
            else:
                final_pos, final_vel, final_gam, final_chg = (
                    cached_pos, cached_vel, cached_gam, cached_chg)

            # Save updated cache + manifest
            new_manifest = _build_manifest(hdf5_filepaths)
            _save_cache(cache_path, manifest_path, new_manifest,
                        final_pos, final_vel, final_gam, final_chg)
            return final_pos, final_vel, final_gam, final_chg

    # ── FULL REBUILD PATH ─────────────────────────────────────────────────
    reason = "no cache found" if not cache_exists else "cache is stale"
    print(f"[DataIO] Full rebuild ({reason}) — "
          f"parsing {len(hdf5_filepaths)} HDF5 file(s)…")

    all_pos, all_vel, all_gam, all_chg = [], [], [], []
    for fp in hdf5_filepaths:
        result = _parse_single_hdf5(fp)
        if result is not None:
            all_pos.append(result[0]);  all_vel.append(result[1])
            all_gam.append(result[2]);  all_chg.append(result[3])

    if not all_pos:
        return (np.array([]), np.array([]),
                np.array([]), np.array([], dtype=np.int8))

    final_pos = np.concatenate(all_pos,  axis=0)
    final_vel = np.concatenate(all_vel,  axis=0)
    final_gam = np.concatenate(all_gam,  axis=0)
    final_chg = np.concatenate(all_chg,  axis=0)

    new_manifest = _build_manifest(hdf5_filepaths)
    _save_cache(cache_path, manifest_path, new_manifest,
                final_pos, final_vel, final_gam, final_chg)

    return final_pos, final_vel, final_gam, final_chg


def _save_cache(cache_path, manifest_path, manifest,
                positions, velocities, gammas, charges):
    """Atomically write the .npz cache and its companion manifest."""
    np.savez(cache_path,
             positions  = positions,
             velocities = velocities,
             gammas     = gammas,
             charges    = charges)
    with open(manifest_path, 'w') as mf:
        json.dump(manifest, mf, indent=2)
    n_total = positions.shape[0]
    n_pbar  = int(np.sum(charges == -1))
    n_prot  = int(np.sum(charges == +1))
    print(f"[DataIO] Cache saved -> {cache_path.name}  "
          f"({n_total} particles: {n_pbar} pbar + {n_prot} p)")


def get_latest_run_file(outputs_dir_name="runs", target_filename="simulation.hdf5"):
    target_files = get_run_files(outputs_dir_name, target_filename)
    if not target_files:
        raise FileNotFoundError(f"No {target_filename} found in {outputs_dir_name}")
    return max(target_files, key=os.path.getmtime)
