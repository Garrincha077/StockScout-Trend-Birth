const state={data:null,filter:'all',query:'',sort:'default'};
const $=s=>document.querySelector(s);
const fmt=(n,d=2)=>Number.isFinite(Number(n))?Number(n).toFixed(d):'—';
const pct=n=>Number.isFinite(Number(n))?fmt(n,1)+'%':'—';
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const labels={'bottom-fishing':'Bottom','next':'Next','ryan-original':'Ryan','kell-daily':'Kell 3x','kell-gap':'Kell Gap'};
const label=s=>labels[s]||s;
const kellFilterLabels={
  'kell-any':'Kell Hits',
  'kell_52w_high':'52W / New High',
  'kell_unusual_volume':'Unusual Vol ≥2x',
  'kell_rvol_3x':'RVOL ≥3x',
  'kell_bull_snort':'Bull Snort',
  'kell_momentum_3m_50':'3M +50%',
  'kell_doubler_6m':'6M Doubler',
  'kell_gapper':'Gapper',
  'kell_buyable_gap_proxy':'Buyable Gap proxy',
  'kell_strength_on_down_day':'Strength on Down Day',
  'kell_rs_divergence':'RS Divergence',
  'kell_name_selection_ok':'Kell Liquid/Price',
  'kell_weekly_trend_ok':'Weekly 10EMA',
  'kell_ema_readiness':'EMA10/20 Ready',
  'kell_wedge_pop':'Wedge Pop',
  'kell_ema_crossback':'EMA Crossback',
  'kell_base_n_break':"Base n' Break",
  'kell_tightening':'Tightening',
  'kell_breakout_proximity':'Near Breakout',
  'kell-score':'Kell ≥60'
};
const kellFilters=new Set(Object.keys(kellFilterLabels));

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
function draw(canvas,rows,large=false){
  const bars=normalizeBars(rows).slice(large?-504:-180);
  const rect=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
  canvas.width=Math.max(1,rect.width*dpr);canvas.height=Math.max(1,rect.height*dpr);
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const w=rect.width,h=rect.height;ctx.clearRect(0,0,w,h);
  if(bars.length<2){ctx.fillStyle='#8ea0b7';ctx.fillText('Chart data unavailable',12,22);return}
  const top=12,bottom=large?36:24,left=6,right=8;
  const lo=Math.min(...bars.map(b=>b.low)),hi=Math.max(...bars.map(b=>b.high)),range=Math.max(hi-lo,.0001);
  const x=i=>left+i*(w-left-right)/(bars.length-1),y=v=>top+(hi-v)*(h-top-bottom)/range;
  ctx.strokeStyle='#1c2d43';ctx.lineWidth=1;
  for(let i=1;i<4;i++){const yy=top+i*(h-top-bottom)/4;ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke()}
  const closes=bars.map(b=>b.close),e10=avg(closes,10,true),e20=avg(closes,20,true),s50=avg(closes,50,false);
  const candleW=Math.max(1,Math.min(5,(w-left-right)/bars.length*.7));
  bars.forEach((b,i)=>{
    const xx=x(i),up=b.close>=b.open;ctx.strokeStyle=up?'#35d78b':'#ff6d7a';ctx.fillStyle=ctx.strokeStyle;
    ctx.beginPath();ctx.moveTo(xx,y(b.high));ctx.lineTo(xx,y(b.low));ctx.stroke();
    const yy=Math.min(y(b.open),y(b.close)),bh=Math.max(1,Math.abs(y(b.open)-y(b.close)));
    ctx.fillRect(xx-candleW/2,yy,candleW,bh);
  });
  [[e10,'#e9bd62'],[e20,'#56a8ff'],[s50,'#a67cff']].forEach(([series,color])=>{
    ctx.strokeStyle=color;ctx.lineWidth=1.3;ctx.beginPath();let started=false;
    series.forEach((v,i)=>{if(v==null)return;const xx=x(i),yy=y(v);if(!started){ctx.moveTo(xx,yy);started=true}else ctx.lineTo(xx,yy)});
    ctx.stroke();
  });
  if(large){ctx.fillStyle='#8ea0b7';ctx.fillText('EMA10 / EMA20 / SMA50 · '+bars.length+' sessions',10,h-10)}
}
function badges(item){
  const sources=item.sources.map(s=>'<span class="badge '+(s==='kell-daily'||s==='kell-gap'?'kell':'')+'">'+esc(label(s))+'</span>').join('');
  const score=Number(item.kell_score);
  const kell=Number.isFinite(score)?'<span class="badge kell-score">Kell '+fmt(score,0)+'</span>':'';
  return sources+kell;
}
function kellHits(item){
  const criteria=item.score_breakdown?.criteria||{};
  return Object.entries(criteria).filter(([,v])=>v?.hit===true).map(([k])=>k.replaceAll('_',' '));
}
function kellBreakdownText(item){
  const breakdown=item.score_breakdown||{},criteria=breakdown.criteria||{};
  const rows=Object.entries(criteria).map(([name,v])=>{
    const mark=v?.hit===true?'✓':v?.hit===false?'—':'?';
    return mark+' '+name.replaceAll('_',' ')+' '+(v?.points??0)+'/'+(v?.max_points??0)+' · '+(v?.detail||'');
  });
  return 'Score '+fmt(item.kell_score,1)+' · '+(breakdown.points??0)+'/'+(breakdown.possible_points??0)+' pts\n'+rows.join('\n');
}
function slopeIcon(value){return value==='upward'?'↑':value==='downward'?'↓':value==='flat'?'→':'—'}
function ruleAnalysis(item){
  const m=item.metrics||{},rvol=Number(m.rvol),rsi=Number(m.rsi14),gap=Math.abs(Number(m.emaGapPct));
  const hh=m.higherHigh===true,hl=m.higherLow===true,trend=m.slope50==='upward'&&m.slope30w==='upward';
  const kell=item.sources.includes('kell-daily')||item.kell_rvol_3x===true;
  const kellGap=item.sources.includes('kell-gap')||item.kell_gapper===true;
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
function isKellView(){return kellFilters.has(state.filter)}
function sourceItems(){
  return isKellView()?(state.data?.kellCandidates||[]):(state.data?.candidates||[]);
}
function visible(item){
  if(state.query&&!item.ticker.includes(state.query))return false;
  if(state.filter==='all')return true;
  if(state.filter==='action')return String(analysisFor(item).status||'').toUpperCase()==='ACTION';
  if(state.filter==='multi')return item.sources.length>1;
  if(state.filter==='kell-any')return true;
  if(state.filter==='kell-score')return Number(item.kell_score)>=60;
  if(kellFilters.has(state.filter))return item[state.filter]===true;
  return item.sources.includes(state.filter);
}
function card(item){
  const m=item.metrics||{},a=analysisFor(item),status=String(a.status||'REVIEW').toUpperCase();
  const gap=item.kellGap||{gapPct:item.kell_metrics?.gap_pct};
  return '<article class="card" tabindex="0" data-ticker="'+esc(item.ticker)+'">'+
    '<div class="card-head"><div class="ticker">'+esc(item.ticker)+'</div><div class="badges">'+badges(item)+'</div></div>'+
    '<div class="metrics"><span>Px <b>'+fmt(m.price)+'</b></span><span>RVOL <b>'+fmt(m.rvol)+'x</b></span><span>RSI <b>'+fmt(m.rsi14,1)+'</b></span><span>EMA gap <b>'+pct(m.emaGapPct)+'</b></span><span>Kell <b>'+fmt(item.kell_score,0)+'</b></span>'+(item.sources.includes('kell-gap')?'<span>Gap <b>'+pct(gap.gapPct)+'</b></span>':'')+'</div>'+
    '<canvas aria-label="'+esc(item.ticker)+' chart" title="Tap/click za analizu"></canvas>'+
    '<div class="metrics structure"><span>50D <b>'+slopeIcon(m.slope50)+'</b></span><span>30W <b>'+slopeIcon(m.slope30w)+'</b></span><span>Swing <b>'+esc(m.swingState||'—')+'</b></span><span>Base <b>'+(m.baseLike===true?'✓':m.baseLike===false?'—':'?')+'</b></span></div>'+
    '<div class="analysis-strip"><span>'+esc(a.state||m.setup||'—')+'</span><strong class="'+(status==='ACTION'?'action':status==='WATCH'?'watch':'')+'">'+esc(status)+'</strong></div>'+
    '</article>';
}
let observer;
function render(){
  if(!state.data)return;
  const items=sourceItems().filter(visible);
  if(state.sort==='kell-score'||isKellView())items.sort((a,b)=>(Number(b.kell_score)||-1)-(Number(a.kell_score)||-1)||a.ticker.localeCompare(b.ticker));
  $('#grid').innerHTML=items.map(card).join('');
  if(isKellView()){
    const pool=state.data.kellScoring?.unifiedCandidateCount??0;
    const coverage=state.data.kellScoring?.chartCoverageCount??0;
    $('#status').textContent=items.length+' pogodaka · '+(kellFilterLabels[state.filter]||'Kell')+' · skenirano '+pool+' Unified kandidata · chart '+coverage+'/'+pool;
  }else{
    const strongKell=(state.data.kellCandidates||[]).filter(x=>Number(x.kell_score)>=60).length;
    $('#status').textContent=items.length+' / '+state.data.candidateCount+' kandidata · Kell ≥60 '+strongKell+' · Kell 3x '+(state.data.kell?.qualifiedCount??state.data.candidates.filter(x=>x.sources.includes('kell-daily')).length)+' · Gap '+(state.data.kellGap?.qualifiedCount??state.data.candidates.filter(x=>x.sources.includes('kell-gap')).length);
  }
  observer?.disconnect();
  observer=new IntersectionObserver(entries=>{
    for(const entry of entries){
      if(!entry.isIntersecting)continue;
      const cardEl=entry.target.closest('.card'),item=state.data.candidates.find(x=>x.ticker===cardEl.dataset.ticker);
      draw(entry.target,item.chartBars);observer.unobserve(entry.target);
    }
  },{rootMargin:'240px'});
  document.querySelectorAll('.card').forEach(cardEl=>{
    const item=state.data.candidates.find(x=>x.ticker===cardEl.dataset.ticker),canvas=cardEl.querySelector('canvas');
    observer.observe(canvas);
    const open=()=>show(item);
    canvas.addEventListener('click',e=>{e.stopPropagation();open()});
    cardEl.addEventListener('click',open);
    cardEl.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}});
  });
}
function fact(name,value){return '<div class="fact"><span>'+esc(name)+'</span>'+esc(value??'—')+'</div>'}
function show(item){
  const m=item.metrics||{},a=analysisFor(item),ai=item.analysis||{},g=item.kellGap||{gapPct:item.kell_metrics?.gap_pct};
  const fundamentals=ai.fundamentalsQoQ||ai.fundamentals||'Work analiza još nije upisana za ovaj snapshot.';
  $('#detailBody').innerHTML=
    '<div class="detail-head"><h2>'+esc(item.ticker)+'</h2><div class="badges">'+badges(item)+'</div></div>'+
    '<canvas class="detail-chart"></canvas>'+
    '<div class="detail-grid">'+
      fact('Setup state',a.state)+fact('Review status',String(a.status||'REVIEW').toUpperCase())+
      fact('Kell score',fmt(item.kell_score,1))+fact('Kell hits',kellHits(item).join(' · ')||'—')+
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
  $('#detail').showModal();
  requestAnimationFrame(()=>draw($('#detailBody canvas'),item.chartBars,true));
}
$('#closeDetail').addEventListener('click',()=>$('#detail').close());
$('#detail').addEventListener('click',e=>{if(e.target===$('#detail'))$('#detail').close()});
$('#search').addEventListener('input',e=>{state.query=e.target.value.trim().toUpperCase();render()});
$('#sort')?.addEventListener('change',e=>{state.sort=e.target.value;render()});
$('#filters').addEventListener('click',e=>{
  const b=e.target.closest('button[data-filter]');if(!b)return;
  state.filter=b.dataset.filter;document.querySelectorAll('#filters button').forEach(x=>x.classList.toggle('active',x===b));render();
});
const queryParams=new URLSearchParams(location.search);
const archived=queryParams.has('snapshot')||queryParams.has('date');
ReviewSnapshots.load(fetch,location.search)
  .then(data=>{state.data=data;$('#runMeta').textContent=(data.source?.sessionDate||'—')+' · Unified '+(data.source?.runId||'—')+' · '+(archived?'archive':'latest')+' · read-only';render()})
  .catch(err=>{$('#status').textContent='Snapshot nije dostupan: '+err.message});
