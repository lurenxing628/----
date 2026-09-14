/* DB source probe. Real main + all registered components, actual Flask/SQLite. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assetRows = new Map(manifest.files.map(row => [row.path, row]));
const additions = ['TrialAdoptionHistoryAPI.js', 'TrialAdoptionHistoryState.js', 'TrialAdoptionHistoryStyles.jsx', 'TrialAdoptionHistory.jsx'];
const pointDependencies = ['PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx'];
const sourceNames = pointDependencies.map(name => 'frontend/workbench/app/' + name);
for (const file of manifest.scripts.filter(name => name.startsWith('workbench/app/'))) {
  const row = assetRows.get(file);
  assert.equal(row.source_files.length, 1, file);
  const name = row.source_files[0].path;
  if (name.endsWith('/TrialResults.jsx')) additions.forEach(n => sourceNames.push('frontend/workbench/app/' + n));
  if (![...additions, ...pointDependencies].some(n => name.endsWith('/' + n))) sourceNames.push(name);
}
assert(sourceNames.includes('frontend/workbench/app/main.jsx'));
assert.equal(new Set(sourceNames).size, sourceNames.length, 'Each current application source must load once');
assert.equal(sourceNames.filter(name => name.endsWith('/main.jsx')).length, 1, 'The history fixture must execute one current main');
const styleSources = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json'), 'utf8')).styles.map(name => {
  const file = 'frontend/workbench/app/styles/' + name; return { path: file, code: fs.readFileSync(path.join(root, file), 'utf8') };
});
const workspaceCSS = styleSources.map(row => row.code).join('\n');
const sources = sourceNames.map(name => ({ path: name, code: fs.readFileSync(path.join(root, name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, i) => ['/source/' + i + '.js', row.code]));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const foundation = manifest.scripts.filter(file => !file.startsWith('workbench/app/'));
const boot = JSON.parse(fs.readFileSync(path.join(output, 'boot-fixture.json'), 'utf8'));
const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div><script id="workbench-boot" type="application/json">' + JSON.stringify(boot) + '</script>' +
  foundation.map(file => '<script src="/static/' + file + '"></script>').join('') + [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') + '</body></html>';
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://fixture').pathname;
  if (pathname.startsWith('/api/') || pathname.startsWith('/fixture/')) {
    const upstream = http.request(backend + req.url, { method: req.method, headers: req.headers }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
    upstream.on('error', error => { if (!res.headersSent) res.writeHead(502); res.end(error.message); }); req.pipe(upstream); return;
  }
  if (pathname === '/' || pathname === '/trial') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html.replace('</head>', '<style>' + workspaceCSS + '</style></head>')); return; }
  if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
  const asset = assets.get(pathname); if (!asset) { res.writeHead(404); res.end(); return; } res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const report = { browser: null, variants: [], checks: [], screenshots: [], errors: [], external: [], geometry: [], boot,
  sources: sources.concat(styleSources).map(s => ({ path: s.path, sha256: crypto.createHash('sha256').update(s.code).digest('hex') })) };
let page, origin, refs, variant;
const button = name => page.getByRole('button', { name, exact: true });
const tab = name => page.getByRole('tab', { name, exact: true });
const done = name => report.checks.push({ variant, name });
const evidence = async () => (await page.request.get(origin + '/fixture/evidence')).json();
async function ready() {
  await page.locator('[data-trial-workspace][data-open-kind="scenario"][data-open-ref="' + refs.scenario_ref + '"] .tt-main').waitFor();
  await page.waitForFunction(() => {
    const reload = document.querySelector('[data-trial-workspace] [aria-label="刷新当前试调"]');
    return reload && !reload.disabled;
  });
}
async function historyReady() { await page.locator('.trial-adoption-history .tah-meta').filter({ hasText: '本试调方案共' }).waitFor(); }
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: false }); report.screenshots.push(file); }
async function layout() {
  await page.locator('.trial-adoption-history').scrollIntoViewIfNeeded();
  const shape = await page.locator('.trial-adoption-history').evaluate(n => {
    const controls = [...n.querySelectorAll('button,select,summary,p,dt,dd')].filter(x => x.getClientRects().length);
    const rgb = value => (value.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const luma = value => rgb(value).map(x => x / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4).reduce((s, x, i) => s + x * [.2126, .7152, .0722][i], 0);
    const background = x => { for (let p = x; p; p = p.parentElement) { const c = getComputedStyle(p).backgroundColor; if (!['transparent', 'rgba(0, 0, 0, 0)'].includes(c)) return c; } return 'rgb(255,255,255)'; };
    const ratios = controls.filter(x => !x.disabled).map(x => { const a = luma(getComputedStyle(x).color), b = luma(background(x)); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); });
    return { overflow: document.documentElement.scrollWidth > innerWidth, theme: document.documentElement.dataset.theme,
      clipped: controls.filter(x => x.scrollWidth > x.clientWidth + 2).map(x => x.tagName + ':' + x.textContent),
      minContrast: Math.min(...ratios), fontSize: getComputedStyle(n.querySelector('li')).fontSize };
  });
  assert(!shape.overflow, JSON.stringify(shape)); assert.deepEqual(shape.clipped, []); assert(shape.minContrast >= 4.5, JSON.stringify(shape));
  report.geometry.push({ variant, ...shape });
}
async function basic() {
  await ready(); await tab('调整记录').click(); await page.getByRole('table', { name: '调整记录', exact: true }).waitFor();
  await tab('采用记录').click(); await historyReady(); await page.getByText('这个试调方案还没有正式采用记录。', { exact: true }).waitFor(); done('original-adjustments-and-empty-history');
  await button('采用方案').click(); await page.getByLabel('采用原因', { exact: true }).fill('核对完整场景与现场记录，保留原基线和全部调整依据。');
  await page.getByLabel('经办人', { exact: true }).fill('计划员 张三'); await page.getByRole('checkbox', { name: /^我已核对试调方案/ }).check();
  await button('确认正式采用').click(); await page.getByRole('dialog', { name: '试调方案采用结果', exact: true }).waitFor();
  await button('完成').click(); await ready(); await button('刷新采用记录').click(); await historyReady();
  await page.locator('[data-adoption-receipt]').waitFor(); assert.equal(await page.locator('[data-adoption-receipt]').count(), 1);
  const receipt = (await evidence()).receipts[0], planRef = JSON.parse(receipt.outcome_json).data.official_plan.plan_ref;
  assert.equal(await page.locator('[data-adoption-receipt]').getAttribute('data-adoption-receipt'), receipt.receipt_ref);
  await page.evaluate(() => localStorage.clear()); await page.reload(); await ready(); await historyReady();
  await page.locator('.tah-current').waitFor(); done('real-adopt-clear-browser-receipt-reload-sqlite-history');
  await page.getByLabel('采用状态', { exact: true }).selectOption('current'); await historyReady();
  await page.getByLabel('采用记录每页', { exact: true }).selectOption('10'); await historyReady();
  await page.locator('.tah-list summary').click(); await layout(); await shot('current-history');
  await button('查看正式计划').click(); await page.locator('[data-plan-workspace] .plan-bar').first().waitFor();
  assert.equal(await page.evaluate(() => history.state.workbench.context.plan_ref), planRef);
  await page.goBack(); await ready(); await historyReady();
  assert.equal(await tab('采用记录').getAttribute('aria-selected'), 'true');
  assert.equal(await page.getByLabel('采用状态', { exact: true }).inputValue(), 'current');
  assert.equal(await page.getByLabel('采用记录每页', { exact: true }).inputValue(), '10'); done('actual-main-plan-navigation-back-filter-preserved');
  const advanced = await page.request.post(origin + '/fixture/control', { data: { action: 'advance' } }); assert.equal(advanced.status(), 200, await advanced.text());
  await page.reload(); await ready(); await page.locator('.trial-adoption-history [role=alert]').waitFor();
  assert.equal(await page.locator('.tah-current').count(), 0); done('stale-snapshot-hides-old-current-badge');
  await button('刷新采用记录').click(); await historyReady(); await page.getByText('当前筛选没有采用记录。', { exact: true }).waitFor();
  await page.getByLabel('采用状态', { exact: true }).selectOption('historical'); await historyReady();
  await page.locator('.tah-historical').waitFor(); await layout(); await shot('historical-after-current-change');
  assert.equal((await evidence()).receipts.length, 2);
  const replay = await page.request.post(origin + '/api/workbench/v1/trial/scenarios/' + refs.scenario_ref + '/adopt', { data: {
    write_token: 'expired', request_key: receipt.request_key, input: { confirm: true, reason: '核对完整场景与现场记录，保留原基线和全部调整依据。', declared_operator: '计划员 张三' } } });
  assert.equal(replay.status(), 200, await replay.text()); assert.equal((await replay.json()).receipt_ref, receipt.receipt_ref);
  await button('刷新采用记录').click(); await historyReady(); assert.equal(await page.locator('[data-adoption-receipt]').count(), 1);
  assert.equal((await evidence()).receipts.length, 2); done('same-key-replay-no-duplicate-history');
  await tab('调整记录').click(); await page.getByRole('table', { name: '调整记录', exact: true }).waitFor();
  await tab('调整记录').focus(); await page.keyboard.press('ArrowRight'); await historyReady(); assert.equal(await tab('采用记录').getAttribute('aria-selected'), 'true'); done('keyboard-tabs-adjustments-retained');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); origin = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true }); report.browser = browser.version();
  try {
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      variant = width + '-' + theme; const context = await browser.newContext({ viewport: { width, height: 1080 }, locale: 'zh-CN' }); page = await context.newPage();
      page.on('pageerror', error => report.errors.push({ variant, message: error.message }));
      page.on('request', request => { if (!request.url().startsWith(origin + '/')) report.external.push(request.url()); });
      const response = await page.request.post(origin + '/fixture/reset', { data: { mode: 'normal' } }); assert.equal(response.status(), 200, await response.text()); refs = await response.json();
      await context.addInitScript(({ theme, scenario }) => {
        localStorage.setItem('aps_kit_theme', theme);
        if (location.pathname === '/trial' && !(history.state && history.state.workbench)) history.replaceState({ workbench: { view: 'trial', context: { scenario_ref: scenario }, key: 0 } }, '', location.href);
      }, { theme, scenario: refs.scenario_ref });
      await page.goto(origin + '/trial'); await basic(); report.variants.push({ variant, passed: true }); await context.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } catch (error) {
    report.failure = error.stack;
    if (page && !page.isClosed()) {
      fs.writeFileSync(path.join(output, variant + '-failure.txt'), await page.locator('body').innerText());
      fs.writeFileSync(path.join(output, variant + '-failure.html'), await page.locator('body').innerHTML());
      await shot('failure');
    }
    throw error;
  }
  finally { fs.writeFileSync(path.join(output, 'history-widgets.json'), JSON.stringify(report, null, 2)); await browser.close(); await new Promise(resolve => server.close(resolve)); }
  console.log(JSON.stringify({ variants: report.variants.length, checks: report.checks.length, output }));
})().catch(error => { console.error(error); process.exitCode = 1; });
