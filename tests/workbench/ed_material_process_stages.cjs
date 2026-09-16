'use strict';
const assert = require('node:assert/strict');
const b = (scope, name) => scope.getByRole('button', {name, exact: true});
async function processPage(p, page) {
  await page.goto(p.ready.url + '/workbench?view=process');
  // Since 2026-09-13 the workspace restores the last open detail dialog after a reload, which keeps the rail disabled;
  // dismiss it so this helper always starts from the list.
  const tile = page.locator('.hb-tile').filter({hasText: /^工艺/}); await tile.waitFor();
  for (let i = 0; i < 40 && await tile.isDisabled(); i++) {
    const restored = page.locator('[role="dialog"][aria-modal="true"]:visible').last();
    if (await restored.count()) { p.step('close-restored-dialog', await restored.getAttribute('aria-label')); await page.keyboard.press('Escape'); }
    await page.waitForTimeout(250);
  }
  await p.click(tile);
  await page.locator('[data-process-workspace] tbody tr[data-process-ref]').first().waitFor();
}
async function openProcess(p, page, code) {
  const area = page.locator('[data-process-workspace]');
  await p.type(area.getByRole('searchbox'), code);
  await p.response('/entities/part', () => area.getByRole('searchbox').press('Enter'));
  const open = b(area, '查看 ' + code), ref = await open.locator('xpath=ancestor::tr').getAttribute('data-process-ref');
  const result = await p.response('/entities/part/' + ref, () => p.click(open));
  await page.getByRole('tablist', {name: '零件工艺步骤', exact: true}).waitFor();
  return result;
}
async function saved(p, action, locator) {
  const response = await p.response('/' + action, () => p.click(locator));
  assert(['committed', 'unchanged'].includes(response.result));
  const receipt = p.oracle().tables.WorkbenchCommandReceipts.find(r => r.receipt_ref === response.receipt_ref);
  assert(receipt); const request = p.report.network.find(r => r.event === 'request' && r.post && JSON.parse(r.post).request_key === receipt.request_key);
  assert(request); return response;
}
async function processStages(p, page, data) {
  await processPage(p, page);
  const before = await openProcess(p, page, data.part);
  await p.click(page.getByRole('tab', {name: /^2 /}));
  let source = page.locator('[data-process-source-editor]:visible');
  assert(await source.getByRole('button', {name: /^保存归属并继续/}).isDisabled());
  assert((await source.getByRole('button', {name: /^保存归属并继续/}).getAttribute('title')).includes('先确认路线'));
  await p.shot('source-prerequisite-blocked');
  await p.click(page.getByRole('tab', {name: /^3 /}));
  let hours = page.locator('[data-process-hours-editor]:visible');
  assert(await hours.getByRole('button', {name: /^保存工时/}).isDisabled()); await p.shot('hours-prerequisite-blocked');
  await p.click(page.getByRole('tab', {name: /^1 /})); await p.click(b(page, '录入路线'));
  let entry = page.getByRole('dialog', {name: /^录入工艺路线 · /});
  assert(await entry.getByRole('button', {name: /^确认保存路线/}).isDisabled());
  await p.click(entry.getByRole('tab', {name: '逐行表格', exact: true}));
  await p.type(entry.getByLabel('第 1 行工序号', {exact: true}), '0'); await p.click(b(entry, '预检路线'));
  await entry.getByRole('alert').first().waitFor(); await p.shot('route-invalid-sequence-rejected');
  await p.type(entry.getByLabel('第 1 行工序号', {exact: true}), '10');
  await p.type(entry.getByLabel('第 1 行工种', {exact: true}), data.long_operation);
  await p.click(b(entry, '新增工序')); await p.type(entry.getByLabel('第 5 行工序号', {exact: true}), '50');
  await p.type(entry.getByLabel('第 5 行工种', {exact: true}), '检验'); await p.click(b(entry, '删除第 5 行'));
  await p.click(entry.getByRole('tab', {name: '整条录入', exact: true}));
  await p.type(entry.getByRole('textbox', {name: '路线文字', exact: true}), data.route);
  const preview = await p.response('/route-preview', () => p.click(b(entry, '预检路线')));
  assert.equal(preview.data.affected_groups.length, 0); assert.equal(preview.data.counts.operations, 4);
  await p.shot('route-real-preview'); await saved(p, 'route_confirm', b(entry, '确认保存路线'));
  source = page.locator('[data-process-source-editor]:visible'); await source.waitFor();
  await p.click(b(source, '保存归属并继续')); await source.getByRole('alert').first().waitFor(); await p.shot('source-unconfirmed-rejected');
  await p.click(b(source, '选择工序 10 工种'));
  let picker = page.getByRole('dialog', {name: '选择自制工种 · 工序 10', exact: true});
  await p.type(picker.getByRole('searchbox'), 'ED确实不存在的工种');
  await p.response('/entities/op_type', () => p.click(b(picker, '搜索'))); await picker.getByText('没有匹配选项。').waitFor(); await p.shot('source-picker-empty');
  await p.type(picker.getByRole('searchbox'), data.long_operation);
  await p.response('/entities/op_type', () => p.click(b(picker, '搜索'))); await p.shot('source-picker-long-name');
  await p.click(b(picker, '采用 ' + data.long_operation));
  await p.click(b(source, '清除工序 20 供应商')); await p.click(b(source, '选择工序 20 供应商'));
  picker = page.getByRole('dialog', {name: '选择供应商 · 工序 20', exact: true});
  await p.type(picker.getByRole('searchbox'), '热处理外协供应商');
  await p.response('/entities/supplier', () => p.click(b(picker, '搜索'))); await p.shot('supplier-picker-long-name');
  await p.click(picker.getByRole('button', {name: /^采用 热处理外协供应商/}));
  await p.click(source.getByRole('group', {name: '工序 10 归属', exact: true}).getByRole('button', {name: '自制', exact: true}));
  const previewResponse = page.waitForResponse(row => new URL(row.url()).pathname.endsWith('/stage-preview'));
  await saved(p, 'source_confirm', b(source, '保存归属并继续'));
  const checked = await (await previewResponse).json(); assert.equal(checked.data.affected_groups.length, 0); await p.shot('source-real-save');
  hours = page.locator('[data-process-hours-editor]:visible'); await hours.waitFor();
  await p.type(hours.getByLabel('工序 10 单件工时', {exact: true}), '');
  await p.click(b(hours, '保存工时')); await hours.getByRole('alert').first().waitFor(); await p.shot('hours-empty-not-zero');
  await p.type(hours.getByLabel('工序 10 单件工时', {exact: true}), '.625');
  await p.type(hours.getByLabel('外协组 20 至 20 总周期', {exact: true}), '7.25');
  await p.click(b(hours, '保存工时')); await page.getByRole('dialog', {name: '按零单件工时保存', exact: true}).waitFor();
  await p.shot('hours-zero-needs-review');
  assert.equal(await page.getByRole('dialog', {name: '按零单件工时保存', exact: true}).getByRole('checkbox').count(), 0);
  await p.shot('hours-real-confirm'); await saved(p, 'hours_confirm', b(page, '按 0 保存'));
  await page.getByText('三阶段已确认 · 已就绪', {exact: true}).waitFor(); await p.shot('process-ready-summary');
  await p.click(b(page, '关闭详情'));
  const after = await openProcess(p, page, data.part); assert(after.data.workflow.ready);
  assert.equal(after.data.operations.find(r => r.sequence === 10).unit_hours, .625);
  const changedGroup = after.data.external_groups.find(r => r.start_sequence === 20); assert.equal(changedGroup.total_days, 7.25);
  for (const group of before.data.external_groups) {
    const current = after.data.external_groups.find(r => r.ref === group.ref); assert(current);
    assert.deepEqual({...current, total_days: group.total_days}, group);
  }
  assert.equal(after.data.fields.remark, before.data.fields.remark);
  assert.equal(after.data.operations.find(r => r.sequence === 20).external_days, null);
  await p.click(b(page, '关闭详情'));
}
async function protectedAndEmpty(p, page) {
  await processPage(p, page); await openProcess(p, page, p.ready.expected.ed.locked_part);
  await p.click(page.getByRole('tab', {name: /^3 /}));
  const hours = page.locator('[data-process-hours-editor]:visible');
  await p.type(hours.getByLabel('工序 1 单件工时', {exact: true}), '4');
  const rejected = await p.response('/hours_confirm', () => p.click(b(hours, '保存工时')), 409);
  assert.equal(rejected.error.code, 'calibration_quota_locked'); assert.equal(rejected.committed, false);
  await page.getByText('已采纳的单件定额已锁定，普通保存不能覆盖。', {exact: true}).waitFor();
  await p.shot('calibration-lock-real-rejection');
  await p.click(b(page, '关闭详情')); await p.click(b(page.getByRole('dialog', {name: '放弃未保存的工艺草稿？', exact: true}), '放弃草稿并关闭'));
  await openProcess(p, page, p.ready.expected.ed.empty_part);
  assert((await page.locator('.process-detail').innerText()).includes('尚无工序记录。')); await p.shot('process-empty-detail');
  await p.click(b(page, '关闭详情'));
}
module.exports = {processStages, protectedAndEmpty, processPage, openProcess};
