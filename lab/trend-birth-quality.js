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
  root.TrendBirthQuality={normalizeRadar,normalizeHistory,count,percent,percentOfStages,zoomTicks,stackSlices,historicalPercentile};
  if(typeof module!=='undefined')module.exports=root.TrendBirthQuality;
})(globalThis);
