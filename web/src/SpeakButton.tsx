import { useEffect, useState } from "react";

import type { Lang } from "./i18n";
import type { ScreenProps } from "./screens/types";
import { speak, stopSpeaking } from "./util";

/** Reads a card aloud only when tapped; tapping again stops it. */
export function SpeakButton({ text, lang, t }: { text: string; lang: Lang; t: ScreenProps["t"] }) {
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => stopSpeaking(), []);

  const toggle = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    setSpeaking(true);
    void speak(text, lang, () => setSpeaking(false));
  };

  return (
    <button className="ghost speak" onClick={toggle} disabled={!text} aria-label={t("readAloud")}>
      {speaking ? `■ ${t("stop")}` : `🔊 ${t("readAloud")}`}
    </button>
  );
}
