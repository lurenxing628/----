/* Isolated current-source components with mock APIs; never a product build. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const files = ['WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'ResourceTableFilterModel.js', 'ResourceTableFilter.jsx', 'ResourceTableHeader.jsx',
  'ResourceDetailRelations.jsx', 'ResourceForms.jsx', 'ResourceTables.jsx', 'ResourceMaterialContract.js', 'ResourceMaterialPreview.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx',
  'ProcessContract.js', 'ProcessReadView.js', 'ProcessActionContract.js', 'ProcessActionPreview.jsx', 'ProcessCollectionActions.jsx', 'ProcessFileContract.js', 'ProcessFilePreview.jsx', 'ProcessFileActions.jsx', 'ProcessControls.jsx', 'ProcessStageEditor.jsx', 'ProcessOpTypeCreate.jsx',
  'ProcessSourceEditor.jsx', 'ProcessHoursEditor.jsx', 'ProcessRouteEntry.jsx', 'ProcessDetail.jsx', 'ProcessWorkspace.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const assets = new Map(manifest.files.map(item => ['/static/' + item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const fixture = `
const R=n=>n.toString(16).padStart(48,'0'), K=n=>n.toString(16).padStart(64,'0'), T='s'.repeat(32);
const stamp=state=>({state,confirmed_at:null,confirmed_by:null});
const caps={route_preview:true,create:true,delete:true,stage_confirm:true,import:false,export:false};
const ctx={write_token:'t'.repeat(32),capabilities:{'process.create':true},blocked_reasons:[]};
const env=data=>({ok:true,schema_version:1,data,meta:{source:'production',time_basis:'factory_local',snapshot_ref:T,request_ref:'mock',as_of:'2026-09-09T12:00:00'},warnings:[]});
function part(n) {return {ref:R(n),business_code:'PART-'+String(n).padStart(3,'0'),label:n===1?'':n===2?'0':'零件 '+n,status:null,
  fields:{route_raw:null,route_parsed:'no',remark:null},relationships:{operation_count:0,batch_count:0,internal_count:0,external_count:0,unclassified_count:0},issues:[],write_context:null,
  workflow:{origin:'managed',stage:'route',ready:false,route:stamp('missing'),source:stamp('locked'),hours:stamp('locked')}};}
let f,viewRoot,mountNumber=0;
function adapter() { return {
  list:async(kind,scope)=>{f.reads.push({type:'list',kind,scope});let rows=f.rows.slice();
    if(scope.query)rows=rows.filter(r=>r.business_code.includes(scope.query));
    if(scope.stage)rows=rows.filter(r=>r.workflow.stage===scope.stage);
    for(const [key,rule] of Object.entries(scope.column_filters||{}))rows=rows.filter(r=>rule.values.includes(K(parseInt(r.ref,16)))===(rule.mode==='include'));
    const sort=APSProcessContract.ordering(scope);for(const item of sort.slice().reverse()) rows.sort((a,b)=>String(a[item.field]||'').localeCompare(String(b[item.field]||''))*(item.direction==='desc'?-1:1));
    return env({entities:rows.slice((scope.page-1)*scope.size,scope.page*scope.size),page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.max(1,Math.ceil(rows.length/scope.size)),sort},metrics:{counts:{total:rows.length,route:rows.length,source:0,hours:0,ready:0}},capabilities:{...caps,import:!!f.spec.files,export:!!f.spec.files},create_context:ctx});},
  facets:async(kind,query)=>{f.reads.push({type:'facets',kind,query});const options=f.rows.map(r=>({key:K(parseInt(r.ref,16)),label:r.label,count:1})).filter(r=>!query.query||r.label.includes(query.query));return env({column:query.column,basis:'toolbar_scope',row_count:f.rows.length,options:options.slice((query.page-1)*query.size,query.page*query.size),page:{number:query.page,size:query.size,total:options.length,pages:Math.max(1,Math.ceil(options.length/query.size))}});},
  facetSelection:async(kind,query)=>{f.reads.push({type:'selection',kind,query});const keys=f.rows.filter(r=>!query.query||r.label.includes(query.query)).map(r=>K(parseInt(r.ref,16)));return env({column:query.column,basis:'toolbar_scope',total:keys.length,keys});},
  detail:async(kind,ref)=>{f.reads.push({type:'detail',kind,ref});if(f.spec.missingCreated)throw APSResourceContract.failure('原零件已不存在，未打开同图号的新零件。');const row=f.rows.find(row=>row.ref===ref);if(!row)throw APSResourceContract.failure('原零件已不存在。');return env({...row,capabilities:caps,operations:[],external_groups:[]});},
  bulkPreview:async body=>{f.reads.push({type:'bulk',body});f.previewRefs=body.refs.slice();const rows=body.refs.map((ref,i)=>({row:i+1,business_code:'PART-'+String(parseInt(ref,16)).padStart(3,'0'),entity_ref:ref,action:'delete',result:f.spec.rejectBulk&&i===1?'rejected':'delete',before:{business_code:'PART-'+parseInt(ref,16),label:'零件',route_raw:null,remark:null,operation_count:0},after:null,changes:{},errors:f.spec.rejectBulk&&i===1?[{message:'该零件已被批次使用，不能删除。'}]:[],requires_confirmation:false,reference_count:f.spec.rejectBulk&&i===1?1:0}));
    return env({preview_ref:'p'.repeat(32),expires_at:new Date(Date.now()+(f.spec.expired?-1000:60000)).toISOString(),operation:'part.bulk_delete',commit_policy:'atomic',can_confirm:!f.spec.rejectBulk,summary:{new:0,update:0,unchanged:0,delete:rows.length-(f.spec.rejectBulk?1:0),rejected:f.spec.rejectBulk?1:0},rows,scope:body.scope,columns:Object.entries(APSProcessActions.fields).map(([key,label])=>({key,label})),write_context:{write_token:'t'.repeat(32),capabilities:{'process_bulk.confirm':true},blocked_reasons:[]}});},
  filePreview:async(kind,mode,body)=>{f.reads.push({type:'file',kind,mode,body:body instanceof FormData?Object.fromEntries([...body.entries()].map(([key,value])=>[key,key==='file'?value.name:value])):body});
    if(mode==='export')return env({kind,export_ref:'e'.repeat(32),selection:body.selection,scope:body.scope,target_ref:body.target_ref||null,row_count:kind==='hours'?130:65,part_count:65,format:body.format,columns:[{key:'business_code',label:'图号'}],expires_at:new Date(Date.now()+60000).toISOString()});
    const columns=kind==='route'?[{key:'business_code',label:'图号'},{key:'route_raw',label:'工艺路线字符串'}]:[{key:'business_code',label:'图号'},{key:'unit_hours',label:'单件工时'}];
    const row={row:2,business_code:'PART-001',entity_ref:R(1),action:'update',result:'update',before:kind==='route'?{business_code:'PART-001',route_raw:'5Turn'}:{business_code:'PART-001',unit_hours:1},after:kind==='route'?{business_code:'PART-001',route_raw:'5Polish'}:{business_code:'PART-001',unit_hours:0},changes:kind==='route'?{route_raw:{before:'5Turn',after:'5Polish'}}:{unit_hours:{before:1,after:0}},errors:[],requires_confirmation:true,reference_count:0,route_summary:kind==='route'?{counts:{operations:1,recognized:1,unknown:0},diagnostics:[],can_confirm_route:true}:null,...(kind==='hours'?{sequence:5}:{})};
    const group={ref:R(450),part_ref:R(1),business_code:'PART-001',start_sequence:5,end_sequence:10,merge_mode:'merged',total_days:6.75,supplier_ref:R(300),supplier_label:'原供应商',remark:'必须保留核对的原备注',issues:[]};
    return env({preview_ref:'p'.repeat(32),expires_at:new Date(Date.now()+60000).toISOString(),operation:'process_'+kind+'_import.confirm',kind,commit_policy:'atomic',can_confirm:true,summary:{new:0,update:1,unchanged:0,delete:0,rejected:0},rows:[row],columns,scope:{},format:body.get('format'),mode:'upsert',template_version:1,file_sha256:'a'.repeat(64),instructions:'空白不补零；确认前完整核对。',zero_review_required:kind==='hours',affected_groups:kind==='route'?[group]:[],...(kind==='hours'?{skipped_count:0,skipped_refs:[],skipped_rows:[]}:{}),write_context:{write_token:'t'.repeat(32),capabilities:{['process_'+kind+'_import.confirm']:true},blocked_reasons:[]}});},
  fileDownload:async(kind,template,query)=>{f.reads.push({type:'download',kind,template,query});return {blob:new Blob(['图号,名称\\nPART-001,0\\n'],{type:'text/csv'}),contentType:'text/csv',disposition:'attachment; filename="process-'+kind+'.csv"'};},
  command:async(kind,action,ref,body)=>{f.commands.push({kind,action,ref,body});if(kind==='process'&&action==='create'){const row={...part(900),business_code:body.input.business_code,label:body.input.label};f.rows.push(row);f.receipt={ok:true,result:'committed',receipt_ref:'r'.repeat(32),replayed:false,warnings:[],data:{entity_ref:row.ref,business_code:row.business_code,workflow:row.workflow}};}
    else if(kind==='process_route_import'||kind==='process_hours_import'){f.receipt={ok:true,result:'committed',receipt_ref:'r'.repeat(32),replayed:false,warnings:[],data:{kind:kind==='process_route_import'?'route':'hours',rows:[{row:2,entity_ref:R(1),business_code:'PART-001',result:'committed',...(kind==='process_hours_import'?{sequence:5}:{})}],summary:{new:0,update:1,unchanged:0,delete:0,rejected:0},affected_refs:[R(1)],...(kind==='process_hours_import'?{skipped_count:0,skipped_refs:[],skipped_rows:[]}:{} )}};}
    else {const rows=f.previewRefs.map(entity_ref=>({entity_ref,result:'committed'}));f.rows=f.rows.filter(row=>!f.previewRefs.includes(row.ref));f.receipt={ok:true,result:'committed',receipt_ref:'r'.repeat(32),replayed:false,warnings:[],data:{deleted_count:rows.length,rows}};}
    if(f.spec.pending)throw Object.assign(new Error('Mock 连接中断'),{committed:'unknown'});if(f.spec.partial)return {...f.receipt,result:'partial'};return f.receipt;},
  lookup:async key=>{f.lookups.push(key);if(f.spec.notRecorded)return {ok:true,state:'not_recorded',receipt:null,may_be_in_flight:true};return f.receipt;},
  readPending:()=>f.pending,savePending:intent=>{f.pending={kind:intent.kind,action:intent.action,ref:intent.ref,request_key:intent.request_key};},clearPending:()=>{f.pending=null;}
};}
function render(){if(viewRoot)viewRoot.unmount();viewRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));viewRoot.render(React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),React.createElement('section',{className:'plana',style:{padding:20}},React.createElement(ProcessWorkspace,{key:++mountNumber,adapter:f.adapter,onCommitted:r=>f.committed.push(r)}))));}
window.mountFixture=spec=>{f=window.fixture={spec,rows:Array.from({length:65},(_,i)=>part(i+1)),reads:[],commands:[],lookups:[],committed:[],pending:spec.restore||null,receipt:spec.receipt||null};f.adapter=adapter();render();};
window.remountFixture=()=>{f.adapter=adapter();render();};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="/static/' + manifest.icon + '">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') + '</head><body class="aps-workbench"><div id="fixture-root"></div>' +
  staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') + '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); }
  else if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); }
  else if (assets.has(name)) { const item = assets.get(name); res.setHeader('Content-Type', item.mime); res.end(item.bytes); }
  else { res.writeHead(404); res.end(); }
});
const report = { scope: 'isolated-process-actions-mock', global_build: false, production_persistence_tested: false, cases: [], screenshots: [], errors: [], external: [], sources: sources.map(source => ({ path: source.path, sha256: crypto.createHash('sha256').update(source.code).digest('hex') })) };
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
const table = () => page.getByRole('table', { name: '零件工艺列表', exact: true });
async function settle() { await page.waitForFunction(() => document.querySelector('[aria-label="零件工艺列表"]')?.getAttribute('aria-busy') === 'false'); }
async function mount(spec = {}) { await page.evaluate(spec => mountFixture(spec), spec); await settle(); }
async function run(name, body) { await body(); report.cases.push({ variant, name, passed: true }); }
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: true }); report.screenshots.push(file); }
async function fillCreate(code = 'NEW-01') { await button('新增零件').click(); await page.getByRole('textbox', { name: '图号', exact: true }).fill(code); await page.getByRole('textbox', { name: '零件名称', exact: true }).fill('新增零件'); }
async function cases() {
  await run('shared-header-sort-resize-and-default-page', async () => {
    await mount(); assert.equal(await table().locator('tbody tr').count(), 20);
    await button('零件名称排序').click(); await settle(); await button('工序数量排序').click(); await settle();
    assert.deepEqual(await page.evaluate(() => fixture.reads.filter(r => r.type === 'list').at(-1).scope.sort), [{ field: 'label', direction: 'asc' }, { field: 'operation_count', direction: 'asc' }]);
    await button('零件名称排序').click(); await settle(); await button('零件名称排序').click(); await settle();
    assert.deepEqual(await page.evaluate(() => fixture.reads.filter(r => r.type === 'list').at(-1).scope.sort), [{ field: 'operation_count', direction: 'asc' }]);
    const handle = page.getByRole('separator', { name: '调整图号列宽', exact: true }); const before = await handle.getAttribute('aria-valuenow');
    await handle.focus(); await handle.press('ArrowRight'); await page.waitForFunction(before => Number(document.querySelector('[aria-label="调整图号列宽"]').getAttribute('aria-valuenow')) > Number(before), before);
  });
  await run('facet-other-columns-kept-zero-empty-and-50-options', async () => {
    await mount(); await button('筛选图号').click(); const popup = page.locator('[data-wb-table-filter]'); await popup.getByRole('checkbox', { name: '（空白）', exact: true }).uncheck(); await settle();
    assert(await popup.isVisible()); assert.equal(await popup.locator('[data-facet-key]').count(), 50); await popup.getByRole('checkbox', { name: '0', exact: true }).waitFor();
    await popup.getByRole('button', { name: '关闭列筛选', exact: true }).click(); await button('筛选零件名称').click();
    await page.waitForFunction(() => fixture.reads.some(r => r.type === 'facets' && r.query.column === 'label'));
    const query = await page.evaluate(() => fixture.reads.filter(r => r.type === 'facets' && r.query.column === 'label').at(-1).query);
    assert.equal(query.size, 50); assert.equal(query.scope.column_filters.business_code.values.length, 1); assert(!query.scope.column_filters.label);
    await popup.getByRole('textbox', { name: '搜索零件名称列值', exact: true }).fill('零件'); await popup.getByRole('checkbox', { name: '全选', exact: true }).waitFor();
    await page.waitForFunction(() => fixture.reads.some(r => r.type === 'selection' && r.query.column === 'label' && r.query.query === '零件'));
    const selection = await page.evaluate(() => fixture.reads.filter(r => r.type === 'selection' && r.query.column === 'label').at(-1).query);
    assert.deepEqual(selection.scope.column_filters, query.scope.column_filters); assert.equal(selection.size, 50);
    await shot('header'); await page.keyboard.press('Escape'); assert.equal(await popup.count(), 0);
  });
  await run('crosspage-bulk-and-single-delete-exact-refs', async () => {
    await mount(); await page.getByRole('checkbox', { name: '选择 PART-001', exact: true }).check(); await button('下一页').click(); await settle();
    await page.getByRole('checkbox', { name: '选择 PART-021', exact: true }).check(); await button('批量删除').click(); await button('检查删除范围').click();
    await page.getByRole('table', { name: '零件操作预检' }).waitFor();
    assert.deepEqual(await page.evaluate(() => fixture.reads.filter(r => r.type === 'bulk').at(-1).body.refs), [1, 21].map(n => n.toString(16).padStart(48, '0')));
    assert.equal(await page.evaluate(() => fixture.commands.length), 0); await button('取消').click(); await button('删除 PART-022').click(); await button('检查删除范围').click();
    await page.getByRole('table', { name: '零件操作预检' }).waitFor(); await page.getByRole('checkbox', { name: '已核对全部明细，确认删除这些零件。', exact: true }).check(); await button('确认删除').click();
    await page.getByText('原请求已确认删除 1 个零件。', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => fixture.commands.length), 1); assert.equal(await page.evaluate(() => fixture.previewRefs.length), 1); await shot('delete'); await button('完成').click();
    assert.equal(await page.locator('[data-process-selection-count]').innerText(), '2');
  });
  await run('create-dirty-cancel-save-original-ref', async () => {
    await mount(); await fillCreate(); await button('取消').click(); await page.getByRole('dialog', { name: '放弃新增零件的填写内容？', exact: true }).waitFor(); await button('继续编辑').click();
    assert.equal(await page.getByRole('textbox', { name: '图号', exact: true }).inputValue(), 'NEW-01'); assert.equal(await page.evaluate(() => fixture.commands.length), 0);
    await button('保存零件').click(); await page.getByText('零件已登记，工艺仍待确认。打开详情前会重读这条原零件。', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => fixture.commands.length), 1); await shot('create'); await button('打开工艺详情').click();
    await page.getByRole('dialog', { name: 'NEW-01 · 新增零件', exact: true }).waitFor(); assert(await page.getByText('待录入路线', { exact: true }).isVisible());
    assert.equal(await page.evaluate(() => fixture.reads.filter(r => r.type === 'detail').at(-1).ref), (900).toString(16).padStart(48, '0')); await button('关闭详情').click();
  });
  await run('pending-receipt-remount-never-resubmits', async () => {
    await mount({ pending: true, notRecorded: true }); await fillCreate('RECOVER'); await button('保存零件').click(); await button('查询原请求回执').waitFor();
    assert(await button('取消').isDisabled()); const key = await page.evaluate(() => fixture.pending.request_key); await page.evaluate(() => remountFixture());
    await button('查询原请求回执').waitFor(); assert.equal(await page.evaluate(() => fixture.commands.length), 1); await page.evaluate(() => fixture.spec.notRecorded = false);
    await button('查询原请求回执').click(); await button('打开工艺详情').waitFor(); assert.equal(await page.evaluate(() => fixture.commands.length), 1);
    assert((await page.evaluate(() => fixture.lookups)).every(item => item === key)); await button('完成').click(); assert.equal(await page.evaluate(() => fixture.pending), null);
  });
  await run('atomic-rejection-pagination-and-expired-preview', async () => {
    await mount({ rejectBulk: true }); await page.getByRole('checkbox', { name: '全选当前页', exact: true }).check(); await button('下一页').click(); await settle(); await page.getByRole('checkbox', { name: '全选当前页', exact: true }).check();
    await button('下一页').click(); await settle(); await page.getByRole('checkbox', { name: '全选当前页', exact: true }).check(); await button('批量删除').click(); await button('检查删除范围').click();
    const grid = page.getByRole('table', { name: '零件操作预检', exact: true }); await grid.waitFor(); assert.equal(await grid.locator('tbody tr:not(.rm-row-note)').count(), 50);
    await page.getByRole('checkbox', { name: '已核对全部明细，确认删除这些零件。', exact: true }).check(); assert(await page.getByRole('button', { name: /^确认删除/ }).isDisabled());
    await button('预检下一页').click(); assert.equal(await grid.locator('tbody tr:not(.rm-row-note)').count(), 10); await button('取消').click(); assert.equal(await page.evaluate(() => fixture.commands.length), 0);
    await mount({ expired: true }); await button('删除 PART-001').click(); await button('检查删除范围').click(); await grid.waitFor(); assert(await page.getByRole('button', { name: /^确认删除/ }).isDisabled()); await button('取消').click();
  });
  await run('missing-created-ref-and-partial-receipt-fail-closed', async () => {
    await mount({ missingCreated: true }); await fillCreate('SAME-CODE'); await button('保存零件').click(); await button('打开工艺详情').click();
    await page.getByText('原零件已不存在，未打开同图号的新零件。', { exact: true }).waitFor(); assert.equal(await page.locator('.process-detail').count(), 0); await button('完成').click();
    await mount({ partial: true }); await button('删除 PART-001').click(); await button('检查删除范围').click(); await page.getByRole('table', { name: '零件操作预检' }).waitFor();
    await page.getByRole('checkbox', { name: '已核对全部明细，确认删除这些零件。', exact: true }).check(); await button('确认删除').click(); await button('查询原请求回执').waitFor();
    assert(await button('取消').isDisabled()); assert.equal(await page.evaluate(() => fixture.committed.length), 0);
    await button('查询原请求回执').click(); await page.getByText('原请求已确认删除 1 个零件。', { exact: true }).waitFor(); await button('完成').click();
  });
  await run('file-import-group-discard-and-zero-review-explicit', async () => {
    await mount({ files: true }); await button('导入工艺路线').click(); await button('CSV (.csv)').click();
    await page.getByLabel('选择工艺路线文件', { exact: true }).setInputFiles({ name: 'route.csv', mimeType: 'text/csv', buffer: Buffer.from('图号,路线\nPART-001,5Polish\n') });
    await button('开始预检').click(); await page.getByRole('table', { name: '原外协组规则', exact: true }).waitFor();
    assert(await page.getByRole('button', { name: /^确认导入/ }).isDisabled()); assert((await page.getByRole('table', { name: '原外协组规则', exact: true }).innerText()).includes('6.75 天'));
    await page.getByRole('checkbox', { name: '已核对全部 1 组，同意解除这些原外协组。', exact: true }).check(); await page.getByRole('checkbox', { name: '已核对全部修改前后内容，确认这些更新。', exact: true }).check();
    await shot('file-route'); await button('确认导入').click(); await page.getByText('已取得原文件请求的完成回执，工艺确认状态以重新读取的详情为准。', { exact: true }).waitFor();
    const input = await page.evaluate(() => fixture.commands.at(-1).body.input);
    assert.deepEqual(input, { preview_ref: 'p'.repeat(32), discard_group_refs: [(450).toString(16).padStart(48, '0')], confirm_zero_unit_hours: false }); await button('完成').click();
    await button('导入工时定额').click(); await button('CSV (.csv)').click();
    await page.getByLabel('选择工时定额文件', { exact: true }).setInputFiles({ name: 'hours.csv', mimeType: 'text/csv', buffer: Buffer.from('图号,工序,单件工时(h)\nPART-001,5,0\n') });
    await button('开始预检').click(); await page.getByRole('checkbox', { name: '已复核单件工时为 0 的记录，确认保留 0。', exact: true }).waitFor();
    await page.getByRole('checkbox', { name: '已核对全部修改前后内容，确认这些更新。', exact: true }).check(); assert(await page.getByRole('button', { name: /^确认导入/ }).isDisabled());
    await page.getByRole('checkbox', { name: '已复核单件工时为 0 的记录，确认保留 0。', exact: true }).check();
    const beforeHours = await page.evaluate(() => ({committed:fixture.committed.length,reads:fixture.reads.length}));
    await button('确认导入').click(); await page.getByRole('table', {name:'工时导入结果明细',exact:true}).waitFor();
    assert.match(await page.getByRole('region', {name:'工时导入回执',exact:true}).innerText(), /已导入\s+1\s+行[\s\S]*锁定跳过\s+0\s+行/);
    assert.equal(await page.evaluate(() => fixture.committed.length), beforeHours.committed);
    assert.equal(await page.evaluate(() => fixture.reads.length), beforeHours.reads);
    assert.equal(await page.evaluate(() => fixture.commands.at(-1).body.input.confirm_zero_unit_hours), true); await button('完成').click();
    await settle(); assert.equal(await page.evaluate(() => fixture.committed.length), beforeHours.committed + 1);
  });
  await run('file-cancel-dirty-and-full-filtered-export-download', async () => {
    await mount({ files: true }); await button('导入工艺路线').click();
    await page.getByLabel('选择工艺路线文件', { exact: true }).setInputFiles({ name: 'route.csv', mimeType: 'text/csv', buffer: Buffer.from('图号\nPART-001\n') });
    await button('取消').click(); await page.getByRole('dialog', { name: '放弃本次文件导入？', exact: true }).waitFor(); await button('继续核对').click(); assert(await page.getByText(/^route.csv · \d+ 字节$/).isVisible());
    await button('取消').click(); await button('放弃导入并关闭').click(); assert.equal(await page.evaluate(() => fixture.commands.length), 0);
    await button('筛选零件名称').click(); await page.locator('[data-wb-table-filter]').getByRole('checkbox', { name: '0', exact: true }).uncheck(); await settle(); await button('关闭列筛选').click();
    await button('导出工时定额').click(); await button('CSV (.csv)').click(); await page.getByRole('radio', { name: '当前筛选结果（全部页）', exact: true }).check(); await button('开始预检').click();
    await page.getByText('已核对 65 个零件，导出 130 行工序记录，不限当前显示页。', { exact: true }).waitFor();
    const request = await page.evaluate(() => fixture.reads.filter(r => r.type === 'file').at(-1).body);
    assert.equal(request.selection, 'filtered'); assert.equal(request.scope.column_filters.label.values.length, 1); assert(!('page' in request.scope));
    const event = page.waitForEvent('download'); await button('下载文件').click(); const download = await event;
    assert.equal(download.suggestedFilename(), 'process-hours.csv'); assert((await fs.promises.readFile(await download.path(), 'utf8')).includes('PART-001,0'));
    assert.deepEqual(await page.evaluate(() => fixture.reads.filter(r => r.type === 'download').at(-1).query), { export_ref: 'e'.repeat(32) });
    await button('完成').click(); assert.equal(await page.evaluate(() => fixture.commands.length), 0);
  });
  await run('file-pending-remount-and-wrong-kind-receipt', async () => {
    await mount({ files: true, pending: true, notRecorded: true }); await button('导入工时定额').click(); await button('CSV (.csv)').click();
    await page.getByLabel('选择工时定额文件', { exact: true }).setInputFiles({ name: 'hours.csv', mimeType: 'text/csv', buffer: Buffer.from('图号,工序\nPART-001,5\n') });
    await button('开始预检').click(); await page.getByRole('checkbox', { name: '已复核单件工时为 0 的记录，确认保留 0。', exact: true }).check();
    await page.getByRole('checkbox', { name: '已核对全部修改前后内容，确认这些更新。', exact: true }).check(); await button('确认导入').click(); await button('查询原请求回执').waitFor();
    const pending = await page.evaluate(() => fixture.pending); assert.equal(pending.kind, 'process_hours_import'); assert.equal(pending.action, 'confirm'); assert(!pending.input);
    await page.evaluate(() => remountFixture()); await button('查询原请求回执').waitFor(); assert.equal(await page.evaluate(() => fixture.commands.length), 1);
    await page.evaluate(() => { fixture.spec.notRecorded = false; fixture.receipt.data.kind = 'route'; }); await button('查询原请求回执').click();
    await page.getByText('导入回执没有完整确认本次文件，请继续查询原请求。', { exact: true }).waitFor(); assert(await button('取消').isDisabled()); assert.equal(await page.evaluate(() => fixture.committed.length), 0);
    await page.evaluate(() => fixture.receipt.data.kind = 'hours'); await button('查询原请求回执').click(); await button('完成').waitFor(); assert.equal(await page.evaluate(() => fixture.commands.length), 1);
    assert((await page.evaluate(() => fixture.lookups)).every(key => key === pending.request_key));
    assert.equal(await page.evaluate(() => fixture.committed.length), 0); await page.getByRole('table', {name:'工时导入结果明细',exact:true}).waitFor();
    await button('完成').click(); await settle(); assert.equal(await page.evaluate(() => fixture.pending), null); assert.equal(await page.evaluate(() => fixture.committed.length), 1);
  });
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] }); report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    const origin = 'http://127.0.0.1:' + server.address().port;
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport }); await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(12000); variant = viewport.width + '-' + theme;
      page.on('pageerror', error => report.errors.push(error.message)); page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin); await cases(); await context.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
    for (const source of report.sources) assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root, source.path))).digest('hex'), source.sha256, source.path);
  } finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'process-actions-result.json'), JSON.stringify(report, null, 2)); }
  console.log(JSON.stringify({ output, cases: report.cases.length, screenshots: report.screenshots.length, browser: report.browser }));
})().catch(error => { console.error(error); process.exitCode = 1; });
