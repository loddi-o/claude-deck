# Architettura

```
┌─────────────── Steam UI (CEF) ───────────────┐        ┌──────────── Decky plugin process (user "deck") ────────────┐
│ React: QuickPanel (QAM) · FullScreen (route) │        │ main.py  Plugin                                            │
│ store.ts  ◄── event "cd" (seq, kind, payload)│◄───────│ Hub ── ring buffer ◄─ ClaudeSession ◄─ stdout JSONL        │
│ reducer.ts (pure)                            │        │   │                      │  ▲                          │
│ api.ts ── callable("send_message", …) ───────┼───────►│   ├ VoiceEngine ─ parecord → VAD → whisper-cli          │
└──────────────────────────────────────────────┘        │   ├ Memory ─ memory.md ◄─ memory_mcp.py (MCP, stdio)    │
                                                        │   └ Sudo ─ sudo.pw (0600) ◄─ bin/askpass ◄─ bin/sudo    │
                                                        │                       ▼ stdin JSONL                         │
                                                        │            claude --input-format stream-json …             │
                                                        └──────────────────────────────────────────────────────────────┘
```

## Backend (`py_modules/claude_deck`, solo libreria standard)

| Modulo | Ruolo |
|---|---|
| `session.py` | Avvia `claude` come sottoprocesso persistente (nuovo gruppo di processi) e traduce il protocollo `stream-json`. Spawn pigro al primo messaggio, `--resume` quando esiste una conversazione, riavvio dopo crash, fallback `auto` → `acceptEdits`. |
| `protocol.py` | Forme dei messaggi: `user`, `control_request`/`control_response` (`can_use_tool`, `interrupt`, `set_permission_mode`, `set_model`). Allineato a claude-agent-sdk e verificato col CLI reale (2.1.x). |
| `hub.py` | Numera gli eventi (`seq`), tiene un ring buffer degli eventi persistenti per risincronizzare la UI e li inoltra con `decky.emit("cd", seq, kind, payload)`. |
| `voice.py` | Registrazione (`parecord --raw` → `pw-record --raw` → `arecord`), rilevamento fine frase a energia, `whisper-cli`, download dei modelli con progresso. |
| `memory.py` / `memory_mcp.py` | `memory.md` + server MCP stdio (`remember`, `recall`, `forget`) esposto a Claude via `--mcp-config`. |
| `sudo.py` + `bin/` | `bin/sudo` (primo nel `PATH`) chiama `sudo -A`; `bin/askpass` stampa la password dal file 0600. |
| `prompts.py` + `defaults/system_prompt.md` | Prompt di sistema: macchina (dispositivo, OS, disco, Game/Desktop Mode), regole per SteamOS/Bazzite, memoria. |
| `sessions_index.py` | Elenco/ripristino delle conversazioni dai transcript di Claude Code (`~/.claude/projects/<cwd>/*.jsonl`). |
| `setup_check.py` | Checklist (claude, login, mic, whisper, sudo), installer e login guidato di Claude Code. |
| `util.py` | `clean_env()` (Decky è un binario PyInstaller: ripristina `LD_LIBRARY_PATH` per i figli), `agent_env()`, `shrink()` (eventi piccoli sul websocket). |

### Comando di `claude`

```
claude --output-format stream-json --input-format stream-json --verbose --include-partial-messages
       --permission-prompt-tool stdio --permission-mode plan|auto
       (--resume <id> | --session-id <uuid>) [--model …] [--effort …]
       --append-system-prompt <prompt> --mcp-config {claude_deck: memory_mcp.py}
       --allowedTools mcp__claude_deck__* Bash(journalctl *) …  --add-dir /etc /var /usr /opt /run /boot /sys /proc
```

- `--permission-prompt-tool stdio`: ogni richiesta di permesso arriva come `control_request` e viene mostrata come card; la risposta è un `control_response` (`allow` + `updatedInput` [+ `updatedPermissions`] o `deny` + `message`).
- «Consenti per la sessione» riusa i `permission_suggestions` del CLI **forzando `destination: "session"`** (di default puntano a `localSettings`, cioè persistenti).
- `ExitPlanMode` → card del piano; «Approva» risponde `allow` con `updatedPermissions: [setMode auto]`. `AskUserQuestion` → pulsanti; la risposta è `updatedInput.answers`.
- Gli strumenti di memoria vengono approvati dal backend senza card.

### Eventi verso la UI (`decky.emit("cd", seq, kind, payload)`)

| kind | Persistente | Contenuto |
|---|---|---|
| `msg` | sì | `assistant` / `user` (tool_result) / `result`, ripuliti e ridotti |
| `history` | sì | eventi ricostruiti da un transcript dopo «riprendi» |
| `perm`, `perm_done` | sì | richiesta di permesso / piano / domanda e suo esito |
| `notice` | sì | avvisi (`auto_fallback`, `process_exited`, …) |
| `reset` | sì | nuova conversazione |
| `stream` | no | delta di testo (coalescenti ogni ~60 ms) |
| `status`, `voice`, `voice_download`, `setup_log`, `login`, `sys` | no | stato istantaneo |

All'avvio la UI si sottoscrive, chiama `get_state()` (snapshot + `seq`) e ignora gli eventi con `seq` già visto: lo stato sopravvive alla chiusura del QAM.

## Frontend (`src/`)

- `store.ts`: store a livello di modulo (`useSyncExternalStore`), azioni, toast quando la UI non è visibile.
- `reducer.ts`: funzione pura eventi → elementi di chat (streaming sostituito dal blocco finale, ciclo di vita degli strumenti, history).
- `components/`: `Chat`, `Cards` (strumenti, permessi, piano, domande), `Composer` (+ microfono), `Markdown` (parser senza dipendenze, ogni blocco è un bersaglio di focus), `ui` (modali, interruttore modalità).
- `pages/`: `QuickPanel` (QAM), `FullScreen` (+ tab `Sessions`, `Memory`, `Settings`).
- Navigazione: `Focusable` + `onSecondaryButton`/`onOptionsButton`/`onButtonDown` di `@decky/ui`; i suggerimenti dei tasti sono quelli di Steam (`on*ActionDescription`).

## Test

| Cosa | Come |
|---|---|
| Backend | `tests/backend` — `unittest`, modulo `decky` finto e un `claude` finto (`fake_claude.py`) che riproduce le forme dei messaggi catturate dal CLI reale |
| Reducer / markdown / strumenti | `tests/frontend` — vitest |
| GUI | `scripts/ui-shots.sh` — componenti reali con `@decky/ui` simulato (`tests/ui-harness`) + Chrome headless |
| End-to-end | `scripts/e2e_real_claude.py` — backend contro il vero `claude` (conversazione, memoria MCP, nuova sessione, riprendi, cambio modalità) |
