import { useEffect, useRef, useState } from "react";

import { api, type AskReply } from "../api";
import { recorderMime, speak, stopSpeaking } from "../util";
import type { ScreenProps } from "./types";

type Message = { role: "user"; text: string } | { role: "kaki"; reply: AskReply };

export function AskScreen({ lang, t, go }: ScreenProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, thinking]);
  useEffect(() => () => stopSpeaking(), []);

  const ask = async (input: { text?: string; audio?: Blob }, spoken: boolean) => {
    setError(null);
    if (input.text) setMessages((current) => [...current, { role: "user", text: input.text! }]);
    setThinking(true);
    try {
      const reply = await api.ask(lang, input);
      setMessages((current) => [
        ...current,
        // For voice questions, show what Kaki heard so the shopkeeper can tell if it misheard.
        ...(spoken ? [{ role: "user" as const, text: reply.heard }] : []),
        { role: "kaki" as const, reply },
      ]);
      void speak(reply.reply, lang);
    } catch {
      setError(t("error"));
    } finally {
      setThinking(false);
    }
  };

  const toggleMic = async () => {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    const mimeType = recorderMime();
    if (!mimeType || !navigator.mediaDevices?.getUserMedia) {
      setError(t("micBlocked"));
      return;
    }
    try {
      stopSpeaking();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const media = new MediaRecorder(stream, { mimeType });
      const chunks: Blob[] = [];
      media.ondataavailable = (event) => chunks.push(event.data);
      media.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
        const audio = new Blob(chunks, { type: mimeType.split(";")[0] });
        if (audio.size > 0) void ask({ audio }, true);
      };
      recorder.current = media;
      media.start();
      setRecording(true);
    } catch {
      setError(t("micBlocked"));
    }
  };

  return (
    <div className="screen ask">
      <header className="screen-head">
        <h1>{t("askTitle")}</h1>
        <p className="muted">{t("askHelp")}</p>
      </header>

      <div className="thread">
        {messages.length === 0 && (
          <div className="chips stacked">
            {t("suggestions")
              .split("|")
              .map((suggestion) => (
                <button key={suggestion} className="chip action" onClick={() => void ask({ text: suggestion }, false)}>
                  {suggestion}
                </button>
              ))}
          </div>
        )}
        {messages.map((message, index) =>
          message.role === "user" ? (
            <p key={index} className="bubble user">
              {message.text}
            </p>
          ) : (
            <div key={index} className="bubble kaki">
              <p>{message.reply.reply}</p>
              <div className="row">
                <button className="ghost small" onClick={() => void speak(message.reply.reply, lang)}>
                  🔊 {t("listen")}
                </button>
                {(message.reply.action === "draft_orders" || message.reply.action === "open_orders") && (
                  <button className="primary" onClick={() => go("orders")}>
                    {t("openOrders")}
                    {message.reply.orders.length > 0 && ` (${message.reply.orders.length})`}
                  </button>
                )}
                {message.reply.action === "scan_shelf" && (
                  <button className="primary" onClick={() => go("scan")}>
                    📷 {t("openScan")}
                  </button>
                )}
                {message.reply.action === "show_low_stock" && (
                  <button className="primary" onClick={() => go("today")}>
                    {t("openToday")}
                  </button>
                )}
              </div>
            </div>
          ),
        )}
        {thinking && (
          <p className="bubble kaki muted" aria-live="polite">
            {t("thinking")}
          </p>
        )}
        {error && <p className="banner error">{error}</p>}
        <div ref={end} />
      </div>

      <div className="composer">
        <button
          className={`mic ${recording ? "recording" : ""}`}
          onClick={() => void toggleMic()}
          disabled={thinking}
          aria-label={recording ? t("tapToStop") : t("tapToTalk")}
        >
          <span aria-hidden="true">{recording ? "■" : "🎙"}</span>
          <span>{recording ? t("listening") : t("tapToTalk")}</span>
        </button>
        <form
          className="type-row"
          onSubmit={(event) => {
            event.preventDefault();
            if (text.trim()) void ask({ text: text.trim() }, false);
            setText("");
          }}
        >
          <input
            aria-label={t("typeQuestion")}
            placeholder={t("typeQuestion")}
            value={text}
            maxLength={1000}
            onChange={(event) => setText(event.target.value)}
          />
          <button className="secondary" disabled={!text.trim() || thinking}>
            {t("send")}
          </button>
        </form>
      </div>
    </div>
  );
}
