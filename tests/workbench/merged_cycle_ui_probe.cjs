'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs');
const {chromium} = require('playwright'), {Probe} = require('./migrated_process_batch_support.cjs');
const {geometry} = require('./ed_material_process_visual.cjs');
const {pagination, noMatches} = require('./ed_material_process_filters.cjs');
const {cycleSave, damaged, protocolFailures} = require('./merged_cycle_ui_steps.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), p = new Probe(ready);
p.report.states = [];
p.report.mutation_policy = {business_rows: 'Only active ER test owner group20 total_days 6.75 -> 7.25',
  untouched: 'Every PartOperations field including NULL ext_days; all Parts, other groups, remarks, old batches and schema',
  metadata: 'Current owner confirmation records, identity revisions and append-only UI command receipts'};
p.save = function() {
  this.report.summary = {cases: this.report.cases.length, failed: this.report.cases.filter(row => !row.passed).length,
    steps: this.report.steps.length, screenshots: this.report.screenshots.length};
  this.json('er-report.json', this.report);
};
const baseShot = p.shot.bind(p);
p.shot = async function(name) {
  const file = await baseShot(name), layout = await geometry(this.page);
  this.report.screenshots[this.report.screenshots.length - 1].layout = layout;
  assert.deepEqual(layout.clipping, []); assert.deepEqual(layout.overlaps, []);
  assert.deepEqual((layout.controlContrast || []).filter(row => !row.passes), []);
  this.save(); return file;
};
p.validate = function(changes, policy) {
  const owned = ready.expected.er.states[this.state].part;
  for (const change of changes) {
    const {table, before, after, columns} = change;
    if (table === 'WorkbenchEntityRefs' && !before) { assert(after); continue; }
    assert.equal(policy, 'write', 'Read/cancel mutated ' + table);
    if (table === 'WorkbenchCommandReceipts') { assert(!before && after); continue; }
    if (table === 'WorkbenchEntityRefs') {
      assert(before && after); assert.deepEqual(columns, ['revision']);
      const op = this.lastAfter.tables.PartOperations.find(row => String(row.id) === after.entity_key);
      const group = this.lastAfter.tables.ExternalGroups.find(row => row.group_id === after.entity_key);
      assert(after.kind === 'part' && after.entity_key === owned || after.kind === 'template_operation' && op && op.part_no === owned
        || after.kind === 'template_external_group' && group && group.part_no === owned); continue;
    }
    if (['WorkbenchProcessWorkflow', 'WorkbenchProcessOperationConfirmations'].includes(table)) {
      const ref = (after || before).part_ref;
      assert(this.lastAfter.tables.WorkbenchEntityRefs.some(row => row.ref === ref && row.entity_key === owned)); continue;
    }
    assert.equal(table, 'ExternalGroups', 'Unexpected business change: ' + JSON.stringify(change));
    assert(before && after && after.part_no === owned && after.start_seq === 20);
    assert.deepEqual(columns, ['total_days']); assert.equal(before.total_days, 6.75); assert.equal(after.total_days, 7.25);
  }
};
async function main() {
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
  try {
    for (const state of ['1920-light', '1920-dark', '1392-light', '1392-dark']) {
      const [widthText, theme] = state.split('-'), width = Number(widthText), data = ready.expected.er.states[state];
      const context = await browser.newContext({viewport: {width, height: width === 1920 ? 1080 : 924}, timezoneId: 'Asia/Shanghai'});
      const page = await context.newPage(); p.attach(page, state);
      await page.goto(ready.url + '/workbench'); await page.locator('.sidebar').waitFor();
      if (theme === 'dark') await p.click(page.getByRole('button', {name: '深色：关', exact: true}));
      assert(await p.run('merged-cycle-save', 'write', () => cycleSave(p, page, data)));
      for (const kind of Object.keys(data.damaged)) assert(await p.run('real-' + kind, 'read', () => damaged(p, page, data, kind)));
      assert(await p.run('protocol-fail-closed', 'read', () => protocolFailures(p, page, data)));
      assert(await p.run('preserved-pagination', 'read', () => pagination(p, page, data)));
      assert(await p.run('preserved-empty-filter', 'read', () => noMatches(p, page, data)));
      await context.close();
    }
  } finally { await browser.close(); p.report.browser_closed = true; p.save(); }
  assert.equal(p.report.summary.failed, 0); assert.deepEqual(p.report.pageerrors, []); assert.deepEqual(p.report.external, []);
  assert.deepEqual(p.report.http_errors, []); assert.deepEqual(p.report.console, []);
}
main().catch(error => {p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1;});
