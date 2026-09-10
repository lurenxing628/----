/* CY: compiled source, real SQLite APIs, real controls and transport-only faults. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const config = JSON.parse(fs.readFileSync(0, 'utf8')), output = process.argv[2], root = path.resolve(__dirname, '../..');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
assert.equal(hash(fs.readFileSync(path.join(__dirname, 'fixtures/schema-v28.sql'))), '2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const names = ['WorkbenchPageContext.jsx', 'WorkbenchCaption.jsx', 'DashboardContract.js', 'DashboardAnalysisAPI.js', 'DashboardCandidateComparisonAPI.js',
  'DashboardTimelineModel.js', 'DashboardTimeline.jsx', 'DashboardAnalysisPanels.jsx', 'DashboardCandidatePanels.jsx', 'DashboardCandidates.jsx',
  'DashboardSession.js', 'DashboardStyles.jsx', 'DashboardPanels.jsx', 'DashboardHistory.jsx', 'DashboardHandling.jsx', 'DashboardWorkspace.jsx'];
const sources = names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true }).outputs;
const scripts = new Map(compiled.map(row => ['/probe/' + row.path, row.code]));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, content: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const report = { compile_global_build: false, sources: sources.map(s => ({ path: 'frontend/workbench/' + s.path, sha256: hash(s.code) })),
  cases: [], boundaries: {}, screenshots: [], errors: [], external: [], responses: [], navigation: [], restarts: 0, contract_rejections: 0 };
const boot = `function CYApp(){
  const [target,setTarget]=React.useState({view:'dashboard',context:{scope:{size:2}}});
  const navigate=(view,context)=>{window.cyNavigation={view,context};setTarget({view,context});};
  const context=target.context, props={initialContext:context,onNavigate:navigate};
  const body=target.view==='dashboard'?React.createElement(window.WorkbenchDashboardWorkspace,props):
    target.view==='field'?React.createElement(window.FieldWorkspace,props):
    target.view==='fieldgantt'?React.createElement(window.ActualGanttWorkspace,props):
    target.view==='batches'?React.createElement(window.BatchWorkspace,{...props,onNav:navigate,adapter:window.APSBatchAPI.create()}):
    React.createElement(window.PlanCenterWorkspace,{...props,view:target.view});
  return React.createElement(React.Fragment,null,React.createElement(window.WorkbenchControlStyles),React.createElement(window.WorkbenchControls),React.createElement(window.WorkbenchNumberControls),
    React.createElement(AppShell,{active:'dashboard',title:'计划员值班台',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
    target.view!=='dashboard'&&React.createElement('button',{type:'button','data-fixture-return':true,onClick:()=>navigate('dashboard',context.return_to.context)},'返回原值班台'),body));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(CYApp));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(f => '<link rel="stylesheet" href="/static/' + f + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(f => !f.endsWith('/main.js') && !f.endsWith('/WorkbenchCaption.js') && !/\/Dashboard[^/]*\.js$/.test(f)).map(f => '<script src="/static/' + f + '"></script>').join('') +
  compiled.map(r => '<script src="/probe/' + r.path + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
let fault = '', blockReceipts = false;
const commandPath = p => /\/items\/[a-f0-9]{48}\/(transition|reopen)$/.test(p);
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const a = assets.get(url.pathname); response.setHeader('Content-Type', a.mime); return response.end(a.content); }
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/__dashboard_fixture__/')) {
    if (url.pathname.startsWith('/api/workbench/v1/commands/') && blockReceipts || commandPath(url.pathname) && fault === 'before') return response.destroy();
    const chunks = []; request.on('data', d => chunks.push(d)); request.on('end', () => {
      const body = Buffer.concat(chunks), upstream = http.request(config.api_origin + request.url, { method: request.method, headers: { cookie: request.headers.cookie || '',
        ...(body.length ? { 'Content-Type': 'application/json', 'Content-Length': body.length } : {}) } }, incoming => {
        const parts = []; incoming.on('data', d => parts.push(d)); incoming.on('end', () => {
          const content = Buffer.concat(parts);
          if ((incoming.headers['content-type'] || '').includes('application/json')) report.responses.push({ path: url.pathname, query: Object.fromEntries(url.searchParams),
            status: incoming.statusCode, method: request.method, input: body.length ? JSON.parse(body.toString()) : null, payload: JSON.parse(content.toString()) });
          if (commandPath(url.pathname) && fault === 'after') return response.destroy();
          if (commandPath(url.pathname) && fault === 'malformed') { response.writeHead(200, { 'Content-Type': 'application/json' }); return response.end('{"ok":true}'); }
          response.writeHead(incoming.statusCode, incoming.headers); response.end(content);
        });
      }); upstream.on('error', e => { report.errors.push(e.message); response.destroy(); }); upstream.end(body);
    }); return;
  }
  response.writeHead(404); response.end();
});
let browser, origin, activePage;
async function launch() { return chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] }); }
async function shot(page, name) { const file = path.join(output, name + '.png'); await page.screenshot({ path: file, animations: 'disabled' }); report.screenshots.push(file); }
async function listAction(page, action, ok = true) {
  const wait = page.waitForResponse(r => new URL(r.url()).pathname === '/api/workbench/v1/dashboard'); await action(); const r = await wait;
  if (ok) { assert.equal(r.status(), 200, await r.text()); await page.locator('[data-dashboard-workspace][data-ready=true]').waitFor(); }
  return r.json();
}
async function fresh(name, viewport = { width: 1392, height: 924 }, theme = 'light', storageState) {
  const context = await browser.newContext({ viewport, ...(storageState ? { storageState } : {}) });
  await context.addCookies([{ name: 'cy_case', value: name, url: origin }]);
  await context.addInitScript(t => { localStorage.setItem('aps_theme', t); localStorage.setItem('aps_kit_theme', t); }, theme);
  const page = await context.newPage(); activePage = page; page.on('pageerror', e => report.errors.push(e.message));
  await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
  const data = await listAction(page, () => page.goto(origin), name !== 'missing'); return { context, page, data };
}
async function select(page, label, option) { await page.getByLabel(label, { exact: true }).click(); await page.locator('.wb-control-popup').getByRole('option', { name: option, exact: true }).click(); }
async function category(page, name) { return listAction(page, () => page.locator('.dy-rail').getByRole('button', { name: new RegExp('^' + name) }).click()); }
async function detail(page, kind = 'delivery') {
  const labels = { delivery: '交期风险', actual: '执行偏差', material: '齐套缺口', downtime: '停机影响' };
  await category(page, labels[kind]); const row = page.locator('tr[data-category="' + kind + '"]').first();
  const wait = page.waitForResponse(r => /\/dashboard\/items\/[a-f0-9]{48}$/.test(new URL(r.url()).pathname));
  await row.getByRole('button').click(); const r = await wait; assert.equal(r.status(), 200); await page.locator('[data-detail-ref]').waitFor(); return (await r.json()).data.item;
}
async function openHandling(page) { await page.locator('[aria-label="条目详情"]').getByRole('button', { name: '登记处置', exact: true }).click(); await page.getByRole('dialog').waitFor(); }
async function fillHandling(page, status, remark, complete) {
  await select(page, '目标处置状态', status); const dialog = page.getByRole('dialog');
  await dialog.getByLabel('责任人', { exact: true }).fill('计划员李工'); await dialog.getByLabel('责任期限', { exact: true }).fill('2026-09-11');
  await dialog.getByLabel('处置行动', { exact: true }).fill('核对精车安排及齐套，协调设备检修后复核交期');
  await dialog.getByLabel('原因 / 核实备注', { exact: true }).fill(remark);
  if (complete) { await dialog.getByLabel('完成时间', { exact: true }).fill('2026-09-10T11:00:17'); await dialog.getByLabel('具体完成结果', { exact: true }).fill(complete.result); await dialog.getByLabel('可核对凭据', { exact: true }).fill(complete.evidence); }
}
async function send(page, reopen = false) {
  const wait = page.waitForResponse(r => commandPath(new URL(r.url()).pathname));
  await page.getByRole('dialog').getByRole('button', { name: reopen ? '确认独立重开' : '提交处置', exact: true }).click(); return wait;
}
async function confirmed(page) { await page.getByRole('dialog').getByText(/^已确认：/).waitFor(); }
async function finish(page) { await listAction(page, () => page.getByRole('dialog').getByRole('button', { name: '完成核实并刷新', exact: true }).click()); }
async function historyTab(page) { const wait = page.waitForResponse(r => /\/dashboard\/items\/[a-f0-9]{48}\/history$/.test(new URL(r.url()).pathname)); await page.getByRole('tab', { name: '处置历史', exact: true }).click(); assert.equal((await wait).status(), 200); await page.locator('[data-history-sequence]').first().waitFor(); }
async function geometry(page, viewport) {
  const g = await page.evaluate(() => {
    const workspace = document.querySelector('[data-dashboard-workspace]'), rect = node => { const r = node.getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width }; };
    const dialog = document.querySelector('.dashboard-live [role=dialog]');
    const text = Array.from(workspace.querySelectorAll('button,input,select,textarea,td,dd')).filter(n => n.getClientRects().length);
    return { width: document.documentElement.scrollWidth, workspace: rect(workspace), theme: document.documentElement.dataset.theme,
      clipped: text.filter(n => n.scrollWidth > n.clientWidth + 3 && !n.matches('textarea,input,select')).map(n => n.textContent),
      darkBlack: text.filter(n => getComputedStyle(n).color === 'rgb(0, 0, 0)').map(n => n.textContent),
      dialog: dialog ? rect(dialog) : null, colors: ['.dy-section-head', '.dy-tabs', '.dy-panel'].map(s => getComputedStyle(workspace.querySelector(s)).backgroundColor) };
  });
  assert(g.width <= viewport.width, JSON.stringify(g)); assert(g.workspace.width > viewport.width * .7, JSON.stringify(g)); assert.deepEqual(g.clipped, []);
  if (g.theme === 'dark') assert.deepEqual(g.darkBlack, []);
  if (g.dialog) assert(g.dialog.x >= 0 && g.dialog.right <= viewport.width && g.dialog.y >= 0 && g.dialog.bottom <= viewport.height);
  return g;
}
async function mutateContracts(page, list, row, receipt, intent) {
  return page.evaluate(({ list, row, receipt, intent }) => {
    const C = window.DashboardContract; let rejected = 0;
    const mutations = [v => { v.meta.source = 'demo'; }, v => { v.data.scope.query = 'other'; }, v => { v.data.categories.external.risk_count = v.data.categories.external.known_risk_count + 1; },
      v => { v.data.items[0].risk.active = 'false'; }, v => { v.data.items[0].handling.status = 'done'; }, v => { v.data.page.total++; }, v => { v.data.resource_pressure.plan_ref = 'f'.repeat(48); }];
    const q = { ...list.data.scope, page: list.data.page.number }; delete q.kind;
    for (const change of mutations) { const v = JSON.parse(JSON.stringify(list)); change(v); try { C.catalog(v, q); } catch (_) { rejected++; } }
    for (const change of [v => { v.data.item_ref = 'f'.repeat(48); }, v => { v.data.handling.owner = '替代责任人'; }, v => { delete v.receipt_ref; }, v => { v.data.risk.active = false; }]) {
      const v = JSON.parse(JSON.stringify(receipt)); change(v); try { C.receipt(v, intent); } catch (_) { rejected++; }
    }
    return rejected;
  }, { list, row, receipt, intent });
}
async function navigateAndReturn(page, button, target, expectedPath) {
  const wait = page.waitForResponse(r => new URL(r.url()).pathname.startsWith(expectedPath));
  await button.click(); const response = await wait; assert.equal(response.status(), 200, await response.text());
  const nav = await page.evaluate(() => window.cyNavigation); assert.equal(nav.view, target); assert.equal(nav.context.return_to.view, 'dashboard');
  report.navigation.push(nav); await listAction(page, () => page.locator('[data-fixture-return]').click());
}
async function filtersAndTabs(page) {
  let data = await listAction(page, () => select(page, '处置状态', '已关闭')); assert.equal(data.data.page.total, 0);
  data = await listAction(page, () => select(page, '处置状态', '未关闭')); assert.equal(data.data.page.total, 29);
  await listAction(page, () => select(page, '排序', '责任期限'));
  data = await listAction(page, () => page.getByRole('button', { name: '改为降序', exact: true }).click()); assert.equal(data.data.scope.direction, 'desc');
  data = await listAction(page, () => select(page, '每页条目数', '10')); assert.equal(data.data.items.length, 10);
  await listAction(page, () => select(page, '排序', '对象')); await listAction(page, () => page.getByRole('button', { name: '改为升序', exact: true }).click());
  await listAction(page, () => page.getByRole('button', { name: '清除条目筛选', exact: true }).click());
  data = await category(page, '外协回厂');
  assert.equal(data.data.categories.external.state, 'no_data');
  assert.equal(data.data.categories.external.risk_count, 0); assert.equal(data.data.categories.external.unknown_count, 0);
  assert.equal(data.data.categories.external.receipt_count, 0); assert.equal(data.data.categories.external.entry.enabled, true);
  assert.equal(await page.locator('.dy-metric').filter({ hasText: '外协回厂' }).locator('strong').innerText(), '0');
  await category(page, '全部风险'); await page.getByRole('tab', { name: '处置清单', exact: true }).focus(); await page.keyboard.press('ArrowRight');
  assert.equal(await page.getByRole('tab', { name: '影响分析', exact: true }).getAttribute('aria-selected'), 'true'); await page.keyboard.press('Home');
  await listAction(page, () => page.reload());
}
async function happy(viewport, theme) {
  const name = theme + '-' + viewport.width, complete = { result: '现场复核完成，检修窗口与工序调整方案已签认 ' + name, evidence: '车间协调单 CY-20260910-' + name };
  let { context, page, data } = await fresh(name, viewport, theme);
  assert.deepEqual(['delivery', 'actual', 'downtime', 'material'].map(k => data.data.categories[k].known_risk_count > 0), [true, true, true, true]);
  const firstGeometry = await geometry(page, viewport); await shot(page, name + '-overview');
  const second = await listAction(page, () => page.getByRole('button', { name: '清单下一页', exact: true }).click()); assert.equal(second.meta.snapshot_ref, data.meta.snapshot_ref);
  await listAction(page, () => page.getByRole('button', { name: '清单上一页', exact: true }).click());
  await page.getByLabel('搜索条目、责任人、行动或备注', { exact: true }).fill('不存在的条目');
  const empty = await listAction(page, () => page.getByRole('button', { name: '执行条目搜索', exact: true }).click()); assert.equal(empty.data.page.total, 0); await page.getByText(/当前筛选没有条目/).waitFor();
  await listAction(page, () => page.getByRole('button', { name: '清除条目筛选', exact: true }).click());
  await filtersAndTabs(page);
  await page.getByRole('tab', { name: '影响分析', exact: true }).click(); await page.getByRole('heading', { name: '正式计划资源压力' }).waitFor();
  assert.equal(await page.locator('[data-resource-ref]').count(), data.data.resource_pressure.resources.length); await shot(page, name + '-pressure');
  await navigateAndReturn(page, page.getByRole('button', { name: '计划甘特', exact: true }), 'gantt', '/api/workbench/v1/plans');
  await page.getByRole('tab', { name: '方案对比', exact: true }).click(); assert.equal(await page.locator('[data-run-ref]').count(), 1);
  assert.equal(await page.locator('[data-run-ref]').getAttribute('data-run-ref'), config.run_ref); await shot(page, name + '-candidates');
  await navigateAndReturn(page, page.getByRole('button', { name: '查看候选', exact: true }), 'analysis', '/api/workbench/v1/scheduling/runs/' + config.run_ref + '/candidates');
  await navigateAndReturn(page, page.getByRole('button', { name: '完整运行目录', exact: true }), 'analysis', '/api/workbench/v1/scheduling/runs');
  const material = await detail(page, 'material'); await page.locator('[data-detail-ref]').getByText('圆钢', { exact: true }).waitFor();
  await navigateAndReturn(page, page.locator('[data-detail-ref]').getByRole('button', { name: '批次资料', exact: true }), 'batches', '/api/workbench/v1/entities/batch/' + material.source.batch_ref);
  const actual = await detail(page, 'actual'); await navigateAndReturn(page, page.locator('[data-detail-ref]').getByRole('button', { name: '现场报工', exact: true }), 'field', '/api/workbench/v1/execution/tasks');
  assert.equal(report.navigation[report.navigation.length - 1].context.task_ref, actual.source.task_ref);
  await page.locator('[data-detail-ref]').waitFor(); await navigateAndReturn(page, page.locator('[data-detail-ref]').getByRole('button', { name: '现场实际', exact: true }), 'fieldgantt', '/api/workbench/v1/actual-gantt');
  await detail(page, 'downtime');
  const selected = await detail(page), ref = selected.item_ref; await openHandling(page);
  await page.keyboard.press('Escape'); await page.getByRole('dialog').waitFor({ state: 'hidden' }); await openHandling(page);
  await page.getByRole('dialog').getByRole('button', { name: '提交处置', exact: true }).click(); await page.getByRole('dialog').getByRole('alert').waitFor();
  await fillHandling(page, '跟进中', '首次核对正式交期及停机交集'); assert.equal((await send(page)).status(), 200); await confirmed(page);
  const intent = await page.evaluate(() => window.DashboardSession.read());
  if (!report.contract_rejections) report.contract_rejections = await mutateContracts(page, data, selected, intent.receipt, intent);
  await finish(page); await page.locator('[data-detail-ref="' + ref + '"]').waitFor(); await openHandling(page);
  await fillHandling(page, '待验证', '协调完成后交生产验证'); assert.equal((await send(page)).status(), 200); await confirmed(page); await finish(page);
  await historyTab(page); await page.getByRole('button', { name: '调整当前处置', exact: true }).click(); await fillHandling(page, '跟进中', '验证未通过，回到跟进补充证据');
  assert.equal((await send(page)).status(), 200); await confirmed(page); await finish(page); await page.locator('[data-history-sequence="3"]').waitFor();
  await page.getByRole('button', { name: '调整当前处置', exact: true }).click(); await fillHandling(page, '已关闭', '依据现场核验完成本轮处置', complete);
  await geometry(page, viewport); await shot(page, name + '-close-form'); fault = 'after'; blockReceipts = true;
  await page.getByRole('dialog').getByRole('button', { name: '提交处置', exact: true }).click(); await page.getByRole('dialog').getByText('结果尚未确认，仅查询原请求。', { exact: true }).waitFor();
  await page.getByRole('dialog').getByRole('button', { name: '查询原回执', exact: true }).waitFor();
  const pending = await page.evaluate(() => window.DashboardSession.read()); assert.equal(pending.phase, 'pending'); assert.equal(pending.item_ref, ref); assert(!JSON.stringify(pending).includes('write_token'));
  const savedState = await context.storageState(); await shot(page, name + '-unknown'); await context.close(); await browser.close(); browser = await launch(); report.restarts++;
  fault = ''; blockReceipts = false; ({ context, page } = await fresh(name, viewport, theme, savedState));
  await page.getByRole('button', { name: '查看已确认回执', exact: true }).waitFor(); await page.getByRole('button', { name: '查看已确认回执', exact: true }).click(); await confirmed(page);
  assert.equal((await page.evaluate(() => window.DashboardSession.read())).request_key, pending.request_key); await finish(page);
  const closed = await detail(page); assert.equal(closed.handling.status, 'closed'); assert.equal(closed.risk.active, true); assert.deepEqual(closed.allowed_transitions, []);
  await historyTab(page); await page.locator('[data-history-sequence="4"] summary').click(); await page.getByText(complete.evidence, { exact: true }).waitFor(); await shot(page, name + '-closed-history');
  const oldPage = page.waitForResponse(r => new URL(r.url()).searchParams.get('history_page') === '2'); await page.getByRole('button', { name: '历史下一页', exact: true }).click(); assert.equal((await oldPage).status(), 200);
  await page.locator('[data-history-sequence="1"]').waitFor(); await page.getByRole('button', { name: '查看第 1 次原始依据', exact: true }).click(); await page.getByText(/永久历史快照/).waitFor();
  await page.getByRole('button', { name: '独立重开', exact: true }).click(); const reason = '复查仍有交期风险，新增跟进 ' + name;
  await page.getByRole('dialog').getByLabel('重开原因', { exact: true }).fill(reason); const r = await send(page, true); assert.equal(r.status(), 200); await confirmed(page); await finish(page);
  await page.locator('[data-history-sequence="5"]').waitFor(); await shot(page, name + '-reopened');
  await page.getByRole('button', { name: '调整当前处置', exact: true }).click(); const noChange = await send(page); assert.equal((await noChange.json()).result, 'unchanged'); await confirmed(page); await finish(page);
  const reopening = report.responses.filter(r => r.path.endsWith('/reopen')).pop(); assert.deepEqual(Object.keys(reopening.input.input), ['reason']);
  report.cases.push({ name, viewport, theme, geometry: firstGeometry, completion_evidence: complete.result, evidence: complete.evidence, reopen_reason: reason, unknown_key: pending.request_key });
  await context.close();
}
async function boundaries() {
  let { context, page, data } = await fresh('missing'); await page.getByRole('alert').waitFor();
  assert.equal(data.error.code, 'dashboard_unavailable'); assert.equal(data.committed, false);
  assert(!/\b0\b/.test(await page.locator('.dy-metric').nth(2).innerText()));
  assert.equal(await page.locator('[data-item-ref]').count(), 0); report.boundaries.schema_missing = true; await shot(page, 'missing-schema'); await context.close();
  ({ context, page } = await fresh('no-official')); await page.getByText('当前无正式计划', { exact: true }).waitFor(); await category(page, '交期风险'); await page.getByText(/当前筛选没有条目/).waitFor();
  await page.getByRole('tab', { name: '方案对比', exact: true }).click(); assert.equal(await page.locator('[data-run-ref]').count(), 1); report.boundaries.no_official_not_candidate = true; await shot(page, 'no-official'); await context.close();
  ({ context, page, data } = await fresh('unknown')); assert.equal(data.data.categories.material.risk_count, null);
  assert.equal(data.data.categories.material.unknown_count, 1); assert.equal(await page.locator('.dy-metric').filter({ hasText: '齐套缺口' }).locator('strong').innerText(), '未知');
  await category(page, '齐套缺口'); await page.getByText(/齐套缺口 · 无法评估 1 项/).click(); await page.getByText(/齐套事实不完整/).waitFor();
  assert(!await page.locator('[data-item-ref]').filter({ hasText: '精密轴套' }).count()); report.boundaries.unknown_not_alarm = true; await shot(page, 'unknown-source'); await context.close();
  ({ context, page } = await fresh('no-data')); await page.getByRole('tab', { name: '方案对比', exact: true }).click(); await page.getByText('尚无排产运行记录。', { exact: true }).waitFor();
  report.boundaries.no_data_not_unloaded = true; await shot(page, 'no-data'); await context.close();
  for (const name of ['drift', 'rollback', 'lost', 'malformed']) {
    ({ context, page } = await fresh(name)); await detail(page); await openHandling(page); await fillHandling(page, '跟进中', '边界测试保留原请求 ' + name);
    if (name === 'drift' || name === 'rollback') assert.equal((await context.request.post(origin + '/__dashboard_fixture__/mutate')).status(), 200);
    if (name === 'lost') fault = 'before'; if (name === 'malformed') { fault = 'malformed'; blockReceipts = true; }
    if (name === 'lost') await page.getByRole('dialog').getByRole('button', { name: '提交处置', exact: true }).click(); else { const response = await send(page); assert.equal(response.status(), name === 'drift' ? 409 : name === 'rollback' ? 500 : 200); }
    if (name === 'drift') { await page.getByText('本次明确未写入。', { exact: true }).waitFor(); report.boundaries.stale_rejected = true; }
    else {
      await page.getByRole('dialog').getByText('结果尚未确认，仅查询原请求。', { exact: true }).waitFor();
      const pending = await page.evaluate(() => window.DashboardSession.read()); assert.equal(pending.phase, 'pending');
      assert.equal(await page.getByRole('button', { name: '提交处置', exact: true }).count(), 0);
      if (name === 'malformed') { fault = ''; blockReceipts = false; await page.getByRole('button', { name: '查询原回执', exact: true }).click(); await confirmed(page); report.boundaries.fetch200_not_confirmed = true; }
      else { await page.getByText(/尚未查到原回执/).waitFor(); report.boundaries[name === 'lost' ? 'not_recorded_retained' : 'transaction_rollback'] = true; }
    }
    await shot(page, name); fault = ''; blockReceipts = false; await context.close();
  }
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); origin = 'http://127.0.0.1:' + server.address().port;
  try {
    browser = await launch(); report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) await happy(viewport, theme);
    await boundaries(); assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } catch (error) { if (activePage && !activePage.isClosed()) { await shot(activePage, 'failure'); report.failure_text = await activePage.locator('body').innerText(); } throw error; }
  finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'dashboard-ui.json'), JSON.stringify(report, null, 2)); }
  console.log(JSON.stringify({ browser: report.browser, cases: report.cases.length, screenshots: report.screenshots.length, boundaries: report.boundaries }));
})().catch(error => { console.error(error); process.exitCode = 1; });
