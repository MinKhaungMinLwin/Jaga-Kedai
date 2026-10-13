import type { Key, Lang } from "../i18n";

export type Tab = "today" | "scan" | "orders" | "ask";

export interface ScreenProps {
  lang: Lang;
  t: (key: Key, vars?: Record<string, string | number>) => string;
  go: (tab: Tab) => void;
}
