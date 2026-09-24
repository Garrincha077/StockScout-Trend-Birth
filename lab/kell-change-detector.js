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
    for(const value of [
      item?.structural_risk_atr,
      item?.kell_structural_risk_atr,
      item?.score_breakdown?.components?.readiness?.structural_risk_atr
    ]){
      const parsed=n(value);
      if(parsed!=null)return parsed;
    }
    return null;
  };
  const explicitRetestState=item=>item?.kell_metrics?.ema_retest_state||item?.kell_ema_retest_state||null;

  function normalizeHistory(value){
    if(Array.isArray(value))return value.filter(Boolean);
    return value?[value]:[];
  }

  function compactSequence(history,current){
    const out=[];
    for(const row of [...normalizeHistory(history),current]){
      const value=stage(row);
      if(!out.length||out[out.length-1]!==value)out.push(value);
    }
    return out.slice(-5);
  }

  function latestWedgeIndex(history){
    let index=-1;
    for(let i=0;i<history.length;i++){
      if(stage(history[i])==='wedge_pop'||setups(history[i]).includes('kell_wedge_pop'))index=i;
    }
    return index;
  }

  function crossbackClass(current,history){
    const currentCrossback=setups(current).includes('kell_ema_crossback')||stage(current)==='ema_crossback';
    const explicit=explicitRetestState(current);
    if(explicit==='late_retest')return'LATE RETEST';
    if(!currentCrossback&&explicit!=='first_crossback')return null;
    const wedgeIndex=latestWedgeIndex(history);
    const cycle=wedgeIndex>=0?history.slice(wedgeIndex+1):history;
    const priorCrossback=cycle.some(row=>setups(row).includes('kell_ema_crossback')||stage(row)==='ema_crossback');
    return priorCrossback?'LATE RETEST':'FIRST CROSSBACK';
  }

  function cycleMaturity(current,history){
    if(stage(current)!=='base_n_break'&&!setups(current).includes('kell_base_n_break'))return null;
    const wedgeIndex=latestWedgeIndex(history);
    const cycle=wedgeIndex>=0?history.slice(wedgeIndex):history;
    const priorBases=cycle.filter(row=>stage(row)==='base_n_break'||setups(row).includes('kell_base_n_break')).length;
    const sawCrossback=cycle.some(row=>stage(row)==='ema_crossback'||setups(row).includes('kell_ema_crossback'));
    const sawExhaustion=cycle.some(row=>stage(row)==='exhaustion_extension');
    if(sawExhaustion||priorBases>=2)return'LATE-CYCLE';
    if(priorBases===1)return'MATURE';
    if(wedgeIndex>=0||sawCrossback)return'EARLY';
    return'UNRESOLVED';
  }

  function classify(current,historyOrPrevious=[],marketContext={}){
    const history=normalizeHistory(historyOrPrevious);
    const previous=history[history.length-1]||null;
    const score=n(current?.kell_score),readiness=n(current?.kell_readiness_score);
    const previousScore=n(previous?.kell_score),previousReadiness=n(previous?.kell_readiness_score);
    const scoreDelta=score!=null&&previousScore!=null?round1(score-previousScore):null;
    const readinessDelta=readiness!=null&&previousReadiness!=null?round1(readiness-previousReadiness):null;
    const currentStage=stage(current),previousStage=previous?stage(previous):null;
    const previousSetups=new Set(setups(previous));
    const previousScreens=new Set(screens(previous));
    const addedSetups=setups(current).filter(name=>ACTION_SETUPS.has(name)&&!previousSetups.has(name));
    const addedScreens=screens(current).filter(name=>DISCOVERY_SCREENS.has(name)&&!previousScreens.has(name));
    const discoveryChanged=addedScreens.length>0;
    const stageChanged=Boolean(previous&&previousStage!==currentStage);
    const structureFailed=currentStage==='wedge_drop'&&previousStage!=='wedge_drop';
    const firstExhaustion=currentStage==='exhaustion_extension'&&previousStage!=='exhaustion_extension';
    const crossback=crossbackClass(current,history);
    const maturity=cycleMaturity(current,history);
    const actionable=addedSetups.length>0;
    const risk=riskAtr(current);
    const riskTooWide=risk!=null&&risk>=3.0;
    const defensive=marketContext?.qqqAboveEma20===false;
    const marketRegime={
      qqqAboveEma20:marketContext?.qqqAboveEma20??null,
      defensive,
      label:defensive?'DEFENSIVE REGIME':marketContext?.qqqAboveEma20===true?'FAVORABLE REGIME':'REGIME UNAVAILABLE'
    };

    let priorityBand='none';
    let headline='';
    let priority=0;
    const reasons=[];
    const changeTypes=[];

    if(discoveryChanged)changeTypes.push('discovery');
    if(stageChanged||structureFailed||firstExhaustion)changeTypes.push('stage');
    if(actionable)changeTypes.push('setup');

    if(structureFailed){
      priorityBand='risk';
      headline='STRUCTURE FAILED · WEDGE DROP';
      priority=380;
      reasons.push('WEDGE DROP');
    }else if(firstExhaustion){
      priorityBand='risk';
      headline='FIRST EXHAUSTION EXTENSION';
      priority=340;
      reasons.push('FIRST EXHAUSTION EXTENSION');
    }else if(actionable){
      priorityBand='setup';
      priority=400;
      if(addedSetups.includes('kell_ema_crossback')||crossback){
        if(crossback==='LATE RETEST'){
          headline='EMA RETEST · LATE';
          priority=320;
          reasons.push('LATE RETEST');
        }else{
          headline='FIRST ACTIONABLE CROSSBACK';
          priority=440;
          reasons.push('FIRST CROSSBACK');
        }
      }else if(addedSetups.includes('kell_base_n_break')){
        headline="BASE N' BREAK · "+(maturity||'UNRESOLVED');
        priority=maturity==='EARLY'?430:maturity==='MATURE'?390:maturity==='LATE-CYCLE'?330:370;
      }else if(addedSetups.includes('kell_wedge_pop')){
        headline='WEDGE POP APPEARED';
        priority=420;
      }else{
        headline='SETUP BECAME ACTIONABLE';
      }
    }else if(stageChanged){
      priorityBand='stage';
      headline='STAGE CHANGED';
      priority=250;
      reasons.push(labelStage(previousStage)+' → '+labelStage(currentStage));
    }else if(discoveryChanged){
      priorityBand='discovery';
      headline='DISCOVERY CHANGED';
      priority=100;
    }

    if(discoveryChanged){
      for(const name of addedScreens.slice(0,3))reasons.push('NEW '+(SCREEN_LABELS[name]||name.replace(/^kell_/,'').replaceAll('_',' ')));
    }
    if(actionable&&risk!=null){
      if(riskTooWide){
        reasons.push('RISK TOO WIDE '+risk.toFixed(2)+' ATR');
        priority-=55;
      }else{
        reasons.push('Natural invalidation '+risk.toFixed(2)+' ATR');
        if(risk<=1.5)priority+=20;
      }
    }
    if(defensive&&priorityBand!=='none'){
      reasons.push('DEFENSIVE REGIME');
      priority-=30;
    }

    const changed=changeTypes.length>0;
    const sequence=compactSequence(history,current);
    return{
      changed,
      direction:priorityBand==='risk'?'risk':changed?'changed':'none',
      priority:changed?round1(Math.max(1,priority)):0,
      priorityBand,
      headline,
      reasons,
      changeTypes,
      newCandidate:!previous,
      discoveryChanged,
      stageChanged,
      setupBecameActionable:actionable,
      actionable,
      addedScreens,
      addedSetups,
      previousStage,
      currentStage,
      sequence,
      sequenceText:sequence.map(labelStage).join(' → '),
      crossbackClass:crossback,
      emaRetestState:explicitRetestState(current),
      cycleMaturity:maturity,
      baseMaturity:maturity,
      structuralRiskAtr:risk,
      riskTooWide,
      riskLabel:risk==null?null:(riskTooWide?'Risk too wide ':'Natural invalidation ')+risk.toFixed(1)+' ATR',
      marketRegime,
      structureFailed,
      firstExhaustion,
      scoreDelta,
      readinessDelta,
      becameReady:false
    };
  }

  function payloadRows(payload){
    return Array.isArray(payload?.candidates)?payload.candidates:[];
  }

  function decorate(candidates,historyPayloads,marketContext={}){
    const ordered=(historyPayloads||[]).slice().sort((a,b)=>String(a?.source?.sessionDate||'').localeCompare(String(b?.source?.sessionDate||'')));
    const maps=ordered.map(payload=>new Map(payloadRows(payload).map(item=>[item.ticker,item])));
    const latestDate=ordered[ordered.length-1]?.source?.sessionDate||null;
    const historyDates=ordered.map(payload=>payload?.source?.sessionDate).filter(Boolean);
    for(const item of candidates||[]){
      const history=maps.map(map=>map.get(item.ticker)).filter(Boolean);
      item.kellChange={...classify(item,history,marketContext),previousDate:latestDate,historyDates};
    }
    return candidates;
  }

  function isoDateOffset(dateText,days){
    const date=new Date(dateText+'T00:00:00Z');
    if(Number.isNaN(date.getTime()))return null;
    date.setUTCDate(date.getUTCDate()+days);
    return date.toISOString().slice(0,10);
  }

  async function loadHistory(fetchImpl,currentDate,maxSessions=5,maxLookback=14){
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
    const history=await loadHistory(fetchImpl,currentDate,1,maxLookback);
    return history[0];
  }

  function summary(candidates){
    const changed=(candidates||[]).filter(item=>item?.kellChange?.changed);
    const actionable=changed.filter(item=>item.kellChange.setupBecameActionable).length;
    return{
      total:changed.length,
      discoveryChanges:changed.filter(item=>item.kellChange.discoveryChanged).length,
      stageChanges:changed.filter(item=>item.kellChange.stageChanged||item.kellChange.structureFailed||item.kellChange.firstExhaustion).length,
      actionable,
      actionableSetups:actionable,
      firstCrossbacks:changed.filter(item=>item.kellChange.crossbackClass==='FIRST CROSSBACK').length,
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
