import { expect, test, vi } from "vitest";

import { api } from "./api";
import { speak, stopSpeaking } from "./util";

test("a second tap while the voice is loading cancels it instead of playing twice", async () => {
  const plays: string[] = [];
  vi.stubGlobal(
    "Audio",
    class {
      onended: (() => void) | null = null;
      constructor(public src: string) {}
      play() {
        plays.push(this.src);
        return Promise.resolve();
      }
      pause() {}
    },
  );
  URL.createObjectURL = vi.fn((blob: Blob) => String(blob.size));
  URL.revokeObjectURL = vi.fn();
  let release!: (blob: Blob) => void;
  vi.spyOn(api, "speak").mockReturnValueOnce(new Promise((resolve) => (release = resolve)));
  const ended = vi.fn();

  const first = speak("hello", "en", ended);
  stopSpeaking(); // second tap: "Stop" while audio is still on its way
  expect(ended).toHaveBeenCalledOnce();
  release(new Blob(["x"]));
  await first;

  expect(plays).toEqual([]);
  vi.unstubAllGlobals();
});
