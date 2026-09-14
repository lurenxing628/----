'use strict';
// 经办人记忆合同：只记住合法的经办人文本；读到坏值或存储不可用时不预填，并把原因通过 hint 讲出来。
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const context = { console };
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/WorkbenchHandlerMemory.js'), 'utf8'), context, { filename: 'WorkbenchHandlerMemory.js' });
const M = context.WorkbenchHandlerMemory;
// vm 里造出来的对象原型不同，先拷成本 realm 的普通对象再比。
const eq = (actual, expected) => assert.deepEqual({ ...actual }, expected);
const store = () => { const map = new Map(); return { getItem: key => map.has(key) ? map.get(key) : null, setItem: (key, value) => map.set(key, value), map }; };

// 空存储：不预填，也没有提示。
let s = store();
eq(M.read(s), { value: '', error: '' });
assert.equal(M.hint('', s), '');

// 正常写入后读回去，预填值旁边说明它从哪来；用户改掉后说明消失。
eq(M.write('  计划员 张三 ', s), { saved: true, error: '' });
assert.equal(s.map.get(M.KEY), '计划员 张三');
eq(M.read(s), { value: '计划员 张三', error: '' });
assert.equal(M.hint('计划员 张三', s), '已按本机上次填写的经办人预填，可以直接改。');
assert.equal(M.hint('计划员 李四', s), '');

// 非法值不记住：空白、超长、非字符串。
for (const bad of ['', '   ', 'x'.repeat(101), null, 12]) assert.equal(M.write(bad, s).saved, false);
assert.equal(s.map.get(M.KEY), '计划员 张三');

// 存储里有坏值：不预填，并说明原因。
s = store(); s.map.set(M.KEY, ' 带空格 ');
eq(M.read(s), { value: '', error: '本机记住的经办人格式无效，这次不预填。' });
assert.equal(M.hint('', s), '本机记住的经办人格式无效，这次不预填。');
s = store(); s.map.set(M.KEY, 'y'.repeat(101));
assert.equal(M.read(s).value, '');

// 存储不可用：读写都不抛错，原因随结果返回，并记在 hint 里直到下次写成功。
const broken = { getItem() { throw new Error('quota'); }, setItem() { throw new Error('quota'); } };
eq(M.read(broken), { value: '', error: '本机经办人记忆无法读取，这次不预填。' });
eq(M.write('张三', broken), { saved: false, error: '本机经办人记忆无法写入，下次仍需手填。' });
assert.equal(M.hint('张三', store()), '本机经办人记忆无法写入，下次仍需手填。');
eq(M.write('张三', store()), { saved: true, error: '' });
assert.equal(M.hint('', store()), '');

// 导出是冻结的，避免页面里被改写。
assert.ok(Object.isFrozen(M));
console.log('handler memory contract ok');
