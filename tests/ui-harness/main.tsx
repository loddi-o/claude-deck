import "./pre";
import { createRoot } from "react-dom/client";
import { FullScreen } from "../../src/pages/FullScreen";
import { QuickPanel } from "../../src/pages/QuickPanel";
import { initStore, setTab } from "../../src/store";
import type { Tab } from "../../src/store";
import { emitToUi } from "./mock-api";
import { scenario } from "./scenarios";

const q = new URLSearchParams(location.search);
const view = q.get("view") || "full";
const name = q.get("scenario") || "chat";
const tab = (q.get("tab") || "chat") as Tab;

const lang = (q.get("lang") || "it") as "it" | "en" | "auto";
const { state, setup, live } = scenario(name, lang);
(window as any).__state = state;
(window as any).__setup = setup;

document.body.classList.add(view === "qam" ? "qam" : "full");

async function start() {
  await initStore();
  setTab(tab);
  if (live) {
    // replay "live" events after mount to exercise the streaming path
    let seq = state.seq;
    for (const [kind, payload, delay] of live) {
      await new Promise((r) => setTimeout(r, delay ?? 30));
      emitToUi("cd", ++seq, kind, payload);
    }
  }
  document.title = "ready";
}

const root = createRoot(document.getElementById("root")!);
root.render(view === "qam" ? <QuickPanel /> : <FullScreen />);
void start();
window.addEventListener("error", (e) => {
  document.body.setAttribute("data-error", String(e.message));
});
