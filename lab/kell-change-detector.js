(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.KellChanges=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const ACTION_SETUPS=new Set(['kell_wedge_pop','kell_ema_crossback','kell_base_n_break','kell_buyable_gap_proxy']);
  const DISCOVERY_SCREENS=new Set([
    'kell_52w_high','kell_unusual_volume','kell_rvol_3x','kell_bull_snort',
    'kell_momentum_3m_50','kell_doubler_ytd','kell_gapper',
    'kell_strength_on_down_day','kell_rs_leader'
  ]);
  const SETUP_LABELS={
    kell_wedge_pop:'Wedge Pop',
    kell_ema_crossback:'EMA Crossback',
    kell_base_n_break:"Base n' Break",
    kell_buyable_gap_proxy:'Buyable Gap'
  };
  const SCREEN_LABELS={
    kell_52w_high:'52W/New High',
    kell_unusual_volume:'Unusual Volume',
    kell_rvol_3x:'RVOL 3x',
    kell_bull_snort:'Bull Snort',
    kell_momentum_3m_50:'3M Momentum',
    kell_doubler_ytd:'Doubler YTD',
    kell_gapper:'Gapper',
    kell_strength_on_down_day:'Strength on Down Day',
    kell_rs_leader:'RS Leader'
  };
  const STAGE_LABELS={
    reversal_extension:'Reversal Extension',
    wedge_pop:'Wedge Pop',
    ema_crossback:'EMA Crossback',
    base_n_break:"Base n' Break",
    exhaustion_extension:'Exhaustion Extension',
    wedge_drop:'Wedge Drop',
    trend_ema_support:'Trend / EMA Support',
    downtrend_repair:'Downtrend / Repair',
    transition:'Transition',
    unavailable:'Unavailable'
  };
  const n=value=>Number.isFinite(Number(value))?Number(value):null;
  const round1=value=>Math.round(value*10)/10;
  const stage=item=>item?.stage||item?.kell_stage?.primary||item?.kell_cycle_stage||'unavailable';
  const setups=item=>item?.setups||item?.kellSetups||item?.kell_setups||[];
  const screens=item=>item?.screens||item?.kellScreens||item?.kell_screens||[];
  const labelStage=value=>STAGE_LABELS[value]||String(value||'Unavailable').replaceAll('_',' ');
  const riskAtr=item=>{
    const direct=n(item?.kell_structural_risk_atr);
    if(direct!=null)return direct;
    return n(item?.score_breakdown?.components?.readiness?.structural_risk_atr);
  };
  const retestState=item=>item?.kell_metrics?.ema_retest_state||item?.kell_ema_retest_state||null;

  function payloadRows(payload){
    return Array.isArray(payload?.candidates)?payload.candidates:[];
  }

  function tickerHistory(ticker,current,historyPayloads){
    const points=[];
    for(const payload of historyPayloads||[]){
      const row=payloadRows(payload).find(item=>item?.ticker===ticker);
      if(row)points.push({date:payload?.source?.sessionDate||null,row});
    }
    points.sort((a,b)=>String(a.date).localeCompare(String(b.date)));
    points.push({date:null,row:current,current:true});
    return points;
  }

  function compactSequence(points){
    const out=[];
    for(const point of points||[]){
      const value=stage(point.row);
      if(!out.length||out[out.length-1]!==value)out.push(value);
    }
    return out.slice(-5);
  }

  function baseMaturity(points,currentStage){
    if(currentStage!=='base_n_break')return null;
    const prior=(points||[]).slice(0,-1);
    let lastPop=-1;
    for(let i=0;i<prior.length;i++){
      if(stage(prior[i].row)==='wedge_pop'||setups(prior[i].row).includes('kell_wedge_pop'))lastPop=i;
    }
    const cycle=lastPop>=0?prior.slice(lastPop):prior;
    const priorBases=cycle.filter(point=>stage(point.row)==='base_n_break'||setups(point.row).includes('kell_base_n_break')).length;
    const sawCrossback=cycle.some(point=>stage(point.row)==='ema_crossback'||setups(point.row).includes('kell_ema_crossback'));
    const sawExhaustion=cycle.some(point=>stage(point.row)==='exhaustion_extension');
    if(sawExhaustion||priorBases>=2)return'LATE-CYCLE';
    if(priorBases===1)return'MATURE';
    if(lastPop>=0||sawCrossback)return'EARLY';
    return'UNRESOLVED';
  }

  function riskLabel(value){
    if(value==null)return null;
    if(value<=1.5)return'Natural invalidation '+value.toFixed(1)+' ATR';
    if(value>=3.0)return'Risk too wide '+value.toFixed(1)+' ATR';
    return'Natural invalidation '+value.toFixed(1)+' ATR';
  }

  function classify(current,previous,historyPayloads=[]){
    const score=n(current?.kell_score),readiness=n(current?.kell_readiness_score);
    const previousScore=n(previous?.kell_score),previousReadiness=n(previous?.kell_readiness_score);
    const scoreDelta=score!=null&&previousScore!=null?round1(score-previousScore):null;
    const readinessDelta=readiness!=null&&previousReadiness!=null?round1(readiness-previousReadiness):null;
    const currentStage=stage(current);
    const previousStage=previous?stage(previous):null;
    const previousSetups=new Set(setups(previous));
    const previousScreens=new Set(screens(previous));
    const addedSetups=setups(current).filter(name=>ACTION_SETUPS.has(name)&&!previousSetups.has(name));
    const addedScreens=screens(current).filter(name=>DISCOVERY_SCREENS.has(name)&&!previousScreens.has(name));
    const points=tickerHistory(current?.ticker,current,historyPayloads);
    const sequence=compactSequence(points);
    const maturity=baseMaturity(points,currentStage);
    const retest=retestState(current);

    const structureFailed=currentStage==='wedge_drop'&&previousStage!=='wedge_drop';
    const firstExhaustion=currentStage==='exhaustion_extension'&&previousStage!=='exhaustion_extension';
    const stageChanged=Boolean(previous&&previousStage!==currentStage);
    const actionable=addedSetups.length>0;
    const lateRetest=retest==='late_retest';
    const discoveryChanged=addedScreens.length>0||(!previous&&screens(current).some(name=>DISCOVERY_SCREENS.has(name)));

    const changeTypes=[];
    if(discoveryChanged)changeTypes.push('discovery');
    if(stageChanged||structureFailed||firstExhaustion||lateRetest)changeTypes.push('stage');
    if(actionable)changeTypes.push('setup');

    const reasons=[];
    let headline='';
    if(structureFailed){
      headline='STRUCTURE FAILED';
      reasons.push('WEDGE DROP');
    }else if(actionable){
      if(addedSetups.includes('kell_ema_crossback')){
        headline='SETUP BECAME ACTIONABLE';
        reasons.push('FIRST CROSSBACK');
      }else if(addedSetups.includes('kell_base_n_break')){
        headline='SETUP BECAME ACTIONABLE';
        reasons.push("BASE N' BREAK"+(maturity?' · '+maturity:''));
      }else if(addedSetups.includes('kell_wedge_pop')){
        headline='SETUP BECAME ACTIONABLE';
        reasons.push('WEDGE POP');
      }else{
        headline='SETUP BECAME ACTIONABLE';
      }
      for(const name of addedSetups){
        const label=SETUP_LABELS[name]||name.replace(/^kell_/,'').replaceAll('_',' ');
        if(!reasons.some(reason=>reason.includes(label.toUpperCase())))reasons.push('NEW '+label);
      }
    }else if(lateRetest){
      headline='STAGE CHANGED';
      reasons.push('LATE RETEST');
    }else if(firstExhaustion){
      headline='STAGE CHANGED';
      reasons.push('FIRST EXHAUSTION EXTENSION');
    }else if(stageChanged){
      headline='STAGE CHANGED';
      reasons.push(labelStage(previousStage)+' → '+labelStage(currentStage));
    }else if(discoveryChanged){
      headline='DISCOVERY CHANGED';
    }

    if(discoveryChanged){
      for(const name of addedScreens.slice(0,3))reasons.push('NEW '+(SCREEN_LABELS[name]||name.replace(/^kell_/,'').replaceAll('_',' ')));
    }

    const risk=riskAtr(current);
    let priority=0;
    if(actionable)priority=400;
    else if(structureFailed)priority=360;
    else if(firstExhaustion)priority=320;
    else if(stageChanged)priority=250;
    else if(lateRetest)priority=210;
    else if(discoveryChanged)priority=100;
    if(actionable&&risk!=null){
      if(risk<=1.5)priority+=25;
      else if(risk>=3.0)priority-=45;
      else if(risk>=2.5)priority-=20;
    }
    if(addedSetups.includes('kell_ema_crossback'))priority+=20;
    if(addedSetups.includes('kell_wedge_pop'))priority+=10;

    const changed=changeTypes.length>0;
    return{
      changed,
      direction:structureFailed||firstExhaustion?'risk':changed?'changed':'none',
      priority:changed?round1(priority):0,
      headline,
      changeTypes,
      reasons,
      newCandidate:!previous,
      discoveryChanged,
      stageChanged,
      setupBecameActionable:actionable,
      addedScreens,
      addedSetups,
      previousStage,
      currentStage,
      sequence,
      sequenceText:sequence.map(labelStage).join(' → '),
      baseMaturity:maturity,
      emaRetestState:retest,
      structuralRiskAtr:risk,
      riskLabel:riskLabel(risk),
      structureFailed,
      firstExhaustion,
      scoreDelta,
      readinessDelta,
      becameReady:false
    };
  }

  function decorate(candidates,historyPayloads){
    const ordered=(historyPayloads||[]).slice().sort((a,b)=>String(a?.source?.sessionDate||'').localeCompare(String(b?.source?.sessionDate||'')));
    const latest=ordered[ordered.length-1]||null;
    const latestByTicker=new Map(payloadRows(latest).map(item=>[item.ticker,item]));
    for(const item of candidates||[]){
      item.kellChange={...classify(item,latestByTicker.get(item.ticker),ordered),previousDate:latest?.source?.sessionDate||null,historyDates:ordered.map(payload=>payload?.source?.sessionDate).filter(Boolean)};
    }
    return candidates;
  }

  function isoDateOffset(dateText,days){
    const date=new Date(dateText+'T00:00:00Z');
    if(Number.isNaN(date.getTime()))return null;
    date.setUTCDate(date.getUTCDate()+days);
    return date.toISOString().slice(0,10);
  }

  async function loadHistory(fetchImpl,currentDate,maxLookback=14,maxSessions=5){
    if(!currentDate)throw new Error('current Kell session date missing');
    const payloads=[];
    for(let days=1;days<=maxLookback&&payloads.length<maxSessions;days++){
      const date=isoDateOffset(currentDate,-days);
      const response=await fetchImpl('data/kell-score-history/'+date+'.json',{cache:'no-store'});
      if(response.status===404)continue;
      if(!response.ok)throw new Error('Kell history '+date+' HTTP '+response.status);
      const payload=await response.json();
      if(payload?.schemaVersion!=='kell-score-history-v1')throw new Error('invalid Kell history schema for '+date);
      if(payload?.source?.sessionDate!==date)throw new Error('Kell history date mismatch for '+date);
      payloads.push(payload);
    }
    if(!payloads.length)throw new Error('no prior uncompressed Kell score snapshot within '+maxLookback+' days');
    return payloads.sort((a,b)=>String(a.source.sessionDate).localeCompare(String(b.source.sessionDate)));
  }

  async function loadPrevious(fetchImpl,currentDate,maxLookback=10){
    const rows=await loadHistory(fetchImpl,currentDate,maxLookback,1);
    return rows[0];
  }

  function summary(candidates){
    const changed=(candidates||[]).filter(item=>item?.kellChange?.changed);
    return{
      total:changed.length,
      discoveryChanges:changed.filter(item=>item.kellChange.discoveryChanged).length,
      stageChanges:changed.filter(item=>item.kellChange.stageChanged||item.kellChange.structureFailed||item.kellChange.firstExhaustion).length,
      actionableSetups:changed.filter(item=>item.kellChange.setupBecameActionable).length,
      firstCrossbacks:changed.filter(item=>item.kellChange.reasons?.includes('FIRST CROSSBACK')).length,
      structureFailures:changed.filter(item=>item.kellChange.structureFailed).length,
      newCandidates:changed.filter(item=>item.kellChange.newCandidate).length,
      becameReady:0,
      newSetups:changed.filter(item=>item.kellChange.addedSetups?.length).length
    };
  }

  return{
    ACTION_SETUPS,DISCOVERY_SCREENS,SETUP_LABELS,SCREEN_LABELS,STAGE_LABELS,
    classify,decorate,loadHistory,loadPrevious,summary
  };
});
