// Exact snapshot links never fall back to a different run or to raw GitHub data.
(function (root) {
  const validId = value => /^[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}$/.test(value);
  async function decoded(response, path) {
    if (path.endsWith('.json.gz')) {
      if (typeof DecompressionStream !== 'function') throw new Error('Preglednik ne podržava gzip arhivu.');
      return new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).json();
    }
    return response.json();
  }
  async function json(fetcher, path) {
    const response = await fetcher(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('Snapshot nije dostupan (HTTP ' + response.status + ').');
    return decoded(response, path);
  }
  async function verifiedJson(fetcher,path,hash,label) {
    const response=await fetcher(path,{cache:'no-store'});
    if(!response.ok)throw Error(label+' · HTTP '+response.status);
    const bytes=await response.arrayBuffer();
    const sum=new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes));
    const digest=Array.from(sum,byte=>byte.toString(16).padStart(2,'0')).join('');
    if(digest!==hash)throw Error(label+' · kontrolni zbroj ne odgovara objavi.');
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  async function exactArchive(fetcher, base) {
    const path = base + '.json';
    const response = await fetcher(path, {cache: 'no-store'});
    if (response.ok) return decoded(response, path);
    if (response.status !== 404) throw new Error('Snapshot nije dostupan (HTTP ' + response.status + ').');
    return json(fetcher, base + '.json.gz');
  }
  function snapshotPath(manifest) {
    const base = 'data/snapshots/' + manifest.snapshotId;
    const actual = manifest.snapshotPath === undefined ? base + '.json' : manifest.snapshotPath;
    if (actual !== base + '.json' && actual !== base + '.json.gz') throw new Error('Neispravan put arhive.');
    return actual;
  }
  async function readPublication(fetcher) {
    const response = await fetcher('data/publication.json', {cache: 'no-store'});
    if (response.status === 404) return null;
    if (!response.ok) throw new Error('Objava trenutačno nije dostupna.');
    const manifest = await response.json();
    if (manifest.schemaVersion !== 'trend-birth-publication-v1' || !validId(manifest.snapshotId)) {
      throw new Error('Neispravna objava.');
    }
    return manifest;
  }
  async function load(fetcher, search) {
    const params = new URLSearchParams(search);
    const id = params.get('snapshot');
    const date = params.get('date');
    if (id !== null) {
      if (!validId(id)) throw new Error('Neispravan snapshot link.');
      return exactArchive(fetcher, 'data/snapshots/' + id);
    }
    if (date !== null) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('Neispravan datum.');
      return exactArchive(fetcher, 'data/history/' + date);
    }
    // Compatibility only before the first publication-v1 deployment.
    const manifest = await readPublication(fetcher);
    return manifest ? loadFull(fetcher, manifest) : exactArchive(fetcher, 'data/latest');
  }
  async function loadFull(fetcher, manifest) {
    const data = await json(fetcher, snapshotPath(manifest));
    if (data.source?.runId !== manifest.runId || data.source?.sessionDate !== manifest.sessionDate) {
      throw new Error('Objava i podaci nisu usklađeni.');
    }
    if (manifest.unifiedManifestSha256 && data.source?.unifiedManifestSha256 !== manifest.unifiedManifestSha256) {
      throw new Error('Objava nije vezana uz istu Unified aktivaciju.');
    }
    return data;
  }
  function aligned(data,manifest) {
    if(data?.source?.runId!==manifest.runId||data?.source?.sessionDate!==manifest.sessionDate||
        data?.source?.unifiedManifestSha256!==manifest.unifiedManifestSha256){
      throw new Error('Objava i podaci nisu usklađeni.');
    }
    return data;
  }
  async function loadInitial(fetcher,search) {
    const params=new URLSearchParams(search);
    if(params.has('snapshot')||params.has('date')||params.get('mode')==='legacy')return load(fetcher,search);
    return (await loadCurrent(fetcher)).data;
  }
  async function loadBootstrap(fetcher, manifest) {
    const expected=['v1','v2'].map(version=>'data/review-bootstrap-'+version+'/'+manifest.snapshotId+'.json');
    if(manifest.bootstrapPath===undefined)return aligned(await json(fetcher,snapshotPath(manifest)),manifest);
    if(!expected.includes(manifest.bootstrapPath))throw new Error('Neispravan put početnog pregleda.');
    const data=aligned(await json(fetcher,manifest.bootstrapPath),manifest);
    if(data.schemaVersion!=='trend-birth-review-bootstrap-v1'||data.reviewSnapshotId!==manifest.snapshotId||
        data.shortlists?.schemaVersion!=='stockscout-shortlists-v2'||
        !Array.isArray(data.shortlists.weeklyTrendBirth)||!Array.isArray(data.shortlists.kellDaily)){
      throw new Error('Neispravan početni pregled.');
    }
    return data;
  }
  async function loadShortlist(fetcher,bootstrap,view){
    const ref=bootstrap.deferredShortlists?.[view];
    if(!ref)return;
    const snapshotId=bootstrap.reviewSnapshotId;
    const path='data/review-bootstrap-v2/'+snapshotId+'/'+view+'--'+ref.sha256+'.json';
    if(!validId(snapshotId)||!['weeklyTrendBirth','kellSwing','kellDaily'].includes(view)||
        !/^[a-f0-9]{64}$/.test(ref.sha256)||path!==ref.path)throw Error('Neispravna lista kandidata.');
    const payload=aligned(await verifiedJson(fetcher,path,ref.sha256,'Lista kandidata'),bootstrap.source);
    if(payload.schemaVersion!=='trend-birth-shortlist-v1'||payload.snapshotId!==snapshotId||
        payload.view!==view||!Array.isArray(payload.items))throw Error('Lista i objava nisu usklađene.');
    bootstrap.shortlists[view]=payload.items;
    delete bootstrap.deferredShortlists[view];
  }
  async function loadCurrent(fetcher, {full = false, previousId = null} = {}) {
    const manifest = await readPublication(fetcher);
    if (!manifest) return {data: await exactArchive(fetcher, 'data/latest'), manifest: null};
    if (manifest.snapshotId === previousId) return {data: null, manifest};
    const data = await (full ? loadFull : loadBootstrap)(fetcher, manifest);
    return {data, manifest};
  }
  async function loadReports(fetcher, expectedDate, expectedRun) {
    const publication = await readPublication(fetcher);
    const ref = publication?.research;
    if (!ref) return null;
    const path = 'data/research-runs/' + publication.snapshotId + '--' + ref.sha256 + '.json';
    if (ref.schemaVersion !== 'trend-birth-review-research-v1' ||
        !/^[a-f0-9]{64}$/.test(ref.sha256) || ref.path !== path ||
        publication.sessionDate !== expectedDate || publication.runId !== expectedRun) {
      throw new Error('Izvještaji i trenutno prikazani podaci nisu usklađeni.');
    }
    const artifact=aligned(await verifiedJson(fetcher,path,ref.sha256,'Izvještaji'),publication);
    if (artifact.schemaVersion !== ref.schemaVersion || artifact.reviewSnapshotId !== publication.snapshotId ||
        !artifact.reports?.trendBirthForward || !artifact.reports?.kellForward) {
      throw new Error('Neispravni izvještaji objave.');
    }
    return artifact.reports;
  }
  async function loadChanges(fetcher,manifest) {
    const ref=manifest?.changes, schema='trend-birth-review-changes-v1';
    const path='data/review-change-runs/'+manifest?.snapshotId+'--'+ref?.sha256+'.json';
    if(!validId(manifest?.snapshotId)||ref?.schemaVersion!==schema||
        !/^[a-f0-9]{64}$/.test(ref.sha256)||ref.path!==path)throw Error('Neispravna poveznica pregleda promjena.');
    const result=aligned(await verifiedJson(fetcher,path,ref.sha256,'Pregled promjena'),manifest);
    const prior=result.previousSession;
    if(result.schemaVersion!==schema||result.snapshotId!==manifest.snapshotId||
        (prior!==null&&(!/^\d{4}-\d{2}-\d{2}$/.test(prior)||prior>=manifest.sessionDate))||
        (result.baseline!==null&&result.baseline?.sessionDate!==prior)||
        !['early','kell'].every(key=>{
          const strategy=result.strategies?.[key];
          return strategy&&['compared','no_baseline','no_overlap','unavailable'].includes(strategy.status)&&
            Array.isArray(strategy.events)&&Array.isArray(strategy.current)&&Number.isInteger(strategy.count)&&
            strategy.count>=strategy.events.length&&Number.isInteger(strategy.compared)&&strategy.compared>=0;
        }))throw Error('Pregled promjena i prikazana EOD objava nisu usklađeni.');
    return result;
  }
  async function loadSpyReference(fetcher,manifest) {
    const ref=manifest?.spyReference,schema='review-spy-reference-v1';
    const path='data/review-spy-runs/'+manifest?.snapshotId+'--'+ref?.sha256+'.json';
    if(!validId(manifest?.snapshotId)||ref?.schemaVersion!==schema||
        !/^[a-f0-9]{64}$/.test(ref.sha256)||ref.path!==path||
        !Number.isInteger(ref.sessionCount)||ref.sessionCount<0||ref.sessionCount>1265)
      throw Error('Neispravna poveznica SPY reference.');
    const payload=aligned(await verifiedJson(fetcher,path,ref.sha256,'SPY referenca'),manifest);
    if(payload.schemaVersion!==schema||payload.snapshotId!==manifest.snapshotId||payload.benchmark!=='SPY'||
        !Array.isArray(payload.points)||payload.points.length!==ref.sessionCount)
      throw Error('SPY referenca i EOD objava nisu usklađene.');
    const levels=new Map();
    let previous='';
    for(const row of payload.points){
      if(!Array.isArray(row)||row.length!==4)throw Error('Neispravna SPY referenca.');
      const [day,close,support,total]=row;
      if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day)||day<=previous||day>manifest.sessionDate||
          !Number.isFinite(close)||close<=0||!Number.isInteger(support)||!Number.isInteger(total)||
          support<5||support>total||support/total<.8)throw Error('Neispravna datirana SPY vrijednost.');
      levels.set(day,close);
      previous=day;
    }
    return levels;
  }
  async function loadResearch(fetcher,data) {
    if(data?.schemaVersion!=='trend-birth-review-bootstrap-v1')return data;
    if(!validId(data.reviewSnapshotId))throw new Error('Neispravan research snapshot.');
    const full=await exactArchive(fetcher,'data/snapshots/'+data.reviewSnapshotId);
    aligned(full,data.source);
    return full;
  }
  const watchlistSchema='trend-birth-watchlist-bucket-v1';
  const watchlistBucket=ticker=>new TextEncoder().encode(ticker).reduce((index,byte)=>(index*31+byte)%64,0);
  async function loadWatchlist(fetcher,manifest,tickers,cache) {
    const ref=manifest?.watchlist;
    if(!ref)throw Error('Objava nema indeks Watchliste.');
    const base='data/watchlist-runs/'+manifest.snapshotId;
    if(!validId(manifest.snapshotId)||ref.schemaVersion!==watchlistSchema||ref.basePath!==base||
        !Array.isArray(ref.sha256)||ref.sha256.length!==64||ref.sha256.some(hash=>!/^[a-f0-9]{64}$/.test(hash))||
        !/^data\/kell-chart-(?:runs|snapshots)\/[A-Za-z0-9][A-Za-z0-9_-]{0,259}$/.test(ref.chartBasePath)){
      throw Error('Neispravan indeks Watchliste.');
    }
    const loadBucket=index=>{
      if(!cache.has(index)){
        const path=base+'/'+index.toString(16).padStart(2,'0')+'.json';
        const request=verifiedJson(fetcher,path,ref.sha256[index],'Podaci za Watchlistu').then(data=>{
          aligned(data,manifest);
          if(data.schemaVersion!==watchlistSchema||data.snapshotId!==manifest.snapshotId||
              data.bucket!==index||!data.rows||Array.isArray(data.rows)||typeof data.rows!=='object'){
            throw Error('Objava i Watchlista nisu usklađene.');
          }
          return data.rows;
        }).catch(error=>{cache.delete(index);throw error});
        cache.set(index,request);
      }
      return cache.get(index);
    };
    const rows=await Promise.all(tickers.map(async ticker=>{
      const data=await loadBucket(watchlistBucket(ticker));
      const row=Object.hasOwn(data,ticker)?data[ticker]:null;
      if(row&&row.ticker!==ticker)throw Error('Neispravan ticker u Watchlisti.');
      return [ticker,row];
    }));
    return new Map(rows);
  }
  root.ReviewSnapshots = {load,loadInitial,loadCurrent,loadResearch,loadReports,loadChanges,loadSpyReference,loadShortlist,loadWatchlist,watchlistBucket};
  if (typeof module !== 'undefined') module.exports = root.ReviewSnapshots;
})(globalThis);
