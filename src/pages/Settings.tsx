import { DropdownItem, Focusable, Navigation, SliderField, ToggleField } from "@decky/ui";
import { ReactNode, useEffect } from "react";
import { FaCheckCircle, FaDownload, FaExclamationCircle, FaKey, FaTimes } from "react-icons/fa";
import { api } from "../api";
import { Btn, SectionTitle, confirmDialog, promptText } from "../components/ui";
import { t } from "../i18n";
import {
  runSetupCheck,
  setSudoSet,
  startInstall,
  startLogin,
  updateSettings,
  useStore,
} from "../store";
import { formatBytes } from "../tools";

function Row({
  label,
  ok,
  text,
  children,
}: {
  label: string;
  ok: boolean | null;
  text: string;
  children?: ReactNode;
}) {
  return (
    <Focusable className="cd-item" flow-children="horizontal">
      <span className={ok === null ? "cd-mutedtxt" : ok ? "cd-ok" : "cd-bad"}>
        {ok === null ? "…" : ok ? <FaCheckCircle /> : <FaExclamationCircle />}
      </span>
      <div className="cd-grow">
        <div className="cd-title">{label}</div>
        <div className="cd-sub">{text}</div>
      </div>
      {children}
    </Focusable>
  );
}

function Setup() {
  const s = useStore();
  const { setup, download, installState, installLog, login } = s;
  useEffect(() => {
    void runSetupCheck();
  }, []);

  if (!setup) return <div className="cd-mutedtxt">{t("loading")}</div>;

  const model = setup.voice.models.find((m) => m.name === setup.voice.selected);
  const dlPct = download && download.total ? Math.min(100, Math.round((download.done / download.total) * 100)) : 0;

  const testSudo = async () => {
    const r = await api.sudoTest();
    const msg = r.ok ? t("sudoOk") : r.message === "wrong_password" ? t("sudoWrong") : r.message === "no_password" ? t("sudoNone") : t("sudoFail");
    await confirmDialog(msg, r.ok ? undefined : r.message);
  };
  const setSudo = async () => {
    const pw = await promptText(t("sudoPrompt"), { password: true });
    if (pw) {
      await api.sudoSetPassword(pw);
      setSudoSet(true);
      await runSetupCheck();
    }
  };
  const removeSudo = async () => {
    await api.sudoClear();
    setSudoSet(false);
    await runSetupCheck();
  };
  const enterCode = async () => {
    const code = await promptText(t("loginCodePrompt"));
    if (code && code.trim()) await api.loginCode(code.trim());
  };

  return (
    <>
      <Row
        label={t("setupClaude")}
        ok={setup.claude.found}
        text={setup.claude.found ? `${setup.claude.version} · ${setup.claude.path}` : t("notInstalled")}
      >
        {!setup.claude.found && (
          <Btn kind="primary" disabled={installState === "running"} onClick={() => void startInstall()}>
            <FaDownload /> {installState === "running" ? t("installing") : t("installClaude")}
          </Btn>
        )}
      </Row>
      {installLog.length > 0 && (
        <Focusable focusClassName="cd-focus" noFocusRing>
          <pre className="cd-log">{installLog.join("\n")}</pre>
        </Focusable>
      )}

      <Row
        label={t("setupLogin")}
        ok={setup.claude.found ? setup.auth.logged_in : null}
        text={setup.auth.logged_in ? t("loggedAs", { email: setup.auth.email || "—" }) : t("notLoggedIn")}
      >
        {setup.claude.found && !setup.auth.logged_in && (
          <Btn kind="primary" disabled={login.state === "running"} onClick={() => void startLogin()}>
            <FaKey /> {t("login")}
          </Btn>
        )}
      </Row>
      {login.state === "running" && (
        <div className="cd-card" style={{ marginBottom: 8 }}>
          <div className="cd-mutedtxt" style={{ marginBottom: 8 }}>{t("loginWaiting")}</div>
          <Focusable className="cd-row" flow-children="horizontal">
            {login.url && (
              <Btn kind="primary" onClick={() => Navigation.NavigateToExternalWeb(login.url)}>
                {t("loginOpenBrowser")}
              </Btn>
            )}
            <Btn onClick={enterCode}>{t("loginCodePrompt")}</Btn>
            <Btn kind="danger" onClick={() => void api.loginCancel()}>
              <FaTimes />
            </Btn>
          </Focusable>
        </div>
      )}

      <Row
        label={t("setupMic")}
        ok={setup.mic.has_mic}
        text={setup.mic.has_mic ? setup.mic.default || setup.mic.sources[0]?.name || t("micOk") : t("micNone")}
      />
      <Row label={t("setupVoiceEngine")} ok={setup.voice.binary} text={setup.voice.binary ? t("engineOk") : t("engineMissing")} />
      <Row
        label={t("setupVoiceModel")}
        ok={setup.voice.selected_installed}
        text={
          download
            ? t("downloading", { pct: dlPct })
            : setup.voice.selected_installed
            ? `${setup.voice.selected} · ${t("modelInstalled")}`
            : `${setup.voice.selected} · ${model ? formatBytes(model.size) : ""}`
        }
      >
        {!setup.voice.selected_installed && !download && model && (
          <Btn kind="primary" onClick={() => void api.voiceDownload(model.name)}>
            <FaDownload /> {t("download")}
          </Btn>
        )}
        {download && (
          <Btn kind="danger" onClick={() => void api.voiceDownloadCancel()}>
            {t("cancelDownload")}
          </Btn>
        )}
      </Row>
      {download && (
        <div className="cd-progress">
          <i style={{ width: `${dlPct}%` }} />
        </div>
      )}
      {download?.error && <div className="cd-warnbox">{download.error}</div>}

      <Row label={t("setupSudo")} ok={setup.sudo.has_password} text={setup.sudo.has_password ? t("sudoSet") : t("sudoNotSet")}>
        <Btn kind={setup.sudo.has_password ? "plain" : "primary"} onClick={setSudo}>
          <FaKey /> {t("sudoSetBtn")}
        </Btn>
        {setup.sudo.has_password && <Btn onClick={testSudo}>{t("sudoTest")}</Btn>}
        {setup.sudo.has_password && (
          <Btn kind="danger" onClick={removeSudo}>
            {t("sudoRemove")}
          </Btn>
        )}
      </Row>
      <div className="cd-warnbox">{t("sudoWarn")}</div>
    </>
  );
}

const MODELS = [
  { data: "", label: "" },
  { data: "sonnet", label: "Sonnet" },
  { data: "opus", label: "Opus" },
  { data: "haiku", label: "Haiku" },
  { data: "fable", label: "Fable" },
];
const EFFORTS = ["", "low", "medium", "high", "xhigh", "max"];
const LANGS = ["auto", "it", "en", "de", "fr", "es", "pt"];

export function SettingsPage() {
  const { settings, version } = useStore();

  return (
    <div className="cd-page">
      <SectionTitle>{t("setupTitle")}</SectionTitle>
      <Setup />

      <SectionTitle>{t("behavior")}</SectionTitle>
      <ToggleField
        label={t("resumeOnOpen")}
        checked={settings.resume_on_open}
        onChange={(v) => void updateSettings({ resume_on_open: v })}
      />
      <DropdownItem
        label={t("model")}
        rgOptions={MODELS.map((m) => ({ data: m.data, label: m.label || t("modelDefault") }))}
        selectedOption={settings.model}
        onChange={(o) => void updateSettings({ model: o.data })}
      />
      <DropdownItem
        label={t("effort")}
        rgOptions={EFFORTS.map((e) => ({ data: e, label: e || t("effortDefault") }))}
        selectedOption={settings.effort}
        onChange={(o) => void updateSettings({ effort: o.data })}
      />
      <Focusable className="cd-item" flow-children="horizontal">
        <div className="cd-grow">
          <div className="cd-title">{t("workdir")}</div>
          <div className="cd-sub">{settings.cwd || "~"}</div>
        </div>
        <Btn
          onClick={async () => {
            const v = await promptText(t("workdirPrompt"), { initial: settings.cwd });
            if (v !== null) void updateSettings({ cwd: v.trim() });
          }}
        >
          {t("edit")}…
        </Btn>
      </Focusable>

      <SectionTitle>{t("voice")}</SectionTitle>
      <DropdownItem
        label={t("voiceLanguage")}
        rgOptions={LANGS.map((l) => ({ data: l, label: l === "auto" ? t("langAuto") : l.toUpperCase() }))}
        selectedOption={settings.voice_language}
        onChange={(o) => void updateSettings({ voice_language: o.data })}
      />
      <DropdownItem
        label={t("voiceModel")}
        rgOptions={[
          { data: "base-q5_1", label: "Base (60 MB)" },
          { data: "small-q5_1", label: "Small (190 MB)" },
          { data: "small", label: "Small HQ (490 MB)" },
        ]}
        selectedOption={settings.voice_model}
        onChange={(o) => {
          void updateSettings({ voice_model: o.data }).then(() => runSetupCheck());
        }}
      />
      <SliderField
        label={t("voiceSilence")}
        value={settings.voice_silence_ms}
        min={800}
        max={3000}
        step={200}
        showValue
        valueSuffix=" ms"
        onChange={(v) => void updateSettings({ voice_silence_ms: v })}
      />
      <ToggleField
        label={t("voiceAutosend")}
        checked={settings.voice_autosend}
        onChange={(v) => void updateSettings({ voice_autosend: v })}
      />

      <SectionTitle>{t("interfaceTitle")}</SectionTitle>
      <DropdownItem
        label={t("uiLanguage")}
        rgOptions={[
          { data: "auto", label: t("langAuto") },
          { data: "it", label: "Italiano" },
          { data: "en", label: "English" },
        ]}
        selectedOption={settings.ui_language}
        onChange={(o) => void updateSettings({ ui_language: o.data })}
      />
      <SliderField
        label={t("textScale")}
        value={Math.round(settings.text_scale * 100)}
        min={80}
        max={140}
        step={10}
        showValue
        valueSuffix="%"
        onChange={(v) => void updateSettings({ text_scale: v / 100 })}
      />
      <ToggleField
        label={t("notifications")}
        checked={settings.notifications}
        onChange={(v) => void updateSettings({ notifications: v })}
      />

      <SectionTitle>{t("about")}</SectionTitle>
      <div className="cd-mutedtxt" style={{ marginBottom: 24 }}>
        {t("version", { v: version })}
        <br />
        {t("aboutBody")}
      </div>
    </div>
  );
}
