(function(root,factory){
  const api=factory(root);
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.OwnerWatchlistSync=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(root){
  const SUPABASE_URL='https://whmjhpaxpcepmpdykrdt.supabase.co';
  const SUPABASE_KEY='sb_publishable_RD25QrL_O8in94uFznguoA_gUgNjB7h';
  const SCHEMA='stockscout_unified_api';
  const WATCHLIST_NAME='Trend Birth';
  const MODE='next';
  const PRICE_BASIS='split_only';
  const TICKER_PATTERN=/^[A-Z0-9._-]{1,20}$/;

  function normalizeTicker(value){
    const ticker=String(value??'').trim().toUpperCase();
    if(!TICKER_PATTERN.test(ticker))throw new Error('Ticker must use 1-20 letters, numbers, dots, dashes or underscores.');
    return ticker;
  }

  function normalizeTickers(values){
    return [...new Set((Array.isArray(values)?values:[]).map(value=>{
      try{return normalizeTicker(typeof value==='object'&&value?value.ticker:value)}catch(_err){return null}
    }).filter(Boolean))].sort();
  }

  function appRoot(pathname){
    const path=String(pathname||'/');
    const last=path.split('/').at(-1)||'';
    return last.includes('.')?path.replace(/[^/]+$/,''):(path.endsWith('/')?path:path+'/');
  }

  function redirectUrl(locationLike){
    return new URL(appRoot(locationLike.pathname),locationLike.origin).toString();
  }

  function create(options={}){
    const lib=options.supabaseLib||root.supabase;
    const fetcher=options.fetch||root.fetch?.bind(root);
    const onSession=typeof options.onSession==='function'?options.onSession:()=>{};
    let client=null,session=null,subscription=null;

    function signedIn(){return Boolean(session?.user)}
    function user(){return session?.user||null}

    async function load(){
      if(!client||!session?.user)return[];
      const ownerId=session.user.id;
      const {data,error}=await client
        .from('unified_watchlist_items')
        .select('ticker')
        .eq('user_id',ownerId)
        .eq('name',WATCHLIST_NAME)
        .eq('mode',MODE)
        .eq('price_basis',PRICE_BASIS)
        .order('ticker');
      if(error)throw error;
      return normalizeTickers((data||[]).map(row=>row.ticker));
    }

    async function setTicker(ticker,present){
      if(!client||!session?.user)throw new Error('Owner sign-in is required');
      const normalized=normalizeTicker(ticker);
      const {error}=await client.rpc('unified_set_watchlist_ticker',{
        p_name:WATCHLIST_NAME,
        p_ticker:normalized,
        p_mode:MODE,
        p_price_basis:PRICE_BASIS,
        p_present:Boolean(present)
      });
      if(error)throw error;
      return load();
    }

    async function migrate(tickers){
      if(!client||!session?.user)return[];
      const local=normalizeTickers(tickers);
      const remote=await load();
      const missing=local.filter(ticker=>!remote.includes(ticker));
      for(const ticker of missing){
        const {error}=await client.rpc('unified_set_watchlist_ticker',{
          p_name:WATCHLIST_NAME,
          p_ticker:ticker,
          p_mode:MODE,
          p_price_basis:PRICE_BASIS,
          p_present:true
        });
        if(error)throw error;
      }
      return missing.length?load():remote;
    }

    async function init(){
      if(!lib?.createClient)throw new Error('Supabase browser client is unavailable');
      client=lib.createClient(SUPABASE_URL,SUPABASE_KEY,{
        db:{schema:SCHEMA},
        auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}
      });
      const {data,error}=await client.auth.getSession();
      if(error)throw error;
      session=data.session||null;
      onSession(session);
      const auth=client.auth.onAuthStateChange((_event,next)=>{
        session=next||null;
        onSession(session);
      });
      subscription=auth?.data?.subscription||null;
      return session;
    }

    async function signInWithGoogle(locationLike=root.location){
      if(!client)throw new Error('Owner sync is not initialized');
      const {error}=await client.auth.signInWithOAuth({
        provider:'google',
        options:{redirectTo:redirectUrl(locationLike),queryParams:{prompt:'select_account'}}
      });
      if(error)throw error;
    }

    async function sendMagicLink(email,locationLike=root.location){
      if(!client)throw new Error('Owner sync is not initialized');
      const {error}=await client.auth.signInWithOtp({
        email:String(email||'').trim(),
        options:{shouldCreateUser:false,emailRedirectTo:redirectUrl(locationLike)}
      });
      if(error)throw error;
    }

    async function signOut(){
      if(!client)return;
      const {error}=await client.auth.signOut();
      if(error)throw error;
      session=null;
      onSession(null);
    }

    function destroy(){subscription?.unsubscribe?.()}

    return{
      init,load,setTicker,migrate,signInWithGoogle,sendMagicLink,signOut,destroy,
      signedIn,user,normalizeTicker,normalizeTickers,
      config:{url:SUPABASE_URL,schema:SCHEMA,name:WATCHLIST_NAME,mode:MODE,priceBasis:PRICE_BASIS}
    };
  }

  return{create,normalizeTicker,normalizeTickers,redirectUrl};
});
