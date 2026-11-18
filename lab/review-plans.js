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
  const reviewKey=(userId,id)=>keyForUser(userId)+'.review.'+encodeURIComponent(id);

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
  function level(plan,close){
    if(close<=plan.invalidation)return 'invalidated';
    if(plan.maxEntry!=null&&close>plan.maxEntry)return 'extended';
    return close>=plan.pivot?'abovePivot':'belowPivot';
  }
  function samePriceBasis(plan,close){
    return validPrice(close)&&Math.abs(close-plan.price)<=Math.max(.005,plan.price*.00005);
  }
  function validReview(plan,review){
    if(!review||!validId(review.snapshotId)||!validDay(review.asOf)||review.asOf<=plan.sessionDate||
      !validPrice(review.close)||!Array.isArray(review.events)||review.events.length>3)return false;
    const seen=new Set();
    let previous=plan.sessionDate;
    for(const event of review.events){
      if(!event||!validDay(event.day)||event.day<=previous||event.day>review.asOf||!validPrice(event.close)||
        event.state==='belowPivot'||event.state!==level(plan,event.close)||seen.has(event.state)||
        seen.has('invalidated'))return false;
      if(event.day===review.asOf&&event.close!==review.close)return false;
      seen.add(event.state);
      previous=event.day;
    }
    return seen.has('invalidated')?review.state==='invalidated':
      review.state!=='invalidated'&&level(plan,review.close)===review.state&&
      (review.state==='belowPivot'||seen.has(review.state));
  }
  function closingReview(plan,snapshotId,result){
    const review={snapshotId,asOf:result.asOf,state:result.state,
      close:result.state==='invalidated'?result.currentClose:result.close,events:result.events};
    return validReview(plan,review)?review:null;
  }
  function archivedReview(plan){
    return validReview(plan,plan.closingReview)?plan.closingReview:null;
  }
  function readReview(storage,userId,plan){
    try{
      const review=JSON.parse(storage.getItem(reviewKey(userId,planId(plan))));
      return validReview(plan,review)?review:null;
    }catch(_error){return null}
  }
  function localBook(storage,userId){
    return load(storage,userId).map(plan=>{
      const previous=archivedReview(plan);
      const checkpoint=!plan.archivedAt&&readReview(storage,userId,plan);
      return checkpoint&&(!previous||checkpoint.asOf>previous.asOf)?{...plan,closingReview:checkpoint}:plan;
    });
  }
  function rememberReview(storage,userId,plan,review){
    if(!validReview(plan,review))return;
    const previous=readReview(storage,userId,plan);
    if(previous&&(previous.snapshotId===review.snapshotId||previous.asOf>review.asOf))return;
    if(!load(storage,userId).some(row=>planId(row)===planId(plan)&&!row.archivedAt))return;
    storage.setItem(reviewKey(userId,planId(plan)),JSON.stringify(review));
  }
  function archive(storage,userId,id,displayedReview){
    const plans=load(storage,userId);
    const active=plans.find(plan=>planId(plan)===id&&!plan.archivedAt);
    if(!active)return false;
    let review=archivedReview(active);
    for(const candidate of [readReview(storage,userId,active),displayedReview]){
      if(validReview(active,candidate)&&(!review||candidate.asOf>=review.asOf))review=candidate;
    }
    const archived={...active,archivedAt:new Date().toISOString(),closingReview:review};
    write(storage,userId,plans.map(plan=>plan===active?archived:plan));
    try{storage.removeItem(reviewKey(userId,id))}catch(_error){/* The archive is already committed. */}
    return true;
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
    if(!samePriceBasis(plan,window[0].close))return {state:'priceBasis'};
    const current=window.at(-1);
    let previous=level(plan,window[0].close);
    let changed=null;
    let lastPivot=null;
    const events=[];
    const recorded=new Set();
    for(const quote of window.slice(1)){
      const state=level(plan,quote.close);
      if(state!=='belowPivot'&&!recorded.has(state)){
        events.push({state,day:quote.day,close:quote.close});
        recorded.add(state);
      }
      if(state==='invalidated')return {state,day:quote.day,close:quote.close,asOf,currentClose:current.close,events};
      if(previous==='belowPivot'&&state!=='belowPivot')lastPivot=quote.day;
      if(state!==previous)changed=quote.day;
      previous=state;
    }
    return {state:previous,asOf,close:current.close,changed,lastPivot,pivotDeltaPct:100*(current.close/plan.pivot-1),events};
  }
  return {STORAGE_KEY,keyForUser,planId,validPlan:valid,load,localBook,capture,save,archive,assess,samePriceBasis,
    closingReview,archivedReview,rememberReview};
});
