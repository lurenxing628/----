/* Current source only, in-memory compilation; real HTTP is proxied to disposable Flask/SQLite. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const files = ['resource-contract.js', 'ResourceControls.jsx', 'RunJobAPI.js', 'RunJobControls.jsx', 'RunJobPanel.jsx'];
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, index) => ['/fixture/script/' + files[index], row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const report = { browser: null, variants: [], cases: [], screenshots: [], errors: [], external: [], dialogs: [], requests: [], injected: [],
  compile: { global_build: false, target: 'chrome109' }, sources: sources.map(row => ({ path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex') })) };
const boot = `let fixtureRoot;window.mountRun=(preflight,adapter)=>{if(fixtureRoot)fixtureRoot.unmount();fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
fixtureRoot.render(React.createElement(RunJobPanel,{preflight,adapter,onNavigate:(...args)=>{window.navigation=args;window.unmountRun();}}));};
window.unmountRun=()=>{if(fixtureRoot){fixtureRoot.unmount();fixtureRoot=null;}};window.mountRun(null);`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>body{margin:0}#fixture-root{margin:24px 32px 24px 264px;min-width:0}@media(max-width:760px){#fixture-root{margin:12px}}</style></head><body class="aps-workbench"><div id="fixture-root"></div>' +
  staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://fixture').pathname;
  if (pathname.startsWith('/api/') || pathname.startsWith('/fixture/') && !scripts.has(pathname)) {
    const upstream = http.request(backend + req.url, { method: req.method, headers: req.headers }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
    upstream.on('error', error => { res.writeHead(502); res.end(error.message); }); req.pipe(upstream); return;
  }
  if (pathname === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
  const asset = assets.get(pathname);
  if (!asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
let page, origin, variant;
const button = name => page.getByRole('button', { name, exact: true });
const startButton = () => page.getByRole('button', { name: /^核对并开始排产/ });
const state = (value, stage) => page.locator('[data-run-state="' + value + '"]' + (stage ? '[data-run-stage="' + stage + '"]' : ''));
const local = () => page.evaluate(() => RunJobAPI.pending().read());
const caseDone = name => report.cases.push({ variant, name, passed: true });
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: true, animations: 'disabled' }); report.screenshots.push(file); }
async function control(action, extra = {}) { const r = await page.request.post(origin + '/fixture/control', { data: { action, ...extra } }); assert(r.ok(), await r.text()); return r.json(); }
async function reset(mode = 'complete') {
  await page.evaluate(() => { window.unmountRun(); localStorage.removeItem(RunJobAPI.PENDING_KEY); });
  const response = await page.request.post(origin + '/fixture/reset', { data: { mode } }); assert(response.ok(), await response.text());
  const settings = await response.json(), checked = await page.request.post(origin + '/api/workbench/v1/scheduling/preflight', { data: settings });
  assert.equal(checked.status(), 200, await checked.text()); const result = (await checked.json()).data;
  assert.equal(result.write_context.write_token, null); assert.equal(result.write_context.capabilities['scheduling.run'], false);
  await page.evaluate(result => { window.currentPreflight = result; window.mountRun(result); }, result); return result;
}
async function confirm() {
  const response = page.waitForResponse(r => r.url().endsWith('/scheduling/runs/preview'));
  await startButton().click(); await page.getByRole('dialog', { name: '确认本次候选排产' }).waitFor();
  await page.evaluate(v => { window.fixturePreview = v; }, await (await response).json());
  assert.equal(await page.locator('.modal-bg').evaluate(n => getComputedStyle(n).position), 'fixed');
  await page.getByText(/精确批次引用/).click(); assert((await page.locator('.rj-refs li').count()) > 0);
  await shot('confirm');
  await button('确认开始排产').evaluate(node => { node.click(); node.click(); });
}
async function accepted() {
  const response = page.waitForResponse(r => r.url().endsWith('/scheduling/runs') && r.status() === 202);
  await confirm(); await state('queued').waitFor(); const intent = await local(); assert(intent.run_ref);
  await page.evaluate(v => { window.fixtureAcceptance = v; }, await (await response).json());
  assert.deepEqual(Object.keys(intent).sort(), ['input_ref', 'request_key', 'run_ref']); return intent;
}
async function refresh() { await button('查询原运行').waitFor({ state: 'visible' }); await button('查询原运行').click(); }
async function layout() {
  const value = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth,
    clippedButtons: [...document.querySelectorAll('[data-run-job-panel] button')].filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.textContent),
    invalid: [...document.querySelectorAll('[data-run-job-panel] input,[data-run-job-panel] select,[data-run-job-panel] progress')].length }));
  assert.equal(value.overflow, false, JSON.stringify(value)); assert.deepEqual(value.clippedButtons, []); assert.equal(value.invalid, 0);
}
async function contracts() {
  const result = await page.evaluate(async () => {
    const A = RunJobAPI, api = A.create(), intent = A.pending().read(), actual = await api.get(intent.run_ref);
    const directory = await api.catalog(intent.run_ref), failures = [], passed = [];
    function reject(name, value, mutate, read) {
      const copy = JSON.parse(JSON.stringify(value)); mutate(copy);
      try { read(copy); failures.push(name); } catch (_) { passed.push(name); }
    }
    const readRun = v => A.run(A.envelope(v), intent.run_ref);
    reject('private-facts-top', actual, v => { v.data.facts_json = '{}'; }, readRun);
    reject('private-execution-candidate', actual, v => { v.data.candidates[0].execution_json = '{}'; }, readRun);
    reject('fake-plan-ref', actual, v => { v.data.plans = [{ plan_ref: 'a'.repeat(48) }]; }, readRun);
    reject('fake-plan-catalog', actual, v => { v.data.plan_catalog_connected = true; }, readRun);
    reject('fabricated-progress', actual, v => { v.data.progress = 80; }, readRun);
    reject('negative-count', actual, v => { v.data.candidates[0].task_count = -1; }, readRun);
    reject('unsafe-count', actual, v => { v.data.candidates[0].task_count = Number.MAX_SAFE_INTEGER + 1; }, readRun);
    reject('candidate-identity-duplicate', actual, v => { v.data.candidates[1].candidate_ref = v.data.candidates[0].candidate_ref; }, readRun);
    reject('run-identity-mismatch', actual, v => { v.data.run_ref = 'f'.repeat(48); }, readRun);
    reject('terminal-receipt-missing', actual, v => { v.data.receipt_ref = null; }, readRun);
    reject('result-not-saved', actual, v => { v.data.result_persisted = false; }, readRun);
    reject('terminal-wrong-stage', actual, v => { v.data.stage = 'computing'; }, readRun);
    reject('untrusted-source', actual, v => { v.meta.source = 'sample'; }, readRun);
    reject('unknown-schema', actual, v => { v.schema_version = 2; }, readRun);
    reject('missing-meta', actual, v => { delete v.meta; }, readRun);
    reject('fake-status-target', fixtureAcceptance, v => { v.status_target = '/scheduler/run'; }, A.accepted);
    reject('accepted-private-payload', fixtureAcceptance, v => { v.data.facts_json = '{}'; }, A.accepted);
    reject('accepted-wrong-receipt-kind', fixtureAcceptance, v => { v.receipt_ref = 'f'.repeat(48); }, A.accepted);
    const readPreview = v => A.preview(v, fixturePreview.data.input_ref);
    reject('preview-wrong-input', fixturePreview, v => { v.data.input_ref = 'z'.repeat(32); }, readPreview);
    reject('preview-private-facts', fixturePreview, v => { v.data.normalized_input.facts_json = '{}'; }, readPreview);
    reject('preview-null-write-token', fixturePreview, v => { v.data.write_context.write_token = null; }, readPreview);
    reject('preview-capability-false-token-present', fixturePreview, v => { v.data.write_context.capabilities['scheduling.run'] = false; }, readPreview);
    reject('preview-duplicate-batches', fixturePreview, v => { v.data.normalized_input.batch_refs.push(v.data.normalized_input.batch_refs[0]); }, readPreview);
    reject('preview-invalid-window', fixturePreview, v => { v.data.normalized_input.start_date = '2026-02-30'; }, readPreview);
    reject('preview-unknown-setting', fixturePreview, v => { v.data.normalized_input.profile = 'other'; }, readPreview);
    const readCatalog = v => A.catalog(v, intent.run_ref);
    reject('catalog-private-artifact', directory, v => { v.data.candidates[0].artifact_json = '{}'; }, readCatalog);
    reject('catalog-task-mismatch', directory, v => { v.data.page.total += 1; }, readCatalog);
    reject('catalog-cross-run', directory, v => { v.data.candidates[0].run_ref = 'f'.repeat(48); }, readCatalog);
    reject('catalog-can-adopt', directory, v => { v.data.capabilities.adopt = true; }, readCatalog);
    reject('catalog-missing-gap-reason', directory, v => { v.data.candidates[0].metrics.makespan_hours = { value: null, reason: null }; }, readCatalog);
    reject('catalog-has-more-lie', directory, v => { v.data.page.has_more = true; }, readCatalog);
    const memory = new Map(), storage = { getItem: k => memory.has(k) ? memory.get(k) : null, setItem: (k, v) => memory.set(k, v), removeItem: k => memory.delete(k) };
    const pending = A.pending(storage), saved = pending.begin('a'.repeat(32));
    try { pending.begin('b'.repeat(32)); failures.push('pending-overwrite'); } catch (_) { passed.push('pending-overwrite'); }
    const attached = pending.attach(saved, 'c'.repeat(48)); pending.attach(saved, 'c'.repeat(48));
    if (attached.request_key === saved.request_key && Object.keys(attached).length === 3) passed.push('idempotent-attach-minimal-original-key'); else failures.push('idempotent-attach-minimal-original-key');
    memory.set(A.PENDING_KEY, JSON.stringify({ ...attached, facts_json: '{}' }));
    try { pending.read(); failures.push('pending-private-field'); } catch (_) { passed.push('pending-private-field'); }
    if (!A.isRejected({ rejected: true })) passed.push('adapter-cannot-forge-definite-rejection'); else failures.push('adapter-cannot-forge-definite-rejection');
    const requests = [];
    const fake = A.create(async (url, options) => { requests.push({ url, options }); return new Response(JSON.stringify(fixtureAcceptance), { status: 200, headers: { 'Content-Type': 'application/json' } }); });
    try { await fake.accept(saved, null); failures.push('old-null-token-posted'); } catch (_) { if (!requests.length) passed.push('old-null-token-never-posted'); else failures.push('old-null-token-posted'); }
    try { await fake.accept(saved, 'z'.repeat(32)); failures.push('wrong-accept-status'); } catch (_) { passed.push('wrong-accept-status'); }
    const body = JSON.parse(requests[0].options.body);
    if (Object.keys(body).sort().join() === 'input_ref,request_key,write_token' && !requests[0].url.includes(saved.input_ref)) passed.push('strict-post-identity-not-url'); else failures.push('strict-post-identity-not-url');
    return { passed, failures };
  });
  assert.deepEqual(result.failures, []); result.passed.forEach(caseDone);
}
async function variants() {
  assert(await startButton().isDisabled()); caseDone('missing-input-disabled');
  await reset(); await control('disable'); await startButton().click();
  await page.getByText('本机排产执行器尚未接入或启用，暂时不能开始排产。', { exact: true }).first().waitFor();
  assert(await startButton().isDisabled()); assert.equal(await page.getByRole('dialog').count(), 0); await shot('dispatcher-disabled'); caseDone('dispatcher-disabled-with-reason');
  await reset(); await control('missing_schema'); await startButton().click();
  await page.getByRole('alert').waitFor(); assert((await page.getByRole('alert').innerText()).includes('v26')); assert(await startButton().isDisabled()); await shot('v26-disabled'); caseDone('v26-disabled-with-reason');
  await reset(); const first = await accepted();
  assert(await startButton().isDisabled()); assert.equal((await control('release')).calls.length, 1);
  caseDone('old-preflight-null-token-independent-preview-and-double-click-once');
  await control('start', { run_ref: first.run_ref }); await refresh(); await state('running', 'computing').waitFor(); await shot('computing');
  const delays = await page.evaluate(() => Array.from({ length: 6 }, (_, i) => RunJobAPI.pollDelay(i)));
  assert.deepEqual(delays, [2000, 4000, 8000, 16000, 30000, 30000]); caseDone('bounded-exponential-backoff');
  await page.evaluate(() => { window.fixtureHidden = true; Object.defineProperty(document, 'hidden', { configurable: true, get: () => window.fixtureHidden }); document.dispatchEvent(new Event('visibilitychange')); });
  report.injected.push({ variant, kind: 'document-hidden-visibilitychange' });
  const count = report.requests.filter(r => r.path.includes('/runs/') || r.path.includes('/requests/')).length;
  await new Promise(resolve => setTimeout(resolve, 2400));
  assert.equal(report.requests.filter(r => r.path.includes('/runs/') || r.path.includes('/requests/')).length, count);
  await control('release');
  await page.evaluate(() => { window.fixtureHidden = false; document.dispatchEvent(new Event('visibilitychange')); });
  await state('complete').waitFor(); caseDone('visibility-pauses-and-resumes-same-run');
  await page.locator('[data-candidate-ref]').first().waitFor();
  assert.equal(await page.locator('[data-candidate-ref]').count(), 4);
  assert.equal(await page.getByRole('button', { name: /查看正式计划/ }).count(), 0);
  assert.equal(await page.locator('[data-candidate-ref] button:not(:disabled)').count(), 0);
  assert.equal(await page.locator('progress,[role="progressbar"]').count(), 0); await layout(); await shot('complete'); caseDone('real-persisted-candidates-no-fake-plans-or-percent');
  await contracts();
  const terminalLookup = '**/scheduling/requests/' + first.request_key;
  await page.route(terminalLookup, route => route.fulfill({ status: 500, contentType: 'text/html', body: '<h1>Unavailable</h1>' }));
  await refresh(); await page.getByRole('alert').waitFor(); assert(await startButton().isDisabled());
  await page.getByText('以下为上次已核实结果，本次查询尚未确认。', { exact: true }).waitFor();
  await page.unroute(terminalLookup); await refresh(); await page.getByText('以下为上次已核实结果，本次查询尚未确认。', { exact: true }).waitFor({ state: 'hidden' }); caseDone('old-terminal-recheck-failure-blocks-new-run');
  await page.evaluate(() => window.mountRun(window.currentPreflight, { ...RunJobAPI.create(), openCandidate: value => { window.candidateLink = value; } }));
  await page.locator('[data-candidate-ref] button:not(:disabled)').first().waitFor();
  await page.locator('[data-candidate-ref] button').first().click();
  const link = await page.evaluate(() => window.candidateLink);
  assert.deepEqual(Object.keys(link).sort(), ['candidate_ref', 'run_ref']); assert.equal(link.run_ref, first.run_ref); caseDone('explicit-candidate-handler-only-permanent-identities');
  await control('restart'); await page.reload(); await state('complete').waitFor(); assert.equal((await local()).run_ref, first.run_ref); caseDone('reload-after-token-registry-reset-keeps-record');
  await button('返回排产检查').click(); assert.deepEqual(await page.evaluate(() => window.navigation), ['run']);
  await page.evaluate(() => window.mountRun({ input_ref: 'z'.repeat(32) })); await state('complete').waitFor();
  assert.equal((await local()).request_key, first.request_key); caseDone('navigate-back-and-unrelated-input-keep-original-record');
  await reset('partial'); const partial = await accepted(); await control('start', { run_ref: partial.run_ref }); await control('release'); await refresh();
  await state('partial').waitFor(); await page.locator('[data-candidate-ref]').first().waitFor(); assert.equal(await page.locator('[data-candidate-ref]').count(), 4);
  assert.equal(await page.locator('[data-candidate-ref] td:nth-child(2)').filter({ hasText: '部分完成' }).count(), 4);
  await shot('partial'); caseDone('real-excluded-batch-partial');
  await reset('failed'); const failed = await accepted(); await control('start', { run_ref: failed.run_ref }); await control('release'); await refresh();
  await state('failed').waitFor(); assert.equal(await page.locator('[data-candidate-ref]').count(), 0); await shot('failed'); caseDone('real-zero-duration-failure');
  await reset(); const interrupted = await accepted(); await control('reconcile_unknown', { run_ref: interrupted.run_ref }); await refresh();
  await state('running', 'awaiting_reconciliation').waitFor(); assert(await startButton().isDisabled()); caseDone('unknown-executor-not-timeout-failure');
  await control('interrupt'); await refresh(); await state('interrupted').waitFor(); await shot('interrupted'); caseDone('confirmed-interruption');
  await reset();
  const acceptPattern = '**/api/workbench/v1/scheduling/runs';
  await page.route(acceptPattern, async route => { const response = await route.fetch(); assert.equal(response.status(), 202); await route.abort('failed'); });
  report.injected.push({ variant, kind: 'lost-202-after-real-admission' });
  await confirm(); await state('queued').waitFor(); const lost = await local();
  assert.equal((await control('release')).calls.length, 1); await page.unroute(acceptPattern);
  await page.reload(); await state('queued').waitFor(); assert.equal((await local()).request_key, lost.request_key);
  await control('start', { run_ref: lost.run_ref }); await control('release'); await refresh(); await state('complete').waitFor();
  assert.equal((await control('release')).calls.length, 1); caseDone('lost-response-recovers-same-request-without-post');
  await reset();
  await page.route(acceptPattern, route => route.abort('failed')); report.injected.push({ variant, kind: 'disconnected-before-admission' });
  await confirm(); await page.getByText(/暂未查到原请求记录/).waitFor(); const unknown = await local(); assert.equal(unknown.run_ref, null);
  await page.unroute(acceptPattern); await page.reload(); await page.getByText(/暂未查到原请求记录/).waitFor();
  assert(await startButton().isDisabled()); assert.equal((await local()).request_key, unknown.request_key); assert.equal((await control('release')).calls.length, 0);
  const lookupPattern = '**/scheduling/requests/*';
  await page.route(lookupPattern, route => route.fulfill({ status: 404, contentType: 'text/html', body: '<h1>Missing</h1>' }));
  await refresh(); await page.getByRole('alert').waitFor(); assert.equal((await local()).request_key, unknown.request_key);
  await page.unroute(lookupPattern); caseDone('not-found-and-404-never-clear-or-repost'); await shot('unknown');
  await page.evaluate(() => { window.unmountRun(); localStorage.setItem(RunJobAPI.PENDING_KEY, JSON.stringify({ request_key: 'system-' + 'a'.repeat(48), input_ref: 'a'.repeat(32), run_ref: null })); window.mountRun(window.currentPreflight); });
  await page.getByRole('alert').waitFor(); assert(await startButton().isDisabled()); caseDone('cross-domain-intent-rejected');
  await page.evaluate(() => { window.unmountRun(); localStorage.setItem(RunJobAPI.PENDING_KEY, '{broken'); window.mountRun(window.currentPreflight); });
  await page.getByRole('alert').waitFor(); assert(await startButton().isDisabled()); assert.equal(await page.evaluate(() => localStorage.getItem(RunJobAPI.PENDING_KEY)), '{broken'); caseDone('corrupt-storage-preserved');
  await reset();
  await page.evaluate(() => { window.unmountRun(); window.mountRun(currentPreflight, { preview: async () => ({ ok: true, data: { facts_json: 'private' } }) }); });
  await startButton().click(); await page.getByRole('alert').waitFor(); assert.equal(await local(), null); assert.equal(await page.getByRole('dialog').count(), 0); caseDone('adapter-cannot-bypass-public-schema');
  await reset(); await startButton().click(); await page.getByRole('dialog').waitFor(); await control('restart');
  await button('确认开始排产').click(); await page.getByText('检查后资料已变化或检查已过期，请重新做排产检查。', { exact: true }).waitFor();
  assert.equal(await local(), null); assert.equal((await control('release')).calls.length, 0); caseDone('definite-stale-rejection-without-automatic-retry');
  await reset(); await startButton().click(); await page.getByRole('dialog').waitFor();
  await page.evaluate(() => { window.fixtureStorageSet = Storage.prototype.setItem; Storage.prototype.setItem = function(k, v) { if (k === RunJobAPI.PENDING_KEY) throw new DOMException('quota', 'QuotaExceededError'); return window.fixtureStorageSet.call(this, k, v); }; });
  await button('确认开始排产').click(); await page.getByRole('alert').waitFor();
  assert((await page.getByRole('alert').innerText()).includes('本机无法保存原请求记录')); assert.equal((await control('release')).calls.length, 0);
  await page.evaluate(() => { Storage.prototype.setItem = window.fixtureStorageSet; }); await button('重新读取恢复记录').click();
  await page.getByRole('alert').waitFor({ state: 'hidden' }); assert.equal(await local(), null); caseDone('storage-quota-no-post-friendly-retry');
  await layout();
}
async function capacity() {
  variant = 'capacity'; await reset('capacity'); const intent = await accepted(); await control('start', { run_ref: intent.run_ref });
  await refresh(); await state('running').waitFor(); await control('release');
  await state('complete').waitFor({ timeout: 300000 });
  await page.locator('[data-candidate-ref]').first().waitFor();
  const result = await page.request.get(origin + '/api/workbench/v1/scheduling/runs/' + intent.run_ref), data = (await result.json()).data;
  assert.equal(data.candidates.length, 4); assert(data.candidates.every(row => row.task_count === 5000));
  report.capacity = { task_count: 5000, candidate_rows: await page.locator('[data-candidate-ref]').count(),
    dom_nodes: await page.locator('[data-run-job-panel] *').count(), run_ref: intent.run_ref, real_compute: true };
  assert.equal(report.capacity.candidate_rows, 4); assert(report.capacity.dom_nodes < 160); await shot('5000-tasks');
  await page.setViewportSize({ width: 390, height: 844 }); await layout(); await shot('mobile');
  await page.reload(); await state('complete').waitFor(); assert.equal((await local()).run_ref, intent.run_ref); caseDone('5000-real-tasks-bounded-dom-mobile-reload');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.')); origin = 'http://127.0.0.1:' + server.address().port;
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      variant = width + '-' + theme; const row = { variant, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height: 1000 } });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(20000);
      page.on('pageerror', error => report.errors.push(error.message)); page.on('dialog', dialog => { report.dialogs.push(dialog.type()); dialog.dismiss(); });
      page.on('request', request => { if (request.url().includes('/api/')) report.requests.push({ method: request.method(), path: new URL(request.url()).pathname, at: Date.now() }); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin);
      try { await variants(); row.passed = true; if (width === 1392 && theme === 'dark') await capacity(); }
      catch (error) { row.error = error.stack; await shot('FAILED'); throw error; }
      finally { await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []);
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'run-job-widgets.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({ output, variants: report.variants.length, cases: report.cases.length, capacity: report.capacity }));
})().catch(error => { console.error(error); process.exitCode = 1; });
