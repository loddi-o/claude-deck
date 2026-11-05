// Must be imported first: i18n reads Steam's language when it is first evaluated.
const q = new URLSearchParams(location.search);
const steam = q.get("steam"); // e.g. ?steam=italian | german
if (steam) {
  (window as any).LocalizationManager = { GetPreferredLocales: () => [steam], m_rgLocalesToUse: [steam] };
}
export {};
