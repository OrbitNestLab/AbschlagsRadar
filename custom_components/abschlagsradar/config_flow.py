"""UI setup and atomic history replacement through the options flow."""

import json
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import DOMAIN, GAS_MODES
from .model import normalize_history, number, parse_date, validate_settings

DEFAULTS = {
    "name": "AbschlagsRadar",
    "energy_type": "electricity",
    "source_unit": "kWh",
    "price": 0.30,
    "base": 10.0,
    "base_period": "monthly",
    "payment": 100.0,
    "payment_day": 1,
    "gas_mode": "uniform",
    "gas_factor": 10.0,
    "annual_estimate": 3000.0,
}


def schema(values):
    fields = {}
    for key in (
        "name",
        "source_sensor",
        "energy_type",
        "source_unit",
        "price",
        "base",
        "base_period",
        "payment",
        "payment_day",
        "billing_start",
        "gas_mode",
        "gas_factor",
        "annual_estimate",
    ):
        marker_type = vol.Optional if key == "source_sensor" else vol.Required
        marker = marker_type(key, default=values[key]) if key in values else marker_type(key)
        if key == "source_sensor":
            control = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
        elif key in ("energy_type", "source_unit", "base_period", "gas_mode"):
            choices = {
                "energy_type": ["electricity", "gas"],
                "source_unit": ["kWh", "m³"],
                "base_period": ["monthly", "yearly"],
                "gas_mode": GAS_MODES,
            }[key]
            control = selector.SelectSelector(selector.SelectSelectorConfig(options=choices, translation_key=key))
        elif key == "billing_start":
            control = selector.DateSelector()
        elif key in ("price", "base", "payment", "payment_day", "gas_factor", "annual_estimate"):
            control = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    **(
                        {"min": 1, "max": 28, "step": 1, "mode": "box"}
                        if key == "payment_day"
                        else {"min": 0, "step": "any", "mode": "box"}
                    )
                )
            )
        else:
            control = selector.TextSelector()
        fields[marker] = control
    return vol.Schema(fields)


class EnergyBudgetFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BudgetOptionsFlow()

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_menu(step_id="user", menu_options=["electricity", "gas"])
        errors = {}
        if user_input is not None:
            try:
                values = validate_settings(user_input)
                state = self.hass.states.get(values.get("source_sensor", ""))
                if state and state.attributes.get("unit_of_measurement") != values["source_unit"]:
                    raise ValueError("source_unit_mismatch")
                # A contract keeps its identity even when its source sensor changes.
                await self.async_set_unique_id(f"{values['energy_type']}:{uuid4()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=values["name"], data=values)
            except ValueError as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="user", data_schema=schema({**DEFAULTS, **(user_input or {})}), errors=errors
        )

    async def async_step_electricity(self, user_input=None):
        return await self._energy_setup("electricity", user_input)

    async def async_step_gas(self, user_input=None):
        return await self._energy_setup("gas", user_input)

    async def _energy_setup(self, energy_type, user_input):
        values = {
            **DEFAULTS,
            "energy_type": energy_type,
            "name": "Strom" if energy_type == "electricity" else "Gas",
            "source_unit": "kWh" if energy_type == "electricity" else "m³",
            "billing_start": dt_util.now().date().isoformat(),
            "gas_mode": "uniform" if energy_type == "electricity" else "heating_hot_water",
            **(user_input or {}),
        }
        if user_input is not None:
            result = await self.async_step_user(values)
            if result["type"] != "form":
                return result
            errors = result.get("errors", {})
        else:
            errors = {}
        hidden = {"energy_type"}
        if energy_type == "electricity":
            hidden |= {"source_unit", "gas_mode", "gas_factor"}
        fields = {key: value for key, value in schema(values).schema.items() if str(key) not in hidden}
        return self.async_show_form(step_id=energy_type, data_schema=vol.Schema(fields), errors=errors)


class BudgetOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init", menu_options=["settings", "history", "reading", "clear_samples", "installment"]
        )

    async def async_step_settings(self, user_input=None):
        values = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            try:
                checked = validate_settings(user_input)
                # Changing the meter unit would reinterpret the whole historical series.
                if checked["energy_type"] != values["energy_type"] or checked["source_unit"] != values["source_unit"]:
                    raise ValueError("identity_change")
                return self.async_create_entry(title="", data={**self.config_entry.options, **checked})
            except ValueError as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="settings", data_schema=schema({**values, **(user_input or {})}), errors=errors
        )

    async def async_step_history(self, user_input=None):
        errors = {}
        text = json.dumps(
            {**self.config_entry.data, **self.config_entry.options}.get("history", {}), indent=2, ensure_ascii=False
        )
        if user_input is not None:
            text = user_input["history_json"]
            try:
                history = normalize_history(json.loads(text))
                return self.async_create_entry(title="", data={**self.config_entry.options, "history": history})
            except (ValueError, TypeError) as err:
                key = str(err)
                errors["base"] = (
                    key
                    if key
                    in ("invalid_date", "invalid_number", "duplicate_date", "decreasing_meter", "overlapping_intervals")
                    else "invalid_history"
                )
        return self.async_show_form(
            step_id="history",
            data_schema=vol.Schema(
                {
                    vol.Required("history_json", default=text): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reading(self, user_input=None):
        """Compatibility form for manual readings; photo capture lives in the App."""
        errors = {}
        defaults = {"date": dt_util.now().date().isoformat()}
        if user_input is not None:
            try:
                day = parse_date(user_input["date"])
                if day > dt_util.now().date():
                    raise ValueError("future_reading")
                history = normalize_history({**self.config_entry.data, **self.config_entry.options}.get("history", {}))
                history["readings"] = [row for row in history["readings"] if row["date"] != day.isoformat()]
                history["readings"].append({"date": day.isoformat(), "value": number(user_input["value"])})
                history = normalize_history(history)
                return self.async_create_entry(title="", data={**self.config_entry.options, "history": history})
            except ValueError as err:
                errors["base"] = str(err)
            defaults = user_input
        value_marker = (
            vol.Required("value", default=defaults["value"]) if "value" in defaults else vol.Required("value")
        )
        return self.async_show_form(
            step_id="reading",
            data_schema=vol.Schema(
                {
                    vol.Required("date", default=defaults["date"]): selector.DateSelector(),
                    value_marker: selector.NumberSelector(selector.NumberSelectorConfig(min=0, step=0.001, mode="box")),
                }
            ),
            errors=errors,
            description_placeholders={
                "unit": self.config_entry.options.get("source_unit", self.config_entry.data["source_unit"]),
            },
        )

    async def async_step_clear_samples(self, user_input=None):
        if user_input is not None:
            from .const import DOMAIN

            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
            previous = coordinator.storage.readings
            coordinator.storage.readings = []
            try:
                await coordinator.storage.async_save()
            except Exception:
                coordinator.storage.readings = previous
                raise
            await coordinator.async_request_refresh()
            return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return self.async_show_form(step_id="clear_samples", data_schema=vol.Schema({}))

    async def async_step_installment(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                day = parse_date(user_input["date"]).isoformat()
                history = normalize_history({**self.config_entry.data, **self.config_entry.options}.get("history", {}))
                history["installments"] = [row for row in history["installments"] if row["date"] != day]
                history["installments"].append({"date": day, "amount": number(user_input["amount"])})
                return self.async_create_entry(
                    title="", data={**self.config_entry.options, "history": normalize_history(history)}
                )
            except ValueError as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="installment",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("date", default=dt_util.now().date().isoformat()): selector.DateSelector(),
                    vol.Required("amount"): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, step=0.01, mode="box")
                    ),
                }
            ),
        )
