/* Z: real components and pending storage; isolated mock reads, no build/DB. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass a temporary artifact directory');
fs.mkdirSync(output, { recursive: true });
const files = ['resource-contract.js', 'resource-api.js', 'resource-session.js', 'ResourceControls.jsx',
  'ResourceTableFilterModel.js', 'ResourceTableFilter.jsx', 'ResourceTableHeader.jsx', 'ResourceDetailRelations.jsx', 'ResourceForms.jsx', 'ResourceTables.jsx', 'ResourceMetrics.jsx', 'ResourceRail.jsx',
  'CalendarContract.js', 'ResourceWorkspace.jsx', 'CalendarFields.jsx', 'CalendarDayDialog.jsx', 'CalendarRangeDialog.jsx', 'ResourceCalendar.jsx',
  'ResourceMaterialContract.js', 'ResourceFileContract.js', 'ResourceMaterialPreview.jsx', 'ResourceMaterialActions.jsx', 'ResourceFileActions.jsx', 'ResourceCatalogModel.js', 'ResourceCatalogEditor.jsx', 'ResourceCatalog.jsx',
  'ProcessAPI.js', 'ProcessContract.js', 'ProcessActionContract.js', 'ProcessActionPreview.jsx', 'ProcessCollectionActions.jsx', 'ProcessFileContract.js', 'ProcessFilePreview.jsx', 'ProcessFileActions.jsx', 'ProcessControls.jsx',
  'ProcessStageEditor.jsx', 'ProcessOpTypeCreate.jsx', 'ProcessSourceEditor.jsx', 'ProcessHoursEditor.jsx', 'ProcessRouteEntry.jsx', 'ProcessDetail.jsx', 'ProcessWorkspace.jsx', 'ResourceLive.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, i) => ['/fixture/' + files[i] + '.js', item.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(item => ['/static/' + item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const foundation = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const fixture = `
const h=React.createElement,R=n=>n.toString(16).padStart(48,'0'),copy=x=>JSON.parse(JSON.stringify(x));
const stamp=state=>({state,confirmed_at:state==='confirmed'?'2026-09-09T12:00:00':null,confirmed_by:null});
const caps={route_preview:true,stage_confirm:true,create:true,delete:true,import:true,export:true};
const wc={write_token:'w'.repeat(32),capabilities:Object.fromEntries(['material','machine','operator','supplier','op_type','process','calendar'].flatMap(kind=>['update','delete','create','upsert','route_confirm','source_confirm','hours_confirm'].map(action=>[kind+'.'+action,true]))),blocked_reasons:[]};
let f,viewRoot,key=0;
function env(data,source='production'){return {ok:true,schema_version:1,data,meta:{source,time_basis:'factory_local',snapshot_ref:'s'.repeat(32),request_ref:'navigation-fixture',as_of:'2026-09-09T12:00:00'},warnings:[]};}
function record(kind,n,category){return {kind,ref:R(n),business_code:'SAME-CODE',label:kind+'原记录'+n+'需要完整显示的中文名称'.repeat(f.spec.long?12:0),status:kind==='op_type'?null:'active',
  fields:kind==='op_type'?{category,default_merge_mode:'separate'}:kind==='material'?{stock_qty:0,unit:'kg',spec:'原规格'}:kind==='supplier'?{default_days:2}:{},relationships:{},issues:[],write_context:wc};}
function part(n){const state=f.spec.locked?'route':'ready';return {ref:R(n),business_code:'SAME-PART',label:'原零件'+n,status:null,fields:{route_raw:'原路线',route_parsed:'yes',remark:null},
  relationships:{operation_count:123,batch_count:2,internal_count:0,external_count:123,unclassified_count:0},issues:[],write_context:wc,capabilities:caps,
  workflow:{origin:'managed',stage:state,ready:state==='ready',route:stamp(f.spec.locked?'unconfirmed':'confirmed'),source:stamp(f.spec.locked?'locked':'confirmed'),hours:stamp(f.spec.locked?'locked':'confirmed')},
  operations:Array.from({length:123},(_,i)=>({ref:R(1000+i+n*10000),sequence:i+1,label:'同名工序'+(i+1)+'很长的工序名称'.repeat(f.spec.long?12:0),source:'external',op_type_ref:R(11),op_type_label:'外协工种',supplier_ref:R(4),supplier_label:'原供应商',external_group_ref:R(3000+Math.min(i,69)+n*10000),
    setup_hours:null,unit_hours:null,external_days:2,status:f.spec.deletedOperation&&i===116?'deleted':'active',issues:[],confirmation:{source:stamp('confirmed'),hours:stamp('confirmed')}})),
  external_groups:Array.from({length:70},(_,i)=>({ref:R(3000+i+n*10000),start_sequence:i+1,end_sequence:i+1,merge_mode:'separate',total_days:null,supplier_ref:R(4),supplier_label:'原供应商',remark:'原组',issues:[]}))};}
function monthData(year,month){const K=APSCalendarContract,days=Array.from({length:K.monthDays(year,month)},(_,i)=>{const date=K.monthKey(year,month)+'-'+String(i+1).padStart(2,'0'),weekday=(new Date(date+'T12:00:00').getDay()+6)%7,explicit=i===8&&!f.spec.deletedDate;
  return {date,day:i+1,weekday,is_weekend:weekday>=5,is_today:false,explicit,calendar_ref:explicit?R(900):null,entity:explicit?{ref:R(900)}:null,
    fields:{type:'work',hours:8,eff:100,allowNormal:'yes',allowUrgent:'yes',note:'原日期说明'},stored:explicit?{day_type:'workday',shift_start:'08:00',shift_end:'16:00',shift_hours:8,efficiency:1,allow_normal:'yes',allow_urgent:'yes'}:null,write_context:wc,
    effective:{is_working:true,window_start:date+'T08:00:00',window_end:date+'T16:00:00'},issues:[]};});
  const cells=[...Array(days[0].weekday).fill(null),...days.map(row=>({date:row.date}))];while(cells.length%7)cells.push(null);
  return {year,month,time_basis:'factory_local',as_of:'2026-09-09T12:00:00',days,cells,stats:{work_days:days.length,configured:1,overrides:0,weekend_rest:0},previous_month:null,next_month:null};}
function list(kind,scope){f.reads.push({type:'list',kind,scope:copy(scope)});const entities=kind==='part'?[part(5),part(6)]:f.records.filter(row=>row.kind===kind&&(!scope.category||row.fields.category===scope.category));
  return env({entities,page:{number:scope.page,size:scope.size,total:entities.length,pages:1,sort:kind==='part'?APSProcessContract.ordering(scope):[]},create_context:wc,
    capabilities:caps,metrics:{counts:{total:2,route:0,source:0,hours:0,ready:2}}});}
async function detail(kind,ref){f.reads.push({type:'detail',kind,ref});const n=parseInt(ref,16);let entity=kind==='part'&&[5,6].includes(n)?part(n):f.records.find(row=>row.kind===kind&&row.ref===ref);
  if(f.spec.deleted||!entity)throw APSResourceContract.failure('原引用已删除，不能使用同号重建记录。');entity=copy(entity);
  if(f.spec.wrongRef)entity.ref=R(999);if(f.spec.wrongKind)entity.kind='wrong';if(f.spec.wrongCategory)entity.fields.category='external';
  if(f.spec.delay&&ref===R(1))await new Promise(resolve=>f.releaseOld=()=>resolve());
  return env(entity,f.spec.demo?'demo':'production');}
const originalCreate=APSResourceAPI.create;
APSResourceAPI.create=function(namespace='resources'){const api=originalCreate(namespace);f.adapters[namespace]=api;
  api.query=async(path,scope)=>{if(path.endsWith('/month')){f.reads.push({type:'month',scope:copy(scope)});return env(monthData(scope.year,scope.month),f.spec.demo?'demo':'production');}
    const segments=path.split('/');if(segments[0]==='entities'){const decoded={...scope};if(segments[1]==='part')for(const field of ['sort','column_filters'])if(typeof decoded[field]==='string')decoded[field]=JSON.parse(decoded[field]);return segments.length===3?detail(segments[1],segments[2]):list(segments[1],decoded);}
    throw APSResourceContract.failure('Unexpected query '+path);};
  api.list=async(kind,scope)=>list(kind,scope);api.detail=detail;
  api.summary=async()=>env({counts:{part:2,material:1,internal_op_types:1,machine:1,operator:1,external_op_types:1,supplier:1}});
  api.relations=async(ref,scope)=>env({parent_ref:ref,parent_kind:'op_type',relation:scope.relation,basis:{code:'recorded_associations',message:'原关联'},entities:[],page:{number:scope.page,size:scope.size,total:0,pages:1,sort:[]}});
  api.lookup=async(request_key)=>{f.lookups.push({namespace,request_key});return f.resolved?f.receipts[namespace]:{ok:true,state:'not_recorded',receipt:null,may_be_in_flight:true};};
  api.execute=async()=>{f.writes++;throw new Error('Navigation must not write');};return api;};
function pending(namespace){const intent={kind:namespace==='process'?'process':namespace==='calendar'?'calendar':namespace==='catalog'?'machine_group':namespace.endsWith('_files')?'machine_import':'material',
  action:namespace==='process'?'hours_confirm':namespace==='calendar'?'upsert':namespace.endsWith('_files')?'confirm':'update',ref:namespace==='process'?R(5):namespace==='calendar'?'2026-09-09':namespace.endsWith('_files')?'p'.repeat(32):R(1),request_key:'resource-'+R(['resources','process','calendar','catalog','machine_files'].indexOf(namespace)+1)};
  originalCreate(namespace).savePending(intent);f.originalPending[namespace]=copy(intent);
  f.receipts[namespace]={ok:true,result:'committed',receipt_ref:'receipt-'+namespace,replayed:true,warnings:[],data:namespace==='process'?{entity_ref:R(5),stage:'hours'}:namespace==='calendar'?{date:'2026-09-09'}:{entity_ref:R(1)}};}
function Harness(){const [navigation,setNavigation]=React.useState({context:f.spec.context,key:++key});window.navigateFixture=context=>setNavigation({context,key:++key});
  return h(React.Fragment,null,h(WorkbenchControlStyles),h(WorkbenchControls),h(WorkbenchNumberControls),h(AppShell,{active:'process',theme:document.documentElement.dataset.theme,title:'基础资料导航',showCapsule:false,onNav:()=>{}},
    h(ResourceLive,{key:navigation.key,initialContext:navigation.context,onNavigate:()=>{}})));}
window.mountFixture=(spec={})=>{if(viewRoot)viewRoot.unmount();sessionStorage.clear();f=window.fixture={spec,reads:[],lookups:[],writes:0,adapters:{},resolved:false,receipts:{},originalPending:{}};
  f.records=[record('material',1),record('material',12),record('machine',2),record('operator',3),record('supplier',4),record('op_type',10,'internal'),record('op_type',11,'external')];
  if(spec.deleted&&spec.context){f.records=f.records.filter(row=>row.ref!==spec.context.entity_ref);if(spec.context.kind!=='part')f.records.push(record(spec.context.kind,999,spec.context.category));}
  (spec.pending||[]).forEach(pending);viewRoot=ReactDOM.createRoot(document.getElementById('root'));viewRoot.render(h(Harness));};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="/static/' + manifest.icon + '">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + foundation.map(file => '<script src="/static/' + file + '"></script>').join('') +
  [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') + '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); }
  else if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); }
  else if (assets.has(name)) { const asset = assets.get(name); res.setHeader('Content-Type', asset.mime); res.end(asset.bytes); }
  else { res.writeHead(404); res.end(); }
});
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const report = { scope: 'resource-navigation-current-source-component-mock', production_persistence_tested: false, compile: { target: compiled.target, global_build: false },
  sources: sources.map(row => ({ path: row.path, sha256: sha(row.code) })), cases: [], screenshots: [], errors: [], external: [] };
const ref = n => n.toString(16).padStart(48, '0'), ctx = (kind, n, patch = {}) => ({ source: 'production', kind, entity_ref: ref(n), ...patch });
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
async function mount(spec = {}) { await page.evaluate(spec => mountFixture(spec), spec); await page.locator('[data-resource-workspace]').waitFor(); }
async function idle() { await page.waitForFunction(() => !Array.from(document.querySelectorAll('[aria-busy]')).some(node => node.getAttribute('aria-busy') === 'true')); }
async function noWrites() { assert.equal(await page.evaluate(() => fixture.writes), 0); assert(await page.evaluate(() => fixture.reads.filter(row => row.type === 'list').every(row => !row.scope.query))); }
async function shot(name) {
  await page.evaluate(() => document.fonts.ready);
  const geometry = await page.evaluate(() => { const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden'; return {
    width: innerWidth, height: innerHeight, scroll: document.documentElement.scrollWidth,
    dialogs: Array.from(document.querySelectorAll('[role="dialog"]')).filter(visible).map(node => { const r = node.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom }; }),
    overflow: Array.from(document.querySelectorAll('button')).filter(visible).filter(node => !node.closest('.card-scroll') && node.scrollWidth > node.clientWidth + 2).map(node => node.textContent) }; });
  assert(geometry.scroll <= geometry.width + 1, JSON.stringify(geometry)); assert(geometry.dialogs.length <= 1, JSON.stringify(geometry)); assert.deepEqual(geometry.overflow, []);
  geometry.dialogs.forEach(r => assert(r.left >= 0 && r.top >= 0 && r.right <= geometry.width + 1 && r.bottom <= geometry.height + 1, JSON.stringify(geometry)));
  const file = variant + '-' + name + '.png'; await page.screenshot({ path: path.join(output, file), animations: 'disabled' }); report.screenshots.push({ file, geometry });
}
async function run(name, test) { try { await test(); await noWrites(); report.cases.push({ variant, name, passed: true }); } catch (error) {
  report.cases.push({ variant, name, passed: false, error: error.stack }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-FAILED.png') }); throw error; } }
async function focused(target) { await page.waitForFunction(ref => document.activeElement.dataset.processLocation === ref, target); const row = page.locator('[data-process-location="' + target + '"]:visible');
  assert.equal(await row.count(), 1); const box = await row.boundingBox(); assert(box.y >= 0 && box.y + box.height <= (await page.viewportSize()).height); }
async function cases() {
  await run('default-and-root-entry', async () => { for (const context of [undefined, { source: 'production' }]) { await mount({ context }); await idle(); assert.equal(await page.getByRole('dialog').count(), 0); assert.equal(await page.evaluate(() => fixture.reads.filter(row => row.type === 'detail').length), 0); } });
  await run('strict-context-protocol', async () => {
    await mount(); const invalid = [[], {}, { source: 'demo' }, { source: 'production', kind: 'unknown' }, ctx('material', 1, { entity_ref: null }), ctx('material', 1, { entity_ref: 'a'.repeat(47) }), ctx('material', 1, { entity_ref: 'A'.repeat(48) }), ctx('material', 1, { category: 'internal' }), ctx('op_type', 10), ctx('op_type', 10, { category: 'unknown' }), ctx('part', 5, { stage: 'ready' }), ctx('part', 5, { template_operation_ref: 'bad' }), ctx('part', 5, { template_external_group_ref: 12 }), ctx('material', 1, { business_code: 'SAME-CODE' }), ctx('machine_group', 1), { source: 'production', catalogkind: 'machine_group' },
      { source: 'production', kind: 'calendar', month: '0000-01' }, { source: 'production', kind: 'calendar', month: '2026-13' }, { source: 'production', kind: 'calendar', month: '2026-09', date: '2026-10-01' }, { source: 'production', kind: 'calendar', month: '2026-02', date: '2026-02-29' }];
    assert(await page.evaluate(invalid => invalid.every(context => !!ResourceWorkspace.navigation(context).error), invalid));
    for (const context of [ctx('material', 1, { source: 'demo' }), ctx('op_type', 10), ctx('part', 5, { entity_ref: undefined })]) { await mount({ context }); await idle(); assert.equal(await page.getByRole('dialog').count(), 0); assert.equal(await page.evaluate(() => fixture.reads.filter(row => row.type === 'detail').length), 0); assert(await page.getByRole('alert').count()); }
  });
  for (const [kind, n, category] of [['material', 1], ['machine', 2], ['operator', 3], ['supplier', 4], ['op_type', 10, 'internal'], ['op_type', 11, 'external']]) await run('exact-' + kind + '-' + n, async () => {
    await mount({ context: ctx(kind, n, category ? { category } : {}), long: true }); await page.getByRole('dialog').waitFor(); await page.getByRole('dialog').getByText(kind + '原记录' + n, { exact: false }).first().waitFor();
    assert.equal(await page.getByRole('dialog').locator('input[name="label"]').count(), 0); assert.deepEqual(await page.evaluate(() => fixture.reads.filter(row => row.type === 'detail').map(row => [row.kind, row.ref])), [[kind, ref(n)]]); if (kind === 'material') await shot('material-long-readonly');
  });
  await run('resource-identity-source-category-reject', async () => { for (const spec of [{ deleted: true }, { wrongRef: true }, { wrongKind: true }, { demo: true }, { wrongCategory: true }]) {
    await mount({ ...spec, context: ctx('op_type', 10, { category: 'internal' }) }); await page.getByRole('dialog').getByRole('alert').waitFor(); assert.equal(await page.getByRole('dialog').getByText('op_type原记录10', { exact: false }).count(), 0);
  } });
  await run('same-kind-key-change-and-late-read', async () => {
    await mount({ context: ctx('material', 1), delay: true }); await page.waitForFunction(() => typeof fixture.releaseOld === 'function'); await page.evaluate(context => navigateFixture(context), ctx('machine', 2));
    await page.getByRole('dialog').getByText('machine原记录2', { exact: true }).waitFor(); await page.evaluate(() => fixture.releaseOld()); await idle(); assert.equal(await page.getByRole('dialog').getByText('material原记录1', { exact: false }).count(), 0);
    await page.evaluate(context => navigateFixture(context), ctx('supplier', 4)); await page.getByRole('dialog').getByText('supplier原记录4', { exact: true }).waitFor();
    await page.evaluate(context => navigateFixture(context), ctx('material', 12)); await page.getByRole('dialog').getByText('material原记录12', { exact: true }).waitFor();
    await page.evaluate(() => { fixture.spec.delay=false; }); await page.evaluate(context => navigateFixture(context), ctx('material', 1)); await page.getByRole('dialog').getByText('material原记录1', { exact: true }).waitFor();
    assert.equal(await page.getByRole('dialog').getByText('material原记录12', { exact: true }).count(), 0);
  });
  await run('deleted-ref-with-same-code-replacement-list', async () => { await mount({ deleted: true, context: ctx('material', 1) }); await page.getByRole('dialog').getByRole('alert').waitFor();
    assert(await page.evaluate(() => fixture.records.some(row => row.ref === (999).toString(16).padStart(48, '0') && row.business_code === 'SAME-CODE')));
    assert.deepEqual(await page.evaluate(() => fixture.reads.filter(row => row.type === 'detail').map(row => row.ref)), [ref(1)]);
  });
  await run('part-stage-long-operation-page-and-focus', async () => {
    for (const stage of ['route', 'source', 'hours']) { const operation = ref(51116); await mount({ context: ctx('part', 5, { stage, template_operation_ref: operation }), long: true });
      await page.locator('[data-process-navigation-stage="' + stage + '"]').waitFor(); await focused(operation); assert.equal(await page.getByRole('dialog').getByRole('spinbutton', { name: /^工序 / }).count(), 0); await shot('operation-' + stage); }
  });
  await run('part-group-page-and-focus', async () => { const group = ref(53065); await mount({ context: ctx('part', 5, { stage: 'hours', template_external_group_ref: group }) }); await focused(group); await shot('group-page-two'); });
  await run('same-part-operation-and-group-accepted', async () => { await mount({ context: ctx('part', 5, { stage: 'source', template_operation_ref: ref(51116), template_external_group_ref: ref(53069) }) });
    await focused(ref(53069)); assert.equal(await page.locator('[data-process-location="' + ref(51116) + '"]:visible').count(), 1);
  });
  await run('readonly-navigation-enters-original-editor-only-explicitly', async () => { await mount({ context: ctx('part', 5, { stage: 'hours' }) }); await button('开始维护').waitFor();
    assert.equal(await page.getByRole('dialog').getByRole('checkbox').count(), 0); await button('开始维护').click(); await page.getByRole('table', { name: '工时定额明细', exact: true }).waitFor();
    assert.equal(await page.locator('[data-process-navigation-stage]').count(), 0); await page.getByRole('dialog').getByRole('button', { name: '导入工时定额', exact: true }).waitFor();
    assert(await page.evaluate(() => fixture.reads.filter(row => row.type === 'detail').every(row => row.ref === '5'.padStart(48, '0'))));
  });
  await run('part-op-group-membership-and-deletion', async () => {
    for (const patch of [{ template_operation_ref: ref(61116) }, { template_external_group_ref: ref(63065) }, { template_operation_ref: ref(51116), template_external_group_ref: ref(53065) }]) {
      await mount({ context: ctx('part', 5, { stage: 'hours', ...patch }) }); await page.getByRole('dialog').getByRole('alert').waitFor(); assert.equal(await page.locator('[data-process-navigation-stage]').count(), 0);
    }
    for (const spec of [{ deletedOperation: true }, { deleted: true }, { wrongRef: true }, { demo: true }]) { await mount({ ...spec, context: ctx('part', 5, { template_operation_ref: ref(51116) }) }); await page.getByRole('dialog').getByRole('alert').waitFor(); assert.equal(await page.locator('[data-process-navigation-stage]').count(), 0); }
  });
  await run('locked-stage-readonly-cannot-confirm', async () => { await mount({ locked: true, context: ctx('part', 5, { stage: 'hours', template_operation_ref: ref(51116) }) }); await focused(ref(51116));
    await page.getByText('前置路线或归属尚未确认；当前只读定位，不能确认工时。', { exact: true }).first().waitFor(); assert(await page.getByRole('button', { name: /^开始维护/ }).isDisabled()); assert.equal(await page.getByRole('dialog').getByRole('checkbox').count(), 0); await shot('locked-hours');
  });
  await run('calendar-date-readonly-and-explicit-edit', async () => { await mount({ context: { source: 'production', kind: 'calendar', month: '2026-09', date: '2026-09-09' } });
    await page.getByRole('dialog', { name: '2026-09-09 · 日历详情', exact: true }).waitFor(); assert.equal(await page.getByRole('dialog').locator('input,select,textarea').count(), 0); await shot('calendar-date');
    await button('维护此日').click(); await button('保存配置').waitFor(); await button('取消').click(); assert.equal(await page.getByRole('dialog').count(), 0);
    await mount({ context: { source: 'production', kind: 'calendar', month: '2024-02' } }); await page.getByText('2024 年 2 月', { exact: true }).waitFor(); await idle(); assert.equal(await page.getByRole('dialog').count(), 0);
  });
  await run('calendar-deleted-or-demo-no-default-substitution', async () => { for (const spec of [{ deletedDate: true }, { demo: true }]) { await mount({ ...spec, context: { source: 'production', kind: 'calendar', month: '2026-09', date: '2026-09-09' } }); await page.getByRole('alert').waitFor(); assert.equal(await page.getByRole('dialog').count(), 0); } });
  await run('base-pending-remount-resolve-explicit-continue', async () => {
    await mount({ pending: ['resources'], context: ctx('machine', 2) }); await page.getByRole('dialog', { name: '原请求结果', exact: true }).waitFor(); await button('查询原请求回执').waitFor(); assert.equal(await page.evaluate(() => fixture.reads.filter(row => row.type === 'detail').length), 0);
    await page.evaluate(context => navigateFixture(context), ctx('supplier', 4)); await button('查询原请求回执').waitFor(); assert.deepEqual(await page.evaluate(() => JSON.parse(sessionStorage.getItem('aps_workbench_resource_pending_v1'))), await page.evaluate(() => fixture.originalPending.resources));
    await page.evaluate(() => { fixture.resolved = true; }); await button('查询原请求回执').click(); await page.waitForFunction(() => fixture.reads.some(row => row.type === 'detail' && row.ref === '1'.padStart(48, '0')));
    await page.getByRole('dialog').locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click(); await page.getByRole('dialog').waitFor({ state: 'detached' }); assert.equal(await page.evaluate(() => fixture.reads.some(row => row.type === 'detail' && row.ref === '4'.padStart(48, '0'))), false);
    await shot('pending-ready-to-continue'); await button('继续原导航').click(); await page.getByRole('dialog').getByText('supplier原记录4', { exact: true }).waitFor(); assert.equal(await page.evaluate(() => sessionStorage.getItem('aps_workbench_resource_pending_v1')), null);
  });
  await run('process-pending-keeps-original-part-before-navigation', async () => {
    await mount({ pending: ['process'], context: ctx('part', 6, { stage: 'hours', template_operation_ref: ref(61116) }) }); await page.getByRole('dialog').getByText('原零件5', { exact: false }).first().waitFor(); await button('查询原请求回执').waitFor();
    assert.equal(await page.evaluate(() => fixture.reads.some(row => row.type === 'detail' && row.ref === '6'.padStart(48, '0'))), false); await page.evaluate(() => { fixture.resolved = true; }); await button('查询原请求回执').click();
    await page.getByText('服务器已确认提交，已重新读取工艺详情。', { exact: true }).waitFor(); await button('关闭详情').click(); await page.getByRole('dialog').waitFor({ state: 'detached' });
    assert.equal(await page.evaluate(() => fixture.reads.some(row => row.type === 'detail' && row.ref === '6'.padStart(48, '0'))), false); await button('继续原导航').click(); await focused(ref(61116));
  });
  await run('calendar-pending-priority-and-continue', async () => { await mount({ pending: ['calendar'], context: ctx('material', 1) }); await page.getByRole('dialog', { name: '工作日历操作回执', exact: true }).waitFor();
    await button('查询原请求回执').waitFor(); assert.equal(await page.evaluate(() => fixture.reads.filter(row => row.type === 'detail').length), 0); await page.evaluate(() => { fixture.resolved = true; }); await button('查询原请求回执').click();
    await page.getByRole('dialog').locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click(); await page.getByRole('dialog').waitFor({ state: 'detached' }); await button('继续原导航').click(); await page.getByRole('dialog').getByText('material原记录1', { exact: true }).waitFor();
  });
  await run('file-catalog-pending-not-overwritten', async () => { for (const namespace of ['machine_files', 'catalog']) { await mount({ pending: [namespace], context: ctx('material', 1) }); await button('查询原请求回执').waitFor();
    assert.equal(await page.evaluate(() => fixture.reads.filter(row => row.type === 'detail').length), 0); await page.evaluate(context => navigateFixture(context), ctx('part', 6)); await button('查询原请求回执').waitFor();
    assert.deepEqual(await page.evaluate(namespace => JSON.parse(sessionStorage.getItem('aps_workbench_resource_pending_v1_' + namespace)), namespace), await page.evaluate(namespace => fixture.originalPending[namespace], namespace));
    assert.equal(await page.locator('[data-process-navigation-stage]').count(), 0); }
  });
}
(async () => { let browser; try {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); const origin = 'http://127.0.0.1:' + server.address().port;
  browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] }); report.browser = browser.version(); assert(report.browser.startsWith('109.'));
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) {
    variant = viewport.width + '-' + theme; const context = await browser.newContext({ viewport });
    await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
    page = await context.newPage(); page.setDefaultTimeout(10000); page.on('pageerror', error => report.errors.push(error.message)); page.on('console', event => { if (event.type() === 'error') report.errors.push(event.text()); });
    await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
    await page.goto(origin); await cases(); await context.close();
  }
  assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
} catch (error) { report.failure = error.stack; process.exitCode = 1; }
finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'navigation-result.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length, failure: report.failure, errors: report.errors })); }
})();
