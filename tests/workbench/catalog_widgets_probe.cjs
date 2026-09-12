/* Isolated catalog fixtures with simulated production envelopes, not backend persistence proof. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const files = ['resource-contract.js', 'resource-api.js', 'resource-session.js', 'WorkbenchGuards.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'ResourceForms.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchFormat.js', 'WorkbenchReferences.jsx',
  'ResourceCatalogModel.js', 'ResourceCatalogEditor.jsx', 'ResourceCatalog.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const styleSources = ['00-tokens.css', '21-table-frame.css', '22-shared-controls.css', '32-calendar-outsourcing.css'].map(name =>
  ({ path: 'frontend/workbench/app/styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const assets = new Map(manifest.files.map(item => [item.path, item]));
const fixtureCode = `
window.fixture = {calls:[],reads:[],lookups:[],events:[],rows:[],serial:0,confirm:false};
const ref = n => n.toString(16).padStart(48,'0');
function context(token, kind, referenced=false) {return {write_token:token,capabilities:{[kind+'.create']:true,[kind+'.update']:true,[kind+'.delete']:!referenced},blocked_reasons:referenced?[{action:kind+'.delete',message:'资源仍被其他记录引用，不能删除。'}]:[]};}
function envelope(data, source='production') {return {ok:true,schema_version:1,data,meta:{source,time_basis:'factory_local',snapshot_ref:'fixture-snapshot',request_ref:'fixture-request',as_of:'2026-09-09T08:00:00'},warnings:[]};}
function record(kind,n) {return {ref:ref(n),business_code:(kind==='machine_group'?'G-':'S-')+String(n).padStart(3,'0'),label:(kind==='machine_group'?'设备组 ':'班次档 ')+n,status:'active',
 fields:{remark:'原备注',hidden_legacy:'must remain untouched',...(kind==='shift_profile'?{anchor_date:'2026-09-01',cycle_days:3,pattern:[{day_offset:0,is_rest:false,shift_start:'22:00',shift_end:'06:00'},{day_offset:1,is_rest:true,shift_start:'00:00',shift_end:'00:00'},{day_offset:2,is_rest:false,shift_start:'08:00',shift_end:'16:00'}]}:{})},
 relationships:{[kind==='machine_group'?'machine_count':'operator_count']:n===1?2:0},issues:[],write_context:context('original-token',kind,n===1)};}
function terminal(id) {return {ok:true,result:'committed',receipt_ref:'fixture-receipt-'+id,replayed:false,data:{entity_ref:ref(100)},warnings:[]};}
let renderRoot;
function Harness({spec}) {
 const adapter=React.useMemo(()=>{
  const api=APSResourceAPI.create('catalog');
  api.list=async(kind,scope)=>{fixture.reads.push({type:'list',kind,scope});let rows=fixture.rows.filter(row=>(!scope.query||row.business_code.includes(scope.query)||row.label.includes(scope.query))&&(!scope.status||scope.status===row.status));
   return envelope({entities:rows.slice((scope.page-1)*scope.size,scope.page*scope.size),page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.ceil(rows.length/scope.size),sort:[]},create_context:context('create-token',kind)},spec.source||'production');};
  api.detail=async(kind,id)=>{fixture.reads.push({type:'detail',kind,id});const row=fixture.rows.find(row=>row.ref===id);if(!row)throw APSResourceContract.failure('记录已删除。');const value=JSON.parse(JSON.stringify(row));
   if(spec.stale&&fixture.calls.length){value.label='服务器新名称';value.fields.remark='服务器保留的新备注';value.write_context=context('reviewed-token',kind);}return envelope(value,spec.source||'production');};
  api.command=async(kind,action,id,body)=>{fixture.calls.push({kind,action,id,body});sessionStorage.setItem('catalog_fixture_calls',JSON.stringify(fixture.calls));
   if(spec.pending)return {ok:false,committed:'unknown',error:{message:'提交结果未知。'}};
   if(spec.stale&&fixture.calls.length===1)return {ok:false,committed:false,error:{code:'stale_write',message:'资料已变化，请重新读取并核对。',fields:[]}};
   if(spec.reject)return {ok:false,committed:false,error:{code:'constraint_conflict',message:'目录仍被引用，不能删除。',fields:[]}};
   if(action==='delete')fixture.rows=fixture.rows.filter(row=>row.ref!==id);
   if(action==='create')fixture.rows.push({...record(kind,100),business_code:body.input.business_code,label:body.input.label,status:body.input.fields.status,fields:{...body.input.fields}});
   return terminal(fixture.calls.length);};
  api.lookup=async(key)=>{fixture.lookups.push(key);return fixture.confirm?terminal('recovered'):{ok:true,state:'not_recorded',receipt:null,may_be_in_flight:true};};return api;
 },[]);
 return React.createElement(React.Fragment,null,React.createElement(ResourceCatalog,{kind:spec.kind,adapter,onClose:()=>fixture.events.push({name:'close'}),onCommitted:receipt=>fixture.events.push({name:'commit',receipt})}),React.createElement(WorkbenchGuardHost));
}
window.mountFixture=(spec,restore=false)=>{
 if(renderRoot)renderRoot.unmount();if(!restore)sessionStorage.removeItem('aps_workbench_resource_pending_v1_catalog');
 fixture.calls=restore?JSON.parse(sessionStorage.getItem('catalog_fixture_calls')||'[]'):[];fixture.lookups=[];fixture.events=[];fixture.reads=[];fixture.confirm=false;
 fixture.rows=Array.from({length:23},(_,i)=>record(spec.kind,i+1));
 sessionStorage.setItem('catalog_fixture_spec',JSON.stringify(spec));renderRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
 renderRoot.render(React.createElement(Harness,{spec,key:++fixture.serial}));
};
if(sessionStorage.getItem('catalog_fixture_spec'))mountFixture(JSON.parse(sessionStorage.getItem('catalog_fixture_spec')),true);
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' +
  manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') + '<style>' + styleSources.map(item => item.code).join('\n') + '</style>' +
  '</head><body class="aps-workbench"><main style="padding:24px"><p>组件夹具 · 无生产数据写入</p><div id="fixture-root"></div></main>' +
  manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-')).map(file => '<script src="/static/' + file + '"></script>').join('') +
  Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixtureCode + '</script></body></html>';
const server = http.createServer((req,res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if(name === '/') {res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
  if(scripts.has(name)) {res.setHeader('Content-Type','application/javascript');res.end(scripts.get(name));return;}
  const asset = assets.get(name.slice('/static/'.length));
  if(!name.startsWith('/static/') || !asset) {res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',asset.mime);res.end(fs.readFileSync(path.join(root,'static',asset.path)));
});
const result = {scope:'isolated-catalog-component-fixtures',simulates_production_envelopes:true,production_persistence_tested:false,
  sources:sources.concat(styleSources).map(item=>({path:item.path,sha256:crypto.createHash('sha256').update(item.code).digest('hex')})),cases:[],errors:[],external:[]};
let page, variant;
async function mount(spec) {
  await page.evaluate(spec=>mountFixture(spec),spec);
  await page.getByRole('dialog').waitFor();
  await page.getByRole('button',{name:'编辑 '+(spec.kind==='machine_group'?'G-':'S-')+'002',exact:true}).waitFor();
}
async function open(kind, action='update') {
  const name=kind==='machine_group'?'设备组':'班次档';
  await page.getByRole('button',{name:action==='create'?'新增'+name:(action==='delete'?'删除 ':'编辑 ')+(kind==='machine_group'?'G-':'S-')+'002',exact:true}).click();
  await page.getByRole('dialog',{name:({create:'新增',update:'编辑',delete:'删除'})[action]+name,exact:true}).waitFor();
}
async function save() {await page.getByRole('button',{name:'保存',exact:true}).click();}
async function lastInput(count=1) {
  await page.waitForFunction(count=>fixture.calls.length===count,count);
  return page.evaluate(()=>fixture.calls[fixture.calls.length-1].body.input);
}
async function screenshot(name) {
  await page.evaluate(()=>document.fonts.ready);
  const geometry=await page.evaluate(()=>{
    const dialog=document.querySelector('[role="dialog"]'),r=dialog.getBoundingClientRect();
    return {viewport:[innerWidth,innerHeight],scroll:document.documentElement.scrollWidth,dialog:{left:r.left,right:r.right,top:r.top,bottom:r.bottom},
      clipped:Array.from(dialog.querySelectorAll('button,.field>label,th')).filter(el=>el.clientWidth&&el.scrollWidth>el.clientWidth+1).map(el=>el.textContent),
      outside:Array.from(dialog.querySelectorAll('button,input,select,table')).filter(el=>{const b=el.getBoundingClientRect();return b.width&&(b.left<r.left||b.right>r.right);}).map(el=>el.tagName+':'+(el.getAttribute('aria-label')||el.textContent).slice(0,50)),
      dialogs:document.querySelectorAll('[role="dialog"]').length};
  });
  assert(geometry.scroll<=geometry.viewport[0]+1);assert(geometry.dialog.left>=0&&geometry.dialog.right<=geometry.viewport[0]+1&&geometry.dialog.top>=0&&geometry.dialog.bottom<=geometry.viewport[1]+1);
  assert.equal(geometry.dialogs,1);assert.deepEqual(geometry.clipped,[]);assert.deepEqual(geometry.outside,[]);
  const file=variant+'-'+name+'.png';await page.screenshot({path:path.join(output,file)});return {screenshot:file,geometry};
}
async function run(name,fn) {
  try {await fn();result.cases.push({variant,name,passed:true});}
  catch(error) {result.cases.push({variant,name,passed:false,message:error.message});await page.screenshot({path:path.join(output,variant+'-'+name+'-failure.png')});throw error;}
}
async function cases() {
  await run('model-complete-cycle-and-precise-patches',async()=>{
    const value=await page.evaluate(()=>{
      const M=APSResourceCatalogModel, original=record('shift_profile',2), draft=M.draft(original), checks={};
      draft.label='仅改名称';checks.patch=M.input('shift_profile',draft,original);
      const full=M.draft(null);Object.assign(full,{business_code:'FULL',label:'完整366天',status:'inactive',anchor_date:'2024-02-29',cycle_days:'366'});
      full.pattern=Array.from({length:366},(_,day_offset)=>({day_offset,is_rest:true,shift_start:'00:00',shift_end:'00:00'}));
      checks.full=M.input('shift_profile',full,null);full.anchor_date='2026-02-29';
      try{M.input('shift_profile',full,null);checks.invalidDate=false;}catch(error){checks.invalidDate=true;}
      const wrap=M.draft(original);wrap.cycle_days='2';wrap.pattern=[{day_offset:0,is_rest:false,shift_start:'05:00',shift_end:'08:00'},{day_offset:1,is_rest:false,shift_start:'22:00',shift_end:'06:00'}];
      try{M.input('shift_profile',wrap,original);checks.wrapRejected=false;}catch(error){checks.wrapRejected=error.fields.some(row=>row.path==='pattern.1');}
      for(const input of ['0','367','1.5','-1','NaN']){try{M.cycle(input);checks[input]=false;}catch(error){checks[input]=true;}}
      return checks;
    });
    assert.deepEqual(value.patch,{label:'仅改名称'});assert.equal(value.full.fields.pattern.length,366);assert.equal(value.full.fields.pattern[365].day_offset,365);
    assert.equal(value.full.fields.anchor_date,'2024-02-29');assert(value.invalidDate&&value.wrapRejected);for(const input of ['0','367','1.5','-1','NaN'])assert(value[input]);
  });
  await run('list-pagination-search-protection',async()=>{
    await mount({kind:'machine_group'});
    assert(await page.getByRole('button',{name:'删除 G-001',exact:true}).isDisabled());
    await page.getByRole('button',{name:'目录下一页',exact:true}).click();await page.getByRole('button',{name:'编辑 G-023',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>fixture.reads[fixture.reads.length-1].scope.snapshot_ref),'fixture-snapshot');
    await page.getByRole('searchbox',{name:'搜索目录编号或名称'}).fill('G-002');await page.getByRole('button',{name:'搜索目录',exact:true}).click();
    await page.getByRole('button',{name:'编辑 G-002',exact:true}).waitFor();assert.equal(await page.locator('.rc-list tbody tr').count(),1);
    assert.equal(await page.evaluate(()=>fixture.reads[fixture.reads.length-1].scope.page),1);
    assert.equal(await page.evaluate(()=>fixture.reads[fixture.reads.length-1].scope.snapshot_ref),undefined);
    result.cases.push({variant,name:'catalog-list-visual',...await screenshot('list')});
  });
  await run('cancel-no-write-and-group-create',async()=>{
    await mount({kind:'machine_group'});await open('machine_group','create');await save();assert.equal(await page.evaluate(()=>fixture.calls.length),0);
    await page.getByLabel('编号',{exact:true}).fill('GROUP-NEW');await page.getByLabel('名称',{exact:true}).fill('独立设备组');await page.getByLabel('状态',{exact:true}).selectOption('active');
    await page.getByRole('button',{name:'返回目录',exact:true}).click();assert(await page.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).isVisible());
    await page.getByRole('button',{name:'留在当前页面',exact:true}).click();assert.equal(await page.getByLabel('名称',{exact:true}).inputValue(),'独立设备组');
    await page.getByLabel('备注',{exact:true}).fill('真实独立目录');result.cases.push({variant,name:'group-form-visual',...await screenshot('group')});
    await save();assert.deepEqual(await lastInput(),{business_code:'GROUP-NEW',label:'独立设备组',fields:{status:'active',remark:'真实独立目录'}});
    assert.equal(await page.evaluate(()=>fixture.events.length),0);await page.getByRole('button',{name:'完成并返回',exact:true}).click();
    assert.equal(await page.evaluate(()=>fixture.events.filter(row=>row.name==='commit').length),1);
    assert.equal(await page.evaluate(()=>sessionStorage.getItem('aps_workbench_resource_pending_v1_catalog')),null);
  });
  await run('discard-is-read-only',async()=>{
    await mount({kind:'machine_group'});await open('machine_group');await page.getByLabel('名称',{exact:true}).fill('未保存草稿');
    for(let i=0;i<12;i++){await page.keyboard.press('Tab');assert(await page.evaluate(()=>document.querySelector('[role="dialog"]').contains(document.activeElement)));}
    await page.keyboard.press('Escape');await page.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();
    assert.equal(await page.evaluate(()=>fixture.calls.length),0);assert.deepEqual(await page.evaluate(()=>fixture.events),[{name:'close'}]);
  });
  await run('group-update-preserves-hidden-and-delete',async()=>{
    await mount({kind:'machine_group'});await open('machine_group');assert(await page.getByLabel('编号',{exact:true}).getAttribute('readonly')!==null);
    await page.getByLabel('名称',{exact:true}).fill('只改名称');await save();assert.deepEqual(await lastInput(),{label:'只改名称'});
    await page.getByRole('button',{name:'继续维护',exact:true}).click();await open('machine_group','delete');await page.getByRole('button',{name:'确认删除',exact:true}).click();
    assert.deepEqual(await lastInput(2),{});await page.getByRole('button',{name:'继续维护',exact:true}).click();
    await page.getByRole('button',{name:'编辑 G-003',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'编辑 G-002',exact:true}).count(),0);
  });
  await run('server-delete-conflict',async()=>{
    await mount({kind:'machine_group',reject:true});await open('machine_group','delete');await page.getByRole('button',{name:'确认删除',exact:true}).click();
    await page.getByText('目录仍被引用，不能删除。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.events.length),0);
    assert.equal(await page.evaluate(()=>fixture.rows.length),23);
  });
  await run('shift-full-pattern-and-no-guessed-production',async()=>{
    await mount({kind:'shift_profile'});await open('shift_profile','create');
    for(const label of ['周期起始日期','轮换天数'])assert.equal(await page.getByLabel(label,{exact:true}).inputValue(),'');
    await page.getByLabel('编号',{exact:true}).fill('SHIFT-NEW');await page.getByLabel('名称',{exact:true}).fill('跨夜轮班');await page.getByLabel('状态',{exact:true}).selectOption('active');
    await page.getByLabel('周期起始日期',{exact:true}).fill('2026-09-09');await page.getByLabel('轮换天数',{exact:true}).fill('2');await save();assert.equal(await page.evaluate(()=>fixture.calls.length),0);
    await page.getByRole('button',{name:'生成逐日规则',exact:true}).click();
    assert.equal(await page.getByLabel('第 1 天工作安排',{exact:true}).inputValue(),'');assert.equal(await page.getByLabel('第 1 天开始',{exact:true}).inputValue(),'');
    await page.getByLabel('第 1 天工作安排',{exact:true}).selectOption('work');await page.getByLabel('第 1 天开始',{exact:true}).fill('22:00');await page.getByLabel('第 1 天结束',{exact:true}).fill('06:00');
    await page.getByLabel('第 2 天工作安排',{exact:true}).selectOption('rest');assert(await page.getByLabel('第 2 天开始',{exact:true}).isDisabled());
    assert(await page.getByRole('cell',{name:'次日结束',exact:true}).isVisible());result.cases.push({variant,name:'shift-pattern-visual',...await screenshot('shift')});
    await save();assert.deepEqual(await lastInput(),{business_code:'SHIFT-NEW',label:'跨夜轮班',fields:{status:'active',anchor_date:'2026-09-09',cycle_days:2,pattern:[
      {day_offset:0,is_rest:false,shift_start:'22:00',shift_end:'06:00'},{day_offset:1,is_rest:true,shift_start:'00:00',shift_end:'00:00'}]}});
  });
  await run('shrink-confirm-and-append-preserve',async()=>{
    await mount({kind:'shift_profile'});await open('shift_profile');await page.getByLabel('轮换天数',{exact:true}).fill('2');await page.getByRole('button',{name:'调整逐日规则',exact:true}).click();
    assert.equal(await page.locator('.rc-pattern-table tbody tr').count(),3);await page.getByRole('button',{name:'保留原周期',exact:true}).click();assert.equal(await page.getByLabel('轮换天数',{exact:true}).inputValue(),'3');
    await page.getByLabel('轮换天数',{exact:true}).fill('2');await page.getByRole('button',{name:'调整逐日规则',exact:true}).click();await page.getByRole('button',{name:'确认移除末尾 1 天',exact:true}).click();
    assert.equal(await page.locator('.rc-pattern-table tbody tr').count(),2);assert.equal(await page.getByLabel('第 1 天开始',{exact:true}).inputValue(),'22:00');
    await page.getByLabel('轮换天数',{exact:true}).fill('4');await page.getByRole('button',{name:'调整逐日规则',exact:true}).click();assert.equal(await page.locator('.rc-pattern-table tbody tr').count(),4);
    assert.equal(await page.getByLabel('第 3 天工作安排',{exact:true}).inputValue(),'');assert.equal(await page.getByLabel('第 3 天开始',{exact:true}).inputValue(),'');
    await save();assert.equal(await page.evaluate(()=>fixture.calls.length),0);
  });
  await run('cyclic-neighbor-overlap-and-rest-toggle',async()=>{
    await mount({kind:'shift_profile'});await open('shift_profile');await page.getByLabel('第 2 天工作安排',{exact:true}).selectOption('work');
    await page.getByLabel('第 2 天开始',{exact:true}).fill('05:00');await page.getByLabel('第 2 天结束',{exact:true}).fill('10:00');await save();assert.equal(await page.evaluate(()=>fixture.calls.length),0);
    assert(await page.getByText('第 1 天：跨夜结束与下一轮换日开始重叠。',{exact:true}).isVisible());
    await page.getByLabel('第 2 天工作安排',{exact:true}).selectOption('rest');await page.getByLabel('第 2 天工作安排',{exact:true}).selectOption('work');
    assert.equal(await page.getByLabel('第 2 天开始',{exact:true}).inputValue(),'05:00');await page.getByLabel('第 2 天开始',{exact:true}).fill('06:00');await save();
    const input=await lastInput();assert.equal(input.fields.pattern[1].shift_start,'06:00');assert(!('hidden_legacy' in input.fields));
  });
  await run('stale-retains-draft-review-then-patch',async()=>{
    await mount({kind:'machine_group',stale:true});await open('machine_group');await page.getByLabel('名称',{exact:true}).fill('待保存名称');await save();await lastInput();
    await page.getByRole('alert').getByText('资料已变化，请重新读取并核对。',{exact:true}).waitFor();assert(await page.getByRole('button',{name:/^保存/}).isDisabled());
    await page.getByRole('button',{name:'重新读取最新资料',exact:true}).click();await page.getByRole('button',{name:'已核对，继续编辑',exact:true}).waitFor();
    assert.equal(await page.getByLabel('名称',{exact:true}).inputValue(),'待保存名称');assert(await page.getByText('G-002 · 服务器新名称',{exact:true}).isVisible());
    result.cases.push({variant,name:'stale-review-visual',...await screenshot('review')});await page.getByRole('button',{name:'已核对，继续编辑',exact:true}).click();
    await save();assert.deepEqual(await lastInput(2),{label:'待保存名称'});
    assert.equal(await page.evaluate(()=>fixture.calls[1].body.write_token),'reviewed-token');assert.notEqual(await page.evaluate(()=>fixture.calls[0].body.request_key),await page.evaluate(()=>fixture.calls[1].body.request_key));
  });
  await run('unknown-key-survives-reload-without-resubmit',async()=>{
    await mount({kind:'machine_group',pending:true});await page.evaluate(()=>sessionStorage.setItem('aps_workbench_resource_pending_v1','parent-intent-preserved'));
    await open('machine_group');await page.getByLabel('名称',{exact:true}).fill('不重复提交');await save();await lastInput();
    await page.getByRole('button',{name:'查询原请求回执',exact:true}).waitFor();const key=await page.evaluate(()=>fixture.calls[0].body.request_key);
    const persisted=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('aps_workbench_resource_pending_v1_catalog')));
    assert.equal(persisted.request_key,key);assert(!('input' in persisted));assert(!('write_token' in persisted));
    await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>fixture.events.length),0);
    assert(await page.getByRole('button',{name:/^保存/}).isDisabled());await page.reload();await page.getByRole('button',{name:'查询原请求回执',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>fixture.calls.length),1);assert((await page.evaluate(()=>fixture.lookups)).every(value=>value===key));
    await page.evaluate(()=>{fixture.confirm=true;});await page.getByRole('button',{name:'查询原请求回执',exact:true}).click();await page.getByRole('button',{name:'完成并返回',exact:true}).waitFor();
    await page.getByRole('button',{name:'完成并返回',exact:true}).click();assert.equal(await page.evaluate(()=>fixture.calls.length),1);assert.equal(await page.evaluate(()=>fixture.events[0].name),'commit');
    assert.equal(await page.evaluate(()=>sessionStorage.getItem('aps_workbench_resource_pending_v1_catalog')),null);
    assert.equal(await page.evaluate(()=>sessionStorage.getItem('aps_workbench_resource_pending_v1')),'parent-intent-preserved');
  });
  await run('366-day-full-grid-and-bounds',async()=>{
    await mount({kind:'shift_profile'});await open('shift_profile','create');await page.getByLabel('轮换天数',{exact:true}).fill('367');await page.getByRole('button',{name:'生成逐日规则',exact:true}).click();
    assert.equal(await page.locator('.rc-pattern-table tbody tr').count(),0);await page.getByLabel('轮换天数',{exact:true}).fill('366');
    const start=Date.now();await page.getByRole('button',{name:'生成逐日规则',exact:true}).click();await page.getByLabel('第 366 天工作安排',{exact:true}).waitFor();
    assert.equal(await page.locator('.rc-pattern-table tbody tr').count(),366);result.cases.push({variant,name:'366-day-grid-timing',elapsed_ms:Date.now()-start});
    await page.getByLabel('第 366 天工作安排',{exact:true}).selectOption('rest');await page.getByLabel('第 366 天工作安排',{exact:true}).scrollIntoViewIfNeeded();
    result.cases.push({variant,name:'366-day-visual',...await screenshot('366-days')});await save();assert.equal(await page.evaluate(()=>fixture.calls.length),0);
  });
  await run('demo-never-writes-focus-single-modal',async()=>{
    await mount({kind:'machine_group',source:'demo'});assert(await page.getByRole('button',{name:/^新增设备组/}).isDisabled());assert(await page.getByRole('button',{name:'编辑 G-002',exact:true}).isDisabled());
    for(let i=0;i<12;i++){await page.keyboard.press('Tab');assert(await page.evaluate(()=>document.querySelector('[role="dialog"]').contains(document.activeElement)));}
    assert.equal(await page.getByRole('dialog').count(),1);assert.equal(await page.evaluate(()=>fixture.calls.length),0);
  });
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
  try {
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    assert(browser.version().startsWith('109.'),'Actual Chromium 109 required');result.browser=browser.version();const origin='http://127.0.0.1:'+server.address().port;
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark']) {
      const context=await browser.newContext({viewport});await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);
      page=await context.newPage();variant=viewport.width+'x'+viewport.height+'-'+theme;
      page.on('pageerror',error=>result.errors.push(error.message));page.on('console',message=>{if(message.type()==='error')result.errors.push(message.text());});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin);await cases();await context.close();
    }
    assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);
  } finally {
    if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'catalog-result.json'),JSON.stringify(result,null,2)+'\n');
  }
  console.log(JSON.stringify({output,browser:result.browser,cases:result.cases.length,errors:result.errors,external:result.external,scope:result.scope}));
})().catch(error=>{console.error(error);process.exitCode=1;});
