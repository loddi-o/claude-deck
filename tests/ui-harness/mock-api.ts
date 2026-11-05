/* Minimal stand-in for @decky/api: a fake backend driven by window.__scenario. */

type Listener = (...args: any[]) => any;
const listeners: Record<string, Listener[]> = {};

export const addEventListener = (event: string, l: Listener) => {
  (listeners[event] ||= []).push(l);
  return l;
};
export const removeEventListener = (event: string, l: Listener) => {
  listeners[event] = (listeners[event] || []).filter((x) => x !== l);
};
export const emitToUi = (event: string, ...args: any[]) => (listeners[event] || []).forEach((l) => l(...args));

const fixtures: Record<string, (...a: any[]) => any> = {
  get_state: () => (window as any).__state,
  list_sessions: () => [
    { id: "2d5c8788-901d-4d76-b2cf-1e9537918011", title: "Giochi PS3 migrati su EmuDeck: non partono dopo l'aggiornamento", age_s: 600, mtime: 0, size: 1 },
    { id: "892fc60e-343c-406d-b413-31e9616bcf2d", title: "Audio Bluetooth che scatta con le cuffie", age_s: 86400 * 2, mtime: 0, size: 1 },
    { id: "cd6586e5-01ff-4f28-a386-fb6cc9467e16", title: "Installa fastfetch e mostra le info di sistema", age_s: 3 * 3600, mtime: 0, size: 1 },
  ],
  memory_get: () =>
    "# Memoria di Claude Deck\nNote persistenti.\n\n## Note\n- [2026-11-04] Il dispositivo è una BC-250 con SteamOS, niente microfono integrato\n- [2026-11-04] EmuDeck installato in ~/Emulation; RPCS3 come AppImage\n- [2026-11-05] Per i giochi PS3 serve il firmware PS3UPDAT.PUP in ~/.config/rpcs3\n",
  setup_check: () => (window as any).__setup,
  sudo_test: () => ({ ok: true, message: "ok" }),
  set_settings: (patch: any) => ({ ...(window as any).__state.settings, ...patch }),
};

export const callable = (route: string) => async (...args: any[]) => {
  (window as any).__calls = ((window as any).__calls || []).concat([[route, args]]);
  const f = fixtures[route];
  return f ? f(...args) : true;
};

export const routerHook = { addRoute() {}, removeRoute() {} };
export const toaster = { toast() {} };
export const definePlugin = (fn: any) => fn;
