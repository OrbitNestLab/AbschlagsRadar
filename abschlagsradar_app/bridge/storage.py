"""Versioned local storage for automatically sampled meter readings."""

from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION


class BudgetStorage:
    def __init__(self, hass, entry_id):
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")
        self.readings = []

    async def async_load(self):
        data = await self._store.async_load()
        self.readings = (data or {}).get("readings", [])

    async def async_save(self):
        await self._store.async_save({"readings": self.readings})

    async def async_remove(self):
        await self._store.async_remove()
