from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from kedai import ai, usage
from kedai.config import Settings
from kedai.forecast import festival_profile, local_forecast
from kedai.main import create_app
from kedai.seed import seed_shop
from kedai.store import MemoryStore

TODAY = date(2026, 10, 13)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("kedai.main.today_sg", lambda: TODAY)
    monkeypatch.setattr("kedai.seed.today_sg", lambda: TODAY)
    store = MemoryStore()
    seed_shop(store, "demo", TODAY)
    app = create_app(Settings(KEDAI_AI_BACKEND="off", KEDAI_ADMIN_TOKEN="secret"), store)
    with TestClient(app) as test_client:
        yield test_client


def test_forecast_tracks_level_and_trend():
    flat, trend = local_forecast([10] * 56, TODAY, 7)
    assert all(9.5 <= value <= 10.5 for value in flat) and trend == 0
    _, rising = local_forecast([5] * 42 + [10] * 14, TODAY, 7)
    assert rising > 0.3


def test_festival_profile_learns_uplift_and_ignores_flat_items():
    festival = date(2025, 10, 20)
    days = {festival - timedelta(days=offset): {} for offset in range(0, 70)}
    for day in days:
        to_go = (festival - day).days
        days[day] = {"GHEE": 9 if 1 <= to_go <= 7 else 3, "SOAP": 3}
    profile = festival_profile(days, "GHEE", festival)
    assert profile[0] == pytest.approx(3.0) and profile[1] == pytest.approx(1.0)
    assert festival_profile(days, "SOAP", festival) is None


def test_today_flags_deepavali_and_monsoon_risks(client):
    today = client.get("/api/today").json()
    assert today["date"] == TODAY.isoformat()
    assert {event["type"] for event in today["events"]} >= {"deepavali", "rainy_season"}
    low = {row["sku"]: row for row in today["running_low"]}
    assert low["ATTA-5KG"]["risk"] == "critical"
    assert "deepavali" in low["GHEE-800"]["reasons"] and low["GHEE-800"]["festival_peak_uplift"] >= 2
    assert "rainy_season" in low["UMBRELLA"]["reasons"] and "deepavali" not in low["UMBRELLA"]["reasons"]
    assert all(row["recommended_quantity"] % 1 == 0 for row in today["running_low"])
    assert low["BREAD-WHITE"]["recommended_quantity"] <= 40, "perishables are capped at shelf life"
    assert {item["name"] for item in today["regulars_not_seen"]} == {"Mdm Lim", "Mr Rajan"}


def test_orders_need_approval_and_only_received_stock_counts(client):
    drafts = client.post("/api/orders/draft", json={}).json()
    assert drafts and all(order["status"] == "draft" for order in drafts)
    murugan = next(order for order in drafts if order["supplier_id"] == "murugan")
    atta = next(line for line in murugan["lines"] if line["sku"] == "ATTA-5KG")
    stock_before = next(p for p in client.get("/api/products").json() if p["sku"] == "ATTA-5KG")["on_hand"]

    approved = client.post(
        f"/api/orders/{murugan['id']}/approve",
        json={"lines": [{"sku": "ATTA-5KG", "quantity": atta["quantity"] + 4}]},
    ).json()
    assert approved["status"] == "approved"
    assert f"x {atta['quantity'] + 4} bag" in approved["message"]
    assert approved["whatsapp_url"].startswith("https://wa.me/?text=")
    assert client.post(f"/api/orders/{murugan['id']}/approve").status_code == 409

    product = next(p for p in client.get("/api/products").json() if p["sku"] == "ATTA-5KG")
    assert product["on_hand"] == stock_before and product["on_order"] == atta["quantity"] + 4

    assert client.post(f"/api/orders/{murugan['id']}/receive").status_code == 200
    product = next(p for p in client.get("/api/products").json() if p["sku"] == "ATTA-5KG")
    assert product["on_hand"] == stock_before + atta["quantity"] + 4 and product["on_order"] == 0

    redrafted = client.post("/api/orders/draft", json={}).json()
    listed = client.get("/api/orders").json()
    assert {order["id"] for order in listed if order["status"] == "draft"} == {
        order["id"] for order in redrafted
    }


def test_scan_is_a_proposal_until_confirmed(client, monkeypatch):
    monkeypatch.setattr(
        ai,
        "scan_shelf",
        lambda *args, **kwargs: ai.ScanResult(
            items=[
                ai.ScanItem(sku="MILO-1KG", count=5, confidence=0.9),
                ai.ScanItem(sku="FAKE", count=1, confidence=1),
            ],
            note="ok",
        ),
    )
    before = next(p for p in client.get("/api/products").json() if p["sku"] == "MILO-1KG")["on_hand"]
    scan = client.post(
        "/api/scan", files={"image": ("s.jpg", b"jpeg", "image/jpeg")}, data={"lang": "zh"}
    ).json()
    assert [item["sku"] for item in scan["items"]] == ["MILO-1KG"] and scan["items"][0]["previous"] == before
    assert next(p for p in client.get("/api/products").json() if p["sku"] == "MILO-1KG")["on_hand"] == before

    assert client.post(
        f"/api/scans/{scan['id']}/confirm", json={"items": [{"sku": "MILO-1KG", "count": 7}]}
    ).json() == {"updated": 1}
    assert next(p for p in client.get("/api/products").json() if p["sku"] == "MILO-1KG")["on_hand"] == 7
    assert (
        client.post(
            f"/api/scans/{scan['id']}/confirm", json={"items": [{"sku": "MILO-1KG", "count": 1}]}
        ).status_code
        == 409
    )
    assert client.post("/api/scan", files={"image": ("s.txt", b"x", "text/plain")}).status_code == 415


def test_ask_drafts_orders_but_never_approves(client, monkeypatch):
    seen = {}

    def fake_ask(settings, **kwargs):
        seen.update(kwargs)
        return ai.AskResult(
            heard="要订什么", reply="草稿准备好了", action="draft_orders", skus=["GHEE-800", "NOPE"]
        )

    monkeypatch.setattr(ai, "ask", fake_ask)
    response = client.post("/api/ask", data={"lang": "zh", "text": "要订什么"}).json()
    assert response["action"] == "draft_orders"
    assert [line["sku"] for order in response["orders"] for line in order["lines"]] == ["GHEE-800"]
    assert all(order["status"] == "draft" for order in response["orders"])
    assert seen["lang"] == "zh" and any(item["sku"] == "GHEE-800" for item in seen["context"]["running_low"])
    assert seen["context"]["running_low"][0]["product"] != seen["context"]["running_low"][0]["sku"]
    assert client.post("/api/ask", data={"lang": "en"}).status_code == 422


def test_ai_failures_degrade_gracefully(client):
    briefing = client.get("/api/briefing?lang=en").json()
    assert briefing["source"] == "fallback" and briefing["points"]
    assert client.post("/api/ask", data={"lang": "en", "text": "hi"}).status_code == 503
    assert client.post("/api/speak", json={"text": "hello"}).status_code == 503


def test_manual_count_and_admin_reset(client):
    assert client.post("/api/stock/count", json={"items": [{"sku": "GHEE-800", "count": 40}]}).json() == {
        "updated": 1
    }
    assert next(p for p in client.get("/api/products").json() if p["sku"] == "GHEE-800")["on_hand"] == 40
    assert client.post("/api/admin/reset").status_code == 403
    assert client.post("/api/admin/reset", headers={"x-admin-token": "secret"}).status_code == 200
    assert next(p for p in client.get("/api/products").json() if p["sku"] == "GHEE-800")["on_hand"] != 40


def test_credit_book_records_and_settles_pay_later_sales(client):
    assert [entry["name"] for entry in client.get("/api/today").json()["credits"]] == ["Cik Siti", "Mdm Lim"]

    added = client.post("/api/credits", json={"name": " Mr Rajan ", "amount_cents": 1240, "note": "Ghee"})
    assert added.status_code == 201 and added.json()["name"] == "Mr Rajan"
    assert client.get("/api/credits").json()[0]["id"] == added.json()["id"]
    assert client.post("/api/credits", json={"name": "Mr Rajan", "amount_cents": 0}).status_code == 422

    assert client.post(f"/api/credits/{added.json()['id']}/paid").json() == {"status": "paid"}
    assert client.post(f"/api/credits/{added.json()['id']}/paid").status_code == 409
    assert client.post("/api/credits/nope/paid").status_code == 404
    assert "Mr Rajan" not in {entry["name"] for entry in client.get("/api/credits").json()}
    assert "credit_paid" in {item["type"] for item in client.get("/api/activity").json()}


def test_whatsapp_order_is_english_and_uses_saved_number(client):
    drafts = client.post("/api/orders/draft", json={}).json()
    huat = next(order for order in drafts if order["supplier_id"] == "huat")
    approved = client.post(f"/api/orders/{huat['id']}/approve").json()
    assert approved["message"].startswith("Hi Ah Huat Trading, this is Ah Tan Provision Shop")
    assert "Order please:" in approved["message"]

    assert client.put("/api/suppliers/huat/whatsapp", json={"whatsapp": "abc"}).status_code == 422
    assert client.put("/api/suppliers/nope/whatsapp", json={"whatsapp": "+65 9123 4567"}).status_code == 404
    assert client.put("/api/suppliers/huat/whatsapp", json={"whatsapp": "+65 9123 4567"}).json() == {
        "whatsapp": "6591234567"
    }
    listed = next(order for order in client.get("/api/orders").json() if order["id"] == huat["id"])
    assert listed["whatsapp_url"].startswith("https://wa.me/6591234567?text=")


def test_undo_steps_orders_and_credits_back(client):
    drafts = client.post("/api/orders/draft", json={}).json()
    order = drafts[0]
    sku = order["lines"][0]["sku"]
    stock = next(p for p in client.get("/api/products").json() if p["sku"] == sku)["on_hand"]
    client.post(f"/api/orders/{order['id']}/approve")
    client.post(f"/api/orders/{order['id']}/receive")
    assert client.post(f"/api/orders/{order['id']}/undo").json() == {"status": "approved"}
    assert next(p for p in client.get("/api/products").json() if p["sku"] == sku)["on_hand"] == stock
    assert client.post(f"/api/orders/{order['id']}/undo").json() == {"status": "draft"}
    assert client.post(f"/api/orders/{order['id']}/undo").status_code == 409
    client.post(f"/api/orders/{order['id']}/cancel")
    assert client.post(f"/api/orders/{order['id']}/undo").json() == {"status": "draft"}

    entry = client.post("/api/credits", json={"name": "Mr Rajan", "amount_cents": 500}).json()
    client.post(f"/api/credits/{entry['id']}/paid")
    assert client.post(f"/api/credits/{entry['id']}/undo").json() == {"status": "owing"}
    assert client.post(f"/api/credits/{entry['id']}/undo").json() == {"status": "removed"}
    assert entry["id"] not in {item["id"] for item in client.get("/api/credits").json()}


def test_each_gemini_call_logs_tokens_and_estimated_cost(monkeypatch):
    lines = []
    monkeypatch.setattr(usage, "_emit", lines.append)
    usage.session_id.set("visitor-1234")
    meta = SimpleNamespace(prompt_token_count=4000, candidates_token_count=300, thoughts_token_count=100)
    entry = usage.record(
        "ask", "gemini-3.5-flash-lite", SimpleNamespace(usage_metadata=meta), shop_id="demo", project="p"
    )
    assert lines == [entry]
    assert (
        entry["event"] == "gemini_usage"
        and entry["feature"] == "ask"
        and entry["session_id"] == "visitor-1234"
    )
    assert (entry["input_tokens"], entry["output_tokens"]) == (4000, 400)
    assert entry["cost_usd"] == (4000 * 0.30 + 400 * 2.50) / 1_000_000
    unknown = usage.record("ask", "some-new-model", SimpleNamespace(), shop_id="demo", project=None)
    assert unknown["cost_usd"] is None and unknown["input_tokens"] == 0


def test_api_tags_ai_calls_with_the_visitor_session(client, monkeypatch):
    seen = []

    def fake_briefing(settings, **kwargs):
        seen.append(usage.session_id.get())
        return ai.Briefing(headline="Morning", points=[])

    monkeypatch.setattr(ai, "briefing", fake_briefing)
    client.get("/api/briefing?lang=en", headers={"X-Kedai-Session": "abc12345-visitor"})
    client.get("/api/briefing?lang=zh", headers={"X-Kedai-Session": "bad id!"})
    assert seen == ["abc12345-visitor", None]


def test_demo_shop_reseeds_on_a_new_day(monkeypatch):
    store = MemoryStore()
    seed_shop(store, "demo", TODAY - timedelta(days=3))
    monkeypatch.setattr("kedai.main.today_sg", lambda: TODAY)
    monkeypatch.setattr("kedai.seed.today_sg", lambda: TODAY)
    client = TestClient(create_app(Settings(KEDAI_AI_BACKEND="off"), store))
    assert client.get("/api/shop").json()["seed_date"] == TODAY.isoformat()
