'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');

async function trialControls(page, report, h, flush) {
  const { action, button, shot } = h;
  const gantt = page.getByRole('region', { name: '试调甘特', exact: true });
  await action(['WBP-TRIAL-001.shell', 'WBP-TRIAL-001.theme', 'WBP-TRIAL-002.selected-status',
    'WBP-TRIAL-003.mode', 'WBP-TRIAL-003.baseline'], async () => {
    assert.equal(await page.locator('html').getAttribute('data-theme'), report.theme);
    assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), report.draft_ref);
    await h.caption(report.draft_ref, '试调草稿');
    const group = gantt.getByRole('tablist', { name: '甘特分组', exact: true });
    for (const name of ['人员', '批次', '设备']) {
      await group.getByRole('tab', { name, exact: true }).click();
      assert.equal(await group.getByRole('tab', { name, exact: true }).getAttribute('aria-selected'), 'true');
    }
    const baseline = gantt.getByRole('checkbox', { name: '原安排', exact: true });
    await baseline.uncheck(); assert.equal(await gantt.locator('[data-baseline-ref]').count(), 0);
    await baseline.check(); assert.equal(await gantt.locator('[data-baseline-ref]').count(), report.original_draft.task_count);
  });
  await action(['WBP-TRIAL-003.only-changed', 'WBP-TRIAL-003.search', 'WBP-TRIAL-003.expand',
    'WBP-TRIAL-003.escape'], async () => {
    const changed = gantt.getByRole('checkbox', { name: '仅变更', exact: true });
    await changed.check(); await gantt.getByText('当前显示范围没有匹配工序', { exact: true }).waitFor();
    assert.equal(await gantt.locator('[data-task-ref]').count(), 0);
    await changed.uncheck();
    const search = page.getByLabel('搜索试调工序', { exact: true });
    await search.fill('item-B'); await flush();
    assert.equal(await gantt.locator('[data-task-ref]').count(), 3);
    const refs = await gantt.locator('[data-task-ref]').evaluateAll(nodes => nodes.map(node => node.dataset.taskRef));
    assert(refs.every(ref => report.original_draft.tasks.some(task => task.task_ref === ref && task.piece_id === 'item-B')));
    await button('展开甘特').click(); await page.locator('.tt-gantt.tt-expanded').waitFor();
    await shot('trial-expanded-search'); await page.keyboard.press('Escape');
    assert.equal(await page.locator('.tt-gantt.tt-expanded').count(), 0);
    await search.fill(''); await flush();
    assert.equal(await gantt.locator('[data-task-ref]').count(), report.original_draft.task_count);
  });
  await action(['WBP-TRIAL-004.predecessors', 'WBP-TRIAL-010.empty'], async () => {
    await h.selectTrial(60);
    const task = report.original_draft.tasks.find(value => value.sequence === 60);
    assert(task.predecessor_refs.length > 0);
    const inspector = page.getByRole('complementary', { name: '工序详情', exact: true });
    await inspector.getByRole('button', { name: /^前序 / }).first().click();
    const selected = await gantt.locator('[data-task-ref][aria-pressed=true]').getAttribute('data-task-ref');
    assert(task.predecessor_refs.includes(selected));
    await page.getByRole('tab', { name: '未排工序', exact: true }).click();
    const table = page.getByRole('table', { name: '未排工序', exact: true });
    assert.equal(await table.locator('tbody tr').count(), 0);
    await table.locator('..').getByText('暂无记录', { exact: true }).waitFor();
    await shot('trial-predecessor-and-empty');
    await page.getByRole('tab', { name: '完整任务', exact: true }).click();
  });
  await action(['WBP-TRIAL-011.print'], async () => {
    const before = await page.evaluate(() => ({ theme: document.documentElement.getAttribute('data-theme'),
      stored: Object.keys(localStorage).sort().map(key => [key, localStorage.getItem(key)]) }));
    await page.evaluate(() => {
      window.__finalPlanningPrint = [];
      for (const name of ['beforeprint', 'afterprint']) window.addEventListener(name, event => window.__finalPlanningPrint.push({
        event: name, trusted: event.isTrusted, theme: document.documentElement.getAttribute('data-theme'),
        stored: Object.keys(localStorage).sort().map(key => [key, localStorage.getItem(key)])
      }), { once: true });
    });
    const target = path.join(path.dirname(report.screenshots[0].full), 'final-planning-native-print.pdf');
    const bytes = await page.pdf({ path: target, printBackground: true });
    assert.equal(bytes.subarray(0, 5).toString(), '%PDF-');
    await page.waitForFunction(() => window.__finalPlanningPrint.length === 2);
    const events = await page.evaluate(() => window.__finalPlanningPrint);
    assert.deepEqual(events.map(row => [row.event, row.trusted, row.theme]), [['beforeprint', true, 'light'], ['afterprint', true, before.theme]]);
    assert(events.every(row => JSON.stringify(row.stored) === JSON.stringify(before.stored)));
    assert.equal(await page.locator('html').getAttribute('data-theme'), before.theme);
    assert.deepEqual(fs.readFileSync(target), bytes);
    report.native_print = { method: 'Chromium native Page.printToPDF, trusted beforeprint/afterprint; no synthetic events or media emulation',
      path: target, sha256: crypto.createHash('sha256').update(bytes).digest('hex'), events };
    await shot('trial-after-native-print');
  });
}
module.exports = { trialControls };
