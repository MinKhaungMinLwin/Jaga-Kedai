import type { Lang } from "./i18n";

export type Names = Record<Lang, string>;
export type Risk = "critical" | "high" | "watch" | "ok";

export interface Outlook {
  sku: string;
  names: Names;
  category: string;
  unit: string;
  supplier_id: string;
  on_hand: number;
  on_order: number;
  lead_time_days: number;
  per_day: number;
  days_left: number | null;
  stockout_date: string | null;
  trend_pct: number;
  sold_last_7: number;
  festival_peak_uplift: number | null;
  recommended_quantity: number;
  risk: Risk;
  reasons: string[];
}

export interface Shop {
  name: string;
  owner: string;
  area: string;
  ai_backend?: string;
  model?: string;
  store_backend?: string;
}

export interface Today {
  shop: Shop;
  date: string;
  events: { type: string; date?: string; days_away?: number }[];
  running_low: Outlook[];
  regulars_not_seen: { name: string; days_since_visit: number; usual_skus: string[] }[];
  draft_orders: number;
  sold_last_7: number;
  credits: Credit[];
}

export interface Credit {
  id: string;
  name: string;
  amount_cents: number;
  note: string;
  status: "owing" | "paid";
  created_at: string;
}

export interface Briefing {
  headline: string;
  points: string[];
  source: "gemini" | "fallback";
}

export interface ScanItem {
  sku: string;
  names: Names;
  previous: number;
  count: number;
  confidence: number;
}

export interface Scan {
  id: string;
  status: string;
  items: ScanItem[];
  unrecognised: string[];
  note: string;
}

export interface OrderLine {
  sku: string;
  names: Names;
  unit: string;
  quantity: number;
  suggested_quantity: number;
  unit_cost_cents: number;
  on_hand: number;
  days_left: number | null;
  stockout_date: string | null;
  risk: Risk;
  reasons: string[];
}

export interface Order {
  id: string;
  supplier_id: string;
  supplier_name: string;
  status: "draft" | "approved" | "received" | "cancelled";
  lines: OrderLine[];
  total_cents: number;
  expected_delivery: string;
  message?: string;
  whatsapp_url?: string;
  supplier_whatsapp?: string;
}

export interface AskReply {
  heard: string;
  reply: string;
  action: "none" | "draft_orders" | "open_orders" | "scan_shelf" | "show_low_stock";
  skus: string[];
  orders: Order[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const SESSION_KEY = "jaga-kedai.session";

/** Anonymous id for this browser tab, so usage logs can show what one visitor costs. No personal data. */
function sessionId(): string {
  try {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = crypto.randomUUID();
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return "";
  }
}

function withSession(init: RequestInit): RequestInit {
  const headers = new Headers(init.headers);
  const id = sessionId();
  if (id) headers.set("X-Kedai-Session", id);
  return { ...init, headers };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, withSession(init));
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(response.status, body?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  today: () => request<Today>("/today"),
  briefing: (lang: Lang) => request<Briefing>(`/briefing?lang=${lang}`),
  scan: (photo: Blob, lang: Lang) => {
    const form = new FormData();
    form.append("image", photo, "shelf.jpg");
    form.append("lang", lang);
    return request<Scan>("/scan", { method: "POST", body: form });
  },
  confirmScan: (id: string, items: { sku: string; count: number }[]) =>
    request<{ updated: number }>(`/scans/${id}/confirm`, json({ items })),
  orders: () => request<Order[]>("/orders"),
  draftOrders: () => request<Order[]>("/orders/draft", json({})),
  approve: (id: string, lines: { sku: string; quantity: number }[]) =>
    request<Order>(`/orders/${id}/approve`, json({ lines })),
  receive: (id: string) => request<{ status: string }>(`/orders/${id}/receive`, { method: "POST" }),
  cancel: (id: string) => request<{ status: string }>(`/orders/${id}/cancel`, { method: "POST" }),
  addCredit: (entry: { name: string; amount_cents: number; note: string }) =>
    request<Credit>("/credits", json(entry)),
  creditPaid: (id: string) => request<{ status: string }>(`/credits/${id}/paid`, { method: "POST" }),
  undoCredit: (id: string) => request<{ status: string }>(`/credits/${id}/undo`, { method: "POST" }),
  undoOrder: (id: string) => request<{ status: string }>(`/orders/${id}/undo`, { method: "POST" }),
  setSupplierPhone: (supplierId: string, whatsapp: string) =>
    request<{ whatsapp: string }>(`/suppliers/${supplierId}/whatsapp`, { ...json({ whatsapp }), method: "PUT" }),
  ask: (lang: Lang, input: { text?: string; audio?: Blob }) => {
    const form = new FormData();
    form.append("lang", lang);
    if (input.text) form.append("text", input.text);
    if (input.audio) form.append("audio", input.audio, "question");
    return request<AskReply>("/ask", { method: "POST", body: form });
  },
  speak: async (text: string): Promise<Blob> => {
    const response = await fetch("/api/speak", withSession(json({ text })));
    if (!response.ok) throw new ApiError(response.status, "Speech unavailable");
    return response.blob();
  },
};
