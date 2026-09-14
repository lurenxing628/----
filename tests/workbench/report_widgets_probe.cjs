/* Mock browser interaction evidence only; real SQLite proof lives in pytest. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass screenshot directory; fixture JSON is read from stdin');
const fixtureBytes = fs.readFileSync(0), fixture = JSON.parse(fixtureBytes);
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const styleNames = ['00-tokens.css', '10-shell.css', '11-navigation.css', '20-controls.css', '21-table-frame.css', '22-shared-controls.css', '37-reports.css'];
const sourceStyles = styleNames.map(name => ({ path: 'frontend/workbench/app/styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
const styleMarkup = sourceStyles.map(row => '<style>' + row.code + '</style>').join('');
const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const names = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'ResourceControls.jsx', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchControlBridge.js', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchDetailPanel.jsx', 'ReportEvidence.jsx', 'ReportAPI.js', 'ReportControls.jsx', 'ReportTable.jsx', 'ReportDetail.jsx', 'ReviewChartViews.jsx', 'ReviewCharts.jsx', 'ReportCatalog.jsx', 'ReportWorkspace.jsx', 'ReviewWorkspace.jsx'];
const sourceFiles = names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype', order.babel.path), sources: sourceFiles }).outputs;
const scripts = new Map(compiled.map(row => ['/probe/' + row.path, row.code]));
const record = { scope: 'mock-browser-interactions-with-captured-sqlite-dto', cases: [], requests: [], screenshots: [], errors: [], external: [], downloads: [], responses: [],
  compile_global_build: false, fixture_sha256: hash(fixtureBytes), style_build_id: manifest.build_id,
  sources: sourceFiles.map(row => ({ path: 'frontend/workbench/' + row.path, sha256: hash(row.code) })), probe_sha256: hash(fs.readFileSync(__filename)) };
function readData(url) {
  const query = Object.fromEntries(url.searchParams), topic = query.topic || 'delivery';
  if (url.pathname.includes('/reports/')) return fixture.catalogs[url.pathname.split('/')[5]];
  const captured = query.query ? fixture.filters.search : query.focus === 'finish_late' ? fixture.filters.finish_late : fixture.topics[topic];
  if (query.query) assert.equal(query.query, 'OP-02', 'Unknown scope has no captured SQLite fixture');
  const result = JSON.parse(JSON.stringify(captured));
  let rows = result.data.rows;
  const sort = query.sort || result.data.page.sort[0].field;
  rows.sort((a, b) => (a[sort] == null ? 1 : b[sort] == null ? -1 : a[sort] < b[sort] ? -1 : a[sort] > b[sort] ? 1 : 0) * (query.direction === 'desc' ? -1 : 1));
  const page = Number(query.page || 1), size = Number(query.size || 20);
  result.data.page = { number: page, size, total: rows.length, pages: Math.max(1, Math.ceil(rows.length / size)), sort: [{ field: sort, direction: query.direction || 'asc' }] };
  result.data.rows = rows.slice((page - 1) * size, page * size);
  if (query.snapshot_ref) assert.equal(query.snapshot_ref, result.meta.snapshot_ref, 'A mock response cannot silently replace its captured snapshot');
  if (url.pathname.includes('/operations/')) result.data.detail = fixture.details[url.pathname.split('/').pop()];
  return result;
}
const boot = `
function ProbeApp(){const [mode,setMode]=React.useState('reports'),[context,setContext]=React.useState({});
  const navigate=(target,value)=>{setMode(target);setContext(value);};
  return React.createElement(AppShell,{active:mode,title:'报表交互夹具（mock）',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:navigate},
    React.createElement(mode==='review'?window.ReviewWorkspace:window.ReportWorkspace,{key:mode,initialContext:context,onNav:navigate}));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(ProbeApp));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  styleMarkup + '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(file => !file.endsWith('/main.js')).map(file => '<script src="/static/' + file + '"></script>').join('') +
  compiled.map(row => '<script src="/probe/' + row.path + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
record.sources.push(...sourceStyles.map(row => ({ path: row.path, sha256: hash(row.code) })));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, row]));
let failNext = false;
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const asset = assets.get(url.pathname); response.setHeader('Content-Type', asset.mime); return response.end(fs.readFileSync(path.join(root, 'static', asset.path))); }
  if (url.pathname.startsWith('/api/workbench/v1/')) {
    record.requests.push({ path: url.pathname, query: Object.fromEntries(url.searchParams), method: request.method });
    if (failNext) { failNext = false; response.writeHead(409, { 'Content-Type': 'application/json' }); return response.end(JSON.stringify({ ok: false, committed: false, error: { code: 'snapshot_stale', message: '范围快照已经失效，请明确刷新。', fields: [] } })); }
    if (url.pathname.endsWith('/export')) {
      const format = url.searchParams.get('format') || 'csv', topic = url.searchParams.get('topic') || 'delivery';
      response.setHeader('Content-Type', format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      response.setHeader('Content-Disposition', 'attachment; filename="report.' + format + '"');
      return response.end(Buffer.from(fixture.downloads[topic + '.' + format], 'base64'));
    }
    const payload = readData(url); record.responses.push({ path: url.pathname, query: Object.fromEntries(url.searchParams), payload });
    response.setHeader('Content-Type', 'application/json'); return response.end(JSON.stringify(payload));
  }
  response.writeHead(404); response.end();
});
async function shot(page, name) {
  const filename = path.join(output, name + '.png'); await page.screenshot({ path: filename }); record.screenshots.push(filename);
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    assert(browser.version().startsWith('109.')); record.browser = browser.version();
    const origin = 'http://127.0.0.1:' + server.address().port;
    for (const viewport of [{ width: 1920, height: 1080 }, { width: Number(process.env.WORKBENCH_UI_NARROW_WIDTH || 1392), height: 924 }]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport, acceptDownloads: true });
      await context.addInitScript(value => { localStorage.setItem('aps_theme', value); localStorage.setItem('aps_kit_theme', value); }, theme);
      const page = await context.newPage(); page.on('pageerror', error => record.errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error' && !message.text().includes('409')) record.errors.push(message.text()); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { record.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin);
      const missingData = await page.evaluate(() => {
        const host = document.createElement('section'); document.body.appendChild(host);
        const root = ReactDOM.createRoot(host), summary = { records: 0, events: 0, production_reports: 0, operations: 3,
          reported_operations: 0, unreported: 3, effective_processing_hours: null, known_effective_processing_hours: 0, unknown_hour_events: 0 };
        function read(value) {
          ReactDOM.flushSync(() => root.render(React.createElement(React.Fragment, null,
            React.createElement(ReportEvidence.NoFeedback, { summary: value }), React.createElement(ReportTable.Metrics, { summary: value, topic: 'records' }))));
          return { banners: host.querySelectorAll('.rw-no-feedback').length,
            values: Array.from(host.querySelectorAll('.wb-metric-value'), node => node.textContent), text: host.textContent };
        }
        const empty = read(summary), partial = read({ ...summary, records: 1, production_reports: 1, unknown_hour_events: 1 });
        ReactDOM.flushSync(() => root.unmount()); host.remove(); return { empty, partial };
      });
      assert.equal(missingData.empty.banners, 1); assert.deepEqual(missingData.empty.values, ['3', '0', '0', '—']);
      assert.equal(missingData.partial.banners, 0); assert.equal(missingData.partial.values[3], '未知');
      assert(missingData.partial.text.includes('已知小计 0；未知 1 条'));
      assert.equal(await page.locator('.mockroot.plana').count(), 0);
      const work = page.getByRole('region', { name: '报表中心', exact: true });
      await work.locator('[role="tabpanel"] table tbody tr').first().waitFor();
      assert.equal(await work.locator('.rw-primary-table table > caption').textContent(), '当前范围报表结果');
      assert(await work.locator('.rw-primary-table thead th').evaluateAll(cells => cells.every(cell => cell.scope === 'col')));
      assert.equal(await work.locator('.rw-primary-table tbody tr').first().locator('.rw-fixed-action').count(), 1);
      assert(await work.locator('.rw-primary-table .aps-th-resize').count() > 0, 'Read-only table must retain column resizing');
      const modifiedArrows = await work.locator('[role="tab"][aria-selected="true"]').evaluateAll(tabs => tabs.flatMap(tab =>
        ['altKey', 'ctrlKey', 'metaKey'].map(modifier => {
          const event = new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true, cancelable: true, [modifier]: true });
          tab.dispatchEvent(event); return event.defaultPrevented;
        })));
      assert(modifiedArrows.length >= 6 && modifiedArrows.every(value => !value), 'Modified arrows must remain available to the browser');
      const prefix = viewport.width + '-' + theme;
      await shot(page, prefix + '-reports');
      await work.getByLabel('每页条数', { exact: true }).selectOption('10');
      await page.waitForFunction(() => document.querySelector('.rw-list-pane > .wb-pager')?.textContent.includes('1 / 3'));
      await work.getByRole('button', { name: '下一页', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.rw-list-pane > .wb-pager')?.textContent.includes('2 / 3'));
      for (const format of ['csv', 'xlsx']) {
        await work.getByLabel('导出格式', { exact: true }).selectOption(format);
        const downloadWait = page.waitForEvent('download'); await work.getByRole('button', { name: '导出范围', exact: true }).click();
        const download = await downloadWait, filename = path.join(output, prefix + '-all-rows.' + format); await download.saveAs(filename);
        const bytes = fs.readFileSync(filename), expected = Buffer.from(fixture.downloads['delivery.' + format], 'base64');
        assert.deepEqual(bytes, expected, 'Downloaded bytes must match the captured real SQLite export');
        if (format === 'csv') assert.equal(bytes.toString('utf8').trim().split(/\r?\n/).length, 24, 'All 23 rows, not current page');
        record.downloads.push({ path: filename, topic: 'delivery', format, sha256: hash(bytes), rows: 23, page: 2, size: 10 });
      }
      await work.getByRole('button', { name: '上一页', exact: true }).click();
      await work.getByRole('button', { name: /^查看工序 / }).first().click();
      const detail = work.locator('.rw-detail'); await detail.getByText('整道完成', { exact: true }).waitFor();
      const detailLayout = await detail.evaluate(node => {
        const rect = node.getBoundingClientRect(), parent = node.parentElement;
        return { display: getComputedStyle(parent).display, width: rect.width, left: rect.left,
          listRight: parent.querySelector('.rw-list-pane').getBoundingClientRect().right, focused: node.contains(document.activeElement) };
      });
      assert.equal(detailLayout.display, 'grid'); assert(detailLayout.width <= 360 && detailLayout.width >= 280);
      assert(detailLayout.listRight <= detailLayout.left); assert(detailLayout.focused, 'Detail heading must receive focus');
      await detail.scrollIntoViewIfNeeded(); await shot(page, prefix + '-detail');
      await detail.getByRole('button', { name: /^关闭/ }).click();
      await page.waitForFunction(() => document.activeElement.matches('.rw-primary-table button'));
      await work.getByRole('tab', { name: '报工记录', exact: true }).click();
      await work.getByText(fixture.topics.records.data.rows[0].record_kind_label, { exact: true }).first().waitFor();
      const records = fixture.topics.records.data;
      assert.equal(records.summary.events, 5); assert.equal(records.summary.production_reports, 0); assert.equal(records.summary.records, 5);
      assert.equal(records.summary.effective_processing_hours, null); assert.equal(records.summary.known_effective_processing_hours, null);
      const cells = await work.locator('.rw-primary-table table tbody tr').evaluateAll(rows => rows.map(row => Array.from(row.cells, cell => cell.textContent)));
      assert.equal(cells.length, records.rows.length);
      records.rows.forEach((row, index) => {
        assert(cells[index][1].includes(row.record_kind_label));
        assert.equal(cells[index][3], row.quantity_done === null ? '未知' : String(row.quantity_done));
        assert.equal(cells[index][4], row.effective_processing_hours === null ? '未知' : String(row.effective_processing_hours));
      });
      await shot(page, prefix + '-records');
      await work.getByRole('tab', { name: '报工记录', exact: true }).press('ArrowRight');
      await work.getByRole('tab', { name: '设备工时', exact: true }).waitFor();
      await work.getByRole('tab', { name: '设备工时', exact: true }).press('End');
      await page.waitForFunction(() => document.querySelector('#report-tab-quality').getAttribute('aria-selected') === 'true');
      await work.getByRole('tab', { name: '数据完整性', exact: true }).press('Home');
      await work.getByRole('searchbox', { name: '搜索批次或工序' }).fill('OP-02');
      await work.getByRole('button', { name: '查询范围', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.rw-list-pane > .wb-pager')?.textContent.includes('共 1 项'));
      await work.getByRole('button', { name: '清除筛选', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.rw-list-pane > .wb-pager')?.textContent.includes('共 23 项'));
      await work.getByRole('button', { name: '更多筛选', exact: true }).click();
      await work.getByLabel('资源类型', { exact: true }).selectOption('machine');
      await work.getByLabel('分析范围', { exact: true }).selectOption('finish_late');
      await work.getByRole('button', { name: '查询范围', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.rw-list-pane > .wb-pager')?.textContent.includes('共 1 项'));
      await work.getByRole('button', { name: '清除筛选', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.rw-list-pane > .wb-pager')?.textContent.includes('共 23 项'));
      failNext = true; await work.getByRole('button', { name: '下一页', exact: true }).click();
      await work.getByRole('alert').waitFor(); assert.equal(await work.getByRole('button', { name: '导出范围', exact: true }).count(), 0);
      await work.getByRole('button', { name: '刷新报表数据', exact: true }).click();
      await work.locator('[role="tabpanel"] table tbody tr').first().waitFor();
      await work.locator('.rw-catalog > summary').click();
      await work.getByLabel('其他报表', { exact: true }).selectOption('downtime');
      await work.getByText('停机只认已登记的停机记录，不把报工空档当成停机。', { exact: false }).waitFor();
      await work.locator('.rw-catalog > summary').evaluate(node => node.scrollIntoView({ block: 'start' }));
      await shot(page, prefix + '-catalog');
      await work.getByRole('tab', { name: '执行复盘', exact: true }).click();
      const review = page.getByRole('region', { name: '执行复盘', exact: true }); await review.locator('table tbody tr').first().waitFor();
      await review.getByRole('tab', { name: '执行复盘', exact: true }).press('Home');
      await work.locator('.rw-primary-table tbody tr').first().waitFor();
      await page.waitForFunction(() => document.activeElement.id === 'analytics-view-reports');
      await work.getByRole('tab', { name: '报表中心', exact: true }).press('End');
      await review.locator('table tbody tr').first().waitFor();
      await page.waitForFunction(() => document.activeElement.id === 'analytics-view-review');
      await page.evaluate(() => window.scrollTo(0, 0)); await shot(page, prefix + '-review');
      await review.locator('.er-chart-disclosure > summary').click();
      await review.locator('.er-chart-disclosure > summary').evaluate(node => node.scrollIntoView({ block: 'start' })); await shot(page, prefix + '-charts');
      const geometry = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
        theme: document.documentElement.dataset.theme, background: getComputedStyle(document.querySelector('.rw-workbench')).backgroundColor,
        controls: Array.from(document.querySelectorAll('.aw-scope-main input,.aw-scope-main select,.aw-scope-tools button')).map(node => { const rect = node.getBoundingClientRect(); return { x: rect.x, right: rect.right, width: rect.width, height: rect.height }; }) }));
      assert(geometry.scroll <= viewport.width + 1, JSON.stringify(geometry));
      assert(geometry.controls.every(item => item.width > 0 && item.height >= 30 && item.right <= viewport.width + 1));
      assert.equal(geometry.background, 'rgba(0, 0, 0, 0)');
      assert.equal(geometry.theme, theme);
      record.cases.push({ viewport, theme, geometry, tabs: true, pagination: true, all_row_download: true, detail: true, filters: true, stale_recovery: true, catalog: true, review: true });
      await context.close();
    }
    assert.deepEqual(record.errors, []); assert.deepEqual(record.external, []); assert(record.requests.every(row => row.method === 'GET'));
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'report-ui-result.json'), JSON.stringify(record, null, 2));
  }
  console.log(JSON.stringify({ output, browser: record.browser, cases: record.cases.length, screenshots: record.screenshots.length, errors: record.errors, external: record.external }));
})().catch(error => { console.error(error); process.exitCode = 1; });
