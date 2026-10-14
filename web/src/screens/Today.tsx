import { useEffect, useState } from "react";

import { api, type Briefing, type Credit, type Outlook, type Today as TodayData } from "../api";
import type { Key, Lang } from "../i18n";
import { money, shortDate, speak, stopSpeaking } from "../util";
import type { ScreenProps } from "./types";

/** The shop's pay-later notebook. Only the shopkeeper adds entries or marks them paid. */
export function CreditBook({
  entries,
  lang,
  t,
  onChange,
}: {
  entries: Credit[];
  lang: Lang;
  t: ScreenProps["t"];
  onChange: () => void;
}) {
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const cents = Math.round(Number(amount) * 100);
  const total = entries.reduce((sum, entry) => sum + entry.amount_cents, 0);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setFailed(false);
    try {
      await action();
      onChange();
      return true;
    } catch {
      setFailed(true);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const add = async () => {
    if (await run(() => api.addCredit({ name: name.trim(), amount_cents: cents, note: note.trim() }))) {
      setName("");
      setAmount("");
      setNote("");
    }
  };

  return (
    <section className="card credit-book">
      <div className="card-head">
        <h2>{t("creditTitle")}</h2>
        {total > 0 && <strong className="credit-total">{t("creditTotal", { amount: money(total, lang) })}</strong>}
      </div>
      {entries.length === 0 ? (
        <p className="muted">{t("creditEmpty")}</p>
      ) : (
        <ul className="credits">
          {entries.map((entry) => (
            <li key={entry.id}>
              <div>
                <strong>{entry.name}</strong> · {money(entry.amount_cents, lang)}
                {entry.note && <span className="muted"> · {entry.note}</span>}
              </div>
              <button className="secondary" disabled={busy} onClick={() => run(() => api.creditPaid(entry.id))}>
                ✓ {t("creditPaid")}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="credit-form"
        onSubmit={(event) => {
          event.preventDefault();
          void add();
        }}
      >
        <input
          aria-label={t("creditName")}
          placeholder={t("creditName")}
          value={name}
          maxLength={80}
          onChange={(event) => setName(event.target.value)}
        />
        <input
          aria-label={t("creditAmount")}
          placeholder={t("creditAmount")}
          type="number"
          inputMode="decimal"
          min="0.01"
          step="0.01"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
        <input
          aria-label={t("creditNote")}
          placeholder={t("creditNote")}
          value={note}
          maxLength={200}
          onChange={(event) => setNote(event.target.value)}
        />
        <button className="primary" type="submit" disabled={busy || !name.trim() || !(cents > 0)}>
          {t("creditAdd")}
        </button>
      </form>
      {failed && <p className="banner error">{t("error")}</p>}
    </section>
  );
}

export function LowStockRow({ row, lang, t }: { row: Outlook; lang: Lang; t: ScreenProps["t"] }) {
  return (
    <li className={`stock-row risk-${row.risk}`}>
      <div className="stock-main">
        <strong>{row.names[lang]}</strong>
        <span className="stock-numbers">
          {row.days_left !== null && t("daysLeft", { n: Math.max(0, Math.round(row.days_left)) })}
          {row.stockout_date && ` · ${t("outBy", { date: shortDate(row.stockout_date, lang) })}`}
          {row.on_order > 0 && ` · ${t("onOrder", { n: row.on_order })}`}
        </span>
        <span className="reasons">
          {row.reasons.map((reason) => (
            <span key={reason} className={`reason reason-${reason}`}>
              {t(`reason_${reason}` as Key)}
            </span>
          ))}
        </span>
        {row.festival_peak_uplift && row.reasons.includes("deepavali") && (
          <span className="learned">{t("lastYear", { x: row.festival_peak_uplift })}</span>
        )}
      </div>
      {row.recommended_quantity > 0 && (
        <span className="suggest-pill">{t("suggest", { n: row.recommended_quantity })}</span>
      )}
    </li>
  );
}

export function TodayScreen({ lang, t, go }: ScreenProps) {
  const [data, setData] = useState<TodayData | null>(null);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.today().then(setData).catch(() => setError(t("error")));
  }, [t]);

  useEffect(() => {
    setBriefing(null);
    api.briefing(lang).then(setBriefing).catch(() => setBriefing(null));
    return () => stopSpeaking();
  }, [lang]);

  const prepare = async () => {
    setBusy(true);
    try {
      await api.draftOrders();
      go("orders");
    } catch {
      setError(t("error"));
    } finally {
      setBusy(false);
    }
  };

  const listen = () => {
    if (!briefing) return;
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    setSpeaking(true);
    void speak([briefing.headline, ...briefing.points].join(" "), lang, () => setSpeaking(false));
  };

  if (error) return <p className="banner error">{error}</p>;
  if (!data) return <p className="muted center">{t("loading")}</p>;

  return (
    <div className="screen">
      <header className="screen-head">
        <h1>{t("greeting", { owner: data.shop.owner })}</h1>
        <p className="muted">
          {data.shop.name} · {shortDate(data.date, lang)}
        </p>
        <div className="chips">
          {data.events.map((event) => (
            <span key={event.type} className={`chip event-${event.type}`}>
              {event.type === "deepavali"
                ? `🪔 ${t("deepavaliIn", { n: event.days_away ?? 0 })}`
                : event.type === "rainy_season"
                  ? `🌧 ${t("rainy")}`
                  : `💰 ${t("payday")}`}
            </span>
          ))}
        </div>
      </header>

      <section className="card briefing" aria-live="polite">
        <div className="card-head">
          <h2>{t("briefing")}</h2>
          <button className="ghost" onClick={listen} disabled={!briefing}>
            {speaking ? `■ ${t("stop")}` : `🔊 ${t("listen")}`}
          </button>
        </div>
        {briefing ? (
          <>
            <p className="headline">{briefing.headline}</p>
            <ul className="points">
              {briefing.points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">{t("loading")}</p>
        )}
      </section>

      {data.draft_orders > 0 ? (
        <button className="primary big" onClick={() => go("orders")}>
          {t("reviewOrders", { n: data.draft_orders })}
        </button>
      ) : (
        data.running_low.length > 0 && (
          <button className="primary big" onClick={prepare} disabled={busy}>
            {busy ? t("loading") : t("prepareOrders")}
          </button>
        )
      )}

      <section className="card">
        <h2>{t("runningLow")}</h2>
        {data.running_low.length === 0 ? (
          <p className="muted">{t("allGood")}</p>
        ) : (
          <ul className="stock-list">
            {data.running_low.slice(0, 10).map((row) => (
              <LowStockRow key={row.sku} row={row} lang={lang} t={t} />
            ))}
          </ul>
        )}
      </section>

      {data.regulars_not_seen.length > 0 && (
        <section className="card">
          <h2>{t("regulars")}</h2>
          <ul className="regulars">
            {data.regulars_not_seen.map((regular) => (
              <li key={regular.name}>
                <strong>{regular.name}</strong>
                <span className="muted">{t("regularLine", { n: regular.days_since_visit })}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <CreditBook
        entries={data.credits ?? []}
        lang={lang}
        t={t}
        onChange={() => api.today().then(setData).catch(() => setError(t("error")))}
      />

      <div className="quick">
        <button className="secondary big" onClick={() => go("scan")}>
          📷 {t("quickScan")}
        </button>
        <button className="secondary big" onClick={() => go("ask")}>
          🎙 {t("quickAsk")}
        </button>
      </div>
    </div>
  );
}
