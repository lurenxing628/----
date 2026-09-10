'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), context = vm.createContext({window: {}});
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/resource-contract.js'), 'utf8'), context);
const C = context.window.APSResourceContract, plain = value => JSON.parse(JSON.stringify(value));
const original = {ref: 'a'.repeat(48), business_code: 'EL-001', label: 'Original', status: 'active',
  fields: {spec: null, unit: 'kg', stock_qty: 1.25, remark: ' Original note\nsecond line ', hidden: 'retained'}, relationships: {}};
let checks = 0;
for (const remark of [null, '', 'Original note', ' 第一行\n第二行 '.repeat(20)]) {
  const entity = {...original, fields: {...original.fields, remark}}, draft = C.draft('material', entity);
  assert.equal(draft.fields.remark, remark == null ? '' : remark);
  assert.deepEqual(plain(C.input('material', draft, entity)), {});
  draft.label = 'Only name';
  assert.deepEqual(plain(C.input('material', draft, entity)), {label: 'Only name'}); checks += 3;
}
for (const value of ['', '  \n\t', '修改备注\n下一行'.repeat(30)]) {
  const draft = C.draft('material', original); draft.fields.remark = value;
  assert.deepEqual(plain(C.input('material', draft, original)), {fields: {remark: value.trim() || null}}); checks++;
}
const stock = C.draft('material', original); stock.fields.stock_qty = '0';
assert.deepEqual(plain(C.input('material', stock, original)), {fields: {stock_qty: 0}}); checks++;
const before = C.draft('material', original); before.fields.remark = 'Local draft';
const fresh = {...original, fields: {...original.fields, remark: 'Server remark', stock_qty: 9}};
const rebased = C.rebaseDraft('material', before, original, fresh);
assert.deepEqual(plain(C.input('material', rebased, fresh)), {fields: {remark: 'Local draft'}}); checks++;
const unchanged = C.rebaseDraft('material', C.draft('material', original), original, fresh);
assert.equal(unchanged.fields.remark, 'Server remark'); checks++;
const create = C.draft('material'); create.business_code = 'EL-NEW'; create.label = 'New'; create.fields.status = 'active'; create.fields.remark = ' 新增备注\n第二行 ';
assert.equal(C.input('material', create).fields.remark, '新增备注\n第二行'); checks++;
for (const kind of ['operator', 'machine', 'supplier']) {
  const draft = C.draft(kind, original); draft.fields.remark = 'Must not broaden other resources';
  assert.deepEqual(plain(C.input(kind, draft, original)), {}); checks++;
}
console.log(JSON.stringify({checks, passed: true}));
