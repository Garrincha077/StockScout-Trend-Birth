const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Stats=require('../lab/trend-birth-stats.js');

const fields=['breadth','pressure','velocity','acceleration','flow','persistence'];
function row(date,rank=50){
  return {sessionDate:date,score:rank,readyFactors:0,
    fields:Object.fromEntries(fields.map(k=>[k,{raw:null,percentile:rank,historyN:0}]))};
}
test('recovery factor contributions match the published 14-weight formula',()=>{
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../lab/data/trend-birth-composite-backtest.json'),'utf8'));
  const ranks=data.latestActual.components;
  const point={fields:Object.fromEntries(fields.map(k=>[k,{raw:1,percentile:ranks[k],historyN:20}]))};
  const result=Stats.compositeFactorRows(point,{
    weights:data.calibration.weights,directions:data.calibration.directions});
  assert.equal(result.total,14);
  assert.ok(Math.abs(result.score-data.latestActual.score)<0.1);
  assert.equal(result.rows.find(x=>x.field==='breadth').direction,-1);
  assert.equal(result.rows.find(x=>x.field==='pressure').direction,-1);
});
test('composite history windows keep original dates and never create fake rows',()=>{
  const sample={actualHistory:[row('2026-09-24'),row('2026-10-01'),row('2026-10-23')],
    oos:{history:[row('2008-01-10'),row('2020-01-15'),row('2026-08-10')]}};
  assert.deepEqual(Stats.compositeHistory(sample,'actual','all').map(p=>p.sessionDate),
    ['2026-09-24','2026-10-01','2026-10-23']);
  assert.deepEqual(Stats.compositeHistory(sample,'actual','1m').map(p=>p.sessionDate),
    ['2026-09-24','2026-10-01','2026-10-23']);
  assert.deepEqual(Stats.compositeHistory(sample,'proxy','5y').map(p=>p.sessionDate),
    ['2026-08-10']);
  assert.throws(()=>Stats.compositeHistory(sample,'bogus','all'),/izvor/);
});
test('fail-closed breakdown rejects corrupt percentiles and mismatched weights',()=>{
  const point=row('2026-10-23');
  point.fields.breadth.percentile=120;
  const profile={weights:Object.fromEntries(fields.map(k=>[k,1])),
    directions:Object.fromEntries(fields.map(k=>[k,1]))};
  assert.throws(()=>Stats.compositeFactorRows(point,profile),/komponenta/);
  point.fields.breadth.percentile=50;
  assert.equal(Stats.compositeFactorRows(point,profile).score,50);
  profile.weights.flow=-1;
  assert.throws(()=>Stats.compositeFactorRows(point,profile),/komponenta/);
});
test('generated proxy and real EOD history reconcile to frozen aggregates',()=>{
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../lab/data/trend-birth-composite-backtest.json'),'utf8'));
  assert.equal(Stats.validateComposite(data),data);
  assert.equal(data.oos.history.length,data.oos.n);
  assert.equal(data.actualHistory.length,data.latestActual.actualHistoryCount);
  assert.equal(data.actualHistory.at(-1).sessionDate,data.latestActual.sessionDate);
  assert.ok(Math.abs(data.actualHistory.at(-1).score-data.latestActual.score)<0.001);
  assert.ok(data.actualHistory.every((point,i)=>i===0||point.sessionDate>data.actualHistory[i-1].sessionDate));
  assert.ok(data.oos.history.every((point,i)=>i===0||point.sessionDate>data.oos.history[i-1].sessionDate));
});
