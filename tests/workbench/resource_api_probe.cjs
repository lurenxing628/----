'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/resource-api.js'), 'utf8');
const ref = 'a'.repeat(48), key = 'resource-' + 'b'.repeat(48);
const envelope = () => ({ok:true,schema_version:1,data:{entities:[]},meta:{source:'production',time_basis:'factory_local',
  snapshot_ref:'snap',request_ref:'req',as_of:'2026-09-09T08:15:00'},warnings:[]});
const receipt = () => ({ok:true,result:'committed',data:{entity_ref:ref},receipt_ref:'saved',replayed:false,warnings:[]});
const response = (value, status=200, mime='application/json') => ({ok:status>=200&&status<300,status,
  headers:{get:name=>name==='content-type'?mime:null},json:async()=>value,blob:async()=>new Blob([value],{type:mime})});
let checks=0;
function runtime(fetcher, {storage=new Map(),delay=20000,storageFailure=false}={}) {
  let timers=0, requests=0;
  const context=vm.createContext({URL,AbortController,FormData,Blob,console,
    location:{origin:'http://127.0.0.1:8222',href:'http://127.0.0.1:8222/workbench?view=process'},
    sessionStorage:{getItem:k=>{if(storageFailure)throw new Error('denied');return storage.has(k)?storage.get(k):null;},
      setItem:(k,v)=>{if(storageFailure)throw new Error('denied');storage.set(k,v);},removeItem:k=>storage.delete(k)},
    fetch:async(...args)=>{requests++;return fetcher(...args);},setTimeout:(fn,ms)=>{assert.equal(ms,20000);timers++;return setTimeout(fn,delay);},
    clearTimeout:t=>{timers--;clearTimeout(t);}});
  context.window=context;vm.runInContext(source,context);
  for(const name of ['resource-contract.js','ProcessAPI.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../frontend/workbench/app',name),'utf8'),context);
  return {api:context.APSResourceAPI.create(),create:namespace=>context.APSResourceAPI.create(namespace),process:()=>context.APSProcessAPI.create(),timers:()=>timers,requests:()=>requests,storage};
}
async function rejects(run, committed, matcher) {
  await assert.rejects(async()=>run(),error=>{assert.equal(error.committed,committed);if(matcher)assert.match(error.message,matcher);return true;});checks++;
}
async function main() {
  const good=runtime(async(url,options)=>{
    assert.equal(options.redirect,'error');assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');
    return response(envelope());
  });
  assert.deepEqual(await good.api.list('material',{query:'12 / #',page:2,size:20}),envelope());checks++;
  for(const mutate of [p=>p.meta.source='demo',p=>p.meta.time_basis='UTC',p=>p.meta.as_of='2026-09-09',p=>p.data=[],p=>delete p.warnings]) {
    const payload=envelope();mutate(payload);const r=runtime(async()=>response(payload));
    await rejects(()=>r.api.summary(),false,/协议不匹配/);assert.equal(r.timers(),0);
  }
  for(const [kind,entity] of [['unknown',ref],['material','bad'],['material','../outside']]) {
    await rejects(()=>good.api.detail(kind,entity),false);assert.equal(good.requests(),1);
  }
  const payload={request_key:key,write_token:'secret-short-token',input:{label:'New'}};
  const successful=runtime(async(url,options)=>{assert.equal(url,'http://127.0.0.1:8222/api/workbench/v1/entities/material/'+ref+'/update');
    assert.deepEqual(JSON.parse(options.body),payload);return response(receipt());});
  assert.deepEqual(await successful.api.command('material','update',ref,payload),receipt());checks++;
  await rejects(()=>successful.api.command('material','create',ref,payload),false);
  for(const mode of ['offline','html','badjson','badshape','http500']) {
    const r=runtime(async()=>{
      if(mode==='offline')throw new TypeError('offline');
      if(mode==='html')return response('<html>',200,'text/html');
      if(mode==='badjson')return {...response(null),json:async()=>{throw new SyntaxError('bad');}};
      return response({ok:true,result:'committed'},mode==='http500'?500:200);
    });
    await rejects(()=>r.api.command('material','update',ref,payload),'unknown');assert.equal(r.requests(),1);assert.equal(r.timers(),0);
  }
  for(const committed of [false,true,'unknown']) {
    const error={code:'stale_write',message:'请核对原值',fields:[{path:'label',message:'名称已变化'}],request_ref:'request-id'};
    const r=runtime(async()=>response({ok:false,committed,error},409));
    await assert.rejects(()=>r.api.command('material','update',ref,payload),e=>{assert.equal(e.committed,committed);assert.deepEqual(e.error,error);return true;});checks++;
  }
  const cancelled=new AbortController();cancelled.abort();
  await rejects(()=>good.api.command('material','update',ref,payload,cancelled.signal),false,/未发送/);assert.equal(good.requests(),1);
  const timeout=runtime(async(_,options)=>new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('aborted'),{name:'AbortError'})))),{delay:3});
  await rejects(()=>timeout.api.command('material','update',ref,payload),'unknown',/超时/);assert.equal(timeout.timers(),0);
  const lookup=runtime(async()=>response({ok:true,state:'not_recorded',receipt:null,may_be_in_flight:true}));
  assert.equal((await lookup.api.lookup(key)).state,'not_recorded');checks++;
  const pending=runtime(async()=>response(receipt()));
  pending.api.savePending({kind:'material',action:'update',ref,request_key:key,input:{label:'private'},write_token:'never-store'});
  assert(!Array.from(pending.storage.values()).join('').includes('private'));assert(!Array.from(pending.storage.values()).join('').includes('never-store'));checks++;
  const reloaded=runtime(async()=>response(receipt()),{storage:pending.storage});
  assert.equal(reloaded.api.readPending().request_key,key);assert.deepEqual(await reloaded.api.lookup(key),receipt());checks++;
  reloaded.api.clearPending();assert.equal(pending.api.readPending(),null);checks++;
  for(const kind of ['material','op_type','machine','operator','supplier'])for(const action of ['import','bulk']){
    const isolated=runtime(async()=>response(receipt())),api=isolated.create(kind+'_files');
    const intent={kind:kind+'_'+action,action:'confirm',ref:'p'.repeat(32),request_key:key,
      ...(kind==='op_type'?{category:'external'}:{}),input:{private:'never-persist'},write_token:'never-store'};
    api.savePending(intent);
    assert.equal(api.readPending().kind,intent.kind);assert.equal(api.readPending().category,intent.category);
    assert.equal(isolated.api.readPending(),null);assert(![...isolated.storage.values()].join('').includes('never-'));checks++;
    const restored=runtime(async()=>response(receipt()),{storage:isolated.storage}).create(kind+'_files');
    assert.equal(restored.readPending().request_key,key);restored.clearPending();assert.equal(api.readPending(),null);checks++;
    const foreign={...intent,kind:kind==='machine'?'operator_import':'machine_import',category:undefined};
    assert.throws(()=>api.savePending(foreign),error=>error.committed===false);checks++;
  }
  const typed=runtime(async()=>response(receipt())).create('op_type_files');
  const namespaces=['resources','calendar','catalog','process','batches',...['material','op_type','machine','operator','supplier'].map(kind=>kind+'_files')];
  const precise=[['process',{kind:'process',action:'create',ref:null}],
    ...['route_confirm','source_confirm','hours_confirm'].map(action=>['process',{kind:'process',action,ref}]),
    ...['process_bulk','process_route_import','process_hours_import'].map(kind=>['process',{kind,action:'confirm',ref:'A_-9'.repeat(8)}]),
    ...['create','update','delete','operation_update','sync_confirm'].map(action=>['batches',{kind:'batch',action,ref:action==='create'?null:ref}]),
    ...['bulk_confirm','import_confirm'].map(action=>['batches',{kind:'batch',action,ref:'A_-9'.repeat(8)}])];
  for(const [namespace,shape] of precise) {
    const fixture=runtime(async url=>{assert(url.endsWith('/commands/'+key));return response(receipt());});
    const intent={...shape,request_key:key,input:{secret:'never-persist'},write_token:'never-persist'},api=fixture.create(namespace);
    api.savePending(intent);assert.equal(api.readPending().request_key,key);
    assert(![...fixture.storage.values()].join('').includes('never-persist'));checks++;
    const fresh=runtime(async url=>{assert(url.endsWith('/commands/'+key));return response(receipt());},{storage:fixture.storage}).create(namespace);
    assert.deepEqual(JSON.parse(JSON.stringify(fresh.readPending())),{...shape,request_key:key});assert.deepEqual(await fresh.lookup(key),receipt());checks++;
    for(const foreign of namespaces.filter(value=>value!==namespace)) {
      assert.throws(()=>fixture.create(foreign).savePending(intent),e=>e.committed===false);
      const storage=new Map([['aps_workbench_resource_pending_v1'+(foreign==='resources'?'':'_'+foreign),JSON.stringify(intent)]]);
      assert.throws(()=>runtime(async()=>response(receipt()),{storage}).create(foreign).readPending(),e=>e.committed==='unknown');checks++;
    }
    for(const category of [null,'internal','external','']) {assert.throws(()=>api.savePending({...intent,category}),e=>e.committed===false);checks++;}
    const badRefs=shape.ref===null?[undefined,ref,'']:[null,undefined,shape.ref.length===32?ref:'A_-9'.repeat(8),'x'.repeat(48),'a'.repeat(31),'a'.repeat(33),'a'.repeat(47),'a'.repeat(49),'!'.repeat(32),48];
    for(const id of badRefs) {assert.throws(()=>api.savePending({...intent,ref:id}),e=>e.committed===false);checks++;}
    for(const action of ['unknown','confirm_all','import','upsert']) {assert.throws(()=>api.savePending({...intent,action}),e=>e.committed===false);checks++;}
    fresh.clearPending();assert.equal(api.readPending(),null);checks++;
  }
  for(const namespace of ['batch','process_files','process_route_import','process_other','unknown','resources_files',null,{}]) {
    assert.throws(()=>good.create(namespace),e=>e.committed===false);checks++;
  }
  for(const kind of ['batch','process','process_bulk']) {await rejects(()=>good.api.detail(kind,ref),false);assert.equal(good.requests(),1);}
  for(const action of ['route_confirm','source_confirm','hours_confirm']) {
    const fixture=runtime(async(url,options)=>{
      assert.equal(url,'http://127.0.0.1:8222/api/workbench/v1/process/'+ref+'/'+action);
      assert.deepEqual(JSON.parse(options.body),payload);return response(receipt());
    }), process=fixture.process();
    process.savePending({kind:'process',action,ref,request_key:key,input:{private:'do-not-store'},write_token:'do-not-store'});
    assert.equal(fixture.api.readPending(),null);assert.equal(process.readPending().action,action);
    assert(![...fixture.storage.values()].join('').includes('do-not-store'));
    assert.deepEqual(await process.command('process',action,ref,payload),receipt());
    const fresh=runtime(async()=>response(receipt()),{storage:fixture.storage}).process();
    assert.equal(fresh.readPending().ref,ref);assert.deepEqual(await fresh.lookup(key),receipt());fresh.clearPending();assert.equal(process.readPending(),null);checks++;
    assert.throws(()=>fixture.api.savePending({kind:'process',action,ref,request_key:key}),error=>error.committed===false);checks++;
    assert.throws(()=>process.savePending({kind:'material',action:'update',ref,request_key:key}),error=>error.committed===false);checks++;
  }
  const processRead=runtime(async(url,options)=>{
    assert.equal(options.method,'POST');assert(url.endsWith('/stage-preview'));
    assert.deepEqual(JSON.parse(options.body),{action:'source_confirm',input:{operations:[]},snapshot_ref:'held'});return response(envelope());
  });
  assert.deepEqual(await processRead.process().stagePreview(ref,'source_confirm',{operations:[]},'held'),envelope());checks++;
  const processOffline=runtime(async()=>{throw new Error('offline');}).process();
  await rejects(()=>processOffline.stagePreview(ref,'source_confirm',{},'held'),false);
  await rejects(()=>processOffline.command('process','hours_confirm',ref,payload),'unknown');
  const processInvalid=runtime(async()=>{throw new Error('Must not request');});
  for(const [kind,action,id] of [['part','route_confirm',ref],['process','create',ref],['process','route_confirm','bad'],['process','hours_confirm',null]])
    await rejects(()=>processInvalid.process().command(kind,action,id,payload),false);
  assert.equal(processInvalid.requests(),0);checks++;
  for(const category of [undefined,null,'all','internal,external']){
    assert.throws(()=>typed.savePending({kind:'op_type_import',action:'confirm',ref:'p'.repeat(32),request_key:key,category}),error=>error.committed===false);checks++;
  }
  const contaminated=new Map([['aps_workbench_resource_pending_v1_machine_files',JSON.stringify({kind:'operator_import',action:'confirm',ref:'p'.repeat(32),request_key:key})]]);
  assert.throws(()=>runtime(async()=>response(receipt()),{storage:contaminated}).create('machine_files').readPending(),error=>error.committed==='unknown');checks++;
  const denied=runtime(async()=>response(receipt()),{storageFailure:true});
  assert.throws(()=>denied.api.readPending(),e=>e.committed==='unknown');checks++;
  assert.throws(()=>denied.api.savePending({kind:'material',action:'update',ref,request_key:key}),e=>e.committed===false);checks++;
  const csv=runtime(async()=>response('编号,名称\n001,Text',200,'text/csv;charset=utf-8'));
  assert((await csv.api.download('exports/material',{})).blob.size>0);checks++;
  const html=runtime(async()=>response('HTML',200,'text/html'));
  await rejects(()=>html.api.download('exports/material',{}),false,/格式不正确/);
  const empty=runtime(async()=>response('',200,'text/csv'));
  await rejects(()=>empty.api.download('exports/material',{}),false,/为空/);
  const scope=runtime(async(url)=>{const query=new URL(url).searchParams;assert.equal(query.get('query'),'12 / #');assert.equal(query.get('status'),null);assert.equal(query.get('snapshot_ref'),null);return response(envelope());});
  await scope.api.list('material',{query:'12 / #',status:'',snapshot_ref:undefined});checks++;
  const filters={spec:{mode:'include',values:['c'.repeat(64)]}}, filteredCalls=[];
  const filtered=runtime(async(url,options)=>{filteredCalls.push({url,method:options.method,body:JSON.parse(options.body)});return response(envelope());});
  await filtered.api.list('material',{query:'12',status:'',page:2,size:20,column_filters:filters,snapshot_ref:'held'});
  assert.equal(filteredCalls[0].method,'POST');assert(filteredCalls[0].url.endsWith('/entities/material/query'));
  assert.deepEqual(filteredCalls[0].body,{query:'12',page:2,size:20,column_filters:filters,snapshot_ref:'held'});checks++;
  await filtered.api.facets('machine',{scope:{status:'',category:null},column:'label',query:'name',page:1,size:100});
  assert(filteredCalls[1].url.endsWith('/entities/machine/facets'));assert.deepEqual(filteredCalls[1].body.scope,{});checks++;
  await filtered.api.facetSelection('machine',{scope:{query:'M'},column:'label',query:'name',size:100,snapshot_ref:'facet'});
  assert(filteredCalls[2].url.endsWith('/entities/machine/facet-selection'));checks++;
  const cleared=runtime(async(url,options)=>{assert.equal(options.method,'GET');assert.equal(new URL(url).searchParams.has('column_filters'),false);return response(envelope());});
  await cleared.api.list('material',{column_filters:{}});checks++;
  await rejects(()=>cleared.api.list('material',{column_filters:null}),false,/未切换到全量列表/);assert.equal(cleared.requests(),1);
  const readFailed=runtime(async()=>{throw new Error('offline');});
  await rejects(()=>readFailed.api.list('material',{column_filters:filters}),false,/请重新读取/);
  assert.equal(readFailed.storage.size,0);checks++;
  const contracts=vm.createContext({});contracts.window=contracts;
  for(const name of ['resource-contract.js','ResourceMaterialContract.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../frontend/workbench/app',name),'utf8'),contracts);
  const materialScope=contracts.APSResourceMaterial.requestBody('export',{refs:[],scope:{query:'filter',status:'',sort:'business_code',direction:'asc',size:20,snapshot_ref:'a'.repeat(32)}},'filtered');
  assert.deepEqual(JSON.parse(JSON.stringify(materialScope)),{scope:{query:'filter',sort:'business_code',direction:'asc'},snapshot_ref:'a'.repeat(32),page_size:20,selection:'filtered'});checks++;
  const columnScope=contracts.APSResourceMaterial.requestBody('export',{refs:[],scope:{column_filters:filters,size:20,snapshot_ref:'a'.repeat(32)}},'filtered');
  assert.deepEqual(JSON.parse(JSON.stringify(columnScope.scope.column_filters)),filters);
  filters.spec.values.push('d'.repeat(64));assert.equal(columnScope.scope.column_filters.spec.values.length,1);checks++;
  const C=contracts.APSResourceContract;
  const before={ref,business_code:'M1',label:'Original',status:'active',fields:{spec:'Before',unit:'kg',stock_qty:1.25},relationships:{}};
  const after={...before,label:'Server name',fields:{...before.fields,spec:'Other window',unit:'件',stock_qty:2.75}};
  const draft=C.draft('material',before);draft.label='My draft';draft.fields.stock_qty='8.375';
  const merged=C.rebaseDraft('material',draft,before,after);
  assert.equal(merged.fields.unit,'件');assert.equal(merged.fields.spec,'Other window');assert.equal(merged.fields.stock_qty,'8.375');
  assert.deepEqual(JSON.parse(JSON.stringify(C.input('material',merged,after))),{label:'My draft',fields:{stock_qty:8.375}});checks++;
  const untouched=C.rebaseDraft('material',C.draft('material',before),before,after);
  assert.equal(untouched.fields.stock_qty,'2.75');assert.equal(untouched.label,'Server name');assert.deepEqual(JSON.parse(JSON.stringify(C.input('material',untouched,after))),{});checks++;
  const unknown={...before,fields:{...before.fields,stock_qty:null}},zero=C.draft('material',unknown);zero.fields.stock_qty='0';
  assert.deepEqual(JSON.parse(JSON.stringify(C.input('material',C.rebaseDraft('material',zero,unknown,after),after))),{fields:{stock_qty:0}});checks++;
  const person={ref,business_code:'P1',label:'Person',status:'active',fields:{},relationships:{skill_refs:['1'.repeat(48)],shift_profile_ref:'2'.repeat(48)}};
  const newPerson={...person,relationships:{skill_refs:['3'.repeat(48)],shift_profile_ref:'4'.repeat(48)}};
  const personDraft=C.draft('operator',person);personDraft.relationships.skill_refs=['5'.repeat(48)];
  const personMerged=C.rebaseDraft('operator',personDraft,person,newPerson);assert.equal(personMerged.relationships.shift_profile_ref,'4'.repeat(48));
  assert.deepEqual(JSON.parse(JSON.stringify(C.input('operator',personMerged,newPerson))),{relationships:{skill_refs:['5'.repeat(48)]}});checks++;
  for (const action of ['create','supplement','correct','import_confirm']) {
    const instance = runtime(async()=>response(receipt())), api = instance.create('execution');
    const intent = {kind:'execution',action,ref:action==='import_confirm'?'p_-'.repeat(10)+'xy':ref,request_key:key};
    api.savePending({...intent,input:{hidden:'do-not-persist'},write_token:'do-not-persist'});
    assert.deepEqual(JSON.parse(JSON.stringify(api.readPending())),intent);
    assert(![...instance.storage.values()].join('').includes('do-not-persist'));checks+=2;
    assert.equal(instance.api.readPending(),null);checks++;
    for(const namespace of ['resources','process','batches','calendar','catalog','material_files']) {
      assert.throws(()=>instance.create(namespace).savePending(intent),e=>e.committed===false);checks++;
    }
    for(const category of [null,'internal','external']) {
      assert.throws(()=>api.savePending({...intent,category}),e=>e.committed===false);checks++;
    }
    const restored=runtime(async()=>response(receipt()),{storage:instance.storage}).create('execution');
    assert.equal(restored.readPending().request_key,key);await restored.lookup(key);restored.clearPending();assert.equal(api.readPending(),null);checks+=2;
  }
  const executionOnly=runtime(async()=>{throw Error('Must not request');});
  for(const [action,id] of [['create',null],['delete',ref],['update',ref],['correct','bad'],['import_confirm',ref]]) {
    assert.throws(()=>executionOnly.create('execution').savePending({kind:'execution',action,ref:id,request_key:key}),e=>e.committed===false);checks++;
  }
  await rejects(()=>executionOnly.api.list('execution',{}),false);assert.equal(executionOnly.requests(),0);checks++;
  console.log(JSON.stringify({checks,network:'mock-only',production:false,persisted_fields:['kind','action','ref','request_key','category']}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
