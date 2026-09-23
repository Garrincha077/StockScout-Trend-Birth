(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.WatchlistStore=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const STORAGE_KEY='stockscout.review.watchlist.v1';

  function normalizeTicker(value){
    return String(value??'').trim().toUpperCase();
  }

  function normalizeItems(items){
    const seen=new Set(),out=[];
    for(const raw of Array.isArray(items)?items:[]){
      const entry=typeof raw==='string'?{ticker:raw}:raw||{};
      const ticker=normalizeTicker(entry.ticker);
      if(!ticker||seen.has(ticker))continue;
      seen.add(ticker);
      out.push({
        ticker,
        addedAt:entry.addedAt||null,
        addedSession:entry.addedSession||null
      });
    }
    return out;
  }

  function load(storage){
    try{
      const raw=storage?.getItem?.(STORAGE_KEY);
      if(!raw)return[];
      const parsed=JSON.parse(raw);
      return normalizeItems(Array.isArray(parsed)?parsed:parsed?.items);
    }catch(_err){
      return[];
    }
  }

  function save(storage,items){
    const normalized=normalizeItems(items);
    try{
      storage?.setItem?.(STORAGE_KEY,JSON.stringify({version:1,items:normalized}));
    }catch(_err){}
    return normalized;
  }

  function has(items,ticker){
    const key=normalizeTicker(ticker);
    return normalizeItems(items).some(item=>item.ticker===key);
  }

  function toggle(items,ticker,meta={}){
    const key=normalizeTicker(ticker);
    const normalized=normalizeItems(items);
    if(!key)return normalized;
    const index=normalized.findIndex(item=>item.ticker===key);
    if(index>=0){
      normalized.splice(index,1);
      return normalized;
    }
    normalized.push({
      ticker:key,
      addedAt:meta.addedAt||new Date().toISOString(),
      addedSession:meta.addedSession||null
    });
    return normalized;
  }

  return{STORAGE_KEY,normalizeTicker,normalizeItems,load,save,has,toggle};
});
