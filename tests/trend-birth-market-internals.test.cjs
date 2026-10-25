const test = require('node:test');
const assert = require('node:assert/strict');
const Stats = require('../lab/trend-birth-stats.js');
const fs = require('node:fs');
const path = require('node:path');

function point(date, counts) {
  const total=counts.reduce((a,b)=>a+b,0);
  const obj=Object.fromEntries(counts.map((n,i)=>[String(i),n]));
  return {sessionDate:date, counts:obj, evaluatedCount:total,
    qualityBreadthPct:100*(counts[3]+counts[4])/total,
    fourBreadthPct:100*counts[4]/total,
    pressurePct:100*counts.reduce((a,n,i)=>a+n*i,0)/(4*total)};
}
test('real, compact internals pass full reconciliation',()=>{
  const obj=JSON.parse(fs.readFileSync(path.join(__dirname,'../lab/data/trend-birth-market-internals.json'),'utf8'));
  assert.equal(Stats.validate(obj),obj);
  assert.ok(obj.points.length>=20);
  assert.equal(obj.points[0].previousSessionDate,null);
  assert.equal(obj.points.at(-1).sessionDate,obj.latestSessionDate);
});
test('negative and incomplete stage counts are rejected',()=>{
  const o=JSON.parse(fs.readFileSync(path.join(__dirname,'../lab/data/trend-birth-market-internals.json'),'utf8'));
  o.points[0].counts['0']--;
  assert.throws(()=>Stats.validate(o),/faza/);
});
test('weighted weekly/monthly breadth uses ticker-days, not naive mean',()=>{
  const rows=[point('2026-10-22',[5,0,0,0,5]),point('2026-10-23',[30,0,0,0,0])];
  const week=Stats.group(rows,'W');
  assert.equal(week.length,1);
  assert.equal(week[0].days,2);
  assert.equal(week[0].evaluatedCount,40);
  assert.equal(week[0].fourBreadthPct,12.5);
  assert.equal(week[0].qualityBreadthPct,12.5);
  assert.equal(Stats.group(rows,'D').length,2);
  assert.equal(Stats.group(rows,'M').length,1);
});
test('rolling velocity/acceleration are in percentage points per observed EOD',()=>{
  const rows=Array.from({length:10},(_,i)=>({...point('2026-10-'+String(1+i).padStart(2,'0'),[8,0,0,0,2]),qualityBreadthPct:i*i}));
  const dyn=Stats.dynamics(rows,9,5,'qualityBreadthPct');
  assert.ok(Math.abs(dyn.velocity-14)<1e-9);
  assert.ok(Math.abs(dyn.acceleration-10)<1e-9);
  assert.equal(Stats.dynamics(rows,6,5,'qualityBreadthPct').acceleration,null);
  assert.equal(Stats.slope(rows,3,5,'qualityBreadthPct'),null);
});
test('point-in-time percentiles do not include current or future readings',()=>{
  const rows=[10,15,20,10].map((v,i)=>({...point('2026-10-0'+(1+i),[3,0,0,0,1]),qualityBreadthPct:v}));
  assert.deepEqual(Stats.percentile(rows,0,'qualityBreadthPct'),{value:null,comparisons:0});
  assert.deepEqual(Stats.percentile(rows,2,'qualityBreadthPct'),{value:100,comparisons:2});
  assert.deepEqual(Stats.percentile(rows,3,'qualityBreadthPct'),{value:100*(0+.5*1)/3,comparisons:3});
});
test('transition selection excludes preceding day outside selected range',()=>{
  const file=JSON.parse(fs.readFileSync(path.join(__dirname,'../lab/data/trend-birth-market-internals.json'),'utf8'));
  const first=file.points[2], second=file.points[3];
  const partial=Stats.transitions([first,second],second.sessionDate);
  assert.equal(partial.pairs,0);
  const both=Stats.transitions([first,second],first.sessionDate);
  assert.equal(both.pairs,1); // first point's predecessor lies outside this range
});
test('regime labels are descriptive and refuse missing acceleration',()=>{
  assert.match(Stats.regime(null,3),/Premalo/);
  assert.match(Stats.regime(1,-1),/usporava/);
  assert.match(Stats.regime(-1,-1),/ubrzava/);
});

test('derived velocity chart preserves nulls and excludes unavailable percentile samples',()=>{
  const points=Array.from({length:12},(_,i)=>point('2026-10-'+String(1+i).padStart(2,'0'),[7,0,0,2,1]));
  points.forEach((p,i)=>p.qualityBreadthPct=i);
  const derived=Stats.withDynamics(points,5);
  assert.equal(derived[0].velocityPp,null);
  assert.equal(derived[9].velocityPp,1);
  assert.equal(derived[9].accelerationPp,0);
  assert.deepEqual(Stats.percentile(derived,3,'velocityPp'),{value:null,comparisons:0});
  assert.equal(Stats.percentile(derived,11,'velocityPp').comparisons,7);
  assert.equal(Stats.group(derived,'M')[0].accelerationPp,0);
});

test('stage forward source-session gap accounting is fail-closed',()=>{
  const raw=JSON.parse(fs.readFileSync(path.join(__dirname,'../lab/data/trend-birth-stage-forward.json'),'utf8'));
  const q={archiveStart:'2026-09-24',archivedSessions:20,exchangeSessionsSinceStart:22,
    missingExchangeSessions:['2026-10-15','2026-10-19'],actualSourceQuotes:53000,
    expectedSourceQuotes:53000,sourcePriceCoveragePct:100};
  raw.dataQuality=q;
  for(const horizon of raw.horizons) for(let stage=0;stage<=4;stage++) {
    const row=raw.byHorizon[String(horizon)][String(stage)];
    row.missingSessionGap=row.missingMatured;
    row.missingTickerQuote=0;
    row.missingUnclassified=0;
  }
  assert.equal(Stats.validateForward(raw),raw);
  raw.byHorizon['5']['3'].missingSessionGap++;
  assert.throws(()=>Stats.validateForward(raw),/Dijagnostika/);
  raw.byHorizon['5']['3'].missingSessionGap--;
  raw.dataQuality.missingExchangeSessions=[];
  assert.throws(()=>Stats.validateForward(raw),/pokrivenost/);
});
