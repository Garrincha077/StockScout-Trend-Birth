(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.ChartEvidence=api;
})(globalThis,function(){
  'use strict';
  const positive=value=>Number.isFinite(value)&&value>0;
  const knownVolume=value=>Number.isFinite(value)&&value>=0;

  function lastCompletedWeek(sessions,asOf){
    if(!Array.isArray(sessions)||!asOf)return null;
    const index=sessions.findIndex(row=>row[0]===asOf);
    if(index<0||index+1>=sessions.length)return null;
    const week=day=>{
      const date=new Date(day+'T00:00:00Z');
      return Math.floor((date.getTime()+(3-(date.getUTCDay()+6)%7)*86400000)/604800000);
    };
    const current=week(asOf);
    if(week(sessions[index+1][0])!==current)return asOf;
    for(let i=index-1;i>=0;i--)if(week(sessions[i][0])!==current)return sessions[i][0];
    return null;
  }

  function volume(history,shown,lookback){
    const offset=history.length-shown.length;
    const points=shown.map((bar,index)=>{
      const end=offset+index;
      const previous=history.slice(Math.max(0,end-lookback),end).map(row=>row.volume);
      const average=previous.length===lookback&&previous.every(knownVolume)?
        previous.reduce((sum,value)=>sum+value,0)/lookback:null;
      return {value:knownVolume(bar.volume)?bar.volume:null,average,up:bar.close>=bar.open};
    });
    const last=points.at(-1);
    return {points,hasValues:points.some(point=>point.value!==null),
      latest:last?.value??null,ratio:last?.value!=null&&positive(last.average)?last.value/last.average:null};
  }

  function relative(shown,sourceByDay){
    const raw=shown.map(bar=>positive(bar.rs)?bar.rs:sourceByDay.get(bar.time));
    const origin=raw.findIndex(positive);
    if(origin<0)return {points:[],latest:null,firstTime:null,lastTime:null,count:0};
    const points=raw.map(value=>positive(value)?100*value/raw[origin]:null);
    const last=points.findLastIndex(value=>value!==null);
    return {points,latest:points[last],firstTime:shown[origin].time,lastTime:shown[last].time,
      count:points.filter(value=>value!==null).length};
  }

  function surface(canvas,size){
    const rect=canvas.getBoundingClientRect();
    const dpr=window.devicePixelRatio||1;
    canvas.width=Math.max(1,Math.round(rect.width*dpr));
    canvas.height=Math.max(1,Math.round(rect.height*dpr));
    const ctx=canvas.getContext('2d');
    ctx.scale(dpr,dpr);
    ctx.font='11px system-ui,sans-serif';
    ctx.textBaseline='middle';
    const plotWidth=Math.max(1,rect.width-10-72),height=Math.max(1,rect.height-16);
    return {ctx,plotWidth,height,left:10,right:rect.width-72,
      x:index=>10+index*plotWidth/Math.max(1,size-1)};
  }

  function line(ctx,points,x,y,color){
    ctx.strokeStyle=color;
    ctx.lineWidth=1.4;
    ctx.beginPath();
    let drawing=false;
    for(const [index,value] of points.entries()){
      if(value===null){drawing=false;continue}
      if(drawing)ctx.lineTo(x(index),y(value));
      else ctx.moveTo(x(index),y(value));
      drawing=true;
    }
    ctx.stroke();
  }

  function drawVolume(canvas,data,compact){
    const {ctx,plotWidth,height,x,right}=surface(canvas,data.points.length);
    const max=Math.max(1,...data.points.flatMap(point=>[point.value||0,point.average||0]));
    const y=value=>7+height*(1-value/max);
    const width=Math.min(6,Math.max(1,plotWidth/data.points.length*.67));
    for(const [index,point] of data.points.entries()){
      if(point.value==null)continue;
      ctx.fillStyle=point.up?'#26856e':'#aa5969';
      ctx.fillRect(x(index)-width/2,y(point.value),width,Math.max(0,y(0)-y(point.value)));
    }
    line(ctx,data.points.map(point=>point.average),x,y,'#e9bd62');
    ctx.fillStyle='#aabbd0';
    ctx.fillText(compact(max),right+6,10);
  }

  function drawRelative(canvas,data){
    const {ctx,height,x,left,right}=surface(canvas,data.points.length);
    const values=data.points.filter(value=>value!==null);
    const min=Math.min(99.5,...values),max=Math.max(100.5,...values);
    const y=value=>7+height*(max-value)/(max-min);
    ctx.strokeStyle='#476175';ctx.lineWidth=1;ctx.setLineDash([4,4]);
    ctx.beginPath();ctx.moveTo(left,y(100));ctx.lineTo(right,y(100));ctx.stroke();
    ctx.setLineDash([]);
    line(ctx,data.points,x,y,'#6ed7e9');
    ctx.fillStyle='#6ed7e9';
    for(const [index,value] of data.points.entries()){
      if(value!==null&&data.points[index-1]==null&&data.points[index+1]==null){
        ctx.beginPath();ctx.arc(x(index),y(value),2,0,2*Math.PI);ctx.fill();
      }
    }
    ctx.fillStyle='#aabbd0';
    ctx.fillText('100',right+6,y(100));
  }

  return {lastCompletedWeek,volume,relative,drawVolume,drawRelative};
});
