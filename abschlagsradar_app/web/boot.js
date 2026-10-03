/* Standalone transport. Authentication stays in Home Assistant Ingress. */
(async () => {
  const element = document.querySelector("abschlagsradar-app");
  const base = new URL(".", window.location.href);
  const endpoint = (name) => new URL(name, base).href;
  async function json(path, options) {
    const response = await fetch(endpoint(path), {
      credentials: "same-origin",
      ...options,
    });
    if (!response.ok) {
      let error;
      try {
        error = (await response.json()).error;
      } catch (e) {
        error = "Bitte die App über die Home-Assistant-Seitenleiste öffnen.";
      }
      throw Error(error || "Anfrage fehlgeschlagen");
    }
    return response.json();
  }
  try {
    const session = await json("api/session");
    element.assetBase = endpoint("assets/");
    element.apiBase = base.href;
    element.standalone = true;
    element.hass = {
      user: { is_admin: session.is_admin },
      callWS: (message) =>
        message.type === "abschlagsradar/app"
          ? json("api/contracts")
          : json("api/message", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(message),
            }),
      fetchWithAuth: (path, options) =>
        fetch(endpoint("api/photo"), {
          credentials: "same-origin",
          ...options,
        }),
    };
  } catch (error) {
    element.assetBase = endpoint("assets/");
    element.error = error.message;
    element.render();
  }
})();
