/* Local application panel. All contract text is escaped before rendering. */
const escape = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const num = (n, unit = "", precision = undefined) =>
  n == null
    ? "Noch offen"
    : new Intl.NumberFormat("de-DE", {
        maximumFractionDigits:
          precision ??
          (unit === "€" || unit === "ct/kWh" ? 2 : unit === "m³" ? 3 : 0),
        minimumFractionDigits: unit === "€" ? 2 : 0,
      }).format(n) +
      " " +
      unit;
const signedBalance = (n) =>
  n == null
    ? { text: "Noch offen", cls: "balanced" }
    : n > 1
      ? { text: `- ${num(Math.abs(n), "€")}`, cls: "payment-due" }
      : n < -1
        ? { text: `+ ${num(Math.abs(n), "€")}`, cls: "credit" }
        : { text: num(Math.abs(n), "€"), cls: "balanced" };
const date = (d) =>
  d ? new Intl.DateTimeFormat("de-DE").format(new Date(d + "T12:00:00")) : "—";
const today = () => new Intl.DateTimeFormat("sv-SE").format(new Date());
class RadarApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.contracts = [];
    this.page = "home";
    this.section = "overview";
    this.loading = false;
    this.error = "";
  }
  set hass(h) {
    this._hass = h;
    if (!this.started) {
      this.started = true;
      this.load();
    }
  }
  connectedCallback() {
    this.timer = setInterval(() => {
      if (!document.hidden && !this.shadowRoot.querySelector("dialog[open]"))
        this.load();
    }, 60000);
  }
  disconnectedCallback() {
    clearInterval(this.timer);
  }
  async load() {
    if (!this._hass || this.loading) return;
    this.loading = true;
    try {
      this.contracts = await this._hass.callWS({ type: "abschlagsradar/app" });
      this.error = "";
    } catch (e) {
      this.error = e.message || "Verbindung fehlgeschlagen";
    }
    this.loading = false;
    this.render();
  }
  get contract() {
    return this.contracts.find((c) => c.id === this.page);
  }
  metric(label, value, sub = "", cls = "") {
    return `<article class="metric ${cls}"><span>${label}</span><strong>${value}</strong><small>${sub}</small></article>`;
  }
  paymentSchedule(c) {
    const dates = c.result.adjustable_payment_dates || [];
    return dates.length
      ? `<p class="muted">Noch anpassbare Zahlungstermine: ${dates.map(date).join(" · ")}. Die Empfehlung gilt bis zum Ende deiner Abrechnungsperiode am ${date(c.result.billing_end)}.</p>`
      : `<p class="muted">Keine anpassbaren Zahlungstermine mehr in dieser Abrechnungsperiode.</p>`;
  }
  graph(c) {
    const months = new Map();
    for (const r of c.result.daily) {
      const key = r.date.slice(0, 7);
      if (!months.has(key))
        months.set(key, {
          actual: 0,
          prev: 0,
          forecast: 0,
          known: 0,
          prior: 0,
          total: 0,
        });
      const m = months.get(key);
      m.total++;
      if (r.actual_kwh != null) {
        m.actual += r.actual_kwh;
        m.known++;
      }
      if (r.previous_kwh != null) {
        m.prev += r.previous_kwh;
        m.prior++;
      }
      m.forecast += r.forecast_kwh;
    }
    const rows = [...months],
      max = Math.max(1, ...rows.flatMap(([, m]) => [m.forecast, m.prev]));
    return `<div class="chart">${rows.map(([key, m]) => `<div class="month"><div class="bars" title="${escape(key)}: Prognose ${num(m.forecast, "kWh")}; gemessener Anteil ${num(m.actual, "kWh")}"><i class="prior" style="height:${m.prior ? (m.prev / max) * 100 : 0}%"></i><i class="forecast" style="height:${(m.forecast / max) * 100}%"><b style="height:${m.forecast ? Math.min(100, (m.actual / m.forecast) * 100) : 0}%"></b></i></div><small>${escape(new Intl.DateTimeFormat("de-DE", { month: "short" }).format(new Date(key + "-15T12:00:00")))}</small></div>`).join("")}</div><div class="legend"><span><i class="solid"></i>Gemessener Anteil</span><span><i class="light"></i>Prognose / ergänzte Lücken</span><span><i class="gray"></i>Vorjahr (vorhandene Daten)</span></div><p class="muted">Verbrauch zwischen Ablesungen wird auf Tage verteilt. Vorjahresbalken können unvollständig sein.</p>`;
  }
  home() {
    return `<div class="intro"><span class="eyebrow">DEINE ENERGIE IM BLICK</span><h1>Gut geplant.<br>Entspannt abgerechnet.</h1><p>Strom und Gas. Dein Verbrauch, deine Kosten und ein Abschlag, der passt.</p></div><div class="contract-grid">${[
      "electricity",
      "gas",
    ]
      .map((type) => {
        const list = this.contracts.filter(
            (c) => c.settings.energy_type === type,
          ),
          title = type === "gas" ? "Gas" : "Strom";
        return list.length
          ? list
              .map((c) => {
                const v = c.result.values,
                  balance = signedBalance(v.balance),
                  color =
                    balance.cls === "payment-due"
                      ? "#c43b3b"
                      : balance.cls === "credit"
                        ? "#168354"
                        : "#172a36";
                return `<button class="contract-card ${type}" data-open="${escape(c.id)}"><span class="symbol">${type === "gas" ? "♨" : "ϟ"}</span><h2>${title}</h2><p>${escape(c.settings.name)}</p><strong class="balance ${balance.cls}" style="color:${color}">${balance.text}</strong><span>voraussichtlich ${v.balance > 1 ? "Nachzahlung" : v.balance < -1 ? "Guthaben" : "ausgeglichen"}</span><footer>Vertrag öffnen <b>↗</b></footer></button>`;
              })
              .join("")
          : `<button class="contract-card ${type}" data-action="setup"><span class="symbol">${type === "gas" ? "♨" : "ϟ"}</span><h2>${title}</h2><p>Noch kein Vertrag eingerichtet</p><footer>Jetzt einrichten ↗</footer></button>`;
      })
      .join(
        "",
      )}</div><button class="primary" data-action="setup">+ Vertrag hinzufügen</button><p class="muted">Alle Berechnungen ohne Boni. Prognosen sind Schätzungen und werden mit neuen Ablesungen aktualisiert.</p>`;
  }
  detail(c) {
    const s = c.settings,
      v = c.result.values,
      h = c.history;
    return `<button class="back" data-home>← Übersicht</button><div class="detail-title"><div><span class="eyebrow">${s.energy_type === "gas" ? "GAS" : "STROM"} · DEIN VERTRAG</span><h1>${escape(s.name)}</h1><p>${date(s.billing_start)} bis ${date(c.result.billing_end)} · ohne Boni</p></div><button class="primary" data-form="reading">+ Zählerstand</button></div><nav class="tabs">${[
      ["overview", "Überblick"],
      ["readings", "Zählerstände"],
      ["payments", "Abschläge"],
      ["tariff", "Tarif"],
      ["entities", "HA-Entitäten"],
    ]
      .map(
        ([k, t]) =>
          `<button class="${this.section === k ? "active" : ""}" data-section="${k}">${t}</button>`,
      )
      .join(
        "",
      )}</nav>${this.section === "overview" ? `${this.metric("Voraussichtliche Abrechnung", num(Math.abs(v.balance), "€"), v.balance > 1 ? "Nachzahlung" : v.balance < -1 ? "Guthaben" : "Ausgeglichen", "hero")}<div class="metrics">${this.metric("Prognose Jahreskosten", num(v.forecast_cost, "€"))}${this.metric("Prognose Verbrauch", num(v.forecast_consumption, "kWh"))}${this.metric("Bereits bezahlt", num(v.paid, "€"), c.result.payments_assumed ? "Laut Zahlungsplan angenommen" : "Bestätigte Zahlungen")}</div><article class="recommend"><div><span class="eyebrow">DEIN ABSCHLAG</span><h2>${num(v.current_installment, "€")} <small>aktuell im Monat</small></h2><p>Für die verbleibenden ${v.remaining_installments} anpassbaren Termine: <b>${num(v.recommended_installment, "€")}</b> pro Monat empfohlen.</p></div><button class="primary" data-form="installment">Abschlag ändern</button></article><div class="metrics">${this.metric("Durchschnitt bezahlt dieses Jahr", num(v.average_paid_installment, "€"), "Bestätigte Zahlungen im Kalenderjahr")}${this.metric("Empfehlung nächstes Jahr", num(v.next_year_installment, "€"), "Monatlich · bekannte Preise, ohne Boni")}</div><article class="box"><h2>Dein Verbrauch im Vergleich</h2>${this.graph(c)}</article><div class="notice">${v.coverage < 100 ? `Für ${Math.round(v.coverage)} % des bisherigen Abrechnungszeitraums liegen Messintervalle vor. Ergänze einen aktuellen Zählerstand für eine bessere Prognose.` : "Deine Messintervalle decken den bisherigen Zeitraum ab."}${s.energy_type === "gas" ? ` Gas wird mit ${escape(s.gas_factor)} kWh/m³ umgerechnet. Prüfe den Faktor anhand deiner Rechnung.` : ""}</div>` : ""}${
      this.section === "readings"
        ? `<article class="box"><div class="row"><h2>Deine Ablesungen</h2><button data-action="photo">Foto auslesen</button></div><p class="muted">Zählerstand in ${escape(s.source_unit)}. Ein Eintrag am gleichen Datum ersetzt den bisherigen Stand.</p>${this.table(
            ["Datum", "Zählerstand"],
            [...h.readings]
              .reverse()
              .map((r) => [date(r.date), num(r.value, s.source_unit, 3)]),
          )}</article>`
        : ""
    }${
      this.section === "payments"
        ? `<div class="metrics">${this.metric("Bezahlt", num(v.paid, "€"))}${this.metric("Aktueller Abschlag", num(v.current_installment, "€"))}</div><div class="metrics">${this.metric("Empfohlener Abschlag für den Rest des Jahres", num(v.recommended_installment, "€"), `Monatlich · noch ${v.remaining_installments} anpassbare Termine`)}${this.metric("Durchschnitt bezahlt dieses Jahr", num(v.average_paid_installment, "€"), "Durchschnitt der Monate mit bestätigten Zahlungen")}${this.metric("Empfehlung nächstes Jahr", num(v.next_year_installment, "€"), "Monatlich · 12 Zahlungen · bekannte Tarife")}</div><article class="box"><div class="row"><h2>Abschlagsänderungen</h2><button data-form="installment">Änderung hinzufügen</button></div>${this.table(
            ["Gültig ab", "Betrag pro Monat"],
            h.installments.map((r) => [date(r.date), num(r.amount, "€")]),
          )}</article><article class="box"><div class="row"><h2>Zahlungen</h2><button data-form="payment">Zahlung erfassen</button></div>${this.table(
            ["Datum", "Bezahlt"],
            [...h.payments]
              .reverse()
              .map((r) => [date(r.date), num(r.amount, "€")]),
          )}</article>`
        : ""
    }${
      this.section === "tariff"
        ? `<article class="box"><div class="row"><h2>Preise und Änderungen</h2><button data-form="tariff">Preisänderung</button></div>${this.table(
            ["Gültig ab", "Arbeitspreis", "Grundpreis"],
            (h.tariffs.length
              ? h.tariffs
              : [
                  {
                    date: s.billing_start,
                    price: s.price,
                    base: s.base,
                    base_period: s.base_period,
                  },
                ]
            ).map((r) => [
              date(r.date),
              num(r.price * 100, "ct/kWh"),
              num(r.base, "€") +
                (r.base_period === "yearly" ? " / Jahr" : " / Monat"),
            ]),
          )}</article><article class="box"><div class="row"><h2>Vertragseinstellungen</h2><button data-form="settings">Bearbeiten</button></div><p>Abrechnungsbeginn: ${date(s.billing_start)}</p>${s.energy_type === "gas" ? `<p>Nutzung: ${{ heating: "Nur Heizung", heating_hot_water: "Heizung + Warmwasser", uniform: "Gleichmäßiger Verbrauch" }[s.gas_mode]}</p><p>Umrechnung: ${escape(s.gas_factor)} kWh/m³</p>` : ""}<p class="muted">Boni werden grundsätzlich nicht eingerechnet.</p></article>`
        : ""
    }${this.section === "entities" ? this.entityPanel(c) : ""}`;
  }
  entityPanel(c) {
    const groups = [
      [
        "Verbrauch",
        [
          "consumption",
          "forecast_consumption",
          "previous_consumption",
          "daily_consumption",
          "daily_previous",
          "daily_forecast",
        ],
      ],
      [
        "Kosten und Abrechnung",
        [
          "cost_so_far",
          "forecast_cost",
          "balance",
          "expected_payment",
          "expected_credit",
        ],
      ],
      [
        "Abschläge",
        [
          "paid",
          "current_installment",
          "recommended_installment",
          "installment_adjustment",
          "planned_installments",
          "average_paid_installment",
          "next_year_installment",
          "remaining_installments",
        ],
      ],
      [
        "Vergleich und Einschätzung",
        ["comparison", "coverage", "history_weight", "budget_status"],
      ],
    ];
    // The retired pending-payment sensor remains available for older automations,
    // but its removed feature does not return to the App's user interface.
    const entities = (c.entities || []).filter(
      (e) => e.key !== "pending_installments",
    );
    const card = (e) => {
      const value = e.disabled
        ? "Deaktiviert"
        : e.state === "unavailable"
          ? "Nicht verfügbar"
          : e.state === "unknown" || e.state == null
            ? "Noch offen"
            : e.state !== "" && Number.isFinite(Number(e.state))
              ? num(Number(e.state), e.unit || "", e.unit === "EUR" ? 2 : 3)
              : e.state;
      const url = new URL("/", this.apiBase);
      url.searchParams.set("more-info-entity-id", e.entity_id);
      return `<article class="entity-card"><h3>${escape(e.name)}</h3><a class="entity-value" href="${escape(url.href)}" target="_blank" rel="noopener noreferrer" aria-label="${escape(e.name)} in Home Assistant öffnen">${escape(value)} <span aria-hidden="true">↗</span></a><label class="entity-id-label">Entity-ID<input readonly value="${escape(e.entity_id)}" aria-label="Entity-ID ${escape(e.name)}"></label><button data-copy-entity="${escape(e.entity_id)}">ID kopieren</button></article>`;
    };
    return `<article class="box"><span class="eyebrow">HOME ASSISTANT</span><h2>Deine Werte weiterverwenden</h2><p>Diese Entitäten werden automatisch für deinen Vertrag erzeugt. Nutze sie in Automationen, Diagrammen und eigenen Dashboards. Ein Klick auf einen Wert öffnet die Entität in Home Assistant in einem neuen Fenster.</p><p class="muted">${entities.length} Entitäten · Werte vom letzten Aktualisieren <button data-action="refresh">Aktualisieren</button></p><p class="copy-status" role="status" aria-live="polite"></p></article>${groups
      .map(([title, keys]) => {
        const rows = entities.filter((e) => keys.includes(e.key));
        return rows.length
          ? `<section class="entity-group"><h2>${title}</h2><div class="entity-grid">${rows.map(card).join("")}</div></section>`
          : "";
      })
      .join(
        "",
      )}${!entities.length ? '<p class="notice">Die Entitäten werden gerade geladen. Bitte gleich aktualisieren.</p>' : ""}`;
  }
  async copyEntity(button) {
    const id = button.dataset.copyEntity;
    let copied = false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(id);
        copied = true;
      }
    } catch {
      /* HTTP Home Assistant and denied clipboard permissions use selection below. */
    }
    if (!copied) {
      const input = button.closest(".entity-card").querySelector("input");
      input.focus();
      input.select();
      try {
        copied = document.execCommand("copy");
      } catch {
        /* Leave the ID selected for manual copying. */
      }
    }
    this.shadowRoot.querySelector(".copy-status").textContent = copied
      ? `Kopiert: ${id}`
      : `ID markiert: ${id}. Bitte über das Kopiermenü oder Strg/Cmd+C kopieren.`;
  }
  table(headers, rows) {
    return `<div class="table-wrap"><table><thead><tr>${headers.map((x) => `<th>${x}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map((r) => `<tr>${r.map((x) => `<td>${escape(x)}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${headers.length}">Noch keine Einträge.</td></tr>`}</tbody></table></div>`;
  }
  render() {
    // Keep the loaded stylesheet attached across navigation and data refreshes.
    // Replacing it with each view briefly exposes unstyled shadow-DOM content.
    if (!this.view) {
      this.view = document.createElement("div");
      this.view.hidden = true;
      const stylesheet = document.createElement("link");
      stylesheet.rel = "stylesheet";
      stylesheet.href = `${this.assetBase || "assets/"}app.css`;
      stylesheet.onload = () => {
        this.view.hidden = false;
      };
      stylesheet.onerror = () => {
        // Keep contract content hidden if its stylesheet cannot be loaded.
        const notice = document.createElement("p");
        notice.setAttribute("role", "alert");
        notice.style.cssText =
          "padding:24px;font:16px/1.5 system-ui;color:#172a36";
        notice.textContent =
          "Die Darstellung konnte nicht geladen werden. Bitte die App erneut öffnen.";
        this.shadowRoot.append(notice);
      };
      this.shadowRoot.append(stylesheet, this.view);
    }
    this.view.innerHTML = `<header><span class="app-badge">APP</span><button class="brand" data-home><i>◉</i> AbschlagsRadar</button><button data-action="export">Daten sichern</button><button data-action="refresh" aria-label="Aktualisieren">↻</button></header><main>${this.error ? `<div role="alert" class="notice">${escape(this.error)} <button data-action="refresh">Erneut versuchen</button></div>` : ""}${this.error ? '<p class="muted">Deine Daten bleiben gespeichert. Sobald Home Assistant erreichbar ist, kannst du sie wieder öffnen.</p>' : this.contract ? this.detail(this.contract) : this.home()}</main><dialog></dialog>`;
    if (!this.error) {
      const main = this.shadowRoot.querySelector("main");
      if (this.contract && this.section === "overview") {
        const result = this.contract.result;
        const issues = {
          source_unavailable: "Der Zählersensor ist momentan nicht verfügbar.",
          source_unit_mismatch:
            "Die Einheit des Zählersensors passt nicht zum Vertrag.",
          meter_reset:
            "Der Zählersensor ist zurückgesprungen. Prüfe einen möglichen Zählerwechsel.",
          conflicting_automatic_readings:
            "Automatische und manuelle Ablesungen widersprechen sich. Für die Berechnung werden vorläufig die manuellen Ablesungen verwendet.",
        };
        main.insertAdjacentHTML(
          "beforeend",
          `<p class="muted">Letzter durch Messintervalle erfasster Verbrauchstag: ${date(result.observed_through)}. Stand der Berechnung: ${date(result.as_of)}.</p>${result.source_issue ? `<div class="notice" role="status">${escape(issues[result.source_issue] || "Bitte den Zählersensor und die Ablesungen prüfen.")}</div>` : ""}`,
        );
      }
      if (this.contract && this.section === "payments") {
        main
          .querySelectorAll(".metrics")[1]
          .insertAdjacentHTML("afterend", this.paymentSchedule(this.contract));
      }
      if (this.contract && this.section === "readings") {
        const manualDates = new Set(
          this.contract.history.readings.map((row) => row.date),
        );
        const automatic = (this.contract.automatic_readings || []).filter(
          (row) => !manualDates.has(row.date),
        );
        if (automatic.length)
          main.insertAdjacentHTML(
            "beforeend",
            `<details class="box"><summary>Automatisch erfasste Ablesungen (${automatic.length})</summary>${this.table(
              ["Datum", "Zählerstand"],
              automatic
                .slice()
                .reverse()
                .map((row) => [
                  date(row.date),
                  num(row.value, this.contract.settings.source_unit, 3),
                ]),
            )}</details>`,
          );
        main.insertAdjacentHTML(
          "beforeend",
          `<article class="box"><div class="row"><h2>Direkte Verbrauchsintervalle</h2><button data-form="interval">Intervall hinzufügen</button></div><p class="muted">Ein Intervall enthält den gesamten Verbrauch in kWh zwischen zwei Daten. Der Endtag gehört zum folgenden Intervall.</p>${this.table(
            ["Von", "Bis", "Verbrauch"],
            this.contract.history.intervals.map((row) => [
              date(row.start),
              date(row.end),
              num(row.kwh, "kWh", 3),
            ]),
          )}</article>`,
        );
      }
      if (!this.contract)
        main.insertAdjacentHTML(
          "beforeend",
          '<button data-action="restore">Sicherung wiederherstellen</button>',
        );
    }
    this.shadowRoot.querySelectorAll("[data-home]").forEach(
      (b) =>
        (b.onclick = () => {
          this.page = "home";
          this.render();
        }),
    );
    this.shadowRoot.querySelectorAll("[data-open]").forEach(
      (b) =>
        (b.onclick = () => {
          this.page = b.dataset.open;
          this.section = "overview";
          this.render();
        }),
    );
    this.shadowRoot.querySelectorAll("[data-copy-entity]").forEach((b) => {
      b.onclick = () => this.copyEntity(b);
    });
    this.shadowRoot.querySelectorAll("[data-section]").forEach(
      (b) =>
        (b.onclick = () => {
          this.section = b.dataset.section;
          this.render();
        }),
    );
    this.shadowRoot
      .querySelectorAll("[data-form]")
      .forEach((b) => (b.onclick = () => this.form(b.dataset.form)));
    this.shadowRoot.querySelectorAll("[data-action]").forEach(
      (b) =>
        (b.onclick = () => {
          if (b.dataset.action === "refresh") this.load();
          else if (b.dataset.action === "setup") this.setup();
          else if (b.dataset.action === "restore") this.restoreBackup();
          else if (b.dataset.action === "export")
            window.location.href = new URL("api/export", this.apiBase).href;
          else this.photo();
        }),
    );
  }
  restoreBackup() {
    if (!this._hass.user?.is_admin) return;
    const dialog = this.shadowRoot.querySelector("dialog");
    dialog.innerHTML = `<form><h2>Sicherung wiederherstellen</h2><p>Hole deine Verträge aus einer Sicherung zurück – auch in eine leere App. Im nächsten Schritt wählst du, ob neue Verträge angelegt oder vorhandene Daten ersetzt werden.</p><label>Sicherung auswählen<input name="backup" type="file" accept="application/json,.json" required></label><p class="form-error" role="alert"></p><div class="form-actions"><button type="button" class="close">Abbrechen</button><button class="primary">Daten prüfen</button></div></form>`;
    dialog.querySelector(".close").onclick = () => dialog.close();
    dialog.showModal();
    dialog.querySelector("form").onsubmit = async (event) => {
      event.preventDefault();
      const form = event.target;
      const submit = form.querySelector(".primary");
      submit.disabled = true;
      try {
        const file = form.querySelector("input").files[0];
        if (file.size > 12 * 1024 * 1024)
          throw Error("Die Sicherung darf höchstens 12 MB groß sein.");
        const backup = JSON.parse(await file.text());
        const preview = await this.request("api/restore/preview", backup);
        this.restoreForm(dialog, backup, preview);
      } catch (error) {
        form.querySelector(".form-error").textContent = error.message;
        submit.disabled = false;
      }
    };
  }
  restoreForm(dialog, backup, preview) {
    dialog.innerHTML = `<form><h2>Sicherung wiederherstellen</h2><label>Wie möchtest du wiederherstellen?<select name="mode"><option value="create">Neue Verträge anlegen</option value="replace" ${this.contracts.length ? "" : "disabled"}>Vorhandenen Vertrag ersetzen</option></select></label><label>Verträge aus der Sicherung<select name="contract_index"></select></label><label class="restore-target" hidden>Vorhandener Zielvertrag<select name="entry_id"></select></label><p class="notice restore-notice"></p><p class="form-error" role="alert"></p><div class="form-actions"><button type="button" class="close">Abbrechen</button><button class="primary">Wiederherstellen</button></div></form>`;
    dialog.querySelector(".close").onclick = () => dialog.close();
    const mode = dialog.querySelector('[name="mode"]');
    const selection = dialog.querySelector('[name="contract_index"]');
    const target = dialog.querySelector('[name="entry_id"]');
    const updateTargets = () => {
      const creating = mode.value === "create";
      dialog.querySelector(".restore-target").hidden = creating;
      target.required = !creating;
      const energy = preview[Number(selection.value)]?.settings.energy_type;
      target.innerHTML = this.contracts
        .filter((row) => row.settings.energy_type === energy)
        .map(
          (row) =>
            `<option value="${escape(row.id)}">${escape(row.settings.name)}</option>`,
        )
        .join("");
      dialog.querySelector(".primary").disabled = !creating && !target.value;
      dialog.querySelector(".primary").textContent = creating
        ? "Verträge wiederherstellen"
        : "Diesen Vertrag ersetzen";
      dialog.querySelector(".restore-notice").textContent = creating
        ? "Die ausgewählten Verträge werden mit ihrer vollständigen Historie neu angelegt. Vorhandene Verträge bleiben erhalten. Neue Verträge erhalten neue Home-Assistant-Entity-IDs."
        : "Die Vertragsdaten und Historie des Zielvertrags werden vollständig ersetzt. Seine Home-Assistant-Sensoren behalten ihre IDs. Sichere vorher den aktuellen Stand.";
    };
    const updateSelection = () => {
      selection.innerHTML =
        (mode.value === "create"
          ? '<option value="all">Alle Verträge aus der Sicherung</option>'
          : "") +
        preview
          .map(
            (row, index) =>
              `<option value="${index}">${escape(row.settings.name)} · ${row.history.readings.length} Ablesungen</option>`,
          )
          .join("");
      updateTargets();
    };
    mode.onchange = updateSelection;
    selection.onchange = updateTargets;
    updateSelection();
    dialog.querySelector("form").onsubmit = async (event) => {
      event.preventDefault();
      const form = event.target;
      const submit = form.querySelector(".primary");
      submit.disabled = true;
      // Prevent target/mode changes and duplicate submission during the import.
      form.querySelectorAll("select, .close").forEach((control) => {
        control.disabled = true;
      });
      try {
        const payload =
          mode.value === "create"
            ? {
                mode: "create",
                contract_indices:
                  selection.value === "all"
                    ? preview.map((_, index) => index)
                    : [Number(selection.value)],
                backup,
              }
            : {
                entry_id: target.value,
                contract_index: Number(selection.value),
                backup,
              };
        await this.request("api/restore", payload);
        dialog.close();
        await this.load();
      } catch (error) {
        form.querySelector(".form-error").textContent = error.message;
        form.querySelectorAll("select, .close").forEach((control) => {
          control.disabled = false;
        });
        submit.disabled = false;
      }
    };
  }
  async request(path, data) {
    const response = await fetch(new URL(path, this.apiBase), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    let body;
    try {
      body = await response.json();
    } catch {
      throw Error(
        "Die Anfrage konnte nicht verarbeitet werden. Bitte erneut versuchen.",
      );
    }
    if (!response.ok) throw Error(body.error || "Die Eingabe wurde abgelehnt.");
    return body;
  }
  setup() {
    if (!this._hass?.user?.is_admin) {
      this.error = "Nur Administratoren können Verträge anlegen.";
      this.render();
      return;
    }
    const dialog = this.shadowRoot.querySelector("dialog");
    dialog.innerHTML = `<h2>Was möchtest du hinzufügen?</h2><p>Jeder Vertrag bekommt seinen eigenen Bereich.</p><div class="choose-energy"><button data-energy="electricity">ϟ Strom</button><button data-energy="gas">♨ Gas</button></div><button class="close">Abbrechen</button>`;
    dialog.querySelector(".close").onclick = () => dialog.close();
    dialog
      .querySelectorAll("[data-energy]")
      .forEach((b) => (b.onclick = () => this.setupForm(b.dataset.energy)));
    dialog.showModal();
  }
  setupForm(energy) {
    const gas = energy === "gas",
      dialog = this.shadowRoot.querySelector("dialog");
    dialog.innerHTML = `<form><h2>${gas ? "Gas" : "Strom"} einrichten</h2><label>Vertragsname<input name="name" required value="${gas ? "Gas" : "Strom"}"></label><label>Abrechnungsbeginn<input name="billing_start" required type="date" value="${today()}"></label><label>Arbeitspreis (ct/kWh)<input name="price" required type="number" min="0" step="any"></label><label>Grundpreis (€)<input name="base" required type="number" min="0" step="any"></label><label>Grundpreis gilt<select name="base_period"><option value="yearly">Pro Jahr</option><option value="monthly">Pro Monat</option></select></label><label>Monatlicher Abschlag (€)<input name="payment" required type="number" min="0" step="any"></label><label>Zahlungstag<input name="payment_day" required type="number" min="1" max="28" step="1" value="1"></label><label>Geschätzter Jahresverbrauch (kWh)<input name="annual_estimate" required type="number" min="0" step="any" value="${gas ? 6000 : 3000}"></label>${gas ? '<label>Gasnutzung<select name="gas_mode"><option value="heating_hot_water">Heizung + Warmwasser</option><option value="heating">Nur Heizung</option><option value="uniform">Gleichmäßiger Verbrauch</option></select></label><label>Umrechnung (kWh/m³)<input name="gas_factor" type="number" required min="0.01" step="any" value="10"></label>' : ""}<p class="form-error" role="alert"></p><div class="form-actions"><button type="button" class="close">Abbrechen</button><button class="primary" type="submit">Vertrag anlegen</button></div></form>`;
    const extra = `<label>Home-Assistant-Zählersensor (optional)<input name="source_sensor" type="text" placeholder="sensor.zaehlerstand"></label>${gas ? '<label>Zählereinheit<select name="source_unit"><option value="m³">m³</option><option value="kWh">kWh</option></select></label><p class="muted">Bei einem kWh-Zähler wird kein Umrechnungsfaktor angewendet.</p>' : ""}`;
    dialog
      .querySelector(".form-error")
      .insertAdjacentHTML("beforebegin", extra);
    dialog.querySelector(".close").onclick = () => dialog.close();
    dialog.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      const payload = {
        energy_type: energy,
        ...Object.fromEntries(new FormData(e.target)),
      };
      for (const i of e.target.querySelectorAll("input[type=number]"))
        payload[i.name] = Number(payload[i.name]);
      payload.price /= 100;
      const submit = e.target.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        const r = await fetch(new URL("api/contracts", this.apiBase), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!r.ok)
          throw Error((await r.json()).error || "Einrichtung fehlgeschlagen");
        dialog.close();
        await new Promise((r) => setTimeout(r, 800));
        await this.load();
      } catch (err) {
        dialog.querySelector(".form-error").textContent = err.message;
        submit.disabled = false;
      }
    };
  }
  photo() {
    if (!this._hass.user?.is_admin) {
      this.error = "Nur Administratoren können Fotos verarbeiten.";
      this.render();
      return;
    }
    const dialog = this.shadowRoot.querySelector("dialog");
    dialog.innerHTML = `<form><h2>Zählerfoto auslesen</h2><p class="muted">Fotografiere die Ziffern möglichst gerade und scharf. Das Foto wird lokal verarbeitet. Prüfe den erkannten Wert vor dem Speichern.</p><label>Ablesedatum<input required name="date" type="date" value="${today()}" max="${today()}"></label><label>Foto auswählen<input required name="file" type="file" accept="image/jpeg,image/png"></label><details><summary>Bildausschnitt begrenzen (optional)</summary><p class="muted">Grenzen in Prozent des Bildes. Bei einem Gesamtfoto nur die Ziffernanzeige einschließen.</p>${[
      ["left", "Links", 0],
      ["top", "Oben", 0],
      ["right", "Rechts", 100],
      ["bottom", "Unten", 100],
    ]
      .map(
        ([key, label, value]) =>
          `<label>${label}<input name="${key}" type="number" min="0" max="100" value="${value}" required></label>`,
      )
      .join(
        "",
      )}</details><p class="form-error" role="alert"></p><div class="form-actions"><button type="button" class="close">Abbrechen</button><button type="submit" class="primary">Foto auslesen</button></div></form>`;
    dialog.querySelector(".close").onclick = () => dialog.close();
    dialog.showModal();
    dialog.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      const form = e.target,
        button = form.querySelector("[type=submit]"),
        file = form.querySelector("[name=file]").files[0],
        d = form.querySelector("[name=date]").value;
      button.disabled = true;
      button.textContent = "Wird ausgelesen …";
      try {
        if (file.size > 12 * 1024 * 1024)
          throw Error("Das Foto darf höchstens 12 MB groß sein.");
        const body = new FormData();
        body.append("file", file);
        const response = await this._hass.fetchWithAuth("/api/file_upload", {
          method: "POST",
          body,
          headers: {
            "X-Radar-Crop": JSON.stringify(
              ["left", "top", "right", "bottom"].map((key) =>
                Number(form.querySelector(`[name="${key}"]`).value),
              ),
            ),
          },
        });
        if (!response.ok) throw Error("Foto konnte nicht hochgeladen werden.");
        const upload = await response.json();
        const candidates = await this._hass.callWS({
          type: "abschlagsradar/scan",
          file_id: upload.file_id,
        });
        this.form("reading");
        const current = this.shadowRoot.querySelector("dialog");
        current.querySelector("[name=date]").value = d;
        current.querySelector("[name=value]").value = candidates[0].value;
        const hint = document.createElement("p");
        hint.className = "notice";
        hint.textContent =
          "Bitte prüfen: Erkannte Werte " +
          candidates.map((c) => c.value).join(", ") +
          ". Erst mit Speichern wird die Ablesung übernommen.";
        current.querySelector("form").prepend(hint);
      } catch (err) {
        form.querySelector(".form-error").textContent =
          err.message || "Auslesen fehlgeschlagen";
        button.disabled = false;
        button.textContent = "Foto auslesen";
      }
    };
  }
  navigate(path) {
    history.pushState(null, "", path);
    window.dispatchEvent(new Event("location-changed"));
  }
  async save(action, payload) {
    await this._hass.callWS({
      type: "abschlagsradar/edit",
      entry_id: this.contract.id,
      action,
      payload,
    });
    await new Promise((r) => setTimeout(r, 600));
    await this.load();
  }
  form(action) {
    if (!this._hass.user?.is_admin) {
      this.error = "Nur Administratoren können Vertragsdaten ändern.";
      this.render();
      return;
    }
    const c = this.contract,
      s = c.settings;
    const input = (key, label, value, type = "number", step = "any") =>
      `<label>${label}<input required name="${key}" type="${type}" value="${escape(value)}" ${type === "number" ? `min="0" step="${step}"` : ""}></label>`;
    let fields = input("date", "Gültig am / ab", today(), "date");
    let title = "";
    if (action === "reading") {
      title = "Zählerstand eintragen";
      fields += input("value", `Zählerstand (${escape(s.source_unit)})`, "");
    }
    if (action === "installment") {
      title = "Abschlag ändern";
      fields += input(
        "amount",
        "Monatlicher Abschlag (€)",
        c.result.values.recommended_installment?.toFixed(2) ||
          c.result.values.current_installment,
      );
    }
    if (action === "payment") {
      title = "Bezahlte Zahlung erfassen";
      fields += input("amount", "Betrag (€)", "");
    }
    if (action === "interval") {
      title = "Verbrauchsintervall erfassen";
      fields =
        input("start", "Beginn (einschließlich)", "", "date") +
        input("end", "Ende (ausschließlich)", today(), "date") +
        input("kwh", "Verbrauch im Zeitraum (kWh)", "");
    }
    if (action === "tariff") {
      title = "Tarif / Preisänderung";
      const tariff =
        [...c.history.tariffs].reverse().find((row) => row.date <= today()) ||
        s;
      fields +=
        input("price", "Arbeitspreis (ct/kWh)", tariff.price * 100) +
        input("base", "Grundpreis (€)", tariff.base) +
        `<label>Grundpreis gilt<select name="base_period"><option value="yearly" ${tariff.base_period === "yearly" ? "selected" : ""}>Pro Jahr</option><option value="monthly" ${tariff.base_period === "monthly" ? "selected" : ""}>Pro Monat</option></select></label>`;
    }
    if (action === "settings") {
      title = "Vertrag bearbeiten";
      fields =
        input("name", "Vertragsname", s.name, "text") +
        input("billing_start", "Abrechnungsbeginn", s.billing_start, "date") +
        input(
          "payment_day",
          "Zahlungstag (1–28)",
          s.payment_day,
          "number",
          "1",
        ) +
        input(
          "annual_estimate",
          "Jahresverbrauch als Ersatzwert (kWh)",
          s.annual_estimate,
        );
      if (s.energy_type === "gas")
        fields +=
          input("gas_factor", "Umrechnungsfaktor (kWh/m³)", s.gas_factor) +
          `<label>Gasnutzung<select name="gas_mode">${[
            ["heating", "Nur Heizung"],
            ["heating_hot_water", "Heizung + Warmwasser"],
            ["uniform", "Gleichmäßiger Verbrauch"],
          ]
            .map(
              ([v, l]) =>
                `<option value="${v}" ${s.gas_mode === v ? "selected" : ""}>${l}</option>`,
            )
            .join("")}</select></label>`;
    }
    if (action === "settings")
      fields += `<label>Home-Assistant-Zählersensor (optional)<input name="source_sensor" type="text" value="${escape(s.source_sensor || "")}" placeholder="sensor.zaehlerstand"></label><p class="muted">Ein kumulativer Zählerstand in ${escape(s.source_unit)}. Leer lassen, um ausschließlich manuell abzulesen.</p>`;
    const dialog = this.shadowRoot.querySelector("dialog");
    dialog.innerHTML = `<form><div class="row"><h2>${title}</h2><button type="button" class="close" aria-label="Schließen">×</button></div>${fields}<p class="form-error" role="alert"></p><div class="form-actions"><button type="button" class="close">Abbrechen</button><button class="primary" type="submit">Speichern</button></div>${action === "installment" ? '<p class="muted">Ändert deine Planung. Den Zahlungsauftrag musst du beim Anbieter selbst anpassen.</p>' : ""}</form>`;
    dialog
      .querySelectorAll(".close")
      .forEach((b) => (b.onclick = () => dialog.close()));
    dialog.showModal();
    if (action === "reading" || action === "payment")
      dialog.querySelector('[name="date"]').max = today();
    if (action === "settings") {
      dialog.querySelector('[name="payment_day"]').max = "28";
      const factor = dialog.querySelector('[name="gas_factor"]');
      if (factor) factor.min = "0.000001";
    }
    dialog.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      const payload = Object.fromEntries(new FormData(e.target));
      for (const input of e.target.querySelectorAll("input[type=number]"))
        payload[input.name] = Number(payload[input.name]);
      if (action === "tariff") payload.price /= 100;
      const submit = e.target.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        await this.save(action, payload);
      } catch (err) {
        dialog.querySelector(".form-error").textContent =
          err.message || "Speichern fehlgeschlagen";
        submit.disabled = false;
      }
    };
  }
}
customElements.define("abschlagsradar-app", RadarApp);
