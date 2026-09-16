/* BT source-only harness. No main/build/shared/static writes or production database. */
'use strict';
const UI = require('./run_ui_source.cjs');
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const files = UI.dependencies(['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'ResourceControls.jsx', 'CalendarContract.js', 'PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx', 'PlanGanttModel.js', 'RunHistoryAPI.js', 'RunHistoryControls.jsx', 'RunHistoryWorkspace.jsx',
  'RunCandidateAPI.js', 'RunCandidateModel.js', 'RunCandidateControls.jsx', 'RunCandidateAnalysisAPI.js', 'RunCandidateAnalysis.jsx', 'RunBaselineAPI.js', 'RunBaselineModel.js', 'RunBaselineControls.jsx', 'RunCandidateGantt.jsx', 'RunCandidateWorkspace.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx']);
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
for (const source of sources) { const target = path.join(output, 'sources', source.path); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, source.code); }
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, i) => ['/source/' + files[i], row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const report = { browser: null, variants: [], checks: [], screenshots: [], errors: [], external: [], dialogs: [], requests: [], downloads: [], layouts: [],
  console: [], responses: [], failedRequests: [], directEntrypoints: [],
  compile: { global_build: false, target: 'chrome109' }, sources: sources.map(row => ({ path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex') })) };
const boot = `let fixtureRoot;function render(component,initialContext={},adapter){if(fixtureRoot)fixtureRoot.unmount();fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
fixtureRoot.render(React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),
React.createElement(component,{initialContext,adapter,onNavigate:(...args)=>{window.navigation=args;}})));}
window.mountHistory=(context={},adapter)=>render(RunHistoryWorkspace,context,adapter);window.mountCandidate=(context)=>render(RunCandidateWorkspace,context);
window.rerenderHistory=(initialContext,adapter)=>fixtureRoot.render(React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),React.createElement(RunHistoryWorkspace,{initialContext,adapter,onNavigate:(...args)=>{window.navigation=args;}})));
window.mountHistory();`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  UI.styles(report, output) + '<style>body{margin:0}#fixture-root{margin:92px 28px 20px 264px;min-width:0}@media(max-width:760px){#fixture-root{margin:12px}}</style></head><body class="aps-workbench"><div id="fixture-root"></div>' +
  staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://fixture').pathname;
  if (pathname.startsWith('/api/') || pathname.startsWith('/fixture/')) {
    const upstream = http.request(backend + req.url, { method: req.method, headers: req.headers }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
    upstream.on('error', error => { res.writeHead(502); res.end(error.message); }); req.pipe(upstream); return;
  }
  if (pathname === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
  const asset = assets.get(pathname); if (!asset) { res.writeHead(404); res.end(); return; } res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
let page, origin, variant, fixtures, phase;
const button = name => name === '清除筛选' ? page.locator('.rh-filters').getByRole('button', { name, exact: true }) : UI.button(page, name);
const done = name => report.checks.push({ variant, name, passed: true });
const rows = () => page.locator('[data-run-ref]');
async function shot(name) {
  const target = path.join(output, variant + '-' + name);
  await page.screenshot({ path: target + '.png', fullPage: true, animations: 'disabled' }); report.screenshots.push(target + '.png');
  fs.writeFileSync(target + '.html', await page.content());
  fs.writeFileSync(target + '-accessible.yaml', await page.locator('body').ariaSnapshot());
}
async function loaded() { await page.waitForFunction(() => { const root = document.querySelector('[data-run-history-workspace]'); return root && root.getAttribute('aria-busy') !== 'true'; }); }
async function mount(context = {}) { await page.evaluate(context => mountHistory(context), context); await loaded(); }
async function control(action) { const response = await page.request.post(origin + '/fixture/control', { data: { action } }); assert(response.ok()); }
async function select(label, name) { await page.getByLabel(label, { exact: true }).click(); await page.getByRole('listbox').getByRole('option', { name: label === '排产记录每页数量' ? name + ' 次' : name, exact: true }).click(); }
async function query() { await button('查询排产记录').click(); await loaded(); }
async function layout() {
  const evidence = await page.evaluate(() => {
    const shell = document.querySelector('[data-run-history-workspace]'), table = shell.querySelector('.rh-table');
    return { width: innerWidth, height: innerHeight, theme: document.documentElement.dataset.theme, pageOverflow: document.documentElement.scrollWidth > innerWidth,
      tableOverflow: table.scrollWidth > table.clientWidth + 1, footerBottom: shell.querySelector('.rh-pagination').getBoundingClientRect().bottom,
      clipped: [...shell.querySelectorAll('button,th')].filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.textContent),
      iconsMissing: [...shell.querySelectorAll('button')].filter(n => !n.querySelector('svg')).map(n => n.getAttribute('aria-label')),
      shadows: [...shell.querySelectorAll('*')].filter(n => getComputedStyle(n).boxShadow !== 'none' && !n.matches('.wb-col-key,.wb-col-actions')).map(n => n.className),
      tableWidth: table.getBoundingClientRect().width, parentWidth: shell.getBoundingClientRect().width,
      actionBoxes: [...shell.querySelectorAll('tbody button')].map(n => { const b = n.getBoundingClientRect(); return { width: b.width, height: b.height, text: n.textContent }; }),
      contentBottom: shell.getBoundingClientRect().bottom,
      numericColors: [...shell.querySelectorAll('tbody tr:first-child td.rh-num')].map(n => getComputedStyle(n).color) };
  });
  report.layouts.push({ variant, ...evidence }); assert(!evidence.pageOverflow && !evidence.tableOverflow, JSON.stringify(evidence));
  assert.deepEqual(evidence.clipped, []); assert.deepEqual(evidence.iconsMissing, []); assert.deepEqual(evidence.shadows, []);
  assert(evidence.footerBottom <= evidence.height && evidence.contentBottom <= evidence.height); assert(Math.abs(evidence.tableWidth - evidence.parentWidth) < 2);
  assert(evidence.actionBoxes.every(b => b.width === 32 && b.height === 32 && b.text === '')); done('layout-no-overflow-shadow-clipping');
}
async function contracts() {
  const results = await page.evaluate(async () => {
    const A = RunHistoryAPI, api = A.create(), original = await api.catalog(), passed = [], failures = [];
    const reject = (name, value, change, validate = v => A.catalog(v)) => { const copy = JSON.parse(JSON.stringify(value)); change(copy); try { validate(copy); failures.push(name); } catch (_) { passed.push(name); } };
    reject('unknown-plan-ref', original, v => { v.data.runs[0].plan_ref = 'a'.repeat(48); });
    reject('unknown-private-payload', original, v => { v.data.runs[0].facts_json = '{}'; });
    reject('wrong-source', original, v => { v.meta.source = 'sample'; });
    reject('truncated-page', original, v => { v.data.runs.pop(); });
    reject('duplicate-run', original, v => { v.data.runs[1] = v.data.runs[0]; });
    reject('wrong-page-total', original, v => { v.data.page.total--; });
    reject('wrong-page-number', original, v => { v.data.page.number++; });
    reject('wrong-has-more', original, v => { v.data.page.has_more = false; });
    reject('date-filter-not-echoed', original, v => { v.data.time_scope.accepted_from = '2026-09-10'; });
    reject('utc-time-basis', original, v => { v.meta.time_basis = 'UTC'; });
    reject('invalid-date', original, v => { v.data.runs[0].accepted_at = '2026-02-30T10:00:00'; });
    reject('constraint-completion-not-inferred', original, v => { v.data.runs[0].constraint_verification = 'passed'; });
    reject('nonfinal-count-not-final', original, v => { v.data.runs.find(r => r.state === 'running').counts_final = true; });
    reject('recovery-reason-required', original, v => { v.data.runs.find(r => r.recovery_required).recovery_reason = null; });
    reject('missing-scope-not-zero', original, v => { v.data.runs[0].scope_summary.batch_count = 0; });
    reject('gap-reason-required', original, v => { v.data.runs[0].scope_summary.data_gaps = []; });
    reject('out-of-order', original, v => { [v.data.runs[0], v.data.runs[1]] = [v.data.runs[1], v.data.runs[0]]; });
    reject('snapshot-substitution', original, v => { v.meta.snapshot_ref = 'z'.repeat(32); }, v => A.catalog(v, { snapshot_ref: original.meta.snapshot_ref }));
    for (const q of [{ accepted_from: '2026-09-10' }, { accepted_from: '2026-09-11', accepted_to: '2026-09-10' }, { accepted_from: '2026-02-30', accepted_to: '2026-03-01' },
      { size: 51 }, { state: 'completed' }, { page: '1' }, { plan_ref: 'a'.repeat(48) }, { sort: 'latest' }, { snapshot_ref: 'latest' }]) {
      let sends = 0; try { await A.create(() => { sends++; throw new Error('sent'); }).catalog(q); failures.push(JSON.stringify(q)); }
      catch (_) { if (sends) failures.push('invalid-query-sent'); else passed.push('reject-query-' + JSON.stringify(q)); }
    }
    for (const q of [{ source: 'sample' }, { run_ref: 'a'.repeat(48) }, { plan_ref: 'a'.repeat(48) }]) {
      try { A.context(q); failures.push('invalid-context'); } catch (_) { passed.push('reject-context-' + Object.keys(q)); }
    }
    for (const sort of ['accepted_at', 'started_at', 'finished_at']) for (const order of ['asc', 'desc']) {
      const q = { sort, order, size: 50 }; A.catalog(await api.catalog(q), q); passed.push('real-sort-' + sort + '-' + order);
    }
    return { passed, failures };
  });
  assert.deepEqual(results.failures, []); results.passed.forEach(done);
}
async function directCandidate() {
  const response = await page.request.get(origin + '/api/workbench/v1/scheduling/candidates/' + fixtures.real.candidate_ref + '/workspace');
  assert.equal(response.status(), 200); const workspace = await response.json(), data = workspace.data;
  fs.writeFileSync(path.join(output, variant + '-candidate-workspace.json'), JSON.stringify(workspace, null, 2));
  assert.equal(data.candidate.candidate_ref, fixtures.real.candidate_ref); assert.equal(data.candidate.run_ref, fixtures.real.run_ref);
  assert.equal(data.capabilities.adopt, false); assert.equal(data.capabilities.edit_draft, false);
  assert.deepEqual(await page.locator('[data-candidate-task-list] [data-row-ref]').evaluateAll(nodes => nodes.map(n => n.dataset.rowRef)), data.tasks.map(t => t.row_ref));
  const before = report.requests.length, navigation = await page.evaluate(() => window.navigation), blocked = [];
  for (const [name, reason] of [['采用方案', '此功能尚未开通。'], ['试调', '此功能尚未开通。']]) {
    const target = button(name); assert(await target.isDisabled()); assert.equal(await target.getAttribute('title'), reason);
    assert.equal(await target.getAttribute('data-wb-disabled-reason'), reason); await page.getByText(reason, { exact: true }).first().waitFor();
    const box = await target.boundingBox(); assert(box); await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    blocked.push({ name, reason, disabled: true });
  }
  await shot('direct-candidate-no-renderers');
  assert.deepEqual(await page.evaluate(() => window.navigation), navigation);
  assert.equal(await page.getByRole('dialog').count(), 0); assert.equal(await page.locator('[data-run-adoption-action]').count(), 0);
  assert.deepEqual(report.requests.slice(before), []);
  report.directEntrypoints.push({ variant, host: 'direct-component-without-renderers', blocked, requests_after_clicks: 0 });
  done('direct-component-without-renderers-pointer-clicks-cannot-write');
  const baseline = page.getByRole('checkbox', { name: '初始计划', exact: true }); assert.equal(await baseline.isChecked(), false);
  assert.equal(report.requests.filter(r => r.variant === variant && new URL(r.url).pathname.endsWith('/baseline')).length, 0);
  const pending = page.waitForResponse(r => new URL(r.url()).pathname === '/api/workbench/v1/scheduling/candidates/' + fixtures.real.candidate_ref + '/baseline');
  await baseline.check(); const read = await pending; assert.equal(read.status(), 200); const value = await read.json();
  await page.evaluate(({ value, data }) => RunBaselineAPI.validate(value, data), { value, data });
  fs.writeFileSync(path.join(output, variant + '-candidate-baseline.json'), JSON.stringify(value, null, 2));
  await page.locator('.rb-panel').waitFor(); await shot('direct-candidate-baseline'); await baseline.uncheck();
  await page.locator('.rb-panel').waitFor({ state: 'hidden' });
  await button('工序详情 ' + data.tasks[0].row_ref).click();
  await UI.reference(page.getByRole('complementary'), data.tasks[0].operation_ref); await button('关闭工序详情').click();
  done('baseline-dependencies-real-route-and-candidate-identity');
}
async function browse() {
  assert.equal(await rows().count(), 20); assert.equal(await page.getByRole('button', { name: /导出|CSV|XLSX/ }).count(), 0);
  await layout(); await shot('history'); done('no-export-no-invented-download');
  const first = await rows().evaluateAll(nodes => nodes.map(n => n.dataset.runRef));
  await button('排产记录下一页').click(); await loaded(); const second = await rows().evaluateAll(nodes => nodes.map(n => n.dataset.runRef));
  assert.equal(first.length + second.length, 27); assert.equal(new Set([...first, ...second]).size, 27);
  await button('排产记录上一页').click(); await loaded(); assert.deepEqual(await rows().evaluateAll(nodes => nodes.map(n => n.dataset.runRef)), first); done('snapshot-bound-pagination');
  await select('排产记录每页数量', '10'); await loaded(); assert.equal(await rows().count(), 10); done('shared-page-size-select');
  await page.getByLabel('排产记录状态', { exact: true }).click(); await page.getByRole('listbox').waitFor(); await shot('state-menu');
  await page.getByRole('listbox').getByRole('option', { name: '计算失败', exact: true }).click(); await query();
  assert.equal(await rows().count(), 4); assert((await rows().allTextContents()).every(t => t.includes('计算失败') && t.includes('未保存可用候选'))); await shot('failed'); done('failed-not-empty-or-complete');
  await select('排产记录状态', '正在计算'); await query();
  await page.locator('[data-run-ref="' + fixtures.awaiting.run_ref + '"]').getByText('等待核对', { exact: true }).waitFor();
  assert((await rows().allTextContents()).every(t => t.includes('非最终'))); await shot('running-recovery'); done('running-reconciliation-nonfinal-counts');
  await select('排产记录状态', '已中断'); await query(); assert((await rows().allTextContents()).every(t => t.includes('未自动重跑'))); done('interrupted-not-complete');
  await select('排产记录状态', '部分完成'); await query(); assert((await rows().allTextContents()).every(t => t.includes('保留部分结果'))); done('partial-preserved');
  await button('清除筛选').click(); await loaded();
  await page.getByLabel('排产记录提交起日', { exact: true }).focus(); await page.keyboard.press('Alt+ArrowDown'); await page.getByRole('dialog').waitFor(); await shot('date-picker'); await page.keyboard.press('Escape');
  await page.getByLabel('排产记录提交起日', { exact: true }).fill('2026-09-10'); await button('查询排产记录').click(); await page.getByRole('alert').waitFor(); done('unpaired-dates-rejected');
  await page.getByLabel('排产记录提交止日', { exact: true }).fill('2026-09-09'); await button('查询排产记录').click(); await page.getByRole('alert').waitFor(); done('reversed-dates-rejected');
  await page.getByLabel('排产记录提交止日', { exact: true }).focus(); await page.keyboard.press('Alt+ArrowDown');
  await page.getByRole('dialog').getByRole('gridcell', { name: '2026-09-10', exact: true }).click();
  assert.equal(await page.getByLabel('排产记录提交止日', { exact: true }).inputValue(), '2026-09-10'); await query(); assert.equal(await rows().count(), 2); done('factory-local-inclusive-date-input-and-calendar-click');
  await page.getByLabel('排产记录提交起日', { exact: true }).fill('2030-01-01'); await page.getByLabel('排产记录提交止日', { exact: true }).fill('2030-01-02'); await query();
  await page.getByText('当前筛选没有匹配的排产记录', { exact: true }).waitFor(); assert.equal(await rows().count(), 0); await shot('empty-filter'); done('empty-filter-never-falls-back');
  await button('清除筛选').click(); await loaded();
  await select('排产记录排序项', '开始时间'); await select('排产记录排序方向', '从旧到新'); await query(); assert.equal(await page.getByLabel('排产记录排序项').inputValue(), 'started_at'); done('sort-input-click-apply');
  await mount({ size: 50 }); await rows().first().waitFor(); const missing = page.locator('[data-run-ref="' + fixtures.missing.run_ref + '"]');
  await missing.getByText('排产时资料缺项 6', { exact: true }).click(); await missing.getByText(/所选批次：排产时未记录此项/).waitFor(); done('missing-admission-values-and-reasons');
  await mount({ state: 'complete', size: 10, order: 'asc', return_plan_context: { plan_ref: 'f'.repeat(48), snapshot_ref: 'not-carried' } });
  await button('查看运行 ' + fixtures.real.run_ref).click(); const nav = await page.evaluate(() => navigation);
  assert.equal(nav[0], 'analysis'); assert.equal(nav[1].run_ref, fixtures.real.run_ref); assert(!nav[1].candidate_ref && !nav[1].plan_ref);
  assert.deepEqual(nav[1].return_plan_context, { plan_ref: 'f'.repeat(48) }); assert(!JSON.stringify(nav).includes('snapshot_ref')); done('permanent-run-navigation-keeps-return-filters');
  await page.evaluate(context => mountCandidate(context), nav[1]); await page.locator('[data-candidate-ref]').first().waitFor();
  assert.equal(await page.getByRole('heading', { name: '候选工作区', exact: true }).count(), 0); done('BP-catalog-no-default-candidate');
  await button('查看候选 ' + fixtures.real.candidate_ref).click(); await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor(); await shot('BP-explicit-candidate'); done('real-engine-history-BP-manual-candidate');
  await directCandidate();
  await mount(nav[1].return_history_context); assert.equal(await page.getByLabel('排产记录状态').inputValue(), 'complete'); assert.equal(await page.getByLabel('排产记录排序方向').inputValue(), 'asc');
  await button('返回正式计划').click(); assert.deepEqual(await page.evaluate(() => navigation), ['analysis', { plan_ref: 'f'.repeat(48) }]); done('return-query-context-restored');
}
async function failures() {
  await control('empty'); await mount(); await page.getByText('尚无排产记录', { exact: true }).waitFor();
  assert.equal(await rows().count(), 0); assert(await button('排产记录下一页').isDisabled()); await shot('empty-directory'); done('real-empty-directory-distinct-from-empty-filter');
  await control('reset'); await mount({ page: 100 }); await page.getByText('当前页没有排产记录', { exact: true }).waitFor();
  await button('返回第 1 页').click(); await loaded(); assert.equal(await rows().count(), 20); done('out-of-range-page-explicit-return');
  await mount(); const apiPattern = '**/api/workbench/v1/scheduling/runs?*';
  await page.route(apiPattern, route => route.fulfill({ status: 500, contentType: 'text/html', body: 'Unavailable' }));
  await button('刷新排产记录').click(); await page.getByRole('alert').waitFor(); assert.equal(await rows().count(), 0); await shot('read-error');
  await page.unroute(apiPattern); await button('重新查询').click(); await loaded(); assert.equal(await rows().count(), 20); done('failed-refresh-clears-old-results-and-retries');
  await control('append'); await button('排产记录下一页').click(); await page.getByRole('alert').waitFor(); assert.equal(await rows().count(), 0);
  await button('重新查询').waitFor(); await shot('snapshot-changed'); await button('重新查询').click(); await loaded();
  assert((await page.locator('.rh-pagination').innerText()).includes('28 次')); done('real-SQLite-change-stops-page-until-explicit-refresh');
  await control('restart'); await button('排产记录下一页').click(); await page.getByRole('alert').waitFor(); await button('重新查询').click(); await loaded(); done('expired-read-token-never-reused');
  await page.evaluate(async () => { const api = RunHistoryAPI.create(), value = await api.catalog(); window.boundSnapshot = value.meta.snapshot_ref; rerenderHistory({ snapshot_ref: boundSnapshot }); });
  await loaded(); await control('restart');
  await page.evaluate(() => rerenderHistory({ snapshot_ref: 'z'.repeat(32) })); await page.getByRole('alert').waitFor(); assert.equal(await rows().count(), 0); done('source-snapshot-prop-change-reloads');
  await mount({ source: 'sample' }); await page.getByRole('alert').waitFor(); assert.equal(await rows().count(), 0); done('unknown-source-no-silent-production-fallback');
  await page.evaluate(() => { const api = RunHistoryAPI.create(); window.deferHistory = null;
    window.mountHistory({}, { catalog: (...args) => api.catalog(...args).then(value => new Promise(resolve => { window.deferHistory = () => resolve(value); })) }); });
  await page.getByText('正在读取排产记录', { exact: true }).waitFor(); assert.equal(await rows().count(), 0); await shot('loading');
  await page.waitForFunction(() => typeof deferHistory === 'function'); await mount({ state: 'failed' }); await page.evaluate(() => deferHistory());
  assert((await rows().allTextContents()).every(t => t.includes('计算失败'))); done('late-request-after-source-change-ignored');
  await page.evaluate(() => { const api = RunHistoryAPI.create(); mountHistory({}, { catalog: async (...args) => { const v = await api.catalog(...args); v.data.runs[0].counts_final = true; return v; } }); });
  await page.getByRole('alert').waitFor(); assert.equal(await rows().count(), 0); done('injected-adapter-also-strictly-validated');
  const storage = await page.evaluate(() => ({ keys: Object.keys(localStorage), url: location.href }));
  assert(storage.keys.every(k => k === 'aps_theme' || k === 'aps_kit_theme')); assert.equal(storage.url, origin + '/'); done('no-read-token-storage-or-location');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.')); origin = 'http://127.0.0.1:' + server.address().port;
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      variant = width + 'x' + height + '-' + theme; phase = 'browse'; const row = { variant, width, height, theme, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height }, recordHar: { path: path.join(output, variant + '-network.har'), content: 'embed' } });
      await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(15000);
      page.on('pageerror', error => report.errors.push(error.message)); page.on('dialog', dialog => { report.dialogs.push(dialog.type()); dialog.dismiss(); });
      page.on('console', message => report.console.push({ variant, phase, type: message.type(), text: message.text(), location: message.location() }));
      page.on('response', response => report.responses.push({ variant, phase, status: response.status(), url: response.url() }));
      page.on('requestfailed', request => report.failedRequests.push({ variant, url: request.url(), error: request.failure() }));
      page.on('download', download => report.downloads.push(download.suggestedFilename()));
      page.on('request', request => { if (request.url().includes('/api/')) report.requests.push({ variant, method: request.method(), url: request.url() }); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      try {
        await page.goto(origin); await loaded(); await control('reset'); await mount(); fixtures = await (await page.request.get(origin + '/fixture/cases')).json();
        await contracts(); await browse(); phase = 'expected-failures'; await failures(); row.passed = true;
      } catch (error) { row.error = error.stack; await shot('FAILED'); throw error; }
      finally { await context.tracing.stop({ path: path.join(output, variant + '-trace.zip') }); await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []); assert.deepEqual(report.downloads, []);
    const httpErrors = report.responses.filter(row => row.status >= 400);
    assert(httpErrors.every(row => row.phase === 'expected-failures' && [409, 500].includes(row.status) && new URL(row.url).pathname === '/api/workbench/v1/scheduling/runs'));
    assert(report.console.filter(row => row.type === 'error').every(row => row.phase === 'expected-failures' &&
      /^Failed to load resource: the server responded with a status of (409|500) \(/.test(row.text) && httpErrors.some(r => r.variant === row.variant && r.url === row.location.url)));
    assert(report.requests.every(r => r.method === 'GET'));
    console.log(JSON.stringify({ browser: report.browser, checks: report.checks.length, variants: report.variants.length, downloads: 'N/A: no history export', output }));
  } finally { if (browser) await browser.close(); server.close(); fs.writeFileSync(path.join(output, 'history-widgets.json'), JSON.stringify(report, null, 2)); }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
