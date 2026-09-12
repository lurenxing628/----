/* BC: browser -> real temporary Flask -> AJ SQLite ledger. No mock HTTP DTOs. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], ready = JSON.parse(fs.readFileSync(path.join(output, 'ready.json')));
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const evidence = { global_build: false, source: 'live-fullapp-flask-sqlite-aj-commands', cases: [], screenshots: [], errors: [], external: [], comparisons: [], downloads: [] };
function createServer() {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'))), assets = new Map();
  evidence.shared_style_build_id = manifest.build_id;
  manifest.files.forEach(item => { const bytes = fs.readFileSync(path.join(root, 'static', item.path)); assert.equal(hash(bytes), item.sha256); assets.set('/static/' + item.path, { bytes, mime: item.mime }); });
  const files = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-api.js', 'resource-session.js', 'ResourceControls.jsx', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchControlBridge.js', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchDetailPanel.jsx', 'ReportEvidence.jsx', 'ReportAPI.js', 'ReportControls.jsx',
    'ReportTable.jsx', 'ReportDetail.jsx', 'ReviewChartViews.jsx', 'ReviewCharts.jsx', 'ReportCatalog.jsx', 'ReportWorkspace.jsx', 'ReviewWorkspace.jsx',
    'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchNumberControls.jsx'];
  const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
  evidence.sources = sources.map(row => ({ path: row.path, sha256: hash(row.code) }));
  const styleNames = ['00-tokens.css', '10-shell.css', '11-navigation.css', '20-controls.css', '21-table-frame.css', '22-shared-controls.css', '37-reports.css'];
  const sourceStyles = styleNames.map(name => ({ path: 'frontend/workbench/app/styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
  evidence.sources.push(...sourceStyles.map(row => ({ path: row.path, sha256: hash(row.code) })));
  const styleMarkup = sourceStyles.map(row => '<style>' + row.code + '</style>').join('');
  const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
  built.outputs.forEach((row, index) => assets.set('/fixture/' + files[index], { bytes: row.code, mime: 'application/javascript' }));
  const boot = `function Harness(){const[view,setView]=React.useState('reports'),[context,setContext]=React.useState({}),[revision,setRevision]=React.useState(0);
    window.remountReports=context=>{setView('reports');setContext(context);setRevision(value=>value+1);};
    const navigate=(view,context)=>{setView(view);setContext(context);};return React.createElement(React.Fragment,null,
      React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),
      React.createElement(AppShell,{active:view,title:'报表与执行复盘',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:navigate},
        React.createElement(view==='review'?ReviewWorkspace:ReportWorkspace,{key:view+revision,initialContext:context,onNav:navigate})));}
    ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(Harness));`;
  const scripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'))
    .map(file => '/static/' + file).concat(files.map(file => '/fixture/' + file));
  const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('')
    + styleMarkup + '</head><body class="aps-workbench"><div id="root"></div>' + scripts.map(file => '<script src="' + file + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
  return http.createServer((req, res) => {
    if (req.url.startsWith('/api/workbench/')) {
      const forwarded = http.request(new URL(req.url, ready.origin), { method: req.method, headers: { accept: req.headers.accept || 'application/json' } }, remote => { res.writeHead(remote.statusCode, remote.headers); remote.pipe(res); });
      forwarded.on('error', error => { res.writeHead(502); res.end(error.message); }); req.pipe(forwarded); return;
    }
    if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
    if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
    const asset = assets.get(req.url); if (!asset) { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
  });
}
async function shot(page, name) { const file = path.join(output, 'screenshots', name + '.png'); await page.screenshot({ path: file }); evidence.screenshots.push(file); }
async function readyWork(page) { await page.locator('.rw-workbench[data-ready="true"]').waitFor(); }
async function change(page, action) {
  const response = page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/analytics');
  response.catch(() => {});
  await action(); const actual = await response; assert.equal(actual.status(), 200, await actual.text()); const body = await actual.json();
  await readyWork(page); return body;
}
async function select(page, label, value) {
  const field = page.locator('select[aria-label="' + label + '"]');
  const text = await field.locator('option').evaluateAll((nodes, value) => nodes.find(node => node.value === value).textContent, value);
  await field.click(); await page.locator('.wb-control-popup').getByRole('option', { name: text, exact: true }).click();
}
async function compare(page, dto, label) {
  const data = dto.data, rows = page.locator('#report-topic-panel .rw-primary-table tbody tr');
  assert.equal(await rows.count(), data.rows.length, label + ': visible rows');
  const actual = await rows.allTextContents();
  data.rows.forEach((row, index) => {
    assert(actual[index].includes(row.operation_label || row.resource_label));
    if (data.topic === 'records') {
      assert(actual[index].includes(row.record_kind_label));
      if (row.quantity_done === null || row.effective_processing_hours === null) assert(actual[index].includes('未知'));
      const cells = actual[index];
      if (row.record_kind === 'production_report') assert(cells.includes(row.report_no));
    }
  });
  const cells = await rows.evaluateAll(nodes => nodes.map(node => Array.from(node.cells).map(cell => cell.textContent)));
  const value = item => item === null ? '未知' : String(item);
  if (data.topic === 'records') data.rows.forEach((row, index) => assert.deepEqual(cells[index].slice(3, 5), [row.quantity_done, row.effective_processing_hours].map(value)));
  if (['machines', 'people'].includes(data.topic)) data.rows.forEach((row, index) => assert.deepEqual(cells[index], data.columns.filter(column => !column.key.endsWith('_ref')).map(column => value(row[column.key]))));
  const helpers = await page.locator('.rw-metrics').innerText();
  if (data.topic !== 'delivery') {
    const values = await page.locator('.rw-metrics .wb-metric-value').allTextContents();
    assert.deepEqual(values, [data.summary.operations, data.summary.production_reports, data.summary.records, data.summary.effective_processing_hours === null ? '未知' : data.summary.effective_processing_hours].map(String));
    assert(helpers.includes('旧现场事件 ' + data.summary.events + ' 条'));
    assert(helpers.includes('已知小计 ' + (data.summary.known_effective_processing_hours ?? '未知')));
  }
  if (data.topic === 'delivery') {
    const values = await page.locator('.rw-metrics .wb-metric-value').allTextContents(), s = data.summary;
    const percent = number => number === null ? '未知' : (number * 100).toFixed(1) + '%';
    assert.deepEqual(values, [percent(s.completion_rate), percent(s.on_time_rate), value(s.late_open), value(s.median_finish_minutes)]);
  }
  if (data.topic === 'quality') {
    data.rows.forEach((row, index) => assert.deepEqual(cells[index].slice(2, 5), [row.event_count, row.production_report_count, row.record_count].map(String)));
  }
  evidence.comparisons.push({ label, topic: data.topic, scope: data.scope, summary: data.summary, rows: data.rows, table: actual });
}
async function download(page, dto, format, name) {
  await select(page, '导出格式', format);
  const pending = page.waitForEvent('download');
  const response = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/analytics/export'));
  await page.getByRole('button', { name: '导出范围', exact: true }).click();
  const saved = await pending, file = path.join(output, 'downloads', name + '.' + format); await saved.saveAs(file);
  const real = await response, direct = await page.request.get(real.url()); assert.equal(direct.status(), 200);
  const bytes = fs.readFileSync(file), oracle = await direct.body();
  if (format === 'csv') assert.equal(hash(bytes), hash(oracle));
  evidence.downloads.push({ file, format, scope: dto.data.scope, total: dto.data.page.total, url: real.url(), sha256: hash(bytes), bytes: bytes.length });
}
async function geometry(page) {
  const result = await page.evaluate(() => {
    const rgb = text => (text.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const luminance = color => rgb(color).map(v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
    const text = Array.from(document.querySelectorAll('.rw-workbench h2,.rw-workbench p,.rw-stack span,.wb-metric-label,.wb-metric-helper,.rw-list-pane > .wb-pager > span'))
      .filter(node => node.getClientRects().length && node.textContent.trim()).map(node => {
        let parent = node, background = 'rgba(0, 0, 0, 0)';
        while (parent && background === 'rgba(0, 0, 0, 0)') { background = getComputedStyle(parent).backgroundColor; parent = parent.parentElement; }
        const color = getComputedStyle(node).color, a = luminance(color), b = luminance(background === 'rgba(0, 0, 0, 0)' ? 'rgb(255,255,255)' : background);
        return { text: node.textContent.slice(0, 100), color, background, contrast: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) };
      });
    const controls = Array.from(document.querySelectorAll('.aw-scope-main input,.aw-scope-main select,.aw-scope-tools button,.rw-filters button'))
      .filter(node => node.getClientRects().length).map(node => { const r = node.getBoundingClientRect(); return { width: r.width, height: r.height, right: r.right, clipped: node.scrollWidth > node.clientWidth + 2 }; });
    return { width: innerWidth, scrollWidth: document.documentElement.scrollWidth, background: getComputedStyle(document.querySelector('.rw-workbench')).backgroundColor, text, controls };
  });
  assert(result.scrollWidth <= result.width + 1, JSON.stringify(result));
  assert(result.controls.every(row => row.width > 0 && row.height >= 30 && row.right <= result.width + 1));
  assert.equal(result.background, 'rgba(0, 0, 0, 0)');
  assert(result.text.every(row => row.contrast >= 4.5), JSON.stringify(result.text.filter(row => row.contrast < 4.5)));
  return result;
}
async function main() {
  const server = createServer(); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
  evidence.browser = browser.version(); assert(evidence.browser.startsWith('109.'));
  try {
    for (const width of [1920, Number(process.env.WORKBENCH_UI_NARROW_WIDTH || 1392)]) for (const theme of ['light', 'dark']) {
      const prefix = width + '-' + theme, context = await browser.newContext({ viewport: { width, height: width === 1920 ? 1080 : 924 }, acceptDownloads: true, timezoneId: 'America/New_York' });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      const page = await context.newPage();
      page.on('pageerror', error => evidence.errors.push(error.stack || error.message));
      page.on('console', message => { if (message.type() === 'error' && !message.text().includes('409')) evidence.errors.push(message.text()); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { evidence.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      let dto = await change(page, () => page.goto(origin)); await compare(page, dto, prefix + '-delivery'); await shot(page, prefix + '-reports');
      const layout = await geometry(page);
      dto = await change(page, () => select(page, '每页条数', '10')); assert.equal(dto.data.page.pages, 3);
      dto = await change(page, () => page.getByRole('button', { name: '下一页', exact: true }).click()); assert.equal(dto.data.page.number, 2); await compare(page, dto, prefix + '-page2');
      await download(page, dto, 'csv', prefix + '-all23'); await download(page, dto, 'xlsx', prefix + '-all23');
      dto = await change(page, () => page.getByRole('tab', { name: '报工记录', exact: true }).click());
      dto = await change(page, () => select(page, '每页条数', '50')); await compare(page, dto, prefix + '-records'); await shot(page, prefix + '-records');
      dto = await change(page, () => select(page, '排序字段', 'quantity_done'));
      dto = await change(page, () => select(page, '排序方向', 'desc')); await compare(page, dto, prefix + '-quantity-desc');
      assert.equal(dto.data.rows[0].quantity_done, 10);
      dto = await change(page, () => select(page, '排序字段', 'event_time'));
      dto = await change(page, () => select(page, '排序方向', 'asc'));
      assert.equal(dto.data.summary.events, 2); assert.equal(dto.data.summary.production_reports, 13); assert.equal(dto.data.summary.records, 15);
      const invalid = await page.evaluate(dto => {
        const mutations = [copy => delete copy.data.summary.production_reports, copy => copy.data.summary.records++,
          copy => delete copy.data.rows[0].record_kind_label, copy => delete copy.data.rows[0].effective_processing_hours];
        return mutations.map(mutate => { const copy = JSON.parse(JSON.stringify(dto)); mutate(copy); try { ReportAPI.validate(copy); return false; } catch (_) { return true; } });
      }, dto); assert(invalid.every(Boolean));
      const item = dto.data.rows.find(row => row.record_kind === 'production_report' && row.operation_ref === ready.expected.operation);
      const detailRead = page.waitForResponse(response => response.url().includes('/analytics/operations/' + item.operation_ref));
      await page.getByRole('button', { name: '查看工序 ' + item.operation_label, exact: true }).first().click();
      const detailDTO = await (await detailRead).json(), detail = page.locator('.rw-detail');
      await detail.getByText('整道完成', { exact: true }).waitFor(); assert.equal(detailDTO.data.detail.operation.record_count, 12);
      await detail.locator('.rw-limitations > summary').first().click();
      const history = detail.locator('.rw-limitations').first(); await history.getByText('逐次报工修订历史（3 次登记）', { exact: true }).waitFor();
      for (const summary of await history.locator('details > summary').all()) await summary.click();
      assert((await history.innerText()).includes('首次登记，无前值')); assert((await history.innerText()).includes('BC corrected quantity and hours'));
      await history.scrollIntoViewIfNeeded(); await shot(page, prefix + '-revisions');
      await detail.getByRole('button', { name: '下一页', exact: true }).click();
      assert.equal(await detail.locator('.wb-detail-body > .rw-table-scroll tbody tr').count(), 2);
      await detail.getByRole('button', { name: /^关闭/ }).click();
      const old = dto.data.rows.find(row => row.record_kind === 'legacy_event');
      const oldRead = page.waitForResponse(response => response.url().includes('/analytics/operations/' + old.operation_ref));
      await page.getByRole('button', { name: '查看工序 ' + old.operation_label, exact: true }).first().click();
      const oldDTO = await (await oldRead).json();
      await detail.getByText('整道完成', { exact: true }).waitFor();
      await detail.locator('.rw-limitations > summary').first().click();
      assert((await detail.innerText()).includes('旧原始事实'));
      const evidenceText = await detail.locator('.rw-limitations[open] .rw-evidence-facts').first().textContent();
      const leaves = value => value && typeof value === 'object' ? Object.values(value).flatMap(leaves) :
        [value === null ? '未知' : typeof value === 'boolean' ? value ? '是' : '否' : String(value)];
      for (const value of leaves(oldDTO.data.detail.records[0].legacy_evidence)) assert(evidenceText.includes(value), value);
      assert((await detail.innerText()).includes('旧系统原存储时间，未转换'));
      await detail.scrollIntoViewIfNeeded(); await shot(page, prefix + '-legacy');
      await detail.getByRole('button', { name: /^关闭/ }).click();
      await download(page, dto, 'csv', prefix + '-records15'); await download(page, dto, 'xlsx', prefix + '-records15');
      for (const [topic, label] of [['quality', '数据完整性'], ['machines', '设备工时'], ['people', '人员工时']]) {
        dto = await change(page, () => page.getByRole('tab', { name: label, exact: true }).click()); await compare(page, dto, prefix + '-' + topic); await shot(page, prefix + '-' + topic);
      }
      await page.getByRole('button', { name: '更多筛选', exact: true }).click();
      await select(page, '资源类型', 'machine'); await select(page, '关联资源', ready.expected.machine2);
      await select(page, '批次筛选', ready.expected.batch); await select(page, '分析范围', 'complete');
      await page.getByRole('searchbox', { name: '搜索批次或工序' }).fill('OP-01');
      for (const label of ['计划完工起日', '计划完工止日']) await page.getByLabel(label, { exact: true }).fill('2026-09-09');
      dto = await change(page, () => page.getByRole('button', { name: '查询范围', exact: true }).click());
      assert.equal(dto.data.summary.operations, 1); assert.equal(dto.data.summary.production_reports, 12); assert.equal(dto.data.summary.events, 0);
      assert.equal(dto.data.summary.effective_processing_hours, 3); assert.equal(dto.data.resources.machines.length, 2);
      await compare(page, dto, prefix + '-combined-cohort'); await download(page, dto, 'csv', prefix + '-filtered');
      dto = await change(page, () => page.getByRole('tab', { name: '执行复盘', exact: true }).click());
      await page.locator('.er-chart-disclosure > summary').click();
      const insights = page.locator('.er-insights'); assert((await insights.innerText()).includes('逐次报工 12 条'));
      assert((await insights.innerText()).includes('有效加工工时 3 小时')); assert(!(await insights.innerText()).includes('不能生成实际工时排名'));
      assert.equal(await page.locator('.er-chart-disclosure .rw-resource-table').count(), 1);
      for (const [kind, label] of [['machines', '设备'], ['people', '人员']]) {
        await page.getByRole('tablist', { name: '资源工时类型' }).getByRole('tab', { name: label, exact: true }).click();
        const values = await page.locator('.er-chart-disclosure .rw-resource-table tbody tr').evaluateAll(nodes => nodes.map(node => Array.from(node.cells).map(cell => cell.textContent)));
        assert.equal(values.length, dto.data.resources[kind].length);
        dto.data.resources[kind].forEach((row, rowIndex) => assert.deepEqual(values[rowIndex], [row.resource_label, row.operations, row.events, row.production_reports, row.records, row.effective_processing_hours, row.known_effective_processing_hours, row.unknown_hour_events].map(v => v === null ? '未知' : String(v))));
      }
      await page.locator('.er-chart-disclosure').scrollIntoViewIfNeeded(); await shot(page, prefix + '-review');
      const chartPoints = await page.locator('.aw-actual circle title').allTextContents(); assert.equal(chartPoints.length, dto.data.charts.trend.filter(row => row.actual !== null).length);
      await page.locator('.aw-data > summary').click();
      const trend = await page.locator('.aw-data tbody tr').evaluateAll(nodes => nodes.map(node => Array.from(node.cells).map(cell => cell.textContent)));
      assert.deepEqual(trend, dto.data.charts.trend.map(row => [row.date, String(row.planned), row.actual === null ? '未知' : String(row.actual)]));
      await shot(page, prefix + '-chart-data');
      dto = await change(page, () => page.getByRole('tab', { name: '报表中心', exact: true }).click()); assert.equal(dto.data.scope.resource_ref, ready.expected.machine2);
      dto = await change(page, () => page.getByRole('button', { name: '清除筛选', exact: true }).click()); assert.equal(dto.data.summary.operations, 23);
      await page.getByRole('searchbox', { name: '搜索批次或工序' }).fill('no-such-operation');
      dto = await change(page, () => page.getByRole('button', { name: '查询范围', exact: true }).click()); assert.equal(dto.data.page.total, 0);
      assert.equal(await page.getByRole('button', { name: /^导出范围/ }).isDisabled(), true);
      const fresh = page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/analytics' && response.status() === 200);
      await page.evaluate(snapshot_ref => remountReports({ snapshot_ref }), ready.expected.stale_snapshot);
      const freshResponse = await fresh;
      assert.equal(new URL(freshResponse.url()).searchParams.has('snapshot_ref'), false);
      dto = await freshResponse.json();
      await compare(page, dto, prefix + '-legacy-token-new-read');
      evidence.cases.push({ width, theme, layout, real_api_comparisons: true, pagination: true, revisions: true, legacy_original: true, exports: true, sort: true,
        combined_filter: true, cohort_resources: true, legacy_token_ignored_on_reentry: true, chart_points: chartPoints });
      await context.close();
    }
    assert.deepEqual(evidence.errors, []); assert.deepEqual(evidence.external, []);
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
}
main().catch(error => { evidence.failure = error.stack; console.error(error); process.exitCode = 1; })
  .finally(() => fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(evidence, null, 2)));
