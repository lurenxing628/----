'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const evidence = { errors: [], external: [], screenshots: [], http: [], main_source_used: true, successful_api_stubs: false };
async function shot(page, name) {
  const file = path.join(input.output, name + '.png'); await page.screenshot({ path: file, fullPage: true }); evidence.screenshots.push(file);
}
async function fit(page) {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
  assert.equal(await page.locator('[style]').evaluateAll(nodes => nodes.some(node => /NaN|Infinity/.test(node.getAttribute('style')))), false);
}
async function main() {
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  evidence.browser = browser.version();
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, timezoneId: 'America/New_York' });
    page.on('pageerror', error => evidence.errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') evidence.errors.push(message.text()); });
    page.on('request', request => { if (!request.url().startsWith(input.base) && !request.url().startsWith('blob:')) evidence.external.push(request.url()); });
    page.on('response', response => { if (response.url().includes('/api/')) evidence.http.push({ url: response.url(), status: response.status() }); });
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      await page.setViewportSize({ width, height: width === 1920 ? 1080 : 900 });
      await page.goto(input.base + '/?view=fieldgantt');
      await page.locator('[data-actual-scroll]').waitFor();
      if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /^深色：/ }).click();
      const point = page.locator('[data-actual-mark="plan-point"]');
      await point.waitFor();
      assert.equal(await point.count(), 1);
      assert.equal(await point.getAttribute('data-point-ref'), input.identity.task.task_ref);
      assert.equal(await point.getAttribute('data-point-at'), input.identity.task.start);
      const box = await point.boundingBox(); assert.equal(box.width, 24); assert.equal(box.height, 24);
      await point.hover();
      assert.ok((await page.getByRole('tooltip').innerText()).includes('原计划点基线'));
      await point.click();
      await page.getByRole('checkbox', { name: '详情', exact: true }).check();
      assert.ok((await page.getByLabel('工序详情').innerText()).includes('计划点 · 0 秒'));
      await point.focus(); await page.keyboard.press('Enter');
      assert.equal(await point.getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('[data-actual-mark=actual]').count(), input.reports ? 1 : 0);
      assert.equal(await page.locator('[data-actual-mark=point]').count(), input.reports ? 2 : 0);
      assert.equal(await page.getByText('待续排', { exact: true }).count(), 0);
      assert.ok((await page.locator('[data-actual-gantt]').innerText()).includes('计划点已安排 · 完成待确认'));
      if (input.reports) {
        const actual = page.locator('[data-actual-mark=actual]'); assert.ok((await actual.boundingBox()).width > 0);
        const reportPoint = page.locator('[data-actual-mark=point]').first();
        await reportPoint.hover();
        assert.ok((await page.getByRole('tooltip').innerText()).includes('报工时点'));
        const reportRef = await reportPoint.getAttribute('data-report-ref');
        assert.equal(await reportPoint.getAttribute('data-point-ref'), reportRef);
        await reportPoint.focus(); await page.keyboard.press('Enter');
        assert.equal(await page.getByLabel('选择报工详情').inputValue(), reportRef);
        await point.focus(); await page.keyboard.press('Enter');
        assert.equal(await page.getByLabel('选择报工详情').inputValue(), '');
      } else assert.ok((await page.getByLabel('工序详情').innerText()).includes('待报工'));
      await page.getByLabel('搜索现场甘特').fill('B1');
      assert.ok((await page.locator('[data-actual-count]').innerText()).includes('1 / 1'));
      await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
      await page.getByRole('button', { name: '定位选中工序', exact: true }).click();
      await page.getByRole('button', { name: '适应全部', exact: true }).click();
      await fit(page); await shot(page, width + '-' + theme + '-actual');
      await page.getByRole('button', { name: '现场报工', exact: true }).click();
      await page.locator('[data-field-workspace]').waitFor();
      await page.getByRole('button', { name: '作业时间线', exact: true }).click();
      const fieldPoint = page.locator('[data-field-point=plan]'); await fieldPoint.waitFor();
      assert.equal(await fieldPoint.getAttribute('data-point-ref'), input.identity.task.task_ref);
      assert.equal((await fieldPoint.boundingBox()).width, 24);
      await fieldPoint.hover(); assert.ok((await page.getByRole('tooltip').innerText()).includes('不占用排产资源'));
      await fieldPoint.focus(); await page.keyboard.press('Space');
      assert.equal(await fieldPoint.getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('[data-field-point=report]').count(), input.reports ? 2 : 0);
      if (input.reports) assert.ok((await page.locator('.field-timeline-axis').innerText()).includes('2026-09-09 09:50:00'));
      await fit(page); await shot(page, width + '-' + theme + '-field');
      await page.getByRole('button', { name: '实际甘特', exact: true }).click(); await page.locator('[data-actual-scroll]').waitFor();
    }
    await page.getByRole('button', { name: '导出 CSV', exact: true }).click();
    const pending = page.waitForEvent('download'); await page.getByRole('button', { name: '下载 CSV', exact: true }).click();
    const download = await pending, file = path.join(input.output, 'actual.csv'); await download.saveAs(file);
    const csv = fs.readFileSync(file, 'utf8'); assert.ok(csv.includes('计划事件类型') && csv.includes('point') && csv.includes(input.identity.task.task_ref));
    assert.ok(csv.includes(input.identity.task.operation_ref));
    if (input.reports) assert.ok(csv.includes('1.25'));
    evidence.export = file;
    evidence.contracts = await page.evaluate(async identity => {
      const query = { plan_ref: identity.plan.plan_ref };
      const dto = await (await fetch('/api/workbench/v1/actual-gantt?plan_ref=' + query.plan_ref)).json();
      ActualGanttContract.workspace(dto, query);
      const failures = [];
      for (const patch of [{ event_kind: undefined }, { duration_seconds: null }, { duration_seconds: false }, { occupies_resources: true }, { end: '2026-09-09T08:00:01' }, { start: '2026-02-31T08:00:00', end: '2026-02-31T08:00:00' }]) {
        const bad = JSON.parse(JSON.stringify(dto)); Object.assign(bad.data.items[0].task, patch);
        try { ActualGanttContract.workspace(bad, query); failures.push(patch); } catch (_) { /* Expected rejection. */ }
      }
      const field = await (await fetch('/api/workbench/v1/execution/tasks?plan_ref=' + query.plan_ref)).json();
      FieldContract.query(field, 'list');
      const malformed = JSON.parse(JSON.stringify(field)); delete malformed.data.tasks[0].event_kind;
      let fieldRejected = false; try { FieldContract.query(malformed, 'list'); } catch (_) { fieldRejected = true; }
      window.ekRealDTO = dto;
      return { incorrectlyAccepted: failures, fieldRejected, plan_span: dto.data.plan_span, task: dto.data.items[0].task };
    }, input.identity);
    assert.deepEqual(evidence.contracts.incorrectlyAccepted, []); assert.equal(evidence.contracts.fieldRejected, true);
    // Dense-row rendering consumes the same real response, without inventing 1000 tasks.
    await page.evaluate(() => {
      const data = window.ekRealDTO.data, view = { query: '', late: 'all', mode: 'machine', collapsed: {}, onlySelected: false, selected: null };
      const model = ActualGanttModel.layout(data, view, window.ekRealDTO.meta.as_of);
      const host = document.createElement('div'); host.id = 'ek-dense-real'; host.className = 'fg-live';
      Object.assign(host.style, { position: 'fixed', left: '20px', top: '20px', width: '1000px', height: '400px', zIndex: '400', background: 'var(--ui-card-bg)' }); document.body.appendChild(host);
      const row = model.rows.find(row => row.baseline);
      const onSelect = (item, report) => { window.ekDenseSelected = report ? report.report_ref : item.task.task_ref; }, onHover = () => {};
      const renderMark = (mark, canvasPainted) => React.createElement(ActualGanttBar, { key: mark.key, mark, row, model, width: 1000, onSelect, onHover, canvasPainted });
      ReactDOM.createRoot(host).render(React.createElement(React.Fragment, null, React.createElement(ActualGanttControls.Styles),
        React.createElement(ActualGanttCanvas.DenseRow, { row, model, width: 1000, viewport: 1000, left: 0, onSelect, onHover, renderMark })));
    });
    const densePoint = page.locator('#ek-dense-real [data-actual-mark="plan-point"]'); await densePoint.waitFor();
    await densePoint.focus(); await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => window.ekDenseSelected), input.identity.task.task_ref);
    evidence.dense_canvas_pixels = await page.locator('#ek-dense-real canvas').evaluate(canvas => {
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let count = 0; for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) count++; return count;
    });
    assert.ok(evidence.dense_canvas_pixels > 0);
    assert.deepEqual(evidence.errors, []); assert.deepEqual(evidence.external, []);
    assert.ok(evidence.http.length > 10 && evidence.http.every(row => row.status === 200));
  } finally { await browser.close(); }
}
main().catch(error => { evidence.runner_error = error.stack; process.exitCode = 1; console.error(error.stack); }).finally(() => {
  fs.writeFileSync(path.join(input.output, 'browser-result.json'), JSON.stringify(evidence, null, 2)); console.log(JSON.stringify(evidence));
});
