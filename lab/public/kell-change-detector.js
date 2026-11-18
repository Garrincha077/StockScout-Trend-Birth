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
  const n=value=>Number.isFinite(Number(value))?Number(value):null;
  const stage=item=>item?.stage||item?.kell_stage?.primary||item?.kell_cycle_stage||'unavailable';
  const setups=item=>item?.setups||item?.kellSetups||item?.kell_setups||[];
  const round1=value=>Math.round(value*10)/10;

  function classify(current,previous){
    const score=n(current?.kell_score),readiness=n(current?.kell_readiness_score);
    if(!previous){
      const changed=(score!=null&&score>=60)||(readiness!=null&&readiness>=80);
      return{
        changed,
        direction:changed?'improved':'none',
        priority:changed?90+(readiness||0)/10+(score||0)/20:0,
        reasons:changed?['NEW KELL']:[],
        newCandidate:changed,
        addedSetups:[],
        previousStage:null,
        currentStage:stage(current),
        scoreDelta:null,
        readinessDelta:null,
        becameReady:false
      };
    }

    const previousScore=n(previous.kell_score),previousReadiness=n(previous.kell_readiness_score);
    const scoreDelta=score!=null&&previousScore!=null?round1(score-previousScore):null;
    const readinessDelta=readiness!=null&&previousReadiness!=null?round1(readiness-previousReadiness):null;
    const previousSetups=new Set(setups(previous));
    const addedSetups=setups(current).filter(name=>ACTION_SETUPS.has(name)&&!previousSetups.has(name));
    const becameReady=previousReadiness!=null&&readiness!=null&&previousReadiness<80&&readiness>=80;
    const setupImproved=addedSetups.length>0&&readiness!=null&&readiness>=60;
    const readinessJump=readinessDelta!=null&&readinessDelta>=30;
    const scoreJump=scoreDelta!=null&&scoreDelta>=20;
    const changed=becameReady||setupImproved||readinessJump||scoreJump;
    const reasons=[];
    if(becameReady)reasons.push('READY');
    for(const name of addedSetups)reasons.push('NEW '+(SETUP_LABELS[name]||name.replace(/^kell_/,'').replaceAll('_',' ')));
    if(readinessJump&&!becameReady)reasons.push('R +'+readinessDelta.toFixed(1));
    if(scoreJump)reasons.push('Kell +'+scoreDelta.toFixed(1));

    let priority=0;
    if(becameReady)priority+=60;
    priority+=Math.min(2,addedSetups.length)*35;
    if(readinessJump)priority+=Math.min(35,readinessDelta);
    if(scoreJump)priority+=Math.min(25,scoreDelta);
    if(stage(current)!==stage(previous))priority+=8;
    priority+=(readiness||0)/20;

    return{
      changed,
      direction:changed?'improved':'none',
      priority:changed?round1(priority):0,
      reasons,
      newCandidate:false,
      addedSetups,
      previousStage:stage(previous),
      currentStage:stage(current),
      scoreDelta,
      readinessDelta,
      becameReady
    };
  }

  function decorate(candidates,previousPayload){
    const previousDate=previousPayload?.source?.sessionDate||null;
    const previousRows=previousPayload?.candidates||[];
    const previousByTicker=new Map(previousRows.map(item=>[item.ticker,item]));
    for(const item of candidates||[]){
      item.kellChange={...classify(item,previousByTicker.get(item.ticker)),previousDate};
    }
    return candidates;
  }

  function isoDateOffset(dateText,days){
    const date=new Date(dateText+'T00:00:00Z');
    if(Number.isNaN(date.getTime()))return null;
    date.setUTCDate(date.getUTCDate()+days);
    return date.toISOString().slice(0,10);
  }

  async function loadPrevious(fetchImpl,currentDate,maxLookback=10){
    if(!currentDate)throw new Error('current Kell session date missing');
    for(let days=1;days<=maxLookback;days++){
      const date=isoDateOffset(currentDate,-days);
      const response=await fetchImpl('data/kell-score-history/'+date+'.json',{cache:'no-store'});
      if(response.status===404)continue;
      if(!response.ok)throw new Error('Kell history '+date+' HTTP '+response.status);
      const payload=await response.json();
      if(payload?.schemaVersion!=='kell-score-history-v1')throw new Error('invalid Kell history schema for '+date);
      if(payload?.source?.sessionDate!==date)throw new Error('Kell history date mismatch for '+date);
      return payload;
    }
    throw new Error('no prior uncompressed Kell score snapshot within '+maxLookback+' days');
  }

  function summary(candidates){
    const changed=(candidates||[]).filter(item=>item?.kellChange?.changed);
    return{
      total:changed.length,
      newCandidates:changed.filter(item=>item.kellChange.newCandidate).length,
      becameReady:changed.filter(item=>item.kellChange.becameReady).length,
      newSetups:changed.filter(item=>item.kellChange.addedSetups?.length).length
    };
  }

  return{ACTION_SETUPS,SETUP_LABELS,classify,decorate,loadPrevious,summary};
});
