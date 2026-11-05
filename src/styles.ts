/** All CSS of the plugin (injected once). Prefix: cd- */
export const CSS = `
.cd-root {
  --cd-accent: #d97757;
  --cd-accent-soft: rgba(217,119,87,.16);
  --cd-plan: #5aa9e6;
  --cd-ok: #5bd17a;
  --cd-warn: #f2c744;
  --cd-err: #ef6b6b;
  --cd-card: rgba(255,255,255,.055);
  --cd-card-2: rgba(255,255,255,.09);
  --cd-line: rgba(255,255,255,.12);
  --cd-text: #e8eaed;
  --cd-dim: #9aa3ad;
  --cd-scale: 1;
  --cd-mono: ui-monospace, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace;
  color: var(--cd-text);
  font-size: calc(15px * var(--cd-scale));
  line-height: 1.45;
  box-sizing: border-box;
}
.cd-root *, .cd-root *::before, .cd-root *::after { box-sizing: border-box; }
.cd-compact { font-size: calc(13px * var(--cd-scale)); }

/* ---- focus ring: one look everywhere ---- */
.cd-focus, .cd-root .gpfocus:not(.cd-nofocus) {
  outline: 2px solid var(--cd-accent) !important;
  outline-offset: 1px;
  box-shadow: 0 0 0 5px rgba(217,119,87,.22) !important;
  border-radius: 10px;
}

/* ---- full screen layout ---- */
.cd-screen {
  position: absolute; top: 40px; left: 0; right: 0; bottom: 0;
  display: flex; flex-direction: column;
  background: radial-gradient(1200px 500px at 70% -10%, rgba(217,119,87,.10), transparent 60%), #14171b;
}
.cd-header {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 22px; border-bottom: 1px solid var(--cd-line);
  background: rgba(0,0,0,.25); flex: 0 0 auto;
}
.cd-brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.15em; color: var(--cd-accent); }
.cd-status { display: flex; align-items: center; gap: 8px; color: var(--cd-dim); font-size: .92em; min-width: 0; }
.cd-spacer { flex: 1; }
.cd-tabs { display: flex; gap: 8px; padding: 8px 22px; flex: 0 0 auto; }
.cd-tab {
  display: flex !important; align-items: center; gap: 8px; width: auto !important; min-width: 0 !important;
  padding: 8px 16px !important; border-radius: 999px !important; font-size: .95em !important;
  background: var(--cd-card) !important; color: var(--cd-dim) !important;
}
.cd-tab.cd-on { background: var(--cd-accent-soft) !important; color: var(--cd-accent) !important; font-weight: 700; }
.cd-body { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; }
.cd-scroll { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 8px 22px 16px; }
.cd-page { max-width: 980px; margin: 0 auto; }
.cd-footer { flex: 0 0 auto; padding: 8px 22px 12px; border-top: 1px solid var(--cd-line); background: rgba(0,0,0,.28); }

/* ---- status ---- */
.cd-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--cd-ok); flex: 0 0 auto; }
.cd-dot.working { background: var(--cd-accent); animation: cd-pulse 1.1s ease-in-out infinite; }
.cd-dot.waiting { background: var(--cd-warn); animation: cd-pulse 1.6s ease-in-out infinite; }
.cd-dot.off { background: #5b6470; }
@keyframes cd-pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: .45; transform: scale(.8); } }
@keyframes cd-spin { to { transform: rotate(360deg); } }
.cd-spin { animation: cd-spin 1s linear infinite; display: inline-block; }

/* ---- mode switch ---- */
.cd-mode { display: flex; gap: 0; border-radius: 999px; background: var(--cd-card); padding: 3px; }
.cd-mode .cd-seg {
  display: flex !important; align-items: center; justify-content: center; gap: 6px;
  width: auto !important; min-width: 0 !important; flex: 1;
  padding: 7px 16px !important; border-radius: 999px !important; background: transparent !important;
  color: var(--cd-dim) !important; font-weight: 600; font-size: .95em !important;
}
.cd-mode .cd-seg.plan.cd-on { background: rgba(90,169,230,.22) !important; color: var(--cd-plan) !important; }
.cd-mode .cd-seg.auto.cd-on { background: var(--cd-accent-soft) !important; color: var(--cd-accent) !important; }

/* ---- chat ---- */
.cd-list { display: flex; flex-direction: column; gap: 10px; }
.cd-user { display: flex; justify-content: flex-end; }
.cd-bubble {
  max-width: 86%; padding: 10px 14px; border-radius: 16px 16px 4px 16px;
  background: var(--cd-accent-soft); border: 1px solid rgba(217,119,87,.35);
  white-space: pre-wrap; word-break: break-word;
}
.cd-asst { padding: 2px 4px 2px 12px; border-left: 3px solid var(--cd-accent); }
.cd-asst > * + * { margin-top: 8px; }
.cd-block { padding: 2px 6px; border-radius: 8px; word-break: break-word; }
.cd-block p, .cd-block ul, .cd-block ol { margin: 0; }
.cd-block ul, .cd-block ol { padding-left: 1.3em; }
.cd-block li + li { margin-top: 3px; }
.cd-block h1, .cd-block h2, .cd-block h3, .cd-block h4 { margin: 4px 0 0; font-size: 1.08em; color: #fff; }
.cd-block h1 { font-size: 1.22em; }
.cd-inline-code, .cd-block code {
  font-family: var(--cd-mono); font-size: .92em; padding: 1px 6px; border-radius: 6px; background: rgba(0,0,0,.35);
}
.cd-code {
  margin: 0; padding: 10px 12px; border-radius: 10px; background: rgba(0,0,0,.42); border: 1px solid var(--cd-line);
  font-family: var(--cd-mono); font-size: .88em; line-height: 1.4; white-space: pre-wrap; word-break: break-all;
  max-height: 320px; overflow: auto;
}
.cd-quote { border-left: 3px solid var(--cd-line); padding-left: 10px; color: var(--cd-dim); }
.cd-cursor { display: inline-block; width: .55em; height: 1em; margin-left: 2px; vertical-align: -2px; background: var(--cd-accent); animation: cd-pulse 1s infinite; }
.cd-thinking { color: var(--cd-dim); font-style: italic; display: flex; align-items: center; gap: 8px; padding-left: 16px; }

/* ---- cards ---- */
.cd-card { background: var(--cd-card); border: 1px solid var(--cd-line); border-radius: 12px; padding: 10px 12px; }
.cd-card.attn { border: 2px solid var(--cd-accent); background: linear-gradient(180deg, rgba(217,119,87,.14), rgba(217,119,87,.05)); }
.cd-card.plan { border: 2px solid var(--cd-plan); background: linear-gradient(180deg, rgba(90,169,230,.14), rgba(90,169,230,.04)); }
.cd-card-title { display: flex; align-items: center; gap: 8px; font-weight: 700; margin-bottom: 8px; }
.cd-tool { display: flex; align-items: center; gap: 10px; padding: 7px 12px; border-radius: 10px; background: var(--cd-card); border: 1px solid var(--cd-line); }
.cd-tool .cd-ico { color: var(--cd-dim); flex: 0 0 auto; }
.cd-tool .cd-label { font-weight: 700; flex: 0 0 auto; }
.cd-tool .cd-detail { color: var(--cd-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex: 1; font-family: var(--cd-mono); font-size: .88em; }
.cd-badge { flex: 0 0 auto; font-size: .78em; padding: 1px 9px; border-radius: 999px; background: var(--cd-card-2); color: var(--cd-dim); }
.cd-badge.ok { color: var(--cd-ok); } .cd-badge.err { color: var(--cd-err); } .cd-badge.warn { color: var(--cd-warn); }
.cd-output { margin-top: 6px; }
.cd-notice { display: flex; align-items: flex-start; gap: 9px; padding: 8px 12px; border-radius: 10px; background: var(--cd-card); color: var(--cd-dim); font-size: .94em; }
.cd-notice.warn { color: var(--cd-warn); background: rgba(242,199,68,.1); }
.cd-notice.error { color: var(--cd-err); background: rgba(239,107,107,.1); }
.cd-turn { text-align: center; color: var(--cd-dim); font-size: .8em; padding: 2px 0 6px; }
.cd-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.cd-row > * { flex: 1 1 0; min-width: 0; }
.cd-btn {
  display: flex !important; align-items: center; justify-content: center; gap: 8px;
  width: auto !important; min-width: 0 !important; padding: 11px 14px !important;
  font-size: 1em !important; line-height: 1.2 !important; text-align: center;
}
.cd-btn.primary { background: var(--cd-accent) !important; color: #1a0f0a !important; font-weight: 700; }
.cd-btn.danger { color: var(--cd-err) !important; }
.cd-btn.ghost { background: var(--cd-card) !important; }
.cd-opt { text-align: left !important; justify-content: flex-start !important; flex-direction: column; align-items: flex-start !important; gap: 2px !important; }
.cd-opt small { opacity: .7; font-size: .82em; }
.cd-opt.sel { background: var(--cd-accent-soft) !important; box-shadow: inset 0 0 0 2px var(--cd-accent); }
.cd-chip { display: inline-block; padding: 1px 10px; border-radius: 999px; background: var(--cd-card-2); font-size: .8em; color: var(--cd-dim); margin-bottom: 6px; }

/* ---- welcome ---- */
.cd-welcome { text-align: center; padding: 26px 8px 8px; }
.cd-welcome h2 { margin: 10px 0 4px; font-size: 1.5em; }
.cd-welcome p { margin: 0 0 18px; color: var(--cd-dim); }
.cd-sugs { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; text-align: left; }
.cd-compact .cd-sugs { grid-template-columns: 1fr; }

/* ---- composer ---- */
.cd-composer { display: flex; align-items: center; gap: 10px; }
.cd-composer .cd-field { flex: 1 1 auto; min-width: 0; }
.cd-composer .cd-field > div { padding: 0 !important; margin: 0 !important; }
.cd-round {
  display: flex !important; align-items: center; justify-content: center;
  width: 46px !important; min-width: 46px !important; height: 46px; padding: 0 !important; border-radius: 50% !important; flex: 0 0 auto;
}
.cd-round.rec { background: var(--cd-err) !important; color: #fff !important; box-shadow: 0 0 0 calc(4px + var(--lvl, 0) * 14px) rgba(239,107,107,.35); transition: box-shadow .09s linear; }
.cd-round.busy { background: var(--cd-card-2) !important; }
.cd-voice-note { display: flex; align-items: center; gap: 8px; padding: 6px 12px; margin-bottom: 8px; border-radius: 10px; background: var(--cd-card); color: var(--cd-dim); }
.cd-voice-note.err { color: var(--cd-warn); background: rgba(242,199,68,.1); }
.cd-voice-note .cd-btn { flex: 0 0 auto; padding: 6px 12px !important; }
.cd-meter { height: 6px; border-radius: 3px; background: var(--cd-card-2); overflow: hidden; flex: 1; }
.cd-meter > i { display: block; height: 100%; background: var(--cd-err); width: calc(var(--lvl, 0) * 100%); transition: width .09s linear; }

/* ---- pages ---- */
.cd-h { margin: 18px 0 8px; font-size: 1.05em; color: var(--cd-accent); font-weight: 700; }
.cd-item { display: flex; align-items: center; gap: 12px; padding: 11px 14px; border-radius: 12px; background: var(--cd-card); margin-bottom: 8px; }
.cd-item .cd-grow { flex: 1; min-width: 0; }
.cd-item .cd-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cd-item .cd-sub { color: var(--cd-dim); font-size: .85em; }
.cd-log { font-family: var(--cd-mono); font-size: .78em; color: var(--cd-dim); max-height: 140px; overflow: auto; white-space: pre-wrap; }
.cd-mem { white-space: pre-wrap; font-family: var(--cd-mono); font-size: .88em; }
.cd-warnbox { padding: 10px 12px; border-radius: 10px; background: rgba(242,199,68,.1); color: var(--cd-warn); font-size: .9em; margin: 6px 0; }
.cd-progress { height: 8px; border-radius: 4px; background: var(--cd-card-2); overflow: hidden; margin-top: 8px; }
.cd-progress > i { display: block; height: 100%; background: var(--cd-accent); }
.cd-ok { color: var(--cd-ok); } .cd-bad { color: var(--cd-err); } .cd-mutedtxt { color: var(--cd-dim); }

/* ---- QAM compact ---- */
.cd-q { padding: 0 2px; }
.cd-q .cd-status { padding: 2px 0 8px; }
.cd-clamp { display: -webkit-box; -webkit-line-clamp: 7; -webkit-box-orient: vertical; overflow: hidden; }
.cd-clamp2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.cd-compact .cd-row { flex-direction: column; }
.cd-compact .cd-card { padding: 8px 10px; }
.cd-compact .cd-asst { border-left: none; padding-left: 0; }
.cd-q .cd-mode { margin: 4px 0 8px; }
.cd-q .cd-composer { gap: 8px; }
.cd-q .cd-round { width: 40px !important; min-width: 40px !important; height: 40px; }
`;
