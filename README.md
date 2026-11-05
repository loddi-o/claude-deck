# Claude Deck

**Claude Code nel Quick Access Menu di SteamOS / Bazzite** — un plugin [Decky Loader](https://decky.xyz) per diagnosticare, riparare, configurare e installare cose sul tuo dispositivo parlando (o scrivendo) con Claude, tutto con il gamepad.

> English summary at the [bottom](#english).

## Cosa fa

- **Agente vero**: lancia il tuo Claude Code locale (`claude`) in modalità agentica. Può leggere i file di sistema, eseguire comandi, modificare file e installare pacchetti, con la tua approvazione.
- **Controller-first**: QAM compatto per l'uso rapido + pagina a **schermo intero** (Chat · Conversazioni · Memoria · Impostazioni). Ogni cosa si raggiunge con D-pad / A / B / X / Y / L1 / R1. Funziona anche con tastiera fisica.
- **Piano e Auto**
  - **Piano**: Claude indaga in sola lettura e ti propone un piano; lo approvi (o lo fai correggere) con un tocco.
  - **Auto**: Claude esegue in autonomia (è la modalità `auto` di Claude Code, che blocca le azioni rischiose). Le richieste che restano compaiono come card **Consenti / Consenti per la sessione / Nega / Nega con motivo**.
- **Dettatura vocale** (solo voce → testo): tocca il microfono, parla, e il testo compare nel campo messaggio. Riconoscimento **offline** con whisper.cpp, fine frase automatica, nessun audio lascia il dispositivo.
- **Memoria**: riprende l'ultima conversazione all'apertura, elenco delle conversazioni passate e una **memoria persistente** (`memory.md`) che Claude legge a ogni nuova conversazione e aggiorna da solo (fix applicati, pacchetti installati, particolarità dell'hardware).
- **Consapevole del sistema**: il prompt di sistema cambia per SteamOS (rootfs read-only, Flatpak, distrobox, `steamos-readonly`) e per Bazzite (`ujust`, `rpm-ostree`, Homebrew).
- **Italiano e inglese**: l'interfaccia segue la lingua di Steam (inglese se non supportata) e si cambia da *Impostazioni ▸ Lingua / Language*.
- **Domande a scelta multipla** (`AskUserQuestion`) come pulsanti: niente digitazione per le scelte.

## Installazione

1. Serve [Decky Loader](https://decky.xyz) e **Claude Code** già installato e collegato al tuo account (dalla pagina *Impostazioni → Configurazione* del plugin puoi anche installarlo / accedere).
2. Scarica `claude-deck-v0.1.1.zip` sul dispositivo.
3. In Game Mode: **Decky ▸ ⚙ Impostazioni ▸ Generale ▸ Modalità sviluppatore** (attivala), poi **Sviluppatore ▸ Installa plugin da ZIP** e scegli il file.
   In alternativa, in Desktop Mode: `scripts/dev-install.sh` (richiede sudo).
4. Apri il QAM (**⋯**) ▸ **Claude Deck**. Le **Impostazioni** sono il pulsante in cima al pannello (oppure l'ingranaggio accanto al titolo).

### Primo avvio

Premi **Impostazioni** (in cima al pannello: il badge ⚠ indica quante cose mancano) e controlla la checklist:

| Voce | Cosa fare |
|---|---|
| Claude Code / Account | Se mancano, usa i pulsanti *Installa* / *Accedi*. |
| Password sudo | Su SteamOS l'utente `deck` non ha password: imposta prima `passwd` da Konsole, poi inseriscila qui (tastiera a schermo). Senza, Claude lavora solo in user-space. |
| Motore vocale / Modello vocale | Premi *Scarica* (modello `small`, ~190 MB, una volta sola). `base` (~60 MB) è più veloce su hardware lento. |
| Microfono | Il Deck ha quello integrato; altri dispositivi: collega un microfono USB/Bluetooth. |

## Uso con il gamepad

I suggerimenti dei pulsanti in basso (barra di Steam) mostrano sempre il tasto giusto per ciò che hai selezionato.

| Azione | Come |
|---|---|
| Muoversi tra messaggi, card e pulsanti | D-pad ↑ ↓ ← → |
| Selezionare / espandere l'output di uno strumento | **A** |
| Indietro / chiudere lo schermo intero | **B** |
| Dettare (sul campo messaggio) · «Consenti per la sessione» (su una richiesta) | **X** |
| Alternare Piano ⇄ Auto (sul campo messaggio) · «Nega con motivo» (su una richiesta) | **Y** / Opzioni |
| Cambiare scheda nello schermo intero | **L1 / R1** |
| Scorrere testi lunghi | D-pad (blocco per blocco) o stick destro / trackpad |

**Tastiera fisica**: `Invio` invia · `Ctrl+M` Piano/Auto · `Ctrl+N` nuova conversazione · `Ctrl+D` detta · `Ctrl+Tab` cambia scheda · `Esc` annulla dettatura · `PgSu/PgGiù/Fine` scorrono la chat.

## Sicurezza — leggi questo

Claude Deck dà a un agente AI la possibilità di **eseguire comandi sul tuo dispositivo**. Questo è il suo scopo, ma:

- In **Piano** non viene modificato nulla finché non approvi. In **Auto** Claude agisce da solo: usalo quando ti fidi del compito.
- La **password sudo**, se la salvi, resta in chiaro in un file `chmod 600` nella cartella dati del plugin (`~/homebrew/settings/claude-deck/sudo.pw`). Claude può usarla — e leggerla — quindi equivale a dargli **accesso root**. Resta salvata anche quando aggiorni il plugin; per toglierla usa *Rimuovi password* nelle Impostazioni **prima di disinstallare** (altrimenti il file resta in quella cartella).
- Il prompt di sistema chiede a Claude di fare backup prima di toccare file di sistema, di non cancellare salvataggi/prefix Proton senza conferma e di avvisare prima di riavviare Decky/Steam (che chiude la sua stessa interfaccia). Sono istruzioni, non garanzie: tieni dei backup.
- Il testo che scrivi e l'output dei comandi vengono inviati ad Anthropic tramite Claude Code, come in qualsiasi sessione di Claude Code. L'audio della dettatura invece **resta sul dispositivo**.
- Le modifiche al rootfs di SteamOS (`pacman`, `/usr`) vengono perse a ogni aggiornamento di SteamOS: Claude è istruito a preferire Flatpak, distrobox e `~/.local`.

## Dove sono i dati

| Cosa | Dove |
|---|---|
| Impostazioni, memoria, password sudo | `~/homebrew/settings/claude-deck/` |
| Modelli vocali | `~/homebrew/data/claude-deck/models/` |
| Log del plugin | `~/homebrew/logs/claude-deck/` |
| Conversazioni | `~/.claude/projects/` (quelle di Claude Code stesso) |

## Compilare dai sorgenti

```bash
scripts/setup-node.sh        # Node 22 + pnpm 9 in ~/.cache (nessun sudo)
scripts/build.sh             # typecheck + test + bundle
scripts/build-whisper.sh     # whisper.cpp statico (AVX2) -> bin/whisper-cli  (serve gcc, cmake, git)
scripts/package.sh           # -> ../claude-deck-v0.1.1.zip
scripts/ui-shots.sh          # screenshot della GUI con Decky simulato (Chrome headless)
python3 scripts/e2e_real_claude.py   # prova end-to-end contro il vero `claude` (pochi token)
```

Requisiti di sviluppo: Python ≥ 3.10 (il backend usa solo la libreria standard), Node ≥ 20.

## Struttura

```
main.py                    backend Decky (API verso la UI)
py_modules/claude_deck/    session (processo claude), protocol, voice, memory(+mcp), sudo, prompts, …
src/                       frontend React (store, reducer, componenti, pagine)
bin/                       sudo (wrapper), askpass, whisper-cli
defaults/                  prompt di sistema e seed della memoria
tests/                     backend (unittest), frontend (vitest), harness visivo
docs/ARCHITECTURE.md       come funziona
```

## Risoluzione problemi

- **«Claude Code non è installato»** — apri Impostazioni e usa *Installa*, oppure installalo da Konsole (`curl -fsSL https://claude.ai/install.sh | bash`).
- **Auto non disponibile** — dipende dal tuo piano/account; il plugin passa a «Accetta modifiche» e te lo segnala (`Auto*`).
- **Microfono: «nessun audio»** — controlla che il dispositivo di ingresso predefinito sia quello giusto (`pactl list short sources`) e che non sia silenziato.
- **La conversazione si è interrotta dopo un riavvio di Decky/Steam** — è normale se Claude ha riavviato il servizio: scrivi un messaggio e riprende da dove era.
- Log: `~/homebrew/logs/claude-deck/plugin.log`.

## Licenza

MIT — vedi [LICENSE](LICENSE). Claude è un marchio di Anthropic; questo progetto non è affiliato né approvato da Anthropic o Valve.

---

## English

**Claude Deck** is a [Decky Loader](https://decky.xyz) plugin that runs your local **Claude Code** agent from the Steam Deck Quick Access Menu (SteamOS / Bazzite) to troubleshoot, fix, configure and install things on your device — fully usable with a gamepad.

- **Agent mode** with access to system files and commands, gated by on-screen **Allow / Allow for session / Deny / Deny with reason** cards.
- **Plan** and **Auto** modes (Auto = Claude Code's `auto` permission mode).
- **Controller-first UI**: compact QAM panel + full-screen page (Chat · Conversations · Memory · Settings), L1/R1 to switch tabs, keyboard shortcuts for physical keyboards.
- **Offline voice dictation** (speech → text only) with whisper.cpp; audio never leaves the device.
- **Memory**: resumes the last conversation and keeps a persistent `memory.md` the agent reads and updates.
- **Distro-aware** system prompt (SteamOS read-only rootfs, Bazzite/ostree).

**Languages**: Italian and English. The UI follows Steam's language (English if it isn't supported); change it in *Settings ▸ Lingua / Language*.

**Install**: download the ZIP → Decky ▸ Settings ▸ General ▸ enable *Developer mode* → Developer ▸ *Install plugin from ZIP*. Then open *Settings* inside the plugin and follow the checklist (Claude login, sudo password, voice model).

**Security**: this plugin lets an AI agent run commands on your device. The optional sudo password is stored in a `chmod 600` file (kept across plugin updates; remove it in Settings before uninstalling) and is effectively root access for the agent. Audio stays local; text and command output go to Anthropic via Claude Code as usual.

Build from source: `scripts/build.sh`, `scripts/build-whisper.sh`, `scripts/package.sh`. MIT licensed.
