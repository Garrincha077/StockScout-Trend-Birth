const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const app=fs.readFileSync(require('node:path').join(__dirname,'../lab/app.js'),'utf8');
function body(name){return app.match(new RegExp('function '+name+'\\([^]*?\\n\\}'))[0]}

test('missing numeric values remain unavailable, while a real zero is preserved',()=>{
  const context={};
  vm.runInNewContext(app.match(/const numberOrNaN=[^\n]+/)[0]+'\n'+app.match(/const fmt=[^\n]+/)[0]+
    '\n'+app.match(/const pct=[^\n]+/)[0]+';this.fmt=fmt;this.pct=pct;',context);
  for(const value of [null,undefined,'',false,'0',NaN,Infinity]){
    assert.equal(context.fmt(value),'—');assert.equal(context.pct(value),'—');
  }
  assert.equal(context.fmt(0),'0.00');assert.equal(context.pct(0),'0.0%');
});

test('the real canvas renderer uses full-history EMA and SMA values on a cropped view',()=>{
  const context={state:{chartPeriod:'3m'},devicePixelRatio:1,
    chartPeriods:{'3m':{daily:63,label:'3M'}},barDateLabel:()=>'',priceLabel:()=>''};
  vm.runInNewContext([body('normalizeBars'),body('avg'),body('draw')].join('\n')+';this.draw=draw;',context);
  const paths=[];let active;
  const ctx={scale(){},clearRect(){},fillText(){},fillRect(){},beginPath(){active=[]},
    moveTo(x,y){active.push([x,y])},lineTo(x,y){active.push([x,y])},stroke(){paths.push(active)}};
  const canvas={width:0,height:0,getBoundingClientRect:()=>({width:400,height:240}),getContext:()=>ctx};
  const closes=[...Array(197).fill(80),...Array(63).fill(100)];
  const rows=closes.map((close,i)=>({time:i+1,open:close,high:close+1,low:close-1,close,volume:10}));
  context.draw(canvas,rows);
  const [ema10,ema20,sma50]=paths.slice(-3);
  assert.equal(ema10.length,63);assert.equal(ema20.length,63);assert.equal(sma50.length,63);
  // At the 20th visible candle EMA20 must still reflect the older closes at 80.
  // Reversing the renderer's price-axis transform recovers that actual price.
  const low=99-0.101,high=101+0.101;
  const actual=high-(ema20[19][1]-24)*(high-low)/(240-24-38);
  assert.ok(Math.abs(actual-97.2978085217)<1e-8);
});
