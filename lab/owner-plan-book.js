(function(root,factory){
  const api=factory(typeof module==='object'&&module.exports?require('./review-plans.js'):root.ReviewPlans);
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.OwnerPlanBook=api;
})(globalThis,function(Plans){
  'use strict';
  const sameSlot=(left,right)=>left.strategy===right.strategy&&left.ticker===right.ticker;

  function validate(book){
    if(!Number.isSafeInteger(book?.version)||book.version<0||!Array.isArray(book.plans)||
      book.plans.some(plan=>!Plans.validPlan(plan)))throw Error('Planovi na računu nisu čitljivi.');
    if(new Set(book.plans.map(Plans.planId)).size!==book.plans.length)
      throw Error('Račun sadrži višestruke zapise istog plana.');
    return book;
  }
  function projection(local,remote){
    const rows=new Map(local.map(plan=>[Plans.planId(plan),plan]));
    for(const plan of remote||[])rows.set(Plans.planId(plan),plan);
    return [...rows.values()];
  }
  function inMemory(plans){
    let value=JSON.stringify({version:1,plans});
    return {getItem:key=>key===Plans.STORAGE_KEY?value:null,setItem:(_key,next)=>{value=next},removeItem:()=>{}};
  }
  function savePlan(plans,plan,expectedArchive){
    const existing=plans.find(row=>Plans.planId(row)===Plans.planId(plan));
    if(existing&&!existing.archivedAt)return {plans};
    if(existing?.archivedAt&&existing.archivedAt!==expectedArchive)
      throw Error('Plan je arhiviran na drugom uređaju. Osvježi Watchlistu prije ponovnog otvaranja.');
    const storage=inMemory(plans);
    if(!Plans.save(storage,undefined,plan))throw Error('Na računu već postoji aktivan plan za ovaj ticker i strategiju.');
    return {plans:Plans.load(storage)};
  }
  function archivePlan(plans,id,review){
    const storage=inMemory(plans);
    if(!Plans.archive(storage,undefined,id,review))return {plans};
    return {plans:Plans.load(storage)};
  }
  function reviewPlans(plans,reviews){
    let changed=false;
    const next=plans.map(plan=>{
      const candidate=reviews.get(Plans.planId(plan)),previous=Plans.archivedReview(plan);
      if(plan.archivedAt||!candidate||previous&&previous.asOf>=candidate.asOf)return plan;
      const updated={...plan,closingReview:candidate};
      if(!Plans.archivedReview(updated))return plan;
      changed=true;
      return updated;
    });
    return {plans:changed?next:plans};
  }
  function canImport(local,remote){
    if(!remote)return true;
    const candidate=Plans.archivedReview(local),previous=Plans.archivedReview(remote);
    return !remote.archivedAt&&Boolean(candidate&&(!previous||candidate.asOf>previous.asOf)&&
      Plans.archivedReview({...remote,closingReview:candidate}));
  }
  function importPlans(plans,local){
    const result={added:0,updated:0,existing:0,conflicts:0},next=[...plans];
    const ids=new Map(plans.map((plan,index)=>[Plans.planId(plan),index]));
    for(const plan of local){
      const id=Plans.planId(plan);
      const index=ids.get(id);
      if(index!==undefined){
        const remote=next[index],candidate=Plans.archivedReview(plan);
        if(canImport(plan,remote)){
          next[index]={...remote,closingReview:candidate};
          result.updated++;
          continue;
        }
        result.existing++;
        continue;
      }
      if(!plan.archivedAt&&next.some(row=>!row.archivedAt&&sameSlot(row,plan))){result.conflicts++;continue}
      ids.set(id,next.length);
      next.push(plan);
      result.added++;
    }
    return {plans:result.added||result.updated?next:plans,result};
  }
  async function update(transport,ownerId,transform){
    for(let attempt=0;attempt<4;attempt++){
      const book=validate(await transport.loadPlanBook(ownerId));
      const next=transform(book.plans);
      if(next.plans===book.plans)return {book,result:next.result};
      const version=await transport.writePlanBook(ownerId,book.version,next.plans);
      if(version===book.version+1)return {book:{version,plans:next.plans},result:next.result};
      if(version!==null)throw Error('Račun nije potvrdio novu verziju planova.');
    }
    throw Error('Planovi se istovremeno mijenjaju na drugom uređaju. Pokušaj ponovno.');
  }
  return {validate,projection,savePlan,archivePlan,reviewPlans,canImport,importPlans,update};
});
