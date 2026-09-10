'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const window = { APSResourceContract: {}, PointContract: { isPoint: () => false } };
const context = vm.createContext({ window, Date, Number, Map, Set });
for (const file of ['FieldContract.js', 'ActualGanttModel.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app', file), 'utf8'), context);
const C = window.FieldContract, M = window.ActualGanttModel;
const base = { piece_id: 'item-A', quantity: 1, batch_quantity: 3, quantity_basis: 'run_admission', quantity_reason: null };
assert(C.planQuantity(base));
for (const patch of [{ piece_id: undefined }, { quantity: undefined }, { quantity: true }, { quantity: -1 }, { quantity: 1.5 }, { quantity_basis: 'guessed' }, { quantity_reason: 'guessed' }]) assert(!C.planQuantity({ ...base, ...patch }));
const old = { ...base, quantity: null, batch_quantity: null, quantity_basis: 'unknown', quantity_reason: 'plan_target_not_recorded' };
assert(C.planQuantity(old)); assert.equal(C.quantity(old.quantity), '未知');
assert(!C.planQuantity({ ...old, quantity: 3 }));
for (const piece of ['item-A', 'item-B', 'item-C', '分件原始中文身份']) {
  const task = { ...base, piece_id: piece, task_ref: piece, batch_id: 'B1', sequence: 20, process_label: 'Turning', start: '2026-09-09T08:00:00', end: '2026-09-09T09:00:00' };
  const item = { task, execution: null };
  assert(M.taskLabel(task).includes(piece)); assert(M.searchText(item, new Map()).includes(piece.toLowerCase()));
  const text = M.describe(item, new Map()).join('\n'); assert(text.includes(piece)); assert(text.includes('计划应做：1 件 · 批次：3 件'));
  const unknown = M.describe({ task: { ...task, ...old }, execution: null }, new Map()).join('\n');
  assert(unknown.includes('计划应做：未知 件')); assert(unknown.includes('旧计划未记录原数量证据'));
}
console.log('FB field contract, original identity, null/zero and actual descriptions passed');
