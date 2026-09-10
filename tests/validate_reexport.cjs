const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const errors=[];page.on('response',async r=>{if(r.url().includes('/api/jobs'))console.log(r.url(),await r.text());});page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.TEST_URL||'http://localhost:8768');await page.locator('#mobile-toggle').click();
 const n=page.locator('[data-aspect="0"]');await n.scrollIntoViewIfNeeded();await n.tap();assert.equal(await n.getAttribute('aria-pressed'),'false');await n.click();assert.equal(await n.getAttribute('aria-pressed'),'true');await n.focus();await page.keyboard.press('Space');assert.equal(await n.getAttribute('aria-pressed'),'false');
 await page.locator('.compass-rose').scrollIntoViewIfNeeded();await page.screenshot({path:'rose-validation.png'});
 await page.locator('[data-tab="export"]').click();await page.locator('#bbox-west').locator('..').count();await page.locator('details.coordinates summary').click();for(const [id,value] of Object.entries({west:'6.84',south:'45.90',east:'6.90',north:'45.94'}))await page.locator('#bbox-'+id).fill(value);await page.locator('#apply-bounds').click();await page.locator('#zoom-min').selectOption('11');await page.locator('#zoom-max').selectOption('11');
 await page.waitForFunction(()=>!document.querySelector('#export-button').disabled);await page.locator('#export-button').click();await page.locator('#xyz-result').waitFor({state:'visible',timeout:120000});const original=await page.locator('#xyz-url').inputValue();const rect=await page.evaluate(()=>({bounds:state.bounds,layer:rectangle._leaflet_id}));
 await page.locator('[data-tab="filters"]').click();await page.locator('#alt-min').evaluate(el=>{el.value='2000';el.dispatchEvent(new Event('input',{bubbles:true}));});assert.deepEqual(await page.evaluate(()=>({bounds:state.bounds,layer:rectangle._leaflet_id})),rect);
 await page.locator('[data-tab="export"]').click();await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/jobs')&&r.request().method()==='POST'),page.locator('#update-link').click()]);await page.waitForFunction(()=>state.job===null);await page.locator('#xyz-result').waitFor({state:'visible',timeout:120000});assert.equal(await page.locator('#xyz-url').inputValue(),original);
 await page.locator('#new-link').click();await page.waitForFunction(old=>document.querySelector('#xyz-url').value!==old,original,{timeout:120000});await page.locator('#xyz-result').waitFor({state:'visible',timeout:120000});assert.notEqual(await page.locator('#xyz-url').inputValue(),original);await page.screenshot({path:'reexport-validation.png'});
 for(const width of [320,390,1440]){await page.setViewportSize({width,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
 assert.deepEqual(errors,[]);console.log('PASS: rose tap/click/keyboard, rectangle after slider, same URL update, new URL, mobile overflow, no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
