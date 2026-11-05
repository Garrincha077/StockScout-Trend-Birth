const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {validateForward}=require('../lab/trend-birth-stats.js');
const fixture=()=>JSON.parse(readFileSync(__dirname+'/../lab/data/trend-birth-stage-forward.json'));
test('tracking coverage stays separate from evaluated-universe price coverage',()=>{
  const data=fixture();
  const primaryCoverage=data.dataQuality.sourcePriceCoveragePct;
  data.outcomeTracking={schemaVersion:'trend-birth-outcome-tracking-v1',asOf:data.asOf,
    startAfterSessionDate:'2026-09-23',enabled:true,status:'partial',
    trackedCount:1177,primaryCoveredCount:1122,supplementalCount:50,missingCount:5,
    calibrationApproved:false,historyBackfilled:false};
  assert.equal(validateForward(data).outcomeTracking.missingCount,5);
  assert.equal(data.dataQuality.sourcePriceCoveragePct,primaryCoverage);
  for(const mutate of [t=>t.missingCount=0,t=>t.asOf='2026-10-22',t=>t.calibrationApproved=true,
    t=>t.trackedCount=-1,t=>t.enabled=false]){
    const wrong=structuredClone(data);mutate(wrong.outcomeTracking);assert.throws(()=>validateForward(wrong),/praćenje/);
  }
});
