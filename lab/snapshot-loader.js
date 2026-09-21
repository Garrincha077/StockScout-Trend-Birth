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
    return data;
  }
  root.ReviewSnapshots = {load};
  if (typeof module !== 'undefined') module.exports = {load};
})(globalThis);
