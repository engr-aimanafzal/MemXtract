"""Warns when records being compared were measured under different conditions."""
from __future__ import annotations


def _vals(records, key):
    return [r[key] for r in records if r.get(key) is not None]


def check(records: list) -> list:
    warnings = []
    if len(records) < 2:
        return warnings

    solutes = {(r.get("solute") or "").strip().lower() for r in records if r.get("solute")}
    if len(solutes) > 1:
        warnings.append("Different solutes are mixed (" + ", ".join(sorted(solutes)[:5])
                        + ") - rejection values are not directly comparable across solutes.")

    conc = _vals(records, "feed_conc_mg_l")
    if len(conc) >= 2 and min(conc) > 0 and max(conc) / min(conc) > 2:
        warnings.append(f"Feed concentrations differ by more than 2x ({min(conc):g} to {max(conc):g} mg/L).")

    temp = _vals(records, "temperature_c")
    if len(temp) >= 2 and max(temp) - min(temp) > 10:
        warnings.append(f"Temperatures differ by more than 10 C ({min(temp):g} to {max(temp):g} C).")

    ph = _vals(records, "ph")
    if len(ph) >= 2 and max(ph) - min(ph) > 2:
        warnings.append(f"pH values differ by more than 2 units ({min(ph):g} to {max(ph):g}).")

    pres = _vals(records, "pressure_bar")
    if len(pres) >= 2 and min(pres) > 0 and max(pres) / min(pres) > 2:
        warnings.append(f"Operating pressures differ by more than 2x ({min(pres):g} to {max(pres):g} bar).")

    missing = sum(1 for r in records if r.get("feed_conc_mg_l") is None and not r.get("feed_conc_raw"))
    if missing:
        warnings.append(f"{missing} of {len(records)} records have no stated feed concentration.")

    flagged = sum(1 for r in records if r.get("flags"))
    if flagged:
        warnings.append(f"{flagged} of {len(records)} records carry extraction flags (see the 'flags' column).")
    return warnings
