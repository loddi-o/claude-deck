/* Scripted backend states for the visual harness. Event shapes mirror the real backend. */

type Ev = [number, string, any];

const makeSettings = (lang: string) => ({
  mode: "plan", model: "", effort: "", resume_on_open: true, cwd: "", extra_dirs: [],
  ui_language: lang, ui_language_resolved: lang === "auto" ? "en" : lang, voice_language: "auto",
  voice_model: "small-q5_1", voice_silence_ms: 1400,
  voice_autosend: false, notifications: true, text_scale: 1, last_session_id: "",
});
let settings = makeSettings("it");

const status = (over: any = {}) => ({
  status: "idle", running: true, mode: "plan", effective_mode: "plan", auto_unavailable: false,
  session_id: "2d5c8788-901d-4d76-b2cf-1e9537918011", model: "claude-sonnet-5-5", cwd: "/home/deck", pending: 0,
  rate: { status: "allowed", five_hour: 0.25, seven_day: 0.16 }, last_result: {}, ...over,
});

const setupOk = {
  claude: { found: true, path: "/home/deck/.local/bin/claude", version: "2.1.318" },
  auth: { logged_in: true, email: "utente@example.com", method: "claude.ai" },
  system: { pretty: "SteamOS", family: "steamos", device: "Valve Jupiter" },
  sudo: { has_password: true },
  mic: { sources: [{ name: "alsa_input.pci-0000_04_00.5-platform-acp5x_mach.0.HiFi__hw_acp5x_1__source", state: "RUNNING" }], default: "alsa_input.pci-0000_04_00.5-platform-acp5x_mach.0.HiFi__hw_acp5x_1__source", has_mic: true },
  voice: {
    binary: true, selected: "small-q5_1", selected_installed: false,
    models: [
      { name: "base-q5_1", file: "a", size: 59707625, installed: false, downloading: false },
      { name: "small-q5_1", file: "b", size: 190085487, installed: false, downloading: false },
      { name: "small", file: "c", size: 487601967, installed: false, downloading: false },
    ],
  },
};

const user = (text: string) => ["msg", { type: "user", local: true, message: { role: "user", content: [{ type: "text", text }] } }];
const asst = (id: string, text: string) => ["msg", { type: "assistant", message: { id, role: "assistant", content: [{ type: "text", text }] } }];
const tool = (id: string, name: string, input: any) => ["msg", { type: "assistant", message: { id: "m" + id, role: "assistant", content: [{ type: "tool_use", id, name, input }] } }];
const result = (id: string, content: string, is_error = false) => ["msg", { type: "user", message: { role: "user", content: [{ type: "tool_result", tool_use_id: id, content, is_error }] } }];
const turn = (ok = true) => ["msg", { type: "result", is_error: !ok, subtype: ok ? "success" : "error_during_execution", stats: { duration_ms: 18400, num_turns: 3 } }];

const ANSWER = `Ho controllato i log di RPCS3 e il problema è chiaro:

## Cosa ho trovato
- Il **firmware PS3** non è installato (\`PS3UPDAT.PUP\` mancante)
- Il percorso dei giochi è ancora quello vecchio su \`/run/media/mmcblk0p1\`
- La cache degli shader è corrotta (**1.2 GB**)

Il comando che usa EmuDeck per lanciarlo:

\`\`\`bash
flatpak run net.rpcs3.RPCS3 --no-gui "/home/deck/Emulation/roms/ps3/God of War III.ps3"
\`\`\`

1. Scarico il firmware dal sito ufficiale
2. Lo installo da *File → Install Firmware*
3. Svuoto la cache shader

> Nessuna modifica fatta finora: dimmi se vuoi che proceda.`;

const PLAN = `# Piano: sistemare i giochi PS3

## Passi
1. Fare un backup di \`~/.config/rpcs3\` in \`~/.config/rpcs3.bak-20261105\`
2. Scaricare il firmware ufficiale **PS3UPDAT.PUP** (~200 MB)
3. Installarlo con \`rpcs3 --installfw\`
4. Svuotare la cache shader in \`~/.cache/rpcs3/shaders_cache\`
5. Aggiornare i percorsi in \`games.yml\`

## Verifica
- Avviare un gioco di prova e controllare \`RPCS3.log\``;

function base(events: [string, any][], over: any = {}, setupOver: any = null): any {
  const evs: Ev[] = events.map(([k, p], i) => [i + 1, k, p]);
  return {
    state: {
      version: "0.1.0", status: status(over), events: evs, seq: evs.length, settings,
      voice: { state: "idle", downloading: "" }, sudo: { has_password: true },
    },
    setup: setupOver ?? setupOk,
  };
}

export function scenario(name: string, lang = "it"): { state: any; setup: any; live?: [string, any, number?][] } {
  settings = makeSettings(lang);
  switch (name) {
    case "empty":
      return base([], { running: false });
    case "chat":
      return base([
        user("perche i miei giochi per ps3 non partono"),
        tool("t1", "Bash", { command: "ls -la ~/.config/rpcs3 && tail -n 40 ~/.cache/rpcs3/RPCS3.log", description: "Controllo config e log di RPCS3" }),
        result("t1", "total 24\ndrwxr-xr-x 5 deck deck 4096 nov  4 22:12 .\n-rw-r--r-- 1 deck deck  812 nov  4 22:12 config.yml\n…"),
        tool("t2", "mcp__claude_deck__remember", { note: "RPCS3 ha il firmware mancante" }),
        result("t2", "Salvato in memoria"),
        tool("t3", "Read", { file_path: "/home/deck/.config/rpcs3/games.yml" }),
        result("t3", "BLES01807: /run/media/mmcblk0p1/roms/ps3/…"),
        asst("a1", ANSWER),
        turn(),
        user("sì procedi ma prima fai un backup"),
      ], { status: "working" });
    case "perm":
      return base([
        user("pulisci la cache degli shader di rpcs3"),
        asst("a1", "Svuoto la cache degli shader. Prima controllo quanto pesa."),
        tool("t1", "Bash", { command: "rm -rf ~/.cache/rpcs3/shaders_cache/*", description: "Svuota la cache shader di RPCS3" }),
        ["perm", { request_id: "r1", kind: "tool", tool_name: "Bash", tool_use_id: "t1", input: { command: "rm -rf ~/.cache/rpcs3/shaders_cache/*", description: "Svuota la cache shader di RPCS3" }, description: "Svuota la cache shader di RPCS3", can_always: true }],
      ], { status: "waiting", pending: 1 });
    case "edit":
      return base([
        user("disabilita il wake on lan"),
        tool("t1", "Edit", { file_path: "/etc/systemd/network/20-wired.network", old_string: "WakeOnLan=magic", new_string: "WakeOnLan=off" }),
        ["perm", { request_id: "r1", kind: "tool", tool_name: "Edit", tool_use_id: "t1", input: { file_path: "/etc/systemd/network/20-wired.network", old_string: "WakeOnLan=magic", new_string: "WakeOnLan=off" }, blocked_path: "/etc/systemd/network/20-wired.network", can_always: false }],
      ], { status: "waiting", pending: 1 });
    case "plan":
      return base([
        user("sistema i giochi ps3"),
        asst("a1", "Ho finito l'analisi, ecco il piano."),
        tool("t9", "ExitPlanMode", { plan: PLAN }),
        ["perm", { request_id: "r1", kind: "plan", tool_name: "ExitPlanMode", tool_use_id: "t9", input: { plan: PLAN }, can_always: false }],
      ], { status: "waiting", pending: 1 });
    case "question":
      return base([
        user("installa un emulatore"),
        tool("t9", "AskUserQuestion", {}),
        ["perm", { request_id: "r1", kind: "question", tool_name: "AskUserQuestion", tool_use_id: "t9", can_always: false, input: { questions: [{ question: "Quale emulatore vuoi installare?", header: "Emulatore", multiSelect: false, options: [{ label: "RetroArch", description: "Multi-sistema, via Flatpak" }, { label: "PCSX2", description: "PlayStation 2" }, { label: "Dolphin", description: "GameCube e Wii" }] }] } }],
      ], { status: "waiting", pending: 1 });
    case "streaming":
      return {
        ...base([user("spiegami cosa fa Decky Loader")], { status: "working" }),
        live: [
          ["stream", { e: "ms", mid: "m1" }, 20],
          ["stream", { e: "bs", i: 0, k: "thinking" }, 20],
          ["stream", { e: "be", i: 0 }, 20],
          ["stream", { e: "bs", i: 1, k: "text" }, 20],
          ["stream", { e: "d", i: 1, k: "text", s: "Decky Loader è un **plugin loader** per la Steam Deck.\n\n- aggiunge plugin al menu rapido\n- " }, 20],
          ["stream", { e: "d", i: 1, k: "text", s: "gira come servizio systemd" }, 20],
        ],
      };
    case "streaming-tool":
      return {
        ...base([user("controlla il disco")], { status: "working" }),
        live: [
          ["stream", { e: "ms", mid: "m1" }, 10],
          ["stream", { e: "bs", i: 0, k: "text" }, 10],
          ["stream", { e: "d", i: 0, k: "text", s: "Controllo lo spazio." }, 10],
          ["msg", { type: "assistant", message: { id: "m1", role: "assistant", content: [{ type: "text", text: "Controllo lo spazio." }] } }, 10],
          ["msg", { type: "assistant", message: { id: "m1", role: "assistant", content: [{ type: "tool_use", id: "tq", name: "Bash", input: { command: "df -h /home" } }] } }, 10],
        ],
      };
    case "notices":
      return base([
        user("ciao"),
        ["notice", { code: "auto_fallback", level: "warn" }],
        ["notice", { code: "process_exited", level: "error", rc: 3, detail: "Error: connection reset\nretrying failed" }],
        ["notice", { code: "claude_missing", level: "error" }],
        turn(false),
      ]);
    case "setup-missing":
      return base([], { running: false }, {
        ...setupOk,
        claude: { found: false, path: "", version: "" },
        auth: { logged_in: null, email: "", method: "" },
        mic: { sources: [], default: "", has_mic: false },
        sudo: { has_password: false },
        voice: { ...setupOk.voice, binary: false },
      });
    default:
      return base([]);
  }
}
