'use strict';
const fs = require('node:fs'), path = require('node:path');

async function restart(h) {
  const { page, request, assert, config, report, shot } = h;
  await h.dashboard();
  if (config.theme === 'dark') await page.getByRole('button', { name: '切换深色', exact: true }).click();
  await h.category('齐套缺口');
  await request('/dashboard', () => h.select('处置状态', '未关闭'));
  await page.getByLabel('搜索条目、责任人、行动或备注', { exact: true }).fill('F-R2');
  await request('/dashboard', () => page.getByRole('button', { name: '执行条目搜索', exact: true }).click());
  await request('/dashboard', () => h.select('每页条目数', '10 项'));
  await request('/dashboard', () => page.getByRole('button', { name: '改为降序', exact: true }).click());
  const second = await request('/dashboard', () => page.getByRole('button', { name: '清单下一页', exact: true }).click());
  assert.equal(second.data.page.number, 2); assert.equal(second.data.page.total, 25);
  assert.equal(second.data.items[0].item_ref, config.item_ref);
  await request('/dashboard/items/' + config.item_ref, () => page.locator('[data-item-ref="' + config.item_ref + '"]').getByRole('button').click());
  await request('/dashboard/items/' + config.item_ref + '/history', () => page.getByRole('button', { name: '查看处置历史', exact: true }).click());
  const originalHistory = await request('/dashboard/items/' + config.item_ref + '/history', () => page.getByRole('button', { name: '历史下一页', exact: true }).click());
  assert.equal(originalHistory.data.history.page.number, 2);
  assert.equal(originalHistory.data.history.page.total, 26);
  await page.waitForFunction(() => history.state.workbench.context.history_page === 2);
  report.before_restart = { url: page.url(), context: await page.evaluate(() => history.state.workbench.context),
    snapshot_ref: second.meta.snapshot_ref, first_sequence: originalHistory.data.history.items[0].sequence };
  await shot('dashboard-second-page-before-new-process');
  fs.writeFileSync(path.join(config.restart_dir, 'browser-restart-request.json'), JSON.stringify(report.before_restart));
  const deadline = Date.now() + 60000, resume = path.join(config.restart_dir, 'browser-restart-resume.json');
  while (!fs.existsSync(resume) && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 100));
  assert(fs.existsSync(resume), 'The real host restart did not finish');
  report.process_restart = JSON.parse(fs.readFileSync(resume, 'utf8'));
  assert.notEqual(report.process_restart.first_pid, report.process_restart.second_pid);
  assert.equal(report.process_restart.first_port, report.process_restart.second_port);
  const responses = [];
  const collect = response => { if (new URL(response.url()).pathname === '/api/workbench/v1/dashboard') responses.push(response); };
  page.on('response', collect);
  await page.reload();
  await page.locator('[data-dashboard-workspace][data-ready=true]').waitFor();
  await page.locator('[data-history-sequence="' + report.before_restart.first_sequence + '"]').waitFor();
  page.off('response', collect);
  report.after_restart = { url: page.url(), context: await page.evaluate(() => history.state.workbench.context), reads: [] };
  for (const response of responses) report.after_restart.reads.push({ url: response.url(), status: response.status(), payload: await response.json() });
  assert.equal(page.url(), report.before_restart.url);
  const expected = structuredClone(report.before_restart.context); delete expected.scope.snapshot_ref;
  assert.deepEqual(report.after_restart.context, expected);
  assert.equal(report.after_restart.context.scope.page, 2);
  assert.equal(report.after_restart.context.history_page, 2);
  const reads = report.after_restart.reads;
  assert.deepEqual(reads.map(row => row.status), [200, 200]);
  assert.deepEqual(reads.map(row => row.payload.data.page.number), [1, 2]);
  assert.notEqual(reads[0].payload.meta.snapshot_ref, report.before_restart.snapshot_ref);
  assert.equal(reads[1].payload.meta.snapshot_ref, reads[0].payload.meta.snapshot_ref);
  for (const row of reads) {
    const q = new URL(row.url).searchParams;
    for (const key of ['category', 'status', 'query', 'sort', 'direction', 'size', 'source']) assert.equal(q.get(key), String(expected.scope[key]));
  }
  await shot('dashboard-history-second-page-after-new-process');
  await page.getByRole('tab', { name: '处置清单', exact: true }).click();
  await page.locator('[data-detail-ref="' + config.item_ref + '"]').waitFor();
  assert.equal(await page.locator('tr[data-selected=true]').getAttribute('data-item-ref'), config.item_ref);
  await page.getByText('共 25 项 · 第 2 / 3 页', { exact: true }).waitFor();
  await shot('dashboard-same-scope-page-two-selection-after-new-process');
  assert.equal(report.responses.filter(row => row.method !== 'GET').length, 0);
}

async function unlocatable(h) {
  const { page, request, assert, config, report, shot, mark } = h;
  await h.dashboard();
  if (config.theme === 'dark') await page.getByRole('button', { name: '切换深色', exact: true }).click();
  const material = await h.detail('material', '齐套缺口');
  assert.equal(material.navigation[0].enabled, true);
  await page.locator('[data-detail-ref]').getByRole('button', { name: '批次管理', exact: true }).click();
  await page.waitForURL('**view=batches');
  assert.equal(await page.getByRole('dialog').count(), 0);
  report.exact_navigation = await page.evaluate(() => history.state.workbench);
  assert.equal(report.exact_navigation.context.entity_ref, material.source.batch_ref);
  await page.goBack(); await page.locator('[data-detail-ref="' + material.item_ref + '"]').waitFor();
  await h.category('交期风险');
  await request('/dashboard', () => h.select('处置状态', '跟进中'));
  await page.getByLabel('搜索条目、责任人、行动或备注', { exact: true }).fill('B1');
  await request('/dashboard', () => page.getByRole('button', { name: '执行条目搜索', exact: true }).click());
  const detail = await request('/dashboard/items/' + config.item_ref, () => page.locator('[data-item-ref="' + config.item_ref + '"]').getByRole('button').click());
  const item = detail.data.item;
  assert.equal(item.source_state, 'not_currently_evaluated'); assert.equal(item.navigation[0].enabled, false);
  assert.equal(item.source.plan_ref, config.original_plan_ref);
  await request('/dashboard/items/' + config.item_ref + '/history', () => page.getByRole('button', { name: '查看处置历史', exact: true }).click());
  await request('/dashboard/items/' + config.item_ref + '/history', () => page.getByRole('button', { name: '历史下一页', exact: true }).click());
  await page.getByRole('tab', { name: '处置清单', exact: true }).click();
  await page.waitForFunction(() => history.state.workbench.context.tab === 'items' && history.state.workbench.context.history_page === 2);
  const original = await page.evaluate(() => history.state.workbench.context), originalURL = page.url();
  const open = async () => {
    await page.locator('[data-detail-ref]').getByRole('button', { name: '计划甘特', exact: true }).click();
    await page.getByRole('dialog', { name: '这条记录暂时打不开', exact: true }).waitFor();
  };
  const dialog = page.getByRole('dialog', { name: '这条记录暂时打不开', exact: true });
  await mark('WBP-DASH-014.unlocatable', async () => {
    report.dismissals = [];
    for (const mode of ['cancel', 'close', 'escape', 'backdrop']) {
      await open();
      await dialog.getByText(item.navigation[0].reason, { exact: true }).waitFor();
      assert((await dialog.innerText()).includes(item.subject));
      await h.revealReference(dialog, item.source.plan_ref);
      assert((await dialog.innerText()).includes(item.source.plan_ref));
      assert.equal(page.url(), originalURL);
      const box = await dialog.boundingBox();
      assert(box && box.x >= 0 && box.y >= 0 && box.x + box.width <= config.viewport.width && box.y + box.height <= config.viewport.height);
      if (mode === 'cancel') { await shot('unlocatable-confirmation-original-source'); await dialog.getByRole('button', { name: '取消', exact: true }).click(); }
      if (mode === 'close') await dialog.getByRole('button', { name: '关闭', exact: true }).click();
      if (mode === 'escape') await page.keyboard.press('Escape');
      if (mode === 'backdrop') await page.locator('.modal-bg').click({ position: { x: 2, y: 2 } });
      await dialog.waitFor({ state: 'hidden' });
      assert.equal(page.url(), originalURL); assert.deepEqual(await page.evaluate(() => history.state.workbench.context), original);
      assert.equal(await page.locator('tr[data-selected=true]').getAttribute('data-item-ref'), item.item_ref);
      report.dismissals.push({ mode, original_context_retained: true });
    }
  });
  await open();
  await mark('WBP-DASH-014.navigation-confirm', async () => {
    await dialog.getByRole('button', { name: '打开计划甘特概览', exact: true }).click();
    await page.waitForURL('**view=gantt');
    await page.getByText('尚未选择计划', { exact: true }).waitFor();
    const target = await page.evaluate(() => history.state.workbench);
    assert.deepEqual(target.context, { return_to: { view: 'dashboard', context: original } });
    assert.equal(await page.locator('.wb-current-plan').count(), 0);
    assert.equal(await page.locator('[data-task-ref][data-selected=true]').count(), 0);
    await shot('safe-gantt-overview-without-any-object-reference');
    report.overview_navigation = target;
    await page.goBack(); await page.locator('[data-detail-ref="' + item.item_ref + '"]').waitFor();
    assert.deepEqual(await page.evaluate(() => history.state.workbench.context), original);
    assert.equal(await dialog.count(), 0);
    await page.locator('[data-detail-ref] .dy-badge').filter({ hasText: /^跟进中$/ }).waitFor();
    await shot('navigation-return-to-original-unlocatable-item');
  });
  await open(); await page.reload(); await page.locator('[data-detail-ref="' + item.item_ref + '"]').waitFor();
  assert.equal(await dialog.count(), 0);
  assert.deepEqual(await page.evaluate(() => history.state.workbench.context), original);
  report.unlocatable = { item, original_context: original, refresh_cleared_dialog_only: true };
  assert.equal(report.responses.filter(row => row.method !== 'GET').length, 0);
}

module.exports = { restart, unlocatable };
