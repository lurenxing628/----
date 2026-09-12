'use strict';
const assert = require('node:assert/strict');
const { recover } = require('./piece_main_recovery.cjs');
const { ganttPixels, formalDetails } = require('./piece_main_visuals.cjs');
const { predecessorLinks } = require('./piece_main_dependencies.cjs');

async function adoption(page, kind, screenshot, record, report, flush) {
  const action = page.locator(kind === 'candidate' ? '[data-run-adoption-action]' : '.trial-adoption-action');
  const response = page.waitForResponse(row => row.url().endsWith('/adopt-preview') && row.request().method() === 'POST');
  await action.getByRole('button', { name: kind === 'candidate' ? '采用方案' : '正式采用', exact: true }).click();
  const preview = await (await response).json();
  const dialog = page.getByRole('dialog');
  if (!preview.data.validation.can_adopt) {
    await screenshot(page, kind + '-adoption-blocked');
    report.findings.push({ id: 'EQ-' + kind.toUpperCase() + '-ADOPTION-BLOCKED', response: preview, screenshot: report.screenshots.at(-1) });
    record(kind + '_adoption_blocked', { issues: preview.data.validation.issues });
    await dialog.getByRole('button', { name: '取消', exact: true }).click();
    return false;
  }
  await dialog.getByLabel('采用原因', { exact: true }).fill('EQ browser verified complete piece scope');
  await dialog.getByLabel('声明人', { exact: true }).fill('EQ browser acceptance');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: '确认正式采用', exact: true }).click();
  await dialog.getByRole('button', { name: '进入正式方案', exact: true }).waitFor();
  await flush();
  await screenshot(page, kind + '-adopted'); record(kind + '_adopted');
  await dialog.getByRole('button', { name: '进入正式方案', exact: true }).click();
  await page.locator('[data-plan-workspace] .plan-main').waitFor();
  return true;
}

async function trialChain(page, ready, report, screenshot, record, flush) {
  assert(await adoption(page, 'candidate', screenshot, record, report, flush));
  await screenshot(page, '05-formal');
  await ganttPixels(page, '[data-plan-workspace] .plan-main', 'official', report);
  await formalDetails(page, report, screenshot);
  await flush();
  const original = report.responses.findLast(row => row.body.data && row.body.data.plan && row.body.data.tasks).body.data;
  report.first_official = original.plan;
  const pieces = original.tasks.filter(task => task.batch_id === 'B1' && [20, 30].includes(task.sequence));
  if (pieces.some(task => !Object.hasOwn(task, 'piece_id'))) report.findings.push({ id: 'EQ-FORMAL-PIECE-IDENTITY',
    message: 'Official workspace DTO lacks piece identity; same-batch same-sequence bars cannot identify a piece', sample: pieces, screenshot: report.screenshots.at(-1) });
  if (pieces.some(task => task.quantity !== 1 || task.batch_quantity !== 3 || task.quantity_basis !== 'run_admission')) report.findings.push({
    id: 'EQ-FORMAL-PIECE-QUANTITY', message: 'Official per-piece and batch quantities must retain original run-admission evidence', sample: pieces, screenshot: report.screenshots.at(-1) });
  await page.locator('[data-plan-workspace] .plan-heading').first().getByRole('button', { name: '试调', exact: true }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: '核对原来源', exact: true }).click();
  await dialog.getByRole('checkbox', { name: '确认基于此来源创建独立草稿，正式计划保持不变', exact: true }).check();
  await flush();
  await dialog.getByRole('button', { name: '确认创建草稿', exact: true }).click();
  await page.locator('[data-trial-workspace] .tt-main').waitFor();
  await page.getByRole('tab', { name: '完整任务', exact: true }).click();
  const table = page.getByRole('table', { name: '完整任务明细', exact: true });
  await table.waitFor();
  await ganttPixels(page, '.tt-gantt', 'trial', report);
  await flush();
  const draft = report.responses.findLast(row => row.body.data && row.body.data.tasks && row.body.data.draft_ref && !row.body.data.scenario_ref).body.data;
  report.draft_ref = draft.draft_ref;
  const split = draft.tasks.filter(task => task.batch_id === 'B1' && task.piece_id !== null);
  assert.equal(split.length, 6); assert(split.every(task => task.quantity === 1 && task.batch_quantity === 3 && task.hours.total_hours === .25));
  const common = draft.tasks.filter(task => task.batch_id === 'B1' && task.piece_id === null);
  assert.equal(common.length, 2); assert(common.every(task => task.quantity === 3 && task.hours.total_hours === .75));
  const join = common.find(task => task.sequence === 40);
  assert.equal(join.predecessor_operation_refs.length, 3);
  const all = new Map(draft.tasks.map(task => [task.operation_ref, task]));
  for (const task of draft.tasks) for (const ref of task.predecessor_operation_refs) assert(all.get(ref).end <= task.start, 'Predecessor must finish before its successor');
  for (const [index, piece] of report.pieces.entries()) {
    const row = table.getByRole('row').filter({ hasText: piece }).filter({ has: page.getByRole('button', { name: 'B1 · Turning 20', exact: true }) });
    assert.equal(await row.count(), 1, 'Select by visible piece and sequence, never opaque ref');
    await row.getByRole('button').click();
    const detail = page.getByRole('complementary', { name: '工序详情', exact: true });
    assert((await detail.innerText()).includes(piece));
    await screenshot(page, 'trial-detail-identity-' + (index + 1));
  }
  const labels = await page.locator('.tt-task-label').filter({ hasText: /20/ }).allTextContents();
  if (labels.length !== 3 || report.pieces.some(piece => !labels.some(label => label.includes(piece)))) report.findings.push({ id: 'EQ-TRIAL-GANTT-IDENTITY',
    message: 'Trial table/details show piece_id, but same-sequence Gantt labels and accessible names omit it', labels, source: 'frontend/workbench/app/TrialGantt.jsx', screenshot: report.screenshots.at(-1) });
  await table.getByRole('button', { name: 'B1 · Turning 10', exact: true }).click();
  assert(await page.getByRole('button', { name: '调整此工序', exact: true }).isDisabled(), 'Completed reported common step must remain protected');
  await screenshot(page, '06-protected-detail'); record('trial_piece_facts_and_protection_verified');
  // The common join has a unique business sequence; no hidden piece/ref is used to choose it.
  await table.getByRole('button', { name: 'B1 · Turning 40', exact: true }).click();
  await predecessorLinks(page, table, report, screenshot);
  await page.getByRole('button', { name: '调整此工序', exact: true }).click();
  await page.getByLabel('调整开工', { exact: true }).fill('2026-09-09T13:00');
  await page.getByRole('button', { name: '保存调整', exact: true }).click();
  await page.getByRole('button', { name: '调整此工序', exact: true }).waitFor();
  await screenshot(page, '07-changed'); record('trial_change_saved');
  await page.getByRole('button', { name: '保存场景', exact: true }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('场景名称', { exact: true }).fill('EQ pieces ' + report.width + ' ' + report.theme);
  await dialog.getByRole('checkbox', { name: '确认保存完整场景，冲突和未排工序一并保留', exact: true }).check();
  await dialog.getByRole('button', { name: '确认保存场景', exact: true }).click();
  await page.locator('[data-open-kind="scenario"] .tt-main').waitFor();
  report.scenario_ref = await page.locator('[data-trial-workspace]').getAttribute('data-open-ref');
  await flush();
  const savedTasks = report.responses.findLast(row => row.body.data && row.body.data.scenario_ref === report.scenario_ref && row.body.data.tasks).body.data.tasks;
  await screenshot(page, '08-scenario'); record('scenario_saved', { scenario_ref: report.scenario_ref });
  if (!await adoption(page, 'trial', screenshot, record, report, flush)) {
    await recover(page, report, screenshot, record, flush, original);
    return;
  }
  await screenshot(page, '09-trial-official');
  await flush();
  const latest = report.responses.findLast(row => row.body.data && row.body.data.plan && row.body.data.tasks).body.data;
  report.second_official = latest.plan;
  assert.equal(latest.plan.version, original.plan.version + 1);
  assert(latest.tasks.filter(task => task.piece_id !== null).every(task => task.quantity === 1 && task.batch_quantity === 3 && task.quantity_basis === 'trial_creation'));
  assert(latest.tasks.some(task => task.batch_id === 'B1' && task.sequence === 40 && task.start === '2026-09-09T13:00:00'));
  await page.goBack();
  await page.locator('[data-open-kind="scenario"] .tt-main').waitFor();
  assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), report.scenario_ref);
  await flush();
  assert.deepEqual(report.responses.findLast(row => row.body.data && row.body.data.scenario_ref === report.scenario_ref && row.body.data.tasks).body.data.tasks, savedTasks);
  await page.locator('.trial-adoption-action').getByRole('button').first().click();
  dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: '查询原请求', exact: true }).click();
  await dialog.getByRole('button', { name: '进入正式方案', exact: true }).waitFor();
  await screenshot(page, '10-original-key-recovered');
  await dialog.locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click();
  await page.getByRole('button', { name: '返回方案', exact: true }).click();
  await page.locator('[data-plan-workspace] .plan-main').waitFor();
  await flush();
  const restored = report.responses.findLast(row => row.body.data && row.body.data.plan && row.body.data.tasks).body.data;
  assert.equal(restored.plan.plan_ref, original.plan.plan_ref);
  assert.deepEqual(restored.tasks, original.tasks);
  await screenshot(page, '11-original-plan-restored'); record('original_plan_and_key_recovered');
  await page.goBack();
  await page.locator('[data-open-kind="scenario"] .tt-main').waitFor();
  await recover(page, report, screenshot, record, flush, original);
}
module.exports = { trialChain };
