import { DialogButton, Focusable, TextField } from "@decky/ui";
import { FaMicrophone, FaPaperPlane, FaStop, FaTimes } from "react-icons/fa";
import { api } from "../api";
import { t } from "../i18n";
import type { Key } from "../i18n";
import {
  dismissVoiceError,
  openFullScreen,
  sendDraft,
  setDraft,
  setTab,
  toggleDictation,
  toggleMode,
  useStore,
} from "../store";
import { Btn } from "./ui";

const VOICE_ERRORS: Record<string, Key> = {
  no_model: "voiceNoModel",
  no_binary: "voiceNoBinary",
  no_audio: "voiceNoAudio",
  no_speech: "voiceNoSpeech",
  no_recorder: "voiceNoRecorder",
  whisper_failed: "voiceFailed",
  timeout: "voiceFailed",
};

export function MicButton() {
  const { voice } = useStore();
  const rec = voice.state === "recording";
  const busy = voice.state === "transcribing";
  return (
    <DialogButton
      className={`cd-round ${rec ? "rec" : busy ? "busy" : ""}`}
      style={{ ["--lvl" as any]: voice.level }}
      onClick={() => void toggleDictation()}
      disabled={busy}
    >
      {busy ? <span className="cd-spin">◐</span> : rec ? <FaStop /> : <FaMicrophone />}
    </DialogButton>
  );
}

export function VoiceBanner() {
  const { voice, setup } = useStore();
  if (voice.state === "recording") {
    return (
      <div className="cd-voice-note" style={{ ["--lvl" as any]: voice.level }}>
        <FaMicrophone style={{ color: "var(--cd-err)" }} />
        <span>{t("dictating")}</span>
        <div className="cd-meter">
          <i />
        </div>
      </div>
    );
  }
  if (voice.state === "transcribing") {
    return (
      <div className="cd-voice-note">
        <span className="cd-spin">◐</span> {t("transcribing")}
      </div>
    );
  }
  if (voice.error) {
    const noMic = voice.error === "no_audio" && setup && !setup.mic.has_mic;
    const key = noMic ? "voiceNoMic" : VOICE_ERRORS[voice.error] ?? "voiceFailed";
    const fixable = voice.error === "no_model" || voice.error === "no_binary";
    return (
      <div className="cd-voice-note err">
        <span style={{ flex: 1 }}>{t(key)}</span>
        {fixable && (
          <Btn
            kind="ghost"
            onClick={() => {
              dismissVoiceError();
              setTab("settings");
              openFullScreen();
            }}
          >
            {t("voiceOpenSettings")}
          </Btn>
        )}
        <Btn kind="ghost" onClick={dismissVoiceError}>
          <FaTimes />
        </Btn>
      </div>
    );
  }
  return null;
}

export function Composer({ compact }: { compact?: boolean }) {
  const { draft, status, voice } = useStore();
  const working = status.status !== "idle";
  const canSend = draft.trim().length > 0;
  return (
    <Focusable
      className="cd-composer"
      flow-children="horizontal"
      onSecondaryButton={() => void toggleDictation()}
      onSecondaryActionDescription={voice.state === "recording" ? t("stopDictation") : t("hintDictate")}
      onOptionsButton={() => void toggleMode()}
      onOptionsActionDescription={t("hintMode")}
    >
      <MicButton />
      <div className="cd-field">
        <TextField
          value={draft}
          placeholder={compact ? t("placeholder").replace("…", "") + "…" : t("placeholder")}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e: any) => {
            if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey) {
              e.preventDefault();
              void sendDraft();
            }
          }}
        />
      </div>
      {working && !canSend ? (
        <DialogButton className="cd-round" onClick={() => void api.interrupt()}>
          <FaStop />
        </DialogButton>
      ) : (
        <DialogButton className="cd-round" disabled={!canSend} onClick={() => void sendDraft()}>
          <FaPaperPlane />
        </DialogButton>
      )}
    </Focusable>
  );
}
