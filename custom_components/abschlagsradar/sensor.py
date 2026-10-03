"""Native numeric sensors suitable for Recorder and HA graph cards."""

from datetime import datetime, time

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .model import parse_date

ENERGY = {
    "consumption",
    "forecast_consumption",
    "previous_consumption",
    "daily_consumption",
    "daily_previous",
    "daily_forecast",
}
MONEY = {
    "cost_so_far",
    "paid",
    "forecast_cost",
    "balance",
    "expected_payment",
    "expected_credit",
    "current_installment",
    "recommended_installment",
    "installment_adjustment",
    "planned_installments",
    "pending_installments",
    "average_paid_installment",
    "next_year_installment",
}
PERCENT = {"comparison", "coverage", "history_weight"}
KEYS = sorted(ENERGY | MONEY | PERCENT | {"budget_status", "remaining_installments"})


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(BudgetSensor(hass.data[DOMAIN][entry.entry_id], key) for key in KEYS)


class BudgetSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.settings["name"],
            manufacturer="AbschlagsRadar",
            model=coordinator.settings["energy_type"],
        )
        if key == "budget_status":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["payment_due", "credit", "balanced"]
        else:
            self._attr_native_unit_of_measurement = (
                "kWh" if key in ENERGY else "EUR" if key in MONEY else None if key == "remaining_installments" else "%"
            )
            if key in ENERGY:
                self._attr_device_class = SensorDeviceClass.ENERGY
            elif key in MONEY:
                self._attr_device_class = SensorDeviceClass.MONETARY
            if key in {"consumption", "cost_so_far", "paid"}:
                self._attr_state_class = SensorStateClass.TOTAL
            # Forecasts and historical comparisons deliberately have no state
            # class: Recorder graphs numeric units without false statistics.
            elif key in {"coverage", "history_weight", "remaining_installments"}:
                self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def last_reset(self):
        if self.key in {"consumption", "cost_so_far", "paid"}:
            start = parse_date(self.coordinator.settings["billing_start"])
            return dt_util.as_utc(datetime.combine(start, time.min, dt_util.DEFAULT_TIME_ZONE))
        return None

    @property
    def native_value(self):
        value = self.coordinator.data["values"].get(self.key)
        return round(value, 4) if isinstance(value, (float, int)) else value

    @property
    def extra_state_attributes(self):
        if self.key == "next_year_installment":
            return {
                "forecast_year": dt_util.now().year + 1,
                "payments_per_year": 12,
                "price_assumption": "known_tariffs",
                "bonuses_included": False,
            }
        if self.key == "average_paid_installment":
            return {
                "calendar_year": dt_util.now().year,
                "pending_included": False,
                "payments_assumed": self.coordinator.data["payments_assumed"],
            }
        if self.key != "budget_status":
            return None
        data = self.coordinator.data
        return {
            "billing_end": data["billing_end"],
            "payments_assumed": data["payments_assumed"],
            "forecast_method": data["forecast_method"],
            "source_issue": data["source_issue"],
        }
