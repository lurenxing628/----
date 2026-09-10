'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs');
const {chromium} = require('playwright'), {Probe} = require('./migrated_process_batch_support.cjs');
const {geometry} = require('./ed_material_process_visual.cjs');
const {materialWrites} = require('./ed_material_process_material.cjs');
const A = require('./el_material_actions.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2]));

class ELProbe extends Probe {
  save() {
    this.report.summary = {cases: this.report.cases.length, failed: this.report.cases.filter(c => !c.passed).length,
      steps: this.report.steps.length, screenshots: this.report.screenshots.length};
    this.json('el-report.json', this.report);
  }
  async shot(name) {
    const file = await super.shot(name), layout = await geometry(this.page);
    this.report.screenshots.at(-1).layout = layout;
    assert.deepEqual(layout.clipping, []); assert.deepEqual(layout.overlaps, []);
    assert.deepEqual((layout.controlContrast || []).filter(c => !c.passes), []);
    this.save(); return file;
  }
  validate(changes, policy) {
    const owned = ready.expected.ed.states[this.state];
    for (const c of changes) {
      if (c.table === 'WorkbenchEntityRefs') {
        assert(c.after);
        if (c.before) {
          assert.equal(c.after.kind, 'material'); assert.equal(policy, 'write');
          assert([owned.material, owned.empty_material, owned.delete_target, owned.create_code].includes(c.after.entity_key));
          assert(c.columns.every(k => ['revision', 'active'].includes(k)));
        }
        continue;
      }
      assert.equal(policy, 'write', 'Read/cancel mutated ' + c.table);
      if (c.table === 'WorkbenchCommandReceipts') { assert(!c.before && c.after); continue; }
      assert.equal(c.table, 'Materials', 'Unrelated table changed');
      const r = c.after || c.before;
      if (r.material_id === owned.delete_target) { assert(c.before && !c.after); continue; }
      if (r.material_id === owned.create_code) { assert(!c.before && c.after); continue; }
      assert(c.before && c.after);
      const allowed = r.material_id === owned.material ? ['name', 'spec', 'stock_qty', 'remark'] : r.material_id === owned.empty_material ? ['name'] : [];
      assert(c.columns.every(k => allowed.includes(k)), JSON.stringify(c));
    }
  }
}
const p = new ELProbe(ready);
p.report.mutation_policy = {business: 'Only each EL state target material name/spec/stock/remark, NULL material name, one explicit last-page deletion and one explicit create',
  preserved: 'All 77 tables checked, every other row and field exact, schema unchanged, existing receipts append-only',
  interactions: 'Real /workbench with type/click; no injected API write or mocked response; CDP only drops actual responses for original-key recovery',
  boundary: 'Pending reload verifies original key and receipt; full page reload is not a saved list-preference feature'};

async function main() {
  const initial = p.oracle(); p.json('el-business-before.json', initial);
  assert.equal(Object.keys(initial.tables).length, 77);
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
  try {
    for (const state of (process.env.EL_STATES || '1920-light,1392-dark,1920-dark,1392-light').split(',')) {
      const [size, theme] = state.split('-'), width = Number(size), data = ready.expected.ed.states[state];
      const context = await browser.newContext({viewport: {width, height: width === 1920 ? 1080 : 924}, timezoneId: 'Asia/Shanghai'});
      const page = await context.newPage(); p.attach(page, state);
      await page.goto(ready.url + '/workbench'); await page.locator('.sidebar').waitFor();
      await p.click(page.locator('.sidebar').getByText('基础资料', {exact: true}));
      await A.area(page).locator('.hb-tile').first().waitFor();
      if (theme === 'dark') await p.click(A.button(page, '深色：关'));
      const stateBefore = p.oracle();
      await A.configure(p, page, data.material_prefix, 2, 25);
      const cases = [
        ['remark-cancel-page-two', 'read', () => A.remarkChange(p, page, data, '取消的中文备注，不得写入', true)],
        ['remark-long-chinese-page-two', 'write', () => A.remarkChange(p, page, data, '长中文物料备注：原编号和库存不能随备注修改。\n' + '检验尺寸、炉批号和保管条件逐项确认；只修改当前物料备注。'.repeat(12))],
        ['edit-stock-original-key-recovery', 'write', async () => {
          await materialWrites(p, page, data);
          const returned = p.report.material_return.at(-1); assert.equal(returned.page_after_save, '2');
          if (state !== '1392-dark') await A.listState(p, page, data.material_prefix, 2, 25);
          else await A.configure(p, page, data.material_prefix, 2, 25);
        }],
        ['remark-clear-page-two', 'write', () => A.remarkChange(p, page, data, '')],
        ['null-remark-omitted', 'write', () => A.nullOmitted(p, page, data)],
        ['delete-page-three-shrink-page-two', 'write', () => A.deleteLastPage(p, page, data)],
        ['create-remark', 'write', () => A.createRemark(p, page, data)],
      ];
      for (const [name, policy, fn] of cases) assert(await p.run(name, policy, fn), 'Case failed: ' + name);
      const stateAfter = p.oracle(); p.lastAfter = stateAfter; p.validate(p.diff(stateBefore, stateAfter), 'write');
      p.report.state_preservation = (p.report.state_preservation || []).concat({state, tables: 77, passed: true});
      await context.close();
    }
    const final = p.oracle(); p.json('el-business-after.json', final);
    const changes = p.diff(initial, final);
    p.report.preservation = {passed: true, tables_checked: 77, schema_unchanged: true,
      changed_tables: [...new Set(changes.map(c => c.table))], changed_rows: changes.length,
      detail: 'Each state independently checked against its exact allowed material IDs; all other rows and fields identical'};
    assert.equal(p.report.summary.failed, 0); assert.deepEqual(p.report.pageerrors, []); assert.deepEqual(p.report.external, []);
    assert.deepEqual(p.report.failed_requests.filter(r => !r.intentional_network_fault && !String(r.error?.errorText).includes('ERR_ABORTED')), []);
  } catch (error) {
    if (p.page && !p.page.isClosed()) p.json('el-fatal-dom.json', {text: await p.page.locator('body').innerText()});
    throw error;
  } finally { await browser.close(); p.report.browser_closed = true; p.save(); }
}
main().catch(error => {p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1;});
