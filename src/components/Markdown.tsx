import { Focusable } from "@decky/ui";
import { memo, ReactElement, ReactNode, useMemo } from "react";
import { MdBlock, parseInline, parseMarkdown } from "../markdown";

function Inline({ text }: { text: string }) {
  return (
    <>
      {parseInline(text).map((n, i) => {
        switch (n.t) {
          case "code":
            return (
              <code key={i} className="cd-inline-code">
                {n.text}
              </code>
            );
          case "b":
            return <b key={i}>{n.text}</b>;
          case "i":
            return <i key={i}>{n.text}</i>;
          case "link":
            return (
              <span key={i} style={{ textDecoration: "underline" }}>
                {n.text}
              </span>
            );
          default:
            return <span key={i}>{n.text}</span>;
        }
      })}
    </>
  );
}

function BlockView({ b }: { b: MdBlock }): ReactElement | null {
  switch (b.t) {
    case "p":
      return (
        <p>
          <Inline text={b.text} />
        </p>
      );
    case "h":
      return b.level <= 1 ? (
        <h1>
          <Inline text={b.text} />
        </h1>
      ) : (
        <h3>
          <Inline text={b.text} />
        </h3>
      );
    case "code":
      return <pre className="cd-code">{b.text}</pre>;
    case "table":
      return <pre className="cd-code">{b.text}</pre>;
    case "ul":
      return (
        <ul>
          {b.items.map((it, i) => (
            <li key={i}>
              <Inline text={it} />
            </li>
          ))}
        </ul>
      );
    case "ol":
      return (
        <ol start={b.start}>
          {b.items.map((it, i) => (
            <li key={i}>
              <Inline text={it} />
            </li>
          ))}
        </ol>
      );
    case "quote":
      return (
        <div className="cd-quote">
          <Inline text={b.text} />
        </div>
      );
    case "hr":
      return <hr style={{ borderColor: "var(--cd-line)", width: "100%" }} />;
    default:
      return null;
  }
}

/**
 * Renders markdown. Each block is its own focus target (focusable=true) so the D-pad walks
 * through a long answer block by block and the page scrolls with it.
 */
export const Markdown = memo(function Markdown({
  text,
  focusable = true,
  streaming = false,
  bare = false,
  maxBlocks,
}: {
  text: string;
  focusable?: boolean;
  streaming?: boolean;
  bare?: boolean;
  maxBlocks?: number;
}) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  const shown = maxBlocks ? blocks.slice(0, maxBlocks) : blocks;
  const wrap = (child: ReactNode, i: number) =>
    focusable ? (
      <Focusable key={i} className="cd-block" focusClassName="cd-focus" noFocusRing>
        {child}
      </Focusable>
    ) : (
      <div key={i} className="cd-block">
        {child}
      </div>
    );
  return (
    <div className={bare ? "" : "cd-asst"}>
      {shown.map((b, i) => wrap(<BlockView b={b} />, i))}
      {shown.length < blocks.length && <div className="cd-mutedtxt">…</div>}
      {streaming && <span className="cd-cursor" />}
    </div>
  );
});
