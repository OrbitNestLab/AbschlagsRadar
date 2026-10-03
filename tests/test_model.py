"""Regression tests for billing behavior; no Home Assistant mocks required."""

from datetime import date

import pytest
from budget_under_test.model import (
    anniversary,
    calculate,
    daily_consumption,
    normalize_history,
    parse_date,
    scheduled_payments,
    seasonal_weight,
    validate_settings,
)


@pytest.fixture
def settings():
    return validate_settings(
        {
            "name": "Test",
            "energy_type": "electricity",
            "source_unit": "kWh",
            "price": 0.30,
            "base": 10,
            "base_period": "monthly",
            "payment": 100,
            "payment_day": 1,
            "billing_start": "2025-01-01",
            "gas_mode": "uniform",
            "gas_factor": 10,
            "annual_estimate": 3650,
        }
    )


def history(**kw):
    return normalize_history(kw)


def test_arbitrary_german_dates():
    assert parse_date("11.02.2025") == date(2025, 2, 11)
    assert history(readings=[{"date": "11.02.2025", "value": 42}])["readings"][0]["date"] == "2025-02-11"


@pytest.mark.parametrize("source", [False, 0, [], {}, "sensor.", "light.living_room", "sensor.invalid-name"])
def test_source_sensor_requires_valid_entity_id(settings, source):
    settings["source_sensor"] = source
    with pytest.raises(ValueError, match="invalid_settings"):
        validate_settings(settings)


def test_incomplete_settings_are_an_input_error():
    with pytest.raises(ValueError, match="invalid_settings"):
        validate_settings({"name": "Missing fields"})


def test_meter_interpolation_direct_override_no_double_count(settings):
    h = history(
        readings=[{"date": "2025-01-01", "value": 1000}, {"date": "2025-01-11", "value": 1100}],
        intervals=[{"start": "2025-01-04", "end": "2025-01-06", "kwh": 30}],
    )
    actual = daily_consumption(h)
    assert sum(actual.values()) == 110
    result = calculate(settings, h, date(2025, 1, 11))["values"]
    assert result["consumption"] == 110
    assert result["coverage"] == 100


def test_price_change_date_and_monthly_base(settings):
    h = history(
        intervals=[{"start": "2025-01-01", "end": "2025-02-01", "kwh": 310}],
        tariffs=[{"date": "2025-01-16", "price": 0.4, "base": 20, "base_period": "monthly"}],
    )
    cost = calculate(settings, h, date(2025, 2, 1))["values"]["cost_so_far"]
    assert cost == pytest.approx(150 * 0.3 + 160 * 0.4 + 15 * 10 / 31 + 16 * 20 / 31)


def test_leap_year_annual_base(settings):
    settings.update(billing_start="2024-01-01", base=366, base_period="yearly", price=0)
    h = history(intervals=[{"start": "2024-01-01", "end": "2025-01-01", "kwh": 0}])
    result = calculate(settings, h, date(2025, 1, 1))["values"]
    assert result["cost_so_far"] == pytest.approx(366)
    assert result["remaining_installments"] == 0
    assert result["recommended_installment"] is None
    assert anniversary(date(2024, 2, 29)) == date(2025, 2, 28)


def test_midyear_installment_and_recommendation(settings):
    h = history(installments=[{"date": "2025-07-01", "amount": 150}])
    result = calculate(settings, h, date(2025, 7, 1))["values"]
    assert result["paid"] == 750
    assert result["planned_installments"] == 1500
    assert result["current_installment"] == 150
    assert result["remaining_installments"] == 5
    # fallback estimate = 3650 kWh * .30 + 120 = 1215 EUR
    assert result["forecast_cost"] == pytest.approx(1215)
    assert result["recommended_installment"] == pytest.approx(93)
    assert result["installment_adjustment"] == pytest.approx(-57)
    assert result["expected_credit"] == pytest.approx(285)


def test_installment_effective_after_due_day(settings):
    h = history(installments=[{"date": "2025-07-02", "amount": 150}])
    assert scheduled_payments(date(2025, 1, 1), date(2026, 1, 1), settings, h) == 1450


def test_actual_payments_replace_assumptions(settings):
    h = history(payments=[{"date": "2025-01-01", "amount": 80}, {"date": "2025-04-01", "amount": 90}])
    result = calculate(settings, h, date(2025, 7, 1))
    assert result["values"]["paid"] == 170
    assert result["payments_assumed"] is False
    assert result["values"]["recommended_installment"] == pytest.approx((1215 - 170) / 6)


def test_overpayment_recommendation_zero(settings):
    h = history(payments=[{"date": "2025-01-01", "amount": 2000}])
    result = calculate(settings, h, date(2025, 7, 1))["values"]
    assert result["recommended_installment"] == 0
    assert result["expected_credit"] > 0


def test_missing_days_are_unknown_not_zero(settings):
    h = history(intervals=[{"start": "2025-01-02", "end": "2025-01-04", "kwh": 20}])
    result = calculate(settings, h, date(2025, 1, 5))["values"]
    assert result["consumption"] is None
    assert result["cost_so_far"] is None
    assert result["coverage"] == 50
    assert result["forecast_consumption"] > 0


def test_gas_conversion(settings):
    settings.update(energy_type="gas", source_unit="m³", gas_factor=10.5)
    h = history(readings=[{"date": "2025-01-01", "value": 100}, {"date": "2025-01-11", "value": 110}])
    assert calculate(settings, h, date(2025, 1, 11))["values"]["consumption"] == 105


def test_gas_modes_and_personal_history(settings):
    settings.update(energy_type="gas", gas_mode="heating")
    assert seasonal_weight(date(2025, 1, 1), settings) > seasonal_weight(date(2025, 7, 1), settings)
    settings["gas_mode"] = "heating_hot_water"
    assert seasonal_weight(date(2025, 7, 1), settings) > 0
    h = history(intervals=[{"start": "2024-01-01", "end": "2025-01-01", "kwh": 4000}])
    result = calculate(settings, h, date(2025, 1, 1))
    assert result["values"]["history_weight"] == 75
    assert result["forecast_method"] == "personal_blend"
    assert len(result["daily"]) == 365


def test_balance_sign_and_previous_year(settings):
    h = history(
        intervals=[
            {"start": "2024-01-01", "end": "2025-01-01", "kwh": 3660},
            {"start": "2025-01-01", "end": "2025-02-01", "kwh": 341},
        ]
    )
    result = calculate(settings, h, date(2025, 2, 1))["values"]
    assert result["previous_consumption"] == pytest.approx(310)
    assert result["comparison"] == pytest.approx(10)
    assert result["expected_payment"] - result["expected_credit"] == result["balance"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, "oops", True, 1e308])
def test_invalid_numbers(value):
    with pytest.raises(ValueError):
        history(readings=[{"date": "2025-01-01", "value": value}])


@pytest.mark.parametrize(
    "data",
    [
        {"readings": [{"date": "2025-01-01", "value": 10}, {"date": "2025-01-02", "value": 9}]},
        {"readings": [{"date": "2025-01-01", "value": 10}, {"date": "2025-01-01", "value": 11}]},
        {
            "intervals": [
                {"start": "2025-01-01", "end": "2025-01-04", "kwh": 3},
                {"start": "2025-01-03", "end": "2025-01-05", "kwh": 3},
            ]
        },
        {"tariffs": [{"date": "2025-01-01", "price": 0.3, "base": 10, "base_period": "weekly"}]},
        {"readings": [{"date": "31.02.2025", "value": 10}]},
        {"installments": [{"date": "2025-01-01", "amount": 100}, {"date": "2025-01-01", "amount": 90}]},
        {"surprise": []},
    ],
)
def test_invalid_history(data):
    with pytest.raises(ValueError):
        normalize_history(data)


def test_pending_payment_is_forecast_but_not_paid(settings):
    h = history(
        payments=[{"date": "2025-06-01", "amount": 600}], pending_payments=[{"date": "2025-07-02", "amount": 100}]
    )
    result = calculate(settings, h, date(2025, 7, 2))["values"]
    assert result["paid"] == 600
    assert result["pending_installments"] == 100
    assert result["remaining_installments"] == 5
    assert result["planned_installments"] == 1200
    assert result["recommended_installment"] == pytest.approx((1215 - 600 - 100) / 5)


def test_pending_regular_due_date_not_double_counted(settings):
    h = history(
        payments=[{"date": "2025-06-01", "amount": 600}], pending_payments=[{"date": "2025-07-01", "amount": 100}]
    )
    result = calculate(settings, h, date(2025, 7, 1))["values"]
    assert result["planned_installments"] == 1200
    assert result["remaining_installments"] == 5
    assert result["paid"] == 600


def test_calendar_average_counts_paid_months_and_excludes_pending(settings):
    h = history(
        payments=[
            {"date": "2024-12-01", "amount": 999},
            {"date": "2025-02-01", "amount": 40},
            {"date": "2025-02-03", "amount": 60},
            {"date": "2025-03-01", "amount": 160},
        ],
        pending_payments=[{"date": "2025-04-01", "amount": 500}],
    )
    values = calculate(settings, h, date(2025, 4, 1))["values"]
    assert values["average_paid_installment"] == 130


def test_next_year_installment_includes_future_tariff_and_base(settings):
    h = history(tariffs=[{"date": "2026-01-01", "price": 0.4, "base": 240, "base_period": "yearly"}])
    values = calculate(settings, h, date(2025, 7, 1))["values"]
    assert values["next_year_installment"] == pytest.approx((3650 * 0.4 + 240) / 12)
    assert calculate(settings, history(), date(2025, 7, 1))["values"]["average_paid_installment"] == 100


def test_confirmed_payment_today_counts_and_is_not_planned_again(settings):
    h = history(payments=[{"date": "2025-07-01", "amount": 120}])
    values = calculate(settings, h, date(2025, 7, 1))["values"]
    assert values["paid"] == 120
    assert values["remaining_installments"] == 5
    assert values["planned_installments"] == 620


def test_assumed_payment_today_and_pending_posting_are_not_counted_twice(settings):
    empty = calculate(settings, history(), date(2025, 7, 1))["values"]
    assert empty["paid"] == 700
    assert empty["remaining_installments"] == 5
    assert empty["planned_installments"] == 1200
    pending = calculate(settings, history(pending_payments=[{"date": "2025-07-02", "amount": 120}]), date(2025, 7, 2))[
        "values"
    ]
    assert pending["paid"] == 600
    assert pending["pending_installments"] == 120
    assert pending["planned_installments"] == 1220
    assert pending["average_paid_installment"] == 100


def test_pending_bank_posting_replaces_monthly_due_even_if_day_differs(settings):
    h = history(
        payments=[{"date": "2025-06-01", "amount": 600}],
        pending_payments=[{"date": "2025-07-02", "amount": 100}],
    )
    result = calculate(settings, h, date(2025, 7, 1))
    assert result["values"]["remaining_installments"] == 5
    assert result["values"]["planned_installments"] == 1200
    assert result["adjustable_payment_dates"][0] == "2025-08-01"


def test_extreme_date_span_rejected_before_daily_allocation():
    with pytest.raises(ValueError, match="history_too_long"):
        history(readings=[{"date": "0001-01-01", "value": 0}, {"date": "9999-12-31", "value": 10}])


@pytest.mark.parametrize("name", [None, [], "", "  ", "x" * 121])
def test_invalid_contract_name_is_rejected(settings, name):
    with pytest.raises(ValueError, match="invalid_settings"):
        validate_settings({**settings, "name": name})


def test_partial_history_does_not_turn_missing_months_into_zero(settings):
    h = history(intervals=[{"start": "2024-01-01", "end": "2024-02-01", "kwh": 310}])
    result = calculate(settings, h, date(2025, 1, 1))
    assert result["values"]["forecast_consumption"] == pytest.approx(3660)
    assert all(row["forecast_kwh"] > 0 for row in result["daily"])


def test_null_optional_source_is_normalized(settings):
    assert validate_settings({**settings, "source_sensor": None})["source_sensor"] == ""


def test_comparison_overflow_is_unknown(settings):
    h = history(
        intervals=[
            {"start": "2024-01-01", "end": "2024-01-02", "kwh": 1e-310},
            {"start": "2025-01-01", "end": "2025-01-02", "kwh": 100},
        ]
    )
    assert calculate(settings, h, date(2025, 1, 2))["values"]["comparison"] is None


def test_sustained_current_consumption_change_is_not_suppressed_by_history(settings):
    h = history(
        intervals=[
            {"start": "2024-01-01", "end": "2025-01-01", "kwh": 3660},
            {"start": "2025-01-01", "end": "2025-07-01", "kwh": 3620},
        ]
    )
    result = calculate(settings, h, date(2025, 7, 1))
    assert result["values"]["forecast_consumption"] == pytest.approx(7300, rel=0.002)
    assert result["values"]["next_year_installment"] == pytest.approx((7300 * 0.3 + 120) / 12, rel=0.002)
