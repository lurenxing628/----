'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const context = { window: {} }; context.window.window = context.window;
vm.createContext(context);
for (const file of ['resource-contract.js', 'BatchContract.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app', file), 'utf8'), context);
const B = context.window.APSBatchContract, C = context.window.APSResourceContract;
const plain = value => JSON.parse(JSON.stringify(value));
const empty = B.draft(null);
assert.deepEqual(plain(B.inputErrors(empty, null).map(row => row.path)), ['business_code', 'part_ref', 'fields.quantity']);
assert.throws(() => B.input(empty, null), error => C.fieldErrors(error).length === 3);
const good = { ...empty, business_code: ' B-NEW ', part_ref: 'a'.repeat(48), quantity: '7' };
assert.deepEqual(plain(B.input(good, null)), { business_code: 'B-NEW', part_ref: 'a'.repeat(48), fields: { quantity: 7, due_date: null, priority: 'normal', ready_status: 'yes', ready_date: null, remark: null } });
for (const quantity of ['0', '-1', '1.5', 'abc', '9007199254740992']) {
  assert.throws(() => B.input({ ...good, quantity }, null), error => C.fieldErrors(error).some(row => row.path === 'fields.quantity'));
}
const original = { fields: { quantity: null, due_date: null, priority: 'legacy', ready_status: null, ready_date: null, remark: 'before' } };
const draft = B.draft(original); draft.remark = 'after';
assert.deepEqual(plain(B.input(draft, original)), { fields: { remark: 'after' } }, 'editing one field must retain legacy unknown values');
assert.deepEqual(plain(B.input(B.draft(original), original)), { fields: {} }, 'unchanged original fields are not rewritten');
const invalidDates = B.inputErrors({ ...good, due_date: '12/09/2026', ready_date: 'tomorrow' }, null);
assert.deepEqual(plain(invalidDates.map(row => row.path)), ['fields.due_date', 'fields.ready_date']);
console.log(JSON.stringify({ passed: true, cases: 10, scope: 'batch-validation-preserves-command-contract' }));
