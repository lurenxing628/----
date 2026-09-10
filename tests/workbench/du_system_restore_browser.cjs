/* Real disposable entrypoint through an asset-only source overlay; no global build. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const options = JSON.parse(fs.readFileSync(0, 'utf8')), root = path.resolve(__dirname, '../..');
const names = ['WorkbenchPageContext.jsx', 'SystemMaintenanceAPI.js', 'SystemRestoreStatus.js', 'SystemMaintenanceControls.jsx', 'SystemRestorePanel.jsx',
  'SystemMaintenanceRecords.jsx', 'SystemMaintenanceConfig.jsx', 'SystemMaintenanceWorkspace.jsx', 'SystemLive.jsx'];
const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const sources = names.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype', order.babel.path), check_combined: true, sources }).outputs;
const assets = new Map(compiled.map(file => ['/__du/' + file.path, file.code]));
const report = { mode: options.mode, theme: options.theme, viewport: options.viewport, requests: [], errors: [], external: [], screenshots: [] };
report.source_sha256 = Object.fromEntries(sources.map(file => [file.path, crypto.createHash('sha256').update(file.code).digest('hex')]));
report.asset_overlay = options.overlay !== false;
report.build_id = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'))).build_id;
let stopped = options.mode === 'cold', dropped = false;
function hashes() {
  const paths = [options.database].concat([options.backups, options.journal].flatMap(directory => fs.readdirSync(directory).filter(name => /\.(db|json)$/.test(name)).map(name => path.join(directory, name))));
  return Object.fromEntries(paths.filter(file => fs.existsSync(file)).sort().map(file => [file, crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
}
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (assets.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(assets.get(url.pathname)); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  const chunks = []; for await (const chunk of request) chunks.push(chunk);
  const body = Buffer.concat(chunks);
  const observed = { path: request.url, method: request.method, after_restore: stopped };
  if (body.length) observed.request_key = JSON.parse(body).request_key;
  report.requests.push(observed);
  const upstream = http.request({ host: '127.0.0.1', port: options.port, path: request.url, method: request.method,
    headers: { ...request.headers, host: '127.0.0.1:' + options.port } }, incoming => {
    const data = []; incoming.on('data', chunk => data.push(chunk)); incoming.on('end', () => {
      let payload = Buffer.concat(data), headers = { ...incoming.headers };
      observed.status = incoming.statusCode;
      if (request.method === 'POST' && url.pathname.endsWith('/backups/restore')) {
        stopped = true;
        const result = JSON.parse(payload); report.operation = result.data && result.data.operation;
        report.after_restore_hashes = hashes();
      }
      if (options.overlay !== false && incoming.statusCode === 200 && String(headers['content-type']).startsWith('text/html') && url.pathname === '/workbench') {
        let html = payload.toString('utf8');
        html = html.replace(/<script src="([^"]+)"><\/script>/g, (tag, src) => names.some(name => src.split('?')[0].endsWith('/' + name.replace(/jsx$/, 'js'))) ? '' : tag);
        html = html.replace(/(<script src="[^"]*\/main\.js[^"]*"><\/script>)/,
          compiled.map(file => '<script src="/__du/' + file.path + '"></script>').join('') + '$1');
        payload = Buffer.from(html);
      }
      delete headers['content-length']; response.writeHead(incoming.statusCode, headers); response.end(payload);
    });
  });
  upstream.on('error', error => { response.statusCode = 502; response.end(String(error)); }); upstream.end(body);
});
async function screenshot(page, name) {
  const file = path.join(options.output, name + '.png'); await page.screenshot({ path: file, fullPage: true }); report.screenshots.push(file);
}
async function geometry(page) {
  return page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, width: innerWidth,
    theme: document.documentElement.dataset.theme,
    fields: [...document.querySelectorAll('button,input[type=text],input:not([type])')].filter(node => node.getClientRects().length && !node.closest('[inert]')).map(node => {
      const box = node.getBoundingClientRect(); return { width: box.width, height: box.height, left: box.left, right: box.right, text: node.textContent }; }) }));
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    const context = await browser.newContext({ viewport: options.viewport, acceptDownloads: true });
    await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, options.theme);
    const page = await context.newPage(), origin = 'http://127.0.0.1:' + server.address().port;
    page.on('pageerror', error => report.errors.push(error.message));
    await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
    if (options.drop) await page.route('**/api/workbench/v1/system/backups/restore', async route => {
      assert.equal(dropped, false, 'Only one original restore POST may reach the transport');
      const response = await route.fetch();
      assert.equal(response.status(), 200);
      const payload = await response.json();
      assert.equal(payload.data.operation.request_key, route.request().postDataJSON().request_key);
      assert.equal(payload.data.operation.state, options.expected || 'succeeded');
      dropped = true;
      // Abort after the real response: a TCP destroy would let Chromium retry the POST.
      await route.abort('failed');
    });
    await page.goto(origin + '/workbench?view=system');
    if (options.mode === 'warm') {
      await page.getByRole('tab', { name: '备份恢复', exact: true }).click();
      const row = page.locator('tbody tr').filter({ hasText: '_source.db' }); await row.click();
      await page.getByRole('button', { name: '恢复备份', exact: true }).click();
      const dialog = page.getByRole('dialog'), submit = dialog.getByRole('button', { name: '确认恢复', exact: true });
      assert(await submit.isDisabled()); await dialog.getByRole('checkbox').check();
      await dialog.getByRole('textbox').fill('恢复'); await screenshot(page, 'warm-confirm');
      await submit.click();
      await page.locator('[data-restore-maintenance=warm]').waitFor();
      await page.waitForFunction(() => !document.querySelector('[data-restore-maintenance] [aria-busy=true]'));
      if (options.drop) { assert.equal(dropped, true); await page.getByRole('button', { name: '核实原请求', exact: true }).click(); }
      await page.getByText(options.expected === 'rollback_failed' ? '系统已暂停，维护结果待核实' : '维护已结束，请重启整个软件', { exact: true }).waitFor();
      assert(await page.evaluate(() => document.getElementById('root').inert));
      assert.equal(await page.getByRole('button', { name: '确认结果', exact: true }).count(), 0);
      assert.equal(await page.getByRole('button', { name: '继续使用', exact: true }).count(), 0);
      report.pending = await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')));
      assert.deepEqual(Object.keys(report.pending).sort(), ['action', 'request_key', 'summary']);
      assert.equal(report.pending.request_key, report.operation.request_key);
      assert.equal(report.operation.state, options.expected || 'succeeded');
      await screenshot(page, 'warm-result');
      await page.getByRole('radio', { name: '维护记录编号', exact: true }).check();
      await page.getByRole('textbox', { name: '查询标识', exact: true }).fill(report.operation.job_ref);
      await page.getByRole('button', { name: '查询维护结果', exact: true }).click();
      await page.waitForFunction(() => !document.querySelector('[data-restore-maintenance] [aria-busy=true]'));
      assert((await page.locator('[data-restore-maintenance]').textContent()).includes(report.operation.filename));
      const download = page.waitForEvent('download'); await page.getByRole('button', { name: '导出维护诊断', exact: true }).click();
      const artifact = await download; await artifact.saveAs(path.join(options.output, artifact.suggestedFilename()));
      report.diagnostic = JSON.parse(fs.readFileSync(path.join(options.output, artifact.suggestedFilename()), 'utf8'));
      assert.equal(report.diagnostic.result.operation.job_ref, report.operation.job_ref);
      assert.equal(report.diagnostic.database_checked_by_page, false);
      report.geometry = await geometry(page); assert.equal(report.geometry.theme, options.theme);
      await page.getByRole('radio', { name: options.theme === 'light' ? '深色' : '浅色', exact: true }).check();
      assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), options.theme === 'light' ? 'dark' : 'light');
      await page.reload();
      await page.locator('[data-restore-maintenance=cold]').waitFor();
      assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')).request_key), report.pending.request_key);
      await screenshot(page, 'browser-refresh-still-maintenance');
      assert.equal(report.requests.filter(row => row.method === 'POST').length, 1);
      assert(report.requests.filter(row => row.after_restore).every(row => row.method === 'GET' && (/^\/api\/workbench\/v1\/system\/(restore-host|results\/|jobs\/)/.test(row.path) || row.path.startsWith('/workbench'))));
      report.after_readonly_hashes = hashes(); assert.deepEqual(report.after_readonly_hashes, report.after_restore_hashes);
    } else {
      await page.locator('[data-restore-maintenance=cold]').waitFor();
      await page.getByRole('textbox', { name: '查询标识', exact: true }).fill(options.reference);
      await page.getByRole('button', { name: '查询维护结果', exact: true }).click();
      await page.waitForURL('**reference=' + options.reference);
      assert((await page.locator('main').textContent()).includes(options.corrupt ? '维护记录损坏' : '校验中'));
      assert.equal(await page.getByRole('textbox', { name: '查询标识', exact: true }).inputValue(), options.reference);
      const download = page.waitForEvent('download'); await page.getByRole('button', { name: '导出维护诊断', exact: true }).click();
      const artifact = await download; await artifact.saveAs(path.join(options.output, artifact.suggestedFilename()));
      report.diagnostic = JSON.parse(fs.readFileSync(path.join(options.output, artifact.suggestedFilename()), 'utf8'));
      assert.equal(report.diagnostic.database_checked_by_page, false);
      assert.equal(Boolean(report.diagnostic.query_error), options.corrupt);
      report.geometry = await geometry(page); assert.equal(report.geometry.theme, options.theme);
      await screenshot(page, options.corrupt ? 'cold-corrupt' : 'cold-pending');
      await page.getByRole('radio', { name: options.theme === 'light' ? '深色' : '浅色', exact: true }).check();
      assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), options.theme === 'light' ? 'dark' : 'light');
      assert(report.requests.every(row => row.method === 'GET' && row.path.startsWith('/workbench')));
    }
    assert(report.geometry.scroll <= options.viewport.width);
    assert(report.geometry.fields.every(box => box.width > 0 && box.height >= 30 && box.right <= options.viewport.width && box.left >= 0));
    await context.close(); assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
    for (const [name, hash] of Object.entries(report.source_sha256)) assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root, 'frontend/workbench/app', name))).digest('hex'), hash);
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(options.output, 'browser-report.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({ output: options.output, browser: report.browser, screenshots: report.screenshots.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
