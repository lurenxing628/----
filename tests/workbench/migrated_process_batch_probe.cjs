'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require('playwright'), {Probe} = require('./migrated_process_batch_support.cjs');
const {unknownWorkflow} = require('./migrated_process_batch_unknown.cjs');
const {recoverReceipt} = require('./migrated_process_batch_recovery.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), p = new Probe(ready), root = ready.root;
let page, state;
const button = (scope, name) => name === '关闭' ? scope.locator('.modal-f').getByRole('button', {name, exact: true}) : scope.getByRole('button', {name, exact: true});
const dialog = name => page.getByRole('dialog', {name, exact: true});
const processArea = () => page.locator('[data-process-workspace]');
const batchArea = () => page.locator('[data-batch-workspace]');
async function processPage() {
  await page.goto(ready.resource_url); await page.locator('.hb-tile').first().waitFor();
  await p.response('/entities/part', () => p.click(page.locator('.hb-tile').filter({hasText: /^工艺/})));
  await processArea().locator('tbody tr[data-process-ref]').first().waitFor();
}
async function batchPage() {
  await p.response('/entities/batch', () => p.click(page.locator('.sidebar').getByText('批次管理', {exact: true})));
  await batchArea().waitFor();
}
async function searchProcess(code) {
  await p.type(processArea().getByRole('searchbox'), code);
  return p.response('/entities/part', () => processArea().getByRole('searchbox').press('Enter'));
}
async function openProcess(code) {
  await searchProcess(code); const open = button(processArea(), '查看 ' + code);
  const ref = await open.locator('xpath=ancestor::tr').getAttribute('data-process-ref');
  const data = await p.response('/entities/part/' + ref, () => p.click(open));
  await page.getByRole('tablist', {name: '零件工艺步骤', exact: true}).waitFor(); return data;
}
async function closeProcess() { await p.click(button(page, '关闭详情')); }
async function saved(action, locator) {
  const endpoint = ['sync_confirm', 'bulk_confirm', 'import_confirm'].includes(action) ? action.replace('_', '-') : action;
  const receipt = await p.response('/' + endpoint, () => p.click(locator));
  assert(['committed', 'unchanged'].includes(receipt.result)); assert(receipt.receipt_ref);
  const rows = p.oracle().tables.WorkbenchCommandReceipts;
  const row = rows.find(row => row.receipt_ref === receipt.receipt_ref);
  assert(row, 'Actual original request receipt exists in SQLite');
  const request = p.report.network.filter(r => r.event === 'request' && r.post).map(r => JSON.parse(r.post)).find(body => body.request_key === row.request_key);
  assert(request, 'Receipt matches an actual UI request_key, not a replacement command');
  return receipt;
}
async function processReads() {
  let result = await searchProcess('PROC-%_'); assert.equal(result.data.page.total, 1);
  assert.equal(result.data.entities[0].business_code, 'PROC-%_'); await searchProcess('');
  for (const title of ['图号', '零件名称', '工序数量', '进度']) {
    for (const direction of ['ascending', 'descending', 'none']) {
      await p.response('/entities/part', () => p.click(button(processArea(), title + '排序')));
      assert.equal(await button(processArea(), title + '排序').locator('xpath=ancestor::th').getAttribute('aria-sort'), direction);
    }
    await p.click(button(processArea(), '筛选' + title));
    const filter = dialog('筛选 · ' + title); await filter.getByRole('checkbox', {name: '全选', exact: true}).waitFor();
    await p.shot('facet-' + title);
    await p.response('/entities/part', () => p.click(filter.getByRole('checkbox', {name: '全选', exact: true})));
    await page.keyboard.press('Escape');
    assert.equal(await processArea().locator('tbody tr[data-process-ref]').count(), 0);
    await p.click(button(processArea(), '筛选' + title));
    const restored = await p.response('/entities/part', () => p.click(button(dialog('筛选 · ' + title), '清除')));
    await p.click(button(processArea(), '筛选' + title));
    const values = dialog('筛选 · ' + title), option = values.locator('[data-facet-key]').first(); await option.waitFor();
    const excludedCount = Number(await option.locator('span').last().innerText());
    const filtered = await p.response('/entities/part', () => p.click(option.getByRole('checkbox')));
    assert.equal(filtered.data.page.total, restored.data.page.total - excludedCount, 'A real individual facet value changes matching rows');
    await page.keyboard.press('Escape'); await p.click(button(processArea(), '筛选' + title));
    await p.response('/entities/part', () => p.click(button(dialog('筛选 · ' + title), '清除')));
  }
  await p.response('/entities/part', () => p.click(button(processArea(), '工序数量排序')));
  await p.response('/entities/part', () => p.click(button(processArea(), '图号排序')));
  assert.equal(await processArea().locator('th[aria-sort="ascending"]').count(), 2);
  for (const title of ['工序数量', '图号']) for (let i = 0; i < 2; i++) await p.response('/entities/part', () => p.click(button(processArea(), title + '排序')));
  const resize = processArea().getByRole('separator', {name: '调整图号列宽', exact: true});
  const before = Number(await resize.getAttribute('aria-valuenow')); await resize.focus(); await resize.press('ArrowRight');
  await page.waitForFunction(before => Number(document.querySelector('[aria-label="调整图号列宽"]').getAttribute('aria-valuenow')) > before, before);
  await resize.press('ArrowLeft');
  await openProcess('PROC-001'); assert((await page.locator('.process-detail').innerText()).includes('保留合并规则'));
  await p.shot('legacy-process-detail'); await closeProcess();
}
async function processExports(prefix = 'CROSSPAGE-', total = 63, operationCount = 0) {
  await searchProcess(prefix);
  await p.click(processArea().getByRole('checkbox', {name: '选择 ' + prefix + '001', exact: true}));
  await p.response('/entities/part', () => p.click(button(processArea(), '下一页')));
  await p.click(processArea().getByRole('checkbox', {name: '选择 ' + prefix + '021', exact: true}));
  assert((await processArea().innerText()).includes('含非当前页记录'));
  await p.response('/entities/part', () => p.click(button(processArea(), '刷新工艺列表')));
  assert.equal(await processArea().locator('[data-process-selection-count]').innerText(), '2');
  for (const kind of ['工艺路线', '工时定额']) for (const format of ['csv', 'xlsx']) for (const selected of [false, true]) {
    await p.click(button(processArea(), '导出' + kind)); const d = dialog('导出' + kind);
    await p.click(button(d, format === 'csv' ? 'CSV (.csv)' : 'Excel (.xlsx)'));
    await p.click(d.getByRole('radio', {name: selected ? '已选零件（含其他页）' : '当前筛选结果（全部页）', exact: true}));
    const preview = await p.response('/export-preview', () => p.click(button(d, '开始预检')));
    assert.equal(preview.data.part_count, selected ? 2 : total);
    const downloaded = await p.download('process-' + prefix + kind + '-' + (selected ? 'selected' : 'filtered'), () => p.click(button(d, '下载文件')));
    const rows = Object.values(downloaded.sheets)[0];
    assert.equal(rows.length - 1, preview.data.row_count, 'Downloaded physical row count matches full preview');
    assert.equal(rows.length - 1, (selected ? 2 : total) * (kind === '工艺路线' ? 1 : operationCount));
    if (kind === '工艺路线' || operationCount) assert(rows.some(r => String(r[0]).includes(prefix + (selected ? '021' : String(total).padStart(3, '0')))));
    await p.click(button(d, '完成'));
  }
  await p.click(button(processArea(), '清除所有选择')); await searchProcess('');
}
async function createProcess() {
  await p.click(button(processArea(), '新增零件')); const d = dialog('新增零件');
  await p.type(d.getByLabel('图号', {exact: true}), 'AN-P-' + state);
  await p.type(d.getByLabel('零件名称', {exact: true}), '真实录入零件 ' + state);
  await p.type(d.getByLabel('路线文字（选填）', {exact: true}), '10车削20检验');
  await p.type(d.getByLabel('备注（选填）', {exact: true}), 'AN original note');
  await p.shot('create-process'); await saved('create', button(d, '保存零件'));
  await p.click(button(d, '完成'));
}
async function processStages(code, legacy = false) {
  const detail = await openProcess(code);
  await p.click(page.getByRole('tab', {name: /^1 /})); await p.click(button(page, '录入路线'));
  const entry = page.getByRole('dialog', {name: /^录入工艺路线 · /});
  await p.type(entry.getByRole('textbox', {name: '路线文字', exact: true}), legacy ? '10车削20热处理30检验' : '10车削20检验');
  const preview = await p.response('/route-preview', () => p.click(button(entry, '预检路线')));
  if (legacy) assert.equal(preview.data.affected_groups.length, 0);
  await p.shot('route-preview-' + (legacy ? 'legacy' : 'new')); await saved('route_confirm', button(entry, '确认保存路线'));
  const source = page.locator('[data-process-source-editor]:visible'); await source.waitFor();
  await p.click(button(source, '选择工序 10 工种'));
  const picker = dialog('选择自制工种 · 工序 10'); await p.type(picker.getByRole('searchbox'), '车削');
  await p.response('/entities/op_type', () => p.click(button(picker, '搜索'))); await p.click(button(picker, '选用 车削'));
  await p.click(source.getByRole('checkbox', {name: '确认本页已核对工序', exact: true}));
  const checked = await p.response('/stage-preview', () => p.click(button(source, '检查归属')));
  if (legacy) assert.equal(checked.data.affected_groups.length, 0);
  await p.shot('source-confirm-' + (legacy ? 'legacy' : 'new')); await saved('source_confirm', button(source, '完成归属 · 解锁工时'));
  const hours = page.locator('[data-process-hours-editor]:visible'); await hours.waitFor();
  if (!legacy) {
    await p.type(hours.getByLabel('工序 10 换型工时', {exact: true}), '0');
    await p.type(hours.getByLabel('工序 20 换型工时', {exact: true}), '0');
    await p.type(hours.getByLabel('工序 20 单件工时', {exact: true}), '1.25');
  }
  await p.type(hours.getByLabel('工序 10 单件工时', {exact: true}), '');
  await p.click(hours.getByRole('checkbox', {name: '确认本页已核对工时', exact: true}));
  const beforeBlank = p.oracle(); await p.click(button(hours, '保存工时'));
  await hours.getByText(/空值不能按 0 保存/).waitFor(); assert.deepEqual(p.diff(beforeBlank, p.oracle()), []);
  await p.shot('hours-blank-rejected');
  await p.type(hours.getByLabel('工序 10 单件工时', {exact: true}), legacy ? '0.25' : '0');
  await p.click(hours.getByRole('checkbox', {name: '确认本页已核对工时', exact: true}));
  const beforeZero = p.oracle(); await p.click(button(hours, '保存工时'));
  await hours.getByText('单件工时为 0，需要明确勾选复核。', {exact: true}).waitFor(); assert.deepEqual(p.diff(beforeZero, p.oracle()), []);
  await p.click(hours.getByRole('checkbox', {name: '已复核单件工时为0', exact: true}));
  await saved('hours_confirm', button(hours, '保存工时'));
  await page.getByText('三阶段已确认 · 已就绪', {exact: true}).waitFor(); await p.shot('ready-' + (legacy ? 'legacy' : 'new'));
  await closeProcess(); const fresh = await openProcess(code); assert(fresh.data.workflow.ready);
  if (legacy) { assert.deepEqual(fresh.data.external_groups, detail.data.external_groups); assert.equal(fresh.data.operations[0].unit_hours, .25); }
  await closeProcess();
}
async function importProcess(kind, file, {cancel = false, rejected = false} = {}) {
  const label = kind === 'route' ? '工艺路线' : '工时定额'; await p.click(button(processArea(), '导入' + label)); const d = dialog('导入' + label);
  await p.click(button(d, file.endsWith('.csv') ? 'CSV (.csv)' : 'Excel (.xlsx)'));
  p.step('setInputFiles', 'input[type=file]', file); await d.locator('input[type=file]').setInputFiles(path.join(root, 'uploads', file));
  const preview = await p.response('/process-files/' + kind + '/preview', () => p.click(button(d, '开始预检'))); await p.shot('import-' + kind + (cancel ? '-cancel' : rejected ? '-rejected' : '-preview'));
  if (cancel || rejected) {
    if (rejected) assert(await d.getByRole('button', {name: /^确认导入/}).isDisabled());
    await p.click(button(d, '取消')); await p.click(button(dialog('放弃本次文件导入？'), '放弃导入并关闭')); return preview;
  }
  for (const label of [/已复核单件工时为 0 的记录/, /已核对全部修改前后内容/]) { const check = d.getByRole('checkbox', {name: label}); if (await check.count()) await p.click(check); }
  const receipt = await saved('confirm', button(d, '确认导入'));
  await d.getByText(/已取得原文件请求的完成回执/).waitFor(); await p.shot('import-' + kind + '-receipt');
  await p.click(button(d, '完成')); return receipt;
}
async function searchBatch(code) { await p.type(batchArea().getByRole('searchbox'), code); return p.response('/entities/batch', () => batchArea().getByRole('searchbox').press('Enter')); }
async function openBatch(code) {
  await searchBatch(code); await p.click(button(batchArea(), code)); await page.locator('[data-batch-detail]').waitFor();
}
async function batchCreate() {
  await p.click(button(batchArea(), '新增批次')); const d = dialog('新增批次');
  await p.type(d.getByLabel('批次号', {exact: true}), 'AN-B-' + state + '-001');
  await p.select(d.getByLabel('图号', {exact: true}), 'PROC-001 · 轴套');
  await p.type(d.getByLabel('数量', {exact: true}), '7');
  const due = d.getByLabel('交期', {exact: true}); await due.focus(); await due.press('F4');
  const calendar = dialog('选择交期'); await p.click(button(calendar, '下个月'));
  await p.click(calendar.locator('[data-date="2026-10-20"]')); assert.equal(await due.inputValue(), '2026-10-20');
  await p.select(d.getByLabel('优先级', {exact: true}), '急件');
  await p.type(d.getByLabel('备注', {exact: true}), 'AN batch original');
  await p.shot('batch-create-date-dropdown'); await saved('create', button(d, '创建批次')); await p.click(button(d, '关闭'));
}
async function batchEditSync() {
  await openBatch('AN-B-' + state + '-001'); await p.click(button(batchArea(), '编辑基础信息')); let d = dialog('编辑批次基础信息');
  const beforeNoop = p.oracle(); await p.click(button(d, '保存基础信息')); await d.getByText('没有需要保存的变更。', {exact: true}).waitFor(); assert.deepEqual(p.diff(beforeNoop, p.oracle()), []);
  await p.type(d.getByLabel('数量', {exact: true}), '9'); await saved('update', button(d, '保存基础信息')); await p.click(button(d, '关闭'));
  await p.response('/sync-preview', () => p.click(button(batchArea(), '按最新工艺模板刷新本批次工序')));
  d = dialog('确认刷新批次工序'); await p.shot('batch-sync-preview'); await saved('sync_confirm', button(d, '确认变更')); await p.click(button(d, '关闭'));
  const first = page.getByRole('table', {name: '批次工序', exact: true}).locator('tbody tr').first(); await p.click(button(first, '补充资料'));
  d = page.getByRole('dialog', {name: /^工序 10 · /}); await p.type(d.getByLabel('单件工时（小时）', {exact: true}), '1.375');
  await saved('operation_update', button(d, '保存工序')); await p.click(button(d, '关闭'));
  await page.getByText('换型 0.5 / 单件 1.375 小时', {exact: true}).waitFor(); await p.shot('batch-operation-edited');
  await p.click(button(batchArea(), '返回列表'));
}
async function batchImport(file, mode, cancel = false) {
  await p.click(button(batchArea(), '批量导入')); const d = dialog('批量维护批次');
  if (mode !== 'overwrite') await p.select(d.getByLabel('导入模式', {exact: true}), mode === 'append' ? '只新增没有的批次（已有的跳过）' : '先清空全部批次，再按表格重导');
  p.step('setInputFiles', 'input[type=file]', file); await d.locator('input[type=file]').setInputFiles(path.join(root, 'uploads', file + '.xlsx'));
  const preview = await p.response('/import-preview', () => p.click(button(d, '预览导入'))); await p.shot('batch-file-' + mode + (cancel ? '-cancel' : ''));
  if (mode === 'replace') { assert.equal(preview.data.can_confirm, false); assert(preview.data.deleted.some(r => r.before.business_code === 'PROC-B')); assert(await button(d, '确认导入').isDisabled()); }
  else if (!cancel) { assert(preview.data.can_confirm); await saved('import_confirm', button(d, '确认导入')); }
  await p.click(button(d, cancel || mode === 'replace' ? '取消' : '关闭')); return preview;
}
async function batchMulti() {
  await searchBatch('AN-MULTI-'); await p.click(batchArea().getByRole('checkbox', {name: '选择 AN-MULTI-001', exact: true}));
  await p.response('/entities/batch', () => p.click(button(batchArea(), '下一页')));
  await p.click(batchArea().getByRole('checkbox', {name: '选择 AN-MULTI-021', exact: true}));
  assert((await batchArea().innerText()).includes('含非当前页记录'));
  for (const selected of [true, false]) {
    await p.click(button(batchArea(), '批量导出')); const d = dialog('导出批次清单');
    if (!selected) await p.click(d.getByRole('radio', {name: '导出当前筛选全部批次', exact: true}));
    const file = await p.download('batch-' + (selected ? 'selected' : 'filtered'), () => p.click(button(d, '下载批次清单')));
    const rows = Object.values(file.sheets)[0]; assert.equal(rows.length - 1, selected ? 2 : 43);
    assert(rows.some(r => r[0] === (selected ? 'AN-MULTI-021' : 'AN-MULTI-043'))); await p.click(button(d, '取消'));
  }
  await p.response('/entities/batch', () => p.click(button(batchArea(), '刷新批次列表'))); assert((await batchArea().innerText()).includes('已选 2 个批次'));
  const beforeCancel = p.oracle(); await p.response('/bulk-preview', () => p.click(button(batchArea(), '删除所选')));
  await p.shot('batch-delete-preview-hidden'); await p.click(button(dialog('确认批量删除'), '取消')); p.validate(p.diff(beforeCancel, p.oracle()), 'read');
  await p.click(button(batchArea(), '清除选择')); await searchBatch('AN-B-' + state);
  await p.click(batchArea().getByRole('checkbox', {name: '选择 AN-B-' + state + '-001', exact: true}));
  const preview = await p.response('/bulk-preview', () => p.click(button(batchArea(), '复制所选')));
  await saved('bulk_confirm', button(dialog('确认批量复制'), '确认变更')); await p.click(button(dialog('确认批量复制'), '关闭'));
  assert(preview.data.rows[0].after.business_code); const copy = preview.data.rows[0].after.business_code;
  await p.click(button(batchArea(), '清除选择')); await searchBatch(copy);
  await p.click(batchArea().getByRole('checkbox', {name: '选择 ' + copy, exact: true}));
  await p.response('/bulk-preview', () => p.click(button(batchArea(), '删除所选')));
  await saved('bulk_confirm', button(dialog('确认批量删除'), '确认变更')); await p.click(button(dialog('确认批量删除'), '关闭'));
  await page.reload(); const fresh = await searchBatch('AN-MULTI-'); assert.equal(fresh.data.page.total, 43);
  assert.equal(await batchArea().getByRole('table', {name: '批次列表', exact: true}).locator('tbody tr').count(), 20);
}
async function main() {
  let browser;
  try {
    browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true}); p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
    const states = (process.env.AN_STATES || '1920-light,1920-dark,1392-light,1392-dark').split(',');
    for (state of states) {
      const width = Number(state.split('-')[0]), theme = state.split('-')[1];
      const context = await browser.newContext({viewport: {width, height: width === 1920 ? 1080 : 924}, timezoneId: 'Asia/Shanghai'});
      page = await context.newPage(); p.attach(page, state); await processPage();
      p.recover = processPage;
      if (theme === 'dark') await p.click(button(page, '深色：关'));
      const scope = process.env.AN_SCOPE || 'all';
      if (scope === 'unknown') {
        await p.run('unknown-op-type-create-bind', 'write', () => unknownWorkflow({p, page, processArea, openProcess, closeProcess, saved}));
        await context.close(); p.save(); continue;
      }
      if (scope === 'recovery') {
        await p.run('original-route-receipt-recovery', 'write', () => recoverReceipt({p, page, processArea, kind: 'route', file: 'recovery-route.csv'}));
        await context.close(); p.save(); continue;
      }
      if (scope !== 'writes') {
        await p.run('process-read-table', 'read', processReads); await processPage();
        await p.run('process-crosspage-downloads', 'read', processExports); await processPage();
      }
      if (scope !== 'reads') {
        await p.run('create-process', 'write', createProcess);
        await p.run('stages-input-confirm', 'write', () => processStages('AN-P-' + state)); await processPage();
        if (state === '1920-light') { await p.run('legacy-groups-hidden-preserved', 'write', () => processStages('PROC-001', true)); await processPage(); }
        if (state === '1920-light') { await p.run('unknown-op-type-create-bind', 'write', () => unknownWorkflow({p, page, processArea, openProcess, closeProcess, saved})); await processPage(); }
        await p.run('route-import-cancel', 'read', () => importProcess('route', 'route-' + state + '.csv', {cancel: true}));
        await p.run('route-import-confirm', 'write', () => importProcess('route', 'route-' + state + '.csv'));
        await p.run('nonempty-hours-crosspage-downloads', 'read', () => processExports('AN-FILE-' + state + '-', 23, 2));
        await p.run('hours-import-cancel', 'read', () => importProcess('hours', 'hours-' + state + '.xlsx', {cancel: true}));
        await p.run('hours-import-confirm', 'write', () => importProcess('hours', 'hours-' + state + '.xlsx'));
        await p.run('hours-import-noop-receipt', 'noop', async () => {
          const receipt = await importProcess('hours', 'hours-' + state + '.xlsx'); assert.equal(receipt.result, 'unchanged');
          const op = p.oracle().tables.PartOperations.find(r => r.part_no === 'AN-P-' + state && r.seq === 10);
          assert.equal(op.unit_hours, .375); assert.equal(op.setup_hours, 0, 'Blank setup cell did not overwrite an existing zero');
        });
        await p.run('hours-import-negative', 'read', () => importProcess('hours', 'bad-hours-' + state + '.xlsx', {rejected: true}));
        if (state === '1920-light') {
          await p.run('original-route-receipt-recovery', 'write', () => recoverReceipt({p, page, processArea, kind: 'route', file: 'recovery-route.csv'}));
          await p.run('original-hours-receipt-recovery', 'noop', () => recoverReceipt({p, page, processArea, kind: 'hours', file: 'hours-' + state + '.xlsx'}));
        }
        await batchPage(); p.recover = async () => { await processPage(); await batchPage(); };
        await p.run('batch-create-date-dropdown', 'write', batchCreate);
        await p.run('batch-base-sync-operation', 'write', batchEditSync);
        if (state === '1920-light') {
          await p.run('batch-overwrite-cancel', 'read', () => batchImport('batch-overwrite', 'overwrite', true));
          await p.run('batch-overwrite-confirm', 'write', () => batchImport('batch-overwrite', 'overwrite'));
          await p.run('batch-append-confirm', 'write', () => batchImport('batch-append', 'append'));
        }
        await p.run('batch-replace-protected', 'read', () => batchImport('batch-replace', 'replace'));
        await p.run('batch-crosspage-copy-delete-persist', 'write', batchMulti);
      }
      await context.close(); p.save();
    }
  } finally { if (browser) { await browser.close(); p.report.browser_closed = true; } p.save(); }
  assert.equal(p.report.summary.failed, 0); assert.deepEqual(p.report.pageerrors, []); assert.deepEqual(p.report.external, []);
  assert.deepEqual(p.report.console.filter(r => !r.intentional_network_fault), []);
  assert.deepEqual(p.report.http_errors, []);
}
main().catch(error => { p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1; });
