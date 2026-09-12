/* Browser input against live temporary SQLite + production GET routes. No DTO replay. */
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
const record = { scope: 'live-sqlite-production-routes-and-business-projection', compile_global_build: false, cases: [], downloads: [], screenshots: [], responses: [], errors: [], external: [],
  sources: sources.map(row => ({ path: 'frontend/workbench/' + row.path, sha256: hash(row.code) })), style_build_id: manifest.build_id, contract_rejections: 0 };
let headerFault = null;
const boot = `
function CalibrationProbe(){
  const api=React.useMemo(()=>{if(location.pathname!='/unknown')return undefined;const real=window.CalibrationAPI.create();return {...real,read:async(...args)=>{const result=await real.read(...args);return {...result,data:{...result.data,capabilities:{...result.data.capabilities,export:'unknown'}}};}};},[]);
  return React.createElement(React.Fragment,null,React.createElement(window.WorkbenchControlStyles),React.createElement(window.WorkbenchControls),
    React.createElement(AppShell,{active:'calib',title:'工时定额校准',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
      React.createElement(window.CalibrationWorkspace,{adapter:api,onNavigate:(target,context)=>{window.calibrationNavigation={target,context};}})));
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(CalibrationProbe));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  styleMarkup + '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(file => !file.endsWith('/main.js') && !/\/Calibration[^/]*\.js$/.test(file)).map(file => '<script src="/static/' + file + '"></script>').join('') +
  compiled.map(row => '<script src="/probe/' + row.path + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
record.sources.push(...sourceStyles.map(row => ({ path: row.path, sha256: hash(row.code) })));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, row]));
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/' || url.pathname === '/unknown') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const asset = assets.get(url.pathname); response.setHeader('Content-Type', asset.mime); return response.end(fs.readFileSync(path.join(root, 'static', asset.path))); }
  if (url.pathname.startsWith('/api/workbench/v1/calibration') || url.pathname.startsWith('/__calibration_fixture__/')) {
    assert.equal(request.method, 'GET');
    const upstream = http.get(config.api_origin + request.url, incoming => {
      const chunks = [];
      incoming.on('data', chunk => chunks.push(chunk));
      incoming.on('end', () => {
        const body = Buffer.concat(chunks), headers = { ...incoming.headers };
        if (url.pathname.endsWith('/export') && incoming.statusCode === 200 && headerFault) { headers[headerFault] = 'incorrect'; headerFault = null; }
        if (headers['content-type']?.includes('application/json')) record.responses.push({ path: url.pathname, query: Object.fromEntries(url.searchParams), status: incoming.statusCode, payload: JSON.parse(body) });
        response.writeHead(incoming.statusCode, headers); response.end(body);
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
async function select(page, name, option) {
  await page.getByLabel(name, { exact: true }).click();
  const popup = page.locator('.wb-control-popup'); await popup.waitFor();
  await popup.getByRole('option', { name: option, exact: true }).click();
}
async function listAfter(page, action) {
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/calibration');
  await action(); const response = await pending, payload = await response.json();
  assert.equal(response.status(), 200, JSON.stringify(payload));
  await page.locator('.calibration-live[data-ready="true"]').waitFor();
  await page.waitForFunction(total => document.querySelector('.calibration-live .ca-list-pane > .wb-pager')?.textContent.includes('共 ' + total + ' 项'), payload.data.page.total);
  return payload;
}
async function readAll(payload) {
  const rows = [];
  for (let page = 1; page <= payload.data.page.total_pages; page++) {
    const query = new URLSearchParams();
    Object.entries(payload.data.scope).forEach(([key, value]) => { if (!['kind', 'method_version'].includes(key) && value !== null && value !== '') query.set(key, String(value)); });
    query.set('snapshot_ref', payload.meta.snapshot_ref); query.set('page', String(page));
    const result = await fetch(config.api_origin + '/api/workbench/v1/calibration?' + query);
    assert.equal(result.status, 200); const parsed = await result.json();
    assert.equal(parsed.meta.snapshot_ref, payload.meta.snapshot_ref); rows.push(...parsed.data.items);
  }
  return rows;
}
async function verifyCells(page, payload) {
  const cells = await page.locator('.ca-table[aria-label="校准明细"] tbody tr').evaluateAll(rows => rows.map(row => ({ ref: row.dataset.ref, cells: Array.from(row.cells, cell => cell.textContent) })));
  assert.equal(cells.length, payload.data.items.length);
  payload.data.items.forEach((item, index) => {
    assert.equal(cells[index].ref, item.suggestion_ref);
    assert.equal(cells[index].cells[2], item.old_unit_hours === null ? '未提供' : String(item.old_unit_hours));
    assert.equal(cells[index].cells[3], '暂无建议'); assert.equal(cells[index].cells[4], '0');
    assert.equal(cells[index].cells[5], '未计算'); assert.equal(cells[index].cells[6], '数据不足');
  });
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
      assert.equal(payload.data.summary.total, 23); await verifyCells(page, payload);
      const geometry = await page.evaluate(() => {
        const first = document.querySelector('.ca-table tbody tr').getBoundingClientRect();
        const groups = Array.from(document.querySelectorAll('.ca-tools')).map(group => Array.from(group.children, child => {
          const rect = child.getBoundingClientRect(); return { x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height };
        }));
        return { scroll_width: document.documentElement.scrollWidth, first_row_bottom: first.bottom, theme: document.documentElement.dataset.theme,
          background: getComputedStyle(document.querySelector('.calibration-live')).backgroundColor, groups };
      });
      assert(geometry.scroll_width <= viewport.width); assert(geometry.first_row_bottom < viewport.height);
      assert.equal(geometry.theme, theme); assert.equal(geometry.background, 'rgba(0, 0, 0, 0)');
      geometry.groups.forEach(group => group.forEach((a, index) => {
        assert(a.width > 0 && a.right <= viewport.width);
        group.slice(index + 1).forEach(b => assert(!(a.x < b.right - 1 && a.right > b.x + 1 && a.y < b.bottom - 1 && a.bottom > b.y + 1), JSON.stringify({ a, b })));
      }));
      await capture(page, prefix + '-list');
      const work = page.getByRole('region', { name: '工时定额校准', exact: true });
      await work.getByRole('searchbox', { name: '搜索校准明细' }).fill('Turning-02');
      payload = await listAfter(page, () => work.getByRole('button', { name: '搜索', exact: true }).click());
      assert.equal(payload.data.page.total, 1); assert.equal(payload.data.items[0].old_unit_hours, 0); await verifyCells(page, payload);
      await work.getByRole('searchbox', { name: '搜索校准明细' }).fill('Turning-03');
      payload = await listAfter(page, () => work.getByRole('searchbox', { name: '搜索校准明细' }).press('Enter'));
      assert.equal(payload.data.page.total, 1); assert.equal(payload.data.items[0].old_unit_hours, null); await verifyCells(page, payload);
      payload = await listAfter(page, () => work.getByRole('checkbox', { name: '仅看偏差 > 20%' }).check());
      assert.equal(payload.data.page.total, 0); await work.getByText('当前筛选没有记录', { exact: true }).waitFor();
      assert(await work.getByRole('button', { name: /^导出全部筛选/ }).isDisabled()); await capture(page, prefix + '-filtered-empty');
      payload = await listAfter(page, () => work.getByRole('button', { name: '清除筛选', exact: true }).click());
      payload = await listAfter(page, () => select(page, '工序来源', '自制')); assert.equal(payload.data.page.total, 22);
      payload = await listAfter(page, () => select(page, '建议状态', '数据不足')); assert.equal(payload.data.page.total, 22);
      payload = await listAfter(page, () => select(page, '排序字段', '原单件定额'));
      payload = await listAfter(page, () => select(page, '排序方向', '降序'));
      payload = await listAfter(page, () => select(page, '每页条数', '10 项'));
      payload = await listAfter(page, () => work.getByRole('button', { name: '下一页', exact: true }).click());
      assert.equal(payload.data.page.number, 2); await verifyCells(page, payload);
      const allRows = await readAll(payload); assert.equal(allRows.length, 22); assert.equal(allRows.at(-1).old_unit_hours, null);
      for (const format of ['csv', 'xlsx']) {
        await select(page, '导出格式', format.toUpperCase());
        const responseWait = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/calibration/export'));
        const downloadWait = page.waitForEvent('download'); await work.getByRole('button', { name: '导出全部筛选', exact: true }).click();
        const response = await responseWait, headers = response.headers(), download = await downloadWait;
        const filename = path.join(output, prefix + '-filtered-all.' + format); await download.saveAs(filename);
        assert.equal(headers['x-workbench-snapshot'], payload.meta.snapshot_ref); assert.equal(Number(headers['x-workbench-row-count']), 22);
        record.downloads.push({ path: filename, format, sha256: hash(fs.readFileSync(filename)), snapshot: payload.meta.snapshot_ref, as_of: payload.meta.as_of,
          headers_count: Number(headers['x-workbench-row-count']), expected_rows: allRows, scope: payload.data.scope, page: payload.data.page.number });
      }
      payload = await listAfter(page, () => work.getByRole('button', { name: '清除筛选', exact: true }).click());
      await work.getByRole('searchbox', { name: '搜索校准明细' }).fill('Turning-01');
      payload = await listAfter(page, () => work.getByRole('searchbox', { name: '搜索校准明细' }).press('Enter'));
      const detailWait = page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/calibration/' + config.template_ref);
      await work.getByRole('button', { name: /^查看 P1 1 / }).click();
      const detailPayload = await (await detailWait).json();
      assert.equal(detailPayload.data.candidate_scope_basis, 'template_ref_and_same_part_unbound');
      assert(detailPayload.data.samples.every(sample => sample.template_operation_ref === null && !sample.eligible && !sample.selected));
      const selected = detailPayload.data.samples.find(sample => sample.reports.some(report => report.report_ref === config.report_ref)); assert(selected);
      const detail = work.locator('.ca-detail');
      const detailLayout = await detail.evaluate(node => ({ display: getComputedStyle(node.parentElement).display,
        width: node.getBoundingClientRect().width, focused: node.contains(document.activeElement) }));
      assert.equal(detailLayout.display, 'grid'); assert(detailLayout.width <= 360 && detailLayout.width >= 280); assert(detailLayout.focused);
      const sample = detail.locator('.ca-sample[data-sample-ref="' + selected.sample_ref + '"]'); await sample.locator(':scope > summary').click();
      await sample.getByText(config.long_code, { exact: true }).waitFor();
      await sample.locator('details > summary').filter({ hasText: /^报工 ·/ }).first().click();
      await sample.getByText('登记与更正记录（2 条）', { exact: true }).waitFor();
      await sample.locator('details > summary').filter({ hasText: /^更正 ·/ }).first().click();
      assert(await detail.getByRole('button', { name: /^采用/ }).isDisabled()); assert(await detail.getByRole('button', { name: /^锁定/ }).isDisabled());
      assert.equal(selected.legacy_facts.length, 3);
      await sample.locator('details > summary').filter({ hasText: /^旧现场记录 1$/ }).click();
      const evidenceText = await sample.locator('.rw-evidence-facts').first().textContent();
      const leaves = value => value && typeof value === 'object' ? Object.values(value).flatMap(leaves) :
        [value === null ? '未知' : typeof value === 'boolean' ? value ? '是' : '否' : String(value)];
      for (const value of leaves(selected.legacy_facts[0])) assert(evidenceText.includes(value), value);
      const sourceGeometry = await sample.evaluate(node => ({ scroll: document.documentElement.scrollWidth, width: innerWidth,
        clipped: Array.from(node.querySelectorAll('dd,td')).filter(item => item.scrollWidth > item.clientWidth + 1).map(item => item.textContent) }));
      assert(sourceGeometry.scroll <= sourceGeometry.width); assert.deepEqual(sourceGeometry.clipped, []);
      await sample.scrollIntoViewIfNeeded(); await capture(page, prefix + '-source-correction');
      const beforeRef = selected.sample_ref;
      const change = await fetch(config.api_origin + '/__calibration_fixture__/change-source'); assert.equal(change.status, 200);
      const staleWait = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/calibration/export'));
      await work.getByRole('button', { name: '导出全部筛选', exact: true }).click(); assert.equal((await staleWait).status(), 409);
      await work.locator('[role="alert"]').filter({ hasText: '前后快照不一致' }).waitFor();
      await capture(page, prefix + '-stale');
      const refreshedDetail = page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/calibration/' + config.template_ref && response.status() === 200);
      await listAfter(page, () => work.getByRole('button', { name: '明确刷新', exact: true }).click()); await refreshedDetail;
      await detail.locator('.ca-sample[data-sample-ref="' + beforeRef + '"][open]').waitFor();
      await detail.getByText(config.long_code, { exact: true }).waitFor();
      await work.getByRole('button', { name: '执行复盘', exact: true }).click();
      const navigation = await page.evaluate(() => window.calibrationNavigation);
      assert.equal(navigation.target, 'review'); assert.equal(navigation.context.returnTo.view, 'calib');
      assert.equal(navigation.context.returnTo.context.selected, config.template_ref);
      assert.equal(navigation.context.returnTo.context.sample_ref, beforeRef);
      await page.evaluate(value => window.CalibrationAPI.initial(value), navigation.context.returnTo.context);
      record.cases.push({ viewport, theme, geometry, zero_distinct_null: true, selected_source_retained: true, real_409: true });
      if (!record.contract_rejections) {
        record.contract_rejections = await page.evaluate(raw => {
          const A = window.CalibrationAPI, query = { ...raw.data.scope }; delete query.kind; delete query.method_version;
          let rejected = 0;
          const changes = [value => { value.data.items[0].old_unit_hours = undefined; }, value => { value.data.items[0].sample_count = 6; },
            value => { value.data.items[0].suggested_unit_hours = 0; }, value => { value.data.page.total++; }, value => { value.meta.snapshot_ref = 'changed'; },
            value => { value.data.scope.size++; }, value => { value.data.items[0].deviation_percent = Infinity; }];
          changes.forEach(change => { const copy = JSON.parse(JSON.stringify(raw)); change(copy); try { A.validate(copy, { ...query, snapshot_ref: raw.meta.snapshot_ref }); } catch (_) { rejected++; } });
          try { A.initial({ scope: { unknown_source: 'ignored?' } }); } catch (_) { rejected++; }
          return rejected;
        }, payload);
        assert.equal(record.contract_rejections, 8);
      }
      await context.close();
    }
    const page = await browser.newPage();
    await listAfter(page, () => page.goto(origin + '/unknown'));
    assert(await page.getByRole('button', { name: /^导出全部筛选/ }).isDisabled());
    await page.getByText('导出权限尚未确认，暂不能导出。', { exact: true }).waitFor(); record.unknown_permission_disabled = true;
    let saves = 0; page.on('download', () => saves++);
    for (const name of ['x-workbench-snapshot', 'x-workbench-row-count']) {
      await listAfter(page, () => page.goto(origin)); headerFault = name;
      await page.getByRole('button', { name: '导出全部筛选', exact: true }).click();
      await page.getByText('导出快照或总行数不一致，文件未保存，请明确刷新。', { exact: true }).waitFor();
      assert.equal(saves, 0);
    }
    record.export_header_rejections = 2;
    await page.close(); assert.deepEqual(record.external, []); assert.deepEqual(record.errors, []);
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'calibration-ui-result.json'), JSON.stringify(record, null, 2));
  }
  console.log(JSON.stringify({ cases: record.cases.length, downloads: record.downloads.length, screenshots: record.screenshots.length, browser: record.browser }));
})().catch(error => { console.error(error); process.exitCode = 1; });
