const {test}=require('node:test');
const assert=require('node:assert/strict');
const {lastCompletedWeek,volume,relative,axis}=require('../lab/chart-evidence.js');

test('weekly chart uses the last exchange session of a completed week',()=>{
  const sessions=['2026-11-20','2026-11-23','2026-11-24','2026-11-25','2026-11-27',
    '2026-11-30','2026-12-21','2026-12-22','2026-12-23','2026-12-24','2026-12-28'].map(day=>[day,0]);
  assert.equal(lastCompletedWeek(sessions,'2026-11-25'),'2026-11-20');
  assert.equal(lastCompletedWeek(sessions,'2026-11-27'),'2026-11-27');
  assert.equal(lastCompletedWeek(sessions,'2026-12-24'),'2026-12-24');
  assert.equal(lastCompletedWeek(sessions,'2026-12-25'),null);
  assert.equal(lastCompletedWeek(sessions,'2026-12-28'),null);
});

test('volume excludes the current bar from its average and preserves zero and missing bars',()=>{
  const bars=[100,200,450,0,null].map(volume=>({volume,open:10,close:11}));
  const result=volume(bars.slice(0,3),bars.slice(2,3),2);
  assert.deepEqual(result.points,[{value:450,average:150,ratio:3,up:true}]);
  assert.equal(volume(bars.slice(0,4),bars.slice(3,4),2).points[0].ratio,0);
  assert.equal(volume(bars,bars.slice(-1),2).hasValues,false);
  const incomplete=[...bars,{volume:500}];
  assert.equal(volume(incomplete,incomplete.slice(-1),2).points[0].ratio,null);
});

test('relative strength uses same-session data, rebases and preserves internal gaps',()=>{
  const bars=[
    {time:'2026-11-09',rs:null},{time:'2026-11-10',rs:25},{time:'2026-11-11',rs:null},
    {time:'2026-11-12',rs:null},{time:'2026-11-13',rs:null}
  ];
  const result=relative(bars,new Map([['2026-11-12',30],['2026-11-14',50]]));
  assert.deepEqual(result,{points:[null,100,null,120,null],firstTime:'2026-11-10',count:2});
});

test('every panel uses the same axis correction for tap selection and cursor placement',()=>{
  for(const width of [320,390,1000]){
    const plot=axis(width,63);
    assert.equal(plot.x(0),10);
    assert.equal(plot.x(62),width-72);
    for(let index=0;index<63;index++)assert.equal(plot.indexAt(plot.x(index)),index);
    assert.equal(plot.indexAt(0),0);
    assert.equal(plot.indexAt(width),62);
  }
});
