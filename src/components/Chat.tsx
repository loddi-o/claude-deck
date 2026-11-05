import { Focusable } from "@decky/ui";
import { memo, useEffect, useRef } from "react";
import { t } from "../i18n";
import type { Key } from "../i18n";
import { sendText } from "../store";
import type { ChatItem } from "../types";
import { Markdown } from "./Markdown";
import { NoticeLine, PermissionItem, ToolCard, TurnLine } from "./Cards";
import { Btn, Spark } from "./ui";

const SUGGESTIONS: Key[] = ["sug1", "sug2", "sug3", "sug4", "sug5"];

export function Welcome({ compact }: { compact?: boolean }) {
  return (
    <div className="cd-welcome">
      <div style={{ color: "var(--cd-accent)" }}>
        <Spark size={compact ? 34 : 52} />
      </div>
      <h2>{t("welcomeTitle")}</h2>
      <p>{t("welcomeBody")}</p>
      <Focusable className="cd-sugs" flow-children="vertical">
        {SUGGESTIONS.slice(0, compact ? 3 : 5).map((k, i) => (
          <Btn key={k} kind="ghost" preferredFocus={i === 0 && !compact} onClick={() => sendText(t(k))}>
            {t(k)}
          </Btn>
        ))}
      </Focusable>
    </div>
  );
}

const Item = memo(function Item({ item, compact }: { item: ChatItem; compact?: boolean }) {
  switch (item.kind) {
    case "user":
      return (
        <Focusable className="cd-user" focusClassName="cd-focus" noFocusRing>
          <div className="cd-bubble">{item.text}</div>
        </Focusable>
      );
    case "assistant":
      return item.text ? <Markdown text={item.text} streaming={item.streaming} focusable={!compact} /> : null;
    case "thinking":
      return item.active ? (
        <div className="cd-thinking">
          <span className="cd-spin">◐</span> {t("thinking")}
        </div>
      ) : null;
    case "tool":
      return <ToolCard item={item} />;
    case "perm":
      return <PermissionItem item={item} compact={compact} />;
    case "notice":
      return <NoticeLine item={item} />;
    case "turn":
      return <TurnLine item={item} />;
    default:
      return null;
  }
});

export function ChatList({ items, compact }: { items: ChatItem[]; compact?: boolean }) {
  return (
    <div className="cd-list">
      {items.map((it) => (
        <Item key={it.id} item={it} compact={compact} />
      ))}
    </div>
  );
}

/** Scrolling container that sticks to the bottom while new content arrives. */
export function ChatScroller({ items, children }: { items: ChatItem[]; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const onScroll = () => {
    const el = ref.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
  };
  useEffect(() => {
    const el = ref.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [items]);
  // PageUp/PageDown from a physical keyboard
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = ref.current;
      if (!el) return;
      if (e.key === "PageUp") el.scrollBy({ top: -el.clientHeight * 0.85 });
      else if (e.key === "PageDown") el.scrollBy({ top: el.clientHeight * 0.85 });
      else if (e.key === "End") el.scrollTop = el.scrollHeight;
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  return (
    <div className="cd-scroll" ref={ref} onScroll={onScroll}>
      <div className="cd-page">{children}</div>
    </div>
  );
}
