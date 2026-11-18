const {test}=require('node:test');
const assert=require('node:assert/strict');
const Plans=require('../lab/review-plans.js');
const Book=require('../lab/owner-plan-book.js');

const origin='2026-11-17',later='2026-11-18';
const snapshot=(day,token)=>day+'-eod-123-1--'+token.repeat(64);
const plan=(ticker='AAA',token='a',strategy='early')=>({ticker,strategy,snapshotId:snapshot(origin,token),
  sessionDate:origin,price:100,pivot:105,invalidation:95,maxEntry:null,evidence:[]});

test('optimistic retry preserves an archive written by another device',async()=>{
  const existing=plan(),incoming=plan('BBB');
  let remote={version:1,plans:[existing]},writes=0;
  const transport={
    loadPlanBook:async owner=>{assert.equal(owner,'A');return remote},
    writePlanBook:async(owner,version,rows)=>{
      assert.equal(owner,'A');
      if(++writes===1){
        remote={version:2,plans:Book.archivePlan(remote.plans,Plans.planId(existing)).plans};
        return null;
      }
      assert.equal(version,2);
      remote={version:version+1,plans:rows};
      return remote.version;
    }
  };
  const {book}=await Book.update(transport,'A',rows=>Book.savePlan(rows,incoming));
  assert.equal(book.version,3);
  assert.ok(book.plans[0].archivedAt);
  assert.deepEqual(book.plans[1],incoming);
  assert.throws(()=>Book.savePlan(book.plans,existing),/arhiviran na drugom uređaju/);
  assert.equal(Book.savePlan(book.plans,existing,book.plans[0].archivedAt).plans[0].archivedAt,null);
});

test('explicit import preserves archived records and keeps competing active copies local',()=>{
  const existing=plan(),duplicate=plan(),competing=plan('AAA','b'),archived={...plan('AAA','c'),archivedAt:'2026-11-18T22:00:00Z'};
  const otherStrategy=plan('AAA','d','kell');
  const {plans,result}=Book.importPlans([existing],[duplicate,competing,archived,otherStrategy]);
  assert.deepEqual(result,{added:2,updated:0,existing:1,conflicts:1});
  assert.deepEqual(plans,[existing,archived,otherStrategy]);
  assert.deepEqual(Book.projection([existing,competing],[archived,{...existing,archivedAt:archived.archivedAt}]),
    [{...existing,archivedAt:archived.archivedAt},competing,archived]);
});

test('a synchronized closing review survives a later archive on an incomplete device',()=>{
  const active=plan(),id=Plans.planId(active);
  const sessions={schemaVersion:'xnys-eod-sessions-v1',sessions:[[origin],[later]]};
  const assessment=Plans.assess(active,[{day:origin,close:100},{day:later,close:106}],later,sessions);
  const review=Plans.closingReview(active,snapshot(later,'b'),assessment);
  const reviewed=Book.reviewPlans([active],new Map([[id,review]])).plans;
  assert.deepEqual(Plans.archivedReview(reviewed[0]),review);
  assert.equal(Book.canImport(reviewed[0],active),true);
  assert.deepEqual(Book.importPlans([active],reviewed),{plans:reviewed,result:{added:0,updated:1,existing:0,conflicts:0}});
  const archived=Book.archivePlan(reviewed,id).plans;
  assert.ok(archived[0].archivedAt);
  assert.deepEqual(Plans.archivedReview(archived[0]),review);
  assert.equal(Book.canImport(reviewed[0],archived[0]),false);
  assert.equal(Book.reviewPlans(archived,new Map([[id,review]])).plans,archived);
});
