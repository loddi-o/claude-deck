export type Mode = "plan" | "auto";
export type RunStatus = "idle" | "working" | "waiting";

export interface Rate {
  status?: string;
  five_hour?: number | null;
  seven_day?: number | null;
}

export interface LastResult {
  subtype?: string;
  is_error?: boolean;
  duration_ms?: number;
  num_turns?: number;
  cost_usd?: number;
  tokens_in?: number;
  tokens_out?: number;
}

export interface StatusPayload {
  status: RunStatus;
  running: boolean;
  mode: Mode;
  effective_mode: string;
  auto_unavailable: boolean;
  session_id: string;
  model: string;
  cwd: string;
  pending: number;
  rate: Rate;
  last_result: LastResult;
}

export interface Settings {
  mode: Mode;
  model: string;
  effort: string;
  resume_on_open: boolean;
  cwd: string;
  extra_dirs: string[];
  ui_language: "auto" | "it" | "en";
  ui_language_resolved: "it" | "en";
  voice_language: string;
  voice_model: string;
  voice_silence_ms: number;
  voice_autosend: boolean;
  notifications: boolean;
  text_scale: number;
  last_session_id: string;
}

export type BackendEvent = [number, string, any];

export interface GetStateResult {
  version: string;
  status: StatusPayload;
  events: BackendEvent[];
  seq: number;
  settings: Settings;
  voice: { state: VoiceState; downloading: string };
  sudo: { has_password: boolean };
}

export type VoiceState = "idle" | "recording" | "transcribing";

export interface VoiceInfo {
  state: VoiceState;
  level: number;
  speech: boolean;
  error?: string;
}

export interface DownloadInfo {
  name: string;
  done: number;
  total: number;
  finished?: boolean;
  error?: string;
}

export interface SessionInfo {
  id: string;
  title: string;
  mtime: number;
  age_s: number;
  size: number;
}

export interface SetupInfo {
  claude: { found: boolean; path: string; version: string };
  auth: { logged_in: boolean | null; email: string; method: string };
  system: { pretty: string; family: string; device: string };
  sudo: { has_password: boolean };
  mic: { sources: { name: string; state: string }[]; default: string; has_mic: boolean };
  voice: {
    binary: boolean;
    models: { name: string; file: string; size: number; installed: boolean; downloading: boolean }[];
    selected: string;
    selected_installed: boolean;
  };
}

/* ------------------------------------------------------------------ chat items */

export type ToolStatus = "running" | "waiting" | "done" | "error" | "denied";

export type PermKind = "tool" | "plan" | "question";

export interface QuestionOption {
  label: string;
  description?: string;
}
export interface Question {
  question: string;
  header?: string;
  multiSelect?: boolean;
  options: QuestionOption[];
}

export type ChatItem =
  | { kind: "user"; id: string; text: string }
  | { kind: "assistant"; id: string; msgId: string; text: string; streaming: boolean; finalized: boolean }
  | { kind: "thinking"; id: string; msgId: string; text: string; active: boolean; finalized: boolean }
  | {
      kind: "tool";
      id: string;
      toolUseId: string;
      name: string;
      input: any;
      status: ToolStatus;
      result?: string;
    }
  | {
      kind: "perm";
      id: string;
      requestId: string;
      permKind: PermKind;
      toolName: string;
      toolUseId?: string;
      input: any;
      description?: string;
      blockedPath?: string;
      canAlways: boolean;
      resolved?: "allow" | "deny" | "cancelled";
    }
  | { kind: "notice"; id: string; code: string; level: "info" | "warn" | "error"; detail?: string; rc?: number }
  | { kind: "turn"; id: string; ok: boolean; stats: LastResult; text?: string };

export interface ChatState {
  items: ChatItem[];
  streamMid: string;
  streamIdx: Record<number, string>;
  nextId: number;
}
