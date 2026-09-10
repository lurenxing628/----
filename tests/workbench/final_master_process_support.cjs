'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {Probe: OriginalProbe} = require('./migrated_process_batch_support.cjs');
const tables = new Set(['WorkbenchDashboardItems', 'WorkbenchOutsourcingOperationOrigins', 'WorkbenchTemplateLineageOrigins', 'WorkbenchTemplateLineageEvents']);

function validateLineageSequence(changes, after, policy) {
  const table = 'WorkbenchTemplateLineageEvents';
  const sequence = changes.filter(row => row.table === 'sqlite_sequence' && (row.after || row.before).name === table);
  const added = changes.filter(row => row.table === table && !row.before && row.after).map(row => row.after.event_id).sort((a, b) => a - b);
  if (!added.length) { assert.equal(sequence.length, 0); return sequence; }
  assert.equal(policy, 'write');
  assert.equal(sequence.length, 1);
  const row = sequence[0], previous = row.before ? row.before.seq : 0;
  assert(row.after && Number.isSafeInteger(previous));
  assert.deepEqual(added, Array.from({length: added.length}, (_, index) => previous + index + 1));
  assert.equal(row.after.seq, previous + added.length);
  assert.equal(row.after.seq, Math.max(...after.tables[table].map(event => event.event_id)));
  if (row.before) assert.deepEqual(row.columns, ['seq']);
  return sequence;
}

class Probe extends OriginalProbe {
  validate(changes, policy) {
    if (changes.some(row => tables.has(row.table) || !row.before && row.after
      && (row.table === 'WorkbenchEntityRefs' && row.after.kind === 'batch' || row.table === 'WorkbenchPlanSourceRefs' && row.after.kind === 'operation'))) {
      const result = JSON.parse(execFileSync(process.env.AN_PYTHON, ['-B', '-m', 'tests.workbench.final_master_metadata_guard_support'], {
        cwd: path.resolve(__dirname, '../..'), input: JSON.stringify({changes, after: this.lastAfter, policy, root: this.root}), maxBuffer: 16 * 1024 * 1024, timeout: 30000
      }));
      this.report.tracking_preservation = this.report.tracking_preservation || [];
      this.report.tracking_preservation.push({case: this.currentCase, ...result});
    }
    const sequence = validateLineageSequence(changes, this.lastAfter, policy);
    super.validate(changes.filter(row => !tables.has(row.table) && !sequence.includes(row)), policy);
  }
}

module.exports = {Probe, validateLineageSequence};
