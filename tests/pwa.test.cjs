const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../lab');

function workerHarness() {
  const listeners = {};
  const deleted = [];
  const stored = [];
  const network = [];
  let offline = false;
  let activated = false;
  const offlinePage = new Response('offline screen', {headers: {'Content-Type': 'text/html'}});
  const scope = 'https://example.test/lab/';
  const cache = {
    addAll: async urls => stored.push(...urls),
    match: async url => (typeof url === 'string' ? url : url.url) === scope + 'offline.html' ? offlinePage : undefined
  };
  const context = {
    URL, Response,
    self: {
      registration: {scope}, location: {origin: 'https://example.test'},
      addEventListener: (type, listener) => { listeners[type] = listener; },
      clients: {claim: async () => {}},
      skipWaiting: async () => { activated = true; }
    },
    caches: {
      open: async () => cache,
      keys: async () => ['trendbirth-install-v0', 'another-app-cache', 'trendbirth-install-v1'],
      delete: async key => { deleted.push(key); }
    },
    fetch: async request => {
      network.push(request.url);
      if (offline) throw new TypeError('offline');
      return {body: 'network', url: request.url};
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'sw.js'), 'utf8'), context);
  const lifecycle = async (name, data) => {
    let promise;
    listeners[name]({data, waitUntil: value => { promise = value; }});
    await promise;
  };
  const request = async (url, mode = 'cors', method = 'GET') => {
    let response;
    listeners.fetch({request: {url, mode, method}, respondWith: value => { response = value; }});
    return response;
  };
  return {scope, stored, deleted, network, offlinePage, lifecycle, request, setOffline: () => { offline = true; }, activated: () => activated};
}

test('manifest has a stable app identity and valid PNG install icons', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.webmanifest')));
  assert.equal(manifest.display, 'standalone');
  assert.equal(manifest.id, './');
  assert.equal(manifest.start_url, './');
  assert.equal(manifest.scope, './');
  assert.equal(manifest.short_name, 'Trend Birth');
  for (const icon of manifest.icons) {
    const image = fs.readFileSync(path.join(root, icon.src));
    const size = Number(icon.sizes.split('x')[0]);
    assert.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
    assert.equal(image.readUInt32BE(16), size);
    assert.equal(image.readUInt32BE(20), size);
  }
  assert.ok(manifest.icons.some(icon => icon.purpose === 'maskable'));
});

test('installation precaches only artwork, manifest and offline screen', async () => {
  const worker = workerHarness();
  await worker.lifecycle('install');
  assert.equal(worker.stored.length, 7);
  for (const url of worker.stored) {
    assert.ok(url.startsWith(worker.scope));
    assert.ok(fs.existsSync(path.join(root, url.slice(worker.scope.length))));
    assert.doesNotMatch(url, /data\/|app\.js|config\.js|watchlist|index\.html/);
  }
  assert.equal(worker.activated(), false, 'updates must wait for user action');
});

test('activation removes only older Trend Birth install caches', async () => {
  const worker = workerHarness();
  await worker.lifecycle('activate');
  assert.deepEqual(worker.deleted, ['trendbirth-install-v0']);
  await worker.lifecycle('message', {type: 'ACTIVATE_UPDATE'});
  assert.equal(worker.activated(), true);
});

test('current publication, immutable snapshots, auth and app scripts bypass caches', async () => {
  const worker = workerHarness();
  for (const resource of ['data/publication.json', 'data/latest.json', 'data/snapshots/exact.json', 'data/kell-latest.json', 'data/kell-charts/AAPL.json', 'config.js', 'app.js', 'owner-watchlist-sync.js', 'auth/callback?code=secret']) {
    assert.equal(await worker.request(worker.scope + resource), undefined, resource);
  }
  assert.equal(await worker.request('https://auth.example.test/token'), undefined);
  assert.equal(await worker.request(worker.scope + 'data/save', 'cors', 'POST'), undefined);
  assert.deepEqual(worker.network, []);
});

test('navigation preserves exact snapshot/auth URL online and shows explicit offline page on failure', async () => {
  const worker = workerHarness();
  const url = worker.scope + '?snapshot=exact--abc&code=callback';
  assert.equal((await worker.request(url, 'navigate')).url, url);
  worker.setOffline();
  const fallback = await worker.request(url, 'navigate');
  assert.equal(await fallback.text(), 'offline screen');
  assert.equal(fallback.redirected, false);
  assert.equal(fallback.headers.get('Content-Type'), 'text/html');
  assert.deepEqual(worker.network, [url, url]);
});
