/* Offline XNYS close/grace policy shared with the publication gate. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.ReviewFreshness=api;
})(globalThis,function(){
  'use strict';
  function assess(calendar,day,now=Date.now()){
    const today=new Date(now).toISOString().slice(0,10);
    if(calendar?.schemaVersion!=='xnys-eod-sessions-v1'||calendar.publicationGraceHours!==4||
       !Array.isArray(calendar.sessions)||!calendar.sessions.length||
       today<calendar.validFrom||today>calendar.validThrough)throw Error('Kalendar nije dostupan za današnji datum');
    let expected=null,sourceClose=null;
    for(const [i,row] of calendar.sessions.entries()){
      if(!Array.isArray(row)||!/^\d{4}-\d{2}-\d{2}$/.test(row[0])||
         !Number.isFinite(Date.parse(row[1]))||(i&&calendar.sessions[i-1][0]>=row[0]))throw Error('Neispravan burzovni kalendar');
      if(Date.parse(row[1])+4*3600000<=now)expected=row[0];
      if(row[0]===day)sourceClose=Date.parse(row[1]);
    }
    if(!expected||sourceClose===null||sourceClose>now)throw Error('Datum objave nije završena burzovna sesija');
    return {expected,stale:day<expected};
  }
  async function loadCalendar(fetcher){
    const response=await fetcher('data/exchange-sessions-v1.json',{cache:'no-store'});
    if(!response.ok)throw Error('Kalendar nije dostupan (HTTP '+response.status+').');
    return response.json();
  }
  function describe(calendar,day,{archived=false,error=null,now=Date.now()}={}){
    if(archived&&day)return {state:'archive',text:'Povijesna snimka · '+day};
    const prefix=day?'Prikazana EOD sesija: '+day+'. ':'';
    if(error)return {state:'unknown',text:prefix+'Provjera novije objave nije uspjela: '+error.message};
    try{
      const result=assess(calendar,day,now);
      return {state:result.stale?'stale':'current',text:(result.stale?'Podaci kasne. ':'')+prefix+
        'Očekivana sesija: '+result.expected+'.'};
    }catch(error){
      return {state:'unknown',text:prefix+'Svježina EOD podataka nije potvrđena: '+error.message+'.'};
    }
  }
  function render(host,calendar,day,options){
    if(!host)return;
    const status=describe(calendar,day,options);
    host.dataset.state=status.state;
    if(host.textContent!==status.text)host.textContent=status.text;
  }
  return {assess,loadCalendar,describe,render};
});
