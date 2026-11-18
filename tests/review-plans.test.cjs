const {test}=require('node:test');
const assert=require('node:assert/strict');
const Plans=require('../lab/review-plans.js');
const first='2026-11-13',next='2026-11-16',last='2026-11-17';
const snapshot=first+'-eod-123-1--'+'a'.repeat(64);
const chart=[[first,100],[next,108],[last,102]].map(([day,close])=>({day,close}));
const calendar={schemaVersion:'xnys-eod-sessions-v1',sessions:[first,next,last].map(day=>[day])};
function plan(){
  return Plans.capture({ticker:'AAA',kellSwing:{sessionDate:first,state:'watch',setup:'wedge_pop',
    pivot:103,stop:95,maxEntry:106}},'kell',snapshot,first,[chart[0]]);
}
function storage(){
  const values=new Map();
  return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
}

test('saved plans preserve original levels in separately scoped browser storage',()=>{
  const cache=storage(),original=plan();
  assert.ok(original);
  assert.equal(Plans.save(cache,'owner-A',original),true);
  assert.equal(Plans.save(cache,'owner-A',{...original,pivot:104}),false);
  assert.equal(Plans.load(cache,'owner-A')[0].pivot,103);
  assert.deepEqual(Plans.load(cache,'owner-B'),[]);
  assert.deepEqual(Plans.load(cache),[]);
  Plans.archive(cache,'owner-A',Plans.planId(original));
  assert.ok(Plans.load(cache,'owner-A')[0].archivedAt);
  assert.equal(Plans.save(cache,'owner-A',{...original,pivot:104}),true);
  assert.equal(Plans.load(cache,'owner-A')[0].pivot,103);
});

test('the exact source is required before saving Early Trend Birth',()=>{
  const row={ticker:'AAA',earlyTrend:{sessionDate:first,phase:'reclaim',reclaimPivot:103,
    invalidation:94,evidence:['support_reclaim']}};
  assert.equal(Plans.capture(row,'early',snapshot,first,chart),null);
  const valid=Plans.capture(row,'early',snapshot,first,[chart[0]]);
  assert.equal(valid.maxEntry,null);
  assert.deepEqual(valid.evidence,['support_reclaim']);
});

test('assesses the original pivot, records a first invalidation and rejects incomplete or changed history',()=>{
  const original=plan();
  assert.equal(Plans.assess(original,chart,next,calendar).state,'extended');
  const retrace=Plans.assess(original,chart,last,calendar);
  assert.equal(retrace.state,'belowPivot');
  assert.equal(retrace.lastPivot,next);
  assert.equal(Plans.assess(original,[],first,calendar,'corrected').state,'revision');
  assert.deepEqual(Plans.assess(original,[chart[0],chart[2]],last,calendar),{state:'coverage'});
  assert.deepEqual(Plans.assess(original,[{day:first,close:50},...chart.slice(1)],last,calendar),{state:'priceBasis'});
  const bounced=Plans.assess(original,[chart[0],{day:next,close:94},chart[2]],last,calendar);
  assert.deepEqual(bounced,{state:'invalidated',day:next,close:94,asOf:last,currentClose:102,
    events:[{state:'invalidated',day:next,close:94}]});
});

test('the Kell journal records first qualifying closes in order and stops on the original stop',()=>{
  const quotes=[chart[0],chart[1],{day:last,close:106},{day:'2026-11-18',close:103},
    {day:'2026-11-19',close:95},{day:'2026-11-20',close:110}];
  const sessions={...calendar,sessions:quotes.map(quote=>[quote.day])};
  const result=Plans.assess(plan(),quotes,'2026-11-20',sessions);
  assert.deepEqual(result.events,[
    {state:'extended',day:next,close:108},
    {state:'abovePivot',day:last,close:106},
    {state:'invalidated',day:'2026-11-19',close:95}
  ]);
  assert.equal(result.state,'invalidated');
  assert.equal(result.currentClose,110);
  assert.deepEqual(Plans.assess(plan(),quotes,last,sessions).events,result.events.slice(0,2));
});

test('the Early journal starts after the origin date and keeps the first later close at the pivot',()=>{
  const quotes=[{day:first,close:108},{day:next,close:103},{day:last,close:102}];
  const early={...plan(),strategy:'early',price:108,maxEntry:null};
  assert.deepEqual(Plans.assess(early,quotes,first,calendar,snapshot),{state:'saved'});
  assert.deepEqual(Plans.assess(early,quotes,last,calendar).events,[{state:'abovePivot',day:next,close:103}]);
});
