(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.ReviewNavigation=api;
})(globalThis,function(){
  'use strict';
  const views=new Map([
    ['early','early'],['weekly','weekly'],['kell','kell-daily'],['watchlist','watchlist'],['research','research']
  ]);
  const alias=new Map([...views].map(([name,value])=>[value,name]));
  const periods=new Set(['3m','6m','1y','base','5y']);
  const ticker=value=>typeof value==='string'&&/^[A-Z0-9._-]{1,20}$/.test(value)?value:null;
  function read(search){
    const params=new URLSearchParams(search);
    return {view:views.get(params.get('view'))||null,ticker:ticker(params.get('ticker')?.toUpperCase()),
      detailView:views.get(params.get('setup'))||null,period:periods.has(params.get('range'))?params.get('range'):null};
  }
  function write(url,{view,ticker:name,detailView,period}){
    for(const key of ['view','ticker','setup','range'])url.searchParams.delete(key);
    if(alias.has(view))url.searchParams.set('view',alias.get(view));
    if(ticker(name)){
      url.searchParams.set('ticker',name);
      if(detailView!==view&&alias.has(detailView))url.searchParams.set('setup',alias.get(detailView));
      if(periods.has(period))url.searchParams.set('range',period);
    }
    return url;
  }
  function copyDate(source,target){
    const exact=source.searchParams.get('snapshot'),day=source.searchParams.get('date');
    if(/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}$/.test(exact??''))target.searchParams.set('snapshot',exact);
    else if(/^\d{4}-\d{2}-\d{2}$/.test(day??''))target.searchParams.set('date',day);
  }
  function tickerLink(href,route){
    const source=new URL(href),target=new URL(source.pathname,source.origin);
    copyDate(source,target);
    return write(target,route);
  }
  function reviewReturn(href,referrer){
    const base=new URL('./',href);
    if(!referrer)return base;
    const visited=new URL(referrer);
    if(visited.origin!==base.origin||![base.pathname,base.pathname+'index',base.pathname+'index.html'].includes(visited.pathname))return base;
    copyDate(visited,base);
    return write(base,{view:read(visited.search).view});
  }
  return {read,write,tickerLink,reviewReturn};
});
