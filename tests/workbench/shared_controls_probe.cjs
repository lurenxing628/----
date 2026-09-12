'use strict';
// Current sources, isolated React fixtures and actual Chromium 109. No database or static build.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const { createHash } = require('node:crypto'), { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output || path.resolve(output).startsWith(root + path.sep)) throw new Error('Pass an artifact directory outside the checkout');
fs.mkdirSync(output, { recursive: true });
const names = ['resource-contract.js', 'WorkbenchReferences.jsx', 'WorkbenchGuards.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchDetailPanel.jsx'];
const sources = names.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const styles = fs.readdirSync(path.join(root, 'frontend/workbench/app/styles')).filter(name => /^(00|20|21|22)-/.test(name))
  .map(name => ({ path: 'frontend/workbench/app/styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(item => ['/static/' + item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const fixture = `
const h=React.createElement,R=ResourceControls,L=WorkbenchListControls;let host;
window.probe={calls:[],closed:0};
function Fields(){
 const form=React.useRef(null),error=APSResourceContract.failure('请核对字段。',[
  {path:'amount',message:'数量必填。'},{path:'input.amount',message:'数量必填。'},{path:'other',message:'未知字段保留。'}]);
 return h('form',{ref:form},h('span',{id:'outside-hint'},'原有说明'),h('input',{'aria-invalid':true,disabled:true}),
  h('details',{id:'field-section'},h('summary',null,'补充字段'),h(R.Field,{label:'数量',path:'amount',error,required:true,hint:'必须输入数量。'},h('input',{id:'stable-amount','aria-describedby':'outside-hint',defaultValue:''}))),
  h(R.ErrorBox,{error,excludePaths:['amount']}),h(R.Button,{onClick:()=>probe.focused=R.focusFirstInvalid(form.current)},'定位无效字段'));
}
function DuplicateSummary(){const error=APSResourceContract.failure('数量必填。',[{path:'amount',message:'数量必填。'}]);
 return h('div',null,h(R.Field,{label:'数量',path:'amount',error},h('input')),h(R.ErrorBox,{error,excludePaths:['input.amount']}));}
function Detail(){const [opened,setOpened]=React.useState(false),[key,setKey]=React.useState(1);return h('div',{className:'wb-detail-layout'},
 h('section',null,h('button',{id:'detail-trigger',onClick:()=>setOpened(true)},'查看条目'),h('p',null,'列表内容'),h('button',{id:'detail-next',onClick:()=>{setKey(v=>v+1);setOpened(true);}},'下一条')),
 opened&&h(WorkbenchDetailPanel,{title:'条目详情',detailKey:key,subtitle:'共用详情',onClose:()=>{probe.closed++;setOpened(false);}},h('button',null,'详情动作')));}
function Guarded(){const [opened,setOpened]=React.useState(false);const owner=WorkbenchGuards.useDirtyGuard({owner:'shared-probe',dirty:opened,message:'草稿尚未保存。'});
 return h('div',null,h('button',{id:'guard-trigger',onClick:()=>setOpened(true)},'打开编辑'),opened&&h(R.Modal,{title:'草稿编辑',guardOwner:owner,onClose:detail=>{probe.calls.push(detail);setOpened(false);}},h('div',{className:'modal-b'},h('input',{defaultValue:'尚未保存', 'aria-label':'草稿'}))));}
function Readonly(){const [opened,setOpened]=React.useState(true);WorkbenchGuards.useDirtyGuard({owner:'other-editor',dirty:true,message:'别处草稿'});
 return opened&&h(R.Modal,{title:'只读详情',onClose:()=>{probe.closed++;setOpened(false);}},h('div',{className:'modal-b'},'只读记录'));}
const cases={fields:()=>h(Fields),duplicate:()=>h(DuplicateSummary),detail:()=>h(Detail),guard:()=>h(Guarded),readonly:()=>h(Readonly),
 autoDetail:()=>h('div',{style:{marginTop:1000}},h(WorkbenchDetailPanel,{title:'自动首条预览',autoFocus:false},'初始概览')),
 pager:()=>h(L.Pager,{page:{number:2,pages:3,total:64,size:25},sizes:[10,25,50],unit:'条',label:'系统',sizeLabel:'每页数量',showPageJump:true,jumpActionLabel:'跳转系统页',onPage:page=>probe.calls.push({page}),onSize:size=>probe.calls.push({size})}),
 cursor:()=>h(L.Pager,{mode:'cursor',label:'计划目录',hasPrevious:false,hasNext:true,onPrevious:()=>probe.calls.push('previous'),onNext:()=>probe.calls.push('next')}),
 loading:()=>h(L.EmptyState,{kind:'loading'}),filtered:()=>h(L.EmptyState,{kind:'filtered',action:h(R.Button,{onClick:()=>probe.calls.push('clear')},'清除筛选')}),
 reason:()=>h('div',null,h(R.Button,{reason:'请先选择记录。'},'导出'),h(R.Button,{reason:'既有可见说明。',reasonDisplay:'tooltip'},'旧入口')),
 reasonNarrow:()=>h('div',{id:'reason-cell',style:{width:110,whiteSpace:'nowrap'}},h(R.Button,{reason:'批次已有计划或执行事实，不能删除；请先核实当前记录。'},'删除'))};
window.mount=name=>{if(host)host.unmount();probe.calls=[];probe.closed=0;host=ReactDOM.createRoot(document.getElementById('fixture'));
 host.render(h(React.Fragment,null,h(WorkbenchGuardHost),cases[name]()));};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '">' + manifest.styles.map(name => '<link rel="stylesheet" href="/static/' + name + '">').join('') +
  '<style>' + styles.map(item => item.code).join('\n') + '</style></head><body class="aps-workbench"><main class="shared-fixture" style="padding:24px"><button id="preserved-trigger">保留当前焦点</button><div id="fixture"></div></main>' +
  manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-')).map(name => '<script src="/static/' + name + '"></script>').join('') +
  '<script src="/compiled.js"></script><script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (name === '/compiled.js') { res.setHeader('Content-Type', 'application/javascript'); res.end(compiled.outputs.map(item => item.code).join('\n;\n')); return; }
  const asset = assets.get(name); if (asset) { res.setHeader('Content-Type', asset.mime); res.end(asset.bytes); return; }
  res.writeHead(404); res.end();
});
const report = { scope: 'current-source-component-fixtures', production_persistence_tested: false, win7_hardware_tested: false,
  sources: sources.concat(styles).map(item => ({ path: item.path, sha256: createHash('sha256').update(item.code).digest('hex') })), cases: [], errors: [], external: [] };
let page;
async function check(name, fn) { await fn(); report.cases.push({ name, passed: true }); }
async function mount(name) { await page.evaluate(name => window.mount(name), name); await page.locator('#fixture').locator(':scope > *').first().waitFor(); }
(async () => {
  let browser;
  try {
    if (!process.env.WORKBENCH_BROWSER) throw new Error('Set WORKBENCH_BROWSER to Chromium 109');
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    page = await browser.newPage({ viewport: { width: 1366, height: 768 } }); page.setDefaultTimeout(7000);
    const origin = 'http://127.0.0.1:' + server.address().port;
    page.on('pageerror', error => report.errors.push(error.message));
    await page.route('**/*', route => { if (route.request().url().startsWith(origin)) return route.continue(); report.external.push(route.request().url()); return route.abort(); });
    await page.goto(origin);
    await check('field-aria-error-dedup-and-focus', async () => {
      await mount('fields'); const input = page.getByLabel('数量', { exact: true });
      assert.equal(await input.getAttribute('id'), 'stable-amount'); assert.equal(await input.getAttribute('aria-invalid'), 'true');
      assert.equal(await input.getAttribute('aria-required'), 'true');
      assert.equal(await input.getAttribute('aria-describedby'), 'outside-hint stable-amount-hint stable-amount-error');
      assert.equal(await page.getByText('数量必填。', { exact: true }).count(), 1); assert.equal(await page.getByText('未知字段保留。', { exact: true }).count(), 1);
      await page.getByRole('button', { name: '定位无效字段', exact: true }).click(); assert(await input.evaluate(node => document.activeElement === node));
      assert(await page.locator('#field-section').evaluate(node => node.open));
      assert.equal(await page.evaluate(() => probe.focused), true);
    });
    await check('summary-does-not-repeat-field-message', async () => { await mount('duplicate'); assert.equal(await page.getByText('数量必填。', { exact: true }).count(), 1); });
    await check('pager-keeps-domain-sizes-and-page-jump', async () => {
      await mount('pager'); assert.deepEqual(await page.getByLabel('每页数量', { exact: true }).locator('option').evaluateAll(rows => rows.map(row => row.value)), ['10', '25', '50']);
      assert(await page.getByText('共 64 条 · 第 2 / 3 页', { exact: true }).isVisible());
      await page.getByLabel('每页数量', { exact: true }).selectOption('50'); await page.getByRole('button', { name: '系统下一页', exact: true }).click();
      await page.getByLabel('跳转页码', { exact: true }).fill('4'); await page.getByRole('button', { name: '跳转系统页', exact: true }).click();
      assert.equal(await page.getByLabel('跳转页码', { exact: true }).getAttribute('aria-invalid'), 'true');
      await page.getByLabel('跳转页码', { exact: true }).fill('1'); await page.getByLabel('跳转页码', { exact: true }).press('Enter');
      assert.deepEqual(await page.evaluate(() => probe.calls), [{ size: 50 }, { page: 3 }, { page: 1 }]);
      assert(await page.evaluate(() => WorkbenchControls.Pager === WorkbenchListControls.Pager));
    });
    await check('cursor-never-fabricates-totals', async () => {
      await mount('cursor'); assert(await page.getByRole('button', { name: '计划目录上一页', exact: true }).isDisabled());
      assert(!/共\s*\d|\d\s*\/\s*\d/.test(await page.locator('.wb-pager').innerText()));
      await page.getByRole('button', { name: '计划目录下一页', exact: true }).click(); assert.deepEqual(await page.evaluate(() => probe.calls), ['next']);
    });
    await check('loading-and-filtered-recovery', async () => {
      await mount('loading'); assert.equal(await page.getByRole('status').getAttribute('aria-busy'), 'true');
      await mount('filtered'); await page.getByRole('button', { name: '清除筛选', exact: true }).click(); assert.deepEqual(await page.evaluate(() => probe.calls), ['clear']);
    });
    await check('inline-disabled-reason-linked', async () => {
      await mount('reason'); const button = page.getByRole('button', { name: '导出', exact: true }); assert(await button.isDisabled());
      const id = await button.getAttribute('aria-describedby'); assert(id); assert.equal(await page.locator('[id="' + id + '"]').innerText(), '请先选择记录。');
      assert.equal(await button.getAttribute('data-wb-disabled-reason'), '请先选择记录。');
      // tooltip mode: reason stays out of the visible row (title + visually hidden description), name still carries it.
      const tooltip = page.getByRole('button', { name: '旧入口：既有可见说明。', exact: true });
      assert(await tooltip.isDisabled()); assert.equal(await tooltip.getAttribute('title'), '既有可见说明。');
      const hidden = await tooltip.getAttribute('aria-describedby'); assert(hidden);
      const description = page.locator('[id="' + hidden + '"]');
      assert.equal(await description.evaluate(node => node.textContent), '既有可见说明。');
      assert(await description.evaluate(node => node.getBoundingClientRect().width <= 1), 'tooltip reason must stay visually hidden');
      assert.equal(await page.locator('.wb-reason').count(), 1, 'only the inline button renders a visible reason');
    });
    await check('long-reason-wraps-inside-narrow-action-cell', async () => {
      await mount('reasonNarrow'); const geometry = await page.locator('#reason-cell').evaluate(node => {
        const range = document.createRange(); range.selectNodeContents(node.querySelector('.wb-reason'));
        const parent = node.getBoundingClientRect(); return { left: parent.left, right: parent.right,
          text: Array.from(range.getClientRects()).map(rect => ({ left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom })) };
      });
      assert(geometry.text.length > 1, 'The complete reason must wrap instead of being clipped');
      assert(geometry.text.every(rect => rect.left >= geometry.left - 1 && rect.right <= geometry.right + 1), JSON.stringify(geometry));
      await page.screenshot({ path: path.join(output, 'reason-narrow.png') });
    });
    await check('automatic-preview-does-not-move-focus-or-scroll', async () => {
      await page.setViewportSize({ width: 1100, height: 720 }); await page.locator('#preserved-trigger').click(); await mount('autoDetail');
      assert.equal(await page.evaluate(() => window.scrollY), 0); assert(await page.locator('#preserved-trigger').evaluate(node => document.activeElement === node));
      await page.setViewportSize({ width: 1366, height: 768 });
    });
    await check('detail-focus-layout-and-return', async () => {
      await mount('detail'); await page.locator('#detail-trigger').click(); const title = page.getByRole('heading', { name: '条目详情', exact: true });
      assert(await title.evaluate(node => document.activeElement === node)); assert.equal(await page.locator('.wb-detail').getAttribute('role'), 'region');
      const panel = await page.locator('.wb-detail').boundingBox(), list = await page.locator('.wb-detail-layout > section').boundingBox(); assert(panel.x > list.x + list.width);
      await page.locator('#detail-next').click(); assert(await title.evaluate(node => document.activeElement === node));
      await page.keyboard.press('Escape'); await page.locator('.wb-detail').waitFor({ state: 'detached' }); assert(await page.locator('#detail-next').evaluate(node => document.activeElement === node));
      await page.setViewportSize({ width: 1100, height: 720 }); await page.locator('#detail-trigger').click();
      const narrowPanel = await page.locator('.wb-detail').boundingBox(), narrowList = await page.locator('.wb-detail-layout > section').boundingBox();
      assert(narrowPanel.y >= narrowList.y + narrowList.height); assert(Math.abs(narrowPanel.width - narrowList.width) < 1);
      await page.screenshot({ path: path.join(output, 'detail-narrow.png') });
    });
    await check('modal-owner-confirmation-cancel-and-continue-once', async () => {
      await page.setViewportSize({ width: 1366, height: 768 }); await mount('guard'); await page.locator('#guard-trigger').click(); await page.keyboard.press('Escape');
      await page.getByRole('dialog', { name: '离开前确认', exact: true }).getByRole('button', { name: '留在当前页面', exact: true }).click();
      assert(await page.getByRole('dialog', { name: '草稿编辑', exact: true }).isVisible()); assert.equal(await page.evaluate(() => probe.calls.length), 0);
      await page.keyboard.press('Escape'); await page.getByRole('button', { name: '放弃未保存内容并继续', exact: true }).click();
      await page.getByRole('dialog', { name: '草稿编辑', exact: true }).waitFor({ state: 'detached' });
      assert.deepEqual(await page.evaluate(() => probe.calls), [{ guardConfirmed: true, guardOwner: 'shared-probe' }]);
      assert(await page.locator('#guard-trigger').evaluate(node => document.activeElement === node));
    });
    await check('readonly-dialog-does-not-prompt-for-unrelated-editor', async () => {
      await mount('readonly'); await page.keyboard.press('Escape'); await page.getByRole('dialog', { name: '只读详情', exact: true }).waitFor({ state: 'detached' });
      assert.equal(await page.getByRole('dialog').count(), 0); assert.equal(await page.evaluate(() => probe.closed), 1);
    });
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } catch (error) { report.failure = error.stack; process.exitCode = 1; if (page) await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {}); }
  finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'shared-controls-result.json'), JSON.stringify(report, null, 2)); }
  process.stdout.write(JSON.stringify({ browser: report.browser, cases: report.cases.length, failure: report.failure || null, output }) + '\n');
})();
