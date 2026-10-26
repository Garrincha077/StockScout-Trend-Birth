/* Offline XNYS close/grace policy shared with the publication gate. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else if(root.document)root.document.addEventListener('DOMContentLoaded',api.start);
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
  async function start(){
    const host=document.getElementById('eodFreshness');
    if(!host)return;
    try{
      const values=await Promise.all(['data/exchange-sessions-v1.json','data/publication.json'].map(async url=>{
        const response=await fetch(url,{cache:'no-store'});
        if(!response.ok)throw Error('HTTP '+response.status);
        return response.json();
      }));
      const day=values[1].sessionDate,result=assess(values[0],day);
      host.dataset.state=result.stale?'stale':'current';
      host.textContent=(result.stale?'Podaci kasne. ':'')+'Zadnja provjerena EOD objava: '+day+
        '. Očekivana sesija: '+result.expected+'. '+
        (result.stale?'Prikazana je posljednja valjana objava. ':'')+
        'Rok osvježenja: 4 sata nakon zatvaranja XNYS-a, uz blagdane i ranija zatvaranja.';
    }catch(error){
      host.dataset.state='unknown';
      host.textContent='Svježina EOD objave nije potvrđena: '+error.message+'. Provjeri datum izvora prije korištenja podataka.';
    }
  }
  return {assess,start};
});
