"""Private application panel and authenticated, validated editing commands."""

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .model import normalize_history, validate_settings


@websocket_api.websocket_command({vol.Required("type"): "abschlagsradar/app"})
@callback
def app_data(hass, connection, msg):
    contracts = []
    registry = er.async_get(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if coordinator is None or coordinator.data is None:
            continue
        settings = coordinator.settings
        contracts.append(
            {
                "id": entry.entry_id,
                "settings": {k: v for k, v in settings.items() if k != "history"},
                "history": normalize_history(settings.get("history", {})),
                "automatic_readings": coordinator.storage.readings,
                "result": coordinator.data,
                "entities": contract_entities(hass, registry, entry.entry_id),
            }
        )
    connection.send_result(msg["id"], contracts)


def contract_entities(hass, registry, entry_id):
    """Resolve actual registered IDs, including user renames and disabled sensors."""
    entities = []
    prefix = entry_id + "_"
    for entity in er.async_entries_for_config_entry(registry, entry_id):
        if entity.platform != DOMAIN or not entity.unique_id.startswith(prefix):
            continue
        state = hass.states.get(entity.entity_id)
        entities.append(
            {
                "key": entity.unique_id[len(prefix) :],
                "entity_id": entity.entity_id,
                "name": state.name if state else entity.name or entity.original_name or entity.entity_id,
                "state": state.state if state else "unavailable",
                "unit": state.attributes.get("unit_of_measurement") if state else entity.unit_of_measurement,
                "disabled": entity.disabled_by is not None,
            }
        )
    return sorted(entities, key=lambda item: item["key"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "abschlagsradar/edit",
        vol.Required("entry_id"): str,
        vol.Required("action"): vol.In(
            [
                "reading",
                "interval",
                "installment",
                "tariff",
                "payment",
                "pending_payment",
                "confirm_payment",
                "settings",
            ]
        ),
        vol.Required("payload"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def edit(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Vertrag nicht gefunden.")
        return
    options = dict(entry.options)
    history = normalize_history({**entry.data, **options}.get("history", {}))
    payload = msg["payload"]
    action = msg["action"]
    try:
        if action == "settings":
            allowed = {
                "name",
                "billing_start",
                "payment_day",
                "gas_mode",
                "gas_factor",
                "annual_estimate",
                "source_sensor",
            }
            if set(payload) - allowed:
                raise ValueError("invalid_settings")
            settings = validate_settings({**entry.data, **options, **payload})
            state = hass.states.get(settings.get("source_sensor", ""))
            if state and state.attributes.get("unit_of_measurement") != settings["source_unit"]:
                raise ValueError("source_unit_mismatch")
            options.update({k: settings[k] for k in payload})
        elif action == "confirm_payment":
            if payload not in history["pending_payments"]:
                raise ValueError("invalid_payment")
            if payload["date"] > dt_util.now().date().isoformat():
                raise ValueError("future_payment")
            history["pending_payments"].remove(payload)
            history["payments"].append(payload)
        else:
            key = {
                "reading": "readings",
                "interval": "intervals",
                "installment": "installments",
                "tariff": "tariffs",
                "payment": "payments",
                "pending_payment": "pending_payments",
            }[action]
            normalized = normalize_history({key: [payload]})[key][0]
            if key in {"readings", "payments"} and normalized["date"] > dt_util.now().date().isoformat():
                raise ValueError("future_reading" if key == "readings" else "future_payment")
            if key == "intervals" and normalized["end"] > dt_util.now().date().isoformat():
                raise ValueError("future_reading")
            if key not in {"payments", "pending_payments"}:
                field = "start" if key == "intervals" else "date"
                history[key] = [r for r in history[key] if r[field] != normalized[field]]
            history[key].append(normalized)
        options["history"] = normalize_history(history)
    except (ValueError, TypeError, KeyError) as err:
        connection.send_error(msg["id"], "invalid_input", str(err))
        return
    hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"])


async def async_register_app(hass):
    """Register the private bridge API used by the standalone app."""
    websocket_api.async_register_command(hass, app_data)
    websocket_api.async_register_command(hass, edit)
    websocket_api.async_register_command(hass, restore)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "abschlagsradar/restore",
        vol.Required("entry_id"): str,
        vol.Required("payload"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def restore(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Vertrag nicht gefunden.")
        return
    try:
        payload = msg["payload"]
        if set(payload) != {"settings", "history"}:
            raise ValueError("invalid_history")
        allowed = {
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
        if not isinstance(payload["settings"], dict) or set(payload["settings"]) - allowed:
            raise ValueError("invalid_settings")
        settings = validate_settings(payload["settings"])
        if settings["energy_type"] != entry.data["energy_type"]:
            raise ValueError("identity_change")
        history = normalize_history(payload["history"])
    except (ValueError, KeyError, TypeError) as err:
        connection.send_error(msg["id"], "invalid_input", str(err))
        return
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        connection.send_error(msg["id"], "not_ready", "Vertrag wird gerade geladen. Bitte erneut versuchen.")
        return
    old_readings = coordinator.storage.readings
    coordinator.storage.readings = []
    try:
        await coordinator.storage.async_save()
    except Exception:
        coordinator.storage.readings = old_readings
        raise
    hass.config_entries.async_update_entry(entry, options={**settings, "history": history})
    connection.send_result(msg["id"], {"restored": True})
