/* Disposable empty server at PORT (8765 by default); uses local Playwright/axe. */
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 320, height: 844 },
  });
  const page = await context.newPage();
  const origin = `http://127.0.0.1:${process.env.PORT || 8765}`;
  const errors = [],
    external = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (new URL(r.url()).origin !== origin) external.push(r.url());
  });
  await page.goto(origin);
  await page.getByText("Up to date.", { exact: true }).waitFor();
  await page.locator("#vehicle-form-registration").fill("REMINDER TEST");
  await page.locator("#vehicle-form-initial_mileage").fill("10000");
  await page.locator("#vehicle-form button").click();
  await page.locator("#context").filter({ hasText: "REMINDER TEST" }).waitFor();
  await page.locator("#add-reminder").waitFor({ state: "visible" });
  await page.locator("#add-reminder").click();
  assert.equal(await page.locator(":focus").getAttribute("name"), "title");
  const dialog = page.locator("#reminder-dialog");
  await dialog.locator("[name=title]").fill("Annual service");
  await dialog.locator("[name=category]").selectOption("SERVICE");
  await page.locator("#reminder-save").click();
  await page
    .locator("#reminder-error")
    .filter({ hasText: "Supply at least one" })
    .waitFor();
  assert.equal(
    await dialog.locator("[name=title]").inputValue(),
    "Annual service",
  );
  assert.equal(
    await page.locator(":focus").getAttribute("id"),
    "reminder-error",
  );
  await dialog.locator("[name=due_mileage]").fill("12000");
  const axe = await new AxeBuilder({ page })
    .include("#reminder-dialog")
    .analyze();
  assert.deepEqual(
    axe.violations.map((x) => x.id),
    [],
  );
  await page.locator("#reminder-save").click();
  await dialog.waitFor({ state: "hidden" });
  await page
    .locator("#reminder-list")
    .getByText(/Annual service/)
    .first()
    .waitFor();
  assert.match(
    await page.locator("#reminder-list").innerText(),
    /Mileage status unknown/,
  );
  const edit = page.getByRole("button", {
    name: "Edit reminder Annual service for REMINDER TEST",
    exact: true,
  });
  await edit.click();
  assert.equal(
    await dialog.locator("[name=due_mileage]").inputValue(),
    "12000",
  );
  await dialog.locator("[name=title]").fill("Draft retained");
  await page.route("**/api/reminders/*", (route) => {
    if (route.request().method() === "PUT")
      return route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            message: "Fixture validation failure",
            fields: { "body.title": "Check title" },
          },
        }),
      });
    return route.continue();
  });
  await page.locator("#reminder-save").click();
  await page
    .locator("#reminder-error")
    .filter({ hasText: "Fixture validation failure" })
    .waitFor();
  assert.equal(
    await dialog.locator("[name=title]").inputValue(),
    "Draft retained",
  );
  assert.equal(
    await dialog.locator("[name=title]").getAttribute("aria-invalid"),
    "true",
  );
  await page.locator("#reminder-error a").click();
  assert.equal(await page.locator(":focus").getAttribute("name"), "title");
  await page.unroute("**/api/reminders/*");
  assert.equal(
    await dialog.evaluate((el) => el.scrollWidth > el.clientWidth),
    false,
  );
  await dialog.locator("[name=title]").fill("Corrected service");
  await dialog.locator("[name=due_date]").fill("2020-01-01");
  await page.locator("#reminder-save").click();
  await dialog.waitFor({ state: "hidden" });
  await page
    .getByRole("button", {
      name: "Edit reminder Corrected service for REMINDER TEST",
      exact: true,
    })
    .waitFor();
  assert.match(
    await page.locator("#reminder-list").innerText(),
    /Due date: 2020-01-01/,
  );
  await page
    .getByRole("button", {
      name: "Edit reminder Corrected service for REMINDER TEST",
      exact: true,
    })
    .click();
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden" });
  assert.match(
    await page.locator(":focus").getAttribute("aria-label"),
    /^Edit reminder/,
  );
  await page
    .getByRole("button", {
      name: "Complete reminder Corrected service for REMINDER TEST",
      exact: true,
    })
    .click();
  await dialog.locator("[name=due_mileage]").fill("15000");
  await page.locator("#reminder-save").click();
  await dialog.waitFor({ state: "hidden" });
  await page
    .getByText("Reminder completed; history retained.", { exact: true })
    .waitFor();
  let rows = await page.evaluate(() =>
    fetch("/api/reminders").then((r) => r.json()),
  );
  assert.equal(rows.length, 2);
  assert.equal(rows.filter((r) => r.status === "completed").length, 1);
  assert.ok(rows.find((r) => !r.reminder.completed_at).reminder.previous_id);
  await page
    .getByRole("button", {
      name: "Complete reminder Corrected service for REMINDER TEST",
      exact: true,
    })
    .click();
  await page.locator("#reminder-save").click();
  await dialog.waitFor({ state: "hidden" });
  await page
    .getByText("Reminder completed; history retained.", { exact: true })
    .waitFor();
  const deletes = page.getByRole("button", {
    name: "Delete reminder Corrected service for REMINDER TEST",
    exact: true,
  });
  await deletes.first().click();
  assert.equal(await page.locator(":focus").textContent(), "Cancel");
  await page.locator("#confirm button[value=cancel]").click();
  assert.match(
    await page.locator(":focus").getAttribute("aria-label"),
    /^Delete reminder/,
  );
  await deletes.first().click();
  await page.locator("#confirm button[value=delete]").click();
  await page.getByText("Reminder deleted.", { exact: true }).waitFor();
  rows = await page.evaluate(() =>
    fetch("/api/reminders").then((r) => r.json()),
  );
  assert.equal(rows.length, 1);
  await page.locator("[data-status=SOLD]").click();
  await page
    .getByText("Saved. Current data refreshed.", { exact: true })
    .waitFor();
  assert.match(
    await page.locator("#reminder-list").innerText(),
    /No reminders yet/,
  );
  await page.locator("#inactive").check();
  await page.getByText("Up to date.", { exact: true }).waitFor();
  assert.match(await page.locator("#reminder-list").innerText(), /SOLD/);
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  const listAxe = await new AxeBuilder({ page })
    .include("section[aria-labelledby=reminder-heading]")
    .analyze();
  assert.deepEqual(
    listAxe.violations.map((x) => x.id),
    [],
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  console.log(
    JSON.stringify({
      browser: browser.version(),
      checks:
        "create validation retention, forced API error/draft retention/retry, edit prefill/save, cancel focus, complete linked next and complete-only history, confirmed delete, lifecycle inactive visibility, keyboard focus, 320px reflow, dialog/list axe, local-only requests",
      axeViolations: 0,
      pageErrors: errors,
      externalRequests: external,
    }),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
