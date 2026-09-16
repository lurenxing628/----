/* DN: real Chromium109, local production APIs and transport-only fault injection. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const config = JSON.parse(fs.readFileSync(0, 'utf8')), output = process.argv[2], root = path.resolve(__dirname, '../..');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const names = ['WorkbenchPageContext.jsx', 'WorkbenchCaption.jsx', 'WorkbenchGuards.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'WorkbenchControlStyles.jsx', 'WorkbenchControlBridge.js', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js',
  'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchNumberControls.jsx', 'OutsourcingContract.js', 'OutsourcingSession.js', 'OutsourcingControls.jsx', 'OutsourcingStyles.jsx', 'OutsourcingWorkspace.jsx',
  'DashboardContract.js', 'DashboardAnalysisAPI.js', 'DashboardCandidateComparisonAPI.js', 'DashboardTimelineModel.js', 'DashboardTimeline.jsx',
  'DashboardAnalysisPanels.jsx', 'DashboardCandidatePanels.jsx', 'DashboardCandidates.jsx', 'DashboardSession.js', 'DashboardStyles.jsx',
  'DashboardPanels.jsx', 'DashboardHistory.jsx', 'DashboardHandling.jsx', 'DashboardWorkspace.jsx'];
const sources = names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const styleSources = ['00-tokens.css', '21-table-frame.css', '22-shared-controls.css', '32-calendar-outsourcing.css'].map(name =>
  ({ path: 'app/styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true }).outputs;
const scripts = new Map(compiled.map(r => ['/probe/' + r.path, r.code]));
const assets = new Map(manifest.files.map(r => ['/static/' + r.path, { ...r, content: fs.readFileSync(path.join(root, 'static', r.path)) }]));
const report = { ...config, compile_global_build: false, sources: sources.concat(styleSources).map(s => ({ path: 'frontend/workbench/' + s.path, sha256: hash(s.code) })),
  cases: [], boundaries: {}, screenshots: [], errors: [], external: [], responses: [], requests: [], restarts: 0, contract_rejections: 0 };
const boot = `ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(React.Fragment,null,
React.createElement(window.WorkbenchControlStyles),React.createElement(window.WorkbenchControls),React.createElement(window.WorkbenchNumberControls),
React.createElement(window.WorkbenchGuardHost),
React.createElement(AppShell,{active:'dashboard',title:'计划员值班台',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
React.createElement('div',{className:'plana'},location.search.includes('dashboard')?
React.createElement(window.WorkbenchDashboardWorkspace,{initialContext:{scope:{category:'external'}}}):React.createElement(window.OutsourcingWorkspace)))));`;
const replacements = new Map(compiled.map(r => [path.basename(r.path), r])), loaded = new Set();
const scriptTags = manifest.scripts.filter(f => !f.endsWith('/main.js')).map(f => {
  const current = replacements.get(path.basename(f));
  if (current) { loaded.add(current.path); return '<script src="/probe/' + current.path + '"></script>'; }
  return '<script src="/static/' + f + '"></script>';
}).join('') + compiled.filter(r => !loaded.has(r.path)).map(r => '<script src="/probe/' + r.path + '"></script>').join('');
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(f => '<link rel="stylesheet" href="/static/' + f + '">').join('') + '<style>' + styleSources.map(item => item.code).join('\n') + '</style>' +
  '</head><body class="aps-workbench"><div id="root"></div>' + scriptTags + '<script>' + boot + '</script></body></html>';
let fault = '', blockReceipts = false;
const base = '/api/workbench/v1/outsourcing', isCommand = (p, method) => p === base + '/receipts' && method === 'POST';
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const a = assets.get(url.pathname); response.setHeader('Content-Type', a.mime); return response.end(a.content); }
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/__outsourcing_fixture__/')) {
    report.requests.push({ path: url.pathname, method: request.method, cookie: request.headers.cookie });
    if (url.pathname.startsWith('/api/workbench/v1/commands/') && blockReceipts || isCommand(url.pathname, request.method) && fault === 'before') return response.destroy();
    const chunks = []; request.on('data', d => chunks.push(d)); request.on('end', () => {
      const body = Buffer.concat(chunks), upstream = http.request(config.api_origin + request.url, { method: request.method, headers: { cookie: request.headers.cookie || '',
        ...(body.length ? { 'Content-Type': 'application/json', 'Content-Length': body.length } : {}) } }, incoming => {
        const parts = []; incoming.on('data', d => parts.push(d)); incoming.on('end', () => {
          const content = Buffer.concat(parts);
          if ((incoming.headers['content-type'] || '').includes('application/json')) report.responses.push({ path: url.pathname, query: Object.fromEntries(url.searchParams), method: request.method,
            status: incoming.statusCode, input: body.length ? JSON.parse(body.toString()) : null, payload: JSON.parse(content.toString()) });
          if (isCommand(url.pathname, request.method) && fault === 'after') return response.destroy();
          if (isCommand(url.pathname, request.method) && fault === 'malformed') { response.writeHead(200, { 'Content-Type': 'application/json' }); return response.end('{"ok":true}'); }
          response.writeHead(incoming.statusCode, incoming.headers); response.end(content);
        });
      }); upstream.on('error', e => { report.errors.push(e.message); response.destroy(); }); upstream.end(body);
    }); return;
  }
  response.writeHead(404); response.end();
});
let browser, origin, activePage;
const dialog = page => page.locator('.outsourcing-live .modal[role=dialog]');
async function launch() { return chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] }); }
async function shot(page, name) { const file = path.join(output, name + '.png'); await page.screenshot({ path: file, animations: 'disabled' }); report.screenshots.push(file); }
async function action(page, suffix, trigger, status = 200, method = 'GET') {
  const wait = page.waitForResponse(r => new URL(r.url()).pathname === base + suffix && r.request().method() === method);
  await trigger(); const r = await wait; assert.equal(r.status(), status, await r.text()); return r.json();
}
async function fresh(name, viewport = { width: 1392, height: 924 }, theme = 'light', storageState, dashboard = false) {
  const context = await browser.newContext({ viewport, ...(storageState ? { storageState } : {}) });
  await context.addCookies([{ name: 'dn_case', value: name, url: origin }]);
  await context.addInitScript(t => { localStorage.setItem('aps_theme', t); localStorage.setItem('aps_kit_theme', t); }, theme);
  const page = await context.newPage(); activePage = page; page.on('pageerror', e => report.errors.push(e.message));
  await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
  await page.goto(origin + (dashboard ? '/?dashboard=1' : ''));
  if (name === 'missing') await page.getByRole('alert').waitFor(); else await page.locator('[data-outsourcing-workspace][data-ready=true]').waitFor();
  return { context, page };
}
async function select(page, label, option) {
  await page.getByLabel(label, { exact: true }).click(); const popup = page.locator('.wb-control-popup'), r = await popup.boundingBox(), viewport = page.viewportSize();
  assert(r && r.x >= 0 && r.y >= 0 && r.x + r.width <= viewport.width && r.y + r.height <= viewport.height);
  await popup.getByRole('option', { name: option, exact: true }).click(); report.boundaries.select_popup_bounds = true;
}
async function findMember(page, code) {
  for (let i = 0; i < 3; i++) {
    const member = dialog(page).getByLabel('选择工序 ' + code, { exact: true }); if (await member.count()) return member;
    const next = dialog(page).getByRole('button', { name: '工序下一页', exact: true }); if (await next.isDisabled()) break;
    await action(page, '/targets', () => next.click());
  }
  while (!await dialog(page).getByRole('button', { name: '工序上一页', exact: true }).isDisabled()) {
    await action(page, '/targets', () => dialog(page).getByRole('button', { name: '工序上一页', exact: true }).click());
  }
  for (let i = 0; i < 3; i++) {
    const member = dialog(page).getByLabel('选择工序 ' + code, { exact: true }); if (await member.count()) return member;
    await action(page, '/targets', () => dialog(page).getByRole('button', { name: '工序下一页', exact: true }).click());
  }
  throw new Error('Member not found: ' + code);
}
async function start(page, merged = false, codes = ['DN-O01']) {
  await action(page, '/targets', () => page.getByRole('button', { name: '新增外协登记', exact: true }).click());
  if (merged) await dialog(page).getByRole('radio', { name: '合并发出', exact: true }).check();
  for (const code of codes) await (await findMember(page, code)).check();
}
async function dates(page, { sent = '2026-09-07T09:00:00', planned = '2026-09-09T12:00:00', returned } = {}) {
  await dialog(page).getByLabel('实际发出', { exact: true }).fill(sent.replace(/:00$/, '')); await dialog(page).getByLabel('计划回厂', { exact: true }).fill(planned.replace(/:00$/, ''));
  if (returned) { await dialog(page).getByLabel('实际回厂', { exact: true }).fill(returned); await select(page, '外协确认状态', '已回厂'); }
}
async function operator(page, reason) {
  await dialog(page).getByLabel('外协经办人', { exact: true }).fill('物流员张工'); await dialog(page).getByLabel('外协核实原因', { exact: true }).fill(reason);
}
async function preview(page, status = 200) {
  const result = await action(page, '/receipts/preview', () => dialog(page).getByRole('button', { name: '预检核对', exact: true }).click(), status, 'POST');
  if (status === 200) {
    await dialog(page).getByText('图号：DN-P · 精密传动轴', { exact: true }).waitFor();
    assert.equal(await dialog(page).getByRole('checkbox').count(), 0);
    if (config.legacy_source && result.data.input.target) {
      assert.equal(result.data.target.source_resolution.basis, 'current_relation');
      await dialog(page).getByText('这批旧工序按本页列出的批次登记。', { exact: true }).waitFor();
    }
    report.boundaries.source_identity_visible_without_extra_confirmation = true;
  }
  return result;
}
async function send(page, status = 200) {
  return action(page, '/receipts', () => dialog(page).getByRole('button', { name: '确认保存外协登记', exact: true }).click(), status, 'POST');
}
async function confirmed(page) { await dialog(page).getByText('外协登记已完成。', { exact: true }).waitFor(); }
async function finish(page) { await action(page, '/receipts', () => dialog(page).getByRole('button', { name: '完成', exact: true }).click()); }
async function edit(page, ref) {
  if (!await page.locator('[data-outsourcing-detail="' + ref + '"]').count()) await action(page, '/receipts/' + ref + '/history', () => page.locator('[data-outsourcing-ref="' + ref + '"]').getByRole('button').click());
  await page.locator('[data-outsourcing-detail="' + ref + '"]').getByRole('button', { name: '核实 / 更正登记', exact: true }).click();
  await dialog(page).waitFor();
}
async function commit(page, reason) { await operator(page, reason); const p = await preview(page); const v = await send(page); await confirmed(page); await finish(page); return { p, v }; }
async function geometry(page, viewport) {
  const g = await page.evaluate(() => {
    const workspace = document.querySelector('[data-outsourcing-workspace]'), rect = n => { const r = n.getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width }; };
    const modal = workspace.querySelector('.modal'), nodes = [...workspace.querySelectorAll('button,th,td,dd,label')].filter(n => n.getClientRects().length);
    return { width: document.documentElement.scrollWidth, workspace: rect(workspace), theme: document.documentElement.dataset.theme,
      clipped: nodes.filter(n => n.scrollWidth > n.clientWidth + 3).map(n => n.textContent),
      black: nodes.filter(n => getComputedStyle(n).color === 'rgb(0, 0, 0)').map(n => n.textContent), modal: modal ? rect(modal) : null,
      selectAppearance: [...workspace.querySelectorAll('select')].map(n => getComputedStyle(n).appearance), text: workspace.innerText };
  });
  assert(g.width <= viewport.width, JSON.stringify(g)); assert.deepEqual(g.clipped, []); assert(g.selectAppearance.every(v => v === 'none'));
  if (g.theme === 'dark') assert.deepEqual(g.black, []);
  if (g.modal) assert(g.modal.x >= 0 && g.modal.right <= viewport.width && g.modal.y >= 0 && g.modal.bottom <= viewport.height);
  return g;
}
async function datePicker(page) {
  const field = dialog(page).getByLabel('实际发出', { exact: true }), box = await field.boundingBox();
  await field.click({ position: { x: box.width - 12, y: box.height / 2 } });
  const popup = page.locator('.wb-control-popup'); await popup.waitFor();
  assert.equal(await popup.locator('input[type=datetime-local],select').count(), 0);
  const r = await popup.boundingBox(), viewport = page.viewportSize(); assert(r.x >= 0 && r.y >= 0 && r.x + r.width <= viewport.width && r.y + r.height <= viewport.height);
  await shot(page, (await page.locator('html').getAttribute('data-theme')) + '-' + viewport.width + '-calendar');
  await page.keyboard.press('Escape'); assert.equal(await dialog(page).count(), 1); report.boundaries.picker_escape_preserves_dialog = true;
  await field.click({ position: { x: box.width - 12, y: box.height / 2 } }); await popup.getByRole('gridcell', { name: '2026-09-07', exact: true }).click();
  await popup.getByLabel('时', { exact: true }).fill('09'); await popup.getByLabel('分', { exact: true }).fill('00'); await popup.getByLabel('秒', { exact: true }).fill('17');
  await popup.getByRole('button', { name: '确认', exact: true }).click(); assert.equal(await field.inputValue(), '2026-09-07T09:00:17'); report.boundaries.picker_commits_seconds = true;
}
async function contracts(page, p, v, intent, list) {
  const targets = report.responses.find(r => r.path === base + '/targets').payload;
  return page.evaluate(({ p, v, intent, list, targets }) => {
    const C = window.OutsourcingContract; let n = 0;
    function reject(fn) { try { fn(); } catch (_) { n++; } }
    for (const mutate of [x => { x.meta.source = 'demo'; }, x => { x.data.after.returned = '2026-09-07T07:00:00'; }, x => { x.data.input.reason = 'other'; },
      x => { x.data.target.operation_refs = ['f'.repeat(48)]; }, x => { x.data.execution.automatically_reported = true; }]) { const x = JSON.parse(JSON.stringify(p)); mutate(x); reject(() => C.preview(x, p.data.input)); }
    for (const mutate of [x => { x.data.planned = '2026-09-12T12:00:00'; }, x => { x.data.reason = 'other'; }, x => { x.data.target.kind = 'single'; },
      x => { x.data.execution.automatically_reported = true; }, x => { delete x.data.fact_ref; }]) { const x = JSON.parse(JSON.stringify(v)); mutate(x); reject(() => C.receipt(x, intent)); }
    const q = { page: list.data.page.number, size: list.data.page.size, status: 'all', snapshot_ref: list.meta.snapshot_ref };
    for (const mutate of [x => { x.meta.snapshot_ref = 'other'; }, x => { x.data.page.number++; }, x => { x.data.page.total++; }]) { const x = JSON.parse(JSON.stringify(list)); mutate(x); reject(() => C.catalog(x, 'receipts', q)); }
    reject(() => C.query('history', { page: 2 })); reject(() => C.stamp('2026-02-30T08:00:00'));
    reject(() => C.target({ ...p.data.target, kind: 'single' })); reject(() => C.target({ ...p.data.target, operation_refs: p.data.target.operation_refs.slice(0, 1) }));
    for (const mutate of [x => { x.data.items[0].batch.ref = 'f'.repeat(48); }, x => { x.data.items[0].supplier.label = 123; }]) {
      const x = JSON.parse(JSON.stringify(targets)); mutate(x); reject(() => C.catalog(x, 'targets', { page: 1, size: 10 }));
    }
    const invalid = { ...intent, input: { ...intent.input, planned: '2026-10-01T00:00:00' } };
    if (!window.OutsourcingSession.valid(invalid)) n++;
    return n;
  }, { p, v, intent, list, targets });
}
async function happy(viewport, theme) {
  const name = theme + '-' + viewport.width; let { context, page } = await fresh(name, viewport, theme);
  await shot(page, name + '-empty'); await start(page); await dates(page); await operator(page, '单工序发出交接单 ' + name); await datePicker(page);
  await geometry(page, viewport); await shot(page, name + '-single-form'); await preview(page); const single = await send(page); await confirmed(page); await finish(page);
  await start(page, true, ['DN-O02', 'DN-O03']); await dates(page); await operator(page, '两道明确成员合并发出 ' + name);
  await geometry(page, viewport); await shot(page, name + '-merged-form'); const mergedPreview = await preview(page); await shot(page, name + '-preview');
  const merged = await send(page), ref = merged.data.outsourcing_ref; await confirmed(page); const intent = await page.evaluate(() => window.OutsourcingSession.read()); await finish(page);
  await edit(page, ref); await dialog(page).getByLabel('实际回厂', { exact: true }).fill('2026-09-10T10:30:15'); await select(page, '外协确认状态', '已回厂');
  await commit(page, '回厂卸货清点，工序报工另行核实');
  await edit(page, ref); const reconfirm = await commit(page, '重新核实原值仍一致'); assert.deepEqual(Object.keys(reconfirm.p.data.input).sort(), ['declared_operator', 'outsourcing_ref', 'reason']);
  await edit(page, ref); await dialog(page).getByLabel('计划回厂', { exact: true }).fill('2026-09-11T12:00');
  const sparse = await commit(page, '更正约定计划回厂'); assert.deepEqual(Object.keys(sparse.p.data.input).sort(), ['declared_operator', 'outsourcing_ref', 'planned', 'reason']);
  await edit(page, ref); await select(page, '外协确认状态', '待确认'); await dialog(page).getByRole('button', { name: '清除实际回厂', exact: true }).click();
  await commit(page, '纠正误认的回厂记录，待签收凭据确认');
  await edit(page, ref); await dialog(page).getByLabel('实际回厂', { exact: true }).fill('2026-09-10T11:15:27'); await select(page, '外协确认状态', '已回厂');
  await operator(page, '签收凭据 DN-20260910-' + name); await preview(page); fault = 'after'; blockReceipts = true;
  await dialog(page).getByRole('button', { name: '确认保存外协登记', exact: true }).click(); await dialog(page).getByText('上次外协登记的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。', { exact: true }).first().waitFor();
  const pending = await page.evaluate(() => window.OutsourcingSession.read()); assert.equal(pending.phase, 'pending'); assert(!JSON.stringify(pending).includes('write_token'));
  await shot(page, name + '-unknown'); const storageState = await context.storageState(); await context.close(); await browser.close(); browser = await launch(); report.restarts++;
  fault = ''; blockReceipts = false; ({ context, page } = await fresh(name, viewport, theme, storageState));
  await page.getByRole('button', { name: '查看已确认的结果', exact: true }).click(); await confirmed(page);
  assert.equal((await page.evaluate(() => window.OutsourcingSession.read())).request_key, pending.request_key); await finish(page);
  await start(page, false, ['DN-O04']); await dates(page); await commit(page, '第三份登记用于分页核对');
  let list = await action(page, '/receipts', () => select(page, '外协登记每页数量', '2 项'));
  const second = await action(page, '/receipts', () => page.getByRole('button', { name: '外协登记下一页', exact: true }).click()); assert.equal(second.meta.snapshot_ref, list.meta.snapshot_ref);
  list = await action(page, '/receipts', () => page.getByRole('button', { name: '外协登记上一页', exact: true }).click());
  await action(page, '/receipts', () => select(page, '外协登记每页数量', '10 项'));
  await action(page, '/receipts/' + ref + '/history', () => page.locator('[data-outsourcing-ref="' + ref + '"]').getByRole('button').click());
  const h = await action(page, '/receipts/' + ref + '/history', () => select(page, '外协历史每页数量', '2 项'));
  const h2 = await action(page, '/receipts/' + ref + '/history', () => page.getByRole('button', { name: '外协历史下一页', exact: true }).click()); assert.equal(h.meta.snapshot_ref, h2.meta.snapshot_ref); assert.equal(h2.data.history.page.number, 2);
  await page.locator('[data-fact-ref]').first().locator(':scope > summary').click(); await geometry(page, viewport); await shot(page, name + '-history');
  if (!report.contract_rejections) report.contract_rejections = await contracts(page, mergedPreview, merged, intent, list);
  const returned = await action(page, '/receipts', () => select(page, '外协登记筛选', '已回厂')); assert.equal(returned.data.page.total, 1);
  await action(page, '/receipts', () => select(page, '外协登记筛选', '全部登记')); const g = await geometry(page, viewport); await shot(page, name + '-registered');
  const posts = report.responses.filter(r => r.method === 'POST' && r.path === base + '/receipts' && r.input.request_key === pending.request_key); assert.equal(posts.length, 1);
  report.cases.push({ name, viewport, theme, merged_ref: ref, single_ref: single.data.outsourcing_ref, unknown_key: pending.request_key, geometry: g });
  report.boundaries.single_merged_explicit = report.boundaries.sparse_null_reconfirm = report.boundaries.history_snapshot = report.boundaries.list_snapshot = report.boundaries.original_key_restart = true;
  await context.close();
}
async function boundaries() {
  let { context, page } = await fresh('missing'); assert.equal(await page.locator('[data-outsourcing-ref]').count(), 0); report.boundaries.schema_missing = true; await shot(page, 'missing-schema'); await context.close();
  ({ context, page } = await fresh('stale')); await start(page); await dates(page, { sent: '2026-09-08T10:00:00', planned: '2026-09-07T09:00:00' }); await operator(page, '倒序边界');
  await dialog(page).getByRole('button', { name: '预检核对', exact: true }).click(); await dialog(page).getByText('计划回厂和实际回厂不能早于实际发出。', { exact: true }).waitFor(); report.boundaries.reverse_dates = true;
  await dates(page, { sent: '2026-09-11T09:00:00', planned: '2026-09-12T12:00:00' }); await preview(page, 422); await dialog(page).getByRole('alert').waitFor(); report.boundaries.future_actuals = true;
  await dates(page); await operator(page, '真实服务未来回厂拒绝'); await dialog(page).getByLabel('实际回厂', { exact: true }).fill('2026-09-11T10:00'); await select(page, '外协确认状态', '已回厂'); await preview(page, 422);
  await dialog(page).getByRole('button', { name: '清除实际回厂', exact: true }).click(); await select(page, '外协确认状态', '在途'); await preview(page); const created = await send(page); await confirmed(page); await finish(page);
  const ref = created.data.outsourcing_ref; await edit(page, ref); await commit(page, '为翻页建立第二次核实'); await edit(page, ref); await commit(page, '为翻页建立第三次核实');
  const old = await action(page, '/receipts/' + ref + '/history', () => select(page, '外协历史每页数量', '2 项'));
  const input = { outsourcing_ref: ref, declared_operator: '另一个核实人', reason: '并发增加核实，旧快照应失效' };
  const p = await context.request.post(origin + base + '/receipts/preview', { data: { input } }); assert.equal(p.status(), 200); const d = (await p.json()).data;
  const update = await context.request.post(origin + base + '/receipts', { data: { input, write_token: d.write_context.write_token, request_key: 'dn-other-page-history-command' } }); assert.equal(update.status(), 200);
  await action(page, '/receipts/' + ref + '/history', () => page.getByRole('button', { name: '外协历史下一页', exact: true }).click(), 409);
  assert.equal(await page.locator('[data-fact-ref]').count(), 0); await action(page, '/receipts/' + ref + '/history', () => page.getByRole('button', { name: '刷新登记历史', exact: true }).click());
  assert.equal(await page.locator('[data-fact-ref]').count(), 2); report.boundaries.stale_history_not_mixed = true; await shot(page, 'stale-history-refreshed'); await context.close();
  for (const name of ['lost', 'malformed', 'drift', 'rollback']) {
    ({ context, page } = await fresh(name)); await start(page); await dates(page); await operator(page, '边界核实 ' + name); await preview(page);
    if (['drift', 'rollback'].includes(name)) assert.equal((await context.request.post(origin + '/__outsourcing_fixture__/mutate')).status(), 200);
    if (name === 'lost') fault = 'before'; if (name === 'malformed') { fault = 'malformed'; blockReceipts = true; }
    if (name === 'lost') await dialog(page).getByRole('button', { name: '确认保存外协登记', exact: true }).click(); else await send(page, name === 'drift' ? 409 : name === 'rollback' ? 500 : 200);
    if (name === 'drift') { await dialog(page).getByText('上次外协登记没有生效，填写内容已保留。改好后重新提交。', { exact: true }).waitFor(); report.boundaries.stale_preview_rejected = true; }
    else {
      await dialog(page).getByText('上次外协登记的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。', { exact: true }).first().waitFor(); assert.equal(await dialog(page).getByRole('button', { name: '确认保存外协登记', exact: true }).count(), 0);
      if (name === 'malformed') { fault = ''; blockReceipts = false; await dialog(page).getByRole('button', { name: '查询结果', exact: true }).click(); await confirmed(page); report.boundaries.malformed200_not_success = true; }
      else { await dialog(page).getByText(/还是没有查到结果/).waitFor(); report.boundaries[name === 'lost' ? 'not_recorded_retained' : 'rollback_atomic'] = true; }
    }
    await shot(page, name); fault = ''; blockReceipts = false; await context.close();
  }
}
async function dashboard(viewport, theme) {
  const { context, page } = await fresh(theme + '-' + viewport.width, viewport, theme, undefined, true);
  await page.locator('[data-dashboard-workspace][data-ready=true]').waitFor();
  const expected = { receipt_count: 3, current_receipt_count: 3, awaiting_return_count: 2, overdue_count: 2, returned_count: 1, awaiting_confirmation_count: 0, unregistered_count: 21, source_gap_count: 0 };
  for (const [k, v] of Object.entries(expected)) assert.equal(await page.locator('[data-external-count="' + k + '"]').innerText(), String(v));
  const summary = report.responses.filter(r => r.path === '/api/workbench/v1/dashboard').pop().payload.data.categories.external;
  report.contract_rejections += await page.evaluate(s => { let n = 0; for (const mutate of [v => { v.handling_supported = true; }, v => { v.closed_count = 1; }, v => { v.receipt_count = 0; }]) {
    const v = JSON.parse(JSON.stringify(s)); mutate(v); try { window.DashboardContract.external(v); } catch (_) { n++; } } return n; }, summary);
  assert.equal(await page.getByRole('tab', { name: '处置历史', exact: true }).count(), 0); assert.equal(await page.getByLabel('处置状态', { exact: true }).count(), 0);
  assert(!/已关闭处置/.test(await page.locator('.dy-metric').nth(2).innerText()));
  await geometry(page, viewport); await shot(page, theme + '-' + viewport.width + '-dashboard');
  await page.getByRole('button', { name: '新增外协登记', exact: true }).click(); await dialog(page).waitFor();
  await geometry(page, viewport); await shot(page, theme + '-' + viewport.width + '-dashboard-form'); await page.keyboard.press('Escape');
  report.boundaries.dashboard_summary_independent = true; await context.close();
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); origin = 'http://127.0.0.1:' + server.address().port;
  try {
    browser = await launch(); report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) await happy(viewport, theme);
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) await dashboard(viewport, theme);
    await boundaries(); assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } catch (error) { if (activePage && !activePage.isClosed()) { await shot(activePage, 'failure'); report.failure_text = await activePage.locator('body').innerText(); } throw error; }
  finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'outsourcing-ui.json'), JSON.stringify(report, null, 2)); }
  console.log(JSON.stringify({ browser: report.browser, cases: report.cases.length, screenshots: report.screenshots.length, boundaries: report.boundaries }));
})().catch(error => { console.error(error); process.exitCode = 1; });
