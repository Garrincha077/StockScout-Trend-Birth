const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Heat=require('../lab/trend-birth-heat.js');

const real=JSON.parse(fs.readFileSync(path.join(__dirname,'../lab/data/trend-birth-market-internals.json'),'utf8'));
const forward=JSON.parse(fs.readFileSync(path.join(__dirname,'../lab/data/trend-birth-stage-forward.json'),'utf8'));
const realCalendar=Heat.exchangeCalendar(real.points,forward);
const initialPoints=real.points.filter(p=>p.sessionDate<='2026-10-23');
const legacyForward={asOf:'2026-10-23',dataQuality:{coverageWindowStart:'2026-09-24',
  archivedSessions:20,exchangeSessionsInWindow:22,missingExchangeSessions:['2026-10-15','2026-10-19']}};
function tradingDates(n) {
  const dates=[],d=new Date('2024-01-02T12:00:00Z');
  while(dates.length<n) {
    if(d.getUTCDay()!==0&&d.getUTCDay()!==6)dates.push(d.toISOString().slice(0,10));
    d.setUTCDate(d.getUTCDate()+1);
  }
  return dates;
}
function synthetic(n) {
  return tradingDates(n).map((sessionDate,i)=>({
    sessionDate,qualityBreadthPct:20+10*Math.sin(i/7)+i/25,
    fourBreadthPct:5+4*Math.sin(i/9)+i/100,
    pressurePct:35+10*Math.sin(i/5)+i/30,
    matchedQualityDeltaPp:i?Math.cos(i/7):null,
    overlapPct:i?99:null
  }));
}
test('five equal zones, inclusive 100 and boundary decisions',()=>{
  const expect=[[0,'very-cold'],[19.999,'very-cold'],[20,'cold'],[39.999,'cold'],
    [40,'neutral'],[59.999,'neutral'],[60,'hot'],[79.999,'hot'],
    [80,'overheated'],[100,'overheated']];
  expect.forEach(([score,key])=>assert.equal(Heat.zoneFor(score)?.key,key));
  assert.equal(Heat.zoneFor(null),null);
  assert.equal(Heat.zoneFor(101),null);
});
test('midrank percentile uses only at least 12 earlier observations, caps at 252',()=>{
  assert.deepEqual(Heat.percentile(4,Array(11).fill(3)),{value:null,historyN:11});
  assert.equal(Heat.percentile(5,Array(12).fill(5)).value,50);
  assert.equal(Heat.percentile(5,[...Array(6).fill(3),...Array(6).fill(5)]).value,75);
  assert.equal(Heat.percentile(3,Array(300).fill(4)).historyN,252);
});
test('actual EOD history is strictly point-in-time and first 12 days cannot score',()=>{
  const rows=Heat.computeHeatHistory(real.points);
  assert.equal(rows.length,real.points.length);
  assert.equal(rows.filter(x=>x.score!==null).length,real.points.length-Heat.MIN_HISTORY);
  assert.equal(rows.find(x=>x.score!==null).sessionDate,'2026-10-12');
  assert.ok(rows.slice(0,12).every(x=>x.score===null));
  const last=rows.find(p=>p.sessionDate==='2026-10-23');
  assert.equal(last.zone.key,'cold');
  assert.equal(last.maturity,'provisional');
  assert.equal(last.readyHeat,3);
  assert.ok(Math.abs(last.score-33.91812865497076)<0.00001);
  assert.ok(Math.abs(last.heatRows.reduce((v,r)=>v+r.contribution,0)-last.score)<1e-10);
  assert.equal(last.heatRows.find(r=>r.key==='persistence').historyN,10);
  assert.equal(last.heatRows.find(r=>r.key==='persistence').ready,false);
  assert.deepEqual(rows.map(r=>r.sessionDate),real.points.map(r=>r.sessionDate));
  assert.equal(rows.some(r=>r.sessionDate==='2026-10-15'),false);
  assert.equal(rows.some(r=>r.sessionDate==='2026-10-19'),false);
});
test('future EOD rows never modify earlier historical score, rank, or labels',()=>{
  const base=synthetic(75),long=Heat.computeHeatHistory(base);
  const expanded=Heat.computeHeatHistory([...base,...synthetic(80).slice(75)]);
  assert.deepEqual(expanded.slice(0,base.length),long);
});
test('persistence starts after its own 12 historical 10-day means; weights renormalize',()=>{
  const rows=Heat.computeHeatHistory(synthetic(26));
  const earlier=rows[20],ready=rows[21];
  assert.equal(earlier.readyHeat,3);
  assert.equal(ready.readyHeat,4);
  assert.equal(earlier.heatRows.find(r=>r.key==='breadth').normalizedWeight,100*40/90);
  assert.equal(ready.heatRows.find(r=>r.key==='breadth').normalizedWeight,40);
  assert.ok(ready.heatRows.some(r=>r.key==='persistence'&&r.historyN===12&&r.ready));
  assert.ok(Math.abs(ready.heatRows.reduce((a,r)=>a+r.contribution,0)-ready.score)<1e-10);
});
test('flow is excluded when universe overlap is low; non-contiguous EODs are not joined',()=>{
  const rows=synthetic(30);rows[29].overlapPct=80;
  const history=Heat.computeHeatHistory(rows);
  assert.equal(history.at(-1).qualityWarning,true);
  assert.equal(history.at(-1).movementRows.find(r=>r.key==='flow').ready,false);
  const calendar=Heat.exchangeCalendar(initialPoints,legacyForward);
  assert.equal(Heat.computeHeatHistory(initialPoints,calendar).find(x=>x.sessionDate==='2026-10-20').continuity,false);
  // An untrustworthy comparison must not contaminate later flow percentile history.
  const longer=synthetic(30),baseline=Heat.computeHeatHistory(longer);
  longer[13].overlapPct=40;longer[13].matchedQualityDeltaPp=9999;
  const guarded=Heat.computeHeatHistory(longer);
  const b=baseline.at(-1).movementRows.find(r=>r.key==='flow');
  const g=guarded.at(-1).movementRows.find(r=>r.key==='flow');
  assert.equal(g.historyN,b.historyN-1);
});
test('exchange sessions preserve holiday continuity and detect actual missing EODs',()=>{
  // Thanksgiving and Good Friday are closed exchanges, not missing observations.
  for(const days of [
    ['2026-11-25','2026-11-27','2026-11-30'],
    ['2026-04-02','2026-04-06','2026-04-07'],
    ['2026-01-16','2026-01-20','2026-01-21'],
  ]){
    const points=synthetic(days.length).map((p,i)=>({...p,sessionDate:days[i]}));
    assert.ok(Heat.computeHeatHistory(points,days).every(p=>p.continuity));
  }
  const points=synthetic(2).map((p,i)=>({...p,sessionDate:['2026-10-16','2026-10-20'][i]}));
  assert.equal(Heat.computeHeatHistory(points,['2026-10-16','2026-10-19','2026-10-20'])[1].continuity,false);
  assert.equal(Heat.computeHeatHistory(points)[1].continuity,null);
  assert.throws(()=>Heat.computeHeatHistory(points,['2026-10-20','2026-10-16']),/kalendar/);
});
test('calendar comes from the aligned forward report, with a safe older-V2 fallback',()=>{
  const initialCalendar=Heat.exchangeCalendar(initialPoints,legacyForward);
  assert.equal(initialCalendar.length,22);
  assert.ok(initialCalendar.includes('2026-10-15'));
  assert.ok(initialCalendar.includes('2026-10-19'));
  assert.deepEqual(Heat.exchangeCalendar(real.points,{...forward,exchangeSessions:realCalendar}),realCalendar);
  assert.deepEqual(Heat.exchangeCalendar(real.points,{...forward,asOf:'2026-10-22'}),[]);
  const broken=structuredClone(legacyForward);
  broken.dataQuality.missingExchangeSessions=[];
  assert.deepEqual(Heat.exchangeCalendar(initialPoints,broken),[]);
  assert.deepEqual(Heat.exchangeCalendar(real.points,null),[]);
});
test('rejected out-of-order dates and no date fabrication',()=>{
  assert.throws(()=>Heat.computeHeatHistory([{sessionDate:'2026-10-03'},{sessionDate:'2026-10-03'}]),/uređeni/);
  assert.equal(Heat.windowStart('2026-10-23','1m'),'2026-09-23');
});
