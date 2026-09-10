'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { run } = require('./final_execution_browser_support.cjs');

async function exercise(p, view) {
  const { page } = p, events = [];
  page.on('response', async response => {
    const url = new URL(response.url());
    if (!url.pathname.includes('/analytics') || url.pathname.endsWith('/export')) return;
    const payload = await response.json();
    events.push({ url: response.url(), status: response.status(), payload });
  });
  p.report.read_events = events;
  async function restart(number, context) {
    fs.writeFileSync(path.join(p.ready.root, 'report-reentry-restart-request-' + number + '.json'), JSON.stringify({ context, origin: p.ready.url }));
    const resumed = path.join(p.ready.root, 'report-reentry-restart-complete-' + number + '.json'), deadline = Date.now() + 100000;
    while (!fs.existsSync(resumed)) { assert(Date.now() < deadline, 'Owned server restart timed out'); await new Promise(resolve => setTimeout(resolve, 50)); }
    assert.equal(JSON.parse(fs.readFileSync(resumed, 'utf8')).url, p.ready.url);
  }
  const tab = '.sidebar a[href$="?view=' + view + '"]';
  await p.read(() => page.locator(tab).click(), '/analytics');
  if (view === 'reports') await p.read(() => page.getByRole('tab', { name: '报工记录', exact: true }).click(), '/analytics');
  const search = page.getByRole('searchbox', { name: '搜索批次或工序', exact: true });
  await search.fill('OP');
  for (const label of ['计划完工起日', '计划完工止日']) await page.getByLabel(label, { exact: true }).fill('2026-09-09');
  let result = await p.read(() => page.getByRole('button', { name: '查询范围', exact: true }).click(), '/analytics');
  await p.read(() => p.choose('每页数量', '10'), '/analytics');
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
    const reads = events.slice(startIndex), lists = reads.filter(event => new URL(event.url).pathname.endsWith('/analytics'));
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
    assert(text.includes(final.payload.meta.as_of.replace('T', ' ')));
    p.report.reentries = (p.report.reentries || []).concat({ label, reads, read_view: context });
    await p.shot(label);
    return final.payload;
  }

  await p.step(['WBP-SCOPE-005', 'WBP-REPORT-010'], view + '-same-pid-sidebar-return-restores-page-two-original-detail', async () => {
    await p.read(() => page.locator('.sidebar a[href$="?view=field"]').click(), '/execution/tasks');
    const start = events.length;
    await page.locator(tab).click(); result = await assertRestored('same-pid-return', start);
  });
  await p.step(['WBP-SCOPE-005'], view + '-legacy-history-F5-ignores-both-old-token-locations', async () => {
    const current = await page.evaluate(() => history.state.workbench.context);
    const legacy = { ...current, snapshot_ref: result.meta.snapshot_ref, table: { ...current.table, snapshot_ref: result.meta.snapshot_ref } };
    p.report.legacy_history = legacy;
    await page.evaluate(value => history.replaceState({ ...history.state, workbench: { ...history.state.workbench, context: value } }, '', location.href), legacy);
    const start = events.length; await page.reload(); result = await assertRestored('same-pid-legacy-F5', start);
  });
  await p.step(['WBP-SCOPE-005', 'WBP-REPORT-008', 'WBP-REPORT-010'], view + '-same-port-new-pid-read-detail-and-real-export', async () => {
    const legacy = { ...(await page.evaluate(() => history.state.workbench.context)), snapshot_ref: result.meta.snapshot_ref };
    legacy.table = { ...legacy.table, snapshot_ref: result.meta.snapshot_ref };
    await page.evaluate(value => history.replaceState({ ...history.state, workbench: { ...history.state.workbench, context: value } }, '', location.href), legacy);
    await restart(1, legacy);
    const start = events.length; await page.reload(); result = await assertRestored('new-pid-original-read-view', start);
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
    const first = events.length;
    const downloadError = await p.read(() => page.getByRole('button', { name: '导出范围', exact: true }).click(), '/analytics/export', 409);
    assert.equal(downloadError.error.code, 'snapshot_stale');
    assert.equal(events.length, first, 'Export failure must not refresh the list automatically');
    await page.getByRole('button', { name: '关闭工序详情', exact: true }).click();
    const detailError = await p.read(() => page.locator('.rw-primary-table').getByRole('button', { name: /^查看工序 / }).first().click(), '/analytics/operations/' + operationRef, 409);
    assert.equal(detailError.error.code, 'snapshot_stale');
    await page.locator('.rw-detail').getByRole('alert').waitFor();
    await page.getByRole('button', { name: '关闭工序详情', exact: true }).click();
    const pageError = await p.read(() => page.locator('#report-topic-panel > .rw-pagination').getByRole('button', { name: '下一页', exact: true }).click(), '/analytics', 409);
    assert.equal(pageError.error.code, 'snapshot_stale'); await page.getByRole('button', { name: '重新读取', exact: true }).waitFor();
    const failed = events.slice(first);
    assert.equal(failed.length, 2); assert(failed.every(event => event.status === 409));
    assert(failed.every(event => new URL(event.url).searchParams.get('snapshot_ref') === result.meta.snapshot_ref));
    await p.shot('live-stale-explicit-error');
    p.report.live_stale = { export: downloadError, reads: failed };
    const recovery = events.length;
    await page.getByRole('button', { name: '重新读取', exact: true }).click();
    await page.waitForFunction(() => { const node = document.querySelector('#report-topic-panel > .rw-pagination'); return node && node.textContent.includes('第 3 /'); });
    const recovered = events.slice(recovery).filter(event => new URL(event.url).pathname.endsWith('/analytics'));
    assert.equal(recovered.length, 2); assert.equal(recovered[0].payload.data.page.number, 1); assert.equal(recovered[1].payload.data.page.number, 3);
    assert.equal(new URL(recovered[0].url).searchParams.has('snapshot_ref'), false);
    assert.equal(new URL(recovered[1].url).searchParams.get('snapshot_ref'), recovered[0].payload.meta.snapshot_ref);
    assert.deepEqual(recovered[1].payload.data.scope, baseline.scope);
    p.report.explicit_recovery = recovered;
  });
  await p.step(['WBP-REPORT-010', 'WBP-REPORT-012'], view + '-unknown-original-detail-ref-stays-explicit-not-replaced', async () => {
    const absent = '0'.repeat(48), start = events.length;
    await page.evaluate(ref => history.replaceState({ ...history.state, workbench: { ...history.state.workbench,
      context: { ...history.state.workbench.context, selected: ref } } }, '', location.href), absent);
    await page.reload(); await page.locator('.rw-detail').getByRole('alert').waitFor();
    const queried = events.slice(start).filter(event => new URL(event.url).pathname.includes('/analytics/operations/'));
    assert.equal(queried.length, 1); assert(queried[0].url.includes('/operations/' + absent)); assert.equal(queried[0].status, 404);
    assert.equal(await page.evaluate(() => history.state.workbench.context.selected), absent);
    assert.equal(await page.locator('.rw-detail-facts').count(), 0);
    p.report.unknown_detail = queried[0]; await p.shot('unknown-original-ref');
  });
}
run('report-reentry', exercise, { once: true });
