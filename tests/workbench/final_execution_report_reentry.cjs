'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { run } = require('./final_execution_browser_support.cjs');

async function exercise(p, view) {
  const { page } = p, events = [], pending = new Set(), requests = new Map(), readErrors = [];
  const owns = value => {
    const pathname = new URL(value.url()).pathname;
    return pathname.includes('/analytics') && !pathname.endsWith('/export');
  };
  function track(reading) { pending.add(reading); reading.then(() => pending.delete(reading)); }
  page.on('request', request => {
    if (owns(request)) track(new Promise(resolve => requests.set(request, resolve)));
  });
  const finishRequest = request => {
    const finish = requests.get(request);
    if (finish) { requests.delete(request); finish(); }
  };
  page.on('requestfinished', finishRequest);
  page.on('requestfailed', request => {
    if (owns(request)) readErrors.push({ url: request.url(), failure: request.failure() });
    finishRequest(request);
  });
  page.on('response', response => {
    if (!owns(response)) return;
    // Reserve the response's position before asynchronously retrieving its body.
    const event = { url: response.url(), status: response.status() };
    events.push(event);
    track(response.json().then(payload => { event.payload = payload; }, error => {
      readErrors.push({ url: response.url(), error: error.message });
    }));
  });
  p.report.read_events = events; p.report.read_errors = readErrors;
  async function drain() {
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Analytics requests and response bodies did not finish')), 15000);
    });
    try { while (pending.size) await Promise.race([Promise.all([...pending]), timeout]); }
    finally { clearTimeout(timer); }
    assert.deepEqual(readErrors, [], 'Every analytics response body must be retained before sampling or navigation');
  }
  async function checkpoint() { await drain(); return events.length; }
  async function readsSince(start) { await drain(); return events.slice(start); }
  async function restart(number, context) {
    await drain();
    fs.writeFileSync(path.join(p.ready.root, 'report-reentry-restart-request-' + number + '.json'), JSON.stringify({ context, origin: p.ready.url }));
    const resumed = path.join(p.ready.root, 'report-reentry-restart-complete-' + number + '.json'), deadline = Date.now() + 100000;
    while (!fs.existsSync(resumed)) { assert(Date.now() < deadline, 'Owned server restart timed out'); await new Promise(resolve => setTimeout(resolve, 50)); }
    assert.equal(JSON.parse(fs.readFileSync(resumed, 'utf8')).url, p.ready.url);
  }
  async function openView() {
    const first = await checkpoint();
    await p.read(() => page.locator('.sidebar a[href$="?view=reports"]').click(), '/analytics');
    if (view === 'reports') return first;
    await page.locator('.rw-workbench[data-ready="true"]').waitFor();
    const reviewTab = page.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '执行复盘', exact: true });
    if (await reviewTab.getAttribute('aria-selected') === 'true') return first;
    const targetStart = await checkpoint();
    await p.read(() => reviewTab.click(), '/analytics');
    p.report.view_entries = (p.report.view_entries || []).concat({ view, transit: events.slice(first, targetStart) });
    return targetStart;
  }
  await openView();
  if (view === 'reports') await p.read(() => page.getByRole('tab', { name: '报工记录', exact: true }).click(), '/analytics');
  const search = page.getByRole('searchbox', { name: '搜索批次或工序', exact: true });
  await search.fill('OP');
  for (const label of ['计划完工起日', '计划完工止日']) await page.getByLabel(label, { exact: true }).fill('2026-09-09');
  let result = await p.read(() => page.getByRole('button', { name: '查询范围', exact: true }).click(), '/analytics');
  await p.read(() => p.choose('每页条数', '10'), '/analytics');
  result = await p.read(() => page.getByRole('button', { name: '下一页', exact: true }).click(), '/analytics');
  assert.equal(result.data.page.number, 2); assert(result.data.page.total > 10);
  const operationRef = result.data.rows[0].operation_ref;
  const detail = await p.read(() => page.locator('.rw-primary-table').getByRole('button', { name: /^查看工序 / }).first().click(), '/analytics/operations/' + operationRef);
  assert.equal(detail.data.detail.operation.operation_ref, operationRef);
  await page.waitForFunction(ref => history.state.workbench.context.selected === ref, operationRef);
  const baseline = { scope: result.data.scope, topic: result.data.topic, page: result.data.page,
    rows: result.data.rows, selected: operationRef, detail: detail.data.detail, snapshot: result.meta.snapshot_ref, as_of: result.meta.as_of };
  p.report.baseline = baseline;

  function facts(row, asOf) {
    if (!Object.prototype.hasOwnProperty.call(row, 'elapsed_since_planned_minutes')) return row;
    const elapsed = row.due && !row.complete ? Math.round((Date.parse(asOf + 'Z') - Date.parse(row.planned_end + 'Z')) / 600) / 100 : null;
    assert.equal(row.elapsed_since_planned_minutes, elapsed, 'Elapsed time is recomputed from this response as_of');
    const { elapsed_since_planned_minutes, ...stable } = row;
    return stable;
  }

  async function assertRestored(label, startIndex) {
    await page.locator('.rw-primary-table').waitFor();
    await page.getByRole('region', { name: '报表结果表格' }).locator('tbody tr').first().waitFor();
    await page.waitForFunction(ref => document.querySelector('.rw-detail .rw-detail-facts') && history.state.workbench.context.selected === ref, operationRef);
    const reads = await readsSince(startIndex), lists = reads.filter(event => new URL(event.url).pathname.endsWith('/analytics'));
    assert.equal(lists[0].status, 200); assert.equal(lists[0].payload.data.page.number, 1, label + ' starts a new page-one read');
    assert.equal(new URL(lists[0].url).searchParams.has('snapshot_ref'), false, label + ' does not replay an old token');
    const final = lists[lists.length - 1];
    assert.equal(final.payload.data.page.number, 2, label + ' must restore the requested page, not page one');
    assert.equal(new URL(final.url).searchParams.get('snapshot_ref'), lists[0].payload.meta.snapshot_ref);
    assert.deepEqual(final.payload.data.scope, baseline.scope); assert.equal(final.payload.data.topic, baseline.topic);
    assert.deepEqual(final.payload.data.rows.map(row => facts(row, final.payload.meta.as_of)), baseline.rows.map(row => facts(row, baseline.as_of)));
    assert.deepEqual(final.payload.data.page, baseline.page);
    const original = reads.find(event => new URL(event.url).pathname.endsWith('/operations/' + operationRef));
    assert(original && original.status === 200);
    assert.equal(new URL(original.url).searchParams.get('snapshot_ref'), final.payload.meta.snapshot_ref);
    assert.deepEqual(facts(original.payload.data.detail.operation, original.payload.meta.as_of), facts(baseline.detail.operation, baseline.as_of));
    assert.deepEqual(original.payload.data.detail.records, baseline.detail.records);
    const context = await page.evaluate(() => history.state.workbench.context);
    assert.equal(Object.prototype.hasOwnProperty.call(context, 'snapshot_ref'), false);
    assert.equal(Object.prototype.hasOwnProperty.call(context.table, 'snapshot_ref'), false);
    assert.equal(context.table.page, 2); assert.equal(context.selected, operationRef);
    const text = await page.locator('.rw-asof').innerText();
    const displayedAsOf = await page.evaluate(value => window.WorkbenchFormat.dateTime(value), final.payload.meta.as_of);
    assert.equal(text, '数据截至 ' + displayedAsOf);
    p.report.reentries = (p.report.reentries || []).concat({ label, reads, read_view: context });
    await p.shot(label);
    return final.payload;
  }

  await p.step(['WBP-SCOPE-005', 'WBP-REPORT-010'], view + '-same-pid-sidebar-return-restores-page-two-original-detail', async () => {
    await drain();
    await p.read(() => page.locator('.sidebar a[href$="?view=field"]').click(), '/execution/tasks');
    const start = await openView(); result = await assertRestored('same-pid-return', start);
  });
  await p.step(['WBP-SCOPE-005'], view + '-legacy-history-F5-ignores-both-old-token-locations', async () => {
    const current = await page.evaluate(() => history.state.workbench.context);
    const legacy = { ...current, snapshot_ref: result.meta.snapshot_ref, table: { ...current.table, snapshot_ref: result.meta.snapshot_ref } };
    p.report.legacy_history = legacy;
    await page.evaluate(value => history.replaceState({ ...history.state, workbench: { ...history.state.workbench, context: value } }, '', location.href), legacy);
    const start = await checkpoint(); await page.reload(); result = await assertRestored('same-pid-legacy-F5', start);
  });
  await p.step(['WBP-SCOPE-005', 'WBP-REPORT-008', 'WBP-REPORT-010'], view + '-same-port-new-pid-read-detail-and-real-export', async () => {
    const legacy = { ...(await page.evaluate(() => history.state.workbench.context)), snapshot_ref: result.meta.snapshot_ref };
    legacy.table = { ...legacy.table, snapshot_ref: result.meta.snapshot_ref };
    await page.evaluate(value => history.replaceState({ ...history.state, workbench: { ...history.state.workbench, context: value } }, '', location.href), legacy);
    await restart(1, legacy);
    const start = await checkpoint(); await page.reload(); result = await assertRestored('new-pid-original-read-view', start);
    assert.notEqual(result.meta.snapshot_ref, legacy.snapshot_ref);
    const waiting = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/analytics/export'));
    const downloaded = await p.download(() => page.getByRole('button', { name: '导出范围', exact: true }).click(), view + '-page2-fullscope');
    const response = await waiting;
    assert.equal(response.status(), 200); assert.equal(new URL(response.url()).searchParams.get('snapshot_ref'), result.meta.snapshot_ref);
    assert.equal(response.headers()['x-workbench-as-of'], result.meta.as_of);
    assert.deepEqual(fs.readFileSync(downloaded), await response.body());
    p.report.export = { url: response.url(), headers: response.headers(), path: downloaded };
  });
  await p.step(['WBP-SCOPE-005.A005', 'WBP-REPORT-008.A004'], view + '-live-expired-export-detail-page-errors-never-auto-rebind', async () => {
    await restart(2, await page.evaluate(() => history.state.workbench.context));
    const first = await checkpoint();
    const downloadError = await p.read(() => page.getByRole('button', { name: '导出范围', exact: true }).click(), '/analytics/export', 409);
    assert.equal(downloadError.error.code, 'snapshot_stale');
    await drain();
    assert.equal(events.length, first, 'Export failure must not refresh the list automatically');
    await page.locator('.rw-detail').getByRole('button', { name: /^关闭/ }).click();
    const detailError = await p.read(() => page.locator('.rw-primary-table').getByRole('button', { name: /^查看工序 / }).first().click(), '/analytics/operations/' + operationRef, 409);
    assert.equal(detailError.error.code, 'snapshot_stale');
    await page.locator('.rw-detail').getByRole('alert').waitFor();
    await page.locator('.rw-detail').getByRole('button', { name: /^关闭/ }).click();
    const pageError = await p.read(() => page.locator('#report-topic-panel .rw-list-pane > .wb-pager').getByRole('button', { name: '下一页', exact: true }).click(), '/analytics', 409);
    assert.equal(pageError.error.code, 'snapshot_stale'); await page.getByRole('button', { name: '刷新报表数据', exact: true }).waitFor();
    const failed = await readsSince(first);
    assert.equal(failed.length, 2); assert(failed.every(event => event.status === 409));
    assert(failed.every(event => new URL(event.url).searchParams.get('snapshot_ref') === result.meta.snapshot_ref));
    await p.shot('live-stale-explicit-error');
    p.report.live_stale = { export: downloadError, reads: failed };
    const recovery = await checkpoint();
    await page.getByRole('button', { name: '刷新报表数据', exact: true }).click();
    await page.waitForFunction(() => { const node = document.querySelector('#report-topic-panel .rw-list-pane > .wb-pager'); return node && node.textContent.includes('第 3 /'); });
    const recovered = (await readsSince(recovery)).filter(event => new URL(event.url).pathname.endsWith('/analytics'));
    assert.equal(recovered.length, 2); assert.equal(recovered[0].payload.data.page.number, 1); assert.equal(recovered[1].payload.data.page.number, 3);
    assert.equal(new URL(recovered[0].url).searchParams.has('snapshot_ref'), false);
    assert.equal(new URL(recovered[1].url).searchParams.get('snapshot_ref'), recovered[0].payload.meta.snapshot_ref);
    assert.deepEqual(recovered[1].payload.data.scope, baseline.scope);
    p.report.explicit_recovery = recovered;
  });
  await p.step(['WBP-REPORT-010', 'WBP-REPORT-012'], view + '-unknown-original-detail-ref-stays-explicit-not-replaced', async () => {
    const absent = '0'.repeat(48), start = await checkpoint();
    await page.evaluate(ref => history.replaceState({ ...history.state, workbench: { ...history.state.workbench,
      context: { ...history.state.workbench.context, selected: ref } } }, '', location.href), absent);
    await page.reload(); await page.locator('.rw-detail').getByRole('alert').waitFor();
    const queried = (await readsSince(start)).filter(event => new URL(event.url).pathname.includes('/analytics/operations/'));
    assert.equal(queried.length, 1); assert(queried[0].url.includes('/operations/' + absent)); assert.equal(queried[0].status, 404);
    assert.equal(await page.evaluate(() => history.state.workbench.context.selected), absent);
    assert.equal(await page.locator('.rw-detail-facts').count(), 0);
    p.report.unknown_detail = queried[0]; await p.shot('unknown-original-ref');
  });
  await drain();
}
run('report-reentry', exercise, { once: true });
