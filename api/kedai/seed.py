"""Reproducible sales history for the demo shop.

Daily units per product follow weekday traffic, paydays, the inter-monsoon and
north-east monsoon rains (umbrellas, ponchos, mosquito coils, instant noodles)
and the run-up to Deepavali (ghee, atta, rice flour, murukku). Randomness is
keyed by date, so regenerating on another day reproduces the same history.

The demo shop re-seeds itself once per Singapore day (see ensure_demo_fresh), so
every judge sees a current, consistent story no matter when they visit.
"""

import argparse
import math
import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from kedai.catalog import CATALOG, REGULAR_LAST_SEEN, REGULARS, SHELF_LIFE_DAYS, SHOP, SUPPLIERS, Item
from kedai.store import Store, now

SINGAPORE = ZoneInfo("Asia/Singapore")
MIN_HISTORY_DAYS = 120
FESTIVAL_LOOKBACK_DAYS = 70  # baseline month + rush weeks before last Deepavali
COLLECTIONS = ("products", "suppliers", "daily_sales", "regulars", "scans", "orders", "activity", "credits")
# Demo credit book: (name, amount in cents, what they took, days ago).
DEMO_CREDITS = (
    ("Mdm Lim", 860, "Bread, kopi-O", 2),
    ("Cik Siti", 1590, "Rice 5kg", 1),
)
DEEPAVALI = {2025: date(2025, 10, 20), 2026: date(2026, 11, 8), 2027: date(2027, 10, 28)}
WEEKDAY = (0.92, 0.9, 0.93, 0.97, 1.08, 1.3, 1.25)


def today_sg() -> date:
    return datetime.now(SINGAPORE).date()


def next_deepavali(day: date) -> date:
    for year in (day.year, day.year + 1):
        festival = DEEPAVALI.get(year)
        if festival and festival >= day:
            return festival
    return date(day.year + 1, 11, 1)


def previous_deepavali(day: date) -> date | None:
    past = [festival for festival in DEEPAVALI.values() if festival < day]
    return max(past) if past else None


def rain_chance(day: date) -> float:
    # Afternoon thunderstorms in the Oct-Nov inter-monsoon, then the wet NE monsoon.
    return {10: 0.55, 11: 0.65, 12: 0.7, 1: 0.6, 4: 0.45, 5: 0.4}.get(day.month, 0.3)


def season_factor(item: Item, day: date, rainy: bool) -> float:
    season = item.season or ""
    if season.startswith("rain"):
        strength = 1.0 if season == "rain" else 0.25
        return 1 + strength * (1.8 if rainy else -0.15)
    if season.startswith("deepavali"):
        festival = next_deepavali(day)
        days_to = (festival - day).days
        last = DEEPAVALI.get(day.year)
        if last and 0 < (day - last).days <= 3:
            return 0.6
        if 0 <= days_to <= 35:
            peak = 3.2 if season == "deepavali" else 0.6
            return 1 + peak * (1 - days_to / 35) ** 2
    return 1.0


def poisson(rng: random.Random, lam: float) -> int:
    threshold, count, product = math.exp(-lam), 0, 1.0
    while True:
        product *= rng.random()
        if product <= threshold:
            return count
        count += 1


def units_for_day(day: date) -> dict[str, int]:
    rng = random.Random(f"kedai-{day.isoformat()}")
    rainy = rng.random() < rain_chance(day)
    traffic = WEEKDAY[day.weekday()] * (1.1 if 25 <= day.day <= 28 else 1.0)
    units = {}
    for item in CATALOG:
        expected = item.demand * traffic * season_factor(item, day, rainy)
        units[item.sku] = poisson(random.Random(f"{item.sku}-{day.isoformat()}"), expected)
    return units


def seed_shop(store: Store, shop_id: str, today: date | None = None) -> dict:
    today = today or today_sg()
    store.clear_shop(shop_id, COLLECTIONS)
    history = {}
    history_days = MIN_HISTORY_DAYS
    previous = previous_deepavali(today)
    if previous:
        # Reach back far enough for the forecast to learn last Deepavali's uplift.
        history_days = max(history_days, (today - previous).days + FESTIVAL_LOOKBACK_DAYS)
    for offset in range(history_days, 0, -1):
        day = today - timedelta(days=offset)
        history[day.isoformat()] = {"date": day.isoformat(), "units": units_for_day(day)}
    store.put_many(shop_id, "daily_sales", history)

    recent = [history[(today - timedelta(days=offset)).isoformat()]["units"] for offset in range(1, 8)]
    products = {}
    for item in CATALOG:
        velocity = max(item.demand * 0.5, sum(day[item.sku] for day in recent) / len(recent))
        products[item.sku] = {
            "sku": item.sku,
            "names": item.names,
            "category": item.category,
            "unit": item.unit,
            "price_cents": round(item.price * 100),
            "cost_cents": round(item.price * 100 * (1 - item.margin)),
            "supplier_id": item.supplier,
            "on_hand": max(1, round(velocity * item.cover_days)),
            "safety_stock": max(1, math.ceil(velocity * 1.5)),
            "case_pack": item.case_pack,
            "looks": item.looks,
            "aliases": list(item.aliases),
            "shelf_life_days": SHELF_LIFE_DAYS.get(item.sku),
            # Festival goods: the forecast learns their uplift from last year's sales.
            "festivals": ["deepavali"] if (item.season or "").startswith("deepavali") else [],
        }
    store.put_many(shop_id, "products", products)
    store.put_many(
        shop_id,
        "suppliers",
        {
            supplier.id: {
                "name": supplier.name,
                "lead_time_days": supplier.lead_time_days,
                "whatsapp": supplier.whatsapp,
                "language": supplier.language,
            }
            for supplier in SUPPLIERS
        },
    )
    store.put_many(
        shop_id,
        "regulars",
        {
            regular_id: {
                "name": name,
                "usual_skus": list(skus),
                "typical_gap_days": gap,
                "last_visit": (today - timedelta(days=REGULAR_LAST_SEEN[regular_id])).isoformat(),
            }
            for regular_id, name, skus, gap in REGULARS
        },
    )
    # Fixed IDs, so two requests re-seeding at the same moment cannot duplicate entries.
    store.put_many(
        shop_id,
        "credits",
        {
            f"demo-{index}": {
                "name": name,
                "amount_cents": amount_cents,
                "note": note,
                "status": "owing",
                "created_at": (now() - timedelta(days=days_ago)).isoformat(),
            }
            for index, (name, amount_cents, note, days_ago) in enumerate(DEMO_CREDITS)
        },
    )
    store.create(
        shop_id,
        "activity",
        {
            "type": "seed",
            "text": f"Demo shop prepared with {history_days} days of sales.",
            "created_at": now().isoformat(),
        },
    )
    store.put_shop(shop_id, {**SHOP, "demo": True, "seed_date": today.isoformat()})
    return {
        "shop_id": shop_id,
        "products": len(products),
        "days": len(history),
        "seed_date": today.isoformat(),
    }


def ensure_demo_fresh(store: Store, shop_id: str) -> bool:
    """Seed a missing shop, and re-seed the demo shop once per Singapore day."""
    shop = store.get_shop(shop_id)
    if shop is None or (shop.get("demo") and shop.get("seed_date") != today_sg().isoformat()):
        seed_shop(store, shop_id)
        return True
    return False


def main() -> None:
    from kedai.config import get_settings
    from kedai.store import build_store

    parser = argparse.ArgumentParser(description="Seed the Jaga Kedai demo shop")
    parser.add_argument("--shop-id", default=None)
    args = parser.parse_args()
    settings = get_settings()
    print(seed_shop(build_store(settings), args.shop_id or settings.shop_id))


if __name__ == "__main__":
    main()
