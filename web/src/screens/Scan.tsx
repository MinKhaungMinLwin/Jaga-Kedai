import { useRef, useState } from "react";

import { api, type Scan } from "../api";
import { downscale } from "../util";
import type { ScreenProps } from "./types";

type Stage = "idle" | "counting" | "review" | "saved" | "error";

export function ScanScreen({ lang, t, go }: ScreenProps) {
  const camera = useRef<HTMLInputElement>(null);
  const gallery = useRef<HTMLInputElement>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [saved, setSaved] = useState(0);

  const reset = () => {
    setStage("idle");
    setScan(null);
    setPreview(null);
  };

  const onPhoto = async (file: File | undefined) => {
    if (!file) return;
    setPreview(URL.createObjectURL(file));
    setStage("counting");
    try {
      const result = await api.scan(await downscale(file), lang);
      setScan(result);
      setCounts(Object.fromEntries(result.items.map((item) => [item.sku, item.count])));
      setStage("review");
    } catch {
      setStage("error");
    }
  };

  const save = async () => {
    if (!scan) return;
    const result = await api.confirmScan(
      scan.id,
      scan.items.map((item) => ({ sku: item.sku, count: counts[item.sku] ?? item.count })),
    );
    setSaved(result.updated);
    setStage("saved");
  };

  return (
    <div className="screen">
      <header className="screen-head">
        <h1>{t("scanTitle")}</h1>
        <p className="muted">{t("scanHelp")}</p>
      </header>

      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(event) => void onPhoto(event.target.files?.[0])}
      />
      <input ref={gallery} type="file" accept="image/*" hidden onChange={(event) => void onPhoto(event.target.files?.[0])} />

      {preview && <img className="shelf-preview" src={preview} alt="" />}

      {stage === "idle" && (
        <div className="stack">
          <button className="primary big" onClick={() => camera.current?.click()}>
            📷 {t("takePhoto")}
          </button>
          <button className="secondary" onClick={() => gallery.current?.click()}>
            {t("choosePhoto")}
          </button>
        </div>
      )}

      {stage === "counting" && <p className="banner info" aria-live="polite">{t("counting")}</p>}

      {stage === "error" && (
        <div className="stack">
          <p className="banner error">{t("scanFailed")}</p>
          <button className="primary big" onClick={reset}>
            {t("scanAgain")}
          </button>
        </div>
      )}

      {stage === "review" && scan && (
        <section className="card">
          <h2>{t("checkCounts")}</h2>
          {scan.note && <p className="muted">{scan.note}</p>}
          <ul className="count-list">
            {scan.items.map((item) => (
              <li key={item.sku}>
                <div>
                  <strong>{item.names[lang]}</strong>
                  <span className="muted">
                    {t("before")}: {item.previous}
                  </span>
                  {item.confidence < 0.7 && <span className="reason reason-runs_out_soon">{t("unsure")}</span>}
                </div>
                <label className="count-input">
                  <span className="sr-only">
                    {t("counted")} {item.names[lang]}
                  </span>
                  <input
                    type="number"
                    inputMode="numeric"
                    min={0}
                    value={counts[item.sku] ?? item.count}
                    onChange={(event) =>
                      setCounts((current) => ({ ...current, [item.sku]: Math.max(0, Number(event.target.value) || 0) }))
                    }
                  />
                </label>
              </li>
            ))}
          </ul>
          {scan.unrecognised.length > 0 && (
            <p className="muted">
              {t("notInList")}: {scan.unrecognised.join(", ")}
            </p>
          )}
          <div className="row">
            <button className="primary big" onClick={() => void save()} disabled={!scan.items.length}>
              ✓ {t("saveCounts")}
            </button>
            <button className="ghost" onClick={reset}>
              {t("discard")}
            </button>
          </div>
        </section>
      )}

      {stage === "saved" && (
        <div className="stack">
          <p className="banner success">{t("saved", { n: saved })}</p>
          <button className="primary big" onClick={reset}>
            {t("scanAgain")}
          </button>
          <button className="secondary" onClick={() => go("today")}>
            {t("openToday")}
          </button>
        </div>
      )}
    </div>
  );
}
