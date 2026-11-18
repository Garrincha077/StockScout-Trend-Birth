const requestedMode=new URLSearchParams(location.search).get('mode');
const defaultMode=requestedMode==='legacy'||requestedMode==='weekly-v2'?requestedMode:(window.StockScoutMode?.defaultMode||'weekly-v2');
const initialReviewRoute=ReviewNavigation.read(location.search);
const state={data:null,kellData:null,kellLoading:null,kellChangesLoading:null,kellChangesPreviousDate:null,kellChartShards:new Map(),kellChartLoading:new Map(),qualityHistory:null,qualityHistoryError:'',intelligence:null,intelligenceError:'',intelligenceMonths:new Map(),tickerDrill:null,tickerDrillLimit:40,journeyTicker:'',primaryView:defaultMode==='legacy'?'research':'weekly',universe:'all',filters:[],query:'',sort:'default',chartPeriod:defaultMode==='legacy'?'1y':'base',watchlist:WatchlistStore.load(window.localStorage),renderedItems:[],detailTicker:null,quickView:null,changeHighlightsExpanded:false,ownerSync:null,ownerSession:null,ownerReconciling:false,ownerSyncError:'',ownerSyncMessage:'',ownerMagicSentTo:'',ownerMagicSending:false};
const $=s=>document.querySelector(s);
if(initialReviewRoute.view){
  state.primaryView=initialReviewRoute.view;
  state.universe=state.primaryView==='watchlist'?'watchlist':'all';
  state.chartPeriod=state.primaryView==='weekly'?'base':'1y';
}
const OWNER_AUTH_BRIDGE_URL='https://garrincha077.github.io/StockScout-Unified/trend-birth-auth-bridge.html';
function ownerAuthBridgeUrl(){
  const url=new URL(OWNER_AUTH_BRIDGE_URL);
  url.searchParams.set('return',location.origin+'/');
  return url.toString();
}
const OWNER_MAGIC_EMAIL_KEY='stockscout:trend-birth-owner-email';
function ownerAuthPhase(){return new URLSearchParams(location.search).get('tb_auth')}
function clearOwnerAuthPhase(){
  const url=new URL(location.href);
  if(!url.searchParams.has('tb_auth'))return;
  url.searchParams.delete('tb_auth');
  history.replaceState(history.state,'',url.pathname+(url.search||'')+(url.hash||''));
}
const numberOrNaN=value=>typeof value==='number'&&Number.isFinite(value)?value:NaN;
const fmt=(n,d=2)=>Number.isFinite(numberOrNaN(n))?n.toFixed(d):'—';
const pct=n=>Number.isFinite(numberOrNaN(n))?fmt(n,1)+'%':'—';
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
  'kell-changed':'Changed today',
  'tb:2':'Trend Birth 2/4',
  'tb:3':'Trend Birth 3/4 READY',
  'tb:4':'Trend Birth 4/4 TRIGGER',
  'multi':'Multi-hit',
  'action':'Action'
};
const reviewFilterLabels={
  'crash-base':'Crash Base',
  'tb-path:recovery':'Recovery',
  'tb-path:compression':'Compression',
  'tb-path:ignition':'Ignition'
};
const filterLabel=key=>reviewFilterLabels[key]||kellFilterLabels[key]||key;
const kellFilters=new Set(Object.keys(kellFilterLabels).filter(key=>!['multi','action'].includes(key)));
const quickViews={
  changed:{filters:['kell-changed'],sort:'change'},
  ready:{filters:['kell-ready'],sort:'readiness'},
  leaders:{filters:['kell_rs_leader','kell_weekly_trend_ok'],sort:'quality'},
  breakout:{filters:['kell_breakout_proximity','kell_weekly_trend_ok'],sort:'readiness'},
  tbready:{filters:['tb:3'],sort:'trend-birth'},
  tbtrigger:{filters:['tb:4'],sort:'trend-birth'},
  extended:{filters:['stage:exhaustion_extension'],sort:'kell-score'},
  reset:{filters:[],sort:'default'}
};
const stageName=value=>kellStageLabels['stage:'+(value||'unavailable')]||String(value||'unavailable').replaceAll('_',' ');
const primaryStage=item=>item?.kell_stage?.primary||item?.kell_cycle_stage||'unavailable';
const trendBirthStage=item=>Number(item?.trendBirth?.stage||0);
function runwayLabel(metrics){
  if(Number.isFinite(numberOrNaN(metrics?.runwayPct)))return pct(metrics.runwayPct)+' od pivota';
  return metrics?.resistanceStatus==='not_detected_in_window'?'Nije detektiran u '+fmt(metrics.historyWeeks,0)+'W':'Otpor nije potvrđen';
}
const tbQualityView={zoom:100,timeframe:'D',range:'all',selectedPeriod:'',scrollToEnd:true};

const tbIntelligenceArchived=new URLSearchParams(location.search).has('snapshot')||
  new URLSearchParams(location.search).has('date');
function intelligenceAligned(){
  const summary=state.intelligence;
  if(!summary||tbIntelligenceArchived)return false;
  const source=state.data?.source,radar=state.data?.trendBirthRadar;
  if(!source)return true; // tiny EOD digest is rendered before the multi-MB review snapshot.
  return source.sessionDate===summary.source.sessionDate&&
    source.runId===summary.source.runId&&radar?.scope===summary.source.scope&&
    ['0','1','2','3','4'].every(stage=>radar.stageCounts?.[stage]===summary.counts[stage]);
}
function renderTrendBirthToday(){
  const panel=$('#tbToday');
  if(!panel)return;
  const data=state.intelligence;
  if(!intelligenceAligned()){panel.hidden=true;return}
  panel.hidden=false;
  const source=data.source;
  $('#tbTodaySource').textContent=source.sessionDate+' · '+data.evaluatedCount.toLocaleString('hr-HR')+
    ' evaluirano · '+data.unavailableCount+' nedostupnih'+
    (source.previousSessionDate?' · usporedba s '+source.previousSessionDate:' · početni dan');
  const metrics=[
    {label:'Novi 4/4',value:data.baselineOnly?'—':data.newFour,kind:'up'},
    {label:'Prelazak na 3/4',value:data.baselineOnly?'—':data.toReady,kind:'up'},
    {label:'Napredovalo',value:data.baselineOnly?'—':data.upgrades,kind:'up'},
    {label:'Nazadovalo',value:data.baselineOnly?'—':data.downgrades,kind:'down'},
  ];
  $('#tbTodayMetrics').innerHTML=metrics.map(m=>'<div class="tb-intelligence-metric" data-kind="'+m.kind+
    '"><small>'+m.label+'</small><strong>'+m.value+'</strong></div>').join('');
  const stability=data.stability;
  const stableBox=$('#tbTodayStability');
  const stableCaption=$('#tbStabilitySource'),retentionBox=$('#tbStabilityRetention');
  if(stability?.quality&&stability?.four){
    const qs=stability.quality,fs=stability.four;
    stableCaption.textContent=stability.observedSessions+' arhiviranih EOD sesija · '+stability.transitionPairs+' uzastopnih parova';
    const stableMetrics=[
      {label:'3+/4 barem 3 EOD zaredom',value:qs.atLeast3,kind:'up'},
      {label:'4/4 barem 3 EOD zaredom',value:fs.atLeast3,kind:'up'},
      {label:'Izgubljen 3+/4 u zadnjem EOD-u',value:qs.latestDropouts??'—',kind:'down'},
      {label:'Izgubljen 4/4 u zadnjem EOD-u',value:fs.latestDropouts??'—',kind:'down'},
    ];
    stableBox.innerHTML=stableMetrics.map(m=>'<div class="tb-intelligence-metric" data-kind="'+m.kind+
      '"><small>'+m.label+'</small><strong>'+m.value+'</strong></div>').join('');
    const retention=r=>r?.percent==null?'—':r.percent.toFixed(1)+'% ('+r.kept+'/'+r.eligible+')';
    retentionBox.textContent='Povijesni ostanak u istoj kvalitetnoj kategoriji na sljedećem EOD-u: 3+/4 '+
      retention(qs.retention)+' · 4/4 '+retention(fs.retention)+
      '. Usporedbe uključuju samo tickere evaluirane u obje susjedne arhivirane sesije.';
  }else{
    stableCaption.textContent='Stabilnost će biti dostupna u sljedećem EOD osvježavanju.';
    stableBox.innerHTML='';
    retentionBox.textContent='';
  }
  const rows=data.topOpportunities||[];
  $('#tbTodayCandidates').innerHTML=rows.length?rows.map(item=>{
    const prior=Number.isInteger(item.previousStage)?item.previousStage+'/4 → ':'';
    const why=item.newChecks?.length?'Novo potvrđeno: '+item.newChecks.slice(0,2).join(', '):
      item.stage===4?'Trenutni 4/4 setup':'Potrebno: '+(item.missingFor4||[]).slice(0,2).join(', ');
    return '<article class="tb-opportunity-card"><div class="tb-opportunity-card-head">'+
      '<strong>'+esc(item.ticker)+'</strong><span>'+prior+item.stage+'/4</span></div>'+
      '<small>'+esc(why)+'</small>'+
      (Number.isInteger(item.qualityStreak)?'<small class="tb-streak-badge">3+/4: '+item.qualityStreak+
        ' EOD u nizu'+(item.fourStreak?' · 4/4: '+item.fourStreak:'')+'</small>':'')+
      '<div class="tb-opportunity-actions">'+
      '<button type="button" data-tb-journey="'+esc(item.ticker)+'">Povijest</button>'+
      '<a href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(item.ticker)+
      '" target="_blank" rel="noopener noreferrer">Chart ↗</a></div></article>';
  }).join(''):'<p class="tb-history-data-note">'+
    (data.baselineOnly?'Početni dan: nema usporedbe s ranijom sesijom.':'Nema novih kandidata u odabranim prijelazima.')+'</p>';
}
async function loadTrendBirthIntelligence(){
  if(tbIntelligenceArchived)return;
  const snapshotId=state.snapshotId;
  try{
    const response=await fetch('data/trend-birth-intelligence.json',{cache:'no-store'});
    if(!response.ok)throw new Error('HTTP '+response.status);
    const summary=TrendBirthIntelligence.validateSummary(await response.json());
    if(snapshotId!==state.snapshotId)return;
    state.intelligence=summary;
    renderTrendBirthToday();
  }catch(error){
    if(snapshotId!==state.snapshotId)return;
    state.intelligenceError=error.message;
    $('#tbToday').hidden=true; // Historical UI and EOD still work without new payload.
  }
}
function selectedDrillPeriod(){
  const source=state.data?.trendBirthRadar,day=state.data?.source?.sessionDate;
  if(!source||!state.qualityHistory)return null;
  const historical=TrendBirthQuality.normalizeHistory(state.qualityHistory,day,source.scope)
    .filter(point=>point.sessionDate!==day);
  const today=TrendBirthQuality.normalizeRadar(source);
  if(!today)return null;
  historical.push({sessionDate:day,...today});
  const all=TrendBirthQuality.aggregateHistory(historical,tbQualityView.timeframe);
  return TrendBirthQuality.selectHistoryRange(all,tbQualityView.range,day)
    .find(point=>point.periodKey===tbQualityView.selectedPeriod)||null;
}
async function loadTickerMonths(from,to){
  const scope=state.data?.trendBirthRadar?.scope||state.intelligence?.source.scope;
  if(!scope)throw new Error('Nedostaje validirani Trend Birth univerzum.');
  const months=TrendBirthIntelligence.monthsInPeriod(from,to);
  return TrendBirthIntelligence.loadMonths(fetch,months,state.intelligenceMonths,scope,to.slice(0,7));
}
function tickerListHTML(entries,limit){
  return entries.slice(0,limit).map(row=>
    '<div class="tb-ticker-entry"><button type="button" data-tb-journey="'+esc(row.ticker)+
    '" title="Pogledaj povijest tickera">'+esc(row.ticker)+'</button>'+
    '<small>'+(row.days>1?row.days+'d · ':'')+
    '<a href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(row.ticker)+
    '" target="_blank" rel="noopener noreferrer">Graf ↗</a></small></div>').join('');
}
async function showSelectedTickerMembers(){
  const period=selectedDrillPeriod(),result=$('#tbDrillResults');
  if(!period){result.textContent='Odabrano razdoblje više nije na grafu.';return}
  const stage=$('#tbDrillStage').value,requested=period.periodKey;
  result.textContent='Učitavam arhivirane tickere…';
  try{
    const end=period.periodEnd<state.data.source.sessionDate?period.periodEnd:state.data.source.sessionDate;
    const months=await loadTickerMonths(period.periodKey,end);
    // Fail closed when daily archives and the displayed aggregate disagree.
    const selection=TrendBirthIntelligence.membersForPeriod(months,period,stage,state.data.source.sessionDate);
    if(tbQualityView.selectedPeriod!==requested||$('#tbDrillStage').value!==stage)return;
    state.tickerDrill={selection,period,stage};
    state.tickerDrillLimit=40;
    renderTickerDrillResults();
  }catch(error){
    result.textContent='Nije moguće prikazati potpun popis: '+error.message;
    state.tickerDrill=null;
  }
}
function renderTickerDrillResults(){
  const selected=state.tickerDrill;
  if(!selected)return;
  const {members,tickerDays}=selected.selection,limit=state.tickerDrillLimit;
  const suffix=tbQualityView.timeframe==='D'?'tickera':'jedinstvenih tickera · '+tickerDays+' ticker-dana';
  $('#tbDrillResults').innerHTML='<div class="tb-history-metric">'+members.length+' '+suffix+
    ' · svaki ticker može se pojaviti više dana u W/M razdoblju.</div>'+
    '<div class="tb-ticker-list">'+tickerListHTML(members,limit)+'</div>'+
    (limit<members.length?'<button type="button" class="tb-drill-more" id="tbDrillMore">Prikaži još '+Math.min(40,members.length-limit)+'</button>':'');
}
async function showTickerJourney(ticker){
  if(!/^[A-Z0-9.^_-]{1,24}$/.test(ticker||''))return;
  const panel=$('#tbTickerJourney');
  panel.hidden=false;
  panel.innerHTML='<h3>'+esc(ticker)+' · putanja setupa</h3><p>Učitavam sačuvane EOD stupnjeve…</p>';
  state.journeyTicker=ticker;
  try{
    const asOf=state.data?.source?.sessionDate||state.intelligence?.source.sessionDate;
    const points=state.qualityHistory?.points||[];
    const earliest=points.filter(p=>p.sessionDate<=asOf).map(p=>p.sessionDate).sort()[0]||asOf;
    const months=await loadTickerMonths(earliest,asOf);
    const journey=TrendBirthIntelligence.journey(months,ticker,asOf);
    const streak=TrendBirthIntelligence.streaks(months,ticker,asOf);
    if(state.journeyTicker!==ticker)return;
    const renderDay=p=>'<div class="tb-ticker-journey-day"><small>'+p.sessionDate.slice(5)+'</small>'+
      '<strong>'+(p.stage==null?'N/A':p.stage+'/4')+'</strong>'+
      '<span class="tb-stage-dot" data-stage="'+(p.stage==null?'na':p.stage)+'"></span></div>';
    panel.innerHTML='<div class="tb-quality-header"><h3>'+esc(ticker)+' · putanja setupa</h3>'+
      '<button type="button" class="tb-text-button" id="tbCloseJourney">Zatvori ×</button></div>'+
      '<p class="tb-history-data-note">'+journey.length+' sačuvanih očitanja · 3+/4 u nizu: '+
      streak.quality+' EOD · 4/4 u nizu: '+streak.four+
      ' EOD. Nedostupnost ili izostanak iz univerzuma prekida niz; ne izmišljamo 0/4.</p>'+
      (journey.length?'<div class="tb-ticker-journey-points">'+journey.map(renderDay).join('')+'</div>':
        '<p>Nema potvrđenih podataka za ticker u spremljenoj povijesti.</p>');
    panel.scrollIntoView({block:'nearest',behavior:'smooth'});
  }catch(error){panel.innerHTML='<h3>'+esc(ticker)+'</h3><p>Putanja nije dostupna: '+esc(error.message)+'</p>'}
}

function renderTrendBirthQuality(){
  const panel=$('#trendBirthQuality'),summary=$('#tbQualitySummary'),countsBox=$('#tbQualityCounts'),historyBox=$('#tbQualityHistory');
  const source=state.data?.trendBirthRadar,quality=TrendBirthQuality.normalizeRadar(source);
  if(!quality){panel.hidden=true;return}
  panel.hidden=false;
  const day=String(state.data?.source?.sessionDate||'');
  const promising=quality.counts['3']+quality.counts['4'];
  const share=quality.evaluatedCount?100*promising/quality.evaluatedCount:0;
  summary.textContent=day+' · '+quality.evaluatedCount.toLocaleString('hr-HR')+' analizirano / '+quality.universeCount.toLocaleString('hr-HR')+' pregledano · '+quality.unavailableCount+' bez podataka · 3/4+4/4: '+share.toFixed(1)+'%';
  countsBox.innerHTML=['0','1','2','3','4'].map(stage=>{
    const number=quality.counts[stage];
    const percent=quality.evaluatedCount?100*number/quality.evaluatedCount:0;
    return '<div class="tb-quality-stage" data-stage="'+stage+'"><span>'+stage+'/4</span><strong>'+number.toLocaleString('hr-HR')+'</strong><small>'+percent.toFixed(1)+'%</small></div>';
  }).join('');
  document.querySelectorAll('[data-tb-zoom]').forEach(button=>
    button.setAttribute('aria-pressed',String(Number(button.dataset.tbZoom)===tbQualityView.zoom)));
  document.querySelectorAll('[data-tb-timeframe]').forEach(button=>
    button.setAttribute('aria-pressed',String(button.dataset.tbTimeframe===tbQualityView.timeframe)));
  document.querySelectorAll('[data-tb-range]').forEach(button=>
    button.setAttribute('aria-pressed',String(button.dataset.tbRange===tbQualityView.range)));
  if(!state.qualityHistory){
    historyBox.textContent=state.qualityHistoryError||'Učitavam povijest potvrđenih dnevnih skenova…';
    return;
  }
  let fullPoints;
  try{fullPoints=TrendBirthQuality.normalizeHistory(state.qualityHistory,day,source.scope)}
  catch(error){historyBox.textContent='Povijesni podaci nisu usporedivi: '+error.message;return}
  fullPoints=fullPoints.filter(point=>point.sessionDate!==day);
  fullPoints.push({sessionDate:day,...quality});
  fullPoints.sort((a,b)=>a.sessionDate.localeCompare(b.sessionDate));
  // W/M are derived from all retained daily sessions, never stored as a second archive.
  const allPeriods=TrendBirthQuality.aggregateHistory(fullPoints,tbQualityView.timeframe);
  const points=TrendBirthQuality.selectHistoryRange(allPeriods,tbQualityView.range,day);
  const selectedStages=[...document.querySelectorAll('input[data-tb-stage]:checked')]
    .map(input=>input.dataset.tbStage);
  const zoom=tbQualityView.zoom;
  const ticks=TrendBirthQuality.zoomTicks(zoom);
  const latest=allPeriods[allPeriods.length-1];
  const selectedPoint=points.find(point=>point.periodKey===tbQualityView.selectedPeriod)||points[points.length-1];
  const periodName=tbQualityView.timeframe==='D'?'Dnevno':tbQualityView.timeframe==='W'?'Tjedno':'Mjesečno';
  const countName=tbQualityView.timeframe==='D'?'dionica':'dionica-dana';
  const bars=points.map(point=>{
    const title=point.label+' · '+['4','3','2','1','0'].map(stage=>
      stage+'/4: '+TrendBirthQuality.percent(point,stage).toFixed(2)+'% ('+point.counts[stage]+' '+countName+')').join(' · ')+
      ' · '+point.sessionCount+' dnevnih sesija · '+point.evaluatedCount+' '+countName+
      ' · '+point.unavailableCount+' bez podataka';
    const segments=TrendBirthQuality.stackSlices(point,zoom).map(slice=>{
      if(slice.visiblePercent<=0)return '';
      const muted=selectedStages.includes(slice.stage)?'':' is-muted';
      return '<span class="tb-history-segment'+muted+'" data-stage="'+slice.stage+'" style="height:'+slice.visiblePercent.toFixed(4)+'%"></span>';
    }).join('');
    const pressed=point.periodKey===selectedPoint.periodKey?'true':'false';
    return '<button type="button" class="tb-history-bar" data-tb-period="'+point.periodKey+
      '" aria-pressed="'+pressed+'" title="'+esc(title)+'" aria-label="'+esc(title)+'">'+segments+'</button>';
  }).join('');
  const yLabels=ticks.map(tick=>'<span>'+tick+'%</span>').join('');
  const gridLines=ticks.map(tick=>
    '<span class="tb-history-gridline" style="bottom:'+(100*tick/zoom).toFixed(4)+'%"></span>').join('');
  const focus=$('#tbPercentileMetric')?.value||'3+';
  const focusStages=focus==='3+'?['3','4']:focus==='selected'?selectedStages:[focus];
  const focusLabel=focus==='3+'?'3/4 + 4/4':focus==='selected'?
    (focusStages.length?focusStages.map(stage=>stage+'/4').join(' + '):'Nijedna razina'):focus+'/4';
  // Ignore the leftmost truncated calendar bucket when comparing weekly/monthly history.
  const rankPoints=tbQualityView.timeframe==='D'?allPeriods:
    allPeriods.filter((point,index)=>index!==0||!point.isPartial||allPeriods.length===1);
  const rank=focusStages.length&&focusStages.length<5?
    TrendBirthQuality.historicalPercentile(rankPoints,focusStages):null;
  const lastCount=focusStages.reduce((sum,stage)=>sum+(latest.counts[stage]||0),0);
  const rankValue=rank?.percentile==null?'—':'P'+Math.round(rank.percentile);
  const unit=tbQualityView.timeframe==='D'?'sesija':tbQualityView.timeframe==='W'?'tjedana':'mjeseci';
  const rankExplain=!focusStages.length?'Označi barem jednu razinu.':
    focusStages.length===5?'Zbroj svih razina uvijek je 100 %; za smislen percentil odaberi užu kombinaciju.':
    'Udio '+TrendBirthQuality.percentOfStages(latest,focusStages).toFixed(2)+'% ('+
    lastCount.toLocaleString('hr-HR')+' od '+latest.evaluatedCount.toLocaleString('hr-HR')+' '+countName+
    '); usporedba s '+(rank?.priorCount||0)+' ranijih '+unit+
    (tbQualityView.timeframe!=='D'&&latest.isPartial?'; posljednje razdoblje još može biti nepotpuno':'')+
    (rank?.priorCount<12?'; mali povijesni uzorak':'')+
    (focusStages.length===1&&focusStages[0]==='0'?'. Viši percentil 0/4 znači više dionica bez setupa.':'.');
  const detail=['4','3','2','1','0'].map(stage=>
    '<span class="tb-day-level"><i class="tb-stage-dot" data-stage="'+stage+'"></i>'+
      stage+'/4: '+TrendBirthQuality.percent(selectedPoint,stage).toFixed(2)+'% ('+
      selectedPoint.counts[stage].toLocaleString('hr-HR')+' '+countName+')</span>').join('');
  const minChartWidth=Math.max(320,points.length*(tbQualityView.timeframe==='D'?9:tbQualityView.timeframe==='W'?17:25));
  const priorScroll=historyBox.querySelector('.tb-history-main')?.scrollLeft;
  historyBox.innerHTML=
    '<div class="tb-history-metric">'+periodName+' · '+points.length+' od '+allPeriods.length+
      ' razdoblja · '+fullPoints.length+' trajno sačuvanih dnevnih očitanja · zoom 0–'+zoom+'%</div>'+
    '<div class="tb-history-percentile" aria-live="polite"><strong>'+rankValue+'</strong>'+
      '<span><b>'+esc(focusLabel)+'</b> · '+esc(rankExplain)+'</span></div>'+
    '<div class="tb-history-plot"><div class="tb-history-y-axis" aria-hidden="true">'+yLabels+'</div>'+
      '<div class="tb-history-main"><div class="tb-history-scroll" style="min-width:'+minChartWidth+'px">'+
        '<div class="tb-history-chart" style="grid-template-columns:repeat('+points.length+',minmax(0,1fr))" aria-label="'+
          periodName+' složeni povijesni stupci: udjeli razina od 0 do '+zoom+' posto">'+
          '<div class="tb-history-gridlines" aria-hidden="true">'+gridLines+'</div>'+bars+'</div>'+
        '<div class="tb-history-axis"><span>'+esc(points[0].label)+'</span><span>'+esc(points[points.length-1].label)+'</span></div>'+
      '</div></div></div>'+
    '<div class="tb-history-day-detail"><strong>'+esc(selectedPoint.label)+
      ' · '+selectedPoint.sessionCount+' dnevnih sesija · '+
      (tbQualityView.timeframe==='D'?selectedPoint.evaluatedCount+' analizirano':
        Math.round(selectedPoint.evaluatedCount/selectedPoint.sessionCount).toLocaleString('hr-HR')+
        ' prosječno analiziranih dionica/dan')+
      ' · '+selectedPoint.unavailableCount+' nedostupnih '+(tbQualityView.timeframe==='D'?'dionica':'dionica-dana')+'</strong>'+
      '<div class="tb-day-levels">'+detail+'</div>'+
      '<span class="tb-history-metric">3/4 + 4/4: '+
        TrendBirthQuality.percent(selectedPoint,'3+').toFixed(2)+'% ('+
        TrendBirthQuality.count(selectedPoint,'3+').toLocaleString('hr-HR')+' '+countName+
        '). Dodirni stupac za detalje razdoblja.</span>'+
      (selectedPoint.isPartial?'<div class="tb-history-data-note">Razdoblje je djelomično pokriveno postojećom arhivom ili još traje.</div>':'')+
      '</div>';
  const scroller=historyBox.querySelector('.tb-history-main');
  if(scroller)scroller.scrollLeft=tbQualityView.scrollToEnd||priorScroll==null?
    scroller.scrollWidth-scroller.clientWidth:priorScroll;
  tbQualityView.scrollToEnd=false;
}
async function loadTrendBirthQualityHistory(){
  const snapshotId=state.snapshotId;
  try{
    const response=await fetch('data/trend-birth-quality-history.json',{cache:'no-store'});
    if(!response.ok)throw new Error('HTTP '+response.status);
    const data=await response.json();
    if(snapshotId!==state.snapshotId)return;
    state.qualityHistory=data;
  }catch(error){
    if(snapshotId!==state.snapshotId)return;
    state.qualityHistoryError='Povijest još nije objavljena ('+error.message+'). Trenutačni dnevni brojevi ostaju prikazani.';
  }
  renderTrendBirthQuality();
}
const trendBirthLabel=item=>{
  const radar=item?.trendBirth||{};
  if(radar.available!==true){
    const reason=String(radar.reason||'unavailable').replaceAll('_',' ');
    return 'N/A · '+reason;
  }
  return trendBirthStage(item)+'/4 '+String(radar.stageLabel||'NO SETUP');
};
function trendBirthChecklistText(item){
  const radar=item?.trendBirth||{},checks=radar.checks||{};
  if(radar.available!==true){
    return '⚪ Trend Birth unavailable — '+String(radar.reason||'unknown reason').replaceAll('_',' ');
  }
  const labels=[
    ['sma50Rising','SMA50 rising'],
    ['sma30wRising','SMA30W rising'],
    ['structureValid','Structure valid'],
    ['notExtended','Not extended'],
    ['recentPullbackCompression','Pullback + EMA compression'],
    ['ema10Rising','EMA10 rising'],
    ['ema20NonFalling','EMA20 non-falling'],
    ['ema10AboveEma20','EMA10 > EMA20'],
    ['closeAboveShortEmas','Close > EMA10 & EMA20'],
    ['bullishReexpansion','Bullish EMA re-expansion']
  ];
  return labels.map(([key,label])=>(checks[key]?'✅ ':'❌ ')+label).join('\n');
}
const birthPathOrder=['recovery','compression','ignition'];
const birthPathLabels={recovery:'Recovery',compression:'Compression',ignition:'Ignition'};
const trendBirthEvidence=item=>item?.trendBirthEvidence||{};
const birthEvidencePhase=item=>String(trendBirthEvidence(item).phase||'');
const birthEvidenceCount=item=>Number(trendBirthEvidence(item).activeCount||0);
function birthPathText(item){
  const evidence=trendBirthEvidence(item);
  return birthPathOrder.map(key=>(Array.isArray(evidence[key])&&evidence[key].length?'✓ ':'○ ')+birthPathLabels[key]).join(' → ');
}
function birthEvidenceText(item){
  const evidence=trendBirthEvidence(item);
  const rows=birthPathOrder
    .filter(key=>Array.isArray(evidence[key])&&evidence[key].length)
    .map(key=>birthPathLabels[key]+': '+evidence[key].join(' · '));
  return rows.join('\n')||'No supporting Bottom/Launch evidence';
}
function birthEvidenceBadge(item){
  const evidence=trendBirthEvidence(item),phase=birthEvidencePhase(item),primary=String(evidence.primary||'');
  if(!phase||!primary)return '';
  const extra=Math.max(0,birthEvidenceCount(item)-1);
  return '<span class="badge birth-evidence">'+esc(birthPathLabels[phase]||phase)+' · '+esc(primary)+(extra?' +'+extra:'')+'</span>';
}
function ownerWatchlistItems(tickers){
  return WatchlistStore.normalizeItems((tickers||[]).map(ticker=>({
    ticker,
    addedAt:state.watchlist.find(item=>item.ticker===ticker)?.addedAt||new Date().toISOString(),
    addedSession:state.watchlist.find(item=>item.ticker===ticker)?.addedSession||state.data?.source?.sessionDate||null
  })));
}
function updateOwnerSyncUi(){
  const summary=$('#ownerSyncSummary'),status=$('#ownerSyncStatus'),form=$('#ownerMagicForm'),steps=$('#ownerMagicSteps'),sent=$('#ownerMagicSent'),sentTo=$('#ownerMagicSentTo'),submit=$('#ownerMagicSubmit'),note=$('.owner-auth-note'),signOut=$('#ownerSignOut');
  if(!summary||!status)return;
  const signedIn=Boolean(state.ownerSession?.user);
  summary.textContent=signedIn?'☁ Watchlist: synced':'☁ Watchlist: local';
  summary.classList.toggle('synced',signedIn);
  status.classList.toggle('sync-error',Boolean(state.ownerSyncError));
  status.classList.toggle('sync-ok',signedIn&&!state.ownerSyncError);
  status.textContent=state.ownerSyncError
    ?state.ownerSyncError
    :signedIn
      ?(state.ownerSyncMessage||('Prijavljen · '+(state.ownerSession.user.email||'owner')))
      :state.ownerMagicSentTo
        ?'Link je poslan. Dovrši prijavu iz najnovijeg emaila.'
        :(state.ownerSyncMessage||'Lokalna zvjezdica radi i bez prijave.');
  if(form)form.hidden=signedIn;
  if(steps)steps.hidden=signedIn;
  if(sent)sent.hidden=signedIn||!state.ownerMagicSentTo;
  if(sentTo)sentTo.textContent=state.ownerMagicSentTo?'Poslano na '+state.ownerMagicSentTo:'';
  if(submit){
    submit.disabled=state.ownerMagicSending;
    submit.textContent=state.ownerMagicSending?'Šaljem…':state.ownerMagicSentTo?'Pošalji ponovno':'Pošalji link';
  }
  if(note)note.hidden=signedIn;
  if(signOut)signOut.hidden=!signedIn;
  const importButton=$('#ownerImportLocal');
  if(importButton)importButton.hidden=!signedIn||!WatchlistStore.load(window.localStorage).length;
}
async function reconcileOwnerWatchlist(){
  if(!state.ownerSync?.signedIn())return;
  if(state.ownerReconciling||state.watchlistUpdating){state.ownerReconcilePending=true;return}
  state.ownerReconciling=true;state.ownerSyncError='';
  try{
    const ownerId=state.ownerSession?.user?.id;
    const remote=await state.ownerSync.load();
    if(ownerId!==state.ownerSession?.user?.id)return;
    state.watchlist=WatchlistStore.save(window.localStorage,ownerWatchlistItems(remote),state.ownerSession?.user?.id);
    state.ownerSyncMessage='Owner watchlist synced · '+remote.length+' tickera.';
    if(state.data)render();
  }catch(err){
    state.ownerSyncError='Owner sync: '+(err?.message||String(err));
  }finally{
    state.ownerReconciling=false;updateOwnerSyncUi();
    if(state.ownerReconcilePending){state.ownerReconcilePending=false;queueMicrotask(()=>reconcileOwnerWatchlist())}
  }
}
let ownerPlanScope=null;
function ownerPlanLists(){
  const account=ownerPlanScope?.ownerId;
  if(!account)return [];
  const local=ReviewPlans.localBook(window.localStorage,account);
  const anonymous=ReviewPlans.localBook(window.localStorage);
  return OwnerPlanBook.projection(anonymous,local);
}
function updateOwnerPlanUi(){
  const scope=ownerPlanScope,panel=$('#ownerPlanPanel');
  if(!panel)return;
  panel.hidden=!scope||state.primaryView!=='watchlist';
  if(panel.hidden)return;
  const note=$('#ownerPlanSyncNote'),importButton=$('#ownerPlanImport');
  const remote=new Map((scope.book?.plans||[]).map(plan=>[ReviewPlans.planId(plan),plan]));
  const count=scope.book?ownerPlanLists().filter(plan=>OwnerPlanBook.canImport(plan,remote.get(ReviewPlans.planId(plan)))).length:0;
  const labels={loading:'Učitavam planove s računa…',local:'Planovi se čuvaju u ovom pregledniku.',
    ready:'Planovi na računu dostupni su na drugim uređajima.',error:'Osvježavanje planova s računa nije uspjelo.'};
  note.textContent=scope.phase==='error'?labels.error:scope.message||labels[scope.phase];
  importButton.hidden=!count;
  importButton.textContent='Prenesi lokalne planove ('+count+')';
  importButton.disabled=Boolean(scope.importing);
  $('#ownerPlanRefresh').hidden=scope.phase==='loading'||scope.phase==='local';
  $('#ownerPlanRefresh').disabled=Boolean(scope.loading);
}
function cloudPlan(id){
  return ownerPlanScope?.book?.plans.find(plan=>ReviewPlans.planId(plan)===id);
}
function acceptOwnerPlanBook(scope,book){
  if(scope!==ownerPlanScope)return false;
  if(!scope.book||book.version>=scope.book.version)scope.book=book;
  scope.phase='ready';
  return true;
}
async function refreshOwnerPlanBook(){
  const scope=ownerPlanScope;
  if(!scope||scope.loading||scope.phase==='local'||document.visibilityState==='hidden')return;
  scope.loading=true;
  updateOwnerPlanUi();
  try{
    const book=OwnerPlanBook.validate(await state.ownerSync.loadPlanBook(scope.ownerId));
    const changed=scope.book?.version!==book.version;
    if(acceptOwnerPlanBook(scope,book)){
      if(changed&&state.data)render();
      flushOwnerPlanReviews(scope);
    }
  }catch(error){
    if(scope!==ownerPlanScope)return;
    scope.phase=!scope.book&&['PGRST205','42P01','PGRST106'].includes(error?.code)?'local':'error';
  }finally{
    scope.loading=false;
    if(scope===ownerPlanScope)updateOwnerPlanUi();
  }
}
async function changeOwnerPlanBook(scope,transform){
  const updated=await OwnerPlanBook.update(state.ownerSync,scope.ownerId,transform);
  if(!acceptOwnerPlanBook(scope,updated.book))throw Error('Račun se promijenio tijekom sinkronizacije.');
  return updated.result;
}
function flushOwnerPlanReviews(scope){
  if(scope!==ownerPlanScope||!scope.reviews.size||scope.reviewWriting)return;
  scope.reviewWriting=true;
  queueMicrotask(async()=>{
    if(scope!==ownerPlanScope)return;
    const batch=scope.reviews;
    scope.reviews=new Map();
    let committed=false;
    try{
      await changeOwnerPlanBook(scope,plans=>OwnerPlanBook.reviewPlans(plans,batch));
      committed=true;
    }catch(_error){
      for(const [id,review] of batch)if(!scope.reviews.has(id))scope.reviews.set(id,review);
    }finally{
      scope.reviewWriting=false;
      if(committed)flushOwnerPlanReviews(scope);
    }
  });
}
function queueOwnerPlanReview(plan,review){
  const id=ReviewPlans.planId(plan),remote=cloudPlan(id);
  if(!remote)return false;
  const saved=ReviewPlans.archivedReview(remote);
  if(!remote.archivedAt&&(!saved||saved.asOf<review.asOf)){
    const scope=ownerPlanScope;
    scope.reviews.set(id,review);
    flushOwnerPlanReviews(scope);
  }
  return true;
}
async function resumeOwnerMagicLinkBridge(){
  const phase=ownerAuthPhase();
  if(!phase)return;
  if(phase==='complete'){
    clearOwnerAuthPhase();
    sessionStorage.removeItem(OWNER_MAGIC_EMAIL_KEY);
    if(state.ownerSession?.user)state.ownerSyncMessage='Prijava uspješna · Watchlist sync je aktivan.';
    return;
  }
  if(phase!=='prepared')return;
  clearOwnerAuthPhase();
  if(state.ownerSession?.user){
    sessionStorage.removeItem(OWNER_MAGIC_EMAIL_KEY);
    return;
  }
  const email=sessionStorage.getItem(OWNER_MAGIC_EMAIL_KEY)?.trim();
  if(!email){
    state.ownerSyncError='Nedostaje email za nastavak magic-link prijave. Upiši ga ponovno.';
    return;
  }
  state.ownerSyncError='';
  state.ownerMagicSending=true;
  state.ownerSyncMessage='Sigurni povratak je pripremljen. Šaljem magic link…';
  updateOwnerSyncUi();
  try{
    await state.ownerSync.sendMagicLink(email);
    state.ownerMagicSentTo=email;
    state.ownerSyncMessage='Link je poslan. Otvori najnoviju Supabase poruku.';
    sessionStorage.removeItem(OWNER_MAGIC_EMAIL_KEY);
  }catch(err){
    state.ownerSyncError='Magic link: '+(err?.message||String(err));
  }finally{
    state.ownerMagicSending=false;
    updateOwnerSyncUi();
  }
}
async function initOwnerWatchlistSync(){
  if(!window.OwnerWatchlistSync){state.ownerSyncError='Owner sync client nije učitan.';updateOwnerSyncUi();return}
  try{
    state.ownerSync=OwnerWatchlistSync.create({
      onSession:session=>{
        const previousUser=state.ownerSession?.user?.id;
        state.ownerSession=session;
        if(previousUser!==session?.user?.id){
          ownerPlanScope=session?.user?{ownerId:session.user.id,phase:'loading',book:null,reviews:new Map()}:null;
          if($('#detail')?.open)$('#detail').close();
          $('#planNotice').hidden=true;
          state.watchlist=WatchlistStore.load(window.localStorage,session?.user?.id);
          if(state.data)render();
        }
        state.ownerSyncError='';
        state.ownerSyncMessage=session?.user?'Watchlist sync je aktivan.':'';
        if(session?.user)state.ownerMagicSentTo='';
        updateOwnerSyncUi();
        if(session?.user)queueMicrotask(()=>{
          reconcileOwnerWatchlist();
          refreshOwnerPlanBook();
        });
      }
    });
    const session=await state.ownerSync.init();
    state.ownerSession=session;
    await resumeOwnerMagicLinkBridge();
    updateOwnerSyncUi();
    if(state.ownerSession?.user)await reconcileOwnerWatchlist();
  }catch(err){
    state.ownerSyncError='Owner sync: '+(err?.message||String(err));
    updateOwnerSyncUi();
  }
}
const isWatched=ticker=>WatchlistStore.has(state.watchlist,ticker);
async function toggleWatchlist(ticker){
  if(state.watchlistUpdating||state.ownerReconciling)return;
  const ownerId=state.ownerSession?.user?.id;
  const before=state.watchlist.map(item=>({...item}));
  const next=WatchlistStore.toggle(state.watchlist,ticker,{
    addedSession:state.data?.source?.sessionDate||null
  });
  const present=WatchlistStore.has(next,ticker);
  state.watchlist=WatchlistStore.save(window.localStorage,next,state.ownerSession?.user?.id);
  state.ownerSyncError='';state.ownerSyncMessage='';
  render();
  if(!state.ownerSync?.signedIn()){updateOwnerSyncUi();return}
  state.watchlistUpdating=true;
  try{
    const remote=await state.ownerSync.setTicker(ticker,present);
    if(ownerId!==state.ownerSession?.user?.id)return;
    state.watchlist=WatchlistStore.save(window.localStorage,ownerWatchlistItems(remote),state.ownerSession?.user?.id);
    state.ownerSyncMessage=(present?'Dodano u':'Maknuto iz')+' synced Trend Birth watchliste.';
  }catch(err){
    if(ownerId!==state.ownerSession?.user?.id)return;
    state.watchlist=WatchlistStore.save(window.localStorage,before,state.ownerSession?.user?.id);
    state.ownerSyncError='Watchlist sync nije uspio: '+(err?.message||String(err));
  }finally{state.watchlistUpdating=false;if(state.ownerReconcilePending){state.ownerReconcilePending=false;queueMicrotask(()=>reconcileOwnerWatchlist())}}
  updateOwnerSyncUi();
  render();
}
function watchedEntries(){
  if(state.primaryView!=='watchlist')return state.watchlist;
  const entries=new Map(state.watchlist.map(saved=>[saved.ticker,saved]));
  for(const plan of state.savedPlans||[]){
    if(!plan.archivedAt&&!entries.has(plan.ticker))entries.set(plan.ticker,{ticker:plan.ticker});
  }
  return [...entries.values()];
}
function watchlistItems(){
  const entries=watchedEntries();
  const byTicker=new Map();
  if(state.primaryView==='watchlist')for(const plan of state.savedPlans||[]){
    if(plan.archivedAt)continue;
    const plans=byTicker.get(plan.ticker)||[];
    plans.push(plan);
    byTicker.set(plan.ticker,plans);
  }
  if(state.publication?.watchlist){
    return entries.map(saved=>{
      const lookup=state.watchlistLookup.rows;
      const row=lookup.get(saved.ticker);
      const view=row||{ticker:saved.ticker,metrics:{},
        watchlistMissing:lookup.has(saved.ticker),watchlistUnavailable:!lookup.has(saved.ticker)};
      return {...view,watchlistSaved:saved,savedPlans:byTicker.get(saved.ticker)};
    });
  }
  const review=new Map((state.data?.candidates||[]).map(item=>[item.ticker,item]));
  const kell=new Map((state.kellData?.kellCandidates||state.data?.kellCandidates||[]).map(item=>[item.ticker,item]));
  const tracked=new Map((state.kellData?.trendBirthCandidateIndex||state.data?.trendBirthCandidateIndex||[]).map(item=>[item.ticker,item]));
  const unified=new Map((state.kellData?.unifiedCandidateIndex||state.data?.unifiedCandidateIndex||[]).map(item=>[item.ticker,item]));
  return entries.map(saved=>{
    const current=tracked.get(saved.ticker)||unified.get(saved.ticker);
    const base=review.get(saved.ticker);
    const overlay=kell.get(saved.ticker);
    if(!current&&!base&&!overlay){
      return{ticker:saved.ticker,sources:[],unifiedSources:[],metrics:{},watchlistSaved:saved,watchlistMissing:true,
        savedPlans:byTicker.get(saved.ticker)};
    }
    const merged={
      ...(current||{}),
      ...(base||{}),
      ...(overlay||{}),
      ticker:saved.ticker,
      sources:[...new Set([...(current?.sources||current?.unifiedSources||[]),...(base?.sources||[]),...(overlay?.sources||[])])],
      unifiedSources:[...new Set([...(current?.unifiedSources||current?.sources||[]),...(base?.unifiedSources||[]),...(overlay?.unifiedSources||[])])],
      metrics:{...(current?.metrics||{}),...(base?.metrics||{}),...(overlay?.metrics||{})},
      trendBirth:current?.trackedWatchlist?current?.trendBirth:(overlay?.trendBirth||base?.trendBirth||current?.trendBirth||{}),
      chartBars:current?.trackedWatchlist&&current?.chartBars?.length?current.chartBars:(base?.chartBars?.length?base.chartBars:overlay?.chartBars),
      weeklyChartBars:current?.trackedWatchlist&&current?.weeklyChartBars?.length?current.weeklyChartBars:(base?.weeklyChartBars?.length?base.weeklyChartBars:overlay?.weeklyChartBars),
      analysis:base?.analysis||overlay?.analysis||{},
      watchlistSaved:saved,
      savedPlans:byTicker.get(saved.ticker)
    };
    if(current&&!base&&!overlay)merged.watchlistUnifiedOnly=true;
    return merged;
  });
}
function watchlistLookup(){
  return {rows:new Map(),cache:new Map(),request:null,error:''};
}
function loadWatchedRows(){
  const entries=watchedEntries();
  if(state.primaryView!=='watchlist'||!entries.length)return;
  const lookup=state.watchlistLookup;
  if(lookup.request||lookup.error)return;
  let request;
  if(state.publication?.watchlist){
    const tickers=entries.map(saved=>saved.ticker).filter(ticker=>!lookup.rows.has(ticker));
    if(!tickers.length)return;
    request=ReviewSnapshots.loadWatchlist(fetch,state.publication,tickers,lookup.cache).then(rows=>{
      for(const [ticker,row] of rows)lookup.rows.set(ticker,row);
    });
  }else if(state.data?.schemaVersion==='trend-birth-review-bootstrap-v1'){
    request=ensureResearchData();
  }else return;
  lookup.request=request;
  request.catch(error=>{lookup.error=error.message;}).finally(()=>{
    lookup.request=null;
    if(state.watchlistLookup===lookup&&state.primaryView==='watchlist')render();
  });
}
function updateWatchlistButton(){
  const button=$('#watchlistUniverse');
  if(!button)return;
  button.textContent='★ Watchlist ('+(state.watchlist?.length||0)+')';
}


function normalizeBars(rows){
  return(rows||[]).filter(Boolean).map(row=>{
    const [time,open,high,low,close,volume,rs]=Array.isArray(row)?row:
      [row.time||row.date,row.open,row.high,row.low,row.close,row.volume,row.rs??row.relativeStrength??row.relative_strength];
    return{time,open:+open,high:+high,low:+low,close:+close,volume:volume==null||volume===''?null:+volume,
      rs:Number.isFinite(+rs)&&+rs>0?+rs:null};
  }).filter(bar=>[bar.open,bar.high,bar.low,bar.close].every(Number.isFinite));
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
  base:{label:'Zona baze · W',weekly:true,weeks:112},
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
      current={key,time:date.toISOString().slice(0,10),open:bar.open,high:bar.high,low:bar.low,close:bar.close,
        volume:Number.isFinite(bar.volume)?bar.volume:null,rs:bar.rs};
      out.push(current);
    }else{
      current.time=date.toISOString().slice(0,10);
      current.high=Math.max(current.high,bar.high);
      current.low=Math.min(current.low,bar.low);
      current.close=bar.close;
      current.volume=Number.isFinite(current.volume)&&Number.isFinite(bar.volume)?current.volume+bar.volume:null;
      current.rs=bar.rs;
    }
  }
  return out;
}
function rowsForPeriod(item,periodKey=state.chartPeriod,
  weeklyCutoff=state.primaryView==='weekly'?item?.weeklyBirth?.metrics?.historyEnd:null){
  const period=chartPeriods[periodKey]||chartPeriods['1y'];
  if(period.weekly){
    const weekly=item?.weeklyChartBars?.length>=2?normalizeBars(item.weeklyChartBars):weeklyBars(item?.chartBars||[]);
    const cutoff=barDate(weeklyCutoff);
    return cutoff ? weekly.filter(bar=>{const day=barDate(bar.time);return day&&day<=cutoff}) : weekly;
  }
  return normalizeBars(item?.chartBars||[]);
}
function weeklyBaseRange(item,rows){
  const metrics=item.weeklyBirth?.metrics||{};
  const end=barDate(metrics.historyEnd);
  const length=metrics.baseWeeks;
  // Weekly Birth reserves the last eight completed weeks for breakout evaluation.
  if(!end||!Number.isInteger(length)||length<9||rows.length<length||
      +barDate(rows.at(-1).time)!==+end)return null;
  const window=rows.slice(-length,-8);
  const floor=Math.min(...window.map(row=>row.low));
  if(!Number.isFinite(metrics.pivotPrice)||metrics.pivotPrice<=floor)return null;
  return {start:window[0].time,end:window.at(-1).time,cutoff:rows.at(-1).time,
    floor,floorBar:window.findLast(row=>row.low===floor),
    lastBelowFloor:rows.slice(-8).findLast(row=>row.close<floor)||null,
    ceiling:metrics.pivotPrice,weeks:length+8};
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
function chartLevels(item,view=state.primaryView){
  if(view==='weekly'){
    const metrics=item?.weeklyBirth?.metrics;
    return [[metrics?.pivotPrice,'Pivot','#80c7ff'],[metrics?.resistancePrice,'Otpor','#ff9aa5']];
  }
  const early=item?.earlyTrend,swing=item?.kellSwing;
  if(early&&view!=='kell-daily')return [
    [early.reclaimPivot,'Pivot','#80c7ff'],[early.baseSupport,'Podrška','#e9bd62'],
    [early.invalidation,'Poništenje','#ff8b99']
  ];
  if(view==='early')return [];
  if(swing)return [
    [swing.maxEntry,'Maks. ulaz','#e9bd62'],[swing.pivot,'Pivot','#80c7ff'],[swing.stop,'Stop','#ff8b99']
  ];
  return [];
}
function draw(canvas,rows,large=false,emptyMessage='Graf nije dostupan',levels=[],base=null,periodKey=state.chartPeriod,savedPlan=null){
  const history=normalizeBars(rows);
  const period=chartPeriods[periodKey]||chartPeriods['1y'];
  const count=periodKey==='base'&&base?base.weeks:period.weekly?period.weeks:period.daily;
  const bars=history.slice(-count);
  const offset=history.length-bars.length;
  const rect=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
  canvas.width=Math.max(1,rect.width*dpr);canvas.height=Math.max(1,rect.height*dpr);
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const w=rect.width,h=rect.height;ctx.clearRect(0,0,w,h);
  ctx.font=(large?'12px':'10px')+' system-ui,-apple-system,Segoe UI,Roboto,sans-serif';
  canvas.removeAttribute?.('aria-description');
  if(bars.length<2){
    ctx.fillStyle='#8ea0b7';ctx.textAlign='left';ctx.textBaseline='alphabetic';
    ctx.fillText(emptyMessage,12,22);return;
  }
  const top=large?32:24,bottom=large?46:38,left=large?10:8,right=large?72:60;
  const rawLo=Math.min(...bars.map(b=>b.low)),high=Math.max(...bars.map(b=>b.high));
  const levelMargin=(high-rawLo)*.2;
  const nearLevels=levels.map(([price])=>price).filter(price=>Number.isFinite(price)&&
    (savedPlan?price>=rawLo-levelMargin&&price<=high+levelMargin:base&&price>=high&&price<=high+levelMargin));
  const rawHi=Math.max(high,...nearLevels),floor=Math.min(rawLo,...nearLevels);
  const rawRange=Math.max(rawHi-floor,.0001),pad=Math.max(rawRange*.035,Math.abs(rawHi)*.001);
  const lo=floor-pad,hi=rawHi+pad,range=Math.max(hi-lo,.0001);
  const axis=large?ChartEvidence.axis(w,bars.length):null;
  const plotW=axis?.plotWidth??Math.max(1,w-left-right),plotH=Math.max(1,h-top-bottom);
  const x=axis?.x??(i=>left+i*plotW/(bars.length-1)),y=v=>top+(hi-v)*plotH/range;
  const description=[];
  if(base){
    const start=bars.findIndex(bar=>bar.time===base.start);
    const end=bars.findIndex(bar=>bar.time===base.end);
    if(start>=0&&end>=start){
      ctx.fillStyle='#58bdb42e';
      ctx.fillRect(x(start),y(base.ceiling),Math.max(1,x(end)-x(start)),y(base.floor)-y(base.ceiling));
      ctx.strokeStyle='#75d6c8';
      ctx.strokeRect(x(start),y(base.ceiling),Math.max(1,x(end)-x(start)),y(base.floor)-y(base.ceiling));
      description.push('Zona baze '+barDateLabel(base.start)+' – '+barDateLabel(base.end),
        'Zadnji dovršeni tjedan '+barDateLabel(base.cutoff),bars.length+' svijeća');
    }
  }
  const planStart=savedPlan?bars.findIndex(bar=>chartDay(bar.time)>=savedPlan.sessionDate):-1;
  if(planStart>=0&&savedPlan.maxEntry>savedPlan.pivot){
    const lower=Math.max(lo,savedPlan.pivot),upper=Math.min(hi,savedPlan.maxEntry);
    if(upper>lower){
      ctx.fillStyle='#80c7ff24';
      ctx.fillRect(x(planStart),y(upper),Math.max(1,x(bars.length-1)-x(planStart)),y(lower)-y(upper));
    }
  }
  if(planStart>=0&&chartDay(bars[planStart].time)===savedPlan.sessionDate){
    const anchor=x(planStart);
    ctx.strokeStyle='#a4c4de80';
    ctx.setLineDash([2,4]);
    ctx.beginPath();ctx.moveTo(anchor,top);ctx.lineTo(anchor,top+plotH);ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.lineWidth=1;ctx.textBaseline='middle';
  for(let i=0;i<4;i++){
    const frac=i/3,yy=top+frac*plotH,value=hi-frac*range;
    ctx.strokeStyle='#1c2d43';ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();
    ctx.fillStyle='#8ea0b7';ctx.textAlign='left';ctx.fillText(priceLabel(value),w-right+6,yy);
  }

  const closes=history.map(b=>b.close),e10=avg(closes,10,true).slice(offset),e20=avg(closes,20,true).slice(offset),s50=avg(closes,50,false).slice(offset);
  const candleW=Math.max(1,Math.min(5,plotW/bars.length*.7));
  bars.forEach((b,i)=>{
    const xx=x(i),up=b.close>=b.open;ctx.strokeStyle=up?'#35d78b':'#ff6d7a';ctx.fillStyle=ctx.strokeStyle;
    ctx.beginPath();ctx.moveTo(xx,y(b.high));ctx.lineTo(xx,y(b.low));ctx.stroke();
    const yy=Math.min(y(b.open),y(b.close)),bh=Math.max(1,Math.abs(y(b.open)-y(b.close)));
    ctx.fillRect(xx-candleW/2,yy,candleW,bh);
  });
  const maLines=period.weekly
    ?[[e10,'#e9bd62'],[e20,'#56a8ff'],[avg(closes,30).slice(offset),'#a67cff'],[avg(closes,40).slice(offset),'#35d78b']]
    :[[e10,'#e9bd62'],[e20,'#56a8ff'],[s50,'#a67cff']];
  maLines.forEach(([series,color])=>{
    ctx.strokeStyle=color;ctx.lineWidth=1.3;ctx.beginPath();let started=false;
    series.forEach((v,i)=>{if(v==null)return;const xx=x(i),yy=y(v);if(!started){ctx.moveTo(xx,yy);started=true}else ctx.lineTo(xx,yy)});
    if(started)ctx.stroke();
  });
  const marked=savedPlan&&planStart<0?[]:levels.filter(([price])=>Number.isFinite(price)&&price>=lo&&price<=hi);
  if(marked.length){
    const lineStart=x(savedPlan?0:Math.floor(bars.length/2));
    ctx.lineWidth=1;
    ctx.setLineDash([4,4]);
    for(const [price,,color] of marked){
      const yy=y(price);
      ctx.strokeStyle=color;ctx.beginPath();
      ctx.moveTo(lineStart,yy);ctx.lineTo(w-right,yy);ctx.stroke();
    }
    ctx.setLineDash([]);
    if(!savedPlan){
      ctx.textAlign='right';
      ctx.textBaseline='middle';
      let labelY=top-13;
      for(const [price,label,color] of marked.sort((a,b)=>b[0]-a[0])){
        labelY=Math.max(labelY+13,y(price));
        ctx.fillStyle=color;ctx.fillText(label,lineStart-6,labelY);
      }
    }
    if(savedPlan)description.push('Spremljeni '+planNames[savedPlan.strategy]+' · '+savedPlan.sessionDate);
    description.push(...marked.map(([price,label])=>label+' '+priceLabel(price)));
  }
  if(description.length)canvas.setAttribute('aria-description',description.join('. '));

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
  if(large&&w>=580){
    ctx.textAlign='center';
    ctx.fillText(period.weekly?'EMA10W / EMA20W / SMA30W / SMA40W':'EMA10 / EMA20 / SMA50',left+plotW/2,14);
    ctx.textAlign='right';
    ctx.fillText(bars.length+(period.weekly?' weeks':' sessions'),w-right,14);
  }
  return {history,bars,axis,marked};
}
function drawTickerChart(canvas,item,rows,large=false){
  const period=chartPeriods[state.chartPeriod];
  const base=state.primaryView==='weekly'&&period?.weekly?weeklyBaseRange(item,rows):null;
  draw(canvas,rows,large,undefined,chartLevels(item),base);
}
function badges(item){
  const sources=(item.sources||[]).map(s=>'<span class="badge '+(s==='kell-daily'||s==='kell-gap'?'kell':'')+'">'+esc(label(s))+'</span>').join('');
  const score=numberOrNaN(item.kell_score);
  const kell=Number.isFinite(score)?'<span class="badge kell-score">Kell '+fmt(score,0)+'</span>':'';
  const tb=trendBirthStage(item)>=2?'<span class="badge kell-score">TB '+trendBirthStage(item)+'/4</span>':'';
  const evidence=birthEvidenceBadge(item);
  return sources+kell+tb+evidence;
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
    'Evidence '+fmt(item.kell_evidence_coverage,0)+'%'+(Number.isFinite(numberOrNaN(item.kell_structural_risk_score))?' · Structural risk '+fmt(item.kell_structural_risk_score,0):''),
  ];
  if(Number.isFinite(Number(ready.structural_risk_atr)))lines.push('Natural invalidation distance '+fmt(ready.structural_risk_atr,2)+' ATR');
  if(Number.isFinite(Number(b.legacy_v4_score)))lines.push('Legacy v4 additive score '+fmt(b.legacy_v4_score,1)+' (diagnostic only)');
  if(Number(b.ttftl_penalty)>0)lines.push('TTFTL penalty -'+fmt(b.ttftl_penalty,0));
  if((b.warnings||[]).length)lines.push('Warnings: '+b.warnings.join(', '));
  return lines.join('\n');
}
function slopeIcon(value){return value==='upward'?'↑':value==='downward'?'↓':value==='flat'?'→':'—'}
function ruleAnalysis(item){
  const m=item.metrics||{},rvol=numberOrNaN(m.rvol),rsi=numberOrNaN(m.rsi14),gap=Math.abs(numberOrNaN(m.emaGapPct));
  const readiness=numberOrNaN(item.kell_readiness_score),stage=primaryStage(item);
  if(Number.isFinite(readiness)&&item.kell_stage){
    if(stage==='wedge_drop')return{status:'REVIEW',state:'KELL WEDGE DROP',preferredTrade:'Nema novog long entryja; čekati repair i novi Wedge Pop/reclaim.',summary:'Kasna/risk-off faza Kell ciklusa. Stage cap sprječava da jaki discovery signali prikriju lošu trenutnu lokaciju.'};
    if(stage==='exhaustion_extension')return{status:'WATCH',state:'KELL EXHAUSTION',preferredTrade:'Ne chaseati extension; čekati re-base, EMA reset ili novi low-risk setup.',summary:'Leader može ostati kvalitetan, ali trenutni entry readiness je namjerno ograničen late-cycle capom.'};
    if(readiness>=80)return{status:'ACTION',state:'KELL READY · '+stageName(stage),preferredTrade:'Koristi prirodnu invalidaciju setupa; ne ulaziti ako se strukturni risk previše proširi.',summary:'Kell v5 readiness je visok: stage, setup i strukturni risk su usklađeni.'};
    if(readiness>=60)return{status:'WATCH',state:'KELL WATCH · '+stageName(stage),preferredTrade:'Čekati jasniji trigger ili bolji odnos entryja prema prirodnoj invalidaciji.',summary:'Kvaliteta može biti dobra, ali entry još nije u gornjoj readiness zoni.'};
    return{status:'REVIEW',state:'KELL EARLY/LATE · '+stageName(stage),preferredTrade:'Bez forsiranog ulaza; čekati povoljniji dio Cycle of Price Action.',summary:'Discovery kvaliteta i trenutna actionability namjerno su odvojene.'};
  }
  const hh=m.higherHigh===true,hl=m.higherLow===true,trend=m.slope50==='upward'&&m.slope30w==='upward';
  const sources=item.sources||[];
  const kell=sources.includes('kell-daily')||hasKell(item,'kell_rvol_3x');
  const kellGap=sources.includes('kell-gap')||hasKell(item,'kell_gapper');
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
function activeFilterSummary(){return activeFilters().map(filterLabel).join(' + ')}
function isKellView(filters=activeFilters()){
  const list=Array.isArray(filters)?filters:[filters];
  return list.some(filter=>kellFilters.has(filter));
}
function universeMatch(item,universe=state.universe){
  if(universe==='all')return true;
  if(universe==='watchlist')return item?.savedPlans?.length||isWatched(item?.ticker);
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
  if(filter==='crash-base')return item?.metrics?.crashBaseTriggered===true;
  if(filter.startsWith('tb-path:')){
    const bucket=filter.slice('tb-path:'.length);
    return Array.isArray(trendBirthEvidence(item)[bucket])&&trendBirthEvidence(item)[bucket].length>0;
  }
  if(filter.startsWith('tb:'))return trendBirthStage(item)===Number(filter.slice(3));
  if(filter.startsWith('stage:'))return primaryStage(item)===filter.slice(6);
  if(kellFilters.has(filter))return hasKell(item,filter);
  return true;
}
function matchesFilters(item,filters=activeFilters()){
  return !filters.length||filters.every(filter=>matchesFilter(item,filter));
}
function sourceItems(filters=activeFilters()){
  if(state.universe==='watchlist')return watchlistItems();
  if(state.primaryView==='weekly')return state.data?.shortlists?.weeklyTrendBirth||[];
  if(state.primaryView==='early')return state.data?.shortlists?.earlyTrendBirth||[];
  if(state.primaryView==='kell-daily')return state.data?.shortlists?.kellSwing??state.data?.shortlists?.kellDaily??[];
  return isKellView(filters)
    ?(state.kellData?.kellCandidates||state.data?.kellCandidates||[])
    :(state.data?.candidates||[]);
}
function shortlistKey(data,view=state.primaryView){
  if(view==='early')return 'earlyTrendBirth';
  if(view==='weekly')return 'weeklyTrendBirth';
  if(view==='kell-daily')return data.shortlists?.kellSwing?'kellSwing':'kellDaily';
  return null;
}
function loadVisibleShortlist(view=state.primaryView){
  const data=state.data,key=shortlistKey(data,view);
  if(!data.deferredShortlists?.[key])return null;
  const requests=state.shortlistRequests;
  if(!requests.has(key)){
    const status={error:''};
    requests.set(key,status);
    status.request=ReviewSnapshots.loadShortlist(fetch,data,key)
      .catch(error=>{status.error=error.message})
      .finally(()=>{if(state.data===data&&shortlistKey(data)===key)render()});
  }
  return {key,...requests.get(key)};
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
    filters.map(filter=>'<button type="button" class="active-filter-chip" data-remove-filter="'+esc(filter)+'">'+esc(filterLabel(filter))+' <span aria-hidden="true">×</span></button>').join('')+
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
async function ensureResearchData(){
  if(state.data?.schemaVersion!=='trend-birth-review-bootstrap-v1')return state.data;
  if(!state.researchLoading){
    const bootstrap=state.data;
    const request=ReviewSnapshots.loadResearch(fetch,bootstrap).then(data=>{
      if(state.data===bootstrap)state.data=data;
      return data;
    }).finally(()=>{if(state.researchLoading===request)state.researchLoading=null});
    state.researchLoading=request;
  }
  return state.researchLoading;
}
async function ensureKellData(){
  if(state.kellData)return state.kellData;
  if(Array.isArray(state.data?.kellCandidates)){state.kellData=state.data;return state.kellData}
  if(state.kellLoading)return state.kellLoading;
  const reviewSource=state.data?.source||{};
  const request=KellDatasets.load(fetch,location.search,reviewSource)
    .then(data=>{
      if(state.kellLoading!==request)return data;
      const normal=new Map((state.data?.candidates||[]).map(item=>[item.ticker,item]));
      for(const item of data.kellCandidates||[]){
        const base=normal.get(item.ticker);
        if(base?.chartBars?.length)item.chartBars=base.chartBars;
      }
      state.kellData=data;
      state.kellChartShards.clear();
      state.kellChartLoading.clear();
      return data;
    })
    .finally(()=>{if(state.kellLoading===request)state.kellLoading=null});
  state.kellLoading=request;
  return state.kellLoading;
}
async function ensureKellChanges(){
  const snapshotId=state.snapshotId;
  const kell=await ensureKellData();
  if(snapshotId!==state.snapshotId)return null;
  if(state.kellChangesPreviousDate)return state.kellChangesPreviousDate;
  if(state.kellChangesLoading)return state.kellChangesLoading;
  const currentDate=state.kellData?.source?.sessionDate||state.data?.source?.sessionDate;
  const request=KellChanges.loadPrevious(fetch,currentDate,10)
    .then(previous=>{
      if(state.kellChangesLoading!==request)return null;
      KellChanges.decorate(kell?.kellCandidates||[],previous);
      state.kellChangesPreviousDate=previous.source.sessionDate;
      return state.kellChangesPreviousDate;
    })
    .finally(()=>{if(state.kellChangesLoading===request)state.kellChangesLoading=null});
  state.kellChangesLoading=request;
  return state.kellChangesLoading;
}
function changeStrip(item){
  const change=item?.kellChange;
  if(!change?.changed)return '';
  const stageMove=change.previousStage&&change.currentStage&&change.previousStage!==change.currentStage
    ?'<span>'+esc(stageName(change.previousStage))+' → '+esc(stageName(change.currentStage))+'</span>'
    :'';
  const deltas=[
    Number.isFinite(Number(change.readinessDelta))?'R '+(change.readinessDelta>=0?'+':'')+fmt(change.readinessDelta,1):'',
    Number.isFinite(Number(change.scoreDelta))?'Kell '+(change.scoreDelta>=0?'+':'')+fmt(change.scoreDelta,1):''
  ].filter(Boolean).join(' · ');
  return '<div class="change-strip"><strong>↑ CHANGED</strong><span>'+esc((change.reasons||[]).join(' · '))+'</span>'+stageMove+(deltas?'<span>'+esc(deltas)+'</span>':'')+'</div>';
}
async function ensureChartData(item,periodKey=state.chartPeriod,weeklyCutoff){
  const rows=()=>rowsForPeriod(item,periodKey,weeklyCutoff);
  const ready=rows();
  const needsPlanDaily=item?.savedPlans?.length&&chartPeriods[periodKey]?.weekly&&!(item?.chartBars?.length>=2);
  if(ready.length>=2&&!needsPlanDaily)return ready;
  if(item?.chartAvailable===false)return [];
  const watchChartBase=item?.chartBasePath||(item?.watchlistSaved&&state.publication?.watchlist?.chartBasePath);
  const data=watchChartBase?state.data:state.kellData;
  const meta=watchChartBase?{basePath:watchChartBase}:data?.kellChartData;
  const shard=Number(item?.chartShard);
  if(!meta||!Number.isInteger(shard)||shard<0)return ready;
  const base=String(meta.basePath||'data/kell-charts').replace(/\/$/,'');
  const key=base+'/'+String(shard);
  const shardCache=state.kellChartShards, pending=state.kellChartLoading;
  let payload=shardCache.get(key);
  if(!payload){
    let loading=pending.get(key);
    if(!loading){
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
          shardCache.set(key,result);
          return result;
        })
        .finally(()=>pending.delete(key));
      pending.set(key,loading);
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
  return rows();
}
function visible(item){
  if(state.query&&!item.ticker.includes(state.query))return false;
  if(!universeMatch(item))return false;
  return matchesFilters(item);
}
const swingStates={watch:'Za praćenje',triggered:'Pivot potvrđen',extended:'Iznad prihvatljivog ulaza',invalidated:'Setup poništen'};
const weeklyStages={1:'Duga baza',2:'Zbijena baza',3:'Blizu pivota',4:'Pokušaj proboja'};
function signedPct(value){
  return Number.isFinite(value)?(value>0?'+':'')+pct(value):'—';
}
function weeklyEvidence(item,detail=false){
  const metrics=item.weeklyBirth?.metrics||{};
  const weekly=rowsForPeriod(item,'base',metrics.historyEnd);
  const close=chartDay(weekly.at(-1)?.time)===metrics.historyEnd?weekly.at(-1)?.close:null;
  const pivot=metrics.pivotPrice,resistance=metrics.resistancePrice;
  const distance=level=>Number.isFinite(level)&&close>0?' · '+signedPct(100*(level/close-1)):'';
  const base=detail?weeklyBaseRange(item,weekly):null;
  return '<div class="metrics weekly-evidence">'+
    '<span>Prozor baze <b>'+fmt(metrics.baseWeeks,0)+' tj.</b></span>'+
    '<span>Dubina <b>'+pct(metrics.baseDepthPct)+'</b></span>'+
    '<span>Pivot <b>'+fmt(pivot)+'</b>'+distance(pivot)+'</span>'+
    '<span>Prvi otpor <b>'+(Number.isFinite(resistance)?fmt(resistance):'nije uočen')+'</b>'+distance(resistance)+'</span>'+
    (Number.isFinite(close)?'<span class="weekly-close">Tjedno zatvaranje '+esc(barDateLabel(metrics.historyEnd))+
      ' <b>'+fmt(close)+'</b></span>':'')+
    (base?'<span class="weekly-close">Dno baze <b>'+priceLabel(base.floor)+'</b> · '+barDateLabel(base.floorBar.time)+
      ' · taj tjedan zatvorio na '+priceLabel(base.floorBar.close)+'</span>':'')+
    (base?.lastBelowFloor?'<span class="weekly-close">Zadnje zatvaranje ispod dna u 8 tj. · '+
      barDateLabel(base.lastBelowFloor.time)+' <b>'+priceLabel(base.lastBelowFloor.close)+'</b></span>':'')+
    '</div>';
}
const earlyPhases={stabilizing:'Stabilizacija',reclaim:'Povrat iznad razine',confirmed:'Potvrđen zaokret'};
const earlyEvidence={
  support_retest:'Ponovljen test podrške',higher_low:'Više dno',support_reclaim:'Povrat iznad podrške',
  range_compression:'Uži dnevni rasponi',relative_strength_turn:'Oporavak relativne snage',
};
const planNames={early:'Early Trend Birth',kell:'Kell Swing'};
const planStatus={
  saved:'Čeka se prvo dnevno zatvaranje nakon izvorne snimke.',
  revision:'Ista sesija, novija snimka. Razine su iz izvorne objave.',
  earlier:'Prikazani EOD prethodi spremljenom planu.',
  calendar:'Burzovne sesije nisu provjerene.',
  coverage:'Nedostaju dnevne cijene za usporedbu.',
  priceBasis:'Cijena u sesiji spremanja naknadno je promijenjena. Provjeri izvorni graf.',
  abovePivot:'Zatvaranje je na pivotu ili iznad njega.',
  belowPivot:'Zatvaranje je ispod pivota.',
  extended:'Zatvaranje je iznad maksimalnog ulaza.',
};
function sourcePlanLink(plan,snapshotId=plan.snapshotId,label='Izvorna snimka '+plan.sessionDate){
  const url=new URL(location.pathname,location.origin);
  url.searchParams.set('snapshot',snapshotId);
  ReviewNavigation.write(url,{view:plan.strategy==='kell'?'kell-daily':'early',ticker:plan.ticker});
  return '<a href="'+esc(url.search)+'" target="_blank" rel="noopener">'+esc(label)+'</a>';
}
function planLevelsText(plan){
  return 'Izvorno zatvaranje <b>'+fmt(plan.price)+'</b> · Pivot <b>'+fmt(plan.pivot)+'</b> · '+
    (plan.strategy==='kell'?'Stop':'Poništenje')+' <b>'+fmt(plan.invalidation)+'</b>'+
    (plan.maxEntry!=null?' · Maks. ulaz <b>'+fmt(plan.maxEntry)+'</b>':'');
}
function planEventRows(plan,events,interactive=false){
  const labels={abovePivot:plan.maxEntry!=null?'Prvo zatvaranje u zoni ulaza':'Prvo zatvaranje na pivotu ili iznad njega',
    extended:'Prvo zatvaranje iznad maksimalnog ulaza',invalidated:'Prvo zatvaranje na ili ispod zaštitne razine'};
  return events.map(event=>{
    const label=labels[event.state];
    const row='<time datetime="'+esc(event.day)+'">'+esc(event.day)+'</time> · <strong>'+fmt(event.close)+'</strong><span>'+label+'</span>';
    return '<li>'+(interactive?'<button type="button" data-plan-candle="'+esc(event.day)+'" aria-label="Otvori svijeću '+
      esc(event.day)+' · '+label+'">'+row+'</button>':row)+'</li>';
  }).join('');
}
function planQuotes(item){
  return normalizeBars(item.chartBars||[]).flatMap(bar=>{
    const day=barDate(bar.time)?.toISOString().slice(0,10);
    return day?[{day,close:bar.close}]:[];
  });
}
function planSaveControl(item,strategy){
  const plan=strategy==='early'?item.earlyTrend:item.kellSwing;
  if(!state.snapshotId||!plan||plan.state==='invalidated'||plan.sessionDate!==state.data.source?.sessionDate)return '';
  const saved=state.savedPlans?.some(entry=>!entry.archivedAt&&entry.ticker===item.ticker&&entry.strategy===strategy);
  return '<button type="button" class="plan-action" data-plan-action="save" data-strategy="'+strategy+'"'+
    (saved?' disabled':'')+'>'+(saved?'Plan spremljen':'Spremi plan')+'</button>';
}
function renderSavedPlans(item,inDetail=false){
  return (item.savedPlans||[]).map(plan=>{
    const reason=plan.strategy==='early'?plan.evidence.map(key=>earlyEvidence[key]).filter(Boolean).join(' · '):
      (kellSetupLabels['kell_'+plan.setup]||'');
    const placement=ownerPlanScope?.book?(cloudPlan(ReviewPlans.planId(plan))?'Na računu':'Na uređaju'):'';
    return '<section class="saved-plan" data-saved-plan="'+esc(ReviewPlans.planId(plan))+'">'+
      '<div class="saved-plan-heading"><strong>'+planNames[plan.strategy]+'</strong>'+sourcePlanLink(plan)+'</div>'+
      (placement||reason?'<small>'+esc([placement,reason].filter(Boolean).join(' · '))+'</small>':'')+
      '<p>'+planLevelsText(plan)+'</p>'+
      '<p class="saved-plan-status" data-plan-status>Učitavam usporedbu s izvornim planom…</p>'+
      '<details class="saved-plan-journal" data-plan-journal hidden'+(inDetail?' open':'')+'>'+
      '<summary>Dnevnik zatvaranja</summary><ol></ol></details>'+
      '<button type="button" class="plan-action" data-plan-action="archive" disabled>Arhiviraj plan</button></section>';
  }).join('');
}
function renderPlanArchive(){
  const plans=state.savedPlans.filter(plan=>plan.archivedAt);
  const shown=state.primaryView==='watchlist'&&plans.length>0;
  $('#planStorageNote').hidden=state.primaryView!=='watchlist'||!state.savedPlans.length||Boolean(ownerPlanScope);
  const panel=$('#savedPlanArchive'),list=$('#archivedPlanList');
  panel.hidden=!shown;
  panel.querySelector('summary').textContent='Arhivirani planovi'+(shown?' ('+plans.length+')':'');
  const expanded=new Set([...list.querySelectorAll('details[open]')].map(node=>node.dataset.archivedPlan));
  list.innerHTML=shown?plans.sort((a,b)=>String(b.archivedAt).localeCompare(String(a.archivedAt))).map(plan=>{
    const id=ReviewPlans.planId(plan),review=ReviewPlans.archivedReview(plan);
    const status=review?.state==='invalidated'?'Plan poništen.':planStatus[review?.state];
    return '<li><details data-archived-plan="'+esc(id)+'"'+(expanded.has(id)?' open':'')+'><summary><strong>'+
      esc(plan.ticker)+'</strong> · '+planNames[plan.strategy]+(status?'<span>'+status+'</span>':'')+'</summary>'+
      '<div class="archived-plan-body"><p>'+planLevelsText(plan)+'</p><p class="archived-plan-links">'+sourcePlanLink(plan)+
      (review?sourcePlanLink(plan,review.snapshotId,'Zadnja provjera '+review.asOf):'')+'</p>'+
      (review?'<p>Zadnje provjereno zatvaranje <b>'+fmt(review.close)+'</b></p>'+
        (review.events.length?'<ol class="archived-plan-events" aria-label="Dnevnik zatvaranja">'+planEventRows(plan,review.events)+'</ol>':
          '<p class="archived-plan-note">Do te sesije nema zabilježenog događaja.</p>'):
        '<p class="archived-plan-note">Nema spremljene provjere nakon izvorne sesije.</p>')+'</div></details></li>';
  }).join(''):'';
}
function updateSavedPlanStatuses(host,item){
  if(!item.savedPlans?.length)return;
  const quotes=planQuotes(item);
  const assessments=new Map();
  for(const section of host.querySelectorAll('[data-saved-plan]')){
    const plan=item.savedPlans.find(entry=>ReviewPlans.planId(entry)===section.dataset.savedPlan);
    if(!plan)continue;
    const result=ReviewPlans.assess(plan,quotes,state.data.source?.sessionDate,freshnessCalendar,state.snapshotId);
    assessments.set(section.dataset.savedPlan,result);
    const node=section.querySelector('[data-plan-status]');
    const journal=section.querySelector('[data-plan-journal]');
    const review=!archived&&state.publication?.snapshotId===state.snapshotId?
      ReviewPlans.closingReview(plan,state.snapshotId,result):null;
    section.closingReview=review;
    if(review){
      try{if(!queueOwnerPlanReview(plan,review))ReviewPlans.rememberReview(window.localStorage,state.ownerSession?.user?.id,plan,review)}
      catch(_error){/* The displayed review is still available when archiving. */}
    }
    section.querySelector('[data-plan-action="archive"]').disabled=false;
    node.dataset.state=result.state;
    if(result.state==='invalidated'){
      node.textContent='Poništenje na zatvaranju '+result.day+' · '+fmt(result.close)+
        (result.asOf!==result.day?' · '+result.asOf+' · zadnje zatvaranje '+fmt(result.currentClose):'');
    }else{
      node.textContent=planStatus[result.state]+(result.asOf?' · '+result.asOf+' · '+fmt(result.close)+' · '+
        (result.pivotDeltaPct>=0?'+':'')+pct(result.pivotDeltaPct)+' od pivota':'');
    }
    journal.hidden=!result.events?.length;
    journal.querySelector('ol').innerHTML=planEventRows(plan,result.events||[],true);
  }
  return assessments;
}
function planCandleTarget(event){
  const button=event.target.closest('[data-plan-candle]');
  if(button)return {day:button.dataset.planCandle,id:button.closest('[data-saved-plan]').dataset.savedPlan};
}
function planAction(event,item){
  const button=event.target.closest('[data-plan-action]');
  if(!button||!item)return false;
  if(button.disabled)return true;
  button.disabled=true;
  const inDetail=Boolean(button.closest('#detail'));
  const account=state.ownerSession?.user?.id;
  const scope=ownerPlanScope,saving=button.dataset.planAction==='save';
  (async()=>{
    try{
      let onAccount=false;
      if(saving){
        const plan=ReviewPlans.capture(item,button.dataset.strategy,state.snapshotId,state.data.source?.sessionDate,planQuotes(item));
        if(!plan)throw Error('Za spremanje plana potrebni su razine i zaključen dnevni graf iz iste snimke.');
        if(scope?.book){
          const previous=cloudPlan(ReviewPlans.planId(plan));
          await changeOwnerPlanBook(scope,rows=>OwnerPlanBook.savePlan(rows,plan,previous?.archivedAt));
          onAccount=true;
        }else if(!ReviewPlans.save(window.localStorage,account,plan)){
          throw Error('Za ovaj ticker i strategiju već postoji aktivan plan.');
        }
      }else{
        const section=button.closest('[data-saved-plan]'),id=section.dataset.savedPlan;
        if(cloudPlan(id)){
          await changeOwnerPlanBook(scope,rows=>OwnerPlanBook.archivePlan(rows,id,section.closingReview));
          onAccount=true;
        }else ReviewPlans.archive(window.localStorage,account,id,section.closingReview);
      }
      if(account!==state.ownerSession?.user?.id)return;
      const sameDetail=inDetail&&button.isConnected&&$('#detail').open;
      render();
      if(sameDetail&&saving){show(item,state.detailView);return}
      if(sameDetail)closeReviewDetail();
      const notice=$('#planNotice');
      notice.textContent=saving?(onAccount?'Plan je spremljen na račun.':'Plan je spremljen u ovom pregledniku.')+
        ' Otvori Watchlistu za praćenje.':onAccount?'Plan je arhiviran na računu.':'Plan je arhiviran.';
      notice.hidden=false;
    }catch(error){
      if(account!==state.ownerSession?.user?.id)return;
      const notice=inDetail&&button.isConnected&&$('#detail').open?$('#detail [data-plan-notice]'):$('#planNotice');
      notice.textContent=error?.name==='QuotaExceededError'?'Nema prostora za spremanje plana u pregledniku.':
        error?.message||'Promjena plana nije potvrđena.';
      notice.hidden=false;
    }finally{
      if(button.isConnected)button.disabled=false;
    }
  })();
  return true;
}
function earlyPlan(item){
  const info=item.earlyTrend;
  if(!info)return '';
  const evidence=(info.evidence||[]).map(key=>earlyEvidence[key]).filter(Boolean);
  return '<section class="swing-plan early-plan" aria-label="Trend Birth dokazi">'+
    '<div class="swing-plan-title"><strong>'+esc(earlyPhases[info.phase]||'Trend Birth')+'</strong><small>'+
    esc(info.sessionDate)+'</small></div>'+
    '<ul>'+evidence.map(label=>'<li>'+esc(label)+'</li>').join('')+'</ul>'+
    '<div class="swing-levels">'+
      '<div><small>Podrška baze</small><b>'+fmt(info.baseSupport)+'</b></div>'+
      '<div><small>Poništenje teze</small><b>'+fmt(info.invalidation)+'</b></div>'+
      '<div><small>Pivot oporavka</small><b>'+fmt(info.reclaimPivot)+'</b></div>'+
      '<div><small>RS prema SPY-u · 20D</small><b>'+pct(info.relativeStrength20Pct)+'</b></div>'+
      '<div><small>Tjedna baza</small><b>'+(info.weeklyBaseWeeks==null?'—':fmt(info.weeklyBaseWeeks,0)+' tj.')+'</b></div>'+
      '<div><small>Potvrda dnevnog radara</small><b>'+fmt(info.dailyStage,0)+'/4</b></div>'+
    '</div>'+planSaveControl(item,'early')+'</section>';
}
const swingReasons={
  price_or_cycle_invalidation:'Cijena ili faza poništava plan.',
  insufficient_liquidity:'Promet ili cijena ispod praga.',
  risk_too_wide:'Stop je preširok za ovaj plan.',
  above_max_entry:'Zatvaranje iznad granice ulaza.',
  pivot_closed_above:'Potvrđeno na zatvaranju. Prvi mogući nalog je iduće sesije.',
  below_pivot:'Cijena je ispod pivota.',
};
function swingPlan(item){
  const plan=item.kellSwing;
  if(!plan)return '';
  const setup=(kellSetupLabels['kell_'+plan.setup]||plan.setup).replace(/ setup$/,'');
  return '<section class="swing-plan" aria-label="Kell swing plan">'+
    '<div class="swing-plan-title"><strong>'+esc(setup)+'</strong><span data-swing-state="'+esc(plan.state)+'">'+
    esc(swingStates[plan.state]||'—')+'</span></div>'+
    '<small>'+esc(stageName(plan.phase))+' · '+esc(plan.sessionDate)+'</small>'+
    '<div class="swing-levels">'+
      '<div><small>Pivot</small><b>'+fmt(plan.pivot)+'</b></div>'+
      '<div><small>Stop</small><b>'+fmt(plan.stop)+'</b></div>'+
      '<div><small>Maks. ulaz</small><b>'+fmt(plan.maxEntry)+'</b></div>'+
      '<div><small>Rizik kod pivota</small><b>'+pct(plan.riskPct)+'</b></div>'+
      '<div><small>Gap sesije</small><b>'+pct(plan.gapPct)+'</b></div>'+
    '</div><small>'+esc(swingReasons[plan.reason]||'')+'</small>'+planSaveControl(item,'kell')+'</section>';
}

function card(item){
  const m=item.metrics||{},a=analysisFor(item),missing=item.watchlistMissing===true;
  const status=missing?'SAVED':String(a.status||'REVIEW').toUpperCase();
  const gap=item.kellGap||{gapPct:item.kell_metrics?.gap_pct};
  const stage=stageName(primaryStage(item));
  const setups=kellSetupsText(item);
  const watched=isWatched(item.ticker);
  const sources=item.sources||[];
  if(state.primaryView==='early'&&item.earlyTrend){
    return '<article class="card early-card" tabindex="0" data-ticker="'+esc(item.ticker)+'">'+
      '<div class="card-head"><div class="ticker-wrap"><button class="watch-star'+(watched?' active':'')+
      '" type="button" data-watch-ticker="'+esc(item.ticker)+'" aria-label="'+(watched?'Makni ':'Dodaj ')+
      esc(item.ticker)+(watched?' iz Watchliste':' na Watchlistu')+'" aria-pressed="'+String(watched)+'">'+
      (watched?'★':'☆')+'</button><div class="ticker">'+esc(item.ticker)+'</div></div>'+
      '<b>'+fmt(m.price)+'</b></div>'+earlyPlan(item)+
      '<canvas aria-label="'+esc(item.ticker)+' graf baze"></canvas></article>';
  }
  if(state.primaryView==='weekly'){
    const w=item.weeklyBirth||{};
    return '<article class="card weekly-card" tabindex="0" data-ticker="'+esc(item.ticker)+'">'+
      '<div class="card-head"><div class="ticker-wrap"><button class="watch-star'+(watched?' active':'')+'" type="button" data-watch-ticker="'+esc(item.ticker)+'" aria-label="'+(watched?'Makni ':'Dodaj ')+esc(item.ticker)+(watched?' iz Watchliste':' na Watchlistu')+'" aria-pressed="'+(watched?'true':'false')+'">'+(watched?'★':'☆')+'</button><div class="ticker">'+esc(item.ticker)+'</div></div><div class="badges"><span class="badge kell-score">'+esc(weeklyStages[w.stage]||w.stageLabel||'Tjedna baza')+'</span><span class="badge">'+fmt(w.score,0)+'/100</span></div></div>'+
      weeklyEvidence(item)+
      '<canvas aria-label="'+esc(item.ticker)+' tjedni graf" title="Otvori graf i detalje"></canvas></article>';
  }
  if(state.primaryView==='kell-daily'&&item.kellSwing){
    return '<article class="card swing-card" tabindex="0" data-ticker="'+esc(item.ticker)+'">'+
      '<div class="card-head"><div class="ticker-wrap"><button class="watch-star'+(watched?' active':'')+
      '" type="button" data-watch-ticker="'+esc(item.ticker)+'" aria-label="'+(watched?'Makni ':'Dodaj ')+
      esc(item.ticker)+(watched?' iz Watchliste':' na Watchlistu')+'" aria-pressed="'+String(watched)+'">'+
      (watched?'★':'☆')+'</button><div class="ticker">'+esc(item.ticker)+'</div></div>'+
      '<b>'+fmt(m.price)+'</b></div>'+swingPlan(item)+
      '<canvas aria-label="'+esc(item.ticker)+' dnevni graf"></canvas></article>';
  }
  return '<article class="card'+(missing?' watchlist-stale':'')+'" tabindex="0" data-ticker="'+esc(item.ticker)+'">'+
    '<div class="card-head"><div class="ticker-wrap"><button class="watch-star'+(watched?' active':'')+'" type="button" data-watch-ticker="'+esc(item.ticker)+'" aria-label="'+(watched?'Makni ':'Dodaj ')+esc(item.ticker)+(watched?' iz Watchliste':' na Watchlistu')+'" aria-pressed="'+(watched?'true':'false')+'">'+(watched?'★':'☆')+'</button><div class="ticker">'+esc(item.ticker)+'</div></div><div class="badges">'+badges(item)+'</div></div>'+changeStrip(item)+
    (missing?'<div class="watchlist-missing">Nema podataka za ticker u prikazanom EOD-u.</div>':item.watchlistUnifiedOnly?'<div class="watchlist-current">U današnjem Unified scanu · trenutačno nema aktivni Review/Kell hit</div>':'')+
    (item.watchlistUnavailable?'<div class="watchlist-missing">'+(state.watchlistLookup.error?'Podaci trenutačno nedostupni':'Učitavam podatke tickera…')+'</div>':'')+
    renderSavedPlans(item)+
    (item.chartAvailable===false?'<div class="watchlist-current" role="status">Graf trenutačno nije dostupan u ovoj objavi</div>':'')+
    '<div class="metrics"><span>Px <b>'+fmt(m.price)+'</b></span><span>RVOL <b>'+fmt(m.rvol)+'x</b></span><span>RSI <b>'+fmt(m.rsi14,1)+'</b></span><span>EMA gap <b>'+pct(m.emaGapPct)+'</b></span><span>Kell <b>'+fmt(item.kell_score,0)+'</b></span><span>TB <b>'+trendBirthStage(item)+'/4</b></span>'+(sources.includes('kell-gap')?'<span>Gap <b>'+pct(gap.gapPct)+'</b></span>':'')+'</div>'+
    '<div class="metrics kell-dimensions"><span>Stage <b>'+esc(stage)+'</b></span><span>Q / R / C <b>'+fmt(item.kell_quality_score,0)+' / '+fmt(item.kell_readiness_score,0)+' / '+fmt(item.kell_context_score,0)+'</b></span><span>Evidence <b>'+fmt(item.kell_evidence_coverage,0)+'%</b></span></div>'+
    '<div class="metrics kell-dimensions"><span>Setup <b>'+esc(setups)+'</b></span></div>'+
    '<canvas aria-label="'+esc(item.ticker)+' chart" title="Tap/click za analizu"></canvas>'+
    '<div class="metrics structure"><span>50D <b>'+slopeIcon(m.slope50)+'</b></span><span>30W <b>'+slopeIcon(m.slope30w)+'</b></span><span>Swing <b>'+esc(m.swingState||'—')+'</b></span><span>Base <b>'+(m.baseLike===true?'✓':m.baseLike===false?'—':'?')+'</b></span></div>'+
    '<div class="analysis-strip"><span>'+esc(a.state||m.setup||'—')+'</span><strong class="'+(status==='ACTION'?'action':status==='WATCH'?'watch':'')+'">'+esc(status)+'</strong></div>'+
    '</article>';
}
let observer;
function renderChangeHighlights(items){
  const box=$('#changeHighlights');
  if(!box)return;
  if(state.quickView!=='changed'){
    box.hidden=true;
    box.innerHTML='';
    state.changeHighlightsExpanded=false;
    return;
  }
  const fresh=(items||[])
    .filter(item=>item?.kellChange?.newCandidate===true)
    .sort((a,b)=>Number(b?.kellChange?.priority||0)-Number(a?.kellChange?.priority||0)||Number(b?.kell_score||0)-Number(a?.kell_score||0)||a.ticker.localeCompare(b.ticker));
  if(!fresh.length){
    box.hidden=true;
    box.innerHTML='';
    return;
  }
  const visible=state.changeHighlightsExpanded?fresh:fresh.slice(0,8);
  const chips=visible.map(item=>{
    const reason=(item?.kellChange?.reasons||[]).join(' · ');
    const title=[reason,'Kell '+fmt(item.kell_score,0),'TB '+trendBirthStage(item)+'/4'].filter(Boolean).join(' · ');
    return '<button type="button" class="new-relevant-chip" data-change-ticker="'+esc(item.ticker)+'" title="'+esc(title)+'"><strong>'+esc(item.ticker)+'</strong><span>K'+fmt(item.kell_score,0)+' · TB'+trendBirthStage(item)+'</span></button>';
  }).join('');
  const more=!state.changeHighlightsExpanded&&fresh.length>visible.length
    ?'<button type="button" class="new-relevant-more" data-change-more>+'+(fresh.length-visible.length)+' više</button>'
    :'';
  box.hidden=false;
  box.innerHTML='<div class="change-highlights-head"><strong>NEW RELEVANT · '+fresh.length+'</strong><span>Novi Kell-relevant kandidati u odnosu na prethodni snapshot</span></div><div class="change-highlight-chips">'+chips+more+'</div>';
}
function render(){
  if(!state.data)return;
  state.savedPlans=OwnerPlanBook.projection(ReviewPlans.load(window.localStorage,state.ownerSession?.user?.id),ownerPlanScope?.book?.plans);
  renderPlanArchive();
  updateOwnerPlanUi();
  $('#chartPeriod option[value="base"]').hidden=state.primaryView!=='weekly';
  loadWatchedRows();
  const shortlist=loadVisibleShortlist();
  const researchControls=state.primaryView==='research';
  $('#filters').hidden=!researchControls;
  $('#quickViews').hidden=!researchControls;
  $('#mobileFiltersToggle').hidden=!researchControls;
  updateWatchlistButton();
  updateFilterBar();
  updateQuickViews();
  updateMobileFilterToggle();
  updateFilterCounts();
  document.querySelectorAll('#primaryViews [data-primary-view]').forEach(button=>{const selected=button.dataset.primaryView===state.primaryView;button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected))});
  const items=sourceItems().filter(visible);
  const sortMode=state.sort==='default'&&isKellView()?'kell-score':state.sort;
  const sortValue=(item,mode)=>{
    if(mode==='kell-score')return Number(item.kell_score);
    if(mode==='change')return Number(item.kellChange?.priority);
    if(mode==='readiness')return Number(item.kell_readiness_score);
    if(mode==='quality')return Number(item.kell_quality_score);
    if(mode==='trend-birth')return trendBirthStage(item)*1000+Number(item.kell_score||0);
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
  renderChangeHighlights(items);
  $('#grid').innerHTML=items.map(card).join('');
  const universeName=universeLabels[state.universe]||state.universe;
  const modeCounts=state.kellData?.source?.modeUniverseCounts||state.data?.source?.modeUniverseCounts||{};
  const unifiedCount=state.kellData?.kellScoring?.unifiedCandidateCount??state.data?.kellScoring?.unifiedCandidateCount;
  const universeSize=state.universe==='watchlist'?state.watchlist.length:(state.universe==='all'?unifiedCount:modeCounts[state.universe]);
  const universeText=universeName+(Number.isFinite(Number(universeSize))?' ('+Number(universeSize)+' candidates)':'');
  const filterSummary=activeFilterSummary();
  if(shortlist){
    $('#status').textContent=shortlist.error||'Učitavam listu i grafikone…';
    if(shortlist.error){
      const retry=document.createElement('button');
      retry.type='button';
      retry.textContent='Ponovi učitavanje';
      retry.onclick=()=>{state.shortlistRequests.delete(shortlist.key);render()};
      $('#status').append(' · ',retry);
    }
  }else if(state.primaryView==='weekly'){
    $('#status').textContent=items.length+' kandidata s dugom konsolidacijom.'+
      (chartPeriods[state.chartPeriod]?.weekly?' Obojena zona prikazuje bazu prije zadnjih osam završenih tjedana.':'');
  }else if(state.primaryView==='early'){
    $('#status').textContent=Array.isArray(state.data?.shortlists?.earlyTrendBirth)?
      items.length+' kandidata za rani zaokret':'Ova snimka još nema listu ranih zaokreta.';
  }else if(state.primaryView==='kell-daily'){
    const active=items.filter(item=>item.kellSwing?.state==='triggered').length;
    $('#status').textContent=Array.isArray(state.data?.shortlists?.kellSwing)
      ?items.length+' swing planova · '+active+' s potvrđenim pivotom'
      :items.length+' arhivskih Kell kandidata';
    const link=document.createElement('a');
    link.href='statistics.html#siKell';
    link.textContent='Provjera planova';
    link.className='analysis-jump';
    $('#status').append(' · ',link);
  }else if(state.quickView==='changed'){
    const changeSummary=KellChanges.summary(items);
    const currentDate=state.kellData?.source?.sessionDate||state.data?.source?.sessionDate||'—';
    $('#status').textContent=items.length+' important changes · '+(state.kellChangesPreviousDate||'prior')+' → '+currentDate+' · '+changeSummary.becameReady+' became Ready · '+changeSummary.newSetups+' new actionable setups · '+changeSummary.newCandidates+' new relevant names';
  }else if(state.universe==='watchlist'){
    const missing=items.filter(item=>item.watchlistMissing).length;
    const unifiedOnly=items.filter(item=>item.watchlistUnifiedOnly).length;
    const planCount=state.savedPlans.filter(plan=>!plan.archivedAt).length;
    $('#status').textContent=items.length+' prikazano · '+state.watchlist.length+' spremljeno na Watchlisti'+
      (planCount?' · '+planCount+' aktivnih planova':'')+
      (unifiedOnly?' · '+unifiedOnly+' još je u Unified universeu bez aktivnog hita':'')+(missing?' · '+missing+' više nije u današnjem Unified scanu':'')+(filterSummary?' · '+filterSummary:'');
    if(state.watchlistLookup.error){
      const retry=document.createElement('button');
      retry.className='watchlist-retry';
      retry.type='button';
      retry.textContent='Ponovi učitavanje';
      retry.title=state.watchlistLookup.error;
      retry.onclick=()=>{state.watchlistLookup.error='';render()};
      $('#status').append(' · ',retry);
    }
  }else if(filterSummary){
    $('#status').textContent=items.length+' pogodaka · '+universeText+' → '+filterSummary;
  }else{
    $('#status').textContent=items.length+' review kandidata · Universe '+universeText+' · odaberi više Screen / Stage / Setup filtera za AND presjek';
  }
  const missingCharts=state.kellData?.kellChartData?.missingChartCount||0;
  if(missingCharts)$('#status').textContent+=' · '+missingCharts+' nedostupnih grafova u objavi';
  observer?.disconnect();
  const lookup=new Map(items.map(item=>[item.ticker,item]));
  observer=new IntersectionObserver(entries=>{
    for(const entry of entries){
      if(!entry.isIntersecting)continue;
      const canvas=entry.target,cardEl=canvas.closest('.card'),item=lookup.get(cardEl.dataset.ticker);
      observer.unobserve(canvas);
      const ready=rowsForPeriod(item);
      if(ready.length>=2){
        drawTickerChart(canvas,item,ready);
        if(!item.savedPlans?.length||item.chartBars?.length>=2){
          updateSavedPlanStatuses(cardEl,item);
          continue;
        }
      }else draw(canvas,[],false,'Loading chart…');
      ensureChartData(item)
        .then(rows=>{if(canvas.isConnected){drawTickerChart(canvas,item,rows);updateSavedPlanStatuses(cardEl,item)}})
        .catch(err=>{if(canvas.isConnected){canvas.title='Chart load error: '+err.message;draw(canvas,[],false,'Chart load failed');updateSavedPlanStatuses(cardEl,item)}})
    }
  },{rootMargin:'240px'});
  document.querySelectorAll('.card').forEach(cardEl=>{
    const item=lookup.get(cardEl.dataset.ticker),canvas=cardEl.querySelector('canvas');
    observer.observe(canvas);
    const open=()=>item&&show(item);
    const star=cardEl.querySelector('[data-watch-ticker]');
    star?.addEventListener('click',async e=>{e.preventDefault();e.stopPropagation();if(star.disabled)return;star.disabled=true;try{await toggleWatchlist(star.dataset.watchTicker)}finally{star.disabled=false}});
    canvas.addEventListener('click',e=>{e.stopPropagation();open()});
    cardEl.addEventListener('click',e=>{
      const jump=planCandleTarget(e);
      if(jump){show(item,state.primaryView,{period:'1y',jump});return}
      if(e.target.closest('[data-watch-ticker]')||e.target.closest('a,[data-plan-journal]')||planAction(e,item))return;
      open();
    });
    cardEl.addEventListener('keydown',e=>{if(e.target.closest('[data-watch-ticker],[data-plan-action],a,[data-plan-journal]'))return;if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}});
  });
}
function fact(name,value){return '<div class="fact"><span>'+esc(name)+'</span>'+esc(value??'—')+'</div>'}
const reviewChangeTitles={
  level_broken:'Zatvaranje na ili ispod prethodne zaštitne razine',
  invalidated:'Setup poništen',triggered:'Pivot potvrđen na zatvaranju',advanced:'Napredovala faza oporavka',
  extended:'Iznad granice ulaza',appeared:'Pojavio se setup',lost:'Setup više nije potvrđen',
  state_changed:'Promijenjeno stanje',setup_changed:'Promijenjen tip setupa',
  left_list:'Ispao iz kratke liste',joined_list:'Ušao u kratku listu'
};
let reviewChangeView='early',reviewChangeLimit=6,reviewChangeRequest=null,reviewChangeData=null;
let reviewChangeDetail=null;
function changeStateLabel(row){
  if(!row.state)return 'Bez potvrđenog setupa';
  const phase=(reviewChangeView==='early'?earlyPhases:swingStates)[row.state]||row.state;
  const setup=row.setup?kellSetupLabels['kell_'+row.setup]:null;
  return phase+(setup?' · '+setup:'');
}
function changeRow(row,changed){
  const from=row.before,to=row.after||row;
  const detail=changed?changeStateLabel(from)+' → '+changeStateLabel(to):changeStateLabel(to);
  const close=changed?(from.close==null?'—':priceLabel(from.close))+' → '+priceLabel(to.close):
    (to.close==null?'':priceLabel(to.close));
  const title=changed?reviewChangeTitles[row.kind]:'';
  return '<li><button class="review-change-ticker" type="button" data-review-change-ticker="'+esc(row.ticker)+'">'+
    '<span><strong>'+esc(row.ticker)+'</strong> <span class="review-change-kind">'+esc(title||detail)+'</span></span>'+
    '<span class="review-change-price">'+esc(close)+'</span>'+
    (changed?'<small>'+esc(detail)+(row.priorLevel==null?'':' · Prethodna zaštitna razina '+priceLabel(row.priorLevel))+'</small>':'')+
    (changed&&from.listed!==to.listed?'<small>'+(to.listed?'U kratkoj listi':'Izvan kratke liste')+'</small>':'')+
    '</button></li>';
}
function renderReviewChanges(){
  const panel=$('#reviewChanges'),rows=$('#reviewChangeRows');
  for(const button of panel.querySelectorAll('[data-review-change-view]')){
    button.setAttribute('aria-pressed',String(button.dataset.reviewChangeView===reviewChangeView));
  }
  const report=reviewChangeData?.strategies[reviewChangeView];
  if(!report){rows.textContent='Učitavam EOD pregled…';return}
  const current=barDateLabel(reviewChangeData.source.sessionDate);
  const compared=report.status==='compared';
  const shown=compared?report.events:report.current;
  const subtitle=compared?
    barDateLabel(reviewChangeData.previousSession)+' → '+current+' · '+report.compared+' uspoređenih tickera · '+report.count+' promjena':
    current+' · '+(report.status==='no_baseline'?'Prethodna sesija nema usporedivu verziju ove strategije.':
      report.status==='no_overlap'?'Nema tickera s provjerenim zatvaranjem u obje sesije.':'Strategija nije dostupna u ovoj snimci.');
  rows.innerHTML='<p class="review-change-caption">'+esc(subtitle)+'</p>'+
    (!compared&&shown.length?'<h2>Trenutačna kratka lista</h2>':'')+
    (shown.length?'<ul>'+shown.slice(0,reviewChangeLimit).map(row=>changeRow(row,compared)).join('')+'</ul>':
      compared?'<p>Nema promjena među uspoređenim tickerima.</p>':'')+
    (shown.length>reviewChangeLimit?'<button type="button" class="review-change-more" data-review-change-more>Prikaži još '+(shown.length-reviewChangeLimit)+'</button>':'')+
    (report.count>report.events.length?'<p class="review-change-caption">Prikaz prvih '+report.events.length+' po važnosti.</p>':'');
}
function loadReviewChanges(){
  if(reviewChangeRequest||reviewChangeData||!state.publication?.changes)return;
  const manifest=state.publication;
  renderReviewChanges();
  const request=ReviewSnapshots.loadChanges(fetch,manifest)
    .then(result=>{
      if(state.publication!==manifest)return;
      reviewChangeData=result;
      renderReviewChanges();
    }).catch(()=>{
      if(state.publication===manifest)$('#reviewChangeRows').innerHTML=
        '<p>Pregled promjena trenutačno se ne može učitati.</p><button type="button" class="review-change-more" data-review-change-retry>Pokušaj ponovno</button>';
    }).finally(()=>{if(reviewChangeRequest===request)reviewChangeRequest=null});
  reviewChangeRequest=request;
}
async function openReviewChange(button){
  const manifest=state.publication,data=state.data,view=reviewChangeView==='kell'?'kell-daily':'early';
  const ticker=button.dataset.reviewChangeTicker,notice=$('#reviewChangeNotice');
  const current=data.shortlists?.[view==='early'?'earlyTrendBirth':'kellSwing']?.find(item=>item.ticker===ticker);
  reviewChangeDetail=button;
  notice.hidden=true;
  if(current){show(current,view);return}
  button.disabled=true;
  try{
    const rows=await ReviewSnapshots.loadWatchlist(fetch,manifest,[ticker],state.watchlistLookup.cache);
    if(state.data!==data||reviewChangeDetail!==button||!button.isConnected||!$('#reviewChanges').open)return;
    const item=rows.get(ticker);
    if(!item)throw Error('Detalj tickera nije dostupan u ovoj snimci.');
    show({...item,chartBasePath:manifest.watchlist.chartBasePath},view);
  }catch(error){
    if(state.data!==data||reviewChangeDetail!==button||!button.isConnected)return;
    notice.textContent=error.message;
    notice.hidden=false;
  }finally{button.disabled=false}
}
$('#reviewChanges').addEventListener('toggle',event=>{
  if(!event.target.open)return;
  reviewChangeView=state.primaryView==='kell-daily'?'kell':'early';
  reviewChangeLimit=6;
  if(reviewChangeData)renderReviewChanges();
  else loadReviewChanges();
});
$('#reviewChanges').addEventListener('click',event=>{
  const strategy=event.target.closest('[data-review-change-view]');
  const ticker=event.target.closest('[data-review-change-ticker]');
  if(strategy){
    reviewChangeView=strategy.dataset.reviewChangeView;
    reviewChangeLimit=6;
    $('#reviewChangeNotice').hidden=true;
    if(reviewChangeData)renderReviewChanges();
  }
  if(ticker)openReviewChange(ticker);
  if(event.target.closest('[data-review-change-more]')){reviewChangeLimit=Infinity;renderReviewChanges()}
  if(event.target.closest('[data-review-change-retry]'))loadReviewChanges();
});
function updateDetailNav(item){
  const items=state.renderedItems||[];
  const index=state.detailView===state.primaryView?items.findIndex(candidate=>candidate.ticker===item?.ticker):-1;
  state.detailTicker=item?.ticker||null;
  const pos=$('#detailPosition'),title=$('#detailToolbarTicker'),prev=$('#prevDetail'),next=$('#nextDetail');
  if(title)title.textContent=item?.ticker||'—';
  if(pos)pos.textContent=index>=0?(index+1)+' / '+items.length:'—';
  if(prev)prev.disabled=index<=0;
  if(next)next.disabled=index<0||index>=items.length-1;
}
function navigateDetail(delta){
  if(state.detailView!==state.primaryView)return;
  const items=state.renderedItems||[];
  const index=items.findIndex(item=>item.ticker===state.detailTicker);
  const nextIndex=index+delta;
  if(index<0||nextIndex<0||nextIndex>=items.length)return;
  show(items[nextIndex]);
}
let reviewLocationRevision=0;
function writeReviewLocation(item,view,period,push=false){
  const url=ReviewNavigation.write(new URL(location.href),{view:state.primaryView,
    ticker:item?.ticker,detailView:view,period});
  const entry={...history.state};
  if(push)entry.reviewDetail=true;
  if(!item)delete entry.reviewDetail;
  history[push?'pushState':'replaceState'](entry,'',url);
}
function closeReviewDetail(){
  ++reviewLocationRevision;
  $('#detail').close();
  if(!ReviewNavigation.read(location.search).ticker)return;
  if(history.state?.reviewDetail)history.back();
  else writeReviewLocation(null);
}
async function restoreReviewLocation(){
  const revision=++reviewLocationRevision,route=ReviewNavigation.read(location.search);
  const data=state.data,manifest=state.publication,notice=$('#reviewRouteNotice');
  notice.hidden=true;
  if(!route.ticker){$('#detail').close();return}
  if(!data)return;
  const active=()=>revision===reviewLocationRevision&&state.data===data;
  const view=route.detailView||route.view||state.primaryView;
  try{
    const shortlist=loadVisibleShortlist(view);
    if(shortlist){
      await shortlist.request;
      if(!active())return;
    }
    const key=shortlistKey(data,view);
    const groups=[data.shortlists?.[key],state.renderedItems,data.shortlists?.earlyTrendBirth,
      data.shortlists?.kellSwing,data.shortlists?.weeklyTrendBirth,data.kellCandidates,data.candidates];
    let item=groups.map(rows=>rows?.find(candidate=>candidate.ticker===route.ticker&&!candidate.watchlistMissing&&
      !candidate.watchlistUnavailable)).find(Boolean);
    if(!item&&manifest?.watchlist){
      const rows=await ReviewSnapshots.loadWatchlist(fetch,manifest,[route.ticker],state.watchlistLookup.cache);
      if(!active())return;
      const candidate=rows.get(route.ticker);
      if(candidate)item={...candidate,chartBasePath:manifest.watchlist.chartBasePath};
    }
    if(!item)item=data.trendBirthCandidateIndex?.find(candidate=>candidate.ticker===route.ticker);
    if(!item)throw Error('Ticker '+route.ticker+' nije dostupan u prikazanoj EOD snimci.');
    show(item,view,{period:route.period,fromLocation:true});
  }catch(error){
    if(!active())return;
    notice.textContent=error.message;
    notice.hidden=false;
  }
}
window.addEventListener('popstate',restoreReviewLocation);
async function copyDetailLink(button){
  const section=button.closest('.detail-link'),field=section.querySelector('input'),status=section.querySelector('[role="status"]');
  const detailView=state.detailView,view=['watchlist','research'].includes(detailView)?'early':detailView;
  const link=ReviewNavigation.tickerLink(location.href,{view,detailView,ticker:state.detailTicker,
    period:$('#detail [data-chart-period]').value}).href;
  try{
    await navigator.clipboard.writeText(link);
    status.textContent='Poveznica je kopirana.';
  }catch{
    field.value=link;
    field.hidden=false;
    field.focus();
    field.select();
    status.textContent='Poveznica je označena za kopiranje.';
  }
}
function detailEvidence(item,periodKey){
  const choices=[['3m','Dnevni · 3 mj.'],['6m','Dnevni · 6 mj.'],['1y','Dnevni · 1 g.']];
  if(item.weeklyBirth?.metrics?.baseWeeks>=9)choices.push(['base','Tjedni · zona baze']);
  choices.push(['5y','Tjedni · do 5 g.']);
  const savedChoices=(item.savedPlans||[]).map(plan=>
    '<option value="'+esc(ReviewPlans.planId(plan))+'">'+planNames[plan.strategy]+' · '+esc(plan.sessionDate)+'</option>');
  return '<section class="detail-evidence" aria-labelledby="detailChartTitle" tabindex="-1">'+
    '<div class="detail-evidence-head"><h2 id="detailChartTitle">Cijena i tržišni kontekst</h2>'+
      '<select data-chart-period aria-label="Razdoblje detaljnog grafa">'+choices.map(([key,label])=>
        '<option value="'+key+'"'+(key===periodKey?' selected':'')+'>'+label+'</option>').join('')+'</select></div>'+
    (savedChoices.length?'<div class="chart-plan-control"><label for="detailPlanLevels">Razine na grafu</label>'+
      '<select id="detailPlanLevels" data-chart-plan><option value="">Razine iz prikazanog EOD-a</option>'+
      savedChoices.join('')+'</select></div><div class="chart-plan-key" data-chart-plan-key hidden></div>'+
      '<p class="chart-plan-message" data-chart-plan-message role="status" hidden></p>':'')+
    '<div class="chart-track"><canvas class="detail-chart" aria-label="'+esc(item.ticker)+' detaljni graf"></canvas></div>'+
    '<p class="detail-chart-meta" role="status"></p>'+
    '<button type="button" class="watchlist-retry detail-chart-retry" hidden>Ponovi učitavanje grafa</button>'+
    '<div class="chart-inspection" hidden>'+
      '<div class="chart-inspection-stats">'+
        '<span><small>Otvaranje</small><b data-candle="open"></b></span>'+
        '<span><small>Najviša</small><b data-candle="high"></b></span>'+
        '<span><small>Najniža</small><b data-candle="low"></b></span>'+
        '<span><small title="U odnosu na prethodno zatvaranje">Promjena</small><b data-candle="change"></b></span>'+
      '</div>'+
      '<div class="chart-inspection-controls">'+
        '<button type="button" data-candle-step="-1" aria-label="Prethodna svijeća">‹</button>'+
        '<input type="range" min="0" max="0" value="0" aria-label="Svijeća na grafu">'+
        '<button type="button" data-candle-step="1" aria-label="Sljedeća svijeća">›</button>'+
        '<button type="button" data-candle-floor hidden>Dno baze</button>'+
      '</div>'+
    '</div>'+
    '<div class="chart-indicators" hidden>'+
      '<figure><figcaption><strong>Volumen</strong><span data-volume-readout></span></figcaption>'+
        '<div class="chart-track"><canvas aria-label="Volumen i prethodni prosjek"></canvas></div></figure>'+
      '<figure><figcaption><strong>Relativna snaga prema SPY-u</strong><span data-relative-readout></span></figcaption>'+
        '<div class="chart-track"><canvas aria-label="Omjer cijene dionice i SPY-a, indeksiran na 100"></canvas></div>'+
        '<small class="chart-rs-source" hidden>SPY referenca izvedena iz podudarnih Unified omjera za iste datume.</small></figure>'+
    '</div></section>';
}
const compactChartVolume=new Intl.NumberFormat('hr-HR',{notation:'compact',maximumFractionDigits:1});
const chartSpyRequests=new WeakMap();
function ensureChartSpy(manifest){
  if(!manifest?.spyReference?.sessionCount)return null;
  if(!chartSpyRequests.has(manifest)){
    const request=ReviewSnapshots.loadSpyReference(fetch,manifest)
      .catch(()=>{chartSpyRequests.delete(manifest);return null});
    chartSpyRequests.set(manifest,request);
  }
  return chartSpyRequests.get(manifest);
}
function chartDay(time){return barDate(time)?.toISOString().slice(0,10)??''}
function renderDetailEvidence(section,item,rows,periodKey,view,benchmark,savedPlan){
  const period=chartPeriods[periodKey],canvas=section.querySelector('.detail-chart');
  const base=period.weekly?weeklyBaseRange(item,rows):null;
  const context=view==='weekly'&&!period.weekly?'early':view;
  const levels=savedPlan?[
    [savedPlan.pivot,'Pivot','#80c7ff'],
    [savedPlan.maxEntry,'Maks. ulaz','#e9bd62'],
    [savedPlan.invalidation,savedPlan.strategy==='kell'?'Stop':'Poništenje','#ff8b99']
  ].filter(([price])=>Number.isFinite(price)):chartLevels(item,context);
  const result=draw(canvas,rows,true,undefined,levels,base,periodKey,savedPlan);
  const key=section.querySelector('[data-chart-plan-key]');
  if(key){
    key.hidden=!savedPlan||!result;
    key.innerHTML=key.hidden?'':'<ul aria-label="Izvorne razine spremljenog plana">'+levels.map(([price,label,color])=>
      '<li><span style="color:'+color+'">'+label+' '+fmt(price)+'</span>'+
      (result.marked.some(([value,name])=>value===price&&name===label)?'':' <small>izvan grafa</small>')+'</li>').join('')+'</ul>';
  }
  const indicators=section.querySelector('.chart-indicators');
  const meta=section.querySelector('.detail-chart-meta');
  indicators.hidden=!result;
  if(!result){meta.textContent='Za ovo razdoblje nema dovoljno podataka.';return}
  const lookback=period.weekly?10:20;
  const volume=ChartEvidence.volume(result.history,result.bars,lookback);
  const volumeCanvas=section.querySelector('[data-volume-readout]').closest('figure').querySelector('canvas');
  volumeCanvas.parentElement.hidden=!volume.hasValues;
  if(volume.hasValues)ChartEvidence.drawVolume(volumeCanvas,volume,value=>compactChartVolume.format(value));
  const dailyRs=new Map(normalizeBars(item.chartBars).filter(bar=>bar.rs!==null).map(bar=>[chartDay(bar.time),bar.rs]));
  const relative=ChartEvidence.relative(result.bars.map(bar=>({...bar,time:chartDay(bar.time)})),dailyRs,benchmark);
  section.querySelector('.chart-rs-source').hidden=relative.source!=='reference';
  const relativeCanvas=section.querySelector('[data-relative-readout]').closest('figure').querySelector('canvas');
  relativeCanvas.parentElement.hidden=relative.count<2;
  if(relative.count>=2)ChartEvidence.drawRelative(relativeCanvas,relative);
  return {...result,volume,relative,period,lookback,floorIndex:base?
    result.bars.findIndex(bar=>bar.time===base.floorBar.time):-1};
}
function showDetailCandle(section,evidence,index){
  const {history,bars,axis,volume,relative,period,lookback}=evidence;
  const selected=index??bars.length-1,bar=bars[selected],day=barDateLabel(bar.time);
  const prefix=index===null?(period.weekly?'Zadnja prikazana tjedna svijeća ':'Zadnja prikazana sesija '):
    (period.weekly?'Tjedan do ':'Sesija ');
  const title=prefix+day+' · zatvaranje '+priceLabel(bar.close);
  section.querySelector('.detail-chart-meta').textContent=title;
  const previousIndex=history.length-bars.length+selected-1;
  const previous=history[previousIndex]?.close;
  const change=previous>0?signedPct(100*(bar.close/previous-1)):'—';
  for(const field of ['open','high','low','change']){
    section.querySelector('[data-candle="'+field+'"]').textContent=field==='change'?change:priceLabel(bar[field]);
  }
  const amount=volume.points[selected],unit=period.weekly?'W':'D';
  section.querySelector('[data-volume-readout]').textContent=amount.value===null?'Volumen za ovaj datum nedostaje':
    compactChartVolume.format(amount.value)+(amount.ratio===null?' · prosjek '+lookback+unit+' nedostaje':
      ' · '+fmt(amount.ratio,2)+'× prethodni '+lookback+unit);
  const rs=relative.points[selected];
  section.querySelector('[data-relative-readout]').textContent=relative.count===0?'Referentni niz nije dostupan':
    rs==null?'RS za ovaj datum nedostaje':fmt(rs,1)+' ('+day+') · 100 na '+barDateLabel(relative.firstTime);
  const slider=section.querySelector('input[type="range"]');
  slider.value=String(selected);
  slider.setAttribute('aria-valuetext',title);
  section.querySelector('[data-candle-step="-1"]').disabled=selected===0;
  section.querySelector('[data-candle-step="1"]').disabled=selected===bars.length-1;
  section.toggleAttribute('data-chart-cursor',index!==null);
  section.style.setProperty('--candle-x',axis.x(selected)+'px');
}
function mountDetailEvidence(section,item,view,initialJump){
  const select=section.querySelector('[data-chart-period]'),canvas=section.querySelector('.detail-chart');
  const planSelect=section.querySelector('[data-chart-plan]'),planKey=section.querySelector('[data-chart-plan-key]');
  const planMessage=section.querySelector('[data-chart-plan-message]');
  const plans=new Map((item.savedPlans||[]).map(plan=>[ReviewPlans.planId(plan),plan]));
  const meta=section.querySelector('.detail-chart-meta'),indicators=section.querySelector('.chart-indicators');
  const retry=section.querySelector('.detail-chart-retry');
  const controls=section.querySelector('.chart-inspection'),slider=controls.querySelector('input');
  const floor=controls.querySelector('[data-candle-floor]');
  const dialog=$('#detail'),manifest=state.publication;
  let revision=0,lastRender=null,lastWidth=null;
  let evidence=null,selected=null,benchmark=null,pendingJump=initialJump,jumpNotice='';
  if(pendingJump&&planSelect)planSelect.value=pendingJump.id;
  function pick(index){
    if(!evidence)return;
    selected=Math.max(0,Math.min(evidence.bars.length-1,index));
    showDetailCandle(section,evidence,selected);
  }
  section.addEventListener('click',event=>{
    if(!evidence)return;
    const track=event.target.closest('.chart-track'),step=event.target.closest('[data-candle-step]');
    if(track)pick(evidence.axis.indexAt(event.clientX-track.getBoundingClientRect().left));
    if(step)pick(Number(slider.value)+Number(step.dataset.candleStep));
    if(event.target===floor&&evidence.floorIndex>=0)pick(evidence.floorIndex);
  });
  slider.addEventListener('input',()=>pick(Number(slider.value)));
  const active=()=>section.isConnected&&dialog.open;
  const observer=new ResizeObserver(entries=>{
    const width=entries[0].contentRect.width;
    if(width===lastWidth)return;
    lastWidth=width;
    if(active())lastRender?.();
    else observer.disconnect();
  });
  observer.observe(section);
  dialog.addEventListener('close',()=>observer.disconnect(),{once:true,signal:section.cleanup.signal});
  section.cleanup.signal.addEventListener('abort',()=>observer.disconnect(),{once:true});
  function setPeriod(period){
    select.value=period;
    writeReviewLocation(item,view,period);
    refresh();
  }
  $('#detailBody').addEventListener('click',event=>{
    const target=planCandleTarget(event);
    if(!target||!plans.has(target.id))return;
    planSelect.value=target.id;
    pendingJump=target;
    jumpNotice='';
    if(evidence&&!evidence.period.weekly&&evidence.bars.some(bar=>chartDay(bar.time)===target.day))lastRender();
    else setPeriod('1y');
  },{signal:section.cleanup.signal});
  planSelect?.addEventListener('change',()=>{
    pendingJump=null;
    jumpNotice='';
    if(planSelect.value&&chartPeriods[select.value].weekly)setPeriod('1y');
    else lastRender?.();
  });
  async function refresh(){
    const current=++revision,periodKey=select.value;
    const isCurrent=()=>active()&&current===revision;
    lastRender=null;
    evidence=null;
    selected=null;
    section.removeAttribute('data-chart-cursor');
    if(planKey)planKey.hidden=true;
    if(planMessage)planMessage.hidden=true;
    indicators.hidden=true;
    controls.hidden=true;
    retry.hidden=true;
    meta.textContent='Učitavanje grafa…';
    draw(canvas,[],true,'Učitavanje…');
    try{
      if(item.watchlistUnavailable&&manifest?.watchlist){
        meta.textContent='Učitavam podatke tickera…';
        const lookup=state.watchlistLookup;
        const rows=await ReviewSnapshots.loadWatchlist(fetch,manifest,[item.ticker],lookup.cache);
        if(!isCurrent())return;
        const row=rows.get(item.ticker);
        lookup.rows.set(item.ticker,row);
        if(!lookup.request)render();
        show({...item,...row,watchlistUnavailable:false,watchlistMissing:!row},view,{period:periodKey,jump:pendingJump});
        return;
      }
      let cutoff=null;
      if(chartPeriods[periodKey].weekly){
        const session=state.data?.source?.sessionDate;
        const modelEnd=item.weeklyBirth?.metrics?.historyEnd;
        cutoff=view==='weekly'?modelEnd:null;
        if(!cutoff){
          const calendar=freshnessCalendar||(modelEnd?null:await ReviewFreshness.loadCalendar(fetch));
          cutoff=ChartEvidence.lastCompletedWeek(calendar?.sessions,session)||modelEnd;
        }
        if(!isCurrent())return;
        if(!cutoff){
          draw(canvas,[],true,'Tjedni graf nije dostupan');
          meta.textContent='Zadnji dovršeni tjedan nije potvrđen.';
          if(item.savedPlans?.length)await ensureChartData(item,'1y');
          if(isCurrent())updateSavedPlanStatuses($('#detailBody'),item);
          return;
        }
      }
      const rows=await ensureChartData(item,periodKey,cutoff);
      if(!isCurrent())return;
      if(!freshnessCalendar&&item.savedPlans?.some(plan=>plan.sessionDate<state.data.source?.sessionDate)){
        try{freshnessCalendar=await ReviewFreshness.loadCalendar(fetch)}catch{/* Status reports missing calendar. */}
        if(!isCurrent())return;
      }
      const assessments=updateSavedPlanStatuses($('#detailBody'),item);
      lastRender=()=>{
        const plan=plans.get(planSelect?.value),assessment=plan&&assessments.get(planSelect.value);
        const sameClose=assessment?.state==='saved'&&ReviewPlans.samePriceBasis(plan,
          rows.find(bar=>chartDay(bar.time)===plan.sessionDate)?.close);
        const overlay=!chartPeriods[periodKey].weekly&&(assessment?.events||sameClose)?plan:null;
        evidence=renderDetailEvidence(section,item,rows,periodKey,view,benchmark,overlay);
        controls.hidden=!evidence;
        const target=pendingJump;
        if(target){
          const verified=overlay&&assessment.events?.some(event=>event.day===target.day);
          const index=verified?evidence?.bars.findIndex(bar=>chartDay(bar.time)===target.day):-1;
          selected=index>=0?index:null;
          jumpNotice=selected===null?'Svijeća za '+target.day+' nije dostupna u dnevnom grafu.':'';
          pendingJump=null;
          section.focus({preventScroll:true});
          section.scrollIntoView({block:'start'});
        }
        if(planMessage){
          planMessage.textContent=jumpNotice||(plan&&!overlay?'Izvorne razine nisu potvrđene za prikazani niz cijena.':'');
          planMessage.hidden=!planMessage.textContent;
        }
        if(!evidence)return;
        slider.max=String(evidence.bars.length-1);
        floor.hidden=evidence.floorIndex<0;
        showDetailCandle(section,evidence,selected);
      };
      lastRender();
      if(!benchmark&&evidence&&evidence.relative.count<evidence.bars.length){
        const request=ensureChartSpy(manifest);
        if(!request)return;
        const verified=await request;
        if(!isCurrent()||!verified)return;
        benchmark=verified;
        lastRender();
      }
    }catch{
      if(!isCurrent())return;
      updateSavedPlanStatuses($('#detailBody'),item);
      draw(canvas,[],true,'Graf nije dostupan');
      meta.textContent='Podaci za graf trenutačno se ne mogu učitati.';
      retry.hidden=false;
    }
  }
  select.addEventListener('change',()=>{
    pendingJump=null;
    jumpNotice='';
    if(planSelect&&chartPeriods[select.value].weekly)planSelect.value='';
    setPeriod(select.value);
  });
  retry.addEventListener('click',refresh);
  requestAnimationFrame(()=>{if(active()&&revision===0)refresh()});
}
function show(item,view=state.primaryView,{period=null,fromLocation=false,jump=null}={}){
  if(!fromLocation)++reviewLocationRevision;
  const m=item.metrics||{},a=analysisFor(item),ai=item.analysis||{},g=item.kellGap||{gapPct:item.kell_metrics?.gap_pct};
  const fundamentals=ai.fundamentalsQoQ||ai.fundamentals||'Work analiza još nije upisana za ovaj snapshot.';
  state.detailView=view;
  state.detailItem=item;
  updateDetailNav(item);
  const reviewStatus=String(a.status||'REVIEW').toUpperCase();
  const tbMissing=(item?.trendBirth?.missingFor4||[]).join(' · ')||'Complete';
  const weekly=item.weeklyBirth||{},weeklyMetrics=weekly.metrics||{};
  const weeklyMode=view==='weekly';
  const body=$('#detailBody'),dialog=$('#detail');
  const fresh=!dialog.open;
  const previous=body.querySelector('.detail-evidence');
  let periodKey=period||(dialog.open?previous?.querySelector('[data-chart-period]')?.value:null);
  periodKey=periodKey||(weeklyMode?state.chartPeriod:view==='kell-daily'?'3m':'6m');
  if(periodKey==='base'&&!(weeklyMetrics.baseWeeks>=9))periodKey='5y';
  previous?.cleanup?.abort();
  body.innerHTML=
    '<div class="detail-head"><div class="badges">'+badges(item)+'</div></div>'+
    '<div class="detail-link"><button type="button" data-copy-detail-link>Kopiraj poveznicu</button>'+
    '<input type="url" aria-label="Poveznica na ticker" readonly hidden><small role="status"></small></div>'+
    '<p data-plan-notice role="status" hidden></p>'+renderSavedPlans(item,true)+
    (weeklyMode?weeklyEvidence(item,true):view==='kell-daily'?swingPlan(item)+earlyPlan(item):earlyPlan(item)+swingPlan(item))+
    detailEvidence(item,periodKey)+
    '<div class="detail-snapshot">'+
      '<div><span>Status</span><strong class="'+(reviewStatus==='ACTION'?'positive':reviewStatus==='WATCH'?'caution':'')+'">'+esc(reviewStatus)+'</strong></div>'+
      '<div><span>Daily radar 0–4</span><strong>'+esc(trendBirthLabel(item))+'</strong></div>'+
      '<div><span>Kell Focus</span><strong>'+fmt(item.kell_score,0)+'</strong></div>'+
      '<div><span>Readiness</span><strong>'+fmt(item.kell_readiness_score,0)+'</strong></div>'+
    '</div>'+
    (weekly.stageLabel?'<div class="detail-tb-note"><span>Weekly Birth</span><strong>'+esc(weekly.stageLabel)+' · '+fmt(weeklyMetrics.baseWeeks,0)+'W base · '+pct(weeklyMetrics.weeklyMaClusterPct)+' MA cluster · '+runwayLabel(weeklyMetrics)+'</strong></div>':'')+
    '<div class="detail-tb-note"><span>Daily radar · nedostaje za 4/4</span><strong>'+esc(tbMissing)+'</strong></div>'+
    '<div class="detail-tb-note"><span>Birth path</span><strong>'+esc(birthPathText(item))+(trendBirthEvidence(item).primary?' · '+esc(trendBirthEvidence(item).primary):'')+'</strong></div>'+
    '<details class="detail-more"><summary>More metrics & setup details</summary><div class="detail-grid">'+
      fact('Review state',a.state)+fact('Kell stage',stageName(primaryStage(item)))+
      fact('Weekly base',fmt(weeklyMetrics.baseWeeks,0)+'W · depth '+pct(weeklyMetrics.baseDepthPct))+
      fact('Weekly MA / runway',pct(weeklyMetrics.weeklyMaClusterPct)+' / '+runwayLabel(weeklyMetrics))+
      fact('Weekly pivot / breakout age',fmt(weeklyMetrics.pivotPrice)+' / '+fmt(weeklyMetrics.weeksSinceBreakout,0)+'W')+
      fact('Quality',fmt(item.kell_quality_score,1))+fact('Context score',fmt(item.kell_context_score,1))+
      fact('Evidence coverage',fmt(item.kell_evidence_coverage,0)+'%')+fact('Structural risk',Number.isFinite(numberOrNaN(item.kell_structural_risk_score))?fmt(item.kell_structural_risk_score,0):'—')+
      fact('Stage cap',fmt(item.kell_stage_cap,0))+fact('Stage confidence',item?.kell_stage?.confidence!=null?fmt(Number(item.kell_stage.confidence)*100,0)+'%':'—')+
      fact('Discovery screens',kellScreensText(item))+fact('Setups',kellSetupsText(item))+
      fact('Context flags',kellContextText(item))+fact('Actionability',m.actionability||'—')+
      fact('RVOL',fmt(m.rvol)+'x')+fact('RSI14',fmt(m.rsi14,1))+
      fact('EMA10 / EMA20',fmt(m.ema10)+' / '+fmt(m.ema20))+fact('EMA gap',pct(m.emaGapPct))+
      fact('50D slope',m.slope50||'—')+fact('30W slope',m.slope30w||'—')+
      fact('Swing',m.swingState||'—')+fact('20D / 40D range',pct(m.range20Pct)+' / '+pct(m.range40Pct))+
      fact('Close location',pct(m.closeLocationPct))+
      ((item.sources||[]).includes('kell-gap')?fact('Gap / held',pct(g.gapPct)+' / '+pct(g.gapHeldPct))+fact('Avg Vol 20D',Number.isFinite(Number(g.avgVolume20d))?Intl.NumberFormat('en',{notation:'compact'}).format(g.avgVolume20d):'—'):'')+
    '</div></details>'+
    '<div class="analysis-text"><b>Sažetak</b>\n'+esc(a.summary||'—')+
    '\n\n<b>Preferred trade</b>\n'+esc(a.preferredTrade||'—')+
    (item.kell?.signals?.length?'\n\n<b>Kell confluence</b>\n'+esc(item.kell.signals.join(' · ')):'')+
    '\n\n<b>Trend Birth checklist</b>\n'+esc(trendBirthChecklistText(item))+
    '\n\n<b>Supporting evidence</b>\n'+esc(birthEvidenceText(item))+
    '\n\n<b>Kell score breakdown</b>\n'+esc(kellBreakdownText(item))+
    '\n\n<b>Fundamenti QoQ</b>\n'+esc(fundamentals)+
    (ai.riskNote?'\n\n<b>Risk note</b>\n'+esc(ai.riskNote):'')+
    '</div>';
  const section=body.querySelector('.detail-evidence');
  section.cleanup=new AbortController();
  if(!fromLocation)writeReviewLocation(item,view,periodKey,fresh&&!ReviewNavigation.read(location.search).ticker);
  if(!dialog.open)dialog.showModal();
  mountDetailEvidence(section,item,view,jump);
}
$('#changeHighlights')?.addEventListener('click',e=>{
  const more=e.target.closest('[data-change-more]');
  if(more){
    state.changeHighlightsExpanded=true;
    renderChangeHighlights(state.renderedItems);
    return;
  }
  const chip=e.target.closest('[data-change-ticker]');
  if(!chip)return;
  const item=(state.renderedItems||[]).find(candidate=>candidate.ticker===chip.dataset.changeTicker);
  if(item)show(item);
});
$('#closeDetail').addEventListener('click',closeReviewDetail);
$('#detailBody').addEventListener('click',e=>{
  const link=e.target.closest('[data-copy-detail-link]');
  if(link)copyDetailLink(link);
  else planAction(e,state.detailItem);
});
$('#prevDetail')?.addEventListener('click',()=>navigateDetail(-1));
$('#nextDetail')?.addEventListener('click',()=>navigateDetail(1));
$('#detail').addEventListener('click',e=>{if(e.target===$('#detail'))closeReviewDetail()});
$('#detail').addEventListener('cancel',e=>{e.preventDefault();closeReviewDetail()});
$('#detail').addEventListener('close',()=>{
  if($('#detail').open||!state.detailTicker)return;
  const ticker=CSS.escape(state.detailTicker);
  ($('.card[data-ticker="'+ticker+'"]')||$('[data-review-change-ticker="'+ticker+'"]'))?.focus({preventScroll:true});
});
$('#mobileFiltersToggle')?.addEventListener('click',()=>setMobileFiltersOpen(!$('#filters')?.classList.contains('mobile-open')));
$('#mobileFiltersClose')?.addEventListener('click',()=>setMobileFiltersOpen(false,true));
$('#mobileFilterBackdrop')?.addEventListener('click',()=>setMobileFiltersOpen(false,true));
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&$('#filters')?.classList.contains('mobile-open')){
    setMobileFiltersOpen(false,true);
    return;
  }

  if(!$('#detail')?.open||e.target.closest?.('select,input,textarea,[contenteditable]'))return;
  if(e.key==='ArrowLeft'){e.preventDefault();navigateDetail(-1)}
  if(e.key==='ArrowRight'){e.preventDefault();navigateDetail(1)}
});
$('#search').addEventListener('input',e=>{state.query=e.target.value.trim().toUpperCase();render()});
$('#sort')?.addEventListener('change',e=>{state.sort=e.target.value;render()});
$('#chartPeriod')?.addEventListener('change',e=>{
  state.chartPeriod=e.target.value in chartPeriods?e.target.value:'1y';
  if($('#detail')?.open)closeReviewDetail();
  render();
});
document.querySelectorAll('input[data-tb-stage]').forEach(input=>
  input.addEventListener('change',renderTrendBirthQuality));
document.querySelectorAll('button[data-tb-zoom]').forEach(button=>
  button.addEventListener('click',()=>{
    tbQualityView.zoom=Number(button.dataset.tbZoom);
    renderTrendBirthQuality();
  }));
document.querySelectorAll('button[data-tb-timeframe]').forEach(button=>
  button.addEventListener('click',()=>{
    tbQualityView.timeframe=button.dataset.tbTimeframe;
    tbQualityView.selectedPeriod='';
    tbQualityView.scrollToEnd=true;
    $('#tbTickerDrill').hidden=true;
    state.tickerDrill=null;
    renderTrendBirthQuality();
  }));
document.querySelectorAll('button[data-tb-range]').forEach(button=>
  button.addEventListener('click',()=>{
    tbQualityView.range=button.dataset.tbRange;
    tbQualityView.selectedPeriod='';
    tbQualityView.scrollToEnd=true;
    $('#tbTickerDrill').hidden=true;
    state.tickerDrill=null;
    renderTrendBirthQuality();
  }));
$('#tbPercentileMetric')?.addEventListener('change',renderTrendBirthQuality);
$('#tbStagesAll')?.addEventListener('click',()=>{
  document.querySelectorAll('input[data-tb-stage]').forEach(input=>{input.checked=true});
  renderTrendBirthQuality();
});
$('#tbStagesQuality')?.addEventListener('click',()=>{
  document.querySelectorAll('input[data-tb-stage]').forEach(input=>
    {input.checked=input.dataset.tbStage==='3'||input.dataset.tbStage==='4'});
  $('#tbPercentileMetric').value='3+';
  renderTrendBirthQuality();
});
$('#tbQualityHistory')?.addEventListener('click',event=>{
  const bar=event.target.closest('button[data-tb-period]');
  if(!bar)return;
  tbQualityView.selectedPeriod=bar.dataset.tbPeriod;
  $('#tbTickerDrill').hidden=false;
  $('#tbDrillPeriod').textContent=bar.getAttribute('aria-label')?.split(' · ')[0]||bar.dataset.tbPeriod;
  renderTrendBirthQuality();
  showSelectedTickerMembers();
  [...$('#tbQualityHistory').querySelectorAll('button[data-tb-period]')].find(
    button=>button.dataset.tbPeriod===tbQualityView.selectedPeriod)?.focus({preventScroll:true});
});
$('#tbDrillStage')?.addEventListener('change',showSelectedTickerMembers);
$('#tbDrillResults')?.addEventListener('click',e=>{
  if(e.target.closest('#tbDrillMore')){
    state.tickerDrillLimit+=40;renderTickerDrillResults();
  }
});
document.addEventListener('click',e=>{
  const picker=e.target.closest('button[data-tb-journey]');
  if(picker){showTickerJourney(picker.dataset.tbJourney);return}
  if(e.target.closest('#tbCloseJourney')){$('#tbTickerJourney').hidden=true;state.journeyTicker=''}
});
$('#filters').addEventListener('click',async e=>{
  const universeButton=e.target.closest('button[data-universe]');
  const filterButton=e.target.closest('button[data-filter]');
  if(!universeButton&&!filterButton)return;
  state.primaryView='research';

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
  state.primaryView='research';
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
    $('#status').textContent='Učitavam prethodni Kell snapshot i računam današnje promjene…';
    try{await ensureKellChanges()}catch(err){$('#status').textContent='What Changed Today nije dostupan: '+err.message;return}
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
  if(event.key!==WatchlistStore.keyForUser(state.ownerSession?.user?.id))return;
  state.watchlist=WatchlistStore.load(window.localStorage,state.ownerSession?.user?.id);
  if(state.ownerSync?.signedIn()){reconcileOwnerWatchlist();return}
  if(state.data)render();
});
$('#ownerGoogle')?.addEventListener('click',async()=>{
  if(!state.ownerSync)return;
  state.ownerSyncError='';state.ownerSyncMessage='Otvaram owner prijavu…';updateOwnerSyncUi();
  try{await state.ownerSync.signInWithGoogle()}catch(err){state.ownerSyncError='Google prijava: '+(err?.message||String(err));updateOwnerSyncUi()}
});
$('#ownerMagicForm')?.addEventListener('submit',e=>{
  e.preventDefault();
  const email=$('#ownerEmail')?.value?.trim();
  if(!email||!state.ownerSync||state.ownerMagicSending)return;
  state.ownerSyncError='';
  state.ownerSyncMessage='Pripremam sigurni povratak nakon klika na magic link…';
  state.ownerMagicSending=true;
  updateOwnerSyncUi();
  try{
    sessionStorage.setItem(OWNER_MAGIC_EMAIL_KEY,email);
    location.assign(ownerAuthBridgeUrl());
  }catch(err){
    state.ownerMagicSending=false;
    state.ownerSyncError='Magic link priprema: '+(err?.message||String(err));
    updateOwnerSyncUi();
  }
});
$('#ownerImportLocal')?.addEventListener('click',async()=>{
  if(!state.ownerSync?.signedIn()||state.ownerReconciling)return;
  state.ownerReconciling=true;
  try{
    const ownerId=state.ownerSession?.user?.id;
    const local=WatchlistStore.load(window.localStorage).map(item=>item.ticker);
    const remote=await state.ownerSync.migrate(local);
    if(ownerId!==state.ownerSession?.user?.id)return;
    state.watchlist=WatchlistStore.save(window.localStorage,ownerWatchlistItems(remote),state.ownerSession?.user?.id);
    state.ownerSyncError='';state.ownerSyncMessage='Lokalni tickeri dodani su u ovaj račun.';
  }catch(err){state.ownerSyncError='Uvoz watchliste: '+err.message}
  finally{state.ownerReconciling=false;updateOwnerSyncUi();render()}
});
$('#ownerSignOut')?.addEventListener('click',async()=>{
  if(!state.ownerSync)return;
  try{await state.ownerSync.signOut();state.ownerSession=null;state.ownerMagicSentTo='';state.ownerSyncMessage='Sync je odjavljen; prikazana je lokalna watchlista ovog preglednika.'}
  catch(err){state.ownerSyncError='Odjava: '+(err?.message||String(err))}
  updateOwnerSyncUi();
});
$('#ownerPlanImport')?.addEventListener('click',async()=>{
  const scope=ownerPlanScope;
  if(!scope?.book||scope.importing)return;
  scope.importing=true;
  scope.message='';
  updateOwnerPlanUi();
  try{
    const local=ownerPlanLists();
    const result=await changeOwnerPlanBook(scope,rows=>OwnerPlanBook.importPlans(rows,local));
    scope.message='Preneseno '+result.added+' · već na računu '+result.existing+
      (result.updated?' · dopunjene provjere '+result.updated:'')+
      (result.conflicts?' · na uređaju zbog sukoba aktivnih planova '+result.conflicts:'');
    render();
  }catch(error){
    scope.message=error?.message||'Prijenos planova nije potvrđen.';
  }finally{
    scope.importing=false;
    if(scope===ownerPlanScope)updateOwnerPlanUi();
  }
});
$('#ownerPlanRefresh')?.addEventListener('click',()=>{
  if(ownerPlanScope)ownerPlanScope.message='';
  refreshOwnerPlanBook();
});
window.addEventListener('focus',refreshOwnerPlanBook);
document.addEventListener('visibilitychange',refreshOwnerPlanBook);
updateOwnerSyncUi();
initOwnerWatchlistSync();
$('#chartPeriod').value=state.chartPeriod;
$('#primaryViews')?.addEventListener('click',async e=>{
  const request=state.primaryRequest=(state.primaryRequest||0)+1;
  const button=e.target.closest('[data-primary-view]');
  if(!button)return;
  if(button.dataset.primaryView==='research'){
    $('#status').textContent='Učitavam istraživački skup…';
    try{await ensureResearchData()}catch(error){$('#status').textContent='Research nije dostupan: '+error.message;return}
  }
  if(request!==state.primaryRequest)return;
  $('#planNotice').hidden=true;
  state.primaryView=button.dataset.primaryView;
  state.filters=[];state.quickView=null;state.sort='default';state.universe=state.primaryView==='watchlist'?'watchlist':'all';
  state.chartPeriod=state.primaryView==='weekly'?'base':'1y';
  ++reviewLocationRevision;
  $('#reviewRouteNotice').hidden=true;
  writeReviewLocation(null);
  $('#chartPeriod').value=state.chartPeriod;$('#sort').value='default';
  document.querySelectorAll('#filters button[data-universe]').forEach(x=>x.classList.toggle('active',x.dataset.universe===state.universe));
  render();
});
const queryParams=new URLSearchParams(location.search);
const archived=queryParams.has('snapshot')||queryParams.has('date');
let freshnessCalendar=null;
let refreshRequest=null;

function showDisplayedSnapshot(data,manifest,lookup){
  if(state.data){
    state.primaryRequest=(state.primaryRequest||0)+1;
    state.researchLoading=null;
    state.kellLoading=null;
    state.kellData=null;
    state.kellChangesLoading=null;
    state.kellChangesPreviousDate=null;
    state.kellChartShards=new Map();
    state.kellChartLoading=new Map();
    state.intelligenceMonths=new Map();
    state.intelligence=null;
    state.qualityHistory=null;
    state.qualityHistoryError='';
    state.detailTicker=null;
    if($('#detail').open)$('#detail').close();
  }
  if(!state.data&&!state.primaryRequest&&!archived&&state.primaryView==='weekly'&&!requestedMode&&!initialReviewRoute.view&&
      Array.isArray(data.shortlists?.earlyTrendBirth)){
    state.primaryView='early';
    state.chartPeriod='1y';
    $('#chartPeriod').value='1y';
  }
  state.data=data;
  state.shortlistRequests=new Map();
  state.publication=manifest;
  state.watchlistLookup=lookup||watchlistLookup();
  reviewChangeData=null;
  reviewChangeRequest=null;
  $('#reviewChanges').hidden=!manifest?.changes;
  $('#reviewChangeNotice').hidden=true;
  if(manifest?.changes&&$('#reviewChanges').open)loadReviewChanges();
  state.snapshotId=manifest?.snapshotId||data.reviewSnapshotId||queryParams.get('snapshot')||null;
  if(!data.shortlists?.weeklyTrendBirth&&state.primaryView==='weekly'){
    state.primaryView='research';
    state.chartPeriod='1y';
    $('#chartPeriod').value='1y';
  }
  $('#runMeta').textContent=(data.source?.sessionDate||'—')+' · Unified '+(data.source?.runId||'—')+' · '+
    (archived?'archive':'latest')+' · read-only';
  renderTrendBirthToday();
  renderTrendBirthQuality();
  loadTrendBirthIntelligence();
  loadTrendBirthQualityHistory();
  render();
  if(ReviewNavigation.read(location.search).ticker)restoreReviewLocation();
}

function refreshDisplayedSnapshot(){
  if(refreshRequest||document.visibilityState==='hidden'||(archived&&state.data))return;
  refreshRequest=(async()=>{
    let error=null;
    try{
      const full=defaultMode==='legacy'||state.primaryView==='research';
      if(archived){
        showDisplayedSnapshot(await ReviewSnapshots.load(fetch,location.search),null);
      }else{
        const oldId=state.snapshotId;
        const {data,manifest}=await ReviewSnapshots.loadCurrent(fetch,{full,previousId:oldId});
        if(data&&(!state.data||manifest)){
          if(state.data?.source?.sessionDate>data.source?.sessionDate)throw Error('Objava ima stariji datum od prikazane sesije.');
          const lookup=watchlistLookup();
          if(state.data)await ReviewSnapshots.loadShortlist(fetch,data,shortlistKey(data));
          const entries=watchedEntries();
          if(state.primaryView==='watchlist'&&entries.length&&manifest?.watchlist){
            lookup.rows=await ReviewSnapshots.loadWatchlist(fetch,manifest,
              entries.map(saved=>saved.ticker),lookup.cache);
          }
          showDisplayedSnapshot(data,manifest,lookup);
        }else if(!manifest){
          throw Error('Nedostaje pokazivač objave.');
        }
      }
      if(!freshnessCalendar&&(!archived||state.primaryView==='watchlist')){
        freshnessCalendar=await ReviewFreshness.loadCalendar(fetch);
        if(state.primaryView==='watchlist'&&state.savedPlans?.length)render();
      }
    }catch(cause){
      error=cause;
      if(!state.data)$('#status').textContent='Snapshot nije dostupan: '+cause.message;
    }
    ReviewFreshness.render($('#eodFreshness'),freshnessCalendar,state.data?.source?.sessionDate,{archived,error});
  })().finally(()=>{refreshRequest=null});
}

document.addEventListener('visibilitychange',refreshDisplayedSnapshot);
window.addEventListener('pageshow',refreshDisplayedSnapshot);
window.addEventListener('focus',refreshDisplayedSnapshot);
refreshDisplayedSnapshot();
