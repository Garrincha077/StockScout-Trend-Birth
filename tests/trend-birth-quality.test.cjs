const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const quality=require('../lab/trend-birth-quality.js');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'lab/index.html'),'utf8');
const app=fs.readFileSync(path.join(root,'lab/app.js'),'utf8');
const workflow=fs.readFileSync(path.join(root,'.github/workflows/unified-review-grid-lab.yml'),'utf8');
const point=(day,counts=[10,8,6,3,1])=>{
  const stages=Object.fromEntries(counts.map((value,index)=>[String(index),value]));
  return {sessionDate:day,scope:'unified-plus-tracked-watchlist',counts:stages,
    evaluatedCount:counts.reduce((a,b)=>a+b,0),unavailableCount:2,universeCount:counts.reduce((a,b)=>a+b,0)+2};
};
test('zero through four reconcile without converting missing data to zero',()=>{
  const p=point('2026-10-23');
  const summary=quality.normalizeRadar({stageCounts:p.counts,evaluatedCount:p.evaluatedCount,unavailableCount:p.unavailableCount});
  assert.equal(summary.evaluatedCount,28);
  assert.equal(summary.universeCount,30);
  assert.equal(quality.count(summary,'3+'),4);
  assert.equal(quality.normalizeRadar({stageCounts:p.counts,evaluatedCount:30,unavailableCount:0}),null);
});
test('history respects scope, archived date and chronological ordering',()=>{
  const payload={schemaVersion:'trend-birth-quality-history-v1',scope:'unified-plus-tracked-watchlist',
    points:[point('2026-10-23'),point('2026-10-21'),point('2026-10-22')]};
  assert.deepEqual(quality.normalizeHistory(payload,'2026-10-22',payload.scope).map(p=>p.sessionDate),['2026-10-21','2026-10-22']);
  assert.throws(()=>quality.normalizeHistory(payload,null,'wrong'));
});
test('app wires all stage tiles and selective historical chart to daily archives',()=>{
  for(const stage of ['0','1','2','3','4'])assert.match(html,new RegExp('<option value="'+stage+'"'));
  assert.match(html,/id="tbQualityCounts"/);
  assert.match(html,/id="tbQualityHistory"/);
  assert.match(html,/trend-birth-quality\.js/);
  assert.match(app,/data\/trend-birth-quality-history\.json/);
  assert.match(app,/TrendBirthQuality\.normalizeHistory/);
  assert.match(workflow,/scripts\/trend_birth_quality_history\.py --history-dir lab\/data\/history/);
});
