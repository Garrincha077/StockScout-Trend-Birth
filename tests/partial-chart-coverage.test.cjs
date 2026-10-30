const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const app=fs.readFileSync(__dirname+'/../lab/app.js','utf8');
const chartLoader=app.slice(app.indexOf('async function ensureChartData('),app.indexOf('\nfunction visible(',app.indexOf('async function ensureChartData(')));

test('declared missing chart shows an empty state without fetching an invalid shard',async()=>{
  const context={rowsForPeriod:()=>[],state:{},fetch:()=>assert.fail('missing chart must not trigger a shard fetch')};
  vm.createContext(context);
  vm.runInContext(chartLoader+';globalThis.load=ensureChartData;',context);
  const result=await context.load({ticker:'MISSING',chartAvailable:false});
  assert.equal(result.length,0);
});

test('an available same-snapshot embedded chart remains usable',async()=>{
  const rows=[{close:10},{close:11}];
  const context={rowsForPeriod:()=>rows,state:{},fetch:()=>assert.fail('embedded chart needs no network')};
  vm.createContext(context);
  vm.runInContext(chartLoader+';globalThis.load=ensureChartData;',context);
  assert.equal(await context.load({ticker:'AAA',chartAvailable:false}),rows);
});
