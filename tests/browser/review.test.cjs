const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const {createServer}=require('node:http');
const {createHash}=require('node:crypto');
const {readFile}=require('node:fs/promises');
const {resolve,sep,extname}=require('node:path');
const {gzipSync}=require('node:zlib');
const {chromium}=require('playwright');
const root=resolve(__dirname,'../../lab');
let browser,server,base,manifest,bootstrap;
before(async()=>{
  manifest=JSON.parse(await readFile(resolve(root,'data/publication.json'),'utf8'));
  bootstrap=JSON.parse(await readFile(resolve(root,manifest.bootstrapPath),'utf8'));
  const types={'.html':'text/html','.js':'text/javascript','.json':'application/json','.css':'text/css'};
  server=createServer(async(req,res)=>{
    const pathname=new URL(req.url,'http://localhost').pathname;
    const file=resolve(root,'.'+(pathname==='/'?'/index.html':pathname));
    if(!file.startsWith(root+sep)){res.writeHead(403).end();return}
    try{const bytes=await readFile(file);res.writeHead(200,{'Content-Type':types[extname(file)]||'application/octet-stream'}).end(bytes)}
    catch{res.writeHead(404).end()}
  });
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  base='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({headless:true,...(process.env.STATISTICS_CHROMIUM_PATH?{executablePath:process.env.STATISTICS_CHROMIUM_PATH}:{})});
});
after(async()=>{await browser?.close();if(server)await new Promise(done=>server.close(done))});

async function pageFor(t, serviceWorkers='block'){
  const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers});
  t.after(()=>context.close());
  const page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  t.after(()=>assert.deepEqual(errors,[]));
  // A local auth simulator: no mail, RPC or external account is contacted.
  await page.route('https://cdn.jsdelivr.net/**',route=>route.fulfill({contentType:'text/javascript',body:`
    window.authTest={session:null,rows:{A:['AAA'],B:['BBB']},writes:[],listener:null};
    window.supabase={createClient:()=>({
      auth:{getSession:async()=>({data:{session:authTest.session}}),
        onAuthStateChange:listener=>{authTest.listener=listener;return{data:{subscription:{unsubscribe(){}}}}},
        signOut:async()=>{authTest.session=null;authTest.listener('SIGNED_OUT',null);return{}}},
      from:()=>{let owner;const q={select:()=>q,eq:(key,value)=>{if(key==='user_id')owner=value;return q},
        order:async()=>({data:(authTest.rows[owner]||[]).map(ticker=>({ticker}))})};return q},
      rpc:async(name,args)=>{authTest.writes.push(args);const rows=authTest.rows[authTest.session.user.id];
        if(args.p_present&&!rows.includes(args.p_ticker))rows.push(args.p_ticker);return{}}
    })};` }));
  return page;
}

test('initial mobile view is bounded and never fetches full Review or Kell data until requested',async t=>{
  const page=await pageFor(t),requests=[];
  page.on('request',r=>requests.push(r.url()));
  assert.ok(gzipSync(JSON.stringify(bootstrap)).length<1_000_000);
  await page.goto(base+'/');
  await page.waitForFunction(()=>document.querySelectorAll('#grid .card').length===15);
  assert.equal(requests.some(url=>url.includes('/data/snapshots/')||url.includes('kell-latest')),false);
  assert.equal(await page.locator('#marketSummary').evaluate(e=>e.open),false);
  assert.ok(await page.locator('#grid .card').first().evaluate(e=>e.getBoundingClientRect().top<innerHeight));
  assert.ok(await page.evaluate(()=>document.body.scrollWidth<=innerWidth));
  assert.ok(await page.locator('[data-primary-view="watchlist"]').evaluate(e=>e.getBoundingClientRect().right<=innerWidth));
  assert.doesNotMatch(await page.locator('#grid').innerText(),/Blue sky/);
  await page.locator('[data-primary-view="kell-daily"]').click();
  assert.equal(await page.locator('#grid .card').count(),5);
  assert.equal(requests.some(url=>url.includes('/data/snapshots/')||url.includes('kell-latest')),false);
  // A full source fixture becomes available only when Research is requested.
  let fullReads=0;
  const items=[...bootstrap.shortlists.weeklyTrendBirth,...bootstrap.shortlists.kellDaily];
  await page.route('**/data/snapshots/*.json',route=>{
    fullReads++;
    return route.fulfill({json:{...bootstrap,schemaVersion:'trend-birth-review-v1',candidates:items,
      kellCandidates:items,unifiedCandidateIndex:items,trendBirthCandidateIndex:items}});
  });
  await page.locator('[data-primary-view="research"]').click();
  await page.waitForFunction(()=>document.querySelector('[data-primary-view="research"]').classList.contains('active'));
  assert.equal(fullReads,1);
  await page.locator('#grid .card').first().click();
  assert.equal(await page.locator('#detail').evaluate(e=>e.open),true);
  assert.match(await page.locator('#detail').innerText(),/Daily radar/i);
});

test('empty mobile watchlist uses no full archive and keeps the current snapshot',async t=>{
  const page=await pageFor(t,'allow'),requests=[];
  page.on('request',request=>requests.push(request.url()));
  await page.goto(base+'/');
  await page.waitForFunction(()=>document.querySelectorAll('#grid .card').length===15);
  await page.evaluate(()=>navigator.serviceWorker.ready);
  await page.locator('[data-primary-view="watchlist"]').click();
  await page.waitForSelector('[data-primary-view="watchlist"].active');
  assert.match(await page.locator('#status').innerText(),/0 spremljeno/);
  assert.equal(requests.some(url=>url.includes('/data/snapshots/')||url.includes('/data/kell-latest')),false);
});

test('Trend Birth opens directly to dated evidence, invalidation and chart',async t=>{
  const page=await pageFor(t),requests=[];
  page.on('request',r=>requests.push(r.url()));
  const sample=bootstrap.shortlists.weeklyTrendBirth[0];
  const price=sample.chartBars.at(-1)[4];
  const row={...sample,earlyTrend:{
    sessionDate:bootstrap.source.sessionDate,phase:'reclaim',evidence:['support_reclaim','relative_strength_turn'],
    baseSupport:price,invalidation:price*.999,reclaimPivot:price*1.001,
    relativeStrength20Pct:3.1,weeklyBaseWeeks:32,dailyStage:2
  }};
  await page.route('**/data/review-bootstrap-v1/**',route=>route.fulfill({json:{
    ...bootstrap,shortlists:{...bootstrap.shortlists,earlyTrendBirth:[row]}
  }}));
  await page.goto(base+'/');
  await page.waitForSelector('[data-primary-view="early"].active');
  assert.equal(await page.locator('#grid .card').count(),1);
  assert.match(await page.locator('#grid').innerText(),/Poništenje teze/);
  assert.match(await page.locator('#grid').innerText(),/RS prema SPY-u/);
  assert.match(await page.locator('#grid').innerText(),new RegExp(bootstrap.source.sessionDate));
  assert.equal(await page.locator('#grid canvas').count(),1);
  await page.waitForSelector('#grid canvas[aria-description*="Poništenje"]');
  assert.equal(requests.some(url=>url.includes('/data/snapshots/')||url.includes('kell-latest')),false);
});

test('modern startup fetches the weekly view and its charts only on selection',async t=>{
  const page=await pageFor(t),requests=[];
  page.on('request',r=>requests.push(r.url()));
  const view='weeklyTrendBirth';
  const payload=JSON.stringify({schemaVersion:'trend-birth-shortlist-v1',snapshotId:manifest.snapshotId,
    source:bootstrap.source,view,items:bootstrap.shortlists.weeklyTrendBirth});
  const sha256=createHash('sha256').update(payload).digest('hex');
  const basePath='data/review-bootstrap-v2/'+manifest.snapshotId;
  const path=basePath+'/'+view+'--'+sha256+'.json';
  await page.route('**/data/publication.json',route=>route.fulfill({json:{...manifest,bootstrapPath:basePath+'.json'}}));
  await page.route('**/'+basePath+'.json',route=>route.fulfill({json:{
    ...bootstrap,shortlists:{...bootstrap.shortlists,earlyTrendBirth:[],[view]:[]},
    deferredShortlists:{[view]:{path,sha256}}
  }}));
  await page.route('**/'+path,route=>route.fulfill({contentType:'application/json',body:payload}));
  await page.goto(base+'/');
  await page.waitForSelector('[data-primary-view="early"].active');
  assert.equal(requests.some(url=>url.endsWith(path)),false);
  await page.locator('[data-primary-view="weekly"]').click();
  await page.waitForSelector('.weekly-card');
  assert.equal(await page.locator('.weekly-card').count(),15);
  assert.equal(requests.filter(url=>url.endsWith(path)).length,1);
  assert.equal(await page.locator('#chartPeriod').inputValue(),'base');
  const canvas=page.locator('.weekly-card canvas').first();
  await page.waitForSelector('.weekly-card canvas[aria-description*="Zona baze"]');
  const focused=await canvas.getAttribute('aria-description');
  const metrics=bootstrap.shortlists.weeklyTrendBirth[0].weeklyBirth.metrics;
  const [year,month,day]=metrics.historyEnd.split('-');
  assert.ok(focused.includes('Zadnji dovršeni tjedan '+day+'.'+month+'.'+year.slice(2)));
  assert.match(focused,/Pivot/);
  const focusedCount=Number(focused.match(/(\d+) svijeća/)[1]);
  assert.equal(focusedCount,metrics.baseWeeks+8);
  await canvas.click();
  const dialogChart=page.locator('#detail canvas[aria-description*="Zona baze"]');
  await dialogChart.waitFor();
  assert.equal(await dialogChart.getAttribute('aria-description'),focused);
});

test('nonempty Watchlist resolves saved symbols only and retains them after a failed ticker request',async t=>{
  const page=await pageFor(t),requests=[];
  const bucket=ticker=>Array.from(ticker).reduce((index,char)=>(31*index+char.charCodeAt(0))%64,0);
  const selected=['AAA','MISSING'];
  await page.addInitScript(tickers=>{
    localStorage.setItem('stockscout.review.watchlist.v1',JSON.stringify({items:tickers}));
  },selected);
  page.on('request',request=>requests.push(request.url()));
  const chartBase='data/kell-chart-runs/read-only-test';
  const watchBase='data/watchlist-runs/'+manifest.snapshotId;
  const schemaVersion='trend-birth-watchlist-bucket-v1';
  const buckets=Array.from({length:64},(_,number)=>JSON.stringify({
    schemaVersion,source:bootstrap.source,snapshotId:manifest.snapshotId,bucket:number,
    rows:number===bucket('AAA')?{AAA:{ticker:'AAA',metrics:{price:42},chartShard:1}}:{}
  }));
  const digests=buckets.map(payload=>createHash('sha256').update(payload).digest('hex'));
  await page.route('**/data/publication.json',route=>route.fulfill({json:{...manifest,watchlist:{
    schemaVersion,basePath:watchBase,chartBasePath:chartBase,sha256:digests
  }}}));
  let fail=true;
  await page.route('**/data/watchlist-runs/**/*.json',route=>{
    const number=Number.parseInt(new URL(route.request().url()).pathname.split('/').at(-1),16);
    if(number===bucket('AAA')&&fail)return route.fulfill({status:503});
    return route.fulfill({contentType:'application/json',body:buckets[number]});
  });
  await page.route('**/'+chartBase+'/shard-001.json',route=>route.fulfill({json:{
    schemaVersion:'kell-chart-shard-v2',source:bootstrap.source,charts:{AAA:{daily:[
      ['2026-11-16',40,43,39,41,100],['2026-11-17',41,43,40,42,130]
    ]}}
  }}));
  await page.goto(base+'/');
  await page.waitForSelector('#grid .card');
  assert.equal(requests.some(url=>url.includes('/data/watchlist-runs/')),false);
  await page.locator('[data-primary-view="watchlist"]').click();
  const retry=page.getByRole('button',{name:'Ponovi učitavanje'});
  await retry.waitFor({timeout:5000}).catch(async error=>{
    throw new Error((await page.locator('#status').innerText())+' '+JSON.stringify(requests.filter(url=>url.includes('/data/'))),{cause:error});
  });
  assert.equal(await page.locator('#grid .card').count(),2);
  fail=false;
  const chartRequest=page.waitForRequest('**/shard-001.json');
  await retry.click();
  await page.getByText('Nema podataka za ticker u prikazanom EOD-u.').waitFor();
  await chartRequest;
  assert.match(await page.locator('.card[data-ticker="AAA"]').innerText(),/42\.00/);
  assert.match(await page.locator('.card[data-ticker="MISSING"]').innerText(),/Nema podataka/);
  assert.equal(requests.some(url=>url.includes('/data/snapshots/')||url.includes('/data/kell-latest')),false);
  assert.equal(new Set(requests.filter(url=>url.includes('/data/watchlist-runs/'))).size,2);
});

test('saved Early Trend Birth plan follows the original levels across a new EOD and can be archived',async t=>{
  const page=await pageFor(t),requests=[];
  page.on('request',request=>requests.push(request.url()));
  const first='2026-11-17',next='2026-11-18',ticker='AAA';
  const make=(day,token,rows,pivot)=>{
    const source={...bootstrap.source,sessionDate:day,runId:day+'-eod-123-'+(day===first?'1':'2')};
    const snapshotId=source.runId+'--'+token.repeat(64);
    const basePath='data/watchlist-runs/'+snapshotId,chartBasePath='data/kell-chart-runs/test';
    const schemaVersion='trend-birth-watchlist-bucket-v1';
    const tickerBucket=ticker.split('').reduce((index,char)=>(31*index+char.charCodeAt(0))%64,0);
    const item={ticker,sources:[],chartBars:rows,metrics:{price:rows.at(-1)[4]},
      earlyTrend:{sessionDate:day,phase:'reclaim',reclaimPivot:pivot,invalidation:95,evidence:['support_reclaim']}};
    const buckets=Array.from({length:64},(_,bucket)=>JSON.stringify({schemaVersion,source,snapshotId,bucket,
      rows:bucket===tickerBucket?{[ticker]:item}:{}}));
    const sha256=buckets.map(body=>createHash('sha256').update(body).digest('hex'));
    return {manifest:{...source,schemaVersion:'trend-birth-publication-v1',snapshotId,
      bootstrapPath:'data/review-bootstrap-v1/'+snapshotId+'.json',watchlist:{basePath,chartBasePath,schemaVersion,sha256}},
    data:{...bootstrap,source,reviewSnapshotId:snapshotId,shortlists:{...bootstrap.shortlists,earlyTrendBirth:[item]}},buckets};
  };
  const bars=[['2026-11-16',100,102,98,101,100], [first,101,102,98,100,100]];
  const origin=make(first,'a',bars,105);
  let active=origin;
  await page.clock.setFixedTime(new Date('2026-11-19T01:00:00Z'));
  await page.route('**/data/publication.json',route=>route.fulfill({json:active.manifest}));
  await page.route('**/data/review-bootstrap-v1/**',route=>route.fulfill({json:active.data}));
  await page.route('**/data/watchlist-runs/**/*.json',route=>{
    const index=Number.parseInt(new URL(route.request().url()).pathname.split('/').at(-1),16);
    return route.fulfill({contentType:'application/json',body:active.buckets[index]});
  });
  await page.goto(base+'/');
  await page.getByRole('button',{name:'Spremi plan',exact:true}).click();
  await page.getByRole('button',{name:'Plan spremljen',exact:true}).waitFor();
  await page.locator('[data-primary-view="watchlist"]').click();
  const card=page.locator('.card[data-ticker="AAA"]');
  await card.locator('[data-plan-status][data-state="saved"]').waitFor();
  assert.match(await card.locator('.saved-plan').innerText(),/Pivot 105\.00/);
  assert.equal(await card.locator('.saved-plan a').getAttribute('href'),'?snapshot='+origin.manifest.snapshotId);

  active=make(next,'b',[...bars,[next,99,101,91,92,100]],110);
  await page.waitForFunction(()=>document.getElementById('eodFreshness').dataset.state);
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await card.locator('[data-plan-status][data-state="invalidated"]').waitFor();
  assert.match(await card.locator('.saved-plan').innerText(),/Pivot 105\.00/);
  assert.match(await card.locator('[data-plan-status]').innerText(),/2026-11-18 · 92\.00/);
  await card.getByRole('button',{name:'Arhiviraj plan'}).click();
  await page.locator('#savedPlanArchive summary').click();
  assert.match(await page.locator('#archivedPlanList').innerText(),/AAA · Early Trend Birth/);
  assert.equal(await card.count(),0);
  assert.equal(requests.some(url=>url.includes('/data/snapshots/')),false);
});

test('visible again: incomplete update preserves the old snapshot, complete update replaces it',async t=>{
  const page=await pageFor(t,'allow');
  const make=(day,token)=>{
    const source={...bootstrap.source,sessionDate:day,runId:day+'-eod-'+token+'-1'};
    const id=source.runId+'--'+token.repeat(64);
    const manifest={...source,schemaVersion:'trend-birth-publication-v1',snapshotId:id,
      bootstrapPath:'data/review-bootstrap-v1/'+id+'.json'};
    return {manifest,bootstrap:{...bootstrap,source,reviewSnapshotId:id}};
  };
  const previous=make('2026-11-16','1'),next=make('2026-11-17','2');
  let active=previous,partial=false;
  await page.clock.setFixedTime(new Date('2026-11-18T08:00:00Z'));
  await page.route('**/data/publication.json',route=>route.fulfill({json:active.manifest}));
  await page.route('**/data/review-bootstrap-v1/**',route=>partial?
    route.fulfill({status:503,body:'Unavailable'}):route.fulfill({json:active.bootstrap}));
  await page.goto(base+'/');
  await page.waitForFunction(()=>document.querySelector('#eodFreshness').dataset.state==='stale');
  active=next;
  partial=true;
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await page.waitForFunction(()=>document.querySelector('#eodFreshness').dataset.state==='unknown');
  assert.match(await page.locator('#eodFreshness').innerText(),/2026-11-16/);
  assert.match(await page.locator('#runMeta').innerText(),/2026-11-16/);
  partial=false;
  await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
  await page.waitForFunction(()=>document.querySelector('#eodFreshness').dataset.state==='current');
  assert.match(await page.locator('#eodFreshness').innerText(),/2026-11-17/);
  assert.match(await page.locator('#runMeta').innerText(),/2026-11-17/);
});

test('historical link shows its own session and stays pinned after a focus event',async t=>{
  const page=await pageFor(t),seen=[];
  page.on('request',request=>seen.push(request.url()));
  const day='2026-09-17';
  await page.route('**/data/history/'+day+'.json',route=>route.fulfill({
    json:{...bootstrap,source:{...bootstrap.source,sessionDate:day}}
  }));
  await page.goto(base+'/?date='+day);
  await page.waitForFunction(()=>document.querySelector('#eodFreshness').dataset.state==='archive');
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  assert.match(await page.locator('#eodFreshness').innerText(),/Povijesna snimka.*2026-09-17/);
  assert.match(await page.locator('#runMeta').innerText(),/2026-09-17/);
  assert.equal(seen.some(url=>url.endsWith('/data/publication.json')),false);
});

test('Kell Swing renders pivot, stop, maximum entry and confirmed state on mobile',async t=>{
  const page=await pageFor(t);
  const item={...bootstrap.shortlists.kellDaily[0],kellSwing:{
    setup:'ema_crossback',phase:'ema_crossback',sessionDate:manifest.sessionDate,state:'triggered',
    reason:'pivot_closed_above',pivot:83.38,stop:79.51,maxEntry:85.31,gapPct:0.6,riskPct:4.64
  }};
  await page.route('**/'+manifest.bootstrapPath,route=>route.fulfill({
    json:{...bootstrap,shortlists:{...bootstrap.shortlists,kellSwing:[item]}}
  }));
  await page.goto(base+'/');
  await page.locator('[data-primary-view="kell-daily"]').click();
  const card=page.locator('#grid .swing-card');
  await card.waitFor();
  const content=await card.innerText();
  for(const text of ['EMA Crossback','Pivot potvrđen','83.38','79.51','85.31','0.6%','iduće sesije']){
    assert.ok(content.includes(text),content);
  }
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
});

test('auth reconciliation respects remote deletions and keeps accounts and anonymous items separate',async t=>{
  const page=await pageFor(t);
  await page.addInitScript(()=>localStorage.setItem('stockscout.review.watchlist.v1',JSON.stringify({items:['LOCAL']})));
  await page.goto(base+'/');
  await page.waitForFunction(()=>window.authTest?.listener&&typeof state!=='undefined'&&state.data);
  const login=async id=>{
    await page.evaluate(id=>{authTest.session={user:{id}};authTest.listener('SIGNED_IN',authTest.session)},id);
    await page.waitForFunction(()=>!state.ownerReconciling);
  };
  await login('A');
  assert.deepEqual(await page.evaluate(()=>state.watchlist.map(x=>x.ticker)),['AAA']);
  assert.equal(await page.evaluate(()=>authTest.writes.length),0);
  await page.evaluate(()=>{authTest.rows.A=[];authTest.listener('TOKEN_REFRESHED',authTest.session)});
  await page.waitForFunction(()=>!state.ownerReconciling&&state.watchlist.length===0);
  assert.equal(await page.evaluate(()=>authTest.writes.length),0);
  await login('B');
  assert.deepEqual(await page.evaluate(()=>state.watchlist.map(x=>x.ticker)),['BBB']);
  await page.locator('#ownerSyncSummary').click();
  await page.locator('#ownerImportLocal').click();
  await page.waitForFunction(()=>!state.ownerReconciling&&state.watchlist.some(x=>x.ticker==='LOCAL'));
  assert.equal(await page.evaluate(()=>authTest.writes.length),1);
  await page.locator('#ownerSignOut').click();
  assert.deepEqual(await page.evaluate(()=>state.watchlist.map(x=>x.ticker)),['LOCAL']);
});
