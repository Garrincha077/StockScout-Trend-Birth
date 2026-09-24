const state={data:null,kellData:null,kellLoading:null,kellChangesLoading:null,kellChangesPreviousDate:null,kellChangesHistoryDates:[],kellChartShards:new Map(),kellChartLoading:new Map(),universe:'all',filters:[],query:'',sort:'default',chartPeriod:'1y',watchlist:WatchlistStore.load(window.localStorage),renderedItems:[],detailTicker:null,quickView:null};
const $=s=>document.querySelector(s);
const fmt=(n,d=2)=>Number.isFinite(Number(n))?Number(n).toFixed(d):'—';
const pct=n=>Number.isFinite(Number(n))?fmt(n,1)+'%':'—';
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const labels={'bottom-fishing':'Bottom','next':'Next','ryan-original':'Ryan','kell-daily':'Kell 3x','kell-gap':'Kell Gap'};
const universeLabels={'all':'All','bottom-fishing':'Bottom','next':'Next','ryan-original':'Ryan','watchlist':'Watchlist'};
const label=s=>labels[s]||s;
const kellScreenLabels={
  'kell_52w_high':'52W / New High',
  'kell_unusual_volume':'Unusual Vol ≥2x',
  'kell_rvol_3x':'RVOL ≥3x',
  'kell_bull_snort':'Bull Snort',
  'kell_momentum_3m_50':'3M +50%',
  'kell_doubler_ytd':'Doublers YTD',
  'kell_gapper':'Gapper',
  'kell_strength_on_down_day':'Strength on Down Day',
  'kell_rs_leader':'RS Leader'
};
const kellSetupLabels={
  'kell_buyable_gap_proxy':'Buyable Gap proxy',
  'kell_wedge_pop':'Wedge Pop setup',
  'kell_ema_crossback':'EMA Crossback setup',
  'kell_base_n_break':"Base n' Break setup",
  'kell_tightening':'Tightening',
  'kell_breakout_proximity':'Near Breakout'
};
const kellContextLabels={
  'kell_focus':'Kell Shortlist',
  'kell_name_selection_ok':'Kell Liquid/Price',
  'kell_growth_context':'Growth Context',
  'kell_rs_divergence':'RS Divergence',
  'kell_weekly_trend_ok':'Weekly 10EMA',
  'kell_ema_readiness':'EMA10/20 Ready'
};
const kellStageLabels={
  'stage:reversal_extension':'Reversal Extension',
  'stage:wedge_pop':'Wedge Pop',
  'stage:ema_crossback':'EMA Crossback',
  'stage:base_n_break':"Base n' Break",
  'stage:exhaustion_extension':'Exhaustion Extension',
  'stage:wedge_drop':'Wedge Drop',
  'stage:trend_ema_support':'Trend / EMA Support',
  'stage:downtrend_repair':'Downtrend / Repair',
  'stage:transition':'Transition',
  'stage:unavailable':'Unavailable'
};
const kellFilterLabels={
  'kell-any':'Kell Hits',
  ...kellScreenLabels,
  ...kellStageLabels,
  ...kellSetupLabels,
  ...kellContextLabels,
  'kell-score':'Kell Focus ≥60',
  'kell-ready':'Readiness ≥80',
  'kell-changed':'Cycle changed',
  'multi':'Multi-hit',
  'action':'Action'
};
const kellFilters=new Set(Object.keys(kellFilterLabels).filter(key=>!['multi','action'].includes(key)));
const quickViews={
  changed:{filters:['kell-changed'],sort:'change'},
  ready:{filters:['kell-ready'],sort:'readiness'},
  leaders:{filters:['kell_rs_leader','kell_weekly_trend_ok'],sort:'quality'},
  breakout:{filters:['kell_breakout_proximity','kell_weekly_trend_ok'],sort:'readiness'},
  extended:{filters:['stage:exhaustion_extension'],sort:'kell-score'},
  reset:{filters:[],sort:'default'}
};
const stageName=value=>kellStageLabels['stage:'+(value||'unavailable')]||String(value||'unavailable').replaceAll('_',' ');
const primaryStage=item=>item?.kell_stage?.primary||item?.kell_cycle_stage||'unavailable';
const isWatched=ticker=>WatchlistStore.has(state.watchlist,ticker);
function toggleWatchlist(ticker){
  state.watchlist=WatchlistStore.toggle(state.watchlist,ticker,{
    addedSession:state.data?.source?.sessionDate||null
  });
  state.watchlist=WatchlistStore.save(window.localStorage,state.watchlist);
  render();
}
function watchlistItems(){
  const review=new Map((state.data?.candidates||[]).map(item=>[item.ticker,item]));
  const kell=new Map((state.kellData?.kellCandidates||state.data?.kellCandidates||[]).map(item=>[item.ticker,item]));
  const unified=new Map((state.kellData?.unifiedCandidateIndex||state.data?.unifiedCandidateIndex||[]).map(item=>[item.ticker,item]));
  return(state.watchlist||[]).map(saved=>{
    const current=unified.get(saved.ticker);
    const base=review.get(saved.ticker);
    const overlay=kell.get(saved.ticker);
    if(!current&&!base&&!overlay){
      return{ticker:saved.ticker,sources:[],unifiedSources:[],metrics:{},watchlistSaved:saved,watchlistMissing:true};
    }
    const merged={
      ...(current||{}),
      ...(base||{}),
      ...(overlay||{}),
      ticker:saved.ticker,
      sources:[...new Set([...(current?.sources||current?.unifiedSources||[]),...(base?.sources||[]),...(overlay?.sources||[])])],
      unifiedSources:[...new Set([...(current?.unifiedSources||current?.sources||[]),...(base?.unifiedSources||[]),...(overlay?.unifiedSources||[])])],
      metrics:{...(current?.metrics||{}),...(base?.metrics||{}),...(overlay?.metrics||{})},
      chartBars:base?.chartBars?.length?base.chartBars:overlay?.chartBars,
      weeklyChartBars:base?.weeklyChartBars?.length?base.weeklyChartBars:overlay?.weeklyChartBars,
      analysis:base?.analysis||overlay?.analysis||{},
      watchlistSaved:saved
    };
    if(current&&!base&&!overlay)merged.watchlistUnifiedOnly=true;
    return merged;
  });
}
function updateWatchlistButton(){
  const button=$('#watchlistUniverse');
  if(!button)return;
  button.textContent='★ Watchlist ('+(state.watchlist?.length||0)+')';
}


function normalizeBars(rows){
  return(rows||[]).map(r=>Array.isArray(r)
    ?{time:r[0],open:+r[1],high:+r[2],low:+r[3],close:+r[4],volume:+r[5]}
    :{time:r.time||r.date,open:+r.open,high:+r.high,low:+r.low,close:+r.close,volume:+(r.volume||0)})
    .filter(r=>[r.open,r.high,r.low,r.close].every(Number.isFinite));
}
function avg(values,n,ema=false){
  let out=[],sum=0,cur=values[0]||0,w=2/(n+1);
  values.forEach((v,i)=>{
    if(ema){cur=i?v*w+cur*(1-w):v;out.push(i+1>=n?cur:null)}
    else{sum+=v;if(i>=n)sum-=values[i-n];out.push(i+1>=n?sum/n:null)}
  });
  return out;
}
const chartPeriods={
  '3m':{label:'3M · D',daily:63},
  '6m':{label:'6M · D',daily:126},
  '1y':{label:'1Y · D',daily:260},
  '5y':{label:'5Y · W',weekly:true,weeks:260}
};
function barDate(value){
  const text=String(value??'').trim();
  const match=text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if(match)return new Date(Date.UTC(+match[1],+match[2]-1,+match[3]));
  const numeric=Number(value);
  if(Number.isFinite(numeric)&&numeric>0){
    const date=new Date(numeric<1e12?numeric*1000:numeric);
    return Number.isNaN(date.getTime())?null:date;
  }
  return null;
}
function weeklyBars(rows){
  const bars=normalizeBars(rows),out=[];
  let current=null;
  for(const bar of bars){
    const date=barDate(bar.time);if(!date)continue;
    const day=date.getUTCDay(),offset=(day+6)%7;
    const monday=new Date(date.getTime()-offset*86400000);
    const key=monday.toISOString().slice(0,10);
    if(!current||current.key!==key){
      current={key,time:date.toISOString().slice(0,10),open:bar.open,high:bar.high,low:bar.low,close:bar.close,volume:bar.volume||0};
      out.push(current);
    }else{
      current.time=date.toISOString().slice(0,10);
      current.high=Math.max(current.high,bar.high);
      current.low=Math.min(current.low,bar.low);
      current.close=bar.close;
      current.volume+=(bar.volume||0);
    }
  }
  return out;
}
function rowsForPeriod(item){
  const period=chartPeriods[state.chartPeriod]||chartPeriods['1y'];
  if(period.weekly){
    const weekly=item?.weeklyChartBars?.length>=2?normalizeBars(item.weeklyChartBars):weeklyBars(item?.chartBars||[]);
    return weekly.slice(-period.weeks);
  }
  return normalizeBars(item?.chartBars||[]).slice(-period.daily);
}
function barDateLabel(value){
  const date=barDate(value);
  if(date){
    const day=String(date.getUTCDate()).padStart(2,'0');
    const month=String(date.getUTCMonth()+1).padStart(2,'0');
    const year=String(date.getUTCFullYear()).slice(2);
    return day+'.'+month+'.'+year;
  }
  return String(value??'').slice(0,8)||'—';
}
function priceLabel(value){
  const n=Number(value);
  if(!Number.isFinite(n))return '—';
  if(Math.abs(n)>=1000)return n.toFixed(0);
  if(Math.abs(n)>=100)return n.toFixed(1);
  if(Math.abs(n)>=10)return n.toFixed(2);
  return n.toFixed(3);
}
function draw(canvas,rows,large=false,emptyMessage='Chart data unavailable'){
  const bars=normalizeBars(rows);
  const period=chartPeriods[state.chartPeriod]||chartPeriods['1y'];
  const rect=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
  canvas.width=Math.max(1,rect.width*dpr);canvas.height=Math.max(1,rect.height*dpr);
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const w=rect.width,h=rect.height;ctx.clearRect(0,0,w,h);
  ctx.font=(large?'12px':'10px')+' system-ui,-apple-system,Segoe UI,Roboto,sans-serif';
  if(bars.length<2){
    ctx.fillStyle='#8ea0b7';ctx.textAlign='left';ctx.textBaseline='alphabetic';
    ctx.fillText(emptyMessage,12,22);return;
  }
  const top=large?32:24,bottom=large?46:38,left=large?10:8,right=large?72:60;
  const rawLo=Math.min(...bars.map(b=>b.low)),rawHi=Math.max(...bars.map(b=>b.high));
  const rawRange=Math.max(rawHi-rawLo,.0001),pad=Math.max(rawRange*.035,Math.abs(rawHi)*.001);
  const lo=rawLo-pad,hi=rawHi+pad,range=Math.max(hi-lo,.0001);
  const plotW=Math.max(1,w-left-right),plotH=Math.max(1,h-top-bottom);
  const x=i=>left+i*plotW/(bars.length-1),y=v=>top+(hi-v)*plotH/range;

  ctx.lineWidth=1;ctx.textBaseline='middle';
  for(let i=0;i<4;i++){
    const frac=i/3,yy=top+frac*plotH,value=hi-frac*range;
    ctx.strokeStyle='#1c2d43';ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();
    ctx.fillStyle='#8ea0b7';ctx.textAlign='left';ctx.fillText(priceLabel(value),w-right+6,yy);
  }

  const closes=bars.map(b=>b.close),e10=avg(closes,10,true),e20=avg(closes,20,true),s50=avg(closes,50,false);
  const candleW=Math.max(1,Math.min(5,plotW/bars.length*.7));
  bars.forEach((b,i)=>{
    const xx=x(i),up=b.close>=b.open;ctx.strokeStyle=up?'#35d78b':'#ff6d7a';ctx.fillStyle=ctx.strokeStyle;
    ctx.beginPath();ctx.moveTo(xx,y(b.high));ctx.lineTo(xx,y(b.low));ctx.stroke();
    const yy=Math.min(y(b.open),y(b.close)),bh=Math.max(1,Math.abs(y(b.open)-y(b.close)));
    ctx.fillRect(xx-candleW/2,yy,candleW,bh);
  });
  [[e10,'#e9bd62'],[e20,'#56a8ff'],[s50,'#a67cff']].forEach(([series,color])=>{
    ctx.strokeStyle=color;ctx.lineWidth=1.3;ctx.beginPath();let started=false;
    series.forEach((v,i)=>{if(v==null)return;const xx=x(i),yy=y(v);if(!started){ctx.moveTo(xx,yy);started=true}else ctx.lineTo(xx,yy)});
    if(started)ctx.stroke();
  });

  const tickIndexes=[0,Math.floor((bars.length-1)/2),bars.length-1];
  const aligns=['left','center','right'];
  ctx.fillStyle='#8ea0b7';ctx.textBaseline='top';
  tickIndexes.forEach((index,i)=>{
    ctx.textAlign=aligns[i];
    ctx.fillText(barDateLabel(bars[index].time),x(index),h-bottom+8);
  });
  ctx.textBaseline='alphabetic';
  ctx.fillStyle='#8ea0b7';
  ctx.textAlign='left';
  ctx.fillText(period.label,left,14);
  if(large){
    ctx.textAlign='center';
    ctx.fillText(period.weekly?'EMA10W / EMA20W / SMA50W':'EMA10 / EMA20 / SMA50',left+plotW/2,14);
    ctx.textAlign='right';
    ctx.fillText(bars.length+(period.weekly?' weeks':' sessions'),w-right,14);
  }
}
function badges(item){
  const sources=(item.sources||[]).map(s=>'<span class="badge '+(s==='kell-daily'||s==='kell-gap'?'kell':'')+'">'+esc(label(s))+'</span>').join('');
  const score=Number(item.kell_score);
  const kell=Number.isFinite(score)?'<span class="badge kell-score">Kell '+fmt(score,0)+'</span>':'';
  return sources+kell;
}
function hasKell(item,field){
  return item?.[field]===true
    ||(item?.kellScreens||item?.kell_screens||[]).includes(field)
    ||(item?.kellSetups||item?.kell_setups||[]).includes(field)
    ||(item?.kellContext||[]).includes(field);
}
function namedHits(item,keys,labels){
  return keys.filter(key=>hasKell(item,key)).map(key=>labels[key]||key.replace(/^kell_/,'').replaceAll('_',' '));
}
function kellScreensText(item){return namedHits(item,Object.keys(kellScreenLabels),kellScreenLabels).join(' · ')||'—'}
function kellSetupsText(item){return namedHits(item,Object.keys(kellSetupLabels),kellSetupLabels).join(' · ')||'—'}
function kellContextText(item){return namedHits(item,Object.keys(kellContextLabels),kellContextLabels).join(' · ')||'—'}
function kellBreakdownText(item){
  const b=item.score_breakdown||{},parts=b.components||{},ready=parts.readiness||{};
  const lines=[
    'Focus '+fmt(item.kell_score,1)+' · raw '+fmt(b.raw_composite,1)+' · stage cap '+fmt(b.stage_cap??item.kell_stage_cap,0),
    'Quality '+fmt(item.kell_quality_score,1)+' · Readiness '+fmt(item.kell_readiness_score,1)+' · Context '+fmt(item.kell_context_score,1),
    'Evidence '+fmt(item.kell_evidence_coverage,0)+'%'+(Number.isFinite(Number(item.kell_structural_risk_score))?' · Structural risk '+fmt(item.kell_structural_risk_score,0):''),
  ];
  if(Number.isFinite(Number(ready.structural_risk_atr)))lines.push('Natural invalidation distance '+fmt(ready.structural_risk_atr,2)+' ATR');
  if(Number.isFinite(Number(b.legacy_v4_score)))lines.push('Legacy v4 additive score '+fmt(b.legacy_v4_score,1)+' (diagnostic only)');
  if(Number(b.ttftl_penalty)>0)lines.push('TTFTL penalty -'+fmt(b.ttftl_penalty,0));
  if((b.warnings||[]).length)lines.push('Warnings: '+b.warnings.join(', '));
  return lines.join('\n');
}
function slopeIcon(value){return value==='upward'?'↑':value==='downward'?'↓':value==='flat'?'→':'—'}
function ruleAnalysis(item){
  const m=item.metrics||{},rvol=Number(m.rvol),rsi=Number(m.rsi14),gap=Math.abs(Number(m.emaGapPct));
  const readiness=Number(item.kell_readiness_score),stage=primaryStage(item);
  if(Number.isFinite(readiness)&&item.kell_stage){
    if(stage==='wedge_drop')return{status:'REVIEW',state:'KELL WEDGE DROP',preferredTrade:'Nema novog long entryja; čekati repair i novi Wedge Pop/reclaim.',summary:'Kasna/risk-off faza Kell ciklusa. Stage cap sprječava da jaki discovery signali prikriju lošu trenutnu lokaciju.'};
    if(stage==='exhaustion_extension')return{status:'WATCH',state:'KELL EXHAUSTION',preferredTrade:'Ne chaseati extension; čekati re-base, EMA reset ili novi low-risk setup.',summary:'Leader može ostati kvalitetan, ali trenutni entry readiness je namjerno ograničen late-cycle capom.'};
    if(readiness>=80)return{status:'ACTION',state:'KELL READY · '+stageName(stage),preferredTrade:'Koristi prirodnu invalidaciju setupa; ne ulaziti ako se strukturni risk previše proširi.',summary:'Kell v5 readiness je visok: stage, setup i strukturni risk su usklađeni.'};
    if(readiness>=60)return{status:'WATCH',state:'KELL WATCH · '+stageName(stage),preferredTrade:'Čekati jasniji trigger ili bolji odnos entryja prema prirodnoj invalidaciji.',summary:'Kvaliteta može biti dobra, ali entry još nije u gornjoj readiness zoni.'};
    return{status:'REVIEW',state:'KELL EARLY/LATE · '+stageName(stage),preferredTrade:'Bez forsiranog ulaza; čekati povoljniji dio Cycle of Price Action.',summary:'Discovery kvaliteta i trenutna actionability namjerno su odvojene.'};
  }
  const hh=m.higherHigh===true,hl=m.higherLow===true,trend=m.slope50==='upward'&&m.slope30w==='upward';
  const kell=item.sources.includes('kell-daily')||hasKell(item,'kell_rvol_3x');
  const kellGap=item.sources.includes('kell-gap')||hasKell(item,'kell_gapper');
  if(kellGap){
    const g=item.kellGap||{},held=Number(g.gapHeldPct),gap=Number(g.gapPct??item.kell_metrics?.gap_pct),strongHold=Number.isFinite(held)&&held>=60;
    return{
      status:strongHold?'ACTION':'WATCH',
      state:strongHold?'KELL GAP HOLD':'KELL GAP WATCH',
      preferredTrade:strongHold?'Ne chaseati opening gap; tražiti intraday/next-day tightness, first pullback ili reclaim uz stop ispod gap-day lowa.':'Gap je oslabio; čekati da obrani gap, 10/20 EMA ili napravi novi HL prije ulaza.',
      summary:'Kell Gappers kandidat: '+(Number.isFinite(gap)?gap.toFixed(1)+'% gap. ':'')+(strongHold?'Veći dio gapa je zadržan do closea.':'Gap nije dovoljno uvjerljivo zadržan do closea.')
    };
  }
  if(kell){
    const extended=Number.isFinite(rsi)&&rsi>=75;
    return{
      status:extended?'WATCH':'ACTION',
      state:'KELL FIRST THRUST',
      preferredTrade:extended?'Ne chaseati thrust; čekati prvi kontrolirani pullback ili novi HL.':'Prvi pullback/reclaim nakon 3x+ RVOL, uz strukturni stop ispod pullback lowa.',
      summary:'Abnormalna participacija je potvrđena. Prioritet nije breakout chase nego procjena koliko je move već extended i može li prvi pullback zadržati 10/20 EMA.'
    };
  }
  if(hh&&hl&&trend){
    return{status:'ACTION',state:'TREND TRANSITION',preferredTrade:'Pullback prema 10/20 EMA ili prethodnom HL-u; breakout koristiti kao potvrdu/add-on.',summary:'Cijena već pokazuje HH+HL uz rastuće 50D i 30W. Fokus je na definiranom pullback entryju, ne na lovljenju extensiona.'};
  }
  if(m.baseLike===true&&Number.isFinite(rsi)&&rsi<=42){
    return{status:'WATCH',state:'SPRING WATCH',preferredTrade:'Failed breakdown / undercut-and-reclaim pa potvrda novog HL-a.',summary:'Dionica je u relativno uskoj bazi i momentum je prigušen. Traži promjenu karaktera na supportu, ne breakout iz vrha rangea.'};
  }
  if(m.baseLike===true&&Number.isFinite(gap)&&gap<=1.5){
    return{status:'WATCH',state:'BASE / RECLAIM',preferredTrade:'Reclaim 10/20 EMA + novi HL; size povećavati tek kad se pojavi HH.',summary:'MA struktura je komprimirana unutar baze. Potrebna je potvrda da se supply apsorbira i da cijena prestaje raditi LL/LH.'};
  }
  return{status:'REVIEW',state:'DEVELOPING',preferredTrade:'Bez forsiranog ulaza; čekati spring, HL/reclaim ili trend pullback s jasnom invalidacijom.',summary:'Setup još nema dovoljno kombinirane potvrde za definirani entry.'};
}
function analysisFor(item){return Object.assign({},ruleAnalysis(item),item.analysis||{})}
function activeFilters(){return Array.isArray(state.filters)?state.filters:[]}
function activeFilterSummary(){return activeFilters().map(filter=>kellFilterLabels[filter]||filter).join(' + ')}
function isKellView(filters=activeFilters()){
  const list=Array.isArray(filters)?filters:[filters];
  return list.some(filter=>kellFilters.has(filter));
}
function universeMatch(item,universe=state.universe){
  if(universe==='all')return true;
  if(universe==='watchlist')return isWatched(item?.ticker);
  const sources=item?.unifiedSources||item?.sources||[];
  return sources.includes(universe);
}
function matchesFilter(item,filter){
  if(!filter||filter==='none')return true;
  if(filter==='action')return String(analysisFor(item).status||'').toUpperCase()==='ACTION';
  if(filter==='multi')return (item?.unifiedSources||item?.sources||[]).length>1;
  if(filter==='kell-any')return Boolean(
    (item?.kellScreens||item?.kell_screens||[]).length
    ||(item?.kellSetups||item?.kell_setups||[]).length
    ||(item?.kellContext||[]).length
  );
  if(filter==='kell-score')return Number(item.kell_score)>=60;
  if(filter==='kell-ready')return Number(item.kell_readiness_score)>=80;
  if(filter==='kell-changed')return item?.kellChange?.changed===true;
  if(filter.startsWith('stage:'))return primaryStage(item)===filter.slice(6);
  if(kellFilters.has(filter))return hasKell(item,filter);
  return true;
}
function matchesFilters(item,filters=activeFilters()){
  return !filters.length||filters.every(filter=>matchesFilter(item,filter));
}
function sourceItems(filters=activeFilters()){
  if(state.universe==='watchlist')return watchlistItems();
  return isKellView(filters)
    ?(state.kellData?.kellCandidates||state.data?.kellCandidates||[])
    :(state.data?.candidates||[]);
}
function updateFilterBar(){
  const filters=activeFilters();
  document.querySelectorAll('#filters button[data-filter]').forEach(button=>{
    const filter=button.dataset.filter;
    const active=filter==='none'?filters.length===0:filters.includes(filter);
    button.classList.toggle('active',active);
    button.setAttribute('aria-pressed',active?'true':'false');
  });
  const bar=$('#activeFilterBar');
  if(!bar)return;
  if(!filters.length){
    bar.hidden=true;
    bar.innerHTML='';
    return;
  }
  bar.hidden=false;
  bar.innerHTML='<span class="active-filter-label">Active '+filters.length+'</span>'+
    filters.map(filter=>'<button type="button" class="active-filter-chip" data-remove-filter="'+esc(filter)+'">'+esc(kellFilterLabels[filter]||filter)+' <span aria-hidden="true">×</span></button>').join('')+
    '<button type="button" class="clear-active-filters" data-clear-filters>Clear all</button>';
}
function updateQuickViews(){
  document.querySelectorAll('#quickViews [data-quick-view]').forEach(button=>{
    button.classList.toggle('active',button.dataset.quickView===state.quickView);
  });
}
function updateMobileFilterToggle(){
  const button=$('#mobileFiltersToggle');
  if(!button)return;
  const count=activeFilters().length;
  button.textContent=count?'Filters ('+count+')':'Filters';
  button.setAttribute('aria-label',count?count+' active filters':'Open filters');
}
function setMobileFiltersOpen(open,restoreFocus=false){
  const panel=$('#filters'),button=$('#mobileFiltersToggle'),backdrop=$('#mobileFilterBackdrop');
  if(!panel||!button||!backdrop)return;
  panel.classList.toggle('mobile-open',open);
  button.setAttribute('aria-expanded',String(open));
  backdrop.hidden=!open;
  document.body.classList.toggle('mobile-filters-open',open);
  if(!open&&restoreFocus)button.focus();
}
function updateFilterCounts(){
  const kellItems=state.kellData?.kellCandidates||state.data?.kellCandidates||[];
  const reviewItems=state.data?.candidates||[];
  const active=activeFilters();
  document.querySelectorAll('#filters button[data-filter]').forEach(button=>{
    const filter=button.dataset.filter;
    if(!button.dataset.baseLabel)button.dataset.baseLabel=button.textContent.replace(/ \(\d+\)$/,'');
    if(filter==='none'){
      button.textContent=button.dataset.baseLabel;
      return;
    }
    const proposed=active.includes(filter)?active:[...active,filter];
    const source=isKellView(proposed)?kellItems:reviewItems;
    const count=source.filter(item=>universeMatch(item)&&matchesFilters(item,proposed)).length;
    button.textContent=button.dataset.baseLabel+' ('+count+')';
  });
}
async function ensureKellData(){
  if(state.kellData)return state.kellData;
  if(state.kellLoading)return state.kellLoading;
  const reviewSource=state.data?.source||{};
  state.kellLoading=KellDatasets.load(fetch,location.search,reviewSource)
    .then(data=>{
      const normal=new Map((state.data?.candidates||[]).map(item=>[item.ticker,item]));
      for(const item of data.kellCandidates||[]){
        const base=normal.get(item.ticker);
        if(base?.chartBars?.length)item.chartBars=base.chartBars;
      }
      state.kellData=data;
      state.kellChartShards.clear();
      state.kellChartLoading.clear();
      state.kellLoading=null;
      return data;
    })
    .catch(err=>{state.kellLoading=null;throw err});
  return state.kellLoading;
}
async function ensureKellChanges(){
  await ensureKellData();
  if(state.kellChangesPreviousDate)return state.kellChangesPreviousDate;
  if(state.kellChangesLoading)return state.kellChangesLoading;
  const currentDate=state.kellData?.source?.sessionDate||state.data?.source?.sessionDate;
  state.kellChangesLoading=KellChanges.loadHistory(fetch,currentDate,14,5)
    .then(history=>{
      KellChanges.decorate(state.kellData?.kellCandidates||[],history);
      state.kellChangesHistoryDates=history.map(payload=>payload?.source?.sessionDate).filter(Boolean);
      state.kellChangesPreviousDate=state.kellChangesHistoryDates[state.kellChangesHistoryDates.length-1]||null;
      state.kellChangesLoading=null;
      return state.kellChangesPreviousDate;
    })
    .catch(err=>{state.kellChangesLoading=null;throw err});
  return state.kellChangesLoading;
}
function changeStrip(item){
  const change=item?.kellChange;
  if(!change?.changed)return '';
  const icon=change.direction==='risk'?'⚠':'↗';
  const headline=change.headline||'CYCLE CHANGED';
  const stageMove=change.previousStage&&change.currentStage&&change.previousStage!==change.currentStage
    ?'<span>Stage: '+esc(stageName(change.previousStage))+' → '+esc(stageName(change.currentStage))+'</span>'
    :'';
  const sequence=change.sequenceText?'<span>Cycle: '+esc(change.sequenceText)+'</span>':'';
  const risk=change.riskLabel?'<span>'+esc(change.riskLabel)+'</span>':'';
  const deltas=[
    Number.isFinite(Number(change.readinessDelta))?'R '+(change.readinessDelta>=0?'+':'')+fmt(change.readinessDelta,1):'',
    Number.isFinite(Number(change.scoreDelta))?'Kell '+(change.scoreDelta>=0?'+':'')+fmt(change.scoreDelta,1):''
  ].filter(Boolean).join(' · ');
  return '<div class="change-strip"><strong>'+icon+' '+esc(headline)+'</strong><span>'+esc((change.reasons||[]).join(' · '))+'</span>'+stageMove+sequence+risk+(deltas?'<span class="change-delta">'+esc(deltas)+'</span>':'')+'</div>';
}
async function ensureChartData(item){
  if(rowsForPeriod(item).length>=2)return rowsForPeriod(item);
  const data=state.kellData;
  const meta=data?.kellChartData;
  const shard=Number(item?.chartShard);
  if(!meta||!Number.isInteger(shard)||shard<0)return rowsForPeriod(item);
  const key=String(shard);
  let payload=state.kellChartShards.get(key);
  if(!payload){
    let loading=state.kellChartLoading.get(key);
    if(!loading){
      const base=String(meta.basePath||'data/kell-charts').replace(/\/$/,'');
      const path=base+'/shard-'+String(shard).padStart(3,'0')+'.json';
      loading=fetch(path,{cache:'no-store'})
        .then(response=>{
          if(!response.ok)throw new Error('chart shard HTTP '+response.status);
          return response.json();
        })
        .then(result=>{
          if(!['kell-chart-shard-v1','kell-chart-shard-v2'].includes(result?.schemaVersion))throw new Error('invalid chart shard schema');
          if(result?.source?.sessionDate!==data?.source?.sessionDate)throw new Error('chart shard date mismatch');
          if(result?.source?.runId!==data?.source?.runId)throw new Error('chart shard run mismatch');
          if(data?.source?.unifiedManifestSha256&&result?.source?.unifiedManifestSha256!==data.source.unifiedManifestSha256){
            throw new Error('chart shard Unified activation mismatch');
          }
          state.kellChartShards.set(key,result);
          state.kellChartLoading.delete(key);
          return result;
        })
        .catch(err=>{state.kellChartLoading.delete(key);throw err});
      state.kellChartLoading.set(key,loading);
    }
    payload=await loading;
  }
  const chart=payload?.charts?.[item.ticker];
  if(Array.isArray(chart)){
    if(chart.length>=2)item.chartBars=chart;
  }else if(chart){
    if(chart.daily?.length>=2)item.chartBars=chart.daily;
    if(chart.weekly?.length>=2)item.weeklyChartBars=chart.weekly;
  }
  return rowsForPeriod(item);
}
function visible(item){
  if(state.query&&!item.ticker.includes(state.query))return false;
  if(!universeMatch(item))return false;
  return matchesFilters(item);
}
function card(item){
  const m=item.metrics||{},a=analysisFor(item),missing=item.watchlistMissing===true;
  const status=missing?'SAVED':String(a.status||'REVIEW').toUpperCase();
  const gap=item.kellGap||{gapPct:item.kell_metrics?.gap_pct};
  const stage=stageName(primaryStage(item));
  const setups=kellSetupsText(item);
  const watched=isWatched(item.ticker);
  const sources=item.sources||[];
  return '<article class="card'+(missing?' watchlist-stale':'')+'" tabindex="0" data-ticker="'+esc(item.ticker)+'">'+
    '<div class="card-head"><div class="ticker-wrap"><button class="watch-star'+(watched?' active':'')+'" type="button" data-watch-ticker="'+esc(item.ticker)+'" aria-label="'+(watched?'Makni ':'Dodaj ')+esc(item.ticker)+(watched?' iz Watchliste':' na Watchlistu')+'" aria-pressed="'+(watched?'true':'false')+'">'+(watched?'★':'☆')+'</button><div class="ticker">'+esc(item.ticker)+'</div></div><div class="badges">'+badges(item)+'</div></div>'+changeStrip(item)+
    (missing?'<div class="watchlist-missing">Nije u današnjem Unified scanu · ostaje spremljen dok ga ručno ne ukloniš</div>':item.watchlistUnifiedOnly?'<div class="watchlist-current">U današnjem Unified scanu · trenutačno nema aktivni Review/Kell hit</div>':'')+
    '<div class="metrics"><span>Px <b>'+fmt(m.price)+'</b></span><span>RVOL <b>'+fmt(m.rvol)+'x</b></span><span>RSI <b>'+fmt(m.rsi14,1)+'</b></span><span>EMA gap <b>'+pct(m.emaGapPct)+'</b></span><span>Kell <b>'+fmt(item.kell_score,0)+'</b></span>'+(sources.includes('kell-gap')?'<span>Gap <b>'+pct(gap.gapPct)+'</b></span>':'')+'</div>'+
    '<div class="metrics kell-dimensions"><span>Stage <b>'+esc(stage)+'</b></span><span>Q / R / C <b>'+fmt(item.kell_quality_score,0)+' / '+fmt(item.kell_readiness_score,0)+' / '+fmt(item.kell_context_score,0)+'</b></span><span>Evidence <b>'+fmt(item.kell_evidence_coverage,0)+'%</b></span></div>'+
    '<div class="metrics kell-dimensions"><span>Setup <b>'+esc(setups)+'</b></span></div>'+
    '<canvas aria-label="'+esc(item.ticker)+' chart" title="Tap/click za analizu"></canvas>'+
    '<div class="metrics structure"><span>50D <b>'+slopeIcon(m.slope50)+'</b></span><span>30W <b>'+slopeIcon(m.slope30w)+'</b></span><span>Swing <b>'+esc(m.swingState||'—')+'</b></span><span>Base <b>'+(m.baseLike===true?'✓':m.baseLike===false?'—':'?')+'</b></span></div>'+
    '<div class="analysis-strip"><span>'+esc(a.state||m.setup||'—')+'</span><strong class="'+(status==='ACTION'?'action':status==='WATCH'?'watch':'')+'">'+esc(status)+'</strong></div>'+
    '</article>';
}
let observer;
function render(){
  if(!state.data)return;
  updateWatchlistButton();
  updateFilterBar();
  updateQuickViews();
  updateMobileFilterToggle();
  updateFilterCounts();
  const items=sourceItems().filter(visible);
  const sortMode=state.sort==='default'&&isKellView()?'kell-score':state.sort;
  const sortValue=(item,mode)=>{
    if(mode==='kell-score')return Number(item.kell_score);
    if(mode==='change')return Number(item.kellChange?.priority);
    if(mode==='readiness')return Number(item.kell_readiness_score);
    if(mode==='quality')return Number(item.kell_quality_score);
    if(mode==='evidence')return Number(item.kell_evidence_coverage);
    if(mode==='rvol')return Number(item.metrics?.rvol);
    return NaN;
  };
  if(sortMode!=='default')items.sort((a,b)=>{
    const av=sortValue(a,sortMode),bv=sortValue(b,sortMode);
    const an=Number.isFinite(av)?av:-Infinity,bn=Number.isFinite(bv)?bv:-Infinity;
    return bn-an||a.ticker.localeCompare(b.ticker);
  });
  state.renderedItems=items.slice();
  $('#grid').innerHTML=items.map(card).join('');
  const universeName=universeLabels[state.universe]||state.universe;
  const modeCounts=state.kellData?.source?.modeUniverseCounts||state.data?.source?.modeUniverseCounts||{};
  const unifiedCount=state.kellData?.kellScoring?.unifiedCandidateCount??state.data?.kellScoring?.unifiedCandidateCount;
  const universeSize=state.universe==='watchlist'?state.watchlist.length:(state.universe==='all'?unifiedCount:modeCounts[state.universe]);
  const universeText=universeName+(Number.isFinite(Number(universeSize))?' ('+Number(universeSize)+' candidates)':'');
  const filterSummary=activeFilterSummary();
  if(state.quickView==='changed'){
    const changeSummary=KellChanges.summary(items);
    const currentDate=state.kellData?.source?.sessionDate||state.data?.source?.sessionDate||'—';
    const depth=state.kellChangesHistoryDates.length;
    $('#status').textContent=items.length+' cycle changes · '+(state.kellChangesPreviousDate||'prior')+' → '+currentDate+' · '+changeSummary.actionableSetups+' actionable setups · '+changeSummary.stageChanges+' stage changes · '+changeSummary.discoveryChanges+' discovery changes · '+changeSummary.structureFailures+' failures · history '+depth+' sessions';
  }else if(state.universe==='watchlist'){
    const missing=items.filter(item=>item.watchlistMissing).length;
    const unifiedOnly=items.filter(item=>item.watchlistUnifiedOnly).length;
    $('#status').textContent=items.length+' prikazano · '+state.watchlist.length+' spremljeno na Watchlisti'+(unifiedOnly?' · '+unifiedOnly+' još je u Unified universeu bez aktivnog hita':'')+(missing?' · '+missing+' više nije u današnjem Unified scanu':'')+(filterSummary?' · '+filterSummary:'');
  }else if(filterSummary){
    $('#status').textContent=items.length+' pogodaka · '+universeText+' → '+filterSummary;
  }else{
    $('#status').textContent=items.length+' review kandidata · Universe '+universeText+' · odaberi više Screen / Stage / Setup filtera za AND presjek';
  }
  observer?.disconnect();
  const lookup=new Map(items.map(item=>[item.ticker,item]));
  observer=new IntersectionObserver(entries=>{
    for(const entry of entries){
      if(!entry.isIntersecting)continue;
      const canvas=entry.target,cardEl=canvas.closest('.card'),item=lookup.get(cardEl.dataset.ticker);
      observer.unobserve(canvas);
      const ready=rowsForPeriod(item);
      if(ready.length>=2){draw(canvas,ready);continue}
      draw(canvas,[],false,'Loading chart…');
      ensureChartData(item)
        .then(rows=>{if(canvas.isConnected)draw(canvas,rows,false,rows.length>=2?'':'Chart data unavailable')})
        .catch(err=>{if(canvas.isConnected){canvas.title='Chart load error: '+err.message;draw(canvas,[],false,'Chart load failed')}})
    }
  },{rootMargin:'240px'});
  document.querySelectorAll('.card').forEach(cardEl=>{
    const item=lookup.get(cardEl.dataset.ticker),canvas=cardEl.querySelector('canvas');
    observer.observe(canvas);
    const open=()=>item&&show(item);
    const star=cardEl.querySelector('[data-watch-ticker]');
    star?.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();toggleWatchlist(star.dataset.watchTicker)});
    canvas.addEventListener('click',e=>{e.stopPropagation();open()});
    cardEl.addEventListener('click',e=>{if(e.target.closest('[data-watch-ticker]'))return;open()});
    cardEl.addEventListener('keydown',e=>{if(e.target.closest('[data-watch-ticker]'))return;if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}});
  });
}
function fact(name,value){return '<div class="fact"><span>'+esc(name)+'</span>'+esc(value??'—')+'</div>'}
function updateDetailNav(item){
  const items=state.renderedItems||[];
  const index=items.findIndex(candidate=>candidate.ticker===item?.ticker);
  state.detailTicker=item?.ticker||null;
  const pos=$('#detailPosition'),prev=$('#prevDetail'),next=$('#nextDetail');
  if(pos)pos.textContent=index>=0?(index+1)+' / '+items.length:'—';
  if(prev)prev.disabled=index<=0;
  if(next)next.disabled=index<0||index>=items.length-1;
}
function navigateDetail(delta){
  const items=state.renderedItems||[];
  const index=items.findIndex(item=>item.ticker===state.detailTicker);
  const nextIndex=index+delta;
  if(index<0||nextIndex<0||nextIndex>=items.length)return;
  show(items[nextIndex]);
}
function show(item){
  const m=item.metrics||{},a=analysisFor(item),ai=item.analysis||{},g=item.kellGap||{gapPct:item.kell_metrics?.gap_pct};
  const fundamentals=ai.fundamentalsQoQ||ai.fundamentals||'Work analiza još nije upisana za ovaj snapshot.';
  updateDetailNav(item);
  $('#detailBody').innerHTML=
    '<div class="detail-head"><h2>'+esc(item.ticker)+'</h2><div class="badges">'+badges(item)+'</div></div>'+
    '<canvas class="detail-chart"></canvas>'+
    '<div class="detail-grid">'+
      fact('Review state',a.state)+fact('Review status',String(a.status||'REVIEW').toUpperCase())+
      fact('Kell Focus',fmt(item.kell_score,1))+fact('Kell stage',stageName(primaryStage(item)))+
      fact('Quality',fmt(item.kell_quality_score,1))+fact('Readiness / Actionability',fmt(item.kell_readiness_score,1))+
      fact('Context score',fmt(item.kell_context_score,1))+fact('Evidence coverage',fmt(item.kell_evidence_coverage,0)+'%')+
      fact('Structural risk',Number.isFinite(Number(item.kell_structural_risk_score))?fmt(item.kell_structural_risk_score,0):'—')+fact('Stage cap',fmt(item.kell_stage_cap,0))+
      fact('Discovery screens',kellScreensText(item))+fact('Setups',kellSetupsText(item))+
      fact('Context flags',kellContextText(item))+fact('Stage confidence',item?.kell_stage?.confidence!=null?fmt(Number(item.kell_stage.confidence)*100,0)+'%':'—')+
      fact('RVOL',fmt(m.rvol)+'x')+fact('RSI14',fmt(m.rsi14,1))+
      fact('EMA10 / EMA20',fmt(m.ema10)+' / '+fmt(m.ema20))+fact('EMA gap',pct(m.emaGapPct))+
      fact('50D slope',m.slope50||'—')+fact('30W slope',m.slope30w||'—')+
      fact('Swing',m.swingState||'—')+fact('20D / 40D range',pct(m.range20Pct)+' / '+pct(m.range40Pct))+
      fact('Close location',pct(m.closeLocationPct))+fact('Actionability',m.actionability||'—')+
      (item.sources.includes('kell-gap')?fact('Gap / held',pct(g.gapPct)+' / '+pct(g.gapHeldPct))+fact('Avg Vol 20D',Number.isFinite(Number(g.avgVolume20d))?Intl.NumberFormat('en',{notation:'compact'}).format(g.avgVolume20d):'—'):'')+
    '</div>'+
    '<div class="analysis-text"><b>Sažetak</b>\n'+esc(a.summary||'—')+
    '\n\n<b>Preferred trade</b>\n'+esc(a.preferredTrade||'—')+
    (item.kell?.signals?.length?'\n\n<b>Kell confluence</b>\n'+esc(item.kell.signals.join(' · ')):'')+
    '\n\n<b>Kell score breakdown</b>\n'+esc(kellBreakdownText(item))+
    '\n\n<b>Fundamenti QoQ</b>\n'+esc(fundamentals)+
    (ai.riskNote?'\n\n<b>Risk note</b>\n'+esc(ai.riskNote):'')+
    '</div>';
  if(!$('#detail').open)$('#detail').showModal();
  requestAnimationFrame(()=>{
    const canvas=$('#detailBody canvas');
    const ready=rowsForPeriod(item);
    if(ready.length>=2){draw(canvas,ready,true);return}
    draw(canvas,[],true,'Loading chart…');
    ensureChartData(item)
      .then(rows=>draw(canvas,rows,true,rows.length>=2?'':'Chart data unavailable'))
      .catch(err=>{canvas.title='Chart load error: '+err.message;draw(canvas,[],true,'Chart load failed')});
  });
}
$('#closeDetail').addEventListener('click',()=>$('#detail').close());
$('#prevDetail')?.addEventListener('click',()=>navigateDetail(-1));
$('#nextDetail')?.addEventListener('click',()=>navigateDetail(1));
$('#detail').addEventListener('click',e=>{if(e.target===$('#detail'))$('#detail').close()});
$('#mobileFiltersToggle')?.addEventListener('click',()=>setMobileFiltersOpen(!$('#filters')?.classList.contains('mobile-open')));
$('#mobileFiltersClose')?.addEventListener('click',()=>setMobileFiltersOpen(false,true));
$('#mobileFilterBackdrop')?.addEventListener('click',()=>setMobileFiltersOpen(false,true));
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&$('#filters')?.classList.contains('mobile-open')){
    setMobileFiltersOpen(false,true);
    return;
  }

  if(!$('#detail')?.open)return;
  if(e.key==='ArrowLeft'){e.preventDefault();navigateDetail(-1)}
  if(e.key==='ArrowRight'){e.preventDefault();navigateDetail(1)}
});
$('#search').addEventListener('input',e=>{state.query=e.target.value.trim().toUpperCase();render()});
$('#sort')?.addEventListener('change',e=>{state.sort=e.target.value;render()});
$('#chartPeriod')?.addEventListener('change',e=>{
  state.chartPeriod=e.target.value in chartPeriods?e.target.value:'1y';
  if($('#detail')?.open)$('#detail').close();
  render();
});
$('#filters').addEventListener('click',async e=>{
  const universeButton=e.target.closest('button[data-universe]');
  const filterButton=e.target.closest('button[data-filter]');
  if(!universeButton&&!filterButton)return;

  if(universeButton){
    state.quickView=null;
    const nextUniverse=universeButton.dataset.universe;
    if(nextUniverse==='watchlist'&&state.universe!=='watchlist')state.filters=[];
    state.universe=nextUniverse;
    document.querySelectorAll('#filters button[data-universe]').forEach(x=>x.classList.toggle('active',x===universeButton));
  }
  if(filterButton){
    state.quickView=null;
    const filter=filterButton.dataset.filter;
    if(filter==='none')state.filters=[];
    else if(activeFilters().includes(filter))state.filters=activeFilters().filter(value=>value!==filter);
    else state.filters=[...activeFilters(),filter];
  }

  if(isKellView()&&!state.kellData){
    $('#status').textContent='Učitavam Kell kandidate za odabrani universe…';
    try{await ensureKellData()}catch(err){$('#status').textContent='Kell podaci nisu dostupni: '+err.message;return}
  }
  render();
});
$('#quickViews')?.addEventListener('click',async e=>{
  const button=e.target.closest('[data-quick-view]');
  if(!button)return;
  const name=button.dataset.quickView;
  const config=quickViews[name];
  if(!config)return;
  state.quickView=name==='reset'?null:name;
  state.filters=[...config.filters];
  state.sort=config.sort;
  const sort=$('#sort');
  if(sort)sort.value=state.sort;
  if(isKellView(state.filters)&&!state.kellData){
    $('#status').textContent='Učitavam Kell kandidate za Quick View…';
    try{await ensureKellData()}catch(err){$('#status').textContent='Kell podaci nisu dostupni: '+err.message;return}
  }
  if(name==='changed'){
    $('#status').textContent='Učitavam Kell povijest i računam promjene u Cycle of Price Action…';
    try{await ensureKellChanges()}catch(err){$('#status').textContent='What Changed in the Cycle nije dostupan: '+err.message;return}
  }
  render();
});
$('#activeFilterBar')?.addEventListener('click',e=>{
  const remove=e.target.closest('[data-remove-filter]');
  const clear=e.target.closest('[data-clear-filters]');
  if(!remove&&!clear)return;
  state.quickView=null;
  if(clear)state.filters=[];
  else state.filters=activeFilters().filter(filter=>filter!==remove.dataset.removeFilter);
  render();
});
window.addEventListener('storage',event=>{
  if(event.key!==WatchlistStore.STORAGE_KEY)return;
  state.watchlist=WatchlistStore.load(window.localStorage);
  if(state.data)render();
});
const queryParams=new URLSearchParams(location.search);
const archived=queryParams.has('snapshot')||queryParams.has('date');
ReviewSnapshots.load(fetch,location.search)
  .then(data=>{state.data=data;$('#runMeta').textContent=(data.source?.sessionDate||'—')+' · Unified '+(data.source?.runId||'—')+' · '+(archived?'archive':'latest')+' · read-only';render();if(!archived)ensureKellData().then(()=>render()).catch(()=>{})})
  .catch(err=>{$('#status').textContent='Snapshot nije dostupan: '+err.message});
