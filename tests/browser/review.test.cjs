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

async function pageFor(t, serviceWorkers='block', options={}){
  const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers,...options});
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
      from:table=>{let owner;const q={select:()=>q,eq:(key,value)=>{if(key==='user_id')owner=value;return q},
        order:async()=>({data:(authTest.rows[owner]||[]).map(ticker=>({ticker}))}),
        maybeSingle:async()=>table==='trend_birth_plan_books'&&window.planServer?
          planServer({action:'read',owner,account:authTest.session?.user?.id}):{error:{code:'PGRST205'}}};return q},
      rpc:async(name,args)=>{if(name==='trend_birth_commit_plan_book')
        return planServer({action:'write',args,account:authTest.session?.user?.id});
        authTest.writes.push(args);const rows=authTest.rows[authTest.session.user.id];
        if(args.p_present&&!rows.includes(args.p_ticker))rows.push(args.p_ticker);return{}}
    })};` }));
  return page;
}

function makePlanFixture(day,token,rows,pivot){
  const ticker='AAA',source={...bootstrap.source,sessionDate:day,runId:day+'-eod-123-1'};
  const snapshotId=source.runId+'--'+token.repeat(64);
  const basePath='data/watchlist-runs/'+snapshotId,chartBasePath='data/kell-chart-runs/test';
  const schemaVersion='trend-birth-watchlist-bucket-v1',tickerBucket=ticker.split('').reduce((index,char)=>(31*index+char.charCodeAt(0))%64,0);
  const item={ticker,sources:[],chartBars:rows,metrics:{price:rows.at(-1)[4]},
    earlyTrend:{sessionDate:day,phase:'reclaim',reclaimPivot:pivot,invalidation:95,evidence:['support_reclaim']}};
  const buckets=Array.from({length:64},(_,bucket)=>JSON.stringify({schemaVersion,source,snapshotId,bucket,
    rows:bucket===tickerBucket?{[ticker]:item}:{}}));
  const sha256=buckets.map(body=>createHash('sha256').update(body).digest('hex'));
  return {manifest:{...source,schemaVersion:'trend-birth-publication-v1',snapshotId,
    bootstrapPath:'data/review-bootstrap-v1/'+snapshotId+'.json',watchlist:{basePath,chartBasePath,schemaVersion,sha256}},
  data:{...bootstrap,source,reviewSnapshotId:snapshotId,shortlists:{...bootstrap.shortlists,earlyTrendBirth:[item]}},buckets};
}
async function routePlanFixture(page,active){
  await page.route('**/data/publication.json',route=>route.fulfill({json:active().manifest}));
  await page.route('**/data/review-bootstrap-v1/**',route=>route.fulfill({json:active().data}));
  await page.route('**/data/watchlist-runs/**/*.json',route=>{
    const index=Number.parseInt(new URL(route.request().url()).pathname.split('/').at(-1),16);
    return route.fulfill({contentType:'application/json',body:active().buckets[index]});
  });
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

test('a plan moved to the signed-in account can be archived on a second device',async t=>{
  const first=await pageFor(t,'block',{hasTouch:true,isMobile:true});
  const second=await pageFor(t,'block',{hasTouch:true,isMobile:true});
  const books=new Map(),writes=[];
  function planServer({action,owner,args,account}){
    if(action==='read')return {data:owner===account?books.get(owner)??null:null};
    assert.equal(args.p_owner,account);
    writes.push({account,version:args.p_expected_version});
    const previous=books.get(account)?.version||0;
    if(previous!==args.p_expected_version)return {data:null};
    books.set(account,{version:previous+1,plans:args.p_plans});
    return {data:previous+1};
  }
  await first.exposeFunction('planServer',planServer);
  await second.exposeFunction('planServer',planServer);
  const origin='2026-11-17',later='2026-11-18',ticker='AAA';
  const bars=[['2026-11-16',100,102,98,101,100],[origin,101,102,98,100,100]];
  const trigger=[later,103,107,101,105,100];
  let active=makePlanFixture(origin,'a',bars,105);
  await routePlanFixture(first,()=>active);
  const incomplete=makePlanFixture('2026-11-19','c',[trigger,['2026-11-19',105,108,103,106,100]],110);
  await routePlanFixture(second,()=>incomplete);
  const signIn=(page,id)=>page.evaluate(id=>{
    authTest.session={user:{id,email:id+'@example.test'}};
    authTest.listener('SIGNED_IN',authTest.session);
  },id);
  await first.goto(base+'/');
  const card=page=>page.locator('.card[data-ticker="'+ticker+'"]');
  const observedStatus=(page,state)=>page.waitForFunction(({ticker,state})=>{
    const card=document.querySelector('.card[data-ticker="'+ticker+'"]');
    if(card?.querySelector('[data-plan-status]')?.dataset.state===state)return true;
    card?.querySelector('canvas')?.scrollIntoView({block:'center'});
    return false;
  },{ticker,state},{polling:150});
  await card(first).getByRole('button',{name:'Spremi plan',exact:true}).tap();
  await card(first).getByRole('button',{name:'Plan spremljen',exact:true}).waitFor();
  await signIn(first,'plan-owner-A');
  await first.locator('[data-primary-view="watchlist"]').tap();
  await first.getByRole('button',{name:'Prenesi lokalne planove (1)',exact:true}).waitFor();
  assert.deepEqual(writes,[]);
  await first.locator('#ownerPlanImport').tap();
  await first.locator('#ownerPlanSyncNote').filter({hasText:'Preneseno 1'}).waitFor();
  assert.equal(books.get('plan-owner-A').plans[0].ticker,ticker);
  assert.equal(await first.evaluate(()=>ReviewPlans.load(window.localStorage).length),1);

  active=makePlanFixture(later,'b',[...bars,trigger],110);
  await first.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await observedStatus(first,'abovePivot');
  await first.waitForFunction(async()=>{
    const {data}=await planServer({action:'read',owner:'plan-owner-A',account:'plan-owner-A'});
    return Boolean(data?.plans[0].closingReview);
  });
  await second.goto(base+'/?view=watchlist');
  await second.waitForFunction(()=>window.authTest.listener);
  await signIn(second,'plan-owner-A');
  await observedStatus(second,'coverage');
  await card(second).getByRole('button',{name:'Arhiviraj plan',exact:true}).tap();
  await second.locator('#planNotice').filter({hasText:'arhiviran na računu'}).waitFor();
  assert.ok(books.get('plan-owner-A').plans[0].archivedAt);
  assert.equal(books.get('plan-owner-A').plans[0].closingReview.asOf,later);
  await second.locator('#savedPlanArchive > summary').tap();
  await second.locator('[data-archived-plan] > summary').filter({hasText:ticker}).waitFor();
  await first.locator('#ownerPlanRefresh').tap();
  await first.locator('#savedPlanArchive').waitFor();
  assert.equal(await card(first).count(),0);
  await signIn(second,'plan-owner-B');
  await second.locator('#ownerPlanSyncNote').filter({hasText:'dostupni su na drugim uređajima'}).waitFor();
  assert.equal(await second.locator('[data-archived-plan]').count(),0);
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

test('mobile browser Back closes the ticker, Forward restores its range, and Statistics returns to its tab',async t=>{
  const page=await pageFor(t,'block',{hasTouch:true,isMobile:true}),requests=[];
  await page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{
    writeText:async value=>{window.copiedTickerLink=value}
  }}));
  page.on('request',request=>requests.push(request.url()));
  await page.goto(base+'/?view=weekly&code=private');
  await page.waitForSelector('[data-primary-view="weekly"].active');
  assert.equal(await page.locator('#weeklyOutcomesLink').getAttribute('href'),'statistics.html#siWeeklyBase');
  const first=page.locator('.weekly-card').first();
  const historyLength=await page.evaluate(()=>history.length);
  const canvas=first.locator('canvas');
  await canvas.scrollIntoViewIfNeeded();
  const gridScroll=await page.evaluate(()=>window.scrollY);
  await canvas.tap();
  await page.locator('#detail[open]').waitFor();
  // A range selection in the same frame as opening the next ticker must still update history.
  await page.locator('#nextDetail').evaluate(button=>{
    button.click();
    const period=document.querySelector('#detail [data-chart-period]');
    period.value='3m';
    period.dispatchEvent(new Event('change',{bubbles:true}));
  });
  const ticker=await page.locator('#detailToolbarTicker').innerText();
  assert.equal(new URL(page.url()).searchParams.get('range'),'3m');
  assert.equal(await page.evaluate(()=>history.length),historyLength+1);
  await page.getByRole('button',{name:'Kopiraj poveznicu'}).tap();
  const copied=new URL(await page.evaluate(()=>window.copiedTickerLink));
  assert.deepEqual([...copied.searchParams.keys()],['view','ticker','range']);
  assert.equal(copied.searchParams.get('view'),'weekly');
  assert.equal(copied.searchParams.get('ticker'),ticker);
  assert.equal(copied.searchParams.get('range'),'3m');
  await page.goBack();
  await page.locator('#detail[open]').waitFor({state:'detached'});
  await page.waitForFunction(name=>document.activeElement?.dataset?.ticker===name,ticker);
  assert.equal(await page.evaluate(()=>window.scrollY),gridScroll);
  await page.goForward();
  await page.locator('#detail[open]').waitFor();
  assert.equal(await page.locator('#detailToolbarTicker').innerText(),ticker);
  assert.equal(await page.locator('#detail .detail-evidence select').inputValue(),'3m');
  await page.locator('#closeDetail').tap();
  await page.waitForFunction(()=>!new URLSearchParams(location.search).has('ticker'));
  await page.locator('.workspace-tabs a[href="statistics.html"]').tap();
  const back=page.getByRole('link',{name:/Dnevni pregled/});
  await page.waitForFunction(()=>document.querySelector('[data-review-return]').href.includes('view=weekly'));
  await back.tap();
  await page.waitForSelector('[data-primary-view="weekly"].active');
  await page.goto(copied.href);
  await page.locator('#detail[open]').waitFor();
  assert.equal(await page.locator('#detailToolbarTicker').innerText(),ticker);
  assert.equal(await page.locator('#detail .detail-evidence select').inputValue(),'3m');
  assert.equal(requests.some(url=>url.includes('/data/snapshots/')||url.includes('kell-latest')),false);
});

test('the PWA keeps a ticker shortcut intact across an offline launch and retry',async t=>{
  const page=await pageFor(t,'allow',{hasTouch:true,isMobile:true});
  const ticker=bootstrap.shortlists.weeklyTrendBirth[0].ticker;
  const target=base+'/?view=weekly&ticker='+encodeURIComponent(ticker)+'&range=3m';
  await page.goto(base+'/');
  await page.waitForFunction(()=>navigator.serviceWorker.controller);
  await page.context().setOffline(true);
  await page.goto(target);
  assert.equal(page.url(),target);
  await page.getByRole('heading',{name:'Nema internetske veze'}).waitFor();
  await page.context().setOffline(false);
  await page.getByRole('button',{name:'Pokušaj ponovno'}).tap();
  await page.locator('#detail[open]').waitFor();
  assert.equal(await page.locator('#detailToolbarTicker').innerText(),ticker);
  assert.equal(await page.locator('#detail .detail-evidence select').inputValue(),'3m');
  assert.equal(await page.evaluate(()=>caches.keys()).then(keys=>keys.filter(name=>name.startsWith('trendbirth-install-')).join()),
    'trendbirth-install-v3');
});

test('dated EOD changes load on demand and open an out-of-list ticker without a full archive',async t=>{
  const page=await pageFor(t),requests=[];
  page.on('request',request=>requests.push(request.url()));
  const schemaVersion='trend-birth-review-changes-v1',ticker='OFFLIST';
  const day=bootstrap.source.sessionDate,prior='2026-11-16';
  const event={ticker,kind:'level_broken',priorLevel:12,
    before:{close:14,state:'reclaim',listed:true},after:{close:11,state:null,listed:false}};
  const payload=JSON.stringify({schemaVersion,source:bootstrap.source,snapshotId:manifest.snapshotId,
    previousSession:prior,baseline:{sessionDate:prior},strategies:{
      early:{status:'compared',count:1,compared:230,events:[event],current:[]},
      kell:{status:'no_baseline',count:0,compared:0,events:[],current:[]}}});
  const sha256=createHash('sha256').update(payload).digest('hex');
  const ref={schemaVersion,sha256,path:'data/review-change-runs/'+manifest.snapshotId+'--'+sha256+'.json'};
  const index=Array.from(ticker).reduce((value,char)=>(31*value+char.charCodeAt(0))%64,0);
  const watchSchema='trend-birth-watchlist-bucket-v1',watchBase='data/watchlist-runs/'+manifest.snapshotId;
  const chartBase='data/kell-chart-runs/read-only-test';
  const buckets=Array.from({length:64},(_,bucket)=>JSON.stringify({schemaVersion:watchSchema,source:bootstrap.source,
    snapshotId:manifest.snapshotId,bucket,rows:bucket===index?{[ticker]:{
      ticker,sources:[],metrics:{price:11},chartAvailable:true,chartShard:3}}:{}}));
  await page.route('**/data/publication.json',route=>route.fulfill({json:{...manifest,changes:ref,watchlist:{
    schemaVersion:watchSchema,basePath:watchBase,chartBasePath:chartBase,
    sha256:buckets.map(raw=>createHash('sha256').update(raw).digest('hex'))
  }}}));
  await page.route('**/'+watchBase+'/'+index.toString(16).padStart(2,'0')+'.json',
    route=>route.fulfill({contentType:'application/json',body:buckets[index]}));
  await page.route('**/'+chartBase+'/shard-003.json',route=>route.fulfill({json:{
    schemaVersion:'kell-chart-shard-v2',source:bootstrap.source,
    charts:{[ticker]:{daily:[[prior,14,15,13,14,100],[day,13,14,10,11,250]]}}
  }}));
  let corrupt=true;
  await page.route('**/'+ref.path,route=>route.fulfill({contentType:'application/json',body:payload+(corrupt?' ':'')}));
  await page.goto(base+'/');
  const panel=page.locator('#reviewChanges');
  await panel.waitFor();
  assert.equal(requests.some(url=>url.includes('/review-change-runs/')),false);
  await panel.locator('summary').click();
  const retry=panel.getByRole('button',{name:'Pokušaj ponovno'});
  await retry.waitFor();
  corrupt=false;
  await retry.click();
  await panel.getByRole('button',{name:/OFFLIST/}).waitFor();
  assert.match(await panel.innerText(),/230 uspoređenih tickera/);
  assert.match(await panel.innerText(),/Prethodna zaštitna razina 12.00/);
  assert.match(await panel.innerText(),/Izvan kratke liste/);
  await panel.getByRole('button',{name:'Kell Swing'}).click();
  assert.match(await panel.innerText(),/nema usporedivu verziju/);
  await panel.getByRole('button',{name:'Early Trend Birth'}).click();
  await panel.getByRole('button',{name:/OFFLIST/}).click();
  await page.waitForFunction(()=>document.querySelector('.detail-chart-meta')?.textContent.includes('zatvaranje 11.00'));
  assert.equal(await page.locator('#detailToolbarTicker').innerText(),ticker);
  assert.equal(requests.filter(url=>url.includes('/watchlist-runs/')).length,1);
  assert.equal(requests.some(url=>url.includes('/data/snapshots/')||url.includes('kell-latest')),false);
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('.detail-chart-meta')?.textContent.includes('zatvaranje 11.00'));
  assert.equal(await page.locator('#detailToolbarTicker').innerText(),ticker);
  assert.equal(await page.evaluate(()=>localStorage.getItem('stockscout.review.watchlist.v1')),null);
});

test('Trend Birth opens directly to dated evidence, invalidation and chart',async t=>{
  const page=await pageFor(t,'block',{hasTouch:true,isMobile:true}),requests=[];
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
  await page.locator('#grid .card').click();
  const detail=page.locator('.detail-evidence');
  assert.equal(await detail.locator('select').inputValue(),'6m');
  await detail.locator('[data-volume-readout]').waitFor();
  assert.match(await detail.locator('[data-volume-readout]').innerText(),/prethodni 20D/);
  assert.match(await detail.locator('[data-relative-readout]').innerText(),/100 na/);
  const slider=detail.getByRole('slider',{name:'Svijeća na grafu'});
  const priceChart=detail.locator('.detail-chart');
  const barCount=Number(await slider.getAttribute('max'))+1;
  const visible=sample.chartBars.slice(-barCount),index=40;
  const width=(await priceChart.boundingBox()).width;
  const x=10+index*(width-82)/(barCount-1);
  await priceChart.tap({position:{x,y:90}});
  await page.waitForFunction(i=>document.querySelector('.chart-inspection-controls input').value===String(i),index);
  const date=String(visible[index][0]).slice(0,10).split('-');
  assert.ok((await detail.locator('.detail-chart-meta').innerText()).includes(date[2]+'.'+date[1]+'.'+date[0].slice(2)));
  const priorVolume=visible.slice(index-20,index).reduce((sum,bar)=>sum+bar[5],0)/20;
  assert.ok((await detail.locator('[data-volume-readout]').innerText()).includes((visible[index][5]/priorVolume).toFixed(2)+'×'));
  const ref=visible.find(bar=>bar[6]>0)[6];
  assert.match(await detail.locator('[data-relative-readout]').innerText(),new RegExp('^'+(100*visible[index][6]/ref).toFixed(1)));
  assert.ok(await detail.evaluate(e=>e.querySelectorAll('.chart-track:not([hidden])').length===3&&
    [...e.querySelectorAll('.chart-track:not([hidden])')].every(track=>
      Math.abs(parseFloat(getComputedStyle(track,'::after').left)-parseFloat(e.style.getPropertyValue('--candle-x')))<.01)));
  await slider.press('ArrowRight');
  assert.equal(await slider.inputValue(),String(index+1));
  assert.equal(await page.locator('#detailToolbarTicker').innerText(),sample.ticker);
  await detail.locator('select').selectOption('5y');
  await page.waitForFunction(()=>document.querySelector('.detail-chart-meta').textContent.includes('tjedna svijeća'));
  assert.equal(await detail.getAttribute('data-chart-cursor'),null);
  assert.match(await detail.locator('[data-volume-readout]').innerText(),/prethodni 10W/);
  await detail.locator('select').selectOption('3m');
  await page.waitForFunction(()=>document.querySelector('.detail-chart-meta').textContent.includes('prikazana sesija'));
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
  const modal=page.locator('#detail');
  const floor=modal.getByRole('button',{name:'Dno baze'});
  await floor.click();
  const summary=await modal.locator('.weekly-evidence').innerText();
  const floorDate=summary.match(/Dno baze [\d.]+ · (\d{2}\.\d{2}\.\d{2})/)[1];
  assert.ok((await modal.locator('.detail-chart-meta').innerText()).startsWith('Tjedan do '+floorDate));
  assert.match(summary,/Prvi otpor/);
});

test('SPY history is lazy and replaces an incomplete view only after checksum verification',async t=>{
  const page=await pageFor(t),requests=[];
  page.on('request',request=>requests.push(request.url()));
  const sample=bootstrap.shortlists.weeklyTrendBirth[0];
  const bars=sample.chartBars.slice(-6).map(bar=>bar.slice(0,6));
  const newest=bars.at(-1),missingDate=bars.at(-2)[0];
  const item={...sample,chartBars:bars,earlyTrend:{sessionDate:bootstrap.source.sessionDate,
    phase:'reclaim',evidence:['support_reclaim'],reclaimPivot:newest[4],invalidation:newest[4]*.9}};
  const schemaVersion='review-spy-reference-v1';
  const points=bars.filter(bar=>bar[0]!==missingDate).map(bar=>[bar[0],500,6,6]);
  const payload=JSON.stringify({schemaVersion,snapshotId:manifest.snapshotId,source:bootstrap.source,benchmark:'SPY',points});
  const sha256=createHash('sha256').update(payload).digest('hex');
  const path='data/review-spy-runs/'+manifest.snapshotId+'--'+sha256+'.json';
  await page.route('**/data/publication.json',route=>route.fulfill({json:{
    ...manifest,spyReference:{schemaVersion,path,sha256,sessionCount:points.length}
  }}));
  await page.route('**/'+manifest.bootstrapPath,route=>route.fulfill({json:{
    ...bootstrap,shortlists:{...bootstrap.shortlists,earlyTrendBirth:[item]}
  }}));
  let corrupt=true;
  await page.route('**/'+path,route=>route.fulfill({contentType:'application/json',body:payload+(corrupt?' ':'')}));
  await page.goto(base+'/');
  await page.waitForSelector('.early-card');
  assert.equal(requests.filter(url=>url.includes('/review-spy-runs/')).length,0);
  const first=page.waitForResponse(response=>response.url().endsWith(path));
  await page.locator('.early-card').click();
  await (await first).finished();
  const section=page.locator('.detail-evidence');
  await section.getByText('Referentni niz nije dostupan').waitFor();
  assert.equal(await section.locator('.chart-rs-source').isVisible(),false);
  corrupt=false;
  await section.locator('select').selectOption('3m');
  await section.locator('.chart-rs-source').waitFor();
  const expected=(100*newest[4]/bars[0][4]).toFixed(1);
  assert.ok((await section.locator('[data-relative-readout]').innerText()).startsWith(expected+' ('));
  await section.getByRole('slider',{name:'Svijeća na grafu'}).press('ArrowLeft');
  assert.match(await section.locator('[data-relative-readout]').innerText(),/RS za ovaj datum nedostaje/);
  await section.locator('select').selectOption('1y');
  await section.locator('.chart-rs-source').waitFor();
  assert.equal(requests.filter(url=>url.includes('/review-spy-runs/')).length,2);
});

test('opening a Watchlist ticker while its bucket is loading hydrates the open chart',async t=>{
  const page=await pageFor(t),requests=[];
  page.on('request',request=>requests.push(request.url()));
  const ticker='AAA',bucket=Array.from(ticker).reduce((index,char)=>(31*index+char.charCodeAt(0))%64,0);
  const watchSchema='trend-birth-watchlist-bucket-v1',watchBase='data/watchlist-runs/'+manifest.snapshotId;
  const day=bootstrap.source.sessionDate;
  const payload=JSON.stringify({schemaVersion:watchSchema,source:bootstrap.source,snapshotId:manifest.snapshotId,bucket,
    rows:{AAA:{ticker,sources:[],metrics:{price:42},chartBars:[['2026-11-16',40,43,39,41,100],[day,41,43,40,42,130]]}}});
  const sha256=Array(64).fill('a'.repeat(64));
  sha256[bucket]=createHash('sha256').update(payload).digest('hex');
  await page.addInitScript(name=>localStorage.setItem('stockscout.review.watchlist.v1',JSON.stringify({items:[name]})),ticker);
  await page.route('**/data/publication.json',route=>route.fulfill({json:{...manifest,watchlist:{
    schemaVersion:watchSchema,basePath:watchBase,chartBasePath:'data/kell-chart-runs/read-only-test',sha256
  }}}));
  let unblock;
  const held=new Promise(resolve=>{unblock=resolve});
  t.after(()=>unblock());
  await page.route('**/'+watchBase+'/'+bucket.toString(16).padStart(2,'0')+'.json',async route=>{
    await held;
    return route.fulfill({contentType:'application/json',body:payload});
  });
  await page.goto(base+'/');
  await page.waitForSelector('#grid .card');
  await page.locator('[data-primary-view="watchlist"]').click();
  const card=page.locator('#grid .card[data-ticker="AAA"]');
  await card.getByText('Učitavam podatke tickera…').waitFor();
  await card.locator('canvas').click();
  await page.locator('#detail .detail-chart-meta').getByText('Učitavam podatke tickera…').waitFor();
  unblock();
  await page.waitForFunction(()=>document.querySelector('#detail .detail-chart-meta').textContent.includes('zatvaranje 42.00'));
  assert.equal(requests.filter(url=>url.includes('/watchlist-runs/')).length,1);
  assert.equal(await page.locator('#detailToolbarTicker').innerText(),ticker);
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
  const page=await pageFor(t,'block',{hasTouch:true,isMobile:true}),requests=[];
  page.on('request',request=>requests.push(request.url()));
  const first='2026-11-17',next='2026-11-18',breach='2026-11-19',ticker='AAA';
  const make=makePlanFixture;
  const bars=[['2026-11-16',100,102,98,101,100], [first,101,102,98,100,100]];
  const origin=make(first,'a',bars,105);
  let active=origin;
  await page.clock.setFixedTime(new Date('2026-11-20T01:00:00Z'));
  await routePlanFixture(page,()=>active);
  await page.goto(base+'/');
  await page.getByRole('button',{name:'Spremi plan',exact:true}).click();
  await page.getByRole('button',{name:'Plan spremljen',exact:true}).waitFor();
  await page.locator('[data-primary-view="watchlist"]').click();
  const card=page.locator('.card[data-ticker="AAA"]');
  await card.locator('[data-plan-status][data-state="saved"]').waitFor();
  assert.match(await card.locator('.saved-plan').innerText(),/Pivot 105\.00/);
  const sourceLink='?snapshot='+origin.manifest.snapshotId+'&view=early&ticker=AAA';
  assert.equal(await card.locator('.saved-plan a').getAttribute('href'),sourceLink);
  assert.equal(await card.locator('[data-plan-journal]').isVisible(),false);

  const pivotBars=[...bars,[next,103,107,101,105,100]];
  active=make(next,'b',pivotBars,110);
  await page.waitForFunction(()=>document.getElementById('eodFreshness').dataset.state);
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await card.locator('[data-plan-status][data-state="abovePivot"]').waitFor();
  const journal=card.locator('[data-plan-journal]');
  await journal.locator('summary').press('Enter');
  assert.equal(await journal.locator('li').isVisible(),true);
  assert.match(await journal.locator('li').innerText(),/2026-11-18 · 105\.00\s+Prvo zatvaranje na pivotu/);
  assert.equal(await page.locator('#detail').isVisible(),false);
  await journal.getByRole('button',{name:/Otvori svijeću 2026-11-18/}).tap();
  const detail=page.locator('#detail'),chart=detail.locator('.detail-evidence');
  await chart.locator('[data-chart-plan-key]:visible').waitFor();
  assert.match(await chart.locator('[data-chart-plan-key]').innerText(),/Pivot 105\.00/);
  assert.match(await chart.locator('.detail-chart').getAttribute('aria-description'),/Spremljeni Early Trend Birth.*Pivot 105\.0/);
  assert.match(await chart.locator('.detail-chart-meta').innerText(),/^Sesija 18\.11\.26 · zatvaranje 105\.0/);
  assert.equal(await chart.evaluate(node=>node===document.activeElement),true);
  await chart.locator('[data-chart-plan]').selectOption('');
  assert.equal(await chart.locator('[data-chart-plan-key]').isVisible(),false);
  assert.equal((await chart.locator('.detail-chart').getAttribute('aria-description')||'').includes('Spremljeni'),false);
  await page.locator('#closeDetail').click();
  await detail.waitFor({state:'hidden'});

  active=make(breach,'c',[...pivotBars,[breach,99,101,91,92,100]],110);
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await card.locator('[data-plan-status][data-state="invalidated"]').waitFor();
  assert.match(await card.locator('.saved-plan').innerText(),/Pivot 105\.00/);
  assert.match(await card.locator('[data-plan-status]').innerText(),/2026-11-19 · 92\.00/);
  await card.locator('canvas').tap();
  await detail.locator('[data-plan-journal][open] li').nth(1).waitFor();
  assert.deepEqual(await detail.locator('[data-plan-journal] time').allTextContents(),[next,breach]);
  await chart.locator('[data-chart-period]').selectOption('5y');
  await detail.getByRole('button',{name:/Otvori svijeću 2026-11-19/}).tap();
  await detail.locator('.detail-evidence[data-chart-cursor]').waitFor();
  assert.equal(await chart.locator('[data-chart-period]').inputValue(),'1y');
  assert.match(await chart.locator('.detail-chart-meta').innerText(),/^Sesija 19\.11\.26 · zatvaranje 92\.00/);
  assert.match(await chart.locator('[data-chart-plan-key]').innerText(),/Poništenje 95\.00/);
  await page.locator('#closeDetail').click();

  const reviewedSnapshot=active.manifest.snapshotId,unavailable='2026-11-20';
  active=make(unavailable,'d',[...pivotBars,[unavailable,104,106,103,104,100]],111);
  await page.reload();
  await card.locator('[data-plan-status][data-state="coverage"]').waitFor();
  await card.getByRole('button',{name:'Arhiviraj plan'}).click();
  await page.reload();
  await page.locator('#savedPlanArchive > summary').click();
  const archivedPlan=page.locator('[data-archived-plan]');
  await archivedPlan.locator('summary').tap();
  assert.match(await archivedPlan.innerText(),/AAA · Early Trend Birth\s+Plan poništen/);
  assert.match(await archivedPlan.innerText(),/Zadnje provjereno zatvaranje 92\.00/);
  assert.deepEqual(await archivedPlan.locator('time').allTextContents(),[next,breach]);
  assert.deepEqual(await archivedPlan.locator('a').evaluateAll(anchors=>anchors.map(anchor=>anchor.getAttribute('href'))),
    [sourceLink,'?snapshot='+reviewedSnapshot+'&view=early&ticker=AAA']);
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
