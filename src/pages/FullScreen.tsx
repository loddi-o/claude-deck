import { DialogButton, Focusable, GamepadButton, Navigation } from "@decky/ui";
import { ReactElement, useEffect } from "react";
import { FaBrain, FaCog, FaCommentDots, FaHistory, FaTimes } from "react-icons/fa";
import { api } from "../api";
import { ChatList, ChatScroller, Welcome } from "../components/Chat";
import { Composer, VoiceBanner } from "../components/Composer";
import { ModeSwitch, Root, Spark, StatusDot, statusLabel } from "../components/ui";
import { Btn } from "../components/ui";
import { t } from "../i18n";
import type { Key } from "../i18n";
import {
  needsSetup,
  newSession,
  registerVisible,
  runSetupCheck,
  setTab,
  stepTab,
  TABS,
  toggleDictation,
  toggleMode,
  useStore,
} from "../store";
import type { Tab } from "../store";
import { MemoryPage } from "./Memory";
import { SessionsPage } from "./Sessions";
import { SettingsPage } from "./Settings";

const TAB_META: Record<Tab, { key: Key; icon: ReactElement }> = {
  chat: { key: "tabChat", icon: <FaCommentDots /> },
  sessions: { key: "tabSessions", icon: <FaHistory /> },
  memory: { key: "tabMemory", icon: <FaBrain /> },
  settings: { key: "tabSettings", icon: <FaCog /> },
};

function Header() {
  const { status } = useStore();
  const rate = status.rate;
  const pct = (v?: number | null) => (typeof v === "number" ? Math.round(v * 100) : null);
  const five = pct(rate.five_hour);
  const seven = pct(rate.seven_day);
  return (
    <div className="cd-header">
      <div className="cd-brand">
        <Spark size={22} /> {t("appName")}
      </div>
      <div className="cd-status">
        <StatusDot status={status.status} running={status.running} />
        <span>{statusLabel(status.status)}</span>
        {status.model && <span>· {status.model.replace(/^claude-/, "")}</span>}
        {five !== null && seven !== null && <span>· {t("rateLimit", { a: five, b: seven })}</span>}
      </div>
      <div className="cd-spacer" />
      <ModeSwitch />
      <Btn kind="ghost" className="cd-round" onClick={() => Navigation.NavigateBack()}>
        <FaTimes />
      </Btn>
    </div>
  );
}

function Tabs() {
  const { tab } = useStore();
  return (
    <Focusable className="cd-tabs" flow-children="horizontal">
      {TABS.map((id) => (
        <DialogButton key={id} className={`cd-tab ${tab === id ? "cd-on" : ""}`} onClick={() => setTab(id)}>
          {TAB_META[id].icon} {t(TAB_META[id].key)}
        </DialogButton>
      ))}
    </Focusable>
  );
}

function ChatTab() {
  const s = useStore();
  const items = s.chat.items;
  return (
    <>
      <ChatScroller items={items}>
        {needsSetup(s) && (
          <div className="cd-warnbox" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ flex: 1 }}>
              {!s.setup?.claude.found ? t("nClaudeMissing") : t("notLoggedIn")}
            </span>
            <Btn kind="ghost" onClick={() => setTab("settings")}>
              {t("tabSettings")}
            </Btn>
          </div>
        )}
        {items.length === 0 ? <Welcome /> : <ChatList items={items} />}
      </ChatScroller>
      <div className="cd-footer">
        <VoiceBanner />
        <Composer />
      </div>
    </>
  );
}

export function FullScreen() {
  const { tab } = useStore();

  useEffect(() => registerVisible(), []);
  useEffect(() => {
    void runSetupCheck();
  }, []);

  // Physical keyboard shortcuts
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      if (e.ctrlKey && k === "m") {
        e.preventDefault();
        void toggleMode();
      } else if (e.ctrlKey && k === "n") {
        e.preventDefault();
        void newSession().then(() => setTab("chat"));
      } else if (e.ctrlKey && k === "d") {
        e.preventDefault();
        void toggleDictation();
      } else if (e.ctrlKey && e.key === "Tab") {
        e.preventDefault();
        stepTab(e.shiftKey ? -1 : 1);
      } else if (e.key === "Escape") {
        void api.voiceCancel();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  return (
    <Root className="cd-screen">
      <Focusable
        style={{ display: "flex", flexDirection: "column", height: "100%" }}
        onButtonDown={(e) => {
          const b = e.detail.button;
          if (b === GamepadButton.BUMPER_LEFT) stepTab(-1);
          else if (b === GamepadButton.BUMPER_RIGHT) stepTab(1);
        }}
        onCancelActionDescription={t("hintBack")}
      >
        <Header />
        <Tabs />
        <div className="cd-body">
          {tab === "chat" && <ChatTab />}
          {tab === "sessions" && (
            <div className="cd-scroll">
              <SessionsPage />
            </div>
          )}
          {tab === "memory" && (
            <div className="cd-scroll">
              <MemoryPage />
            </div>
          )}
          {tab === "settings" && (
            <div className="cd-scroll">
              <SettingsPage />
            </div>
          )}
        </div>
      </Focusable>
    </Root>
  );
}
