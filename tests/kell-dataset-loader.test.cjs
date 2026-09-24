const test=require('node:test');
const assert=require('node:assert/strict');
const {resolve,load}=require('../lab/kell-dataset-loader.js');

const id='run-1--'+'a'.repeat(64);
const review={runId:'run-1',sessionDate:'2026-09-23',unifiedManifestSha256:'b'.repeat(64)};
const matching={source:{...review}};

test('snapshot links request their exact Kell companion first',async()=>{
  const paths=[];
  const data=await load(async path=>{
    paths.push(path);
    return{ok:true,status:200,json:async()=>matching};
  },'?snapshot='+id,review);
  assert.deepEqual(paths,['data/kell-snapshots/'+id+'.json']);
  assert.equal(data.source.runId,'run-1');
});

test('missing snapshot companion may use latest only when identity still matches',async()=>{
  const paths=[];
  const data=await load(async path=>{
    paths.push(path);
    if(path.startsWith('data/kell-snapshots/'))return{ok:false,status:404};
    return{ok:true,status:200,json:async()=>matching};
  },'?snapshot='+id,review);
  assert.deepEqual(paths,['data/kell-snapshots/'+id+'.json','data/kell-latest.json']);
  assert.equal(data.source.sessionDate,'2026-09-23');
});

test('missing snapshot companion never accepts Kell latest from another run',async()=>{
  await assert.rejects(
    load(async path=>{
      if(path.startsWith('data/kell-snapshots/'))return{ok:false,status:404};
      return{ok:true,status:200,json:async()=>({
        source:{runId:'run-0',sessionDate:'2026-09-22',unifiedManifestSha256:'c'.repeat(64)}
      })};
    },'?snapshot='+id,review),
    /odbijam koristiti Kell podatke iz drugog Unified runa/
  );
});

test('dated archives use dated Kell history',()=>{
  assert.equal(resolve('?date=2026-09-23').primary,'data/kell-history/2026-09-23.json');
});

test('latest view uses moving Kell latest',()=>{
  assert.equal(resolve('').primary,'data/kell-latest.json');
});
