'use strict';
const assert = require('node:assert/strict');

async function recover(page, report, screenshot, record, flush, original) {
  const writes = report.requests.filter(row => row.method !== 'GET').length;
  const scenario = report.scenario_ref;
  await flush();
  await page.reload();
  await page.locator('[data-open-kind="scenario"] .tt-main').waitFor();
  assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), scenario);
  await screenshot(page, '12-saved-scenario-reload');
  await page.getByRole('button', { name: '返回方案', exact: true }).click();
  await page.locator('[data-plan-workspace] .plan-main').waitFor();
  await flush();
  const restored = report.responses.findLast(row => row.body.data && row.body.data.plan && row.body.data.tasks).body.data;
  assert.equal(restored.plan.plan_ref, original.plan.plan_ref); assert.deepEqual(restored.tasks, original.tasks);
  await screenshot(page, '13-original-plan-restored');
  await page.locator('.sidebar-nav').getByRole('link', { name: '执行排产', exact: true }).click();
  await page.getByRole('button', { name: '查询原运行', exact: true }).click();
  await page.getByRole('table', { name: '已保存候选', exact: true }).waitFor();
  await page.getByRole('table', { name: '已保存候选', exact: true }).getByRole('button', { name: '详情', exact: true }).first().click();
  await page.getByRole('table', { name: '候选任务安排', exact: true }).waitFor();
  await page.locator('[data-run-adoption-action]').getByRole('button').first().click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: '进入正式方案', exact: true }).waitFor();
  await screenshot(page, '14-candidate-key-recovered');
  await flush();
  const posted = report.requests.filter(row => row.method === 'POST' && /\/candidates\/[^/]+\/adopt$/.test(row.url));
  assert.equal(posted.length, 1);
  const originalKey = posted[0].input.request_key;
  assert(report.requests.some(row => row.method === 'GET' && row.url.endsWith('/commands/' + originalKey)), 'Original adoption receipt must be read by original request key');
  assert.equal(report.requests.filter(row => row.method !== 'GET').length, writes, 'Recovery must not create another write request');
  report.recovery = { original_plan_ref: restored.plan.plan_ref, scenario_ref: scenario, candidate_request_key: originalKey, writes: 0 };
  record('original_scenario_plan_run_and_candidate_key_recovered');
}
module.exports = { recover };
