/* Requires the app on :8878 with disposable data; NODE_PATH as in smoke.md. */
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const AxeBuilder = require("@axe-core/playwright").default;
(async () => {
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({viewport: {width: 320, height: 800}, acceptDownloads: true});
  const page = await context.newPage();
  const external = [];
  page.on("request", r => { if (!r.url().startsWith("http://127.0.0.1:8878")) external.push(r.url()); });
  await page.goto("http://127.0.0.1:8878");
  for (const kind of ["json", "csv", "backup"]) {
    const button = page.locator(`[data-download=${kind}]`);
    await button.focus();
    const promise = page.waitForEvent("download");
    await page.keyboard.press("Enter");
    const download = await promise;
    assert.equal(await download.failure(), null);
    assert.match(download.suggestedFilename(), /^odometer-\w+-\d{4}-\d{2}-\d{2}\.(json|csv|sqlite3)$/);
    const bytes = await fs.readFile(await download.path());
    if (kind === "json") assert.equal(JSON.parse(bytes).format_version, 1);
    if (kind === "backup") assert.equal(bytes.subarray(0, 15).toString(), "SQLite format 3");
    assert.equal(await button.evaluate(el => el === document.activeElement), true);
    assert.match(await page.locator("#download-status").textContent(), /check your browser downloads/);
  }
  for (const dataset of ["fuel", "expenses"]) {
    await page.locator("#csv-record-type").selectOption(dataset);
    const promise = page.waitForEvent("download");
    await page.locator("[data-download=csv]").click();
    assert.match((await promise).suggestedFilename(), new RegExp(`odometer-${dataset}-`));
  }
  await page.route("**/api/downloads/json", route => route.fulfill({status: 500, body: "error"}));
  await page.locator("[data-download=json]").click();
  await page.waitForFunction(() => document.getElementById("download-error").textContent.includes("Try again"));
  assert.equal(await page.locator("#download-error").getAttribute("role"), "alert");
  assert.equal(await page.locator("[data-download=json]").getAttribute("aria-disabled"), null);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  const results = await new AxeBuilder({page}).include("section[aria-labelledby=data-tools-heading]").analyze();
  assert.deepEqual(results.violations, []);
  assert.deepEqual(external, []);
  await browser.close();
  console.log("PASS: five downloads, file bytes/names, keyboard focus, errors, 320px reflow, axe and local requests");
})().catch(error => { console.error(error); process.exit(1); });
