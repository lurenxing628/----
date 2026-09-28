/* Current batch editor in real Chromium 109; choices and writes are explicit mock I/O. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http');
const path = require('node:path'), crypto = require('node:crypto'), { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass a temporary artifact directory');
fs.mkdirSync(output, { recursive: true });
const files = ['WorkbenchPageContext.jsx', 'WorkbenchGuards.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx',
  'resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'ResourceForms.jsx',
  'BatchContract.js', 'BatchControls.jsx', 'BatchOperationEditor.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(item => [item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const styleSources = ['00-tokens.css', '20-controls.css', '21-table-frame.css', '22-shared-controls.css', '31-batches-resources.css']
  .map(name => ({ path: 'frontend/workbench/app/styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
const fixture = `
const ref=n=>n.toString(16).padStart(48,'0'), copy=value=>JSON.parse(JSON.stringify(value));
const envelope=data=>({ok:true,schema_version:1,data,meta:{source:'production',time_basis:'factory_local',snapshot_ref:'batch-supplier-snapshot',request_ref:'batch-supplier-read',as_of:'2026-09-28T04:00:00Z'},warnings:[]});
const resource=(id,code,label)=>({ref:ref(id),business_code:code,label,status:'active'});
function makeFixture(spec){const group=spec.mode==='ungrouped'?null:{ref:ref(400),business_code:'WB-0123456789abcdef0123456789abcdef',start_sequence:20,end_sequence:30,merge_mode:spec.mode,total_days:spec.days};
  const supplier=resource(301,'S-01','原热处理厂'), operation={ref:ref(1000),operation_ref:ref(1000),business_code:'B001_20',sequence:20,piece_id:null,label:'热处理',source:'external',status:'pending',completed:false,
    setup_hours:0,unit_hours:0,external_days:0.04,machine_ref:null,operator_ref:null,supplier_ref:supplier.ref,op_type_ref:ref(101),resources:{machine:null,operator:null,supplier,op_type:resource(101,'TYPE-EX','热处理')},external_group:group,issues:[],editable:true};
  const entity={ref:ref(1),business_code:'B001',write_context:{write_token:'batch-supplier-token',capabilities:{'batch.operation_update':true},blocked_reasons:[]}};
  return {spec,entity,operation,commands:[],committed:[],closed:false,pending:null,choicesRead:0};
}
function adapter(){return {
  operationChoices:async()=>{fixtureState.choicesRead++;return envelope({parts:[],machines:[],operators:[],authorizations:[],suppliers:[resource(301,'S-01','原热处理厂'),resource(302,'S-02','另一热处理厂')]});},
  command:async(kind,action,entityRef,body)=>{fixtureState.commands.push({kind,action,entityRef,body:copy(body)});return {ok:true,result:'committed',receipt_ref:'batch-supplier-receipt',replayed:false,data:{entity_ref:entityRef,operation_ref:fixtureState.operation.ref},warnings:[]};},
  readPending:()=>null,savePending:intent=>{fixtureState.pending=copy(intent);},clearPending:()=>{fixtureState.pending=null;},lookup:async()=>({ok:true,state:'not_recorded',receipt:null,may_be_in_flight:false})};}
function Harness(){const current=fixtureState, api=React.useMemo(adapter,[]), command=APSResourceSession.useCommand(api),[closed,setClosed]=React.useState(false);
  return React.createElement(React.Fragment,null,React.createElement(WorkbenchGuardHost),!closed&&React.createElement('div',{className:'plana'},React.createElement(BatchOperationEditor,{adapter:api,entity:current.entity,operation:current.operation,source:'production',command,
    onCommitted:receipt=>current.committed.push(copy(receipt)),onClose:()=>{if(command.reset()){current.closed=true;setClosed(true);}}})));}
let renderRoot;
window.mountFixture=spec=>{if(renderRoot)renderRoot.unmount();window.fixtureState=makeFixture(spec);renderRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));renderRoot.render(React.createElement(Harness));};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>' + styleSources.map(row => row.code).join('\n') + '</style></head><body class="aps-workbench"><div id="fixture-root"></div>' +
  staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); return; }
  const asset = assets.get(name.slice('/static/'.length));
  if (!name.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const report = { scope: 'batch-merged-supplier-component-mock', production_persistence_tested: false, compile: { target: compiled.target, global_build: false },
  sources: sources.concat(styleSources).map(row => ({ path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex') })), cases: [], screenshots: [], errors: [], external: [] };
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
async function mount(spec) { await page.evaluate(spec => mountFixture(spec), spec); await page.getByRole('dialog', { name: '工序 20 · 热处理' }).waitFor(); await page.waitForFunction(() => fixtureState.choicesRead === 1 && document.querySelector('select option[value="'+(302).toString(16).padStart(48,'0')+'"]')); }
async function shot(name) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => Array.from(document.querySelectorAll('.modal-bg')).filter(node => node.getClientRects().length).every(node => getComputedStyle(node).opacity === '1'));
  const box = await page.getByRole('dialog').boundingBox(), viewport = page.viewportSize();
  assert(box.x >= 0 && box.y >= 0 && box.x + box.width <= viewport.width + 1 && box.y + box.height <= viewport.height + 1, 'dialog stays inside viewport');
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'no page horizontal overflow');
  const nameOnDisk = variant + '-' + name + '.png'; await page.screenshot({ path: path.join(output, nameOnDisk) }); report.screenshots.push(nameOnDisk);
}
async function run(name, action) { try { await action(); report.cases.push({ name, variant, passed: true }); } catch (error) { report.cases.push({ name, variant, passed: false, error: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') }); throw error; } }
async function cases() {
  for (const days of [0.04, 6.75]) await run('merged-' + days + '-readonly', async () => {
    await mount({ mode: 'merged', days }); const supplier = page.getByRole('combobox', { name: '供应商', exact: true });
    assert(await supplier.isDisabled()); assert.equal(await supplier.inputValue(), (301).toString(16).padStart(48, '0'));
    assert.equal(await button('保存工序').count(), 0); assert.equal(await page.getByRole('textbox', { name: '外协周期（天）', exact: true }).count(), 0);
    const text = await page.getByRole('dialog').innerText(); assert(text.includes('工序 20 至 30 · 整段周期 ' + days + ' 天（只读）')); assert(text.includes('合并外协段不能逐道更换供应商'));
    assert(!text.includes('WB-')); assert(!text.includes('0123456789abcdef0123456789abcdef')); assert(!/[0-9a-f]{48}/.test(text));
    await page.getByRole('dialog').locator('form').evaluate(form => form.requestSubmit()); assert.equal(await page.evaluate(() => fixtureState.commands.length), 0);
    await shot('merged-' + days); await page.getByRole('dialog').locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click();
    await page.waitForFunction(() => fixtureState.closed); assert.equal(await page.getByRole('dialog').count(), 0);
  });
  for (const mode of ['separate', 'ungrouped']) await run(mode + '-supplier-update', async () => {
    await mount({ mode, days: null }); const supplier = page.getByRole('combobox', { name: '供应商', exact: true }); assert(await supplier.isEnabled());
    assert(await page.getByRole('textbox', { name: '外协周期（天）', exact: true }).isEnabled()); assert.equal(await page.getByRole('textbox', { name: '外协周期（天）', exact: true }).inputValue(), '0.04');
    await supplier.selectOption((302).toString(16).padStart(48, '0')); assert(await button('保存工序').isEnabled()); await shot(mode + '-editable'); await button('保存工序').click();
    await page.waitForFunction(() => fixtureState.committed.length === 1); const saved = await page.evaluate(() => fixtureState.commands[0]);
    assert.equal(saved.kind, 'batch'); assert.equal(saved.action, 'operation_update'); assert.equal(saved.entityRef, (1).toString(16).padStart(48, '0'));
    assert.equal(saved.body.input.operation_ref, (1000).toString(16).padStart(48, '0')); assert.deepEqual(saved.body.input.fields, { supplier_ref: (302).toString(16).padStart(48, '0') });
    assert.equal(await page.evaluate(() => fixtureState.commands.length), 1);
    await page.getByRole('dialog').locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click(); await page.waitForFunction(() => fixtureState.closed);
    assert.equal(await page.evaluate(() => fixtureState.pending), null);
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
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'batch-merged-supplier-result.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length, screenshots: report.screenshots.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
