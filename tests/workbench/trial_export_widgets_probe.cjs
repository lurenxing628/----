/* CZ source-only harness. No production DB, existing preview, shared port, or built app. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchGuards.js', 'WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'WorkbenchControlStyles.jsx', 'WorkbenchControlBridge.js', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchNumberControls.jsx',  'PointContract.js', 'PointGantt.jsx', 'TrialContract.js', 'TrialAPI.js', 'TrialSession.js',
  ...(fs.existsSync(path.join(root, 'frontend/workbench/app/TrialExport.js')) ? ['TrialExport.js'] : []),
  'TrialControls.jsx', 'TrialViewState.js', 'TrialCatalog.jsx', 'TrialGantt.jsx', 'TrialDetails.jsx', 'TrialResults.jsx', 'TrialStyles.jsx', 'TrialWorkspace.jsx'];
const styleSources = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json'), 'utf8')).styles.map(name => {
  const file = 'frontend/workbench/app/styles/' + name; return { path: file, code: fs.readFileSync(path.join(root, file), 'utf8') };
});
const workspaceCSS = styleSources.map(row => row.code).join('\n');
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, i) => ['/source/' + files[i], row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const foundation = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>body{margin:0}#fixture-root{margin-left:208px;padding:16px 24px;min-height:100vh}</style>' +
  '</head><body class="aps-workbench"><div id="fixture-root"></div>' + foundation.map(file => '<script src="/static/' + file + '"></script>').join('') +
  [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') +
  '<script>let root;window.mountTrial=target=>{if(root)root.unmount();root=ReactDOM.createRoot(document.getElementById("fixture-root"));root.render(React.createElement(React.Fragment,null,React.createElement(WorkbenchGuardHost),React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchTrialWorkspace,{initialTarget:target})));};window.mountExport=data=>{root.render(React.createElement(TrialControls.Download,{data}));};</script></body></html>';
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://fixture').pathname;
  if (pathname.startsWith('/api/') || pathname.startsWith('/fixture/')) {
    if (req.method !== 'GET') { res.writeHead(405); res.end('CZ exports are read-only'); return; }
    const upstream = http.request(backend + req.url, { method: req.method, headers: req.headers }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
    upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('CZ isolated fixture unavailable'); }); req.pipe(upstream); return;
  }
  if (pathname === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html.replace('</head>', '<style>' + workspaceCSS + '</style></head>')); return; }
  if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
  const asset = assets.get(pathname); if (!asset) { res.writeHead(404); res.end(); return; } res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const report = { browser: null, variants: [], downloads: [], boundary_checks: [], errors: [], external: [], screenshots: [],
  sources: sources.concat(styleSources).map(s => ({ path: s.path, sha256: crypto.createHash('sha256').update(s.code).digest('hex') })) };
let page, origin, variant;
const button = name => page.getByRole('button', { name, exact: true });
const proof = async () => (await page.request.get(origin + '/fixture/export-proof')).json();
async function shot(name) {
  const file = path.join(output, variant + '-' + name + '.png');
  await page.screenshot({ path: file, fullPage: true, animations: 'disabled' }); report.screenshots.push(file);
}
async function download(name, entry, data) {
  const before = await proof(), requests = [];
  const listener = request => requests.push(request.url()); page.on('request', listener);
  let item;
  try {
    const pending = page.waitForEvent('download'); await button(name).click(); const file = await pending;
    const filename = file.suggestedFilename(), dest = path.join(output, variant + '-' + entry + '-' + filename);
    await file.saveAs(dest); item = { variant, entry, filename, path: dest, button: name };
    report.downloads.push(item);
  } finally { page.off('request', listener); }
  assert.deepEqual(requests, [], 'Download must not fetch, re-evaluate, or write');
  const after = await proof(); assert.deepEqual(after, before); item.database_unchanged = true;
  if (name === '导出对比') {
    assert(item.filename.endsWith('.csv'), 'FIRST ORIGINAL FAILURE: comparison button downloads JSON, not prototype CSV');
    const bytes = fs.readFileSync(item.path); assert.deepEqual([...bytes.subarray(0, 3)], [239, 187, 191]);
    assert(bytes.toString('utf8').includes('批次')); assert(!bytes.toString('utf8').includes('write_token'));
    assert.equal(await page.evaluate(() => czBlobs[czBlobs.length - 1].type), 'text/csv;charset=utf-8');
  } else {
    assert(item.filename.endsWith('.json')); assert.deepEqual(JSON.parse(fs.readFileSync(item.path, 'utf8')), data);
    assert.equal(await page.evaluate(() => czBlobs[czBlobs.length - 1].type), 'application/json;charset=utf-8');
  }
}
async function realDTO(entry) {
  const key = Object.keys(entry.target)[0], kind = key === 'scenario_ref' ? 'scenarios' : 'drafts';
  const response = await page.request.get(origin + '/api/workbench/v1/trial/' + kind + '/' + entry.target[key]);
  assert.equal(response.status(), 200); const envelope = await response.json();
  assert.equal(envelope.meta.source, 'production');
  await page.evaluate(target => mountTrial(target), entry.target); await button('导出对比').waitFor();
  await page.getByRole('tab', { name: '批次对比', exact: true }).waitFor();
  const data = JSON.parse(JSON.stringify(envelope.data, (key, value) => key === 'write_context' ? undefined : value));
  const dto = path.join(output, variant + '-' + entry.name + '-dto.json'); fs.writeFileSync(dto, JSON.stringify(data, null, 2));
  if (['saved-plan', 'editing-plan'].includes(entry.name)) {
    assert.equal(data.task_count, 72); assert.equal(data.comparison.batches.length, 24);
    assert.equal(await page.getByRole('table', { name: '批次交付对比' }).locator('tbody tr').count(), 20);
    assert.equal(await page.locator('.tt-bar').count(), 0, 'Original display query hides tasks, not full DTO');
  }
  await download('导出对比', entry.name, data);
  report.downloads[report.downloads.length - 1].dto = dto;
  await download('导出原始数据', entry.name, data);
  if (entry.name === 'saved-plan') {
    assert(data.change_history.some(change => change.before.machine_ref !== change.after.machine_ref && change.before.operator_ref !== change.after.operator_ref));
    await page.getByRole('tab', { name: '完整任务', exact: true }).click();
    assert.equal(await page.getByRole('table', { name: '完整任务明细' }).locator('tbody tr').count(), 50);
    await page.getByRole('button', { name: '完整任务明细下一页', exact: true }).click();
    assert.equal(await page.getByRole('table', { name: '完整任务明细' }).locator('tbody tr').count(), 22);
    await download('导出对比', entry.name + '-last-page', data); report.downloads[report.downloads.length - 1].dto = dto;
    const two = report.downloads.filter(row => row.dto === dto);
    assert.deepEqual(fs.readFileSync(two[0].path), fs.readFileSync(two[1].path), 'Pagination must not affect export');
    await shot(entry.name);
  }
  const geometry = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
    buttons: [...document.querySelectorAll('button')].filter(b => /^(导出对比|导出原始数据)$/.test(b.textContent)).map(b => {
      const r = b.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, overflow: b.scrollWidth > b.clientWidth + 1 };
    }) }));
  assert(geometry.scroll <= geometry.width + 1); assert.equal(geometry.buttons.length, 2);
  assert(geometry.buttons.every(b => b.left >= 0 && b.right <= geometry.width && !b.overflow));
  if (entry.name === 'saved-plan' && variant === '1920-light') await boundaries(data);
}
async function boundaries(real) {
  // Deliberately synthetic values test serialization only; they are never attributed to service calculations.
  const data = structuredClone(real), vectors = ['=1+1', '+SUM(1,2)', '-2+3', '@SUM(1,2)', '\t=1', '\r=1', '\n=1', ' \t=1', '\uFEFF=1', '\u0001=1',
    '\u200b@SUM(1)', '＝1', '＋1', '－1', '＠1', "'已有单引号", '0000123', '123456789012345678901234567890', '合金,零件', '合金"零件', '合金\r\n零件', '\t普通文本', '空字符串之后', ''];
  data.name = '=方案,"中文"\r\n换行'; data.comparison.changeovers = 0;
  data.comparison.batches.forEach((batch, i) => {
    batch.batch_id = vectors[i]; batch.part_name = i === 22 ? null : vectors[(i + 1) % vectors.length];
    batch.quantity = i % 3 === 0 ? null : i % 3 === 1 ? 0 : 123456;
    batch.priority = i === 0 ? 'future_priority' : batch.priority;
    batch.risk = ['on_time', 'overdue', 'unavailable', 'invalid_data'][i % 4];
    batch.late_hours = [0, 1.25, null, null][i % 4]; batch.improvement_hours = [-1.25, 0, 1 / 3][i % 3];
  });
  await page.evaluate(data => { window.czSynthetic = data; mountExport(data); }, data);
  const dto = path.join(output, 'synthetic-boundaries-dto.json'); fs.writeFileSync(dto, JSON.stringify(data, null, 2));
  await download('导出对比', 'synthetic-boundaries', data); report.downloads[report.downloads.length - 1].dto = dto;
  await download('导出原始数据', 'synthetic-boundaries', data);
  const checks = await page.evaluate(() => {
    const before = JSON.stringify(czSynthetic), result = [];
    const verify = (name, patch) => {
      const value = structuredClone(czSynthetic); patch(value);
      let rejected = false; try { TrialExport.csv(value); } catch (_) { rejected = true; }
      result.push({ name, passed: rejected });
    };
    verify('incomplete-tasks-rejected', d => { d.tasks.pop(); });
    verify('wrong-task-count-rejected', d => { d.task_count++; });
    verify('incomplete-batches-rejected', d => { d.comparison.batches.pop(); });
    verify('duplicate-batches-rejected', d => { d.comparison.batches[0] = d.comparison.batches[1]; });
    verify('false-resource-change-rejected', d => { d.comparison.batches[0].moved = !d.comparison.batches[0].moved; });
    verify('non-finite-number-rejected', d => { d.comparison.batches[0].quantity = Infinity; });
    verify('nul-text-not-silently-replaced', d => { d.name = 'NUL\u0000value'; });
    const credentials = structuredClone(czSynthetic); credentials.tasks[0].execution.write_context = { write_token: 'CZ-fake-secret' };
    result.push({ name: 'nested-write-context-excluded-from-raw', passed: !TrialExport.raw(credentials).text.includes('CZ-fake-secret') });
    TrialExport.csv(czSynthetic); TrialExport.raw(czSynthetic);
    result.push({ name: 'dto-not-mutated', passed: JSON.stringify(czSynthetic) === before });
    return result;
  });
  checks.forEach(check => assert(check.passed, check.name)); report.boundary_checks.push(...checks);
  const downloads = [];
  const listener = file => downloads.push(file.suggestedFilename()); page.on('download', listener);
  await page.evaluate(() => { const d = structuredClone(czSynthetic); d.comparison.batches.pop(); mountExport(d); });
  await button('导出对比').click(); await page.getByRole('alert').getByText('批次对比不完整，无法导出。', { exact: true }).waitFor();
  assert.deepEqual(downloads, []);
  await page.evaluate(() => { window.czClick = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { throw Error('CZ simulated anchor failure'); }; mountExport(czSynthetic); });
  try { await button('导出对比').click(); await page.getByText('CZ simulated anchor failure', { exact: true }).waitFor(); }
  finally { await page.evaluate(() => { HTMLAnchorElement.prototype.click = czClick; }); }
  await page.waitForFunction(() => czBlobs.every(row => row.revoked));
  assert.equal(await page.locator('a[href^="blob:"]').count(), 0); assert.deepEqual(downloads, []); page.off('download', listener);
  report.boundary_checks.push({ name: 'visible-failure-no-download-and-url-anchor-cleanup', passed: true });
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.')); origin = 'http://127.0.0.1:' + server.address().port;
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      variant = width + '-' + theme; const row = { variant, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height: width === 1920 ? 1080 : 924 }, timezoneId: 'America/New_York', acceptDownloads: true });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      await context.addInitScript(() => {
        window.czBlobs = []; const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
        URL.createObjectURL = blob => { const url = create(blob); czBlobs.push({ url, type: blob.type, revoked: false }); return url; };
        URL.revokeObjectURL = url => { czBlobs.filter(row => row.url === url).forEach(row => { row.revoked = true; }); return revoke(url); };
      });
      page = await context.newPage(); page.setDefaultTimeout(15000);
      page.on('pageerror', error => report.errors.push(error.message));
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      try {
        await page.goto(origin); const entries = await (await page.request.get(origin + '/fixture/export-targets')).json();
        for (const entry of entries) await realDTO(entry);
        row.passed = true;
      } catch (error) { row.error = error.stack; await shot('FIRST-FAILURE'); throw error; }
      finally { await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
    console.log(JSON.stringify({ browser: report.browser, downloads: report.downloads.length, variants: report.variants.length, output }));
  } finally { if (browser) await browser.close(); server.close(); fs.writeFileSync(path.join(output, 'trial-export-widgets.json'), JSON.stringify(report, null, 2)); }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
