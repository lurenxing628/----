'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const input = JSON.parse(fs.readFileSync(0, 'utf8')), root = path.resolve(__dirname, '../..');
const output = path.resolve(input.output), entry = input.entry || '/workbench';
assert(output !== root && !output.startsWith(root + path.sep), 'Artifacts stay outside checkout');
fs.mkdirSync(output, { recursive: true });
const source = fs.readFileSync(path.join(root, 'frontend/workbench/app/PlanWorkspace.jsx'), 'utf8');
const dependencies = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx'].map(name => ({ path: name,
  code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [...dependencies, { path: 'PlanWorkspace.jsx', code: source }], check_combined: true });
const dependencyCode = built.outputs.slice(0, -1).map((item, index) =>
  'if (!window.' + dependencies[index].path.replace('.jsx', '') + ') {\n' + item.code + '\n}').join('\n');
const workspaceCode = dependencyCode + '\n' + built.outputs[built.outputs.length - 1].code;
const report = { scope: input.cases ? 'temporary-real-adoptions' : 'existing-host-readonly', global_build: false,
  source_sha256: crypto.createHash('sha256').update(source).digest('hex'), errors: [], writes: [], external: [], requests: [], cases: [], screenshots: [], source_overrides: 0 };
async function settle(page) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
}
async function navigate(page, planRef, view = 'analysis') {
  await page.evaluate(({ planRef, view, entry }) => {
    const context = planRef ? { plan_ref: planRef } : {};
    history.pushState({ workbench: { view, context, key: Date.now() } }, '', entry + '?view=' + view);
    dispatchEvent(new PopStateEvent('popstate'));
  }, { planRef, view, entry });
}
async function check(page, fixture, variant) {
  await navigate(page, fixture.plan_ref);
  const workspace = page.locator('[data-plan-workspace]'), heading = workspace.locator(':scope > .plan-heading').first();
  await workspace.waitFor();
  if (fixture.plan_ref) await workspace.locator('[data-plan-gantt]').waitFor();
  else await workspace.getByText('从目录中选择一个可查看的计划。', { exact: true }).waitFor();
  await settle(page);
  assert.equal(await workspace.getByRole('button', { name: /^(采用|正式采用|重新采用)/ }).count(), 0);
  assert.equal(await workspace.locator('[title*="暂不支持采用方案"]').count(), 0);
  assert(!(await workspace.innerText()).includes('暂不支持采用方案'));
  const ready = !!fixture.plan_ref;
  const trial = heading.getByRole('button', { name: '试调', exact: true });
  const download = heading.getByRole('button', { name: /^导出/ });
  assert.equal(await trial.isEnabled(), ready);
  assert.equal(await download.isEnabled(), ready);
  assert.equal(await heading.getByRole('button', { name: '查看甘特', exact: true }).isEnabled(), !!fixture.plan_ref);
  if (ready) {
    assert.equal(await heading.locator('.plan-state').innerText(), fixture.identity);
    await download.click(); await page.getByRole('dialog').waitFor();
    await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
    await heading.getByRole('button', { name: '查看甘特', exact: true }).click();
    await heading.getByRole('button', { name: '选择方案', exact: true }).waitFor();
    await heading.getByRole('button', { name: '选择方案', exact: true }).click();
    await heading.getByRole('button', { name: '查看甘特', exact: true }).waitFor();
    await workspace.locator('[data-plan-gantt]').waitFor();
    const payload = await page.evaluate(async ref => (await fetch('/api/workbench/v1/plans/' + ref + '/workspace')).json(), fixture.plan_ref);
    if (fixture.payload) assert.deepEqual(payload.data, fixture.payload.data, 'UI must not change plan data');
    const data = payload.data, label = value => value.replace('T', ' ');
    const inclusive = data.plan_span.end_inclusive === true;
    const caption = inclusive && data.plan_span.start === data.plan_span.end ? '计划时间点：' + label(data.plan_span.start)
      : '计划时间范围：' + label(data.time_scope.range_start) + ' → ' + label(data.time_scope.range_end) + (inclusive ? '（包含末端计划点）' : '（不含结束时刻）');
    assert.equal(await workspace.locator(':scope > .plan-note').innerText(), caption, 'Keep FA scope caption');
    const metrics = await workspace.locator(':scope > .wb-metrics > .wb-metric').evaluateAll(nodes => nodes.slice(2).map(node => ({
      value: Number(node.querySelector('.wb-metric-value').textContent), tone: node.dataset.tone })));
    assert(metrics.every(row => row.tone === (row.value === 0 ? 'neutral' : 'warn')), 'Keep FA risk-zero tones');
  } else assert.equal(await heading.locator('.plan-state').count(), 0);
  await settle(page);
  const geometry = await heading.evaluate(node => {
    const title = node.firstElementChild.getBoundingClientRect(), actions = node.lastElementChild.getBoundingClientRect();
    const buttons = Array.from(node.lastElementChild.children).map(item => {
      const r = item.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    });
    return { viewport: innerWidth, width: document.documentElement.scrollWidth,
      separated: title.right <= actions.left + 1 || title.bottom <= actions.top + 1,
      buttons, fits: buttons.every(r => r.left >= 0 && r.right <= innerWidth + 1) };
  });
  assert(geometry.width <= geometry.viewport + 1 && geometry.separated && geometry.fits, JSON.stringify(geometry));
  const filename = path.join(output, variant + '-' + fixture.name + '.png');
  await page.screenshot({ path: filename }); report.screenshots.push(filename);
  report.cases.push({ variant, name: fixture.name, ready, geometry });
}
async function main() {
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
  report.browser = browser.version(); assert.match(report.browser, /^109\./);
  try {
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport: { width, height: width === 1920 ? 1080 : 924 } });
      try {
        const page = await context.newPage(); page.setDefaultTimeout(10000);
        page.on('pageerror', error => report.errors.push(error.message));
        page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
        await page.route('**/*', route => {
          const request = route.request(), url = new URL(request.url());
          report.requests.push({ url: request.url(), method: request.method() });
          if (!['GET', 'HEAD'].includes(request.method())) { report.writes.push(request.url()); return route.abort(); }
          if (url.origin !== input.base) { report.external.push(request.url()); return route.abort(); }
          // Test current source without changing the host's frozen build or preview.
          if (url.pathname === '/static/workbench/app/PlanWorkspace.js') {
            report.source_overrides++;
            return route.fulfill({ status: 200, contentType: 'application/javascript', body: workspaceCode });
          }
          return route.continue();
        });
        await page.goto(input.base + entry + '?view=analysis');
        await page.locator('[data-plan-workspace]').waitFor();
        await page.evaluate(theme => APSWorkbenchTheme.set(theme), theme);
        await page.waitForFunction(theme => document.documentElement.dataset.theme === theme, theme);
        let cases = input.cases;
        if (!cases) {
          const catalog = await page.evaluate(async () => (await fetch('/api/workbench/v1/plans')).json());
          assert(catalog.ok); const current = catalog.data.plans.find(plan => plan.is_current_official);
          assert(current, 'Existing host must have a current official plan');
          report.current = current;
          cases = [{ name: 'initial-no-plan' }, { name: 'current', plan_ref: current.plan_ref, identity: '当前正式' }];
        }
        for (const fixture of cases) await check(page, fixture, width + '-' + theme);
      } finally { await context.close(); }
    }
    assert.deepEqual(report.writes, []); assert.deepEqual(report.external, []); assert.deepEqual(report.errors, []);
    if (!input.cases) assert.equal(report.source_overrides, 4);
  } finally { await browser.close(); }
}
main().catch(error => { report.failure = error.stack; process.exitCode = 1; console.error(error.stack); }).finally(() => {
  fs.writeFileSync(path.join(output, 'fg-plan-actions-result.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length, writes: report.writes }));
});
