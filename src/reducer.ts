/** Pure reducer: turns backend events into the list of chat items shown by the UI. */
import type { ChatItem, ChatState, PermKind } from "./types";

export function emptyChat(): ChatState {
  return { items: [], streamMid: "", streamIdx: {}, nextId: 1 };
}

const MAX_RESULT = 6000;

export function textOf(content: any): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((b) => {
        if (typeof b === "string") return b;
        if (b && b.type === "text") return b.text ?? "";
        if (b && b.type === "image") return "[image]";
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  return "";
}

function clone(state: ChatState): ChatState {
  return { ...state, items: state.items.slice(), streamIdx: { ...state.streamIdx } };
}

function nid(st: ChatState): string {
  return `i${st.nextId++}`;
}

function findIndex(st: ChatState, pred: (it: ChatItem) => boolean): number {
  for (let i = st.items.length - 1; i >= 0; i--) if (pred(st.items[i])) return i;
  return -1;
}

function findIndexById(st: ChatState, id: string): number {
  return findIndex(st, (it) => it.id === id);
}

/** earliest (oldest) item matching, needed to pair a final block with its first streamed copy */
function findFirstIndex(st: ChatState, pred: (it: ChatItem) => boolean): number {
  for (let i = 0; i < st.items.length; i++) if (pred(st.items[i])) return i;
  return -1;
}

function finalizeText(st: ChatState, msgId: string, text: string): void {
  const i = findFirstIndex(
    st,
    (it) => it.kind === "assistant" && it.msgId === msgId && !it.finalized && msgId !== ""
  );
  if (i >= 0) {
    const it = st.items[i] as Extract<ChatItem, { kind: "assistant" }>;
    st.items[i] = { ...it, text, streaming: false, finalized: true };
  } else if (text.trim()) {
    st.items.push({ kind: "assistant", id: nid(st), msgId, text, streaming: false, finalized: true });
  }
}

function finalizeThinking(st: ChatState, msgId: string, text: string): void {
  const i = findFirstIndex(
    st,
    (it) => it.kind === "thinking" && it.msgId === msgId && !it.finalized && msgId !== ""
  );
  if (i >= 0) {
    const it = st.items[i] as Extract<ChatItem, { kind: "thinking" }>;
    st.items[i] = { ...it, text, active: false, finalized: true };
  } else if (text.trim()) {
    st.items.push({ kind: "thinking", id: nid(st), msgId, text, active: false, finalized: true });
  }
}

function setToolStatus(st: ChatState, toolUseId: string | undefined, patch: Partial<Extract<ChatItem, { kind: "tool" }>>) {
  if (!toolUseId) return;
  const i = findIndex(st, (it) => it.kind === "tool" && it.toolUseId === toolUseId);
  if (i >= 0) st.items[i] = { ...(st.items[i] as any), ...patch };
}

function applyMsg(st: ChatState, msg: any, history: boolean): void {
  const type = msg?.type;
  if (type === "user") {
    const content = msg.message?.content;
    const blocks: any[] = typeof content === "string" ? [{ type: "text", text: content }] : Array.isArray(content) ? content : [];
    for (const b of blocks) {
      if (b.type === "text") {
        const text: string = b.text ?? "";
        if (!text.trim()) continue;
        if (text.startsWith("[Request interrupted")) {
          st.items.push({ kind: "notice", id: nid(st), code: "interrupted", level: "info" });
        } else {
          st.items.push({ kind: "user", id: nid(st), text });
        }
      } else if (b.type === "tool_result") {
        const res = textOf(b.content);
        setToolStatus(st, b.tool_use_id, {
          status: b.is_error ? "error" : "done",
          result: res.length > MAX_RESULT ? res.slice(0, MAX_RESULT) + "…" : res,
        });
      }
    }
  } else if (type === "assistant") {
    const msgId: string = msg.message?.id ?? "";
    const content: any[] = Array.isArray(msg.message?.content) ? msg.message.content : [];
    for (const b of content) {
      if (b.type === "text") finalizeText(st, msgId, b.text ?? "");
      else if (b.type === "thinking") finalizeThinking(st, msgId, b.thinking ?? "");
      else if (b.type === "tool_use") {
        if (findIndex(st, (it) => it.kind === "tool" && it.toolUseId === b.id) >= 0) continue;
        st.items.push({
          kind: "tool",
          id: nid(st),
          toolUseId: b.id,
          name: b.name,
          input: b.input ?? {},
          status: history ? "done" : "running",
        });
      }
    }
  } else if (type === "result") {
    for (let i = 0; i < st.items.length; i++) {
      const it = st.items[i];
      if (it.kind === "assistant" && it.streaming) st.items[i] = { ...it, streaming: false, finalized: true };
      if (it.kind === "thinking" && it.active) st.items[i] = { ...it, active: false, finalized: true };
      if (it.kind === "tool" && it.status === "running") st.items[i] = { ...it, status: "done" };
    }
    st.items.push({
      kind: "turn",
      id: nid(st),
      ok: !msg.is_error,
      stats: msg.stats ?? {},
      text: msg.is_error ? msg.result : undefined,
    });
  }
}

function applyStream(st: ChatState, p: any): void {
  switch (p.e) {
    case "ms":
      st.streamMid = p.mid ?? "";
      st.streamIdx = {};
      break;
    case "bs": {
      if (p.k === "text") {
        const id = nid(st);
        st.items.push({ kind: "assistant", id, msgId: st.streamMid, text: "", streaming: true, finalized: false });
        st.streamIdx[p.i] = id;
      } else if (p.k === "thinking") {
        const id = nid(st);
        st.items.push({ kind: "thinking", id, msgId: st.streamMid, text: "", active: true, finalized: false });
        st.streamIdx[p.i] = id;
      }
      break;
    }
    case "d": {
      let id = st.streamIdx[p.i];
      let idx = id ? findIndexById(st, id) : -1;
      if (idx < 0) {
        id = nid(st);
        st.items.push(
          p.k === "thinking"
            ? { kind: "thinking", id, msgId: st.streamMid, text: "", active: true, finalized: false }
            : { kind: "assistant", id, msgId: st.streamMid, text: "", streaming: true, finalized: false }
        );
        st.streamIdx[p.i] = id;
        idx = st.items.length - 1;
      }
      const it = st.items[idx];
      if (it.kind === "assistant" || it.kind === "thinking") st.items[idx] = { ...it, text: it.text + (p.s ?? "") } as ChatItem;
      break;
    }
    case "be": {
      const id = st.streamIdx[p.i];
      const idx = id ? findIndexById(st, id) : -1;
      if (idx >= 0) {
        const it = st.items[idx];
        if (it.kind === "assistant") st.items[idx] = { ...it, streaming: false };
        if (it.kind === "thinking") st.items[idx] = { ...it, active: false };
      }
      break;
    }
    case "me":
      st.streamMid = "";
      st.streamIdx = {};
      break;
  }
}

/** Apply one backend event. Returns the same object when the event doesn't affect the chat. */
export function reduceChat(state: ChatState, kind: string, p: any): ChatState {
  switch (kind) {
    case "reset":
      return emptyChat();
    case "history": {
      const st = clone(state);
      for (const ev of p.events ?? []) applyMsg(st, ev, true);
      return st;
    }
    case "msg": {
      const st = clone(state);
      applyMsg(st, p, false);
      return st;
    }
    case "stream": {
      const st = clone(state);
      applyStream(st, p);
      return st;
    }
    case "perm": {
      if (findIndex(state, (it) => it.kind === "perm" && it.requestId === p.request_id) >= 0) return state;
      const st = clone(state);
      st.items.push({
        kind: "perm",
        id: nid(st),
        requestId: p.request_id,
        permKind: (p.kind ?? "tool") as PermKind,
        toolName: p.tool_name ?? "",
        toolUseId: p.tool_use_id,
        input: p.input ?? {},
        description: p.description ?? undefined,
        blockedPath: p.blocked_path ?? undefined,
        canAlways: !!p.can_always,
      });
      setToolStatus(st, p.tool_use_id, { status: "waiting" });
      return st;
    }
    case "perm_done": {
      const i = findIndex(state, (it) => it.kind === "perm" && it.requestId === p.request_id);
      if (i < 0) return state;
      const st = clone(state);
      const it = st.items[i] as Extract<ChatItem, { kind: "perm" }>;
      const outcome = p.outcome === "allow" ? "allow" : p.outcome === "deny" ? "deny" : "cancelled";
      st.items[i] = { ...it, resolved: outcome };
      setToolStatus(st, it.toolUseId, { status: outcome === "allow" ? "running" : outcome === "deny" ? "denied" : "done" });
      return st;
    }
    case "notice": {
      const st = clone(state);
      st.items.push({
        kind: "notice",
        id: nid(st),
        code: p.code,
        level: p.level ?? "info",
        detail: p.detail,
        rc: p.rc,
      });
      return st;
    }
    default:
      return state;
  }
}

/** The permission request currently waiting for the user, if any. */
export function pendingPerm(items: ChatItem[]): Extract<ChatItem, { kind: "perm" }> | undefined {
  for (let i = items.length - 1; i >= 0; i--) {
    const it = items[i];
    if (it.kind === "perm" && !it.resolved) return it;
  }
  return undefined;
}
