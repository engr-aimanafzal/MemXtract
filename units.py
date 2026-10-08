"""Deterministic unit conversion. The LLM never converts units - this code does.

Every function returns (value, flag). `flag` is None when the conversion is clean,
otherwise a short string explaining the assumption or problem.
"""
from __future__ import annotations

import re


def num(value):
    """Extract a float from a number or a messy string such as '≈ 3.5' or '1,000'."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("−", "-")
    if re.fullmatch(r"-?\d+,\d{1,2}", s):
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def clean_unit(u) -> str:
    u = (u or "").strip().lower()
    for a, b in (("·", ""), ("⋅", ""), ("²", "2"), ("³", "3"), ("−", "-"), ("µ", "u"), ("μ", "u"),
                 ("°", ""), ("º", ""), ("deg", "")):
        u = u.replace(a, b)
    return re.sub(r"[\s\.\(\)\[\]]", "", u)


_PRESSURE = {"bar": 1.0, "bars": 1.0, "mbar": 0.001, "kpa": 0.01, "mpa": 10.0, "pa": 1e-5,
             "psi": 0.0689476, "atm": 1.01325, "kgf/cm2": 0.980665}


def to_bar(value, unit):
    v = num(value)
    if v is None:
        return None, None
    u = clean_unit(unit)
    if not u:
        return v, "pressure_unit_assumed_bar"
    f = _PRESSURE.get(u)
    if f is None:
        return None, f"pressure_unit_unknown:{unit}"
    return v * f, None


def to_percent(value, unit):
    v = num(value)
    if v is None:
        return None, None
    u = clean_unit(unit)
    if u in ("%", "percent", "pct", "wt%"):
        return v, None
    if u in ("fraction", "-"):
        return v * 100.0, None
    if not u:
        if v <= 1.0:
            return v * 100.0, "rejection_unit_missing_assumed_fraction"
        return v, "rejection_unit_missing_assumed_percent"
    return None, f"rejection_unit_unknown:{unit}"


_FLUX = {
    "lmh": 1.0, "l/m2h": 1.0, "l/m2/h": 1.0, "l/m2hr": 1.0, "l/m2/hr": 1.0, "lm-2h-1": 1.0,
    "kg/m2h": 1.0, "kg/m2/h": 1.0,
    "l/m2/day": 1 / 24, "l/m2d": 1 / 24, "lmd": 1 / 24, "lm-2d-1": 1 / 24,
    "m3/m2/day": 1000 / 24, "m3/m2d": 1000 / 24, "m/day": 1000 / 24,
    "m3/m2/s": 3.6e6, "m/s": 3.6e6,
    "ml/cm2/min": 600.0, "ml/cm2min": 600.0,
    "gfd": 1.6977, "gal/ft2/day": 1.6977,
}


def to_lmh(value, unit):
    v = num(value)
    if v is None:
        return None, None
    u = clean_unit(unit)
    if not u:
        return None, "flux_unit_missing"
    f = _FLUX.get(u)
    if f is None:
        return None, f"flux_unit_unknown:{unit}"
    return v * f, None


_CONC = {
    "mg/l": 1.0, "mgl-1": 1.0, "ppm": 1.0, "g/m3": 1.0,
    "g/l": 1000.0, "gl-1": 1000.0, "kg/m3": 1000.0, "mg/ml": 1000.0,
    "ug/l": 0.001, "ugl-1": 0.001, "ppb": 0.001,
}


def to_mg_per_l(value, unit):
    v = num(value)
    if v is None:
        return None, None
    u = clean_unit(unit)
    if u in _CONC:
        return v * _CONC[u], None
    if u in ("wt%", "%", "w/v%", "wt.%"):
        return v * 10000.0, "conc_percent_approximate"
    # mol/L, mM, etc. need the molar mass - keep the raw text, skip numeric conversion
    return None, f"conc_unit_not_converted:{unit}" if u else "conc_unit_missing"


def to_celsius(value, unit):
    v = num(value)
    if v is None:
        return None, None
    u = clean_unit(unit)
    if u in ("c", "celsius"):
        return v, None
    if u in ("k", "kelvin"):
        return v - 273.15, None
    if u in ("f", "fahrenheit"):
        return (v - 32) * 5 / 9, None
    if not u:
        return v, "temperature_unit_assumed_celsius"
    return None, f"temperature_unit_unknown:{unit}"
