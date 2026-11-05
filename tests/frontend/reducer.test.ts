import { describe, expect, it } from "vitest";
import { emptyChat, pendingPerm, reduceChat, textOf } from "../../src/reducer";
import type { ChatItem, ChatState } from "../../src/types";

const run = (events: [string, any][], from: ChatState = emptyChat()) =>
  events.reduce((st, [k, p]) => reduceChat(st, k, p), from);

const kinds = (st: ChatState) => st.items.map((i) => i.kind);

// Event order as captured from the real CLI: message_start, block_start, deltas, assistant (full block), block_stop, message_stop
const textTurn = (mid: string, text: string): [string, any][] => [
  ["stream", { e: "ms", mid }],
  ["stream", { e: "bs", i: 0, k: "text" }],
  ["stream", { e: "d", i: 0, k: "text", s: text.slice(0, 3) }],
  ["stream", { e: "d", i: 0, k: "text", s: text.slice(3) }],
  ["msg", { type: "assistant", message: { id: mid, content: [{ type: "text", text }] } }],
  ["stream", { e: "be", i: 0 }],
  ["stream", { e: "me" }],
];

describe("streaming assistant text", () => {
  it("builds one item from deltas and replaces it (no duplicate) with the final block", () => {
    let st = run(textTurn("m1", "Ciao mondo").slice(0, 4));
    expect(st.items).toHaveLength(1);
    const it = st.items[0] as Extract<ChatItem, { kind: "assistant" }>;
    expect(it.text).toBe("Ciao mondo");
    expect(it.streaming).toBe(true);

    st = run(textTurn("m1", "Ciao mondo").slice(4), st);
    expect(st.items).toHaveLength(1);
    const done = st.items[0] as Extract<ChatItem, { kind: "assistant" }>;
    expect(done.finalized).toBe(true);
    expect(done.streaming).toBe(false);
  });

  it("works without partial messages (final block only)", () => {
    const st = run([["msg", { type: "assistant", message: { id: "m9", content: [{ type: "text", text: "solo finale" }] } }]]);
    expect(st.items).toHaveLength(1);
    expect((st.items[0] as any).text).toBe("solo finale");
  });

  it("creates the item when the first delta arrives without block_start (UI attached mid-stream)", () => {
    const st = run([["stream", { e: "d", i: 2, k: "text", s: "metà" }]]);
    expect(st.items).toHaveLength(1);
    expect((st.items[0] as any).text).toBe("metà");
  });

  it("empty thinking blocks are tracked but finalize quietly", () => {
    const st = run([
      ["stream", { e: "ms", mid: "m2" }],
      ["stream", { e: "bs", i: 0, k: "thinking" }],
      ["msg", { type: "assistant", message: { id: "m2", content: [{ type: "thinking", thinking: "" }] } }],
    ]);
    expect(st.items).toHaveLength(1);
    expect((st.items[0] as any).active).toBe(false);
  });
});

describe("tool lifecycle", () => {
  const toolUse = ["msg", { type: "assistant", message: { id: "m3", content: [{ type: "tool_use", id: "t1", name: "Bash", input: { command: "ls" } }] } }] as [string, any];

  it("running -> done with output", () => {
    const st = run([
      toolUse,
      ["msg", { type: "user", message: { content: [{ type: "tool_result", tool_use_id: "t1", content: "file.txt", is_error: false }] } }],
    ]);
    const tool = st.items[0] as Extract<ChatItem, { kind: "tool" }>;
    expect(tool.status).toBe("done");
    expect(tool.result).toBe("file.txt");
  });

  it("tool_result with list content and is_error", () => {
    const st = run([
      toolUse,
      ["msg", { type: "user", message: { content: [{ type: "tool_result", tool_use_id: "t1", content: [{ type: "text", text: "boom" }], is_error: true }] } }],
    ]);
    expect((st.items[0] as any).status).toBe("error");
    expect((st.items[0] as any).result).toBe("boom");
  });

  it("permission request flips the tool to waiting, then allow -> running, deny -> denied", () => {
    const perm = ["perm", { request_id: "r1", kind: "tool", tool_name: "Bash", tool_use_id: "t1", input: { command: "ls" }, can_always: true }] as [string, any];
    let st = run([toolUse, perm]);
    expect((st.items[0] as any).status).toBe("waiting");
    expect(pendingPerm(st.items)?.requestId).toBe("r1");
    const allowed = run([["perm_done", { request_id: "r1", outcome: "allow" }]], st);
    expect((allowed.items[0] as any).status).toBe("running");
    expect(pendingPerm(allowed.items)).toBeUndefined();
    const denied = run([["perm_done", { request_id: "r1", outcome: "deny" }]], st);
    expect((denied.items[0] as any).status).toBe("denied");
    // duplicates are ignored
    expect(run([perm], st).items).toHaveLength(st.items.length);
  });

  it("result closes dangling running tools and adds a turn summary", () => {
    const st = run([toolUse, ["msg", { type: "result", is_error: false, stats: { duration_ms: 1200, num_turns: 2 } }]]);
    expect((st.items[0] as any).status).toBe("done");
    expect(kinds(st)).toEqual(["tool", "turn"]);
  });
});

describe("user messages, history, reset", () => {
  it("local echo and interruption marker", () => {
    const st = run([
      ["msg", { type: "user", local: true, message: { content: [{ type: "text", text: "ciao" }] } }],
      ["msg", { type: "user", message: { content: [{ type: "text", text: "[Request interrupted by user]" }] } }],
    ]);
    expect(kinds(st)).toEqual(["user", "notice"]);
    expect((st.items[1] as any).code).toBe("interrupted");
  });

  it("history replays user/assistant/tool without spinners", () => {
    const st = run([
      [
        "history",
        {
          events: [
            { type: "user", message: { content: "dimmi lo spazio" } },
            { type: "assistant", message: { id: "h1", content: [{ type: "tool_use", id: "ht", name: "Bash", input: { command: "df -h" } }] } },
            { type: "user", message: { content: [{ type: "tool_result", tool_use_id: "ht", content: "ok" }] } },
            { type: "assistant", message: { id: "h2", content: [{ type: "text", text: "Hai 100 GB liberi" }] } },
          ],
        },
      ],
    ]);
    expect(kinds(st)).toEqual(["user", "tool", "assistant"]);
    expect((st.items[1] as any).status).toBe("done");
  });

  it("reset clears everything", () => {
    const st = run([...textTurn("m1", "abc"), ["reset", {}]]);
    expect(st.items).toHaveLength(0);
  });

  it("unrelated kinds return the same state object", () => {
    const st = emptyChat();
    expect(reduceChat(st, "status", {})).toBe(st);
    expect(reduceChat(st, "voice", {})).toBe(st);
  });
});

describe("questions, plans, notices", () => {
  it("keeps question/plan kinds", () => {
    const st = run([
      ["perm", { request_id: "q", kind: "question", tool_name: "AskUserQuestion", input: { questions: [] } }],
      ["perm", { request_id: "p", kind: "plan", tool_name: "ExitPlanMode", input: { plan: "# x" } }],
    ]);
    expect(st.items.map((i: any) => i.permKind)).toEqual(["question", "plan"]);
    expect(pendingPerm(st.items)?.requestId).toBe("p");
  });

  it("notices carry code, level and detail", () => {
    const st = run([["notice", { code: "process_exited", level: "error", rc: 3, detail: "boom" }]]);
    expect(st.items[0]).toMatchObject({ kind: "notice", code: "process_exited", level: "error", rc: 3, detail: "boom" });
  });

  it("only the first matching streamed item is finalized per block", () => {
    const st = run([
      ["stream", { e: "ms", mid: "mm" }],
      ["stream", { e: "bs", i: 0, k: "text" }],
      ["stream", { e: "d", i: 0, k: "text", s: "uno" }],
      ["stream", { e: "bs", i: 1, k: "text" }],
      ["stream", { e: "d", i: 1, k: "text", s: "due" }],
      ["msg", { type: "assistant", message: { id: "mm", content: [{ type: "text", text: "uno" }] } }],
      ["msg", { type: "assistant", message: { id: "mm", content: [{ type: "text", text: "due" }] } }],
    ]);
    expect(st.items.map((i: any) => [i.text, i.finalized])).toEqual([["uno", true], ["due", true]]);
  });
});

describe("textOf", () => {
  it("flattens blocks", () => {
    expect(textOf([{ type: "text", text: "a" }, { type: "image" }, { type: "tool_reference" }])).toBe("a\n[immagine]");
    expect(textOf("x")).toBe("x");
    expect(textOf(null)).toBe("");
  });
});
