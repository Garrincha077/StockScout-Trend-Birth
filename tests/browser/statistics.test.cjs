// Run with Playwright installed; STATISTICS_CHROMIUM_PATH can select a system Chromium.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const {createServer}=require('node:http');
const {createHash}=require('node:crypto');
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
test('Early Trend Birth statistics separate horizons and describe a later median honestly',async t=>{
  const page=await mobile(t);
  const forward=JSON.parse(await readFile(resolve(root,'data/trend-birth-stage-forward.json'),'utf8'));
  const pending={observed:0,matured:0,pending:4,leadersCaptured:0,leadersMissed:0,leaderOpportunities:0,
    belowUniverseMedian:0,excessPct:null};
  const measured={...pending,observed:4,matured:5,pending:0,leadersCaptured:1,leadersMissed:1,
    leaderOpportunities:2,belowUniverseMedian:2,excessPct:-1};
  const row=early=>({early,daily4:pending,weekly:pending});
  forward.earlyTrend={schemaVersion:'early-trend-outcomes-v1',observedSessions:4,lead:{
    daily4:{matched:2,earlier:0,same:0,later:2,medianSessions:-3},weekly:{matched:0}
  },horizons:{20:row(measured),63:row(pending),126:row(pending),252:row(pending)}};
  const emptyMatch={observed:0,pending:0,missingPairPrices:0,observedDates:0,positiveDates:0,
    signalReturnPct:null,controlReturnPct:null,differencePp:null};
  const pendingMatch={...emptyMatch,pending:4};
  const measuredMatch={...emptyMatch,observed:3,missingPairPrices:1,observedDates:2,positiveDates:0,
    signalReturnPct:.5,controlReturnPct:.75,differencePp:-.25};
  const matchGroup={signals:7,signalDates:3,paired:4,missingFeatures:2,unmatched:1,
    outcomes:{5:measuredMatch,20:pendingMatch,63:pendingMatch,126:pendingMatch,252:pendingMatch}};
  forward.earlyTrend.matched={schemaVersion:'trend-birth-matched-cohorts-v1',asOf:forward.asOf,
    earlyObservedSessions:4,dailyObservedSessions:32,lookbackSessions:20,maxPriceRatio:2,maxMomentumGapPp:10,
    groups:{early:matchGroup,daily4:{...matchGroup,signals:12,unmatched:6}}};
  await page.route('**/data/trend-birth-stage-forward.json',route=>route.fulfill({json:forward}));
  await ready(page);
  await page.locator('#siEarly').waitFor();
  assert.match(await page.locator('#siEarlyLead').innerText(),/kasnije za 3 sesija/);
  assert.equal(await page.locator('#siEarlyTable tbody tr').count(),3);
  assert.match(await page.locator('#siEarlyTable').innerText(),/4 \/ 5/);
  await page.locator('#siMatched').waitFor();
  assert.match(await page.locator('#siMatchedCoverage').innerText(),/4 \/ 7 uparenih/);
  assert.match(await page.locator('#siMatchedDates').innerText(),/4 na čekanju/);
  assert.equal(await page.locator('#siMatchedResults').isVisible(),false);
  await page.selectOption('#siMatchedCohort','daily4');
  assert.match(await page.locator('#siMatchedCoverage').innerText(),/32 arhivirane sesije · 4 \/ 12/);
  await page.selectOption('#siMatchedHorizon','5');
  assert.match(await page.locator('#siMatchedDates').innerText(),/3 s ishodom · 0 na čekanju · 1 bez cijene za par/);
  assert.match(await page.locator('#siMatchedDifference').innerText(),/[-−]0,25 p. b./);
  assert.ok(await page.evaluate(()=>document.body.scrollWidth<=innerWidth));
  await page.selectOption('#siEarlyHorizon','252');
  assert.match(await page.locator('#siEarlyMaturity').innerText(),/Još nema dospjelih ishoda za 252 sesija/);
  assert.match(await page.locator('#siEarlyTable').innerText(),/252D · Trend Birth/);
});

test('Kell Swing separates archived fills from reconstructed returns and applies selected costs',async t=>{
  const page=await mobile(t);
  const forward=JSON.parse(await readFile(resolve(root,'data/trend-birth-stage-forward.json'),'utf8'));
  const history=JSON.parse(await readFile(resolve(root,'data/trend-birth-market-internals.json'),'utf8'));
  const source={sessionDate:history.latestSessionDate,runId:history.latestRunId,unifiedManifestSha256:'b'.repeat(64)};
  const snapshotId=source.runId+'--'+'a'.repeat(64);
  const outcome={selected:3,pending:3,missingBars:0,unmatchedClose:0,corporateAction:0,invalidLevels:0,
    evaluable:0,fills:0,netRByCost:{'20bp':null,'50bp':null}};
  const filled={...outcome,pending:0,evaluable:3,fills:2,netRByCost:{'20bp':[-.3,.5],'50bp':[-.5,.3]}};
  const detailedPending={...outcome,signalDates:1,fillDates:0,ambiguousFills:0};
  const detailedFilled={...filled,signalDates:1,fillDates:1,ambiguousFills:1};
  const empty={...detailedPending,selected:0,pending:0,signalDates:0};
  const emptyHorizons={5:empty,10:empty,20:empty};
  const groups=(outcomes,setup,regime)=>({
    outcomes,bySetup:Object.fromEntries(['ema_crossback','wedge_pop','base_n_break','buyable_gap_proxy','tightening']
      .map(key=>[key,key===setup?outcomes:emptyHorizons])),
    byBreadth:Object.fromEntries(['rising','steady','falling','unknown'].map(key=>[key,key===regime?outcomes:emptyHorizons]))
  });
  const published=groups({5:detailedFilled,10:detailedPending,20:detailedPending},'wedge_pop','falling');
  const historical=groups({5:{...detailedFilled,netRByCost:{'20bp':[.25,.45],'50bp':[.12,.32]}},
    10:detailedPending,20:detailedPending},'ema_crossback','rising');
  const result={pairedDates:1,selectedDates:2,pairedSelectionsPerStrategy:2,returnPctByCost:{
    '20bp':{swing:.25,legacy:-.5,momentum:0},'50bp':{swing:-.05,legacy:-.8,momentum:-.3}
  }};
  const report={schemaVersion:'kell-swing-statistics-v1',asOf:source.sessionDate,horizons:[5,10,20],
    maxSelectionsPerSession:5,published:{firstSession:source.sessionDate,sessionCount:2,...published},
    reconstructed:{sessionCount:3,comparisons:{5:result,10:result,20:result}},
    executionCohorts:{schemaVersion:'kell-swing-execution-cohorts-v1',asOf:source.sessionDate,
      breadthThresholdPp:.5,historical}};
  const schemaVersion='trend-birth-review-research-v1';
  const body=JSON.stringify({schemaVersion,reviewSnapshotId:snapshotId,source,
    reports:{trendBirthForward:forward,kellForward:{swingStatistics:report}}});
  const sha256=createHash('sha256').update(body).digest('hex');
  const path='data/research-runs/'+snapshotId+'--'+sha256+'.json';
  await page.route('**/data/publication.json',route=>route.fulfill({json:{...source,snapshotId,
    schemaVersion:'trend-birth-publication-v1',research:{path,sha256,schemaVersion}}}));
  await page.route('**/'+path,route=>route.fulfill({contentType:'application/json',body}));
  await ready(page);
  await page.locator('#siKellContent').waitFor();
  assert.match(await page.locator('#siKellPublished').innerText(),/2 \/ 3 simuliranih izvršenja/);
  assert.match(await page.locator('#siKellComparison').innerText(),/Kell Swing\s+0,25%/);
  assert.match(await page.locator('#siKellGroupList').innerText(),/Izlaz iz klina/);
  assert.match(await page.locator('#siKellGroupList').innerText(),/1 dvosmislenih/);
  await page.selectOption('#siKellCost','50bp');
  assert.match(await page.locator('#siKellComparison').innerText(),/Kell Swing\s+[-−]0,05%/);
  await page.selectOption('#siKellGroupSample','historical');
  assert.match(await page.locator('#siKellGroupList').innerText(),/Povrat iznad EMA\s+0,12R do 0,32R/);
  await page.selectOption('#siKellGroupDimension','byBreadth');
  assert.match(await page.locator('#siKellGroupList').innerText(),/Rast širine/);
  await page.selectOption('#siKellHorizon','20');
  assert.match(await page.locator('#siKellPublished').innerText(),/3 na čekanju/);
  assert.match(await page.locator('#siKellGroupList').innerText(),/3 na čekanju/);
  assert.ok(await page.evaluate(()=>document.body.scrollWidth<=innerWidth));
});

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
  const internals=JSON.parse(await readFile(resolve(root,'data/trend-birth-market-internals.json'),'utf8'));
  internals.points=internals.points.filter(point=>point.sessionDate<='2026-10-23');
  internals.latestSessionDate=internals.points.at(-1).sessionDate;
  internals.latestRunId=internals.points.at(-1).runId;
  await page.route('**/data/trend-birth-market-internals.json',route=>route.fulfill({
    contentType:'application/json',json:internals
  }));
  await page.clock.setFixedTime(new Date('2026-10-27T00:00:00Z'));
  await ready(page);
  await page.waitForFunction(()=>document.getElementById('eodFreshness').dataset.state==='stale');
  assert.match(await page.locator('#eodFreshness').innerText(),/Prikazana EOD sesija: 2026-10-23/);
  assert.match(await page.locator('#eodFreshness').innerText(),/Očekivana sesija: 2026-10-26/);
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
