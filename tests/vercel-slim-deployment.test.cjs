const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');

const repo = path.resolve(__dirname, '..');
const base = 'https://raw.githubusercontent.com/Garrincha077/StockScout-Trend-Birth/feature/unified-review-grid-lab/lab/data/:path*';

test('both possible Vercel roots publish no JSON data, with a path-preserving external rewrite', () => {
  for (const filename of ['vercel.json', 'lab/vercel.json']) {
    const config = JSON.parse(fs.readFileSync(path.join(repo, filename), 'utf8'));
    assert.equal(config.outputDirectory, 'dist');
    assert.equal(config.rewrites.length, 1);
    assert.deepEqual(config.rewrites[0], {source: '/data/:path*', destination: base});
    assert.match(config.buildCommand, /build-vercel\.mjs/);
  }
});

test('UI-only build retains scripts and images but never embeds historical data', () => {
  for (const workdir of ['repository-root', 'lab-root']) {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'trend-birth-deploy-'));
    try {
      const lab = path.join(tmp, 'lab');
      fs.mkdirSync(path.join(lab, 'icons'), {recursive: true});
      fs.mkdirSync(path.join(lab, 'data', 'snapshots'), {recursive: true});
      const script = path.join(lab, 'build-vercel.mjs');
      fs.copyFileSync(path.join(repo, 'lab', 'build-vercel.mjs'), script);
      for (const item of ['index.html', 'snapshot-loader.js', 'kell-dataset-loader.js', 'app.js', 'styles.css']) {
        fs.writeFileSync(path.join(lab, item), item);
      }
      fs.writeFileSync(path.join(lab, 'icons', 'logo.svg'), '<svg/>');
      fs.writeFileSync(path.join(lab, 'data', 'latest.json'), '{"large":true}');
      fs.writeFileSync(path.join(lab, 'data', 'snapshots', 'old.json'), '{"historical":true}');
      const cwd = workdir === 'lab-root' ? lab : tmp;
      const build = spawnSync(process.execPath, [script], {cwd, encoding: 'utf8', timeout: 20000});
      assert.equal(build.status, 0, build.stderr || build.stdout);
      const dist = path.join(cwd, 'dist');
      assert.ok(fs.existsSync(path.join(dist, 'index.html')));
      assert.ok(fs.existsSync(path.join(dist, 'snapshot-loader.js')));
      assert.ok(fs.existsSync(path.join(dist, 'icons', 'logo.svg')));
      assert.equal(fs.existsSync(path.join(dist, 'data')), false);
      assert.equal(fs.existsSync(path.join(dist, 'build-vercel.mjs')), false);
      assert.equal(fs.existsSync(path.join(dist, 'vercel.json')), false);
    } finally {
      fs.rmSync(tmp, {recursive: true, force: true});
    }
  }
});
