const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'lab','index.html'),'utf8');
const app=fs.readFileSync(path.join(root,'lab','app.js'),'utf8');
const css=fs.readFileSync(path.join(root,'lab','styles.css'),'utf8');

test('quick views expose high-value review presets',()=>{
  for(const view of ['ready','leaders','breakout','extended','reset']){
    assert.match(html,new RegExp('data-quick-view="'+view+'"'));
  }
  assert.match(app,/ready:\{filters:\['kell-ready'\],sort:'readiness'\}/);
  assert.match(app,/leaders:\{filters:\['kell_rs_leader','kell_weekly_trend_ok'\],sort:'quality'\}/);
  assert.match(app,/breakout:\{filters:\['kell_breakout_proximity','kell_weekly_trend_ok'\],sort:'readiness'\}/);
  assert.match(app,/extended:\{filters:\['stage:exhaustion_extension'\],sort:'kell-score'\}/);
  assert.match(app,/if\(filter==='kell-ready'\)return Number\(item\.kell_readiness_score\)>=80/);
});

test('manual filter interaction clears quick-view ownership without clearing filters',()=>{
  assert.match(app,/if\(universeButton\)\{\s*state\.quickView=null/);
  assert.match(app,/if\(filterButton\)\{\s*state\.quickView=null/);
  assert.match(app,/state\.quickView=null;\s*if\(clear\)state\.filters=\[\]/);
});

test('render stores sorted visible items as the detail navigation sequence',()=>{
  assert.match(app,/state\.renderedItems=items\.slice\(\)/);
  assert.match(app,/function navigateDetail\(delta\)/);
  assert.match(app,/items\.findIndex\(item=>item\.ticker===state\.detailTicker\)/);
  assert.match(app,/show\(items\[nextIndex\]\)/);
});

test('detail dialog has previous and next controls plus keyboard arrows',()=>{
  assert.match(html,/id="prevDetail"/);
  assert.match(html,/id="detailPosition"/);
  assert.match(html,/id="nextDetail"/);
  assert.match(app,/addEventListener\('click',\(\)=>navigateDetail\(-1\)\)/);
  assert.match(app,/addEventListener\('click',\(\)=>navigateDetail\(1\)\)/);
  assert.match(app,/e\.key==='ArrowLeft'/);
  assert.match(app,/e\.key==='ArrowRight'/);
  assert.match(app,/if\(!\$\('#detail'\)\.open\)\$\('#detail'\)\.showModal\(\)/);
});

test('legacy Action and Multi-hit do not become full Kell-universe filters',()=>{
  assert.match(app,/filter\(key=>!\['multi','action'\]\.includes\(key\)\)/);
});

test('mobile review keeps primary quick views and moves full filters into a drawer',()=>{
  assert.match(html,/id="mobileFiltersToggle"[^>]+aria-controls="filters"[^>]+aria-expanded="false"/);
  assert.match(html,/id="mobileFiltersClose"/);
  assert.match(html,/id="mobileFilterBackdrop"[^>]+hidden/);
  assert.match(app,/function setMobileFiltersOpen\(open,restoreFocus=false\)/);
  assert.match(app,/button\.textContent=count\?'Filters \('\+count\+'\)'\:'Filters'/);
  assert.match(app,/classList\.toggle\('mobile-open',open\)/);
  assert.match(app,/e\.key==='Escape'&&\$\('#filters'\)\?\.classList\.contains\('mobile-open'\)/);
  assert.match(css,/@media\(max-width:720px\)/);
  assert.match(css,/\.filters\.mobile-open\{display:flex\}/);
  assert.match(css,/\.quick-views button\[data-quick-view="extended"\],\.quick-views button\[data-quick-view="reset"\],\.quick-view-label\{display:none\}/);
  assert.match(css,/\.active-filter-bar\{display:none!important\}/);
  assert.match(css,/\.mobile-filter-head\+\.filter-group-label\{margin-left:0;padding-left:0;border-left:0\}/);
});
