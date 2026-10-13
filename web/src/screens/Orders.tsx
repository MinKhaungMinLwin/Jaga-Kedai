import { useCallback, useEffect, useState } from "react";

import { api, type Order } from "../api";
import type { Key } from "../i18n";
import { money, shortDate } from "../util";
import type { ScreenProps } from "./types";

function OrderCard({
  order,
  lang,
  t,
  onChanged,
}: ScreenProps & { order: Order; onChanged: () => void }) {
  const [quantities, setQuantities] = useState<Record<string, number>>(
    Object.fromEntries(order.lines.map((line) => [line.sku, line.quantity])),
  );
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const editable = order.status === "draft";
  const total = order.lines.reduce((sum, line) => sum + (quantities[line.sku] ?? 0) * line.unit_cost_cents, 0);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const step = (sku: string, delta: number) =>
    setQuantities((current) => ({ ...current, [sku]: Math.max(0, (current[sku] ?? 0) + delta) }));

  return (
    <article className={`card order status-${order.status}`}>
      <div className="card-head">
        <div>
          <h2>{order.supplier_name}</h2>
          <p className="muted">{t("deliveryBy", { date: shortDate(order.expected_delivery, lang) })}</p>
        </div>
        <span className={`status status-${order.status}`}>{t(`status_${order.status}` as Key)}</span>
      </div>
      <ul className="order-lines">
        {order.lines.map((line) => (
          <li key={line.sku}>
            <div>
              <strong>{line.names[lang]}</strong>
              <span className="reasons">
                {line.reasons.slice(0, 2).map((reason) => (
                  <span key={reason} className={`reason reason-${reason}`}>
                    {t(`reason_${reason}` as Key)}
                  </span>
                ))}
              </span>
              {editable && quantities[line.sku] !== line.suggested_quantity && (
                <span className="muted small">{t("suggested", { n: line.suggested_quantity })}</span>
              )}
            </div>
            {editable ? (
              <div className="stepper">
                <button aria-label="−" onClick={() => step(line.sku, -1)}>
                  −
                </button>
                <output aria-label={line.names[lang]}>{quantities[line.sku]}</output>
                <button aria-label="+" onClick={() => step(line.sku, 1)}>
                  +
                </button>
              </div>
            ) : (
              <strong className="qty">× {line.quantity}</strong>
            )}
          </li>
        ))}
      </ul>
      <p className="total">
        {t("total")}: <strong>{money(editable ? total : order.total_cents, lang)}</strong>
      </p>
      {order.status === "draft" && (
        <div className="row">
          <button
            className="primary big"
            disabled={busy || total === 0}
            onClick={() =>
              void run(() =>
                api.approve(
                  order.id,
                  order.lines.map((line) => ({ sku: line.sku, quantity: quantities[line.sku] ?? 0 })),
                ),
              )
            }
          >
            ✓ {t("approve")}
          </button>
          <button className="ghost" disabled={busy} onClick={() => void run(() => api.cancel(order.id))}>
            {t("cancel")}
          </button>
        </div>
      )}
      {order.status === "approved" && (
        <div className="stack">
          {order.whatsapp_url && (
            <a className="button whatsapp big" href={order.whatsapp_url} target="_blank" rel="noreferrer">
              {t("sendWhatsApp")}
            </a>
          )}
          <div className="row">
            {order.message && (
              <button
                className="secondary"
                onClick={() => {
                  void navigator.clipboard?.writeText(order.message ?? "");
                  setCopied(true);
                }}
              >
                {copied ? t("copied") : t("copyMessage")}
              </button>
            )}
            <button className="secondary" disabled={busy} onClick={() => void run(() => api.receive(order.id))}>
              📦 {t("received")}
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

export function OrdersScreen(props: ScreenProps) {
  const { t } = props;
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.orders().then(setOrders).catch(() => setOrders([]));
  }, []);
  useEffect(load, [load]);

  const prepare = async () => {
    setBusy(true);
    try {
      await api.draftOrders();
      load();
    } finally {
      setBusy(false);
    }
  };

  const active = (orders ?? []).filter((order) => order.status === "draft" || order.status === "approved");
  const done = (orders ?? []).filter((order) => order.status === "received").slice(0, 3);

  return (
    <div className="screen">
      <header className="screen-head">
        <h1>{t("ordersTitle")}</h1>
        <p className="banner info">🛑 {t("hardStop")}</p>
      </header>
      {orders === null && <p className="muted center">{t("loading")}</p>}
      {orders !== null && !active.some((order) => order.status === "draft") && (
        <button className="primary big" onClick={() => void prepare()} disabled={busy}>
          {busy ? t("loading") : t("prepareOrders")}
        </button>
      )}
      {orders !== null && active.length === 0 && <p className="muted">{t("noOrders")}</p>}
      {active.map((order) => (
        <OrderCard key={`${order.id}-${order.status}`} order={order} onChanged={load} {...props} />
      ))}
      {done.map((order) => (
        <OrderCard key={`${order.id}-${order.status}`} order={order} onChanged={load} {...props} />
      ))}
    </div>
  );
}
