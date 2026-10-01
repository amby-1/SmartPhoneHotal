/**
 * iPhone/Safari-friendly beep.
 * Web Audio alone is often muted by the hardware Silent switch;
 * HTMLAudioElement uses the media volume path instead.
 */

let audioCtx: AudioContext | null = null;
let unlocked = false;
let htmlAudio: HTMLAudioElement | null = null;
let beepUrl: string | null = null;

function getCtx(): AudioContext {
  if (!audioCtx) {
    const AC =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    audioCtx = new AC();
  }
  return audioCtx;
}

/** Build a short WAV (mono 16-bit) as a Blob URL. */
function createBeepUrl(freq = 880, durationSec = 0.12, peak = 0.55): string {
  const sampleRate = 22050;
  const n = Math.floor(sampleRate * durationSec);
  const data = new ArrayBuffer(44 + n * 2);
  const view = new DataView(data);

  const writeStr = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };

  writeStr(0, "RIFF");
  view.setUint32(4, 36 + n * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, n * 2, true);

  for (let i = 0; i < n; i++) {
    const t = i / sampleRate;
    const env =
      t < 0.01 ? t / 0.01 : t > durationSec - 0.03 ? (durationSec - t) / 0.03 : 1;
    const f = freq * (1 - 0.15 * (t / durationSec));
    const sample = Math.sin(2 * Math.PI * f * t) * peak * Math.max(0, env);
    const s = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, (s * 0x7fff) | 0, true);
  }

  return URL.createObjectURL(new Blob([data], { type: "audio/wav" }));
}

function ensureHtmlAudio(): HTMLAudioElement {
  if (!beepUrl) beepUrl = createBeepUrl();
  if (!htmlAudio) {
    htmlAudio = new Audio(beepUrl);
    htmlAudio.preload = "auto";
    htmlAudio.setAttribute("playsinline", "true");
  }
  return htmlAudio;
}

/** Must run inside a user gesture (tap / button). */
export async function unlockAudio(): Promise<void> {
  try {
    const ctx = getCtx();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
    // Silent buffer kick for Web Audio unlock on iOS
    const silent = ctx.createBuffer(1, 1, 22050);
    const src = ctx.createBufferSource();
    src.buffer = silent;
    src.connect(ctx.destination);
    src.start(0);

    const el = ensureHtmlAudio();
    el.volume = 0.01;
    el.currentTime = 0;
    await el.play().catch(() => undefined);
    el.pause();
    el.currentTime = 0;
    el.volume = 1;
    unlocked = true;
  } catch {
    // Still mark attempt; playBeep will retry
    unlocked = false;
  }
}

/**
 * Play a short firefly beep.
 * volume in [0, 1] — 0 skips (待機中など).
 */
export async function playBeep(volume: number): Promise<void> {
  if (volume <= 0) return;

  await unlockAudio();
  const v = Math.min(1, Math.max(0, volume));

  // Primary: HTMLAudio (works with Silent switch off OR media volume path)
  try {
    const el = ensureHtmlAudio();
    el.volume = Math.min(1, v);
    el.currentTime = 0;
    await el.play();
  } catch {
    // Fallback: Web Audio oscillator
    try {
      const ctx = getCtx();
      if (ctx.state === "suspended") await ctx.resume();
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(660, now + 0.08);
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(v * 0.7, now + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.14);
    } catch {
      // give up silently
    }
  }
}

export function isAudioUnlocked(): boolean {
  return unlocked;
}
