/** Inter-tap intervals → mean frequency (Hz). Needs at least 2 taps. */
export function tapsToFrequencyHz(tapsMs: number[]): number | null {
  if (tapsMs.length < 2) return null;
  const sorted = [...tapsMs].sort((a, b) => a - b);
  const intervals: number[] = [];
  for (let i = 1; i < sorted.length; i++) {
    const dt = sorted[i]! - sorted[i - 1]!;
    if (dt > 80 && dt < 5000) intervals.push(dt);
  }
  if (intervals.length === 0) return null;
  const meanMs =
    intervals.reduce((sum, v) => sum + v, 0) / intervals.length;
  return 1000 / meanMs;
}

export function frequenciesFromSession(
  taps: { deskId: string; tMs: number; experiment: string }[],
  experiment: "experiment1" | "experiment2",
): { deskId: string; hz: number }[] {
  const byDesk = new Map<string, number[]>();
  for (const tap of taps.filter((t) => t.experiment === experiment)) {
    const list = byDesk.get(tap.deskId) ?? [];
    list.push(tap.tMs);
    byDesk.set(tap.deskId, list);
  }
  const result: { deskId: string; hz: number }[] = [];
  for (const [deskId, times] of byDesk) {
    const hz = tapsToFrequencyHz(times);
    if (hz != null) result.push({ deskId, hz });
  }
  return result;
}

export function histogram(
  values: number[],
  binWidth = 0.1,
): { center: number; count: number }[] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const start = Math.floor(min / binWidth) * binWidth;
  const end = Math.ceil(max / binWidth) * binWidth;
  const bins: { center: number; count: number }[] = [];
  for (let edge = start; edge < end + binWidth / 2; edge += binWidth) {
    bins.push({ center: edge + binWidth / 2, count: 0 });
  }
  for (const v of values) {
    const idx = Math.min(
      bins.length - 1,
      Math.max(0, Math.floor((v - start) / binWidth)),
    );
    bins[idx]!.count += 1;
  }
  return bins;
}
