import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";

const names = { en: "Pure ghee 800g", zh: "酥油 800克", ms: "Minyak sapi (ghee) 800g", ta: "நெய் 800கி" };
const today = {
  shop: { name: "Ah Tan Provision Shop", owner: "Uncle Tan", area: "Toa Payoh" },
  date: "2026-10-13",
  events: [{ type: "deepavali", date: "2026-11-08", days_away: 26 }],
  running_low: [
    {
      sku: "GHEE-800", names, category: "Indian groceries", unit: "tin", supplier_id: "murugan", on_hand: 3,
      on_order: 0, lead_time_days: 3, per_day: 0.9, days_left: 3.3, stockout_date: "2026-10-16", trend_pct: -30,
      sold_last_7: 4, festival_peak_uplift: 3.2, recommended_quantity: 12, risk: "high",
      reasons: ["runs_out_soon", "deepavali"],
    },
  ],
  regulars_not_seen: [{ name: "Mr Rajan", days_since_visit: 24, usual_skus: ["GHEE-800"] }],
  draft_orders: 0,
  sold_last_7: 400,
  credits: [{ id: "c1", name: "Mdm Lim", amount_cents: 860, note: "Bread", status: "owing", created_at: "2026-10-12" }],
};
const draft = {
  id: "o1", supplier_id: "murugan", supplier_name: "Sri Murugan Wholesale", status: "draft",
  expected_delivery: "2026-10-16", total_cents: 15204,
  lines: [{ sku: "GHEE-800", names, unit: "tin", quantity: 12, suggested_quantity: 12, unit_cost_cents: 1267,
    on_hand: 3, days_left: 3.3, stockout_date: "2026-10-16", risk: "high", reasons: ["deepavali"] }],
};

let calls: { url: string; body?: unknown; session?: string | null }[] = [];

beforeEach(() => {
  calls = [];
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body, session: new Headers(init?.headers).get("X-Kedai-Session") });
    const reply = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url.startsWith("/api/today")) return reply(today);
    if (url.startsWith("/api/briefing")) return reply({ headline: "早安", points: ["酥油快卖完了"], source: "gemini" });
    if (url === "/api/orders") return reply([draft]);
    if (url === "/api/orders/o1/approve") return reply({ ...draft, status: "approved" });
    return reply({});
  }));
});
afterEach(() => vi.unstubAllGlobals());

test("home speaks the shopkeeper's language and explains the Deepavali learning", async () => {
  render(<App />);
  expect(await screen.findByText("酥油 800克")).toBeInTheDocument();
  expect(screen.getByText("去年屠妖节多卖了 3.2 倍")).toBeInTheDocument();
  expect(screen.getByText("Mr Rajan")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "EN" }));
  expect(await screen.findByText("Pure ghee 800g")).toBeInTheDocument();
  expect(screen.getByText("Last Deepavali sold 3.2× more")).toBeInTheDocument();
  expect(localStorage.getItem("jaga-kedai.lang")).toBe("en");
});

test("orders are only approved by the shopkeeper, with edited quantities", async () => {
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /订货/ }));
  expect(await screen.findByText("您批准之前，不会向供应商发出任何订单。", { exact: false })).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: "+" }));
  expect(screen.getByText("Kaki 建议 12")).toBeInTheDocument();
  expect(calls.some((call) => call.url.includes("/approve"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: /批准/ }));
  await waitFor(() => expect(calls.some((call) => call.url === "/api/orders/o1/approve")).toBe(true));
  const approve = calls.find((call) => call.url === "/api/orders/o1/approve");
  expect(JSON.parse(String(approve?.body))).toEqual({ lines: [{ sku: "GHEE-800", quantity: 13 }] });
});

test("the credit book is written and settled only by the shopkeeper", async () => {
  const view = within(render(<App />).container);
  expect(await view.findByText("赊账本")).toBeInTheDocument();
  expect(view.getByText("Mdm Lim")).toBeInTheDocument();
  fireEvent.click(view.getByRole("button", { name: /已还钱/ }));
  await waitFor(() => expect(calls.some((call) => call.url === "/api/credits/c1/paid")).toBe(true));

  const write = view.getByRole("button", { name: "记下来" });
  expect(write).toBeDisabled();
  fireEvent.change(view.getByLabelText("名字"), { target: { value: "Mr Rajan" } });
  fireEvent.change(view.getByLabelText("金额（$）"), { target: { value: "12.40" } });
  fireEvent.change(view.getByLabelText("拿了什么"), { target: { value: "Ghee" } });
  fireEvent.click(write);
  await waitFor(() => expect(calls.some((call) => call.url === "/api/credits")).toBe(true));
  const added = calls.find((call) => call.url === "/api/credits");
  expect(JSON.parse(String(added?.body))).toEqual({ name: "Mr Rajan", amount_cents: 1240, note: "Ghee" });
});

test("approving an order can be undone, and text size is remembered", async () => {
  const view = within(render(<App />).container);
  fireEvent.click(view.getByRole("button", { name: /字体大小/ }));
  expect(localStorage.getItem("jaga-kedai.size")).toBe("1");

  fireEvent.click(await view.findByRole("button", { name: /订货/ }));
  expect(await view.findByText(/1 张订单等您确认/)).toBeInTheDocument();
  fireEvent.click(await view.findByRole("button", { name: /批准/ }));
  fireEvent.click(await view.findByRole("button", { name: /撤销/ }));
  await waitFor(() => expect(calls.some((call) => call.url === "/api/orders/o1/undo")).toBe(true));
});

test("every API call carries the same anonymous session id", async () => {
  const view = within(render(<App />).container);
  await view.findByText("Mdm Lim");
  const sessions = new Set(calls.map((call) => call.session));
  expect(sessions.size).toBe(1);
  expect([...sessions][0]).toMatch(/^[0-9a-f-]{36}$/);
});
