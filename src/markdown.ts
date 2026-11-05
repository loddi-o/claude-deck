/** Tiny dependency-free markdown parser (blocks + inline), enough for chat answers. */

export type MdBlock =
  | { t: "p"; text: string }
  | { t: "h"; level: number; text: string }
  | { t: "code"; lang: string; text: string }
  | { t: "ul"; items: string[] }
  | { t: "ol"; items: string[]; start: number }
  | { t: "quote"; text: string }
  | { t: "table"; text: string }
  | { t: "hr" };

export type MdInline = { t: "text" | "code" | "b" | "i" | "link"; text: string; href?: string };

export function parseMarkdown(src: string): MdBlock[] {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const out: MdBlock[] = [];
  let i = 0;
  const flushPara = (buf: string[]) => {
    if (buf.length) out.push({ t: "p", text: buf.join(" ").trim() });
    buf.length = 0;
  };
  const para: string[] = [];

  while (i < lines.length) {
    const line = lines[i];

    // fenced code (also an unterminated one, as happens while streaming)
    const fence = /^\s*(```|~~~)\s*([\w+-]*)\s*$/.exec(line);
    if (fence) {
      flushPara(para);
      const marker = fence[1];
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(marker)) body.push(lines[i++]);
      i++; // closing fence
      out.push({ t: "code", lang: fence[2] || "", text: body.join("\n") });
      continue;
    }

    if (!line.trim()) {
      flushPara(para);
      i++;
      continue;
    }

    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) {
      flushPara(para);
      out.push({ t: "h", level: h[1].length, text: h[2].trim() });
      i++;
      continue;
    }

    if (/^\s*([-*_])\s*(\1\s*){2,}$/.test(line)) {
      flushPara(para);
      out.push({ t: "hr" });
      i++;
      continue;
    }

    if (/^\s*>/.test(line)) {
      flushPara(para);
      const q: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) q.push(lines[i++].replace(/^\s*>\s?/, ""));
      out.push({ t: "quote", text: q.join("\n") });
      continue;
    }

    if (/^\s*\|.*\|\s*$/.test(line)) {
      flushPara(para);
      const rows: string[] = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        if (!/^\s*\|[\s:|-]+\|\s*$/.test(lines[i])) rows.push(lines[i].trim());
        i++;
      }
      out.push({ t: "table", text: rows.join("\n") });
      continue;
    }

    const ul = /^\s*[-*+]\s+(.*)$/.exec(line);
    if (ul) {
      flushPara(para);
      const items: string[] = [];
      while (i < lines.length) {
        const m = /^\s*[-*+]\s+(.*)$/.exec(lines[i]);
        if (m) {
          items.push(m[1]);
          i++;
        } else if (/^\s{2,}\S/.test(lines[i]) && items.length) {
          items[items.length - 1] += " " + lines[i].trim();
          i++;
        } else break;
      }
      out.push({ t: "ul", items });
      continue;
    }

    const ol = /^\s*(\d+)[.)]\s+(.*)$/.exec(line);
    if (ol) {
      flushPara(para);
      const start = parseInt(ol[1], 10);
      const items: string[] = [];
      while (i < lines.length) {
        const m = /^\s*\d+[.)]\s+(.*)$/.exec(lines[i]);
        if (m) {
          items.push(m[1]);
          i++;
        } else if (/^\s{2,}\S/.test(lines[i]) && items.length) {
          items[items.length - 1] += " " + lines[i].trim();
          i++;
        } else break;
      }
      out.push({ t: "ol", items, start });
      continue;
    }

    para.push(line.trim());
    i++;
  }
  flushPara(para);
  return out;
}

export function parseInline(src: string): MdInline[] {
  const out: MdInline[] = [];
  const re = /(`+)([^`]+?)\1|\*\*([^*]+?)\*\*|__([^_]+?)__|\[([^\]]+)\]\((https?:[^)\s]+)\)|(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src))) {
    if (m.index > last) out.push({ t: "text", text: src.slice(last, m.index) });
    if (m[2] !== undefined) out.push({ t: "code", text: m[2] });
    else if (m[3] !== undefined) out.push({ t: "b", text: m[3] });
    else if (m[4] !== undefined) out.push({ t: "b", text: m[4] });
    else if (m[5] !== undefined) out.push({ t: "link", text: m[5], href: m[6] });
    else if (m[7] !== undefined) out.push({ t: "i", text: m[7] });
    last = m.index + m[0].length;
  }
  if (last < src.length) out.push({ t: "text", text: src.slice(last) });
  return out;
}
