/* Current source compile + real Chromium 109. Adapter mocks, not backend/database proof. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http');
const path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright');
const controls = require('./custom_control_actions.cjs');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass a temporary artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchGuards.js', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'ResourceTableFilterModel.js',
  'ResourceTableFilter.jsx', 'ResourceTableHeader.jsx', 'ResourceDetailRelations.jsx', 'ResourceForms.jsx', 'ResourceTables.jsx',
  'ResourceMaterialContract.js', 'ResourceMaterialPreview.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js',
  'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchNumberControls.jsx',
  'ProcessContract.js', 'ProcessReadView.js', 'ProcessActionContract.js', 'ProcessActionPreview.jsx', 'ProcessCollectionActions.jsx',
  'ProcessFileContract.js', 'ProcessFilePreview.jsx', 'ProcessFileActions.jsx',
  'ProcessControls.jsx', 'ProcessStageEditor.jsx', 'ProcessOpTypeCreate.jsx', 'ProcessSourceEditor.jsx',
  'ProcessHoursEditor.jsx', 'ProcessRouteEntry.jsx', 'ProcessDetail.jsx', 'ProcessWorkspace.jsx'];
const styleSources = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json'), 'utf8')).styles.map(name => {
  const file = 'frontend/workbench/app/styles/' + name; return { path: file, code: fs.readFileSync(path.join(root, file), 'utf8') };
});
const workspaceCSS = styleSources.map(row => row.code).join('\n');
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const assets = new Map(manifest.files.map(item => [item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const fixtureCode = `
const ref = n => n.toString(16).padStart(48,'0');
const stamp = state => ({state,confirmed_at:null,confirmed_by:null});
const caps = {route_preview:true,create:false,delete:false,stage_confirm:false,import:false,export:false};
const envelope = (data,snapshot='fixture-detail',source='demo') => ({ok:true,schema_version:1,data,meta:{source,time_basis:'factory_local',snapshot_ref:snapshot,request_ref:'mock-request',as_of:'2026-09-09T08:00:00'},warnings:[]});
function recordPart(n,long=false) {
  const missing=n%2===0;
  return {ref:ref(n),business_code:'PART-'+String(n).padStart(3,'0'),label:long?'长名称AlphaBeta'.repeat(16):'零件 '+n,status:null,
    fields:{route_raw:missing?null:'5Turn10Polish20Unknown',route_parsed:missing?'no':'yes',remark:long?'原备注及隐藏资料必须保留'.repeat(24):null},
    relationships:{batch_count:2,operation_count:missing?0:3,internal_count:missing?0:1,external_count:missing?0:1,unclassified_count:missing?0:1},
    issues:n===3?[{code:'legacy_data',message:'存量资料需要复核'}]:[],write_context:null,
    workflow:{origin:'legacy',stage:missing?'route':'source',route:stamp(missing?'missing':'present'),source:stamp(missing?'locked':'unconfirmed'),hours:stamp('locked'),ready:false}};
}
function detailPart(n,long=false,count) {
  const p=recordPart(n,long), total=count===undefined?p.relationships.operation_count:count;
  p.relationships.operation_count=total;
  // Projection DTO, not raw storage: invalid external/group zeros remain null + value_invalid, never a usable group cycle.
  p.operations=Array.from({length:total},(_,i)=>({ref:ref(1000+i),sequence:(i+1)*5,label:['Turn','Polish','Unknown'][i%3],source:['internal','external',null][i%3],
    op_type_ref:i%3===2?null:ref(100+i),op_type_label:i%3===2?null:['Turn','Polish'][i%3],supplier_ref:i%3===1?ref(300):null,supplier_label:i%3===1?'供应商长名称'.repeat(long?16:1):null,
    external_group_ref:i%3===1?ref(400):null,setup_hours:i%3===0?0:null,unit_hours:i%3===0?1.25:null,external_days:null,external_days_source:null,status:'active',
    issues:i%3===1?[{code:'external_group_invalid',message:'关联的外协组规则不合法，这道工序仍用自己的周期。请核对外协组的起止序、成员和周期。'},
      {code:'value_invalid',message:'外协周期填的值不合法，系统不会用默认值顶替。'}]:i%3===2?[{code:'unknown_type',message:'旧记录工种未识别'}]:[],confirmation:{source:stamp('unconfirmed'),hours:stamp('unconfirmed')}}));
  p.external_groups=total?[{ref:ref(400),start_sequence:10,end_sequence:10,merge_mode:'merged',total_days:null,supplier_ref:ref(300),supplier_label:'原供应商',remark:'保留原外协规则',issues:[{code:'value_invalid',message:'合并周期填的值不合法，系统不会用默认值顶替。'}]}]:[];
  p.capabilities={...caps};return p;
}
function previewData(partRef,body) {
  let rows=body.mode==='rows'?body.rows:!body.route_raw?[]:body.route_raw==='SLOW'||body.route_raw==='FAST'?[{seq:5,op_type_name:body.route_raw}]:[{seq:5,op_type_name:'Turn'},{seq:10,op_type_name:body.route_raw.includes('Unknown')?'Unknown':'Polish'}];
  const diagnostics=[], seen=new Set();
  rows.forEach(row=>{if(seen.has(row.seq))diagnostics.push({code:'duplicate_sequence',severity:'error',message:'工序号重复',sequence:row.seq});seen.add(row.seq);
    if(!row.op_type_name.trim())diagnostics.push({code:'missing_name',severity:'error',message:'工种名称缺失',sequence:row.seq});});
  if(!rows.length)diagnostics.push({code:'empty_route',severity:'error',message:'路线不能为空'});
  const operations=rows.map(row=>({sequence:row.seq,op_type_name:row.op_type_name,op_type_ref:['Turn','Polish'].includes(row.op_type_name)?ref(101):null,
    source_suggestion:row.op_type_name==='Turn'?'internal':row.op_type_name==='Polish'?'external':null,supplier_ref:row.op_type_name==='Polish'?ref(300):null,
    supplier_label:row.op_type_name==='Polish'?'原供应商':null,external_days:row.op_type_name==='Polish'?0:null,basis:'MOCK: local fixture lookup only',issues:[]}));
  if(operations.some(row=>row.op_type_ref===null))diagnostics.push({code:'unknown_type',severity:'warning',message:'未知工种仅预检，尚未建档'});
  return {part_ref:partRef,mode:body.mode,route_raw:body.mode==='text'?body.route_raw:rows.map(row=>row.seq+' '+row.op_type_name).join(' '),
    normalized_input:rows.map(row=>row.seq+' '+row.op_type_name).join(' / '),operations,diagnostics,can_confirm_route:!diagnostics.some(row=>row.severity==='error'),
    counts:{operations:operations.length,recognized:operations.filter(row=>row.op_type_ref!==null).length,unknown:operations.filter(row=>row.op_type_ref===null).length},
    baseline:{operation_count:3,external_group_count:1,has_published_template:true},changes:{added:[10],removed:[15],retained:[5],same_sequence_changed:[5]},affected_groups:[],
    write_context:diagnostics.some(row=>row.severity==='error')?null:{write_token:'mock-route-token',capabilities:{'process.route_confirm':true},blocked_reasons:[]}};
}
let renderRoot;
function Harness({spec}) {
  const [disabled,setDisabled]=React.useState(!!spec.disabled), f=fixture;
  f.setDisabled=setDisabled;
  const adapter=React.useMemo(()=>{
    async function call(type,request,signal) {
      const item={id:++f.serial,type,...request};f.reads.push(item);
      if(signal.aborted)f.aborted.push(item.id);
      signal.addEventListener('abort',()=>f.aborted.push(item.id),{once:true});
      const held=type==='list'&&request.scope.query==='SLOW'||type==='preview'&&request.body.route_raw==='SLOW'||type==='detail'&&f.spec.slowDetail;
      if(held)await new Promise(resolve=>{f.holds[type]=resolve;});else await new Promise(resolve=>setTimeout(resolve,8));
      f.settled.push(item.id);return item;
    }
    const a={
      list:async(kind,scope,signal)=>{
        await call('list',{kind,scope},signal);if(f.spec.failList)throw {ok:false,error:{code:'unavailable',message:'Mock 列表读取失败'}};
        let rows=f.rows.filter(row=>!scope.query||scope.query==='SLOW'||row.business_code.includes(scope.query)||row.label.includes(scope.query)||row.fields.route_raw&&row.fields.route_raw.includes(scope.query));
        if(scope.stage)rows=rows.filter(row=>row.workflow.stage===scope.stage);
        const counts={total:rows.length,route:rows.filter(row=>row.workflow.stage==='route').length,source:rows.filter(row=>row.workflow.stage==='source').length,hours:0,ready:0};
        if(!Array.isArray(scope.sort))throw new Error('MOCK CONTRACT: process sort must be an array');
        const ordering=scope.sort.map(item=>({...item}));
        rows=rows.slice().sort((a,b)=>{for(const {field,direction} of ordering){const value=row=>field==='operation_count'?row.relationships.operation_count:field==='stage'?row.workflow.stage:row[field];const av=value(a),bv=value(b);if(av!==bv)return (av<bv?-1:1)*(direction==='desc'?-1:1);}return a.ref<b.ref?-1:a.ref>b.ref?1:0;});
        if(f.spec.empty)rows=[];
        const snapshot='fixture-list:'+JSON.stringify({query:scope.query,stage:scope.stage||'',sort:ordering,column_filters:scope.column_filters,size:scope.size});
        const d={entities:rows.slice((scope.page-1)*scope.size,scope.page*scope.size),page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.max(1,Math.ceil(rows.length/scope.size)),sort:ordering},metrics:{counts},capabilities:{...caps,...f.spec.capabilities},create_context:null};
        if(f.spec.badList)delete d.metrics;
        return envelope(d,f.spec.stalePage&&scope.page===2?'changed':snapshot);
      },
      detail:async(kind,id,signal)=>{
        await call('detail',{kind,ref:id},signal);if(f.spec.failDetail)throw {ok:false,error:{message:'Mock 详情读取失败'}};
        const n=parseInt(id,16), d=detailPart(n,f.spec.long,f.spec.operationCount);d.capabilities={...caps,...f.spec.capabilities};
        if(f.spec.largeSequence) {
          d.operations[0].sequence='9223372036854775807';d.operations[0].op_type_label='RenamedMaster';
          d.fields.route_raw='9223372036854775807Turn';d.external_groups[0].start_sequence='9007199254740992';d.external_groups[0].end_sequence='9223372036854775807';
          d.operations.push({...d.operations[0],ref:ref(9000),sequence:99,label:'DeletedOriginal',status:'deleted'});
        }
        if(f.spec.invalidStored) {
          d.operations[0].sequence=0;d.operations[0].unit_hours=0;d.operations[0].issues=[{code:'invalid_stored_sequence',message:'原工序号为0，请核对'}];
          d.operations[1].sequence=-5;d.operations[2].sequence='原始坏序号TEXT';
          d.external_groups[0].start_sequence='bad-start';d.external_groups[0].end_sequence=-10;
          d.external_groups[0].issues=[{code:'invalid_stored_range',message:'原外协组范围不合法，请核对'}];
        }
        if(f.spec.unknownParsed)d.fields.route_parsed='legacy-unknown-flag';
        if(f.spec.badDetail)d.ref=ref(999);return envelope(d,f.spec.detailSnapshot||'fixture-detail',f.spec.demoDetail?'demo':'production');
      },
      choices:async(kind,scope,signal)=>{
        await call('choices',{kind,scope},signal);
        const entities=[[101,'OP-1','Turn','internal'],[102,'OP-2','Polish','external'],[103,'OP-3','Grind','internal']]
          .map(([n,code,label,category])=>({ref:ref(n),business_code:code,label,status:null,fields:{category},relationships:{},issues:[],write_context:null}));
        return envelope({entities,page:{number:1,size:scope.size,total:entities.length,pages:1,sort:[]}},'fixture-choices');
      },
      routePreview:async(id,body,signal)=>{
        await call('preview',{ref:id,body},signal);if(f.spec.failPreview)throw {ok:false,error:{code:'stale_snapshot',message:'Mock 预检快照失效'}};
        const d=previewData(id,body);if(f.spec.badPreview)d.part_ref=ref(999);
        if(f.spec.largeSequence) {
          d.operations[0].sequence='9223372036854775807';d.normalized_input='9223372036854775807Turn';
          d.changes={added:['9223372036854775807'],removed:['9007199254740992'],retained:[5],same_sequence_changed:['9223372036854775806']};
          d.diagnostics.push({code:'review_large',severity:'warning',sequence:'9223372036854775807',message:'MOCK large sequence preserved'});
        }
        return envelope(d,'fixture-preview');
      },
      command:async(...args)=>{f.commands.push(args);throw new Error('No command allowed in read/preview phase');}
    };
    for(const name of ['openImport','openExport','openBulk','create','delete','stageConfirm'])a[name]=(...args)=>{f.commands.push({name,args});throw new Error('Unexpected write/file entry');};
    if(spec.disconnected)delete a.command;
    f.adapter=a;return a;
  },[]);
  return React.createElement(React.Fragment,null,React.createElement(WorkbenchGuardHost),React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),
    React.createElement('section',{className:'plana',style:{padding:24,minWidth:0}},React.createElement('h2',null,'零件工艺'),React.createElement(ProcessWorkspace,{adapter,disabled,onCommitted:receipt=>f.committed.push(receipt)})));
}
window.mountFixture=spec=>{
  if(renderRoot)renderRoot.unmount();
  window.fixture={spec,reads:[],commands:[],committed:[],aborted:[],settled:[],holds:{},serial:0,keys:[],rows:Array.from({length:45},(_,i)=>recordPart(i+1,!!spec.long&&i===0))};
  renderRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));renderRoot.render(React.createElement(Harness,{spec}));
};
document.addEventListener('keydown',event=>{if(window.fixture)fixture.keys.push({key:event.key,label:event.target.getAttribute('aria-label')});});
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' +
  manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><p style="padding:0 24px">组件测试 · Mock 接口 · 非生产持久化证据</p><div id="fixture-root"></div>' +
  staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') +
  Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixtureCode + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html.replace('</head>', '<style>' + workspaceCSS + '</style></head>')); return; }
  if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); return; }
  const asset = assets.get(name.slice('/static/'.length));
  if (!name.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const report = { scope: 'process-read-preview-component-mock', production_persistence_tested: false, data_source: 'mock', detail_meta_source: 'production',
  compile: { babel: compiled.babel_version, target: compiled.target, global_build: false },
  sources: sources.concat(styleSources).map(item => ({ path: item.path, sha256: hash(item.code) })),
  probes: [__filename, path.join(__dirname, 'test_process_widgets.py'), path.join(__dirname, 'custom_control_actions.cjs')].map(file => ({ path: path.relative(root, file), sha256: hash(fs.readFileSync(file)) })),
  assets: [...new Set([...manifest.styles, ...staticScripts, manifest.theme_script])].map(file => ({ path: 'static/' + file, sha256: hash(assets.get(file).bytes) })),
  cases: [], screenshots: [], pagination: [], errors: [], external: [] };
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
const table = () => page.getByRole('table', { name: '零件工艺列表', exact: true });
async function settled() { await table().filter({ has: page.locator('tbody') }).waitFor(); await page.waitForFunction(() => document.querySelector('table[aria-label="零件工艺列表"]').getAttribute('aria-busy') === 'false'); }
async function mount(spec = {}) { await page.evaluate(spec => mountFixture(spec), spec); await settled(); }
async function type(locator, value) { await locator.click(); await locator.press('Meta+A'); await locator.press('Backspace'); await locator.pressSequentially(value, { delay: 4 }); }
async function search(value) { await type(page.getByRole('searchbox', { name: '搜索图号、名称、路线' }), value); await button('搜索').click(); }
async function open(n = 1) { await button('查看 PART-' + String(n).padStart(3, '0')).click(); await page.locator('.process-detail .stepper').waitFor(); }
async function entry(n = 1) { await open(n); await page.getByRole('tab', { name: /工艺路线/ }).click(); await button('录入路线').click(); await page.getByRole('textbox', { name: '路线文字', exact: true }).waitFor(); }
async function preflight() { await button('预检路线').click(); await page.locator('[data-process-preview]').waitFor(); }
async function closeDetail(discard = false) {
  await button('关闭详情').click();
  if (discard) {
    const prompt = page.getByRole('dialog', { name: '放弃未保存的工艺草稿？', exact: true });
    await prompt.waitFor(); await prompt.getByRole('button', { name: '放弃草稿并关闭', exact: true }).click();
  }
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.equal(await page.getByRole('dialog').count(), 0);
}
async function readAllOperations(name, expected) {
  const dialog = page.getByRole('dialog'), grid = dialog.getByRole('table', { name, exact: true });
  const rows = grid.locator('tbody tr'), numbers = grid.locator('tbody tr td:first-child b');
  const size = dialog.getByRole('combobox', { name: '每页条数', exact: true });
  const pager = size.locator('xpath=ancestor::nav');
  assert.equal(await size.inputValue(), '50');
  assert.deepEqual(await size.locator('option').evaluateAll(nodes => nodes.map(node => node.value)), ['20', '50', '100']);
  for (const value of ['20', '100', '50']) {
    await controls.select(size, value);
    assert.equal(await rows.count(), Number(value));
    assert.deepEqual(await numbers.allTextContents(), expected.slice(0, Number(value)));
    assert(await pager.getByText('共 ' + expected.length + ' 项 · 第 1 / ' + Math.ceil(expected.length / Number(value)) + ' 页', { exact: true }).isVisible());
  }
  const sequences = [], pages = [], next = dialog.getByRole('button', { name: '下一页', exact: true });
  const count = Math.ceil(expected.length / 50);
  for (let number = 1; number <= count; number++) {
    assert(await pager.getByText('共 ' + expected.length + ' 项 · 第 ' + number + ' / ' + count + ' 页', { exact: true }).isVisible());
    const values = await numbers.allTextContents(), wanted = expected.slice((number - 1) * 50, number * 50);
    assert.equal(await rows.count(), wanted.length); assert(values.length > 0 && values.length <= 50);
    assert.deepEqual(values, wanted, name + ' page ' + number);
    assert.equal(await dialog.getByRole('button', { name: '上一页', exact: true }).isDisabled(), number === 1);
    sequences.push(...values); pages.push({ number, count: values.length, first: values[0], last: values.at(-1) });
    assert.equal(await next.isDisabled(), number === count);
    if (number < count) await next.click();
  }
  assert.deepEqual(sequences, expected); assert.equal(new Set(sequences).size, expected.length);
  report.pagination.push({ variant, table: name, page_size: 50, next_clicks: count - 1, total: sequences.length, pages, sequences });
}
async function noCommands() { assert.deepEqual(await page.evaluate(() => fixture.commands), []); assert.deepEqual(await page.evaluate(() => fixture.committed), []); }
async function shot(name) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => Array.from(document.querySelectorAll('.modal-bg')).filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden').every(el => getComputedStyle(el).opacity === '1'));
  const geometry = await page.evaluate(() => {
    const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
    const modal = Array.from(document.querySelectorAll('[role="dialog"]')).filter(visible);
    const bounds = el => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }; };
    const controls = Array.from(document.querySelectorAll('button,input,textarea,select')).filter(visible).filter(el => !el.closest('.card-scroll'));
    return { width: innerWidth, height: innerHeight, scroll: document.documentElement.scrollWidth, theme: document.documentElement.dataset.theme,
      dialogs: modal.map(bounds), clipped: controls.filter(el => el.scrollWidth > el.clientWidth + 1 && el.tagName === 'BUTTON').map(el => el.textContent),
      outside: controls.filter(el => { const r = el.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1; }).map(el => el.getAttribute('aria-label') || el.textContent),
      count: controls.length, icons: document.querySelectorAll('button svg').length,
      stepColors: Array.from(document.querySelectorAll('.process-detail .stp[aria-selected="false"] .stp-t')).filter(visible).map(el => ({color:getComputedStyle(el).color,expected:getComputedStyle(el.closest('.modal').querySelector('.modal-h2')).color})),
      modalScroll: modal.map(el => { const body = el.querySelector('.modal-b'); return { width: body.clientWidth, scroll: body.scrollWidth }; }) };
  });
  assert(geometry.scroll <= geometry.width + 1, 'no document horizontal overflow');
  assert(geometry.stepColors.every(row => row.color === row.expected), 'Unselected step labels must use readable theme text');
  assert.deepEqual(geometry.outside, []); assert.deepEqual(geometry.clipped, []); assert(geometry.icons > 8);
  assert(geometry.dialogs.length <= 1, 'only one visible modal');
  for (const r of geometry.dialogs) { assert(r.left >= 0 && r.right <= geometry.width + 1 && r.top >= 0 && r.bottom <= geometry.height + 1); assert(r.width >= 1000, 'centered large detail'); assert(Math.abs((r.left + r.right) / 2 - geometry.width / 2) < 2); }
  for (const s of geometry.modalScroll) assert(s.scroll <= s.width + 1, 'only table shell may scroll horizontally');
  const file = variant + '-' + name + '.png'; await page.screenshot({ path: path.join(output, file) }); report.screenshots.push({ variant, name, file, geometry });
}
async function run(name, test) {
  try { await test(); await noCommands(); report.cases.push({ variant, name, passed: true }); }
  catch (error) { report.cases.push({ variant, name, passed: false, error: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') }); fs.writeFileSync(path.join(output, variant + '-' + name + '-failure.html'), await page.content()); throw error; }
}
async function cases() {
  await run('pagination-selection-search-shared-controls-tristate-sort', async () => {
    await mount(); await page.getByRole('checkbox', { name: '选择 PART-001', exact: true }).check();
    await button('下一页').click(); await button('查看 PART-021').waitFor();
    assert.equal(await page.locator('[data-process-selection-count]').innerText(), '1');
    assert(await page.evaluate(() => fixture.reads.filter(x => x.type === 'list').at(-1).scope.snapshot_ref.startsWith('fixture-list:')));
    await page.getByRole('checkbox', { name: '全选当前页' }).check(); assert.equal(await page.locator('[data-process-selection-count]').innerText(), '21');
    await page.getByRole('checkbox', { name: '全选当前页' }).uncheck(); assert.equal(await page.locator('[data-process-selection-count]').innerText(), '1');
    await search('PART-045'); await button('查看 PART-045').waitFor(); assert.equal(await table().locator('tbody tr').count(), 1);
    assert.equal(await page.locator('[data-process-selection-count]').innerText(), '1');
    const query = await page.evaluate(() => fixture.reads.filter(x => x.type === 'list').at(-1).scope); assert.equal(query.page, 1); assert.equal(query.snapshot_ref, undefined);
    await search(''); await settled();
    const sizes = page.getByRole('combobox', { name: '每页条数' }); await sizes.click(); await page.getByRole('listbox').waitFor();
    await page.getByRole('listbox').getByRole('option', { name: '50 项', exact: true }).click(); await settled(); assert.equal(await table().locator('tbody tr').count(), 45);
    assert.equal(await sizes.inputValue(), '50');
    const defaultRefs = Array.from({ length: 45 }, (_, index) => (index + 1).toString(16).padStart(48, '0'));
    for (const [key, label] of [['business_code', '图号'], ['label', '零件名称'], ['operation_count', '工序数量'], ['stage', '进度']]) {
      for (const dir of ['asc', 'desc', null]) {
        await button(label + '排序').click(); await settled();
        const scope = await page.evaluate(() => fixture.reads.filter(x => x.type === 'list').at(-1).scope);
        assert.deepEqual(scope.sort, dir ? [{ field: key, direction: dir }] : []); assert.equal(scope.direction, undefined);
        assert.equal(await table().getByRole('columnheader').filter({ has: button(label + '排序') }).getAttribute('aria-sort'), dir ? dir === 'asc' ? 'ascending' : 'descending' : 'none');
        const value = ref => { const n = parseInt(ref, 16); return key === 'operation_count' ? n % 2 ? 3 : 0 : key === 'stage' ? n % 2 ? 'source' : 'route' : key === 'label' ? '零件 ' + n : ref; };
        const expected = defaultRefs.slice().sort((a, b) => !dir || value(a) === value(b) ? a < b ? -1 : a > b ? 1 : 0 : (value(a) < value(b) ? -1 : 1) * (dir === 'desc' ? -1 : 1));
        assert.deepEqual(await table().locator('tbody tr').evaluateAll(rows => rows.map(row => row.dataset.processRef)), expected);
      }
    }
    await page.getByRole('tab', { name: /^待导入路线/ }).click(); await settled(); assert.equal(await table().locator('tbody tr').count(), 22);
    await page.getByRole('tab', { name: /^已就绪/ }).click(); await settled(); assert(await page.getByText('当前筛选没有匹配的零件', { exact: true }).isVisible());
    await page.getByRole('tab', { name: /^全部/ }).click(); await settled(); await button('清除所有选择').click();
    assert.equal(await page.locator('[data-process-selection-count]').innerText(), '0'); await shot('list');
    assert((await page.evaluate(() => fixture.keys.filter(x => x.label === '搜索图号、名称、路线').map(x => x.key))).includes('P'));
  });
  await run('long-detail-unconfirmed-source-zero-vs-null', async () => {
    await mount({ long: true }); await open(); assert.equal(await page.getByRole('tab', { selected: true, name: /工艺路线/ }).count(), 1);
    assert(await page.getByRole('table', { name: '路线工序明细', exact: true }).isVisible());
    assert.equal(await page.getByRole('table', { name: '归属明细', exact: true }).count(), 0);
    await page.getByRole('tab', { name: /^2 归属/ }).click();
    assert(await page.getByRole('group', { name: '工序 5 归属' }).getByRole('button', { name: /^自制/ }).isDisabled());
    await page.getByRole('tab', { name: /工时定额/ }).click();
    assert.equal(await page.getByRole('spinbutton', { name: '工序 5 换型工时', exact: true }).inputValue(), '0');
    assert.equal(await page.getByRole('spinbutton', { name: '工序 10 换型工时', exact: true }).count(), 0);
    assert.equal(await page.getByRole('spinbutton', { name: '工序 15 换型工时', exact: true }).inputValue(), '');
    assert(await page.getByRole('spinbutton', { name: '工序 5 换型工时' }).isDisabled());
    assert(!(await page.getByRole('spinbutton', { name: '工序 5 换型工时' }).locator('..').innerText()).includes('请复核'));
    assert.equal(await page.getByRole('spinbutton', { name: '工序 10 外协周期', exact: true }).inputValue(), '');
    assert.equal(await page.getByRole('spinbutton', { name: '外协组 10 至 10 总周期', exact: true }).inputValue(), '');
    assert((await page.getByRole('dialog').innerText()).includes('外协周期填的值不合法，系统不会用默认值顶替。'));
    assert((await page.getByRole('table', { name: '外协组原记录', exact: true }).innerText()).includes('合并周期填的值不合法，系统不会用默认值顶替。'));
    assert(await page.getByRole('table', { name: '外协组原记录', exact: true }).getByRole('cell', { name: '保留原外协规则', exact: true }).isVisible()); await shot('hours');
    await page.getByRole('tab', { name: /工艺路线/ }).click(); await shot('route-long');
    for (let i = 0; i < 12; i++) { await page.keyboard.press('Tab'); assert(await page.evaluate(() => document.querySelector('.process-detail [role="dialog"]').contains(document.activeElement))); }
    await page.keyboard.press('Escape'); assert.equal(await page.getByRole('dialog').count(), 0);
  });
  await run('text-preview-real-click-no-save-edit-invalidates', async () => {
    await mount(); await entry(); const input = page.getByRole('textbox', { name: '路线文字', exact: true });
    await type(input, '5Turn10Unknown'); await preflight();
    const call = await page.evaluate(() => fixture.reads.filter(x => x.type === 'preview').at(-1));
    assert.deepEqual(call.body, { mode: 'text', route_raw: '5Turn10Unknown', snapshot_ref: 'fixture-detail' });
    assert(await page.getByRole('button', { name: /^确认保存路线/ }).isDisabled());
    assert((await page.locator('[data-process-preview]').innerText()).includes('尚未保存')); assert((await page.locator('[data-process-preview]').innerText()).includes('same_sequence_changed') === false);
    assert(!(await page.locator('[data-process-preview]').innerText()).includes('unknown_type'));
    assert(await page.getByText(/未知工种仅预检/).isVisible()); await shot('text-preview');
    await input.click(); await input.pressSequentially('X'); assert.equal(await page.locator('[data-process-preview]').count(), 0);
    await button('取消').click(); assert.equal(await page.getByRole('dialog').count(), 1);
    assert.equal(await page.getByRole('textbox', { name: '路线文字', exact: true }).count(), 0);
    await button('录入路线').click(); assert.equal(await input.inputValue(), '5Turn10UnknownX');
    assert.equal(await page.locator('[data-process-preview]').count(), 0);
    await button('取消').click(); await closeDetail(true);
  });
  await run('rows-preview-invalid-integer-duplicate-mode-drafts', async () => {
    await mount(); await entry(2); const input = page.getByRole('textbox', { name: '路线文字', exact: true }); await type(input, 'TextDraft');
    await page.getByRole('tab', { name: '逐行表格', exact: true }).click();
    const seq = page.getByRole('textbox', { name: '第 1 行工序号', exact: true }), name = page.getByRole('combobox', { name: '第 1 行工种', exact: true });
    // The op_type catalog is read once on entry and only suggests: free text still reaches the server preflight.
    await page.waitForFunction(() => document.querySelectorAll('.process-route-entry datalist option').length === 3);
    assert.deepEqual(await page.evaluate(() => Array.from(document.querySelectorAll('.process-route-entry datalist option')).map(node => node.value)), ['Turn', 'Polish', 'Grind']);
    assert.equal(await page.evaluate(() => fixture.reads.filter(x => x.type === 'choices').length), 1);
    assert.deepEqual(await page.evaluate(() => fixture.reads.find(x => x.type === 'choices').scope), { query: '', page: 1, size: 200 });
    assert.equal(await page.evaluate(() => document.querySelector('.process-route-entry datalist').id), await name.getAttribute('list'));
    await type(seq, '5.5'); await type(name, 'Turn'); await button('预检路线').click(); await page.getByText('第 1 行工序号必须是正整数。', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => fixture.reads.filter(x => x.type === 'preview').length), 0);
    await type(seq, '5'); await button('新增工序').click(); await type(page.getByRole('textbox', { name: '第 2 行工序号', exact: true }), '5');
    await type(page.getByRole('combobox', { name: '第 2 行工种', exact: true }), 'Unknown'); await preflight();
    assert(await page.getByText(/工序号重复/).isVisible()); assert((await page.locator('[data-process-preview]').innerText()).includes('输入存在待处理问题'));
    await type(page.getByRole('textbox', { name: '第 2 行工序号', exact: true }), '10'); await preflight();
    assert.deepEqual(await page.evaluate(() => fixture.reads.filter(x => x.type === 'preview').at(-1).body), { mode: 'rows', rows: [{ seq: 5, op_type_name: 'Turn' }, { seq: 10, op_type_name: 'Unknown' }], snapshot_ref: 'fixture-detail' });
    await shot('rows-preview'); await page.getByRole('tab', { name: '整条录入', exact: true }).click(); assert.equal(await input.inputValue(), 'TextDraft');
    assert.equal(await page.locator('[data-process-preview]').count(), 0); await page.getByRole('tab', { name: '逐行表格', exact: true }).click(); assert.equal(await name.inputValue(), 'Turn');
    await button('删除第 1 行').click(); assert.equal(await name.inputValue(), 'Unknown');
    await page.keyboard.press('Escape'); assert.equal(await page.getByRole('dialog').count(), 1);
    await button('录入路线').click(); assert.equal(await name.inputValue(), 'Unknown');
    await button('取消').click(); await closeDetail(true);
  });
  await run('list-fail-empty-retry-malformed-stale-page', async () => {
    await mount({ failList: true }); assert(await page.getByText('Mock 列表读取失败', { exact: true }).isVisible());
    await page.evaluate(() => { fixture.spec.failList = false; fixture.spec.empty = true; }); await button('刷新列表').click(); await settled(); assert(await page.getByText('暂无零件工艺', { exact: true }).isVisible());
    await page.evaluate(() => { fixture.spec.empty = false; fixture.spec.badList = true; }); await button('刷新工艺列表').click(); await settled(); assert(await page.getByText(/读到的工艺列表不完整/).isVisible());
    await page.evaluate(() => { fixture.spec.badList = false; fixture.spec.stalePage = true; }); await button('刷新列表').click(); await settled();
    await button('下一页').click(); await settled(); assert(await page.getByText(/翻页位置已失效/).isVisible());
    await page.evaluate(() => fixture.spec.stalePage = false); await button('刷新列表').click(); await button('查看 PART-001').waitFor();
  });
  await run('detail-preview-errors-retry-capability-fail-closed', async () => {
    await mount({ demoDetail: true }); await button('查看 PART-001').click(); await page.getByText('未取得原零件的生产详情，不能使用样例替代。', { exact: true }).waitFor();
    assert.equal(await page.locator('.process-detail .stepper').count(), 0); await noCommands(); await button('关闭详情').click();
    await mount({ failDetail: true }); await button('查看 PART-001').click(); await page.getByText('Mock 详情读取失败', { exact: true }).waitFor();
    await page.evaluate(() => { fixture.spec.failDetail = false; fixture.spec.badDetail = true; }); await button('刷新详情').click(); await page.getByText('返回的不是原零件记录，不能继续使用同图号的新零件。', { exact: true }).waitFor();
    assert.equal(await page.locator('.process-detail .stepper').count(), 0);
    await page.evaluate(() => { fixture.spec.badDetail = false; fixture.spec.failPreview = true; }); await button('刷新详情').click(); await page.locator('.process-detail .stepper').waitFor();
    await page.getByRole('tab', { name: /工艺路线/ }).click(); await button('录入路线').click(); await button('预检路线').click(); await page.getByText('Mock 预检快照失效', { exact: true }).waitFor();
    await page.evaluate(() => { fixture.spec.failPreview = false; fixture.spec.badPreview = true; }); await button('重试预检').click(); await page.getByText(/读到的路线预检结果不完整或不是这个零件/).waitFor();
    await page.evaluate(() => fixture.spec.badPreview = false); await button('重试预检').click(); await page.locator('[data-process-preview]').waitFor();
    await button('取消').click(); await closeDetail();
    await mount({ capabilities: { route_preview: false } }); await open(2); assert(await page.getByRole('button', { name: /^录入路线/ }).isDisabled()); await button('关闭详情').click();
    await mount({ disconnected:true, capabilities: { create: true, delete: true, stage_confirm: true, import: true, export: true } });
    for (const label of ['新增零件', '批量删除', '导入工艺路线', '导出工艺路线', '导入工时定额', '导出工时定额']) assert(await page.getByRole('button', { name: new RegExp('^' + label) }).isDisabled());
    await entry(); await preflight(); assert(await page.getByRole('button', { name: /^确认保存路线/ }).isDisabled());
  });
  await run('old-list-detail-preview-ignored-after-abort', async () => {
    await mount(); await search('SLOW'); await page.waitForFunction(() => !!fixture.holds.list);
    await search('PART-045'); await button('查看 PART-045').waitFor();
    await page.evaluate(() => fixture.holds.list()); await page.waitForFunction(() => fixture.settled.includes(fixture.reads.find(x => x.type === 'list' && x.scope.query === 'SLOW').id));
    assert.equal(await table().locator('tbody tr').count(), 1); assert(await page.evaluate(() => fixture.aborted.includes(fixture.reads.find(x => x.type === 'list' && x.scope.query === 'SLOW').id)));
    await mount({ slowDetail: true }); await button('查看 PART-001').click(); await page.waitForFunction(() => !!fixture.holds.detail); await button('关闭详情').click();
    await page.evaluate(() => { fixture.spec.slowDetail = false; fixture.holds.detail(); }); await open(2); assert(await page.getByRole('dialog', { name: 'PART-002 · 零件 2', exact: true }).isVisible()); await button('关闭详情').click();
    await entry(2); const input = page.getByRole('textbox', { name: '路线文字', exact: true }); await type(input, 'SLOW'); await button('预检路线').click(); await page.waitForFunction(() => !!fixture.holds.preview);
    await type(input, 'FAST'); await preflight(); await page.evaluate(() => fixture.holds.preview());
    await page.waitForFunction(() => fixture.settled.includes(fixture.reads.find(x => x.type === 'preview' && x.body.route_raw === 'SLOW').id));
    assert((await page.locator('[data-process-preview]').innerText()).includes('FAST')); assert(!(await page.locator('[data-process-preview]').innerText()).includes('SLOW'));
    assert(await page.evaluate(() => fixture.aborted.includes(fixture.reads.find(x => x.type === 'preview' && x.body.route_raw === 'SLOW').id)));
    await type(input, 'SLOW'); await button('预检路线').click(); await page.waitForFunction(() => fixture.reads.filter(x => x.type === 'preview' && x.body.route_raw === 'SLOW').length === 2);
    await button('取消').click(); await page.evaluate(() => fixture.holds.preview()); assert.equal(await page.locator('[data-process-preview]').count(), 0); assert.equal(await page.getByRole('dialog').count(), 1);
  });
  await run('disabled-mid-request-and-cancel-no-command', async () => {
    await mount(); await entry(2); await type(page.getByRole('textbox', { name: '路线文字', exact: true }), 'SLOW'); await button('预检路线').click(); await page.waitForFunction(() => !!fixture.holds.preview);
    await page.evaluate(() => fixture.setDisabled(true)); await page.waitForFunction(() => document.querySelector('textarea.re-text').disabled);
    await page.evaluate(() => fixture.holds.preview()); assert.equal(await page.locator('[data-process-preview]').count(), 0);
    assert(await button('预检路线').isDisabled()); await button('取消').click(); await closeDetail(true);
    assert(await button('查看 PART-001').isDisabled());
  });
  await run('contract-rejects-guessed-confirmation-and-nonfinite-values', async () => {
    const checked = await page.evaluate(() => {
      const bad = [], accept = change => { const p = detailPart(1); change(p); try { APSProcessContract.detail(envelope(p), ref(1)); bad.push(false); } catch (error) { bad.push(true); } };
      accept(p => p.workflow.ready = true); accept(p => p.workflow.source.state = 'confirmed'); accept(p => p.operations[0].setup_hours = Infinity);
      accept(p => p.operations[0].unit_hours = '0'); accept(p => p.operations.push(p.operations[0])); accept(p => p.fields.route_raw = undefined);
      const zero = APSProcessContract.detail(envelope(detailPart(1)), ref(1)).data.operations[0].setup_hours;
      const d = previewData(ref(1), { mode: 'text', route_raw: '' }); d.can_confirm_route = true;
      try { APSProcessContract.preview(envelope(d), ref(1), { mode: 'text' }); bad.push(false); } catch (error) { bad.push(true); }
      return { bad, zero };
    });
    assert(checked.bad.every(Boolean)); assert.equal(checked.zero, 0);
  });
  await run('2000-operation-detail-no-truncation', async () => {
    const start = Date.now(); await mount({ operationCount: 2000 }); await open();
    const expected = Array.from({ length: 2000 }, (_, index) => String((index + 1) * 5));
    for (const [stage, name] of [[/^1 工艺路线/, '路线工序明细'], [/^2 归属/, '归属明细'], [/^3 工时定额/, '工时定额明细']]) {
      await page.getByRole('tab', { name: stage }).click(); await readAllOperations(name, expected);
      const last = page.getByRole('table', { name, exact: true }).locator('tbody tr').last();
      await last.scrollIntoViewIfNeeded(); assert((await last.innerText()).includes('10000'));
    }
    report.cases.push({ variant, name: '2000-operation-render-timing', elapsed_ms: Date.now() - start, passed: true });
    await closeDetail();
  });
  await run('int64-sequences-preserved-all-surfaces-and-rows-blocked', async () => {
    await mount({ largeSequence: true }); await open();
    const ops = page.getByRole('table', { name: '路线工序明细', exact: true }); assert.equal(await ops.locator('tbody tr').count(), 4);
    assert((await ops.innerText()).includes('9223372036854775807')); assert((await ops.innerText()).includes('DeletedOriginal'));
    assert((await ops.innerText()).includes('已停用工序')); assert(!(await ops.innerText()).includes('deleted'));
    const groups = page.getByRole('table', { name: '外协组原记录', exact: true }); assert((await groups.innerText()).includes('9007199254740992 至 9223372036854775807'));
    await page.getByRole('tab', { name: /工艺路线/ }).click(); await button('录入路线').click(); await preflight();
    const rendered = await page.locator('[data-process-preview]').innerText();
    for (const value of ['9223372036854775807', '9223372036854775806', '9007199254740992']) assert(rendered.includes(value));
    assert(!rendered.includes('9223372036854776000'));
    await page.getByRole('tab', { name: '逐行表格', exact: true }).click();
    assert.equal(await page.getByRole('textbox', { name: '第 1 行工序号', exact: true }).inputValue(), '9223372036854775807');
    assert.equal(await page.getByRole('combobox', { name: '第 1 行工种', exact: true }).inputValue(), 'Turn', 'original operation name, not renamed master label');
    assert.equal(await page.getByRole('table', { name: '逐行路线录入' }).locator('tbody tr').count(), 3, 'deleted record not resurrected into draft');
    await button('预检路线').click(); await page.getByText(/行工序号太大，请改用整条文字预检/).waitFor();
    assert.equal(await page.evaluate(() => fixture.reads.filter(x => x.type === 'preview').length), 1);
    assert.equal(await page.getByRole('textbox', { name: '第 1 行工序号', exact: true }).inputValue(), '9223372036854775807');
    const check = await page.evaluate(() => {
      const checks = [], bad = [1.5, 9007199254740992, '', null, undefined, true, Infinity];
      for (const value of bad) { const d = detailPart(1); d.operations[0].sequence = value; try { APSProcessContract.detail(envelope(d), ref(1)); checks.push(false); } catch (_) { checks.push(true); } }
      for (const value of [1, Number.MAX_SAFE_INTEGER, '9007199254740992', '9223372036854775807']) {
        const d = detailPart(1); d.operations[0].sequence = value; checks.push(APSProcessContract.detail(envelope(d), ref(1)).data.operations[0].sequence === value);
      }
      const body = APSProcessContract.previewBody('rows', '', [{ seq: '9007199254740991', op_type_name: 'Turn' }], 'snapshot');
      for (const value of [0, -1, 'bad', '01', '+1', '1e3', '1.0', '9223372036854775808']) {
        const d = previewData(ref(1), { mode: 'text', route_raw: '5Turn' }); d.operations[0].sequence = value;
        try { APSProcessContract.preview(envelope(d), ref(1), { mode: 'text' }); checks.push(false); } catch (_) { checks.push(true); }
      }
      return { checks, value: body.rows[0].seq };
    });
    assert(check.checks.every(Boolean)); assert.equal(check.value, Number.MAX_SAFE_INTEGER);
    await shot('int64-rows-rejected'); await button('取消').click();
    assert.equal(await page.evaluate(() => WorkbenchGuards.hasDirty()), false, 'Changing display mode without editing facts is not a dirty draft');
    await closeDetail();
  });
  await run('refresh-stale-detail-keeps-draft-and-rebinds-snapshot', async () => {
    await mount({ failPreview: true }); await entry(2); const input = page.getByRole('textbox', { name: '路线文字', exact: true });
    await type(input, '5Turn10Unknown'); await button('预检路线').click(); await page.getByText('Mock 预检快照失效', { exact: true }).waitFor();
    await page.evaluate(() => { fixture.spec.failPreview = false; fixture.spec.detailSnapshot = 'fresh-detail'; });
    await button('刷新详情并保留草稿').click(); await page.getByText('已刷新详情，录入内容保留；请核对后重新预检。', { exact: true }).waitFor();
    assert.equal(await input.inputValue(), '5Turn10Unknown'); assert(await button('预检路线').isDisabled());
    await button('采用最新资料').click();
    assert.equal(await input.inputValue(), '5Turn10Unknown'); await preflight();
    assert.equal(await page.evaluate(() => fixture.reads.filter(x => x.type === 'preview').at(-1).body.snapshot_ref), 'fresh-detail');
    assert(await page.getByRole('button', { name: /^确认保存路线/ }).isDisabled());
    await button('取消').click(); await closeDetail(true);
  });
  await run('bad-stored-sequences-stay-visible-zero-setup-normal', async () => {
    await mount({ invalidStored: true }); await open();
    const ops = page.getByRole('table', { name: '路线工序明细', exact: true });
    assert.equal(await ops.locator('tbody tr').count(), 3); assert((await ops.innerText()).includes('原始坏序号TEXT'));
    assert((await ops.innerText()).includes('-5')); assert((await ops.innerText()).includes('原工序号为0，请核对'));
    assert((await page.getByRole('table', { name: '外协组原记录' }).innerText()).includes('bad-start 至 -10'));
    await page.getByRole('tab', { name: /工时定额/ }).click();
    const setup = page.getByRole('spinbutton', { name: '工序 0 换型工时', exact: true }), unit = page.getByRole('spinbutton', { name: '工序 0 单件工时', exact: true });
    assert.equal(await setup.inputValue(), '0'); assert(!(await setup.locator('..').innerText()).includes('请复核'));
    assert.equal(await unit.inputValue(), '0'); assert((await unit.locator('..').innerText()).includes('0 · 请复核'));
    await button('关闭详情').click();
  });
  await run('chinese-record-labels-do-not-imply-human-confirmation', async () => {
    await mount(); await open();
    assert(await page.getByRole('cell', { name: /有效.*未人工确认/ }).first().isVisible());
    assert(!(await page.getByRole('table', { name: '路线工序明细', exact: true }).innerText()).includes('active'));
    await page.getByRole('tab', { name: /工艺路线/ }).click(); assert(await page.getByText('已解析', { exact: true }).isVisible());
    await button('关闭详情').click(); await open(2); assert(await page.getByText('未解析', { exact: true }).isVisible()); await button('关闭详情').click();
    await mount({ unknownParsed: true }); await open(); await page.getByRole('tab', { name: /工艺路线/ }).click();
    assert(await page.getByText('原标记不明确', { exact: true }).isVisible()); assert.equal(await page.getByText('legacy-unknown-flag', { exact: true }).count(), 0);
    await button('关闭详情').click();
  });
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    assert(browser.version().startsWith('109.'), 'Actual Chromium 109 required'); report.browser = browser.version();
    const origin = 'http://127.0.0.1:' + server.address().port;
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(15000); variant = viewport.width + 'x' + viewport.height + '-' + theme;
      page.on('pageerror', error => report.errors.push(error.message)); page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin); await cases(); await context.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'process-result.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length, screenshots: report.screenshots.length, errors: report.errors, external: report.external, scope: report.scope }));
})().catch(error => { console.error(error); process.exitCode = 1; });
