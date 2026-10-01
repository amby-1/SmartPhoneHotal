import { io, Socket } from "socket.io-client";
import type { SessionView, TapEvent } from "../types";

const URL =
  import.meta.env.VITE_SOCKET_URL ??
  (import.meta.env.DEV ? "http://localhost:3001" : undefined);

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    socket = io(URL, {
      autoConnect: true,
      transports: ["websocket", "polling"],
    });
  }
  return socket;
}

export async function createSession(): Promise<SessionView> {
  const res = await fetch("/api/sessions", { method: "POST" });
  if (!res.ok) throw new Error("Failed to create session");
  return res.json();
}

export async function fetchSession(code: string): Promise<SessionView> {
  const res = await fetch(`/api/sessions/${code}`);
  if (!res.ok) throw new Error("Session not found");
  return res.json();
}

export function joinSession(
  code: string,
  deskId: string,
  role: "participant" | "instructor" = "participant",
): Promise<{
  ok: boolean;
  error?: string;
  session?: SessionView;
  participant?: { id: string; deskId: string; x: number; y: number };
}> {
  const s = getSocket();
  return new Promise((resolve) => {
    s.emit("session:join", { code, deskId, role }, resolve);
  });
}

export function startExperiment(
  code: string,
  kind: "experiment1" | "experiment2",
): Promise<{ ok: boolean; error?: string; session?: SessionView }> {
  return new Promise((resolve) => {
    getSocket().emit("experiment:start", { code, kind }, resolve);
  });
}

export function stopExperiment(
  code: string,
): Promise<{ ok: boolean; error?: string; session?: SessionView }> {
  return new Promise((resolve) => {
    getSocket().emit("experiment:stop", { code }, resolve);
  });
}

export function clearExperiment(
  code: string,
  experiment?: "experiment1" | "experiment2",
): Promise<{ ok: boolean; error?: string; session?: SessionView }> {
  return new Promise((resolve) => {
    getSocket().emit("experiment:clear", { code, experiment }, resolve);
  });
}

export function sendTap(
  code: string,
  tMs: number,
): Promise<{ ok: boolean; error?: string; tap?: TapEvent }> {
  return new Promise((resolve) => {
    getSocket().emit("tap", { code, tMs }, resolve);
  });
}

export function onSessionUpdate(handler: (session: SessionView) => void): () => void {
  const s = getSocket();
  s.on("session:update", handler);
  return () => {
    s.off("session:update", handler);
  };
}
