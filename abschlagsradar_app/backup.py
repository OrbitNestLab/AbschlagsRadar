"""Validate portable backups completely before restoring one selected contract."""

from radarcore.model import normalize_history, validate_settings

SETTINGS = {
    "name",
    "energy_type",
    "source_unit",
    "source_sensor",
    "price",
    "base",
    "base_period",
    "payment",
    "payment_day",
    "billing_start",
    "gas_mode",
    "gas_factor",
    "annual_estimate",
}


def read_backup(data):
    if not isinstance(data, dict) or data.get("format") != "abschlagsradar-backup" or data.get("version") != 1:
        raise ValueError("Keine unterstützte AbschlagsRadar-Sicherung.")
    contracts = data.get("contracts")
    if not isinstance(contracts, list) or not 1 <= len(contracts) <= 20:
        raise ValueError("Die Sicherung muss zwischen einem und 20 Verträgen enthalten.")
    result = []
    for row in contracts:
        if not isinstance(row, dict) or not isinstance(row.get("settings"), dict) or set(row["settings"]) - SETTINGS:
            raise ValueError("Ungültige Vertragsdaten in der Sicherung.")
        settings = validate_settings(row["settings"])
        history = normalize_history(row.get("history", {}))
        automatic = normalize_history({"readings": row.get("automatic_readings", [])})["readings"]
        merged = {reading["date"]: reading for reading in automatic}
        merged.update({reading["date"]: reading for reading in history["readings"]})
        history["readings"] = sorted(merged.values(), key=lambda reading: reading["date"])
        result.append({"settings": settings, "history": normalize_history(history)})
    return result
