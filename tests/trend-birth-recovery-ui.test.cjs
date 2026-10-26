const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {validateRecovery,horizonTotals,validateForward}=require('../lab/trend-birth-stats.js');
const fixture=()=>JSON.parse(readFileSync(__dirname+'/../lab/data/recovery-v3/comparison.json'));
test('recovery compares frozen matching dates and weights coverage by matured outcomes',()=>{
  const data=validateRecovery(fixture());
  assert.equal(horizonTotals(data.before,5).n,3255);
  assert.equal(horizonTotals(data.after,5).n,4567);
  assert.equal(horizonTotals(data.after,5).missing,109);
  assert.equal(horizonTotals(data.after,20).coverage,null);
  assert.throws(()=>validateForward(data.after),/Neispravno/);
});
test('rejects mixed dates, unverified replay, activation and calibration',()=>{
  for(const mutate of [d=>d.after.asOf='2026-10-26',d=>d.baselineReplayMatchesPublished=false,
    d=>d.migration.activated=true,d=>d.after.byHorizon['5']['4'].eligibleForCalibration=true,
    d=>d.after.byHorizon['5']['4'].missingMatured++]){
    const data=fixture();mutate(data);assert.throws(()=>validateRecovery(data));
  }
});
