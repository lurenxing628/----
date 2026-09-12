'use strict';
const assert = require('node:assert/strict');
const { run } = require('./final_execution_browser_support.cjs');

async function exercise(p, phase) {
  const { page, ready } = p;
  await p.read(() => page.locator('.sidebar a[href$="?view=reports"]').click(), '/analytics');
  const initial = await p.read(() => page.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '执行复盘', exact: true }).click(), '/analytics');
  const data = initial.data;
  assert.equal(data.plan.plan_ref, ready.expected.final_e.plan_ref); assert.equal(data.summary.records, 33);
  assert.equal(data.resources.machines.length, 9); assert.equal(data.resources.people.length, 9);
  p.report.resources = data.resources;
  if (phase === 'restart') {
    await p.step(['WBP-REVIEW-008'], 'new-process-reads-identical-original-resource-facts', async () => { await p.shot('resources-restart'); });
    return;
  }
  await page.locator('.er-chart-disclosure > summary').click();
  for (const [kind, label, collection] of [['machine', '设备', 'machines'], ['operator', '人员', 'people']]) {
    await p.step(['WBP-REVIEW-008.A001', 'WBP-REVIEW-008.A004', 'WBP-REVIEW-008.A006'], kind + '-six-group-pages-full-coverage-and-F5', async () => {
      await page.getByRole('tablist', { name: '资源工时类型', exact: true }).getByRole('tab', { name: label, exact: true }).click();
      const section = page.getByRole('region', { name: '实际资源工时', exact: true });
      const refs = () => section.locator('.er-resource-row').evaluateAll(nodes => nodes.map(node => node.dataset.resourceRef));
      const first = await refs(); assert.equal(first.length, 6);
      await section.getByRole('button', { name: '资源工时下一页', exact: true }).click();
      const second = await refs(); assert.equal(second.length, 3);
      assert.deepEqual([...first, ...second], data.resources[collection].map(row => row.resource_ref || 'unassigned'));
      assert(await section.getByRole('button', { name: '资源工时下一页', exact: true }).isDisabled());
      await p.read(() => page.reload(), '/analytics'); await section.waitFor();
      assert.deepEqual(await refs(), second);
      assert.equal(await page.getByRole('tablist', { name: '资源工时类型', exact: true }).getByRole('tab', { selected: true }).innerText(), label);
      await section.getByRole('button', { name: '资源工时上一页', exact: true }).click(); assert.deepEqual(await refs(), first);
      await section.getByRole('button', { name: '资源工时下一页', exact: true }).click(); assert.deepEqual(await refs(), second);
      await p.shot(kind + '-resource-second-page');
    });
    await p.step(['WBP-REVIEW-008.A002', 'WBP-REVIEW-008.A003', 'WBP-REVIEW-008.A005'], kind + '-resource-drill-keeps-all-related-operation-records', async () => {
      const section = page.getByRole('region', { name: '实际资源工时', exact: true });
      const resource = ready.expected.final_e.resource_corrections[6][kind + '_ref'];
      const row = section.locator('[data-resource-ref="' + resource + '"]');
      await row.waitFor();
      const control = kind === 'machine' ? row.locator('.er-resource-bar') : row.locator('.er-resource-name');
      const opened = await p.read(() => control.click(), '/analytics');
      assert.equal(opened.data.scope.plan_ref, data.scope.plan_ref); assert.equal(opened.data.scope.resource_type, kind);
      assert.equal(opened.data.scope.resource_ref, resource); assert.equal(opened.data.topic, 'records');
      assert.equal(opened.data.rows.length, 13); assert.equal(opened.data.summary.records, 13);
      assert(new Set(opened.data.rows.map(record => record[kind + '_ref'])).size > 1);
      await page.locator('.rw-header').getByRole('button', { name: '返回来源', exact: true }).click(); await section.waitFor();
      assert.equal(await section.locator('.er-resource-row').count(), 3);
      assert.equal(await page.getByRole('tablist', { name: '资源工时类型', exact: true }).getByRole('tab', { selected: true }).innerText(), label);
      await p.shot(kind + '-resource-source-restored');
    });
  }
}
run('resources', exercise, { once: true });
