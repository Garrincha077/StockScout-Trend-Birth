const test=require('node:test');
const assert=require('node:assert/strict');
const OwnerWatchlistSync=require('../lab/owner-watchlist-sync.js');

test('owner sync normalizes tickers and preserves canonical redirect root',()=>{
  assert.deepEqual(
    OwnerWatchlistSync.normalizeTickers([' clov ','CLOV','brk.b','bad ticker']),
    ['BRK.B','CLOV']
  );
  assert.equal(
    OwnerWatchlistSync.redirectUrl({origin:'https://example.test',pathname:'/index.html'}),
    'https://example.test/'
  );
});

test('owner sync uses dedicated Trend Birth row and existing RLS RPC',async()=>{
  let rows=[];
  const rpcCalls=[];
  const user={id:'11111111-1111-1111-1111-111111111111',email:'owner@example.test'};
  const client={
    auth:{
      async getSession(){return{data:{session:{user}},error:null}},
      onAuthStateChange(){return{data:{subscription:{unsubscribe(){}}}}},
      async signOut(){return{error:null}}
    },
    from(table){
      assert.equal(table,'unified_watchlist_items');
      const chain={
        select(){return chain},
        eq(){return chain},
        order(){return Promise.resolve({data:rows.map(ticker=>({ticker})),error:null})}
      };
      return chain;
    },
    async rpc(name,args){
      assert.equal(name,'unified_set_watchlist_ticker');
      rpcCalls.push(args);
      const ticker=String(args.p_ticker).toUpperCase();
      if(args.p_present){
        if(!rows.includes(ticker))rows.push(ticker);
      }else rows=rows.filter(item=>item!==ticker);
      return{error:null};
    }
  };
  const sync=OwnerWatchlistSync.create({supabaseLib:{createClient:()=>client}});
  await sync.init();
  assert.deepEqual(await sync.migrate(['CLOV']),['CLOV']);
  assert.deepEqual(await sync.setTicker('NVDA',true),['CLOV','NVDA']);
  assert.deepEqual(await sync.setTicker('CLOV',false),['NVDA']);
  assert.ok(rpcCalls.every(call=>call.p_name==='Trend Birth'));
  assert.ok(rpcCalls.every(call=>call.p_mode==='next'));
  assert.ok(rpcCalls.every(call=>call.p_price_basis==='split_only'));
});


test('owner sync sends magic links through the allowed Unified Site URL',async()=>{
  let otpPayload=null;
  const client={
    auth:{
      async getSession(){return{data:{session:null},error:null}},
      onAuthStateChange(){return{data:{subscription:{unsubscribe(){}}}}},
      async signInWithOtp(payload){otpPayload=payload;return{error:null}},
      async signOut(){return{error:null}}
    }
  };
  const sync=OwnerWatchlistSync.create({supabaseLib:{createClient:()=>client}});
  await sync.init();
  await sync.sendMagicLink(' owner@example.test ');
  assert.equal(otpPayload.email,'owner@example.test');
  assert.equal(otpPayload.options.shouldCreateUser,false);
  assert.equal(
    otpPayload.options.emailRedirectTo,
    'https://garrincha077.github.io/StockScout-Unified/'
  );
  assert.equal(sync.config.magicLinkSiteUrl,'https://garrincha077.github.io/StockScout-Unified/');
});
