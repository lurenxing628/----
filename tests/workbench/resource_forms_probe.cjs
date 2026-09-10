/* Isolated component fixtures, including simulated production envelopes. No database or production writes. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const files = ['resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'ResourceTableFilterModel.js',
  'ResourceTableFilter.jsx', 'ResourceTableHeader.jsx', 'ResourceDetailRelations.jsx', 'ResourceForms.jsx', 'ResourceTables.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const assets = new Map(manifest.files.map(item => [item.path, item]));
const fixtureCode = `
window.fixture = {calls:[],choices:[],serial:0};
function ref(n) { return n.toString(16).padStart(48,'0'); }
function wc(token) { return {write_token:token,capabilities:Object.fromEntries(['material','op_type','machine','operator','supplier'].flatMap(kind=>['create','update','delete'].map(action=>[kind+'.'+action,true]))),blocked_reasons:[]}; }
function envelope(data, source='demo') { return {ok:true,schema_version:1,data,meta:{source,time_basis:'factory_local',snapshot_ref:'choice-snapshot',request_ref:'fixture-request',as_of:'2026-09-09T08:00:00'},warnings:[]}; }
function entity(kind, patch={}) {
  const common={ref:ref(1000),business_code:'R-001',label:'当前名称',status:'active',fields:{remark:'旧备注保留',hidden_legacy:'raw-unknown'},relationships:{counts:{machines:99,skills:88}},issues:[],write_context:wc('original-token')};
  if(kind==='material') common.fields={...common.fields,spec:'原规格',unit:'kg',stock_qty:null};
  if(kind==='op_type') {common.status=null;common.fields={...common.fields,category:'internal',default_merge_mode:'legacy-policy'};}
  if(kind==='machine') {common.fields.category='旧设备分类';common.relationships={...common.relationships,op_type_ref:ref(1),op_type:{ref:ref(1),label:'自制 1'},group_ref:ref(65),group:{ref:ref(65),label:'设备组 65'}};}
  if(kind==='operator') {common.status='unknown';common.fields.legacy_status='inactive';common.relationships={...common.relationships,skill_refs:[ref(65)],skills:[{ref:ref(65),label:'自制 65'}],skills_declared:true,shift_profile_ref:ref(70),shift_profile:{ref:ref(70),label:'班次 70'},machine_authorization_count:2};}
  if(kind==='supplier') {common.status='unknown';common.fields={...common.fields,default_days:3,legacy_status:'inactive'};common.relationships={...common.relationships,op_type_refs:[ref(1),ref(65)],op_types:[{ref:ref(1),label:'外协 1',legacy:true},{ref:ref(65),label:'外协 65',explicit:true}]};}
  return {...common,...patch,fields:{...common.fields,...patch.fields},relationships:{...common.relationships,...patch.relationships}};
}
const receipt = () => ({ok:true,result:'unchanged',receipt_ref:'fixture-only-receipt',data:{entity_ref:ref(1000)},warnings:[]});
const rejected = () => ({ok:false,committed:false,error:{code:'stale_context',message:'资料已变化，请重新读取并核对。',fields:[]}});
let renderRoot;
function Harness({spec}) {
  const kind=spec.kind || 'material', original=spec.create ? null : entity(kind,spec.patch);
  const [context,setContext]=React.useState(wc('original-token')), [review,setReview]=React.useState(null);
  const adapter=React.useMemo(()=>({
    command:async(kind,action,ref,body)=>{fixture.calls.push({kind,action,ref,body});if(spec.behavior==='stale'&&fixture.calls.length===1)return rejected();if(spec.behavior==='pending')return {ok:false,error:{message:'连接中断，提交结果未知。'}};return receipt();},
    lookup:async()=>fixture.confirmReceipt ? receipt() : {state:'not_recorded'},
    choices:async(kind,scope)=>{fixture.choices.push({kind,scope});if(spec.choiceStale&&scope.page===2&&!fixture.choiceRetried)throw rejected();
      const title=kind==='op_type' ? scope.category==='external' ? '外协' : '自制' : kind==='machine_group' ? '设备组' : '班次';
      const all=Array.from({length:75},(_,i)=>({ref:ref(i+1),business_code:'C-'+(i+1),label:title+' '+(i+1),status:kind==='op_type'?null:i===73?'inactive':'active',fields:{category:scope.category},relationships:{},issues:[],write_context:null}));
      const rows=all.filter(row=>!scope.query||row.label.includes(scope.query));return envelope({entities:rows.slice((scope.page-1)*scope.size,scope.page*scope.size),page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.ceil(rows.length/scope.size),sort:[]}});}
  }),[]);
  const command=APSResourceSession.useCommand(adapter);
  const source=spec.source || 'production';
  const props={adapter,kind,action:spec.create?'create':'update',entity:original,category:spec.category,writeContext:context,source,command,onClose:()=>{fixture.closed=true;},
    onReloadContext:()=>setReview(envelope(entity(kind,{label:'服务器当前名称',fields:{stock_qty:17,remark:'active'}}),'production')),
    contextReview:review,onAcceptContext:()=>{setContext(wc('reviewed-token'));setReview(null);},refreshState:{}};
  if(spec.detail)return React.createElement(ResourceForms.Detail,{kind,result:envelope(original),onClose:()=>{},onEdit:()=>{},onDelete:()=>{}});
  if(spec.table)return React.createElement(ResourceTables,{kind,category:spec.category,entities:spec.empty?[]:[original],source,selected:[],onSelect:()=>{},onOpen:()=>{fixture.opened=true;},onEdit:()=>{fixture.edited=true;},onDelete:()=>{fixture.deleted=true;}});
  return React.createElement(ResourceForms,props);
}
window.mountFixture = spec => {
  fixture.calls=[];fixture.choices=[];fixture.confirmReceipt=false;fixture.choiceRetried=false;
  if(renderRoot)renderRoot.unmount();renderRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
  renderRoot.render(React.createElement(Harness,{spec,key:++fixture.serial}));
};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' +
  manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><main class="plana" style="padding:24px"><p>组件测试数据 · 无生产写入</p><div id="fixture-root"></div></main>' +
  manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-')).map(file => '<script src="/static/' + file + '"></script>').join('') +
  Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixtureCode + '</script></body></html>';
const server = http.createServer((req,res) => {
  const name = new URL(req.url,'http://fixture').pathname;
  if(name==='/') {res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
  if(scripts.has(name)) {res.setHeader('Content-Type','application/javascript');res.end(scripts.get(name));return;}
  const asset = assets.get(name.slice('/static/'.length));
  if(!name.startsWith('/static/') || !asset) {res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',asset.mime);res.end(fs.readFileSync(path.join(root,'static',asset.path)));
});
const result={scope:'isolated-component-fixtures',data_source:'demo',simulates_production_envelopes:true,production_persistence_tested:false,
  compiled_sources:sources.map(item=>({path:item.path,sha256:crypto.createHash('sha256').update(item.code).digest('hex')})),cases:[],errors:[],external:[]};
let page, variant;
const ref = n => n.toString(16).padStart(48,'0');
async function mount(spec) {
  await page.evaluate(spec=>window.mountFixture(spec),spec);
  await page.locator(spec.table?'table':'[role="dialog"]').waitFor();
  if(['machine','operator','supplier'].includes(spec.kind) && !spec.detail && !spec.table) {
    await page.waitForFunction(()=>document.querySelectorAll('select option').length>20 || document.querySelectorAll('.fchip').length>20);
  }
}
async function save() {await page.getByRole('button',{name:'保存',exact:true}).click();}
async function lastInput(count=1) {
  await page.waitForFunction(count=>fixture.calls.length===count,count);
  return page.evaluate(()=>fixture.calls[fixture.calls.length-1].body.input);
}
async function shot(name) {
  await page.evaluate(()=>document.fonts.ready);
  const geometry=await page.evaluate(()=>{
    const dialog=document.querySelector('[role="dialog"]'), r=dialog&&dialog.getBoundingClientRect();
    return {viewport:[innerWidth,innerHeight],scrollWidth:document.documentElement.scrollWidth,dialog:r&&{left:r.left,right:r.right,top:r.top,bottom:r.bottom},
      clipped:Array.from(document.querySelectorAll('.modal button,.field>label,th')).filter(el=>el.scrollWidth>el.clientWidth+1).map(el=>el.textContent)};
  });
  assert(geometry.scrollWidth<=geometry.viewport[0]+1,'horizontal document overflow');
  if(geometry.dialog)assert(geometry.dialog.left>=0&&geometry.dialog.right<=geometry.viewport[0]+1&&geometry.dialog.top>=0&&geometry.dialog.bottom<=geometry.viewport[1]+1,'dialog framing');
  assert.deepEqual(geometry.clipped,[],'clipped button/field/table labels');
  const file=variant+'-'+name+'.png';await page.screenshot({path:path.join(output,file)});return {screenshot:file,geometry};
}
async function run(name,fn) {
  try {await fn();result.cases.push({variant,name,passed:true});}
  catch(error) {result.cases.push({variant,name,passed:false,message:error.message});await page.screenshot({path:path.join(output,variant+'-'+name+'-failure.png')});throw error;}
}
async function cases() {
  await run('self-made-columns',async()=>{
    await mount({kind:'op_type',table:true,category:'internal'});
    assert.deepEqual(await page.locator('th').allInnerTexts(),['','工种编号','名称','可用设备','可用人员','产能备注','操作']);
    assert.equal(await page.getByText('待读取',{exact:true}).count(),2);
    assert(!(await page.locator('tbody').innerText()).includes('99'));
    await mount({kind:'op_type',table:true,category:'internal',patch:{availability:{machines:3,operators:0,basis:'enabled_authorized_matching'}}});
    assert.deepEqual(await page.locator('tbody td.r').allTextContents(),['3','0']);
    assert(await page.getByTitle('启用且绑定此工种的设备；不代表当日日历空闲。',{exact:true}).isVisible());
    result.cases.push({variant,name:'self-made-visual',...await shot('self-made-table')});
    await mount({kind:'op_type',table:true,category:'internal',empty:true});
    assert.equal(await page.getByRole('columnheader').filter({has:page.locator('.wb-th-title').getByText('可用设备',{exact:true})}).count(),1);
  });
  await run('external-columns',async()=>{
    await mount({kind:'op_type',table:true,category:'external',patch:{fields:{category:'external',default_merge_mode:'merged'}}});
    assert.deepEqual(await page.locator('th').allInnerTexts(),['','工种编号','名称','默认周期策略','备注','操作']);
    assert(await page.getByRole('cell',{name:'合并设置',exact:true}).isVisible());
    result.cases.push({variant,name:'external-visual',...await shot('external-table')});
  });
  await run('resource-column-labels',async()=>{
    const headers={material:['','物料编号','名称','规格','库存','状态','操作'],machine:['','设备编号','名称','绑定工种','设备组','状态','操作'],
      operator:['','工号','姓名','技能工种','班次','状态','操作'],supplier:['','编号','供应商','可做外协工种','默认周期（天）','状态','操作']};
    for(const [kind,labels] of Object.entries(headers)) {
      await mount({kind,table:true});assert.deepEqual(await page.locator('th').allInnerTexts(),labels);
      assert(!((await page.locator('tbody').innerText()).includes(ref(65))),'opaque ref is not a display label');
    }
  });
  await run('internal-form-hidden-policy',async()=>{
    await mount({kind:'op_type'});
    assert.equal(await page.getByRole('dialog',{name:'编辑自制工种'}).count(),1);
    assert.equal(await page.getByLabel('默认周期策略',{exact:true}).count(),0);
    assert.equal(await page.getByLabel('归属',{exact:true}).count(),0);
    assert(await page.getByLabel('工种编号',{exact:true}).getAttribute('readonly')!==null);
    await page.getByLabel('产能备注',{exact:true}).fill('瓶颈工序，人员偏紧');
    result.cases.push({variant,name:'internal-form-visual',...await shot('internal-form')});
    await save();assert.deepEqual(await lastInput(),{fields:{remark:'瓶颈工序，人员偏紧'}});
  });
  await run('external-unknown-policy-and-null',async()=>{
    await mount({kind:'op_type',patch:{fields:{category:'external'}}});
    assert.equal(await page.getByLabel('默认周期策略',{exact:true}).inputValue(),'legacy-policy');
    await page.getByLabel('名称',{exact:false}).fill('外协新名称');await save();
    assert.deepEqual(await lastInput(),{label:'外协新名称'});
    await mount({kind:'op_type',patch:{fields:{category:'external',default_merge_mode:'merged'}}});
    await page.getByLabel('默认周期策略',{exact:true}).selectOption('');await save();
    assert.deepEqual(await lastInput(),{fields:{default_merge_mode:null}});
  });
  await run('new-op-types-preserve-category',async()=>{
    for(const category of ['internal','external']) {
      await mount({kind:'op_type',create:true,category});await save();
      assert.equal(await page.evaluate(()=>fixture.calls.length),0);
      assert.equal(await page.getByLabel('工种编号',{exact:false}).getAttribute('aria-invalid'),'true');
      await page.getByLabel('工种编号',{exact:false}).fill('OT-NEW');await page.getByLabel('名称',{exact:false}).fill('新增工种');
      if(category==='external')await page.getByLabel('默认周期策略',{exact:true}).selectOption('merged');
      await save();assert.deepEqual(await lastInput(),{business_code:'OT-NEW',label:'新增工种',fields:category==='internal'?{category}:{category,default_merge_mode:'merged'}});
    }
    await mount({kind:'op_type',patch:{fields:{category:null}}});
    await page.getByLabel('名称',{exact:false}).fill('只改旧工种名称');await save();assert.deepEqual(await lastInput(),{label:'只改旧工种名称'});
  });
  await run('material-current-unknown-and-clear',async()=>{
    await mount({kind:'material'});
    assert.equal(await page.getByLabel('库存数量',{exact:true}).inputValue(),'');
    assert.equal(await page.getByLabel('备注',{exact:true}).count(),0);
    await page.getByLabel('名称',{exact:false}).fill('材料新名称');
    await page.getByLabel('规格',{exact:true}).fill('');await page.getByLabel('单位',{exact:true}).fill('');
    result.cases.push({variant,name:'material-visual',...await shot('material-form')});
    await save();assert.deepEqual(await lastInput(),{label:'材料新名称',fields:{spec:null,unit:null}});
    await mount({kind:'material',patch:{fields:{stock_qty:4}}});
    await page.getByLabel('库存数量',{exact:true}).fill('');await save();
    assert.equal(await page.evaluate(()=>fixture.calls.length),0);
    assert(await page.getByLabel('库存数量',{exact:true}).getAttribute('aria-invalid')==='true');
  });
  await run('operator-paginated-real-refs',async()=>{
    await mount({kind:'operator'});
    assert.equal(await page.getByLabel('状态',{exact:false}).inputValue(),'unknown');
    assert(await page.getByText('原停用状态，原因未登记',{exact:true}).isVisible());
    assert(await page.getByRole('checkbox',{name:'自制 65',exact:false}).isChecked());
    await page.getByRole('button',{name:'技能工种下一页',exact:true}).click();
    await page.getByRole('checkbox',{name:'自制 55',exact:true}).waitFor();
    assert(await page.getByRole('checkbox',{name:'自制 65',exact:true}).isChecked());
    await page.getByRole('checkbox',{name:'自制 55',exact:true}).check();
    await page.getByLabel('班次',{exact:true}).selectOption('');
    result.cases.push({variant,name:'operator-visual',...await shot('operator-form')});
    await save();assert.deepEqual(await lastInput(),{relationships:{skill_refs:[ref(65),ref(55)],shift_profile_ref:null}});
    const requests=await page.evaluate(()=>fixture.choices);
    assert(requests.some(item=>item.kind==='op_type'&&item.scope.page===2&&item.scope.snapshot_ref==='choice-snapshot'));
    assert(requests.filter(item=>item.kind==='op_type').every(item=>item.scope.category==='internal'&&!('status' in item.scope)));
  });
  await run('operator-new-no-guessed-authorization',async()=>{
    await mount({kind:'operator',create:true});
    assert(await page.getByText('新人员尚无设备操作授权；登记工种技能不会自动增加授权。',{exact:true}).isVisible());
    assert.equal(await page.getByLabel('班次',{exact:true}).inputValue(),'');
    await page.getByLabel('工号',{exact:false}).fill('P-NEW');await page.getByLabel('姓名',{exact:false}).fill('新人员');
    await page.getByLabel('状态',{exact:false}).selectOption('active');await save();
    assert.deepEqual(await lastInput(),{business_code:'P-NEW',label:'新人员',fields:{status:'active'},relationships:{skill_refs:[]}});
  });
  await run('choice-stale-retains-selection',async()=>{
    await mount({kind:'operator',choiceStale:true});
    await page.getByLabel('姓名',{exact:false}).fill('选择失败时的草稿');
    await page.getByRole('button',{name:'技能工种下一页',exact:true}).click();
    await page.getByRole('button',{name:'重读选项',exact:true}).waitFor();
    assert(await page.getByRole('checkbox',{name:'自制 65',exact:false}).isChecked());
    assert.equal(await page.getByLabel('姓名',{exact:false}).inputValue(),'选择失败时的草稿');
    await page.evaluate(()=>{fixture.choiceRetried=true;});await page.getByRole('button',{name:'重读选项',exact:true}).click();
    await page.getByRole('checkbox',{name:'自制 1',exact:true}).waitFor();
    assert(await page.getByRole('checkbox',{name:'自制 65',exact:false}).isChecked());
  });
  await run('choice-search-preserves-off-page-refs',async()=>{
    await mount({kind:'operator'});
    await page.getByRole('button',{name:'查找技能工种',exact:true}).click();
    await page.getByRole('textbox',{name:'搜索技能工种',exact:true}).fill('自制 55');
    await page.getByRole('button',{name:'执行技能工种搜索',exact:true}).click();
    await page.getByRole('checkbox',{name:'自制 55',exact:true}).waitFor();
    assert(await page.getByRole('checkbox',{name:'自制 65',exact:false}).isChecked());
    await page.getByRole('checkbox',{name:'自制 55',exact:true}).check();
    await save();assert.deepEqual(await lastInput(),{relationships:{skill_refs:[ref(65),ref(55)]}});
    const request=await page.evaluate(()=>fixture.choices.find(item=>item.scope.query==='自制 55'));
    assert.equal(request.scope.page,1);assert(!('snapshot_ref' in request.scope));assert(!('status' in request.scope));
  });
  await run('machine-clear-and-catalog',async()=>{
    await mount({kind:'machine'});
    assert.equal(await page.getByLabel('设备组',{exact:true}).inputValue(),ref(65));
    await page.getByRole('button',{name:'设备组下一页',exact:true}).click();
    await page.waitForFunction(()=>Array.from(document.querySelectorAll('select option')).some(option=>option.textContent==='设备组 70'));
    assert(await page.getByLabel('设备组',{exact:true}).locator('option',{hasText:'设备组 74'}).isDisabled());
    await page.getByLabel('设备组',{exact:true}).selectOption(ref(70));
    await page.getByLabel('绑定工种',{exact:true}).selectOption('');await page.getByLabel('状态',{exact:false}).selectOption('maintain');
    result.cases.push({variant,name:'machine-visual',...await shot('machine-form')});
    await save();assert.deepEqual(await lastInput(),{fields:{status:'maintain'},relationships:{op_type_ref:null,group_ref:ref(70)}});
  });
  await run('supplier-many-unknown-and-clear',async()=>{
    await mount({kind:'supplier'});
    assert.equal(await page.getByLabel('默认周期（天）',{exact:false}).inputValue(),'3');
    assert.equal(await page.getByLabel('状态',{exact:false}).inputValue(),'unknown');
    await page.getByRole('checkbox',{name:'外协 1',exact:true}).uncheck();await page.getByRole('checkbox',{name:'外协 65',exact:false}).click();
    assert.equal(await page.getByRole('checkbox',{name:'外协 65',exact:false}).count(),0);
    result.cases.push({variant,name:'supplier-visual',...await shot('supplier-form')});
    await save();assert.deepEqual(await lastInput(),{relationships:{op_type_refs:[]}});
    await mount({kind:'supplier'});await page.getByLabel('默认周期（天）',{exact:false}).fill('0');await save();
    assert.equal(await page.evaluate(()=>fixture.calls.length),0);
    assert.equal(await page.getByLabel('默认周期（天）',{exact:false}).getAttribute('aria-invalid'),'true');
  });
  await run('explicit-status-not-guessed-reason',async()=>{
    for(const [kind,state] of [['operator','leave'],['supplier','pending_review'],['machine','inactive'],['material','inactive']]) {
      await mount({kind});await page.getByLabel('状态',{exact:false}).selectOption(state);await save();
      assert.deepEqual(await lastInput(),{fields:{status:state}});
    }
    await mount({kind:'supplier',patch:{fields:{default_days:null}}});
    await page.getByRole('textbox',{name:'供应商',exact:true}).fill('保留未知周期');await save();assert.deepEqual(await lastInput(),{label:'保留未知周期'});
  });
  await run('numeric-bad-input-is-not-omitted',async()=>{
    await mount({kind:'material'});
    const stock=page.getByLabel('库存数量',{exact:true});await stock.fill('1');await stock.press('e');await save();
    assert.equal(await page.evaluate(()=>fixture.calls.length),0);
    assert.equal(await stock.getAttribute('aria-invalid'),'true');
    await stock.fill('0');await save();assert.deepEqual(await lastInput(),{fields:{stock_qty:0}});
  });
  await run('stale-context-preserves-draft-and-labels',async()=>{
    await mount({kind:'material',behavior:'stale'});await page.getByLabel('名称',{exact:false}).fill('未提交的草稿');await save();
    await page.getByRole('alert').filter({hasText:'资料已变化'}).waitFor();
    assert.equal(await page.getByLabel('名称',{exact:false}).inputValue(),'未提交的草稿');
    await page.getByRole('button',{name:'重新读取最新资料',exact:true}).click();
    await page.getByRole('button',{name:'已核对，继续编辑',exact:true}).waitFor();
    assert(await page.getByText('服务器当前名称',{exact:false}).isVisible());
    assert.equal(await page.getByLabel('库存数量',{exact:true}).inputValue(),'');
    const review=await page.getByRole('status').filter({has:page.getByRole('button',{name:'已核对，继续编辑',exact:true})}).innerText();
    assert(review.includes('库存数量')&&review.includes('17')&&review.includes('active'));
    assert(!review.includes('stock_qty')&&!review.includes('hidden_legacy'));
    result.cases.push({variant,name:'stale-visual',...await shot('stale-review')});
    await page.getByRole('button',{name:'已核对，继续编辑',exact:true}).click();await save();
    assert.deepEqual(await lastInput(2),{label:'未提交的草稿'});
    const calls=await page.evaluate(()=>fixture.calls);assert.equal(calls[1].body.write_token,'reviewed-token');
    assert.notEqual(calls[0].body.request_key,calls[1].body.request_key);
  });
  await run('pending-not-success',async()=>{
    await mount({kind:'material',behavior:'pending'});await page.getByLabel('名称',{exact:false}).fill('待核实草稿');await save();
    await page.getByRole('button',{name:'查询原请求回执',exact:true}).waitFor();
    assert(await page.getByLabel('名称',{exact:false}).isDisabled());assert.equal(await page.evaluate(()=>fixture.calls.length),1);
    assert.equal(await page.getByText('服务器已确认提交。',{exact:true}).count(),0);
    await page.evaluate(()=>{fixture.confirmReceipt=true;});await page.getByRole('button',{name:'查询原请求回执',exact:true}).click();
    await page.getByText('服务器确认内容未变化。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.calls.length),1);
  });
  await run('demo-cannot-save',async()=>{
    await mount({kind:'material',source:'demo'});
    assert(await page.getByRole('button',{name:'保存：当前不是生产数据，不能保存。',exact:true}).isDisabled());
    assert.equal(await page.evaluate(()=>fixture.calls.length),0);
  });
  await run('detail-literal-values-and-policy-scope',async()=>{
    await mount({kind:'op_type',detail:true,patch:{fields:{remark:'active'}}});
    assert(await page.getByText('产能备注',{exact:true}).isVisible());assert(await page.getByText('active',{exact:true}).isVisible());
    assert.equal(await page.getByText('默认周期策略',{exact:true}).count(),0);
    await mount({kind:'supplier',detail:true});assert(await page.getByText('旧状态 / 原因未知',{exact:true}).isVisible());
    await mount({kind:'op_type',detail:true,patch:{fields:{category:'external',default_merge_mode:'toString',constructor:'hidden-field'}}});
    assert(await page.getByText('toString',{exact:true}).isVisible());assert.equal(await page.getByText('hidden-field',{exact:true}).count(),0);
    await mount({kind:'op_type',patch:{fields:{category:'constructor'}}});assert.equal(await page.getByRole('dialog',{name:'编辑工种',exact:true}).count(),1);
    await mount({kind:'machine',detail:true,patch:{fields:{category:'internal'}}});
    assert(await page.getByText('设备分类（只读）',{exact:true}).isVisible());assert(await page.getByText('internal',{exact:true}).isVisible());
  });
  await run('pure-input-hidden-fields-no-mutation',async()=>{
    const proof=await page.evaluate(()=>{
      const C=APSResourceContract,original=entity('op_type'),before=JSON.stringify(original),draft=C.draft('op_type',original);
      draft.business_code='CANNOT-CHANGE';draft.fields.default_merge_mode='merged';draft.label='New';
      const input=C.input('op_type',draft,original);
      const staff=entity('operator'),staffDraft=C.draft('operator',staff);staffDraft.fields.remark='hidden edit';staffDraft.fields.unknown='hidden';
      return {input,unchanged:JSON.stringify(original)===before,staff:C.input('operator',staffDraft,staff)};
    });
    assert.deepEqual(proof,{input:{label:'New'},unchanged:true,staff:{}});
  });
  await run('availability-contract-rejects-bad-facts',async()=>{
    const valid=await page.evaluate(()=>{
      const C=APSResourceContract,values=[undefined,{machines:0,operators:0,basis:'enabled_authorized_matching'},null,
        {machines:-1,operators:1,basis:'enabled_authorized_matching'},{machines:1,operators:'2',basis:'enabled_authorized_matching'},
        {machines:1,operators:2,basis:'reference_counts'}];
      return values.map(value=>{const row=entity('op_type');if(value!==undefined)row.availability=value;return C.entity(row);});
    });
    assert.deepEqual(valid,[true,true,false,false,false,false]);
    const queryRejected=await page.evaluate(()=>{
      try {APSResourceContract.query(envelope(entity('op_type',{availability:{machines:-1,operators:0,basis:'enabled_authorized_matching'}})),'entity');return false;}
      catch(error){return error.committed===false;}
    });assert(queryRejected);
  });
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
  try {
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    result.browser=browser.version();assert(result.browser.startsWith('109.'),'Actual Chromium 109 required');
    const origin='http://127.0.0.1:'+server.address().port;
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark']) {
      variant=viewport.width+'x'+viewport.height+'-'+theme;
      const context=await browser.newContext({viewport});
      await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);
      page=await context.newPage();page.setDefaultTimeout(10000);
      page.on('pageerror',error=>result.errors.push({variant,message:error.message}));
      page.on('console',message=>{if(message.type()==='error')result.errors.push({variant,message:message.text()});});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')&&!route.request().url().startsWith('data:')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin);await page.waitForFunction(()=>typeof window.mountFixture==='function');
      assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),theme);
      await cases();await context.close();
    }
    assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);
  } finally {
    if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));
    fs.writeFileSync(path.join(output,'forms-result.json'),JSON.stringify(result,null,2)+'\n');
  }
  console.log(JSON.stringify({output,browser:result.browser,checks:result.cases.filter(item=>item.passed).length,screenshots:result.cases.filter(item=>item.screenshot).length,scope:result.scope,production_persistence_tested:false}));
})().catch(error=>{console.error(error);process.exitCode=1;});
