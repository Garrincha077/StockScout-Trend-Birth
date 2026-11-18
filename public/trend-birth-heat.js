/* Trend Birth Market Thermometer — real EOD only, point-in-time percentile ranks.
 * Descriptive market temperature. It does not affect Composite Score or trading signals.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TrendBirthHeat = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const MIN_HISTORY = 12;
  const LOOKBACK = 252;
  const HEAT_FACTORS = [
    {key:'breadth',label:'Quality breadth 3+/4',field:'qualityBreadthPct',weight:40,unit:'%'},
    {key:'pressure',label:'Setup pressure',field:'pressurePct',weight:30,unit:'%'},
    {key:'four',label:'Udio 4/4',field:'fourBreadthPct',weight:20,unit:'%'},
    {key:'persistence',label:'Trajnost 3+/4 (10 EOD)',field:'persistencePct',weight:10,unit:'%'}
  ];
  const MOVE_FACTORS = [
    {key:'velocity',label:'Brzina 5 EOD',field:'velocityPp',weight:45,unit:' pp/EOD'},
    {key:'acceleration',label:'Akceleracija 5+5 EOD',field:'accelerationPp',weight:30,unit:' pp/EOD'},
    {key:'flow',label:'Promjena kvalitete istih tickera',field:'matchedQualityDeltaPp',weight:25,unit:' pp'}
  ];
  const ZONES = [
    {key:'very-cold',label:'Vrlo hladno',color:'#176b4a'},
    {key:'cold',label:'Hladno',color:'#4caf75'},
    {key:'neutral',label:'Neutralno',color:'#e2bf54'},
    {key:'hot',label:'Vruće',color:'#e79142'},
    {key:'overheated',label:'Pregrijano',color:'#d74c55'}
  ];
  const zoneFor = score => finite(score) && score>=0 && score<=100 ? ZONES[Math.min(4,Math.floor(score/20))] : null;
  const fmt = (v,digits=1) => Number.isFinite(v) ? v.toLocaleString('hr-HR',{maximumFractionDigits:digits}) : '—';
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  function percentile(value, previous) {
    const history=previous.filter(finite).slice(-LOOKBACK);
    if (!finite(value) || history.length<MIN_HISTORY) return {value:null,historyN:history.length};
    const less=history.filter(v=>v<value).length;
    const ties=history.filter(v=>v===value).length;
    return {value:100*(less+0.5*ties)/history.length,historyN:history.length};
  }
  function slope(values,end,n=5) {
    if(end<n-1) return null;
    const slice=values.slice(end-n+1,end+1);
    if(slice.length!==n || slice.some(v=>!finite(v))) return null;
    const centre=(n-1)/2,den=n*(n*n-1)/12;
    return slice.reduce((sum,value,i)=>sum+(i-centre)*value,0)/den;
  }
  function exchangeCalendar(points,report) {
    if (!report || report.asOf!==points.at(-1)?.sessionDate) return [];
    if (Array.isArray(report.exchangeSessions)) return report.exchangeSessions;
    // Older V2 reports already identify every missing session in their coverage
    // window. Their union with observed dates is the same verified calendar.
    const quality=report.dataQuality;
    if (!quality || !Array.isArray(quality.missingExchangeSessions) ||
        typeof quality.coverageWindowStart!=='string') return [];
    const observed=points.filter(p=>p.sessionDate>=quality.coverageWindowStart).map(p=>p.sessionDate);
    const sessions=[...observed,...quality.missingExchangeSessions].sort();
    if (observed.length!==quality.archivedSessions || sessions.length!==quality.exchangeSessionsInWindow ||
        new Set(sessions).size!==sessions.length || sessions.at(-1)!==report.asOf) return [];
    return sessions;
  }
  function factorRows(point,archive,factors,readyCore) {
    let weightReady=0;
    const rows=factors.map(f=>{
      const ranked=percentile(point[f.field],archive.map(p=>f.key==='flow'&&!(p.overlapPct>=95)?null:p[f.field]));
      const ready=ranked.value!==null && (f.key!=='flow'||point.overlapPct>=95);
      if (ready)weightReady+=f.weight;
      return {...f,raw:point[f.field]??null,percentile:ready?ranked.value:null,
        historyN:ranked.historyN,ready,normalizedWeight:0,contribution:0};
    });
    const complete=rows.filter(r=>r.ready).length>=readyCore;
    if(complete) for(const r of rows) if(r.ready) {
      r.normalizedWeight=100*r.weight/weightReady;
      r.contribution=r.normalizedWeight*r.percentile/100;
    }
    return {rows,complete,weightReady,
      score:complete?rows.reduce((s,r)=>s+r.contribution,0):null};
  }
  function computeHeatHistory(points,exchangeSessions=[]) {
    if (!Array.isArray(points)) throw Error('Market Thermometer: očekuje se niz EOD opažanja');
    for(let i=0;i<points.length;i++) {
      if(!/^\d{4}-\d{2}-\d{2}$/.test(points[i].sessionDate)||
         (i&&points[i-1].sessionDate>=points[i].sessionDate))
        throw Error('Market Thermometer: EOD datumi moraju biti uređeni i jedinstveni');
    }
    if (!Array.isArray(exchangeSessions) || exchangeSessions.some((day,i)=>
        !/^\d{4}-\d{2}-\d{2}$/.test(day) || (i&&exchangeSessions[i-1]>=day)))
      throw Error('Market Thermometer: neispravan burzovni kalendar');
    const positions=new Map(exchangeSessions.map((day,i)=>[day,i]));
    const breadth=points.map(p=>p.qualityBreadthPct);
    const prepared=points.map((p,i)=>{
      const velocity=slope(breadth,i);
      const earlier=slope(breadth,i-5);
      const persistence=i>=9&&breadth.slice(i-9,i+1).every(finite)?
        breadth.slice(i-9,i+1).reduce((a,b)=>a+b,0)/10:null;
      return {...p,persistencePct:persistence,velocityPp:velocity,
        accelerationPp:finite(velocity)&&finite(earlier)?velocity-earlier:null};
    });
    return prepared.map((p,i)=>{
      const archive=prepared.slice(0,i);
      const heat=factorRows(p,archive,HEAT_FACTORS,3);
      // The three core inputs must be ready; persistence never substitutes for missing core data.
      const coreReady=heat.rows.slice(0,3).every(r=>r.ready);
      if(!coreReady){heat.complete=false;heat.score=null;heat.rows.forEach(r=>{r.contribution=0;r.normalizedWeight=0;});}
      const moves=factorRows(p,archive,MOVE_FACTORS,2);
      const momentum=moves.complete?moves.rows.reduce((s,r)=>s+(r.normalizedWeight*(2*r.percentile-100)/100),0):null;
      const up=moves.rows.filter(r=>r.ready&&r.raw>0).length;
      const down=moves.rows.filter(r=>r.ready&&r.raw<0).length;
      const candidate=momentum!==null && momentum>=30 && up>=2?'warming':
        momentum!==null && momentum<=-30 && down>=2?'cooling':'stable';
      const oldest=Math.min(...heat.rows.filter(r=>r.ready).map(r=>r.historyN));
      const zone=heat.complete?zoneFor(heat.score):null;
      return {sessionDate:p.sessionDate,source:p,score:heat.score,zone,
        heatRows:heat.rows,readyHeat:heat.rows.filter(r=>r.ready).length,
        maturity:!heat.complete?'unavailable':oldest<60?'provisional':oldest<120?'medium':'mature',
        momentum,movementRows:moves.rows,candidate,trend:'stable',
        accelerationHighlight:moves.rows.find(r=>r.key==='acceleration')?.ready &&
          p.accelerationPp>0 && moves.rows.find(r=>r.key==='acceleration').percentile>=65,
        qualityWarning:i>0&&(p.overlapPct===null||p.overlapPct<95),
        continuity:i===0?true:positions.has(points[i-1].sessionDate)&&positions.has(p.sessionDate)?
          positions.get(p.sessionDate)-positions.get(points[i-1].sessionDate)===1:null};
    }).map((record,index,list)=>{
      // Two actually consecutive valid EOD observations confirm a warming/cooling regime.
      const prev=list[index-1];
      record.trend=record.candidate!=='stable'&&prev&&prev.candidate===record.candidate &&
        record.continuity&&record.momentum!==null&&prev.momentum!==null?
        record.candidate:'stable';
      return record;
    });
  }
  function windowStart(latest,range) {
    if(range==='all') return '0000-01-01';
    const d=new Date(latest+'T12:00:00Z');
    if(range==='1m')d.setUTCMonth(d.getUTCMonth()-1);
    else if(range==='3m')d.setUTCMonth(d.getUTCMonth()-3);
    else if(range==='1y')d.setUTCFullYear(d.getUTCFullYear()-1);
    else if(range==='5y')d.setUTCFullYear(d.getUTCFullYear()-5);
    else throw Error('Nepoznato razdoblje: '+range);
    return d.toISOString().slice(0,10);
  }
  function mount(payload,forwardReport) {
    const history=computeHeatHistory(payload.points,exchangeCalendar(payload.points,forwardReport));
    const $=id=>document.getElementById(id);
    const range=$('siHeatRange'),slider=$('siHeatPoint'),chart=$('siHeatChart');
    if(!range||!slider||!chart)return history;
    let selectedDate=history.at(-1).sessionDate;
    let compositeSource='actual';
    const svgNS='http://www.w3.org/2000/svg';
    function node(tag,props,parent){
      const el=document.createElementNS(svgNS,tag);
      Object.entries(props||{}).forEach(([k,v])=>el.setAttribute(k,String(v)));
      parent.appendChild(el);return el;
    }
    function makeCard(id,record,rowKey) {
      const card=$(id),factor=record.heatRows.find(r=>r.key===rowKey);
      if(!card||!factor)return;
      card.dataset.heatZone=factor.ready?zoneFor(factor.percentile).key:'unavailable';
      const flag=card.querySelector('.si-heat-pill');
      if(flag)flag.textContent=factor.ready?fmt(factor.percentile,0)+'. pct · '+zoneFor(factor.percentile).label:'Čeka ≥12 ranijih EOD';
      if(flag)flag.title='Temperatura povijesnog percentila, ne ocjena kvalitete dionice.';
    }
    const latest=history.at(-1);
    $('siFour').textContent=fmt(latest.source.fourBreadthPct)+'%';
    $('siFourSub').textContent=latest.source.counts['4']+' / '+latest.source.evaluatedCount+' evaluiranih';
    $('siPersistence').textContent=fmt(latest.source.persistencePct)+'%';
    $('siPersistenceSub').textContent='Prosjek 3+/4 kroz 10 stvarnih EOD očitanja';
    [['siQualityCard','breadth'],['siPressureCard','pressure'],
      ['siFourCard','four'],['siPersistenceCard','persistence']].forEach(([id,f])=>makeCard(id,latest,f));
    function show(record) {
      $('siHeatScore').textContent=record.score===null?'—':fmt(record.score)+' / 100';
      $('siHeatLabel').textContent=record.zone?record.zone.label:'Čeka povijest';
      $('siHeatLabel').dataset.heatZone=record.zone?.key||'unavailable';
      $('siHeatConfidence').textContent=record.score===null?
        'Još nema 12 prethodnih EOD očitanja za tri obvezna faktora.':
        (record.maturity==='provisional'?'PRELIMINARNO · 12–59 ranijih EOD':
          record.maturity==='medium'?'SREDNJA POUZDANOST · 60–119 ranijih EOD':
            'DULJA POVIJEST · najmanje 120 ranijih EOD')+
          ' · '+record.readyHeat+'/4 temperaturna faktora spremna';
      $('siHeatMomentum').textContent=record.momentum===null?'—':fmt(record.momentum,0)+' / ±100';
      const moveLabel={warming:'Zagrijavanje',cooling:'Hlađenje',stable:'Bez potvrđenog smjera'};
      $('siHeatMovement').textContent=moveLabel[record.trend]+
        (record.accelerationHighlight?' · akceleracija ≥65. percentila':'');
      $('siHeatCoverage').textContent=(record.qualityWarning?'Upozorenje: preklapanje tickera <95%.':
        'Usporedni skup: '+fmt(record.source.overlapPct)+'% preklapanja')+
        (record.continuity===false?' · razmak u EOD arhivi, bez interpolacije':
          record.continuity===null?' · burzovni kontinuitet nije potvrđen':'');
      $('siHeatSelected').textContent=record.sessionDate+' · '+(record.zone?
        fmt(record.score)+' / 100 · '+record.zone.label:'još bez valjane temperature')+
        ' · '+(compositeSource==='actual'?'datumski usklađeno s Composite EOD':'ETF proxy nema zajednički stock-univerzum');
      $('siHeatFormula').textContent='Temperatura = Σ(aktivna težina × percentil) / 100. '+
        'Bazne težine: breadth 40%, pressure 30%, 4/4 20%, trajnost 10%. '+
        'Samo prethodnih najviše 252 EOD očitanja; ≥12 za svaki faktor. '+
        'Nespremni faktor ispada iz izračuna, preostale težine zbrajaju se na 100%. '+
        'Raspoložive dinamike odvojene su od temperature.';
      const table=$('siHeatFactorTable');table.replaceChildren();
      const thead=document.createElement('thead'),tr=document.createElement('tr');
      ['Faktor','Sirovo','PIT percentil','Bazna težina','Efektivna težina','Doprinos','Povijest'].forEach(s=>{
        const th=document.createElement('th');th.textContent=s;tr.appendChild(th);
      });thead.appendChild(tr);table.appendChild(thead);
      const body=document.createElement('tbody');
      for(const row of record.heatRows){
        const tr=document.createElement('tr');
        [row.label,fmt(row.raw,3)+row.unit,row.ready?fmt(row.percentile,1)+'%':'—',
          row.weight+'%',row.ready&&record.score!==null?fmt(row.normalizedWeight,1)+'%':'—',
          row.ready&&record.score!==null?fmt(row.contribution,2)+' bod.':'—',
          row.historyN+' prethodnih'+(row.ready?'':' · nedovoljno')].forEach((value,i)=>{
          const td=document.createElement(i===0?'th':'td');td.textContent=value;tr.appendChild(td);
        });
        body.appendChild(tr);
      }
      table.appendChild(body);
      const foot=document.createElement('tfoot'),sum=document.createElement('tr');
      ['Market Thermometer','','','100%',
        record.score===null?'—':'100%',
        record.score===null?'—':fmt(record.score,2)+' / 100',''].forEach((s,i)=>{
        const td=document.createElement(i===0?'th':'td');td.textContent=s;sum.appendChild(td);
      });foot.appendChild(sum);table.appendChild(foot);
      $('siHeatDynamics').textContent='Smjer = 45% percentile brzine + 30% percentile akceleracije + 25% percentile neto pomaka '+
        'na istim tickerima, svaki transformiran u −100…+100. Prag ±30 i najmanje 2 pozitivne/negativne '+
        'sirove komponente, uz potvrdu kroz 2 susjedna valjana EOD-a. Danas: '+
        (record.momentum===null?'nedovoljna povijest':fmt(record.momentum,1))+
        '. Odvojeno od topline. '+(record.qualityWarning?'Preklapanje ispod praga, tok isključen.':'');
    }
    function draw() {
      const visible=history.filter(r=>r.sessionDate>=windowStart(history.at(-1).sessionDate,range.value));
      if(!visible.length)return;
      slider.min='0';slider.max=String(visible.length-1);
      let selected=visible.findIndex(r=>r.sessionDate===selectedDate);
      if(selected<0){selected=visible.length-1;selectedDate=visible[selected].sessionDate;}
      slider.value=String(selected);
      chart.replaceChildren();
      const width=970,height=280,left=45,right=22,top=18,bottom=42;
      const bottomY=height-bottom,plotH=bottomY-top;
      const ms=visible.map(p=>Date.parse(p.sessionDate+'T00:00:00Z'));
      const start=ms[0],duration=Math.max(1,ms.at(-1)-start);
      const x=i=>left+(ms[i]-start)/duration*(width-left-right);
      const y=v=>bottomY-v/100*plotH;
      const svg=node('svg',{viewBox:'0 0 '+width+' '+height,role:'img','aria-label':
        'Povijesna temperatura od 0 do 100, '+visible[0].sessionDate+' do '+visible.at(-1).sessionDate},chart);
      node('title',{},svg).textContent='Market Thermometer: zeleno hladno, crveno pregrijano. Praznine nisu popunjene.';
      ZONES.forEach((zone,i)=>{
        node('rect',{x:left,y:y((i+1)*20),width:width-left-right,height:y(i*20)-y((i+1)*20),
          fill:zone.color,'fill-opacity':0.12},svg);
        node('line',{x1:left,y1:y(i*20),x2:width-right,y2:y(i*20),
          stroke:'#36526d','stroke-width':0.8},svg);
      });
      node('line',{x1:left,y1:y(100),x2:width-right,y2:y(100),stroke:'#36526d'},svg);
      [0,20,40,60,80,100].forEach(v=>{
        node('text',{x:left-10,y:y(v)+4,'text-anchor':'end',fill:'#a9bed2','font-size':11},svg).textContent=String(v);
      });
      const indices=new Set([0,visible.length-1]);
      for(let i=1;i<=4;i++)indices.add(Math.round((visible.length-1)*i/5));
      [...indices].sort((a,b)=>a-b).forEach(i=>{
        node('text',{x:x(i),y:height-14,'text-anchor':i===0?'start':i===visible.length-1?'end':'middle',
          fill:'#a9bed2','font-size':11},svg).textContent=visible[i].sessionDate.slice(8,10)+'.'+visible[i].sessionDate.slice(5,7)+'.';
      });
      for(let i=1;i<visible.length;i++){
        const a=visible[i-1],b=visible[i];
        if(a.score===null||b.score===null||!b.continuity)continue;
        const segment=node('line',{x1:x(i-1),y1:y(a.score),x2:x(i),y2:y(b.score),
          stroke:'#e9f1fa','stroke-width':2.2,'stroke-linecap':'round',
          'stroke-dasharray':a.maturity==='provisional'||b.maturity==='provisional'?'5 4':'none'},svg);
        node('title',{},segment).textContent=b.sessionDate+' · '+fmt(b.score)+' / 100';
      }
      visible.forEach((p,i)=>{
        if(p.score===null)return;
        const dot=node('circle',{cx:x(i),cy:y(p.score),r:4,fill:p.zone.color,
          stroke:'#eef6ff','stroke-width':0.8},svg);
        node('title',{},dot).textContent=p.sessionDate+' · '+fmt(p.score,2)+' / 100 · '+p.zone.label;
      });
      const marker=node('circle',{cx:x(selected),cy:y(visible[selected].score??0),
        r:6,fill:'#fff',stroke:'#13233d','stroke-width':2},svg);
      function choose(i,emit) {
        i=Math.min(visible.length-1,Math.max(0,i));
        selectedDate=visible[i].sessionDate;slider.value=String(i);
        const point=visible[i];marker.setAttribute('cx',String(x(i)));
        marker.setAttribute('cy',String(y(point.score??0)));
        marker.style.visibility=point.score===null?'hidden':'visible';
        const bounds=marker.getBoundingClientRect(),clip=chart.getBoundingClientRect();
        if(bounds.left<clip.left+8)chart.scrollLeft-=clip.left+8-bounds.left;
        else if(bounds.right>clip.right-8)chart.scrollLeft+=bounds.right-clip.right+8;
        show(point);
        if(emit&&compositeSource==='actual')document.dispatchEvent(
          new CustomEvent('tb:statistics-date-select',{detail:{origin:'heat',date:selectedDate}}));
      }
      slider.oninput=()=>choose(+slider.value,true);
      svg.addEventListener('click',e=>{
        const rect=svg.getBoundingClientRect(),mouseX=(e.clientX-rect.left)/rect.width*width;
        let index=0,best=Infinity;
        visible.forEach((p,i)=>{const dx=Math.abs(x(i)-mouseX);if(dx<best){best=dx;index=i;}});
        choose(index,true);
      });
      $('siHeatChartMeta').textContent=visible.filter(p=>p.score!==null).length+' valjanih od '+visible.length+
        ' stvarnih EOD očitanja · '+visible[0].sessionDate+' – '+visible.at(-1).sessionDate+
          '. Linije i potvrda smjera traže potvrđene susjedne burzovne sesije. Nema ETF proxy backfilla.';
      choose(selected,false);
    }
    range.addEventListener('change',()=>{
      draw();
      if(compositeSource==='actual')document.dispatchEvent(
        new CustomEvent('tb:statistics-range-select',{detail:{origin:'heat',range:range.value}}));
      if(compositeSource==='actual')document.dispatchEvent(
        new CustomEvent('tb:statistics-date-select',{detail:{origin:'heat',date:selectedDate}}));
    });
    document.addEventListener('tb:statistics-date-select',e=>{
      if(e.detail?.origin!=='composite'||compositeSource!=='actual')return;
      if(history.some(p=>p.sessionDate===e.detail.date)){selectedDate=e.detail.date;draw();}
    });
    document.addEventListener('tb:statistics-range-select',e=>{
      if(e.detail?.origin!=='composite'||compositeSource!=='actual')return;
      if(['1m','3m','1y','5y','all'].includes(e.detail.range)){range.value=e.detail.range;draw();}
    });
    document.addEventListener('tb:statistics-source-select',e=>{
      if(e.detail?.origin!=='composite')return;
      compositeSource=e.detail.source;
      $('siHeatSyncStatus').textContent=compositeSource==='actual'?
        'Grafovi koriste istu kalendarsku os i dijele odabrani EOD datum i raspon.':
        'ETF proxy ima drugi univerzum i godine; automatsko usklađivanje s njim je isključeno.';
      if(compositeSource==='actual'){selectedDate=latest.sessionDate;range.value=$('siCompositeRange').value;draw();}
      else show(history.find(p=>p.sessionDate===selectedDate)||latest);
    });
    draw();
    document.dispatchEvent(new CustomEvent('tb:statistics-selection-request'));
    return history;
  }
  return {MIN_HISTORY,LOOKBACK,HEAT_FACTORS,MOVE_FACTORS,ZONES,
    percentile,slope,exchangeCalendar,zoneFor,computeHeatHistory,windowStart,mount};
});
