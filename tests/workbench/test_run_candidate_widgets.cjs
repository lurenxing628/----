/* BP source-only bundle. No build, static writes, production DB or parent preview. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const files = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx',
  'resource-contract.js', 'ResourceControls.jsx', 'CalendarContract.js', 'PlanGanttModel.js', 'RunCandidateAPI.js', 'RunCandidateAnalysisAPI.js', 'RunCandidateModel.js', 'RunCandidateControls.jsx', 'RunCandidateAnalysis.jsx',
  'RunBaselineAPI.js', 'RunBaselineModel.js', 'RunBaselineControls.jsx',
  'RunCandidateGantt.jsx', 'RunCandidateWorkspace.jsx', 'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx',
  'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx'];
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
for (const source of sources) { const target = path.join(output, 'sources', source.path); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, source.code); }
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, i) => ['/source/' + files[i], row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const report = { browser: null, variants: [], cases: [], screenshots: [], errors: [], external: [], dialogs: [], requests: [], downloads: [], capacity: [],
  compile: { global_build: false, target: 'chrome109' }, sources: sources.map(row => ({ path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex') })) };
const boot = `let fixtureRoot;window.mountCandidate=(initialContext={},adapter)=>{if(fixtureRoot)fixtureRoot.unmount();fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
fixtureRoot.render(React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),
React.createElement(RunCandidateWorkspace,{initialContext,adapter,onNavigate:(...args)=>{window.navigation=args;}})));};window.mountCandidate();`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>body{margin:0}#fixture-root{margin:20px 28px 20px 264px;min-width:0}@media(max-width:760px){#fixture-root{margin:12px}}</style></head><body class="aps-workbench"><div id="fixture-root"></div>' +
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
let page, origin, variant, fixtures;
const button = name => page.getByRole('button', { name, exact: true });
const done = name => report.cases.push({ variant, name, passed: true });
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: true, animations: 'disabled' }); report.screenshots.push(file); }
async function mount(which, extra = {}) {
  const value = which ? { ...fixtures[which], ...extra } : extra; delete value.refs;
  await page.evaluate(value => { window.fixtureSource = value; window.mountCandidate(value); }, value);
  if (value.candidate_ref && /^[a-f0-9]{48}$/.test(value.candidate_ref)) await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor();
  return value;
}
async function workspace(ref, scope = {}) {
  const result = await page.evaluate(async ({ ref, scope }) => RunCandidateAPI.create().workspace(ref, scope), { ref, scope });
  return result;
}
async function fillTime(label, value) {
  const normalized = value.length === 19 && value.endsWith(':00') ? value.slice(0, 16) : value;
  await page.getByLabel(label, { exact: true }).fill(normalized);
}
async function layout() {
  assert.equal(await page.getByRole('checkbox', { name: '初始计划', exact: true }).isChecked(), false);
  assert.equal(await page.locator('[data-baseline-lane], [data-baseline-list]').count(), 0);
  const value = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth,
    clipped: [...document.querySelectorAll('[data-run-candidate-workspace] button')].filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.textContent),
    width: document.querySelector('[data-run-candidate-workspace]').getBoundingClientRect().width,
    available: innerWidth - (innerWidth > 760 ? 292 : 24),
    icons: [...document.querySelectorAll('[data-run-candidate-workspace] button')].filter(n => n.getAttribute('aria-label') && !n.querySelector('svg')).map(n => n.getAttribute('aria-label')) }));
  assert.equal(value.overflow, false, JSON.stringify(value)); assert.deepEqual(value.clipped, []); assert.deepEqual(value.icons, []);
  assert(Math.abs(value.width - value.available) < 2, JSON.stringify(value));
}
async function download(fmt, expected) {
  const started = page.waitForEvent('download'); await button(fmt.toUpperCase()).click(); const file = await started;
  const target = path.join(output, variant + '-' + report.downloads.length + '.' + fmt); await file.saveAs(target); assert.equal(await file.failure(), null);
  report.downloads.push({ path: target, format: fmt, task_count: expected.data.task_count,
    row_count: Math.max(1, expected.data.task_count + (expected.data.unplanned_operation_count || 0)),
    row_refs: expected.data.tasks.map(t => t.row_ref), operation_refs: expected.data.tasks.map(t => t.operation_ref), starts: expected.data.tasks.map(t => t.start),
    candidate_ref: expected.data.candidate.candidate_ref, run_ref: expected.data.candidate.run_ref });
  await page.getByText(/^已下载 \d+ 条记录/).waitFor(); done('real-' + fmt + '-download-full-scope-' + expected.data.task_count);
}
async function contracts() {
  const result = await page.evaluate(async () => {
    const A = RunCandidateAPI, api = A.create(), source = fixtureSource, full = await api.workspace(source.candidate_ref), directory = await api.catalog(source.run_ref), failures = [], passed = [];
    function reject(name, value, edit, read) { const copy = JSON.parse(JSON.stringify(value)); edit(copy); try { read(copy); failures.push(name); } catch (_) { passed.push(name); } }
    const read = v => A.workspace(v, source.candidate_ref, {}, source.run_ref);
    reject('fake-plan-identity', full, v => { v.data.candidate.plan_ref = 'f'.repeat(48); }, read);
    reject('fake-task-identity', full, v => { v.data.tasks[0].task_ref = v.data.tasks[0].row_ref; }, read);
    reject('formal-version-allocated', full, v => { v.data.generation.formal_version_allocated = true; }, read);
    reject('cross-candidate', full, v => { v.data.candidate.candidate_ref = 'a'.repeat(48); }, read);
    reject('cross-run', full, v => { v.data.candidate.run_ref = 'a'.repeat(48); }, read);
    reject('current-metadata', full, v => { v.data.generation.current_entities_consulted = true; }, read);
    reject('truncated-task-count', full, v => { v.data.tasks.pop(); }, read);
    reject('incomplete-task-list', full, v => { v.data.tasks_complete = false; }, read);
    reject('duplicate-row-ref', full, v => { v.data.tasks[1].row_ref = v.data.tasks[0].row_ref; }, read);
    reject('duplicate-operation-ref', full, v => { v.data.tasks[1].operation_ref = v.data.tasks[0].operation_ref; }, read);
    reject('reversed-interval', full, v => { v.data.tasks[0].end = v.data.tasks[0].start; }, read);
    reject('invalid-calendar-date', full, v => { v.data.tasks[0].start = '2026-02-30T00:00:00'; }, read);
    reject('missing-metric-reason', full, v => { v.data.candidate.metrics.makespan_hours = { value: null, reason: null }; }, read);
    reject('fabricated-zero-unplanned', full, v => { v.data.unplanned_operations = null; v.data.unplanned_operation_count = 0; }, read);
    reject('private-payload', full, v => { v.data.tasks[0].facts_json = '{}'; }, read);
    reject('untrusted-source', full, v => { v.meta.source = 'sample'; }, read);
    reject('foreign-scope', full, v => { v.data.time_scope.range_start = '2026-09-01T00:00:00'; }, read);
    reject('unscoped-truncation', full, v => { v.data.task_count--; v.data.tasks.pop(); v.data.task_span.end = v.data.tasks[v.data.tasks.length - 1].end; }, read);
    reject('unexpected-mutation-capability', full, v => { v.data.capabilities.adopt = true; }, read);
    reject('catalog-identity', directory, v => { v.data.candidates[0].run_ref = 'e'.repeat(48); }, v => A.catalog(v, source.run_ref));
    reject('catalog-count', directory, v => { v.data.page.total++; }, v => A.catalog(v, source.run_ref));
    reject('catalog-hidden-status', directory, v => { v.data.candidates[0].status = 'skipped'; }, v => A.catalog(v, source.run_ref));
    const keys = new Set(Object.keys(full.data.tasks[0])); if (!keys.has('task_ref') && keys.has('row_ref')) passed.push('permanent-row-identity-only'); else failures.push('permanent-row-identity-only');
    const sample = full.data.tasks, copy = { ...full.data, tasks: sample.map(t => ({ ...t, start: sample[0].start, end: sample[0].end })) };
    const before = JSON.stringify(copy), model = RunCandidateModel.layout(copy, 'machine', '');
    if (model.rows.length === 3 && JSON.stringify(copy) === before && sample.every(t => model.locations.has(t.row_ref))) passed.push('overlap-tracks-no-source-mutation'); else failures.push('overlap-tracks-no-source-mutation');
    const sends = [], fake = A.create(async (...args) => { sends.push(args); throw new Error('unexpected'); });
    try { await fake.workspace('latest'); failures.push('latest-request'); } catch (_) { if (!sends.length) passed.push('empty-invalid-ref-no-request'); }
    return { passed, failures };
  });
  assert.deepEqual(result.failures, []); result.passed.forEach(done);
}
async function baseline() {
  assert.equal(report.requests.filter(r => r.variant === variant).length, 0); await page.getByText(/尚未指定运行或候选来源/).waitFor(); done('no-source-no-latest-no-request');
  await mount(null, { candidate_ref: 'latest' }); await page.getByRole('alert').waitFor(); assert.equal(report.requests.filter(r => r.variant === variant).length, 0); done('invalid-ref-no-request');
  await mount(null, { run_ref: fixtures.complete.run_ref }); await page.locator('[data-candidate-ref]').first().waitFor();
  assert.equal(await page.getByRole('heading', { name: '候选工作区', exact: true }).count(), 0); await button('查看候选 ' + fixtures.complete.candidate_ref).click();
  await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor(); done('explicit-run-manual-candidate-selection');
  await mount('complete', { return_run_context: { run_ref: fixtures.complete.run_ref, snapshot_ref: 'private' }, return_plan_context: { plan_ref: 'f'.repeat(48), snapshot_ref: 'private' } });
  assert.equal(await page.locator('[data-candidate-ref]').count(), 4);
  assert(await page.getByRole('button', { name: /^采用方案/ }).isDisabled()); assert(await page.getByRole('button', { name: /^试调/ }).isDisabled());
  assert.equal(await page.getByRole('button', { name: /报工/ }).count(), 0); await layout(); await shot('complete');
  await contracts();
  const full = await workspace(fixtures.complete.candidate_ref); assert.equal(full.data.task_count, 3);
  assert(full.data.tasks.every(t => t.machine.label === 'Original lathe')); assert(!JSON.stringify(full).includes('CURRENT RENAMED')); done('captured-generation-labels-after-current-rename');
  for (const name of ['人员', '批次', '设备']) { await button(name).click(); await page.locator('[data-candidate-lane]').first().waitFor(); assert(await button(name).getAttribute('aria-pressed') === 'true'); }
  const canvas = page.locator('[data-candidate-lane]').first();
  const painted = await canvas.evaluate(n => { const bytes = n.getContext('2d').getImageData(0, 0, n.width, n.height).data; let p = 0; for (let i = 3; i < bytes.length; i += 4) if (bytes[i]) p++; return p; }); assert(painted > 300); done('three-dimensions-real-canvas-pixels');
  const bars = await canvas.evaluate(n => ({ width: n.getBoundingClientRect().width, rects: n.__fixtureRects }));
  assert.equal(bars.rects.length, 3);
  const instant = v => Date.parse(v + 'Z'), span = instant(full.data.task_span.end) - instant(full.data.task_span.start);
  full.data.tasks.forEach((t, i) => assert(Math.abs(bars.rects[i][2] - (instant(t.end) - instant(t.start)) / span * bars.width) < 0.001));
  assert(bars.rects[1][2] < 1); done('real-paint-time-proportions-no-short-bar-inflation');
  await canvas.focus(); await page.keyboard.press('Home'); await page.getByRole('complementary', { name: '候选工序详情' }).getByText(full.data.tasks[0].row_ref, { exact: true }).waitFor();
  await page.keyboard.press('ArrowRight'); await page.getByRole('complementary').getByText(full.data.tasks[1].row_ref, { exact: true }).waitFor(); done('short-task-keyboard-row-ref-selection');
  const box = await canvas.boundingBox(), model = await page.evaluate(data => {
    const m = RunCandidateModel.layout(data, 'machine', ''); return { start: m.start, end: m.end, start0: m.rows[0].items[0].start, end0: m.rows[0].items[0].end };
  }, full.data);
  await page.mouse.move(box.x + ((model.start0 + model.end0) / 2 - model.start) / (model.end - model.start) * box.width, box.y + 20);
  await page.getByRole('tooltip').waitFor(); assert((await page.getByRole('tooltip').innerText()).includes(full.data.tasks[0].row_ref)); done('real-canvas-hit-tooltip');
  await button('放大候选时间轴').click(); assert.equal(await page.getByLabel('候选时间轴缩放', { exact: true }).inputValue(), '2');
  await button('适配完整候选时间轴').click(); done('zoom-and-fit');
  await page.getByLabel('搜索候选工序').fill(full.data.tasks[0].row_ref); assert.equal(await page.locator('[data-candidate-task-list] [data-row-ref]').count(), 1);
  await download('csv', full); await download('xlsx', full); done('search-does-not-truncate-export');
  await page.getByLabel('搜索候选工序').fill('');
  await button('读取范围').click(); await page.getByLabel('候选读取开始', { exact: true }).focus(); await page.keyboard.press('Alt+ArrowDown');
  await page.getByRole('dialog').waitFor(); await shot('workbench-date-picker'); await page.keyboard.press('Escape'); done('shared-workbench-date-picker');
  await fillTime('候选读取开始', '2026-10-01T00:00:00');
  await fillTime('候选读取结束', '2026-09-01T00:00:00'); await button('应用范围').click(); await page.getByRole('alert').waitFor(); done('reversed-range-rejected');
  await fillTime('候选读取开始', '2026-09-01T00:00:00'); await fillTime('候选读取结束', full.data.tasks[0].end);
  await button('应用范围').click(); await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor();
  const partial = await workspace(fixtures.complete.candidate_ref, { range_start: '2026-09-01T00:00:00', range_end: full.data.tasks[0].end });
  assert.equal(partial.data.task_count, 1); await download('csv', partial); done('half-open-range-exact-download');
  await button('完整候选').click(); await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor();
  await button('返回运行页').click(); assert.deepEqual(await page.evaluate(() => navigation), ['run', { run_ref: fixtures.complete.run_ref }]);
  await button('返回正式方案').click(); assert.deepEqual(await page.evaluate(() => navigation), ['analysis', { plan_ref: 'f'.repeat(48) }]); done('navigation-context-no-read-token');
  const storage = await page.evaluate(() => ({ keys: Object.keys(localStorage), url: location.href })); assert(storage.keys.every(k => k === 'aps_theme' || k === 'aps_kit_theme')); assert.equal(storage.url, origin + '/'); done('no-token-in-location-or-storage');
  await mount('partial'); await page.getByRole('tab', { name: '未安排明细', exact: true }).click(); await page.getByText('生成时该工序明确排除，未隐藏此项。', { exact: true }).waitFor();
  const partialAll = await workspace(fixtures.partial.candidate_ref); assert.equal(partialAll.data.unplanned_operation_count, 1); await download('xlsx', partialAll); await shot('partial'); done('real-partial-preserves-skipped-operation');
  for (const status of ['failed', 'skipped']) {
    await mount(status); const value = await workspace(fixtures[status].candidate_ref); assert.equal(value.data.task_count, 0);
    assert.equal(await page.locator('[data-candidate-lane]').count(), 0); assert.equal(value.data.candidate.status, status);
    const generation = page.locator('.rc-generation'); assert.equal(await generation.getAttribute('open'), null);
    await generation.locator('summary').first().click();
    await generation.getByText(fixtures[status].run_ref, { exact: true }).waitFor();
    await generation.getByText(fixtures[status].candidate_ref, { exact: true }).waitFor();
    assert((await page.locator('[aria-label="生成时范围"]').innerText()).includes('未知')); await shot(status); done('persisted-' + status + '-not-fabricated-plan');
  }
  await mount('complete'); await page.getByLabel('候选状态', { exact: true }).click(); await page.getByRole('listbox').waitFor();
  await page.getByRole('listbox').getByRole('option', { name: '失败', exact: true }).click(); await page.getByText('此运行在当前筛选下没有候选记录。', { exact: true }).waitFor(); done('workbench-dropdown-empty-filter-not-latest');
  await mount('complete'); const pattern = '**/scheduling/candidates/' + fixtures.complete.candidate_ref + '/workspace?*';
  await page.route(pattern, route => route.fulfill({ status: 500, contentType: 'text/html', body: 'Unavailable' })); await button('刷新指定候选来源').click();
  await page.getByRole('alert').waitFor(); assert.equal(await page.locator('[data-candidate-lane]').count(), 0); assert.equal(await button('CSV').count(), 0);
  await page.unroute(pattern); await button('刷新指定候选来源').click(); await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor(); done('failed-refresh-clears-old-data-and-export');
  await page.request.post(origin + '/fixture/restart'); await button('CSV').click(); await page.getByRole('alert').waitFor(); done('expired-read-token-download-not-faked');
  await button('刷新指定候选来源').click(); await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor();
  await page.evaluate(() => { const api = RunCandidateAnalysisAPI.create(); window.mountCandidate(fixtureSource, { ...api, workspace: async (...args) => { const v = await api.workspace(...args); v.data.capabilities.view = false; return v; } }); });
  await page.getByText('接口未授权查看该候选。', { exact: false }).waitFor(); assert.equal(await button('CSV').count(), 0); assert.equal(await page.locator('[data-candidate-lane]').count(), 0); done('view-capability-false-no-content-or-export');
  await page.evaluate(() => { const api = RunCandidateAnalysisAPI.create(); window.mountCandidate(fixtureSource, { ...api, workspace: async (...args) => { const v = await api.workspace(...args); v.data.capabilities.export = false; return v; } }); });
  await button('CSV').waitFor(); assert(await button('CSV').isDisabled()); assert(await button('XLSX').isDisabled()); done('export-capability-false-disabled');
  const history = await (await page.request.get(origin + '/api/workbench/v1/scheduling/runs')).json();
  assert(history.ok); const old = history.data.runs.find(r => r.run_ref === fixtures.complete.run_ref); assert(old);
  assert.equal(old.constraint_verification, 'not_checked_by_history'); assert.equal(old.task_count_basis, 'persisted_rows_across_candidates');
  const directory = await (await page.request.get(origin + '/api/workbench/v1/scheduling/runs/' + old.run_ref + '/candidates')).json();
  await mount(null, { run_ref: old.run_ref, candidate_ref: directory.data.candidates[0].candidate_ref });
  assert.equal(await page.locator('[data-candidate-task-list] [data-row-ref]').count(), 3); done('BQ-real-history-to-old-run-candidate-workspace');
}
async function capacity() {
  await mount('capacity'); const full = await workspace(fixtures.capacity.candidate_ref); assert.equal(full.data.task_count, 5000); await page.locator('[data-candidate-lane]').first().waitFor();
  for (const dimension of ['设备', '人员', '批次']) {
    await button(dimension).click();
    const lastLabel = await page.evaluate(({ data, dimension }) => {
      const mode = { '设备': 'machine', '人员': 'operator', '批次': 'batch' }[dimension], model = RunCandidateModel.layout(data, mode, '');
      return model.rows[model.rows.length - 1].label;
    }, { data: full.data, dimension });
    const scroll = page.locator('[data-candidate-gantt-scroll]'); await scroll.evaluate(n => { n.scrollTop = n.scrollHeight; });
    await page.waitForFunction(label => [...document.querySelectorAll('[data-candidate-track]')].some(n => n.textContent.includes(label)), lastLabel);
    assert(await scroll.evaluate(n => Math.abs(n.scrollHeight - n.clientHeight - n.scrollTop) < 2));
    const lanes = await page.locator('[data-candidate-lane]').count(), nodes = await page.locator('[data-run-candidate-workspace] *').count();
    assert(lanes < 12); assert(nodes < 1200); report.capacity.push({ variant, dimension, tasks: 5000, lanes, nodes });
  }
  const list = page.locator('[data-candidate-task-list]'); await list.evaluate(n => { n.scrollTop = n.scrollHeight; });
  await page.locator('[data-candidate-task-list] [data-row-ref="' + full.data.tasks[4999].row_ref + '"]').waitFor();
  assert(await page.locator('[data-candidate-task-list] [data-row-ref]').count() <= 16);
  await button('工序详情 ' + full.data.tasks[4999].row_ref).click(); await page.getByRole('complementary').getByText(full.data.tasks[4999].row_ref, { exact: true }).waitFor();
  await layout(); await shot('5000'); await page.getByLabel('搜索候选工序').fill('CAP-099');
  await download('csv', full); await download('xlsx', full); done('5000-source-tasks-bounded-dom-and-complete-download');
  await page.reload(); await page.getByText(/尚未指定运行或候选来源/).waitFor();
  await mount(null, { candidate_ref: fixtures.capacity.candidate_ref }); await page.locator('[data-candidate-ref]').first().waitFor();
  assert.equal(await page.locator('[data-candidate-ref]').count(), 4); done('fresh-page-explicit-old-candidate-recovers-run');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  assert(![63938, 51093, 56264, 52155, 51733].includes(server.address().port));
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.')); origin = 'http://127.0.0.1:' + server.address().port;
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      variant = width + '-' + theme; const row = { variant, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height: 1100 } });
      await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      await context.addInitScript(() => {
        const transform = CanvasRenderingContext2D.prototype.setTransform, fill = CanvasRenderingContext2D.prototype.fillRect;
        CanvasRenderingContext2D.prototype.setTransform = function(...args) { if (this.canvas.hasAttribute('data-candidate-lane')) this.canvas.__fixtureRects = []; return transform.apply(this, args); };
        CanvasRenderingContext2D.prototype.fillRect = function(...args) { if (this.canvas.hasAttribute('data-candidate-lane')) this.canvas.__fixtureRects.push(args); return fill.apply(this, args); };
      });
      page = await context.newPage(); page.setDefaultTimeout(20000);
      page.on('pageerror', error => report.errors.push(error.message)); page.on('dialog', dialog => { report.dialogs.push(dialog.type()); dialog.dismiss(); });
      page.on('request', request => { if (request.url().includes('/api/')) report.requests.push({ variant, method: request.method(), path: new URL(request.url()).pathname }); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin); fixtures = await (await page.request.get(origin + '/fixture/cases')).json();
      try { await baseline(); await capacity(); row.passed = true; }
      catch (error) { row.error = error.stack; await shot('FAILED'); throw error; }
      finally { await context.tracing.stop({ path: path.join(output, variant + '-trace.zip') }); await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []);
    assert.deepEqual(report.requests.filter(r => r.path.endsWith('/baseline')), []);
    console.log(JSON.stringify({ browser: report.browser, checks: report.cases.length, variants: report.variants.length, downloads: report.downloads.length, output }));
  } finally {
    if (browser) await browser.close(); server.close();
    fs.writeFileSync(path.join(output, 'candidate-widgets.json'), JSON.stringify(report, null, 2));
  }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
