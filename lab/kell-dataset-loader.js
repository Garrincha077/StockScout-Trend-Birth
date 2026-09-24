(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.KellDatasets=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const SNAPSHOT_RE=/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}$/;

  function resolve(search){
    const params=new URLSearchParams(search||'');
    const snapshot=params.get('snapshot');
    const date=params.get('date');
    if(snapshot!==null){
      if(!SNAPSHOT_RE.test(snapshot))throw new Error('Neispravan Kell snapshot link.');
      return{
        kind:'snapshot',
        primary:'data/kell-snapshots/'+snapshot+'.json',
        fallback:'data/kell-latest.json'
      };
    }
    if(date!==null){
      if(!/^\d{4}-\d{2}-\d{2}$/.test(date))throw new Error('Neispravan Kell datum.');
      return{
        kind:'date',
        primary:'data/kell-history/'+date+'.json',
        fallback:'data/kell-latest.json'
      };
    }
    return{kind:'latest',primary:'data/kell-latest.json',fallback:null};
  }

  function validateIdentity(reviewSource,kellSource){
    const review=reviewSource||{},kell=kellSource||{};
    if(review.sessionDate&&kell.sessionDate&&review.sessionDate!==kell.sessionDate){
      throw new Error('Kell dataset je za '+kell.sessionDate+', a Review Grid za '+review.sessionDate+'.');
    }
    if(review.runId&&kell.runId&&review.runId!==kell.runId){
      throw new Error('Kell i Review Grid nisu iz istog Unified runa.');
    }
    if(review.unifiedManifestSha256&&kell.unifiedManifestSha256&&review.unifiedManifestSha256!==kell.unifiedManifestSha256){
      throw new Error('Kell i Review Grid nisu iz iste aktivirane Unified objave.');
    }
  }

  async function fetchJson(fetcher,path){
    const response=await fetcher(path,{cache:'no-store'});
    if(!response.ok)return{response,data:null};
    return{response,data:await response.json()};
  }

  async function load(fetcher,search,reviewSource){
    const target=resolve(search);
    let result=await fetchJson(fetcher,target.primary);
    if(!result.response.ok&&target.fallback&&result.response.status===404){
      const fallback=await fetchJson(fetcher,target.fallback);
      if(!fallback.response.ok){
        throw new Error('Kell podaci nisu dostupni (HTTP '+fallback.response.status+').');
      }
      try{
        validateIdentity(reviewSource,fallback.data?.source);
      }catch(_err){
        throw new Error('Kell arhiva nije dostupna za ovaj Review snapshot; odbijam koristiti Kell podatke iz drugog Unified runa.');
      }
      return fallback.data;
    }
    if(!result.response.ok){
      const label=target.kind==='latest'?'Kell dataset':'Kell arhiva';
      throw new Error(label+' nije dostupan (HTTP '+result.response.status+').');
    }
    validateIdentity(reviewSource,result.data?.source);
    return result.data;
  }

  return{resolve,validateIdentity,load};
});
