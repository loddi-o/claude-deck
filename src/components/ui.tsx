import {
  ConfirmModal,
  DialogButton,
  DialogFooter,
  DialogHeader,
  Focusable,
  ModalRoot,
  TextField,
  showModal,
} from "@decky/ui";
import { ReactNode, useState } from "react";
import {
  FaBolt,
  FaBookOpen,
  FaBrain,
  FaClipboardList,
  FaExclamationTriangle,
  FaInfoCircle,
  FaFileAlt,
  FaGlobe,
  FaPen,
  FaQuestionCircle,
  FaRobot,
  FaSearch,
  FaTasks,
  FaTerminal,
  FaTools,
} from "react-icons/fa";
import { t } from "../i18n";
import { CSS } from "../styles";
import { setMode, useStore } from "../store";
import type { ToolIcon } from "../tools";

/** Generic asterisk-style spark used as the plugin mark. */
export function Spark({ size = 20 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <g stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
        {[0, 30, 60, 90, 120, 150].map((a) => (
          <line key={a} x1="12" y1="3.2" x2="12" y2="20.8" transform={`rotate(${a} 12 12)`} />
        ))}
      </g>
    </svg>
  );
}

export function ToolGlyph({ icon }: { icon: ToolIcon }) {
  switch (icon) {
    case "terminal":
      return <FaTerminal />;
    case "file":
      return <FaFileAlt />;
    case "edit":
      return <FaPen />;
    case "search":
      return <FaSearch />;
    case "web":
      return <FaGlobe />;
    case "memory":
      return <FaBrain />;
    case "todo":
      return <FaTasks />;
    case "agent":
      return <FaRobot />;
    case "plan":
      return <FaClipboardList />;
    case "question":
      return <FaQuestionCircle />;
    default:
      return <FaTools />;
  }
}

/** Injected once per root; harmless if repeated. */
export function Styles() {
  return <style>{CSS}</style>;
}

export function Root({
  compact,
  children,
  className = "",
}: {
  compact?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const { settings } = useStore();
  return (
    <div
      className={`cd-root ${compact ? "cd-compact" : ""} ${className}`}
      style={{ ["--cd-scale" as any]: settings.text_scale }}
    >
      <Styles />
      {children}
    </div>
  );
}

type BtnKind = "primary" | "danger" | "ghost" | "plain";

export function Btn({
  children,
  onClick,
  kind = "plain",
  className = "",
  disabled,
  preferredFocus,
}: {
  children: ReactNode;
  onClick?: () => void;
  kind?: BtnKind;
  className?: string;
  disabled?: boolean;
  preferredFocus?: boolean;
}) {
  return (
    <DialogButton
      className={`cd-btn ${kind === "plain" ? "" : kind} ${className}`}
      onClick={() => onClick?.()}
      disabled={disabled}
      preferredFocus={preferredFocus}
    >
      {children}
    </DialogButton>
  );
}

export function StatusDot({ status, running }: { status: string; running?: boolean }) {
  const cls = status === "working" ? "working" : status === "waiting" ? "waiting" : running ? "" : "off";
  return <span className={`cd-dot ${cls}`} />;
}

export function statusLabel(status: string): string {
  return status === "working" ? t("working") : status === "waiting" ? t("waiting") : t("ready");
}

export function ModeSwitch() {
  const { status } = useStore();
  const mode = status.mode;
  const autoLabel = status.auto_unavailable ? `${t("modeAuto")}*` : t("modeAuto");
  return (
    <Focusable className="cd-mode" flow-children="horizontal">
      <DialogButton className={`cd-seg plan ${mode === "plan" ? "cd-on" : ""}`} onClick={() => setMode("plan")}>
        <FaClipboardList /> {t("modePlan")}
      </DialogButton>
      <DialogButton className={`cd-seg auto ${mode === "auto" ? "cd-on" : ""}`} onClick={() => setMode("auto")}>
        <FaBolt /> {autoLabel}
      </DialogButton>
    </Focusable>
  );
}

export function Notice({ level, children }: { level: "info" | "warn" | "error"; children: ReactNode }) {
  return (
    <div className={`cd-notice ${level}`}>
      {level === "info" ? (
        <FaInfoCircle style={{ marginTop: 3, flex: "0 0 auto" }} />
      ) : (
        <FaExclamationTriangle style={{ marginTop: 3, flex: "0 0 auto" }} />
      )}
      <div>{children}</div>
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <div className="cd-h">{children}</div>;
}

export function HelpIcon() {
  return <FaBookOpen />;
}

/* --------------------------------------------------------------------- modals */

function TextPromptModal({
  title,
  initial,
  password,
  placeholder,
  onDone,
  closeModal,
}: {
  title: string;
  initial: string;
  password?: boolean;
  placeholder?: string;
  onDone: (v: string | null) => void;
  closeModal?: () => void;
}) {
  const [val, setVal] = useState(initial);
  const submit = () => {
    onDone(val);
    closeModal?.();
  };
  const cancel = () => {
    onDone(null);
    closeModal?.();
  };
  return (
    <ModalRoot onCancel={cancel} closeModal={closeModal}>
      <DialogHeader>{title}</DialogHeader>
      <div style={{ margin: "8px 0 16px" }}>
        <TextField
          focusOnMount
          value={val}
          placeholder={placeholder}
          bIsPassword={password}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e: any) => {
            if (e.key === "Enter") submit();
          }}
        />
      </div>
      <DialogFooter>
        <DialogButton onClick={submit}>{t("ok")}</DialogButton>
        <DialogButton onClick={cancel}>{t("cancel")}</DialogButton>
      </DialogFooter>
    </ModalRoot>
  );
}

/** Opens a modal with a text field (Steam's on-screen keyboard on the Deck). null = cancelled. */
export function promptText(
  title: string,
  opts: { initial?: string; password?: boolean; placeholder?: string } = {}
): Promise<string | null> {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (v: string | null) => {
      if (!settled) {
        settled = true;
        resolve(v);
      }
    };
    showModal(
      <TextPromptModal
        title={title}
        initial={opts.initial ?? ""}
        password={opts.password}
        placeholder={opts.placeholder}
        onDone={finish}
      />,
      undefined,
      { fnOnClose: () => finish(null) }
    );
  });
}

export function confirmDialog(title: string, description?: string): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (v: boolean) => {
      if (!settled) {
        settled = true;
        resolve(v);
      }
    };
    showModal(
      <ConfirmModal
        strTitle={title}
        strDescription={description}
        strOKButtonText={t("ok")}
        strCancelButtonText={t("cancel")}
        onOK={() => finish(true)}
        onCancel={() => finish(false)}
      />,
      undefined,
      { fnOnClose: () => finish(false) }
    );
  });
}
