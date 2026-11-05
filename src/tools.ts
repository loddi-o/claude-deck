/** Human readable summaries of Claude Code tool calls. */
import { t } from "./i18n";
import type { Key } from "./i18n";

export type ToolIcon = "terminal" | "file" | "edit" | "search" | "web" | "memory" | "todo" | "agent" | "plan" | "question" | "tool";

export interface ToolSummary {
  icon: ToolIcon;
  label: string; // short name
  detail: string; // one line of the most relevant argument
}

const firstLine = (s: unknown, max = 140): string => {
  const line = String(s ?? "").split("\n")[0].trim();
  return line.length > max ? line.slice(0, max - 1) + "…" : line;
};

const base = (p: unknown): string => {
  const s = String(p ?? "");
  const home = "/home/deck/";
  return s.startsWith(home) ? "~/" + s.slice(home.length) : s;
};

export function summarizeTool(name: string, input: any): ToolSummary {
  const i = input ?? {};
  switch (name) {
    case "Bash":
      return { icon: "terminal", label: "Bash", detail: firstLine(i.description || i.command) };
    case "Read":
      return { icon: "file", label: "Read", detail: base(i.file_path) };
    case "Write":
      return { icon: "edit", label: "Write", detail: base(i.file_path) };
    case "Edit":
    case "MultiEdit":
    case "NotebookEdit":
      return { icon: "edit", label: "Edit", detail: base(i.file_path || i.notebook_path) };
    case "Glob":
      return { icon: "search", label: "Glob", detail: firstLine(i.pattern) };
    case "Grep":
      return { icon: "search", label: "Grep", detail: firstLine(i.pattern) };
    case "WebFetch":
      return { icon: "web", label: "WebFetch", detail: firstLine(i.url) };
    case "WebSearch":
      return { icon: "web", label: "WebSearch", detail: firstLine(i.query) };
    case "TodoWrite":
      return { icon: "todo", label: "Todo", detail: `${(i.todos ?? []).length}` };
    case "Task":
      return { icon: "agent", label: "Agent", detail: firstLine(i.description) };
    case "ExitPlanMode":
      return { icon: "plan", label: "Plan", detail: "" };
    case "AskUserQuestion":
      return { icon: "question", label: "Question", detail: "" };
    case "mcp__claude_deck__remember":
      return { icon: "memory", label: t("toolMemory"), detail: firstLine(i.note) };
    case "mcp__claude_deck__recall":
      return { icon: "memory", label: t("toolMemory"), detail: "recall" };
    case "mcp__claude_deck__forget":
      return { icon: "memory", label: t("toolMemory"), detail: firstLine(i.match) };
    default: {
      const vals = Object.values(i).filter((v) => typeof v === "string") as string[];
      return { icon: "tool", label: name.replace(/^mcp__/, "").replace(/__/g, ": "), detail: firstLine(vals[0] ?? "") };
    }
  }
}

/** Heading for a permission request card. */
export function permissionTitleKey(name: string): Key {
  switch (name) {
    case "Bash":
      return "permBash";
    case "Edit":
    case "MultiEdit":
    case "NotebookEdit":
      return "permEdit";
    case "Write":
      return "permWrite";
    case "Read":
    case "Glob":
    case "Grep":
      return "permRead";
    case "WebFetch":
    case "WebSearch":
      return "permWeb";
    default:
      return "permTitleTool";
  }
}

/** The text shown in the body of a permission card (command, path, diff…). */
export function permissionBody(name: string, input: any): string {
  const i = input ?? {};
  switch (name) {
    case "Bash":
      return String(i.command ?? "");
    case "Read":
    case "Write":
      return base(i.file_path) + (name === "Write" && i.content ? "\n\n" + String(i.content).slice(0, 1200) : "");
    case "Edit": {
      const old = String(i.old_string ?? "").split("\n").map((l: string) => "- " + l).join("\n");
      const neu = String(i.new_string ?? "").split("\n").map((l: string) => "+ " + l).join("\n");
      return `${base(i.file_path)}\n\n${old}\n${neu}`;
    }
    case "WebFetch":
      return String(i.url ?? "");
    case "WebSearch":
      return String(i.query ?? "");
    default:
      try {
        return JSON.stringify(i, null, 2).slice(0, 1500);
      } catch {
        return "";
      }
  }
}

export function formatAge(seconds: number): { key: Key; n?: number } {
  if (seconds < 60) return { key: "ago_s" };
  if (seconds < 3600) return { key: "ago_m", n: Math.floor(seconds / 60) };
  if (seconds < 86400) return { key: "ago_h", n: Math.floor(seconds / 3600) };
  return { key: "ago_d", n: Math.floor(seconds / 86400) };
}

export function formatBytes(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + " GB";
  if (n >= 1e6) return Math.round(n / 1e6) + " MB";
  return Math.round(n / 1e3) + " KB";
}
