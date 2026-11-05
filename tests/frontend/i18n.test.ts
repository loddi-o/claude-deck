import { describe, expect, it } from "vitest";
import {
  currentLanguage,
  detectSystemLanguage,
  languageFromValue,
  resolveLanguage,
  setLanguage,
  t,
} from "../../src/i18n";
import { setupIssues } from "../../src/setup";
import type { SetupInfo } from "../../src/types";

const src = (v: string | undefined | null) => () => v;

describe("languageFromValue", () => {
  it("understands Steam language names and BCP-47 tags", () => {
    expect(languageFromValue("italian")).toBe("it");
    expect(languageFromValue("english")).toBe("en");
    expect(languageFromValue("it-IT")).toBe("it");
    expect(languageFromValue("it_IT")).toBe("it");
    expect(languageFromValue("EN-us")).toBe("en");
    expect(languageFromValue(" it ")).toBe("it");
  });
  it("returns undefined for anything we don't translate", () => {
    for (const v of ["german", "brazilian", "schinese", "latam", "de-DE", "pt-BR", "", null, undefined]) {
      expect(languageFromValue(v as any)).toBeUndefined();
    }
  });
});

describe("detectSystemLanguage", () => {
  it("reads the Steam language", () => {
    expect(detectSystemLanguage([src("italian")])).toBe("it");
    expect(detectSystemLanguage([src("english")])).toBe("en");
  });
  it("falls back to English for an unsupported language", () => {
    expect(detectSystemLanguage([src("german")])).toBe("en");
    expect(detectSystemLanguage([src("brazilian")])).toBe("en");
  });
  it("the FIRST source that answers decides, even if a later one is Italian", () => {
    expect(detectSystemLanguage([src("german"), src("italian"), src("it-IT")])).toBe("en");
    expect(detectSystemLanguage([src("italian"), src("english")])).toBe("it");
  });
  it("skips sources that are empty or throw", () => {
    const boom = () => {
      throw new ReferenceError("window is not defined");
    };
    expect(detectSystemLanguage([boom, src(undefined), src(""), src("it-IT")])).toBe("it");
    expect(detectSystemLanguage([boom, src(null)])).toBe("en");
    expect(detectSystemLanguage([])).toBe("en");
  });
});

describe("resolveLanguage / setLanguage / t", () => {
  it("explicit picks win over the system", () => {
    expect(resolveLanguage("it")).toBe("it");
    expect(resolveLanguage("en")).toBe("en");
    expect(resolveLanguage("de" as any)).toBe("en");
  });
  it("switches the strings", () => {
    setLanguage("it");
    expect(currentLanguage()).toBe("it");
    expect(t("tabSettings")).toBe("Impostazioni");
    expect(t("downloading", { pct: 42 })).toBe("Scarico… 42%");
    setLanguage("en");
    expect(currentLanguage()).toBe("en");
    expect(t("tabSettings")).toBe("Settings");
    expect(t("downloading", { pct: 42 })).toBe("Downloading… 42%");
    expect(t("setupPending", { n: 2 })).toBe("2 to set up");
  });
  it("the language label is bilingual so it can be found from either language", () => {
    for (const l of ["it", "en"] as const) {
      setLanguage(l);
      expect(t("language")).toContain("Lingua");
      expect(t("language")).toContain("Language");
    }
  });
});

const setup = (over: Partial<{ found: boolean; logged: boolean | null; binary: boolean; model: boolean }> = {}): SetupInfo => {
  const o = { found: true, logged: true, binary: true, model: true, ...over };
  return {
    claude: { found: o.found, path: "", version: "" },
    auth: { logged_in: o.logged, email: "", method: "" },
    system: { pretty: "", family: "", device: "" },
    sudo: { has_password: false },
    mic: { sources: [], default: "", has_mic: false },
    voice: { binary: o.binary, models: [], selected: "small-q5_1", selected_installed: o.model },
  };
};

describe("setupIssues", () => {
  it("counts only essentials (not sudo, not the microphone)", () => {
    expect(setupIssues(null)).toBe(0);
    expect(setupIssues(setup())).toBe(0);
    expect(setupIssues(setup({ model: false }))).toBe(1);
    expect(setupIssues(setup({ logged: false }))).toBe(1);
    expect(setupIssues(setup({ found: false, logged: null, binary: false, model: false }))).toBe(2);
    expect(setupIssues(setup({ logged: false, model: false }))).toBe(2);
  });
});
