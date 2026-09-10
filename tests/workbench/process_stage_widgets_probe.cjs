/* Current-source browser probes. Mock command/choice adapters, not database proof. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http');
const path = require('node:path'), crypto = require('node:crypto'), { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass a temporary artifact directory');
fs.mkdirSync(output, { recursive: true });
const files = ['resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'ResourceTableFilterModel.js',
  'ResourceTableFilter.jsx', 'ResourceTableHeader.jsx', 'ResourceDetailRelations.jsx', 'ResourceTables.jsx', 'ResourceForms.jsx',
  'ResourceMaterialContract.js', 'ResourceMaterialPreview.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js',
  'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx',
  'ProcessContract.js', 'ProcessActionContract.js', 'ProcessActionPreview.jsx', 'ProcessCollectionActions.jsx',
  'ProcessFileContract.js', 'ProcessFilePreview.jsx', 'ProcessFileActions.jsx', 'ProcessControls.jsx',
  'ProcessStageEditor.jsx', 'ProcessSourceEditor.jsx', 'ProcessHoursEditor.jsx', 'ProcessOpTypeCreate.jsx', 'ProcessRouteEntry.jsx', 'ProcessDetail.jsx', 'ProcessWorkspace.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(item => [item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const fixture = `
const ref=n=>n.toString(16).padStart(48,'0'), copy=value=>JSON.parse(JSON.stringify(value));
const stamp=(state='unconfirmed')=>({state,confirmed_at:state==='confirmed'?'2026-09-09T12:34:56':null,confirmed_by:null});
const caps={route_preview:true,stage_confirm:true,create:false,delete:false,import:false,export:false};
const wc=action=>({write_token:'TOKEN:'+action+':'+fixtureState.revision,capabilities:{['process.'+action]:true},blocked_reasons:[]});
const envelope=data=>({ok:true,schema_version:1,data,meta:{source:'production',time_basis:'factory_local',snapshot_ref:'s'+fixtureState.revision,request_ref:'fixture-request',as_of:'2026-09-09T12:00:00'},warnings:[]});
function record(spec={}) {
  const stage=spec.stage||'route', sourceDone=['hours','ready'].includes(stage), routeDone=stage!=='route';
  const operations=Array.from({length:spec.count||3},(_,i)=>({ref:ref(1000+i),sequence:(i+1)*5,label:i===1?'Polish':'Turn',source:i===1?'external':'internal',op_type_ref:ref(i===1?102:101),op_type_label:i===1?'Polish':'Turn',
    supplier_ref:i===1?ref(300):null,supplier_label:i===1?'Original supplier':null,external_group_ref:i===1?ref(400):null,setup_hours:i===1?null:0,unit_hours:i===1?null:1.25,external_days:i===1?2:null,external_days_source:i===1?'operation':null,status:'active',issues:[],
    confirmation:{source:stamp(sourceDone||spec.matched&&i===0?'confirmed':'unconfirmed'),hours:stamp(stage==='ready'?'confirmed':'unconfirmed')}}));
  if(spec.unknown){operations[2].label='Unknown';operations[2].op_type_ref=null;operations[2].op_type_label=null;}
  if(spec.zero)operations[0].unit_hours=0;
  if(spec.blank)operations[0].setup_hours=null;
  const part={ref:ref(1),business_code:'PART-001',label:'零件 A',status:null,fields:{route_raw:'5Turn10Polish15Turn',route_parsed:'yes',remark:'保留原零件备注'},relationships:{batch_count:7,operation_count:operations.length,internal_count:operations.length-1,external_count:1,unclassified_count:0},issues:[],write_context:null,
    workflow:{origin:stage==='route'?'legacy':'managed',stage,ready:stage==='ready',route:stamp(routeDone?'confirmed':'present'),source:stamp(sourceDone?'confirmed':routeDone?'unconfirmed':'locked'),hours:stamp(stage==='ready'?'confirmed':sourceDone?'unconfirmed':'locked')},operations,
    external_groups:[{ref:ref(400),start_sequence:10,end_sequence:10,merge_mode:'merged',total_days:3,supplier_ref:ref(300),supplier_label:'Original supplier',remark:'原周期规则备注 KEEP',issues:[]}],capabilities:{...caps}};
  return part;
}
function resource(n,label,category) {return {ref:ref(n),business_code:'R'+n,label,status:category?null:'active',fields:category?{category,default_merge_mode:null,remark:null}:{},relationships:{},issues:[],write_context:null};}
function listing(rows,scope,extra={}) {return envelope({entities:rows.slice((scope.page-1)*scope.size,scope.page*scope.size),page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.max(1,Math.ceil(rows.length/scope.size)),sort:Array.isArray(scope.sort)?copy(scope.sort):[{field:scope.sort||'business_code',direction:scope.direction||'asc'}]},...extra});}
function assertFixture(ok,message){if(!ok)throw APSResourceContract.failure('MOCK CONTRACT: '+message);}
function detail() {const d=copy(fixtureState.part);d.write_context=wc('hours_confirm');return envelope(d);}
function preview(partRef,body){const f=fixtureState;const operations=(body.mode==='rows'?body.rows:[{seq:5,op_type_name:'Turn'},{seq:10,op_type_name:'Polish'},{seq:15,op_type_name:'Turn'}]).map(row=>({sequence:row.seq,op_type_name:row.op_type_name,op_type_ref:ref(row.op_type_name==='Polish'?102:101),source_suggestion:row.op_type_name==='Polish'?'external':'internal',supplier_ref:null,supplier_label:null,external_days:null,basis:'真实工种目录现值的测试替身',issues:[]}));
  const affected=f.spec.affectRoute?copy(f.part.external_groups):[];const token=wc('route_confirm');f.tokens[token.write_token]={input:copy(body),affected:affected.map(row=>row.ref)};
  return envelope({part_ref:partRef,mode:body.mode,route_raw:body.route_raw||'',normalized_input:body.route_raw||'rows',can_confirm_route:true,operations,diagnostics:[],counts:{operations:operations.length,recognized:operations.length,unknown:0},baseline:{operation_count:f.part.operations.length,external_group_count:f.part.external_groups.length,has_published_template:true},changes:{added:[],removed:[],retained:[5,10,15],same_sequence_changed:[]},affected_groups:affected,write_context:token});}
function applyCommand(action,body){const f=fixtureState,p=f.part,input=body.input;
  if(action!=='hours_confirm') {const bound=f.tokens[body.write_token];assertFixture(!!bound,'preview token required');const sent=action==='route_confirm'?input.route:{operations:input.operations,discard_group_refs:[]};const expected=copy(bound.input);delete expected.snapshot_ref;assertFixture(JSON.stringify(sent)===JSON.stringify(expected),'token input mismatch');assertFixture(JSON.stringify(input.discard_group_refs.slice().sort())===JSON.stringify(bound.affected.slice().sort()),'affected groups exactset');p.external_groups=p.external_groups.filter(row=>!input.discard_group_refs.includes(row.ref));p.operations.forEach(row=>{if(input.discard_group_refs.includes(row.external_group_ref))row.external_group_ref=null;});}
  if(action==='route_confirm'){p.workflow.origin='managed';p.workflow.route=stamp('confirmed');p.workflow.source=stamp();p.workflow.hours=stamp('locked');p.workflow.stage='source';p.workflow.ready=false;p.fields.route_raw=input.route.route_raw||p.fields.route_raw;}
  else {const active=p.operations.filter(row=>row.status==='active');assertFixture(input.operations.length===active.length,'all active operations required');const refs=new Set(input.operations.map(row=>row.ref));assertFixture(active.every(row=>refs.has(row.ref)),'active exactset');
    const byRef=new Map(p.operations.map(row=>[row.ref,row]));input.operations.forEach(row=>{const op=byRef.get(row.ref);Object.assign(op,row);delete op.confirmed;op.confirmation[action==='source_confirm'?'source':'hours']=stamp('confirmed');});
    if(action==='source_confirm'){p.workflow.source=stamp('confirmed');p.workflow.hours=stamp();p.workflow.stage='hours';p.workflow.ready=false;}else{const groups=new Set(active.map(row=>row.external_group_ref));assertFixture(input.groups.length===p.external_groups.filter(row=>row.merge_mode==='merged'&&groups.has(row.ref)).length,'all active merged groups required');input.groups.forEach(row=>p.external_groups.find(item=>item.ref===row.ref).total_days=row.total_days);
      // This is the post-command projection DTO. A blank member delegates only to its valid merged group.
      active.filter(row=>row.source==='external').forEach(row=>{const group=p.external_groups.find(item=>item.ref===row.external_group_ref);
        const grouped=group&&group.merge_mode==='merged'&&group.total_days>0&&!group.issues.length
          &&active.filter(item=>item.external_group_ref===group.ref).every(item=>item.source==='external'&&item.sequence>=group.start_sequence&&item.sequence<=group.end_sequence);
        assertFixture(row.external_days!==null||grouped,'blank external cycle requires a valid merged group');
        row.external_days_source=row.external_days===null?'group':'operation';});
      p.workflow.hours=stamp('confirmed');p.workflow.stage='ready';p.workflow.ready=true;}}
  f.revision++;
  const receipt={ok:true,result:'committed',receipt_ref:'receipt-'+f.commands.length,data:{entity_ref:p.ref,business_code:p.business_code,stage:action.replace('_confirm','')},warnings:[]};f.receipts[body.request_key]=receipt;return receipt;
}
function makeAdapter(){const f=fixtureState;return {
  list:async(kind,scope)=>{f.reads.push({type:'list',scope:copy(scope)});const row=copy(f.part);delete row.operations;delete row.external_groups;const counts={total:1,route:0,source:0,hours:0,ready:0};counts[row.workflow.stage]=1;return listing([row],scope,{metrics:{counts},capabilities:caps,create_context:null});},
  detail:async(kind,id)=>{f.reads.push({type:'detail',ref:id});if(f.spec.failDetail)throw APSResourceContract.failure('MOCK detail unavailable');assertFixture(id===f.part.ref,'wrong detail part');const response=detail();if(f.spec.holdInitial&&f.reads.filter(row=>row.type==='detail').length===1)await new Promise(resolve=>f.releaseInitial=resolve);return response;},
  routePreview:async(id,body,signal)=>{f.reads.push({type:'routePreview',body:copy(body)});if(f.spec.holdPreview)await new Promise(resolve=>f.releasePreview=resolve);return preview(id,body);},
  stagePreview:async(id,action,input,snapshot,signal)=>{f.reads.push({type:'stagePreview',input:copy(input),snapshot});if(f.spec.rejectPreview)throw APSResourceContract.failure('MOCK stale preview');if(f.spec.holdPreview)await new Promise(resolve=>f.releasePreview=resolve);
    const oldByRef=new Map(f.part.operations.map(row=>[row.ref,row]));const affected=f.part.external_groups.filter(g=>input.operations.some(row=>{const old=oldByRef.get(row.ref);return old.external_group_ref===g.ref&&['source','op_type_ref','supplier_ref'].some(key=>old[key]!==row[key]);}));
    const token=wc(action);f.tokens[token.write_token]={input:copy(input),affected:affected.map(row=>row.ref)};return envelope({part_ref:id,action,affected_groups:copy(affected),write_context:token});},
  choices:async(kind,scope)=>{f.reads.push({type:'choices',kind,scope:copy(scope)});let rows=kind==='supplier'?[resource(300,'Original supplier'),resource(301,'Second supplier')]:[resource(101,'Turn','internal'),resource(102,'Polish','external'),...f.created];if(scope.category)rows=rows.filter(row=>row.fields.category===scope.category);if(scope.query)rows=rows.filter(row=>row.label.includes(scope.query));return listing(rows,scope);},
  command:async(kind,action,id,body)=>{f.commands.push({kind,action,ref:id,body:copy(body)});if(f.spec.reject){f.spec.reject=false;throw APSResourceContract.failure('MOCK stale snapshot');}if(f.spec.holdCommand)await new Promise(resolve=>f.releaseCommand=resolve);const receipt=applyCommand(action,body);if(f.part.operations.length<2000)sessionStorage.setItem('stage-server',JSON.stringify({part:f.part,receipts:f.receipts,revision:f.revision}));if(f.spec.failAfterSave)f.spec.failDetail=true;if(f.spec.pending)throw new Error('MOCK reply lost');const delivered=copy(receipt);if(f.spec.missingReceiptRef)delete delivered.data.entity_ref;if(f.spec.wrongReceiptRef)delivered.data.entity_ref=ref(999);if(f.spec.missingReceiptStage)delete delivered.data.stage;if(f.spec.wrongReceiptStage)delivered.data.stage='route';return delivered;},
  lookup:async key=>{f.lookups.push(key);return f.spec.pending&&!f.allowLookup?{state:'not_recorded'}:f.receipts[key]||{state:'not_recorded'};},
  readPending:()=>JSON.parse(sessionStorage.getItem('stage-pending')||'null'),savePending:intent=>sessionStorage.setItem('stage-pending',JSON.stringify(intent)),clearPending:()=>sessionStorage.removeItem('stage-pending')
};}
function resourceAdapter(){const f=fixtureState;return {list:async(kind,scope)=>listing(f.created,scope,{create_context:{write_token:'RESOURCE-CREATE',capabilities:{'op_type.create':true},blocked_reasons:[]}}),
  detail:async(kind,id)=>envelope(f.created.find(row=>row.ref===id)),choices:async(kind,scope)=>listing([],scope),
  command:async(kind,action,id,body)=>{f.resourceCommands.push({kind,action,ref:id,body:copy(body)});assertFixture(kind==='op_type'&&action==='create'&&body.write_token==='RESOURCE-CREATE','independent real create_context required');const row=resource(500+f.created.length,body.input.label,body.input.fields.category);f.created.push(row);f.revision++;return {ok:true,result:'committed',receipt_ref:'resource-receipt-'+f.created.length,data:{entity_ref:row.ref},warnings:[]};},
  readPending:()=>null,savePending:()=>{},clearPending:()=>{},lookup:async()=>({state:'not_recorded'})};}
let renderRoot;
function Harness(){const adapter=React.useMemo(()=>{const a=makeAdapter();a.resourceAdapter=resourceAdapter();return a;},[]);return React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),React.createElement('section',{className:'plana',style:{padding:16}},React.createElement(ProcessWorkspace,{adapter,onCommitted:r=>fixtureState.committed.push(r)})));}
window.mountFixture=(spec={},restore=false)=>{if(renderRoot)renderRoot.unmount();if(!restore){sessionStorage.removeItem('stage-pending');sessionStorage.removeItem('stage-server');}const stored=restore&&JSON.parse(sessionStorage.getItem('stage-server')||'null');window.fixtureState={spec,revision:stored?stored.revision:1,part:stored?stored.part:record(spec),receipts:stored?stored.receipts:{},tokens:{},commands:[],resourceCommands:[],reads:[],lookups:[],committed:[],created:[]};if(spec.recoverReadRace)sessionStorage.setItem('stage-pending',JSON.stringify({kind:'process',action:'source_confirm',ref:ref(1),request_key:'resource-'+ref(999),input:{}}));renderRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));renderRoot.render(React.createElement(Harness));};
if(sessionStorage.getItem('stage-pending'))mountFixture({pending:true},true);
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><div id="fixture-root"></div>' + staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {const name = new URL(req.url, 'http://fixture').pathname;if (name === '/') {res.setHeader('Content-Type', 'text/html;charset=utf-8');res.end(html);return;}if (scripts.has(name)) {res.setHeader('Content-Type', 'application/javascript');res.end(scripts.get(name));return;}const asset = assets.get(name.slice('/static/'.length));if (!name.startsWith('/static/') || !asset) {res.writeHead(404);res.end();return;}res.setHeader('Content-Type', asset.mime);res.end(asset.bytes);});
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const report = { scope: 'process-stage-component-mock', production_persistence_tested: false, compile: { target: compiled.target, global_build: false }, sources: sources.map(row => ({ path: row.path, sha256: sha(row.code) })),
  probes: [__filename, path.join(__dirname, 'test_process_stage_widgets.py')].map(file => ({ path: path.relative(root, file), sha256: sha(fs.readFileSync(file)) })),
  cases: [], screenshots: [], errors: [], external: [] };
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
const check = name => page.getByRole('checkbox', { name, exact: true });
async function mount(spec = {}) {await page.evaluate(spec => mountFixture(spec), spec);await button('查看 PART-001').waitFor();}
async function open(stage) {await button('查看 PART-001').click();await page.locator('.stepper').waitFor();if (stage) await page.getByRole('tab', { name: new RegExp(stage) }).click();}
async function lastCommand() {return page.evaluate(() => fixtureState.commands[fixtureState.commands.length - 1]);}
async function sourceCheck() {await check('确认本页已核对工序').check();await button('检查归属').click();await page.getByText(/当前归属已检查/).waitFor();}
async function caseOf(name, run) {try {await run();report.cases.push({ variant, name, passed: true });} catch (error) {report.cases.push({ variant, name, passed: false, error: error.message });await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') });fs.writeFileSync(path.join(output, variant + '-' + name + '-failure.html'), await page.content());throw error;}}
async function shot(name) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => Array.from(document.querySelectorAll('.modal-bg')).filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden').every(el => getComputedStyle(el).opacity === '1'));
  const geometry = await page.evaluate(() => {const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';const dialogs = [...document.querySelectorAll('[role=dialog]')].filter(visible);return { width: innerWidth, height: innerHeight, scroll: document.documentElement.scrollWidth,
    dialogs: dialogs.map(e => {const r = e.getBoundingClientRect();return { x:r.x,y:r.y,right:r.right,bottom:r.bottom };}),overflow: [...document.querySelectorAll('button')].filter(visible).filter(e => !e.closest('.card-scroll') && e.scrollWidth > e.clientWidth + 2).map(e => e.textContent) };});
  assert(geometry.scroll <= geometry.width + 1, 'document overflow');assert.equal(geometry.dialogs.length, 1);assert.deepEqual(geometry.overflow, []);
  geometry.dialogs.forEach(r => assert(r.x >= 0 && r.y >= 0 && r.right <= geometry.width + 1 && r.bottom <= geometry.height + 1));
  const file = variant + '-' + name + '.png';await page.screenshot({ path: path.join(output, file) });report.screenshots.push({ file, geometry });
}
async function cases() {
  await caseOf('route-source-hours-ready-receipts', async () => {
    await mount();await open();assert(await check('确认工序 5 归属').count() === 0, 'hidden stage controls excluded');
    await button('录入路线').click();await button('预检路线').click();await page.locator('[data-process-preview]').waitFor();await shot('route');await button('确认保存路线').click();
    await check('确认工序 5 归属').waitFor();assert(!(await check('确认工序 5 归属').isChecked()));assert(!(await check('确认工序 10 归属').isChecked()));
    await sourceCheck();await shot('source');await button('完成归属 · 解锁工时').click();await check('确认工序 5 工时').waitFor();assert(!(await check('确认工序 5 工时').isChecked()));
    await check('确认本页已核对工时').check();await shot('hours');await button('保存工时').click();await page.getByText('三阶段已确认 · 已就绪', { exact: true }).waitFor();await shot('ready');
    const state = await page.evaluate(() => ({ actions:fixtureState.commands.map(r=>r.action),committed:fixtureState.committed.length,part:fixtureState.part,pending:sessionStorage.getItem('stage-pending') }));
    assert.deepEqual(state.actions, ['route_confirm','source_confirm','hours_confirm']);assert.equal(state.committed, 3);assert.equal(state.pending, null);assert.equal(state.part.external_groups[0].remark, '原周期规则备注 KEEP');assert.equal(state.part.external_groups[0].merge_mode, 'merged');assert.equal(state.part.relationships.batch_count, 7);
    assert(!(await page.getByRole('dialog').innerText()).includes('确认人：'));assert((await page.getByRole('dialog').innerText()).includes('2026-09-09 12:34:56'));
    assert((await page.getByRole('dialog').locator('time[datetime="2026-09-09T12:34:56"]').count()) > 0, 'Keep the exact source timestamp in datetime');
    const last = await lastCommand();assert.equal(last.body.input.operations.length, 3);assert.deepEqual(last.body.input.groups, [{ ref:'190'.padStart(48,'0'),total_days:3 }]);
  });
  await caseOf('route-preflight-invalidation-and-group-ack', async () => {
    await mount({affectRoute:true});await open();await button('录入路线').click();await button('预检路线').click();await page.locator('[data-process-preview]').waitFor();assert(await page.getByRole('button',{name:/^确认保存路线/}).isDisabled());
    assert((await page.getByRole('table',{name:'受影响外协组'}).innerText()).includes('原周期规则备注 KEEP'));await check('解除外协组 10 至 10').check();
    await page.getByRole('textbox',{name:'路线文字',exact:true}).fill('5Turn10Polish15Turn ');assert.equal(await page.locator('[data-process-preview]').count(),0);assert(await page.getByRole('button',{name:/^确认保存路线/}).isDisabled());
    await button('预检路线').click();await check('解除外协组 10 至 10').waitFor();assert(!(await check('解除外协组 10 至 10').isChecked()));await check('解除外协组 10 至 10').check();await button('确认保存路线').click();await check('确认工序 5 归属').waitFor();assert.equal((await lastCommand()).body.input.discard_group_refs.length,1);
  });
  await caseOf('source-choice-single-picker-and-exact-ack', async () => {
    await mount({stage:'source',matched:true});await open();assert(await check('确认工序 5 归属').isChecked());assert(!(await check('确认工序 10 归属').isChecked()));
    await button('选择工序 10 供应商').click();await button('选用 Second supplier').click();assert(!(await check('确认工序 10 归属').isChecked()));await sourceCheck();
    assert(await page.getByRole('button',{name:/^完成归属/}).isDisabled());await check('解除外协组 10 至 10').check();await button('完成归属 · 解锁工时').click();await check('确认工序 5 工时').waitFor();
    const cmd=await lastCommand();assert(cmd.body.write_token.startsWith('TOKEN:source_confirm:'));assert.equal(cmd.body.input.discard_group_refs.length,1);assert.equal(cmd.body.input.operations[1].supplier_ref,'12d'.padStart(48,'0'));
  });
  await caseOf('draft-tab-close-and-latest-context-review', async () => {
    await mount({stage:'hours'});await open();const unit=page.getByRole('spinbutton',{name:'工序 5 单件工时',exact:true});await unit.fill('8.5');await page.getByRole('tab',{name:/工序归属/}).click();await page.getByRole('tab',{name:/工时定额/}).click();assert.equal(await unit.inputValue(),'8.5');
    await page.evaluate(()=>{fixtureState.part.operations[0].unit_hours=4;fixtureState.revision++;});await button('重读详情并保留草稿').click();await page.getByRole('table',{name:'最新资料差异'}).waitFor();assert.equal(await unit.inputValue(),'8.5');assert(await page.getByRole('button',{name:/^保存工时/}).isDisabled());
    assert((await page.getByRole('table',{name:'最新资料差异'}).innerText()).includes('4'));await button('已核对，采用最新范围并保留可匹配草稿').click();assert.equal(await unit.inputValue(),'8.5');
    await button('关闭详情').click();await button('继续编辑').click();assert.equal(await unit.inputValue(),'8.5');await button('关闭详情').click();await button('放弃草稿并关闭').click();assert.equal(await page.getByRole('dialog').count(),0);
  });
  await caseOf('hours-blank-zero-positive-and-merged-total', async () => {
    const times=await page.evaluate(()=>[null,'invalid-time','2026-09-09T13:21:16.397888Z','2026-09-09T15:00:00'].map(window.ProcessStageEditor.confirmationTime));
    assert.deepEqual(times,['未填写','时间格式待核对','2026-09-09 21:21:16','2026-09-09 15:00:00']);
    await mount({stage:'hours',blank:true,zero:true});await open();await check('确认本页已核对工时').check();await button('保存工时').click();await page.getByText(/空值不能按 0 保存/).waitFor();assert.equal(await page.evaluate(()=>fixtureState.commands.length),0);
    await page.getByRole('spinbutton',{name:'工序 5 换型工时',exact:true}).fill('0');await check('确认本页已核对工时').check();await button('保存工时').click();await page.getByText('单件工时为 0，需要明确勾选复核。',{exact:true}).waitFor();
    await page.getByRole('spinbutton',{name:'工序 10 外协周期',exact:true}).fill('0');await check('确认本页已核对工时').check();await check('已复核单件工时为0').check();await button('保存工时').click();await page.getByText('工序 10 外协周期必须填写大于 0 的有限数。',{exact:true}).waitFor();
    await page.getByRole('spinbutton',{name:'工序 10 外协周期',exact:true}).fill('2.5');await page.getByRole('spinbutton',{name:'外协组 10 至 10 总周期',exact:true}).fill('7');await check('确认本页已核对工时').check();await check('已复核单件工时为0').check();await button('保存工时').click();await page.getByText('三阶段已确认 · 已就绪',{exact:true}).waitFor();
    const cmd=await lastCommand();assert.equal(cmd.body.input.operations[0].unit_hours,0);assert.equal(cmd.body.input.operations[0].setup_hours,0);assert.equal(cmd.body.input.confirm_zero_unit_hours,true);assert.equal(cmd.body.input.groups[0].total_days,7);
  });
  await caseOf('pending-refresh-recovery-no-new-submit', async () => {
    await mount({stage:'source',pending:true});await open();await sourceCheck();await button('完成归属 · 解锁工时').click();await button('查询原请求回执').waitFor();assert(await button('关闭详情').isDisabled());assert(await page.getByRole('tab',{name:/工时定额/}).isDisabled());
    const key=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('stage-pending')).request_key);await page.reload();await button('查询原请求回执').waitFor();assert(await button('关闭详情').isDisabled());assert.equal(await page.evaluate(()=>fixtureState.commands.length),0);
    await page.evaluate(()=>fixtureState.allowLookup=true);await button('查询原请求回执').click();await check('确认工序 5 工时').waitFor();assert.equal(await page.evaluate(()=>fixtureState.commands.length),0);assert(await page.evaluate(key=>fixtureState.lookups.every(item=>item===key),key));assert.equal(await page.evaluate(()=>sessionStorage.getItem('stage-pending')),null);
  });
  await caseOf('merged-members-null-use-group-total', async () => {
    // An existing operation cycle remains editable; after saving NULL the DTO renders the exact group label instead.
    await mount({stage:'hours'});await open();const cycle=page.getByRole('spinbutton',{name:'工序 10 外协周期',exact:true});await cycle.fill('');assert.equal(await cycle.getAttribute('placeholder'),'未填写');
    await check('确认本页已核对工时').check();await button('保存工时').click();await page.getByText('三阶段已确认 · 已就绪',{exact:true}).waitFor();const cmd=await lastCommand();assert.equal(cmd.body.input.operations[1].external_days,null);assert.equal(cmd.body.input.groups[0].total_days,3);
    assert.equal(await page.evaluate(()=>fixtureState.part.operations[1].external_days_source),'group');
    await page.getByRole('tab',{name:/工时定额/}).click();assert.equal(await cycle.count(),0);
    assert.equal(await page.locator('[data-process-hours-editor] [data-process-cycle-group]').innerText(),'按外协组周期 · 10 至 10');
  });
  await caseOf('source-preview-edit-abort-and-source-category-binding', async () => {
    await mount({stage:'source',holdPreview:true});await open();await check('确认本页已核对工序').check();await button('检查归属').click();await page.waitForFunction(()=>!!fixtureState.releasePreview);
    await check('确认工序 5 归属').uncheck();await page.evaluate(()=>{fixtureState.spec.holdPreview=false;fixtureState.releasePreview();});assert.equal(await page.getByText(/当前归属已检查/).count(),0);
    const row=page.getByRole('table',{name:'工序归属明细'}).locator('tbody tr').first();await row.getByRole('button',{name:'外协',exact:true}).click();assert((await row.innerText()).includes('未绑定工种'));await button('选择工序 5 工种').click();await button('选用 Polish').waitFor();assert.equal(await button('选用 Turn').count(),0);await button('选用 Polish').click();
    assert.equal(await page.evaluate(()=>fixtureState.reads.filter(row=>row.type==='choices').length),1);assert.equal(await page.evaluate(()=>fixtureState.commands.length),0);
  });
  await caseOf('independent-op-type-create-keeps-source-draft', async () => {
    await mount({stage:'source',unknown:true});await open();await check('确认工序 5 归属').check();await button('待建工种').click();await page.getByRole('textbox',{name:'名称',exact:true}).waitFor();
    await page.getByRole('textbox',{name:'工种编号',exact:true}).fill('NEW-OP');await page.getByRole('textbox',{name:'名称',exact:true}).fill('New type');
    const category=page.getByRole('combobox',{name:'归属',exact:true});await category.selectOption('internal');await button('保存').click();await page.getByText('已重新读取最新数据。',{exact:true}).waitFor();await page.locator('.modal-f').getByRole('button',{name:'关闭',exact:true}).click();
    await page.getByText(/最新资料已读取，草稿未被替换/).waitFor();assert(await check('确认工序 5 归属').isChecked());assert.equal(await page.evaluate(()=>fixtureState.commands.length),0);assert.equal(await page.evaluate(()=>fixtureState.resourceCommands.length),1);assert.equal(await page.evaluate(()=>fixtureState.committed.length),1);
    await button('已核对，采用最新范围并保留可匹配草稿').click();await button('选择工序 15 工种').click();await button('选用 New type').click();await sourceCheck();await button('完成归属 · 解锁工时').click();await check('确认工序 5 工时').waitFor();assert.equal((await lastCommand()).body.input.operations[2].op_type_ref,'1f4'.padStart(48,'0'));
  });
  await caseOf('2000-10000-operations-paged-full-range-draft', async () => {
    for(const count of [2000,10000]) {const start=Date.now();await mount({stage:'ready',count});await open('工时定额');const table=page.getByRole('table',{name:'工时定额明细'});assert.equal(await table.locator('tbody tr').count(),50);assert.equal(await page.evaluate(()=>fixtureState.reads.filter(row=>row.type==='choices').length),0);
      await page.getByRole('spinbutton',{name:'工序 5 单件工时',exact:true}).fill('9');const editor=page.locator('[data-process-hours-editor]');await editor.getByRole('spinbutton',{name:'跳转页码',exact:true}).fill(String(count/50));await editor.getByRole('button',{name:'跳转',exact:true}).click();assert((await table.locator('tbody tr').last().innerText()).includes(String(count*5)));
      await editor.getByRole('spinbutton',{name:'跳转页码',exact:true}).fill('1');await editor.getByRole('button',{name:'跳转',exact:true}).click();assert.equal(await page.getByRole('spinbutton',{name:'工序 5 单件工时',exact:true}).inputValue(),'9');
      await check('确认本页已核对工时').check();await button('保存工时').click();await page.getByRole('table',{name:'已就绪工序汇总'}).waitFor();const cmd=await lastCommand();assert.equal(cmd.body.input.operations.length,count);assert.equal(cmd.body.input.operations[0].unit_hours,9);assert.equal(cmd.body.input.operations[count-1].unit_hours,1.25);
      await page.getByRole('tab',{name:/工序归属/}).click();await button('选择工序 5 工种').click();await button('选用 Turn').click();await sourceCheck();assert.equal(await page.evaluate(()=>fixtureState.reads.filter(row=>row.type==='stagePreview').pop().input.operations.length),count);assert.equal(await page.evaluate(()=>fixtureState.reads.filter(row=>row.type==='choices').length),1);
      report.cases.push({variant,name:'render-save-'+count,passed:true,elapsed_ms:Date.now()-start});}
  });
  await caseOf('sending-lock-and-rejected-source-recheck', async () => {
    await mount({stage:'source',holdCommand:true});await open();await sourceCheck();await button('完成归属 · 解锁工时').click();await page.waitForFunction(()=>!!fixtureState.releaseCommand);
    assert(await button('关闭详情').isDisabled());assert(await page.getByRole('tab',{name:/工艺路线/}).isDisabled());assert(await page.getByRole('button',{name:/^完成归属/}).isDisabled());await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),1);
    await page.evaluate(()=>fixtureState.releaseCommand());await check('确认工序 5 工时').waitFor();assert.equal(await page.evaluate(()=>fixtureState.commands.length),1);
    await mount({stage:'source',reject:true});await open();await sourceCheck();await button('完成归属 · 解锁工时').click();await page.getByText('MOCK stale snapshot',{exact:true}).waitFor();assert(await check('确认工序 5 归属').isChecked());assert(await page.getByRole('button',{name:/^完成归属/}).isDisabled());
    await button('重读详情并保留草稿').click();await button('已核对，采用最新范围并保留可匹配草稿').click();await sourceCheck();await button('完成归属 · 解锁工时').click();await check('确认工序 5 工时').waitFor();assert.equal(await page.evaluate(()=>fixtureState.commands.length),2);
  });
  await caseOf('route-receipt-reread-failure-no-repeat-write', async () => {
    await mount({failAfterSave:true});await open();await button('录入路线').click();await button('预检路线').click();await page.locator('[data-process-preview]').waitFor();await button('确认保存路线').click();await button('重新读取保存结果').waitFor();assert(await page.getByRole('button',{name:/^确认保存路线/}).isDisabled());
    await page.evaluate(()=>{fixtureState.spec.failDetail=false;fixtureState.spec.failAfterSave=false;});await button('重新读取保存结果').click();await check('确认工序 5 归属').waitFor();assert.equal(await page.evaluate(()=>fixtureState.commands.length),1);assert.equal(await page.evaluate(()=>fixtureState.committed.length),1);
  });
  await caseOf('late-initial-detail-cannot-overwrite-receipt-reread', async () => {
    await mount({stage:'source',pending:true,holdInitial:true,recoverReadRace:true});await page.waitForFunction(()=>!!fixtureState.releaseInitial);await button('查询原请求回执').waitFor();
    await page.evaluate(()=>{const f=fixtureState,key=JSON.parse(sessionStorage.getItem('stage-pending')).request_key;f.part.workflow.source=stamp('confirmed');f.part.workflow.hours=stamp();f.part.workflow.stage='hours';f.part.operations.forEach(row=>row.confirmation.source=stamp('confirmed'));f.revision++;f.allowLookup=true;f.receipts[key]={ok:true,result:'committed',receipt_ref:'recovered-receipt',data:{entity_ref:f.part.ref,business_code:f.part.business_code,stage:'source'},warnings:[]};});
    await button('查询原请求回执').click();await check('确认工序 5 工时').waitFor();await page.evaluate(()=>fixtureState.releaseInitial());await page.waitForFunction(()=>document.querySelector('.stepper .stp[aria-selected=true]').textContent.includes('工时定额'));
    assert(!(await check('确认工序 5 工时').isDisabled()));assert.equal(await page.evaluate(()=>fixtureState.commands.length),0);
  });
  await caseOf('active-exactset-orphan-groups-and-total-reconfirmation', async () => {
    await mount({stage:'source'});await page.evaluate(()=>{fixtureState.part.operations[2].status='deleted';fixtureState.part.relationships.operation_count=2;fixtureState.part.relationships.internal_count=1;fixtureState.part.external_groups.push({...copy(fixtureState.part.external_groups[0]),ref:ref(401),start_sequence:999,end_sequence:999,remark:'ORPHAN KEEP'});});await open();
    assert.equal(await check('确认工序 15 归属').count(),0);await sourceCheck();await button('完成归属 · 解锁工时').click();await check('确认工序 5 工时').waitFor();assert.equal((await lastCommand()).body.input.operations.length,2);
    assert.equal(await page.getByRole('spinbutton',{name:'外协组 999 至 999 总周期',exact:true}).count(),0);await check('确认本页已核对工时').check();await page.getByRole('spinbutton',{name:'外协组 10 至 10 总周期',exact:true}).fill('4');assert(!(await check('确认工序 10 工时').isChecked()));assert(await check('确认工序 5 工时').isChecked());
    await check('确认工序 10 工时').check();await button('保存工时').click();await page.getByRole('table',{name:'已就绪工序汇总'}).waitFor();assert.equal((await lastCommand()).body.input.groups.length,1);assert.equal(await page.evaluate(()=>fixtureState.part.external_groups[1].remark),'ORPHAN KEEP');
  });
  await caseOf('source-fieldwise-rebase-and-readable-review', async () => {
    await mount({stage:'hours'});await page.evaluate(()=>{fixtureState.created.push(resource(103,'New Polish','external'),resource(104,'Turn','internal'));fixtureState.part.external_groups.push({...copy(fixtureState.part.external_groups[0]),ref:ref(402),start_sequence:50,end_sequence:55,remark:'原组删除前备注'});});await open('工序归属');
    await button('选择工序 10 工种').click();await button('选用 New Polish').click();await check('确认工序 10 归属').check();
    await page.evaluate(()=>{const p=fixtureState.part;p.operations[0].op_type_ref=ref(104);p.operations[1].supplier_ref=ref(301);p.operations[2].source='external';p.operations[2].op_type_ref=ref(102);p.operations[2].op_type_label='Polish';p.operations[2].supplier_ref=ref(300);p.operations[2].supplier_label='Original supplier';p.operations[2].external_days=4;p.operations[2].external_days_source='operation';
      Object.assign(p.external_groups[0],{end_sequence:15,merge_mode:'separate',total_days:9,supplier_ref:ref(301),remark:'服务器新备注'});p.external_groups.pop();p.external_groups.push({...copy(p.external_groups[0]),ref:ref(401),start_sequence:20,end_sequence:30,remark:'新增组备注'});
      p.workflow.stage='ready';p.workflow.ready=true;p.workflow.hours=stamp('confirmed');p.operations.forEach(row=>row.confirmation.hours=stamp('confirmed'));p.workflow.route.confirmed_at='2026-09-09T15:00:00';p.relationships.internal_count=1;p.relationships.external_count=2;fixtureState.revision++;});
    await button('重读详情并保留草稿').click();const review=page.getByRole('table',{name:'最新资料差异'});await review.waitFor();const text=await review.innerText();
    assert(!/[0-9a-f]{48}/i.test(text),'Review must not expose opaque references');assert(!/op_type_ref|supplier_ref|merge_mode|confirmed_at|confirmed_by|external_group_ref|\{"/.test(text),'Review must not dump internal JSON/field names');
    for(const label of ['关联记录已更换','自制','外协','工序范围','周期策略','合并设置','分别设置','总周期（天）','供应商','服务器新备注','新增组备注','原组删除前备注','已移除','工时定额','已就绪','2026-09-09 15:00:00'])assert(text.includes(label),label);
    await review.locator('tbody tr').first().scrollIntoViewIfNeeded();await shot('source-review');await button('已核对，采用最新范围并保留可匹配草稿').click();const rows=page.getByRole('table',{name:'工序归属明细'}).locator('tbody tr');assert((await rows.nth(1).innerText()).includes('New Polish'));
    for(const seq of [5,10,15])assert(!(await check('确认工序 '+seq+' 归属').isChecked()),'Changed operations require fresh explicit confirmation');
    await sourceCheck();await check('解除外协组 10 至 15').check();await button('完成归属 · 解锁工时').click();await check('确认工序 5 工时').waitFor();const body=(await lastCommand()).body.input;
    assert.equal(body.operations[0].op_type_ref,'68'.padStart(48,'0'),'Untouched op type adopts replacement record even when label matches');assert.equal(body.operations[1].op_type_ref,'67'.padStart(48,'0'),'User-selected op type is retained');assert.equal(body.operations[1].supplier_ref,'12d'.padStart(48,'0'),'Untouched supplier adopts server replacement');assert.equal(body.operations[2].source,'external');
  });
  await caseOf('source-supplier-edit-retains-new-server-optype-and-label', async () => {
    await mount({stage:'hours'});await open('工序归属');await button('选择工序 10 供应商').click();await button('选用 Second supplier').click();await check('确认工序 10 归属').check();
    await page.evaluate(()=>{const p=fixtureState.part;p.operations[0].op_type_label='Renamed Turn';p.operations[1].op_type_ref=ref(103);p.operations[1].op_type_label='Server Polish';fixtureState.revision++;});await button('重读详情并保留草稿').click();await button('已核对，采用最新范围并保留可匹配草稿').click();
    const rows=page.getByRole('table',{name:'工序归属明细'}).locator('tbody tr');assert((await rows.first().innerText()).includes('Renamed Turn'));assert((await rows.nth(1).innerText()).includes('Server Polish'));assert((await rows.nth(1).innerText()).includes('Second supplier'));assert(!(await check('确认工序 10 归属').isChecked()));assert(await check('确认工序 15 归属').isChecked());
    await sourceCheck();await check('解除外协组 10 至 10').check();await button('完成归属 · 解锁工时').click();await check('确认工序 5 工时').waitFor();const row=(await lastCommand()).body.input.operations[1];assert.equal(row.op_type_ref,'67'.padStart(48,'0'));assert.equal(row.supplier_ref,'12d'.padStart(48,'0'));
  });
  await caseOf('hours-fieldwise-rebase-keeps-user-values-and-server-updates', async () => {
    await mount({stage:'ready'});await open('工时定额');await page.getByRole('spinbutton',{name:'工序 5 单件工时',exact:true}).fill('8.5');await page.getByRole('spinbutton',{name:'工序 10 外协周期',exact:true}).fill('2.5');await check('确认本页已核对工时').check();
    await page.evaluate(()=>{const p=fixtureState.part;p.operations[0].setup_hours=6;p.operations[0].unit_hours=3;p.operations[1].external_days=4;p.operations[2].unit_hours=4;p.external_groups[0].total_days=9;p.external_groups[0].remark='服务器更新的周期备注';fixtureState.revision++;});await button('重读详情并保留草稿').click();await page.getByRole('table',{name:'最新资料差异'}).locator('tbody tr').first().scrollIntoViewIfNeeded();await shot('hours-review');await button('已核对，采用最新范围并保留可匹配草稿').click();
    for(const [label,expected] of [['工序 5 换型工时','6'],['工序 5 单件工时','8.5'],['工序 10 外协周期','2.5'],['工序 15 单件工时','4'],['外协组 10 至 10 总周期','9']])assert.equal(await page.getByRole('spinbutton',{name:label,exact:true}).inputValue(),expected,label);
    for(const seq of [5,10,15])assert(!(await check('确认工序 '+seq+' 工时').isChecked()));await check('确认本页已核对工时').check();await button('保存工时').click();await page.getByRole('table',{name:'已就绪工序汇总'}).waitFor();const body=(await lastCommand()).body.input;
    assert.deepEqual(body.operations[0],{ref:'3e8'.padStart(48,'0'),setup_hours:6,unit_hours:8.5});assert.equal(body.operations[1].external_days,2.5);assert.equal(body.operations[2].unit_hours,4);assert.equal(body.groups[0].total_days,9);assert.equal(await page.evaluate(()=>fixtureState.part.external_groups[0].remark),'服务器更新的周期备注');
  });
  await caseOf('hours-source-reset-and-dirty-group-total-only', async () => {
    await mount({stage:'ready'});await open('工时定额');await page.getByRole('spinbutton',{name:'工序 5 单件工时',exact:true}).fill('8.5');await page.getByRole('spinbutton',{name:'外协组 10 至 10 总周期',exact:true}).fill('7');await check('确认本页已核对工时').check();
    await page.evaluate(()=>{const p=fixtureState.part;Object.assign(p.operations[0],{source:'external',op_type_ref:ref(102),op_type_label:'Polish',supplier_ref:ref(300),supplier_label:'Original supplier',external_days:6,external_days_source:'operation',setup_hours:30,unit_hours:40});p.operations[1].external_days=5;p.external_groups[0].total_days=9;p.relationships.internal_count=1;p.relationships.external_count=2;fixtureState.revision++;});
    await button('重读详情并保留草稿').click();await button('已核对，采用最新范围并保留可匹配草稿').click();assert.equal(await page.getByRole('spinbutton',{name:'工序 5 单件工时',exact:true}).count(),0);assert.equal(await page.getByRole('spinbutton',{name:'工序 5 外协周期',exact:true}).inputValue(),'6');assert.equal(await page.getByRole('spinbutton',{name:'工序 10 外协周期',exact:true}).inputValue(),'5');assert.equal(await page.getByRole('spinbutton',{name:'外协组 10 至 10 总周期',exact:true}).inputValue(),'7');
    assert(!(await check('确认工序 5 工时').isChecked()));assert(!(await check('确认工序 10 工时').isChecked()));assert(await check('确认工序 15 工时').isChecked());await check('确认本页已核对工时').check();await button('保存工时').click();await page.getByRole('table',{name:'已就绪工序汇总'}).waitFor();const body=(await lastCommand()).body.input;assert.deepEqual(body.operations[0],{ref:'3e8'.padStart(48,'0'),external_days:6});assert.equal(body.operations[1].external_days,5);assert.equal(body.groups[0].total_days,7);
  });
  await caseOf('receipt-missing-ref-or-wrong-stage-stays-pending', async () => {
    for(const fault of ['missingReceiptRef','wrongReceiptRef','missingReceiptStage','wrongReceiptStage']) {
      await mount({stage:'source',[fault]:true});await open();await sourceCheck();await button('完成归属 · 解锁工时').click();await button('查询原请求回执').waitFor();assert(await button('关闭详情').isDisabled());assert(await page.getByRole('tab',{name:/工时定额/}).isDisabled());
      assert.equal(await page.evaluate(()=>fixtureState.committed.length),0);assert.equal(await page.evaluate(()=>fixtureState.commands.length),1);assert(await page.evaluate(()=>!!sessionStorage.getItem('stage-pending')));assert.equal(await page.getByText('服务器已确认提交。',{exact:true}).count(),0);
      await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),1);await button('查询原请求回执').click();await check('确认工序 5 工时').waitFor();assert.equal(await page.evaluate(()=>fixtureState.commands.length),1);assert.equal(await page.evaluate(()=>fixtureState.committed.length),1);assert.equal(await page.evaluate(()=>sessionStorage.getItem('stage-pending')),null);
    }
  });
}
(async () => {await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));let browser;try {
  browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});report.browser=browser.version();assert(report.browser.startsWith('109.'));
  const origin='http://127.0.0.1:'+server.address().port;
  for(const viewport of [{width:1392,height:924},{width:640,height:900}]) for(const theme of ['light','dark']) {
    const context=await browser.newContext({viewport});await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);
    page=await context.newPage();page.setDefaultTimeout(12000);variant=viewport.width+'x'+viewport.height+'-'+theme;page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
    await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){report.external.push(route.request().url());return route.abort();}return route.continue();});await page.goto(origin);await cases();await context.close();
  }
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.external,[]);
} finally {if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'process-stage-result.json'),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({output,browser:report.browser,cases:report.cases.length,screenshots:report.screenshots.length,errors:report.errors,external:report.external}));})().catch(error=>{console.error(error);process.exitCode=1;});
