/* Disposable local server: CHART_BASE=http://127.0.0.1:8896 NODE_PATH=... node tests/browser/charts.cjs */
const { chromium } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.CHART_BASE || 'http://127.0.0.1:8896';
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({viewport:{width:320,height:800}});
  const page = await context.newPage();
  const external=[], errors=[];
  page.on('request', r => {if(new URL(r.url()).origin !== base) external.push(r.url());});
  page.on('pageerror', e=>errors.push(e.message));
  const ready=()=>page.locator('#status').filter({hasText:'Up to date.'}).waitFor();
  await page.goto(base); await ready();
  const api=async(path,method='GET',body)=> {
    const r=await page.request.fetch(base+'/api'+path,{method,data:body,headers:{'X-Odometer-Request':'1','Origin':base}});
    assert(r.ok(),await r.text()); return r.json();
  };
  const v=await api('/vehicles','POST',{registration:'CHART FIXTURE',initial_mileage:1000,fuel_tank_litres:60});
  try {
    for(const [date,miles] of [['2026-01-01',1000],['2026-02-01',1100]])
      await api(`/vehicles/${v.id}/fuel`,'POST',{date,odometer_miles:miles,litres:10,total_cost_pence:1501,is_full_tank:true});
    // Existing deduplication treats this FUEL expense alongside fuel logs.
    await api(`/vehicles/${v.id}/expenses`,'POST',{date:'2026-02-01',category:'FUEL',amount_pence:1501});
    await api(`/vehicles/${v.id}/expenses`,'POST',{date:'2026-02-01',category:'SERVICE',amount_pence:12345});
    await page.reload(); await ready();
    await page.locator('#vehicle').selectOption(v.id); await ready();
    await page.locator('#year').fill('2026'); await page.locator('#year').dispatchEvent('change'); await ready();
    const summary=await api(`/summary?vehicle_id=${v.id}&year=2026`);
    const fmt=p=>new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP'}).format(p/100);
    for(const [index,key] of [[0,'total_spend_pence'],[1,'miles_driven']]) {
      const rows=page.locator('figure').nth(index).locator('.chart-row');
      assert.equal(await rows.count(),summary.monthly.length);
      for(let i=0;i<summary.monthly.length;i++) {
        const r=summary.monthly[i];
        const value=r[key]==null?'No reading/data':key==='total_spend_pence'?fmt(r[key]):`${r[key]} miles`;
        assert.match(await rows.nth(i).textContent(),new RegExp(r.period));
        assert.equal(await rows.nth(i).locator('span').last().textContent(),value);
        assert((await page.locator('#monthly-values').textContent()).includes(value.replace(' miles','')));
        if(r[key]==null) assert.equal(await rows.nth(i).locator('.chart-bar').count(),0);
      }
    }
    await page.locator('figure a').first().focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'),'monthly-values');
    for (const width of [320,800,1280]) {
      await page.setViewportSize({width,height:900});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      assert.deepEqual((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations,[]);
    }
    await api(`/vehicles/${v.id}`,'PATCH',{status:'SOLD'});
    await page.locator('#inactive').check(); await ready();
    assert.match(await page.locator('figcaption').first().textContent(),/including sold and archived/);
    await page.locator('#year').fill('2025'); await page.locator('#year').dispatchEvent('change'); await ready();
    assert.match(await page.locator('figcaption').first().textContent(),/2025/);
    assert.match(await page.locator('figure').first().textContent(),/£0.00/);
    assert.equal(await page.locator('figure').nth(1).locator('.chart-bar').count(),0);
    // Empty and one-period response contracts, without manufacturing absent months.
    for(const monthly of [[],[summary.monthly[0]]]) {
      await page.route('**/api/summary?*',r=>r.fulfill({json:{...summary,monthly}}));
      await page.locator('#refresh').click(); await ready();
      assert.equal(await page.locator('figure').first().locator('.chart-row').count(),monthly.length);
      if(!monthly.length) assert.match(await page.locator('figure').first().textContent(),/No monthly data/);
      await page.unroute('**/api/summary?*');
    }
    // Hold an old-year response while a newer scope completes.
    let release, arrived;
    const gate = new Promise(r => release = r);
    const received = new Promise(r => arrived = r);
    await page.route('**/api/summary?*', async route => {
      if (new URL(route.request().url()).searchParams.get('year') !== '2024') return route.continue();
      const response = await route.fetch(); arrived(); await gate; await route.fulfill({response});
    });
    await page.locator('#year').fill('2024'); await page.locator('#year').dispatchEvent('change'); await received;
    await page.locator('#year').fill('2026'); await page.locator('#year').dispatchEvent('change'); await ready();
    release(); await page.unrouteAll({behavior:'wait'});
    assert.match(await page.locator('figcaption').first().textContent(), /2026/);
    assert.match(await page.locator('figure').first().textContent(), /£15.01/);
    if(process.env.SCREENSHOT_PATH) await page.screenshot({path:process.env.SCREENSHOT_PATH,fullPage:true});
    await page.route('**/api/summary?*',r=>r.fulfill({status:500,json:{error:{message:'Test failure'}}}));
    await page.locator('#refresh').click(); await page.locator('#error').waitFor({state:'visible'});
    assert.equal(await page.locator('figure').count(),0);
    assert.deepEqual(external,[]); assert.deepEqual(errors,[]);
    console.log('PASS 12.1–12.5: service/table/chart parity, dedup fixture, zero/null, keyboard, 320/800/1280 reflow, axe, inactive/year, empty/one period, failure clearing, local requests');
  } finally { await api(`/vehicles/${v.id}`,'DELETE'); await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
