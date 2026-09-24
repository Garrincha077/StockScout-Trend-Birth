(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.KellChanges=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const ACTION_SETUPS=new Set(['kell_wedge_pop','kell_ema_crossback','kell_base_n_break','kell_buyable_gap_proxy']);
  const SETUP_LABELS={
    kell_wedge_pop:'Wedge Pop',
    kell_ema_crossback:'EMA Crossback',
    kell_base_n_break:"Base n' Break",
    kell_buyable_gap_proxy:'Buyable Gap'
  };
  const SCREEN_LABELS={
    kell_52w_high:'52W / New High',
    kell_unusual_volume:'Unusual Volume',
    kell_rvol_3x:'RVOL >=3x',
    kell_bull_snort:'Bull Snort',
    kell_momentum_3m_50:'3M +50%',
    kell_doubler_ytd:'Doubler YTD',
    kell_gapper:'Gapper',
    kell_strength_on_down_day:'Strength on Down Day',
    kell_rs_leader:'RS Leader'
  };
  const BULLISH_STRUCTURE=new Set(['wedge_pop','ema_crossback','base_n_break','trend_ema_support']);
  const RISK_WIDE_ATR=3.0; // StockScout review proxy, not a Kell-published constant.

  const n=value=>Number.isFinite(Number(value))?Number(value):null;
  const round1=value=>Math.round(value*10)/10;
  const stage=item=>item?.stage||item?.kell_stage?.primary||item?.kell_cycle_stage||'unavailable';
  const stageBasis=item=>item?.kell_stage?.basis||[];
  const setups=item=>item?.setups||item?.kellSetups||item?.kell_setups||[];
  const screens=item=>item?.screens||item?.kellScreens||item?.kell_screens||[];
  const context=item=>item?.context||item?.kellContext||item?.kell_context||[];
  const structuralRiskAtr=item=>n(
    item?.structural_risk_atr
    ??item?.kell_structural_risk_atr
    ??item?.score_breakdown?.components?.readiness?.structural_risk_atr
  );
  const hasStageOrSetup=(item,name)=>stage(item)===name||setups(item).includes('kell_'+name);
  const unique=values=>[...new Set(values.filter(Boolean))];

  function archiveCandidates(payload){
    const rows=payload?.kellCandidates||payload?.candidates||[];
    if(!rows.length)return[];
    if(rows.every(row=>row&&typeof row==='object'&&!Array.isArray(row)))return rows;
    const columns=payload?.columns||[];
    if(columns.length&&rows.every(Array.isArray)){
      return rows.map(row=>Object.fromEntries(
        row.slice(0,columns.length).map((value,index)=>[String(columns[index]),value])
      ));
    }
    return[];
  }

  function marketState(marketContext){
    const qqqAbove20=marketContext?.qqqAboveEma20
      ??marketContext?.qqq?.aboveEma20
      ??marketContext?.qqq?.above_ema20;
    const coarse=String(
      marketContext?.regime?.state
      ??marketContext?.state
      ??marketContext?.marketRegime
      ??''
    ).toLowerCase();
    const defensive=qqqAbove20===false||['under_pressure','correction','defensive'].includes(coarse);
    return{
      qqqAbove20:typeof qqqAbove20==='boolean'?qqqAbove20:null,
      coarse:coarse||null,
      defensive,
      label:defensive?'DEFENSIVE REGIME':qqqAbove20===true?'QQQ > 20EMA':'REGIME NEUTRAL/UNKNOWN'
    };
  }

  function compressedStages(rows){
    const out=[];
    for(const row of rows){
      const value=stage(row);
      if(value&&value!=='unavailable'&&out[out.length-1]!==value)out.push(value);
    }
    return out;
  }

  function sequenceInfo(current,priorRows=[]){
    const previous=priorRows.length?priorRows[priorRows.length-1]:null;
    const currentStage=stage(current);
    const previousStage=previous?stage(previous):null;
    const currentSetups=setups(current);
    const previousSetups=new Set(previous?setups(previous):[]);
    const addedSetups=currentSetups.filter(name=>ACTION_SETUPS.has(name)&&!previousSetups.has(name));
    const currentScreens=screens(current);
    const previousScreens=new Set(previous?screens(previous):[]);
    const addedScreens=currentScreens.filter(name=>!previousScreens.has(name));

    const priorWedgeIndexes=[];
    const priorCrossbackIndexes=[];
    const priorBaseIndexes=[];
    const priorExhaustionIndexes=[];
    priorRows.forEach((row,index)=>{
      if(hasStageOrSetup(row,'wedge_pop'))priorWedgeIndexes.push(index);
      if(hasStageOrSetup(row,'ema_crossback'))priorCrossbackIndexes.push(index);
      if(hasStageOrSetup(row,'base_n_break'))priorBaseIndexes.push(index);
      if(stage(row)==='exhaustion_extension')priorExhaustionIndexes.push(index);
    });

    const lastWedge=priorWedgeIndexes.length?priorWedgeIndexes[priorWedgeIndexes.length-1]:-1;
    const priorCrossbacksAfterWedge=priorCrossbackIndexes.filter(index=>index>lastWedge);
    const crossbackActive=currentSetups.includes('kell_ema_crossback')||currentStage==='ema_crossback';
    const crossbackNew=addedSetups.includes('kell_ema_crossback')||(!previous&&crossbackActive);
    const crossbackBasisConfirmed=stageBasis(current).includes('first_retest_after_wedge_pop');
    let crossbackClass=null;
    if(crossbackActive){
      if(previous&&hasStageOrSetup(previous,'ema_crossback')){
        crossbackClass='ONGOING CROSSBACK';
      }else if(crossbackNew&&(crossbackBasisConfirmed||(lastWedge>=0&&priorCrossbacksAfterWedge.length===0))){
        crossbackClass='FIRST CROSSBACK';
      }else if(crossbackNew&&lastWedge>=0&&priorCrossbacksAfterWedge.length>0){
        crossbackClass='LATE RETEST';
      }else{
        crossbackClass='CROSSBACK · SEQUENCE UNCONFIRMED';
      }
    }

    const baseActive=currentSetups.includes('kell_base_n_break')||currentStage==='base_n_break';
    const baseNew=addedSetups.includes('kell_base_n_break')||(!previous&&baseActive);
    let cycleMaturity=null;
    if(baseActive){
      if(priorExhaustionIndexes.length||priorRows.some(row=>stage(row)==='wedge_drop')){
        cycleMaturity='LATE';
      }else if(priorBaseIndexes.length){
        cycleMaturity='MATURE';
      }else if(priorRows.some(row=>hasStageOrSetup(row,'ema_crossback')||hasStageOrSetup(row,'wedge_pop'))){
        cycleMaturity='EARLY';
      }else{
        cycleMaturity='UNCONFIRMED';
      }
    }

    const firstExhaustion=currentStage==='exhaustion_extension'&&!priorExhaustionIndexes.length;
    const exhaustionCount=currentStage==='exhaustion_extension'?priorExhaustionIndexes.length+1:null;
    const structureFailed=currentStage==='wedge_drop'&&previousStage!=='wedge_drop';
    const structureDeteriorated=currentStage==='downtrend_repair'
      &&previousStage!=null
      &&BULLISH_STRUCTURE.has(previousStage);
    const stageChanged=Boolean(previous&&currentStage!==previousStage);
    const setupActionable=addedSetups.length>0;
    const trail=compressedStages([...priorRows,current]).slice(-6);

    return{
      previous,
      previousStage,
      currentStage,
      addedSetups,
      addedScreens,
      stageChanged,
      setupActionable,
      crossbackClass,
      baseNew,
      cycleMaturity,
      firstExhaustion,
      exhaustionCount,
      structureFailed,
      structureDeteriorated,
      trail
    };
  }

  function headlineFor(seq){
    if(seq.structureFailed)return'STRUCTURE FAILED · WEDGE DROP';
    if(seq.structureDeteriorated)return'STRUCTURE DETERIORATED';
    if(seq.crossbackClass==='FIRST CROSSBACK'&&seq.setupActionable)return'FIRST ACTIONABLE CROSSBACK';
    if(seq.addedSetups.includes('kell_base_n_break')){
      return"BASE N' BREAK · "+(seq.cycleMaturity||'UNCONFIRMED');
    }
    if(seq.addedSetups.includes('kell_wedge_pop'))return'WEDGE POP APPEARED';
    if(seq.addedSetups.includes('kell_buyable_gap_proxy'))return'BUYABLE GAP APPEARED';
    if(seq.firstExhaustion)return'FIRST EXHAUSTION EXTENSION';
    if(seq.currentStage==='exhaustion_extension'&&seq.stageChanged)return'EXHAUSTION EXTENSION #'+seq.exhaustionCount;
    if(seq.stageChanged)return'STAGE CHANGED';
    if(seq.addedScreens.length)return'DISCOVERY CHANGED';
    return null;
  }

  function classify(current,history=[],marketContext=null){
    const priorRows=Array.isArray(history)?history.filter(Boolean):(history?[history]:[]);
    const seq=sequenceInfo(current,priorRows);
    const previous=seq.previous;
    const score=n(current?.kell_score),readiness=n(current?.kell_readiness_score);
    const previousScore=n(previous?.kell_score),previousReadiness=n(previous?.kell_readiness_score);
    const scoreDelta=score!=null&&previousScore!=null?round1(score-previousScore):null;
    const readinessDelta=readiness!=null&&previousReadiness!=null?round1(readiness-previousReadiness):null;
    const riskAtr=structuralRiskAtr(current);
    const riskTooWide=riskAtr!=null&&riskAtr>=RISK_WIDE_ATR;
    const regime=marketState(marketContext);

    const changeTypes=[];
    if(seq.setupActionable)changeTypes.push('setup');
    if(seq.structureFailed||seq.structureDeteriorated||seq.firstExhaustion)changeTypes.push('risk');
    if(seq.stageChanged||seq.firstExhaustion||seq.structureFailed||seq.structureDeteriorated)changeTypes.push('stage');
    if(seq.addedScreens.length)changeTypes.push('discovery');

    const headline=headlineFor(seq);
    const changed=Boolean(headline);
    let priorityBand='none';
    let priority=0;
    if(changed){
      if(seq.setupActionable){
        priorityBand='setup';
        priority=4000;
        if(seq.crossbackClass==='FIRST CROSSBACK')priority+=900;
        else if(seq.crossbackClass==='LATE RETEST')priority+=250;
        if(seq.addedSetups.includes('kell_base_n_break'))priority+=seq.cycleMaturity==='EARLY'?800:seq.cycleMaturity==='MATURE'?450:200;
        if(seq.addedSetups.includes('kell_wedge_pop'))priority+=650;
        if(seq.addedSetups.includes('kell_buyable_gap_proxy'))priority+=500;
      }else if(seq.structureFailed||seq.structureDeteriorated||seq.firstExhaustion){
        priorityBand='risk';
        priority=3900+(seq.structureFailed?800:seq.structureDeteriorated?600:500);
      }else if(seq.stageChanged){
        priorityBand='stage';
        priority=3000;
      }else if(seq.addedScreens.length){
        priorityBand='discovery';
        priority=2000;
      }
      if(riskAtr!=null)priority+=Math.max(0,300-Math.min(300,riskAtr*75));
      if(riskTooWide)priority-=500;
      if(regime.defensive&&priorityBand==='setup')priority-=250;
    }

    const reasons=[];
    if(headline)reasons.push(headline);
    if(seq.crossbackClass&&seq.crossbackClass!=='FIRST CROSSBACK')reasons.push(seq.crossbackClass);
    if(seq.addedScreens.length&&priorityBand!=='discovery'){
      reasons.push('Discovery +'+seq.addedScreens.length);
    }
    if(riskAtr!=null)reasons.push((riskTooWide?'RISK TOO WIDE ':'Natural invalidation ')+riskAtr.toFixed(2)+' ATR');
    if(regime.defensive)reasons.push(regime.label);

    return{
      changed,
      direction:seq.structureFailed||seq.structureDeteriorated||seq.firstExhaustion?'risk':seq.setupActionable?'actionable':changed?'changed':'none',
      priority:changed?round1(priority):0,
      priorityBand,
      headline,
      changeTypes:unique(changeTypes),
      reasons,
      newCandidate:!previous&&changed,
      addedScreens:seq.addedScreens,
      addedSetups:seq.addedSetups,
      previousStage:seq.previousStage,
      currentStage:seq.currentStage,
      stageChanged:seq.stageChanged,
      setupActionable:seq.setupActionable,
      crossbackClass:seq.crossbackClass,
      cycleMaturity:seq.cycleMaturity,
      firstExhaustion:seq.firstExhaustion,
      exhaustionCount:seq.exhaustionCount,
      structureFailed:seq.structureFailed,
      structureDeteriorated:seq.structureDeteriorated,
      sequenceTrail:seq.trail,
      structuralRiskAtr:riskAtr,
      riskTooWide,
      marketRegime:regime,
      scoreDelta,
      readinessDelta
    };
  }

  function decorate(candidates,historyInput,marketContext=null){
    const payloads=(Array.isArray(historyInput)?historyInput:(historyInput?[historyInput]:[]))
      .filter(Boolean)
      .slice()
      .sort((a,b)=>String(a?.source?.sessionDate||'').localeCompare(String(b?.source?.sessionDate||'')));
    const dates=payloads.map(payload=>payload?.source?.sessionDate).filter(Boolean);
    const indexes=payloads.map(payload=>new Map(
      archiveCandidates(payload).map(item=>[item.ticker,item])
    ));
    for(const item of candidates||[]){
      const rows=indexes.map(index=>index.get(item.ticker)).filter(Boolean);
      item.kellChange={
        ...classify(item,rows,marketContext),
        previousDate:dates.length?dates[dates.length-1]:null,
        historyDates:dates
      };
    }
    return candidates;
  }

  function isoDateOffset(dateText,days){
    const date=new Date(dateText+'T00:00:00Z');
    if(Number.isNaN(date.getTime()))return null;
    date.setUTCDate(date.getUTCDate()+days);
    return date.toISOString().slice(0,10);
  }

  async function gunzipBase64(text){
    if(typeof DecompressionStream!=='function'||typeof atob!=='function')throw new Error('gzip history unsupported in this browser');
    const binary=atob(String(text||'').replace(/\s+/g,''));
    const bytes=Uint8Array.from(binary,char=>char.charCodeAt(0));
    const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    return JSON.parse(await new Response(stream).text());
  }

  async function fetchHistoryPayload(fetchImpl,date){
    let response=await fetchImpl('data/kell-score-history/'+date+'.json',{cache:'no-store'});
    if(response.status!==404){
      if(!response.ok)throw new Error('Kell history '+date+' HTTP '+response.status);
      return await response.json();
    }
    response=await fetchImpl('data/kell-score-history/'+date+'.json.gz.b64',{cache:'no-store'});
    if(response.status===404)return null;
    if(!response.ok)throw new Error('Kell compressed history '+date+' HTTP '+response.status);
    try{
      return await gunzipBase64(await response.text());
    }catch(_err){
      return null;
    }
  }

  function normalizeArchive(payload,date){
    if(!payload)return null;
    const session=payload?.source?.sessionDate;
    if(session!==date)throw new Error('Kell history date mismatch for '+date);
    const candidates=archiveCandidates(payload);
    return{...payload,candidates};
  }

  async function loadHistory(fetchImpl,currentDate,maxSessions=5,maxLookback=20){
    if(!currentDate)throw new Error('current Kell session date missing');
    const payloads=[];
    for(let days=1;days<=maxLookback&&payloads.length<maxSessions;days++){
      const date=isoDateOffset(currentDate,-days);
      const payload=normalizeArchive(await fetchHistoryPayload(fetchImpl,date),date);
      if(payload)payloads.push(payload);
    }
    if(!payloads.length)throw new Error('no prior Kell score snapshot within '+maxLookback+' days');
    return payloads.sort((a,b)=>String(a.source.sessionDate).localeCompare(String(b.source.sessionDate)));
  }

  async function loadPrevious(fetchImpl,currentDate,maxLookback=10){
    const history=await loadHistory(fetchImpl,currentDate,1,maxLookback);
    return history[history.length-1];
  }

  function summary(candidates){
    const changed=(candidates||[]).filter(item=>item?.kellChange?.changed);
    return{
      total:changed.length,
      actionable:changed.filter(item=>item.kellChange.priorityBand==='setup').length,
      risk:changed.filter(item=>item.kellChange.priorityBand==='risk').length,
      stage:changed.filter(item=>item.kellChange.priorityBand==='stage').length,
      discovery:changed.filter(item=>item.kellChange.priorityBand==='discovery').length,
      firstCrossbacks:changed.filter(item=>item.kellChange.crossbackClass==='FIRST CROSSBACK').length,
      earlyBases:changed.filter(item=>item.kellChange.cycleMaturity==='EARLY'&&item.kellChange.addedSetups?.includes('kell_base_n_break')).length,
      defensive:changed.filter(item=>item.kellChange.marketRegime?.defensive).length
    };
  }

  return{
    ACTION_SETUPS,SETUP_LABELS,SCREEN_LABELS,RISK_WIDE_ATR,
    archiveCandidates,marketState,sequenceInfo,classify,decorate,
    loadHistory,loadPrevious,summary
  };
});
