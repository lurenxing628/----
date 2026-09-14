'use strict';
const assert = require('node:assert/strict');
const {processPage, openProcess} = require('./ed_material_process_stages.cjs');
const b = (scope, name) => scope.getByRole('button', {name, exact: true});
const operation = (raw, seq) => raw.data.operations.find(row => row.sequence === seq);
function valid(raw, total = 6.75) {
  for (const seq of [20, 25, 40]) {
    const row = operation(raw, seq), group = raw.data.external_groups.find(group => group.ref === row.external_group_ref);
    assert.equal(row.external_days, null); assert.equal(row.external_days_source, 'group'); assert.deepEqual(row.issues, []);
    assert.equal(group.total_days, seq === 40 ? 9.5 : total); assert.deepEqual(group.issues, []);
  }
}
async function labels(area, raw, count = 3) {
  const cells = area.locator('[data-process-cycle-group]'); assert.equal(await cells.count(), count);
  for (const seq of [20, 25, 40]) {
    const row = operation(raw, seq);
    assert.equal(await area.getByLabel('工序 ' + seq + ' 外协周期', {exact: true}).count(), 0);
    assert((await cells.filter({hasText: '按外协组周期'}).allTextContents()).some(text => text.includes(seq === 40 ? '40 至 40' : '20 至 25')));
    assert(await area.locator('[data-process-cycle-group="' + row.external_group_ref + '"]').count() > 0);
  }
}
async function save(p, action, locator) {
  const response = await p.response('/' + action, () => p.click(locator));
  assert.equal(response.result, 'committed');
  const receipt = p.oracle().tables.WorkbenchCommandReceipts.find(row => row.receipt_ref === response.receipt_ref);
  assert(receipt); assert.deepEqual(JSON.parse(receipt.outcome_json), {data: response.data, result: response.result, warnings: response.warnings});
  const request = p.report.network.find(row => row.event === 'request' && row.post && JSON.parse(row.post).request_key === receipt.request_key);
  assert(request); return JSON.parse(request.post).input;
}
async function cycleSave(p, page, data) {
  await processPage(p, page); const before = await openProcess(p, page, data.part); valid(before);
  await p.click(page.getByRole('tab', {name: /^2 /}));
  let source = page.locator('[data-process-source-editor]:visible');
  await labels(source, before); await p.shot('source-valid-null-members');
  await p.click(page.getByRole('tab', {name: /^1 /})); await p.click(b(page, '录入路线'));
  const entry = page.getByRole('dialog', {name: /^录入工艺路线 · /});
  await p.click(entry.getByRole('tab', {name: '整条录入', exact: true}));
  await p.type(entry.getByRole('textbox', {name: '路线文字', exact: true}), data.route);
  const preview = await p.response('/route-preview', () => p.click(b(entry, '预检路线')));
  assert.equal(preview.data.counts.operations, 5); assert.deepEqual(preview.data.affected_groups, []);
  await save(p, 'route_confirm', b(entry, '确认保存路线'));
  source = page.locator('[data-process-source-editor]:visible'); await source.waitFor(); await labels(source, before);
  await p.click(source.getByRole('checkbox', {name: '确认本页已核对工序', exact: true}));
  const checked = await p.response('/stage-preview', () => p.click(b(source, '检查归属')));
  assert.deepEqual(checked.data.affected_groups, []);
  await save(p, 'source_confirm', b(source, '完成归属 · 解锁工时'));
  const hours = page.locator('[data-process-hours-editor]:visible'); await hours.waitFor(); await labels(hours, before);
  const total = hours.getByLabel('外协组 20 至 25 总周期', {exact: true});
  assert.equal(await total.inputValue(), '6.75');
  assert.equal(await hours.getByLabel('外协组 40 至 40 总周期', {exact: true}).inputValue(), '9.5');
  await page.waitForFunction(() => document.querySelector('[aria-label="外协组 20 至 25 总周期"]').classList.contains('wb-number-input'));
  assert.equal(await hours.getByRole('button', {name: '增加外协组 20 至 25 总周期', exact: true}).count(), 1);
  await p.click(hours.getByRole('checkbox', {name: '确认本页已核对工时', exact: true}));
  await p.type(total, '7.25');
  for (const seq of [20, 25]) assert.equal(await hours.getByRole('checkbox', {name: '确认工序 ' + seq + ' 工时', exact: true}).isChecked(), false);
  assert.equal(await hours.getByRole('checkbox', {name: '确认工序 40 工时', exact: true}).isChecked(), true);
  await p.click(hours.getByRole('checkbox', {name: '确认本页已核对工时', exact: true}));
  await p.click(hours.getByRole('checkbox', {name: '已复核单件工时为0', exact: true}));
  await p.shot('hours-group-only-editor');
  const payload = await save(p, 'hours_confirm', b(hours, '保存工时'));
  assert.equal(payload.groups.length, 2);
  for (const seq of [20, 25, 40]) assert.equal(payload.operations.find(row => row.ref === operation(before, seq).ref).external_days, null);
  await page.getByText('三阶段已确认 · 已就绪', {exact: true}).waitFor();
  await labels(page.getByRole('table', {name: '已就绪工序汇总', exact: true}), before);
  await p.shot('ready-group-cycle-summary'); await p.click(b(page, '关闭详情'));
  const after = await openProcess(p, page, data.part); valid(after, 7.25); assert(after.data.workflow.ready);
  assert.deepEqual(after.data.fields, before.data.fields);
  for (const group of before.data.external_groups) {
    const current = after.data.external_groups.find(row => row.ref === group.ref);
    assert.deepEqual({...current, total_days: group.total_days}, group);
  }
  const sql = p.oracle().tables;
  for (const row of sql.PartOperations.filter(row => row.part_no === data.part && row.source === 'external')) assert.equal(row.ext_days, null);
  p.report.states.push({state: p.state, part: data.part, before, after, payload, sqlite_members_null: true});
  await p.click(b(page, '关闭详情'));
}
async function damaged(p, page, data, kind) {
  await processPage(p, page); const raw = await openProcess(p, page, data.damaged[kind]), row = operation(raw, 20);
  const codes = row.issues.map(item => item.code);
  if (kind === 'operation') { assert.equal(row.external_days_source, 'operation'); assert.equal(row.external_days, 3.25); }
  else {
    assert.equal(row.external_days_source, null); assert(codes.includes(kind === 'member_value' ? 'value_invalid' : 'value_missing'));
    if (kind === 'cross_part') assert(codes.includes('external_group_part_mismatch'));
    if (['total', 'member'].includes(kind)) assert(codes.includes('external_group_invalid'));
  }
  assert.equal(operation(raw, 40).external_days_source, 'group');
  await p.click(page.getByRole('tab', {name: /^3 /}));
  const hours = page.locator('[data-process-hours-editor]:visible'); await hours.waitFor();
  const member = hours.getByLabel('工序 20 外协周期', {exact: true}).locator('xpath=ancestor::tr'); await member.waitFor();
  assert.equal(await member.count(), 1); assert.equal(await member.locator('[data-process-cycle-group]').count(), 0);
  const text = await member.innerText();
  for (const issue of row.issues) assert(text.includes(issue.message), issue.message);
  assert.equal(await hours.getByLabel('工序 20 外协周期', {exact: true}).inputValue(), kind === 'operation' ? '3.25' : '');
  assert.equal(await hours.getByLabel('外协组 40 至 40 总周期', {exact: true}).inputValue(), '9.5');
  await p.shot('real-' + kind + '-not-hidden'); await p.click(b(page, '关闭详情'));
}
async function protocolFailures(p, page, data) {
  await processPage(p, page); const baseline = await openProcess(p, page, data.part); await p.click(b(page, '关闭详情'));
  const url = '**/api/workbench/v1/entities/part/' + baseline.data.ref;
  for (const kind of ['unknown', 'missing', 'mismatched_ref', 'missing_total']) {
    await page.route(url, async route => {
      const response = await route.fetch(), body = await response.json(), row = operation(body, 20);
      if (kind === 'unknown') row.external_days_source = 'supplier';
      if (kind === 'missing') delete row.external_days_source;
      if (kind === 'mismatched_ref') row.external_group_ref = operation(body, 40).external_group_ref;
      if (kind === 'missing_total') body.data.external_groups.find(group => group.ref === row.external_group_ref).total_days = null;
      await route.fulfill({response, json: body});
    });
    await p.click(b(page.locator('[data-process-workspace]'), '查看 ' + data.part));
    const detail = page.locator('.process-detail');
    await detail.getByText('读到的工艺详情不完整或不是这个零件，请刷新后重试。', {exact: true}).waitFor();
    assert.equal(await detail.locator('[data-process-hours-editor]').count(), 0);
    await p.shot('protocol-' + kind + '-rejected'); await page.unroute(url);
    await p.click(b(detail, '刷新详情')); await page.getByRole('tablist', {name: '零件工艺步骤', exact: true}).waitFor();
    await p.click(b(page, '关闭详情'));
  }
}
module.exports = {cycleSave, damaged, protocolFailures};
