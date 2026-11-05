// Bundles the visual harness: real plugin components + mocked Decky modules.
// usage: node tests/ui-harness/build.mjs OUT_DIR
import { build } from "esbuild";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const here = new URL(".", import.meta.url).pathname;
const out = resolve(process.argv[2] || "/tmp/cd-harness");
mkdirSync(out, { recursive: true });

await build({
  entryPoints: [resolve(here, "main.tsx")],
  bundle: true,
  outfile: resolve(out, "harness.js"),
  format: "iife",
  jsx: "automatic",
  alias: {
    "@decky/ui": resolve(here, "mock-ui.tsx"),
    "@decky/api": resolve(here, "mock-api.ts"),
  },
  define: { "process.env.NODE_ENV": '"development"' },
  logLevel: "warning",
});

writeFileSync(
  resolve(out, "index.html"),
  `<!doctype html><html><head><meta charset="utf-8"><title>harness</title>
<style>
  html,body{margin:0;height:100%;background:#0e1014;color:#e8eaed;font-family:"Motiva Sans",system-ui,sans-serif}
  body.qam{width:308px;background:#1c1f26;padding:8px 10px;overflow:auto}
  body.full{position:relative;overflow:hidden}
  body.full::before{content:"Steam";position:absolute;top:0;left:0;right:0;height:40px;background:#0b0d11;color:#6b7480;padding:10px 16px;box-sizing:border-box;font-size:13px}
  #root{height:100%}
  .DialogButton{background:#3d4450;color:#dfe3e8;border:0;border-radius:4px;padding:10px 16px;font:inherit;cursor:pointer;width:100%;box-sizing:border-box}
  .DialogButton:disabled{opacity:.4}
  .mock-input{width:100%;box-sizing:border-box;height:44px;border-radius:4px;border:0;background:#2b303a;color:#fff;padding:0 12px;font:inherit}
  .mock-section{margin:0 0 12px}.mock-section-title{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#8b929a;padding:6px 0}
  .mock-row{padding:3px 0}.mock-buttonitem{text-align:center}
  .mock-field{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 14px;background:rgba(255,255,255,.05);border-radius:10px;margin-bottom:8px}
  .mock-title{font-weight:700}
</style></head><body><div id="root"></div><script src="harness.js"></script></body></html>`
);
console.log("harness built in", out);
