const test=require('node:test');
const assert=require('node:assert/strict');
const KellChanges=require('../lab/kell-change-detector.js');

function row(overrides={}){
  return{
    ticker:'TEST',
    kell_score:55,
    kell_readiness_score:50,
    stage:'transition',
    screens:[],
    setups:[],
    context:[],
    ...overrides
  };
}

test('score jumps alone do not define What Changed in the Cycle',()=>{
  const previous=row({kell_score:45,kell_readiness_score:40});
  const current=row({kell_score:80,kell_readiness_score:90});
  const change=KellChanges.classify(current,[previous]);
  assert.equal(change.changed,false);
  assert.equal(change.scoreDelta,35);
  assert.equal(change.readinessDelta,50);
});

test('discovery changes are tracked separately from stage and setup',()=>{
  const previous=row({screens:['kell_rs_leader']});
  const current=row({screens:['kell_rs_leader','kell_bull_snort']});
  const change=KellChanges.classify(current,[previous]);
  assert.equal(change.changed,true);
  assert.equal(change.priorityBand,'discovery');
  assert.deepEqual(change.changeTypes,['discovery']);
  assert.equal(change.headline,'DISCOVERY CHANGED');
  assert.deepEqual(change.addedScreens,['kell_bull_snort']);
});

test('auxiliary repair/support flicker is not a cycle event',()=>{
  const previous=row({stage:'transition'});
  const current=row({stage:'trend_ema_support'});
  const change=KellChanges.classify(current,[previous]);
  assert.equal(change.changed,false);
  assert.equal(change.stageChanged,false);
  assert.equal(change.priorityBand,'none');
});

test('stage transition is a change even without score movement',()=>{
  const previous=row({stage:'transition'});
  const current=row({stage:'wedge_pop'});
  const change=KellChanges.classify(current,[previous]);
  assert.equal(change.changed,true);
  assert.equal(change.priorityBand,'stage');
  assert.equal(change.stageChanged,true);
  assert.equal(change.previousStage,'transition');
  assert.equal(change.currentStage,'wedge_pop');
});

test('first crossback after Wedge Pop becomes the highest-priority actionable setup',()=>{
  const wedge=row({stage:'wedge_pop',setups:['kell_wedge_pop']});
  const current=row({
    stage:'ema_crossback',
    setups:['kell_ema_crossback'],
    kell_stage:{primary:'ema_crossback',basis:['first_retest_after_wedge_pop','10_20_ema_support']},
    structural_risk_atr:1.1
  });
  const change=KellChanges.classify(current,[wedge]);
  assert.equal(change.changed,true);
  assert.equal(change.priorityBand,'setup');
  assert.equal(change.crossbackClass,'FIRST CROSSBACK');
  assert.equal(change.headline,'FIRST ACTIONABLE CROSSBACK');
  assert.equal(change.riskTooWide,false);
  assert.ok(change.reasons.includes('Natural invalidation 1.10 ATR'));
});

test('a repeated retest after a prior crossback is explicitly degraded',()=>{
  const history=[
    row({stage:'wedge_pop',setups:['kell_wedge_pop']}),
    row({stage:'ema_crossback',setups:['kell_ema_crossback']}),
    row({stage:'trend_ema_support',setups:[]})
  ];
  const current=row({stage:'ema_crossback',setups:['kell_ema_crossback']});
  const change=KellChanges.classify(current,history);
  assert.equal(change.crossbackClass,'LATE RETEST');
  assert.equal(change.priorityBand,'setup');
  assert.ok(change.reasons.includes('LATE RETEST'));
});

test('chart-derived retest state wins over incomplete snapshot history',()=>{
  const staleHistory=[
    row({stage:'ema_crossback',setups:['kell_ema_crossback']}),
    row({stage:'transition',setups:[]})
  ];
  const current=row({
    stage:'ema_crossback',
    setups:['kell_ema_crossback'],
    kell_metrics:{ema_retest_state:'first_crossback'}
  });
  const change=KellChanges.classify(current,staleHistory);
  assert.equal(change.crossbackClass,'FIRST CROSSBACK');
  assert.equal(change.headline,'FIRST ACTIONABLE CROSSBACK');
});

test('late EMA retest is visible but lower priority than a first actionable Crossback',()=>{
  const history=[row({stage:'trend_ema_support',setups:[]})];
  const late=KellChanges.classify(row({
    stage:'trend_ema_support',
    setups:[],
    kell_metrics:{ema_retest_state:'late_retest'}
  }),history);
  const first=KellChanges.classify(row({
    stage:'ema_crossback',
    setups:['kell_ema_crossback'],
    kell_metrics:{ema_retest_state:'first_crossback'}
  }),history);
  assert.equal(late.changed,true);
  assert.equal(late.priorityBand,'stage');
  assert.equal(late.headline,'EMA RETEST · LATE');
  assert.ok(first.priority>late.priority);
});

test("Base n' Break is early after the first Wedge/Crossback sequence and mature after a prior base",()=>{
  const earlyHistory=[
    row({stage:'wedge_pop',setups:['kell_wedge_pop']}),
    row({stage:'ema_crossback',setups:['kell_ema_crossback']})
  ];
  const current=row({stage:'base_n_break',setups:['kell_base_n_break']});
  const early=KellChanges.classify(current,earlyHistory);
  assert.equal(early.cycleMaturity,'EARLY');
  assert.equal(early.headline,"BASE N' BREAK · EARLY");

  const mature=KellChanges.classify(current,[
    ...earlyHistory,
    row({stage:'base_n_break',setups:['kell_base_n_break']}),
    row({stage:'trend_ema_support',setups:[]})
  ]);
  assert.equal(mature.cycleMaturity,'MATURE');
  assert.equal(mature.headline,"BASE N' BREAK · MATURE");
  assert.ok(early.priority>mature.priority);
});

test('first Exhaustion Extension and Wedge Drop are cycle-risk changes',()=>{
  const trend=row({stage:'base_n_break',setups:['kell_base_n_break']});
  const exhaustion=KellChanges.classify(row({stage:'exhaustion_extension'}),[trend]);
  assert.equal(exhaustion.firstExhaustion,true);
  assert.equal(exhaustion.priorityBand,'risk');
  assert.equal(exhaustion.headline,'FIRST EXHAUSTION EXTENSION');

  const drop=KellChanges.classify(row({stage:'wedge_drop'}),[
    trend,
    row({stage:'exhaustion_extension'})
  ]);
  assert.equal(drop.structureFailed,true);
  assert.equal(drop.priorityBand,'risk');
  assert.equal(drop.headline,'STRUCTURE FAILED · WEDGE DROP');
});

test('wide natural invalidation and defensive regime reduce review priority but do not hide setup',()=>{
  const history=[row({stage:'wedge_pop',setups:['kell_wedge_pop']})];
  const tight=KellChanges.classify(row({
    stage:'ema_crossback',
    setups:['kell_ema_crossback'],
    kell_stage:{primary:'ema_crossback',basis:['first_retest_after_wedge_pop']},
    structural_risk_atr:1.0
  }),history,{qqqAboveEma20:true});
  const wideDefensive=KellChanges.classify(row({
    stage:'ema_crossback',
    setups:['kell_ema_crossback'],
    kell_stage:{primary:'ema_crossback',basis:['first_retest_after_wedge_pop']},
    structural_risk_atr:3.4
  }),history,{qqqAboveEma20:false});
  assert.equal(wideDefensive.changed,true);
  assert.equal(wideDefensive.riskTooWide,true);
  assert.equal(wideDefensive.marketRegime.defensive,true);
  assert.ok(wideDefensive.reasons.includes('RISK TOO WIDE 3.40 ATR'));
  assert.ok(wideDefensive.reasons.includes('DEFENSIVE REGIME'));
  assert.ok(tight.priority>wideDefensive.priority);
});

test('coarse Unified correction is a defensive fallback without pretending QQQ/20EMA is exact',()=>{
  const history=[row({stage:'transition',setups:[]})];
  const current=row({stage:'wedge_pop',setups:['kell_wedge_pop']});
  const change=KellChanges.classify(current,history,{
    qqqAboveEma20:null,
    qqq20ExactAvailable:false,
    regime:{state:'correction'}
  });
  assert.equal(change.marketRegime.defensive,true);
  assert.equal(change.marketRegime.exactQqq20,false);
  assert.match(change.marketRegime.label,/UNIFIED FALLBACK/);
  assert.ok(change.reasons.includes('DEFENSIVE REGIME'));
});

test('columnar history archives are inflated for sequence tracking',()=>{
  const payload={
    source:{sessionDate:'2026-09-22'},
    columns:['ticker','stage','setups','screens'],
    candidates:[['AAA','wedge_pop',['kell_wedge_pop'],[]]]
  };
  const current=[row({
    ticker:'AAA',
    stage:'ema_crossback',
    setups:['kell_ema_crossback'],
    kell_metrics:{ema_retest_state:'first_crossback'}
  })];
  KellChanges.decorate(current,[payload],{});
  assert.equal(current[0].kellChange.previousStage,'wedge_pop');
  assert.equal(current[0].kellChange.crossbackClass,'FIRST CROSSBACK');
});

test('decorate uses multiple historical sessions and summary reports sequence events',()=>{
  const history=[
    {
      schemaVersion:'kell-score-history-v1',
      source:{sessionDate:'2026-09-21'},
      candidates:[row({ticker:'AAA',stage:'wedge_pop',setups:['kell_wedge_pop']})]
    },
    {
      schemaVersion:'kell-score-history-v1',
      source:{sessionDate:'2026-09-22'},
      candidates:[row({ticker:'AAA',stage:'transition',setups:[]})]
    }
  ];
  const current=[
    row({
      ticker:'AAA',
      stage:'ema_crossback',
      setups:['kell_ema_crossback'],
      kell_stage:{primary:'ema_crossback',basis:['first_retest_after_wedge_pop']}
    })
  ];
  KellChanges.decorate(current,history,{qqqAboveEma20:true});
  assert.equal(current[0].kellChange.previousDate,'2026-09-22');
  assert.deepEqual(current[0].kellChange.historyDates,['2026-09-21','2026-09-22']);
  assert.equal(current[0].kellChange.crossbackClass,'FIRST CROSSBACK');
  assert.equal(KellChanges.summary(current).firstCrossbacks,1);
  assert.equal(KellChanges.summary(current).actionable,1);
});

test('loadHistory skips missing calendar days and returns several sessions chronologically',async()=>{
  const calls=[];
  const fakeFetch=async path=>{
    calls.push(path);
    const match=path.match(/(2026-09-\d\d)\.json$/);
    const date=match?.[1];
    if(['2026-09-22','2026-09-21'].includes(date)){
      return{
        status:200,ok:true,
        json:async()=>({schemaVersion:'kell-score-history-v1',source:{sessionDate:date},candidates:[]})
      };
    }
    return{status:404,ok:false,json:async()=>({}),text:async()=>''};
  };
  const payloads=await KellChanges.loadHistory(fakeFetch,'2026-09-24',2,5);
  assert.deepEqual(payloads.map(item=>item.source.sessionDate),['2026-09-21','2026-09-22']);
  assert.ok(calls.includes('data/kell-score-history/2026-09-23.json'));
  assert.ok(calls.includes('data/kell-score-history/2026-09-22.json'));
  assert.ok(calls.includes('data/kell-score-history/2026-09-21.json'));
});
