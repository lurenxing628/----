/* Current source in Chromium 109; choice/command adapters are explicit fixtures. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http');
const path = require('node:path'), crypto = require('node:crypto'), { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass a temporary artifact directory');
fs.mkdirSync(output, { recursive: true });
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'resource-contract.js',
  'resource-session.js', 'ResourceControls.jsx', 'ProcessContract.js', 'ProcessStageEditor.jsx', 'ProcessSourceEditor.jsx', 'ProcessGroupEditor.jsx', 'ProcessHoursEditor.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(item => [item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const styles = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json'))).styles.map(name => fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8')).join('\n');
const fixture = `
const ref=n=>n.toString(16).padStart(48,'0'), copy=x=>JSON.parse(JSON.stringify(x));
const stamp=state=>({state,confirmed_at:state==='confirmed'?'2026-09-28T04:00:00Z':null,confirmed_by:null});
const envelope=data=>({ok:true,schema_version:1,data,meta:{source:'production',time_basis:'factory_local',snapshot_ref:'fixture-snapshot',request_ref:'fixture-request',as_of:'2026-09-28T04:00:00Z'},warnings:[]});
const types=[{ref:ref(101),label:'热处理'},{ref:ref(102),label:'表面处理'}];
function supplier(id,label,ids){return {ref:ref(id),business_code:'S'+id,label,status:'active',fields:{default_days:3.25},relationships:{op_type_refs:ids.map(ref),op_types:ids.map(id=>types.find(row=>row.ref===ref(id)))},issues:[],write_context:null};}
const suppliers=[supplier(300,'仅热处理厂',[101]),supplier(301,'共同供应商',[101,102]),supplier(303,'另一共同厂',[101,102])];
window.ResourceTables={Pager:()=>null};
window.ResourceForms={Feedback:()=>null};
window.ProcessFileButtons=()=>null;
function entity(){const operations=[10,20,21,30,40,50].map(seq=>{const internal=[10,30].includes(seq),group=[20,21].includes(seq);return {
  ref:ref(1000+seq),sequence:seq,label:internal?'车削':seq%2===0?'热处理':'表面处理',source:internal?'internal':'external',op_type_ref:ref(internal?100:seq===21||seq===50?102:101),op_type_label:internal?'车削':seq===21||seq===50?'表面处理':'热处理',
  supplier_ref:internal?null:ref(301),supplier_label:internal?null:'共同供应商',external_group_ref:group?ref(400):null,setup_hours:internal?0:null,unit_hours:internal?1:null,external_days:internal||group?null:3.25,external_days_source:internal?null:group?'group':'operation',status:'active',issues:[],confirmation:{source:stamp('confirmed'),hours:stamp('unconfirmed')}};});
  return {ref:ref(1),business_code:'P1',label:'零件',status:null,fields:{route_raw:'10车削20热处理21表面处理30车削40热处理50表面处理',route_parsed:'yes',remark:null},relationships:{batch_count:1,operation_count:6,internal_count:2,external_count:4,unclassified_count:0},issues:[],write_context:{write_token:'TOKEN',capabilities:{'process.hours_confirm':true},blocked_reasons:[]},
    workflow:{origin:'managed',stage:'hours',ready:false,route:stamp('confirmed'),source:stamp('confirmed'),hours:stamp('unconfirmed')},operations,
    external_groups:[{ref:ref(400),start_sequence:20,end_sequence:21,merge_mode:'merged',total_days:6.75,supplier_ref:ref(301),supplier_label:'共同供应商',remark:null,issues:[]},
      {ref:ref(401),start_sequence:80,end_sequence:80,merge_mode:'separate',total_days:4,supplier_ref:ref(301),supplier_label:'共同供应商',remark:'历史记录保留',issues:[]}],
    capabilities:{route_preview:true,create:true,delete:true,stage_confirm:true,import:true,export:true}};
}
function facts(group,refs,supplierRef,total){return {operation_refs:refs,sequences:refs.map(id=>String(fixtureState.entity.operations.find(row=>row.ref===id).sequence)),supplier_id:supplierRef?'S'+parseInt(supplierRef,16):null,supplier_label:'共同供应商',total_days:total,merge_mode:group?group.merge_mode:'merged'};}
function preview(input){const old=fixtureState.entity.external_groups,ops=fixtureState.entity.operations;const before=g=>facts(g,ops.filter(row=>row.external_group_ref===g.ref).map(row=>row.ref),g.supplier_ref,g.total_days);
  const changes=input.groups.map(row=>({ref:row.ref,action:row.ref?'update':'create',before:row.ref?before(old.find(g=>g.ref===row.ref)):null,after:facts(null,row.operation_refs,row.supplier_ref,row.total_days)}));
  input.discard_group_refs.forEach(id=>changes.push({ref:id,action:'discard',before:before(old.find(g=>g.ref===id)),after:null}));return changes;
}
let renderRoot;
window.mountFixture=(spec={})=>{if(renderRoot)renderRoot.unmount();const current=entity();window.fixtureState={entity:current,commands:[],previews:[],dirty:[],closed:false};
 const adapter={command:async()=>{},detail:async()=>envelope(copy(current)),choices:async(kind,scope)=>envelope({entities:suppliers.filter(row=>!scope.query||row.label.includes(scope.query)),page:{number:1,size:50,total:3,pages:1,sort:[]}}),
 stagePreview:async(part,action,input)=>{fixtureState.previews.push(copy(input));return envelope({part_ref:current.ref,action,affected_groups:[],changes:preview(input),write_context:{write_token:'GROUP-TOKEN',capabilities:{'process.groups_confirm':true},blocked_reasons:[]}});}};
 const command={locked:false,phase:'idle',submit:async(kind,action,id,context,input)=>fixtureState.commands.push({kind,action,id,input:copy(input)})};
 const props={adapter,result:envelope(copy(current)),command,saved:0,onDirty:(key,value)=>fixtureState.dirty.push({key,value}),onOverlay:()=>{},onClose:()=>{fixtureState.closed=true;renderRoot.render(null);}};
 renderRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));renderRoot.render(React.createElement('div',{className:'plana process-detail'},React.createElement(spec.hours?ProcessHoursEditor:ProcessGroupEditor,props)));};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') + '<style>' + styles + '</style></head>' +
  '<body class="aps-workbench"><div id="fixture-root"></div>' + staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); return; }
  const asset = assets.get(name.slice('/static/'.length));
  if (!name.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const report = { scope: 'process-group-component', production_persistence_tested: false, compile: { target: compiled.target, global_build: false },
  sources: sources.map(row => ({ path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex') })), cases: [], errors: [], external: [], screenshots: [] };
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
async function mount(spec = {}) { await page.evaluate(spec => mountFixture(spec), spec); await page.locator('[data-process-group-editor], [data-process-hours-editor]').waitFor(); }
async function run(name, action) { try { await action(); report.cases.push({ name, variant, passed: true }); } catch (error) { report.cases.push({ name, variant, passed: false, error: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') }); throw error; } }
async function cases() {
  await run('new-stage-capability-default-and-explicit-preview', async () => {
    await mount(); await button('新增外协段').click();
    assert(await page.getByRole('checkbox',{name:'外协段包含工序 30',exact:true}).isDisabled());
    await page.getByRole('checkbox',{name:'外协段包含工序 40',exact:true}).check();await page.getByRole('checkbox',{name:'外协段包含工序 50',exact:true}).check();
    await button('选择整段供应商').click();assert(await button('采用 仅热处理厂').isDisabled());await button('采用 共同供应商').click();
    assert.equal(await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).inputValue(),'3.25');
    assert(await button('确认保存外协段').isDisabled());await button('预检外协段').click();await page.getByRole('table',{name:'外协段变更预检'}).waitFor();
    const shot=variant+'-new-stage.png';await page.screenshot({path:path.join(output,shot)});report.screenshots.push(shot);
    await button('确认保存外协段').click();await page.waitForFunction(()=>fixtureState.commands.length===1);
    const sent=await page.evaluate(()=>fixtureState.commands[0]);assert.equal(sent.action,'groups_confirm');assert.equal(sent.input.groups.length,1);assert.equal(sent.input.groups[0].ref,null);assert.equal(sent.input.groups[0].total_days,3.25);assert.equal(sent.input.groups[0].operation_refs.length,2);assert.deepEqual(sent.input.discard_group_refs,[]);
  });
  await run('split-retains-original-stage-and-builds-second',async()=>{
    await mount();await button('修改范围 / 供应商').first().click();await page.getByRole('checkbox',{name:'外协段包含工序 21',exact:true}).uncheck();
    await button('新增外协段').click();await page.getByRole('checkbox',{name:'外协段包含工序 21',exact:true}).check();await button('选择整段供应商').click();await button('采用 共同供应商').click();
    await button('预检外协段').click();await page.getByRole('table',{name:'外协段变更预检'}).waitFor();await button('确认保存外协段').click();await page.waitForFunction(()=>fixtureState.commands.length===1);
    const sent=await page.evaluate(()=>fixtureState.commands[0].input);assert.equal(sent.groups.length,2);assert.equal(sent.groups[0].ref,(400).toString(16).padStart(48,'0'));assert.equal(sent.groups[0].total_days,6.75);assert.equal(sent.groups[0].operation_refs.length,1);assert.equal(sent.groups[1].operation_refs.length,1);assert.deepEqual(sent.discard_group_refs,[]);
  });
  await run('whole-stage-supplier-change-keeps-cycle-and-members',async()=>{
    await mount();await button('修改范围 / 供应商').first().click();await button('选择整段供应商').click();await button('采用 另一共同厂').click();
    assert.equal(await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).inputValue(),'6.75');
    await button('预检外协段').click();await page.getByRole('table',{name:'外协段变更预检'}).waitFor();await button('确认保存外协段').click();await page.waitForFunction(()=>fixtureState.commands.length===1);
    const row=await page.evaluate(()=>fixtureState.commands[0].input.groups[0]);assert.equal(row.ref,(400).toString(16).padStart(48,'0'));assert.equal(row.supplier_ref,(303).toString(16).padStart(48,'0'));assert.equal(row.operation_refs.length,2);assert.equal(row.total_days,6.75);
  });
  await run('release-is-explicit-and-history-is-not-omitted-as-delete',async()=>{
    await mount();await button('解除此段').first().click();await button('预检外协段').click();const table=page.getByRole('table',{name:'外协段变更预检'});await table.waitFor();assert((await table.innerText()).includes('解除段'));
    await button('确认保存外协段').click();await page.waitForFunction(()=>fixtureState.commands.length===1);const input=await page.evaluate(()=>fixtureState.commands[0].input);assert.deepEqual(input.groups,[]);assert.deepEqual(input.discard_group_refs,[(400).toString(16).padStart(48,'0')]);
  });
  await run('dirty-close-and-edits-invalidate-reviewed-input',async()=>{
    await mount();await button('修改范围 / 供应商').first().click();await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).fill('7.125');await button('预检外协段').click();await page.getByRole('table',{name:'外协段变更预检'}).waitFor();
    await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).fill('8.125');assert(await button('确认保存外协段').isDisabled());await button('返回工时').click();await button('放弃段修改并返回').waitFor();assert.equal(await page.evaluate(()=>fixtureState.closed),false);await button('放弃段修改并返回').click();assert.equal(await page.evaluate(()=>fixtureState.closed),true);assert.equal(await page.evaluate(()=>fixtureState.commands.length),0);
  });
  await run('effective-cycle-shown-and-member-input-absent',async()=>{
    await mount({hours:true});const table=page.getByRole('table',{name:'外协周期明细'});assert((await table.innerText()).includes('整段 6.75 天 · 工序 20 至 21'));assert.equal(await page.getByRole('spinbutton',{name:'工序 20 外协周期',exact:true}).count(),0);
    assert(await page.getByRole('spinbutton',{name:'工序 40 外协周期',exact:true}).isVisible());await button('管理外协段').click();await page.locator('[data-process-group-editor]').waitFor();
  });
  await run('deleted-stage-rebase-removes-invalid-draft-and-permits-fresh-edit',async()=>{
    await mount();await button('修改范围 / 供应商').first().click();await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).fill('8.5');
    await page.evaluate(()=>{const e=fixtureState.entity;e.external_groups=[];e.operations.forEach(row=>{if(row.source==='external'){row.status='deleted';row.external_group_ref=null;row.external_days_source=row.external_days===null?null:'operation';}});e.relationships.operation_count=2;e.relationships.external_count=0;});
    await button('刷新最新资料').click();await page.getByText(/接受后会移除失效段的编辑/).waitFor();await button('已核对，继续编辑').click();
    assert.equal(await button('编辑本次第 1 段').count(),0);assert.equal(await button('选择整段供应商').count(),0);
    assert(await button('预检外协段').isDisabled());
    await button('新增外协段').click();assert(await button('选择整段供应商').isDisabled());await button('撤销本次编辑').click();
    await button('返回工时').click();assert.equal(await page.evaluate(()=>fixtureState.closed),true);assert.equal(await page.evaluate(()=>fixtureState.commands.length),0);
  });
  await run('new-stage-rebase-prunes-deleted-member-and-keeps-valid-user-cycle',async()=>{
    await mount();await button('新增外协段').click();await page.getByRole('checkbox',{name:'外协段包含工序 40',exact:true}).check();await page.getByRole('checkbox',{name:'外协段包含工序 50',exact:true}).check();
    await button('选择整段供应商').click();await button('采用 共同供应商').click();await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).fill('8.5');
    await page.evaluate(()=>{const e=fixtureState.entity;e.operations.find(row=>row.sequence===50).status='deleted';e.relationships.operation_count=5;e.relationships.external_count=3;});
    await button('刷新最新资料').click();await page.getByText(/接受后会移除失效段的编辑/).waitFor();await button('已核对，继续编辑').click();
    assert.equal(await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).inputValue(),'8.5');
    await button('选择整段供应商').click();await button('采用 共同供应商').click();
    await button('预检外协段').click();await page.getByRole('table',{name:'外协段变更预检'}).waitFor();await button('确认保存外协段').click();await page.waitForFunction(()=>fixtureState.commands.length===1);
    const row=await page.evaluate(()=>fixtureState.commands[0].input.groups[0]);assert.equal(row.ref,null);assert.equal(row.total_days,8.5);assert.deepEqual(row.operation_refs,[(1040).toString(16).padStart(48,'0')]);
  });
  await run('same-members-rebase-preserves-legitimate-stage-draft',async()=>{
    await mount();await button('修改范围 / 供应商').first().click();await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).fill('8.5');
    await page.evaluate(()=>{fixtureState.entity.external_groups[0].total_days=7.5;});await button('刷新最新资料').click();await button('已核对，继续编辑').click();
    assert.equal(await page.getByRole('spinbutton',{name:'整段外协周期',exact:true}).inputValue(),'8.5');
    await button('预检外协段').click();await page.getByRole('table',{name:'外协段变更预检'}).waitFor();await button('确认保存外协段').click();await page.waitForFunction(()=>fixtureState.commands.length===1);
    const row=await page.evaluate(()=>fixtureState.commands[0].input.groups[0]);assert.equal(row.ref,(400).toString(16).padStart(48,'0'));assert.equal(row.total_days,8.5);assert.equal(row.operation_refs.length,2);
  });
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] }); report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    const origin = 'http://127.0.0.1:' + server.address().port;
    for (const viewport of [{ width: 1392, height: 924 }, { width: 640, height: 900 }]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport }); await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(10000); variant = viewport.width + '-' + theme;
      page.on('pageerror', error => report.errors.push(error.message)); page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin); await cases(); await context.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'process-group-result.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
