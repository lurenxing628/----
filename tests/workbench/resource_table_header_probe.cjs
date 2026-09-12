/* Isolated demo envelopes. Compiles current sources in memory; no global build or database. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http');
const path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const files = ['resource-contract.js', 'WorkbenchGuards.js', 'WorkbenchReferences.jsx', 'ResourceControls.jsx', 'WorkbenchControlStyles.jsx', 'ResourceTableFilterModel.js', 'ResourceTableFilter.jsx', 'ResourceTableHeader.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const styleSources = ['00-tokens.css', '20-controls.css', '21-table-frame.css', '22-shared-controls.css', '31-batches-resources.css']
  .map(name => ({ path: 'frontend/workbench/app/styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
const assets = new Map(manifest.files.map(item => [item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const fixtureCode = `
const key = n => n.toString(16).padStart(64,'0');
const values = Array.from({length:2000},(_,i)=>({key:key(i+1),label:i===0?'':i===1?'车削、铣削 / 组合技能':i===2?'超长业务单元格'.repeat(16):'设备值 '+String(i+1).padStart(4,'0'),count:i%4+1}));
function envelope(data,snapshot) {return {ok:true,schema_version:1,data,meta:{source:'demo',time_basis:'factory_local',snapshot_ref:snapshot,request_ref:'component-only',as_of:'2026-09-09T08:00:00'},warnings:[]};}
let renderRoot;
window.mountFixture = spec => {
  if(renderRoot)renderRoot.unmount();
  window.fixture={facets:[],selections:[],filters:[],sorts:[],widths:[],aborted:[],settled:[],spec,serial:0};
  renderRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));renderRoot.render(React.createElement(Harness,{spec}));
};
function Harness({spec}) {
  const [filter,setFilter]=React.useState(spec.filter || null),[scope,setScope]=React.useState({query:'基础搜索',status:'active',category:'internal',source:'demo',page:7,size:50,snapshot_ref:'LIST-NOT-FACET',column_filters:{other:{mode:'include',values:[key(99)]}}});
  const [sort,setSort]=React.useState({sort:null,direction:null,sortActive:false}),[width,setWidth]=React.useState(spec.width || 220),[disabled,setDisabled]=React.useState(false),[shown,setShown]=React.useState(true),[reversed,setReversed]=React.useState(false);
  const [matchingCount,setCount]=React.useState(spec.unknownCount?undefined:1234),[kind,setKind]=React.useState('machine');
  fixture.current={filter,scope,sort,width,disabled,kind}; fixture.changeScope=patch=>setScope(old=>({...old,...patch}));fixture.setFilter=setFilter;fixture.disable=setDisabled;fixture.hide=()=>setShown(false);fixture.reverse=()=>setReversed(v=>!v);fixture.setKind=setKind;
  const request = async (method,kind,query,signal) => {
    const call={kind,query,id:++fixture.serial};fixture[method].push(call);
    signal.addEventListener('abort',()=>fixture.aborted.push(call.id),{once:true});
    const behavior=fixture.spec;
    const delay=query.query==='slow'?180:method==='selections'?(behavior.selectionDelay || 15):10;
    const snapshot=query.snapshot_ref || 'facet:'+query.query;
    let rows=values.filter(row=>!query.query || (query.query==='slow'?row.label.includes('000'):query.query==='fast'?row.label.includes('199'):row.label.includes(query.query)));
    if(behavior.empty)rows=[];
    await new Promise(resolve=>setTimeout(resolve,delay));
    if(behavior.holdSelection && method==='selections')await new Promise(resolve=>{fixture.releaseSelection=resolve;});
    fixture.settled.push(call.id);
    if(behavior.failFacets&&method==='facets'||behavior.failSelection&&method==='selections'||behavior.failPage&&query.page===2)
      throw {ok:false,error:{message:method==='selections'?'完整匹配值读取失败，未改变筛选。':'列值读取失败，请回到首页重新读取。'}};
    if(behavior.capacity&&method==='selections')throw {ok:false,error:{message:'匹配值超过 50000 个，容量拒绝，未截断。'}};
    let data=method==='facets'?{column:query.column,basis:'toolbar_scope',options:rows.slice((query.page-1)*100,query.page*100),page:{number:query.page,size:100,total:rows.length,pages:Math.max(1,Math.ceil(rows.length/100))},row_count:5000}:{column:query.column,basis:'toolbar_scope',keys:rows.map(row=>row.key),total:rows.length};
    if(behavior.badKey&&method==='facets'&&data.options.length)data.options=[{...data.options[0],key:'a'.repeat(48)},...data.options.slice(1)];
    const raw=envelope(data,behavior.stalePage&&query.page===2?'changed-snapshot':snapshot);
    if(behavior.warning)raw.warnings=[{message:'测试范围说明：仅组件示例'}];
    return raw;
  };
  // Deliberately recreated each render: callbacks updating the list must not restart facets.
  const adapter={facets:(...args)=>request('facets',...args),facetSelection:(...args)=>request('selections',...args)};
  const renderedWidth=spec.actualWidth&&!fixture.widths.some(row=>row.key==='name')?spec.actualWidth:width;
  const main=shown&&React.createElement('th',{key:'name',style:{width:renderedWidth,padding:'6px 8px'}},React.createElement(ResourceTableHeader,{column:{key:'name',title:spec.longTitle?'非常长的资源名称列标题':'名称'},kind,scope,adapter,filter,matchingCount,width,onResize:value=>{fixture.widths.push({key:'name',value});setWidth(value);},...sort,
    disabled,onSort:(column,dir)=>{fixture.sorts.push([column,dir]);setSort({sort:column,direction:dir,sortActive:dir!==null});},onFilter:rule=>{fixture.filters.push(rule);setFilter(rule);setCount(rule===null?1234:432);setScope(old=>({...old,page:1,snapshot_ref:'LIST-AFTER-'+fixture.filters.length,column_filters:{...old.column_filters,name:rule}}));}}));
  const other=React.createElement('th',{key:'other',style:{width:120,padding:'6px 8px'}},React.createElement(ResourceTableHeader,{column:{key:'qty',title:'数量',numeric:true},kind,scope,adapter,filter:null,width:120,...sort,onSort:(column,dir)=>{fixture.sorts.push([column,dir]);setSort({sort:column,direction:dir,sortActive:dir!==null});},onFilter:()=>{},onResize:value=>fixture.widths.push({key:'qty',value})}));
  const table=React.createElement('div',{style:{overflowX:'auto',maxWidth:'100%'}},React.createElement('table',{style:{tableLayout:'fixed',width:renderedWidth+120,borderCollapse:'collapse'}},React.createElement('thead',null,React.createElement('tr',null,reversed?[other,main]:[main,other])),React.createElement('tbody',null,React.createElement('tr',null,React.createElement('td',null,'设备资源'),React.createElement('td',null,'123')))));
  const content=React.createElement('div',{className:'plana',style:spec.corner?{position:'fixed',right:8,bottom:8,maxWidth:'95vw',width:width+120}:{padding:16}},table);
  return React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),spec.modal?React.createElement(ResourceControls.Modal,{title:'资源主弹窗',onClose:()=>{fixture.parentClosed=true;},footer:React.createElement(ResourceControls.Button,null,'主弹窗按钮')},content):content);
}
`;
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const html = '<!doctype html><html><head><meta charset="utf-8"><link rel="icon" href="/static/' + manifest.icon + '">' +
  manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') + '<style>' + styleSources.map(source => source.code).join('\n') + '</style>' +
  '</head><body class="aps-workbench"><main class="plana" style="padding:24px"><button id="outside" type="button" class="btn">弹层外部</button><div id="fixture-root"></div></main>' +
  staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') +
  Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixtureCode + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); return; }
  const asset = assets.get(name.slice('/static/'.length));
  if (!name.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const result = { scope: 'isolated-component-fixtures', data_source: 'demo', production_persistence_tested: false,
  sources: sources.concat(styleSources).map(item => ({ path: item.path, sha256: hash(item.code) })),
  probes: [__filename, path.join(__dirname, 'test_resource_table_header_widgets.py')].map(file => ({ path: path.relative(root, file), sha256: hash(fs.readFileSync(file)) })),
  assets: [...new Set([...manifest.styles, ...staticScripts])].map(file => ({ path: 'static/' + file, sha256: hash(assets.get(file).bytes) })),
  cases: [], screenshots: [], errors: [], external: [] };
let page, variant;
const key = n => n.toString(16).padStart(64, '0');
const popup = () => page.locator('[data-wb-table-filter]');
const button = name => page.getByRole('button', { name, exact: true });
const all = () => popup().getByRole('checkbox', { name: '全选', exact: true });
const option = n => popup().locator('[data-facet-key="' + key(n) + '"] input');
async function mount(spec = {}) { await page.evaluate(spec => mountFixture(spec), spec); await page.locator('[data-column-key="name"]').waitFor(); }
async function open() { await button('筛选名称').click(); await popup().waitFor(); }
async function ready() { await page.waitForFunction(() => { const el = document.querySelector('.wb-table-facet-options'); return el && el.getAttribute('aria-busy') === 'false'; }); }
async function filterValue() { return page.evaluate(() => fixture.current.filter); }
async function search(value) { await popup().getByRole('textbox').fill(value); await ready(); }
async function shot(name) {
  const geometry = await page.evaluate(() => {
    const el = document.querySelector('[data-wb-table-filter]'), r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, viewport: [innerWidth, innerHeight], scrollWidth: el.scrollWidth, width: el.clientWidth,
      clipped: Array.from(el.querySelectorAll('button')).filter(node => node.scrollWidth > node.clientWidth + 1).map(node => node.textContent),
      background: getComputedStyle(el).backgroundColor, filterIcons: document.querySelectorAll('.wb-th-filter svg').length,
      sortIcons: document.querySelectorAll('.wb-th-sort-glyph svg').length,
      parentModal: el.parentElement.closest('[role="dialog"]') && (() => { const parent = el.parentElement.closest('[role="dialog"]'), rect = parent.getBoundingClientRect(); return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, backdrop: getComputedStyle(parent.parentElement).position }; })() };
  });
  assert(geometry.left >= 8 && geometry.top >= 8 && geometry.right <= geometry.viewport[0] - 7 && geometry.bottom <= geometry.viewport[1] - 7, 'popup viewport clamp');
  assert(geometry.scrollWidth <= geometry.width + 1, 'popup horizontal overflow'); assert.deepEqual(geometry.clipped, []);
  assert.equal(geometry.filterIcons, 2, 'both filter controls retain bundled icons');
  assert(geometry.sortIcons <= 1, 'only the active sort direction has a glyph');
  if (geometry.parentModal) { assert.equal(geometry.parentModal.backdrop, 'fixed'); assert(geometry.parentModal.left >= 0 && geometry.parentModal.right <= geometry.viewport[0] && geometry.parentModal.top >= 0 && geometry.parentModal.bottom <= geometry.viewport[1], 'real styled parent modal framing'); }
  const file = variant + '-' + name + '.png'; await page.screenshot({ path: path.join(output, file) }); result.screenshots.push({ variant, name, file, geometry });
}
async function run(name, test) {
  try { await test(); result.cases.push({ variant, name, passed: true }); }
  catch (error) { result.cases.push({ variant, name, passed: false, message: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') }); throw error; }
}
async function cases() {
  await run('instant-commit-preserves-menu-list-and-snapshot', async () => {
    await mount(); await open(); await ready(); assert(await all().isChecked()); assert.equal(await popup().getByText('1234 行匹配').count(), 1);
    assert.equal(await popup().getByRole('button', { name: /应用|取消/ }).count(), 0);
    await option(1).uncheck(); await ready(); assert.deepEqual(await filterValue(), { mode: 'exclude', values: [key(1)] });
    assert.equal(await popup().count(), 1); assert.equal(await popup().getByText('432 行匹配').count(), 1);
    await page.evaluate(() => fixture.changeScope({ page: 12, snapshot_ref: 'another-list', sort: 'qty', direction: 'desc', column_filters: { elsewhere: { mode: 'include', values: [] } } }));
    await page.waitForTimeout(30); assert.equal(await popup().count(), 1); assert.equal(await page.evaluate(() => fixture.facets.length), 1);
    const calls = await page.evaluate(() => [...fixture.facets, ...fixture.selections]);
    assert(calls.every(call => JSON.stringify(call.query.scope) === JSON.stringify({ query: '基础搜索', status: 'active', category: 'internal', source: 'demo' })));
    assert(!('snapshot_ref' in calls[0].query)); assert.equal(calls[1].query.snapshot_ref, 'facet:');
    await shot('instant-long-empty-values'); await page.keyboard.press('Escape'); assert.equal(await popup().count(), 0); assert.deepEqual(await filterValue(), { mode: 'exclude', values: [key(1)] });
    await page.waitForFunction(() => document.activeElement && document.activeElement.getAttribute('aria-label') === '筛选名称');
    assert(await button('筛选名称').evaluate(el => el === document.activeElement));
    await open(); await ready(); await option(2).uncheck(); await button('弹层外部').click(); assert.deepEqual(await filterValue(), { mode: 'exclude', values: [key(1), key(2)] });
    await open(); await ready(); await button('清除').click(); assert.equal(await filterValue(), null); assert.equal(await popup().count(), 0);
  });
  await run('all-2000-values-and-page-cache', async () => {
    await mount(); await open(); await ready(); await all().uncheck(); assert.deepEqual(await filterValue(), { mode: 'include', values: [] });
    await button('列值下一页').click(); await ready(); assert(!(await option(101).isChecked()));
    await option(101).check(); await ready(); assert(await all().evaluate(el => el.indeterminate));
    await button('列值上一页').click(); await ready(); assert(!(await option(1).isChecked()));
    assert.equal(await page.evaluate(() => fixture.selections.length), 1);
    await all().check(); assert.deepEqual(await filterValue(), { mode: 'exclude', values: [] });
    assert.equal(await page.evaluate(() => fixture.facets[1].query.snapshot_ref), 'facet:');
    await button('列值下一页').click(); await ready(); assert(await option(200).isChecked());
  });
  await run('search-bulk-include-exclude-preserves-unseen', async () => {
    await mount({ filter: { mode: 'include', values: [key(2), key(1900)] } }); await open(); await ready(); await search('设备值 1');
    assert(await all().evaluate(el => el.indeterminate)); await all().check();
    let rule = await filterValue(); assert.equal(rule.values.length, 1001); assert(rule.values.includes(key(2)) && rule.values.includes(key(1999)));
    await all().uncheck(); assert.deepEqual(await filterValue(), { mode: 'include', values: [key(2)] });
    await page.evaluate(key => fixture.setFilter({ mode: 'exclude', values: [key, '0'.repeat(60) + '0770'] }), key(2));
    await ready(); assert(await all().evaluate(el => el.indeterminate)); await all().check();
    assert.deepEqual(await filterValue(), { mode: 'exclude', values: [key(2)] }); await all().uncheck(); rule = await filterValue();
    assert.equal(rule.values.length, 1001); assert(rule.values.includes(key(2)) && rule.values.includes(key(1000)) && rule.values.includes(key(1999)));
    assert.equal(await page.evaluate(() => fixture.selections.filter(call => call.query.query === '设备值 1').length), 1);
    await shot('search-bulk');
  });
  await run('exact-tristate-not-first-page-and-whole-cell', async () => {
    await mount({ filter: { mode: 'include', values: Array.from({ length: 100 }, (_, i) => key(i + 1000)) } }); await open(); await ready(); await search('设备值 1');
    assert(await all().evaluate(el => !el.checked && el.indeterminate)); assert.equal(await popup().locator('[data-facet-key]').count(), 100);
    await search(' 组合技能 '); assert.equal(await popup().locator('[data-facet-key]').count(), 1); await all().check();
    assert((await filterValue()).values.includes(key(2))); assert.equal((await filterValue()).values.length, 101);
    await search('完全不存在'); assert(await all().isDisabled()); assert.equal(await popup().getByText('没有匹配的列值').count(), 1);
    await search('   '); await page.evaluate(() => fixture.setFilter({ mode: 'exclude', values: ['f'.repeat(64)] })); await ready();
    assert(await all().isChecked(), 'excluded missing value is not a mixed existing universe');
  });
  await run('async-group-cancel-stale-and-failure-preserves-filter', async () => {
    await mount({ selectionDelay: 140, holdSelection: true }); await open(); await ready(); await popup().getByRole('textbox').fill('设备值 1');
    await page.waitForFunction(() => typeof fixture.releaseSelection === 'function');
    await popup().getByText('正在读取全部匹配值…').waitFor(); assert(await all().isDisabled()); assert.equal(await filterValue(), null);
    await page.evaluate(() => { fixture.spec.holdSelection = false; fixture.releaseSelection(); fixture.releaseSelection = null; });
    await ready(); await page.evaluate(() => fixture.spec.failSelection = true); await search('设备值 2');
    assert.equal(await popup().getByRole('alert').count(), 1); assert(await all().isDisabled()); assert.equal(await filterValue(), null);
    await page.evaluate(() => fixture.spec.failSelection = false); await button('回到首页重新读取').click(); await ready(); assert(!(await all().isDisabled()));
    await popup().getByRole('textbox').fill('slow'); await page.waitForFunction(() => fixture.facets.some(call => call.query.query === 'slow'));
    await popup().getByRole('textbox').fill('fast'); await ready(); await page.waitForTimeout(230);
    assert.equal(await popup().locator('[data-facet-key]').count(), 12); assert.equal(await popup().getByRole('textbox').inputValue(), 'fast');
    assert(await page.evaluate(() => fixture.facets.filter(call => call.query.query === 'slow').every(call => fixture.aborted.includes(call.id))));
    await popup().getByRole('textbox').fill('设备值 1'); await page.waitForFunction(() => fixture.selections.filter(call => call.query.query === '设备值 1').length === 2);
    const canceled = await page.evaluate(() => fixture.selections[fixture.selections.length - 1].id);
    await search('设备值 2'); await page.waitForTimeout(160); assert(await page.evaluate(id => fixture.aborted.includes(id), canceled));
    assert.equal(await popup().getByRole('textbox').inputValue(), '设备值 2');
    await popup().getByRole('textbox').fill('设备值 1'); await page.waitForFunction(() => fixture.selections.filter(call => call.query.query === '设备值 1').length === 3);
    await page.keyboard.press('Escape'); await page.waitForTimeout(180); assert.equal(await popup().count(), 0); assert.equal(await filterValue(), null);
    assert(await page.evaluate(() => fixture.aborted.includes(fixture.selections[fixture.selections.length - 1].id)));
  });
  await run('explicit-capacity-api-empty-and-stale-page', async () => {
    await mount({ capacity: true }); await open(); await ready(); await search('设备值'); assert(await popup().getByText(/容量拒绝/).isVisible()); assert.equal(await filterValue(), null);
    await mount({ failFacets: true, filter: { mode: 'include', values: [key(2)] } }); await open(); await ready(); assert(await button('回到首页重新读取').isVisible()); assert.equal(await popup().locator('[data-facet-key]').count(), 0);
    assert.equal(await popup().getByText('正在读取全部匹配值…').count(), 0); assert.deepEqual(await filterValue(), { mode: 'include', values: [key(2)] });
    await page.evaluate(() => fixture.spec.failFacets = false); await button('回到首页重新读取').click(); await ready(); assert.equal(await popup().locator('[data-facet-key]').count(), 100);
    await mount({ stalePage: true }); await open(); await ready(); await button('列值下一页').click(); await ready(); assert(await popup().getByText(/快照已经变化/).isVisible());
    await button('回到首页重新读取').click(); await ready(); assert.equal(await page.evaluate(() => fixture.facets[fixture.facets.length - 1].query.page), 1);
    assert(await page.evaluate(() => !('snapshot_ref' in fixture.facets[fixture.facets.length - 1].query)));
    await mount({ badKey: true }); await open(); await ready(); assert(await popup().getByText(/列值标识、文字或数量/).isVisible());
    await mount({ empty: true, unknownCount: true }); await open(); await ready(); assert(await all().isDisabled()); assert(await popup().getByText('当前范围没有列值').isVisible()); assert(await popup().getByText('匹配行数待读取').isVisible()); await shot('empty');
  });
  await run('base-scope-source-kind-disabled-and-modal-escape', async () => {
    for (const patch of [{ status: 'inactive' }, { category: 'external' }, { query: '新的基础查询' }, { source: 'production' }]) {
      await mount(); await open(); await ready(); await page.evaluate(patch => fixture.changeScope(patch), patch); await popup().waitFor({ state: 'detached' });
    }
    await mount(); await open(); await ready(); await page.evaluate(() => fixture.setKind('operator')); await popup().waitFor({ state: 'detached' });
    await open(); await ready(); await page.evaluate(() => fixture.disable(true)); await popup().waitFor({ state: 'detached' }); assert(await button('筛选名称').isDisabled()); assert(await button('名称排序').isDisabled());
    await mount({ modal: true }); await button('筛选名称').focus(); await page.keyboard.press('Enter'); await ready();
    assert(await popup().evaluate(el => !!el.parentElement.closest('[role="dialog"]'))); await shot('modal');
    await button('清除').focus(); await page.keyboard.press('Tab'); assert(await button('关闭列筛选').evaluate(el => el === document.activeElement));
    await page.keyboard.press('Shift+Tab'); assert(await button('清除').evaluate(el => el === document.activeElement));
    await page.keyboard.press('Escape'); assert.equal(await popup().count(), 0); assert(!(await page.evaluate(() => fixture.parentClosed)));
    await page.keyboard.press('Escape'); assert(await page.evaluate(() => fixture.parentClosed));
  });
  await run('sort-three-state-independent-filter', async () => {
    await mount({ filter: { mode: 'include', values: [] } });
    for (let i = 0; i < 3; i++) await button('名称排序').click();
    assert.deepEqual(await page.evaluate(() => fixture.sorts), [['name', 'asc'], ['name', 'desc'], ['name', null]]); assert.deepEqual(await filterValue(), { mode: 'include', values: [] });
    await button('数量排序').click(); await button('名称排序').click(); assert.deepEqual(await page.evaluate(() => fixture.sorts.slice(-2)), [['qty', 'asc'], ['name', 'asc']]);
    await button('名称排序').focus(); await page.keyboard.press('Space'); assert.deepEqual(await page.evaluate(() => fixture.sorts.slice(-1)), [['name', 'desc']]);
  });
  await run('resize-keyboard-pointer-minimum-no-maximum-reorder', async () => {
    await mount(); const grip = page.getByRole('separator', { name: '调整名称列宽' }); await grip.focus();
    await page.keyboard.press('ArrowRight'); await page.keyboard.press('Shift+ArrowRight'); assert.equal(await page.evaluate(() => fixture.current.width), 260);
    await page.keyboard.press('ArrowLeft'); assert.equal(await page.evaluate(() => fixture.current.width), 252); await page.keyboard.press('Home'); assert.equal(await page.evaluate(() => fixture.current.width), 56);
    await page.keyboard.press('ArrowLeft'); assert.equal(await page.evaluate(() => fixture.current.width), 56);
    let r = await grip.boundingBox(); await page.mouse.move(r.x + 4, r.y + r.height / 2); await page.mouse.down(); await page.mouse.move(r.x + 404, r.y + r.height / 2); await page.mouse.up();
    assert.equal(await page.evaluate(() => fixture.current.width), 456); assert.equal(await page.evaluate(() => document.body.style.cursor), '');
    await page.evaluate(() => fixture.reverse()); r = await grip.boundingBox(); await page.mouse.move(r.x + 4, r.y + r.height / 2); await page.mouse.down(); await page.mouse.move(r.x + 104, r.y + r.height / 2); await page.keyboard.press('Escape'); await page.mouse.up();
    assert.equal(await page.evaluate(() => fixture.current.width), 456); assert(await page.evaluate(() => fixture.widths.every(row => row.key === 'name')));
    await grip.focus(); for (let i = 0; i < 30; i++) await page.keyboard.press('Shift+ArrowRight'); assert.equal(await page.evaluate(() => fixture.current.width), 1416);
    await page.keyboard.press('Home'); r = await grip.boundingBox(); await page.mouse.move(r.x + 4, r.y + r.height / 2); await page.mouse.down(); await page.evaluate(() => fixture.hide()); await page.mouse.up();
    assert.equal(await page.evaluate(() => document.body.style.cursor), ''); assert.equal(await page.evaluate(() => document.body.style.userSelect), '');
  });
  await run('scroll-containment-corner-framing-and-warning', async () => {
    await mount({ corner: true, warning: true }); await open(); await ready(); await shot('corner');
    await popup().locator('.wb-table-facet-options').evaluate(el => el.scrollTop = 1200); await page.waitForTimeout(40); assert.equal(await popup().count(), 1);
    await page.locator('table').evaluate(el => { el.parentElement.style.width = '200px'; el.parentElement.scrollLeft = 10; }); await popup().waitFor({ state: 'detached' });
    await mount({ filter: { mode: 'include', values: ['a'.repeat(48)] } }); await open(); await ready(); assert(await popup().getByText(/本列筛选规则不完整/).isVisible());
    assert(await all().isDisabled()); await button('清除').click(); assert.equal(await filterValue(), null);
  });
  await run('queued-before-open-scroll-does-not-dismiss-new-popup', async () => {
    await mount();
    // Scroll queues a native event before the discrete click mounts the popup.
    await page.locator('table').evaluate(table => {
      const viewport = table.parentElement; viewport.style.width = '200px'; viewport.scrollLeft = 10;
      table.querySelector('[data-column-key="name"] .wb-th-filter').click();
    });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await popup().count(), 1, 'pre-open queued scroll must not close a newly opened menu');
    await ready();
    await page.locator('table').evaluate(table => table.parentElement.dispatchEvent(new Event('scroll')));
    assert.equal(await popup().count(), 1, 'an unchanged scroll position cannot invalidate the popup anchor');
    await page.locator('table').evaluate(table => table.parentElement.scrollLeft += 10);
    await popup().waitFor({ state: 'detached' });
  });
  await run('shorter-list-scroll-clamp-retains-menu-and-next-scroll-closes', async () => {
    await mount();
    await page.evaluate(() => { document.querySelector('main').style.paddingTop = '650px'; document.body.style.minHeight = '4000px';
      document.documentElement.style.setProperty('overflow-anchor', 'auto', 'important'); window.scrollTo(0, 600); });
    await page.waitForFunction(() => document.scrollingElement.scrollTop === 600);
    await open(); await ready();
    const previous = await page.evaluate(() => document.scrollingElement.scrollTop);
    await page.evaluate(() => document.body.style.minHeight = '1300px');
    await page.waitForFunction(before => document.scrollingElement.scrollTop < before, previous);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await popup().count(), 1, 'Native document clamp after a shorter list must keep the same menu');
    const clamped = await page.evaluate(() => document.scrollingElement.scrollTop);
    await page.evaluate(() => { document.querySelector('main').style.paddingTop = '696px'; document.body.style.minHeight = '1346px'; });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.evaluate(() => document.scrollingElement.scrollTop), clamped, 'Completing the list cannot anchor-scroll the document');
    const geometry = await popup().evaluate(panel => {
      const owner = document.querySelector('[data-column-key="name"] .wb-th-filter').getBoundingClientRect(), box = panel.getBoundingClientRect();
      return { above: Math.abs(box.bottom - owner.top + 4), below: Math.abs(box.top - owner.bottom - 4) };
    });
    assert(Math.min(geometry.above, geometry.below) <= 1, 'Open menu must track its owner after list reflow');
    await all().uncheck(); await ready(); assert.equal(await popup().count(), 1);
    await page.evaluate(() => window.scrollBy(0, -30)); await popup().waitFor({ state: 'detached' });
    assert.deepEqual(await page.evaluate(() => ['overflow-anchor'].map(name => [document.documentElement.style.getPropertyValue(name), document.documentElement.style.getPropertyPriority(name)])), [['auto', 'important']]);
    await page.evaluate(() => { document.querySelector('main').style.paddingTop = '24px'; document.body.style.minHeight = '';
      document.documentElement.style.removeProperty('overflow-anchor'); window.scrollTo(0, 0); });
  });
  await run('narrow-long-title-and-large-selection-render', async () => {
    await mount({ width: 56, longTitle: true });
    const geometry = await page.locator('[data-column-key="name"]').evaluate(el => {
      const sort = el.querySelector('.wb-th-sort').getBoundingClientRect(), filter = el.querySelector('.wb-th-filter').getBoundingClientRect(), th = el.closest('th').getBoundingClientRect();
      return { sort: { left: sort.left, right: sort.right }, filter: { left: filter.left, right: filter.right }, th: { left: th.left, right: th.right } };
    });
    assert(geometry.sort.right <= geometry.filter.left && geometry.filter.right <= geometry.th.right, '56px column controls cannot overlap adjacent column');
    await button('筛选非常长的资源名称列标题').click(); await ready(); await shot('narrow-long-title');
    await mount({ filter: { mode: 'include', values: Array.from({ length: 50000 }, (_, i) => key(i + 1)) } }); await open(); await ready();
    assert(await all().isChecked()); await option(1).uncheck(); await ready(); assert.equal((await filterValue()).values.length, 49999);
    assert(await all().evaluate(el => el.indeterminate)); assert.equal(await page.evaluate(() => fixture.selections.length), 1);
  });
  await run('over-capacity-toggle-and-bulk-show-error-without-callback', async () => {
    const original = { mode: 'include', values: Array.from({ length: 50000 }, (_, i) => key(i + 50001)) };
    await mount({ filter: original }); await open(); await ready(); await option(1).click();
    assert(await popup().getByText(/本次选择会使本列筛选超过 50000/).isVisible()); assert(!(await option(1).isChecked()));
    assert.equal(await page.evaluate(() => fixture.filters.length), 0); assert.deepEqual(await filterValue(), original);
    await search('设备值 1'); await all().click(); assert(!(await all().isChecked()));
    assert.equal(await page.evaluate(() => fixture.filters.length), 0); assert.deepEqual(await filterValue(), original);
    assert.equal(await popup().count(), 1); await shot('over-capacity');
    await page.evaluate(() => fixture.setFilter({ mode: 'include', values: fixture.current.filter.values.slice(0, 48000) }));
    await all().check(); assert.equal((await filterValue()).values.length, 49000); assert.equal(await popup().getByRole('alert').count(), 0);
    await button('清除').click(); assert.equal(await filterValue(), null);
  });
  await run('resize-starts-from-rendered-th-not-stale-width-prop', async () => {
    await mount({ width: 220, actualWidth: 340 }); let grip = page.getByRole('separator', { name: '调整名称列宽' });
    await page.waitForFunction(() => document.querySelector('[aria-label="调整名称列宽"]').getAttribute('aria-valuenow') === '340');
    let r = await grip.boundingBox(); await page.mouse.move(r.x + 4, r.y + r.height / 2); await page.mouse.down(); await page.mouse.move(r.x + 44, r.y + r.height / 2); await page.mouse.up();
    assert.equal(await page.evaluate(() => fixture.widths[0].value), 380); assert.equal(await page.locator('[data-column-key="name"]').evaluate(el => el.closest('th').getBoundingClientRect().width), 380);
    await mount({ width: 220, actualWidth: 340 }); grip = page.getByRole('separator', { name: '调整名称列宽' }); await grip.focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await page.evaluate(() => fixture.widths[0].value), 348);
    r = await grip.boundingBox(); await page.mouse.move(r.x + 4, r.y + r.height / 2); await page.mouse.down(); await page.mouse.move(r.x + 54, r.y + r.height / 2);
    await page.evaluate(() => fixture.reverse()); await page.mouse.move(r.x + 84, r.y + r.height / 2); await page.mouse.up();
    assert(await page.evaluate(() => fixture.widths.every(row => row.key === 'name'))); assert.equal(await page.evaluate(() => document.body.style.cursor), '');
  });
}
async function modelCases() {
  await run('strict-model-envelope-key-capacity-and-immutable-bulk', async () => {
    const proof = await page.evaluate(() => {
      const M = ResourceTableFilterModel, failures = [], k = n => n.toString(16).padStart(64, '0');
      const request = { column: 'name', snapshot_ref: 'menu', expected_total: 2 }, good = { column: 'name', basis: 'toolbar_scope', keys: [k(1), k(2)], total: 2 };
      const rejection = data => { try { M.selection(envelope(data, 'menu'), request); return false; } catch (_) { return true; } };
      for (const data of [{ ...good, keys: [k(1), k(1)] }, { ...good, keys: ['a'.repeat(48), k(1)] }, { ...good, total: 1 }, { ...good, column: 'other' }, { ...good, total: 1, keys: [k(1)] }, { ...good, keys: Array.from({ length: 50001 }, (_, i) => k(i)), total: 50001 }]) if (!rejection(data)) failures.push('bad selection accepted');
      const original = { mode: 'exclude', values: [k(9)] }, keys = Array.from({ length: 50000 }, (_, i) => k(i + 1));
      const next = M.toggleKeys(original, keys, false); if (next.values.length !== 50000 || original.values.length !== 1) failures.push('bulk mutation');
      if (M.selection(envelope({ ...good, keys, total: 50000 }, 'menu'), { ...request, expected_total: 50000 }).data.total !== 50000) failures.push('exact capacity rejected');
      const restored = M.toggleKeys(next, keys, true); if (restored.values.length !== 0) failures.push('bulk clear');
      if (M.active(null) || !M.active({ mode: 'include', values: [] })) failures.push('empty include semantics');
      for (const operation of [() => M.toggle(next, k(50001), false), () => M.toggleKeys(next, [k(50001), k(50002)], false), () => M.rule({ mode: 'include', values: keys.concat(k(50001)) })]) {
        let rejected = false; try { operation(); } catch (_) { rejected = true; } if (!rejected) failures.push('accumulated capacity accepted');
      }
      return failures;
    }); assert.deepEqual(proof, []);
  });
}
(async () => {
  let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true }); result.browser = await browser.version();
    assert(result.browser.startsWith('109.'), 'Must use actual Chromium 109');
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) {
      variant = viewport.width + '-' + theme; const context = await browser.newContext({ viewport, timezoneId: 'Asia/Shanghai' }); page = await context.newPage(); page.setDefaultTimeout(6000);
      page.on('pageerror', error => result.errors.push({ variant, message: error.message })); page.on('console', event => { if (event.type() === 'error') result.errors.push({ variant, message: event.text() }); });
      page.on('request', request => { if (!request.url().startsWith(origin + '/') && !request.url().startsWith('data:')) result.external.push(request.url()); });
      await page.goto(origin); await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme); await cases(); await modelCases(); await context.close();
    }
    assert.deepEqual(result.errors, []); assert.deepEqual(result.external, []);
    result.source_hashes_still_match = [...result.sources, ...result.probes].every(item => hash(fs.readFileSync(path.join(root, item.path))) === item.sha256);
    assert(result.source_hashes_still_match, 'Sources changed during verification; rerun against current source');
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'table-header-result.json'), JSON.stringify(result, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, browser: result.browser, cases: result.cases.length, screenshots: result.screenshots.length, errors: result.errors, external: result.external }));
})().catch(error => { console.error(error); process.exitCode = 1; });
