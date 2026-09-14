'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require('playwright');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), root = ready.root, origin = ready.url;
const scope = process.env.WORKBENCH_PROCESS_STAGE_SCOPE || 'all';
assert(['regular', 'large', 'all'].includes(scope));
const report = {scope: 'isolated-stage-write-workflow-' + scope, build_id: ready.assets.build_id,
  input_method: 'Real clicks and keyboard input; large route and each visible numeric field use keyboard.insertText; only preview failure is injected',
  cases: [], screenshots: [], requests: [], errors: [], external: [], http_errors: [], expected_failures: []};
let page, state;
const source = () => page.locator('[data-process-source-editor]:visible');
const hours = () => page.locator('[data-process-hours-editor]:visible');
const entry = () => page.getByRole('dialog', {name: /^录入工艺路线 · /});
async function type(field, value) { await field.click(); await field.fill(''); await field.type(String(value), {delay: 0}); }
async function insertText(field, value) {
  value = String(value);
  await field.click(); await field.fill(''); await page.keyboard.insertText(value);
  assert.equal(await field.inputValue(), value);
}
async function responseTo(suffix, action) {
  const pending = page.waitForResponse(r => new URL(r.url()).pathname.endsWith(suffix));
  const [response] = await Promise.all([pending, Promise.resolve().then(action)]);
  assert.equal(response.status(), 200, await response.text()); return response.json();
}
async function open(code) {
  const workspace = page.locator('[data-process-workspace]');
  await type(workspace.getByRole('searchbox', {name: '搜索图号、名称、路线', exact: true}), code);
  await responseTo('/entities/part', () => workspace.getByRole('button', {name: '搜索', exact: true}).click());
  const result = await responseTo('/entities/part/' + await workspace.getByRole('button', {name: '查看 ' + code, exact: true})
    .locator('xpath=ancestor::tr').getAttribute('data-process-ref'), () => workspace.getByRole('button', {name: '查看 ' + code, exact: true}).click());
  await page.getByRole('tablist', {name: '零件工艺步骤', exact: true}).waitFor(); return result;
}
async function close() { await page.getByRole('button', {name: '关闭详情', exact: true}).click(); await page.getByRole('tablist', {name: '零件工艺步骤', exact: true}).waitFor({state: 'detached'}); }
async function tab(number) { await page.getByRole('tab', {name: new RegExp('^' + number + ' ')}).click(); }
async function saved(action, click) {
  const refresh = page.waitForResponse(r => /\/entities\/part\/[0-9a-f]{48}$/.test(new URL(r.url()).pathname));
  const [response, receipt] = await Promise.all([refresh, responseTo('/' + action, click)]);
  assert(['committed', 'unchanged'].includes(receipt.result)); assert(receipt.receipt_ref);
  assert.equal(response.status(), 200); return response.json();
}
async function reloadDraft(scope) {
  await responseTo('/entities/part/' + (await currentRef()), () => scope.getByRole('button', {name: '刷新详情并保留草稿', exact: true}).click());
  await scope.getByRole('button', {name: '采用最新资料', exact: true}).click();
}
let partRef;
async function currentRef() { assert(partRef); return partRef; }
async function snapshot(name) {
  const geometry = await page.evaluate(() => ({width: innerWidth, height: innerHeight,
    scroll: document.documentElement.scrollWidth, nodes: document.querySelectorAll('*').length,
    options: document.querySelectorAll('option,[role="option"]').length,
    rows: Array.from(document.querySelectorAll('.process-detail table')).filter(n => n.getClientRects().length).map(n => ({name: n.getAttribute('aria-label'), rows: n.querySelectorAll('tbody tr').length})),
    dialogs: Array.from(document.querySelectorAll('[role="dialog"]')).filter(n => n.getClientRects().length).map(n => {
      const r = n.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};})}));
  assert(geometry.scroll <= geometry.width + 1, JSON.stringify(geometry));
  assert(geometry.nodes < 20000 && geometry.options < 2500, 'Unbounded DOM: ' + JSON.stringify(geometry));
  assert(geometry.rows.every(row => row.rows <= 50), 'Unpaginated stage: ' + JSON.stringify(geometry));
  assert(geometry.dialogs.every(r => r.left >= 0 && r.right <= geometry.width + 1 && r.top >= 0 && r.bottom <= geometry.height + 1), JSON.stringify(geometry));
  const file = state + '-' + name + '.png'; await page.screenshot({path: path.join(root, 'screenshots', file)});
  report.screenshots.push({state, name, file, geometry});
}
async function run(name, fn) {
  const started = Date.now();
  console.log(state + ' / ' + name + ': started');
  try { await fn(); report.cases.push({state, name, passed: true, milliseconds: Date.now() - started}); console.log(state + ' / ' + name + ': passed'); }
  catch (error) { report.cases.push({state, name, passed: false, error: error.stack});
    fs.writeFileSync(path.join(root, state + '-' + name + '-FAILED.html'), await page.content());
    fs.writeFileSync(path.join(root, state + '-' + name + '-FAILED.txt'), await page.locator('body').innerText());
    await page.screenshot({path: path.join(root, 'screenshots', state + '-' + name + '-FAILED.png')}); throw error; }
  finally { writeReport(); }
}
function writeReport() {
  report.summary = {cases: report.cases.length, failed: report.cases.filter(row => !row.passed).length, screenshots: report.screenshots.length};
  fs.writeFileSync(path.join(root, 'process-stage-probe-results.json'), JSON.stringify(report, null, 2) + '\n');
}
async function confirmSource() {
  await responseTo('/stage-preview', () => source().getByRole('button', {name: '检查归属', exact: true}).click());
  return saved('source_confirm', () => source().getByRole('button', {name: '完成归属 · 解锁工时', exact: true}).click());
}
async function walkPages(scope, checkName, edit) {
  let pages = 0, edited = 0;
  while (true) {
    if (edit) edited += await edit(scope);
    await scope.getByRole('checkbox', {name: checkName, exact: true}).check(); pages++;
    const next = scope.getByRole('button', {name: '下一页', exact: true});
    if (!(await next.count()) || await next.isDisabled()) break;
    const previous = await scope.getByRole('checkbox', {name: /^确认工序 /}).first().getAttribute('aria-label');
    await next.click();
    await scope.getByRole('checkbox', {name: previous, exact: true}).waitFor({state: 'detached'});
  }
  return {pages, edited};
}
async function smallWorkflow() {
  const initial = await open('STAGE-' + state); partRef = initial.data.ref;
  await tab(1); await page.getByRole('button', {name: '录入路线', exact: true}).click();
  const field = entry().getByRole('textbox', {name: '路线文字', exact: true});
  const text = '10车削20热处理30检验'; await type(field, text);
  await reloadDraft(entry()); assert.equal(await field.inputValue(), text);
  const pattern = '**/process/*/route-preview';
  await page.route(pattern, async route => {
    report.expected_failures.push({state, url: route.request().url(), status: 500});
    await route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({ok: false, committed: false,
      error: {code: 'storage_failure', message: 'Stage fixture preview failure', fields: [], retryable: true, request_ref: 'injected'}})});
  }, {times: 1});
  await entry().getByRole('button', {name: '预检路线', exact: true}).click();
  await entry().getByText('Stage fixture preview failure', {exact: true}).waitFor();
  assert.equal(await field.inputValue(), text);
  await responseTo('/route-preview', () => entry().getByRole('button', {name: '重试预检', exact: true}).click());
  await snapshot('route-recovered');
  let detail = await saved('route_confirm', () => entry().getByRole('button', {name: '确认保存路线', exact: true}).click());
  assert.equal(detail.data.workflow.route.state, 'confirmed'); await source().waitFor();
  await source().getByRole('button', {name: '选择工序 10 工种', exact: true}).click();
  const picker = page.getByRole('dialog', {name: '选择自制工种 · 工序 10', exact: true});
  await type(picker.getByRole('searchbox', {name: '搜索自制工种', exact: true}), '车削');
  await responseTo('/entities/op_type', () => picker.getByRole('button', {name: '搜索', exact: true}).click());
  await picker.getByRole('button', {name: '采用 车削', exact: true}).click();
  await source().getByRole('checkbox', {name: '确认本页已核对工序', exact: true}).check();
  await reloadDraft(source());
  assert(await source().getByRole('checkbox', {name: '确认工序 10 归属', exact: true}).isChecked());
  await snapshot('source-reviewed'); detail = await confirmSource();
  assert.equal(detail.data.workflow.source.state, 'confirmed'); await hours().waitFor();
  await type(hours().getByLabel('工序 10 单件工时', {exact: true}), '2.125');
  await type(hours().getByLabel('工序 20 外协周期', {exact: true}), '4.25');
  await type(hours().getByLabel('外协组 20 至 20 总周期', {exact: true}), '9.5');
  await reloadDraft(hours());
  assert.equal(await hours().getByLabel('工序 10 单件工时', {exact: true}).inputValue(), '2.125');
  await hours().getByRole('checkbox', {name: '确认本页已核对工时', exact: true}).check();
  await hours().getByRole('button', {name: '保存工时', exact: true}).click();
  await hours().getByText('单件工时为 0，需要明确勾选复核。', {exact: true}).waitFor();
  await hours().getByRole('checkbox', {name: '已复核单件工时为0', exact: true}).check();
  await snapshot('hours-reviewed');
  detail = await saved('hours_confirm', () => hours().getByRole('button', {name: '保存工时', exact: true}).click());
  assert(detail.data.workflow.ready); await snapshot('ready'); await close();
  detail = await open('STAGE-' + state);
  assert(detail.data.workflow.ready); assert.equal(detail.data.operations[0].unit_hours, 2.125);
  assert.equal(detail.data.operations[1].external_days, 4.25); assert.equal(detail.data.external_groups[0].total_days, 9.5);
  await close();
}
async function scaleWorkflow(count) {
  const code = 'STAGE-' + count, initial = await open(code); partRef = initial.data.ref;
  assert.equal(initial.data.operations.length, count);
  if (count === 2000) {
    await tab(1); await page.getByRole('button', {name: '录入路线', exact: true}).click();
    await insertText(entry().getByRole('textbox', {name: '路线文字', exact: true}), Array.from({length: count}, (_, i) => (i + 1) + '车削').join(';'));
    const preview = await responseTo('/route-preview', () => entry().getByRole('button', {name: '预检路线', exact: true}).click());
    assert.equal(preview.data.operations.length, count); await snapshot('2000-route-preview');
    await saved('route_confirm', () => entry().getByRole('button', {name: '确认保存路线', exact: true}).click());
  }
  await tab(2);
  await source().waitFor(); await snapshot(count + '-source-dom');
  const review = await walkPages(source(), '确认本页已核对工序'); assert.equal(review.pages, count / 50);
  const sourceSaved = await confirmSource(); assert.equal(sourceSaved.data.operations.length, count); await tab(3); await hours().waitFor();
  const filled = await walkPages(hours(), '确认本页已核对工时', count === 2000 ? async scope => {
    const fields = scope.locator('input[aria-label$=" 单件工时"]'); const size = await fields.count();
    for (let i = 0; i < size; i++) {
      const field = fields.nth(i), label = await field.getAttribute('aria-label'), seq = Number(label.match(/^工序 (\d+)/)[1]);
      await insertText(field, seq + .125);
    }
    return size;
  } : null);
  assert.equal(filled.pages, count / 50); assert.equal(filled.edited, count === 2000 ? count : 0);
  await snapshot(count + '-hours-last-page');
  const detail = await saved('hours_confirm', () => hours().getByRole('button', {name: '保存工时', exact: true}).click());
  assert(detail.data.workflow.ready); assert.equal(detail.data.operations.length, count);
  assert.equal(new Set(detail.data.operations.map(row => row.ref)).size, count);
  assert(detail.data.operations.every(row => row.unit_hours === (count === 2000 ? Number(row.sequence) + .125 : 1)));
  assert(detail.data.operations.every(row => row.confirmation.hours.state === 'confirmed'));
  await snapshot(count + '-ready'); await close();
}
(async () => {
  let browser;
  try {
    browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
    report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    for (const viewport of [{width: 1920, height: 1080}, {width: 1392, height: 924}]) for (const theme of ['light', 'dark']) {
      state = viewport.width + '-' + theme;
      const context = await browser.newContext({viewport, timezoneId: 'Asia/Shanghai'});
      await context.addInitScript(value => { localStorage.setItem('aps_theme', value); localStorage.setItem('aps_kit_theme', value); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(30000);
      page.on('pageerror', error => report.errors.push({state, message: error.stack}));
      page.on('request', request => {
        if (!request.url().startsWith(origin + '/') && !request.url().startsWith('data:')) report.external.push(request.url());
        if (request.url().startsWith(origin + '/api/')) report.requests.push({state, method: request.method(), path: new URL(request.url()).pathname});
      });
      page.on('response', response => { if (response.status() >= 400) report.http_errors.push({state, url: response.url(), status: response.status()}); });
      await page.goto(ready.resource_url); await page.locator('.hb-tile').first().waitFor();
      await responseTo('/entities/part', () => page.locator('.hb-tile').filter({hasText: /^工艺/}).click());
      if (scope !== 'large') await run('route-source-hours-ready-recovery', smallWorkflow);
      if (scope !== 'regular') {
        await run('2000-paged-full-input', () => scaleWorkflow(2000));
        await run('10000-existing-stage', () => scaleWorkflow(10000));
      }
      await context.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
    assert(report.http_errors.every(row => report.expected_failures.some(expected => expected.state === row.state && expected.url === row.url && expected.status === row.status)));
  } finally {
    writeReport();
    if (browser) await browser.close();
    writeReport();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
