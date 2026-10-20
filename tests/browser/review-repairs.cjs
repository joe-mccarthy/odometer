/* Run against tests/browser/review-repairs-server.py's disposable fixture on :8899; see smoke.md. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:320,height:800}});
 const errors=[],external=[];
 const origin=process.env.ORIGIN || 'http://127.0.0.1:8899';
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(new URL(r.url()).origin!==origin)external.push(r.url());});
 await page.goto(origin);
 await page.locator('#status').filter({hasText:'Up to date'}).waitFor();
 const v=await page.evaluate(async()=> (await (await fetch('/api/vehicles')).json()).find(v=>v.registration==='EXACT48'));
 await page.locator('#vehicle').selectOption(v.id);
 const amounts=['9007199254740990','9007199254740993','9223372036854775807'];
 async function save(kind){
   await page.getByRole('button',{name:'Save changes',exact:true}).click();
   await page.locator('#status').filter({hasText:kind==='fuel'?'Fuel updated':'Expense updated'}).waitFor();
 }
 for(const [i,amount] of amounts.entries())for(const kind of ['fuel','expense']){
   const field=kind==='fuel'?'total_cost_pence':'amount_pence';
   const host=page.locator(`#${kind}-list`);
   await host.locator(`[data-edit-id="shared${i}"]`).click();
   assert.equal(await page.locator(`#edit-${field}`).inputValue(),`${BigInt(amount)/100n}.${(BigInt(amount)%100n).toString().padStart(2,'0')}`);
   await page.locator('#edit-notes').fill(`notes ${kind} ${i}`);
   const sent=page.waitForRequest(r=>r.method()==='PUT');
   await save(kind);
   const request=await sent;
   assert.match(request.postData(),new RegExp(`"${field}":${amount}(?:,|})`));
   const response=await page.evaluate(async({v,kind})=>(await (await fetch(`/api/vehicles/${v.id}/${kind==='fuel'?'fuel':'expenses'}`)).json()),{v,kind});
   const row=response.find(r=>r.id===`shared${i}`);
   assert.equal(row[field+'_exact'],amount);
   if(kind==='fuel')assert.equal(row.price_per_litre_pence,null);
   assert.equal(await host.locator(`[data-edit-id="shared${i}"]`).evaluate(e=>e===document.activeElement),true);
 }
 // Changed amounts beyond safe numeric entry must fail before a write.
 await page.locator('#expense-list [data-edit-id="shared1"]').click();
 await page.locator('#edit-amount_pence').fill('90071992547409.95');
 await page.getByRole('button',{name:'Save changes',exact:true}).click();
 await page.getByRole('dialog').getByRole('alert').filter({hasText:'Amount is too large'}).waitFor();
 assert.equal(await page.locator('#edit-amount_pence').inputValue(),'90071992547409.95');
 await page.locator('#edit-amount_pence').fill('12.34');
 await save('expense');
 // An edited expense leaves its filtered view while the same-ID fuel stays visible.
 await page.locator('#expense-filters [name=date_from]').fill('2026-01-01');
 await page.locator('#expense-filters').getByRole('button',{name:'Apply filters'}).click();
 await page.locator('#expense-list [data-edit-id="shared0"]').click();
 await page.locator('#edit-date').fill('2024-01-01');
 await save('expense');
 assert.equal(await page.locator(':focus').getAttribute('id'),'expense-list');
 assert.match(await page.locator('#status').textContent(),/outside this view/);
 assert.equal(await page.locator('#fuel-list [data-edit-id="shared0"]').count(),1);
 // Same overlap, but off page after date correction instead of excluded by filter.
 await page.locator('#expense-filters').getByRole('button',{name:'Clear filters'}).click();
 await page.locator('#expense-list [data-edit-id="shared2"]').click();
 await page.locator('#edit-date').fill('2023-01-01');
 await save('expense');
 assert.equal(await page.locator(':focus').getAttribute('id'),'expense-list');
 assert.match(await page.locator('#status').textContent(),/outside this view/);
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 console.log('PASS: exact numeric JSON for safe/unsafe/int64 amounts, notes-only fuel/expense, imported null, changed validation, overlapping-ID focus and filtered/off-page fallbacks, 320px, local-only');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
