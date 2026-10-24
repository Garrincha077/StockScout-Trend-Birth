const test = require('node:test');
const assert = require('node:assert/strict');
const T = require('../lab/trend-birth-intelligence.js');
const scope = 'unified-plus-tracked-watchlist';
function day(date, stages, unavailable = []) {
  const counts={0:0,1:0,2:0,3:0,4:0};
  Object.values(stages).forEach(([stage])=>counts[stage]++);
  return {sessionDate:date,runId:'run-'+date,stages,counts,
    evaluatedCount:Object.keys(stages).length,unavailable,unavailableCount:unavailable.length};
}
function month(name,sessions){return {schemaVersion:'trend-birth-ticker-month-v1',month:name,scope,sessions};}
test('summary must reconcile counts and provenance',()=>{
  const good={schemaVersion:'trend-birth-intelligence-v1',source:{sessionDate:'2026-10-24',runId:'r',scope},
    counts:{0:1,1:1,2:1,3:1,4:1},evaluatedCount:5,topOpportunities:[]};
  assert.equal(T.validateSummary(good,'2026-10-24',scope),good);
  assert.throws(()=>T.validateSummary(good,'2026-10-23',scope),/datum/);
  assert.throws(()=>T.validateSummary({...good,evaluatedCount:4},'2026-10-24',scope),/brojčani/);
  assert.throws(()=>T.validateSummary(good,'2026-10-24','other'),/univerzum/);
});
test('month ranges cross year and do not include irrelevant months',()=>{
  assert.deepEqual(T.monthsInPeriod('2025-12-28','2026-02-01'),['2025-12','2026-01','2026-02']);
  assert.throws(()=>T.monthsInPeriod('2026-11-01','2026-10-01'),/raspon/);
});
test('ticker members reconcile selected day and week with ticker-days',()=>{
  const a=day('2026-10-23',{AAA:[3,7],BBB:[4,9]});
  const b=day('2026-10-24',{AAA:[4,15],CCC:[4,7]});
  const payload=T.validateMonth(month('2026-10',[a,b]),'2026-10',scope);
  const daily=T.membersForPeriod([payload],{periodKey:a.sessionDate,periodEnd:a.sessionDate,
    sessionCount:1,counts:a.counts},'4','2026-10-24');
  assert.deepEqual(daily.members.map(x=>x.ticker),['BBB']);
  const weekly=T.membersForPeriod([payload],{periodKey:'2026-10-19',periodEnd:'2026-10-25',
    sessionCount:2,counts:{4:3}},'4','2026-10-24');
  assert.deepEqual(weekly.members.map(x=>x.ticker),['AAA','BBB','CCC']);
  assert.equal(weekly.tickerDays,3);
  assert.throws(()=>T.membersForPeriod([payload],{periodKey:'2026-10-19',periodEnd:'2026-10-25',
    sessionCount:3,counts:{4:3}},'4'),/nisu potpuni/);
});
test('invalid monthly counts and duplicated unavailable fail closed',()=>{
  const good=day('2026-10-23',{AAA:[3,1]},['DDD']);
  assert.throws(()=>T.validateMonth(month('2026-10',[{...good,unavailable:['DDD','DDD']}]),'2026-10',scope));
  assert.throws(()=>T.validateMonth(month('2026-10',[{...good,counts:{0:1}}]),'2026-10',scope));
});
test('journey ignores ticker absent from universe rather than assigning zero',()=>{
  const a=day('2026-10-23',{AAA:[2,1]});
  const b=day('2026-10-24',{AAA:[3,3]},['BBB']);
  const list=T.journey([month('2026-10',[a,b])],'AAA','2026-10-24');
  assert.deepEqual(list.map(x=>x.stage),[2,3]);
  assert.deepEqual(T.journey([month('2026-10',[a,b])],'BBB').map(x=>x.unavailable),[true]);
});
test('lazy monthly archive loader caches verified results',async()=>{
  let calls=0;
  const file=month('2026-10',[day('2026-10-24',{AAA:[4,3]})]);
  const fetcher=async()=>{calls++;return {ok:true,json:async()=>file}};
  const cache=new Map();
  assert.equal((await T.loadMonths(fetcher,['2026-10'],cache,scope,'2026-10')).length,1);
  await T.loadMonths(fetcher,['2026-10'],cache,scope,'2026-10');
  assert.equal(calls,1);
});
