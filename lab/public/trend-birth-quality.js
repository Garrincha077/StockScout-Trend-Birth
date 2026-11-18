// Read-only model for the point-in-time stage-distribution history.
(function(root){
  const STAGES=['0','1','2','3','4'];
  function normalizeRadar(radar){
    if(!radar||!radar.stageCounts)return null;
    const counts={};
    for(const stage of STAGES){
      const value=radar.stageCounts[stage];
      if(!Number.isSafeInteger(value)||value<0)return null;
      counts[stage]=value;
    }
    const evaluated=radar.evaluatedCount,unavailable=radar.unavailableCount;
    if(!Number.isSafeInteger(evaluated)||evaluated<0||!Number.isSafeInteger(unavailable)||unavailable<0)return null;
    if(STAGES.reduce((sum,stage)=>sum+counts[stage],0)!==evaluated)return null;
    return {counts,evaluatedCount:evaluated,unavailableCount:unavailable,universeCount:evaluated+unavailable};
  }
  function normalizeHistory(payload,asOf,scope){
    if(payload?.schemaVersion!=='trend-birth-quality-history-v1'||!Array.isArray(payload.points))throw new Error('Nepoznat format povijesti setupa.');
    if(scope&&payload.scope!==scope)throw new Error('Povijesni universe nije usporediv.');
    const seen=new Set(),points=[];
    for(const point of payload.points){
      const day=point?.sessionDate;
      if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day)||seen.has(day))throw new Error('Neispravan ili ponovljen povijesni datum.');
      seen.add(day);
      if(asOf&&day>asOf)continue;
      const normalized=normalizeRadar({stageCounts:point.counts,evaluatedCount:point.evaluatedCount,unavailableCount:point.unavailableCount});
      if(!normalized||normalized.universeCount!==point.universeCount||point.scope!==payload.scope)throw new Error('Nesukladni povijesni brojevi setupa.');
      points.push({sessionDate:day,...normalized});
    }
    return points.sort((a,b)=>a.sessionDate.localeCompare(b.sessionDate));
  }
  const STACK_ORDER=['4','3','2','1','0'];
  const ZOOMS=[25,50,75,100];
  function count(point,stage){return stage==='3+'?point.counts['3']+point.counts['4']:point.counts[stage]}
  function percent(point,stage){return point.evaluatedCount?100*count(point,stage)/point.evaluatedCount:0}
  function percentOfStages(point,stages){
    const keys=[...new Set(stages)];
    if(keys.some(stage=>!STAGES.includes(stage)))throw new Error('Nepoznata razina setupa');
    return point.evaluatedCount?100*keys.reduce((sum,stage)=>sum+point.counts[stage],0)/point.evaluatedCount:0;
  }
  function zoomTicks(zoom){
    if(!ZOOMS.includes(zoom))throw new Error('Nepoznat raspon zooma');
    const step=zoom===100||zoom===75?25:zoom===50?10:5;
    return Array.from({length:zoom/step+1},(_,i)=>zoom-i*step);
  }
  function stackSlices(point,zoom){
    if(!ZOOMS.includes(zoom))throw new Error('Nepoznat raspon zooma');
    let used=0;
    return STACK_ORDER.map(stage=>{
      const share=percent(point,stage);
      const visible=Math.max(0,Math.min(share,zoom-used));
      used+=share;
      return {stage,percent:share,visiblePercent:100*visible/zoom};
    });
  }
  const TIMEFRAMES=['D','W','M'];
  const HISTORY_RANGES={'1m':1,'3m':3,'1y':12,'5y':60,all:0};
  const dateString=date=>date.toISOString().slice(0,10);
  const dateUTC=day=>new Date(day+'T00:00:00Z');
  function monthOffset(day,months){
    const input=dateUTC(day);
    const first=new Date(Date.UTC(input.getUTCFullYear(),input.getUTCMonth()-months,1));
    const lastDay=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
    first.setUTCDate(Math.min(input.getUTCDate(),lastDay));
    return dateString(first);
  }
  function calendarBucket(day,timeframe){
    if(timeframe==='D')return {key:day,end:day,label:day};
    const date=dateUTC(day);
    if(timeframe==='W'){
      const monday=new Date(date);
      monday.setUTCDate(monday.getUTCDate()-(monday.getUTCDay()+6)%7);
      const sunday=new Date(monday);
      sunday.setUTCDate(sunday.getUTCDate()+6);
      const start=dateString(monday),end=dateString(sunday);
      return {key:start,end,label:start+' – '+end};
    }
    const start=dateString(new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth(),1)));
    const end=dateString(new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()+1,0)));
    return {key:start,end,label:start.slice(0,7)};
  }
  function aggregateHistory(daily,timeframe='D'){
    if(!TIMEFRAMES.includes(timeframe))throw new Error('Nepoznata vremenska agregacija');
    if(!daily.length)return [];
    const sorted=[...daily].sort((a,b)=>a.sessionDate.localeCompare(b.sessionDate));
    const grouped=new Map();
    for(const day of sorted){
      const bucket=calendarBucket(day.sessionDate,timeframe);
      let point=grouped.get(bucket.key);
      if(!point){
        point={periodKey:bucket.key,periodEnd:bucket.end,label:bucket.label,sessionDate:day.sessionDate,
          counts:{'0':0,'1':0,'2':0,'3':0,'4':0},evaluatedCount:0,unavailableCount:0,
          universeCount:0,sessionCount:0,isPartial:false};
        grouped.set(bucket.key,point);
      }
      for(const stage of STAGES)point.counts[stage]+=day.counts[stage];
      point.evaluatedCount+=day.evaluatedCount;
      point.unavailableCount+=day.unavailableCount;
      point.universeCount+=day.universeCount;
      point.sessionCount++;
      point.sessionDate=day.sessionDate;
    }
    const result=[...grouped.values()];
    if(timeframe!=='D'){
      const first=result[0],last=result[result.length-1];
      first.isPartial=first.periodKey<sorted[0].sessionDate;
      last.isPartial=last.isPartial||last.periodEnd>sorted[sorted.length-1].sessionDate;
    }
    return result;
  }
  function selectHistoryRange(points,range='all',asOf){
    if(!Object.prototype.hasOwnProperty.call(HISTORY_RANGES,range))throw new Error('Nepoznat raspon povijesti');
    if(!points.length||range==='all')return [...points];
    const anchor=asOf||points[points.length-1].sessionDate;
    const cutoff=monthOffset(anchor,HISTORY_RANGES[range]);
    return points.filter(point=>point.sessionDate>=cutoff&&point.sessionDate<=anchor);
  }
  function historicalPercentile(points,stages){
    if(!points.length)return null;
    const last=points[points.length-1];
    const current=percentOfStages(last,stages);
    const prior=points.slice(0,-1).map(point=>percentOfStages(point,stages));
    const lower=prior.filter(value=>value<current-1e-9).length;
    const ties=prior.filter(value=>Math.abs(value-current)<=1e-9).length;
    return {currentPercent:current,percentile:prior.length?100*(lower+0.5*ties)/prior.length:null,
      priorCount:prior.length,sessionDate:last.sessionDate};
  }
  root.TrendBirthQuality={normalizeRadar,normalizeHistory,count,percent,percentOfStages,zoomTicks,stackSlices,aggregateHistory,selectHistoryRange,historicalPercentile};
  if(typeof module!=='undefined')module.exports=root.TrendBirthQuality;
})(globalThis);
