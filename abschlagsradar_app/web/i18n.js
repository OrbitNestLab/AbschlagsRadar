/* Phrase catalogs translate static UI text, never interpolated contract data.
 * Home Assistant's per-user language takes priority over the browser language.
 * Unsupported languages use English UI text and the user's regional formats.
 */
const RadarI18n = (() => {
  let language = "de",
    locale = "de-DE",
    catalog = {},
    matcher;
  function preferredLanguage(hass) {
    if (hass?.locale?.language || hass?.language)
      return hass.locale?.language || hass.language;
    try {
      let frame = window;
      for (let depth = 0; depth < 4 && frame.parent !== frame; depth++) {
        frame = frame.parent;
        const parentHass = frame.document.querySelector("home-assistant")?.hass;
        if (parentHass?.locale?.language || parentHass?.language)
          return parentHass.locale?.language || parentHass.language;
      }
    } catch {
      // Cross-origin embeddings cannot read the HA parent; use the browser.
    }
    return typeof navigator === "undefined"
      ? "de-DE"
      : navigator.language || "en";
  }
  function setLocale(value) {
    let regional;
    try {
      regional = Intl.getCanonicalLocales(value || "en")[0];
    } catch {
      regional = "en";
    }
    const next = regional.toLowerCase().startsWith("de") ? "de" : "en";
    const changed = language !== next || locale !== regional;
    language = next;
    locale = regional;
    if (typeof document !== "undefined") {
      document.documentElement.lang = language;
      document.documentElement.dir = "ltr";
    }
    return changed;
  }
  function setCatalog(value) {
    catalog = value;
    const keys = Object.keys(catalog).sort((a, b) => b.length - a.length);
    matcher = new RegExp(
      keys.map((key) => key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"),
      "g",
    );
  }
  function text(value) {
    const source = String(value ?? "");
    return language === "de" || !matcher
      ? source
      : source.replace(matcher, (key) => catalog[key]);
  }
  function message(parts, ...values) {
    // Only the static parts of a template are translated. User-supplied names,
    // entity IDs, input values and escaped markup are preserved byte for byte.
    return parts.reduce(
      (result, part, i) =>
        result + text(part) + (i < values.length ? values[i] : ""),
      "",
    );
  }
  async function initialize(assetBase) {
    setLocale(preferredLanguage());
    const response = await fetch(new URL("translations/en.json", assetBase));
    if (!response.ok)
      throw Error(
        language === "de"
          ? "Die Sprache konnte nicht geladen werden. Bitte die App erneut öffnen."
          : "The language could not be loaded. Please reopen the app.",
      );
    setCatalog(await response.json());
  }
  return {
    text,
    message,
    setLocale,
    setCatalog,
    preferredLanguage,
    initialize,
    get locale() {
      return locale;
    },
    get language() {
      return language;
    },
  };
})();
const t = RadarI18n.text;
const msg = RadarI18n.message;
