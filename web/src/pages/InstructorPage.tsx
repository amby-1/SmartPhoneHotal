import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  clearExperiment,
  createSession,
  fetchSession,
  joinSession,
  onSessionUpdate,
  startExperiment,
  stopExperiment,
} from "../lib/api";
import { frequenciesFromSession, histogram } from "../lib/frequency";
import type { ExportPayload, SessionView } from "../types";
import FrequencyChart from "../components/FrequencyChart";

export default function InstructorPage() {
  const { code: codeParam } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState<SessionView | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [qrUrl, setQrUrl] = useState("");

  useEffect(() => {
    if (!codeParam) return;
    let cancelled = false;
    (async () => {
      try {
        const s = await fetchSession(codeParam);
        if (cancelled) return;
        setSession(s);
        await joinSession(s.code, "", "instructor");
      } catch {
        if (!cancelled) setError("セッションを取得できません");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [codeParam]);

  useEffect(() => {
    if (!session) return;
    const off = onSessionUpdate((s) => {
      if (s.code === session.code) setSession(s);
    });
    return off;
  }, [session?.code]);

  useEffect(() => {
    if (!session) return;
    const joinPath = `${window.location.origin}/join/${session.code}`;
    setQrUrl(
      `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(joinPath)}`,
    );
  }, [session?.code]);

  const freq1 = useMemo(
    () =>
      session
        ? frequenciesFromSession(session.taps, "experiment1")
        : [],
    [session],
  );
  const freq2 = useMemo(
    () =>
      session
        ? frequenciesFromSession(session.taps, "experiment2")
        : [],
    [session],
  );
  const hist1 = useMemo(
    () => histogram(freq1.map((f) => f.hz), 0.1),
    [freq1],
  );
  const hist2 = useMemo(
    () => histogram(freq2.map((f) => f.hz), 0.1),
    [freq2],
  );

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      const s = await createSession();
      await joinSession(s.code, "", "instructor");
      setSession(s);
      navigate(`/instructor/${s.code}`, { replace: true });
    } catch {
      setError("セッション作成に失敗しました");
    } finally {
      setBusy(false);
    }
  }

  async function run(
    kind: "experiment1" | "experiment2" | "stop" | "clear1" | "clear2",
  ) {
    if (!session) return;
    setBusy(true);
    try {
      if (kind === "stop") await stopExperiment(session.code);
      else if (kind === "clear1")
        await clearExperiment(session.code, "experiment1");
      else if (kind === "clear2")
        await clearExperiment(session.code, "experiment2");
      else await startExperiment(session.code, kind);
    } finally {
      setBusy(false);
    }
  }

  async function downloadJson() {
    if (!session) return;
    const res = await fetch(
      `/api/sessions/${session.code}/export?note=${encodeURIComponent(note)}`,
    );
    const data = (await res.json()) as ExportPayload;
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `hotaru-${session.code}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function downloadCsv() {
    if (!session) return;
    window.open(`/api/sessions/${session.code}/export.csv`, "_blank");
  }

  if (!session) {
    return (
      <section className="card-panel">
        <h1>講師画面</h1>
        <p className="muted">
          セッションを作成すると、参加用コードとQRが表示されます。
        </p>
        {error && <p className="error">{error}</p>}
        <button
          className="btn primary"
          type="button"
          disabled={busy}
          onClick={() => void handleCreate()}
        >
          {busy ? "作成中…" : "セッションを作成"}
        </button>
      </section>
    );
  }

  const connected = session.participants.filter((p) => p.connected).length;

  return (
    <section className="instructor">
      <div className="instructor-head">
        <div>
          <p className="eyebrow">セッション</p>
          <h1 className="code-display">{session.code}</h1>
          <p className="muted">
            参加 {connected}/{session.participants.length} · 状態{" "}
            {session.experiment}
          </p>
        </div>
        {qrUrl && (
          <div className="qr-box">
            <img src={qrUrl} alt={`Join ${session.code}`} width={180} height={180} />
            <Link to={`/join/${session.code}`}>/join/{session.code}</Link>
          </div>
        )}
      </div>

      <div className="control-row">
        <button
          className="btn primary"
          type="button"
          disabled={busy}
          onClick={() => void run("experiment1")}
        >
          実験1 開始（音弱）
        </button>
        <button
          className="btn primary"
          type="button"
          disabled={busy}
          onClick={() => void run("experiment2")}
        >
          実験2 開始（音量MAX）
        </button>
        <button
          className="btn"
          type="button"
          disabled={busy}
          onClick={() => void run("stop")}
        >
          停止
        </button>
      </div>

      <div className="charts">
        <FrequencyChart
          title="実験1 周波数分布（ベース）"
          bins={hist1}
          sampleCount={freq1.length}
        />
        <FrequencyChart
          title="実験2 周波数分布（同期）"
          bins={hist2}
          sampleCount={freq2.length}
        />
      </div>

      <div className="card-panel export-panel">
        <h2>データ出力</h2>
        <label>
          メモ（音量条件など）
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="教室後方の音量がやや小さい など"
          />
        </label>
        <div className="control-row">
          <button className="btn primary" type="button" onClick={() => void downloadJson()}>
            JSON ダウンロード
          </button>
          <button className="btn" type="button" onClick={downloadCsv}>
            CSV ダウンロード
          </button>
          <button className="btn" type="button" onClick={() => void run("clear1")}>
            実験1ログ削除
          </button>
          <button className="btn" type="button" onClick={() => void run("clear2")}>
            実験2ログ削除
          </button>
        </div>
        <p className="muted">
          保存した JSON は <code>python -m sim.run path/to.json</code>{" "}
          でシミュレーション入力に使えます。
        </p>
      </div>

      <div className="card-panel">
        <h2>参加者</h2>
        <ul className="participant-list">
          {session.participants.map((p) => (
            <li key={p.deskId}>
              <strong>{p.deskId}</strong>
              <span>
                ({p.x.toFixed(1)}, {p.y.toFixed(1)}) m
              </span>
              <span className={p.connected ? "ok" : "off"}>
                {p.connected ? "online" : "offline"}
              </span>
            </li>
          ))}
          {session.participants.length === 0 && (
            <li className="muted">まだ参加者はいません</li>
          )}
        </ul>
      </div>
    </section>
  );
}
