import { Focusable } from "@decky/ui";
import { useCallback, useEffect, useState } from "react";
import { FaHistory, FaPlay, FaPlus, FaTrash } from "react-icons/fa";
import { api } from "../api";
import { Btn, SectionTitle, confirmDialog } from "../components/ui";
import { t } from "../i18n";
import { newSession, setTab, useStore } from "../store";
import { formatAge } from "../tools";
import type { SessionInfo } from "../types";

export function SessionsPage() {
  const { status } = useStore();
  const [list, setList] = useState<SessionInfo[] | null>(null);

  const load = useCallback(async () => {
    try {
      setList(await api.listSessions());
    } catch {
      setList([]);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load, status.session_id]);

  const resume = async (id: string) => {
    await api.resumeSession(id);
    setTab("chat");
  };
  const remove = async (s: SessionInfo) => {
    if (await confirmDialog(t("sessionDeleteConfirm"), s.title)) {
      await api.deleteSession(s.id);
      await load();
    }
  };
  const fresh = async () => {
    await newSession();
    setTab("chat");
  };

  return (
    <div className="cd-page">
      <Focusable className="cd-row" flow-children="horizontal" style={{ marginTop: 6 }}>
        <Btn kind="primary" preferredFocus onClick={fresh}>
          <FaPlus /> {t("newChat")}
        </Btn>
      </Focusable>
      <SectionTitle>
        <FaHistory style={{ verticalAlign: -2 }} /> {t("sessionsTitle")}
      </SectionTitle>
      {list === null && <div className="cd-mutedtxt">{t("loading")}</div>}
      {list && list.length === 0 && <div className="cd-mutedtxt">{t("sessionsEmpty")}</div>}
      {list?.map((s) => {
        const current = s.id === status.session_id;
        const age = formatAge(s.age_s);
        return (
          <Focusable key={s.id} className="cd-item" flow-children="horizontal">
            <div className="cd-grow">
              <div className="cd-title">{s.title}</div>
              <div className="cd-sub">
                {current ? `${t("sessionCurrent")} · ` : ""}
                {t(age.key, { n: age.n ?? 0 })}
              </div>
            </div>
            {!current && (
              <Btn onClick={() => resume(s.id)}>
                <FaPlay /> {t("sessionResume")}
              </Btn>
            )}
            <Btn kind="danger" onClick={() => remove(s)}>
              <FaTrash />
            </Btn>
          </Focusable>
        );
      })}
    </div>
  );
}
