'use strict';
const assert = require('node:assert/strict');
const {validateLineageSequence} = require('./final_master_process_support.cjs');
const table = 'WorkbenchTemplateLineageEvents';
function fixture() {
  const events = [1, 2, 3, 4].map(event_id => ({event_id}));
  return {after: {tables: {[table]: events}}, changes: [
    {table: 'sqlite_sequence', before: {name: table, seq: 2}, after: {name: table, seq: 4}, columns: ['seq']},
    ...events.slice(2).map(after => ({table, after}))
  ]};
}
let value = fixture();
assert.equal(validateLineageSequence(value.changes, value.after, 'write').length, 1);
for (const fault of ['read', 'noop', 'extra_increment', 'missing_event', 'gap', 'changed_column', 'missing_sequence', 'unexplained_sequence']) {
  value = fixture();
  if (fault === 'extra_increment') value.changes[0].after.seq = 5;
  if (fault === 'missing_event') value.changes.pop();
  if (fault === 'gap') value.changes[1].after.event_id = 99;
  if (fault === 'changed_column') value.changes[0].columns.push('name');
  if (fault === 'missing_sequence') value.changes.shift();
  if (fault === 'unexplained_sequence') value.changes = value.changes.slice(0, 1);
  assert.throws(() => validateLineageSequence(value.changes, value.after, ['read', 'noop'].includes(fault) ? fault : 'write'));
}
console.log('9 exact lineage sequence assertions passed');
