/* BZ pending source hook. No main build, registry, frozen preview or production DB. */
'use strict';
const UI = require('./run_ui_source.cjs');
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const files = UI.dependencies(['resource-contract.js', 'ResourceControls.jsx', 'CalendarContract.js', 'PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx', 'PlanGanttModel.js', 'RunCandidateAPI.js', 'RunCandidateModel.js', 'RunCandidateControls.jsx',
  'RunBaselineAPI.js', 'RunBaselineModel.js', 'RunBaselineControls.jsx', 'RunCandidateGantt.jsx']);
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, i) => ['/source/' + files[i], row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const report = { browser: null, variants: [], checks: [], screenshots: [], errors: [], external: [], dialogs: [], requests: [], capacity: [],
  compile: { global_build: false, target: 'chrome109' }, sources: sources.map(row => ({ path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex') })) };
const boot = `let fixtureRoot;function Fixture(props){const [data,setData]=React.useState(props.data),[selected,setSelected]=React.useState(null),[query,setQuery]=React.useState('');
window.setBaselineData=d=>{window.fixtureData=d;setData(d);setSelected(null);};window.setBaselineSearch=setQuery;window.fixtureData=data;
return React.createElement('div',{className:'plana run-candidate-workspace'},React.createElement(RunCandidateControls.Styles),React.createElement(RunCandidateGantt,{data,query,selected,onSelect:setSelected}),
React.createElement(RunCandidateControls.Detail,{task:selected,onClose:()=>setSelected(null)}));}
window.mountBaseline=async(ref,scope={})=>{const result=await RunCandidateAPI.create().workspace(ref,scope);window.workspaceEnvelope=result;
if(fixtureRoot)fixtureRoot.unmount();fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));fixtureRoot.render(React.createElement(Fixture,{data:result.data}));};
window.swapBaseline=async(ref,scope={})=>{const result=await RunCandidateAPI.create().workspace(ref,scope);window.workspaceEnvelope=result;window.setBaselineData(result.data);};`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  UI.styles(report, output) + '<style>body{margin:0}#fixture-root{margin:20px 28px 20px 264px;min-width:0}@media(max-width:760px){#fixture-root{margin:12px}}</style></head><body class="aps-workbench"><div id="fixture-root"></div>' +
  staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
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
const button = name => UI.button(page, name);
const toggle = () => page.getByRole('checkbox', { name: '初始计划', exact: true });
const done = name => report.checks.push({ variant, name, passed: true });
const paintedFrame = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: true, animations: 'disabled' }); report.screenshots.push(file); }
async function mount(name, scope = {}) {
  await page.evaluate(({ ref, scope }) => mountBaseline(ref, scope), { ref: fixtures[name].candidate_ref, scope }); await toggle().waitFor();
}
async function loaded() {
  await page.locator('.rb-panel').waitFor(); assert.equal(await page.getByRole('alert').count(), 0);
}
async function readBaseline() {
  return page.evaluate(async () => { const v = await RunBaselineAPI.create().read(fixtureData); window.baselineEnvelope = v; return { count: v.data.operation_count, counts: v.data.counts }; });
}
async function layout() {
  await paintedFrame();
  const result = await page.evaluate(() => {
    const g = document.querySelector('.rc-gantt'), scroll = g.querySelector('.rc-scroll'), box = scroll.getBoundingClientRect();
    return { overflow: document.documentElement.scrollWidth > innerWidth, width: g.getBoundingClientRect().width,
      labels: [...g.querySelectorAll('.rc-lane-label')].map(n => ({ x: n.getBoundingClientRect().x, width: n.getBoundingClientRect().width })),
      canvases: [...g.querySelectorAll('canvas')].map(n => ({ x: n.getBoundingClientRect().x, right: n.getBoundingClientRect().right })),
      scroll: { x: box.x, right: box.right }, clipped: [...g.querySelectorAll('button')].filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.textContent) };
  });
  assert.equal(result.overflow, false, JSON.stringify(result)); assert.deepEqual(result.clipped, []);
  assert(result.labels.every(n => Math.abs(n.x - result.scroll.x) < 2 && Math.abs(n.width - 156) < 2));
  assert(result.canvases.every(n => n.x >= result.scroll.x + 155 && n.right <= result.scroll.right + 2), JSON.stringify(result));
}
async function proportions() {
  const result = await page.evaluate(() => {
    const M = RunCandidateModel, B = RunBaselineModel, mode = ['machine', 'operator', 'batch'].find((k, i) => document.querySelectorAll('[aria-label="候选甘特维度"] button')[i].getAttribute('aria-pressed') === 'true');
    const model = B.compose(M.layout(fixtureData, mode, ''), baselineEnvelope.data, mode, ''), scroll = document.querySelector('.rc-scroll');
    const left = scroll.scrollLeft, width = document.querySelector('.rc-bar-space').getBoundingClientRect().width;
    let painted = 0, short = 0, compared = 0;
    for (const canvas of document.querySelectorAll('.rc-gantt canvas')) {
      const parent = canvas.closest('.rc-lane'), key = parent.getAttribute('data-baseline-track') || parent.getAttribute('data-candidate-track');
      const row = model.rows.find(r => r.key === key), bars = row.baseline ? canvas.__strokes : canvas.__fills;
      const items = M.visibleItems(row.items, model.start + left / width * (model.end - model.start), model.start + (left + canvas.clientWidth) / width * (model.end - model.start));
      if (bars.length !== items.length) throw Error('Canvas item count mismatch ' + key + ' ' + bars.length + '/' + items.length);
      items.forEach((item, i) => {
        const bar = bars[i], w = (item.end - item.start) / (model.end - model.start) * width, x = (item.start - model.start) / (model.end - model.start) * width - left;
        const edge = row.baseline ? Math.min(w, bar.lineWidth) : 0;
        if (Math.abs(bar.args[0] - x - edge / 2) > 0.0001 || Math.abs(bar.args[2] + edge - w) > 0.0001) throw Error('Wrong time proportion');
        if (row.baseline && bar.dash.join() !== '4,3') throw Error('Missing dashed initial plan');
        if (w < 1) short++; compared++;
      });
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) painted++;
    }
    return { painted, short, compared };
  });
  assert(result.painted > 100); assert(result.compared > 0); return result;
}
async function contracts() {
  const result = await page.evaluate(async () => {
    const source = baselineEnvelope, W = fixtureData, A = RunBaselineAPI, failures = [], passed = [];
    const reject = (name, change) => { const copy = JSON.parse(JSON.stringify(source)); change(copy); try { A.validate(copy, W); failures.push(name); } catch (_) { passed.push(name); } };
    reject('wrong-candidate', v => { v.data.candidate.candidate_ref = 'a'.repeat(48); });
    reject('wrong-scope', v => { v.data.time_scope.range_start = '2026-01-01T00:00:00'; });
    reject('current-metadata', v => { v.data.generation.current_entities_consulted = true; });
    reject('incomplete-rows', v => { v.data.rows_complete = false; });
    reject('wrong-count', v => { v.data.comparisons.pop(); });
    reject('fake-task-ref', v => { v.data.comparisons[0].task_ref = 'a'.repeat(48); });
    reject('fake-candidate-row-for-baseline-only', v => { v.data.comparisons.find(r => r.status === 'baseline_only').row_ref = 'b'.repeat(48); });
    reject('unscheduled-benefit', v => { v.data.comparisons.find(r => r.status === 'unscheduled').delta.end_hours = -4; });
    reject('fabricated-benefit', v => { v.data.improvement_assessment = 'better'; });
    reject('wrong-delta', v => { v.data.comparisons.find(r => r.status === 'matched').delta.start_hours += 1; });
    reject('merged-segment', v => { v.data.comparisons.find(r => r.baseline_segments.length > 1).baseline_segments.pop(); });
    reject('duplicate-segment', v => { const r = v.data.comparisons.find(r => r.baseline_segments.length > 1); r.baseline_segments[1].row_ref = r.baseline_segments[0].row_ref; });
    reject('invalid-date', v => { v.data.comparisons.find(r => r.baseline_segments.length).baseline_segments[0].start = '2026-02-30T08:00:00'; });
    const before = JSON.stringify([W, source]), candidate = RunCandidateModel.layout(W, 'machine', ''), combined = RunBaselineModel.compose(candidate, source.data, 'machine', '');
    if (JSON.stringify([W, source]) !== before) failures.push('mutation'); else passed.push('composition-does-not-mutate-dtos');
    const oldRows = combined.rows.filter(r => r.baseline);
    if (!oldRows.some(r => r.label === 'Admission old lathe') || !oldRows.some(r => r.laneCount > 1)) failures.push('missing-old-resource-or-overlap'); else passed.push('original-resource-and-overlap-tracks-retained');
    if (oldRows.some(r => r.items.some(i => i.task || i.segment.task_ref))) failures.push('fake-task'); else passed.push('separate-baseline-identity-no-candidate-task');
    const all = source.data.comparisons.flatMap(r => r.baseline_segments).filter(s => s.interval_comparable);
    if (oldRows.reduce((n, r) => n + r.items.length, 0) !== all.length) failures.push('lost-segment'); else passed.push('every-saved-baseline-segment-retained');
    const key = W.candidate.candidate_ref, response = await fetch('/api/workbench/v1/scheduling/candidates/' + key + '/baseline?snapshot_ref=' + workspaceEnvelope.meta.snapshot_ref);
    if (response.ok) failures.push('workspace-token-accepted'); else passed.push('server-rejects-workspace-token-for-baseline');
    if (A.scope(W).snapshot_ref !== undefined || source.meta.snapshot_ref === workspaceEnvelope.meta.snapshot_ref) failures.push('snapshot-reuse'); else passed.push('independent-baseline-snapshot');
    return { failures, passed };
  });
  assert.deepEqual(result.failures, []); result.passed.forEach(done);
}
async function small() {
  await mount('mixed'); assert.equal(report.requests.filter(r => r.variant === variant && r.path.includes('/baseline')).length, 0); done('default-no-baseline-request');
  const initial = await page.evaluate(() => ({ rows: document.querySelectorAll('[data-candidate-track]').length, span: fixtureData.task_span }));
  await toggle().check(); await loaded(); await readBaseline(); await contracts(); await layout();
  assert(await page.locator('[data-baseline-track]').count() > 0); assert((await proportions()).short > 0); await shot('overlay'); done('shared-full-time-axis-and-short-bars');
  assert.equal(await page.locator('.rb-panel').getAttribute('open'), null); done('explanations-collapsed-by-default');
  const candidateLane = page.locator('[data-candidate-lane]').first(); await candidateLane.focus(); await page.keyboard.press('Home'); await page.keyboard.press('ArrowRight');
  const shortRef = await page.evaluate(() => fixtureData.tasks[1].row_ref); await UI.reference(page.getByRole('complementary'), shortRef); done('short-candidate-keyboard-detail');
  const baselineLane = page.locator('[data-baseline-lane]').first(); await baselineLane.focus(); await page.keyboard.press('End');
  await page.getByRole('region', { name: '初始计划工序对照', exact: true }).waitFor(); done('baseline-keyboard-own-detail');
  const gold = await baselineLane.evaluate(n => n.__strokes.some(s => s.color === getComputedStyle(n).getPropertyValue('--wb-gantt-gold').trim() && s.lineWidth === 2)); assert(gold); done('selected-baseline-gold-border');
  const multiRef = await page.evaluate(() => baselineEnvelope.data.comparisons.find(r => r.baseline_segments.length > 1).operation_ref);
  await button('初始计划对照 ' + multiRef).click(); assert.equal(await page.locator('[data-baseline-segment]').count(), 2);
  await page.getByText('初始计划里这道工序分成了几段，这里不合并也不任选一段来对照。', { exact: true }).waitFor(); await shot('multi-segment-detail'); done('multiple-segments-not-merged');
  const unplannedRef = await page.evaluate(() => baselineEnvelope.data.comparisons.find(r => r.status === 'unscheduled').operation_ref);
  await button('初始计划对照 ' + unplannedRef).click(); await page.getByText('此候选方案未安排该工序。', { exact: true }).waitFor(); done('unscheduled-is-not-improvement');
  const onlyRef = await page.evaluate(() => baselineEnvelope.data.comparisons.find(r => r.status === 'baseline_only').operation_ref);
  await button('初始计划对照 ' + onlyRef).click(); await page.getByText('这道工序只在排产时的正式计划里，不在这次选择的范围内。', { exact: true }).waitFor(); done('baseline-only-detail-retained');
  for (const name of ['人员', '批次', '设备']) { await button(name).click(); await proportions(); await layout(); }
  done('three-dimensions-preserve-both-sides');
  await button('放大候选时间轴').click(); await paintedFrame(); await page.getByLabel('候选时间轴水平位置', { exact: true }).evaluate(n => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; setter.call(n, n.max); n.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.locator('.rc-scroll').evaluate(n => { n.scrollLeft = n.scrollWidth; });
  await page.waitForFunction(() => document.querySelector('.rc-scroll').scrollLeft > 0); await layout(); await proportions(); await shot('zoom-right-edge'); done('zoom-pan-no-label-overpaint');
  await toggle().uncheck(); assert.equal(await page.locator('[data-baseline-lane]').count(), 0); await button('显示完整候选时间范围').click();
  assert.equal(await page.locator('[data-candidate-track]').count(), initial.rows); assert.equal(await page.locator('.rb-panel').count(), 0); await layout(); done('close-restores-candidate-only-geometry');
  await toggle().check(); await loaded(); await toggle().uncheck(); done('close-and-reopen-fresh-read');
  await mount('no_baseline'); await toggle().check(); await loaded(); await page.locator('.rb-panel summary').click();
  await page.getByText('排产时没有正式的初始计划，算不出相对改善。', { exact: true }).waitFor(); assert.equal(await page.locator('[data-baseline-lane]').count(), 0); done('no-baseline-not-zero-improvement');
  await mount('execution'); await toggle().check(); await loaded(); await readBaseline(); await page.locator('.rb-panel summary').click();
  const execRef = await page.evaluate(() => baselineEnvelope.data.comparisons.find(r => r.execution_affected).operation_ref);
  await button('初始计划对照 ' + execRef).click(); await page.getByText('排产时这道工序已经开工或数量不明，时间差不能算成排产优化。', { exact: true }).waitFor(); done('real-execution-evidence-no-benefit-attribution');
}
async function scopes() {
  await mount('mixed', { range_start: '2026-09-12T08:01:00', range_end: '2026-09-12T08:02:00' });
  assert.equal(await page.locator('[data-candidate-lane]').count(), 0); await toggle().check(); await loaded(); await readBaseline();
  assert(await page.locator('[data-baseline-lane]').count() > 0); await page.locator('.rb-panel summary').click();
  const ref = await page.evaluate(() => baselineEnvelope.data.comparisons.find(r => r.candidate).operation_ref);
  await button('初始计划对照 ' + ref).click(); await page.getByText('该候选安排不在当前读取范围；此处保留完整对照。', { exact: true }).waitFor();
  assert.equal(await page.locator('[data-candidate-lane]').count(), 0); await layout(); done('baseline-side-only-scope-no-fabricated-candidate-row');
  const result = await page.evaluate(async ref => {
    const all = await RunCandidateAPI.create().workspace(ref), batch = all.data.tasks[0].batch_ref;
    const q = { range_start: '2026-09-12T11:00:00', range_end: '2026-09-13T00:00:00', batch_ref: batch };
    const w = await RunCandidateAPI.create().workspace(ref, q), b = await RunBaselineAPI.create().read(w.data);
    const future = await RunCandidateAPI.create().workspace(ref, { range_start: '2027-01-01T00:00:00', range_end: '2027-01-02T00:00:00' });
    const f = await RunBaselineAPI.create().read(future.data);
    return { boundaryCount: b.data.operation_count, statuses: f.data.comparisons.map(r => r.status), allStarts: baselineEnvelope.data.comparisons.flatMap(r => r.baseline_segments).map(s => s.start) };
  }, fixtures.mixed.candidate_ref);
  assert.equal(result.boundaryCount, 0); assert.deepEqual(result.statuses.sort(), ['baseline_only', 'unscheduled']); assert(result.allStarts.includes('2026-09-12T08:00:00'));
  done('half-open-batch-scope-and-untimed-policy');
  await mount('mixed'); await toggle().check(); await loaded(); await page.evaluate(() => setBaselineSearch('Admission old lathe'));
  await page.waitForFunction(() => document.querySelectorAll('[data-baseline-lane]').length === 1); assert.equal(await page.locator('[data-candidate-lane]').count(), 0); done('search-preserves-original-resource');
}
async function failuresAndRaces() {
  await mount('mixed'); await toggle().check(); await loaded(); await toggle().uncheck();
  const pattern = '**/scheduling/candidates/' + fixtures.mixed.candidate_ref + '/baseline?*';
  await page.route(pattern, route => route.fulfill({ status: 500, contentType: 'text/html', body: 'Unavailable' }));
  await toggle().check(); await page.getByRole('alert').waitFor(); assert.equal(await page.locator('[data-baseline-lane]').count(), 0); assert.equal(await page.locator('.rb-panel').count(), 0);
  assert(await page.locator('[data-candidate-lane]').count() > 0); await page.unroute(pattern); await button('刷新初始计划').click(); await loaded(); done('failed-read-clears-baseline-only-and-retry');
  for (const action of ['cancel', 'candidate', 'scope']) {
    await mount('mixed'); let release, ready;
    const gate = new Promise(resolve => { release = resolve; }), received = new Promise(resolve => { ready = resolve; });
    await page.route(pattern, async route => { const response = await route.fetch(); ready(); await gate; try { await route.fulfill({ response }); } catch (error) { if (!/closed|disposed|Invalid Interception|abort/i.test(error.message)) throw error; } });
    const aborted = await page.evaluate(() => window.baselineAborts || 0);
    await toggle().check(); await received;
    if (action === 'cancel') await toggle().uncheck();
    else await page.evaluate(({ ref, scope }) => swapBaseline(ref, scope), { ref: action === 'candidate' ? fixtures.no_baseline.candidate_ref : fixtures.mixed.candidate_ref,
      scope: action === 'scope' ? { range_start: '2027-01-01T00:00:00', range_end: '2027-01-02T00:00:00' } : {} });
    await page.waitForFunction(n => window.baselineAborts > n, aborted); release(); await page.unroute(pattern);
    if (action !== 'cancel') await loaded();
    assert.equal(await page.locator('[data-baseline-track]').filter({ hasText: 'Admission old lathe' }).count(), 0);
    if (action === 'cancel') assert.equal(await page.locator('.rb-panel').count(), 0);
    done('abort-and-ignore-old-response-' + action);
  }
  const leaked = report.requests.filter(r => r.variant === variant && r.path.endsWith('/baseline') && r.query.includes('snapshot_ref') && !r.query.includes('snapshot_ref='));
  assert.deepEqual(leaked, []);
}
async function capacity() {
  await mount('capacity'); await toggle().check(); await loaded(); const actual = await readBaseline(); assert.equal(actual.count, 5000); assert.deepEqual(actual.counts, { matched: 5000 });
  for (const name of ['设备', '人员', '批次']) {
    await button(name).click();
    const last = await page.evaluate(name => {
      const mode = { '设备': 'machine', '人员': 'operator', '批次': 'batch' }[name], m = RunBaselineModel.compose(RunCandidateModel.layout(fixtureData, mode, ''), baselineEnvelope.data, mode, '');
      return m.rows[m.rows.length - 1].key;
    }, name);
    await page.locator('.rc-scroll').evaluate(n => { n.scrollTop = n.scrollHeight; }); await page.locator('[data-baseline-track="' + last + '"]').waitFor();
    assert(await page.locator('.rc-scroll').evaluate(n => Math.abs(n.scrollHeight - n.clientHeight - n.scrollTop) < 2));
    const lanes = await page.locator('.rc-gantt canvas').count(), nodes = await page.locator('.rc-gantt *').count(); assert(lanes < 16); assert(nodes < 350);
    report.capacity.push({ variant, dimension: name, operations: actual.count, lanes, nodes }); await proportions();
  }
  await page.locator('.rb-panel summary').click(); await page.locator('[data-baseline-list]').evaluate(n => { n.scrollTop = n.scrollHeight; });
  const lastRef = await page.evaluate(() => baselineEnvelope.data.comparisons[4999].operation_ref);
  await button('初始计划对照 ' + lastRef).click(); await UI.reference(page.getByRole('region', { name: '初始计划工序对照', exact: true }), lastRef);
  assert(await page.locator('[data-baseline-operation]').count() <= 12); await layout(); await shot('5000-last-track-and-detail'); done('5000-virtual-rows-last-track-and-detail');
  await toggle().uncheck(); await page.locator('.rc-scroll').evaluate(n => { n.scrollTop = n.scrollHeight; });
  const lastCandidate = await page.evaluate(() => { const row = RunCandidateModel.layout(fixtureData, 'batch', '').rows.slice(-1)[0]; return { key: row.key, ref: row.items.slice(-1)[0].task.row_ref }; });
  const lastLane = page.locator('[data-candidate-track="' + lastCandidate.key + '"] canvas'); await lastLane.waitFor(); await lastLane.focus(); await page.keyboard.press('End');
  await UI.reference(page.getByRole('complementary'), lastCandidate.ref); done('5000-close-restores-last-candidate-keyboard');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.')); origin = 'http://127.0.0.1:' + server.address().port;
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      variant = width + '-' + theme; const row = { variant, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height: 1100 }, timezoneId: 'America/New_York' });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      await context.addInitScript(() => {
        const transform = CanvasRenderingContext2D.prototype.setTransform, fill = CanvasRenderingContext2D.prototype.fillRect, stroke = CanvasRenderingContext2D.prototype.strokeRect;
        CanvasRenderingContext2D.prototype.setTransform = function(...args) { this.canvas.__fills = []; this.canvas.__strokes = []; return transform.apply(this, args); };
        CanvasRenderingContext2D.prototype.fillRect = function(...args) { this.canvas.__fills.push({ args, color: this.fillStyle }); return fill.apply(this, args); };
        CanvasRenderingContext2D.prototype.strokeRect = function(...args) { this.canvas.__strokes.push({ args, color: this.strokeStyle, lineWidth: this.lineWidth, dash: this.getLineDash() }); return stroke.apply(this, args); };
        const send = window.fetch; window.baselineAborts = 0;
        window.fetch = function(url, options) { if (String(url).includes('/baseline?') && options && options.signal) options.signal.addEventListener('abort', () => window.baselineAborts++); return send.apply(this, arguments); };
      });
      page = await context.newPage(); page.setDefaultTimeout(20000);
      page.on('pageerror', error => report.errors.push(error.message)); page.on('dialog', dialog => { report.dialogs.push(dialog.type()); dialog.dismiss(); });
      page.on('request', req => { if (req.url().includes('/api/')) { const url = new URL(req.url()); report.requests.push({ variant, method: req.method(), path: url.pathname, query: url.search }); } });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin); fixtures = await (await page.request.get(origin + '/fixture/cases')).json();
      try { await small(); await scopes(); await failuresAndRaces(); await capacity(); row.passed = true; }
      catch (error) { row.error = error.stack; await shot('FAILED'); throw error; }
      finally { await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []);
    console.log(JSON.stringify({ browser: report.browser, checks: report.checks.length, variants: report.variants.length, output }));
  } finally { if (browser) await browser.close(); server.close(); fs.writeFileSync(path.join(output, 'baseline-widgets.json'), JSON.stringify(report, null, 2)); }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
