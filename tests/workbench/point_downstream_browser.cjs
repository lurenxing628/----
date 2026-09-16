'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const evidence = { errors: [], external: [], screenshots: [], http: [], navigation_scopes: [], main_source_used: true, successful_api_stubs: false };
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
      if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /^切换(?:深色|浅色)$/ }).click();
      const point = page.locator('[data-actual-mark="plan-point"]');
      try { await point.waitFor(); } catch (error) {
        evidence.failed_mount = await page.evaluate(() => {
          const board = document.querySelector('[data-actual-scroll]');
          return { context: history.state && history.state.workbench && history.state.workbench.context,
            board: board && { width: board.clientWidth, scrollWidth: board.scrollWidth, left: board.scrollLeft, top: board.scrollTop },
            rows: Array.from(document.querySelectorAll('.fg-virtual-row')).map(node => ({ kind: node.getAttribute('data-kind'), top: node.style.top, text: node.innerText.slice(0, 160) })),
            text: document.querySelector('[data-actual-gantt]')?.innerText.slice(0, 1500) };
        });
        await shot(page, width + '-' + theme + '-failed-mount'); throw error;
      }
      assert.equal(await point.count(), 1);
      assert.equal(await point.getAttribute('data-point-ref'), input.identity.task.task_ref);
      assert.equal(await point.getAttribute('data-point-at'), input.identity.task.start);
      const box = await point.boundingBox(); assert.equal(box.width, 24); assert.equal(box.height, 24);
      if (width === 1920 && theme === 'light') {
        await page.waitForFunction(() => Number.isFinite(history.state?.workbench?.context?.actual_view?.position?.centerAt));
        const before = await page.evaluate(() => history.state.workbench.context.actual_view.position);
        await page.setViewportSize({ width: 1392, height: 900 });
        await page.waitForFunction(old => history.state.workbench.context.actual_view.position.viewport !== old, before.viewport);
        await page.reload(); await point.waitFor();
        let releaseRead, reachedRead;
        const heldRead = new Promise(resolve => { reachedRead = resolve; });
        await page.route('**/api/workbench/v1/actual-gantt?*', async route => {
          await new Promise(resolve => { releaseRead = resolve; reachedRead(); });
          await route.continue();
        }, { times: 1 });
        const response = page.waitForResponse(value => new URL(value.url()).pathname === '/api/workbench/v1/actual-gantt');
        await page.getByRole('button', { name: '刷新实际甘特', exact: true }).click();
        await heldRead;
        await page.setViewportSize({ width, height: 1080 });
        releaseRead();
        const refreshRead = await response;
        assert.equal(refreshRead.status(), 200); await point.waitFor();
        await page.waitForFunction(() => document.querySelector('[data-actual-scroll]') && Number.isFinite(history.state?.workbench?.context?.actual_view?.position?.centerAt));
        const after = await page.evaluate(() => history.state.workbench.context.actual_view.position);
        assert(Math.abs(after.centerAt - before.centerAt) < before.windowSpan * .003, 'Resize, reload and fresh API read preserve the visible time center');
        assert(Math.abs(after.windowSpan - before.windowSpan) < before.windowSpan * .003, 'Fresh API read preserves visible duration');
        evidence.window_restore = { before, after, fresh_read_status: refreshRead.status() };
        await page.setViewportSize({ width, height: 1080 });
        await point.waitFor();
      }
      // The default plan window can exclude later reports; inspect the entire axis for all-report assertions.
      await page.getByRole('button', { name: '适应全部', exact: true }).click();
      await point.hover();
      assert.ok((await page.getByRole('tooltip').innerText()).includes('原计划 · 零工时工序'));
      await point.click();
      await page.getByRole('checkbox', { name: '详情', exact: true }).check();
      assert.ok((await page.getByLabel('工序详情').innerText()).includes('零工时工序，无资源占用。'));
      await point.focus(); await page.keyboard.press('Enter');
      assert.equal(await point.getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('[data-actual-mark=actual]').count(), input.reports ? 1 : 0);
      assert.equal(await page.locator('[data-actual-mark=point]').count(), input.reports ? 2 : 0);
      assert.equal(await page.getByText('待续排', { exact: true }).count(), 0);
      assert.ok((await page.locator('[data-actual-gantt]').innerText()).includes('零工时工序已安排 · 完成待确认'));
      if (input.reports) {
        const actual = page.locator('[data-actual-mark=actual]'); assert.ok((await actual.boundingBox()).width > 0);
        const reportPoint = page.locator('[data-actual-mark=point]').first();
        await reportPoint.hover();
        assert.ok((await page.getByRole('tooltip').innerText()).includes('报工时刻'));
        const reportRef = await reportPoint.getAttribute('data-report-ref');
        assert.equal(await reportPoint.getAttribute('data-point-ref'), reportRef);
        await reportPoint.focus(); await page.keyboard.press('Enter');
        assert.equal(await page.getByLabel('选择报工详情').inputValue(), reportRef);
        await point.focus(); await page.keyboard.press('Enter');
        assert.equal(await page.getByLabel('选择报工详情').inputValue(), '');
      } else assert.ok((await page.getByLabel('工序详情').innerText()).includes('待报工'));
      await page.getByLabel('搜索现场甘特').fill('B1');
      assert.ok((await page.locator('[data-actual-count]').innerText()).includes('1 / 1'));
      await page.getByRole('button', { name: '适应全部', exact: true }).click();
      await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
      await page.getByRole('button', { name: '定位选中工序', exact: true }).click();
      await page.getByRole('button', { name: '适应全部', exact: true }).click();
      await fit(page); await shot(page, width + '-' + theme + '-actual');
      const originContext = await page.evaluate(() => history.state.workbench.context);
      const [fieldRead] = await Promise.all([
        page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/execution/tasks'),
        page.getByRole('button', { name: '现场记录', exact: true }).click(),
      ]);
      const fieldPayload = await fieldRead.json();
      evidence.navigation_scopes.push({ width, theme, origin: originContext, url: fieldRead.url(), status: fieldRead.status(), payload: fieldPayload });
      assert.equal(fieldRead.status(), 200, JSON.stringify(fieldPayload));
      assert.equal(fieldPayload.data.scope.plan_ref, input.identity.plan.plan_ref);
      assert.equal(fieldPayload.data.scope.query, 'B1');
      assert.equal(new URL(fieldRead.url()).searchParams.has('batch_ids'), false, 'Unrestricted Actual batches must not serialize as an explicit empty Field batch restriction');
      await page.locator('[data-field-workspace]').waitFor();
      await page.getByRole('button', { name: '作业时间线', exact: true }).click();
      const fieldPoint = page.locator('[data-field-point=plan]'); await fieldPoint.waitFor();
      const returnContext = await page.evaluate(() => history.state.workbench.context.return_to);
      assert.equal(returnContext.view, 'fieldgantt'); assert.equal(returnContext.context.plan_ref, input.identity.plan.plan_ref);
      assert.equal(returnContext.context.task_ref, input.identity.task.task_ref); assert.equal(returnContext.context.scope.query, 'B1');
      if (returnContext.context.scope.batch_ids !== undefined) assert.deepEqual(returnContext.context.scope.batch_ids, []);
      assert.equal(await fieldPoint.getAttribute('data-point-ref'), input.identity.task.task_ref);
      assert.equal((await fieldPoint.boundingBox()).width, 24);
      await fieldPoint.hover(); assert.ok((await page.getByRole('tooltip').innerText()).includes('零工时工序，无资源占用。'));
      await fieldPoint.focus(); await page.keyboard.press('Space');
      assert.equal(await fieldPoint.getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('[data-field-point=report]').count(), input.reports ? 2 : 0);
      // Report times are second-precision facts; the axis shows the exact latest report instant.
      if (input.reports) assert.equal(await page.locator('.field-timeline-axis > span').last().innerText(), '2026-09-09 09:50:00');
      await fit(page); await shot(page, width + '-' + theme + '-field');
      await page.getByRole('button', { name: '实际甘特', exact: true }).click(); await page.locator('[data-actual-scroll]').waitFor();
    }
    await page.getByLabel('批次范围', { exact: true }).fill('B1');
    const [scopedRead] = await Promise.all([
      page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/actual-gantt'),
      page.getByRole('button', { name: '应用范围', exact: true }).click(),
    ]);
    assert.equal(scopedRead.status(), 200); const originalScoped = await scopedRead.json();
    assert.deepEqual(originalScoped.data.scope.batch_ids, ['B1']);
    await page.locator('[data-actual-scroll]').waitFor();
    const [scopedField] = await Promise.all([
      page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/execution/tasks'),
      page.getByRole('button', { name: '现场记录', exact: true }).click(),
    ]);
    const scopedPayload = await scopedField.json();
    evidence.nonempty_batch_navigation = { url: scopedField.url(), status: scopedField.status(), payload: scopedPayload };
    assert.equal(scopedField.status(), 200, JSON.stringify(scopedPayload));
    assert.deepEqual(scopedPayload.data.scope.batch_ids, ['B1']);
    assert.deepEqual(JSON.parse(new URL(scopedField.url()).searchParams.get('batch_ids')), ['B1']);
    assert.equal(scopedPayload.data.scope.plan_ref, input.identity.plan.plan_ref);
    assert(scopedPayload.data.tasks.some(task => task.task_ref === input.identity.task.task_ref));
    await page.getByRole('button', { name: '作业时间线', exact: true }).waitFor();
    const nonemptyReturn = await page.evaluate(() => history.state.workbench.context.return_to);
    assert.deepEqual(nonemptyReturn.context.scope.batch_ids, ['B1']);
    const [returned] = await Promise.all([
      page.waitForResponse(response => new URL(response.url()).pathname === '/api/workbench/v1/actual-gantt'),
      page.locator('.field-toolbar').getByRole('button', { name: '返回', exact: true }).click(),
    ]);
    assert.equal(returned.status(), 200); const restoredScope = (await returned.json()).data.scope;
    assert.deepEqual(restoredScope, originalScoped.data.scope);
    await page.locator('[data-actual-scroll]').waitFor();
    assert.equal(await page.getByLabel('搜索现场甘特').inputValue(), 'B1');
    assert.equal(await page.locator('[data-actual-mark="plan-point"]').getAttribute('aria-pressed'), 'true');
    evidence.nonempty_batch_navigation.returned_scope = restoredScope;
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
