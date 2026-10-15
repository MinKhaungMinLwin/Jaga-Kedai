import { useCallback, useEffect, useState } from "react";

import { api, type Order } from "../api";
import type { Key } from "../i18n";
import { SpeakButton } from "../SpeakButton";
import { money, shortDate } from "../util";
import type { ScreenProps } from "./types";

function OrderCard({
  order,
  lang,
  t,
  notify,
  onChanged,
}: ScreenProps & { order: Order; onChanged: () => void }) {
  const [quantities, setQuantities] = useState<Record<string, number>>(
    Object.fromEntries(order.lines.map((line) => [line.sku, line.quantity])),
  );
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [phone, setPhone] = useState("");
  const editable = order.status === "draft";
  const total = order.lines.reduce((sum, line) => sum + (quantities[line.sku] ?? 0) * line.unit_cost_cents, 0);

  /** Runs an order action, then offers Undo for it. */
  const run = async (action: () => Promise<unknown>, toast?: Key) => {
    setBusy(true);
    try {
      await action();
      if (toast) notify(t(toast, { supplier: order.supplier_name }), () => api.undoOrder(order.id));
      onChanged();
    } catch {
      notify(t("error"));
    } finally {
      setBusy(false);
    }
  };

  const spoken = [
    order.supplier_name,
    t(`status_${order.status}` as Key),
    ...order.lines.map((line) => `${line.names[lang]} × ${editable ? quantities[line.sku] : line.quantity}`),
    `${t("total")} ${money(editable ? total : order.total_cents, lang)}`,
  ].join(". ");

  const step = (sku: string, delta: number) =>
    setQuantities((current) => ({ ...current, [sku]: Math.max(0, (current[sku] ?? 0) + delta) }));

  return (
    <article className={`card order status-${order.status}`}>
      <div className="card-head">
        <div>
          <h2>{order.supplier_name}</h2>
          <p className="muted">{t("deliveryBy", { date: shortDate(order.expected_delivery, lang) })}</p>
        </div>
        <div>
          <span className={`status status-${order.status}`}>{t(`status_${order.status}` as Key)}</span>
          <SpeakButton text={spoken} lang={lang} t={t} />
        </div>
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
              void run(
                () =>
                  api.approve(
                    order.id,
                    order.lines.map((line) => ({ sku: line.sku, quantity: quantities[line.sku] ?? 0 })),
                  ),
                "toastApproved",
              )
            }
          >
            ✓ {t("approve")}
          </button>
          <button
            className="ghost"
            disabled={busy}
            onClick={() => void run(() => api.cancel(order.id), "toastCancelled")}
          >
            {t("cancel")}
          </button>
        </div>
      )}
      {order.status === "approved" && (
        <div className="stack">
          {!order.supplier_whatsapp && (
            <form
              className="phone-form"
              onSubmit={(event) => {
                event.preventDefault();
                void run(() => api.setSupplierPhone(order.supplier_id, phone));
              }}
            >
              <label htmlFor={`phone-${order.id}`}>{t("supplierPhone")}</label>
              <p className="muted small">{t("phoneHelp")}</p>
              <div className="row">
                <input
                  id={`phone-${order.id}`}
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="+65 9123 4567"
                  pattern="\+?[\d ]{8,20}"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                />
                <button className="secondary" type="submit" disabled={busy || phone.replace(/\D/g, "").length < 8}>
                  {t("savePhone")}
                </button>
              </div>
            </form>
          )}
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
            <button className="secondary" disabled={busy} onClick={() => void run(() => api.receive(order.id), "toastReceived")}
            >
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
  const waiting = active.filter((order) => order.status === "draft").length;

  return (
    <div className="screen">
      <header className="screen-head">
        <h1>{t("ordersTitle")}</h1>
        <p className="banner info">🛑 {t("hardStop")}</p>
      </header>
      {orders === null && <p className="muted center">{t("loading")}</p>}
      {waiting > 0 && <p className="waiting">⏳ {t("waitingCount", { n: waiting })}</p>}
      {/* Always visible, so the owner never has to hunt for it; new drafts replace old ones. */}
      {orders !== null && (
        <button
          className={waiting > 0 ? "secondary big" : "primary big"}
          onClick={() => void prepare()}
          disabled={busy}
        >
          {busy ? t("loading") : waiting > 0 ? t("prepareNew") : t("prepareOrders")}
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
