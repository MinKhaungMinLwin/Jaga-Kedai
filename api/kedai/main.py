"""Kedai Kaki API (Cloud Run).

Hard stops: Gemini can propose shelf counts and draft orders, but stock only
changes when the shopkeeper confirms a scan or marks an order received, and an
order only leaves the shop when the shopkeeper approves it and taps Send.
"""

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import date, timedelta
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from kedai import ai
from kedai.config import Settings, get_settings
from kedai.forecast import plan, reason_codes
from kedai.seed import ensure_demo_fresh, next_deepavali, previous_deepavali, rain_chance, seed_shop, today_sg
from kedai.store import Store, build_store, now
from kedai.tracing import configure_tracing

logger = logging.getLogger(__name__)
Lang = Literal["en", "zh", "ms", "ta"]
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-m4a", "audio/aac"}


class ScanConfirmLine(BaseModel):
    sku: str
    count: int = Field(ge=0, le=100_000)


class ScanConfirm(BaseModel):
    items: list[ScanConfirmLine] = Field(min_length=1, max_length=200)


class ManualCount(BaseModel):
    items: list[ScanConfirmLine] = Field(min_length=1, max_length=200)


class OrderLineEdit(BaseModel):
    sku: str
    quantity: int = Field(ge=0, le=100_000)


class OrderApprove(BaseModel):
    lines: list[OrderLineEdit] | None = None


class DraftRequest(BaseModel):
    skus: list[str] | None = None


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: str) -> None:
        current = time.monotonic()
        with self.lock:
            window = self.hits[key]
            while window and current - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                raise HTTPException(status_code=429, detail="Too many AI requests; please wait a minute")
            window.append(current)


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = store or build_store(settings)
    configure_tracing(settings)
    limiter = RateLimiter(settings.ai_requests_per_minute)
    plan_cache: dict[str, tuple[float, list[dict]]] = {}
    briefing_cache: dict[tuple[str, str], dict] = {}

    app = FastAPI(title="Kedai Kaki API", version="0.1.0")
    app.state.settings = settings
    app.state.store = store
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
    )

    # -- helpers ----------------------------------------------------------------

    def shop_id() -> str:
        return settings.shop_id

    def fresh_shop() -> dict:
        if ensure_demo_fresh(store, settings.shop_id):
            invalidate()
        shop = store.get_shop(settings.shop_id)
        if shop is None:
            raise HTTPException(status_code=503, detail="Shop is not ready")
        return shop

    def invalidate() -> None:
        plan_cache.clear()
        briefing_cache.clear()

    def ai_guard(request: Request) -> None:
        forwarded = request.headers.get("x-forwarded-for", "")
        client_ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
        limiter.check(client_ip)

    def suppliers() -> dict[str, dict]:
        return {doc["id"]: doc for doc in store.list(shop_id(), "suppliers")}

    def outlook(horizon_days: int = 7) -> list[dict]:
        key = f"{horizon_days}"
        cached = plan_cache.get(key)
        if cached and time.monotonic() - cached[0] < 60:
            return cached[1]
        today = today_sg()
        deepavali = next_deepavali(today)
        previous = previous_deepavali(today)
        sales = store.list(
            shop_id(), "daily_sales", where=("date", ">=", (today - timedelta(days=60)).isoformat())
        )
        if previous:
            # Last year's festival window, for the learned Deepavali uplift.
            sales += store.list(
                shop_id(),
                "daily_sales",
                where=[
                    ("date", ">=", (previous - timedelta(days=64)).isoformat()),
                    ("date", "<=", previous.isoformat()),
                ],
            )
        rows = plan(
            store.list(shop_id(), "products"),
            suppliers(),
            sales,
            store.list(shop_id(), "orders", where=("status", "==", "approved")),
            today,
            horizon_days,
            festival=deepavali,
            last_festival=previous,
        )
        rainy = rain_chance(today) >= 0.5
        for row in rows:
            row["reasons"] = reason_codes(row, today, deepavali, rainy)
        plan_cache[key] = (time.monotonic(), rows)
        return rows

    def log(text: str, kind: str, **extra) -> None:
        store.create(
            shop_id(), "activity", {"type": kind, "text": text, "created_at": now().isoformat(), **extra}
        )

    def events(today: date) -> list[dict]:
        deepavali = next_deepavali(today)
        items = []
        if 0 <= (deepavali - today).days <= 45:
            items.append(
                {"type": "deepavali", "date": deepavali.isoformat(), "days_away": (deepavali - today).days}
            )
        if rain_chance(today) >= 0.5:
            items.append({"type": "rainy_season", "label": "Inter-monsoon / NE monsoon: frequent heavy rain"})
        if today.day >= 20:
            items.append({"type": "payday", "label": "Month-end payday: busier weekend"})
        return items

    def overdue_regulars(today: date) -> list[dict]:
        overdue = []
        for regular in store.list(shop_id(), "regulars"):
            days = (today - date.fromisoformat(regular["last_visit"])).days
            if days >= max(7, 3 * regular["typical_gap_days"]):
                overdue.append(
                    {"name": regular["name"], "days_since_visit": days, "usual_skus": regular["usual_skus"]}
                )
        return sorted(overdue, key=lambda item: -item["days_since_visit"])

    def ai_context(lang: str) -> dict:
        today = today_sg()
        rows = outlook()
        names = {row["sku"]: row["names"].get(lang, row["names"]["en"]) for row in rows}
        sups = suppliers()
        return {
            "today": today.isoformat(),
            "weekday": today.strftime("%A"),
            "events": events(today),
            "running_low": [
                {
                    "sku": row["sku"],
                    "product": names[row["sku"]],
                    "on_hand": row["on_hand"],
                    "sells_per_day": row["per_day"],
                    "days_left": row["days_left"],
                    "runs_out_on": row["stockout_date"],
                    "supplier": sups.get(row["supplier_id"], {}).get("name"),
                    "delivery_days": row["lead_time_days"],
                    "recommended_order": row["recommended_quantity"],
                    "last_deepavali_peak_sales_multiple": row["festival_peak_uplift"],
                    "reasons": row["reasons"],
                }
                for row in rows
                if row["risk"] != "ok"
            ][:10],
            "best_sellers_last_7_days": [
                {"product": names[row["sku"]], "sold": row["sold_last_7"]}
                for row in sorted(rows, key=lambda row: -row["sold_last_7"])[:5]
            ],
            "regulars_not_seen": [
                {**item, "usual_items": [names.get(sku, sku) for sku in item.pop("usual_skus")]}
                for item in overdue_regulars(today)
            ],
            "orders_waiting_for_approval": [
                {"supplier": order["supplier_name"], "items": len(order["lines"])}
                for order in store.list(shop_id(), "orders", where=("status", "==", "draft"))
            ],
        }

    def draft_orders(only_skus: list[str] | None = None) -> list[dict]:
        rows = outlook()
        sups = suppliers()
        wanted = [
            row
            for row in rows
            if row["recommended_quantity"] > 0
            and (only_skus is None or row["sku"] in only_skus)
            and (only_skus is not None or row["risk"] in ("critical", "high", "watch"))
        ]
        for order in store.list(shop_id(), "orders", where=("status", "==", "draft")):
            store.update(
                shop_id(), "orders", order["id"], {"status": "replaced", "updated_at": now().isoformat()}
            )
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in wanted:
            grouped[row["supplier_id"]].append(row)
        created = []
        for supplier_id, items in sorted(grouped.items()):
            supplier = sups.get(supplier_id, {"name": supplier_id, "lead_time_days": 2})
            lines = [
                {
                    "sku": row["sku"],
                    "names": row["names"],
                    "unit": row["unit"],
                    "quantity": row["recommended_quantity"],
                    "suggested_quantity": row["recommended_quantity"],
                    "unit_cost_cents": row["unit_cost_cents"],
                    "on_hand": row["on_hand"],
                    "days_left": row["days_left"],
                    "stockout_date": row["stockout_date"],
                    "risk": row["risk"],
                    "reasons": row["reasons"],
                }
                for row in items
            ]
            order = {
                "supplier_id": supplier_id,
                "supplier_name": supplier["name"],
                "status": "draft",
                "lines": lines,
                "total_cents": sum(line["quantity"] * line["unit_cost_cents"] for line in lines),
                "expected_delivery": (today_sg() + timedelta(days=supplier["lead_time_days"])).isoformat(),
                "created_at": now().isoformat(),
                "updated_at": now().isoformat(),
            }
            order["id"] = store.create(shop_id(), "orders", order)
            created.append(order)
        if created:
            log(f"Kaki prepared {len(created)} draft orders for review.", "orders_drafted")
        return created

    def whatsapp_message(shop: dict, order: dict, supplier: dict) -> tuple[str, str]:
        delivery = date.fromisoformat(order["expected_delivery"]).strftime("%a %d %b")
        lines = "\n".join(
            f"- {line['names']['en']} x {line['quantity']} {line['unit']}"
            for line in order["lines"]
            if line["quantity"] > 0
        )
        text = (
            f"Hi {supplier.get('name', '')}, this is {shop['name']} ({shop['area']}).\n"
            f"Order please:\n{lines}\nDeliver by {delivery} if possible. Thank you!"
        )
        number = "".join(ch for ch in (supplier.get("whatsapp") or "") if ch.isdigit())
        return text, f"https://wa.me/{number}?text={quote(text)}"

    # -- routes -----------------------------------------------------------------

    @app.get("/api/health")
    def health():
        return {"status": "ok", "store": store.backend, "ai": settings.resolved_ai_backend}

    @app.get("/api/shop")
    def get_shop():
        shop = fresh_shop()
        return {
            **shop,
            "ai_backend": settings.resolved_ai_backend,
            "model": settings.model,
            "store_backend": store.backend,
        }

    @app.get("/api/today")
    def today_view():
        shop = fresh_shop()
        today = today_sg()
        rows = outlook()
        drafts = store.list(shop_id(), "orders", where=("status", "==", "draft"))
        return {
            "shop": shop,
            "date": today.isoformat(),
            "events": events(today),
            "running_low": [row for row in rows if row["risk"] != "ok"],
            "regulars_not_seen": overdue_regulars(today),
            "draft_orders": len(drafts),
            "sold_last_7": sum(row["sold_last_7"] for row in rows),
        }

    @app.get("/api/products")
    def products():
        fresh_shop()
        return outlook()

    @app.get("/api/briefing")
    def get_briefing(request: Request, lang: Lang = "en"):
        shop = fresh_shop()
        key = (today_sg().isoformat(), lang)
        if key in briefing_cache:
            return briefing_cache[key]
        context = ai_context(lang)
        ai_guard(request)
        try:
            result = ai.briefing(settings, shop=shop, context=context, lang=lang)
        except Exception as exc:  # The home screen must load even when Gemini is unavailable.
            logger.warning("Briefing fallback: %s", type(exc).__name__)
            return {
                "headline": f"Good morning, {shop['owner']}!",
                "points": [
                    f"{item['product']}: about {item['days_left']} days left"
                    for item in context["running_low"][:3]
                ],
                "source": "fallback",
            }
        payload = {**result.model_dump(), "source": "gemini"}
        briefing_cache[key] = payload
        return payload

    @app.post("/api/scan")
    async def scan(request: Request, image: UploadFile = File(...), lang: Lang = Form("en")):
        fresh_shop()
        mime = (image.content_type or "").lower()
        if mime not in IMAGE_TYPES:
            raise HTTPException(status_code=415, detail="Please upload a photo (JPEG, PNG, WebP or HEIC)")
        data = await image.read()
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Photo is too large")
        ai_guard(request)
        products_by_sku = {p["sku"]: p for p in store.list(shop_id(), "products")}
        try:
            from starlette.concurrency import run_in_threadpool

            result = await run_in_threadpool(
                ai.scan_shelf, settings, data, mime, list(products_by_sku.values()), lang
            )
        except Exception as exc:
            logger.warning("Scan failed: %s", type(exc).__name__)
            raise HTTPException(
                status_code=503, detail="Kaki could not read the photo; please count manually"
            ) from exc
        items = [
            {
                "sku": item.sku,
                "names": products_by_sku[item.sku]["names"],
                "previous": products_by_sku[item.sku]["on_hand"],
                "count": item.count,
                "confidence": round(item.confidence, 2),
            }
            for item in sorted(result.items, key=lambda item: item.sku)
            if item.sku in products_by_sku
        ]
        scan_doc = {
            "status": "proposed",
            "items": items,
            "unrecognised": result.unrecognised,
            "note": result.note,
            "created_at": now().isoformat(),
        }
        scan_doc["id"] = store.create(shop_id(), "scans", scan_doc)
        return scan_doc

    @app.post("/api/scans/{scan_id}/confirm")
    def confirm_scan(scan_id: str, payload: ScanConfirm):
        fresh_shop()
        scan_doc = store.get(shop_id(), "scans", scan_id)
        if scan_doc is None:
            raise HTTPException(status_code=404, detail="Scan not found")
        if scan_doc["status"] != "proposed":
            raise HTTPException(status_code=409, detail="This scan was already handled")
        updated = apply_counts(payload.items)
        store.update(
            shop_id(),
            "scans",
            scan_id,
            {
                "status": "confirmed",
                "confirmed": [line.model_dump() for line in payload.items],
                "confirmed_at": now().isoformat(),
            },
        )
        log(f"Shelf count confirmed for {updated} products.", "scan_confirmed", scan_id=scan_id)
        return {"updated": updated}

    @app.post("/api/stock/count")
    def manual_count(payload: ManualCount):
        fresh_shop()
        updated = apply_counts(payload.items)
        log(f"Manual stock count saved for {updated} products.", "manual_count")
        return {"updated": updated}

    def apply_counts(lines: list[ScanConfirmLine]) -> int:
        known = {p["sku"] for p in store.list(shop_id(), "products")}
        updated = 0
        for line in lines:
            if line.sku in known:
                store.update(
                    shop_id(), "products", line.sku, {"on_hand": line.count, "counted_at": now().isoformat()}
                )
                updated += 1
        invalidate()
        return updated

    @app.get("/api/orders")
    def list_orders():
        fresh_shop()
        orders = store.list(shop_id(), "orders", order_by="created_at", descending=True, limit=40)
        return [order for order in orders if order["status"] != "replaced"]

    @app.post("/api/orders/draft")
    def create_drafts(payload: DraftRequest | None = None):
        fresh_shop()
        return draft_orders(payload.skus if payload else None)

    @app.post("/api/orders/{order_id}/approve")
    def approve_order(order_id: str, payload: OrderApprove | None = None):
        shop = fresh_shop()
        order = store.get(shop_id(), "orders", order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] != "draft":
            raise HTTPException(status_code=409, detail="Only draft orders can be approved")
        lines = order["lines"]
        if payload and payload.lines is not None:
            edits = {line.sku: line.quantity for line in payload.lines}
            lines = [{**line, "quantity": edits.get(line["sku"], line["quantity"])} for line in lines]
        lines = [line for line in lines if line["quantity"] > 0]
        if not lines:
            raise HTTPException(status_code=422, detail="Nothing to order")
        supplier = store.get(shop_id(), "suppliers", order["supplier_id"]) or {"name": order["supplier_name"]}
        fields = {
            "status": "approved",
            "lines": lines,
            "total_cents": sum(line["quantity"] * line["unit_cost_cents"] for line in lines),
            "approved_at": now().isoformat(),
            "updated_at": now().isoformat(),
        }
        text, link = whatsapp_message(shop, {**order, **fields}, supplier)
        fields.update({"message": text, "whatsapp_url": link})
        store.update(shop_id(), "orders", order_id, fields)
        invalidate()
        log(
            f"Order to {order['supplier_name']} approved ({len(lines)} items).",
            "order_approved",
            order_id=order_id,
        )
        return {**order, **fields}

    @app.post("/api/orders/{order_id}/receive")
    def receive_order(order_id: str):
        fresh_shop()
        order = store.get(shop_id(), "orders", order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] != "approved":
            raise HTTPException(status_code=409, detail="Only approved orders can be received")
        for line in order["lines"]:
            store.increment(shop_id(), "products", line["sku"], "on_hand", int(line["quantity"]))
        store.update(shop_id(), "orders", order_id, {"status": "received", "received_at": now().isoformat()})
        invalidate()
        log(f"Delivery from {order['supplier_name']} received.", "order_received", order_id=order_id)
        return {"status": "received"}

    @app.post("/api/orders/{order_id}/cancel")
    def cancel_order(order_id: str):
        fresh_shop()
        order = store.get(shop_id(), "orders", order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] not in ("draft", "approved"):
            raise HTTPException(status_code=409, detail="This order can no longer be cancelled")
        store.update(shop_id(), "orders", order_id, {"status": "cancelled", "updated_at": now().isoformat()})
        invalidate()
        return {"status": "cancelled"}

    @app.post("/api/ask")
    async def ask_kaki(
        request: Request,
        lang: Lang = Form("en"),
        text: str | None = Form(None, max_length=1000),
        audio: UploadFile | None = File(None),
    ):
        from starlette.concurrency import run_in_threadpool

        shop = fresh_shop()
        audio_bytes = None
        audio_mime = None
        if audio is not None:
            audio_mime = (audio.content_type or "").split(";")[0].lower()
            if audio_mime not in AUDIO_TYPES:
                raise HTTPException(status_code=415, detail="Unsupported audio format")
            audio_bytes = await audio.read()
            if len(audio_bytes) > settings.max_upload_bytes:
                raise HTTPException(status_code=413, detail="Recording is too long")
        if not audio_bytes and not (text and text.strip()):
            raise HTTPException(status_code=422, detail="Say or type a question")
        ai_guard(request)
        context = await run_in_threadpool(ai_context, lang)
        try:
            result = await run_in_threadpool(
                lambda: ai.ask(
                    settings,
                    shop=shop,
                    context=context,
                    lang=lang,
                    text=text,
                    audio=audio_bytes,
                    audio_mime=audio_mime,
                )
            )
        except Exception as exc:
            logger.warning("Ask failed: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Kaki is not available right now") from exc
        payload = result.model_dump()
        payload["orders"] = []
        if result.action == "draft_orders":
            skus = [sku for sku in result.skus if sku in {row["sku"] for row in outlook()}] or None
            payload["orders"] = await run_in_threadpool(draft_orders, skus)
        return payload

    @app.post("/api/speak")
    def speak(request: Request, payload: SpeakRequest):
        ai_guard(request)
        try:
            audio = ai.speak(settings, payload.text)
        except Exception as exc:
            logger.warning("Speech failed: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Speech is not available") from exc
        return Response(content=audio, media_type="audio/wav")

    @app.get("/api/activity")
    def activity():
        fresh_shop()
        return store.list(shop_id(), "activity", order_by="created_at", descending=True, limit=20)

    @app.post("/api/admin/reset")
    def reset(x_admin_token: str | None = Header(default=None)):
        if not settings.admin_token or x_admin_token != settings.admin_token:
            raise HTTPException(status_code=403, detail="Forbidden")
        invalidate()
        return seed_shop(store, settings.shop_id)

    return app


app = create_app()
