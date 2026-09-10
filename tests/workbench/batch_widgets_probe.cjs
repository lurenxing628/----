/* Explicit mock fixtures. Only components are locally compiled, never global assets. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
fs.mkdirSync(output, { recursive: true });
const files = ['resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'ResourceTables.jsx', 'ResourceForms.jsx',
  'BatchContract.js', 'BatchControls.jsx', 'BatchForms.jsx', 'BatchOperationEditor.jsx', 'BatchDetail.jsx', 'BatchTable.jsx', 'BatchFiles.jsx', 'BatchWorkspace.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
let compiled;
try { compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true }); }
catch (error) { console.error(error.message); process.exit(1); }
const scripts = new Map(compiled.outputs.map((item, i) => ['/fixture/' + files[i] + '.js', item.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(item => [item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const fixture = `
const ref=n=>n.toString(16).padStart(48,'0'), clone=o=>JSON.parse(JSON.stringify(o));
const wc=()=>({write_token:'test-token-'+f.revision,capabilities:Object.fromEntries(APSBatchContract.actions.map(a=>['batch.'+a,true])),blocked_reasons:[]});
const envelope=data=>({ok:true,schema_version:1,data,meta:{source:'production',snapshot_ref:'s'+f.revision,as_of:'2026-09-09T12:00:00',request_ref:'test-read',time_basis:'factory_local'},warnings:[]});
const resource=(n,code,label)=>({ref:ref(n),business_code:code,label,status:'active'});
function record(n){ const op={ref:ref(1000+n),operation_ref:ref(1000+n),business_code:'B'+n+'_01',sequence:1,piece_id:null,label:'精加工',source:'internal',status:'pending',completed:false,
  setup_hours:null,unit_hours:0,external_days:null,machine_ref:null,operator_ref:null,supplier_ref:null,op_type_ref:ref(400),resources:{machine:null,operator:null,supplier:null,op_type:resource(400,'TYPE','精加工')},external_group:null,issues:[{code:'data_gap',message:'换型工时未填写。'}],editable:true};
  return {ref:ref(n),business_code:'B'+String(n).padStart(3,'0'),label:'零件 '+n,status:'pending',fields:{quantity:n,due_date:'2026-10-01',priority:n%2?'normal':'urgent',ready_status:n%2?'no':'yes',ready_date:null,remark:null},
    relationships:{part_ref:ref(300),part_no:'PART-01',part_name:'零件 '+n,operation_count:1,completed_count:0,gap_count:1,plan_reference_count:0,execution_reference_count:0,material_requirement_count:0},operations:[op],all_operations_complete:false,issues:[],protected:false,write_context:wc(),
    materials:{requirements:[],count:0},template:{origin:'legacy',ready:false}};}
function matching(scope){return f.rows.filter(r=>(!scope.query||r.business_code.includes(scope.query))&&(!scope.status||r.status===scope.status)&&(!scope.ready_status||r.fields.ready_status===scope.ready_status)&&Object.entries(scope.column_filters||{}).every(([key,values])=>values.includes(key==='business_code'?r.business_code:key==='part_no'?r.relationships.part_no:key==='status'?r.status:r.fields[key])));}
function pageData(scope){const rows=matching(scope).slice();const cell=r=>scope.sort==='business_code'?r.business_code:scope.sort==='part_no'?r.relationships.part_no:scope.sort==='status'?r.status:r.fields[scope.sort];rows.sort((a,b)=>(cell(a)>cell(b)?1:cell(a)<cell(b)?-1:0)*(scope.direction==='desc'?-1:1));return envelope({entities:clone(rows.slice((scope.page-1)*scope.size,scope.page*scope.size)).map(r=>({...r,write_context:wc()})),page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.max(1,Math.ceil(rows.length/scope.size)),sort:[{field:scope.sort,direction:scope.direction}]},create_context:wc(),metrics:{total:rows.length}});}
function adapter(){return {
 list:async(kind,scope)=>{f.reads.push(clone(scope));if(f.spec.failList)throw APSResourceContract.failure('MOCK 列表失败');const result=pageData(scope);if(f.spec.badList)result.data.entities[0].all_operations_complete=true;return result;},
 detail:async(kind,id)=>{if(f.spec.failDetail)throw APSResourceContract.failure('MOCK 详情失败');const row=f.rows.find(r=>r.ref===id);if(!row)throw APSResourceContract.failure('MOCK 已删除');return envelope({...clone(row),write_context:wc()});},
 choices:async()=>envelope({parts:[{ref:ref(300),business_code:'PART-01',label:'当前零件'}],machines:[resource(100,'M-01','数控设备')],operators:[resource(200,'O-01','人员甲')],suppliers:[],authorizations:[{machine_ref:ref(100),operator_ref:ref(200)}]}),
 selection:async scope=>{f.selections.push(clone(scope));const rows=matching(scope);return envelope({refs:rows.map(r=>r.ref),count:rows.length});},
 facets:async(scope,field)=>envelope({field,values:field==='quantity'?[1,2,3]:['normal','urgent'],count:3}),
 importPreview:async(file,mode,scope,snapshot)=>{f.files.push({name:file.name,size:file.size,mode,scope:clone(scope),snapshot});return envelope({operation:'batch.import_confirm',mode,preview_ref:'f'.repeat(32),write_context:wc(),count:1,can_confirm:!f.spec.fileErrors,commit_policy:'atomic',deleted:mode==='replace'?[{entity_ref:ref(1),before:clone(f.rows[0]),errors:f.spec.fileErrors?['已有执行引用']:[]}]:[],warnings:[],rows:[{row:2,business_code:'IMPORT-NEW',action:'create',entity_ref:null,before:null,errors:f.spec.fileErrors?['数量无效']:[],input:{fields:{quantity:3,due_date:null,priority:'normal',ready_status:'no',ready_date:null,remark:null}}}]});},
 exportPreview:async(selection,scope,refs)=>{f.exports.push({selection,scope:clone(scope),refs:clone(refs)});return envelope({export_ref:'e'.repeat(32),count:selection==='selected'?refs.length:matching(scope).length,selection});},
 downloadTemplate:async()=>({blob:new Blob(['explicit component mock download'],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})}),
 downloadExport:async()=>({blob:new Blob(['explicit component mock download'],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})}),
 preview:async(action,id,input,scope,snapshot)=>{f.previews.push({action,id,input:clone(input),scope:clone(scope),snapshot});const token='a'.repeat(31)+(f.previews.length%10);f.tokens[token]={action,id,input:clone(input)};return envelope(action==='bulk'?{operation:'batch.bulk_confirm',action:input.action,preview_ref:token,write_context:wc(),rows:input.refs.map(ref=>{const before=clone(f.rows.find(r=>r.ref===ref));return {entity_ref:ref,before,after:input.action==='delete'?null:{...before,fields:{...before.fields,...input.patch}}};}),count:input.refs.length,commit_policy:'atomic',warnings:[]}:{operation:'batch.sync_confirm',entity_ref:id,strict_mode:input.strict_mode,preview_ref:token,write_context:wc(),before:f.rows.find(r=>r.ref===id).operations,after:[{sequence:1,label:'精加工',setup_hours:null,unit_hours:0,external_days:null}],commit_policy:'atomic',warnings:[]});},
 command:async(kind,action,id,body)=>{f.commands.push({kind,action,id,body:clone(body)});if(f.spec.stale){const e=APSResourceContract.failure('MOCK stale：资料已变化');e.committed=false;throw e;}let data={entity_ref:id};
   if(action==='create'){const row=record(f.rows.length+1);row.business_code=body.input.business_code;row.fields=clone(body.input.fields);row.operations=[];row.relationships.operation_count=0;row.relationships.gap_count=0;f.rows.push(row);data.entity_ref=row.ref;}
   if(action==='update')Object.assign(f.rows.find(r=>r.ref===id).fields,body.input.fields);
   if(action==='operation_update'){const op=f.rows.find(r=>r.ref===id).operations.find(o=>o.ref===body.input.operation_ref);Object.assign(op,body.input.fields);data.operation_ref=op.ref;}
   if(action==='import_confirm')data={items:[{entity_ref:ref(26),business_code:'IMPORT-NEW',result:'committed'}],count:1};
   if(action==='bulk_confirm'){const p=f.tokens[body.input.preview_ref].input;data={items:p.refs.map(ref=>({entity_ref:ref,result:'committed'})),count:p.refs.length};if(p.action==='delete')f.rows=f.rows.filter(r=>!p.refs.includes(r.ref));if(p.action==='update')f.rows.filter(r=>p.refs.includes(r.ref)).forEach(r=>Object.assign(r.fields,p.patch));}
   f.revision++;const receipt={ok:true,result:'committed',receipt_ref:'receipt'+f.commands.length,replayed:false,data,warnings:[]};f.receipts[body.request_key]=receipt;if(f.spec.pending)throw new Error('MOCK 响应丢失');return receipt;},
 lookup:async key=>f.allowLookup?f.receipts[key]:{ok:true,state:'not_recorded',receipt:null,may_be_in_flight:true},
 readPending:()=>null,savePending:intent=>{f.pending=clone(intent);},clearPending:()=>{f.pending=null;}
};}
let root;
window.mountFixture=(spec={})=>{if(root)root.unmount();window.f={spec,revision:1,rows:[],commands:[],reads:[],previews:[],tokens:{},receipts:{},selections:[],files:[],exports:[]};f.rows=Array.from({length:25},(_,i)=>record(i+1));root=ReactDOM.createRoot(document.getElementById('fixture-root'));root.render(React.createElement('section',{className:'plana',style:{padding:16}},React.createElement(BatchWorkspace,{adapter:adapter()})));};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><div id="fixture-root"></div>' + staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => { const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); return; }
  const asset = assets.get(name.slice('/static/'.length)); if (!name.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const report = { scope: 'batch-component-mock', production_persistence_tested: false, compile: { global_build: false, target: compiled.target },
  sources: sources.map(row => ({ path: row.path, sha256: sha(row.code) })), cases: [], screenshots: [], errors: [], external: [] };
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
async function mount(spec = {}) { await page.evaluate(spec => mountFixture(spec), spec); await button('B001').waitFor(); }
async function type(name, value) { const input = page.getByLabel(name, { exact: true }); await input.fill(''); await input.pressSequentially(value); }
async function shot(name) {
  const geometry = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
    dialogs: [...document.querySelectorAll('[role=dialog]')].map(el => { const r = el.getBoundingClientRect(); return { left:r.left, top:r.top, right:r.right, bottom:r.bottom }; }), height: innerHeight }));
  assert(geometry.scroll <= geometry.width + 1, JSON.stringify(geometry));
  geometry.dialogs.forEach(r => assert(r.left >= 0 && r.top >= 0 && r.right <= geometry.width + 1 && r.bottom <= geometry.height + 1, JSON.stringify(r)));
  const file = variant + '-' + name + '.png'; await page.screenshot({ path: path.join(output, file), fullPage: true, animations: 'disabled' }); report.screenshots.push({ file, geometry });
}
async function run(name, action) { try { await action(); report.cases.push({ variant, name, passed: true }); } catch (error) { report.cases.push({ variant, name, passed: false, error: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-FAILED.png') }); throw error; } }
async function cases() {
  await run('list-search-selection-paging-filter', async () => {
    await mount(); assert.equal(await page.getByRole('table', { name: '批次列表' }).locator('tbody tr').count(), 20); await shot('list');
    const resizer = page.getByRole('separator', { name: '调整图号列宽' }); const width = Number(await resizer.getAttribute('aria-valuenow'));
    await resizer.focus(); await resizer.press('ArrowRight'); assert.equal(Number(await resizer.getAttribute('aria-valuenow')), width + 12);
    await page.getByRole('checkbox', { name: '选择 B001', exact: true }).check(); await button('下一页').click(); await button('B021').waitFor();
    assert((await page.locator('[data-batch-workspace]').innerText()).includes('含非当前页记录')); await button('全选当前筛选').click(); await page.getByText(/已选 25 个批次/).waitFor();
    await type('搜索批次号、图号、零件名', 'B001'); await button('搜索').click(); await button('B001').waitFor(); assert.equal(await page.getByRole('table', { name: '批次列表' }).locator('tbody tr').count(), 1);
    assert.equal(await page.evaluate(() => f.selections.length), 1); await button('筛选数量').click(); await page.getByRole('dialog').waitFor(); await shot('column-filter');
    await button('全部不选').click(); await button('完成').click(); await page.getByText('当前条件下暂无批次', { exact: true }).waitFor(); await button('清除全部筛选').click(); await button('B001').waitFor();
  });
  await run('create-real-form-command-payload', async () => {
    await mount(); await button('新增批次').click(); await page.getByRole('combobox', { name: '图号' }).selectOption('12c'.padStart(48,'0'));
    await type('批次号', 'NEW-INPUT'); await page.getByRole('spinbutton', { name: '数量', exact: true }).fill('7'); await page.getByLabel('交期', { exact: true }).fill('2028-02-29'); await type('备注', '真实输入测试'); await shot('create');
    await button('创建批次').click(); await page.getByText('服务器已确认提交。', { exact: true }).waitFor();
    const command = await page.evaluate(() => f.commands[0]); assert.equal(command.action, 'create'); assert.equal(command.body.input.fields.quantity, 7); assert.equal(command.body.input.fields.ready_date, null);
    assert.equal(command.body.input.fields.due_date, '2028-02-29'); await button('关闭').last().click(); assert.equal(await page.evaluate(() => f.pending), null);
  });
  await run('detail-null-zero-operation-edit', async () => {
    await mount(); await button('B001').click(); await page.locator('[data-batch-detail]').waitFor(); await shot('detail');
    assert((await page.getByRole('table', { name: '批次工序', exact: true }).innerText()).includes('换型 未填写 / 单件 0 小时'));
    await button('补充资料').click(); await page.getByRole('combobox', { name: '设备' }).selectOption('64'.padStart(48,'0'));
    await page.getByRole('combobox', { name: '人员' }).selectOption('c8'.padStart(48,'0')); await type('换型工时（小时）', '0'); await shot('operation');
    await button('保存工序').click(); await page.getByText('服务器已确认提交。', { exact: true }).waitFor();
    const input = await page.evaluate(() => f.commands[0].body.input); assert.equal(input.fields.setup_hours, 0); assert(!('unit_hours' in input.fields)); assert(/^[0-9a-f]{48}$/.test(input.operation_ref));
    await button('关闭').last().click(); await button('按最新工艺模板刷新本批次工序').click(); await page.getByRole('dialog', { name: '确认刷新批次工序' }).waitFor();
    assert.equal(await page.evaluate(() => f.commands.length), 1); await shot('sync-preview'); await button('确认变更').click(); await page.getByText('服务器已确认提交。', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => f.commands[1].action), 'sync_confirm'); await button('关闭').last().click(); await button('返回列表').click(); await button('B001').waitFor();
  });
  await run('stale-edit-keeps-draft-explicit-review', async () => {
    await mount({ stale: true }); await button('B001').click(); await button('编辑基础信息').click(); await type('备注', '不能丢失的草稿'); await button('保存基础信息').click();
    await page.getByText('MOCK stale：资料已变化', { exact: true }).waitFor(); assert.equal(await page.getByRole('textbox', { name: '备注' }).inputValue(), '不能丢失的草稿');
    await button('重新读取并核对').click(); await button('采用最新资料继续编辑').waitFor(); assert(await button('保存基础信息').isDisabled());
    await button('采用最新资料继续编辑').click(); assert.equal(await page.getByRole('textbox', { name: '备注' }).inputValue(), '不能丢失的草稿'); await shot('stale-preserved');
    await page.evaluate(() => f.spec.stale = false); await button('保存基础信息').click(); await page.getByText('服务器已确认提交。', { exact: true }).waitFor(); await button('关闭').last().click();
  });
  await run('bulk-preview-cancel-and-confirm', async () => {
    await mount(); await page.getByRole('checkbox', { name: '选择 B001', exact: true }).check(); await button('批量修改').click(); await type('批量备注', '批量实际输入');
    await button('预览变更').click(); await page.getByRole('dialog', { name: '确认批量修改' }).waitFor(); assert.equal(await page.evaluate(() => f.commands.length), 0); await shot('bulk-preview');
    await button('取消').click(); assert.equal(await page.evaluate(() => f.commands.length), 0); await button('删除所选').click(); await button('确认变更').click();
    await page.getByText('服务器已确认提交。', { exact: true }).waitFor(); assert.equal(await page.evaluate(() => f.rows.some(r => r.business_code === 'B001')), false); await button('关闭').last().click();
  });
  await run('uncertain-receipt-locks-writes', async () => {
    await mount({ pending: true }); await button('B001').click(); await button('编辑基础信息').click(); await type('备注', '待核实'); await button('保存基础信息').click();
    await page.getByText(/结果待核实。请保留当前页面/).waitFor(); assert(await button('保存基础信息').isDisabled()); assert(await button('取消').isDisabled());
    await page.evaluate(() => f.allowLookup = true); await button('查询原请求回执').click(); await page.getByText('服务器已确认提交。', { exact: true }).waitFor(); assert.equal(await page.evaluate(() => f.commands.length), 1); await button('关闭').last().click();
  });
  await run('file-mode-preview-invalidation-confirm-and-download-scope', async () => {
    await mount(); await button('批量导入').click();
    const templateWait = page.waitForEvent('download'); await button('下载批次模板').click(); assert.equal((await templateWait).suggestedFilename(), 'batches-template.xlsx');
    await page.getByLabel('选择 Excel 文件').setInputFiles({ name: 'batches.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.from('Explicit mock bytes, parser is independently tested in SQLite suite') });
    await button('预览导入').click(); await page.getByRole('table', { name: '批次导入预览' }).waitFor(); assert.equal(await page.evaluate(() => f.commands.length), 0);
    await page.getByLabel('导入模式').selectOption('append'); assert.equal(await page.getByRole('table', { name: '批次导入预览' }).count(), 0); await button('预览导入').click(); await button('确认导入').waitFor();
    await shot('file-preview'); await button('确认导入').click(); await page.getByText('服务器已确认提交。', { exact: true }).waitFor(); assert.equal(await page.evaluate(() => f.files[1].mode), 'append');
    assert.equal(await page.evaluate(() => f.commands[0].action), 'import_confirm'); await button('关闭').last().click();
    await button('批量导出').click(); const downloading = page.waitForEvent('download'); await button('下载批次清单').click(); const file = await downloading; assert.equal(file.suggestedFilename(), 'batches.xlsx');
    assert.equal(await page.evaluate(() => f.exports[0].selection), 'filtered'); await page.getByText('已生成 25 个批次的清单。', { exact: true }).waitFor(); await button('取消').click();
  });
  await run('replace-errors-disable-confirmation', async () => {
    await mount({ fileErrors: true }); await button('批量导入').click(); await page.getByLabel('导入模式').selectOption('replace');
    await page.getByLabel('选择 Excel 文件').setInputFiles({ name: 'replace.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.from('Explicit invalid fixture') });
    await button('预览导入').click(); await page.getByText('将删除的全部批次', { exact: true }).waitFor(); assert(await button('确认导入').isDisabled());
    assert.equal(await page.evaluate(() => f.commands.length), 0); await shot('replace-rejected'); await button('取消').click();
  });
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] }); report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    const origin = 'http://127.0.0.1:' + server.address().port;
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); variant = viewport.width + 'x' + viewport.height + '-' + theme; page.setDefaultTimeout(12000);
      page.on('pageerror', error => report.errors.push(error.message)); page.on('console', msg => { if (msg.type() === 'error') report.errors.push(msg.text()); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin); await cases(); await context.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'batch-result.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
