/* StockScout Trend Birth — descriptive market internals (no additional scan).
 * Pure functions are exported for Node tests; browser loads a compact EOD JSON.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { root.TrendBirthStats = api; if (root.document) root.document.addEventListener('DOMContentLoaded', api.start); }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const SCHEMA = 'trend-birth-market-internals-v1';
  const SCOPE = 'unified-plus-tracked-watchlist';
  const COLORS = ['#f26d79', '#ef9d54', '#e6c861', '#91cf74', '#37cb89'];
  const FMT = new Intl.NumberFormat('hr-HR', {maximumFractionDigits: 2});
  function fmt(value, unit) { return value === null || value === undefined || !Number.isFinite(value) ? '—' : FMT.format(value) + (unit || ''); }
  function metric(point, name) {
    if (['qualityBreadthPct','fourBreadthPct','pressurePct','velocityPp','accelerationPp'].includes(name)) return point[name];
    throw Error('Nepoznati pokazatelj');
  }
  function validate(payload) {
    if (!payload || payload.schemaVersion !== SCHEMA || payload.scope !== SCOPE || !Array.isArray(payload.points) || !payload.points.length) throw Error('Nedostaje valjana povijest market internals');
    let previous = null;
    for (const p of payload.points) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(p.sessionDate) || (previous && p.sessionDate <= previous.sessionDate)) throw Error('Neispravan redoslijed EOD datuma');
      if (typeof p.runId !== 'string' || !p.runId || !Number.isInteger(p.evaluatedCount) || p.evaluatedCount <= 0 || !Number.isInteger(p.unavailableCount) || p.unavailableCount < 0) throw Error('Neispravno očitanje');
      const counts = Object.keys(p.counts || {});
      if (counts.length !== 5 || ![0, 1, 2, 3, 4].every(i => Number.isInteger(p.counts[i]) && p.counts[i] >= 0) || [0, 1, 2, 3, 4].reduce((n, i) => n + p.counts[i], 0) !== p.evaluatedCount) throw Error('Neusklađen broj faza');
      if (Math.abs(p.qualityBreadthPct - (p.counts[3] + p.counts[4]) / p.evaluatedCount * 100) > 0.001 ||
          Math.abs(p.fourBreadthPct - p.counts[4] / p.evaluatedCount * 100) > 0.001 ||
          Math.abs(p.pressurePct - [0, 1, 2, 3, 4].reduce((n, i) => n + i * p.counts[i], 0) / (4 * p.evaluatedCount) * 100) > 0.001) throw Error('Netočan pokazatelj');
      if (!previous) {
        if (p.transitions !== null || p.matchedCount !== null || p.previousSessionDate !== null) throw Error('Prvo očitanje nema par');
      } else {
        if (p.previousSessionDate !== previous.sessionDate || !Array.isArray(p.transitions) || p.transitions.length !== 5 ||
            !p.transitions.every(row => Array.isArray(row) && row.length === 5 && row.every(n => Number.isInteger(n) && n >= 0))) throw Error('Neispravna matrica prijelaza');
        const n = p.transitions.flat().reduce((a,b) => a+b,0);
        if (n !== p.matchedCount || p.matchedCount + p.newCoverage !== p.evaluatedCount ||
            p.matchedCount + p.lostCoverage !== previous.evaluatedCount) throw Error('Prijelazi nisu usklađeni s pokrivenošću');
        const qIn = p.transitions.slice(0,3).reduce((a,r) => a+r[3]+r[4],0);
        const qOut = p.transitions.slice(3).reduce((a,r) => a+r[0]+r[1]+r[2],0);
        const fIn = p.transitions.slice(0,4).reduce((a,r)=>a+r[4],0);
        const fOut = p.transitions[4].slice(0,4).reduce((a,b)=>a+b,0);
        if (qIn !== p.qualityFlow.in || qOut !== p.qualityFlow.out || qIn-qOut !== p.qualityFlow.net ||
            fIn !== p.fourFlow.in || fOut !== p.fourFlow.out || fIn-fOut !== p.fourFlow.net) throw Error('Neusklađeni tokovi');
      }
      previous = p;
    }
    if (payload.latestSessionDate !== previous.sessionDate || payload.latestRunId !== previous.runId) throw Error('Zadnje očitanje nije usklađeno');
    return payload;
  }
  function slope(points, idx, size, field) {
    if (!Number.isInteger(size) || idx - size + 1 < 0) return null;
    const values = points.slice(idx-size+1, idx+1).map(p => metric(p,field));
    const cx = (size - 1)/2;
    const denom = size*(size*size-1)/12;
    return values.reduce((acc,v,i)=>acc+(i-cx)*v,0)/denom;
  }
  function dynamics(points, idx, size, field) {
    const velocity = slope(points,idx,size,field);
    const previous = slope(points,idx-size,size,field);
    return {velocity, acceleration:velocity===null || previous===null?null:velocity-previous};
  }
  function percentile(points, idx, field) {
    if (idx < 1) return {value:null, comparisons:0};
    const v = metric(points[idx],field);
    const older = points.slice(0,idx).map(p=>metric(p,field)).filter(Number.isFinite);
    if (!Number.isFinite(v) || !older.length) return {value:null, comparisons:older.length};
    const lower = older.filter(x=>x<v).length;
    const equal = older.filter(x=>x===v).length;
    return {value:100*(lower+0.5*equal)/older.length,comparisons:older.length};
  }
  function withDynamics(points, size) {
    return points.map((p,i) => {
      const d=dynamics(points,i,size,'qualityBreadthPct');
      return {...p,velocityPp:d.velocity,accelerationPp:d.acceleration};
    });
  }
  function windowStart(latest, range) {
    if (range === 'all') return '0000-01-01';
    const date = new Date(latest+'T12:00:00Z');
    if (!Number.isFinite(date.getTime())) throw Error('Neispravan datum');
    if (range === '1m') date.setUTCMonth(date.getUTCMonth()-1);
    else if (range === '3m') date.setUTCMonth(date.getUTCMonth()-3);
    else if (range === '1y') date.setUTCFullYear(date.getUTCFullYear()-1);
    else if (range === '5y') date.setUTCFullYear(date.getUTCFullYear()-5);
    else throw Error('Nepoznato razdoblje');
    return date.toISOString().slice(0,10);
  }
  function weekKey(day) {
    const date = new Date(day+'T12:00:00Z');
    date.setUTCDate(date.getUTCDate()-(date.getUTCDay()+6)%7);
    return date.toISOString().slice(0,10);
  }
  function group(points, aggregation) {
    if (!['D','W','M'].includes(aggregation)) throw Error('Neispravan interval');
    if (aggregation === 'D') return points.map(p => ({date:p.sessionDate,first:p.sessionDate,last:p.sessionDate,days:1,counts:p.counts,evaluatedCount:p.evaluatedCount,qualityBreadthPct:p.qualityBreadthPct,fourBreadthPct:p.fourBreadthPct,pressurePct:p.pressurePct,velocityPp:p.velocityPp,accelerationPp:p.accelerationPp}));
    const buckets = new Map();
    for (const p of points) {
      const key = aggregation === 'W' ? weekKey(p.sessionDate) : p.sessionDate.slice(0,7);
      if (!buckets.has(key)) buckets.set(key,{date:key,first:p.sessionDate,last:p.sessionDate,days:0,counts:{0:0,1:0,2:0,3:0,4:0},evaluatedCount:0});
      const bucket = buckets.get(key);
      bucket.last=p.sessionDate;bucket.days++;bucket.evaluatedCount+=p.evaluatedCount;bucket.velocityPp=p.velocityPp;bucket.accelerationPp=p.accelerationPp;
      for (let i=0;i<5;i++) bucket.counts[i]+=p.counts[i];
    }
    return Array.from(buckets.values(), b => ({...b,
      qualityBreadthPct:100*(b.counts[3]+b.counts[4])/b.evaluatedCount,
      fourBreadthPct:100*b.counts[4]/b.evaluatedCount,
      pressurePct:100*[0,1,2,3,4].reduce((n,i)=>n+i*b.counts[i],0)/(4*b.evaluatedCount)
    }));
  }
  function transitions(points, start) {
    const matrix=Array.from({length:5},()=>Array(5).fill(0));
    let pairs=0, matched=0;
    for (const p of points) {
      if (!p.transitions || p.sessionDate < start || p.previousSessionDate < start) continue;
      pairs++;matched+=p.matchedCount;
      for (let i=0;i<5;i++) for(let j=0;j<5;j++) matrix[i][j]+=p.transitions[i][j];
    }
    return {matrix,pairs,matched};
  }
  function regime(velocity, acceleration) {
    if (velocity === null || acceleration === null) return 'Premalo EOD očitanja';
    if (velocity >= 0) return acceleration >= 0 ? 'Širenje se ubrzava' : 'Širenje usporava';
    return acceleration >= 0 ? 'Pad se ublažava' : 'Pad se ubrzava';
  }
  function el(id) { return document.getElementById(id); }
  function renderChart(rows, field, zoom) {
    const host=el('siChart');
    host.textContent='';
    if (!rows.length) {host.textContent='Nema očitanja u tom razdoblju.';return;}
    const signed=field==='velocityPp'||field==='accelerationPp';
    const values=rows.map(row=>metric(row,field)).filter(Number.isFinite);
    const ymax=signed?Math.max(.01,...values.map(Math.abs))*1.15:+zoom;
    const width=Math.max(720,rows.length*18+68), height=260, left=50, right=14, top=15, bottom=42;
    const end=height-bottom, baseline=signed?(top+end)/2:end;
    const ns='http://www.w3.org/2000/svg';
    function svgEl(tag,attrs,parent) {const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs||{}))n.setAttribute(k,String(v));(parent||svg).appendChild(n);return n;}
    const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 '+width+' '+height);svg.setAttribute('role','img');svg.setAttribute('aria-label','Povijesni stupci '+field+', raspon osi '+(signed?'± '+fmt(ymax)+' pp/EOD': '0–'+ymax+'%'));
    const plotWidth=width-left-right;
    const step=plotWidth/rows.length, bar=Math.max(2,Math.min(23,step*.7));
    const levels=signed?[-1,-.5,0,.5,1]:[0,.25,.5,.75,1];
    for (const v of levels) {
      const y=signed?baseline-(end-top)*v/2:end-(end-top)*v;
      svgEl('line',{x1:left,y1:y,x2:width-right,y2:y,stroke:v===0&&signed?'#879bb4':'#28405b','stroke-width':v===0&&signed?1.5:.7});
      const t=svgEl('text',{x:left-7,y:y+4,'text-anchor':'end',fill:'#a7b7c9','font-size':11});
      t.textContent=fmt(ymax*v,signed?' pp':'%');
    }
    rows.forEach((row,i)=>{
      const v=metric(row,field), x=left+i*step+(step-bar)/2;
      if(Number.isFinite(v)) {
        const clipped=signed?Math.max(-ymax,Math.min(ymax,v)):Math.min(v,ymax);
        const y=signed?baseline-(end-top)*clipped/(2*ymax):end-(end-top)*clipped/ymax;
        const color=signed?(v<0?'#f26d79':'#37cb89'):field==='pressurePct'?'#e5bd64':field==='fourBreadthPct'?'#37cb89':'#58abf2';
        const rect=svgEl('rect',{x,y:Math.min(y,baseline),width:bar,height:Math.max(1,Math.abs(baseline-y)),fill:color,rx:1});
        const title=svgEl('title',{},rect);title.textContent=row.first+' — '+row.last+': '+fmt(v,signed?' pp/EOD':'%')+' ('+row.days+' EOD)';
        if(!signed && v>ymax) svgEl('circle',{cx:x+bar/2,cy:top,r:2,fill:'#f26d79'});
      }
      if (i===0 || i===rows.length-1 || i%Math.max(1,Math.ceil(rows.length/9))===0) {
        const tick=svgEl('text',{x:x+bar/2,y:height-19,'text-anchor':'middle',fill:'#a7b7c9','font-size':10});
        tick.textContent=row.date.slice(5);
      }
    });
    host.appendChild(svg);
  }
  function renderMatrix(value) {
    const table=el('siMatrix'); table.textContent='';
    const header=document.createElement('tr');
    const corner=document.createElement('th');corner.textContent='Iz ↓ / U →';header.appendChild(corner);
    for (let j=0;j<5;j++) {const th=document.createElement('th');th.textContent=j+'/4';th.style.color=COLORS[j];header.appendChild(th);}
    const head=document.createElement('thead');head.appendChild(header);table.appendChild(head);
    const body=document.createElement('tbody');
    for(let i=0;i<5;i++){
      const tr=document.createElement('tr'),th=document.createElement('th');th.textContent=i+'/4';th.style.color=COLORS[i];tr.appendChild(th);
      const sum=value.matrix[i].reduce((a,b)=>a+b,0);
      for(let j=0;j<5;j++){
        const td=document.createElement('td');const v=value.matrix[i][j];const p=sum?100*v/sum:null;
        td.textContent=fmt(p,'%');td.title=v+' od '+sum+' usporedivih tickera / EOD prijelaza ('+i+'/4 → '+j+'/4)';
        td.style.backgroundColor='color-mix(in srgb, '+COLORS[j]+' '+(p===null?0:Math.round(6+Math.min(48,p*.48)))+'%, #112138)';
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
    table.appendChild(body);
    el('siMatrixMeta').textContent=value.pairs+' uspoređenih EOD parova · '+FMT.format(value.matched)+' usporedivih ticker-prijelaza (redak = 100% ako postoje opažanja).';
  }
  function fill(id, value, subtitle) {
    el(id).textContent=value;
    if (subtitle!==undefined) el(id+'Sub').textContent=subtitle;
  }
  function render(data) {
    const raw=data.points, latest=raw[raw.length-1];
    const range=el('siRange').value, aggregation=el('siAggregation').value;
    const field=el('siMetric').value, zoom=el('siZoom').value;
    const n=+el('siWindow').value;
    const points=withDynamics(raw,n);
    const signed=field==='velocityPp'||field==='accelerationPp';
    const start=windowStart(latest.sessionDate,range);
    const filtered=points.filter(p=>p.sessionDate>=start), groups=group(filtered,aggregation);
    const idx=points.length-1, d=dynamics(points,idx,n,'qualityBreadthPct');
    const pressureDynamic=dynamics(points,idx,n,'pressurePct');
    const per=percentile(points,idx,field);
    const previous=points.length>1?points[points.length-2]:null;
    fill('siQuality',fmt(latest.qualityBreadthPct,'%'),(latest.counts[3]+latest.counts[4])+' / '+latest.evaluatedCount+' evaluiranih');
    fill('siPressure',fmt(latest.pressurePct,'%'),'0–100 · srednja faza ponderirana 0/4–4/4');
    fill('siVelocity',fmt(d.velocity,' pp/EOD'),n+' EOD · nagib linearnog trenda 3+/4');
    fill('siAcceleration',fmt(d.acceleration,' pp/EOD'),'promjena nagiba dvaju nepoklopljenih prozora od '+n+' EOD');
    fill('siNetFlow',fmt(latest.qualityFlow.net),latest.qualityFlow.in===null?'Bez prethodne EOD sesije':'Ulazi '+latest.qualityFlow.in+' · izlazi '+latest.qualityFlow.out+' (isti tickeri)');
    fill('siPercentile',fmt(per.value,'%'),per.comparisons+' ranijih EOD očitanja za: '+el('siMetric').selectedOptions[0].text);
    fill('siCoverage',fmt(latest.overlapPct,'%'),latest.matchedCount===null?'Nema prethodne sesije':latest.matchedCount+' u paru · '+latest.newCoverage+' novih · '+latest.lostCoverage+' izašlo');
    el('siRegime').textContent=regime(d.velocity,d.acceleration);
    el('siRegimeDesc').textContent='Deskriptivno: 3+/4 breadth, nagib zadnjih '+n+' EOD i promjena u odnosu na prethodnih '+n+'. Nije signal za trgovanje.';
    el('siLatest').textContent='Zadnje očitanje: '+latest.sessionDate+' · '+points.length+' EOD zapisa u cijeloj arhivi · '+filtered.length+' u odabranom rasponu. Mjerenje nakon zatvaranja tržišta.';
    el('siChartMeta').textContent=groups.length+' stupaca ('+aggregation+'); '+(signed?'Za W/M je prikazan nagib/akceleracija zadnjeg zabilježenog EOD-a u intervalu, crveno = negativno; os se automatski prilagođava.':'Za W/M se ponderira brojem ticker-dana.')+' Boja nije trading signal.';
    renderChart(groups,field,zoom);
    renderMatrix(transitions(points,start));
    el('siFlows').textContent=previous?('Zadnji EOD: 3+/4 ulazi '+latest.qualityFlow.in+', izlazi '+latest.qualityFlow.out+', neto '+fmt(latest.qualityFlow.net)+
      ' · 4/4 ulazi '+latest.fourFlow.in+', izlazi '+latest.fourFlow.out+', neto '+fmt(latest.fourFlow.net)+
      ' · promjena breadth na istim tickerima '+fmt(latest.matchedQualityDeltaPp,' pp')):'Prvi dan arhive: nema parnih prijelaza.';
    el('siPressureDynamics').textContent='Setup pressure: nagib '+fmt(pressureDynamic.velocity,' pp/EOD')+', akceleracija '+fmt(pressureDynamic.acceleration,' pp/EOD')+'. Različit obuhvat tickera može utjecati na ukupnu širinu.';
    el('siZoom').disabled=signed;
    el('siChart').setAttribute('data-selected-metric',field);
  }

  function validateComposite(data) {
    if (!data || data.schemaVersion !== 'trend-birth-composite-backtest-v1' ||
        data.scope !== 'equity-etf-proxy-not-historical-stockscout' ||
        !data.oos || !Array.isArray(data.oos.regimes) || !Number.isInteger(data.oos.n) ||
        !data.calibration || !data.latestActual ||
        !Number.isFinite(data.latestActual.score) || data.latestActual.score < 0 || data.latestActual.score > 100 ||
        !/^\d{4}-\d{2}-\d{2}$/.test(data.latestActual.sessionDate))
      throw Error('Neispravan backtest / Composite Score zapis');
    return data;
  }
  function renderComposite(raw, eodDate) {
    const data = validateComposite(raw), report=data.oos, latest=data.latestActual;
    const stale=latest.sessionDate!==eodDate;
    el('siCompositeScore').textContent=fmt(latest.score,' / 100');
    el('siCompositeScoreSub').textContent=(stale?'Zastarjelo mjerenje '+latest.sessionDate+' · ':'')+
      'indikativno, '+latest.actualHistoryCount+' stvarnih EOD dana; nije verificiran trading signal';
    el('siCompositeSpread').textContent=fmt(report.topMinusBottomPp,' pp');
    el('siCompositeSpreadSub').textContent='SPY H20: gornja četvrtina '+fmt(report.highScoreMean20dPct,'%')+
      ', donja '+fmt(report.lowScoreMean20dPct,'%')+'. Korelacija '+fmt(report.scoreReturnPearson)+'.';
    el('siCompositeSample').textContent=FMT.format(report.n);
    el('siCompositeSampleSub').textContent=report.startYear+'–'+report.endYear+
      ' · '+report.testedYears+' kalendarskih godina · '+report.positiveSpreadYears+' s pozitivnom razlikom';
    const names={breadth:'Širina 3+/4',pressure:'Setup pressure',velocity:'Brzina',acceleration:'Akceleracija',
      flow:'Neto pomak istog skupa',persistence:'Trajnost širine'};
    const parts=Object.entries(data.calibration.weights).map(([k,w])=>
      names[k]+': '+(data.calibration.directions[k]<0?'obrnuto ':'')+w+
      '× (zadnji percentil '+fmt(latest.components[k],'%')+')');
    el('siCompositeFactors').textContent='Profil: '+data.calibration.selectedProfile+
      ' · komponente: '+parts.join(' · ')+
      '. Ponderi su odabrani na povijesnim ETF proxy godinama, a percentili se računaju samo na stvarnoj StockScout arhivi.';
    const target=el('siCompositeRegimes');
    target.replaceChildren();
    const thead=document.createElement('thead'), header=document.createElement('tr');
    for(const h of ['Režim','Uzorak','Gornji kvartil H20','Donji kvartil H20','Razlika (pp)']) {
      const th=document.createElement('th');th.textContent=h;header.appendChild(th);
    }
    thead.appendChild(header);target.appendChild(thead);
    const body=document.createElement('tbody');
    const translations={
      '2008 GFC':'2008 · financijska kriza',
      '2011 sovereign debt':'2011 · dužnička kriza',
      '2015-16 industrial correction':'2015–16 · korekcija',
      '2018 tightening':'2018 · stezanje monetarne politike',
      '2020 pandemic':'2020 · pandemija',
      '2022 inflation bear':'2022 · inflacija / bear',
      '2023-24 rally':'2023–24 · rast',
      'High volatility (VIX >= 30)':'Stres (VIX ≥ 30)',
      'Lower volatility (VIX < 20)':'Niska volatilnost (VIX < 20)',
    };
    for(const item of report.regimes) {
      const tr=document.createElement('tr');
      const cells=[translations[item.regime]||item.regime,
        FMT.format(item.n),fmt(item.highScoreMean20dPct,'%'),fmt(item.lowScoreMean20dPct,'%'),
        fmt(item.topMinusBottomPp,' pp')];
      cells.forEach((c,i)=>{const td=document.createElement(i===0?'th':'td');td.textContent=c;
        if(i===4 && Number.isFinite(item.topMinusBottomPp)) td.style.color=item.topMinusBottomPp>=0?'#37cb89':'#f26d79';
        tr.appendChild(td);
      });
      body.appendChild(tr);
    }
    target.appendChild(body);
    el('siCompositeMethod').textContent='Walk-forward: '+report.n+
      ' izvanuzoračkih promatranja, interval 10 burzovnih dana, SPY realizirani prinos od sljedećeg prilagođenog zatvaranja do 20. idućeg zatvaranja. '+
      'Za svaki testni kalendarski period težine su birane SAMO prema prije završenim godinama ('+
      data.method.testedProfiles+' kandidatskih profila). Izvor cijena zaključan na GitHub SHA; zadnji dan izvora '+
      data.source.lastDate+'. Nisu uračunati transakcijski troškovi; rezultati se djelomično preklapaju.';
    el('siCompositeStatus').textContent='EKSPERIMENTALNI pokazatelj · ETF proxy, slaba do umjerena izvanuzoračka veza s prinosima; '+
      'loši režimi ostaju prikazani ('+(stale?'Composite još nije osvježen za zadnje EOD podatke.':'zadnji EOD je osvježen.')+')';
  }

  function validateForward(value) {
    if (!value || value.schemaVersion !== 'trend-birth-stage-forward-v2' ||
        value.scope !== SCOPE || !/^\d{4}-\d{2}-\d{2}$/.test(value.asOf) ||
        !Array.isArray(value.horizons) || value.horizons.join(',') !== '5,20,60' ||
        !value.byHorizon || !Number.isInteger(value.stageTransitions))
      throw Error('Neispravno arhivirani stvarni ishodi setupa');
    for (const h of value.horizons) for (let stage=0;stage<=4;stage++) {
      const item=value.byHorizon[String(h)]?.[String(stage)];
      if (!item || !Number.isInteger(item.n) || !Number.isInteger(item.expectedMatured) ||
          !Number.isInteger(item.missingMatured) || !Number.isInteger(item.pending) ||
          item.n+item.missingMatured!==item.expectedMatured ||
          (item.n && !Number.isFinite(item.meanPct))) throw Error('Neusklađen uzorak ishoda');
    }
    return value;
  }
  function renderForward(raw, eodDate) {
    const data=validateForward(raw);
    const status=el('siForwardStatus');
    const stale=data.asOf!==eodDate;
    status.textContent=(stale?'UPOZORENJE: mjerenje nije osvježeno za današnji EOD · ':'')+
      'Stvarna point-in-time povijest · '+data.asOf+
      ' · '+FMT.format(data.stageTransitions)+' potvrđenih prijelaza, '+FMT.format(data.archivedEventDays)+' datuma.';
    el('siForwardSummary').textContent='Uzorci dospijevaju nakon 1 + 5/20/60 burzovnih sesija. '+
      'Samo potpun broj dospjelih ishoda u tablici ulazi u prosjek; nedostajuće cijene ne tretiraju se kao 0%.';
    const table=el('siForwardTable');
    table.replaceChildren();
    const thead=document.createElement('thead'), tr=document.createElement('tr');
    for (const label of ['Faza','Horizont','Dospjelo s cijenom','Na čekanju','Pokrivenost','Prosjek','Medijan','% pozitivnih','P10 / P90']) {
      const th=document.createElement('th'); th.textContent=label; tr.appendChild(th);
    }
    thead.appendChild(tr); table.appendChild(thead);
    const tbody=document.createElement('tbody');
    for (let stage=0;stage<=4;stage++) for (const horizon of data.horizons) {
      const row=data.byHorizon[String(horizon)][String(stage)], r=document.createElement('tr');
      const cells=[stage+'/4',horizon+'D',FMT.format(row.n)+' / '+FMT.format(row.expectedMatured),
        FMT.format(row.pending),fmt(row.coveragePct,'%'),fmt(row.meanPct,'%'),
        fmt(row.medianPct,'%'),fmt(row.winRatePct,'%'),
        fmt(row.p10Pct,'%')+' / '+fmt(row.p90Pct,'%')];
      cells.forEach((value,i)=>{const cell=document.createElement(i===0?'th':'td');cell.textContent=value;
        if (i===0) cell.style.color=COLORS[stage];
        if (i===5 && Number.isFinite(row.meanPct)) cell.style.color=row.meanPct>=0?'#37cb89':'#f26d79';
        r.appendChild(cell);
      });
      tbody.appendChild(r);
    }
    table.appendChild(tbody);
  }

  async function start() {
    const status=el('siStatus');
    if (!status) return;
    try {
      const response=await fetch('data/trend-birth-market-internals.json',{cache:'no-store'});
      if (!response.ok) throw Error('HTTP '+response.status);
      const data=validate(await response.json());
      for(const id of ['siRange','siAggregation','siMetric','siZoom','siWindow']) el(id).addEventListener('change',()=>render(data));
      render(data);
      status.hidden=true;
      try {
        const compositeResponse=await fetch('data/trend-birth-composite-backtest.json',{cache:'no-store'});
        if (!compositeResponse.ok) throw Error('HTTP '+compositeResponse.status);
        renderComposite(await compositeResponse.json(),data.latestSessionDate);
      } catch (error) {
        el('siCompositeStatus').textContent='Backtest nije dostupan: '+(error?.message||String(error));
      }
      try {
        const forwardResponse=await fetch('data/trend-birth-stage-forward.json',{cache:'no-store'});
        if (!forwardResponse.ok) throw Error('HTTP '+forwardResponse.status);
        renderForward(await forwardResponse.json(),data.latestSessionDate);
      } catch (error) {
        el('siForwardStatus').textContent='Stvarni ishodi zasad nisu dostupni: '+(error?.message||String(error));
      }
    } catch(e) {
      status.textContent='Statistika nije dostupna: '+(e?.message||String(e))+' · Pokušaj osvježiti stranicu.';
      status.className='si-error';
    }
  }
  return {validate, validateComposite, validateForward, metric, slope, dynamics, withDynamics, percentile, windowStart, weekKey, group, transitions, regime, start};
});
