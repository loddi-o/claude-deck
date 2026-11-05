import { Focusable } from "@decky/ui";
import { ReactElement, useState } from "react";
import { FaCheck, FaClipboardList, FaExclamationTriangle, FaQuestionCircle, FaTimes } from "react-icons/fa";
import { t } from "../i18n";
import type { Key } from "../i18n";
import { openFullScreen, respond } from "../store";
import { permissionBody, permissionTitleKey, summarizeTool } from "../tools";
import type { ChatItem, Question } from "../types";
import { Markdown } from "./Markdown";
import { Btn, Notice, ToolGlyph, promptText } from "./ui";

type PermItem = Extract<ChatItem, { kind: "perm" }>;
type ToolItem = Extract<ChatItem, { kind: "tool" }>;

/* ------------------------------------------------------------------ tool rows */

const STATUS_BADGE: Record<ToolItem["status"], { key: Key; cls: string }> = {
  running: { key: "toolRunning", cls: "" },
  waiting: { key: "waiting", cls: "warn" },
  done: { key: "toolDone", cls: "ok" },
  error: { key: "toolFailed", cls: "err" },
  denied: { key: "toolDenied", cls: "err" },
};

function toolDetailText(item: ToolItem): string {
  const i = item.input ?? {};
  if (item.name === "TodoWrite") {
    return (i.todos ?? [])
      .map((x: any) => `${x.status === "completed" ? "[x]" : x.status === "in_progress" ? "[~]" : "[ ]"} ${x.content}`)
      .join("\n");
  }
  const head =
    item.name === "Bash"
      ? `$ ${i.command ?? ""}`
      : item.name === "Edit" || item.name === "Write"
      ? permissionBody(item.name, i)
      : (() => {
          try {
            return JSON.stringify(i, null, 2);
          } catch {
            return "";
          }
        })();
  return item.result ? `${head}\n\n${item.result}` : head;
}

export function ToolCard({ item }: { item: ToolItem }) {
  const [open, setOpen] = useState(item.name === "TodoWrite");
  if (item.name === "ExitPlanMode" || item.name === "AskUserQuestion") return null;
  const s = summarizeTool(item.name, item.input);
  const badge = STATUS_BADGE[item.status];
  return (
    <div>
      <Focusable
        className="cd-tool"
        focusClassName="cd-focus"
        noFocusRing
        onActivate={() => setOpen((o) => !o)}
        onOKActionDescription={open ? t("hideOutput") : t("showOutput")}
      >
        <span className="cd-ico">
          <ToolGlyph icon={s.icon} />
        </span>
        <span className="cd-label">{s.label}</span>
        <span className="cd-detail">{s.detail}</span>
        <span className={`cd-badge ${badge.cls}`}>
          {item.status === "running" ? <span className="cd-spin">◐</span> : t(badge.key)}
        </span>
      </Focusable>
      {open && (
        <Focusable className="cd-output" focusClassName="cd-focus" noFocusRing>
          <pre className="cd-code">{toolDetailText(item) || "—"}</pre>
        </Focusable>
      )}
    </div>
  );
}

/* ----------------------------------------------------------- resolved one-liner */

function Resolved({ icon, text, ok }: { icon: ReactElement; text: string; ok: boolean }) {
  return (
    <Focusable className="cd-notice" focusClassName="cd-focus" noFocusRing>
      <span className={ok ? "cd-ok" : "cd-bad"} style={{ marginTop: 3 }}>
        {icon}
      </span>
      <div>{text}</div>
    </Focusable>
  );
}

/* ------------------------------------------------------------ tool permission */

function ToolPerm({ item }: { item: PermItem }) {
  const [busy, setBusy] = useState(false);
  const s = summarizeTool(item.toolName, item.input);
  if (item.resolved) {
    const ok = item.resolved === "allow";
    const label = item.resolved === "allow" ? t("allowed") : item.resolved === "deny" ? t("denied") : t("cancelled");
    return (
      <Resolved
        ok={ok}
        icon={ok ? <FaCheck /> : <FaTimes />}
        text={`${label}: ${s.label}${s.detail ? " · " + s.detail : ""}`}
      />
    );
  }
  const decide = async (d: Record<string, unknown>) => {
    if (busy) return;
    setBusy(true);
    await respond(item.requestId, d);
  };
  const denyWithReason = async () => {
    const reason = await promptText(t("denyPrompt"));
    if (reason !== null) await decide({ behavior: "deny", message: reason || undefined });
  };
  const body = permissionBody(item.toolName, item.input);
  return (
    <div className="cd-card attn">
      <div className="cd-card-title">
        <ToolGlyph icon={s.icon} /> {t(permissionTitleKey(item.toolName))}
      </div>
      {item.description && item.toolName === "Bash" && <div className="cd-mutedtxt" style={{ marginBottom: 6 }}>{item.description}</div>}
      <Focusable focusClassName="cd-focus" noFocusRing>
        <pre className="cd-code">{body}</pre>
      </Focusable>
      {item.blockedPath && <div className="cd-warnbox">{item.blockedPath}</div>}
      <Focusable
        className="cd-row"
        flow-children="horizontal"
        onSecondaryButton={() => item.canAlways && decide({ behavior: "allow", always: true })}
        onSecondaryActionDescription={item.canAlways ? t("hintAlways") : undefined}
        onOptionsButton={denyWithReason}
        onOptionsActionDescription={t("hintDenyReason")}
      >
        <Btn kind="primary" preferredFocus disabled={busy} onClick={() => decide({ behavior: "allow" })}>
          <FaCheck /> {t("allow")}
        </Btn>
        {item.canAlways && (
          <Btn disabled={busy} onClick={() => decide({ behavior: "allow", always: true })}>
            {t("allowAlways")}
          </Btn>
        )}
        <Btn kind="danger" disabled={busy} onClick={() => decide({ behavior: "deny" })}>
          <FaTimes /> {t("deny")}
        </Btn>
        <Btn disabled={busy} onClick={denyWithReason}>
          {t("denyReason")}
        </Btn>
      </Focusable>
    </div>
  );
}

/* ----------------------------------------------------------------------- plan */

function PlanCard({ item, compact }: { item: PermItem; compact?: boolean }) {
  const [busy, setBusy] = useState(false);
  const plan = String(item.input?.plan ?? "");
  if (item.resolved) {
    const ok = item.resolved === "allow";
    return (
      <Resolved ok={ok} icon={<FaClipboardList />} text={ok ? t("planApproved") : t("planRejected")} />
    );
  }
  const decide = async (d: Record<string, unknown>) => {
    if (busy) return;
    setBusy(true);
    await respond(item.requestId, d);
  };
  const revise = async () => {
    const note = await promptText(t("planReviseDone"));
    if (note !== null && note.trim()) {
      await decide({ behavior: "deny", message: `The user asks to revise the plan: ${note.trim()}` });
    }
  };
  return (
    <div className="cd-card plan">
      <div className="cd-card-title" style={{ color: "var(--cd-plan)" }}>
        <FaClipboardList /> {t("planTitle")}
      </div>
      <Markdown text={plan} bare focusable maxBlocks={compact ? 6 : undefined} />
      {compact && (
        <Btn kind="ghost" onClick={openFullScreen}>
          {t("openFull")}
        </Btn>
      )}
      <Focusable className="cd-row" flow-children="horizontal">
        <Btn kind="primary" preferredFocus disabled={busy} onClick={() => decide({ behavior: "allow", mode: "auto" })}>
          <FaCheck /> {t("planApprove")}
        </Btn>
        <Btn disabled={busy} onClick={revise}>
          {t("planRevise")}
        </Btn>
        <Btn kind="danger" disabled={busy} onClick={() => decide({ behavior: "deny", interrupt: true, message: "The user cancelled the plan." })}>
          <FaTimes /> {t("planReject")}
        </Btn>
      </Focusable>
    </div>
  );
}

/* ------------------------------------------------------------------- question */

function QuestionCard({ item }: { item: PermItem }) {
  const questions: Question[] = Array.isArray(item.input?.questions) ? item.input.questions : [];
  const [sel, setSel] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  if (item.resolved) {
    return <Resolved ok={item.resolved === "allow"} icon={<FaQuestionCircle />} text={t("answered")} />;
  }
  const submit = async (answers: Record<string, string[]>) => {
    if (busy) return;
    setBusy(true);
    const flat: Record<string, string> = {};
    for (const q of questions) flat[q.question] = (answers[q.question] ?? []).join(", ");
    await respond(item.requestId, { behavior: "allow", answers: flat });
  };
  const instant = questions.length === 1 && !questions[0].multiSelect;
  const pick = async (q: Question, label: string) => {
    const next = { ...sel };
    if (q.multiSelect) {
      const cur = new Set(next[q.question] ?? []);
      cur.has(label) ? cur.delete(label) : cur.add(label);
      next[q.question] = Array.from(cur);
    } else {
      next[q.question] = [label];
    }
    setSel(next);
    if (instant) await submit(next);
  };
  const other = async (q: Question) => {
    const text = await promptText(q.question || t("otherPrompt"));
    if (text && text.trim()) await pick(q, text.trim());
  };
  const complete = questions.every((q) => (sel[q.question] ?? []).length > 0);
  return (
    <div className="cd-card attn">
      <div className="cd-card-title">
        <FaQuestionCircle /> {t("questionTitle")}
      </div>
      {questions.map((q, qi) => (
        <div key={qi} style={{ marginBottom: 10 }}>
          {q.header && <span className="cd-chip">{q.header}</span>}
          <div style={{ fontWeight: 600, marginBottom: 6 }}>{q.question}</div>
          <Focusable style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {q.options.map((o, oi) => (
              <Btn
                key={oi}
                preferredFocus={qi === 0 && oi === 0}
                className={`cd-opt ${(sel[q.question] ?? []).includes(o.label) ? "sel" : ""}`}
                disabled={busy}
                onClick={() => pick(q, o.label)}
              >
                <span>
                  {q.multiSelect ? ((sel[q.question] ?? []).includes(o.label) ? "☑ " : "☐ ") : ""}
                  {o.label}
                </span>
                {o.description && <small>{o.description}</small>}
              </Btn>
            ))}
            <Btn kind="ghost" disabled={busy} onClick={() => other(q)}>
              {t("other")}
            </Btn>
          </Focusable>
        </div>
      ))}
      {!instant && (
        <Btn kind="primary" disabled={busy || !complete} onClick={() => submit(sel)}>
          <FaCheck /> {t("confirm")}
        </Btn>
      )}
    </div>
  );
}

export function PermissionItem({ item, compact }: { item: PermItem; compact?: boolean }) {
  if (item.permKind === "plan") return <PlanCard item={item} compact={compact} />;
  if (item.permKind === "question") return <QuestionCard item={item} />;
  return <ToolPerm item={item} />;
}

/* -------------------------------------------------------------- notices, turns */

const NOTICE_KEYS: Record<string, Key> = {
  claude_missing: "nClaudeMissing",
  spawn_failed: "nSpawnFailed",
  write_failed: "nWriteFailed",
  resume_failed: "nResumeFailed",
  process_exited: "nProcessExited",
  memory_unavailable: "nMemoryUnavailable",
  mode_failed: "nModeFailed",
  auto_fallback: "autoFallback",
  interrupted: "interrupted",
};

export function NoticeLine({ item }: { item: Extract<ChatItem, { kind: "notice" }> }) {
  const key = NOTICE_KEYS[item.code];
  return (
    <Notice level={item.level}>
      {key ? t(key) : item.code}
      {item.level === "error" && item.detail ? (
        <div className="cd-mutedtxt" style={{ fontSize: ".85em", marginTop: 3, wordBreak: "break-word" }}>
          {item.detail.split("\n").slice(-2).join(" · ").slice(0, 240)}
        </div>
      ) : null}
    </Notice>
  );
}

export function TurnLine({ item }: { item: Extract<ChatItem, { kind: "turn" }> }) {
  const st = item.stats ?? {};
  const secs = st.duration_ms ? `${Math.max(1, Math.round(st.duration_ms / 1000))} s` : "";
  const turns = st.num_turns ? `${st.num_turns} ${t("turns")}` : "";
  const parts = [item.ok ? t("turnDone") : t("turnFailed"), secs, turns].filter(Boolean);
  return (
    <div className="cd-turn">
      {item.ok ? "✓" : <FaExclamationTriangle style={{ verticalAlign: -1 }} />} {parts.join(" · ")}
      {!item.ok && item.text ? <div style={{ color: "var(--cd-err)", marginTop: 2 }}>{String(item.text).slice(0, 200)}</div> : null}
    </div>
  );
}
