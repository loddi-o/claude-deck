/** Module-level store: lives as long as the Steam UI, so chat state survives closing the QAM. */
import { addEventListener, removeEventListener, toaster } from "@decky/api";
import { Navigation } from "@decky/ui";
import { useSyncExternalStore } from "react";
import { api } from "./api";
import { currentLanguage, setLanguage, t } from "./i18n";
import { emptyChat, pendingPerm, reduceChat } from "./reducer";
import { summarizeTool } from "./tools";
import type {
  ChatState,
  DownloadInfo,
  Mode,
  Settings,
  SetupInfo,
  StatusPayload,
  VoiceInfo,
} from "./types";

export const ROUTE = "/claude-deck";

export type Tab = "chat" | "sessions" | "memory" | "settings";
export const TABS: Tab[] = ["chat", "sessions", "memory", "settings"];

export interface AppState {
  tab: Tab;
  ready: boolean;
  error: string;
  version: string;
  chat: ChatState;
  status: StatusPayload;
  settings: Settings;
  draft: string;
  voice: VoiceInfo;
  download: DownloadInfo | null;
  sudoSet: boolean;
  setup: SetupInfo | null;
  installLog: string[];
  installState: "idle" | "running" | "ok" | "failed";
  login: { url: string; lines: string[]; state: "idle" | "running" | "ok" | "failed" };
  sysNote: string;
}

const defaultSettings: Settings = {
  mode: "plan",
  model: "",
  effort: "",
  resume_on_open: true,
  cwd: "",
  extra_dirs: [],
  ui_language: "auto",
  ui_language_resolved: "en",
  voice_language: "auto",
  voice_model: "small-q5_1",
  voice_silence_ms: 1400,
  voice_autosend: false,
  notifications: true,
  text_scale: 1,
  last_session_id: "",
};

const defaultStatus: StatusPayload = {
  status: "idle",
  running: false,
  mode: "plan",
  effective_mode: "",
  auto_unavailable: false,
  session_id: "",
  model: "",
  cwd: "",
  pending: 0,
  rate: {},
  last_result: {},
};

let state: AppState = {
  tab: "chat",
  ready: false,
  error: "",
  version: "",
  chat: emptyChat(),
  status: defaultStatus,
  settings: defaultSettings,
  draft: "",
  voice: { state: "idle", level: 0, speech: false },
  download: null,
  sudoSet: false,
  setup: null,
  installLog: [],
  installState: "idle",
  login: { url: "", lines: [], state: "idle" },
  sysNote: "",
};

const listeners = new Set<() => void>();
let handle: ((...args: any[]) => any) | null = null;
let buffered: [number, string, any][] | null = null;
let lastSeq = 0;
let uiVisible = 0;
let sysTimer: ReturnType<typeof setTimeout> | undefined;

function set(patch: Partial<AppState>): void {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

export const getState = (): AppState => state;
export function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}
export function useStore(): AppState {
  return useSyncExternalStore(subscribe, getState, getState);
}

/** Components that show the chat register here so we only toast when nobody is looking. */
export function registerVisible(): () => void {
  uiVisible++;
  return () => {
    uiVisible = Math.max(0, uiVisible - 1);
  };
}

export function openFullScreen(): void {
  Navigation.CloseSideMenus();
  Navigation.Navigate(ROUTE);
}

/** Opens the full-screen page directly on the Settings tab. */
export function openSettings(): void {
  set({ tab: "settings" });
  openFullScreen();
}

/* ------------------------------------------------------------------- events */

const CHAT_KINDS = new Set(["msg", "history", "stream", "perm", "perm_done", "notice", "reset"]);

function toast(title: string, body: string): void {
  if (!state.settings.notifications || uiVisible > 0) return;
  try {
    toaster.toast({ title, body, duration: 7000, onClick: openFullScreen });
  } catch {
    /* toasts are best effort */
  }
}

function handleEvent(seq: number, kind: string, p: any): void {
  if (seq <= lastSeq) return;
  lastSeq = seq;

  if (CHAT_KINDS.has(kind)) {
    const chat = reduceChat(state.chat, kind, p);
    if (chat !== state.chat) set({ chat });
    if (kind === "perm") {
      const s = summarizeTool(p.tool_name, p.input);
      toast(t("toastPermTitle"), `${s.label}${s.detail ? ": " + s.detail : ""}`);
    }
    if (kind === "msg" && p.type === "result" && !p.is_error) toast(t("toastDoneTitle"), "");
    return;
  }

  switch (kind) {
    case "status":
      set({ status: p });
      break;
    case "voice": {
      const voice: VoiceInfo = {
        state: p.state ?? "idle",
        level: p.level ?? 0,
        speech: !!p.speech,
        error: p.error,
      };
      if (p.text) {
        const draft = state.draft ? `${state.draft} ${p.text}` : p.text;
        set({ voice, draft });
        if (state.settings.voice_autosend) void sendDraft();
      } else {
        set({ voice });
      }
      break;
    }
    case "voice_download":
      set({ download: p.finished && !p.error ? null : p });
      if (p.finished) void runSetupCheck();
      break;
    case "setup_log":
      if (p.line) set({ installLog: [...state.installLog, p.line].slice(-40) });
      if (p.done) {
        set({ installState: p.ok ? "ok" : "failed" });
        void runSetupCheck();
      }
      break;
    case "login": {
      const login: AppState["login"] = { ...state.login, state: "running" };
      if (p.url) login.url = p.url;
      if (p.line) login.lines = [...login.lines, p.line].slice(-6);
      if (p.done) login.state = p.ok ? "ok" : "failed";
      set({ login });
      if (p.done) void runSetupCheck();
      break;
    }
    case "sys":
      set({ sysNote: p.status || "" });
      clearTimeout(sysTimer);
      sysTimer = setTimeout(() => set({ sysNote: "" }), 4000);
      break;
  }
}

/* ------------------------------------------------------------------ lifecycle */

export async function initStore(): Promise<void> {
  if (handle) return;
  buffered = [];
  handle = addEventListener<[number, string, any]>("cd", (seq, kind, payload) => {
    if (buffered) buffered.push([seq, kind, payload]);
    else handleEvent(seq, kind, payload);
  });
  try {
    // The frontend can load before the Python backend has finished starting: retry for a while.
    let snap: Awaited<ReturnType<typeof api.getState>> | null = null;
    for (let attempt = 0; attempt < 20 && !snap; attempt++) {
      try {
        snap = await api.getState();
      } catch (e) {
        if (attempt === 19) throw e;
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    if (!snap) throw new Error("backend not available");
    setLanguage(snap.settings.ui_language);
    if (snap.settings.ui_language_resolved !== currentLanguage()) {
      // the agent replies in this language when the user's text doesn't say otherwise
      snap.settings = { ...snap.settings, ui_language_resolved: currentLanguage() };
      void api.setSettings({ ui_language_resolved: currentLanguage() });
    }
    let chat = emptyChat();
    for (const [, kind, payload] of snap.events) chat = reduceChat(chat, kind, payload);
    lastSeq = snap.seq;
    set({
      ready: true,
      error: "",
      version: snap.version,
      chat,
      status: snap.status,
      settings: snap.settings,
      voice: { state: snap.voice.state, level: 0, speech: false },
      sudoSet: snap.sudo.has_password,
    });
  } catch (e) {
    set({ error: String(e) });
  }
  const pending = buffered ?? [];
  buffered = null;
  for (const [seq, kind, payload] of pending) handleEvent(seq, kind, payload);
}

export function disposeStore(): void {
  if (handle) removeEventListener("cd", handle);
  handle = null;
  buffered = null;
  clearTimeout(sysTimer);
}

/* -------------------------------------------------------------------- actions */

export function setDraft(draft: string): void {
  set({ draft });
}

export async function sendText(text: string): Promise<void> {
  const msg = text.trim();
  if (!msg) return;
  set({ draft: "" });
  await api.sendMessage(msg);
}

export async function sendDraft(): Promise<void> {
  await sendText(state.draft);
}

export async function toggleDictation(): Promise<void> {
  const v = state.voice.state;
  if (v === "idle") {
    set({ voice: { state: "recording", level: 0, speech: false } });
    await api.voiceStart();
  } else if (v === "recording") {
    await api.voiceStop();
  }
}

export async function setMode(mode: Mode): Promise<void> {
  set({ settings: { ...state.settings, mode }, status: { ...state.status, mode } });
  await api.setMode(mode);
}

export async function toggleMode(): Promise<void> {
  await setMode(state.status.mode === "plan" ? "auto" : "plan");
}

export async function updateSettings(patch: Partial<Settings>): Promise<void> {
  set({ settings: { ...state.settings, ...patch } });
  if (patch.ui_language) {
    setLanguage(patch.ui_language);
    patch = { ...patch, ui_language_resolved: currentLanguage() };
  }
  const saved = await api.setSettings(patch);
  set({ settings: saved });
}

export async function respond(requestId: string, decision: Record<string, unknown>): Promise<void> {
  await api.respondPermission(requestId, decision);
}

export async function newSession(): Promise<void> {
  await api.newSession();
}

export async function runSetupCheck(): Promise<SetupInfo | null> {
  try {
    const setup = await api.setupCheck();
    set({ setup, sudoSet: setup.sudo.has_password });
    return setup;
  } catch (e) {
    api.log("warning", "setup check failed: " + String(e));
    return null;
  }
}

export async function startInstall(): Promise<void> {
  set({ installLog: [], installState: "running" });
  if (!(await api.installClaude())) set({ installState: "failed" });
}

export async function startLogin(): Promise<void> {
  set({ login: { url: "", lines: [], state: "running" } });
  if (!(await api.loginStart())) set({ login: { url: "", lines: [], state: "failed" } });
}

export function setTab(tab: Tab): void {
  set({ tab });
}

export function stepTab(delta: number): void {
  const i = TABS.indexOf(state.tab);
  set({ tab: TABS[(i + delta + TABS.length) % TABS.length] });
}

export function dismissVoiceError(): void {
  set({ voice: { ...state.voice, error: undefined } });
}

export function setSudoSet(v: boolean): void {
  set({ sudoSet: v });
}

/** True when something essential is missing and the user should see the setup page first. */
export function needsSetup(s: AppState): boolean {
  return !!s.setup && (!s.setup.claude.found || s.setup.auth.logged_in === false);
}

export { pendingPerm };
