// Exact snapshot links never fall back to a different run or to raw GitHub data.
(function (root) {
  const validId = value => /^[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}$/.test(value);
  async function json(fetcher, path) {
    const response = await fetcher(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('Snapshot nije dostupan (HTTP ' + response.status + ').');
    return response.json();
  }
  async function load(fetcher, search) {
    const params = new URLSearchParams(search);
    const id = params.get('snapshot');
    const date = params.get('date');
    if (id !== null) {
      if (!validId(id)) throw new Error('Neispravan snapshot link.');
      return json(fetcher, 'data/snapshots/' + id + '.json');
    }
    if (date !== null) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('Neispravan datum.');
      return json(fetcher, 'data/history/' + date + '.json');
    }
    const response = await fetcher('data/publication.json', {cache: 'no-store'});
    // Compatibility only before the first publication-v1 deployment.
    if (response.status === 404) return json(fetcher, 'data/latest.json');
    if (!response.ok) throw new Error('Objava trenutačno nije dostupna.');
    const manifest = await response.json();
    if (manifest.schemaVersion !== 'trend-birth-publication-v1' || !validId(manifest.snapshotId)) {
      throw new Error('Neispravna objava.');
    }
    const data = await json(fetcher, 'data/snapshots/' + manifest.snapshotId + '.json');
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
    const response=await fetcher('data/publication.json',{cache:'no-store'});
    if(response.status===404)return json(fetcher,'data/latest.json');
    if(!response.ok)throw new Error('Objava trenutačno nije dostupna.');
    const manifest=await response.json();
    if(manifest.schemaVersion!=='trend-birth-publication-v1'||!validId(manifest.snapshotId))throw new Error('Neispravna objava.');
    const expected='data/review-bootstrap-v1/'+manifest.snapshotId+'.json';
    if(manifest.bootstrapPath===undefined)return aligned(await json(fetcher,'data/snapshots/'+manifest.snapshotId+'.json'),manifest);
    if(manifest.bootstrapPath!==expected)throw new Error('Neispravan put početnog pregleda.');
    const data=aligned(await json(fetcher,expected),manifest);
    if(data.schemaVersion!=='trend-birth-review-bootstrap-v1'||data.reviewSnapshotId!==manifest.snapshotId||
        data.shortlists?.schemaVersion!=='stockscout-shortlists-v2'||
        !Array.isArray(data.shortlists.weeklyTrendBirth)||!Array.isArray(data.shortlists.kellDaily)){
      throw new Error('Neispravan početni pregled.');
    }
    return data;
  }
  async function loadResearch(fetcher,data) {
    if(data?.schemaVersion!=='trend-birth-review-bootstrap-v1')return data;
    if(!validId(data.reviewSnapshotId))throw new Error('Neispravan research snapshot.');
    const full=await json(fetcher,'data/snapshots/'+data.reviewSnapshotId+'.json');
    aligned(full,data.source);
    return full;
  }
  root.ReviewSnapshots = {load,loadInitial,loadResearch};
  if (typeof module !== 'undefined') module.exports = {load,loadInitial,loadResearch};
})(globalThis);
