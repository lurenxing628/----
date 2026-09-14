'use strict';
const assert = require('node:assert/strict');
const button = (scope, name) => (name === '关闭' ? scope.locator('.modal-f') : scope).getByRole('button', {name, exact: true});
const area = page => page.locator('[data-resource-workspace]');
const dialog = (page, name) => page.getByRole('dialog', {name, exact: true});
const row = (p, code) => p.oracle().tables.Materials.find(r => r.material_id === code);

async function listState(p, page, prefix, number, total) {
  const view = area(page);
  // Shared WorkbenchControls.Pager (2026-09-13) renders one summary sentence: 「共 25 项 · 第 2 / 2 页」.
  const summary = '共 ' + total + ' 项 · 第 ' + number + ' / ' + Math.max(1, Math.ceil(total / 20)) + ' 页';
  await view.locator('.wb-pager .wb-pager-summary').filter({hasText: summary}).waitFor();
  assert.equal((await view.locator('.wb-pager .wb-pager-summary').innerText()).replace(/\s+/g, ' ').trim(), summary);
  await page.waitForFunction(() => document.querySelector('[data-resource-workspace] table')?.getAttribute('aria-busy') === 'false');
  assert.equal(await view.getByRole('searchbox').inputValue(), prefix);
  assert.equal(await view.locator('select[aria-label="状态筛选"]').inputValue(), 'active');
  assert.equal(await view.locator('th[data-column="status"]').getAttribute('aria-sort'), 'descending');
  assert.equal(await view.getByLabel('每页条数', {exact: true}).inputValue(), '20');
  p.report.list_states = (p.report.list_states || []).concat({state: p.state, case: p.currentCase, query: prefix, status: 'active', sort: 'status', direction: 'desc', page: number, size: 20, total});
}

async function configure(p, page, prefix, number = 1, total = 25) {
  const view = area(page);
  await p.type(view.getByRole('searchbox', {name: '搜索编号或名称'}), prefix);
  await p.response('/entities/material', () => p.click(button(view, '搜索')));
  if (await view.locator('select[aria-label="状态筛选"]').inputValue() !== 'active')
    await p.response('/entities/material', () => p.select(view.getByLabel('状态筛选', {exact: true}), '启用'));
  for (let i = 0; await view.locator('th[data-column="status"]').getAttribute('aria-sort') !== 'descending'; i++) {
    assert(i < 2); await p.response('/entities/material', () => p.click(button(view, '状态排序')));
  }
  for (let i = 1; i < number; i++) await p.response('/entities/material', () => p.click(button(view, '下一页')));
  await listState(p, page, prefix, number, total);
}

async function edit(p, page, code) {
  await p.click(button(area(page), code));
  const detail = dialog(page, '物料详情');
  await detail.locator('.wb-resource-remark').waitFor();
  await p.click(button(detail, '编辑'));
  return dialog(page, '编辑物料');
}

async function remarkChange(p, page, data, value, cancel = false) {
  const original = row(p, data.material), d = await edit(p, page, data.material);
  const field = d.getByLabel('备注', {exact: true});
  assert.equal(await field.inputValue(), original.remark || '');
  await p.type(field, value);
  await p.shot(cancel ? 'remark-cancel-draft' : value.trim() ? 'remark-long-chinese-draft' : 'remark-explicit-empty-draft');
  if (cancel) {
    await p.click(button(d, '取消'));
    // Since 2026-09-13 a changed form asks before discarding; the draft must be dropped without any write.
    const guard = page.getByRole('dialog', {name: '离开前确认', exact: true}); await guard.waitFor(); await p.shot('remark-cancel-guard');
    await p.click(guard.getByRole('button', {name: '放弃未保存内容并继续', exact: true}));
    await d.waitFor({state: 'detached'}); assert.deepEqual(row(p, data.material), original);
  } else {
    const receipt = await p.response('/update', () => p.click(button(d, '保存')));
    assert.equal(receipt.result, 'committed');
    await d.getByText('已刷新到最新数据。', {exact: true}).waitFor();
    const request = p.report.network.filter(r => r.event === 'request' && r.url.endsWith('/update')).at(-1);
    assert.deepEqual(JSON.parse(request.post).input, {fields: {remark: value.trim() || null}});
    assert.deepEqual(row(p, data.material), {...original, remark: value.trim() || null});
    await p.shot('remark-saved-original-receipt'); await p.click(button(d, '关闭'));
    await p.click(button(area(page), data.material));
    const detail = dialog(page, '物料详情');
    await detail.locator('.wb-resource-remark dd').waitFor();
    assert.equal(await detail.locator('.wb-resource-remark dd').textContent(), value.trim() || '未填写');
    await p.shot('remark-persisted-detail'); await p.click(button(detail, '关闭'));
  }
  await listState(p, page, data.material_prefix, 2, 25);
  p.step('scroll-into-view', 'material pager after remark action');
  await area(page).locator('.wb-pager').scrollIntoViewIfNeeded();
  await p.shot('remark-return-original-page-two');
}

async function nullOmitted(p, page, data) {
  await configure(p, page, data.empty_material, 1, 1);
  const original = row(p, data.empty_material), d = await edit(p, page, data.empty_material);
  assert.equal(original.remark, null); assert.equal(await d.getByLabel('备注', {exact: true}).inputValue(), '');
  await p.type(d.getByLabel('名称', {exact: false}), 'EL只改名称，NULL备注和规格单位保持原值');
  await p.response('/update', () => p.click(button(d, '保存')));
  await d.getByText('已刷新到最新数据。', {exact: true}).waitFor();
  assert.deepEqual(row(p, data.empty_material), {...original, name: 'EL只改名称，NULL备注和规格单位保持原值'});
  const request = p.report.network.filter(r => r.event === 'request' && r.url.endsWith('/update')).at(-1);
  assert.deepEqual(JSON.parse(request.post).input, {label: 'EL只改名称，NULL备注和规格单位保持原值'});
  await p.shot('null-remark-omitted-not-cleared'); await p.click(button(d, '关闭'));
}

async function deleteLastPage(p, page, data) {
  await configure(p, page, data.delete_prefix, 3, 41);
  const original = row(p, data.delete_target), view = area(page);
  await p.click(view.getByRole('checkbox', {name: '选择 ' + data.delete_target + ' ' + original.name, exact: true}));
  await p.click(button(view, data.delete_target));
  const detail = dialog(page, '物料详情'); await detail.locator('.wb-resource-remark').waitFor();
  await p.click(button(detail, '删除'));
  const d = dialog(page, '删除物料'); await p.shot('last-page-single-selected-row');
  await p.click(d.getByRole('checkbox', {name: '我已核对要删除的资料及其关联关系', exact: true}));
  await p.response('/delete', () => p.click(button(d, '确认删除')));
  await d.getByText('已刷新到最新数据。', {exact: true}).waitFor();
  assert.equal(row(p, data.delete_target), undefined);
  await p.click(button(d, '关闭'));
  await listState(p, page, data.delete_prefix, 2, 40);
  assert.equal(await view.locator('[data-resource-selection-count]').count(), 0);
  p.step('scroll-into-view', 'material pager after last-page delete');
  await view.locator('.wb-pager').scrollIntoViewIfNeeded();
  await p.shot('page-three-shrinks-to-two');
  await p.response('/entities/material', () => p.click(button(view, '刷新列表')));
  await listState(p, page, data.delete_prefix, 2, 40);
  await p.shot('manual-refresh-keeps-page-two');
  await configure(p, page, 'EL-no-match-' + p.state, 1, 0);
  // Shared EmptyState (2026-09-13): a filtered list with no rows shows the 「filtered」 title.
  await view.locator('.wb-empty-filtered .wb-empty-title').waitFor();
  assert.equal(await view.locator('.wb-empty-filtered .wb-empty-title').innerText(), '当前筛选没有匹配项');
}

async function createRemark(p, page, data) {
  await configure(p, page, data.create_code, 1, 0);
  await p.click(button(area(page), '新增物料'));
  const d = dialog(page, '新增物料');
  await p.type(d.locator('input[name="business_code"]'), data.create_code);
  await p.type(d.locator('input[name="label"]'), 'EL新增物料备注迁移闭环');
  await p.type(d.getByLabel('备注', {exact: true}), '新增备注第一行\n新增备注第二行');
  await p.select(d.getByLabel(/^状态/), '启用');
  await p.shot('create-remark-draft');
  await p.response('/create', () => p.click(button(d, '保存')));
  await d.getByText('已刷新到最新数据。', {exact: true}).waitFor();
  assert.equal(row(p, data.create_code).remark, '新增备注第一行\n新增备注第二行');
  await p.click(button(d, '关闭')); await listState(p, page, data.create_code, 1, 1);
}

module.exports = {button, area, dialog, row, listState, configure, remarkChange, nullOmitted, deleteLastPage, createRemark};
