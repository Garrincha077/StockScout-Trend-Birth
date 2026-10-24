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
test('historic setup breadth is a percentage of each session’s evaluated universe',()=>{
  const narrow=point('2026-10-23',[0,0,0,3,1]);
  const wide=point('2026-10-22',[96,0,0,3,1]);
  assert.equal(quality.percent(narrow,'3+'),100);
  assert.equal(quality.percent(wide,'3+'),4);
  assert.equal(quality.percent(wide,'0'),96);
  assert.equal(quality.percent(narrow,'0'),0);
  assert.equal(quality.percent({counts:{'0':0,'1':0,'2':0,'3':0,'4':0},evaluatedCount:0},'3+'),0);
});
test('stacked daily percentages stay point-in-time and zoom crops only the visible axis',()=>{
  const p=point('2026-10-23',[85,7,2,2,4]);
  assert.deepEqual(quality.zoomTicks(25),[25,20,15,10,5,0]);
  assert.deepEqual(quality.zoomTicks(50),[50,40,30,20,10,0]);
  assert.deepEqual(quality.zoomTicks(75),[75,50,25,0]);
  assert.deepEqual(quality.zoomTicks(100),[100,75,50,25,0]);
  for(const zoom of [25,50,75,100]){
    const slices=quality.stackSlices(p,zoom);
    assert.deepEqual(slices.map(slice=>slice.stage),['4','3','2','1','0']);
    assert.ok(Math.abs(slices.reduce((sum,slice)=>sum+slice.visiblePercent,0)-100)<1e-10);
    assert.equal(quality.percentOfStages(p,['3','4']),6);
  }
  assert.equal(quality.stackSlices(p,25)[0].visiblePercent,16);
  assert.equal(quality.stackSlices(p,25)[4].visiblePercent,40);
  assert.equal(quality.stackSlices(p,100)[4].visiblePercent,85);
  assert.throws(()=>quality.stackSlices(p,110));
});
test('latest percentile uses only earlier sessions, midranks ties and supports arbitrary subsets',()=>{
  const p1=point('2026-10-21',[90,0,0,6,4]);
  const p2=point('2026-10-22',[80,0,0,12,8]);
  const p3=point('2026-10-23',[80,0,0,12,8]);
  assert.equal(quality.historicalPercentile([p1,p2,p3],['3','4']).percentile,75);
  assert.equal(quality.historicalPercentile([p1,p1,p1],['3','4']).percentile,50);
  assert.equal(quality.historicalPercentile([p1,p2],['3','4']).percentile,100);
  assert.equal(quality.historicalPercentile([p3],['3','4']).percentile,null);
  assert.equal(quality.percentOfStages(p3,['3','4','4']),20);
  assert.throws(()=>quality.percentOfStages(p3,['bad']));
});
test('app renders five coloured stack layers, four selectable zooms and historic percentile',()=>{
  const styles=fs.readFileSync(path.join(root,'lab/styles.css'),'utf8');
  for(const stage of ['0','1','2','3','4'])assert.match(html,new RegExp('data-tb-stage="'+stage+'"'));
  for(const zoom of ['25','50','75','100'])assert.match(html,new RegExp('data-tb-zoom="'+zoom+'"'));
  assert.match(html,/id="tbPercentileMetric"/);
  assert.match(html,/value="selected">Označene razine/);
  assert.match(app,/TrendBirthQuality\.stackSlices\(point,zoom\)/);
  assert.match(app,/selectedStages\.includes\(slice\.stage\)/);
  assert.match(app,/TrendBirthQuality\.zoomTicks\(zoom\)/);
  assert.match(app,/TrendBirthQuality\.historicalPercentile\(rankPoints,focusStages\)/);
  assert.match(app,/TrendBirthQuality\.aggregateHistory\(fullPoints,tbQualityView\.timeframe\)/);
  assert.match(app,/TrendBirthQuality\.selectHistoryRange\(allPeriods,tbQualityView\.range,day\)/);
  assert.doesNotMatch(app,/fullPoints\.slice\(-45\)/);
  assert.match(styles,/\.tb-history-segment\[data-stage="0"\]\{background:#df5962/);
  assert.match(styles,/\.tb-history-segment\[data-stage="4"\]\{background:#2fca87/);
  assert.match(styles,/\.tb-history-segment\.is-muted\{background:#334457/);
  assert.doesNotMatch(app,/tbHistoryStage/);
});
test('D/W/M use the complete retained daily archive and ticker-day weighted shares',()=>{
  const daily=[
    point('2026-09-24',[2,0,0,0,2]), // 50% 4/4; early first partial week
    point('2026-09-25',[90,0,0,0,10]), // 10% 4/4; heavier day
    point('2026-09-28',[8,0,0,0,2]), // next ISO week
    point('2026-10-01',[4,0,0,0,6])
  ];
  const d=quality.aggregateHistory(daily,'D');
  assert.deepEqual(d.map(p=>p.sessionDate),daily.map(p=>p.sessionDate));
  const w=quality.aggregateHistory(daily,'W');
  assert.deepEqual(w.map(p=>p.periodKey),['2026-09-21','2026-09-28']);
  assert.equal(w[0].sessionCount,2);
  assert.equal(w[0].evaluatedCount,104);
  assert.equal(w[0].counts['4'],12);
  assert.equal(quality.percent(w[0],'4'),100*12/104);
  assert.equal(w[0].isPartial,true);
  assert.equal(w[1].counts['4'],8);
  const m=quality.aggregateHistory(daily,'M');
  assert.deepEqual(m.map(p=>p.periodKey),['2026-09-01','2026-10-01']);
  assert.equal(m[0].evaluatedCount,114);
  assert.equal(m[0].counts['4'],14);
  assert.equal(m[0].isPartial,true);
  for(const point of [...w,...m]){
    for(const zoom of [25,50,75,100]){
      assert.ok(Math.abs(quality.stackSlices(point,zoom).reduce((sum,slice)=>sum+slice.visiblePercent,0)-100)<1e-9);
    }
  }
  assert.throws(()=>quality.aggregateHistory(daily,'yearly'));
});
test('1M/3M/1Y/5Y/All filter by the latest archived EOD date without truncating old data',()=>{
  const dates=['2020-01-01','2021-10-23','2025-10-23','2026-07-23','2026-09-23',
               '2026-10-22','2026-10-23'];
  const daily=dates.map(day=>point(day));
  assert.deepEqual(quality.selectHistoryRange(daily,'1m').map(p=>p.sessionDate),dates.slice(4));
  assert.deepEqual(quality.selectHistoryRange(daily,'3m').map(p=>p.sessionDate),dates.slice(3));
  assert.deepEqual(quality.selectHistoryRange(daily,'1y').map(p=>p.sessionDate),dates.slice(2));
  assert.deepEqual(quality.selectHistoryRange(daily,'5y').map(p=>p.sessionDate),dates.slice(1));
  assert.deepEqual(quality.selectHistoryRange(daily,'all').map(p=>p.sessionDate),dates);
  const leap=['2024-02-28','2024-02-29','2024-03-31'].map(day=>point(day));
  assert.deepEqual(quality.selectHistoryRange(leap,'1m').map(p=>p.sessionDate),
    ['2024-02-29','2024-03-31']);
  assert.throws(()=>quality.selectHistoryRange(daily,'bad'));
});
test('interval and historical-window controls are selectable without adding files or new work cycles',()=>{
  for(const interval of ['D','W','M'])assert.match(html,new RegExp('data-tb-timeframe="'+interval+'"'));
  for(const span of ['1m','3m','1y','5y','all'])assert.match(html,new RegExp('data-tb-range="'+span+'"'));
  assert.match(app,/tbQualityView\.scrollToEnd=true/);
  assert.match(app,/data-tb-period/);
  assert.doesNotMatch(app,/slice\(-45\)/);
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
