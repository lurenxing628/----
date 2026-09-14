/* Real CE-created SQLite -> public calibration routes -> isolated Chrome 109. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const config = JSON.parse(fs.readFileSync(0, 'utf8')), output = process.argv[2], root = path.resolve(__dirname, '../..');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const styleNames = ['00-tokens.css', '10-shell.css', '11-navigation.css', '20-controls.css', '21-table-frame.css', '22-shared-controls.css', '37-reports.css'];
const sourceStyles = styleNames.map(name => ({ path: 'frontend/workbench/app/styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
const styleMarkup = sourceStyles.map(row => '<style>' + row.code + '</style>').join('');
const names = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'ResourceControls.jsx', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchControlBridge.js', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchDetailPanel.jsx', 'ReportEvidence.jsx', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchControls.jsx',
  'CalibrationAPI.js', 'CalibrationControls.jsx', 'CalibrationDetail.jsx', 'CalibrationWorkspace.jsx'];
const sources = names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true }).outputs;
const scripts = new Map(compiled.map(row => ['/probe/' + row.path, row.code]));
const record = { scope: 'CE-real-template-copies-ledger-public-API-Chrome109', compile_global_build: false, cases: [], downloads: [], screenshots: [], responses: [], errors: [], external: [],
  sources: sources.map(row => ({ path: 'frontend/workbench/' + row.path, sha256: hash(row.code) })), style_build_id: manifest.build_id, contract_rejections: 0 };
const boot = `ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(React.Fragment,null,
  React.createElement(window.WorkbenchControlStyles),React.createElement(window.WorkbenchControls),
  React.createElement(AppShell,{active:'calib',title:'工时定额校准',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
    React.createElement(window.CalibrationWorkspace))));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  styleMarkup + '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(file => !file.endsWith('/main.js') && !/\/Calibration[^/]*\.js$/.test(file)).map(file => '<script src="/static/' + file + '"></script>').join('') +
  compiled.map(row => '<script src="/probe/' + row.path + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
record.sources.push(...sourceStyles.map(row => ({ path: row.path, sha256: hash(row.code) })));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, row]));
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const asset = assets.get(url.pathname); response.setHeader('Content-Type', asset.mime); return response.end(fs.readFileSync(path.join(root, 'static', asset.path))); }
  if (url.pathname.startsWith('/api/workbench/v1/calibration')) {
    assert.equal(request.method, 'GET');
    const upstream = http.get(config.api_origin + request.url, incoming => {
      const chunks = [];
      incoming.on('data', chunk => chunks.push(chunk));
      incoming.on('end', () => {
        const body = Buffer.concat(chunks);
        if (incoming.headers['content-type']?.includes('application/json')) record.responses.push({ path: url.pathname, query: Object.fromEntries(url.searchParams), status: incoming.statusCode, payload: JSON.parse(body) });
        response.writeHead(incoming.statusCode, incoming.headers); response.end(body);
      });
    });
    upstream.on('error', error => { record.errors.push(error.message); response.writeHead(502); response.end(); });
    return;
  }
  response.writeHead(404); response.end();
});
async function capture(page, name) {
  const filename = path.join(output, name + '.png'); await page.screenshot({ path: filename }); record.screenshots.push(filename);
}
async function select(page, label, value) {
  await page.getByLabel(label, { exact: true }).click();
  const popup = page.locator('.wb-control-popup'); await popup.waitFor();
  await popup.getByRole('option', { name: value, exact: true }).click();
}
async function listAfter(page, action) {
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/calibration');
  await action(); const response = await pending, payload = await response.json();
  assert.equal(response.status(), 200, JSON.stringify(payload));
  await page.locator('.calibration-live[data-ready="true"]').waitFor();
  await page.waitForFunction(total => document.querySelector('.calibration-live .ca-list-pane > .wb-pager')?.textContent.includes('共 ' + total + ' 项'), payload.data.summary.total);
  return payload;
}
async function search(page, text) {
  await page.getByRole('searchbox', { name: '搜索校准明细' }).fill(text);
  return listAfter(page, () => page.getByRole('searchbox', { name: '搜索校准明细' }).press('Enter'));
}
async function verifyCells(page, payload) {
  const rows = await page.locator('.ca-table[aria-label="校准明细"] tbody tr').evaluateAll(nodes => nodes.map(node => ({ ref: node.dataset.ref, cells: Array.from(node.cells, cell => cell.textContent) })));
  assert.equal(rows.length, payload.data.items.length);
  payload.data.items.forEach((item, index) => {
    assert.equal(rows[index].ref, item.suggestion_ref);
    assert.equal(rows[index].cells[2], item.old_unit_hours === null ? '未填写' : String(item.old_unit_hours));
    assert.equal(rows[index].cells[3], item.suggested_unit_hours === null ? '暂无建议' : String(item.suggested_unit_hours));
    assert.equal(rows[index].cells[4], String(item.sample_count));
    assert.equal(rows[index].cells[6], item.status === 'suggested' ? '待复核' : '数据不足');
  });
}
async function openDetail(page, ref) {
  const [response] = await Promise.all([
    page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/calibration/' + ref),
    page.locator('.ca-table tr[data-ref="' + ref + '"]').getByRole('button', { name: /^查看 / }).click(),
  ]);
  const payload = await response.json(); assert.equal(response.status(), 200, JSON.stringify(payload));
  await page.locator('[data-sample-group="selected"]').waitFor();
  return payload;
}
async function readAll(payload) {
  const rows = [], query = new URLSearchParams();
  Object.entries(payload.data.scope).forEach(([key, value]) => { if (!['kind', 'method_version'].includes(key) && value !== null && value !== '') query.set(key, String(value)); });
  query.set('snapshot_ref', payload.meta.snapshot_ref);
  for (let page = 1; page <= payload.data.page.total_pages; page++) {
    query.set('page', String(page));
    const response = await fetch(config.api_origin + '/api/workbench/v1/calibration?' + query); assert.equal(response.status, 200);
    const parsed = await response.json(); assert.equal(parsed.meta.snapshot_ref, payload.meta.snapshot_ref); rows.push(...parsed.data.items);
  }
  return rows;
}
async function geometry(page, viewport) {
  const value = await page.evaluate(() => {
    const groups = Array.from(document.querySelectorAll('.ca-tools')).map(group => Array.from(group.children, child => {
      const rect = child.getBoundingClientRect(); return { x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom, width: rect.width };
    }));
    return { width: document.documentElement.scrollWidth, theme: document.documentElement.dataset.theme, groups,
      clipped: Array.from(document.querySelectorAll('.ca-refs dd,.ca-table td')).filter(node => node.scrollWidth > node.clientWidth + 1).map(node => node.textContent) };
  });
  assert(value.width <= viewport.width); assert.deepEqual(value.clipped, []);
  value.groups.forEach(group => group.forEach((a, index) => {
    assert(a.width > 0 && a.right <= viewport.width);
    group.slice(index + 1).forEach(b => assert(!(a.x < b.right - 1 && a.right > b.x + 1 && a.y < b.bottom - 1 && a.bottom > b.y + 1), JSON.stringify({ a, b })));
  }));
  return value;
}
async function rejectInvalidDetails(page, payload) {
  return page.evaluate(raw => {
    const A = window.CalibrationAPI, row = raw.data.suggestion, query = { ...raw.data.scope, snapshot_ref: raw.meta.snapshot_ref };
    delete query.kind; delete query.method_version;
    A.validate(raw, query, row.suggestion_ref);
    const linked = value => value.data.samples.find(sample => sample.selected), unbound = value => value.data.samples.find(sample => sample.template_operation_ref === null);
    const changes = [value => { linked(value).template_operation_ref = 'f'.repeat(48); }, value => { linked(value).template_revision++; },
      value => { unbound(value).selected = true; }, value => { linked(value).sample_revision = 'changed'; }, value => { value.data.samples[1].sample_ref = value.data.samples[0].sample_ref; },
      value => { linked(value).reports[0].correction_history = null; }, value => { value.data.suggestion.sample_refs[0] = unbound(value).sample_ref; },
      value => { value.data.suggestion.candidate_count++; }, value => { value.data.candidate_scope_basis = 'same_part_unbound_not_template_match'; },
      value => { delete value.data.lineage_available; }, value => { linked(value).effective_processing_hours = undefined; }, value => { linked(value).selected = false; }];
    let rejected = 0;
    changes.forEach(change => { const copy = JSON.parse(JSON.stringify(raw)); change(copy); try { A.validate(copy, query, row.suggestion_ref); } catch (_) { rejected++; } });
    return rejected;
  }, payload);
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    record.browser = browser.version(); assert(record.browser.startsWith('109.'));
    for (const viewport of [{ width: 1920, height: 1080 }, { width: Number(process.env.WORKBENCH_UI_NARROW_WIDTH || 1392), height: 924 }]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport, acceptDownloads: true });
      await context.addInitScript(value => { localStorage.setItem('aps_theme', value); localStorage.setItem('aps_kit_theme', value); }, theme);
      const page = await context.newPage(); page.on('pageerror', error => record.errors.push(error.message));
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { record.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      const prefix = viewport.width + '-' + theme;
      let payload = await listAfter(page, () => page.goto(origin));
      assert.equal(payload.data.summary.total, 23); assert.equal(payload.data.summary.suggested, 3); await verifyCells(page, payload);
      const layout = await geometry(page, viewport); assert.equal(layout.theme, theme); await capture(page, prefix + '-list');
      payload = await search(page, 'Turning-01'); assert.equal(payload.data.items[0].suggested_unit_hours, 3); await verifyCells(page, payload);
      const main = await openDetail(page, config.template_ref), data = main.data;
      assert.equal(data.candidate_scope_basis, 'template_ref_and_same_part_unbound'); assert.equal(data.samples.length, 14);
      assert.deepEqual(new Set(data.suggestion.sample_refs), new Set(config.selected_refs));
      assert(!data.samples.some(sample => config.other_refs.includes(sample.sample_ref) || config.recent_refs.includes(sample.sample_ref)));
      const detail = page.locator('.ca-detail');
      for (const [kind, count] of [['selected', 5], ['excluded', 7], ['unbound', 2]]) {
        const group = detail.locator('[data-sample-group="' + kind + '"]');
        assert.equal(await group.locator('.ca-sample').count(), count); assert((await group.locator('h4').first().textContent()).includes('（' + count + '）'));
      }
      assert(await detail.getByRole('button', { name: /^采用/ }).isDisabled()); assert(await detail.getByRole('button', { name: /^锁定/ }).isDisabled());
      await detail.scrollIntoViewIfNeeded(); await capture(page, prefix + '-groups');
      const sample = detail.locator('.ca-sample[data-sample-ref="' + config.correction_sample_ref + '"]');
      await sample.locator(':scope > summary').click(); await sample.locator(':scope > .wb-ref > summary').click(); await sample.getByText(config.template_ref, { exact: true }).waitFor();
      await sample.locator('details > summary').filter({ hasText: /^报工 ·/ }).first().click();
      await sample.locator('details:not([open]).wb-ref > summary').first().click(); await sample.getByText(config.report_ref, { exact: true }).waitFor();
      await sample.getByText('登记与更正记录（2 条）', { exact: true }).waitFor();
      await sample.locator('details > summary').filter({ hasText: /^更正 ·/ }).click();
      const correction = await sample.getByRole('table', { name: '更正前后值' }).locator('tr').filter({ hasText: '有效加工工时（小时）' }).textContent();
      assert(correction.includes('900') && correction.includes('1000')); await geometry(page, viewport);
      await sample.locator('details > summary').filter({ hasText: /^更正 ·/ }).scrollIntoViewIfNeeded(); await capture(page, prefix + '-correction');
      const unknown = detail.locator('.ca-sample[data-sample-ref="' + config.unknown_ref + '"]');
      assert((await unknown.locator(':scope > summary').textContent()).includes('已知数量 0 · 1 条数量未知'));
      await unknown.locator(':scope > summary').click(); await unknown.getByRole('heading', { name: '数据缺口' }).waitFor();
      await unknown.getByText('单件工时：未知；数量未知记录 1 条。', { exact: true }).waitFor();
      await unknown.scrollIntoViewIfNeeded(); await capture(page, prefix + '-unbound');
      if (!record.contract_rejections) { record.contract_rejections = await rejectInvalidDetails(page, main); assert.equal(record.contract_rejections, 12); }
      payload = await search(page, 'Turning-02'); assert.equal(payload.data.items[0].old_unit_hours, 0); assert.equal(payload.data.items[0].suggested_unit_hours, 20); await verifyCells(page, payload);
      const other = await openDetail(page, payload.data.items[0].suggestion_ref);
      assert.equal(other.data.samples.length, 7); assert(!other.data.samples.some(sample => config.selected_refs.includes(sample.sample_ref)));
      payload = await search(page, 'Turning-03'); assert.equal(payload.data.items[0].old_unit_hours, null); assert.equal(payload.data.items[0].suggested_unit_hours, null); await verifyCells(page, payload);
      const empty = await openDetail(page, payload.data.items[0].suggestion_ref);
      assert(empty.data.samples.every(sample => sample.template_operation_ref === null));
      await detail.getByText('同模板、同版本的可用完工记录不足 5 条，暂无建议。', { exact: true }).waitFor(); await capture(page, prefix + '-insufficient');
      payload = await search(page, 'Turning-04'); const recent = await openDetail(page, payload.data.items[0].suggestion_ref);
      assert.equal(recent.data.suggestion.sample_count, 20); assert.equal(recent.data.suggestion.suggested_unit_hours, 15.5);
      const group = detail.locator('[data-sample-group="selected"]');
      const refs = () => group.locator('.ca-sample').evaluateAll(nodes => nodes.map(node => node.dataset.sampleRef));
      assert.deepEqual(await refs(), recent.data.suggestion.sample_refs.slice(0, 10));
      await group.getByRole('button', { name: '可用记录下一页', exact: true }).click();
      assert.deepEqual(await refs(), recent.data.suggestion.sample_refs.slice(10));
      assert(recent.data.samples.filter(sample => sample.eligible && !sample.selected).every(sample => sample.exclusion_reasons.some(reason => reason.code === 'outside_recent_20')));
      payload = await listAfter(page, () => page.getByRole('button', { name: '清除筛选', exact: true }).click());
      payload = await listAfter(page, () => select(page, '建议状态', '已有建议')); assert.equal(payload.data.summary.total, 3); await verifyCells(page, payload);
      payload = await listAfter(page, () => page.getByRole('checkbox', { name: '仅看偏差 > 20%' }).check()); assert.equal(payload.data.summary.total, 2);
      payload = await listAfter(page, () => page.getByRole('button', { name: '清除筛选', exact: true }).click());
      payload = await listAfter(page, () => select(page, '工序来源', '自制'));
      payload = await listAfter(page, () => select(page, '排序列', '建议单件定额'));
      payload = await listAfter(page, () => select(page, '排序方向', '降序'));
      payload = await listAfter(page, () => select(page, '每页条数', '10 项'));
      payload = await listAfter(page, () => page.getByRole('button', { name: '下一页', exact: true }).click());
      assert.equal(payload.data.page.number, 2); await verifyCells(page, payload);
      const allRows = await readAll(payload); assert.equal(allRows.length, 22); assert.equal(allRows.filter(row => row.suggested_unit_hours !== null).length, 3);
      for (const format of ['csv', 'xlsx']) {
        await select(page, '导出格式', format.toUpperCase());
        const waitResponse = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/calibration/export'));
        const waitDownload = page.waitForEvent('download'); await page.getByRole('button', { name: '导出全部筛选', exact: true }).click();
        const response = await waitResponse, download = await waitDownload, filename = path.join(output, prefix + '-all-filtered.' + format);
        await download.saveAs(filename); assert.equal(Number(response.headers()['x-workbench-row-count']), 22);
        assert.equal(response.headers()['x-workbench-snapshot'], payload.meta.snapshot_ref);
        record.downloads.push({ path: filename, format, sha256: hash(fs.readFileSync(filename)), expected_rows: allRows, scope: payload.data.scope,
          snapshot: payload.meta.snapshot_ref, as_of: payload.meta.as_of, page: payload.data.page.number });
      }
      record.cases.push({ viewport, theme, geometry: layout, median: 3, selected: 5, excluded: 7, unbound: 2, recent20_median: 15.5 });
      await context.close();
    }
    const page = await browser.newPage(); page.on('pageerror', error => record.errors.push(error.message));
    await listAfter(page, () => page.goto(origin)); let payload = await search(page, 'Turning-01'); await openDetail(page, config.template_ref);
    assert.equal((await fetch(config.api_origin + '/__calibration_lineage_fixture__/recreate', { method: 'POST' })).status, 200);
    const stale = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/calibration/export'));
    await page.getByRole('button', { name: '导出全部筛选', exact: true }).click(); assert.equal((await stale).status(), 409);
    await page.locator('.calibration-live[data-stale="true"]').waitFor();
    const missing = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/calibration/' + config.template_ref));
    payload = await listAfter(page, () => page.getByRole('button', { name: '刷新', exact: true }).click());
    assert.equal((await missing).status(), 404); assert.notEqual(payload.data.items[0].suggestion_ref, config.template_ref);
    assert.equal(payload.data.items[0].sample_count, 0); assert.equal(payload.data.items[0].suggested_unit_hours, null);
    await page.locator('.ca-detail .wb-ref > summary').first().click(); await page.locator('.ca-detail').getByText(config.template_ref, { exact: true }).waitFor();
    record.recreated_ref_not_retargeted = true; await capture(page, 'deleted-recreated-ref'); await page.close();
    assert.deepEqual(record.errors, []); assert.deepEqual(record.external, []);
  } catch (error) {
    record.runner_error = error.stack;
    throw error;
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'calibration-lineage-ui.json'), JSON.stringify(record, null, 2));
  }
  console.log(JSON.stringify({ browser: record.browser, cases: record.cases.length, downloads: record.downloads.length, screenshots: record.screenshots.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
