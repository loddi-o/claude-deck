import { Focusable } from "@decky/ui";
import { useCallback, useEffect, useState } from "react";
import { FaBrain, FaPlus, FaTrash } from "react-icons/fa";
import { api } from "../api";
import { Btn, SectionTitle, confirmDialog, promptText } from "../components/ui";
import { t } from "../i18n";

interface Note {
  line: number;
  text: string;
}

export function MemoryPage() {
  const [raw, setRaw] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRaw(await api.memoryGet());
    } catch {
      setRaw("");
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const lines = (raw ?? "").split("\n");
  const notes: Note[] = lines
    .map((text, line) => ({ text, line }))
    .filter((l) => l.text.trimStart().startsWith("- "));

  const add = async () => {
    const note = await promptText(t("memoryAddPrompt"));
    if (note && note.trim()) {
      await api.memoryAdd(note.trim());
      await load();
    }
  };
  const remove = async (n: Note) => {
    const next = lines.filter((_, i) => i !== n.line).join("\n");
    await api.memorySet(next);
    await load();
  };
  const clear = async () => {
    if (await confirmDialog(t("memoryClearConfirm"))) {
      await api.memoryClear();
      await load();
    }
  };

  return (
    <div className="cd-page">
      <SectionTitle>
        <FaBrain style={{ verticalAlign: -2 }} /> {t("memoryTitle")}
      </SectionTitle>
      <div className="cd-mutedtxt" style={{ marginBottom: 10 }}>
        {t("memoryDesc")}
      </div>
      <Focusable className="cd-row" flow-children="horizontal">
        <Btn kind="primary" preferredFocus onClick={add}>
          <FaPlus /> {t("memoryAdd")}
        </Btn>
        <Btn kind="danger" onClick={clear} disabled={notes.length === 0}>
          <FaTrash /> {t("memoryClear")}
        </Btn>
      </Focusable>
      <div style={{ height: 12 }} />
      {raw === null && <div className="cd-mutedtxt">{t("loading")}</div>}
      {raw !== null && notes.length === 0 && <div className="cd-mutedtxt">{t("memoryEmpty")}</div>}
      {notes.map((n) => (
        <Focusable key={n.line} className="cd-item" flow-children="horizontal">
          <div className="cd-grow" style={{ whiteSpace: "normal", wordBreak: "break-word" }}>
            {n.text.replace(/^\s*-\s*/, "")}
          </div>
          <Btn kind="danger" onClick={() => remove(n)}>
            <FaTrash />
          </Btn>
        </Focusable>
      ))}
    </div>
  );
}
