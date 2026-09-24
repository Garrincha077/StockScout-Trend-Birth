const test=require('node:test');
const assert=require('node:assert/strict');
const KellChanges=require('../lab/kell-change-detector.js');

function row(overrides={}){
  return{
    ticker:'TEST',
    kell_score:55,
    kell_readiness_score:50,
    stage:'transition',
    setups:[],
    ...overrides
  };
}

test('new candidates only qualify when already materially relevant',()=>{
  assert.equal(KellChanges.classify(row(),null).changed,false);
  const strong=KellChanges.classify(row({kell_score:62}),null);
  assert.equal(strong.changed,true);
  assert.equal(strong.newCandidate,true);
  assert.deepEqual(strong.reasons,['NEW KELL']);
});

test('crossing Ready is an important daily change',()=>{
  const previous=row({kell_readiness_score:74,kell_score:60});
  const current=row({kell_readiness_score:86,kell_score:67});
  const change=KellChanges.classify(current,previous);
  assert.equal(change.changed,true);
  assert.equal(change.becameReady,true);
  assert.ok(change.reasons.includes('READY'));
});

test('new actionable setup qualifies when readiness is at least 60',()=>{
  const previous=row({kell_readiness_score:64,setups:[]});
  const current=row({kell_readiness_score:68,stage:'base_n_break',setups:['kell_base_n_break']});
  const change=KellChanges.classify(current,previous);
  assert.equal(change.changed,true);
  assert.deepEqual(change.addedSetups,['kell_base_n_break']);
  assert.ok(change.reasons.includes("NEW Base n' Break"));
});

test('small score noise alone does not enter What Changed Today',()=>{
  const previous=row({kell_score:61,kell_readiness_score:71});
  const current=row({kell_score:66,kell_readiness_score:78});
  const change=KellChanges.classify(current,previous);
  assert.equal(change.changed,false);
});

test('large readiness or Focus jumps qualify',()=>{
  const readiness=KellChanges.classify(row({kell_readiness_score:75}),row({kell_readiness_score:42}));
  assert.equal(readiness.changed,true);
  assert.equal(readiness.readinessDelta,33);
  const focus=KellChanges.classify(row({kell_score:72}),row({kell_score:50}));
  assert.equal(focus.changed,true);
  assert.equal(focus.scoreDelta,22);
});

test('decorate attaches previous date and summary counts',()=>{
  const current=[
    row({ticker:'AAA',kell_score:65}),
    row({ticker:'BBB',kell_score:50,kell_readiness_score:85})
  ];
  const previous={
    schemaVersion:'kell-score-history-v1',
    source:{sessionDate:'2026-09-22'},
    candidates:[row({ticker:'AAA',kell_score:64}),row({ticker:'BBB',kell_readiness_score:70})]
  };
  KellChanges.decorate(current,previous);
  assert.equal(current[1].kellChange.previousDate,'2026-09-22');
  assert.equal(KellChanges.summary(current).becameReady,1);
});

test('loadPrevious skips missing calendar days and returns first valid snapshot',async()=>{
  const calls=[];
  const fakeFetch=async path=>{
    calls.push(path);
    if(path.includes('2026-09-22.json'))return{
      status:200,ok:true,json:async()=>({schemaVersion:'kell-score-history-v1',source:{sessionDate:'2026-09-22'},candidates:[]})
    };
    return{status:404,ok:false,json:async()=>({})};
  };
  const payload=await KellChanges.loadPrevious(fakeFetch,'2026-09-24',5);
  assert.equal(payload.source.sessionDate,'2026-09-22');
  assert.deepEqual(calls,[
    'data/kell-score-history/2026-09-23.json',
    'data/kell-score-history/2026-09-22.json'
  ]);
});
