'use strict';
const assert = require('node:assert/strict'), path = require('node:path');
const { execFileSync } = require('node:child_process');

async function trialStaleWrite(page, ready, report, h, flush) {
  await h.action(['WBP-TRIAL-012.stale-write'], async () => {
    const original = report.original_draft.tasks.find(row => row.batch_id === 'B1' && row.sequence === 20 && row.piece_id === 'item-B');
    await h.selectTrial(20, 'item-B'); await h.button('调整此工序').click();
    await page.getByLabel('调整开工', { exact: true }).fill('2026-09-09T13:30');
    const other = await h.newTab(page.url());
    try {
      await other.page.locator('[data-trial-workspace] .tt-main').waitFor(); await flush();
      assert.equal(await other.page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), report.draft_ref);
      await other.h.selectTrial(20, 'item-B'); await other.h.button('调整此工序').click();
      await other.page.getByLabel('调整开工', { exact: true }).fill('2026-09-09T13:00');
      const write = other.page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/change'));
      await other.h.button('保存调整').click(); assert.equal((await write).status(), 200);
      await other.h.button('调整此工序').waitFor(); await flush();
      const changed = h.last(data => data.draft_ref === report.draft_ref && data.tasks).tasks.find(row => row.task_ref === original.task_ref);
      assert.equal(changed.start, '2026-09-09T13:00:00');
      const snapshot = label => JSON.parse(execFileSync(process.env.WORKBENCH_PYTHON || path.resolve(__dirname, '../../.venv/bin/python'),
        ['-B', path.join(__dirname, 'final_planning_database_probe.py'), ready.root, label], { encoding: 'utf8', env: process.env }));
      const before = snapshot('stale-write-before');
      const rejected = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/change'));
      await h.button('保存调整').click(); const response = await rejected, body = await response.json();
      assert.equal(response.status(), 409); assert.equal(body.ok, false); assert.equal(body.committed, false); assert.equal(body.error.code, 'stale_write');
      report.expected_rejected_api = (report.expected_rejected_api || []).concat({ url: response.url(), method: 'POST', status: 409,
        status_text: response.statusText(), code: body.error.code });
      await flush();
      assert.equal(await page.getByLabel('调整开工', { exact: true }).inputValue(), '2026-09-09T13:30');
      assert(await h.button('保存调整').isDisabled());
      const after = snapshot('stale-write-after');
      assert.equal(after.sha256, before.sha256); assert.equal(after.tables, 79);
      report.trial_stale_write = { draft_ref: report.draft_ref, task_ref: original.task_ref, other_tab_start: changed.start,
        retained_input: '2026-09-09T13:30', status: 409, code: body.error.code, before, after, all_tables_byte_equal: true };
      await h.shot('trial-real-two-tab-stale-write');
      await h.button('刷新工序').click(); await flush();
      assert.equal(await page.getByLabel('调整开工', { exact: true }).inputValue(), '2026-09-09T13:30');
      assert(!await page.getByRole('checkbox', { name: '已核对当前工序与保留输入', exact: true }).isChecked());
      assert(await h.button('保存调整').isDisabled());
      await h.button('取消编辑').click();
      const discard = page.getByRole('dialog', { name: '离开前确认', exact: true });
      await discard.getByText('试调工序的设备、人员或开工调整尚未保存。', { exact: true }).waitFor();
      await h.button('留在当前页面', discard).click(); await discard.waitFor({ state: 'hidden' });
      assert.equal(await page.getByLabel('调整开工', { exact: true }).inputValue(), '2026-09-09T13:30');
      assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), report.draft_ref);
      assert.equal(snapshot('stale-write-leave-refused').sha256, after.sha256);
      await h.button('取消编辑').click(); await h.button('放弃未保存内容并继续', discard).click();
      await discard.waitFor({ state: 'hidden' });
      assert.equal(snapshot('stale-write-edit-discarded').sha256, after.sha256);
      await h.selectTrial(20, 'item-B'); await h.button('调整此工序').click();
      await page.getByLabel('调整开工', { exact: true }).fill(original.start.slice(0, 16));
      const restoring = page.waitForResponse(value => value.request().method() === 'POST' && value.url().endsWith('/change'));
      await h.button('保存调整').click(); assert.equal((await restoring).status(), 200);
      await h.button('调整此工序').waitFor(); await flush();
      const restored = h.last(data => data.draft_ref === report.draft_ref && data.tasks);
      const task = restored.tasks.find(row => row.task_ref === original.task_ref);
      assert.equal(task.start, original.start); assert.equal(task.end, original.end); assert.equal(task.changed, false);
      assert.equal(restored.validation.constraints_status, 'valid');
    } finally { await other.page.close(); }
  });
}
module.exports = { trialStaleWrite };
