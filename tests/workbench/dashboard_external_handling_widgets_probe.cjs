/* DX: real Chromium109, isolated production DTOs, no global build or main view. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const config = JSON.parse(fs.readFileSync(0, 'utf8')), output = process.argv[2], root = path.resolve(__dirname, '../..');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const names = ['WorkbenchPageContext.jsx', 'WorkbenchCaption.jsx', 'ResourceControls.jsx', 'WorkbenchControlStyles.jsx', 'WorkbenchControlBridge.js', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js',
  'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx', 'OutsourcingContract.js', 'OutsourcingSession.js', 'OutsourcingControls.jsx', 'OutsourcingStyles.jsx', 'OutsourcingWorkspace.jsx',
  'DashboardContract.js', 'DashboardAnalysisAPI.js', 'DashboardCandidateComparisonAPI.js', 'DashboardTimelineModel.js', 'DashboardTimeline.jsx',
  'DashboardAnalysisPanels.jsx', 'DashboardCandidatePanels.jsx', 'DashboardCandidates.jsx', 'DashboardSession.js', 'DashboardStyles.jsx',
  'DashboardPanels.jsx', 'DashboardHistory.jsx', 'DashboardHandling.jsx', 'DashboardWorkspace.jsx'];
const sources = names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true }).outputs;
const scripts = new Map(compiled.map(r => ['/probe/' + r.path, r.code]));
const assets = new Map(manifest.files.map(r => ['/static/' + r.path, { ...r, content: fs.readFileSync(path.join(root, 'static', r.path)) }]));
const report = { ...config, compile_global_build: false, sources: sources.map(s => ({ path: 'frontend/workbench/' + s.path, sha256: hash(s.code) })),
  cases: [], boundaries: {}, screenshots: [], errors: [], external: [], responses: [], restarts: 0, contract_rejections: 0 };
const replacements = new Map(compiled.map(r => [path.basename(r.path), r])), loaded = new Set();
const scriptTags = manifest.scripts.filter(f => !f.endsWith('/main.js')).map(f => {
  const current = replacements.get(path.basename(f));
  if (current) { loaded.add(current.path); return '<script src="/probe/' + current.path + '"></script>'; }
  return '<script src="/static/' + f + '"></script>';
}).join('') + compiled.filter(r => !loaded.has(r.path)).map(r => '<script src="/probe/' + r.path + '"></script>').join('');
const boot = `ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(React.Fragment,null,
React.createElement(window.WorkbenchControlStyles),React.createElement(window.WorkbenchControls),React.createElement(window.WorkbenchNumberControls),
React.createElement(AppShell,{active:'dashboard',title:'计划员值班台',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
React.createElement(window.WorkbenchDashboardWorkspace,{initialContext:{scope:{category:'external',size:2}},onNavigate:()=>{throw new Error('DX must not invent a main view');}}))));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(f => '<link rel="stylesheet" href="/static/' + f + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + scriptTags + '<script>' + boot + '</script></body></html>';
const base = '/api/workbench/v1/dashboard', logistics = '/api/workbench/v1/outsourcing/receipts';
const commandPath = p => /^\/api\/workbench\/v1\/dashboard\/items\/[a-f0-9]{48}\/(transition|reopen)$/.test(p);
let fault = '', blockReceipts = false;
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const a = assets.get(url.pathname); response.setHeader('Content-Type', a.mime); return response.end(a.content); }
  if (!url.pathname.startsWith('/api/') && !url.pathname.startsWith('/__dx_fixture__/')) { response.writeHead(404); return response.end(); }
  if (url.pathname.startsWith('/api/workbench/v1/commands/') && blockReceipts || commandPath(url.pathname) && fault === 'before') return response.destroy();
  const chunks = []; request.on('data', d => chunks.push(d)); request.on('end', () => {
    const body = Buffer.concat(chunks), upstream = http.request(config.api_origin + request.url, { method: request.method, headers: { cookie: request.headers.cookie || '',
      ...(body.length ? { 'Content-Type': 'application/json', 'Content-Length': body.length } : {}) } }, incoming => {
      const parts = []; incoming.on('data', d => parts.push(d)); incoming.on('end', () => {
        const content = Buffer.concat(parts);
        if ((incoming.headers['content-type'] || '').includes('application/json')) report.responses.push({ path: url.pathname, query: Object.fromEntries(url.searchParams), method: request.method,
          status: incoming.statusCode, input: body.length ? JSON.parse(body.toString()) : null, payload: JSON.parse(content.toString()) });
        if (commandPath(url.pathname) && fault === 'after') return response.destroy();
        if (commandPath(url.pathname) && fault === 'malformed') { response.writeHead(200, { 'Content-Type': 'application/json' }); return response.end('{"ok":true}'); }
        response.writeHead(incoming.statusCode, incoming.headers); response.end(content);
      });
    }); upstream.on('error', e => { report.errors.push(e.message); response.destroy(); }); upstream.end(body);
  });
});
let browser, origin, activePage;
const dialog = page => page.getByRole('dialog'), detail = page => page.locator('[data-detail-ref]');
async function launch() { return chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] }); }
async function shot(page, name) { const file = path.join(output, name + '.png'); await page.screenshot({ path: file, animations: 'disabled' }); report.screenshots.push(file); }
async function action(page, target, trigger, method = 'GET', status = 200) {
  const wait = page.waitForResponse(r => new URL(r.url()).pathname === target && r.request().method() === method);
  await trigger(); const r = await wait; assert.equal(r.status(), status, await r.text()); return r.json();
}
async function fresh(name, viewport = { width: 1392, height: 924 }, theme = 'light', storageState) {
  const context = await browser.newContext({ viewport, ...(storageState ? { storageState } : {}) });
  await context.addCookies([{ name: 'dx_case', value: name, url: origin }]);
  await context.addInitScript(t => { localStorage.setItem('aps_theme', t); localStorage.setItem('aps_kit_theme', t); }, theme);
  const page = await context.newPage(); activePage = page; page.on('pageerror', e => report.errors.push(e.message));
  await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
  const data = await action(page, base, () => page.goto(origin)); await page.locator('[data-dashboard-workspace][data-ready=true]').waitFor();
  await page.locator('[data-outsourcing-workspace][data-ready=true]').waitFor(); return { context, page, data };
}
async function select(page, label, option) {
  await page.getByLabel(label, { exact: true }).click(); const popup = page.locator('.wb-control-popup'), r = await popup.boundingBox(), v = page.viewportSize();
  assert(r && r.x >= 0 && r.y >= 0 && r.x + r.width <= v.width && r.y + r.height <= v.height);
  await popup.getByRole('option', { name: option, exact: true }).click(); report.boundaries.unified_select = true;
}
async function register(page) {
  const targets = '/api/workbench/v1/outsourcing/targets';
  await action(page, targets, () => page.getByRole('button', { name: '新建外协登记', exact: true }).click());
  await dialog(page).getByRole('radio', { name: '合并发出', exact: true }).check();
  for (const code of ['DN-O01', 'DN-O02']) {
    while (!await dialog(page).getByRole('button', { name:'工序上一页',exact:true }).isDisabled())
      await action(page, targets, () => dialog(page).getByRole('button', { name:'工序上一页',exact:true }).click());
    for (let i = 0; !await dialog(page).getByLabel('选择工序 ' + code, { exact: true }).count() && i < 2; i++)
      await action(page, targets, () => dialog(page).getByRole('button', { name:'工序下一页',exact:true }).click());
    await dialog(page).getByLabel('选择工序 ' + code, { exact: true }).check();
  }
  await dialog(page).getByLabel('实际发出', { exact: true }).fill('2026-09-07T09:00');
  await dialog(page).getByLabel('计划回厂', { exact: true }).fill('2026-09-09T12:00');
  await dialog(page).getByLabel('外协声明人', { exact: true }).fill('物流员张工');
  await dialog(page).getByLabel('外协核实原因', { exact: true }).fill('DX 实际合并发出，原单 WX-20260907-01');
  return saveLogistics(page, true);
}
async function saveLogistics(page, dashboard = false) {
  await action(page, logistics + '/preview', () => dialog(page).getByRole('button', { name: '预览核对', exact: true }).click(), 'POST');
  const result = await action(page, logistics, () => dialog(page).getByRole('button', { name: '确认保存外协登记', exact: true }).click(), 'POST');
  await dialog(page).getByText('已确认：外协登记已保存，回厂不等于工序完工。', { exact: true }).waitFor();
  await action(page, dashboard ? base : logistics, () => dialog(page).getByRole('button', { name: '完成核实并刷新', exact: true }).click());
  return result.data.outsourcing_ref;
}
async function choose(page, ref) {
  const row = page.locator(ref ? '[data-item-ref="' + ref + '"]' : 'tr[data-category="external"]').first();
  const selected = await row.getAttribute('data-item-ref');
  if (await row.getAttribute('data-selected') === 'true') {
    await page.locator('[data-detail-ref="' + selected + '"]').waitFor();
    return report.responses.filter(r => r.path === base + '/items/' + selected && r.status === 200).pop().payload.data.item;
  }
  const result = await action(page, base + '/items/' + selected, () => row.getByRole('button').click());
  await detail(page).waitFor(); return result.data.item;
}
async function open(page, closed = false) { await detail(page).getByRole('button', { name: closed ? '独立重开' : '登记处置', exact: true }).click(); await dialog(page).waitFor(); }
async function fillHandling(page, status, complete) {
  await select(page, '目标处置状态', status);
  await dialog(page).getByLabel('责任人', { exact: true }).fill('外协跟单员李工');
  await dialog(page).getByLabel('责任期限', { exact: true }).fill('2026-09-11');
  await dialog(page).getByLabel('处置行动', { exact: true }).fill('核实炉批，协调加急运输并跟进检验');
  await dialog(page).getByLabel('原因 / 核实备注', { exact: true }).fill('核对原登记与供应商签认，不替代回厂登记');
  if (complete) {
    await dialog(page).getByLabel('完成时间', { exact: true }).fill('2026-09-10T11:00:17');
    await dialog(page).getByLabel('具体完成结果', { exact: true }).fill(complete.result);
    await dialog(page).getByLabel('可核对凭据', { exact: true }).fill(complete.evidence);
  }
}
async function submit(page, ref, reopen = false, status = 200) {
  return action(page, base + '/items/' + ref + '/' + (reopen ? 'reopen' : 'transition'),
    () => dialog(page).getByRole('button', { name: reopen ? '确认独立重开' : '提交处置', exact: true }).click(), 'POST', status);
}
async function finish(page) { await dialog(page).getByText(/^已确认：/).waitFor(); return action(page, base, () => dialog(page).getByRole('button', { name: '完成核实并刷新', exact: true }).click()); }
async function reload(page) { return action(page, base, () => page.getByRole('button', { name: '明确刷新值班台', exact: true }).click()); }
async function geometry(page) {
  const g = await page.evaluate(() => {
    const w = document.querySelector('.dashboard-live'), d = w.querySelector('[role=dialog]'), rect = n => { const r = n.getBoundingClientRect(); return { x:r.x,y:r.y,right:r.right,bottom:r.bottom }; };
    const nodes = [...w.querySelectorAll('button,td,dd,label')].filter(n => n.getClientRects().length);
    return { width:document.documentElement.scrollWidth, theme:document.documentElement.dataset.theme,
      clipped:nodes.filter(n => n.scrollWidth > n.clientWidth + 3).map(n => n.textContent),
      black:nodes.filter(n => getComputedStyle(n).color === 'rgb(0, 0, 0)').map(n => n.textContent), dialog:d ? rect(d) : null };
  });
  const v = page.viewportSize(); assert(g.width <= v.width, JSON.stringify(g)); assert.deepEqual(g.clipped, []);
  if (g.theme === 'dark') assert.deepEqual(g.black, []);
  if (g.dialog) assert(g.dialog.x >= 0 && g.dialog.y >= 0 && g.dialog.right <= v.width && g.dialog.bottom <= v.height, JSON.stringify(g));
  return g;
}
async function history(page, ref) {
  const response = await action(page, base + '/items/' + ref + '/history', () => page.getByRole('tab', { name: '处置历史', exact: true }).click());
  await page.locator('[data-history-sequence]').first().waitFor(); return response;
}
async function happy(viewport, theme) {
  const name = theme + '-' + viewport.width, complete = { result:'加急承运与检验安排已签认，尚未回厂 ' + name, evidence:'外协协调单 DX-20260910-' + name };
  let { context, page, data } = await fresh(name, viewport, theme);
  assert.equal(data.data.categories.external.handling_supported, true); assert.equal(data.data.categories.external.risk_count, null);
  const outsourcingRef = await register(page), selected = await choose(page), ref = selected.item_ref;
  assert.equal(selected.source.outsourcing_ref, outsourcingRef); assert.equal(selected.source.target_kind, 'merged'); assert.equal(selected.risk.active, true);
  await detail(page).scrollIntoViewIfNeeded(); await geometry(page); await shot(page, name + '-separate-facts');
  await open(page); await dialog(page).getByRole('button', { name: '提交处置', exact: true }).click(); await dialog(page).getByRole('alert').waitFor();
  await fillHandling(page, '跟进中'); await submit(page, ref); await finish(page); await detail(page).waitFor();
  await open(page); await fillHandling(page, '待验证'); await submit(page, ref); await finish(page); await detail(page).waitFor();
  await open(page); await fillHandling(page, '已关闭', complete); await geometry(page); await shot(page, name + '-close-form');
  const timeInput = dialog(page).getByLabel('完成时间', { exact:true }), timeBounds = await timeInput.boundingBox();
  await timeInput.click({ position:{ x:timeBounds.width - 12,y:timeBounds.height / 2 } });
  const picker = page.locator('.wb-control-popup'); await picker.getByRole('button', { name:'增加秒', exact:true }).click();
  const bounds = await picker.boundingBox(); assert(bounds.x >= 0 && bounds.y >= 0 && bounds.x + bounds.width <= viewport.width && bounds.y + bounds.height <= viewport.height);
  await shot(page, name + '-datetime-control'); await picker.getByRole('button', { name:'确定', exact:true }).click();
  assert.equal(await dialog(page).getByLabel('完成时间', { exact:true }).inputValue(), '2026-09-10T11:00:18'); report.boundaries.unified_datetime = true;
  fault = 'after'; blockReceipts = true;
  await dialog(page).getByRole('button', { name: '提交处置', exact: true }).click();
  await dialog(page).getByText('结果尚未确认，仅查询原请求。', { exact: true }).waitFor();
  const pending = await page.evaluate(() => window.DashboardSession.read()); assert.equal(pending.phase, 'pending'); assert.equal(pending.item_ref, ref);
  assert(!JSON.stringify(pending).includes('write_token')); await shot(page, name + '-original-key-unknown');
  const savedState = await context.storageState(); await context.close(); await browser.close(); browser = await launch(); report.restarts++;
  fault = ''; blockReceipts = false; ({ context, page } = await fresh(name, viewport, theme, savedState));
  await page.getByRole('button', { name: '查看已确认回执', exact: true }).waitFor();
  assert.equal((await page.evaluate(() => window.DashboardSession.read())).request_key, pending.request_key);
  await page.getByRole('button', { name: '查看已确认回执', exact: true }).click(); await finish(page);
  const closed = await choose(page, ref); assert.equal(closed.handling.status, 'closed'); assert.equal(closed.risk.active, true);
  assert.equal(closed.source.receipt.returned, null); assert.equal(closed.source.receipt.confirmedState, 'in_transit');
  const summary = report.responses.filter(r => r.path === base).pop().payload.data.categories.external;
  assert.equal(summary.awaiting_return_count, 1); assert.equal(summary.overdue_count, 1); assert.equal(summary.known_risk_count, 1); assert.equal(summary.closed_count, 1);
  report.contract_rejections += await page.evaluate(row => {
    let n = 0; const C = window.DashboardContract;
    for (const mutate of [v => { v.navigation[0].context.outsourcing_ref='f'.repeat(48); }, v => { v.navigation[0].view='batches'; },
      v => { v.navigation[0].context.batch_ref='f'.repeat(48); }, v => { v.source.outsourcing_ref='f'.repeat(48); }, v => { v.risk.active='false'; }]) {
      const v = JSON.parse(JSON.stringify(row)); mutate(v); try { C.item(v); } catch (_) { n++; }
    } return n;
  }, closed);
  await detail(page).scrollIntoViewIfNeeded(); await shot(page, name + '-closed-risk-active');
  await action(page, base, () => select(page, '处置状态', '已关闭')); await choose(page, ref);
  await detail(page).getByRole('button', { name:'原外协物流登记', exact:true }).click();
  assert.equal(await page.locator('[data-dashboard-outsourcing]').getAttribute('data-return-item'), ref);
  await page.locator('[data-outsourcing-detail="' + outsourcingRef + '"]').waitFor();
  await page.getByRole('button', { name:'返回原值班台条目', exact:true }).click();
  assert.equal(await detail(page).getAttribute('data-detail-ref'), ref); assert.equal(await page.getByLabel('处置状态', { exact:true }).inputValue(), 'closed');
  await detail(page).getByRole('button', { name:'原外协物流登记', exact:true }).click();
  await page.locator('[data-outsourcing-detail="' + outsourcingRef + '"]').getByRole('button', { name:'核实 / 更正登记', exact:true }).click();
  await dialog(page).getByLabel('实际回厂', { exact:true }).fill('2026-09-10T11:40'); await select(page, '外协确认状态', '已回厂');
  await dialog(page).getByLabel('外协声明人', { exact:true }).fill('收货员王工');
  await dialog(page).getByLabel('外协核实原因', { exact:true }).fill('原批次两件回厂，收货单 DX-RETURN-01，不登记工序完工');
  await saveLogistics(page); await page.getByRole('button', { name:'返回原值班台条目', exact:true }).click();
  await page.getByText(/原物流登记已更新/).waitFor(); assert.equal(await detail(page).getAttribute('data-detail-ref'), ref);
  const returnedList = await reload(page); assert.equal(returnedList.data.categories.external.returned_count, 1); assert.equal(returnedList.data.categories.external.known_risk_count, 0);
  const returned = await choose(page, ref); assert.equal(returned.risk.active, false); assert.equal(returned.handling.history_count, 3); assert.equal(returned.handling.status, 'closed');
  assert.equal(returned.handling.completion_evidence, complete.result);
  await detail(page).scrollIntoViewIfNeeded(); await shot(page, name + '-returned-risk-resolved'); await history(page, ref);
  await page.locator('[data-history-sequence="3"] summary').click(); await page.getByText(complete.evidence, { exact:true }).waitFor();
  await page.getByRole('button', { name:'查看第 3 次原始依据', exact:true }).click(); await page.getByText(/永久历史快照/).waitFor();
  await page.locator('[data-history-sequence="3"]').scrollIntoViewIfNeeded(); await geometry(page); await shot(page, name + '-returned-history-preserved');
  await page.getByRole('tab', { name:'处置清单', exact:true }).click(); await action(page, base, () => select(page, '处置状态', '全部状态')); await choose(page, ref);
  await open(page, true); const reason = '继续跟进回厂检验，旧完成证据独立保留 ' + name;
  await dialog(page).getByLabel('重开原因', { exact:true }).fill(reason); const reopened = await submit(page, ref, true);
  assert.deepEqual(reopened.data.handling.completed_at, null); assert.equal(reopened.data.handling.status, 'following'); await finish(page);
  const histories = await history(page, ref); assert.equal(histories.data.item.item_ref, ref); assert.equal(histories.data.history.page.total, 4);
  assert.equal(histories.data.history.items.find(h => h.sequence === 3).after.completion_evidence, complete.result);
  await page.locator('[data-history-sequence="4"]').scrollIntoViewIfNeeded(); await geometry(page); await shot(page, name + '-reopened');
  await page.getByRole('button', { name:'历史下一页', exact:true }).click(); await page.locator('[data-history-sequence="1"]').waitFor();
  await page.getByRole('tab', { name:'处置清单', exact:true }).click(); await detail(page).getByRole('button', { name:'原外协物流登记', exact:true }).click();
  await page.getByRole('button', { name:'返回原值班台条目', exact:true }).click(); await history(page, ref); await page.locator('[data-history-sequence="1"]').waitFor();
  report.boundaries.original_navigation_and_history_page = true;
  report.cases.push({ name, viewport, theme, item_ref:ref, outsourcing_ref:outsourcingRef, unknown_key:pending.request_key, completion_evidence:complete.result, evidence:complete.evidence, reopen_reason:reason });
  await context.close();
}
async function boundaries() {
  for (const name of ['current30', 'missing']) {
    const { context, page, data } = await fresh(name); assert.equal(data.data.categories.external.handling_supported, false);
    await page.getByText(/处置数量未知，未显示为零/).waitFor(); assert.equal(await page.getByRole('tab', { name:'处置历史', exact:true }).count(), 0);
    await register(page); assert.equal(await page.locator('tr[data-category="external"]').count(), 0);
    if (name === 'missing') { assert.equal(data.data.categories.external.handling_state, 'unavailable'); assert.equal(data.data.categories.external.handling_count, null); }
    await geometry(page); await shot(page, name + '-unsupported'); report.boundaries[name] = true; await context.close();
  }
  for (const name of ['unknown', 'lost', 'malformed', 'stale']) {
    const { context, page } = await fresh(name); await register(page); const item = await choose(page), ref = item.item_ref;
    await open(page); await fillHandling(page, '跟进中');
    if (name === 'unknown') {
      await submit(page, ref); await finish(page); assert.equal((await context.request.post(origin + '/__dx_fixture__/mutate')).status(), 200);
      await reload(page); const unknown = await choose(page, ref); assert.equal(unknown.risk.active, null); assert.equal(unknown.source_state, 'not_currently_evaluated');
      const navigation = detail(page).getByRole('button', { name:/^原外协物流登记/ });
      const beforeNavigation = report.responses.length;
      assert.equal(await navigation.isEnabled(), true); await navigation.click();
      const confirmation = page.getByRole('dialog', { name:'原对象暂不可定位', exact:true });
      await confirmation.getByText(unknown.navigation.find(n => n.view === 'outsourcing').reason, { exact:true }).waitFor();
      assert((await confirmation.innerText()).includes(ref));
      assert.equal(await confirmation.getByRole('button', { name:'打开外协物流登记概览', exact:true }).isEnabled(), true);
      await confirmation.getByRole('button', { name:'取消', exact:true }).click(); await confirmation.waitFor({ state:'hidden' });
      assert.equal(await detail(page).getAttribute('data-detail-ref'), ref);
      assert.equal(await page.locator('[data-dashboard-outsourcing]').count(), 0);
      assert.equal(report.responses.length, beforeNavigation, 'Unlocatable confirmation/cancel must not navigate or submit');
      await history(page, ref); await page.locator('[data-history-sequence="1"]').waitFor(); report.boundaries.unknown_not_guessed = true;
    } else {
      if (name === 'stale') assert.equal((await context.request.post(origin + '/__dx_fixture__/mutate')).status(), 200);
      if (name === 'lost') fault = 'before'; if (name === 'malformed') { fault = 'malformed'; blockReceipts = true; }
      if (name === 'lost') await dialog(page).getByRole('button', { name:'提交处置', exact:true }).click(); else await submit(page, ref, false, name === 'stale' ? 409 : 200);
      if (name === 'stale') { await page.getByText('本次明确未写入。', { exact:true }).waitFor(); report.boundaries.stale_rejected = true; }
      else {
        await dialog(page).getByText('结果尚未确认，仅查询原请求。', { exact:true }).waitFor();
        const pending = await page.evaluate(() => window.DashboardSession.read()); assert.equal(pending.phase, 'pending');
        assert.equal(await dialog(page).getByRole('button', { name:'提交处置', exact:true }).count(), 0);
        if (name === 'lost') { await page.getByText(/尚未查到原回执/).waitFor(); await page.reload(); await page.getByRole('button', { name:'核实原处置请求', exact:true }).click();
          assert.equal((await page.evaluate(() => window.DashboardSession.read())).request_key, pending.request_key); report.boundaries.not_recorded_original_key = true; }
        else { fault = ''; blockReceipts = false; await page.getByRole('button', { name:'查询原回执', exact:true }).click(); await dialog(page).getByText(/^已确认：/).waitFor(); report.boundaries.malformed_not_success = true; }
      }
    }
    await shot(page, name); fault = ''; blockReceipts = false; await context.close();
  }
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); assert(![52392,58448,64612].includes(server.address().port)); origin = 'http://127.0.0.1:' + server.address().port;
  try {
    browser = await launch(); report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    for (const viewport of [{ width:1920,height:1080 }, { width:1392,height:924 }]) for (const theme of ['light','dark']) await happy(viewport, theme);
    await boundaries(); assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } catch (error) { if (activePage && !activePage.isClosed()) { await shot(activePage, 'failure'); report.failure_text = await activePage.locator('body').innerText(); } throw error; }
  finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'dashboard-external-ui.json'), JSON.stringify(report, null, 2)); }
  console.log(JSON.stringify({ browser:report.browser,cases:report.cases.length,screenshots:report.screenshots.length,boundaries:report.boundaries }));
})().catch(error => { console.error(error); process.exitCode = 1; });
