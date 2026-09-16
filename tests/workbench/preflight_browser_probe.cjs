/* Real POST preflight and batch reads are proxied to an isolated Flask database. */
'use strict';
const UI = require('./run_ui_source.cjs');
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const files = UI.dependencies(['WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-api.js', 'ResourceControls.jsx', 'BatchContract.js', 'BatchAPI.js', 'CalendarContract.js',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js',
  'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx',
  'PreflightContract.js', 'PreflightAPI.js', 'PreflightControls.jsx', 'PreflightBatchPicker.jsx', 'PreflightWorkspace.jsx']);
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, index) => ['/fixture/' + files[index] + '.js', row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => [row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const report = { browser: null, variants: [], screenshots: [], errors: [], external: [], requests: [], injected: [],
  compile: { global_build: false, target: 'chrome109' }, sources: sources.map(row => ({ path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex') })) };
const mount = `let fixtureRoot; window.mountPreflight=context=>{if(fixtureRoot)fixtureRoot.unmount();fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));window.navigations=[];
fixtureRoot.render(React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),React.createElement(PreflightWorkspace,{initialContext:context,onNavigate:(...args)=>navigations.push(args)})));};`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  UI.styles(report, output) + '<style>body{margin:0}#fixture-root{margin:24px 32px 24px 264px;min-width:0}</style></head><body class="aps-workbench"><div id="fixture-root"></div>' + staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + mount + '</script></body></html>';
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://fixture').pathname;
  if (pathname.startsWith('/api/')) {
    const proxied = http.request(backend + req.url, { method: req.method, headers: req.headers }, upstream => { res.writeHead(upstream.statusCode, upstream.headers); upstream.pipe(res); });
    proxied.on('error', error => { res.writeHead(502); res.end(String(error)); }); req.pipe(proxied); return;
  }
  if (pathname === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
  const asset = assets.get(pathname.slice('/static/'.length));
  if (!pathname.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
let page, variant;
const button = name => UI.button(page, name);
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: true, animations: 'disabled' }); report.screenshots.push(file); }
async function mounted(context) { await page.evaluate(context => window.mountPreflight(context), context); await button('选择批次').click(); await page.getByRole('checkbox', { name: '选择 PF-0000', exact: true }).waitFor(); }
async function checked(name = '开始排产检查') {
  const awaiting = page.waitForResponse(response => response.url().endsWith('/scheduling/preflight'));
  await button(name).click(); const response = await awaiting, payload = await response.json();
  assert.equal(response.status(), 200); assert.equal(payload.meta.source, 'production');
  await page.getByText(/检查时间：/).waitFor(); return payload.data;
}
async function layout() {
  const result = await page.evaluate(() => {
    const node = document.querySelector('[data-preflight-workspace]'), style = getComputedStyle(node);
    const rects = selector => Array.from(document.querySelectorAll(selector), row => { const r = row.getBoundingClientRect(); return { y: r.y, height: r.height }; });
    return { overflow: document.documentElement.scrollWidth > innerWidth, padding: style.padding, maxWidth: style.maxWidth,
      ancestor: !!node.parentElement.closest('.plana'), left: rects('.pf-rule'), right: rects('.pf-check'),
      controls: Array.from(document.querySelectorAll('.pf-segment'), row => row.getBoundingClientRect().width),
      clipped: Array.from(node.querySelectorAll('.pf-rule strong,.pf-check strong,.pf-check p,.pf-segment span'))
        .filter(row => row.scrollWidth > row.clientWidth + 1 || row.scrollHeight > row.clientHeight + 1).map(row => row.textContent) };
  });
  assert.equal(result.overflow, false); assert.equal(result.padding, '0px'); assert.equal(result.maxWidth, 'none'); assert.equal(result.ancestor, false);
  assert(Math.abs(result.left[0].y - result.right[0].y) <= 1, JSON.stringify(result));
  // Independent rule and check columns can use different row heights; their content must remain readable.
  [result.left, result.right].forEach(rows => rows.forEach((row, i) => {
    if (i) assert(row.y >= rows[i - 1].y + rows[i - 1].height - 1, JSON.stringify(result));
  }));
  assert.deepEqual(result.clipped, []);
  assert.equal(new Set(result.controls).size, 1);
}
async function cases() {
  await mounted();
  assert((await page.locator('.pf-stepper [aria-current="step"]').innerText()).includes('选批次和日期'));
  assert((await page.locator('.pf-picker-row').first().innerText()).includes('交期：'));
  assert((await page.locator('.pf-picker-row').first().innerText()).includes('优先级：'));
  let data = await checked(); assert.equal(data.counts.selected_tasks, 0); assert.equal(data.eligible_tasks, 0);
  assert(await button('开始排产').isDisabled()); await button('收起范围').click(); await layout(); await shot('empty');
  await mounted();
  await page.getByRole('checkbox', { name: '选择 PF-0000', exact: true }).check(); await button('批次下一页').click();
  assert((await page.locator('.pf-stepper [aria-current="step"]').innerText()).includes('检查'));
  assert((await button('开始排产检查').getAttribute('class')).includes('primary'));
  await page.getByRole('checkbox', { name: '选择 PF-0020', exact: true }).check();
  assert((await page.locator('.pf-picker').innerText()).includes('非当前页 1 批'));
  await page.getByRole('radio', { name: '暂不排', exact: true }).check();
  await page.getByLabel('计划开始日期', { exact: true }).fill('2026-09-09'); await page.getByLabel('计划结束日期', { exact: true }).fill('2026-09-09');
  data = await checked(); assert.equal(data.counts.selected_batches, 2); assert.equal(data.counts.ready_tasks, 2);
  assert((await page.locator('.pf-stepper [aria-current="step"]').innerText()).includes('计算'));
  assert(!(await button('重新检查').getAttribute('class')).includes('primary'));
  assert.equal(data.normalized_input.missing_resource_policy, 'exclude'); assert.equal(data.calendar_check, 'not_evaluated');
  const ids = data.included_batches.map(row => row.batch_id).sort(); assert.deepEqual(ids, ['PF-0000', 'PF-0020']);
  await button('收起范围').click(); await layout(); await shot('checked');
  await page.getByText('检查明细 · 2 道', { exact: true }).click(); assert.equal(await page.getByRole('table', { name: '排产检查明细' }).locator('tbody tr').count(), 2);
  await page.getByRole('radio', { name: '关闭', exact: true }).check(); assert.equal(await page.getByText(/检查时间：/).count(), 0);
  await page.getByText('排产参数已变化，请重新检查后再开始计算。', { exact: true }).waitFor();
  await button('选择批次').click(); await page.getByRole('checkbox', { name: '选择 PF-0000', exact: true }).waitFor();
  await button('全选当前筛选').click(); await page.getByText(/已选 46 批/).first().waitFor();
  await page.getByLabel('批次每页条数', { exact: true }).press('Enter'); await page.getByRole('listbox').waitFor(); await shot('unified-dropdown'); await page.keyboard.press('Escape');
  await page.getByLabel('计划开始日期', { exact: true }).press('Enter'); await page.getByRole('dialog').waitFor(); await shot('unified-date'); await page.keyboard.press('Escape');
  await page.getByLabel('搜索排产批次', { exact: true }).fill('NO-SUCH-BATCH'); await button('搜索').click(); await page.getByText('当前筛选没有待排批次', { exact: true }).waitFor(); await shot('empty-filter');
  const pattern = '**/scheduling/preflight';
  await page.route(pattern, route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ ok: false, committed: false, error: { code: 'storage_failure', message: '测试注入：读取失败', fields: [] } }) }));
  report.injected.push({ variant, status: 500 }); await button('开始排产检查').click(); await page.getByText('测试注入：读取失败', { exact: true }).waitFor(); await shot('read-error'); await page.unroute(pattern);
  await page.evaluate(() => window.mountPreflight({ snapshot_ref: 'expired-context' })); await page.getByRole('alert').waitFor(); assert.equal(await page.locator('.pf-picker-row').count(), 0); await shot('invalid-context');
  await button('重新选择范围').click(); await button('选择批次').click(); await page.getByRole('checkbox', { name: '选择 PF-0000', exact: true }).waitFor();
  const huge = Array.from({ length: 5000 }, (_, i) => i.toString(16).padStart(48, '0'));
  await mounted({ batch_refs: huge }); assert.equal(await page.locator('.pf-picker-row').count(), 20); assert((await page.locator('.pf-window').innerText()).includes('已选 5000 批'));
  const waiting = page.waitForResponse(response => response.url().endsWith('/scheduling/preflight'));
  await button('开始排产检查').click(); const failed = await waiting; assert.equal(failed.status(), 404); await page.getByRole('alert').waitFor(); await shot('huge-invalid-refs');
  const request = failed.request(); assert(request.url().length < 150); assert.equal(request.postDataJSON().batch_refs.length, 5000);
  await page.evaluate(refs => window.mountPreflight({ batch_refs: refs }), huge.concat('f'.repeat(48)));
  await page.getByRole('alert').waitFor(); assert.equal(await page.locator('.pf-picker-row').count(), 0);
  const batchPattern = '**/entities/batch/query';
  await page.route(batchPattern, async route => {
    const original = await route.fetch(), value = await original.json(); value.data.entities[0].fields.due_date = '2026-02-30';
    await route.fulfill({ response: original, json: value });
  });
  report.injected.push({ variant, case: 'legacy-invalid-due-date-preserved-as-text' });
  await mounted(); await page.getByText('交期原值待核对', { exact: false }).waitFor();
  await UI.reference(page.locator('.pf-picker-row').first(), '2026-02-30');
  assert.equal(await page.locator('.pf-picker-row').count(), 20); await page.unroute(batchPattern);
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.')); const origin = 'http://127.0.0.1:' + server.address().port;
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      variant = width + '-' + theme; const row = { variant, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height: 1000 } });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(12000);
      page.on('pageerror', error => report.errors.push(error.message));
      page.on('request', request => { if (request.url().includes('/api/')) report.requests.push({ method: request.method(), url: request.url() }); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin); try { await cases(); row.passed = true; } catch (error) { row.error = error.stack; await shot('FAILED'); throw error; } finally { await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
    assert(report.requests.every(row => row.url.includes('/scheduling/preflight') || row.url.includes('/entities/batch/')));
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'preflight-browser.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({ output, variants: report.variants.length, screenshots: report.screenshots.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
