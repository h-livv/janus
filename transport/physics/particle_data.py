"""Authoritative species mass and charge table."""

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
