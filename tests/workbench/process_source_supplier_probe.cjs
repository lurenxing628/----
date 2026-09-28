/* Current source in Chromium 109; choice/command adapters are explicit fixtures. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http');
const path = require('node:path'), crypto = require('node:crypto'), { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass a temporary artifact directory');
fs.mkdirSync(output, { recursive: true });
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'resource-contract.js',
  'resource-session.js', 'ResourceControls.jsx', 'ProcessContract.js', 'ProcessStageEditor.jsx', 'ProcessSourceEditor.jsx'];
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
const type=(id,label)=>({ref:ref(id),business_code:'OT'+id,label,status:null,fields:{category:'external'},relationships:{},issues:[],write_context:null});
const types=[type(101,'热处理'),type(102,'表面处理'),type(103,'包装')];
function supplier(id,label,ids,status='active'){return {ref:ref(id),business_code:'S'+id,label,status,fields:{default_days:3},relationships:{op_type_refs:ids.map(ref),op_types:ids.map(id=>types.find(row=>row.ref===ref(id)))},issues:[],write_context:null};}
function listing(rows,scope){const filtered=rows.filter(row=>!scope.query||row.label.includes(scope.query));return envelope({entities:filtered.slice((scope.page-1)*scope.size,scope.page*scope.size),page:{number:scope.page,size:scope.size,total:filtered.length,pages:Math.max(1,Math.ceil(filtered.length/scope.size)),sort:[]}});}
window.ResourceTables={Pager:({page,onPage,disabled})=>React.createElement('div',null,
  React.createElement('button',{disabled:disabled||page.number===1,onClick:()=>onPage(page.number-1)},'上一页'),
  React.createElement('span',null,'第 '+page.number+' 页'),
  React.createElement('button',{disabled:disabled||page.number>=page.pages,onClick:()=>onPage(page.number+1)},'下一页'))};
function makeEntity(count){const operations=Array.from({length:count},(_,i)=>({ref:ref(1000+i),sequence:(i+1)*10,label:types[i===1?1:0].label,source:'external',op_type_ref:ref(i===1?102:101),op_type_label:types[i===1?1:0].label,
  supplier_ref:ref(i<2?301:300),supplier_label:i<2?'共同供应商':'仅热处理厂',external_group_ref:ref(i<2?400:401),setup_hours:null,unit_hours:null,external_days:null,external_days_source:'group',status:'active',issues:[],confirmation:{source:stamp('unconfirmed'),hours:stamp('unconfirmed')}}));
  return {ref:ref(1),business_code:'P1',label:'零件',status:null,fields:{route_raw:'10热处理20表面处理30热处理',route_parsed:'yes',remark:null},relationships:{},issues:[],write_context:null,
    workflow:{origin:'managed',stage:'source',ready:false,route:stamp('confirmed'),source:stamp('unconfirmed'),hours:stamp('locked')},operations,
    external_groups:[{ref:ref(400),start_sequence:10,end_sequence:20,merge_mode:'merged',total_days:3,supplier_ref:ref(301),supplier_label:'共同供应商',remark:null,issues:[]},
      {ref:ref(401),start_sequence:30,end_sequence:count*10,merge_mode:'merged',total_days:4,supplier_ref:ref(300),supplier_label:'仅热处理厂',remark:null,issues:[]}],capabilities:{stage_confirm:true}};
}
let renderRoot;
window.mountFixture=(spec={})=>{if(renderRoot)renderRoot.unmount();const entity=makeEntity(spec.count||3);window.fixtureState={spec,entity,choices:[],commands:[],previewInputs:[]};
  const rows=spec.many?Array.from({length:50},(_,i)=>supplier(500+i,'仅热处理厂 '+i,[101])).concat([supplier(301,'共同供应商',[101,102])]):[
    supplier(300,'仅热处理厂',[101]),supplier(301,'共同供应商',[101,102]),supplier(302,'仅表面处理厂',[102]),supplier(303,'全部工种厂',[101,102,103]),supplier(304,'停用共同厂',[101,102],'inactive')];
  const adapter={command:async()=>{},choices:async(kind,scope)=>{fixtureState.choices.push({kind,scope:copy(scope)});return listing(kind==='supplier'?rows:types,scope);},
    stagePreview:async(part,action,input)=>{fixtureState.previewInputs.push(copy(input));if(spec.reject){throw APSResourceContract.failure('工序 '+entity.operations.at(-1).sequence+' 的供应商承接能力已变化。',[{path:'operations.'+entity.operations.at(-1).ref+'.supplier_ref',message:'请改选可承接本工种的供应商。'}]);}
      return envelope({part_ref:entity.ref,action,affected_groups:[],write_context:{write_token:'TOKEN',capabilities:{'process.source_confirm':true},blocked_reasons:[]}});}};
  const command={locked:false,phase:'idle',submit:async(kind,action,part,context,input)=>fixtureState.commands.push(copy(input))};
  renderRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));renderRoot.render(React.createElement('div',{className:'plana process-detail'},React.createElement(ProcessSourceEditor,{adapter,result:envelope(entity),command,saved:0,onOverlay:()=>{},focusRef:spec.focus?entity.operations.at(-1).ref:null})));};
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
const report = { scope: 'process-source-supplier-component', production_persistence_tested: false, compile: { target: compiled.target, global_build: false },
  sources: sources.map(row => ({ path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex') })), cases: [], errors: [], external: [], screenshots: [] };
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
async function mount(spec = {}) { await page.evaluate(spec => mountFixture(spec), spec); await page.locator('[data-process-source-editor]').waitFor(); }
async function run(name, action) { try { await action(); report.cases.push({ name, variant, passed: true }); } catch (error) { report.cases.push({ name, variant, passed: false, error: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') }); throw error; } }
async function cases() {
  await run('joint-capability-and-isolated-group-save', async () => {
    await mount(); await button('选择工序 10 供应商').click();
    const dialog = page.getByRole('dialog', { name: '选择供应商 · 外协段 10 至 20' }); await dialog.waitFor();
    assert((await dialog.innerText()).includes('10 热处理、20 表面处理'));
    assert(await button('采用 仅热处理厂').isDisabled()); assert(await button('采用 仅表面处理厂').isDisabled()); assert(await button('采用 停用共同厂').isDisabled());
    assert((await dialog.innerText()).includes('不能承接：工序 20 表面处理'));
    assert(await button('采用 共同供应商').isEnabled());
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => Array.from(document.querySelectorAll('.modal-bg')).filter(node => node.getClientRects().length).every(node => getComputedStyle(node).opacity === '1'));
    const shot = variant + '-supplier-choices.png'; await page.screenshot({ path: path.join(output, shot) }); report.screenshots.push(shot);
    await button('采用 全部工种厂').click(); await button('保存归属并继续').click(); await page.waitForFunction(() => fixtureState.commands.length === 1);
    const rows = await page.evaluate(() => fixtureState.commands[0].operations); assert.equal(rows[0].supplier_ref, rows[1].supplier_ref); assert.equal(rows[0].supplier_ref, (303).toString(16).padStart(48, '0')); assert.equal(rows[2].supplier_ref, (300).toString(16).padStart(48, '0'));
  });
  await run('changing-type-rechecks-whole-group', async () => {
    await mount(); await button('选择工序 10 工种').click(); await button('采用 包装').click();
    const rows = page.getByRole('table', { name: '归属明细' }).locator('tbody tr'); assert((await rows.nth(0).innerText()).includes('未选供应商')); assert((await rows.nth(1).innerText()).includes('未选供应商')); assert((await rows.nth(2).innerText()).includes('仅热处理厂'));
    await button('选择工序 20 供应商').click(); assert(await button('采用 共同供应商').isDisabled()); await button('采用 全部工种厂').click();
    await button('保存归属并继续').click(); await page.waitForFunction(() => fixtureState.commands.length === 1); assert.equal(await page.evaluate(() => fixtureState.commands[0].operations[0].op_type_ref), (103).toString(16).padStart(48, '0'));
  });
  await run('eligible-supplier-remains-reachable-by-page-and-search', async () => {
    await mount({ many: true }); await button('选择工序 10 供应商').click(); await button('采用 仅热处理厂 0').waitFor(); assert(await button('采用 仅热处理厂 0').isDisabled());
    await page.getByRole('dialog').getByRole('button', { name: '下一页', exact: true }).click(); await button('采用 共同供应商').waitFor(); assert(await button('采用 共同供应商').isEnabled());
    await page.getByRole('searchbox', { name: '搜索供应商' }).fill('共同'); await page.getByRole('dialog').getByRole('button', { name: '搜索', exact: true }).click(); await button('采用 共同供应商').waitFor();
    const scopes = await page.evaluate(() => fixtureState.choices.map(row => row.scope)); assert.equal(scopes.at(-2).page, 2); assert.equal(scopes.at(-2).snapshot_ref, 'fixture-snapshot'); assert.equal(scopes.at(-1).page, 1); assert.equal(scopes.at(-1).query, '共同');
    await button('采用 共同供应商').click();
  });
  await run('backend-operation-error-locates-hidden-page', async () => {
    await mount({ count: 60, reject: true }); await button('保存归属并继续').click(); await button('定位到第 2 页').waitFor(); await button('定位到第 2 页').click();
    assert((await page.getByRole('table', { name: '归属明细' }).innerText()).includes('600')); assert.equal(await page.evaluate(() => fixtureState.commands.length), 0);
  });
  await run('external-operation-focus-opens-correct-page', async () => {
    await mount({ count: 60, focus: true }); const target = page.locator('[data-process-source-editor] tr[aria-current=true]'); await target.waitFor(); assert((await target.innerText()).includes('600'));
    await page.waitForFunction(() => document.activeElement && document.activeElement.dataset.processLocation === fixtureState.entity.operations.at(-1).ref);
    assert.equal(await target.evaluate(node => document.activeElement === node), true);
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
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'source-supplier-result.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
