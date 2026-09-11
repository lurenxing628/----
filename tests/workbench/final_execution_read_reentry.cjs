'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { run } = require('./final_execution_browser_support.cjs');

async function exercise(p, view) {
  const { page } = p, field = view === 'field', endpoint = field ? '/execution/tasks' : '/calibration', events = [], pending = new Set(), bodyErrors = [], requests = new Set();
  const ownedRequest = request => new URL(request.url()).pathname.includes(field ? '/execution/' : '/calibration');
  page.on('request', request => { if (ownedRequest(request)) requests.add(request); });
  page.on('requestfinished', request => requests.delete(request));
  page.on('requestfailed', request => requests.delete(request));
  page.on('response', response => {
    const url = new URL(response.url());
    if (!url.pathname.includes(field ? '/execution/' : '/calibration') || !response.headers()['content-type']?.includes('application/json')) return;
    const reading = response.json().then(payload => events.push({ url: response.url(), status: response.status(), payload }));
    pending.add(reading);
    reading.then(() => pending.delete(reading), error => { bodyErrors.push({ url: response.url(), error: error.message }); pending.delete(reading); });
  });
  p.report.read_events = events; p.report.body_errors = bodyErrors;
  async function drain() {
    const deadline = Date.now() + 15000;
    while (requests.size || pending.size) {
      assert(Date.now() < deadline, 'Owned response bodies did not finish before navigation');
      await Promise.all([...pending]);
      if (requests.size) await new Promise(resolve => setTimeout(resolve, 20));
    }
    assert.deepEqual(bodyErrors, [], 'Every observed response body must be retained before navigation');
  }
  const selectedKey = field ? 'task_ref' : 'selected', expectedPage = field ? 2 : 3;
  const expectedRef = field ? p.ready.expected.final_e.task_refs['15'] : p.ready.expected.final_e.template_ref;
  const rowSelector = field ? '[data-field-task="' + expectedRef + '"]' : '.ca-table [data-ref="' + expectedRef + '"]';
  const selectedRow = () => page.locator(rowSelector);
  const detailSelector = field ? '.field-detail' : '.ca-detail';
  const paging = field ? '.field-footer' : '.calibration-live > .ca-page';
  const refreshLabel = field ? '刷新现场记录' : '刷新校准数据';
  const listReads = start => events.slice(start).filter(event => new URL(event.url).pathname.endsWith(endpoint));
  const context = () => page.evaluate(() => history.state.workbench.context);
  async function restart(number, saved) {
    await drain();
    fs.writeFileSync(path.join(p.ready.root, 'read-reentry-restart-request-' + number + '.json'), JSON.stringify({ context: saved, origin: p.ready.url }));
    const resumed = path.join(p.ready.root, 'read-reentry-restart-complete-' + number + '.json'), deadline = Date.now() + 100000;
    while (!fs.existsSync(resumed)) { assert(Date.now() < deadline, 'Owned server restart timed out'); await new Promise(resolve => setTimeout(resolve, 50)); }
    assert.equal(JSON.parse(fs.readFileSync(resumed, 'utf8')).url, p.ready.url);
  }
  let result = await p.read(() => page.locator('.sidebar a[href$="?view=' + view + '"]').click(), endpoint);
  if (field) {
    await page.getByRole('searchbox', { name: '搜索批次或工序', exact: true }).fill('B1');
    await p.read(() => page.getByRole('button', { name: '查询现场记录', exact: true }).click(), endpoint);
    await p.read(() => p.choose('现场每页数量', '10'), endpoint);
    result = await p.read(() => page.getByRole('button', { name: '现场下一页', exact: true }).click(), endpoint);
  } else {
    await page.getByRole('searchbox', { name: '搜索校准明细', exact: true }).fill('P1');
    await p.read(() => page.getByRole('button', { name: '搜索', exact: true }).click(), endpoint);
    await p.read(() => p.choose('工序来源', 'internal'), endpoint);
    await p.read(() => p.choose('排序字段', 'sample_count'), endpoint);
    await p.read(() => p.choose('每页数量', '10'), endpoint);
    for (let number = 1; number < expectedPage; number++) result = await p.read(() => page.getByRole('button', { name: '下一页', exact: true }).click(), endpoint);
  }
  assert.equal(result.data.page.number, expectedPage); assert(result.data.page.total > 10);
  const detail = await p.read(() => selectedRow().getByRole('button', { name: field ? /^查看报工 / : /^查看 P1 / }).click(), endpoint + '/' + expectedRef);
  let sampleRef = null;
  if (!field) {
    sampleRef = detail.data.suggestion.sample_refs[0]; assert(sampleRef);
    await page.locator('[data-sample-ref="' + sampleRef + '"] > summary').click();
    await page.waitForFunction(ref => history.state.workbench.context.sample_ref === ref, sampleRef);
  }
  await page.waitForFunction(({ key, ref }) => history.state.workbench.context[key] === ref, { key: selectedKey, ref: expectedRef });
  const baseline = { result, detail, selected: expectedRef, sample: sampleRef, context: await context() };
  p.report.baseline = baseline;

  function facts(value, meta, key) {
    if (Array.isArray(value)) return value.map(item => facts(item, meta));
    if (!value || typeof value !== 'object') return value;
    const result = {};
    for (const [name, item] of Object.entries(value)) {
      if (key === 'write_context' && ['write_token', 'expires_at'].includes(name)) {
        if (name === 'write_token') assert(item === null || typeof item === 'string');
        else assert(item === null || Number.isFinite(Date.parse(item + 'Z')));
      } else if (!field && ['snapshot_ref', 'as_of', 'generated_at'].includes(name)) {
        assert.equal(item, name === 'snapshot_ref' ? meta.snapshot_ref : meta.as_of);
      } else result[name] = facts(item, meta, name);
    }
    return result;
  }

  async function restored(label, start) {
    const lists = listReads(start);
    assert(lists.length, 'A new list request must be observed');
    assert.equal(lists[0].status, 200, JSON.stringify(lists[0]));
    await page.locator(detailSelector + (field ? '' : ' .ca-facts')).waitFor();
    await page.waitForFunction(({ key, ref, number }) => history.state.workbench.context[key] === ref && history.state.workbench.context.table.page === number,
      { key: selectedKey, ref: expectedRef, number: expectedPage });
    const reads = listReads(start), first = reads[0], last = reads[reads.length - 1];
    assert.equal(first.payload.data.page.number, 1); assert.equal(new URL(first.url).searchParams.has('snapshot_ref'), false);
    assert.equal(reads.length, 2); assert.equal(last.status, 200); assert.equal(last.payload.data.page.number, expectedPage);
    assert.equal(new URL(last.url).searchParams.get('snapshot_ref'), first.payload.meta.snapshot_ref);
    assert.deepEqual(last.payload.data.scope, baseline.result.data.scope);
    assert.deepEqual(facts(last.payload.data, last.payload.meta), facts(baseline.result.data, baseline.result.meta));
    const original = events.slice(start).find(event => new URL(event.url).pathname.endsWith(endpoint + '/' + expectedRef));
    assert(original && original.status === 200); assert.equal(new URL(original.url).searchParams.get('snapshot_ref'), last.payload.meta.snapshot_ref);
    assert.deepEqual(facts(original.payload.data, original.payload.meta), facts(baseline.detail.data, baseline.detail.meta));
    const saved = await context();
    for (const section of [saved, saved.table, saved.scope]) assert.equal(Object.hasOwnProperty.call(section, 'snapshot_ref'), false);
    assert.equal(saved[selectedKey], expectedRef); assert.equal(saved.table.page, expectedPage);
    if (field) assert.equal(saved.plan_ref, baseline.context.plan_ref);
    else { assert.equal(saved.sample_ref, sampleRef); assert.equal(await page.locator('[data-sample-ref="' + sampleRef + '"]').getAttribute('open'), ''); }
    p.report.reentries = (p.report.reentries || []).concat({ label, reads: events.slice(start), read_view: saved });
    await p.shot(label);
    result = last.payload;
  }
  async function reload(label) {
    await drain();
    const start = events.length;
    await p.read(() => page.reload(), endpoint);
    await restored(label, start);
  }
  await p.step([field ? 'WBP-FIELD-014' : 'WBP-CALIB-006'], view + '-same-page-new-pid-legacy-history-original-page-and-refs', async () => {
    const saved = await context(), token = result.meta.snapshot_ref;
    const legacy = { ...saved, snapshot_ref: token, table: { ...saved.table, snapshot_ref: token }, scope: { ...saved.scope, snapshot_ref: token } };
    p.report.legacy_history = legacy;
    await page.evaluate(value => history.replaceState({ ...history.state, workbench: { ...history.state.workbench, context: value } }, '', location.href), legacy);
    if (field) {
      await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
      await page.locator('.field-editor > details > summary').click();
      await page.getByRole('textbox', { name: '作业备注', exact: true }).fill('UNSAVED-RESTART-MUST-NOT-POST');
    }
    await restart(1, legacy);
    await reload('same-port-new-pid-original-read-view');
    assert.notEqual(result.meta.snapshot_ref, token);
    assert.equal(p.report.requests.filter(request => request.method === 'POST').length, 0);
  });
  await p.step([field ? 'WBP-FIELD-014' : 'WBP-CALIB-006'], view + '-same-pid-sidebar-return-and-F5', async () => {
    await drain();
    await p.read(() => page.locator('.sidebar a[href$="?view=reports"]').click(), '/analytics');
    const start = events.length;
    await p.read(() => page.locator('.sidebar a[href$="?view=' + view + '"]').click(), endpoint);
    await restored('same-pid-sidebar-return', start);
    await reload('same-pid-F5');
  });
  await p.step([field ? 'WBP-FIELD-017' : 'WBP-CALIB-005'], view + '-download-uses-fresh-legitimate-list-token', async () => {
    if (field) await page.getByRole('button', { name: '报工文件', exact: true }).click();
    const ending = field ? '/execution/files/export' : '/calibration/export';
    const waiting = page.waitForResponse(response => new URL(response.url()).pathname.endsWith(ending));
    const file = await p.download(() => page.getByRole('button', { name: field ? '导出当前范围' : '导出全部筛选', exact: true }).click(), view + '-original-filtered-scope');
    const response = await waiting;
    assert.equal(response.status(), 200); assert.equal(new URL(response.url()).searchParams.get('snapshot_ref'), result.meta.snapshot_ref);
    // Python binds these saved bytes to the unique original host stream; response.body() can refetch attachments on Chromium 109.
    p.report.export = { path: file, url: response.url(), headers: response.headers() };
    if (field) await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  });
  await p.step([field ? 'WBP-FIELD-014' : 'WBP-CALIB-006'], view + '-active-old-token-409-no-auto-rebind-explicit-refresh-preserves-page', async () => {
    await restart(2, await context());
    const start = events.length;
    const error = await p.read(() => page.locator(paging).getByRole('button', { name: field ? '现场上一页' : '上一页', exact: true }).click(), endpoint, 409);
    assert.equal(error.error.code, 'snapshot_stale');
    assert.equal(listReads(start).length, 1); assert.equal(new URL(listReads(start)[0].url).searchParams.get('snapshot_ref'), result.meta.snapshot_ref);
    await p.shot('active-stale-visible-error');
    const fresh = events.length;
    const detailResponse = !field && page.waitForResponse(response => new URL(response.url()).pathname.endsWith(endpoint + '/' + expectedRef)
      && response.status() === 200).then(response => response.json());
    const targetResponse = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname.endsWith(endpoint) && url.searchParams.get('page') === String(expectedPage - 1) && response.status() === 200;
    });
    await p.read(() => page.getByRole('button', { name: refreshLabel, exact: true }).click(), endpoint);
    await (await targetResponse).json();
    if (detailResponse) {
      const detail = await detailResponse;
      assert.equal(detail.data.suggestion.template_operation_ref, expectedRef);
      await page.waitForFunction(({ ref, number }) => history.state.workbench.context.selected === ref
        && history.state.workbench.context.table.page === number && document.querySelector('.ca-detail .ca-facts'),
        { ref: expectedRef, number: expectedPage - 1 });
    }
    await page.waitForFunction(({ selector, number }) => { const node = document.querySelector(selector); return node && node.textContent.includes('第 ' + number + ' /'); },
      { selector: paging, number: expectedPage - 1 });
    const reads = listReads(fresh);
    assert.equal(reads[0].payload.data.page.number, 1); assert.equal(new URL(reads[0].url).searchParams.has('snapshot_ref'), false);
    const last = reads[reads.length - 1]; assert.equal(last.payload.data.page.number, expectedPage - 1);
    const originalScope = { ...baseline.result.data.scope }, returnedScope = { ...last.payload.data.scope };
    if (!field) { delete originalScope.page; delete returnedScope.page; }
    assert.deepEqual(returnedScope, originalScope);
    p.report.live_stale = { error, fresh: reads };
  });
  await p.step([field ? 'WBP-FIELD-014' : 'WBP-CALIB-006'], view + '-unknown-original-ref-visible-failure-no-substitution', async () => {
    await drain();
    const absent = '0'.repeat(48), saved = await context(), start = events.length;
    await page.evaluate(value => history.replaceState({ ...history.state, workbench: { ...history.state.workbench, context: value } }, '', location.href),
      { ...saved, [selectedKey]: absent, ...(field ? { operation_ref: undefined } : {}) });
    await page.reload();
    await page.locator(field ? '.field-workspace' : '.ca-detail').getByRole('alert').first().waitFor();
    const rejected = events.slice(start).filter(event => event.status >= 400);
    assert(rejected.length); assert(rejected.some(event => event.status === 404));
    assert.equal((await context())[selectedKey], absent);
    if (field) assert.equal(await page.locator('.field-detail').count(), 0);
    else assert.equal(await page.locator('.ca-detail .ca-facts').count(), 0);
    p.report.unknown_original = rejected; await p.shot('unknown-original-ref');
  });
  await drain();
}
run('read-reentry', exercise, { once: true });
