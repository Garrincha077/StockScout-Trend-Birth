const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {assess}=require('../lab/eod-freshness.js');
const calendar=JSON.parse(readFileSync(__dirname+'/../lab/data/exchange-sessions-v1.json'));
test('freshness follows close plus grace, including early closes and DST',()=>{
  const check=(day,now)=>assess(calendar,day,Date.parse(now));
  assert.deepEqual(check('2026-10-23','2026-10-26T23:59:59Z'),{expected:'2026-10-23',stale:false});
  assert.deepEqual(check('2026-10-23','2026-10-27T00:00:00Z'),{expected:'2026-10-26',stale:true});
  assert.equal(check('2026-11-25','2026-11-27T22:00:00Z').expected,'2026-11-27');
  assert.equal(check('2026-10-30','2026-11-03T00:30:00Z').stale,false);
  assert.throws(()=>check('2026-10-26','2026-10-26T18:00:00Z'),/završena/);
  assert.throws(()=>check('2026-10-24','2026-10-26T18:00:00Z'),/završena/);
  assert.throws(()=>check('2030-12-31','2031-01-01T18:00:00Z'),/Kalendar/);
});
