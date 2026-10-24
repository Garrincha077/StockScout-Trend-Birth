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
  function count(point,stage){return stage==='3+'?point.counts['3']+point.counts['4']:point.counts[stage]}
  root.TrendBirthQuality={normalizeRadar,normalizeHistory,count};
  if(typeof module!=='undefined')module.exports=root.TrendBirthQuality;
})(globalThis);
