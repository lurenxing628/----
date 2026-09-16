/* CU: real route responses, input/click UI, and transport faults without fabricated business facts. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const config = JSON.parse(fs.readFileSync(0, 'utf8')), output = process.argv[2], root = path.resolve(__dirname, '../..');
const hash = v => crypto.createHash('sha256').update(v).digest('hex');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const names = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'ResourceControls.jsx', 'WorkbenchControlStyles.jsx', 'WorkbenchControlBridge.js', 'WorkbenchSelectMenu.jsx', 'WorkbenchControls.jsx',
  'CalibrationAPI.js', 'CalibrationControls.jsx', 'CalibrationAdoptionAPI.js', 'CalibrationAdoptionState.js', 'CalibrationAdoptionControls.jsx', 'CalibrationAdoptionAction.jsx', 'CalibrationDetail.jsx', 'CalibrationWorkspace.jsx'];
const sources = names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true }).outputs;
const scripts = new Map(compiled.map(row => ['/probe/' + row.path, row.code]));
const record = { compile_global_build: false, cases: [], downloads: [], errors: [], external: [], screenshots: [], responses: [], browser_restarts: 0,
  sources: sources.map(row => ({ path: 'frontend/workbench/' + row.path, sha256: hash(row.code) })), contract_rejections: 0 };
const boot = `ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(React.Fragment,null,
  React.createElement(window.WorkbenchControlStyles),React.createElement(window.WorkbenchControls),
  React.createElement(AppShell,{active:'calib',title:'工时定额校准',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
    React.createElement(window.CalibrationWorkspace,{onNavigate:(view,context)=>{window.cuNavigation={view,context};}}))));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(file => !file.endsWith('/main.js') && !/\/Calibration[^/]*\.js$/.test(file)).map(file => '<script src="/static/' + file + '"></script>').join('') +
  compiled.map(row => '<script src="/probe/' + row.path + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, row]));
let fault = '', blockReceipts = false, crossed = false;
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const asset = assets.get(url.pathname); response.setHeader('Content-Type', asset.mime); return response.end(fs.readFileSync(path.join(root, 'static', asset.path))); }
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/__calibration_adoption_fixture__/')) {
    if (url.pathname.includes('/receipts/') && blockReceipts) return response.destroy();
    if (url.pathname.endsWith('/adopt') && fault === 'before') return response.destroy();
    const chunks = []; request.on('data', data => chunks.push(data));
    request.on('end', () => {
      const body = Buffer.concat(chunks), post = body.length ? JSON.parse(body.toString()) : null;
      const target = crossed && url.pathname.endsWith('/adopt-preview') ? url.pathname.replace(config.template_ref, config.other_ref) : request.url;
      const upstream = http.request(config.api_origin + target, { method: request.method, headers: { cookie: request.headers.cookie || '', ...(body.length ? { 'Content-Type': 'application/json', 'Content-Length': body.length } : {}) } }, incoming => {
        const parts = []; incoming.on('data', data => parts.push(data)); incoming.on('end', () => {
          const content = Buffer.concat(parts);
          if (incoming.headers['content-type']?.includes('application/json')) record.responses.push({ path: url.pathname, target, status: incoming.statusCode, input: post, payload: JSON.parse(content.toString()) });
          if (url.pathname.endsWith('/adopt') && fault === 'after') return response.destroy();
          response.writeHead(incoming.statusCode, incoming.headers); response.end(content);
        });
      });
      upstream.on('error', error => { record.errors.push(error.message); response.destroy(); }); upstream.end(body);
    }); return;
  }
  response.writeHead(404); response.end();
});
async function screenshot(page, name) { const file = path.join(output, name + '.png'); await page.screenshot({ path: file, animations: 'disabled' }); record.screenshots.push(file); }
async function geometry(page, viewport) {
  const data = await page.evaluate(() => {
    const dialog = document.querySelector('[role=dialog]'), body = document.querySelector('.cad-body');
    const rect = node => { const r = node.getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom }; };
    return { width: document.documentElement.scrollWidth, theme: document.documentElement.dataset.theme, dialog: rect(dialog),
      body_scroll: body.scrollHeight, body_height: body.clientHeight,
      fields: Array.from(dialog.querySelectorAll('input[type=text],textarea'), node => ({ ...rect(node), color: getComputedStyle(node).color })),
      footer: Array.from(dialog.querySelectorAll('.modal-f button'), rect),
      clipped: Array.from(dialog.querySelectorAll('dd,td,button')).filter(node => node.scrollWidth > node.clientWidth + 2).map(node => node.textContent) };
  });
  assert(data.width <= viewport.width && data.dialog.x >= 0 && data.dialog.right <= viewport.width && data.dialog.y >= 0 && data.dialog.bottom <= viewport.height);
  assert.deepEqual(data.clipped, []);
  data.footer.forEach((a, i) => data.footer.slice(i + 1).forEach(b => assert(!(a.x < b.right - 1 && a.right > b.x + 1 && a.y < b.bottom - 1 && a.bottom > b.y + 1))));
  return data;
}
async function waitList(page, action) {
  const promise = page.waitForResponse(r => new URL(r.url()).pathname === '/api/workbench/v1/calibration');
  await action(); const response = await promise; assert.equal(response.status(), 200); await page.locator('.calibration-live[data-ready=true]').waitFor(); return response.json();
}
async function selectDetail(page, ref = config.template_ref) {
  const [response] = await Promise.all([
    page.waitForResponse(r => new URL(r.url()).pathname === '/api/workbench/v1/calibration/' + ref),
    page.locator('.ca-table tr[data-ref="' + ref + '"]').getByRole('button', { name: /^查看 / }).click(),
  ]);
  assert.equal(response.status(), 200); await page.locator('[data-sample-group=selected]').waitFor(); return response.json();
}
async function startPreview(page, reason = '核对已完成批次和加工小时，采用中位数定额', declared = '校准复核员') {
  await page.getByRole('button', { name: '预检采用', exact: true }).click();
  const dialog = page.getByRole('dialog'); await dialog.waitFor();
  await dialog.getByLabel('采用原因', { exact: true }).fill(reason); await dialog.getByLabel('经办人', { exact: true }).fill(declared);
  const wait = page.waitForResponse(r => r.url().endsWith('/adopt-preview'));
  await dialog.getByRole('button', { name: '检查是否可采用', exact: true }).click(); const response = await wait; return { response, dialog, reason, declared };
}
async function validated(page, preview, original, intent, receipt, stored) {
  return page.evaluate(({ preview, original, intent, receipt, stored }) => {
    const A = window.CalibrationAdoptionAPI; A.preview(preview, original, intent); A.receipt(receipt, stored);
    const mutations = [v => { v.data.template_operation_ref = 'f'.repeat(48); }, v => { v.data.suggestion.old_unit_hours++; },
      v => { v.data.suggestion.template_revision++; }, v => { v.data.suggestion.sample_refs.reverse(); }, v => { v.data.samples[0].sample_revision = 'bad'; },
      v => { v.data.samples[0].template_operation_ref = 'f'.repeat(48); }, v => { v.data.samples[0].selected = false; }, v => { v.data.samples.pop(); },
      v => { v.data.input.reason += 'changed'; }, v => { v.data.input.declared_operator += 'changed'; }, v => { v.data.write_context.capabilities['calibration.adopt'] = false; },
      v => { v.data.effect_scope = 'existing_batches'; }];
    let rejected = 0;
    mutations.forEach(change => { const copy = JSON.parse(JSON.stringify(preview)); change(copy); try { A.preview(copy, original, intent); } catch (_) { rejected++; } });
    [v => { v.data.request_key += 'x'; }, v => { v.data.template_operation_ref = 'e'.repeat(48); }, v => { v.data.locked = false; },
      v => { v.data.new_unit_hours++; }, v => { v.data.declared_operator = 'other'; }, v => { v.data.confirmed = false; }].forEach(change => {
      const copy = JSON.parse(JSON.stringify(receipt)); change(copy); try { A.receipt(copy, stored); } catch (_) { rejected++; }
    }); return rejected;
  }, { preview, original, intent, receipt, stored });
}
let browser, origin;
async function launch() { return chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] }); }
async function contextFor(name, viewport = { width: 1392, height: 924 }, theme = 'light', storageState) {
  const context = await browser.newContext({ viewport, acceptDownloads: true, ...(storageState ? { storageState } : {}) });
  await context.addCookies([{ name: 'cu_case', value: name, url: origin }]);
  await context.addInitScript(value => { localStorage.setItem('aps_theme', value); localStorage.setItem('aps_kit_theme', value); }, theme);
  const page = await context.newPage(); page.on('pageerror', e => record.errors.push(e.message));
  await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { record.external.push(route.request().url()); return route.abort(); } return route.continue(); });
  await waitList(page, () => page.goto(origin)); return { context, page };
}
async function happyCase(viewport, theme) {
  const name = theme + '-' + viewport.width, reason = '核对五个整道完工实例，采用3小时中位数 ' + name, declared = '校准员-' + name;
  let { context, page } = await contextFor(name, viewport, theme);
  const original = await selectDetail(page), selected = page.locator('[data-sample-group=selected]');
  assert.equal(await selected.locator('.ca-sample').count(), 5);
  assert.equal(await page.locator('[data-sample-group=excluded] .ca-sample').count(), 2);
  assert.equal(await page.locator('[data-sample-group=unbound] .ca-sample').count(), 1);
  await selected.locator('summary').first().click();
  await page.getByRole('button', { name: '执行复盘', exact: true }).click();
  const navigation = await page.evaluate(() => window.cuNavigation);
  assert.equal(navigation.context.returnTo.context.selected, config.template_ref); assert(navigation.context.returnTo.context.sample_ref); record.navigation_retained = true;
  const waitDownload = page.waitForEvent('download'); await page.getByRole('button', { name: '导出全部筛选', exact: true }).click();
  const download = await waitDownload, filename = path.join(output, name + '.csv'); await download.saveAs(filename);
  assert(fs.readFileSync(filename).includes(Buffer.from(config.template_ref))); record.downloads.push({ path: filename, sha256: hash(fs.readFileSync(filename)) });
  const inspected = await startPreview(page, reason, declared), preview = await inspected.response.json();
  assert.equal(inspected.response.status(), 200); assert.equal(preview.data.validation.can_adopt, true);
  assert.equal(preview.data.suggestion.old_unit_hours, 2); assert.equal(preview.data.suggestion.suggested_unit_hours, 3);
  await inspected.dialog.getByText('检查通过，可以采用。', { exact: true }).waitFor();
  assert(await inspected.dialog.getByRole('button', { name: '确认采用并锁定', exact: true }).isDisabled());
  const layout = await geometry(page, viewport); assert.equal(layout.theme, theme); await screenshot(page, name + '-preview');
  await inspected.dialog.getByRole('checkbox').check();
  fault = 'after'; blockReceipts = true;
  await inspected.dialog.getByRole('button', { name: '确认采用并锁定', exact: true }).click();
  await inspected.dialog.getByRole('alert').waitFor();
  const stored = await page.evaluate(() => window.CalibrationAdoptionState.read()); assert.equal(stored.phase, 'pending');
  await screenshot(page, name + '-unknown'); const state = await context.storageState();
  await context.close(); await browser.close(); browser = await launch(); record.browser_restarts++;
  blockReceipts = false; fault = ''; ({ context, page } = await contextFor(name, viewport, theme, state));
  await page.getByRole('button', { name: '查看采用结果', exact: true }).click();
  let dialog = page.getByRole('dialog'); await dialog.getByText('采用已完成。新定额 3 小时 / 件，定额已锁定（来自工时校准）。', { exact: true }).waitFor();
  const committed = await page.evaluate(() => window.CalibrationAdoptionState.read());
  assert.equal(committed.request_key, stored.request_key); assert(committed.receipt.replayed);
  await geometry(page, viewport); await screenshot(page, name + '-receipt');
  const replay = await context.request.post(origin + '/api/workbench/v1/calibration/' + config.template_ref + '/adopt', { data: {
    write_token: 'expired-original-token', request_key: stored.request_key, input: stored.input } });
  assert.equal(replay.status(), 200); const replayed = await replay.json(); assert.equal(replayed.replayed, true);
  assert.equal(replayed.receipt_ref, committed.receipt.receipt_ref);
  const wrong = await context.request.get(origin + '/api/workbench/v1/calibration/' + config.other_ref + '/adopt/receipts/' + stored.request_key);
  assert.equal(wrong.status(), 409);
  if (!record.contract_rejections) record.contract_rejections = await validated(page, preview, original.data.suggestion, { reason, declared_operator: declared }, committed.receipt, stored);
  await dialog.getByRole('button', { name: '完成', exact: true }).click();
  await selectDetail(page); const locked = await startPreview(page, reason, declared);
  assert.equal((await locked.response.json()).data.quota_lock.locked, true);
  await locked.dialog.getByText('这个模板的定额已经采用并锁定，不能重复采用或覆盖。', { exact: true }).waitFor();
  assert(await locked.dialog.getByRole('button', { name: '确认采用并锁定', exact: true }).isDisabled()); await screenshot(page, name + '-locked');
  record.cases.push({ name, viewport, theme, request_key: stored.request_key, reason, declared_operator: declared, geometry: layout }); await context.close();
}
async function boundaries() {
  let { context, page } = await contextFor('disabled'); await selectDetail(page);
  let inspected = await startPreview(page); assert.equal(inspected.response.status(), 503);
  await inspected.dialog.getByText('此功能尚未开通。', { exact: true }).waitFor();
  record.disabled_reason = true; await screenshot(page, 'disabled'); await context.close();
  ({ context, page } = await contextFor('missing'));
  await selectDetail(page, config.missing_ref);
  inspected = await startPreview(page); assert.equal((await inspected.response.json()).data.validation.can_adopt, false);
  await inspected.dialog.getByText('这个模板版本下合格的整道完工记录不足 5 条，不能采用。', { exact: true }).waitFor();
  record.insufficient_reason = true; await screenshot(page, 'insufficient'); await context.close();
  ({ context, page } = await contextFor('cross')); await selectDetail(page); crossed = true;
  inspected = await startPreview(page); assert.equal(inspected.response.status(), 200);
  await inspected.dialog.getByRole('alert').waitFor(); assert(await inspected.dialog.getByRole('button', { name: '确认采用并锁定', exact: true }).isDisabled());
  record.cross_template_blocked = true; crossed = false; await screenshot(page, 'cross-template'); await context.close();
  ({ context, page } = await contextFor('drift')); await selectDetail(page); inspected = await startPreview(page);
  assert.equal(inspected.response.status(), 200); await inspected.dialog.getByRole('checkbox').check();
  assert.equal((await context.request.post(origin + '/__calibration_adoption_fixture__/mutate')).status(), 200);
  const confirm = page.waitForResponse(r => r.url().endsWith('/adopt')); await inspected.dialog.getByRole('button', { name: '确认采用并锁定', exact: true }).click();
  assert.equal((await confirm).status(), 409); await inspected.dialog.getByText(/本次没有采用；请点「刷新所选模板」/).waitFor();
  assert(await inspected.dialog.getByRole('button', { name: '确认采用并锁定', exact: true }).isDisabled());
  const changed = page.waitForResponse(r => r.url().endsWith('/adopt-preview')); await inspected.dialog.getByRole('button', { name: '检查是否可采用', exact: true }).click();
  assert.equal((await changed).status(), 200); await inspected.dialog.getByText('模板、原定额或完工记录已变化，请点「刷新所选模板」后重新预检。', { exact: true }).waitFor();
  const refreshed = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/calibration/' + config.template_ref));
  await inspected.dialog.getByRole('button', { name: '刷新所选模板', exact: true }).click(); assert.equal((await refreshed).status(), 200);
  record.drift_blocked = true; await screenshot(page, 'drift-refreshed'); await context.close();
  ({ context, page } = await contextFor('lost')); await selectDetail(page); inspected = await startPreview(page); await inspected.dialog.getByRole('checkbox').check();
  fault = 'before'; const notFound = page.waitForResponse(r => r.url().includes('/receipts/'));
  await inspected.dialog.getByRole('button', { name: '确认采用并锁定', exact: true }).click(); assert.equal((await notFound).status(), 404);
  await inspected.dialog.getByText(/上次采用的结果还没查到/).waitFor(); const stored = await page.evaluate(() => window.CalibrationAdoptionState.read());
  await inspected.dialog.getByRole('button', { name: '关闭并保留上次操作', exact: true }).click(); await selectDetail(page, config.other_ref);
  await page.getByRole('button', { name: '查询上次采用结果', exact: true }).click();
  await page.getByRole('dialog').getByText('另一个模板的采用结果待确认，请先查询结果。', { exact: true }).waitFor();
  assert.equal((await page.evaluate(() => window.CalibrationAdoptionState.read())).request_key, stored.request_key);
  assert.equal(await page.getByRole('button', { name: '确认采用并锁定', exact: true }).count(), 0);
  record.not_found_retained = true; await screenshot(page, 'not-found-retained'); await context.close();
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); origin = 'http://127.0.0.1:' + server.address().port;
  try {
    browser = await launch(); record.browser = browser.version(); assert(record.browser.startsWith('109.'));
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) await happyCase(viewport, theme);
    await boundaries(); assert.deepEqual(record.errors, []); assert.deepEqual(record.external, []);
  } catch (error) {
    record.runner_error = error.stack;
    throw error;
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'calibration-adoption-ui.json'), JSON.stringify(record, null, 2));
  }
  console.log(JSON.stringify({ browser: record.browser, cases: record.cases.length, restarts: record.browser_restarts, screenshots: record.screenshots.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
