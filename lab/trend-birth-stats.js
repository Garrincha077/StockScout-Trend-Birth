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
      if (!['qualityBreadthPct','fourBreadthPct','pressurePct'].every(key =>
          Number.isFinite(p[key]) && p[key] >= 0 && p[key] <= 100)) throw Error('Neispravan numerički pokazatelj');
      if (Math.abs(p.qualityBreadthPct - (p.counts[3] + p.counts[4]) / p.evaluatedCount * 100) > 0.001 ||
          Math.abs(p.fourBreadthPct - p.counts[4] / p.evaluatedCount * 100) > 0.001 ||
          Math.abs(p.pressurePct - [0, 1, 2, 3, 4].reduce((n, i) => n + i * p.counts[i], 0) / (4 * p.evaluatedCount) * 100) > 0.001) throw Error('Netočan pokazatelj');
      if (!previous) {
        if (p.transitions !== null || p.matchedCount !== null || p.previousSessionDate !== null) throw Error('Prvo očitanje nema par');
        if (p.overlapPct !== null || p.matchedQualityDeltaPp !== null) throw Error('Prvo očitanje nema usporedni pokazatelj');
      } else {
        if (p.previousSessionDate !== previous.sessionDate || !Array.isArray(p.transitions) || p.transitions.length !== 5 ||
            !p.transitions.every(row => Array.isArray(row) && row.length === 5 && row.every(n => Number.isInteger(n) && n >= 0))) throw Error('Neispravna matrica prijelaza');
        const n = p.transitions.flat().reduce((a,b) => a+b,0);
        if (n !== p.matchedCount || p.matchedCount + p.newCoverage !== p.evaluatedCount ||
            p.matchedCount + p.lostCoverage !== previous.evaluatedCount) throw Error('Prijelazi nisu usklađeni s pokrivenošću');
        if (!Number.isFinite(p.overlapPct) || p.overlapPct < 0 || p.overlapPct > 100 ||
            (p.matchedCount > 0 ? !Number.isFinite(p.matchedQualityDeltaPp) ||
              Math.abs(p.matchedQualityDeltaPp) > 100 : p.matchedQualityDeltaPp !== null))
          throw Error('Neispravan usporedni numerički pokazatelj');
        const union=p.matchedCount+p.newCoverage+p.lostCoverage;
        if (Math.abs(p.overlapPct-100*p.matchedCount/union)>0.001) throw Error('Netočno preklapanje univerzuma');
        const qIn = p.transitions.slice(0,3).reduce((a,r) => a+r[3]+r[4],0);
        const qOut = p.transitions.slice(3).reduce((a,r) => a+r[0]+r[1]+r[2],0);
        const fIn = p.transitions.slice(0,4).reduce((a,r)=>a+r[4],0);
        const fOut = p.transitions[4].slice(0,4).reduce((a,b)=>a+b,0);
        if (qIn !== p.qualityFlow.in || qOut !== p.qualityFlow.out || qIn-qOut !== p.qualityFlow.net ||
            fIn !== p.fourFlow.in || fOut !== p.fourFlow.out || fIn-fOut !== p.fourFlow.net) throw Error('Neusklađeni tokovi');
        if (p.matchedCount > 0 && Math.abs(p.matchedQualityDeltaPp-100*(qIn-qOut)/p.matchedCount)>0.001)
          throw Error('Netočan pomak usporedivog skupa');
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


  const COMPOSITE_FIELDS = [
    ['breadth','Širina kvalitetnih setupa','%'],
    ['pressure','Setup pressure','%'],
    ['velocity','Brzina promjene širine',' pp/EOD'],
    ['acceleration','Akceleracija širine',' pp/EOD'],
    ['flow','Pomak usporedivog skupa',' pp'],
    ['persistence','Trajnost kvalitete','%'],
  ];
  function compositeFactorRows(point, profile) {
    if (!point || !point.fields || !profile || !profile.weights || !profile.directions)
      throw Error('Nedostaje dokaz po komponentama Composite Scorea');
    const total=COMPOSITE_FIELDS.reduce((sum,[field])=>sum+(profile.weights[field]||0),0);
    if (!Number.isFinite(total) || total<=0) throw Error('Neispravne Composite težine');
    const rows=COMPOSITE_FIELDS.map(([field,label,unit])=>{
      const info=point.fields[field], weight=profile.weights[field], direction=profile.directions[field];
      if (!info || !Number.isFinite(info.percentile) || info.percentile<0 || info.percentile>100 ||
          !Number.isFinite(weight) || weight<0 || ![-1,1].includes(direction) ||
          !(info.raw===null || Number.isFinite(info.raw)) ||
          (info.historyN!==undefined && (!Number.isInteger(info.historyN)||info.historyN<0)))
        throw Error('Neispravna povijesna komponenta: '+field);
      const adjusted=direction<0?100-info.percentile:info.percentile;
      return {field,label,unit,raw:info.raw,percentile:info.percentile,historyN:info.historyN,
        weight,direction,adjusted,contribution:adjusted*weight/total,
        provisional:info.historyN!==undefined && (info.raw===null || info.historyN<12)};
    });
    return {rows,total,score:rows.reduce((sum,row)=>sum+row.contribution,0)};
  }
  function compositeHistory(data, source, range) {
    if (!['actual','proxy'].includes(source)) throw Error('Nepoznat izvor Scorea');
    const original=source==='actual'?data.actualHistory:data.oos.history;
    if (!Array.isArray(original)) return [];
    if (!original.length || range==='all') return original.slice();
    const last=original[original.length-1].sessionDate;
    const base=new Date(last+'T00:00:00Z');
    if (range==='1m') base.setUTCMonth(base.getUTCMonth()-1);
    else if (range==='3m') base.setUTCMonth(base.getUTCMonth()-3);
    else if (range==='1y') base.setUTCFullYear(base.getUTCFullYear()-1);
    else if (range==='5y') base.setUTCFullYear(base.getUTCFullYear()-5);
    else throw Error('Nepoznato razdoblje Composite povijesti');
    const start=base.toISOString().slice(0,10);
    return original.filter(point=>point.sessionDate>=start);
  }
  function validateCompositeTrace(items, profileBook, isActual) {
    if (!Array.isArray(items)) throw Error('Nedostaje Composite povijest');
    let prior='';
    for (const point of items) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(point.sessionDate) || point.sessionDate<=prior ||
          !Number.isFinite(point.score) || point.score<0 || point.score>100)
        throw Error('Neispravan slijed Composite datuma ili ocjena');
      const config=isActual?profileBook.current:profileBook[point.profile];
      const checked=compositeFactorRows(point,config);
      if (Math.abs(checked.score-point.score)>0.02)
        throw Error('Doprinosi ne odgovaraju ukupnom Composite Scoreu: '+point.sessionDate);
      if (isActual && (!Number.isInteger(point.readyFactors) || point.readyFactors<0 || point.readyFactors>6 ||
          point.readyFactors!==checked.rows.filter(row=>!row.provisional).length))
        throw Error('Neispravna oznaka kvalitete povijesne ocjene');
      if (!isActual && (typeof point.profile!=='string'|| !/^\d{4}-\d{2}-\d{2}$/.test(point.labelEnd) ||
          point.labelEnd<=point.sessionDate || !Number.isFinite(point.future20dPct)))
        throw Error('Neispravan izvanuzorački Composite zapis');
      prior=point.sessionDate;
    }
  }
  function validateComposite(data) {
    if (!data || data.schemaVersion !== 'trend-birth-composite-backtest-v1' ||
        data.scope !== 'equity-etf-proxy-not-historical-stockscout' ||
        !data.oos || !Array.isArray(data.oos.regimes) || !Number.isInteger(data.oos.n) ||
        !data.calibration || !data.latestActual ||
        !Number.isFinite(data.latestActual.score) || data.latestActual.score < 0 || data.latestActual.score > 100 ||
        !/^\d{4}-\d{2}-\d{2}$/.test(data.latestActual.sessionDate))
      throw Error('Neispravan backtest / Composite Score zapis');
    const book={...(data.calibration.profileBook||{}),
      current:{weights:data.calibration.weights,directions:data.calibration.directions}};
    if (data.actualHistory!==undefined) {
      validateCompositeTrace(data.actualHistory,book,true);
      const last=data.actualHistory.at(-1);
      if (!last || last.sessionDate!==data.latestActual.sessionDate ||
          Math.abs(last.score-data.latestActual.score)>0.02)
        throw Error('Zadnja stvarna povijesna ocjena nije usklađena');
    }
    if (data.oos.history!==undefined) {
      validateCompositeTrace(data.oos.history,book,false);
      if (data.oos.history.length!==data.oos.n)
        throw Error('Nedostaje izvanuzoračka Composite povijest');
    }
    return data;
  }

  function renderCompositeHistory(data) {
    const sourceEl=el('siCompositeSeries'), rangeEl=el('siCompositeRange');
    const slider=el('siCompositePoint'), host=el('siCompositeChart');
    const details=el('siCompositeSelected'), table=el('siCompositeFactorTable');
    const labels=Object.fromEntries(COMPOSITE_FIELDS.map(([key,label])=>[key,label]));
    const profileBook={...(data.calibration.profileBook||{}),
      current:{weights:data.calibration.weights,directions:data.calibration.directions}};
    const svgNs='http://www.w3.org/2000/svg';
    let currentPoints=[],selectCurrent=null;
    function svgElement(tag,attributes,parent) {
      const node=document.createElementNS(svgNs,tag);
      for (const [key,value] of Object.entries(attributes||{})) node.setAttribute(key,String(value));
      parent.appendChild(node);
      return node;
    }
    function showFactors(point,mode) {
      const profile=mode==='actual'?profileBook.current:profileBook[point.profile];
      const breakdown=compositeFactorRows(point,profile);
      if (Math.abs(breakdown.score-point.score)>0.02)
        throw Error('Suma faktora se ne podudara s arhiviranim Scoreom');
      table.replaceChildren();
      const thead=document.createElement('thead'),head=document.createElement('tr');
      for(const caption of ['Faktor','Sirova vrijednost','Percentil','Smjer','Težina','Udio u ocjeni','Pouzdanost']) {
        const cell=document.createElement('th');cell.textContent=caption;head.appendChild(cell);
      }
      thead.appendChild(head);table.appendChild(thead);
      const tbody=document.createElement('tbody');
      for (const part of breakdown.rows) {
        const tr=document.createElement('tr');
        const unit=part.unit.startsWith(' ')?part.unit:part.unit;
        const values=[
          labels[part.field],fmt(part.raw,unit),fmt(part.percentile,'%'),
          part.direction<0?'100 − percentil':'izravni',String(part.weight)+' / '+breakdown.total,
          fmt(part.contribution,' bod.'),
          part.provisional?'Neutralno 50 · kratka povijest':
            part.historyN!==undefined?part.historyN+' prethodnih EOD':'ETF povijesni rang',
        ];
        values.forEach((value,i)=>{
          const cell=document.createElement(i===0?'th':'td');
          cell.textContent=value;
          if(i===5)cell.className='si-contribution';
          if(i===6&&part.provisional)cell.className='si-provisional';
          tr.appendChild(cell);
        });
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      const tfoot=document.createElement('tfoot'),foot=document.createElement('tr');
      for(const [i,value] of ['Ukupni Composite','', '', '', 'Σ '+breakdown.total,
           fmt(breakdown.score,' / 100'),''].entries()){
        const cell=document.createElement(i===0?'th':'td');
        cell.textContent=value;foot.appendChild(cell);
      }
      tfoot.appendChild(foot);table.appendChild(tfoot);
      el('siCompositeFactorTitle').textContent='Razrada bodovanja · '+point.sessionDate+
        (mode==='proxy'?' · ETF OOS profil '+point.profile:' · stvarni EOD');
      el('siCompositeFormula').textContent='Score = Σ[težina × usmjereni percentil] / Σtežina. '+
        'Za obrnuti faktor koristi se 100 − percentil. Odabrani profil ima '+breakdown.total+
        ' pondera; zbroj doprinosa = '+fmt(breakdown.score,' / 100')+'.';
      const provisional=breakdown.rows.filter(row=>row.provisional);
      el('siCompositeScoringCaveat').textContent=mode==='actual'?
        (provisional.length?provisional.length+' od 6 faktora za ovaj dan koristi neutralni 50. percentil '+
          'jer nije dostupno barem 12 PRETHODNIH valjanih opažanja ili sirova vrijednost. ':
          'Svih šest faktora ima najmanje 12 prethodnih valjanih opažanja. ')+
        'Težine su zamrznute iz ETF-proxy kalibracije; ovo nije historijski stock-level backtest.':
        'Svaki ETF datum koristi tada dostupne percentilne ulaze, a profil je biran samo iz prethodno '+
        'završenih godina. H20 prinos je naknadni kontrolni ishod, nikada sastavni dio Scorea.';
    }
    function draw() {
      const mode=sourceEl.value;
      const points=compositeHistory(data,mode,rangeEl.value);
      currentPoints=points;selectCurrent=null;
      host.replaceChildren();
      if (!points.length) {
        host.textContent='Za odabrani izvor nema sačuvane povijesne serije u ovom izdanju.';
        slider.disabled=true;
        el('siCompositeChartMeta').textContent='Sažeti backtest je dostupan, ali vremenska serija još nije objavljena.';
        details.textContent='—';table.replaceChildren();
        return;
      }
      slider.disabled=false;
      slider.max=String(points.length-1);
      slider.min='0';
      const width=970,height=280,left=45,right=22,top=18,bottom=42;
      const bottomY=height-bottom,plotH=bottomY-top;
      const ms=points.map(p=>Date.parse(p.sessionDate+'T00:00:00Z'));
      const start=ms[0],duration=Math.max(1,ms[ms.length-1]-start);
      const x=i=>left+(ms[i]-start)/duration*(width-left-right);
      const y=value=>bottomY-value/100*plotH;
      const svg=svgElement('svg',{viewBox:'0 0 '+width+' '+height,role:'img',
        'aria-label':'Composite Score od 0 do 100, '+points[0].sessionDate+' do '+
        points[points.length-1].sessionDate},host);
      const title=svgElement('title',{},svg);
      title.textContent=mode==='actual'?'Stvarni arhivirani Trend Birth Score (provisionalni dani označeni isprekidano)':
        'Povijesni ETF proxy Score s godišnjim izvanuzoračkim profilima';
      for(const tick of [0,25,50,75,100]) {
        const yy=y(tick);
        svgElement('line',{x1:left,y1:yy,x2:width-right,y2:yy,
          stroke:tick===50?'#7895ae':'#2a4058','stroke-width':tick===50?1.4:0.8,
          'stroke-dasharray':tick===50?'5 5':'none'},svg);
        const label=svgElement('text',{x:left-10,y:yy+4,'text-anchor':'end',
          fill:'#a9bed2','font-size':12},svg);label.textContent=String(tick);
      }
      const ticks=new Set([0,points.length-1]);
      for(let i=1;i<=4;i++)ticks.add(Math.round((points.length-1)*i/5));
      for(const idx of [...ticks].sort((a,b)=>a-b)){
        const textNode=svgElement('text',{x:x(idx),y:height-14,'text-anchor':idx===0?'start':
          idx===points.length-1?'end':'middle',fill:'#a9bed2','font-size':11},svg);
        const years=(ms[ms.length-1]-ms[0])/(365.25*86400000);
        textNode.textContent=years>5?points[idx].sessionDate.slice(0,4):
          years>1?points[idx].sessionDate.slice(0,7):
          points[idx].sessionDate.slice(8,10)+'.'+points[idx].sessionDate.slice(5,7)+'.';
      }
      const baseColor=mode==='proxy'?'#74b6ff':'#55e0ac';
      for(let i=1;i<points.length;i++){
        const warmup=mode==='actual'&&(points[i].readyFactors<6||points[i-1].readyFactors<6);
        const line=svgElement('line',{x1:x(i-1),y1:y(points[i-1].score),
          x2:x(i),y2:y(points[i].score),stroke:warmup?'#ebba69':baseColor,
          'stroke-width':2.5,'stroke-linecap':'round',
          'stroke-dasharray':warmup?'5 4':'none'},svg);
        const tip=svgElement('title',{},line);
        tip.textContent=points[i].sessionDate+' · '+fmt(points[i].score,' / 100');
      }
      const marker=svgElement('circle',{cx:x(points.length-1),cy:y(points[points.length-1].score),
        r:6,stroke:'#fff','stroke-width':2,fill:baseColor},svg);
      function choose(index,emit=false){
        const i=Math.max(0,Math.min(points.length-1,index));
        const point=points[i];
        slider.value=String(i);
        marker.setAttribute('cx',String(x(i)));
        marker.setAttribute('cy',String(y(point.score)));
        const bounds=marker.getBoundingClientRect(),clip=host.getBoundingClientRect();
        if(bounds.left<clip.left+8)host.scrollLeft-=clip.left+8-bounds.left;
        else if(bounds.right>clip.right-8)host.scrollLeft+=bounds.right-clip.right+8;
        const isProxy=mode==='proxy';
        details.textContent=point.sessionDate+' · '+fmt(point.score,' / 100')+
          (isProxy?' · OOS profil '+point.profile+' · SPY sljedećih 20D '+fmt(point.future20dPct,'%')+
            ' (naknadno poznat ishod)':
            ' · '+point.readyFactors+'/6 faktora s dovoljnom ranijom poviješću');
        showFactors(point,mode);
        if(emit&&mode==='actual')document.dispatchEvent(new CustomEvent('tb:statistics-date-select',
          {detail:{origin:'composite',date:point.sessionDate}}));
      }
      selectCurrent=choose;
      slider.oninput=()=>choose(Number(slider.value),true);
      svg.addEventListener('click',event=>{
        const rect=svg.getBoundingClientRect();
        const chartX=(event.clientX-rect.left)/rect.width*width;
        let nearest=0,dist=Infinity;
        for(let i=0;i<points.length;i++){
          const delta=Math.abs(x(i)-chartX);
          if(delta<dist){dist=delta;nearest=i;}
        }
        choose(nearest,true);
      });
      el('siCompositeChartMeta').textContent=points.length+(mode==='actual'?' stvarnih EOD zapisa · ':' povijesnih ETF OOS točaka · ')+
        points[0].sessionDate+' – '+points[points.length-1].sessionDate+'. '+
        (mode==='actual'?'Isprekidano zlatno = nedovoljna prethodna povijest; nema izmišljenih sesija.':
          'Izvanuzorački ETF proxy, uzorak svakih 10 burzovnih dana; profil se može mijenjati po godini.');
      choose(points.length-1);
    }
    sourceEl.addEventListener('change',()=>{
      draw();
      document.dispatchEvent(new CustomEvent('tb:statistics-source-select',
        {detail:{origin:'composite',source:sourceEl.value}}));
    });
    rangeEl.addEventListener('change',()=>{
      draw();
      if(sourceEl.value==='actual')document.dispatchEvent(new CustomEvent('tb:statistics-range-select',
        {detail:{origin:'composite',range:rangeEl.value}}));
      if(sourceEl.value==='actual'&&currentPoints.length)document.dispatchEvent(
        new CustomEvent('tb:statistics-date-select',{detail:{origin:'composite',date:currentPoints.at(-1).sessionDate}}));
    });
    document.addEventListener('tb:statistics-date-select',event=>{
      if(event.detail?.origin!=='heat'||sourceEl.value!=='actual'||!selectCurrent)return;
      const idx=currentPoints.findIndex(p=>p.sessionDate===event.detail.date);
      if(idx>=0)selectCurrent(idx);
    });
    document.addEventListener('tb:statistics-range-select',event=>{
      if(event.detail?.origin!=='heat'||sourceEl.value!=='actual')return;
      if(['1m','3m','1y','5y','all'].includes(event.detail.range)){
        rangeEl.value=event.detail.range;draw();
      }
    });
    function publishSelection() {
      document.dispatchEvent(new CustomEvent('tb:statistics-source-select',
        {detail:{origin:'composite',source:sourceEl.value}}));
      if(sourceEl.value==='actual'&&currentPoints.length){
        document.dispatchEvent(new CustomEvent('tb:statistics-range-select',
          {detail:{origin:'composite',range:rangeEl.value}}));
        document.dispatchEvent(new CustomEvent('tb:statistics-date-select',
          {detail:{origin:'composite',date:currentPoints[Number(slider.value)].sessionDate}}));
      }
    }
    document.addEventListener('tb:statistics-selection-request',publishSelection);
    draw();
    publishSelection();
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
    el('siCompositeFactors').textContent='Trenutačni profil: '+data.calibration.selectedProfile+
      ' · '+names.breadth+', '+names.pressure+', '+names.velocity+', '+names.acceleration+
      ', '+names.flow+' i '+names.persistence+'. Klikni na graf ili pomakni klizač za razradu odabranog datuma.';
    renderCompositeHistory(data);
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

  function validateForward(value, version='trend-birth-stage-forward-v2') {
    if (!value || value.schemaVersion !== version ||
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
      if (value.dataQuality && (
          !Number.isInteger(item.missingSessionGap) || !Number.isInteger(item.missingTickerQuote) ||
          !Number.isInteger(item.missingUnclassified) ||
          item.missingSessionGap<0 || item.missingTickerQuote<0 || item.missingUnclassified<0 ||
          item.missingSessionGap+item.missingTickerQuote+item.missingUnclassified!==item.missingMatured))
        throw Error('Dijagnostika nedostajućih ishoda nije usklađena');
    }
    if (value.dataQuality) {
      const q=value.dataQuality;
      if (!Number.isInteger(q.archivedSessions) || !Number.isInteger(q.exchangeSessionsInWindow) ||
          !Array.isArray(q.missingExchangeSessions) || !Number.isInteger(q.actualSourceQuotes) ||
          !Number.isInteger(q.expectedSourceQuotes) || !Number.isFinite(q.sourcePriceCoveragePct) ||
          q.sourcePriceCoveragePct<0 || q.sourcePriceCoveragePct>100 ||
          q.archivedSessions+q.missingExchangeSessions.length!==q.exchangeSessionsInWindow ||
          q.actualSourceQuotes<0 || q.actualSourceQuotes>q.expectedSourceQuotes ||
          Math.abs(q.sourcePriceCoveragePct-(100*q.actualSourceQuotes/q.expectedSourceQuotes))>0.02)
        throw Error('Neusklađena EOD pokrivenost cijena');
    }
    if (value.exchangeSessions!==undefined && (!Array.isArray(value.exchangeSessions) ||
        !value.exchangeSessions.length || value.exchangeSessions.at(-1)!==value.asOf ||
        value.exchangeSessions.some((day,i)=>!/^\d{4}-\d{2}-\d{2}$/.test(day) ||
          (i&&value.exchangeSessions[i-1]>=day)))) throw Error('Neispravan burzovni kalendar ishoda');
    if(value.outcomeTracking!==undefined){
      const t=value.outcomeTracking;
      if(t?.schemaVersion!=='trend-birth-outcome-tracking-v1'||t.asOf!==value.asOf||
         !['waiting-for-next-session','partial','complete'].includes(t.status)||typeof t.enabled!=='boolean'||
         !/^\d{4}-\d{2}-\d{2}$/.test(t.startAfterSessionDate)||t.enabled!==(t.asOf>t.startAfterSessionDate)||
         ![t.trackedCount,t.primaryCoveredCount,t.supplementalCount,t.missingCount].every(n=>Number.isInteger(n)&&n>=0)||
         t.primaryCoveredCount>t.trackedCount||
         (t.enabled&&t.primaryCoveredCount+t.supplementalCount+t.missingCount!==t.trackedCount)||
         t.status!==(!t.enabled?'waiting-for-next-session':t.missingCount?'partial':'complete')||
         t.calibrationApproved!==false||t.historyBackfilled!==false)
        throw Error('Neusklađeno praćenje cijena otvorenih ishoda');
    }
    return value;
  }
  function validateRecovery(value){
    if(value?.schemaVersion!=='trend-birth-recovery-comparison-v3'||value.scope!==SCOPE||
       value.baselineReplayMatchesPublished!==true||value.migration?.activated!==false||
       value.migration?.v2InputsUntouched!==true||value.migration?.calibrationApproved!==false||
       value.after?.calibrationApproved!==false||!value.before?.dataQuality||!value.after?.dataQuality||
       value.asOf!=='2026-10-23'||value.asOf!==value.before?.asOf||
       value.asOf!==value.after?.asOf)throw Error('Neispravna usporedba V2/V3');
    validateForward(value.before);
    validateForward(value.after,'trend-birth-stage-forward-v3');
    for(const report of [value.before,value.after])for(const stages of Object.values(report.byHorizon))
      if(Object.values(stages).some(row=>row.eligibleForCalibration!==false))throw Error('V3 usporedba ne odobrava kalibraciju');
    return value;
  }
  function horizonTotals(report,horizon){
    const rows=Object.values(report.byHorizon[String(horizon)]);
    const sum=key=>rows.reduce((n,row)=>n+row[key],0);
    const n=sum('n'),expected=sum('expectedMatured');
    return {n,expected,missing:sum('missingMatured'),pending:sum('pending'),coverage:expected?100*n/expected:null};
  }
  function comparisonTable(id,headers,rows){
    const table=el(id);
    table.querySelectorAll('thead,tbody').forEach(node=>node.remove());
    const head=document.createElement('thead'),header=document.createElement('tr');
    for(const title of headers){const th=document.createElement('th');th.textContent=title;th.scope='col';header.appendChild(th);}
    head.appendChild(header);table.appendChild(head);
    const body=document.createElement('tbody');
    for(const values of rows){
      const row=document.createElement('tr');
      values.forEach((value,index)=>{const cell=document.createElement(index?'td':'th');
        cell.textContent=value;if(!index)cell.scope='row';row.appendChild(cell);});
      body.appendChild(row);
    }
    table.appendChild(body);
  }
  function renderRecovery(data){
    const reports=[data.before,data.after],totals=reports.map(report=>horizonTotals(report,5));
    comparisonTable('siRecoveryCoverage',['Pokazatelj · '+data.asOf,'V2 · izvorno','V3 · rekonstrukcija'],[
      ['EOD sesije',...reports.map(r=>r.dataQuality.archivedSessions+' / '+r.dataQuality.exchangeSessionsInWindow)],
      ['Prijelazi faza',...reports.map(r=>FMT.format(r.stageTransitions))],
      ['Dospjeli 5D s cijenom',...totals.map(r=>FMT.format(r.n)+' / '+FMT.format(r.expected))],
      ['Pokrivenost 5D',...totals.map(r=>fmt(r.coverage,'%'))],
      ['Nedostaju dospjeli 5D',...totals.map(r=>FMT.format(r.missing))]
    ]);
    const horizon=el('siRecoveryHorizon').value,rows=[];
    for(let stage=0;stage<=4;stage++)for(const [index,report] of reports.entries()){
      const row=report.byHorizon[horizon][String(stage)];
      rows.push([stage+'/4',index?'V3':'V2',FMT.format(row.n)+' / '+FMT.format(row.expectedMatured),
        FMT.format(row.pending),fmt(row.coveragePct,'%'),fmt(row.meanPct,'%'),fmt(row.medianPct,'%'),
        [row.missingSessionGap,row.missingTickerQuote,row.missingUnclassified].map(n=>FMT.format(n)).join(' / ')]);
    }
    comparisonTable('siRecoveryTable',['Faza','Verzija','Dospjelo s cijenom','Na čekanju','Pokrivenost','Prosjek','Medijan','Nedostaje: sesija / ticker / ostalo'],rows);
    const totalsForHorizon=reports.map(r=>horizonTotals(r,horizon));
    el('siRecoveryStatus').textContent='Zamrznuta usporedba do '+data.asOf+' · '+horizon+'D. '+
      (totalsForHorizon.every(r=>r.expected===0)?'Ishodi još nisu dospjeli; prinosi nisu dostupni.':
        'Veća pokrivenost nije dokaz boljeg prinosa.');
  }
  function mountRecovery(){
    const details=el('siRecovery');if(!details)return;
    let data=null,loading=false;
    el('siRecoveryHorizon').addEventListener('change',()=>{if(data)renderRecovery(data);});
    details.addEventListener('toggle',async()=>{
      if(!details.open||data||loading)return;
      loading=true;el('siRecoveryStatus').textContent='Učitavam odvojenu usporedbu V2/V3…';
      try{
        const response=await fetch('data/recovery-v3/comparison.json',{cache:'no-store'});
        if(!response.ok)throw Error('HTTP '+response.status);
        const recovered=validateRecovery(await response.json());
        renderRecovery(recovered);data=recovered;el('siRecoveryContent').hidden=false;
      }catch(error){el('siRecoveryStatus').textContent='Usporedba nije dostupna: '+error.message+'. Zatvori i ponovno otvori za ponovni pokušaj. Glavni V2 prikaz ostaje dostupan.';}
      finally{loading=false;}
    });
  }
  function renderForward(raw, eodDate) {
    const data=validateForward(raw);
    const status=el('siForwardStatus');
    const stale=data.asOf!==eodDate;
    status.textContent=(stale?'UPOZORENJE: mjerenje nije osvježeno za današnji EOD · ':'')+
      'V2 · stvarna point-in-time povijest · '+data.asOf+
      ' · '+FMT.format(data.stageTransitions)+' potvrđenih prijelaza, '+FMT.format(data.archivedEventDays)+' datuma.';
    el('siForwardSummary').textContent='Uzorci dospijevaju nakon 1 + 5/20/60 burzovnih sesija. '+
      'Samo potpun broj dospjelih ishoda u tablici ulazi u prosjek; nedostajuće cijene ne tretiraju se kao 0%.';
    const quality=data.dataQuality;
    el('siForwardQuality').textContent=quality
      ? 'Kontrola izvora: '+quality.archivedSessions+' / '+quality.exchangeSessionsInWindow+
        ' stvarnih burzovnih sesija od '+quality.coverageWindowStart+'; nedostaju cijeli EOD-i: '+
        (quality.missingExchangeSessions.join(', ')||'nema')+'. Cijene za sačuvane EOD-e: '+
        fmt(quality.sourcePriceCoveragePct,'%')+' ('+FMT.format(quality.actualSourceQuotes)+
        ' / '+FMT.format(quality.expectedSourceQuotes)+'). Rupe u datumima nisu isto što i nestali tickeri.'
      : 'Dijagnostika rupa u EOD kalendaru bit će dostupna nakon sljedeće objave podataka.';
    const tracking=data.outcomeTracking;
    if(tracking)el('siForwardQuality').textContent+=tracking.enabled
      ? ' Otvoreni ishodi: '+FMT.format(tracking.trackedCount)+' dionica ostaje u praćenju do 60D ishoda; '+
        FMT.format(tracking.supplementalCount)+' dodatnih cijena izvan dnevnog skupa, '+
        FMT.format(tracking.missingCount)+' cijena nedostaje. Stare arhive nisu prepisane.'
      : ' Dodatno praćenje cijena otvorenih ishoda počinje nakon '+tracking.startAfterSessionDate+'.';
    const table=el('siForwardTable');
    table.replaceChildren();
    const thead=document.createElement('thead'), tr=document.createElement('tr');
    for (const label of ['Faza','Horizont','Dospjelo s cijenom','Na čekanju','Pokrivenost','Nedostaje: sesija / ticker / ostalo','Prosjek','Medijan','% pozitivnih','P10 / P90']) {
      const th=document.createElement('th'); th.textContent=label; tr.appendChild(th);
    }
    thead.appendChild(tr); table.appendChild(thead);
    const tbody=document.createElement('tbody');
    for (let stage=0;stage<=4;stage++) for (const horizon of data.horizons) {
      const row=data.byHorizon[String(horizon)][String(stage)], r=document.createElement('tr');
      const cells=[stage+'/4',horizon+'D',FMT.format(row.n)+' / '+FMT.format(row.expectedMatured),
        FMT.format(row.pending),fmt(row.coveragePct,'%'),
        quality ? [row.missingSessionGap,row.missingTickerQuote,row.missingUnclassified].map(x=>FMT.format(x)).join(' / ') : '—',
        fmt(row.meanPct,'%'),
        fmt(row.medianPct,'%'),fmt(row.winRatePct,'%'),
        fmt(row.p10Pct,'%')+' / '+fmt(row.p90Pct,'%')];
      cells.forEach((value,i)=>{const cell=document.createElement(i===0?'th':'td');cell.textContent=value;
        if (i===0) cell.style.color=COLORS[stage];
        if (i===6 && Number.isFinite(row.meanPct)) cell.style.color=row.meanPct>=0?'#37cb89':'#f26d79';
        r.appendChild(cell);
      });
      tbody.appendChild(r);
    }
    table.appendChild(tbody);
  }

  async function start() {
    const status=el('siStatus');
    if (!status) return;
    mountRecovery();
    try {
      const response=await fetch('data/trend-birth-market-internals.json',{cache:'no-store'});
      if (!response.ok) throw Error('HTTP '+response.status);
      const data=validate(await response.json());
      for(const id of ['siRange','siAggregation','siMetric','siZoom','siWindow']) el(id).addEventListener('change',()=>render(data));
      render(data);
      status.hidden=true;
      await Promise.all([
        (async()=>{
          try {
            const response=await fetch('data/trend-birth-composite-backtest.json',{cache:'no-store'});
            if (!response.ok) throw Error('HTTP '+response.status);
            renderComposite(await response.json(),data.latestSessionDate);
          } catch (error) {
            el('siCompositeStatus').textContent='Backtest nije dostupan: '+(error?.message||String(error));
          }
        })(),
        (async()=>{
          let forward=null;
          try {
            const response=await fetch('data/trend-birth-stage-forward.json',{cache:'no-store'});
            if (!response.ok) throw Error('HTTP '+response.status);
            forward=validateForward(await response.json());
            renderForward(forward,data.latestSessionDate);
          } catch (error) {
            el('siForwardStatus').textContent='Stvarni ishodi zasad nisu dostupni: '+(error?.message||String(error));
          }
          try {
            if(!globalThis.TrendBirthHeat)throw Error('Nedostaje modul Market Thermometera');
            globalThis.TrendBirthHeat.mount(data,forward);
          } catch (error) {
            el('siHeatTitle').textContent='Market Thermometer nije dostupan: '+(error?.message||String(error));
          }
        })()
      ]);
    } catch(e) {
      status.textContent='Statistika nije dostupna: '+(e?.message||String(e))+' · Pokušaj osvježiti stranicu.';
      status.className='si-error';
    }
  }
  return {validate, validateComposite, validateForward, validateRecovery, horizonTotals, compositeFactorRows, compositeHistory,
    metric, slope, dynamics, withDynamics, percentile, windowStart, weekKey, group, transitions, regime, start};
});
