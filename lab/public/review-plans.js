(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.ReviewPlans=api;
})(globalThis,function(){
  'use strict';
  const STORAGE_KEY='stockscout.review.plans.v1';
  const keyForUser=userId=>userId?STORAGE_KEY+'.user.'+encodeURIComponent(userId):STORAGE_KEY;
  const validDay=value=>typeof value==='string'&&/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value);
  const validPrice=value=>Number.isFinite(value)&&value>0;
  const validId=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}$/.test(value);
  const planId=({ticker,strategy,snapshotId})=>strategy+':'+ticker+':'+snapshotId;

  function valid(plan){
    return plan&&['early','kell'].includes(plan.strategy)&&typeof plan.ticker==='string'&&plan.ticker.length>0&&
      Array.isArray(plan.evidence)&&validDay(plan.sessionDate)&&validId(plan.snapshotId)&&validPrice(plan.price)&&
      validPrice(plan.pivot)&&validPrice(plan.invalidation)&&plan.invalidation<plan.pivot&&
      (plan.maxEntry==null||validPrice(plan.maxEntry)&&plan.maxEntry>=plan.pivot);
  }
  function load(storage,userId){
    try{
      const data=JSON.parse(storage.getItem(keyForUser(userId)));
      return data?.version===1&&Array.isArray(data.plans)?data.plans.filter(valid):[];
    }catch(_error){return []}
  }
  function write(storage,userId,plans){
    storage.setItem(keyForUser(userId),JSON.stringify({version:1,plans}));
  }
  function capture(item,strategy,snapshotId,sessionDate,quotes){
    const source=strategy==='early'?item.earlyTrend:item.kellSwing;
    if(!source||source.sessionDate!==sessionDate||source.state==='invalidated')return null;
    const last=quotes.at(-1);
    if(last?.day!==sessionDate)return null;
    const plan={ticker:item.ticker,strategy,snapshotId,sessionDate,price:last.close,
      pivot:strategy==='early'?source.reclaimPivot:source.pivot,
      invalidation:strategy==='early'?source.invalidation:source.stop,
      maxEntry:strategy==='early'?null:source.maxEntry??null,
      phase:source.phase,setup:source.setup??null,
      evidence:strategy==='early'&&Array.isArray(source.evidence)?source.evidence.slice():[],
      savedAt:new Date().toISOString()};
    return valid(plan)?plan:null;
  }
  function save(storage,userId,plan){
    if(!valid(plan))throw Error('Plan nema valjanu snimku ili razine.');
    const plans=load(storage,userId);
    if(plans.some(old=>!old.archivedAt&&old.ticker===plan.ticker&&old.strategy===plan.strategy))return false;
    const id=planId(plan);
    const rows=plans.some(old=>planId(old)===id)?
      plans.map(old=>planId(old)===id?{...old,archivedAt:null}:old):[...plans,plan];
    write(storage,userId,rows);
    return true;
  }
  function archive(storage,userId,id){
    const plans=load(storage,userId);
    write(storage,userId,plans.map(plan=>planId(plan)===id&&!plan.archivedAt?
      {...plan,archivedAt:new Date().toISOString()}:plan));
  }
  function level(plan,close){
    if(close<=plan.invalidation)return 'invalidated';
    if(plan.maxEntry!=null&&close>plan.maxEntry)return 'extended';
    return close>=plan.pivot?'abovePivot':'belowPivot';
  }
  function assess(plan,quotes,asOf,calendar,snapshotId){
    if(!validDay(asOf)||asOf<plan.sessionDate)return {state:'earlier'};
    if(asOf===plan.sessionDate)return {state:snapshotId&&snapshotId!==plan.snapshotId?'revision':'saved'};
    if(calendar?.schemaVersion!=='xnys-eod-sessions-v1'||!Array.isArray(calendar.sessions))return {state:'calendar'};
    const days=calendar.sessions.map(row=>row[0]).filter(day=>day>=plan.sessionDate&&day<=asOf);
    if(days[0]!==plan.sessionDate||days.at(-1)!==asOf)return {state:'calendar'};
    const window=quotes.filter(quote=>quote.day>=plan.sessionDate&&quote.day<=asOf);
    if(window.length!==days.length||window.some((quote,i)=>quote.day!==days[i]||!validPrice(quote.close)))return {state:'coverage'};
    // A different close on the saved session can indicate a corrected or split-adjusted series.
    if(Math.abs(window[0].close-plan.price)>Math.max(.005,plan.price*.00005))return {state:'priceBasis'};
    const current=window.at(-1);
    let previous=level(plan,window[0].close);
    let changed=null;
    let lastPivot=null;
    for(const quote of window.slice(1)){
      const state=level(plan,quote.close);
      if(state==='invalidated')return {state,day:quote.day,close:quote.close,asOf,currentClose:current.close};
      if(previous==='belowPivot'&&state!=='belowPivot')lastPivot=quote.day;
      if(state!==previous)changed=quote.day;
      previous=state;
    }
    return {state:previous,asOf,close:current.close,changed,lastPivot,pivotDeltaPct:100*(current.close/plan.pivot-1)};
  }
  return {STORAGE_KEY,keyForUser,planId,load,capture,save,archive,assess};
});
