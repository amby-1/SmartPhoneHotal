import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { joinSession } from "../lib/api";
import { unlockAudio } from "../lib/audio";

export default function JoinPage() {
  const { code: codeParam } = useParams();
  const navigate = useNavigate();
  const [code, setCode] = useState(codeParam?.toUpperCase() ?? "");
  const [deskId, setDeskId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await unlockAudio();
      const result = await joinSession(code.trim().toUpperCase(), deskId.trim());
      if (!result.ok || !result.session || !result.participant) {
        setError(result.error ?? "参加に失敗しました");
        return;
      }
      sessionStorage.setItem(
        "hotaru",
        JSON.stringify({
          code: result.session.code,
          deskId: result.participant.deskId,
        }),
      );
      navigate("/play");
    } catch {
      setError("サーバに接続できません");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card-panel">
      <h1>実験に参加</h1>
      <p className="muted">席番号は「A2」または同じ机の2人目なら「A2-2」</p>
      <form className="form" onSubmit={onSubmit}>
        <label>
          セッションコード
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="ABCD"
            autoCapitalize="characters"
            required
            maxLength={8}
          />
        </label>
        <label>
          席番号
          <input
            value={deskId}
            onChange={(e) => setDeskId(e.target.value.toUpperCase())}
            placeholder="A2"
            autoCapitalize="characters"
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? "接続中…" : "参加する"}
        </button>
      </form>
    </section>
  );
}
