const test=require('node:test');
const assert=require('node:assert/strict');
const WatchlistStore=require('../lab/watchlist-store.js');

function memoryStorage(initial={}){
  const map=new Map(Object.entries(initial));
  return{
    getItem:key=>map.has(key)?map.get(key):null,
    setItem:(key,value)=>map.set(key,String(value)),
    dump:()=>Object.fromEntries(map)
  };
}

test('watchlist persists until the ticker is explicitly toggled off',()=>{
  const storage=memoryStorage();
  let items=WatchlistStore.load(storage);
  items=WatchlistStore.toggle(items,'halo',{addedAt:'2026-09-23T20:00:00Z',addedSession:'2026-09-23'});
  items=WatchlistStore.save(storage,items);

  const reloaded=WatchlistStore.load(storage);
  assert.equal(reloaded.length,1);
  assert.equal(reloaded[0].ticker,'HALO');
  assert.equal(reloaded[0].addedSession,'2026-09-23');

  const removed=WatchlistStore.toggle(reloaded,'HALO');
  WatchlistStore.save(storage,removed);
  assert.deepEqual(WatchlistStore.load(storage),[]);
});

test('watchlist normalizes and deduplicates tickers',()=>{
  const storage=memoryStorage({
    [WatchlistStore.STORAGE_KEY]:JSON.stringify({version:1,items:[' nvda ',{ticker:'NVDA'},{ticker:'grmn'}]})
  });
  assert.deepEqual(WatchlistStore.load(storage).map(item=>item.ticker),['NVDA','GRMN']);
});

test('invalid storage never breaks the review UI',()=>{
  const storage=memoryStorage({[WatchlistStore.STORAGE_KEY]:'{not-json'});
  assert.deepEqual(WatchlistStore.load(storage),[]);
});
