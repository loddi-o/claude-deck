import { callable } from "@decky/api";
import type { GetStateResult, SessionInfo, SetupInfo, Settings } from "./types";

export const api = {
  getState: callable<[], GetStateResult>("get_state"),
  getSettings: callable<[], Settings>("get_settings"),
  setSettings: callable<[Partial<Settings>], Settings>("set_settings"),

  sendMessage: callable<[string], boolean>("send_message"),
  interrupt: callable<[], boolean>("interrupt"),
  setMode: callable<[string], boolean>("set_mode"),
  respondPermission: callable<[string, Record<string, unknown>], boolean>("respond_permission"),
  newSession: callable<[], boolean>("new_session"),
  restartSession: callable<[], boolean>("restart_session"),
  resumeSession: callable<[string], boolean>("resume_session"),
  listSessions: callable<[], SessionInfo[]>("list_sessions"),
  deleteSession: callable<[string], boolean>("delete_session"),

  memoryGet: callable<[], string>("memory_get"),
  memorySet: callable<[string], boolean>("memory_set"),
  memoryAdd: callable<[string], boolean>("memory_add"),
  memoryClear: callable<[], boolean>("memory_clear"),

  sudoSetPassword: callable<[string], boolean>("sudo_set_password"),
  sudoClear: callable<[], boolean>("sudo_clear"),
  sudoTest: callable<[], { ok: boolean; message: string }>("sudo_test"),

  voiceStart: callable<[], boolean>("voice_start"),
  voiceStop: callable<[], boolean>("voice_stop"),
  voiceCancel: callable<[], boolean>("voice_cancel"),
  voiceDownload: callable<[string], boolean>("voice_download"),
  voiceDownloadCancel: callable<[], boolean>("voice_download_cancel"),

  setupCheck: callable<[], SetupInfo>("setup_check"),
  installClaude: callable<[], boolean>("install_claude"),
  loginStart: callable<[], boolean>("login_start"),
  loginCode: callable<[string], boolean>("login_code"),
  loginCancel: callable<[], boolean>("login_cancel"),

  log: callable<[string, string], void>("log_frontend"),
};
