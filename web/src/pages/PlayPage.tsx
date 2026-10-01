import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { joinSession, onSessionUpdate, sendTap } from "../lib/api";
import { playBeep, unlockAudio } from "../lib/audio";
import type { SessionView } from "../types";

interface StoredJoin {
  code: string;
  deskId: string;
}

function loadJoin(): StoredJoin | null {
  const raw = sessionStorage.getItem("hotaru");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredJoin;
  } catch {
    return null;
  }
}

export default function PlayPage() {
  const join = loadJoin();
  const [session, setSession] = useState<SessionView | null>(null);
  const [flash, setFlash] = useState(false);
  const [localTaps, setLocalTaps] = useState(0);
  const [audioHint, setAudioHint] = useState(true);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (!join) return;
    let cancelled = false;
    (async () => {
      const result = await joinSession(join.code, join.deskId);
      if (!cancelled && result.session) {
        setSession(result.session);
        if (result.session.experimentStartedAt) {
          startRef.current = result.session.experimentStartedAt;
        }
      }
    })();
    const off = onSessionUpdate((s) => {
      if (s.code === join.code) {
        setSession(s);
        if (s.experimentStartedAt) {
          startRef.current = s.experimentStartedAt;
        }
      }
    });
    return () => {
      cancelled = true;
      off();
    };
  }, [join?.code, join?.deskId]);

  if (!join) {
    return (
      <section className="card-panel">
        <h1>未参加</h1>
        <p className="muted">先にセッションへ参加してください。</p>
        <Link className="btn primary" to="/join">
          参加画面へ
        </Link>
      </section>
    );
  }

  const active =
    session?.experiment === "experiment1" ||
    session?.experiment === "experiment2";
  const volume = session?.volume ?? 0;
  const label =
    session?.experiment === "experiment1"
      ? "実験1 · 音弱"
      : session?.experiment === "experiment2"
        ? "実験2 · 音量MAX"
        : "待機中";

  async function handleTap() {
    // Always unlock on gesture (iOS needs this before experiment 2)
    await unlockAudio();
    if (!active || !join) return;
    const origin = startRef.current ?? session?.experimentStartedAt ?? Date.now();
    const tMs = Date.now() - origin;
    // 実験1は無音、実験2のみ音を出す
    if (volume > 0) {
      await playBeep(volume);
      setAudioHint(false);
    }
    setFlash(true);
    window.setTimeout(() => setFlash(false), 120);
    setLocalTaps((n: number) => n + 1);
    await sendTap(join.code, tMs);
  }

  return (
    <section className={`play-screen ${flash ? "flash" : ""}`}>
      <div className="play-meta">
        <div>
          <p className="eyebrow">{label}</p>
          <h1>{join.deskId}</h1>
          <p className="muted">
            セッション {join.code} · タップ {localTaps}
          </p>
        </div>
        <p className="status-pill">{active ? "タップ可" : "開始待ち"}</p>
      </div>
      {audioHint && (
        <p className="muted" style={{ margin: "0 0 0.5rem" }}>
          実験1は無音、実験2で音が出ます。iPhone
          はサイレントスイッチをオフにし、メディア音量を上げてください。
        </p>
      )}
      <button
        type="button"
        className={`tap-pad ${active ? "live" : "idle"}`}
        onPointerDown={(e) => {
          e.preventDefault();
          void handleTap();
        }}
      >
        <span>TAP</span>
        <small>
          {active
            ? session?.experiment === "experiment1"
              ? "無音です。心地よい一定リズムでやさしくタップ"
              : "音量MAX想定。心地よい一定リズムでやさしくタップ"
            : "講師の開始合図を待ってください"}
        </small>
      </button>
    </section>
  );
}
