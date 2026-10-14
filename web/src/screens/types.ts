import type { Key, Lang } from "../i18n";

export type Tab = "today" | "scan" | "orders" | "ask";

export interface ScreenProps {
  lang: Lang;
  t: (key: Key, vars?: Record<string, string | number>) => string;
  go: (tab: Tab) => void;
  /** Shows a message for 10 seconds; with `undo`, it carries an Undo button that reverses the action. */
  notify: (message: string, undo?: () => Promise<unknown>) => void;
}
