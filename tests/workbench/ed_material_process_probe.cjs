'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require('playwright'), {Probe} = require('./migrated_process_batch_support.cjs');
const {materialWrites} = require('./ed_material_process_material.cjs');
const {processStages, protectedAndEmpty} = require('./ed_material_process_stages.cjs');
const {detailStates} = require('./ed_material_process_states.cjs'), {geometry} = require('./ed_material_process_visual.cjs');
const {pagination, noMatches} = require('./ed_material_process_filters.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), p = new Probe(ready);
p.report.mutation_policy = {business_rows: 'Only the current-state ED material and ED process rows; material name/spec/stock, seq10 unit hours, group20 total days',
  protected: 'All other business rows, schema, batches, plans, reports, calibration lock/adoption and original receipts unchanged',
  receipts: 'Append only for real UI POSTs; original request_key and receipt_ref must match SQLite',
  metadata: 'Read may append real identities; existing identities only revise for the current edited owner',
  coverage_boundary: 'Does not claim original page retention: all four combinations currently reset page 2 to page 1'};
const baseShot = p.shot.bind(p);
p.shot = async function(name) {
  const file = await baseShot(name), measured = await geometry(this.page);
  this.report.screenshots[this.report.screenshots.length - 1].layout = measured;
  assert.deepEqual(measured.clipping, []); assert.deepEqual(measured.overlaps, []);
  assert.deepEqual((measured.controlContrast || []).filter(row => !row.passes), []);
  this.save(); return file;
};
p.save = function () { this.report.summary = {cases: this.report.cases.length, failed: this.report.cases.filter(c => !c.passed).length,
  steps: this.report.steps.length, screenshots: this.report.screenshots.length}; this.json('ed-report.json', this.report); };
p.validate = function (changes, policy) {
  const owned = ready.expected.ed.states[this.state];
  for (const c of changes) {
    if (c.table === 'WorkbenchEntityRefs') {
      assert(c.after);
      if (c.before) {
        assert.equal(policy, 'write'); assert(c.columns.every(k => ['revision', 'active'].includes(k)));
        const row = c.after, op = this.lastAfter.tables.PartOperations.find(op => String(op.id) === row.entity_key), group = this.lastAfter.tables.ExternalGroups.find(g => g.group_id === row.entity_key);
        assert(row.kind === 'material' && row.entity_key === owned.material || row.kind === 'part' && row.entity_key === owned.part ||
          row.kind === 'template_operation' && op && op.part_no === owned.part || row.kind === 'template_external_group' && group && group.part_no === owned.part);
      }
      continue;
    }
    if (policy === 'read') assert.fail('Read/cancel mutated ' + c.table);
    if (c.table === 'WorkbenchCommandReceipts') { assert(!c.before && c.after); continue; }
    if (['WorkbenchProcessWorkflow', 'WorkbenchProcessOperationConfirmations'].includes(c.table)) {
      const identity = this.lastAfter.tables.WorkbenchEntityRefs.find(row => row.ref === (c.after || c.before).part_ref);
      assert(identity && identity.entity_key === owned.part); continue;
    }
    const row = c.after || c.before;
    if (c.table === 'Materials') { assert(c.before && c.after && row.material_id === owned.material); assert(c.columns.every(k => ['name', 'spec', 'stock_qty'].includes(k))); continue; }
    if (c.table === 'PartOperations') { assert(c.before && c.after && row.part_no === owned.part && row.seq === 10); assert.deepEqual(c.columns, ['unit_hours']); continue; }
    if (c.table === 'ExternalGroups') { assert(c.before && c.after && row.part_no === owned.part && row.start_seq === 20); assert.deepEqual(c.columns, ['total_days']); continue; }
    assert.fail('Out-of-scope mutation: ' + JSON.stringify(c));
  }
};
const b = (scope, name) => scope.getByRole('button', {name, exact: true});
async function main() {
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
  try {
    for (const state of (process.env.ED_STATES || '1920-light,1920-dark,1392-light,1392-dark').split(',')) {
      const [size, theme] = state.split('-'), width = Number(size), data = ready.expected.ed.states[state];
      const context = await browser.newContext({viewport: {width, height: width === 1920 ? 1080 : 924}, timezoneId: 'Asia/Shanghai'});
      const page = await context.newPage(); p.attach(page, state);
      await page.goto(ready.url + '/workbench'); await page.locator('.sidebar').waitFor();
      await p.click(page.locator('.sidebar').getByText('基础资料', {exact: true}));
      await page.locator('[data-resource-workspace] .hb-tile').first().waitFor();
      if (theme === 'dark') await p.click(b(page, '切换深色'));
      if (process.env.ED_SCOPE === 'filters') {
        await p.run('process-filter-paging', 'read', () => pagination(p, page, data));
        await p.run('process-filter-empty', 'read', () => noMatches(p, page, data));
        await context.close(); continue;
      }
      const area = page.locator('[data-resource-workspace]');
      await p.type(area.getByRole('searchbox', {name: '搜索编号或名称'}), data.material_prefix);
      await p.response('/entities/material', () => p.click(b(area, '搜索')));
      await p.click(area.getByLabel('状态筛选', {exact: true})); await page.getByRole('listbox').waitFor(); await p.shot('material-list-status-dropdown');
      await p.response('/entities/material', () => p.click(page.getByRole('listbox').getByRole('option', {name: '启用', exact: true})));
      await p.click(b(area, '下一页'));
      await b(area, data.material).waitFor();
      await p.run('material-detail-baseline', 'read', async () => {
        await p.click(b(area, data.material));
        const d = page.getByRole('dialog', {name: '物料详情', exact: true});
        await d.locator('.wb-resource-stock').waitFor();
        assert.equal(await d.locator('.wb-resource-stock').innerText(), '0\n千克');
        await p.shot('material-detail');
        await p.click(b(d, '编辑'));
        const editor = page.getByRole('dialog', {name: '编辑物料', exact: true});
        p.report.material_fields = await editor.locator('input,select,textarea').evaluateAll(nodes => nodes.map(n => ({name: n.name, type: n.type, value: n.value})));
        await p.shot('material-edit');
        await p.click(b(editor, '取消'));
      });
      await p.run('material-edit-stock-recovery', 'write', () => materialWrites(p, page, data));
      await p.run('process-three-stages', 'write', () => processStages(p, page, data));
      await p.run('process-calibration-lock-empty', 'read', () => protectedAndEmpty(p, page));
      await p.run('detail-cold-empty-error-retry', 'read', () => detailStates(p, page, data));
      await p.run('process-filter-paging', 'read', () => pagination(p, page, data));
      await p.run('process-filter-empty', 'read', () => noMatches(p, page, data));
      await context.close();
    }
  } catch (error) {
    if (p.page && !p.page.isClosed()) { p.json('ed-fatal-dom.json', {text: await p.page.locator('body').innerText()}); await p.shot('fatal'); }
    throw error;
  } finally { await browser.close(); p.report.browser_closed = true; p.save(); }
  assert.equal(p.report.summary.failed, 0); assert.deepEqual(p.report.pageerrors, []); assert.deepEqual(p.report.external, []);
}
main().catch(error => {p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1;});
