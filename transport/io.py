import os
os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"

# Override print to suppress [DataIO] prints by default unless verbose mode is set
if os.environ.get("DATAIO_VERBOSE", "0") != "1":
    def print(*args, **kwargs):
        pass
import uproot
import json
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Physical Invariants
M_PBAR = 938.2720813  # Mass of antiproton / proton in MeV/c^2
Q_PBAR = -1.0         # Elementary charge equivalent

# PDG codes of interest
_PDG_ANTIPROTON = -2212
_PDG_PROTON     =  2212

# Cache version tag — bump whenever the output schema changes to force
# invalidation of stale on-disk caches automatically.
# v6: no momentum cut at ROOT extraction (experiment applies momentum_slice)
_CACHE_VERSION = "v6"

# Fixed cache filename — does not encode N so the cache survives new batches
_CACHE_FILENAME = f"merged_seeds_cache_{_CACHE_VERSION}.npz"
_MANIFEST_FILENAME = f"merged_seeds_manifest_{_CACHE_VERSION}.json"

_REQUIRED_NPZ_KEYS = ("positions", "velocities", "gammas", "charges")
_OPTIONAL_NPZ_KEYS = ("momenta_mevc", "start_z")


@dataclass
class SeedArrays:
    """Validated Geant4 seed arrays at the Janus/Xsuite boundary.

    positions: (N, 3) float32, meters
    velocities: (N, 3) float32, m/s (legacy; used when momenta_mevc absent)
    gammas: (N,) float32
    charges: (N,) int8, elementary charge sign {-1, +1}
    momenta_mevc: optional (N, 3) float32, MeV/c
    start_z: optional (N,) float32, original Geant4 longitudinal injection [m]
    source_path: optional path to ROOT or NPZ source file
    """

    positions: np.ndarray
    velocities: np.ndarray
    gammas: np.ndarray
    charges: np.ndarray
    momenta_mevc: Optional[np.ndarray] = None
    start_z: Optional[np.ndarray] = None
    source_path: Optional[str] = None


def load_seed_npz(path: str | Path) -> SeedArrays:
    """Load and validate a Janus seed NPZ file for Xsuite conversion."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Seed NPZ not found: {path}")

    with np.load(path) as data:
        missing = [k for k in _REQUIRED_NPZ_KEYS if k not in data]
        if missing:
            raise ValueError(f"Seed NPZ missing required keys: {missing}")

        positions = np.asarray(data["positions"], dtype=np.float32)
        velocities = np.asarray(data["velocities"], dtype=np.float32)
        gammas = np.asarray(data["gammas"], dtype=np.float32)
        charges = np.asarray(data["charges"], dtype=np.int8)

        n = positions.shape[0]
        if n == 0:
            raise ValueError("Seed NPZ contains zero particles")
        if positions.shape != (n, 3):
            raise ValueError(f"positions must be (N, 3), got {positions.shape}")
        if velocities.shape != (n, 3):
            raise ValueError(f"velocities must be (N, 3), got {velocities.shape}")
        if gammas.shape != (n,):
            raise ValueError(f"gammas must be (N,), got {gammas.shape}")
        if charges.shape != (n,):
            raise ValueError(f"charges must be (N,), got {charges.shape}")

        for name, arr in (("positions", positions), ("velocities", velocities), ("gammas", gammas)):
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"Non-finite values in '{name}'")

        if not np.isin(charges, (-1, 1)).all():
            raise ValueError("charges must be elementary signs {-1, +1}")

        momenta_mevc = None
        if "momenta_mevc" in data:
            momenta_mevc = np.asarray(data["momenta_mevc"], dtype=np.float32)
            if momenta_mevc.shape != (n, 3):
                raise ValueError(f"momenta_mevc must be (N, 3), got {momenta_mevc.shape}")
            if not np.all(np.isfinite(momenta_mevc)):
                raise ValueError("Non-finite values in 'momenta_mevc'")

        start_z = None
        if "start_z" in data:
            start_z = np.asarray(data["start_z"], dtype=np.float32)
            if start_z.shape != (n,):
                raise ValueError(f"start_z must be (N,), got {start_z.shape}")
        else:
            start_z = positions[:, 2].copy()

    return SeedArrays(
        positions=positions,
        velocities=velocities,
        gammas=gammas,
        charges=charges,
        momenta_mevc=momenta_mevc,
        start_z=start_z,
        source_path=str(path),
    )


def get_run_files(outputs_dir_name="interactions/runs", target_filename="simulation.root"):
    base_dir     = Path(__file__).resolve().parent.parent
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
    """Convert a path to a relative POSIX-style path starting from 'interactions/runs/' to be OS-independent."""
    p_str = str(p).replace("\\", "/")
    if "interactions/runs/" in p_str:
        return "interactions/runs/" + p_str.split("interactions/runs/", 1)[1]
    if "runs/" in p_str:
        return "interactions/runs/" + p_str.split("runs/", 1)[1]
    return p_str


def _file_fingerprint(path: Path) -> str:
    """Return a stable fingerprint for a single ROOT file using its mtime + size."""
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


def _build_manifest(root_paths):
    """
    Build a dict that maps each normalized filepath string to its fingerprint.
    This is the ground truth that the cache was built from.
    """
    return {_normalize_path(p): _file_fingerprint(p) for p in root_paths}


def _manifest_is_stale(manifest: dict, root_paths) -> tuple[bool, list]:
    """
    Compare a stored manifest against the current set of ROOT files.
    Returns (is_stale, new_files) where new_files are paths not yet in the cache.

    is_stale=True means the cache must be fully rebuilt (a file was modified or removed).
    is_stale=False + new_files=[] means the cache is fully up-to-date.
    is_stale=False + new_files=[...] means only incremental new files need to be merged.
    """
    # Normalize keys in stored manifest to support legacy absolute paths
    normalized_manifest = {_normalize_path(k): v for k, v in manifest.items()}
    current_fps = {_normalize_path(p): _file_fingerprint(p) for p in root_paths}

    # Check for modifications or deletions of files that were previously cached
    for path_str, cached_fp in normalized_manifest.items():
        if path_str not in current_fps:
            print(f"[DataIO] Cache stale: previously cached file no longer present: {path_str}")
            return True, []
        if not _fingerprints_match(current_fps[path_str], cached_fp):
            print(f"[DataIO] Cache stale: file modified since last cache: {path_str} (cached: {cached_fp}, current: {current_fps[path_str]})")
            return True, []

    # Identify genuinely new files not present in the manifest at all
    new_files = [p for p in root_paths if _normalize_path(p) not in normalized_manifest]
    return False, new_files


def _parse_single_root(root_filepath: Path):
    """
    Parse one ROOT file. Returns (positions, velocities, gammas, charges, momenta_mevc)
    as float32/int8 arrays, or None if the file has no usable data.

    Extracts proton and antiproton birth states only (PDG ±2212). Does not apply
    momentum selection — that is an experiment parameter applied in the pipeline.
    """
    c_light = 299792458.0

    with uproot.open(root_filepath) as f:
        if 'Seeds' not in f:
            return None

        group     = f['Seeds']
        pdg_array = group['pdg_code'].array(library="np")

        is_antiproton = (pdg_array == _PDG_ANTIPROTON)
        is_proton     = (pdg_array == _PDG_PROTON)
        charged_mask  = is_antiproton | is_proton

        if not np.any(charged_mask):
            print(f"[DataIO]   Skipping {root_filepath.name}: no antiprotons or protons.")
            return None

        pdg_charged = pdg_array[charged_mask]

        x_m  = group['start_x'].array(library="np")[charged_mask] * 1e-3
        y_m  = group['start_y'].array(library="np")[charged_mask] * 1e-3
        z_m  = group['start_z'].array(library="np")[charged_mask] * 1e-3

        px_mevc = group['start_px'].array(library="np")[charged_mask]
        py_mevc = group['start_py'].array(library="np")[charged_mask]
        pz_mevc = group['start_pz'].array(library="np")[charged_mask]

    positions_f = np.column_stack((x_m, y_m, z_m)).astype(np.float32)
    P_mevc_f    = np.column_stack((px_mevc, py_mevc, pz_mevc)).astype(np.float32)
    p_sq_f      = np.sum(P_mevc_f.astype(np.float64)**2, axis=1)
    pdg_f       = pdg_charged

    E_total    = np.sqrt(p_sq_f + M_PBAR**2)
    gammas     = (E_total / M_PBAR).astype(np.float32)
    velocities = (P_mevc_f * (c_light / E_total[:, np.newaxis])).astype(np.float32)
    charges    = np.where(pdg_f == _PDG_ANTIPROTON, -1, 1).astype(np.int8)

    n_pbar = int(np.sum(pdg_f == _PDG_ANTIPROTON))
    n_prot = int(np.sum(pdg_f == _PDG_PROTON))
    print(f"[DataIO]   {root_filepath.name}: "
          f"{n_pbar} antiprotons + {n_prot} protons")

    return positions_f, velocities, gammas, charges, P_mevc_f


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_cern_ad_seeds(root_filepaths=None):
    """
    Parse one or more Geant4 ROOT output files and return:
      positions     : np.float32 (N, 3)  — [m]
      velocities    : np.float32 (N, 3)  — [m/s]
      gammas        : np.float32 (N,)
      charges       : np.int8    (N,)    — {-1, +1}
      momenta_mevc  : np.float32 (N, 3)  — [MeV/c]

    Caching strategy
    ----------------
    A fixed-name .npz cache and a companion JSON manifest are stored in the
    interactions/runs/ directory.  The manifest records {filepath: (size, mtime_ns)} for
    every ROOT file that contributed to the cache.

    On each call:
      1. Stat all ROOT files (fast — no file reads).
      2. If cache + manifest exist and every previously seen file is unmodified:
           a. If there are NEW files (batches added since last run):
              → Parse only the new files, concatenate with cached data, save.
           b. Otherwise:
               → Return the cache directly. Zero ROOT I/O.
      3. If any previously cached file was modified or deleted:
           → Full rebuild from all files.

    This means adding a new Geant4 batch only ever parses that one new file,
    not the entire history.
    """
    if root_filepaths is None:
        root_filepaths = get_run_files()
    elif not isinstance(root_filepaths, list):
        root_filepaths = [root_filepaths]

    if not root_filepaths:
        empty_f = np.array([], dtype=np.float32).reshape(0, 3)
        return empty_f, empty_f, np.array([]), np.array([], dtype=np.int8), empty_f

    # Cache lives inside the unique run directory
    cache_dir     = root_filepaths[0].parent
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
    new_files = root_filepaths
    if cache_exists:
        is_stale, new_files = _manifest_is_stale(stored_manifest, root_filepaths)

    if cache_exists and not is_stale:
        if not new_files:
            print(f"[DataIO] Cache hit — loading {cache_path.name} (zero ROOT I/O)")
            with np.load(cache_path) as data:
                momenta = data["momenta_mevc"] if "momenta_mevc" in data else None
                if momenta is None:
                    momenta = _reconstruct_momenta_mevc(
                        data["velocities"], data["gammas"], data["charges"]
                    )
                return (
                    data["positions"], data["velocities"],
                    data["gammas"], data["charges"], momenta,
                )
        else:
            # ── INCREMENTAL PATH: only parse the new batch(es) ───────────
            print(f"[DataIO] Incremental update — "
                  f"parsing {len(new_files)} new file(s), reusing cached data for "
                  f"{len(stored_manifest)} existing file(s).")

            with np.load(cache_path) as existing:
                cached_pos = existing["positions"]
                cached_vel = existing["velocities"]
                cached_gam = existing["gammas"]
                cached_chg = existing["charges"]
                if "momenta_mevc" in existing:
                    cached_mom = existing["momenta_mevc"]
                else:
                    cached_mom = _reconstruct_momenta_mevc(cached_vel, cached_gam, cached_chg)

            new_pos, new_vel, new_gam, new_chg, new_mom = [], [], [], [], []
            for fp in new_files:
                result = _parse_single_root(fp)
                if result is not None:
                    new_pos.append(result[0]); new_vel.append(result[1])
                    new_gam.append(result[2]); new_chg.append(result[3])
                    new_mom.append(result[4])

            if new_pos:
                final_pos = np.concatenate([cached_pos] + new_pos, axis=0)
                final_vel = np.concatenate([cached_vel] + new_vel, axis=0)
                final_gam = np.concatenate([cached_gam] + new_gam, axis=0)
                final_chg = np.concatenate([cached_chg] + new_chg, axis=0)
                final_mom = np.concatenate([cached_mom] + new_mom, axis=0)
            else:
                final_pos, final_vel, final_gam, final_chg, final_mom = (
                    cached_pos, cached_vel, cached_gam, cached_chg, cached_mom)

            new_manifest = _build_manifest(root_filepaths)
            _save_cache(cache_path, manifest_path, new_manifest,
                        final_pos, final_vel, final_gam, final_chg, final_mom)
            return final_pos, final_vel, final_gam, final_chg, final_mom

    # ── FULL REBUILD PATH ─────────────────────────────────────────────────
    reason = "no cache found" if not cache_exists else "cache is stale"
    print(f"[DataIO] Full rebuild ({reason}) — "
          f"parsing {len(root_filepaths)} ROOT file(s)…")

    all_pos, all_vel, all_gam, all_chg, all_mom = [], [], [], [], []
    for fp in root_filepaths:
        result = _parse_single_root(fp)
        if result is not None:
            all_pos.append(result[0]); all_vel.append(result[1])
            all_gam.append(result[2]); all_chg.append(result[3])
            all_mom.append(result[4])

    if not all_pos:
        empty_f = np.array([], dtype=np.float32).reshape(0, 3)
        return empty_f, empty_f, np.array([]), np.array([], dtype=np.int8), empty_f

    final_pos = np.concatenate(all_pos, axis=0)
    final_vel = np.concatenate(all_vel, axis=0)
    final_gam = np.concatenate(all_gam, axis=0)
    final_chg = np.concatenate(all_chg, axis=0)
    final_mom = np.concatenate(all_mom, axis=0)

    new_manifest = _build_manifest(root_filepaths)
    _save_cache(cache_path, manifest_path, new_manifest,
                final_pos, final_vel, final_gam, final_chg, final_mom)

    return final_pos, final_vel, final_gam, final_chg, final_mom


def _reconstruct_momenta_mevc(velocities, gammas, charges):
    """Reconstruct MeV/c momenta from legacy cache without momenta_mevc."""
    c_light = 299792458.0
    m_kg = 1.67262192369e-27
    p_si = gammas[:, np.newaxis] * m_kg * velocities
    return (p_si * c_light / 1e6).astype(np.float32)


def _save_cache(cache_path, manifest_path, manifest,
                positions, velocities, gammas, charges, momenta_mevc):
    """Atomically write the .npz cache and its companion manifest."""
    start_z = positions[:, 2].astype(np.float32)
    np.savez(
        cache_path,
        positions=positions,
        velocities=velocities,
        gammas=gammas,
        charges=charges,
        momenta_mevc=momenta_mevc,
        start_z=start_z,
    )
    with open(manifest_path, 'w') as mf:
        json.dump(manifest, mf, indent=2)
    n_total = positions.shape[0]
    n_pbar  = int(np.sum(charges == -1))
    n_prot  = int(np.sum(charges == +1))
    print(f"[DataIO] Cache saved -> {cache_path.name}  "
          f"({n_total} particles: {n_pbar} pbar + {n_prot} p)")


def get_latest_run_file(outputs_dir_name="interactions/runs", target_filename="simulation.root"):
    target_files = get_run_files(outputs_dir_name, target_filename)
    if not target_files:
        raise FileNotFoundError(f"No {target_filename} found in {outputs_dir_name}")
    return max(target_files, key=os.path.getmtime)


# ---------------------------------------------------------------------------
# Species table (mass / charge)
# ---------------------------------------------------------------------------

M_P_KG = 1.67262192369e-27
M_P_MEV = 938.2720813
M_E_KG = 9.1093837015e-31
M_E_MEV = 0.51099895000
M_MU_KG = 1.883531627e-28
M_MU_MEV = 105.6583745
M_PI_KG = 2.476990084e-28
M_PI_MEV = 139.57039

_SPECIES = {
    "antiproton": (M_P_KG, M_P_MEV, -1),
    "proton": (M_P_KG, M_P_MEV, 1),
    "electron": (M_E_KG, M_E_MEV, -1),
    "positron": (M_E_KG, M_E_MEV, 1),
    "muon-": (M_MU_KG, M_MU_MEV, -1),
    "muon+": (M_MU_KG, M_MU_MEV, 1),
    "pion-": (M_PI_KG, M_PI_MEV, -1),
    "pion+": (M_PI_KG, M_PI_MEV, 1),
}


def mass_of(species: str) -> float:
    key = species.lower()
    if key not in _SPECIES:
        raise KeyError(f"Unknown species '{species}'. Available: {sorted(_SPECIES)}")
    return _SPECIES[key][0]


def mass_mev_of(species: str) -> float:
    key = species.lower()
    if key not in _SPECIES:
        raise KeyError(f"Unknown species '{species}'. Available: {sorted(_SPECIES)}")
    return _SPECIES[key][1]


def charge_of(species: str) -> int:
    key = species.lower()
    if key not in _SPECIES:
        raise KeyError(f"Unknown species '{species}'. Available: {sorted(_SPECIES)}")
    return _SPECIES[key][2]


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

_C_LIGHT = 299792458.0


def load_geant4_seeds() -> SeedArrays:
    """Load proton/antiproton birth-state seeds from the latest Geant4 ROOT run.

    Does not select species or momentum window — the experiment does that.
    """
    root_file = get_latest_run_file()
    positions, velocities, gammas, charges, momenta_mevc = extract_cern_ad_seeds([root_file])
    return SeedArrays(
        positions=positions,
        velocities=velocities,
        gammas=gammas,
        charges=charges,
        momenta_mevc=momenta_mevc,
        start_z=positions[:, 2].copy() if len(positions) else None,
        source_path=str(root_file),
    )


def single_particle_seeds(
    *,
    particle: str,
    position: list[float],
    velocity: list[float],
    gamma: float,
) -> SeedArrays:
    """Build a one-particle seed batch for smoke tests."""
    pos = np.array([position], dtype=np.float32)
    vel = np.array([velocity], dtype=np.float32)
    gammas = np.array([gamma], dtype=np.float32)
    charges = np.array([charge_of(particle)], dtype=np.int8)
    m_kg = mass_of(particle)
    p_mevc = (gamma * m_kg * vel * _C_LIGHT / 1e6).reshape(1, 3).astype(np.float32)
    return SeedArrays(
        positions=pos,
        velocities=vel,
        gammas=gammas,
        charges=charges,
        momenta_mevc=p_mevc,
        start_z=pos[:, 2].copy(),
        source_path=None,
    )
