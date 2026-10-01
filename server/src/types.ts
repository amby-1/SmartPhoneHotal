export type ExperimentKind = "idle" | "experiment1" | "experiment2";

export interface DeskPosition {
  id: string;
  x: number;
  y: number;
}

export interface Participant {
  id: string;
  deskId: string;
  x: number;
  y: number;
  connected: boolean;
}

export interface TapEvent {
  participantId: string;
  deskId: string;
  tMs: number;
  experiment: "experiment1" | "experiment2";
}

export interface SessionState {
  code: string;
  createdAt: string;
  experiment: ExperimentKind;
  experimentStartedAt: number | null;
  volume: number;
  participants: Participant[];
  taps: TapEvent[];
}

export interface ExportPayload {
  sessionId: string;
  createdAt: string;
  desks: DeskPosition[];
  experiment1: { deskId: string; taps_ms: number[] }[];
  experiment2: { deskId: string; taps_ms: number[] }[];
  meta: {
    volumeExperiment1: number;
    volumeExperiment2: number;
    note?: string;
  };
}
