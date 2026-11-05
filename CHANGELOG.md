# Changelog

## 0.1.0 – 2026-11-05
Prima versione.

- Claude Code agentico dal Quick Access Menu (sottoprocesso `claude` con protocollo `stream-json`).
- QAM compatto + pagina a schermo intero (Chat · Conversazioni · Memoria · Impostazioni), pensata per il gamepad; tastiera fisica supportata.
- Modalità **Piano** e **Auto**; richieste di permesso, piano e domande come card con pulsanti (Consenti / Consenti per la sessione / Nega / Nega con motivo).
- Dettatura vocale offline (whisper.cpp) con fine-frase automatica; il testo finisce nel campo messaggio.
- Memoria: ripresa delle conversazioni + memoria persistente (`memory.md`, strumenti MCP `remember`/`recall`/`forget`).
- `sudo` non interattivo tramite wrapper + askpass (password salvata in file 0600, scelta dell'utente).
- Prompt di sistema su misura per SteamOS / Bazzite (rootfs read-only, Flatpak, distrobox, ujust…).
- Interfaccia in italiano e inglese.
