/* Regression checks on actual App assets; synthetic contracts only. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");
const WEB = path.join(__dirname, "../abschlagsradar_app/web");
function contract(energy) {
  return {
    id: energy,
    settings: {
      name: energy === "gas" ? "Gas Test" : "Strom Test",
      energy_type: energy,
      source_unit: energy === "gas" ? "m³" : "kWh",
      billing_start: "2026-01-01",
      gas_mode: "heating_hot_water",
      gas_factor: 10,
      price: 0.3,
      base: 120,
      base_period: "yearly",
    },
    history: {
      readings: [{ date: "2026-01-01", value: 100 }],
      intervals: [],
      installments: [],
      tariffs: [],
      payments: [{ date: "2026-01-01", amount: 100 }],
      pending_payments: [{ date: "2026-11-01", amount: 100 }],
    },
    automatic_readings: [],
    entities: [
      {
        key: "forecast_cost",
        entity_id: "sensor.renamed_annual_cost",
        name: "Jahreskosten",
        state: "1000.25",
        unit: "EUR",
        disabled: false,
      },
      {
        key: "consumption",
        entity_id: "sensor.my_consumption",
        name: "Ist-Verbrauch",
        state: "unknown",
        unit: "kWh",
        disabled: false,
      },
      {
        key: "daily_forecast",
        entity_id: "sensor.disabled_prediction",
        name: "Tagesprognose",
        state: "unavailable",
        unit: "kWh",
        disabled: true,
      },
      {
        key: "pending_installments",
        entity_id: "sensor.old_pending",
        name: "Vorgemerkt",
        state: "100",
        unit: "EUR",
        disabled: false,
      },
    ],
    result: {
      as_of: "2026-10-03",
      observed_through: "2026-10-02",
      billing_end: "2027-01-01",
      adjustable_payment_dates: ["2026-12-01"],
      daily: [
        {
          date: "2026-01-01",
          actual_kwh: 10,
          previous_kwh: 8,
          forecast_kwh: 10,
        },
      ],
      values: {
        balance: energy === "gas" ? -100 : 100,
        forecast_cost: 1000,
        forecast_consumption: 3000,
        paid: 100,
        pending_installments: 100,
        current_installment: 100,
        remaining_installments: 1,
        recommended_installment: 150,
        average_paid_installment: 100,
        next_year_installment: 90,
        coverage: 100,
      },
    },
  };
}
async function fixture() {
  let releaseCss;
  const cssGate = new Promise((resolve) => {
    releaseCss = resolve;
  });
  const state = {
    rows: [contract("electricity"), contract("gas")],
    restores: [],
    cssRequests: 0,
    apiError: false,
    cssError: false,
    releaseCss,
  };
  const server = http.createServer(async (req, res) => {
    try {
      res.setHeader("Cache-Control", "no-store");
      if (
        req.method === "POST" &&
        ["/api/restore/preview", "/api/restore"].includes(req.url)
      ) {
        let body = "";
        for await (const chunk of req) body += chunk;
        const data = JSON.parse(body);
        if (req.url.endsWith("preview"))
          return res.end(JSON.stringify(data.contracts));
        state.restores.push(data);
        if (data.mode === "create")
          state.rows.push(
            ...data.contract_indices.map((i) => ({
              ...data.backup.contracts[i],
              id: "restored-" + i,
            })),
          );
        else
          state.rows = state.rows.map((row) =>
            row.id === data.entry_id
              ? { ...data.backup.contracts[data.contract_index], id: row.id }
              : row,
          );
        return res.end(JSON.stringify({ restored: true }));
      }
      if (req.url === "/api/session")
        return res.end(JSON.stringify({ is_admin: true, version: "0.4.3" }));
      if (req.url === "/api/contracts") {
        if (state.apiError) {
          res.statusCode = 503;
          return res.end(
            JSON.stringify({ error: "Testverbindung unterbrochen" }),
          );
        }
        return res.end(JSON.stringify(state.rows));
      }
      const file =
        req.url === "/" ? "index.html" : req.url?.replace(/^\/assets\//, "");
      if (
        !["index.html", "app.css", "shell.css", "app.js", "boot.js"].includes(
          file,
        )
      ) {
        res.statusCode = 404;
        return res.end();
      }
      if (file === "app.css") {
        state.cssRequests++;
        await cssGate;
        if (state.cssError) {
          res.statusCode = 404;
          return res.end();
        }
      }
      res.setHeader(
        "Content-Type",
        file.endsWith(".css")
          ? "text/css"
          : file.endsWith(".js")
            ? "text/javascript"
            : "text/html",
      );
      res.end(await fs.readFile(path.join(WEB, file)));
    } catch (error) {
      res.statusCode = 500;
      res.end("Fixture error");
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  state.url = "http://127.0.0.1:" + server.address().port + "/";
  state.close = () => new Promise((resolve) => server.close(resolve));
  return state;
}
async function browser() {
  return chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
}
for (const viewport of [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
]) {
  test(`No unstyled frames or pending-payment UI at ${viewport.width}px`, async () => {
    const site = await fixture();
    const engine = await browser();
    try {
      const page = await engine.newPage({ viewport });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.addInitScript(() => {
        window.unstyledFrames = [];
        function inspect() {
          const app = document.querySelector("abschlagsradar-app");
          const header = app?.shadowRoot?.querySelector("header");
          if (
            app?.view &&
            !app.view.hidden &&
            header &&
            getComputedStyle(header).display !== "flex"
          )
            window.unstyledFrames.push("header without layout");
          requestAnimationFrame(inspect);
        }
        requestAnimationFrame(inspect);
      });
      await page.goto(site.url, { waitUntil: "domcontentloaded" });
      await page.waitForFunction(
        () => document.querySelector("abschlagsradar-app")?.view,
      );
      assert.equal(
        await page.locator("header").isVisible(),
        false,
        "Contract content must remain hidden while CSS is delayed",
      );
      site.releaseCss();
      await page.getByRole("heading", { name: "Strom", exact: true }).waitFor();
      await page.evaluate(
        () =>
          (window.initialStyle = document
            .querySelector("abschlagsradar-app")
            .shadowRoot.querySelector("link")),
      );
      for (const energy of ["electricity", "gas"]) {
        await page.locator(`[data-open="${energy}"]`).click();
        for (let cycle = 0; cycle < 3; cycle++)
          for (const section of [
            "payments",
            "readings",
            "tariff",
            "entities",
            "overview",
          ]) {
            await page.locator(`[data-section="${section}"]`).click();
            await page.evaluate(
              () =>
                new Promise((resolve) =>
                  requestAnimationFrame(() => requestAnimationFrame(resolve)),
                ),
            );
            const state = await page.evaluate(() => {
              const app = document.querySelector("abschlagsradar-app");
              return {
                styled:
                  getComputedStyle(app.shadowRoot.querySelector("header"))
                    .display === "flex",
                sameStyle:
                  window.initialStyle === app.shadowRoot.querySelector("link"),
                text: app.view.innerText,
                pendingControls: app.shadowRoot.querySelectorAll(
                  '[data-confirm], [data-form="pending_payment"]',
                ).length,
              };
            });
            assert.equal(state.styled, true);
            assert.equal(state.sameStyle, true);
            assert.equal(state.pendingControls, 0);
            assert.doesNotMatch(state.text, /vorgemerkt|vormerken/i);
          }
        await page
          .getByRole("button", { name: "← Übersicht", exact: true })
          .click();
      }
      site.apiError = true;
      await page.getByRole("button", { name: "Aktualisieren" }).click();
      await page.getByRole("alert").waitFor();
      site.apiError = false;
      await page.getByRole("button", { name: "Erneut versuchen" }).click();
      await page.getByRole("heading", { name: "Strom", exact: true }).waitFor();
      assert.equal(
        site.cssRequests,
        1,
        "CSS must not be fetched again during navigation or refresh",
      );
      assert.deepEqual(await page.evaluate(() => window.unstyledFrames), []);
      assert.deepEqual(errors, []);
    } finally {
      site.releaseCss();
      await engine.close();
      await site.close();
    }
  });
}
test("Failed stylesheet never exposes unstyled contracts on refresh", async () => {
  const site = await fixture();
  site.cssError = true;
  site.releaseCss();
  const engine = await browser();
  try {
    const page = await engine.newPage();
    await page.goto(site.url);
    await page.getByRole("alert").waitFor();
    await page.evaluate(() =>
      document.querySelector("abschlagsradar-app").render(),
    );
    assert.equal(await page.locator("header").isVisible(), false);
    assert.equal(await page.getByRole("alert").isVisible(), true);
    assert.equal(site.cssRequests, 1);
  } finally {
    await engine.close();
    await site.close();
  }
});

test("Empty App restores both contracts without creating blank targets first", async () => {
  const site = await fixture();
  site.rows = [];
  site.releaseCss();
  const engine = await browser();
  try {
    const page = await engine.newPage({
      viewport: { width: 390, height: 844 },
    });
    await page.goto(site.url);
    await page
      .getByRole("button", { name: "Sicherung wiederherstellen" })
      .click();
    const backup = {
      format: "abschlagsradar-backup",
      version: 1,
      contracts: [contract("electricity"), contract("gas")],
    };
    await page
      .locator('input[name="backup"]')
      .setInputFiles({
        name: "backup.json",
        mimeType: "application/json",
        buffer: Buffer.from(JSON.stringify(backup)),
      });
    await page.getByRole("button", { name: "Daten prüfen" }).click();
    assert.equal(await page.locator('[name="mode"]').inputValue(), "create");
    assert.equal(
      await page.locator('[name="contract_index"]').inputValue(),
      "all",
    );
    assert.equal(await page.locator(".restore-target").isVisible(), false);
    assert.equal(
      await page
        .getByRole("button", { name: "Verträge wiederherstellen" })
        .isEnabled(),
      true,
    );
    await page
      .getByRole("button", { name: "Verträge wiederherstellen" })
      .click();
    await page.locator('[data-open="restored-0"]').waitFor();
    await page.locator('[data-open="restored-1"]').waitFor();
    assert.equal(site.restores.length, 1);
    assert.deepEqual(site.restores[0].contract_indices, [0, 1]);
    assert.equal(site.restores[0].mode, "create");
    assert.equal(site.rows.length, 2);
  } finally {
    await engine.close();
    await site.close();
  }
});

test("Entity tab uses registered IDs, explicit unknown states and HTTP-compatible copy", async () => {
  const site = await fixture();
  site.releaseCss();
  const engine = await browser();
  try {
    const page = await engine.newPage({
      viewport: { width: 390, height: 844 },
    });
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", { value: undefined });
    });
    await page.goto(site.url);
    await page.locator('[data-open="electricity"]').click();
    await page
      .getByRole("button", { name: "HA-Entitäten", exact: true })
      .click();
    const cost = page
      .locator(".entity-card")
      .filter({ hasText: "Jahreskosten" });
    assert.match(await cost.innerText(), /1\.000,25 EUR/);
    const link = cost.getByRole("link");
    assert.equal(
      new URL(await link.getAttribute("href")).searchParams.get(
        "more-info-entity-id",
      ),
      "sensor.renamed_annual_cost",
    );
    assert.equal(await link.getAttribute("target"), "_blank");
    await cost.getByRole("button", { name: "ID kopieren" }).click();
    await page
      .getByRole("status")
      .filter({ hasText: "sensor.renamed_annual_cost" })
      .waitFor();
    assert.equal(
      await cost.locator("input").inputValue(),
      "sensor.renamed_annual_cost",
    );
    assert.match(
      await page
        .locator(".entity-card")
        .filter({ hasText: "Ist-Verbrauch" })
        .innerText(),
      /Noch offen/,
    );
    assert.match(
      await page
        .locator(".entity-card")
        .filter({ hasText: "Tagesprognose" })
        .innerText(),
      /Deaktiviert/,
    );
    assert.doesNotMatch(
      await page.locator("main").innerText(),
      /vorgemerkt|vormerken/i,
    );
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
  } finally {
    await engine.close();
    await site.close();
  }
});
