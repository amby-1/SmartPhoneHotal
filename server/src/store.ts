import { randomBytes } from "node:crypto";
import { deskIdToCoords } from "./desk.js";
import type {
  ExperimentKind,
  ExportPayload,
  Participant,
  SessionState,
  TapEvent,
} from "./types.js";

const VOLUME_EXP1 = 0; // ベース計測は無音（物理結合なし）
const VOLUME_EXP2 = 1.0;

function makeCode(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = randomBytes(4);
  let code = "";
  for (let i = 0; i < 4; i++) {
    code += alphabet[bytes[i]! % alphabet.length];
  }
  return code;
}

export class SessionStore {
  private sessions = new Map<string, SessionState>();

  create(): SessionState {
    let code = makeCode();
    while (this.sessions.has(code)) {
      code = makeCode();
    }
    const session: SessionState = {
      code,
      createdAt: new Date().toISOString(),
      experiment: "idle",
      experimentStartedAt: null,
      volume: 0,
      participants: [],
      taps: [],
    };
    this.sessions.set(code, session);
    return session;
  }

  get(code: string): SessionState | undefined {
    return this.sessions.get(code.toUpperCase());
  }

  join(
    code: string,
    deskId: string,
    socketId: string,
  ): { session: SessionState; participant: Participant } {
    const session = this.get(code);
    if (!session) {
      throw new Error("Session not found");
    }
    const normalized = deskId.trim().toUpperCase();
    const { x, y } = deskIdToCoords(normalized);

    const existing = session.participants.find((p) => p.deskId === normalized);
    if (existing) {
      existing.id = socketId;
      existing.connected = true;
      existing.x = x;
      existing.y = y;
      return { session, participant: existing };
    }

    const participant: Participant = {
      id: socketId,
      deskId: normalized,
      x,
      y,
      connected: true,
    };
    session.participants.push(participant);
    return { session, participant };
  }

  leave(socketId: string): SessionState | undefined {
    for (const session of this.sessions.values()) {
      const p = session.participants.find((item) => item.id === socketId);
      if (p) {
        p.connected = false;
        return session;
      }
    }
    return undefined;
  }

  startExperiment(
    code: string,
    kind: "experiment1" | "experiment2",
  ): SessionState {
    const session = this.require(code);
    session.experiment = kind;
    session.experimentStartedAt = Date.now();
    session.volume = kind === "experiment1" ? VOLUME_EXP1 : VOLUME_EXP2;
    return session;
  }

  stopExperiment(code: string): SessionState {
    const session = this.require(code);
    session.experiment = "idle";
    session.experimentStartedAt = null;
    session.volume = 0;
    return session;
  }

  addTap(
    code: string,
    participantId: string,
    deskId: string,
    clientTMs: number,
  ): TapEvent {
    const session = this.require(code);
    if (
      session.experiment !== "experiment1" &&
      session.experiment !== "experiment2"
    ) {
      throw new Error("No active experiment");
    }
    const startedAt = session.experimentStartedAt ?? Date.now();
    const tMs =
      typeof clientTMs === "number" && Number.isFinite(clientTMs)
        ? Math.max(0, clientTMs)
        : Date.now() - startedAt;

    const tap: TapEvent = {
      participantId,
      deskId: deskId.toUpperCase(),
      tMs,
      experiment: session.experiment,
    };
    session.taps.push(tap);
    return tap;
  }

  clearTaps(code: string, experiment?: "experiment1" | "experiment2"): SessionState {
    const session = this.require(code);
    if (experiment) {
      session.taps = session.taps.filter((t) => t.experiment !== experiment);
    } else {
      session.taps = [];
    }
    return session;
  }

  export(code: string, note?: string): ExportPayload {
    const session = this.require(code);
    const desks = session.participants.map((p) => ({
      id: p.deskId,
      x: p.x,
      y: p.y,
    }));

    const group = (kind: "experiment1" | "experiment2") => {
      const byDesk = new Map<string, number[]>();
      for (const tap of session.taps.filter((t) => t.experiment === kind)) {
        const list = byDesk.get(tap.deskId) ?? [];
        list.push(tap.tMs);
        byDesk.set(tap.deskId, list);
      }
      return [...byDesk.entries()].map(([deskId, taps_ms]) => ({
        deskId,
        taps_ms: taps_ms.sort((a, b) => a - b),
      }));
    };

    return {
      sessionId: session.code,
      createdAt: session.createdAt,
      desks,
      experiment1: group("experiment1"),
      experiment2: group("experiment2"),
      meta: {
        volumeExperiment1: VOLUME_EXP1,
        volumeExperiment2: VOLUME_EXP2,
        note,
      },
    };
  }

  publicView(session: SessionState) {
    return {
      code: session.code,
      createdAt: session.createdAt,
      experiment: session.experiment as ExperimentKind,
      experimentStartedAt: session.experimentStartedAt,
      volume: session.volume,
      participants: session.participants,
      tapCount: session.taps.length,
      taps: session.taps,
    };
  }

  private require(code: string): SessionState {
    const session = this.get(code);
    if (!session) {
      throw new Error("Session not found");
    }
    return session;
  }
}
