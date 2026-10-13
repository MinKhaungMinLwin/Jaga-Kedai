import { useCallback, useEffect, useState } from "react";

import { LANGS, translate, type Key, type Lang } from "./i18n";
import { AskScreen } from "./screens/Ask";
import { OrdersScreen } from "./screens/Orders";
import { ScanScreen } from "./screens/Scan";
import { TodayScreen } from "./screens/Today";
import type { Tab } from "./screens/types";
import { stopSpeaking } from "./util";

const LANG_KEY = "kedai-kaki.lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(LANG_KEY) as Lang | null;
    if (saved && LANGS.some((item) => item.code === saved)) return saved;
  } catch {
    // Storage can be unavailable in private browsing; fall back to Mandarin, the demo shop's default.
  }
  return "zh";
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

  const go = (next: Tab) => {
    stopSpeaking();
    setTab(next);
    window.scrollTo?.({ top: 0 });
  };

  const props = { lang, t, go };
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/icon.svg" alt="" width={36} height={36} />
          <div>
            <strong>Kedai Kaki</strong>
            <small>{t("tagline")}</small>
          </div>
        </div>
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
        {tab === "today" && <TodayScreen key={`today-${lang}`} {...props} />}
        {tab === "scan" && <ScanScreen {...props} />}
        {tab === "orders" && <OrdersScreen {...props} />}
        {tab === "ask" && <AskScreen key={`ask-${lang}`} {...props} />}
      </main>

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
