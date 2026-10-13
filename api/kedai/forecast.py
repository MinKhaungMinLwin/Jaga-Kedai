"""Demand forecasting and restock planning for a small shop.

The model is deliberately simple and explainable: a weekday profile times a
winsorised recent level times a damped two-week trend. Restock quantities are
computed here, never by the language model, so every number the shopkeeper
approves can be traced back to sales history.
"""

import math
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

HISTORY_WINDOW = 56
RISK_ORDER = {"critical": 0, "high": 1, "watch": 2, "ok": 3}


def daily_series(sales_docs: list[dict], skus: list[str], today: date, days: int = HISTORY_WINDOW):
    start = today - timedelta(days=days)
    series = {sku: [0] * days for sku in skus}
    for doc in sales_docs:
        index = (date.fromisoformat(doc["date"]) - start).days
        if 0 <= index < days:
            for sku, units in doc.get("units", {}).items():
                if sku in series:
                    series[sku][index] += units
    return series


def local_forecast(history: list[int], start: date, horizon: int) -> tuple[list[float], float]:
    """Forecast `horizon` days from `start`; returns (daily forecast, two-week trend)."""
    days = len(history)
    first_day = start - timedelta(days=days)
    mean = sum(history) / days if days else 0.0
    if mean == 0:
        return [0.0] * horizon, 0.0
    by_weekday: dict[int, list[int]] = defaultdict(list)
    for index, units in enumerate(history):
        by_weekday[(first_day + timedelta(days=index)).weekday()].append(units)
    weekday = {day: 0.5 + 0.5 * statistics.fmean(values) / mean for day, values in by_weekday.items()}
    cap = max(2 * statistics.median(history[-28:]), 1)

    def level(window: list[int], offset: int) -> float:
        return statistics.fmean(
            min(units, cap) / weekday.get((first_day + timedelta(days=offset + index)).weekday(), 1.0)
            for index, units in enumerate(window)
        )

    recent = level(history[-14:], days - 14)
    previous = level(history[-28:-14], days - 28)
    ratio = min(1.6, max(0.7, recent / previous)) if previous > 0 else 1.0
    growth = ratio ** (1 / 14)
    forecast = [
        recent * growth ** min(step + 7, 35) * weekday.get((start + timedelta(days=step)).weekday(), 1.0)
        for step in range(horizon)
    ]
    return forecast, ratio - 1


FESTIVAL_WEEKS = 5  # the festival rush is modelled over the five weeks before the day


def festival_profile(
    units_by_date: dict[date, dict[str, int]], sku: str, festival: date
) -> list[float] | None:
    """Last festival's weekly uplift vs the month before it: index 0 = final week before the festival."""
    baseline_days = [festival - timedelta(days=offset) for offset in range(36, 64)]
    if not all(day in units_by_date for day in baseline_days):
        return None
    baseline = statistics.fmean(units_by_date[day].get(sku, 0) for day in baseline_days)
    if baseline <= 0:
        return None
    weeks = []
    for week in range(FESTIVAL_WEEKS):
        days = [festival - timedelta(days=offset) for offset in range(week * 7 + 1, week * 7 + 8)]
        if not all(day in units_by_date for day in days):
            return None
        weeks.append(
            min(6.0, max(0.5, statistics.fmean(units_by_date[day].get(sku, 0) for day in days) / baseline))
        )
    return weeks if max(weeks) >= 1.3 else None


def uplift_on(profile: list[float] | None, festival: date | None, day: date) -> float:
    if profile is None or festival is None:
        return 1.0
    days_to = (festival - day).days
    if 1 <= days_to <= FESTIVAL_WEEKS * 7:
        return profile[(days_to - 1) // 7]
    return 1.0


def plan(
    products: list[dict],
    suppliers: dict[str, dict],
    sales_docs: list[dict],
    open_orders: list[dict],
    today: date,
    horizon_days: int = 7,
    festival: date | None = None,
    last_festival: date | None = None,
) -> list[dict[str, Any]]:
    """Per-product stock outlook and recommended order quantity.

    When the shop's history covers the previous festival, the forecast applies
    that festival's learned weekly uplift to the days leading up to the next one.
    """
    skus = [product["sku"] for product in products]
    series = daily_series(sales_docs, skus, today)
    units_by_date = {date.fromisoformat(doc["date"]): doc.get("units", {}) for doc in sales_docs}
    on_order: dict[str, int] = defaultdict(int)
    for order in open_orders:
        if order.get("status") == "approved":
            for line in order.get("lines", []):
                on_order[line["sku"]] += int(line["quantity"])
    rows = []
    for product in products:
        sku = product["sku"]
        lead = suppliers.get(product["supplier_id"], {}).get("lead_time_days", 2)
        cover = min(horizon_days, product.get("shelf_life_days") or horizon_days)
        window = lead + cover
        forecast, trend = local_forecast(series[sku], today, max(window, 7))
        festival_item = "deepavali" in product.get("festivals", [])
        profile = (
            festival_profile(units_by_date, sku, last_festival) if last_festival and festival_item else None
        )
        if profile:
            # The recent level already contains the current week's uplift; scale to each future day's.
            recent = statistics.fmean(
                uplift_on(profile, festival, today - timedelta(days=d)) for d in range(1, 15)
            )
            forecast = [
                value * uplift_on(profile, festival, today + timedelta(days=step)) / recent
                for step, value in enumerate(forecast)
            ]
        stock = product["on_hand"]
        stockout_day = None
        for step, demand in enumerate(forecast[:window]):
            if step == lead:
                stock += on_order[sku]
            stock -= demand
            if stock <= 0 and stockout_day is None:
                stockout_day = step
        per_day = sum(forecast[:7]) / 7
        need = sum(forecast[:window]) + product["safety_stock"] - product["on_hand"] - on_order[sku]
        recommended = math.ceil(need / product["case_pack"]) * product["case_pack"] if need > 0 else 0
        if stockout_day is not None and stockout_day < lead:
            risk = "critical"
        elif stockout_day is not None:
            risk = "high"
        elif recommended > 0:
            risk = "watch"
        else:
            risk = "ok"
        rows.append(
            {
                "sku": sku,
                "names": product["names"],
                "category": product["category"],
                "unit": product["unit"],
                "supplier_id": product["supplier_id"],
                "on_hand": product["on_hand"],
                "on_order": on_order[sku],
                "lead_time_days": lead,
                "per_day": round(per_day, 1),
                "days_left": round(product["on_hand"] / per_day, 1) if per_day > 0 else None,
                "stockout_date": (
                    (today + timedelta(days=stockout_day)).isoformat() if stockout_day is not None else None
                ),
                "trend_pct": round(trend * 100),
                "sold_last_7": sum(series[sku][-7:]),
                "forecast_next_7": round(sum(forecast[:7]), 1),
                "festival_peak_uplift": round(max(profile), 1) if profile else None,
                "recommended_quantity": recommended,
                "unit_cost_cents": product["cost_cents"],
                "risk": risk,
            }
        )
    rows.sort(
        key=lambda row: (RISK_ORDER[row["risk"]], row["days_left"] if row["days_left"] is not None else 1e9)
    )
    return rows


def reason_codes(row: dict, today: date, deepavali: date, rainy_season: bool) -> list[str]:
    """Short, translatable reasons the UI shows next to a recommendation."""
    reasons = []
    if row["risk"] == "critical":
        reasons.append("runs_out_before_delivery")
    elif row["risk"] == "high":
        reasons.append("runs_out_soon")
    if row["trend_pct"] >= 20:
        reasons.append("demand_rising")
    if row.get("festival_peak_uplift") and 0 <= (deepavali - today).days <= FESTIVAL_WEEKS * 7:
        reasons.append("deepavali")
    if rainy_season and row["sku"] in {"UMBRELLA", "PONCHO", "MOSQ-COIL"}:
        reasons.append("rainy_season")
    return reasons
