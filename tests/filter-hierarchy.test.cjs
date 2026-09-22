const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'lab','index.html'),'utf8');
const app=fs.readFileSync(path.join(root,'lab','app.js'),'utf8');

test('universe and secondary filters are separate controls',()=>{
  for(const universe of ['all','bottom-fishing','next','ryan-original']){
    assert.match(html,new RegExp('data-universe="'+universe+'"'));
  }
  assert.match(html,/data-filter="none" class="active">All candidates/);
  assert.match(html,/data-filter="kell_bull_snort"/);
  assert.doesNotMatch(html,/data-filter="bottom-fishing"/);
});

test('secondary filtering intersects the selected universe',()=>{
  assert.match(app,/universe:'all',filter:'none'/);
  assert.match(app,/function universeMatch\(item,universe=state\.universe\)/);
  assert.match(app,/if\(!universeMatch\(item\)\)return false;\s*return matchesFilter\(item\);/);
  assert.match(app,/source\.filter\(item=>universeMatch\(item\)&&matchesFilter\(item,filter\)\)\.length/);
});

test('universe and filter active states are updated independently',()=>{
  assert.match(app,/button\[data-universe\]/);
  assert.match(app,/button\[data-filter\]/);
  assert.match(app,/state\.universe=universeButton\.dataset\.universe/);
  assert.match(app,/state\.filter=filterButton\.dataset\.filter/);
});
