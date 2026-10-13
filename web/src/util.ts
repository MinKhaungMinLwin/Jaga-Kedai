import { api } from "./api";
import { LANGS, localeOf, type Lang } from "./i18n";

export function money(cents: number, lang: Lang): string {
  return new Intl.NumberFormat(localeOf(lang), { style: "currency", currency: "SGD" }).format(cents / 100);
}

export function shortDate(iso: string, lang: Lang): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(localeOf(lang), {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

let current: { stop: () => void } | null = null;

export function stopSpeaking() {
  current?.stop();
  current = null;
}

/** Gemini text-to-speech, falling back to the browser's own voices. */
export async function speak(text: string, lang: Lang, onEnd?: () => void): Promise<void> {
  stopSpeaking();
  try {
    const audio = new Audio(URL.createObjectURL(await api.speak(text)));
    current = { stop: () => audio.pause() };
    audio.onended = () => onEnd?.();
    await audio.play();
  } catch {
    if (!("speechSynthesis" in window)) return onEnd?.();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = LANGS.find((item) => item.code === lang)?.speech ?? "en-SG";
    utterance.rate = 0.95;
    utterance.onend = () => onEnd?.();
    current = { stop: () => window.speechSynthesis.cancel() };
    window.speechSynthesis.speak(utterance);
  }
}

/** Shrink phone photos to at most 1600px so uploads are fast on mobile data. */
export async function downscale(file: File, maxSide = 1600): Promise<Blob> {
  if (!("createImageBitmap" in window)) return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => canvas.toBlob((blob) => resolve(blob ?? file), "image/jpeg", 0.85));
  } catch {
    return file;
  }
}

export function recorderMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find((type) =>
    MediaRecorder.isTypeSupported(type),
  ) ?? "";
}
