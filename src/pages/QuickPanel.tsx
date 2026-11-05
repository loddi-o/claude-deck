import { ButtonItem, Focusable, PanelSection, PanelSectionRow } from "@decky/ui";
import { useEffect } from "react";
import { FaCog, FaExpand, FaPlus, FaStop } from "react-icons/fa";
import { api } from "../api";
import { Welcome } from "../components/Chat";
import { PermissionItem } from "../components/Cards";
import { Composer, VoiceBanner } from "../components/Composer";
import { Markdown } from "../components/Markdown";
import { Btn, ModeSwitch, Root, StatusDot, ToolGlyph, statusLabel } from "../components/ui";
import { t } from "../i18n";
import { pendingPerm } from "../reducer";
import {
  needsSetup,
  newSession,
  openFullScreen,
  openSettings,
  registerVisible,
  runSetupCheck,
  useStore,
} from "../store";
import { setupIssues } from "../setup";
import { summarizeTool } from "../tools";
import type { ChatItem } from "../types";

function lastOf<K extends ChatItem["kind"]>(items: ChatItem[], kind: K): Extract<ChatItem, { kind: K }> | undefined {
  for (let i = items.length - 1; i >= 0; i--) if (items[i].kind === kind) return items[i] as any;
  return undefined;
}

/** Condensed view of the conversation: last question, last answer, what Claude is doing now. */
function Latest({ items }: { items: ChatItem[] }) {
  const user = lastOf(items, "user");
  const asst = [...items].reverse().find((i) => i.kind === "assistant" && i.text) as
    | Extract<ChatItem, { kind: "assistant" }>
    | undefined;
  const tool = [...items].reverse().find((i) => i.kind === "tool" && (i.status === "running" || i.status === "waiting")) as
    | Extract<ChatItem, { kind: "tool" }>
    | undefined;
  const thinking = items.some((i) => i.kind === "thinking" && i.active);
  const s = tool ? summarizeTool(tool.name, tool.input) : null;
  return (
    <Focusable
      className="cd-card"
      focusClassName="cd-focus"
      noFocusRing
      onActivate={openFullScreen}
      onOKActionDescription={t("openFull")}
    >
      {user && (
        <div className="cd-mutedtxt cd-clamp2" style={{ marginBottom: 6 }}>
          › {user.text}
        </div>
      )}
      {asst && (
        <div className="cd-clamp">
          <Markdown text={asst.text} focusable={false} bare streaming={asst.streaming} />
        </div>
      )}
      {thinking && !asst?.streaming && (
        <div className="cd-thinking" style={{ paddingLeft: 0 }}>
          <span className="cd-spin">◐</span> {t("thinking")}
        </div>
      )}
      {s && (
        <div className="cd-tool" style={{ marginTop: 8 }}>
          <span className="cd-ico">
            <ToolGlyph icon={s.icon} />
          </span>
          <span className="cd-label">{s.label}</span>
          <span className="cd-detail">{s.detail}</span>
          <span className="cd-spin">◐</span>
        </div>
      )}
    </Focusable>
  );
}

/** Always-visible way into the Settings page; shows how many essentials are still missing. */
function SettingsEntry({ issues }: { issues: number }) {
  return (
    <Btn className="cd-settings-entry" onClick={openSettings}>
      <FaCog />
      <span className="cd-lbl">{t("tabSettings")}</span>
      {issues > 0 && <span className="cd-pill">⚠ {t("setupPending", { n: issues })}</span>}
    </Btn>
  );
}

export function QuickPanel() {
  const s = useStore();
  useEffect(() => registerVisible(), []);
  useEffect(() => {
    void runSetupCheck();
  }, []);

  if (!s.ready) {
    return (
      <Root compact>
        <PanelSection>
          <PanelSectionRow>
            <div className="cd-mutedtxt">{s.error || t("loading")}</div>
          </PanelSectionRow>
        </PanelSection>
      </Root>
    );
  }

  const items = s.chat.items;
  const perm = pendingPerm(items);
  const working = s.status.status !== "idle";

  return (
    <Root compact className="cd-q">
      <PanelSection>
        <PanelSectionRow>
          <div className="cd-status">
            <StatusDot status={s.status.status} running={s.status.running} />
            <span>{statusLabel(s.status.status)}</span>
            {s.status.model && <span>· {s.status.model.replace(/^claude-/, "")}</span>}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <SettingsEntry issues={setupIssues(s.setup)} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ModeSwitch />
        </PanelSectionRow>
      </PanelSection>

      {needsSetup(s) && (
        <PanelSection>
          <PanelSectionRow>
            <div className="cd-warnbox">{!s.setup?.claude.found ? t("nClaudeMissing") : t("notLoggedIn")}</div>
          </PanelSectionRow>
        </PanelSection>
      )}

      <PanelSection>
        <PanelSectionRow>{items.length === 0 ? <Welcome compact /> : <Latest items={items} />}</PanelSectionRow>
        {perm && (
          <PanelSectionRow>
            <PermissionItem item={perm} compact />
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <div style={{ width: "100%" }}>
            <VoiceBanner />
            <Composer compact />
          </div>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={openFullScreen}>
            <FaExpand style={{ marginRight: 8, verticalAlign: -2 }} />
            {t("openFull")}
          </ButtonItem>
        </PanelSectionRow>
        {working && (
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => void api.interrupt()}>
              <FaStop style={{ marginRight: 8, verticalAlign: -2 }} />
              {t("stop")}
            </ButtonItem>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => void newSession()}>
            <FaPlus style={{ marginRight: 8, verticalAlign: -2 }} />
            {t("newChat")}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </Root>
  );
}
