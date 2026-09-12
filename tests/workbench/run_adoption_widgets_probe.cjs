/* CB source-only UI probe. Adoption always reaches the real isolated Flask service. */
'use strict';
const UI = require('./run_ui_source.cjs');
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { expect } = require('playwright/test'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const files = UI.dependencies(['resource-contract.js', 'ResourceControls.jsx', 'WorkbenchControlStyles.jsx', 'RunAdoptionAPI.js', 'RunAdoptionControls.jsx', 'RunAdoptionAction.jsx']);
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, i) => ['/source/' + files[i], row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const staticScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const boot = `let appRoot;window.events=[];window.nav=[];
function Fixture({candidateRef}){const [outer,setOuter]=React.useState(false);return React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),
React.createElement('button',{onClick:()=>setOuter(true),id:'open-parent',className:'btn'},'外层操作'),
React.createElement(RunAdoptionAction,{candidateRef,onNavigate:(...v)=>{window.nav.push(v);},onAdopted:r=>{window.events.push(r.receipt_ref);if(window.failAdoptCallback)return Promise.reject(Error('fixture callback failure'));}}),
outer&&React.createElement(ResourceControls.Modal,{title:'外层候选',onClose:()=>setOuter(false)},React.createElement(RunAdoptionAction,{candidateRef})));}
window.mountAdoption=(ref)=>{sessionStorage.setItem('cb_fixture_candidate',ref);if(appRoot)appRoot.unmount();appRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));appRoot.render(React.createElement(Fixture,{candidateRef:ref}));};
if(sessionStorage.getItem('cb_fixture_candidate'))mountAdoption(sessionStorage.getItem('cb_fixture_candidate'));`;
const report = { browser: null, variants: [], checks: [], screenshots: [], errors: [], external: [], dialogs: [], layout: [], wait_contracts: [],
  sources: sources.map(s => ({ path: s.path, sha256: crypto.createHash('sha256').update(s.code).digest('hex') })) };
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  UI.styles(report, output) + '<style>body{margin:0}#fixture-root{padding:32px;display:flex;gap:16px;align-items:flex-start}</style></head><body class="aps-workbench"><div id="fixture-root"></div>' +
  staticScripts.map(file => '<script src="/static/' + file + '"></script>').join('') + [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
let dropReply = false;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://fixture').pathname;
  if (pathname === '/probe/drop-next-adoption-reply') { dropReply = true; res.end('{}'); return; }
  if (pathname.startsWith('/api/') || pathname.startsWith('/fixture/')) {
    const upstream = http.request(backend + req.url, { method: req.method, headers: req.headers }, response => {
      if (dropReply && pathname.endsWith('/adopt')) {
        dropReply = false; response.resume(); response.on('end', () => { res.setHeader('Content-Type', 'application/json'); res.end('{"ok":'); }); return;
      }
      res.writeHead(response.statusCode, response.headers); response.pipe(res);
    });
    upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('Isolated fixture unavailable'); }); req.pipe(upstream); return;
  }
  if (pathname === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
  const asset = assets.get(pathname); if (!asset) { res.writeHead(404); res.end(); return; } res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
let page, origin, variant, fixture;
const button = name => UI.button(page, name);
const done = name => report.checks.push({ variant, name, passed: true });
const state = () => page.evaluate(() => RunAdoptionAPI.pending().read());
const evidence = async () => (await page.request.get(origin + '/fixture/evidence')).json();
const control = action => page.request.post(origin + '/fixture/control', { data: { action } });
async function waitForAsyncCondition(predicate) {
  // waitForFunction tests the Promise itself; evaluate awaits the predicate's value.
  await expect.poll(() => page.evaluate(predicate), { timeout: 15000 }).toBe(true);
}
async function checkAsyncObservationWait() {
  await page.evaluate(() => { window.__adoptionWaitSamples = 0; });
  try {
    await waitForAsyncCondition(async () => ++window.__adoptionWaitSamples >= 3);
    const samples = await page.evaluate(() => window.__adoptionWaitSamples);
    report.wait_contracts.push({ variant, samples });
    assert.equal(samples, 3, 'An async predicate must be sampled until its resolved value becomes true');
  } finally { await page.evaluate(() => { delete window.__adoptionWaitSamples; }); }
}
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: true, animations: 'disabled' }); report.screenshots.push(file); }
async function reset(mode = 'normal') {
  fixture = await (await page.request.post(origin + '/fixture/reset', { data: { mode } })).json();
  await page.evaluate(ref => { localStorage.removeItem(RunAdoptionAPI.PENDING_KEY); mountAdoption(ref); }, fixture.candidate_ref);
  await button('正式采用').waitFor();
}
async function inspect() { await button('正式采用').click(); await page.getByRole('dialog', { name: '确认正式采用' }).waitFor(); await button('重新预览').waitFor(); }
async function fill(reason = '生产负责人复核：覆盖完整批次，按此候选安排生产。') {
  await page.getByLabel('采用原因', { exact: true }).fill(reason);
  await page.getByLabel('声明人', { exact: true }).fill('现场计划员 张三');
  await page.getByRole('checkbox').check();
}
async function success() { await page.getByRole('dialog', { name: '正式采用回执' }).waitFor(); await page.getByText('已核实：本次生成正式版本 v41，共 2 道工序。', { exact: false }).waitFor(); }
async function layout() {
  const result = await page.evaluate(() => {
    const dialogs = [...document.querySelectorAll('[role="dialog"]')], dialog = dialogs[dialogs.length - 1], r = dialog.getBoundingClientRect();
    const body = dialog.querySelector('.ra-body'), style = getComputedStyle(body), input = dialog.querySelector('textarea');
    const rgb = value => (value.match(/[\d.]+/g) || []).map(Number).slice(0, 3);
    const luma = color => rgb(color).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
    const ratio = (a, b) => { const x = luma(a), y = luma(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
    return { overflow: document.documentElement.scrollWidth > innerWidth, position: getComputedStyle(dialog.parentElement).position,
      headerLayout: getComputedStyle(dialog.querySelector('.modal-head')).display,
      bounds: { x: r.x, y: r.y, right: r.right, bottom: r.bottom, w: innerWidth, h: innerHeight },
      focusInside: dialog.contains(document.activeElement), textContrast: ratio(style.color, getComputedStyle(dialog).backgroundColor),
      inputContrast: input ? ratio(getComputedStyle(input).color, getComputedStyle(input).backgroundColor) : null,
      buttons: [...dialog.querySelectorAll('button.btn')].map(n => { const s = getComputedStyle(n); return { text: n.textContent, disabled: n.disabled, color: s.color, background: s.backgroundColor, opacity: s.opacity, contrast: ratio(s.color, s.backgroundColor) }; }),
      clipped: [...dialog.querySelectorAll('button,input,textarea,dd')].filter(n => n.getClientRects().length && n.scrollWidth > n.clientWidth + 2).map(n => n.tagName + ':' + n.textContent) };
  });
  assert.equal(result.overflow, false); assert.equal(result.focusInside, true); assert.equal(result.position, 'fixed'); assert.equal(result.headerLayout, 'flex');
  assert(result.bounds.x >= 0 && result.bounds.y >= 0 && result.bounds.right <= result.bounds.w + 1 && result.bounds.bottom <= result.bounds.h + 1, JSON.stringify(result));
  assert(result.textContrast >= 4.5 && (result.inputContrast === null || result.inputContrast >= 4.5), JSON.stringify(result));
  assert(result.buttons.every(n => n.disabled || n.contrast >= 4.5), JSON.stringify(result.buttons));
  assert.deepEqual(result.clipped, []); report.layout.push({ variant, ...result });
  for (let i = 0; i < 14; i++) { await page.keyboard.press(i % 3 ? 'Tab' : 'Shift+Tab'); assert(await page.evaluate(() => { const d = [...document.querySelectorAll('[role="dialog"]')].pop(); return d.contains(document.activeElement); })); }
}
async function basic() {
  await reset(); const before = await evidence();
  assert.equal(before.journal.filter(r => r.path.includes(fixture.candidate_ref)).length, 0); done('mount-does-not-preview-or-adopt');
  const get = await (await page.request.get(origin + '/api/workbench/v1/scheduling/candidates/' + fixture.candidate_ref + '/workspace')).json();
  assert(get.ok); assert.equal(get.data.capabilities.adopt, false);
  await inspect(); await page.getByText('v7', { exact: true }).waitFor();
  assert(!(await page.locator('.ra-body').innerText()).includes(fixture.candidate_ref));
  assert(!/write_token|snapshot_ref|write_context/.test(await page.locator('.ra-body').innerText()));
  assert(await button('确认正式采用').isDisabled()); assert.equal(await page.getByLabel('采用原因', { exact: true }).inputValue(), '');
  await fill(); await layout(); await shot('confirm'); assert.equal(await state(), null);
  assert.equal((await evidence()).receipts, 0); await button('取消').click(); assert.equal(await state(), null); done('preview-readonly-manual-input-and-cancel');
  await inspect(); assert.equal(await page.getByLabel('声明人', { exact: true }).inputValue(), '现场计划员 张三');
  assert(await button('确认正式采用').isDisabled()); await page.getByRole('checkbox').check();
  await button('确认正式采用').click(); await success(); await layout(); await shot('receipt');
  const saved = await state(); assert.equal(saved.input.confirm, true); assert.equal((await evidence()).receipts, 1);
  assert(!JSON.stringify(saved).includes('write_token'));
  await page.locator('.ra-records summary').click(); await page.getByText('新正式方案编号：', { exact: false }).waitFor(); await layout(); await shot('expanded-receipt');
  await button('进入正式方案').click(); const nav = await page.evaluate(() => window.nav); assert.equal(nav[0][0], 'analysis');
  assert.notEqual(nav[0][1].plan_ref, fixture.candidate_ref); assert.equal((await page.evaluate(() => window.events)).length, 1);
  const beforeReload = (await evidence()).journal.filter(r => r.path.endsWith('/adopt')).length;
  await page.reload(); await button('查看采用回执').waitFor(); await button('查看采用回执').click(); await success();
  assert.equal((await state()).request_key, saved.request_key);
  assert.equal((await evidence()).journal.filter(r => r.path.endsWith('/adopt')).length, beforeReload); done('receipt-only-navigation-and-reload-lookup');
  const receipt = await (await page.request.get(origin + '/api/workbench/v1/commands/' + saved.request_key)).json();
  const rejected = await page.evaluate(({ receipt, intent }) => {
    const cases = [v => v.data.row_count++, v => v.data.candidate_ref = 'f'.repeat(48), v => v.data.official_plan.plan_ref = intent.candidate_ref,
      v => v.data.official_plan.kind = 'candidate', v => v.data.official_plan.version = 7, v => v.data.official_plan.baseline_ref = null];
    return cases.map(change => { const copy = JSON.parse(JSON.stringify(receipt)); change(copy); try { RunAdoptionAPI.receipt(copy, intent); return false; } catch (_) { return true; } });
  }, { receipt, intent: saved }); assert(rejected.every(Boolean)); done('receipt-identity-scope-and-version-validation');
  await button('完成核实').click(); assert.equal(await state(), null);
  await reset('empty'); await inspect(); await page.getByText('尚无正式计划', { exact: true }).waitFor(); await fill();
  await button('确认正式采用').click(); await success(); done('explicit-empty-formal-baseline');
}
async function rejections() {
  await reset('disabled'); await inspect(); await page.getByText('候选正式采用尚未完成联合接入，保持关闭。', { exact: true }).waitFor();
  assert(await button('确认正式采用').isDisabled()); await control('enable'); await button('重新预览').click(); await page.getByText('v7', { exact: true }).waitFor();
  await button('取消').click(); done('disabled-is-retryable-with-explicit-preview');
  await reset('partial'); await inspect(); await page.locator('.ra-notice').waitFor(); assert(await button('确认正式采用').isDisabled()); await button('取消').click(); done('partial-is-not-adoptable');
  await reset(); await inspect(); await fill(); await control('drift'); await button('确认正式采用').click();
  await page.getByText('输入已保留，请重新预览并确认。', { exact: false }).waitFor(); const stale = await state(); assert.equal(stale.phase, 'rejected');
  await page.reload(); await button('重新核对采用').click(); assert.equal(await page.getByLabel('声明人', { exact: true }).inputValue(), stale.input.declared_operator);
  assert(await button('确认正式采用').isDisabled()); await button('重新预览').click(); await page.locator('.ra-notice').waitFor();
  assert(await button('确认正式采用').isDisabled()); assert.equal((await evidence()).receipts, 0); await shot('drift-blocked'); done('409-retains-input-and-repreview-blocks-drift');
  await button('结束本次未采用').click(); assert.equal(await state(), null); await button('正式采用').waitFor(); done('explicit-rejection-can-release-original-intent');
  await reset(); await inspect(); await fill(); await control('expire'); await button('确认正式采用').click();
  await page.getByText('输入已保留，请重新预览并确认。', { exact: false }).waitFor(); const old = await state();
  await button('重新预览').click(); await page.getByText('v7', { exact: true }).waitFor(); assert(await button('确认正式采用').isDisabled());
  await page.getByRole('checkbox').check(); await button('确认正式采用').click(); await success();
  assert.equal((await state()).request_key, old.request_key); assert.equal((await evidence()).receipts, 1); done('expired-preview-reconfirmed-with-original-key');
}
async function uncertain() {
  await reset('paused'); await inspect(); await fill(); await button('确认正式采用').click();
  await waitForAsyncCondition(async () => (await (await fetch('/fixture/evidence')).json()).started);
  const original = await state(); await button('关闭并保留请求').click();
  await page.evaluate(ref => mountAdoption(ref), fixture.other_ref); await button('核实采用结果').click();
  await page.getByText('存在另一候选的原采用请求，请先核实该记录。', { exact: true }).waitFor();
  assert.equal(await button('确认正式采用').count(), 0); assert.equal(await page.getByLabel('采用原因', { exact: true }).getAttribute('readonly'), '');
  await page.reload(); await button('核实采用结果').click(); await page.getByRole('button', { name: '查询原请求', exact: true }).waitFor();
  assert.equal((await state()).request_key, original.request_key); assert.equal((await evidence()).receipts, 0);
  await control('release'); await waitForAsyncCondition(async () => (await (await fetch('/fixture/evidence')).json()).receipts === 1);
  await button('查询原请求').click(); await success(); done('inflight-close-candidate-switch-refresh-not-recorded-then-lookup');
  await reset(); await inspect(); await fill(); await page.route('**/api/workbench/v1/commands/*', route => route.abort());
  await page.request.post(origin + '/probe/drop-next-adoption-reply'); await button('确认正式采用').click();
  await page.getByRole('dialog', { name: '核实原采用请求' }).waitFor();
  await waitForAsyncCondition(async () => (await (await fetch('/fixture/evidence')).json()).receipts === 1);
  const lost = await state(); await button('关闭并保留请求').click(); await page.reload();
  await button('核实采用结果').click(); assert.equal(await button('进入正式方案').count(), 0); await shot('unknown-preserved');
  await page.unroute('**/api/workbench/v1/commands/*'); await button('查询原请求').click(); await success();
  assert.equal((await state()).request_key, lost.request_key);
  const journal = (await evidence()).journal.filter(r => r.path.endsWith('/adopt') && r.request_key === lost.request_key);
  assert.equal(journal.length, 1); done('lost-real-commit-response-recovered-without-rewrite');
}
async function focusAndStorage() {
  await reset(); await button('外层操作').click();
  await page.getByRole('dialog', { name: '外层候选' }).getByRole('button', { name: '采用方案', exact: true }).click();
  await page.getByText('v7', { exact: true }).waitFor(); await layout(); await shot('nested-focus');
  await page.keyboard.press('Escape'); assert.equal(await page.getByRole('dialog').count(), 1);
  assert(await page.getByRole('dialog').evaluate(n => n.contains(document.activeElement))); await page.keyboard.press('Escape');
  assert.equal(await page.getByRole('dialog').count(), 0); done('nested-top-modal-focus-escape-restores-parent');
  await inspect(); await fill();
  await page.evaluate(() => { window.originalStorageWrite = Storage.prototype.setItem; Storage.prototype.setItem = function(k, v) { if (k === RunAdoptionAPI.PENDING_KEY) throw Error('fixture storage full'); return window.originalStorageWrite.call(this, k, v); }; });
  await button('确认正式采用').click(); await page.getByText('无法保存采用恢复记录', { exact: false }).first().waitFor();
  assert.equal((await evidence()).receipts, 0); await page.evaluate(() => { Storage.prototype.setItem = window.originalStorageWrite; });
  await button('重读恢复记录').click(); await button('重新预览').click(); await page.getByText('v7', { exact: true }).waitFor();
  await page.evaluate(() => { window.failAdoptCallback = true; });
  await page.getByRole('checkbox').check(); await button('确认正式采用').click(); await success(); done('storage-failure-before-write-and-actionable-recovery');
  await page.getByText('采用已核实，但关联页面更新失败，请重新打开正式方案。', { exact: true }).waitFor(); done('parent-refresh-failure-does-not-erase-receipt');
  assert.deepEqual(await page.evaluate(() => [localStorage.getItem('aps_workbench_run_pending_v1'), localStorage.getItem('aps_workbench_batch_pending_v1')]), ['unrelated-run', 'unrelated-batch']);
  done('independent-pending-namespace');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    assert(![63938, 51093, 56264].includes(server.address().port));
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.')); origin = 'http://127.0.0.1:' + server.address().port;
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      variant = width + '-' + theme; const row = { variant, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height: width === 1920 ? 1080 : 900 }, timezoneId: 'America/New_York' });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme);
        localStorage.setItem('aps_workbench_run_pending_v1', 'unrelated-run'); localStorage.setItem('aps_workbench_batch_pending_v1', 'unrelated-batch'); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(15000);
      page.on('pageerror', error => report.errors.push(error.stack || error.message)); page.on('dialog', dialog => { report.dialogs.push(dialog.type()); dialog.dismiss(); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      try { await page.goto(origin); await checkAsyncObservationWait(); await basic(); await rejections(); await uncertain(); await focusAndStorage(); row.passed = true; }
      catch (error) { row.error = error.stack; await shot('FAILED'); throw error; }
      finally { await control('release'); await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []);
    console.log(JSON.stringify({ browser: report.browser, checks: report.checks.length, variants: report.variants.length, output }));
  } finally { if (browser) await browser.close(); server.close(); fs.writeFileSync(path.join(output, 'adoption-widgets.json'), JSON.stringify(report, null, 2)); }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
