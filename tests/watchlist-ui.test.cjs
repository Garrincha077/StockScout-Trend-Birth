const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'lab','index.html'),'utf8');
const app=fs.readFileSync(path.join(root,'lab','app.js'),'utf8');
const kellLoader=fs.readFileSync(path.join(root,'lab','kell-dataset-loader.js'),'utf8');

test('owner watchlist sync loads before app code and exposes sign-in controls',()=>{
  assert.ok(html.indexOf('@supabase/supabase-js@2.112.3')<html.indexOf('owner-watchlist-sync.js'));
  assert.ok(html.indexOf('owner-watchlist-sync.js')<html.indexOf('app.js'));
  assert.match(html,/id="ownerSyncSummary"/);
  assert.match(html,/id="ownerGoogle"/);
  assert.match(html,/id="ownerMagicForm"/);
  assert.match(app,/OwnerWatchlistSync\.create/);
  assert.match(app,/ownerSync\.setTicker\(ticker,present\)/);
  assert.match(app,/ownerSync\.migrate\(local\)/);
});

test('grid exposes a persistent Watchlist universe and loads its store before app code',()=>{
  assert.match(html,/data-universe="watchlist" id="watchlistUniverse"/);
  assert.ok(html.indexOf('watchlist-store.js')<html.indexOf('app.js'));
  assert.match(app,/watchlist:WatchlistStore\.load\(window\.localStorage\)/);
});

test('cards expose an accessible star toggle without opening the detail card',()=>{
  assert.match(app,/data-watch-ticker/);
  assert.match(app,/aria-pressed/);
  assert.match(app,/toggleWatchlist\(star\.dataset\.watchTicker\)/);
  assert.match(app,/e\.target\.closest\('\[data-watch-ticker\]'\)/);
});

test('saved tickers survive disappearance from the current daily scan',()=>{
  assert.match(app,/watchlistMissing:true/);
  assert.match(app,/Nije u današnjem Unified scanu/);
  assert.match(app,/state\.kellData\?\.trendBirthCandidateIndex\|\|state\.data\?\.trendBirthCandidateIndex/);
  assert.match(app,/tracked\.get\(saved\.ticker\)\|\|unified\.get\(saved\.ticker\)/);
  assert.match(app,/current\?\.trackedWatchlist&&current\?\.chartBars\?\.length\?current\.chartBars/);
  assert.match(app,/trendBirth:current\?\.trackedWatchlist\?current\?\.trendBirth/);
  assert.match(app,/watchlistUnifiedOnly=true/);
  assert.match(app,/U današnjem Unified scanu/);
  assert.match(app,/if\(state\.universe==='watchlist'\)return watchlistItems\(\)/);
});

test('opening Watchlist defaults to all saved names rather than inheriting stale daily filters',()=>{
  assert.match(app,/nextUniverse==='watchlist'&&state\.universe!=='watchlist'/);
  assert.match(app,/state\.filters=\[\]/);
});

test('browser rejects Kell or chart data from another Unified activation',()=>{
  assert.ok(html.indexOf('kell-dataset-loader.js')<html.indexOf('app.js'));
  assert.match(kellLoader,/review\.runId&&kell\.runId&&review\.runId!==kell\.runId/);
  assert.match(kellLoader,/review\.unifiedManifestSha256&&kell\.unifiedManifestSha256&&review\.unifiedManifestSha256!==kell\.unifiedManifestSha256/);
  assert.match(app,/result\?\.source\?\.runId!==data\?\.source\?\.runId/);
  assert.match(app,/chart shard Unified activation mismatch/);
});

test('Kell Hits filter does not treat every saved Unified name as a Kell hit',()=>{
  assert.match(app,/if\(filter==='kell-any'\)return Boolean\(/);
  assert.match(app,/item\?\.kellScreens/);
  assert.match(app,/item\?\.kellSetups/);
  assert.match(app,/item\?\.kellContext/);
});
