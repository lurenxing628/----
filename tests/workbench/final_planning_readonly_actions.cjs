'use strict';
const assert = require('node:assert/strict');

async function readonlyActions(page, ready, report, h, flush) {
  const { action, button, last, shot } = h;
  await page.goto(ready.url + '/workbench?view=analysis');
  await page.getByRole('table', { name: '可选排产方案', exact: true }).waitFor();
  if (await page.locator('html').getAttribute('data-theme') !== report.theme) await page.getByRole('button', { name: /^深色：/ }).click();
  assert.equal(await page.locator('html').getAttribute('data-theme'), report.theme);
  const navigation = { version: 1, view: 'analysis', context: { plan_ref: 'not-a-valid-plan' } };
  await action(['WBP-PLAN-004.invalid-reference'], async () => {
    const response = await page.goto(ready.url + '/workbench?view=analysis&nav=' + encodeURIComponent(JSON.stringify(navigation)));
    assert.equal(response.status(), 400);
    report.expected_rejected_documents = [{ url: response.url(), status: response.status() }];
    await page.getByRole('heading', { name: '工作台暂不可用', exact: true }).waitFor();
    await page.getByText('页面定位或范围无效，未恢复旧选择、改查其他身份或扩大范围。', { exact: true }).waitFor();
    await flush();
    assert(!report.requests.some(row => row.url.includes('/plans/not-a-valid-plan')));
    assert.equal(await page.locator('[data-plan-gantt]').count(), 0);
    assert.equal(await page.locator('.wb-current-plan[data-plan-ref]').count(), 0);
    const again = await page.reload(); assert.equal(again.status(), 400);
    report.expected_rejected_documents.push({ url: again.url(), status: again.status() });
    await page.getByRole('heading', { name: '工作台暂不可用', exact: true }).waitFor();
    await flush(); assert.equal(await page.locator('[data-plan-gantt]').count(), 0);
    await shot('invalid-plan-retained-no-fallback');
  });
  await action(['WBP-DELAY-001.unknown'], async () => {
    await page.getByRole('link', { name: '打开工作台', exact: true }).click();
    await page.locator('.sidebar-nav').getByRole('link', { name: '选择排产方案', exact: true }).click();
    if (await page.locator('html').getAttribute('data-theme') !== report.theme) await page.getByRole('button', { name: /^深色：/ }).click();
    const row = page.getByRole('table', { name: '可选排产方案', exact: true }).getByRole('row')
      .filter({ has: page.getByRole('cell', { name: String(ready.expected.official_version), exact: true }) });
    await row.getByRole('radio').check(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    const data = last(value => value.plan && value.tasks);
    assert.equal(data.plan.plan_ref, ready.expected.original_plan_ref);
    assert.equal(data.plan.version, 4);
    assert.notEqual(data.projections.baseline.state, 'available');
    const changed = page.getByRole('checkbox', { name: '仅变更', exact: true });
    assert(await changed.isDisabled()); assert(!(await changed.isChecked()));
    assert((await changed.locator('..').getAttribute('title')).length > 0);
    const risk = data.projections.delivery_risks.items.find(value => value.batch_id === 'B1');
    assert.equal(risk.risk, 'unknown'); assert.equal(risk.planned_finish, null); assert.equal(risk.delay_hours, null);
    assert.equal(risk.unscheduled_operation_count, 11);
    assert.equal(risk.partial_planned_finish, '2026-09-09T08:45:00');
    await button('交付风险', page.locator('.plan-heading').first()).click(); await flush();
    const batch = page.getByRole('table', { name: '交付风险列表', exact: true }).getByRole('row').filter({ has: button('B1') });
    assert((await batch.innerText()).includes('无法核实'));
    assert(!(await batch.innerText()).includes('预计按期'));
    await h.caption(ready.expected.original_plan_ref, '当前正式');
    report.original_incomplete_batch = risk;
    await shot('incomplete-original-batch-unknown');
  });
  assert(report.requests.every(row => row.method === 'GET'), 'Read-only boundary inspection cannot write');
}
module.exports = { readonlyActions };
