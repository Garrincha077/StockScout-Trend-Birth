const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'lab','index.html'),'utf8');
const app=fs.readFileSync(path.join(root,'lab','app.js'),'utf8');

test('universe and secondary filters remain separate controls',()=>{
  for(const universe of ['all','bottom-fishing','next','ryan-original','watchlist']){
    assert.match(html,new RegExp('data-universe="'+universe+'"'));
  }
  assert.match(html,/data-filter="none" class="active">Clear filters/);
  assert.match(html,/data-filter="kell_bull_snort"/);
  assert.match(html,/data-filter="crash-base"/);
  for(const filter of ['tb-path:recovery','tb-path:compression','tb-path:ignition']){
    assert.match(html,new RegExp('data-filter="'+filter+'"'));
  }
  assert.doesNotMatch(html,/data-filter="bottom-fishing"/);
  assert.doesNotMatch(html,/data-universe="crash-base"/);
});

test('Crash Base remains a review filter and does not switch to the Kell dataset',()=>{
  assert.match(app,/if\(filter==='crash-base'\)return item\?\.metrics\?\.crashBaseTriggered===true;/);
  assert.match(app,/'crash-base':'Crash Base'/);
  assert.match(app,/'tb-path:recovery':'Recovery'/);
  assert.match(app,/'tb-path:compression':'Compression'/);
  assert.match(app,/'tb-path:ignition':'Ignition'/);
  assert.match(app,/const filterLabel=key=>reviewFilterLabels\[key\]\|\|kellFilterLabels\[key\]\|\|key;/);
  assert.match(app,/filter\(key=>!\['multi','action'\]\.includes\(key\)\)/);
});

test('Birth Path filters are supporting-evidence filters, not dataset switches',()=>{
  assert.match(app,/if\(filter\.startsWith\('tb-path:'\)\)/);
  assert.match(app,/trendBirthEvidence\(item\)\[bucket\]/);
  assert.doesNotMatch(html,/data-universe="tb-path:/);
  assert.match(app,/const kellFilters=new Set\(Object\.keys\(kellFilterLabels\)/);
});

test('secondary filters are an AND intersection inside the selected universe',()=>{
  assert.match(app,/universe:'all',filters:\[\]/);
  assert.match(app,/function universeMatch\(item,universe=state\.universe\)/);
  assert.match(app,/function matchesFilters\(item,filters=activeFilters\(\)\)/);
  assert.match(app,/filters\.every\(filter=>matchesFilter\(item,filter\)\)/);
  assert.match(app,/if\(!universeMatch\(item\)\)return false;\s*return matchesFilters\(item\);/);
});

test('filter buttons toggle independently and Clear filters resets the intersection',()=>{
  assert.match(app,/state\.filters=\[\.\.\.activeFilters\(\),filter\]/);
  assert.match(app,/state\.filters=activeFilters\(\)\.filter\(value=>value!==filter\)/);
  assert.match(app,/if\(filter==='none'\)state\.filters=\[\]/);
  assert.match(app,/data-remove-filter/);
  assert.match(app,/data-clear-filters/);
});

test('active filter bar exposes the current intersection',()=>{
  assert.match(html,/id="activeFilterBar"/);
  assert.match(app,/function activeFilterSummary\(\)/);
  assert.match(app,/class="active-filter-chip"/);
  assert.match(app,/Active '\+filters\.length/);
});

test('filter counts preview the intersection after adding another filter',()=>{
  assert.match(app,/const proposed=active\.includes\(filter\)\?active:\[\.\.\.active,filter\]/);
  assert.match(app,/matchesFilters\(item,proposed\)/);
});

test('supporting Birth Path evidence does not alter Trend Birth ranking',()=>{
  assert.match(app,/if\(mode==='trend-birth'\)return trendBirthStage\(item\)\*1000\+Number\(item\.kell_score\|\|0\);/);
  assert.doesNotMatch(app,/birthEvidenceCount\(item\)\*100/);
  assert.doesNotMatch(app,/const pathRank=/);
});

test('sorting exposes Kell dimensions and RVOL without changing scoring',()=>{
  for(const value of ['kell-score','readiness','quality','evidence','rvol']){
    assert.match(html,new RegExp('option value="'+value+'"'));
  }
  assert.match(app,/if\(mode==='readiness'\)return Number\(item\.kell_readiness_score\)/);
  assert.match(app,/if\(mode==='quality'\)return Number\(item\.kell_quality_score\)/);
  assert.match(app,/if\(mode==='evidence'\)return Number\(item\.kell_evidence_coverage\)/);
  assert.match(app,/if\(mode==='rvol'\)return Number\(item\.metrics\?\.rvol\)/);
});
