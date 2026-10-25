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
