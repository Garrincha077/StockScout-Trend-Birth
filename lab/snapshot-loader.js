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
    const expected='data/review-bootstrap-v1/'+manifest.snapshotId+'.json';
    if(manifest.bootstrapPath===undefined)return aligned(await json(fetcher,snapshotPath(manifest)),manifest);
    if(manifest.bootstrapPath!==expected)throw new Error('Neispravan put početnog pregleda.');
    const data=aligned(await json(fetcher,expected),manifest);
    if(data.schemaVersion!=='trend-birth-review-bootstrap-v1'||data.reviewSnapshotId!==manifest.snapshotId||
        data.shortlists?.schemaVersion!=='stockscout-shortlists-v2'||
        !Array.isArray(data.shortlists.weeklyTrendBirth)||!Array.isArray(data.shortlists.kellDaily)){
      throw new Error('Neispravan početni pregled.');
    }
    return data;
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
    const response = await fetcher(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('Izvještaji nisu dostupni (HTTP ' + response.status + ').');
    const bytes = await response.arrayBuffer();
    const sum = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes));
    const digest = [...sum].map(byte => byte.toString(16).padStart(2, '0')).join('');
    if (digest !== ref.sha256) throw new Error('Kontrolni zbroj izvještaja nije točan.');
    const artifact = aligned(JSON.parse(new TextDecoder().decode(bytes)), publication);
    if (artifact.schemaVersion !== ref.schemaVersion || artifact.reviewSnapshotId !== publication.snapshotId ||
        !artifact.reports?.trendBirthForward || !artifact.reports?.kellForward) {
      throw new Error('Neispravni izvještaji objave.');
    }
    return artifact.reports;
  }
  async function loadResearch(fetcher,data) {
    if(data?.schemaVersion!=='trend-birth-review-bootstrap-v1')return data;
    if(!validId(data.reviewSnapshotId))throw new Error('Neispravan research snapshot.');
    const full=await exactArchive(fetcher,'data/snapshots/'+data.reviewSnapshotId);
    aligned(full,data.source);
    return full;
  }
  root.ReviewSnapshots = {load,loadInitial,loadCurrent,loadResearch,loadReports};
  if (typeof module !== 'undefined') module.exports = root.ReviewSnapshots;
})(globalThis);
