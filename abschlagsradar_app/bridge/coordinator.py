"""Local push updates plus a daily refresh; no network traffic."""

import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .model import calculate, normalize_history, number, validate_settings

_LOGGER = logging.getLogger(__name__)


class BudgetCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, storage):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=15))
        self.entry = entry
        self.storage = storage
        self.settings = validate_settings({**entry.data, **entry.options})
        self.source_issue = None

    async def _async_update_data(self):
        today = dt_util.now().date()
        state = self.hass.states.get(self.settings.get("source_sensor", ""))
        self.source_issue = None
        if state is not None and state.state not in ("unknown", "unavailable"):
            try:
                unit = state.attributes.get("unit_of_measurement")
                if unit != self.settings["source_unit"]:
                    raise ValueError("source_unit_mismatch")
                value = number(state.state)
                rows = self.storage.readings
                # Keep the first valid sample each day, nearest the daily boundary.
                # Later readings must not shift today's consumption into yesterday.
                previous = [row for row in rows if row["date"] < today.isoformat()]
                manual = normalize_history(self.settings.get("history", {}))["readings"]
                previous += [row for row in manual if row["date"] < today.isoformat()]
                if previous and value < max(previous, key=lambda row: row["date"])["value"]:
                    raise ValueError("meter_reset")
                row = {"date": today.isoformat(), "value": value}
                if not any(item["date"] == row["date"] for item in rows):
                    self.storage.readings = ([item for item in rows if item["date"] != row["date"]] + [row])[-10000:]
                    await self.storage.async_save()
            except ValueError as err:
                self.source_issue = str(err)
        else:
            self.source_issue = "source_unavailable" if self.settings.get("source_sensor") else None
        history = normalize_history(self.settings.get("history", {}))
        # Manual readings override automatic samples on the same calendar date.
        merged = {row["date"]: row for row in self.storage.readings}
        merged.update({row["date"]: row for row in history["readings"]})
        history["readings"] = sorted(merged.values(), key=lambda row: row["date"])
        try:
            history = normalize_history(history)
        except ValueError:
            # A changed/manual meter baseline must never create negative consumption.
            self.source_issue = "conflicting_automatic_readings"
            history = normalize_history(self.settings.get("history", {}))
        # Daily history/forecast work must not block HA's event loop on large imports.
        result = await self.hass.async_add_executor_job(calculate, self.settings, history, today)
        result["source_issue"] = self.source_issue
        return result
