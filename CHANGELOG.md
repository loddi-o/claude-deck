# Changelog

## 0.1.2 – 2026-11-05
- **Corretto il download del modello vocale dentro Decky.** Il Python incorporato in Decky non trovava l'archivio dei certificati e il download falliva con `CERTIFICATE_VERIFY_FAILED`. Ora il plugin usa il bundle di certificati del sistema (SteamOS, Fedora/Bazzite, Debian) e, se non basta, ripiega su `curl`. `clean_env` scarta inoltre le variabili `SSL_CERT_*` che puntano a file inesistenti o alla cartella temporanea di PyInstaller.
- Dopo un download fallito o annullato la pagina Impostazioni mostra l'errore e un pulsante **Riprova** (prima restava su «Scarico… 0%»).
- README dettagliato in inglese e italiano con screenshot, demo e istruzioni; `THIRD_PARTY_NOTICES.md`.
- Test: TLS e ripiego su curl (reali, con Python privo di certificati), `clean_env`, schermata di errore di download.

## 0.1.1 – 2026-11-05
- **Impostazioni sempre in evidenza**: pulsante «Impostazioni» in cima al pannello del QAM (con il numero di cose ancora da configurare) e ingranaggio nella barra del titolo del plugin.
- **Lingua**: interfaccia in italiano e inglese. Di default segue la lingua di Steam (`LocalizationManager` / parametro `LANGUAGE`, poi `navigator.language`); se non è supportata, inglese. Si cambia da *Impostazioni ▸ Lingua / Language* (in cima alla pagina).
- Claude risponde nella lingua scelta quando il tuo testo non indica altro; i testi rivolti al modello (memoria, rifiuti, ecc.) sono ora in inglese.
- **Aggiornamenti**: la password sudo salvata non viene più cancellata quando reinstalli il plugin (Decky esegue la disinstallazione a ogni aggiornamento). Per rimuoverla usa *Rimuovi password* prima di disinstallare. Nota: l'aggiornamento 0.1.0 → 0.1.1 esegue ancora la disinstallazione della 0.1.0, quindi la password va reinserita una volta.
- Test: rilevamento lingua, `setupIssues`, prompt con lingua di risposta, `_uninstall`.

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
