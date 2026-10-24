// Read-only client model for compact, point-in-time Trend Birth intelligence.
(function(root){
  const SCHEMA='trend-birth-intelligence-v1';
  const MONTH_SCHEMA='trend-birth-ticker-month-v1';
  const MONTH_PATTERN=/^\d{4}-\d{2}$/;
  const DATE_PATTERN=/^\d{4}-\d{2}-\d{2}$/;
  const STAGES=['0','1','2','3','4'];

  function validateSummary(payload,asOf,scope){
    if(payload?.schemaVersion!==SCHEMA)throw new Error('Nepoznata verzija dnevnog intelligence pregleda.');
    const source=payload.source||{};
    if(!DATE_PATTERN.test(source.sessionDate||'')||!source.runId||!source.scope){
      throw new Error('Nedostaje izvor intelligence očitanja.');
    }
    if(scope&&source.scope!==scope)throw new Error('Intelligence univerzum nije usporediv.');
    if(asOf&&source.sessionDate!==asOf)throw new Error('Intelligence datum nije usklađen s EOD-om.');
    const counts=payload.counts||{};
    if(STAGES.some(stage=>!Number.isSafeInteger(counts[stage])||counts[stage]<0)
      ||!Number.isSafeInteger(payload.evaluatedCount)
      ||STAGES.reduce((sum,stage)=>sum+counts[stage],0)!==payload.evaluatedCount){
      throw new Error('Nesukladni brojčani pokazatelji intelligence pregleda.');
    }
    const stability=payload.stability;
    if(stability!==undefined){
      if(!Number.isSafeInteger(stability?.observedSessions)||stability.observedSessions<1||
        !Number.isSafeInteger(stability?.transitionPairs)||
        stability.transitionPairs!==stability.observedSessions-1){
        throw new Error('Neispravan broj EOD sesija za trajnost.');
      }
      for(const key of ['quality','four']){
        const group=stability[key];
        if(!group||['current','atLeast3','atLeast5','oneSession'].some(field=>
          !Number.isSafeInteger(group[field])||group[field]<0)||
          group.atLeast3>group.current||group.atLeast5>group.atLeast3||
          group.oneSession>group.current||
          (group.latestDropouts!==null&&(!Number.isSafeInteger(group.latestDropouts)||group.latestDropouts<0))||
          !group.retention||!Number.isSafeInteger(group.retention.eligible)||
          !Number.isSafeInteger(group.retention.kept)||group.retention.kept<0||
          group.retention.eligible<group.retention.kept){
          throw new Error('Neispravni pokazatelji trajnosti setupa.');
        }
        const expected=group.retention.eligible?
          100*group.retention.kept/group.retention.eligible:null;
        if((expected===null&&group.retention.percent!==null)||
           (expected!==null&&(!Number.isFinite(group.retention.percent)||
             Math.abs(group.retention.percent-expected)>0.051))){
          throw new Error('Nesukladna stopa povijesnog ostanka.');
        }
      }
      if(stability.quality.current!==counts['3']+counts['4']||
         stability.four.current!==counts['4']){
        throw new Error('Trajnost nije usklađena s dnevnim univerzumom.');
      }
    }
    if(!Array.isArray(payload.topOpportunities)
      ||payload.topOpportunities.some(row=>!row.ticker||!Number.isInteger(row.stage)
        ||row.stage<0||row.stage>4)){
      throw new Error('Neispravni kandidati intelligence pregleda.');
    }
    return payload;
  }

  function monthsInPeriod(start,end){
    if(!DATE_PATTERN.test(start||'')||!DATE_PATTERN.test(end||'')||end<start){
      throw new Error('Neispravan povijesni raspon.');
    }
    const month=new Date(start.slice(0,7)+'-01T00:00:00Z');
    const last=end.slice(0,7);
    const result=[];
    while(month.toISOString().slice(0,7)<=last){
      result.push(month.toISOString().slice(0,7));
      month.setUTCMonth(month.getUTCMonth()+1);
      if(result.length>1200)throw new Error('Predug povijesni raspon.');
    }
    return result;
  }

  function validateMonth(payload,month,scope){
    if(!MONTH_PATTERN.test(month)||payload?.schemaVersion!==MONTH_SCHEMA
      ||payload.month!==month||payload.scope!==scope||!Array.isArray(payload.sessions)){
      throw new Error('Neispravna mjesečna arhiva '+month+'.');
    }
    const dates=new Set();
    for(const point of payload.sessions){
      if(!DATE_PATTERN.test(point.sessionDate||'')||!point.sessionDate.startsWith(month)
        ||dates.has(point.sessionDate)||!point.runId
        ||!Array.isArray(point.unavailable)||!point.stages
        ||typeof point.stages!=='object'){
        throw new Error('Neispravno dnevno očitanje u '+month+'.');
      }
      dates.add(point.sessionDate);
      const counts={0:0,1:0,2:0,3:0,4:0};
      for(const [ticker,value] of Object.entries(point.stages)){
        if(!ticker||ticker!==ticker.toUpperCase()||!Array.isArray(value)
          ||value.length!==2||!Number.isInteger(value[0])
          ||value[0]<0||value[0]>4||!Number.isInteger(value[1])||value[1]<0||value[1]>=1024){
          throw new Error('Neispravan ticker-stupanj u '+month+'.');
        }
        counts[value[0]]++;
      }
      if(new Set(point.unavailable).size!==point.unavailable.length
        ||point.unavailable.some(t=>typeof t!=='string'||!t||t!==t.toUpperCase()||Object.hasOwn(point.stages,t))
        ||point.unavailable.length!==point.unavailableCount
        ||Object.values(counts).reduce((a,b)=>a+b,0)!==point.evaluatedCount
        ||STAGES.some(stage=>counts[stage]!==point.counts?.[stage])){
        throw new Error('Mjesečna arhiva ne odgovara EOD brojevima za '+point.sessionDate+'.');
      }
    }
    return payload;
  }

  async function loadMonths(fetcher,months,cache,scope,latestMonth){
    const data=await Promise.all(months.map(async month=>{
      if(cache.has(month))return cache.get(month);
      const response=await fetcher('data/trend-birth-ticker-history/'+month+'.json',
        {cache:month===latestMonth?'no-store':'default'});
      if(!response.ok)throw new Error('Nema arhive ticker stupnjeva za '+month+' (HTTP '+response.status+').');
      const payload=validateMonth(await response.json(),month,scope);
      cache.set(month,payload);
      return payload;
    }));
    return data;
  }

  function membersForPeriod(payloads,period,stage,asOf){
    if(!STAGES.includes(String(stage)))throw new Error('Nepoznata razina.');
    const from=period?.periodKey,to=period?.periodEnd;
    if(!DATE_PATTERN.test(from||'')||!DATE_PATTERN.test(to||''))throw new Error('Neispravno razdoblje.');
    const tickerDays=new Map();
    let days=0,occurrences=0;
    for(const month of payloads){
      for(const point of month.sessions){
        if(point.sessionDate<from||point.sessionDate>to||(asOf&&point.sessionDate>asOf))continue;
        days++;
        for(const [ticker,value] of Object.entries(point.stages)){
          if(String(value[0])!==String(stage))continue;
          occurrences++;
          const old=tickerDays.get(ticker)||{ticker,days:0,lastDate:'',stage:Number(stage)};
          old.days++;
          if(point.sessionDate>old.lastDate)old.lastDate=point.sessionDate;
          tickerDays.set(ticker,old);
        }
      }
    }
    const expected=period.counts?.[String(stage)];
    if(days!==period.sessionCount||occurrences!==expected){
      throw new Error('Povijesni tickeri nisu potpuni za odabrano razdoblje: '
        +occurrences+'/'+expected+' dionica-dana u '+days+'/'+period.sessionCount+' sesija.');
    }
    return {
      members:[...tickerDays.values()].sort((a,b)=>b.days-a.days||a.ticker.localeCompare(b.ticker)),
      tickerDays:occurrences,sessionCount:days,
    };
  }

  function journey(payloads,ticker,asOf){
    const normalized=String(ticker||'').toUpperCase();
    if(!normalized)throw new Error('Ticker nije odabran.');
    return payloads.flatMap(month=>month.sessions)
      .filter(point=>!asOf||point.sessionDate<=asOf)
      .sort((a,b)=>a.sessionDate.localeCompare(b.sessionDate))
      .map(point=>({
        sessionDate:point.sessionDate,
        stage:point.stages[normalized]?.[0]??null,
        unavailable:point.unavailable.includes(normalized),
      }))
      .filter(point=>point.stage!==null||point.unavailable);
  }

  function streaks(payloads,ticker,asOf){
    const normalized=String(ticker||'').toUpperCase();
    if(!normalized)throw new Error('Ticker nije odabran.');
    let quality=0,four=0;
    const all=payloads.flatMap(month=>month.sessions)
      .filter(point=>!asOf||point.sessionDate<=asOf)
      .sort((a,b)=>a.sessionDate.localeCompare(b.sessionDate));
    for(const point of all){
      const stage=point.stages[normalized]?.[0];
      quality=stage>=3?quality+1:0;
      four=stage===4?four+1:0;
    }
    return {quality,four};
  }

  const api={validateSummary,monthsInPeriod,validateMonth,loadMonths,membersForPeriod,journey,streaks};
  root.TrendBirthIntelligence=api;
  if(typeof module!=='undefined')module.exports=api;
})(globalThis);
