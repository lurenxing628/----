'use strict';
const assert = require('node:assert/strict');
const {processPage, openProcess} = require('./ed_material_process_stages.cjs');
const b = (scope, name) => scope.getByRole('button', {name, exact: true});
async function pagination(p, page, data) {
  await processPage(p, page); await openProcess(p, page, data.scale_part);
  const table = page.getByRole('table', {name: '路线工序明细', exact: true});
  const area = table.locator('xpath=ancestor::div[3]');
  assert.equal(await table.locator('tbody tr').count(), 50);
  await p.select(area.getByLabel('每页条数', {exact: true}), '20 项');
  await p.type(area.getByRole('searchbox'), '复核子集');
  assert.equal(await table.locator('tbody tr').count(), 20);
  const observation = {state: p.state, source_count: 63, filtered_count: 25, page_size: 20,
    visible_rows: await table.locator('tbody tr').count(), pager_count: await area.locator('.wb-pager').count()};
  p.report.filtered_paging = (p.report.filtered_paging || []).concat(observation);
  await p.shot('process-filter-25-of-63-at-page-size-20');
  assert.equal(observation.pager_count, 1, '25 matching operations must retain page 2 when page size is 20');
  await p.click(b(area, '下一页')); assert.equal(await table.locator('tbody tr').count(), 5);
  assert((await table.locator('tbody tr').first().innerText()).includes('复核子集21'));
  await p.shot('process-filter-last-five-reachable');
  await p.click(b(area, '上一页')); assert.equal(await table.locator('tbody tr').count(), 20);
  await p.click(b(page, '关闭详情'));
}
async function noMatches(p, page, data) {
  await processPage(p, page); await openProcess(p, page, data.scale_part);
  for (const [stage, selector] of [[2, '[data-process-source-editor]'], [3, '[data-process-hours-editor]']]) {
    await p.click(page.getByRole('tab', {name: new RegExp('^' + stage + ' ')}));
    const area = page.locator(selector + ':visible');
    await p.type(area.getByRole('searchbox'), 'ED没有匹配的工序编号');
    await p.shot('process-stage-' + stage + '-empty-search');
    if (stage === 2) {
      const table = area.getByRole('table', {name: '归属明细', exact: true});
      assert((await table.innerText()).includes('没有匹配的工序。'), 'Source stage needs an explicit empty-result row');
      await p.type(area.getByRole('searchbox'), ''); assert.equal(await table.locator('tbody tr').count(), 50);
    } else {
      await area.getByText('当前页没有自制工序。', {exact: true}).waitFor();
      await area.getByText('当前页没有外协工序。', {exact: true}).waitFor();
      await p.type(area.getByRole('searchbox'), '');
      const rows = await Promise.all(['自制工时明细', '外协周期明细'].map(name => area.getByRole('table', {name, exact: true})
        .locator('tbody tr').evaluateAll(items => items.filter(row => row.querySelector('td b')).length)));
      assert.equal(rows.reduce((total, value) => total + value, 0), 50);
    }
  }
  await p.click(b(page, '关闭详情'));
}
module.exports = {pagination, noMatches};
