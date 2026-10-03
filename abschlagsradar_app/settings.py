"""Strict app onboarding; no bonus, credentials or arbitrary HA fields accepted."""

from datetime import datetime
from zoneinfo import ZoneInfo


def create_settings(data):
    allowed = {
        "name",
        "energy_type",
        "price",
        "base",
        "base_period",
        "payment",
        "payment_day",
        "billing_start",
        "gas_mode",
        "gas_factor",
        "annual_estimate",
        "source_sensor",
        "source_unit",
    }
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("Ungültige Vertragsfelder.")
    energy = data.get("energy_type")
    if energy not in {"electricity", "gas"}:
        raise ValueError("Bitte Strom oder Gas auswählen.")
    return {
        "name": "Strom" if energy == "electricity" else "Gas",
        "price": 0.3,
        "base": 120,
        "base_period": "yearly",
        "payment": 100,
        "payment_day": 1,
        "billing_start": datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat(),
        "gas_mode": "heating_hot_water" if energy == "gas" else "uniform",
        "gas_factor": 10,
        "annual_estimate": 6000 if energy == "gas" else 3000,
        **data,
        "source_unit": data.get("source_unit", "m³" if energy == "gas" else "kWh"),
    }
