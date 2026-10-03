"""AbschlagsRadar: private local electricity and gas billing estimates."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, PLATFORMS
from .coordinator import BudgetCoordinator
from .storage import BudgetStorage


async def async_setup(hass, config):
    """Expose daily history as an action response without bloating Recorder."""

    async def get_daily_history(call):
        coordinator = hass.data.get(DOMAIN, {}).get(call.data["entry_id"])
        if coordinator is None:
            raise ServiceValidationError("Unknown AbschlagsRadar config entry")
        return {"billing_end": coordinator.data["billing_end"], "daily": coordinator.data["daily"]}

    hass.services.async_register(
        DOMAIN,
        "get_daily_history",
        get_daily_history,
        schema=vol.Schema({vol.Required("entry_id"): str}),
        supports_response=SupportsResponse.ONLY,
    )
    from .panel import async_register_app

    await async_register_app(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    storage = BudgetStorage(hass, entry.entry_id)
    await storage.async_load()
    coordinator = BudgetCoordinator(hass, entry, storage)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()

    async def source_changed(event):
        await coordinator.async_request_refresh()

    if coordinator.settings.get("source_sensor"):
        entry.async_on_unload(
            async_track_state_change_event(hass, coordinator.settings["source_sensor"], source_changed)
        )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False


async def async_remove_entry(hass, entry):
    await BudgetStorage(hass, entry.entry_id).async_remove()
