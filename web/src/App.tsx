import { useCallback, useEffect, useRef, useState } from "react";

import { LANGS, translate, type Key, type Lang } from "./i18n";
import { AskScreen } from "./screens/Ask";
import { OrdersScreen } from "./screens/Orders";
import { ScanScreen } from "./screens/Scan";
import { TodayScreen } from "./screens/Today";
import type { Tab } from "./screens/types";
import { stopSpeaking } from "./util";

const LANG_KEY = "jaga-kedai.lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(LANG_KEY) as Lang | null;
    if (saved && LANGS.some((item) => item.code === saved)) return saved;
  } catch {
    // Storage can be unavailable in private browsing; fall back to Mandarin, the demo shop's default.
  }
  return "zh";
}

const SIZE_KEY = "jaga-kedai.size";
// Every font-size in styles.css is multiplied by --text-scale, so text grows while the layout reflows.
const SIZES = [
  { scale: 1, label: "A" },
  { scale: 1.15, label: "A+" },
  { scale: 1.3, label: "A++" },
];
const TOAST_MS = 10_000;

function initialSize(): number {
  try {
    const saved = Number(localStorage.getItem(SIZE_KEY));
    if (saved > 0 && saved < SIZES.length) return saved;
  } catch {
    // Storage can be unavailable; default to normal size.
  }
  return 0;
}

interface Toast {
  id: number;
  message: string;
  undo?: () => Promise<unknown>;
}

const TABS: { id: Tab; icon: string; label: Key }[] = [
  { id: "today", icon: "🏠", label: "tabToday" },
  { id: "scan", icon: "📷", label: "tabScan" },
  { id: "orders", icon: "🧾", label: "tabOrders" },
  { id: "ask", icon: "🎙", label: "tabAsk" },
];

export function App() {
  const [lang, setLang] = useState<Lang>(initialLang);
  const [tab, setTab] = useState<Tab>("today");
  const t = useCallback(
    (key: Key, vars?: Record<string, string | number>) => translate(lang, key, vars),
    [lang],
  );

  useEffect(() => {
    document.documentElement.lang = LANGS.find((item) => item.code === lang)?.locale ?? "en";
    try {
      localStorage.setItem(LANG_KEY, lang);
    } catch {
      // Remembering the language is a convenience only.
    }
  }, [lang]);

  const [size, setSize] = useState(initialSize);
  const [toast, setToast] = useState<Toast | null>(null);
  // Bumped after an undo so the current screen remounts and reloads its data.
  const [version, setVersion] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    document.documentElement.style.setProperty("--text-scale", String(SIZES[size].scale));
    try {
      localStorage.setItem(SIZE_KEY, String(size));
    } catch {
      // Remembering the size is a convenience only.
    }
  }, [size]);

  useEffect(() => () => clearTimeout(timer.current), []);

  const notify = useCallback((message: string, undo?: () => Promise<unknown>) => {
    clearTimeout(timer.current);
    setToast({ id: Date.now(), message, undo });
    timer.current = setTimeout(() => setToast(null), TOAST_MS);
  }, []);

  const undoLast = async () => {
    const action = toast?.undo;
    clearTimeout(timer.current);
    setToast(null);
    if (!action) return;
    try {
      await action();
      notify(t("toastUndone"));
    } catch {
      notify(t("error"));
    }
    setVersion((current) => current + 1);
  };

  const go = (next: Tab) => {
    stopSpeaking();
    setTab(next);
    window.scrollTo?.({ top: 0 });
  };

  const props = { lang, t, go, notify };
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/icon.svg" alt="" width={36} height={36} />
          <div>
            <strong>Jaga Kedai</strong>
            <small>{t("tagline")}</small>
          </div>
        </div>
        <button
          className="text-size"
          aria-label={`${t("textSize")}: ${SIZES[size].label}`}
          title={t("textSize")}
          onClick={() => setSize((current) => (current + 1) % SIZES.length)}
        >
          {SIZES[(size + 1) % SIZES.length].label}
        </button>
        <div className="langs" role="group" aria-label="Language">
          {LANGS.map((item) => (
            <button
              key={item.code}
              className={item.code === lang ? "active" : ""}
              aria-pressed={item.code === lang}
              onClick={() => setLang(item.code)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </header>

      <main>
        {tab === "today" && <TodayScreen key={`today-${lang}-${version}`} {...props} />}
        {tab === "scan" && <ScanScreen key={`scan-${version}`} {...props} />}
        {tab === "orders" && <OrdersScreen key={`orders-${version}`} {...props} />}
        {tab === "ask" && <AskScreen key={`ask-${lang}`} {...props} />}
      </main>

      {toast && (
        <div className="toast" role="status" key={toast.id}>
          <span>{toast.message}</span>
          {toast.undo && (
            <button className="undo" onClick={() => void undoLast()}>
              ↩ {t("undo")}
            </button>
          )}
        </div>
      )}

      <nav className="tabs" aria-label="Sections">
        {TABS.map((item) => (
          <button
            key={item.id}
            className={tab === item.id ? "active" : ""}
            aria-current={tab === item.id ? "page" : undefined}
            onClick={() => go(item.id)}
          >
            <span aria-hidden="true">{item.icon}</span>
            {t(item.label)}
          </button>
        ))}
      </nav>
    </div>
  );
}
