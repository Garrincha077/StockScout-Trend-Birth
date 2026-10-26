const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const {createServer}=require('node:http');
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

async function pageFor(t){
  const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
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
