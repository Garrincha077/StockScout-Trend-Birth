const {test}=require('node:test');
const assert=require('node:assert/strict');
const nav=require('../lab/review-navigation.js');

test('ticker links keep the chart context and archive identity without auth parameters',()=>{
  const id='2026-11-17-eod-42-1--'+'a'.repeat(64);
  const source='https://app.example/lab/?snapshot='+id+'&view=watchlist&code=private&tb_auth=done#access_token=private';
  const link=nav.tickerLink(source,{view:'early',detailView:'kell-daily',ticker:'BRK.B',period:'3m'});
  assert.equal(link.searchParams.get('snapshot'),id);
  assert.equal(link.hash,'');
  assert.deepEqual([...link.searchParams.keys()],['snapshot','view','ticker','setup','range']);
  assert.deepEqual(nav.read(link.search),{view:'early',detailView:'kell-daily',ticker:'BRK.B',period:'3m'});
});

test('invalid route parameters are ignored and closing preserves unrelated navigation state',()=>{
  assert.deepEqual(nav.read('?view=settings&ticker=%3Cimg%3E&setup=owner&range=bad'),
    {view:null,ticker:null,detailView:null,period:null});
  const url=nav.write(new URL('https://app.example/?date=2026-11-17&view=kell&ticker=ABC&range=3m'),{view:'kell-daily'});
  assert.equal(url.search,'?date=2026-11-17&view=kell');
});

test('Statistics returns to the selected Review tab and keeps foreign referrers out',()=>{
  const href='https://app.example/lab/statistics.html';
  const from='https://app.example/lab/index.html?view=weekly&ticker=ABC&date=2026-11-17&code=private';
  assert.equal(nav.reviewReturn(href,from).href,'https://app.example/lab/?date=2026-11-17&view=weekly');
  for(const foreign of ['https://other.example/lab/?view=weekly','https://app.example/outside/?view=weekly','']){
    assert.equal(nav.reviewReturn(href,foreign).href,'https://app.example/lab/');
  }
});
