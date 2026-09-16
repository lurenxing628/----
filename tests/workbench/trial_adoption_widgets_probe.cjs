/* CX source harness: main Trial renderAdoption hook, actual CQ HTTP and SQLite, no successful fetch mocks. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchHandlerMemory.js', 'WorkbenchReferences.jsx', 'WorkbenchGuards.js', 'WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-api.js', 'resource-session.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'WorkbenchControlStyles.jsx', 'WorkbenchControlBridge.js', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchNumberControls.jsx',  'PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx',
  'TrialContract.js', 'TrialAPI.js', 'TrialSession.js', 'TrialControls.jsx', 'TrialViewState.js', 'TrialCatalog.jsx', 'TrialGantt.jsx', 'TrialDetails.jsx', 'TrialResults.jsx', 'TrialStyles.jsx', 'TrialWorkspace.jsx',
  'TrialAdoptionAPI.js', 'TrialAdoptionState.js', 'TrialAdoptionControls.jsx', 'TrialAdoptionAction.jsx',
  'PlanProcessOrder.js', 'PlanContract.js', 'PlanAPI.js', 'PlanLayout.jsx', 'PlanSelectionModel.js', 'PlanCatalogUI.jsx', 'PlanGanttModel.js', 'PlanGanttCanvas.jsx', 'PlanGantt.jsx', 'PlanDetailsUI.jsx', 'PlanExportUI.jsx', 'PlanWorkspace.jsx'];
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
const boot = `window.nav=[];window.events=[];window.hookSnapshots={};let fixtureRoot;
function Fixture(){const [target,setTarget]=React.useState(sessionStorage.getItem('cx_scenario')),[plan,setPlan]=React.useState(null),[disabled,setDisabled]=React.useState(false);
window.mountTrial=ref=>{sessionStorage.setItem('cx_scenario',ref);setPlan(null);setTarget(ref);};window.disableAdoption=setDisabled;
const navigate=(view,context)=>{nav.push([view,context]);setPlan(context.plan_ref);};
return React.createElement(React.Fragment,null,React.createElement(WorkbenchGuardHost),React.createElement(WorkbenchControlStyles),plan?
React.createElement(React.Fragment,null,React.createElement(ResourceControls.Button,{onClick:()=>setPlan(null)},'返回原场景'),React.createElement(PlanWorkspace,{view:'analysis',initialContext:{plan_ref:plan}})):
target&&React.createElement(WorkbenchTrialWorkspace,{initialTarget:{scenario_ref:target},onNavigate:navigate,
renderAdoption:props=>{hookSnapshots[props.scenarioRef]=JSON.stringify(props.data);return React.createElement(TrialAdoptionAction,{...props,disabled:props.disabled||disabled,
onAdopted:r=>{events.push(r.receipt_ref);if(window.failAdoptCallback)return Promise.reject(Error('CX callback failure'));return props.onAdopted(r);}});}}));}
fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));fixtureRoot.render(React.createElement(Fixture));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>body{margin:0}#fixture-root{margin-left:208px;padding:16px 24px;min-height:100vh}.fixture-rail{position:fixed;inset:0 auto 0 0;width:208px;padding:24px;background:var(--sidebar-bg);border-right:1px solid var(--ui-border);color:var(--sidebar-text-strong)}</style>' +
  '</head><body class="aps-workbench"><aside class="fixture-rail">APS 智能排产<br>场景正式采用</aside><div id="fixture-root"></div>' +
  foundation.map(file => '<script src="/static/' + file + '"></script>').join('') + [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
let dropReply = false;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://fixture').pathname;
  if (pathname === '/probe/drop-next-reply') { dropReply = true; res.end('{}'); return; }
  if (pathname.startsWith('/api/') || pathname.startsWith('/fixture/')) {
    const upstream = http.request(backend + req.url, { method: req.method, headers: req.headers }, response => {
      if (dropReply && pathname.endsWith('/adopt')) {
        dropReply = false; response.resume(); response.on('end', () => { res.setHeader('Content-Type', 'application/json'); res.end('{"ok":'); }); return;
      }
      res.writeHead(response.statusCode, response.headers); response.pipe(res);
    });
    upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('CX isolated fixture unavailable'); }); req.pipe(upstream); return;
  }
  if (pathname === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html.replace('</head>', '<style>' + workspaceCSS + '</style></head>')); return; }
  if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
  const asset = assets.get(pathname); if (!asset) { res.writeHead(404); res.end(); return; } res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const report = { browser: null, variants: [], checks: [], screenshots: [], errors: [], external: [], dialogs: [], layout: [],
  sources: sources.concat(styleSources).map(s => ({ path: s.path, sha256: crypto.createHash('sha256').update(s.code).digest('hex') })) };
let page, origin, variant, refs;
const button = name => page.getByRole('button', { name, exact: true });
const done = name => report.checks.push({ variant, name, passed: true });
const state = () => page.evaluate(() => TrialAdoptionState.read());
const evidence = async () => (await page.request.get(origin + '/fixture/evidence')).json();
const control = async action => { const r = await page.request.post(origin + '/fixture/control', { data: { action } }); assert.equal(r.status(), 200, await r.text()); return r.json(); };
const savedScenario = async () => (await (await page.request.get(origin + '/api/workbench/v1/trial/scenarios/' + refs.scenario_ref)).json()).data;
async function eventually(predicate) {
  const deadline = Date.now() + 15000;
  while (!await predicate()) { assert(Date.now() < deadline, 'Timed out waiting for real fixture evidence'); await new Promise(resolve => setTimeout(resolve, 40)); }
}
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: false, animations: 'disabled' }); report.screenshots.push(file); }
async function ready() { await page.locator('[data-trial-adoption-action]').waitFor(); await page.waitForFunction(() => !document.querySelector('[aria-label="刷新当前试调"]')?.disabled); }
async function reset(mode = 'normal') {
  const response = await page.request.post(origin + '/fixture/reset', { data: { mode } }); assert.equal(response.status(), 200, await response.text()); refs = await response.json();
  await page.evaluate(ref => { localStorage.removeItem(TrialAdoptionState.KEY); sessionStorage.setItem('cx_scenario', ref); }, refs.scenario_ref);
  await page.goto(origin); await ready(); await button('采用方案').waitFor();
}
async function inspect() { await button('采用方案').click(); await page.getByRole('dialog', { name: '确认正式采用试调方案', exact: true }).waitFor(); }
async function fill() {
  await page.getByLabel('采用原因', { exact: true }).fill('现场核对完整场景与原草稿，保留原执行，采用全部安排。');
  await page.getByLabel('经办人', { exact: true }).fill('计划员 张三'); await page.getByRole('checkbox', { name: /^确认将完整试调方案正式采用/ }).check();
}
async function success(version = 41) {
  await page.getByRole('dialog', { name: '试调方案采用结果', exact: true }).waitFor();
  await page.getByText('已确认：这次生成正式计划第 ' + version + ' 版，共 2 道工序。', { exact: false }).waitFor();
}
async function selectedOfficial(planRef, version, identity) {
  const catalog = page.getByRole('region', { name: '排产方案列表', exact: true });
  assert.equal(await catalog.getByRole('combobox', { name: '切换所选计划', exact: true }).inputValue(), planRef);
  await catalog.getByRole('button', { name: '展开计划列表', exact: true }).click();
  const selected = catalog.getByRole('table', { name: '可选排产方案', exact: true }).locator('tbody tr[aria-selected=true]');
  await selected.waitFor(); assert.equal(await selected.count(), 1); assert(await selected.getByRole('radio').isChecked());
  assert.equal(await selected.getByRole('cell').nth(1).innerText(), String(version));
  assert.equal(await selected.locator('.plan-state').innerText(), identity);
  assert((await page.locator('.plan-scope-heading').innerText()).includes(identity));
}
async function geometry(name) {
  const row = await page.evaluate(() => {
    const d = document.querySelector('.trial-adoption-action [role=dialog]'), r = d.getBoundingClientRect();
    const rgb = x => (x.match(/[\d.]+/g) || []).map(Number).slice(0, 3);
    const luma = x => rgb(x).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
    const background = n => { for (let p = n; p; p = p.parentElement) { const c = getComputedStyle(p).backgroundColor; if (!['transparent', 'rgba(0, 0, 0, 0)'].includes(c)) return c; } return 'rgb(255,255,255)'; };
    const controls = [...d.querySelectorAll('button:not(:disabled),input:not(:disabled),textarea,dd,dt,.ta-note,.ta-result')].filter(n => n.getClientRects().length);
    const contrast = n => { const a = luma(getComputedStyle(n).color), b = luma(background(n)); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); };
    const footer = d.querySelector('.modal-f').getBoundingClientRect(), body = d.querySelector('.ta-body').getBoundingClientRect();
    return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: innerWidth, height: innerHeight,
      overflow: document.documentElement.scrollWidth > innerWidth, minContrast: Math.min(...controls.map(contrast)), focusInside: d.contains(document.activeElement),
      position: getComputedStyle(d.parentElement).position, bodyFooterOverlap: body.bottom > footer.top + 1,
      clipped: controls.filter(n => !n.matches('input') && n.scrollWidth > n.clientWidth + 2).map(n => n.tagName + ':' + n.textContent),
      fontFamily: getComputedStyle(d).fontFamily, theme: document.documentElement.dataset.theme };
  });
  assert(!row.overflow && row.focusInside && !row.bodyFooterOverlap); assert.equal(row.position, 'fixed'); assert(row.minContrast >= 4.5, JSON.stringify(row));
  assert(row.x >= 0 && row.y >= 0 && row.right <= row.width + 1 && row.bottom <= row.height + 1, JSON.stringify(row)); assert.deepEqual(row.clipped, []);
  for (let i = 0; i < 10; i++) { await page.keyboard.press(i % 3 ? 'Tab' : 'Shift+Tab'); assert(await page.getByRole('dialog').evaluate(n => n.contains(document.activeElement))); }
  report.layout.push({ variant, name, ...row });
}
async function basic() {
  await reset(); const before = await savedScenario();
  assert(!before.validation.issues.some(i => i.code === 'scenario_adoption_not_connected'));
  assert.equal(before.validation.can_adopt, false);
  assert.equal(await page.locator('.tt-bar').count(), 0); assert.equal(await state(), null);
  const initial = await evidence();
  assert(!initial.journal.some(r => r.path.endsWith('/adopt-preview') && r.database === initial.lifecycle.database_path));
  await inspect(); await page.getByText('完整试调方案，共 2 道工序', { exact: true }).waitFor(); assert(await button('确认正式采用').isDisabled());
  await fill(); assert.equal(await state(), null); await geometry('confirm'); await shot('confirm');
  assert(!/write_token|snapshot_ref|write_context/.test(await page.locator('.ta-body').innerText()));
  await button('取消').click(); assert.equal((await evidence()).receipts.length, 0); assert.deepEqual(await savedScenario(), before); done('new-post-preview-only-historical-validation-unchanged-full-hidden-scope');
  await inspect(); await page.getByText('完整试调方案，共 2 道工序', { exact: true }).waitFor(); assert(await button('确认正式采用').isDisabled());
  await page.getByRole('checkbox', { name: /^确认将完整试调方案正式采用/ }).check(); await button('确认正式采用').click(); await success();
  const intent = await state(); assert.equal(intent.phase, 'committed'); assert(!JSON.stringify(intent).includes('write_token'));
  assert.equal(intent.scenario_ref, before.scenario_ref); assert.equal(intent.preview.draft_ref, before.draft_ref); assert.equal((await evidence()).receipts.length, 1);
  assert.deepEqual(await savedScenario(), before); assert.equal(await page.evaluate(ref => hookSnapshots[ref], refs.scenario_ref), JSON.stringify(before));
  await geometry('receipt'); await shot('receipt'); await page.locator('.ta-records summary').click(); await geometry('expanded'); await shot('expanded');
  await button('进入正式计划').click(); await page.locator('[data-plan-workspace] .plan-bar').first().waitFor();
  const navigation = await page.evaluate(() => nav[nav.length - 1]); assert.deepEqual(navigation, ['analysis', { plan_ref: intent.receipt.data.official_plan.plan_ref }]);
  assert.notEqual(navigation[1].plan_ref, refs.scenario_ref); assert.notEqual(navigation[1].plan_ref, refs.baseline_ref);
  await selectedOfficial(navigation[1].plan_ref, 41, '当前正式'); await shot('official-navigation'); done('real-commit-new-official-identity-main-plan-navigation');
  await button('返回原场景').click(); await ready(); await button('查看采用结果').click(); await success();
  const advanced = await control('advance'); assert.equal(advanced.data.official_plan.version, 42);
  const writes = (await evidence()).journal.filter(r => r.request_key === intent.request_key && r.path.endsWith('/adopt')).length;
  await page.reload(); await ready(); await button('查看采用结果').click(); await success(); await button('查询结果').click();
  await page.getByText('已查询到上次采用结果。', { exact: true }).waitFor();
  assert.equal((await state()).request_key, intent.request_key); assert.equal((await evidence()).journal.filter(r => r.request_key === intent.request_key && r.path.endsWith('/adopt')).length, writes);
  const replay = await page.request.post(origin + '/api/workbench/v1/trial/scenarios/' + refs.scenario_ref + '/adopt', {
    data: { write_token: 'expired-replay-token', request_key: intent.request_key, input: intent.input } });
  const replayed = await replay.json(); assert.equal(replayed.receipt_ref, intent.receipt.receipt_ref); assert(replayed.replayed); assert.equal(replayed.data.official_plan.version, 41);
  assert.equal((await evidence()).receipts.length, 2); assert.deepEqual(await savedScenario(), before); await shot('old-receipt-after-new-official');
  await button('进入正式计划').click(); await page.locator('[data-plan-workspace] .plan-bar').first().waitFor();
  await selectedOfficial(intent.receipt.data.official_plan.plan_ref, 41, '历史正式'); done('original-key-replay-after-newer-official-is-historical-not-current');
  await button('返回原场景').click(); await ready(); await button('查看采用结果').click(); await success(); await button('完成').click(); assert.equal(await state(), null);
}
async function rejectedCases() {
  await reset('disabled'); await inspect(); await page.locator('.ta-notice').filter({ hasText: '此功能尚未开通' }).waitFor(); assert(await button('确认正式采用').isDisabled());
  await control('enable'); await button('重新预检').click(); await page.getByText('完整试调方案，共 2 道工序', { exact: true }).waitFor(); await button('取消').click(); done('explicit-disabled-preview-blocker');
  await reset('invalid'); await inspect(); await page.locator('.ta-notice').waitFor(); assert(await button('确认正式采用').isDisabled());
  assert.equal(await page.getByText('完整试调方案，共 2 道工序', { exact: true }).count(), 1); await shot('invalid-blocked'); done('invalid-saved-constraints-blocked');
  await reset(); await inspect(); await fill(); await control('expire'); await button('确认正式采用').click();
  await page.getByText('上次采用没有生效', { exact: false }).waitFor(); const original = await state(); assert.equal(original.phase, 'rejected');
  await page.reload(); await ready(); await button('重新核对采用').click();
  assert.equal(await page.getByLabel('经办人', { exact: true }).inputValue(), original.input.declared_operator); assert(await page.getByLabel('经办人', { exact: true }).getAttribute('readonly') !== null);
  await button('重新预检').click(); await page.getByText('完整试调方案，共 2 道工序', { exact: true }).waitFor(); assert(await button('确认正式采用').isDisabled());
  await page.getByRole('checkbox', { name: /^确认将完整试调方案正式采用/ }).check(); await button('确认正式采用').click(); await success();
  assert.equal((await state()).request_key, original.request_key); assert.equal((await evidence()).receipts.length, 1); done('expired-token-refresh-frozen-intent-explicit-reconfirm-same-key');
  await reset(); await inspect(); await fill(); await control('run-busy'); await button('确认正式采用').click();
  await page.getByText('正在排产，这次采用没有执行', { exact: false }).waitFor(); assert.equal((await state()).phase, 'rejected'); assert.equal((await evidence()).receipts.length, 0);
  await control('run-idle'); await button('结束本次未采用').click(); assert.equal(await state(), null); done('real-global-run-lock-explained-no-write');
  await reset(); await inspect(); await fill(); await control('drift'); await button('确认正式采用').click();
  await page.getByText('上次采用没有生效', { exact: false }).waitFor(); await button('重新预检').click(); await page.locator('.ta-notice').waitFor();
  assert(await button('确认正式采用').isDisabled()); assert.equal((await evidence()).receipts.length, 0); await shot('drift-blocked'); done('current-facts-drift-rechecked-and-blocked');
}
async function uncertainCases() {
  await reset('paused'); await inspect(); await fill(); await button('确认正式采用').click();
  await eventually(async () => (await evidence()).started); const original = await state();
  const peer = await page.context().newPage(); peer.on('pageerror', e => report.errors.push(e.message));
  await peer.goto(origin); await peer.evaluate(ref => mountTrial(ref), refs.other_ref); await peer.getByRole('button', { name: '查询采用结果', exact: true }).click();
  await peer.getByText('另一个试调方案的采用结果待确认，请先查询结果。', { exact: true }).waitFor();
  assert.equal((await peer.evaluate(() => TrialAdoptionState.read())).request_key, original.request_key);
  assert.equal(await peer.getByRole('button', { name: '确认正式采用', exact: true }).count(), 0); await peer.close(); done('another-tab-recovers-same-key-no-adoption-for-other-scenario');
  await button('关闭并保留这次操作').click(); await page.evaluate(ref => mountTrial(ref), refs.other_ref); await ready(); await button('查询采用结果').click();
  await page.getByText('另一个试调方案的采用结果待确认，请先查询结果。', { exact: true }).waitFor();
  await page.reload(); await ready(); await button('查询采用结果').click(); await page.getByText('上次采用的结果还没查到', { exact: false }).waitFor();
  assert.equal((await state()).request_key, original.request_key); assert.equal(await button('确认正式采用').count(), 0); assert.equal((await evidence()).receipts.length, 0);
  await shot('inflight-other-scenario'); await control('release');
  await eventually(async () => { const e = await evidence(); return e.receipts.length === 1 && e.journal.some(r => r.request_key === original.request_key && r.status === 200 && r.path.endsWith('/adopt')); });
  await button('查询结果').click(); await success();
  assert.equal((await evidence()).journal.filter(r => r.request_key === original.request_key && r.path.endsWith('/adopt')).length, 1); done('inflight-switch-refresh-not-observed-original-scenario-only-lookup');
  for (const mode of ['ack', 'normal', 'rollback']) {
    await reset(mode); await inspect(); await fill(); await page.route('**/adoption-commands/*', route => route.abort());
    if (mode === 'normal') await page.request.post(origin + '/probe/drop-next-reply');
    await button('确认正式采用').click(); await page.getByRole('dialog', { name: '查询上次采用结果', exact: true }).waitFor(); const lost = await state();
    await eventually(async () => (await evidence()).journal.some(r => r.request_key === lost.request_key && r.path.endsWith('/adopt')));
    assert.equal((await state()).phase, 'pending');
    await page.reload(); await ready(); await button('查询采用结果').click(); assert.equal(await button('进入正式计划').count(), 0);
    assert.equal((await state()).request_key, lost.request_key); await shot('unknown-' + mode); await page.unroute('**/adoption-commands/*'); await button('查询结果').click();
    if (mode === 'rollback') { await page.getByText('上次采用的结果还没查到', { exact: false }).waitFor(); assert.equal((await evidence()).receipts.length, 0); }
    else { await success(); assert.equal((await evidence()).receipts.length, 1); }
    const posts = (await evidence()).journal.filter(r => r.request_key === lost.request_key && r.path.endsWith('/adopt')); assert.equal(posts.length, 1);
    if (mode !== 'normal') { assert.equal(posts[0].status, 500); assert.equal(posts[0].committed, 'unknown'); assert(posts[0].error.result_target.endsWith(lost.request_key)); }
    done(mode + '-real-storage-or-response-failure-no-automatic-resubmit');
  }
}
async function storageAndBoundaries() {
  await reset(); await inspect(); await fill();
  await page.evaluate(() => { window.originalSetItem = Storage.prototype.setItem; Storage.prototype.setItem = function(k, v) { if (k === TrialAdoptionState.KEY) throw Error('CX storage full'); return originalSetItem.call(this, k, v); }; });
  await button('确认正式采用').click(); await page.getByText('存不下这次采用操作的记录', { exact: false }).first().waitFor();
  const blocked = await evidence(); assert.equal(blocked.receipts.length, 0);
  assert.equal(blocked.journal.filter(r => r.path.endsWith('/adopt') && r.database === blocked.lifecycle.database_path).length, 0);
  await page.evaluate(() => { Storage.prototype.setItem = originalSetItem; }); await button('刷新上次操作记录').click();
  await button('重新预检').click(); await page.getByText('完整试调方案，共 2 道工序', { exact: true }).waitFor();
  await page.evaluate(() => { window.failAdoptCallback = true; }); await page.getByRole('checkbox', { name: /^确认将完整试调方案正式采用/ }).check(); await button('确认正式采用').click(); await success();
  await page.getByText('采用已确认，但相关页面没有更新成功。请重新打开正式计划。', { exact: true }).waitFor(); done('storage-failure-no-post-receipt-survives-parent-callback-failure');
  const intent = await state();
  const guards = await page.evaluate(intent => {
    const clone = x => JSON.parse(JSON.stringify(x)), rejects = f => { try { f(); return false; } catch (_) { return true; } };
    const changes = [v => v.data.scenario_ref = 'f'.repeat(48), v => v.data.draft_ref = 'f'.repeat(48), v => v.data.row_count++,
      v => v.data.official_plan.source_scenario_ref = 'f'.repeat(48), v => v.data.official_plan.source_draft_ref = 'f'.repeat(48),
      v => v.data.official_plan.candidate_ref = intent.scenario_ref, v => v.data.official_plan.plan_ref = intent.scenario_ref,
      v => v.data.official_plan.version = 7, v => v.data.official_plan.baseline_ref = null, v => v.data.official_plan.kind = 'candidate'];
    const invalid = changes.map(change => { const v = clone(intent.receipt); change(v); return rejects(() => TrialAdoptionAPI.receipt(v, intent)); });
    const stored = clone(intent); stored.phase = 'rejected'; delete stored.receipt;
    invalid.push(rejects(() => TrialAdoptionState.begin(intent.preview, { ...intent.input, reason: 'changed' }, stored)));
    invalid.push(rejects(() => TrialAdoptionState.begin({ ...intent.preview, scenario_ref: 'f'.repeat(48) }, intent.input, stored)));
    invalid.push(rejects(() => TrialAdoptionAPI.source('f'.repeat(48), JSON.parse(hookSnapshots[intent.scenario_ref]))));
    return invalid;
  }, intent); assert(guards.every(Boolean)); done('wrong-object-provenance-count-version-and-original-intent-fail-closed');
  await reset(); await page.evaluate(() => localStorage.setItem(TrialAdoptionState.KEY, '{')); await page.reload(); await ready();
  const corruption = page.getByRole('alert').filter({ hasText: '上次采用操作的记录已损坏。请不要再操作，联系维护人员。' });
  await corruption.waitFor(); await corruption.scrollIntoViewIfNeeded();
  assert(await page.locator('[data-trial-adoption-action] button').first().isDisabled());
  const corrupt = await evidence(); assert(!corrupt.journal.some(r => r.database === corrupt.lifecycle.database_path && r.path.endsWith('/adopt')));
  await shot('corrupt-storage'); done('corrupt-persistent-record-blocks-new-adoption');
  await reset(); await inspect(); await fill(); await page.evaluate(() => disableAdoption(true));
  await page.getByRole('dialog', { name: '确认正式采用试调方案', exact: true }).getByText('试调方案正在读取，或还有操作没确认结果，暂时不能开始采用。', { exact: true }).waitFor(); assert(await button('确认正式采用').isDisabled());
  await page.evaluate(() => disableAdoption(false)); assert(await button('确认正式采用').isDisabled()); await button('重新预检').click();
  await page.getByText('完整试调方案，共 2 道工序', { exact: true }).waitFor(); assert(await button('确认正式采用').isDisabled()); done('host-disabled-invalidates-preview-and-consent');
  await fill(); await control('drain'); await button('确认正式采用').click();
  await page.getByText('系统正在退出或维护', { exact: false }).waitFor(); assert.equal((await evidence()).receipts.length, 0); assert.equal((await state()).phase, 'rejected');
  await geometry('draining'); await shot('draining'); done('real-http-draining-503-explained-and-original-key-retained');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    assert.notEqual(server.address().port, 57734); origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      variant = width + '-' + theme; const row = { variant, width, height: width === 1920 ? 1080 : 924, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height: row.height }, timezoneId: 'America/New_York' });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(15000);
      page.on('pageerror', e => report.errors.push(e.message)); page.on('dialog', d => { report.dialogs.push(d.type()); d.dismiss(); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      try { await page.goto(origin); await basic(); await rejectedCases(); await uncertainCases(); await storageAndBoundaries(); row.passed = true; }
      catch (e) { row.error = e.stack; await shot('FAILED'); throw e; }
      finally { await control('release'); await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []);
    console.log(JSON.stringify({ browser: report.browser, checks: report.checks.length, variants: report.variants.length, output }));
  } finally { if (browser) await browser.close(); server.close(); fs.writeFileSync(path.join(output, 'trial-adoption-widgets.json'), JSON.stringify(report, null, 2)); }
})().catch(e => { console.error(e.stack); process.exitCode = 1; });
