import { describe, expect, it } from "vitest";
import { parseInline, parseMarkdown } from "../../src/markdown";
import { formatAge, formatBytes, permissionBody, summarizeTool } from "../../src/tools";

describe("parseMarkdown", () => {
  it("splits headings, paragraphs, lists, code, quotes, rules", () => {
    const md = [
      "# Titolo",
      "prima riga",
      "seconda riga",
      "",
      "- uno",
      "- due",
      "  continua",
      "",
      "1. primo",
      "2. secondo",
      "",
      "```bash",
      "echo ciao",
      "```",
      "> citazione",
      "---",
    ].join("\n");
    const blocks = parseMarkdown(md);
    expect(blocks.map((b) => b.t)).toEqual(["h", "p", "ul", "ol", "code", "quote", "hr"]);
    expect((blocks[1] as any).text).toBe("prima riga seconda riga");
    expect((blocks[2] as any).items).toEqual(["uno", "due continua"]);
    expect((blocks[4] as any)).toMatchObject({ lang: "bash", text: "echo ciao" });
  });

  it("tolerates an unterminated code fence (streaming)", () => {
    const blocks = parseMarkdown("testo\n```sh\nls -la\nstill typing");
    expect(blocks.map((b) => b.t)).toEqual(["p", "code"]);
    expect((blocks[1] as any).text).toBe("ls -la\nstill typing");
  });

  it("keeps tables as preformatted text without the separator row", () => {
    const blocks = parseMarkdown("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(blocks).toEqual([{ t: "table", text: "| a | b |\n| 1 | 2 |" }]);
  });

  it("empty input", () => {
    expect(parseMarkdown("")).toEqual([]);
  });
});

describe("parseInline", () => {
  it("code, bold, italic and links", () => {
    const parts = parseInline("usa `ls -la` con **cautela**, *piano* e [doc](https://x.io/a)");
    expect(parts.map((p) => p.t)).toEqual(["text", "code", "text", "b", "text", "i", "text", "link"]);
    expect(parts[1].text).toBe("ls -la");
    expect(parts[7]).toMatchObject({ text: "doc", href: "https://x.io/a" });
  });

  it("does not treat snake_case or a*b as emphasis", () => {
    expect(parseInline("file_name_here e 2*3*4").every((p) => p.t === "text")).toBe(true);
  });
});

describe("tool helpers", () => {
  it("summarizes common tools", () => {
    expect(summarizeTool("Bash", { command: "journalctl -b\nsecond", description: "" }).detail).toBe("journalctl -b");
    expect(summarizeTool("Read", { file_path: "/home/deck/.bashrc" }).detail).toBe("~/.bashrc");
    expect(summarizeTool("mcp__claude_deck__remember", { note: "x" }).icon).toBe("memory");
    expect(summarizeTool("mcp__srv__do", { a: "b" }).label).toBe("srv: do");
  });

  it("permission body shows a diff for Edit", () => {
    const body = permissionBody("Edit", { file_path: "/etc/x", old_string: "a", new_string: "b\nc" });
    expect(body).toContain("- a");
    expect(body).toContain("+ b\n+ c");
  });

  it("formats age and bytes", () => {
    expect(formatAge(5).key).toBe("ago_s");
    expect(formatAge(300)).toEqual({ key: "ago_m", n: 5 });
    expect(formatAge(7200)).toEqual({ key: "ago_h", n: 2 });
    expect(formatAge(172800)).toEqual({ key: "ago_d", n: 2 });
    expect(formatBytes(190085487)).toBe("190 MB");
    expect(formatBytes(2.5e9)).toBe("2.5 GB");
  });
});
