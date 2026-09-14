'use strict';
const assert = require('node:assert/strict');

async function adoption(page, ready, theme, report, flush) {
  await page.goto(ready.run_url);
  await page.locator('[data-preflight-workspace]').getByRole('heading', { name: '执行排产', exact: true }).waitFor();
  if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /^切换(?:深色|浅色)$/ }).click();
  await page.getByRole('button', { name: '选择批次', exact: true }).click();
  for (const batch of ready.expected.batches) await page.getByRole('checkbox', { name: '选择 ' + batch, exact: true }).check();
  await page.getByLabel('计划开始日期', { exact: true }).fill('2026-09-09');
  await page.getByLabel('计划结束日期', { exact: true }).fill('2026-09-25');
  await page.getByRole('button', { name: '开始排产检查', exact: true }).click();
  await page.getByText('检查明细 · ' + ready.expected.task_count + ' 道', { exact: true }).click();
  await page.getByRole('button', { name: '核对并开始排产', exact: true }).click();
  await page.getByRole('button', { name: '确认开始排产', exact: true }).click();
  const table = page.getByRole('table', { name: '已保存候选', exact: true });
  await table.waitFor({ timeout: 120000 });
  await table.getByRole('button', { name: '详情', exact: true }).first().click();
  await page.getByRole('table', { name: '候选任务安排', exact: true }).waitFor();
  await page.locator('[data-run-adoption-action]').getByRole('button', { name: '采用方案', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '确认正式采用', exact: true });
  await dialog.getByLabel('采用原因', { exact: true }).fill('FB isolated downstream acceptance');
  await dialog.getByLabel('经办人', { exact: true }).fill('FB browser');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: '确认正式采用', exact: true }).click();
  await page.getByRole('dialog', { name: '正式采用结果', exact: true }).getByRole('button', { name: '进入正式计划', exact: true }).click();
  await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
  const formal = report.responses.slice().reverse().find(row => row.body.data && row.body.data.plan && row.body.data.tasks).body.data;
  assert.equal(formal.tasks.length, 9); assert.equal(formal.plan.version, 5);
  assert(formal.tasks.filter(task => task.piece_id !== null).every(task => task.quantity === 1 && task.batch_quantity === 3));
  return formal;
}
module.exports = { adoption };
