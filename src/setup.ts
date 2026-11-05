/** Pure helpers about the setup checklist (kept free of Steam imports so they can be unit-tested). */
import type { SetupInfo } from "./types";

/**
 * How many essential things are still missing: Claude Code, its login, the speech engine / model.
 * The sudo password is optional (the user may choose to work without root) so it never counts.
 */
export function setupIssues(setup: SetupInfo | null): number {
  if (!setup) return 0;
  let n = 0;
  if (!setup.claude.found) n++;
  else if (setup.auth.logged_in === false) n++;
  if (!setup.voice.binary) n++;
  else if (!setup.voice.selected_installed) n++;
  return n;
}
