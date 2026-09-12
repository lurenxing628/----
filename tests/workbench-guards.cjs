'use strict';
// Pure-node contract for WorkbenchGuards: locking comes only from entries that declare it, and a prompt
// whose protected entries disappear closes itself instead of leaving an empty dialog behind.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const listeners = {};
const context = vm.createContext({
  window: {
    addEventListener: (name, listener) => { (listeners[name] = listeners[name] || []).push(listener); },
    removeEventListener: (name, listener) => { listeners[name] = (listeners[name] || []).filter(value => value !== listener); },
    setTimeout,
  },
  React: { useId: () => ':r0:', useRef: () => ({ current: null }), useLayoutEffect: () => {} },
});
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/WorkbenchGuards.js'), 'utf8'), context);
const G = context.window.WorkbenchGuards;
const settled = promise => Promise.race([promise.then(value => ({ settled: true, value })),
  new Promise(resolve => setTimeout(() => resolve({ settled: false }), 20))]);

(async () => {
  // Without a mounted host the request is refused loudly instead of silently leaving.
  const offA = G.register({ owner: 'A', dirty: true, message: 'A 未保存' });
  await assert.rejects(G.confirmLeave(), error => error.message.includes('草稿确认组件未挂载'));
  // A host receives the prompt and the caller gets the answer.
  const prompts = [];
  const unsubscribe = G.subscribe(prompt => prompts.push(prompt));
  const leaveA = G.confirmLeave();
  // Arrays cross the vm realm boundary, so compare by content rather than by prototype identity.
  const messages = () => JSON.stringify(G.getPrompt().messages);
  assert.equal(messages(), JSON.stringify(['A 未保存']));
  G.resolvePrompt(G.getPrompt().id, true);
  assert.equal(await leaveA, true);
  assert.equal(G.getPrompt(), null);
  offA();
  // The editor unmounts while its prompt is open: nothing is left to protect, so the prompt closes and leaving proceeds.
  const offB = G.register({ owner: 'B', dirty: true, message: 'B 未保存' });
  const leaveB = G.confirmLeave({ owner: 'B' });
  assert.equal(messages(), JSON.stringify(['B 未保存']));
  offB();
  assert.deepEqual(await settled(leaveB), { settled: true, value: true });
  assert.equal(G.getPrompt(), null);
  assert.equal(prompts[prompts.length - 1], null, 'host must be told the prompt is gone');
  // A locked entry (a pending command) keeps blocking even when clean and cannot be abandoned.
  const offC = G.register({ owner: 'C', dirty: false, locked: true, message: 'C 请求待核实' });
  const leaveC = G.confirmLeave({ owner: 'C' });
  assert.equal(G.getPrompt().locked, true);
  G.resolvePrompt(G.getPrompt().id, true);
  assert.deepEqual(await settled(leaveC), { settled: false }, 'locked prompt must refuse to leave');
  G.resolvePrompt(G.getPrompt().id, false);
  assert.equal(await leaveC, false);
  offC();
  // A clean, unlocked entry never prompts: busy UI state must be expressed through dirty/locked only.
  const offD = G.register({ owner: 'D', dirty: false, message: 'D' });
  assert.equal(await G.confirmLeave(), true);
  assert.equal(G.hasDirty(), false);
  offD();
  // The beforeunload listener is installed once and removed when nothing is dirty.
  const offE = G.register({ owner: 'E', dirty: true, message: 'E' });
  const offF = G.register({ owner: 'F', dirty: true, message: 'F' });
  assert.equal((listeners.beforeunload || []).length, 1);
  offE(); offF();
  assert.equal((listeners.beforeunload || []).length, 0);
  unsubscribe();
  assert.equal(G.hasDirty(), false);
  process.stdout.write('WorkbenchGuards contracts passed.\n');
})().catch(error => { console.error(error); process.exit(1); });
