// Run with Playwright installed; STATISTICS_CHROMIUM_PATH can select a system Chromium.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const {createServer}=require('node:http');
const {readFile}=require('node:fs/promises');
const {resolve,sep,extname}=require('node:path');
const {chromium}=require('playwright');

const root=resolve(__dirname,'../../lab');
let server,browser,base;
before(async()=>{
  const types={'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json'};
  server=createServer(async(req,res)=>{
    const path=resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
    if(!path.startsWith(root+sep)){res.writeHead(403).end();return;}
    try{
      const content=await readFile(path);
      res.writeHead(200,{'Content-Type':types[extname(path)]||'application/octet-stream'}).end(content);
    }catch{res.writeHead(404).end();}
  });
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  base='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({headless:true,
    ...(process.env.STATISTICS_CHROMIUM_PATH?{executablePath:process.env.STATISTICS_CHROMIUM_PATH}:{})});
});
after(async()=>{
  if(browser)await browser.close();
  if(server)await new Promise(done=>server.close(done));
});
async function mobile(t){
  const context=await browser.newContext({viewport:{width:390,height:844}});
  t.after(()=>context.close());
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  t.after(()=>assert.deepEqual(errors,[]));
  return page;
}
async function ready(page){
  await page.goto(base+'/statistics.html');
  await page.waitForFunction(()=>document.querySelector('#siCompositeFactorTable tbody')&&
    document.querySelector('#siHeatFactorTable tbody'));
}
async function selectedPointVisible(page,id){
  return page.evaluate(id=>{
    const host=document.getElementById(id),marker=host.querySelector('circle:last-of-type');
    const clip=host.getBoundingClientRect(),dot=marker.getBoundingClientRect();
    return dot.left>=clip.left&&dot.right<=clip.right;
  },id);
}
test('mobile recovery comparison loads only on demand, uses a frozen date and preserves V2',async t=>{
  const page=await mobile(t),requests=[];
  page.on('request',request=>requests.push(request.url()));
  await ready(page);
  const v2=await page.locator('#siForwardTable').innerText();
  assert.equal(requests.some(url=>url.includes('recovery-v3')),false);
  await page.locator('#siRecovery summary').click();
  await page.locator('#siRecoveryContent').waitFor({state:'visible'});
  assert.match(await page.locator('#siRecoveryCoverage').innerText(),/97,67%/);
  assert.match(await page.locator('#siRecoveryStatus').innerText(),/2026-10-23/);
  assert.match(await page.locator('#siRecoveryTable').innerText(),/V3/);
  assert.ok(await page.locator('#siRecoveryCoverage').evaluate(table=>table.scrollWidth<=table.clientWidth));
  await page.selectOption('#siRecoveryHorizon','20');
  assert.match(await page.locator('#siRecoveryStatus').innerText(),/još nisu dospjeli/);
  assert.match(await page.locator('#siRecoveryTable').innerText(),/—/);
  assert.equal(await page.locator('#siForwardTable').innerText(),v2);
  assert.ok(await page.evaluate(()=>document.body.scrollWidth<=innerWidth));
});
test('failed V3 request leaves V2 usable and can be retried',async t=>{
  const page=await mobile(t);let attempts=0;
  await page.route('**/data/recovery-v3/comparison.json',route=>++attempts===1
    ?route.fulfill({status:503,body:'unavailable'}):route.continue());
  await ready(page);
  await page.locator('#siRecovery summary').click();
  await page.waitForFunction(()=>document.getElementById('siRecoveryStatus').textContent.includes('HTTP 503'));
  assert.equal(await page.locator('#siForwardTable tbody tr').count(),15);
  assert.equal(await page.locator('#siRecoveryContent').isVisible(),false);
  await page.locator('#siRecovery summary').click();
  await page.locator('#siRecovery summary').click();
  await page.locator('#siRecoveryContent').waitFor({state:'visible'});
  assert.equal(attempts,2);
});
test('stale publication is visible while valid statistics remain available',async t=>{
  const page=await mobile(t);
  // Pin the stale source as well as the clock: the checked-in latest advances daily.
  await page.route('**/data/publication.json',route=>route.fulfill({
    contentType:'application/json',body:JSON.stringify({sessionDate:'2026-10-23'})
  }));
  await page.clock.setFixedTime(new Date('2026-10-27T00:00:00Z'));
  await ready(page);
  await page.waitForFunction(()=>document.getElementById('eodFreshness').dataset.state==='stale');
  assert.match(await page.locator('#eodFreshness').innerText(),/Očekivana sesija: 2026-10-26/);
  assert.equal(await page.locator('#siForwardTable tbody tr').count(),15);
});
test('Statistics discloses missing tracked-outcome quotes separately from primary source coverage',async t=>{
  const page=await mobile(t);
  const data=JSON.parse(await readFile(resolve(root,'data/trend-birth-stage-forward.json'),'utf8'));
  data.outcomeTracking={schemaVersion:'trend-birth-outcome-tracking-v1',asOf:data.asOf,
    startAfterSessionDate:'2026-09-23',enabled:true,status:'partial',trackedCount:1177,
    primaryCoveredCount:1122,supplementalCount:50,missingCount:5,calibrationApproved:false,historyBackfilled:false};
  await page.route('**/data/trend-birth-stage-forward.json',route=>route.fulfill({json:data}));
  await ready(page);
  await page.waitForFunction(()=>document.getElementById('siForwardQuality').textContent.includes('50 dodatnih'));
  assert.match(await page.locator('#siForwardQuality').innerText(),/5 cijena nedostaje/);
  assert.equal(await page.locator('#siForwardTable tbody tr').count(),15);
});
test('mobile shows the latest markers and follows a selected historical EOD without moving the page',async t=>{
  const page=await mobile(t);await ready(page);
  assert.equal(await selectedPointVisible(page,'siHeatChart'),true);
  assert.equal(await selectedPointVisible(page,'siCompositeChart'),true);
  assert.ok(await page.evaluate(()=>document.body.scrollWidth<=innerWidth));
  const scrollY=await page.evaluate(()=>window.scrollY);
  await page.locator('#siHeatPoint').evaluate(input=>{input.value='12';input.dispatchEvent(new Event('input'));});
  assert.equal(await selectedPointVisible(page,'siHeatChart'),true);
  assert.equal(await selectedPointVisible(page,'siCompositeChart'),true);
  assert.equal(await page.evaluate(()=>window.scrollY),scrollY);
  assert.match(await page.locator('#siHeatSelected').textContent(),/^2026-10-12/);
  assert.match(await page.locator('#siCompositeSelected').textContent(),/^2026-10-12/);
});
test('date and range remain synchronized while ETF proxy stays independent',async t=>{
  const page=await mobile(t);await ready(page);
  await page.locator('#siCompositePoint').evaluate(input=>{input.value='14';input.dispatchEvent(new Event('input'));});
  assert.match(await page.locator('#siHeatSelected').textContent(),/^2026-10-14/);
  await page.selectOption('#siHeatRange','3m');
  assert.equal(await page.locator('#siCompositeRange').inputValue(),'3m');
  assert.match(await page.locator('#siCompositeSelected').textContent(),/^2026-10-14/);
  await page.selectOption('#siCompositeSeries','proxy');
  const proxyDate=await page.locator('#siCompositeSelected').textContent();
  await page.locator('#siHeatPoint').evaluate(input=>{input.value='12';input.dispatchEvent(new Event('input'));});
  assert.equal(await page.locator('#siCompositeSelected').textContent(),proxyDate);
  await page.selectOption('#siCompositeSeries','actual');
  const heatDate=(await page.locator('#siHeatSelected').textContent()).slice(0,10);
  assert.equal((await page.locator('#siCompositeSelected').textContent()).slice(0,10),heatDate);
  assert.equal(await selectedPointVisible(page,'siHeatChart'),true);
});
test('a late calendar response preserves the already selected ETF source',async t=>{
  const page=await mobile(t);
  let release;
  const gate=new Promise(done=>{release=done;});
  t.after(()=>release());
  await page.route('**/data/trend-birth-stage-forward.json',async route=>{await gate;await route.continue();});
  await page.goto(base+'/statistics.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#siCompositeFactorTable tbody'));
  await page.selectOption('#siCompositeSeries','proxy');
  release();
  await page.waitForFunction(()=>document.querySelector('#siHeatFactorTable tbody'));
  assert.match(await page.locator('#siHeatSyncStatus').textContent(),/isključeno/);
  assert.equal(await page.locator('#siCompositeSeries').inputValue(),'proxy');
});
test('unavailable calendar keeps heat evidence visible without claiming verified continuity',async t=>{
  const page=await mobile(t);
  await page.route('**/data/trend-birth-stage-forward.json',route=>route.fulfill({status:503,body:'Unavailable'}));
  await ready(page);
  assert.match(await page.locator('#siForwardStatus').textContent(),/503/);
  assert.match(await page.locator('#siHeatCoverage').textContent(),/kontinuitet nije potvrđen/);
  assert.match(await page.locator('#siHeatScore').textContent(),/\d.*\/ 100/);
  assert.equal(await selectedPointVisible(page,'siHeatChart'),true);
});
