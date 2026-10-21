/* Run after seeding test_history_pagination.seed; PORT defaults to 8877. */
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 320, height: 844 },
  });
  const page = await context.newPage();
  const origin = `http://127.0.0.1:${process.env.PORT || 8877}`;
  const errors = [],
    external = [],
    payloads = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (new URL(r.url()).origin !== origin) external.push(r.url());
  });
  page.on("response", async (r) => {
    if (/\/(fuel|expenses)\?/.test(r.url()) && r.status() === 200)
      payloads.push(await r.json());
  });
  await page.goto(origin);
  await page.locator("#status").filter({ hasText: "Up to date." }).waitFor();
  const options = await page
    .locator("#vehicle option")
    .evaluateAll((es) =>
      es.map((e) => ({ value: e.value, text: e.textContent })),
    );
  const populated = options.find((o) => o.text.includes("PAGE 1")).value;
  const empty = options.find((o) => o.text.includes("EMPTY 2")).value;
  await page.locator("#vehicle").selectOption(populated);
  await page.locator("#fuel-range").filter({ hasText: "1–50 fuel" }).waitFor();
  await page
    .locator("#expense-range")
    .filter({ hasText: "1–50 expenses" })
    .waitFor();
  assert(await page.locator("#fuel-previous").isDisabled());
  assert(await page.locator("#expense-previous").isDisabled());
  for (const kind of ["fuel", "expense"]) {
    for (let n = 1; n < 25; n++) {
      await page.locator(`#${kind}-next`).focus();
      await page.keyboard.press("Enter");
      const end = Math.min((n + 1) * 50, 1205);
      await page
        .locator(`#${kind}-range`)
        .filter({ hasText: `${n * 50 + 1}–${end}` })
        .waitFor();
      assert.equal(
        await page.locator(`#${kind}-list tbody tr`).count(),
        end - n * 50,
      );
    }
    assert(await page.locator(`#${kind}-next`).isDisabled());
    assert.equal(
      await page.locator(":focus").getAttribute("id"),
      `${kind}-range`,
    );
    await page.locator(`#${kind}-previous`).focus();
    await page.keyboard.press("Enter");
    await page
      .locator(`#${kind}-range`)
      .filter({ hasText: "1151–1200" })
      .waitFor();
    assert.equal(
      await page.locator(":focus").getAttribute("id"),
      `${kind}-previous`,
    );
  }
  const firstPass = payloads.filter((p) => p.offset === 1200);
  assert.equal(firstPass.length, 2);
  for (const prefix of ["f", "e"]) {
    const ids = payloads
      .filter((p) => p.items[0]?.id.startsWith(prefix))
      .slice(0, 25)
      .flatMap((p) => p.items.map((r) => r.id));
    assert.equal(new Set(ids).size, 1205);
    assert.deepEqual(
      ids,
      Array.from(
        { length: 1205 },
        (_, i) => prefix + String(1204 - i).padStart(5, "0"),
      ),
    );
  }
  await page.locator("#expense-filters select").selectOption("MOT");
  await page
    .locator("#expense-filters button")
    .filter({ hasText: "Apply filters" })
    .click();
  await page
    .locator("#expense-range")
    .filter({ hasText: "0 expenses" })
    .waitFor();
  assert.match(await page.locator("#expense-scope").textContent(), /MOT/);
  assert(await page.locator("#expense-next").isDisabled());
  await page.locator("#expense-date_from").fill("2026-02-01");
  await page.locator("#expense-date_to").fill("2026-01-01");
  await page
    .locator("#expense-filters button")
    .filter({ hasText: "Apply filters" })
    .click();
  await page.locator("#error").waitFor({ state: "visible" });
  assert.match(
    await page.locator("#expense-range").textContent(),
    /0 expenses/,
  );
  assert.equal(
    await page.locator("#expense-date_from").inputValue(),
    "2026-02-01",
  );
  await page
    .locator("#expense-filters button")
    .filter({ hasText: "Clear filters" })
    .click();
  await page
    .locator("#expense-range")
    .filter({ hasText: "1–50 expenses" })
    .waitFor();
  await page.locator("#vehicle").selectOption(empty);
  await page
    .locator("#expense-range")
    .filter({ hasText: "0 expenses" })
    .waitFor();
  await page.locator("#vehicle").selectOption(populated);
  await page.locator("#fuel-range").filter({ hasText: "1–50 fuel" }).waitFor();
  await page.locator("#fuel-next").click();
  await page
    .locator("#fuel-range")
    .filter({ hasText: "51–100 fuel" })
    .waitFor();
  await page.locator("#inactive").check();
  await page.locator("#fuel-range").filter({ hasText: "1–50 fuel" }).waitFor();
  await page.locator("#fuel-next").click();
  await page
    .locator("#fuel-range")
    .filter({ hasText: "51–100 fuel" })
    .waitFor();
  await page.locator("#year").fill("2025");
  await page.locator("#year").press("Tab");
  await page.locator("#status").filter({ hasText: "Up to date." }).waitFor();
  assert.match(await page.locator("#fuel-range").textContent(), /51–100/);
  const axe = await new AxeBuilder({ page }).analyze();
  assert.deepEqual(axe.violations, []);
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  console.log(
    JSON.stringify({
      result: "PASS",
      rowsPerKind: 1205,
      maxPayload: Math.max(...payloads.map((p) => p.items.length)),
      keyboard: true,
      viewport: 320,
      axeViolations: axe.violations.length,
      externalRequests: external.length,
    }),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
