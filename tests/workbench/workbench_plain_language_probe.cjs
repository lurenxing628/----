'use strict';
// Real browser, current components and resource transport; all API responses are fixtures.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright'), H = require('./plan_ui_browser_harness.cjs');
const { compile } = require('../../scripts/workbench/compile.cjs');
const F = require('./plan_ui_fixtures.cjs');
const output = path.resolve(process.argv[2] || '');
assert(process.argv[2] && output !== H.root && !output.startsWith(H.root + path.sep), 'Use an artifact directory outside checkout');
fs.mkdirSync(output, { recursive: true });
const report = { scope: 'plain-language-current-source-mock-api', production_persistence_tested: false,
  win7_hardware_tested: false, pending_storage_tested: false, cases: [], screenshots: [], errors: [], external: [], unexpected_requests: [] };
const server = H.server(report), original = server.listeners('request')[0];
const extraFiles = ['WorkbenchGuards.js', 'WorkbenchGuardHost.jsx', 'resource-api.js', 'ResourceForms.jsx'];
const sources = extraFiles.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(H.root, 'frontend/workbench/app', name), 'utf8') }));
const extra = compile({ babel_path: path.join(H.root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
report.sources.push(...sources.map(item => ({ path: item.path, sha256: H.hash(item.code) })));
for (const name of ['workbench_plain_language_probe.cjs', 'test_workbench_plain_language.py']) report.probes.push({ path: 'tests/workbench/' + name, sha256: H.hash(fs.readFileSync(path.join(__dirname, name))) });
const manifest = JSON.parse(fs.readFileSync(path.join(H.root, 'static/workbench/asset-manifest.json')));
const resourceHarness = `
const params = new URLSearchParams(location.search);
document.documentElement.dataset.theme = params.get('theme') || 'light';
const raw = '用户原文：上下文、容差、兑现、serverScope';
const entity = {ref:'${F.ref(1000)}',business_code:'PLAIN-001',label:'原名称',status:'active',
  fields:{spec:raw,unit:'kg',stock_qty:5,hidden_legacy:raw},relationships:{},issues:[],write_context:null};
const context = {write_token:'fixture-write-token',capabilities:{'material.update':true},blocked_reasons:[]};
window.resourceFixture = {closed:false};
function ResourceHarness() {
  const adapter = React.useMemo(()=>APSResourceAPI.create(), []);
  const command = APSResourceSession.useCommand(adapter);
  const [refresh,setRefresh] = React.useState({}), [closed,setClosed] = React.useState(false);
  resourceFixture.command = command; resourceFixture.entity = entity; resourceFixture.setRefresh = setRefresh;
  const close = () => { if(command.reset()) {resourceFixture.closed=true;setClosed(true);} };
  return closed ? React.createElement('p', {role:'status'}, '已关闭') : React.createElement(ResourceForms,
    {adapter,kind:'material',action:'update',entity,writeContext:context,source:'production',command,
      refreshState:refresh,onRefresh:()=>setRefresh({done:true}),onClose:close});
}
ReactDOM.createRoot(document.getElementById('resource-root')).render(React.createElement(React.Fragment,null,
  React.createElement(WorkbenchGuardHost),React.createElement(ResourceHarness)));
`;
const shared = manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-'));
const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  manifest.styles.map(name => '<link rel="stylesheet" href="/static/' + name + '">').join('') + '</head><body class="aps-workbench"><main class="plana"><div id="resource-root"></div></main>' +
  shared.map(name => '<script src="/static/' + name + '"></script>').join('') +
  ['WorkbenchReferences.jsx', 'resource-contract.js', 'resource-session.js', 'ResourceControls.jsx'].map(name => '<script src="/fixture/' + name + '.js"></script>').join('') +
  extraFiles.map(name => '<script src="/plain/' + name + '"></script>').join('') + '<script>' + resourceHarness + '</script></body></html>';
server.removeListener('request', original);
server.on('request', (req, res) => {
  if (req.url.startsWith('/plain-resource')) { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  const index = extraFiles.findIndex(name => req.url === '/plain/' + name);
  if (index >= 0) { res.setHeader('Content-Type', 'application/javascript'); res.end(extra.outputs[index].code); return; }
  original(req, res);
});
const pendingKey = 'aps_workbench_resource_pending_v1';
const raw = '用户原文：上下文、容差、兑现、serverScope';
const terminal = (result = 'committed', data = {}) => ({ ok: true, result, replayed: false, receipt_ref: 'fixture-receipt',
  data: { entity_ref: F.ref(1000), ...data }, warnings: [] });
const missing = { ok: true, state: 'not_recorded', receipt: null, may_be_in_flight: true };
const rejected = { ok: false, committed: false, error: { code: 'stale_write', message: '资料已变化，本次未保存。', fields: [] } };
let state, origin;
async function check(name, action) {
  const row = { state: state.id, name, passed: false }; report.cases.push(row);
  try { await action(); row.passed = true; }
  catch (error) { row.error = error.stack; throw error; }
  finally { console.log(state.id + ' / ' + name + ': ' + (row.passed ? 'passed' : 'FAILED')); }
}
async function shot(page, name) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
  const geometry = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
    clipped: Array.from(document.querySelectorAll('.modal button,.modal-h2,.plan-heading h2')).filter(el => el.scrollWidth > el.clientWidth + 1).map(el => el.textContent),
    dialog: Array.from(document.querySelectorAll('[role="dialog"]')).map(el => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, height: innerHeight }; }) }));
  assert(geometry.scroll <= geometry.width + 1, JSON.stringify(geometry));
  assert.deepEqual(geometry.clipped, []);
  assert(geometry.dialog.every(r => r.left >= 0 && r.right <= geometry.width + 1 && r.top >= 0 && r.bottom <= r.height + 1));
  const filename = path.join(output, state.id + '-' + name + '.png');
  await page.screenshot({ path: filename, animations: 'disabled' }); report.screenshots.push(filename);
}
async function mountPlan(page, spec = {}) {
  await page.evaluate(spec => mountPlan(spec), { theme: state.theme, context: { plan_ref: F.ref(1) }, ...spec });
}
async function selectFirstPlanTask(page) {
  const reference = await page.locator('[data-plan-task]').first().getAttribute('data-plan-task');
  const target = page.locator('[data-plan-task="' + reference + '"]').first();
  const context = await page.evaluate(() => ({ context: fixture.spec.context,
    reads: fixture.calls.filter(row => row.type === 'workspace').map(row => ({ ref: row.ref, scope: row.scope })) }));
  const evidence = { state: state.id, task_ref: reference, context, method: 'pointer' };
  if (state.width === 390) {
    await target.scrollIntoViewIfNeeded();
    evidence.geometry = await target.evaluate(node => {
      const rect = element => { const r = element.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }; };
      const task = rect(node), board = rect(node.closest('[data-plan-scroll]')), frozen = rect(node.closest('.plan-lane').querySelector('.plan-resource'));
      const center = { x: (task.left + task.right) / 2, y: (task.top + task.bottom) / 2 }, hit = document.elementFromPoint(center.x, center.y);
      const left = Math.max(0, board.left, frozen.right), right = Math.min(innerWidth, board.right);
      return { viewport: { width: innerWidth, height: innerHeight }, task, board, frozen, center,
        center_hits_task: !!hit && node.contains(hit), center_hits_frozen: !!(hit && hit.closest('.plan-resource')),
        center_hit: hit && { tag: hit.tagName, className: hit.className, text: hit.textContent },
        visible_time_width: Math.max(0, right - left), visible_task_width: Math.max(0, Math.min(task.right, right) - Math.max(task.left, left)) };
    });
  }
  await target.click();
  await page.waitForFunction(ref => Array.from(document.querySelectorAll('[data-plan-task][aria-pressed="true"]')).some(node => node.dataset.planTask === ref), reference);
  assert.deepEqual(await page.evaluate(() => ({ context: fixture.spec.context,
    reads: fixture.calls.filter(row => row.type === 'workspace').map(row => ({ ref: row.ref, scope: row.scope })) })), context);
  (report.plan_selections || (report.plan_selections = [])).push(evidence);
}
async function plans(page) {
  await page.goto(origin);
  await check('plan-read-loading-cancel-failure-missing', async () => {
    await mountPlan(page, { hold: 'workspace' });
    await page.getByText('正在读取所选计划、工序安排和分析结果…', { exact: true }).waitFor();
    await page.getByRole('button', { name: '取消计划读取', exact: true }).click();
    await page.getByText('计划读取已取消，未显示上次读取的内容。', { exact: true }).waitFor();
    await page.evaluate(() => { fixture.held.splice(0).forEach(resolve => resolve()); });
    assert.equal(await page.locator('[data-plan-gantt]').count(), 0);
    await mountPlan(page, { workspaceFailure: '所选计划读取失败。' });
    await page.getByText('所选计划读取失败。', { exact: true }).waitFor();
    assert.equal(await page.locator('[data-plan-gantt]').count(), 0);
    await page.evaluate(() => { fixture.spec.workspaceFailure = null; delete fixture.adapter.workspace; });
    await page.getByRole('button', { name: '重新读取所选计划', exact: true }).click();
    await page.getByText('暂时无法读取计划，请稍后重试。', { exact: true }).waitFor();
  });
  await check('plan-scope-export-not-search-no-json-change', async () => {
    await mountPlan(page, { context: { plan_ref: F.ref(1), range_start: '2026-09-09T23:00:00', range_end: '2026-09-10T01:00:00' } });
    await page.locator('[data-plan-gantt]').waitFor();
    await page.getByText(/每道安排的起止时间完整保留/).waitFor();
    await page.getByRole('searchbox').fill('钻孔');
    await page.getByText(/只影响甘特图显示；分析表和导出仍包含/).waitFor();
    await page.getByRole('button', { name: '导出', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '导出计划', exact: true }); await dialog.waitFor();
    const text = await dialog.innerText();
    assert(text.includes('共 5 道工序安排')); assert(text.includes('找到 1 道安排')); assert(text.includes('全部 5 道安排，不是搜索结果'));
    assert(text.includes('不会自动更换计划或继续下载')); assert(!/serverScope|服务端|快照|投影/.test(text));
    await shot(page, 'plan-export');
    const download = page.waitForEvent('download'); await dialog.getByRole('button', { name: '下载 CSV', exact: true }).click();
    assert.equal((await download).suggestedFilename(), '计划读取范围.csv');
    const call = await page.evaluate(() => fixture.calls.find(row => row.type === 'export'));
    assert.deepEqual(call.scope, { format: 'csv', snapshot_ref: 'workspace-ui:' + F.ref(1) + ':2026-09-09T23:00:00', range_start: '2026-09-09T23:00:00', range_end: '2026-09-10T01:00:00' });
    assert.equal(await page.evaluate(() => fixture.writes), 0);
  });
  await check('plan-export-failure-preserves-warning-and-selection', async () => {
    await page.evaluate(() => { fixture.spec.exportFailure = '计划内容已变化，请重新读取。'; });
    await page.getByRole('button', { name: '导出', exact: true }).click();
    await page.getByRole('button', { name: '下载 CSV', exact: true }).click();
    await page.getByText('计划内容已变化，请重新读取。', { exact: true }).waitFor();
    assert.equal(await page.getByRole('dialog', { name: '导出计划', exact: true }).count(), 1);
    assert.equal(await page.getByText(/^已发起下载：/).count(), 0);
    assert.equal((await page.evaluate(() => fixture.calls.filter(row => row.type === 'workspace'))).length, 1);
    await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  });
  await check('plan-unknown-analysis-not-zero-or-complete', async () => {
    await mountPlan(page, { unknown: true }); await page.locator('[data-plan-gantt]').waitFor();
    const table = page.getByRole('table', { name: '交付风险列表' });
    assert((await table.innerText()).includes('无法核实')); assert((await table.innerText()).includes('已安排部分结束于'));
    await selectFirstPlanTask(page);
    assert((await page.locator('[data-plan-inspector]').innerText()).includes('不代表批次完工'));
    await page.getByRole('button', { name: '资源负荷', exact: true }).click();
    assert((await page.getByRole('region', { name: '计划分析', exact: true }).innerText()).includes('设备有空闲时间不代表人员已就绪'));
    assert((await page.getByRole('table', { name: '资源负荷列表' }).innerText()).includes('无法核实'));
    await shot(page, 'plan-unknown-analysis');
  });
  await check('plan-initial-comparison-keeps-unverified-boundaries', async () => {
    await mountPlan(page, { context: { plan_ref: F.ref(3) } }); await page.locator('[data-plan-gantt]').waitFor();
    await selectFirstPlanTask(page);
    await page.getByRole('button', { name: '查看初始安排', exact: true }).click();
    const detail = page.locator('[data-plan-inspector]');
    assert((await detail.innerText()).includes('初始计划安排'));
    assert((await detail.innerText()).includes('未核实初始计划的交付风险'));
    assert((await detail.innerText()).includes('初始计划的日历和占用未单独核实'));
    assert(await detail.getByRole('button', { name: /^调整此工序(?:：|$)/ }).isDisabled());
    assert.equal(await detail.getByRole('button', { name: /^保存(?:试调)?(?:：|$)/ }).count(), 0);
    assert.equal(await detail.locator('.plan-actions button:not(:disabled)').count(), 0);
    assert.equal(await page.evaluate(() => fixture.writes), 0);
  });
}
async function resources(page) {
  let api;
  await page.route('**/api/workbench/v1/**', async route => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    if (request.method() === 'POST') {
      api.posts.push({ path: pathname, body: request.postDataJSON() });
      if (api.hold) await new Promise(resolve => { api.release = resolve; });
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(api.response) });
    } else {
      api.lookups.push(pathname);
      if (api.holdLookup) await new Promise(resolve => { api.releaseLookup = resolve; });
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(api.lookup) });
    }
  });
  async function open(response, lookup = missing) {
    await page.evaluate(() => sessionStorage.clear());
    api = { posts: [], lookups: [], response, lookup };
    await page.goto(origin + '/plain-resource?theme=' + state.theme);
    await page.getByRole('dialog', { name: '编辑物料', exact: true }).waitFor();
    await page.locator('input[name="label"]').fill(raw);
  }
  const phase = value => page.waitForFunction(value => resourceFixture.command.phase === value, value);
  const save = () => page.getByRole('button', { name: '保存', exact: true }).click();
  const noSuccess = async () => {
    assert.equal(await page.getByText(/^(已保存。?|服务器已确认提交。|已重新读取最新数据。)$/).count(), 0);
    assert(await page.getByRole('button', { name: '保存', exact: true }).isDisabled());
    assert(await page.getByRole('button', { name: '关闭', exact: true }).isDisabled());
  };
  await check('resource-sending-success-refresh-failure-keeps-receipt', async () => {
    const response = terminal(); response.warnings = [{ code: 'raw_warning', message: raw }];
    await open(response); api.hold = true; await save(); await phase('sending');
    await page.getByText('正在提交，请勿重复保存…', { exact: true }).waitFor(); await noSuccess();
    const before = await page.evaluate(key => sessionStorage.getItem(key), pendingKey);
    assert(!before.includes(raw)); assert(!before.includes('write_token')); api.release(); await phase('done');
    assert(await page.getByText(/^(已保存。?|服务器已确认提交。)$/).isVisible());
    assert.deepEqual(api.posts[0].body.input, { label: raw });
    assert.equal(api.posts[0].body.write_token, 'fixture-write-token');
    assert.equal(await page.locator('input[name="spec"]').inputValue(), raw);
    assert.equal(await page.evaluate(() => resourceFixture.entity.fields.hidden_legacy), raw);
    assert((await page.getByRole('dialog').innerText()).includes(raw));
    const result = await page.evaluate(() => resourceFixture.command.result);
    assert.deepEqual(result, response);
    await page.evaluate(() => resourceFixture.setRefresh({ loading: true }));
    await page.getByText('正在重读列表和详情…', { exact: true }).waitFor();
    await page.evaluate(() => resourceFixture.setRefresh({ error: APSResourceContract.failure('已保存，但最新列表读取失败。') }));
    await page.getByText('已保存，但最新列表读取失败。', { exact: true }).waitFor();
    await page.getByText('最新数据尚未确认。', { exact: true }).waitFor();
    assert.deepEqual(await page.evaluate(() => resourceFixture.command.result), result);
    await shot(page, 'resource-saved-refresh-failed');
    await page.getByRole('button', { name: '重新读取保存结果', exact: true }).click();
    await page.getByText('已重新读取最新数据。', { exact: true }).waitFor(); assert.equal(api.posts.length, 1);
  });
  await check('resource-unchanged-keeps-unchanged-state', async () => {
    await open(terminal('unchanged')); await save(); await phase('done');
    assert((await page.getByRole('dialog').innerText()).includes('内容未变化'));
    assert.equal(await page.evaluate(() => resourceFixture.command.result.result), 'unchanged');
  });
  await check('resource-partial-preserves-item-failures-and-raw-values', async () => {
    await open(terminal('partial', { items: [{ label: raw, result: 'failed', error: { message: raw } }, { label: '第二项', result: 'skipped' }] }));
    await save(); await phase('done'); await page.getByText('部分操作完成，请核对逐项结果。', { exact: true }).waitFor();
    assert((await page.locator('li').allTextContents()).some(text => text.includes(raw + '：失败；' + raw)));
    assert((await page.locator('li').allTextContents()).some(text => text.includes('第二项：未执行')));
    assert.equal(await page.getByText(/^(已保存。?|服务器已确认提交。)$/).count(), 0);
  });
  await check('resource-explicit-failure-is-editable-not-success', async () => {
    await open(rejected); await save(); await phase('rejected');
    await page.getByText(rejected.error.message, { exact: true }).waitFor();
    assert(!(await page.getByRole('button', { name: '保存', exact: true }).isDisabled()));
    assert.equal(await page.locator('input[name="label"]').inputValue(), raw);
    assert.equal(await page.evaluate(key => sessionStorage.getItem(key), pendingKey), null);
    assert.equal(await page.getByText(/^(已保存。?|服务器已确认提交。)$/).count(), 0);
  });
  for (const [name, response, lookup] of [
    ['unknown', { ok: false, committed: 'unknown', error: { code: 'uncertain', message: '提交结果未知，请核对原请求。', fields: [] } }, missing],
    ['pending', { ok: true, state: 'pending' }, missing],
    ['missing-receipt', { ...terminal(), receipt_ref: '' }, missing],
    ['failed-lookup', { ok: true, state: 'pending' }, { ok: false, committed: 'unknown', error: { code: 'unavailable', message: '原请求结果暂时无法核实。', fields: [] } }]
  ]) await check('resource-' + name + '-reload-checks-original-before-unlock', async () => {
    await open(response, lookup); await save(); await phase('pending');
    await page.waitForFunction(() => document.body.textContent.includes('结果待核实。请保留当前页面'));
    await noSuccess();
    const stored = await page.evaluate(key => JSON.parse(sessionStorage.getItem(key)), pendingKey);
    assert.equal(stored.request_key, api.posts[0].body.request_key);
    assert.deepEqual(Object.keys(stored).sort(), ['action', 'kind', 'ref', 'request_key']);
    await page.reload(); await phase('pending'); await noSuccess(); assert.equal(api.posts.length, 1);
    assert(api.lookups.every(url => url.endsWith('/' + stored.request_key)));
    assert.deepEqual(await page.evaluate(key => JSON.parse(sessionStorage.getItem(key)), pendingKey), stored);
    api.holdLookup = true; await page.getByRole('button', { name: '查询原请求回执', exact: true }).click(); await phase('checking');
    await page.getByText('正在核实原请求的回执…', { exact: true }).waitFor(); await noSuccess();
    await page.waitForFunction(() => resourceFixture.command.phase === 'checking');
    while (!api.releaseLookup) await new Promise(resolve => setTimeout(resolve, 5));
    api.lookup = { ...terminal(), replayed: true }; api.releaseLookup(); await phase('done');
    assert(await page.getByText(/^(已保存。?|服务器已确认提交。)$/).isVisible());
    assert.equal(await page.evaluate(() => resourceFixture.command.result.replayed), true); assert.equal(api.posts.length, 1);
    await page.getByText('最新数据尚未确认。', { exact: true }).waitFor();
    await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).last().click();
    await page.getByText('已关闭', { exact: true }).waitFor();
    assert.equal(await page.evaluate(key => sessionStorage.getItem(key), pendingKey), null);
    report.pending_storage_tested = true;
  });
  await check('resource-controls-no-adapter-keeps-original-choice', async () => {
    await page.evaluate(() => {
      const element = document.createElement('div'); document.body.appendChild(element);
      ReactDOM.createRoot(element).render(React.createElement(ResourceControls.Choice, { adapter: {},
        field: { kind: 'machine_group', key: 'group_ref', label: '设备组', catalog: true }, value: resourceFixture.entity.ref,
        original: { relationships: { group_ref: resourceFixture.entity.ref, group: { ref: resourceFixture.entity.ref, label: '原设备组' } } }, onChange: () => {} }));
    });
    await page.getByText('暂时无法读取可选资料，请稍后重试。', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('设备组', { exact: true }).inputValue(), F.ref(1000));
    const button = page.getByRole('button', { name: '维护设备组', exact: true });
    assert(await button.isDisabled()); assert.equal(await button.getAttribute('title'), '暂不支持维护设备组。');
  });
}
async function main() {
  let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true }); report.browser = browser.version();
    assert(report.browser.startsWith('109.'));
    for (state of [{ id: 'desktop-light', theme: 'light', width: 1440, height: 1000 }, { id: 'desktop-dark', theme: 'dark', width: 1440, height: 1000 },
      { id: 'mobile-light', theme: 'light', width: 390, height: 844 }, { id: 'mobile-dark', theme: 'dark', width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport: { width: state.width, height: state.height }, acceptDownloads: true });
      const page = await context.newPage(); page.setDefaultTimeout(12000);
      page.on('pageerror', error => report.errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
      page.on('request', request => { if (!request.url().startsWith(origin) && !request.url().startsWith('blob:')) report.external.push(request.url()); });
      try { await plans(page); await resources(page); }
      finally { await context.close(); }
    }
  } catch (error) { report.runner_error = error.stack; }
  finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    report.summary = { cases: report.cases.length, failed: report.cases.filter(row => !row.passed).length, screenshots: report.screenshots.length };
    fs.writeFileSync(path.join(output, 'plain-language-result.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify(report.summary));
    if (report.runner_error || report.summary.failed || report.errors.length || report.external.length || report.unexpected_requests.length) process.exitCode = 1;
  }
}
main();
