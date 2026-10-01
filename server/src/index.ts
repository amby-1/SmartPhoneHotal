import cors from "cors";
import express from "express";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Server } from "socket.io";
import { isValidDeskId } from "./desk.js";
import { SessionStore } from "./store.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT ?? 3001);
const store = new SessionStore();

const app = express();
app.set("trust proxy", 1);
app.use(cors());
app.use(express.json({ limit: "2mb" }));

app.get("/api/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/api/sessions", (_req, res) => {
  const session = store.create();
  res.json(store.publicView(session));
});

app.get("/api/sessions/:code", (req, res) => {
  const session = store.get(req.params.code);
  if (!session) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  res.json(store.publicView(session));
});

app.get("/api/sessions/:code/export", (req, res) => {
  try {
    const note = typeof req.query.note === "string" ? req.query.note : undefined;
    const payload = store.export(req.params.code, note);
    res.json(payload);
  } catch {
    res.status(404).json({ error: "Session not found" });
  }
});

app.get("/api/sessions/:code/export.csv", (req, res) => {
  try {
    const payload = store.export(req.params.code);
    const lines = ["experiment,deskId,t_ms,x,y"];
    const deskMap = new Map(payload.desks.map((d) => [d.id, d]));
    for (const exp of ["experiment1", "experiment2"] as const) {
      for (const row of payload[exp]) {
        const desk = deskMap.get(row.deskId);
        for (const t of row.taps_ms) {
          lines.push(
            `${exp},${row.deskId},${t},${desk?.x ?? ""},${desk?.y ?? ""}`,
          );
        }
      }
    }
    res.setHeader("Content-Type", "text/csv; charset=utf-8");
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="hotaru-${payload.sessionId}.csv"`,
    );
    res.send(lines.join("\n"));
  } catch {
    res.status(404).json({ error: "Session not found" });
  }
});

const webDist = path.resolve(__dirname, "../../web/dist");
app.use(express.static(webDist));
app.get("*", (req, res, next) => {
  if (req.path.startsWith("/api") || req.path.startsWith("/socket.io")) {
    next();
    return;
  }
  res.sendFile(path.join(webDist, "index.html"), (err) => {
    if (err) next();
  });
});

const httpServer = createServer(app);
const io = new Server(httpServer, {
  cors: { origin: "*" },
});

function emitSession(code: string) {
  const session = store.get(code);
  if (!session) return;
  io.to(code).emit("session:update", store.publicView(session));
}

io.on("connection", (socket) => {
  socket.on(
    "session:join",
    (
      payload: { code: string; deskId: string; role?: "participant" | "instructor" },
      ack?: (result: unknown) => void,
    ) => {
      try {
        const code = payload.code?.toUpperCase();
        if (!code || !store.get(code)) {
          ack?.({ ok: false, error: "Session not found" });
          return;
        }

        socket.join(code);
        socket.data.code = code;
        socket.data.role = payload.role ?? "participant";

        if (payload.role === "instructor") {
          ack?.({ ok: true, session: store.publicView(store.get(code)!) });
          emitSession(code);
          return;
        }

        if (!payload.deskId || !isValidDeskId(payload.deskId)) {
          ack?.({ ok: false, error: "Invalid desk id (e.g. A2 or A2-1)" });
          return;
        }

        const { session, participant } = store.join(
          code,
          payload.deskId,
          socket.id,
        );
        socket.data.deskId = participant.deskId;
        ack?.({
          ok: true,
          participant,
          session: store.publicView(session),
        });
        emitSession(code);
      } catch (err) {
        ack?.({
          ok: false,
          error: err instanceof Error ? err.message : "Join failed",
        });
      }
    },
  );

  socket.on(
    "experiment:start",
    (
      payload: { code: string; kind: "experiment1" | "experiment2" },
      ack?: (result: unknown) => void,
    ) => {
      try {
        const session = store.startExperiment(payload.code, payload.kind);
        emitSession(session.code);
        ack?.({ ok: true, session: store.publicView(session) });
      } catch (err) {
        ack?.({
          ok: false,
          error: err instanceof Error ? err.message : "Start failed",
        });
      }
    },
  );

  socket.on(
    "experiment:stop",
    (payload: { code: string }, ack?: (result: unknown) => void) => {
      try {
        const session = store.stopExperiment(payload.code);
        emitSession(session.code);
        ack?.({ ok: true, session: store.publicView(session) });
      } catch (err) {
        ack?.({
          ok: false,
          error: err instanceof Error ? err.message : "Stop failed",
        });
      }
    },
  );

  socket.on(
    "experiment:clear",
    (
      payload: { code: string; experiment?: "experiment1" | "experiment2" },
      ack?: (result: unknown) => void,
    ) => {
      try {
        const session = store.clearTaps(payload.code, payload.experiment);
        emitSession(session.code);
        ack?.({ ok: true, session: store.publicView(session) });
      } catch (err) {
        ack?.({
          ok: false,
          error: err instanceof Error ? err.message : "Clear failed",
        });
      }
    },
  );

  socket.on(
    "tap",
    (
      payload: { code: string; tMs?: number },
      ack?: (result: unknown) => void,
    ) => {
      try {
        const code = payload.code?.toUpperCase() ?? socket.data.code;
        const deskId = socket.data.deskId as string | undefined;
        if (!code || !deskId) {
          ack?.({ ok: false, error: "Not joined" });
          return;
        }
        const tap = store.addTap(code, socket.id, deskId, payload.tMs ?? NaN);
        io.to(code).emit("tap:new", tap);
        // Lightweight sync: send full state occasionally is fine for class size
        emitSession(code);
        ack?.({ ok: true, tap });
      } catch (err) {
        ack?.({
          ok: false,
          error: err instanceof Error ? err.message : "Tap failed",
        });
      }
    },
  );

  socket.on("disconnect", () => {
    const session = store.leave(socket.id);
    if (session) {
      emitSession(session.code);
    }
  });
});

httpServer.listen(PORT, "0.0.0.0", () => {
  console.log(`Hotaru server listening on port ${PORT}`);
});
