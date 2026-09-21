const {test} = require('node:test');
const assert = require('node:assert/strict');
const {load} = require('../lab/snapshot-loader.js');
const id = 'run-1--' + 'a'.repeat(64);
test('old links request only their exact archive', async () => {
  const paths=[];
  const data=await load(async path=>{paths.push(path);return {ok:true,json:async()=>({old:true})}}, '?snapshot='+id);
  assert.deepEqual(paths,['data/snapshots/'+id+'.json']);
  assert.equal(data.old,true);
});
test('missing archive never silently loads latest', async () => {
  let calls=0;
  await assert.rejects(load(async()=>{calls++;return {ok:false,status:404}}, '?snapshot='+id));
  assert.equal(calls,1);
});
test('reject traversal without fetching', async () => {
  await assert.rejects(load(()=>assert.fail('must not fetch'), '?snapshot=../latest'));
});
test('latest follows manifest and rejects mixed runs', async () => {
  const manifest={schemaVersion:'trend-birth-publication-v1',snapshotId:id,runId:'run-1',sessionDate:'2026-09-18'};
  await assert.rejects(load(async path=>({ok:true,json:async()=>path.endsWith('publication.json')?manifest:{source:{runId:'run-2'}}}), ''));
});
