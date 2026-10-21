/* Run with NODE_PATH pointing to a temporary Playwright install; see smoke.md. */
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const BASE = process.env.ODOMETER_TEST_URL || "http://127.0.0.1:8876";
const AxeBuilder = require("@axe-core/playwright").default;
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage();
  const failures = [],
    external = [];
  page.on("pageerror", (e) => failures.push(e.message));
  page.on("request", (r) => {
    if (new URL(r.url()).origin !== BASE) external.push(r.url());
  });
  await page.goto(BASE);
  const ready = () =>
    page
      .locator("#status")
      .filter({ hasText: /Up to date|Saved|Vehicle deleted/ })
      .waitFor();
  await ready();
  await page.keyboard.press("Tab");
  assert.equal(await page.locator(":focus").textContent(), "Skip to dashboard");
  assert.match(await page.locator("#vehicle-detail").textContent(), /empty/);
  await page.locator("#vehicle-form-registration").fill("UI TEST");
  await page.locator("#vehicle-form-initial_mileage").fill("10000");
  await page.locator("#vehicle-form-fuel_tank_litres").fill("60");
  await page.locator("#vehicle-form-purchase_price_pence").fill("1234.56");
  await page.locator("#vehicle-form button").click();
  await ready();
  assert.match(await page.locator("#context").textContent(), /UI TEST/);
  assert.match(await page.locator("#metrics").textContent(), /No fuel history/);
  const fill = async (miles, litres, cost, full) => {
    await page.locator("#fuel-form-date").fill("2026-10-20");
    await page.locator("#fuel-form-odometer_miles").fill(String(miles));
    await page.locator("#fuel-form-litres").fill(String(litres));
    await page.locator("#fuel-form-total_cost_pence").fill(cost);
    await page.locator("#fuel-form-is_full_tank").setChecked(full);
    await page.locator("#fuel-form button").click();
    await ready();
  };
  await fill(10000, 30, "45.01", true);
  await fill(10150, 15, "22.50", false);
  await fill(10300, 30, "45.00", true);
  assert.match(await page.locator("#metrics").textContent(), /30.31/);
  const disclosure = page.getByText("How UK MPG was calculated", {
    exact: true,
  });
  await disclosure.focus();
  await page.keyboard.press("Enter");
  assert.equal(await page.locator("#metrics details").getAttribute("open"), "");
  assert.match(
    await page.locator("#metrics details").textContent(),
    /45 litres/,
  );
  assert.match(
    await page.locator("#metrics details").textContent(),
    /imperial gallons/,
  );
  await page.setViewportSize({ width: 320, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  assert.match(await page.locator("#metrics").textContent(), /£112.51/);
  await page.locator("#expense-form-date").fill("2026-10-20");
  await page.locator("#expense-form-category").selectOption("SERVICE");
  await page.locator("#expense-form-amount_pence").fill("123.45");
  await page
    .locator("#expense-form-description")
    .fill("<img src=x onerror=alert(1)>");
  await page.locator("#expense-form button").click();
  await ready();
  assert.equal(await page.locator("#expense-list img").count(), 0);
  assert.match(await page.locator("#metrics").textContent(), /£235.96/);
  // Service error preserves input and announces it.
  await page.locator("#fuel-form-date").fill("2026-10-20");
  await page.locator("#fuel-form-odometer_miles").fill("9000");
  await page.locator("#fuel-form-litres").fill("10");
  await page.locator("#fuel-form-total_cost_pence").fill("15.00");
  await page.locator("#fuel-form button").click();
  await page.locator("#error").waitFor({ state: "visible" });
  assert.equal(
    await page.locator("#fuel-form-total_cost_pence").inputValue(),
    "15.00",
  );
  assert.equal(
    await page.locator("#error").evaluate((e) => e === document.activeElement),
    true,
  );
  // Cancel and confirm record deletion.
  await page.locator("#expense-list button.danger").click();
  await page.locator("#confirm button[value=cancel]").click();
  assert.equal(await page.locator("#expense-list tbody tr").count(), 1);
  await page.locator("#expense-list button.danger").click();
  await Promise.all([
    page.waitForResponse((r) => r.request().method() === "DELETE"),
    page.locator("#confirm button[value=delete]").click(),
  ]);
  await ready();
  assert.match(await page.locator("#expense-list").textContent(), /No expenses recorded/);
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  assert.deepEqual(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
    [],
  );
  if (process.env.SCREENSHOT_PATH)
    await page.screenshot({
      path: process.env.SCREENSHOT_PATH,
      fullPage: true,
    });
  await page.setViewportSize({ width: 1280, height: 900 });
  assert.deepEqual(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
    [],
  );
  // Vehicle cascade is explicit, cancel safe, then final deletion returns to empty fleet.
  await page.locator("#delete-vehicle").click();
  assert.match(
    await page.locator("#confirm-text").textContent(),
    /ALL its fuel and expense/,
  );
  await page.locator("#confirm button[value=cancel]").click();
  await page.locator("#delete-vehicle").click();
  await Promise.all([
    page.waitForResponse((r) => r.request().method() === "DELETE"),
    page.locator("#confirm button[value=delete]").click(),
  ]);
  await ready();
  assert.match(await page.locator("#vehicle-detail").textContent(), /empty/);
  // Exercise lifecycle, tank updates and stale responses with two real resources.
  const request = async (path, method, body) =>
    page.evaluate(
      async ({ path, method, body }) => {
        const response = await fetch("/api" + path, {
          method,
          headers: {
            "Content-Type": "application/json",
            "X-Odometer-Request": "1",
          },
          body: JSON.stringify(body),
        });
        if (!response.ok) throw new Error(await response.text());
        return response.json();
      },
      { path, method, body },
    );
  const a = await request("/vehicles", "POST", {
    registration: "CONTEXT A",
    initial_mileage: 0,
  });
  const b = await request("/vehicles", "POST", {
    registration: "CONTEXT B",
    initial_mileage: 0,
  });
  await request(`/vehicles/${a.id}/expenses`, "POST", {
    date: "2026-10-20",
    category: "OTHER",
    amount_pence: 999,
  });
  await page.reload();
  await ready();
  let release, held;
  const gate = new Promise((resolve) => (release = resolve));
  const received = new Promise((resolve) => (held = resolve));
  await page.route(`**/api/summary?*vehicle_id=${a.id}`, async (route) => {
    const response = await route.fetch();
    held();
    await gate;
    await route.fulfill({ response });
  });
  await page.locator("#vehicle").selectOption(a.id);
  await received;
  await page.locator("#vehicle").selectOption(b.id);
  await ready();
  release();
  await page.unrouteAll({ behavior: "wait" });
  assert.match(await page.locator("#context").textContent(), /CONTEXT B/);
  assert.doesNotMatch(await page.locator("#metrics").textContent(), /£9.99/);
  await page.locator("#tank-form input").fill("50");
  await page.locator("#tank-form button").click();
  await ready();
  assert.match(await page.locator("#vehicle-detail").textContent(), /50 litre/);
  await page.locator("[data-status=SOLD]").click();
  await ready();
  assert.equal(await page.locator("#vehicle").inputValue(), "");
  await page.locator("#inactive").check();
  await ready();
  await page.locator("#vehicle").selectOption(b.id);
  await ready();
  assert.match(await page.locator("#context").textContent(), /SOLD/);
  await page.locator("[data-status=ARCHIVED]").click();
  await ready();
  assert.match(await page.locator("#context").textContent(), /ARCHIVED/);
  await request(`/vehicles/${a.id}`, "DELETE");
  await request(`/vehicles/${b.id}`, "DELETE");
  assert.deepEqual(failures, []);
  assert.deepEqual(external, []);
  console.log(
    "PASS: empty garage, keyboard, vehicle creation, exact money, partial-fill MPG, expense, XSS text, validation, cancel/delete, cascade, mobile overflow, local-only requests",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
