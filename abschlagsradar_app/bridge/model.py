"""Pure daily billing model, independent of Home Assistant.

Intervals are half-open [start, end). Meter deltas are spread uniformly;
explicit consumption intervals override meter estimates, never add to them.
Missing days remain missing, rather than being interpreted as zero.
"""

from __future__ import annotations

import math
import re
from bisect import bisect_right
from calendar import monthrange
from datetime import date, datetime, timedelta

HEATING = (0.17, 0.15, 0.13, 0.08, 0.04, 0.015, 0.01, 0.015, 0.04, 0.08, 0.12, 0.15)


def parse_date(value):
    """Accept ISO dates and German dates; persist only ISO dates."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()  # noqa: DTZ007 - this is a calendar date, not a timestamp
        except (ValueError, TypeError):
            pass
    raise ValueError("invalid_date")


def number(value, minimum=0):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as err:
        raise ValueError("invalid_number") from err
    # Generous physical/accounting bound also prevents later multiplication overflow.
    if not math.isfinite(result) or result < minimum or result > 1e12 or isinstance(value, bool):
        raise ValueError("invalid_number")
    return result


def days(start, end):
    while start < end:
        yield start
        start += timedelta(days=1)


def anniversary(start):
    return start.replace(year=start.year + 1, day=min(start.day, monthrange(start.year + 1, start.month)[1]))


def previous_day(day):
    return day.replace(year=day.year - 1, day=min(day.day, monthrange(day.year - 1, day.month)[1]))


def normalize_history(data):
    """Validate a complete replacement before saving any user data."""
    if not isinstance(data, dict) or set(data) - {
        "readings",
        "intervals",
        "tariffs",
        "payments",
        "installments",
        "pending_payments",
    }:
        raise ValueError("invalid_history")
    result = {key: [] for key in ("readings", "intervals", "tariffs", "payments", "installments", "pending_payments")}
    fields = {
        "readings": {"date", "value"},
        "intervals": {"start", "end", "kwh"},
        "tariffs": {"date", "price", "base", "base_period"},
        "payments": {"date", "amount"},
        "installments": {"date", "amount"},
        "pending_payments": {"date", "amount"},
    }
    for key, required in fields.items():
        rows = data.get(key, [])
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError("invalid_history")
        for row in rows:
            if not isinstance(row, dict) or set(row) != required:
                raise ValueError("invalid_history")
            row = dict(row)
            for field in required & {"date", "start", "end"}:
                row[field] = parse_date(row[field]).isoformat()
            for field in required & {"value", "kwh", "price", "base", "amount"}:
                row[field] = number(row[field])
            if key == "tariffs" and row["base_period"] not in ("monthly", "yearly"):
                raise ValueError("invalid_history")
            if key == "intervals" and row["end"] <= row["start"]:
                raise ValueError("invalid_history")
            result[key].append(row)
        result[key].sort(key=lambda row: row.get("date", row.get("start")))
        if key not in {"payments", "pending_payments"}:
            dates = [row.get("date", row.get("start")) for row in result[key]]
            if len(dates) != len(set(dates)):
                raise ValueError("duplicate_date")
    for left, right in zip(result["readings"], result["readings"][1:]):
        if right["value"] < left["value"]:
            raise ValueError("decreasing_meter")
    for left, right in zip(result["intervals"], result["intervals"][1:]):
        if left["end"] > right["start"]:
            raise ValueError("overlapping_intervals")
    # Bound daily expansion, including gaps between meter readings, before doing work.
    endpoints = [
        parse_date(row[field])
        for key in ("readings", "intervals")
        for row in result[key]
        for field in ({"date"} if key == "readings" else {"start", "end"})
    ]
    if endpoints and (max(endpoints) - min(endpoints)).days > 36600:
        raise ValueError("history_too_long")
    return result


def validate_settings(settings):
    required = {
        "name",
        "billing_start",
        "price",
        "base",
        "payment",
        "annual_estimate",
        "gas_factor",
        "payment_day",
        "base_period",
        "energy_type",
        "gas_mode",
        "source_unit",
    }
    if not isinstance(settings, dict) or not required <= set(settings):
        raise ValueError("invalid_settings")
    result = dict(settings)
    name = result.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError("invalid_settings")
    result["name"] = name.strip()
    result["billing_start"] = parse_date(result["billing_start"]).isoformat()
    if not 1900 <= parse_date(result["billing_start"]).year <= 2198:
        raise ValueError("invalid_settings")
    source = result.get("source_sensor")
    if "source_sensor" in result and source is None:
        result["source_sensor"] = ""
    if source not in (None, "") and (
        not isinstance(source, str) or re.fullmatch(r"sensor\.[a-z0-9_]+", source) is None
    ):
        raise ValueError("invalid_settings")
    for key in ("price", "base", "payment", "annual_estimate"):
        result[key] = number(result[key])
    result["gas_factor"] = number(result["gas_factor"], 0.000001)
    day = number(result["payment_day"], 1)
    if day != int(day):
        raise ValueError("invalid_settings")
    result["payment_day"] = int(day)
    if result["payment_day"] > 28 or result["base_period"] not in ("monthly", "yearly"):
        raise ValueError("invalid_settings")
    if result["energy_type"] not in ("electricity", "gas") or result["gas_mode"] not in (
        "heating",
        "heating_hot_water",
        "uniform",
    ):
        raise ValueError("invalid_settings")
    if result["source_unit"] not in ("kWh", "m³") or (
        result["energy_type"] == "electricity" and result["source_unit"] != "kWh"
    ):
        raise ValueError("invalid_settings")
    return result


def daily_consumption(history, factor=1):
    result = {}
    for left, right in zip(history["readings"], history["readings"][1:]):
        start, end = parse_date(left["date"]), parse_date(right["date"])
        value = (right["value"] - left["value"]) * factor / (end - start).days
        result.update((day, value) for day in days(start, end))
    for row in history["intervals"]:
        start, end = parse_date(row["start"]), parse_date(row["end"])
        result.update((day, row["kwh"] / (end - start).days) for day in days(start, end))
    return result


def seasonal_weight(day, settings):
    if settings["energy_type"] == "electricity" or settings["gas_mode"] == "uniform":
        return 1 / (366 if monthrange(day.year, 2)[1] == 29 else 365)
    heating = HEATING[day.month - 1] / sum(HEATING) / monthrange(day.year, day.month)[1]
    if settings["gas_mode"] == "heating_hot_water":
        return 0.8 * heating + 0.2 / (366 if monthrange(day.year, 2)[1] == 29 else 365)
    return heating


def tariff_for(day, settings, history):
    tariff = settings
    for row in history["tariffs"]:
        if parse_date(row["date"]) > day:
            break
        tariff = row
    return tariff


def cost(day, kwh, settings, history, tariff=None):
    tariff = tariff if tariff is not None else tariff_for(day, settings, history)
    denominator = (
        monthrange(day.year, day.month)[1]
        if tariff["base_period"] == "monthly"
        else (366 if monthrange(day.year, 2)[1] == 29 else 365)
    )
    return kwh * tariff["price"] + tariff["base"] / denominator


def installment_for(day, settings, history):
    amount = settings["payment"]
    for row in history["installments"]:
        if parse_date(row["date"]) > day:
            break
        amount = row["amount"]
    return amount


def payment_dates(start, end, settings):
    result = []
    day = start.replace(day=1)
    while day < end:
        due = day.replace(day=settings["payment_day"])
        if start <= due < end:
            result.append(due)
        day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return result


def scheduled_payments(start, end, settings, history):
    return sum(installment_for(day, settings, history) for day in payment_dates(start, end, settings))


def calculate(settings, history, today):
    """Return sensors plus explicit coverage and daily chart data.

    Costs through today exclude today (the last complete calendar day).
    Positive balance means payment due; negative balance means credit.
    Explicit payments replace assumed payments for the entire period.
    """
    start = parse_date(settings["billing_start"])
    end = anniversary(start)
    cutoff = min(max(today, start), end)
    factor = settings["gas_factor"] if settings["source_unit"] == "m³" else 1
    tariff_dates = [parse_date(row["date"]) for row in history["tariffs"]]

    def daily_cost(day, kwh):
        index = bisect_right(tariff_dates, day)
        tariff = history["tariffs"][index - 1] if index else settings
        return cost(day, kwh, settings, history, tariff)

    actual = daily_consumption(history, factor)
    elapsed = list(days(start, cutoff))
    known = [day for day in elapsed if day in actual]
    complete = len(known) == len(elapsed)
    # Personal monthly distribution gradually replaces the generic curve.
    prior_start = start.replace(year=start.year - 1, day=min(start.day, monthrange(start.year - 1, start.month)[1]))
    prior_days = list(days(prior_start, start))
    prior_known = [day for day in prior_days if day in actual]
    prior_total = sum(actual[day] for day in prior_known)
    prior_coverage = len(prior_known) / len(prior_days)
    prior_scale = prior_total / sum(seasonal_weight(day, settings) for day in prior_known) if prior_known else None
    history_weight = min(0.75, prior_coverage * 0.75)
    monthly = []
    for month in range(1, 13):
        samples = [day for day in prior_known if day.month == month]
        # Missing months are not zero consumption. Fill them with the generic curve.
        if samples and prior_total > 0:
            amount = sum(actual[day] for day in samples) / len(samples) * monthrange(start.year, month)[1]
        else:
            amount = sum(
                seasonal_weight(date(start.year, month, day), settings)
                for day in range(1, monthrange(start.year, month)[1] + 1)
            ) * (prior_scale or settings["annual_estimate"])
        monthly.append(amount)
    monthly_total = sum(monthly)

    def learned_weight(day):
        generic = seasonal_weight(day, settings)
        personal = (
            monthly[day.month - 1] / monthly_total / monthrange(day.year, day.month)[1]
            if monthly_total > 0
            else generic
        )
        return (1 - history_weight) * generic + history_weight * personal

    observed_weight = sum(learned_weight(day) for day in known)
    current_scale = sum(actual[day] for day in known) / observed_weight if observed_weight else None
    if current_scale is None:
        scale = prior_scale if prior_scale is not None else settings["annual_estimate"]
    elif prior_scale is None:
        scale = current_scale
    else:
        # History informs the season, but must not suppress a sustained current change.
        evidence = min(1.0, observed_weight / 0.25)
        scale = current_scale * evidence + prior_scale * (1 - evidence)

    def predicted(day):
        return scale * learned_weight(day)

    rows = []
    for day in days(start, end):
        measured = actual.get(day) if day < cutoff else None
        rows.append(
            {
                "date": day.isoformat(),
                "actual_kwh": measured,
                "previous_kwh": actual.get(previous_day(day)),
                "forecast_kwh": measured if measured is not None else predicted(day),
            }
        )
    forecast = sum(row["forecast_kwh"] for row in rows)
    forecast_cost = sum(daily_cost(parse_date(row["date"]), row["forecast_kwh"]) for row in rows)
    payments = history["payments"]
    pending_by_date = {}
    for row in history["pending_payments"]:
        due = parse_date(row["date"])
        if start <= due < end:
            pending_by_date[due] = pending_by_date.get(due, 0) + row["amount"]
    # An initiated payment is outstanding, not paid and not adjustable.
    # Pending dates matching a regular future due date replace that assumed
    # payment, so it cannot be counted twice.
    # Banks may post on the 2nd/next business day even when the due day is the 1st.
    # Match fixed/confirmed payments by calendar month, never count that due twice.
    fixed_months = {(day.year, day.month) for day in pending_by_date}
    fixed_months.update(
        (day.year, day.month) for row in payments if start <= (day := parse_date(row["date"])) < end and day <= today
    )
    due_dates = payment_dates(start, end, settings)
    assumed_paid_dates = [day for day in due_dates if day <= today and (day.year, day.month) not in fixed_months]
    paid = (
        sum(
            row["amount"]
            for row in payments
            if start <= parse_date(row["date"]) < end and parse_date(row["date"]) <= today
        )
        if payments
        else sum(installment_for(day, settings, history) for day in assumed_paid_dates)
    )
    # Costs stop at the last full day; payment accounting includes the current day.
    if not payments:
        fixed_months.update((day.year, day.month) for day in assumed_paid_dates)
    future_dates = [day for day in due_dates if day >= today]
    adjustable_dates = [day for day in future_dates if (day.year, day.month) not in fixed_months]
    pending = sum(pending_by_date.values())
    planned = paid + pending + sum(installment_for(day, settings, history) for day in adjustable_dates)
    balance = forecast_cost - planned
    remaining = len(adjustable_dates)
    recommended = max(0, (forecast_cost - paid - pending) / remaining) if remaining else None
    current_payment = installment_for(cutoff, settings, history)
    yesterday = cutoff - timedelta(days=1)
    previous_values = [actual.get(previous_day(day)) for day in elapsed]
    previous = sum(previous_values) if all(value is not None for value in previous_values) else None
    consumption = sum(actual[day] for day in known) if complete else None
    comparison = 100 * (consumption / previous - 1) if consumption is not None and previous else None
    if comparison is not None and not math.isfinite(comparison):
        comparison = None
    calendar_start = date(today.year, 1, 1)
    if payments:
        year_payments = [row for row in payments if calendar_start <= parse_date(row["date"]) <= today]
        paid_months = {row["date"][:7] for row in year_payments}
        average_paid = sum(row["amount"] for row in year_payments) / len(paid_months) if paid_months else None
    else:
        assumed_dates = [day for day in assumed_paid_dates if day >= calendar_start]
        average_paid = (
            sum(installment_for(day, settings, history) for day in assumed_dates) / len(assumed_dates)
            if assumed_dates
            else None
        )
    next_start, next_end = date(today.year + 1, 1, 1), date(today.year + 2, 1, 1)
    # Next calendar year uses known dated tariffs and the learned seasonal curve.
    # Unknown future supplier price changes cannot be predicted; no bonus is included.
    next_cost = sum(daily_cost(day, predicted(day)) for day in days(next_start, next_end))
    values = {
        "consumption": consumption,
        "cost_so_far": sum(daily_cost(day, actual[day]) for day in known) if complete else None,
        "paid": paid,
        "forecast_consumption": forecast,
        "forecast_cost": forecast_cost,
        "balance": balance,
        "expected_payment": max(0, balance),
        "expected_credit": max(0, -balance),
        "budget_status": "payment_due" if balance > 1 else "credit" if balance < -1 else "balanced",
        "coverage": 100 * len(known) / len(elapsed) if elapsed else 100,
        "previous_consumption": previous,
        "comparison": comparison,
        "daily_consumption": actual.get(yesterday),
        "daily_previous": actual.get(previous_day(yesterday)),
        "daily_forecast": predicted(yesterday),
        "history_weight": history_weight * 100,
        "current_installment": current_payment,
        "recommended_installment": recommended,
        "installment_adjustment": recommended - current_payment if recommended is not None else None,
        "remaining_installments": remaining,
        "planned_installments": planned,
        "pending_installments": pending,
        "average_paid_installment": average_paid,
        "next_year_installment": next_cost / 12,
    }
    return {
        "values": values,
        "daily": rows,
        "billing_end": end.isoformat(),
        "payments_assumed": not bool(payments),
        "forecast_method": "personal_blend" if prior_known else "seasonal_estimate",
        "as_of": today.isoformat(),
        "adjustable_payment_dates": [day.isoformat() for day in adjustable_dates],
        "observed_through": max(known).isoformat() if known else None,
    }
