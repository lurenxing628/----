"""Frontend pending store CAS serialization and terminal state recovery across component remounts."""

import json
import subprocess
from pathlib import Path

from tests._support.node_runtime_support import node_runtime

ROOT = Path(__file__).resolve().parents[2]

# 宿主侧的同源 Web Locks：同名请求按 FIFO 排队；ifAvailable 在锁被占或有人排队时以 null 回调；回调总是异步触发，
# 回调返回的 Promise 结束后才放锁。与浏览器一样，只有同一个 LockManager 下的页面才互斥。
LOCK_MANAGER = r"""
function createLockManager() {
  const queues = new Map();
  function pump(queue) {
    if (queue.held || !queue.waiters.length) return;
    const { callback, resolve, reject } = queue.waiters.shift();
    queue.held = true;
    Promise.resolve().then(() => callback({})).then(resolve, reject).finally(() => { queue.held = false; pump(queue); });
  }
  return {
    request(name, options, callback) {
      if (!queues.has(name)) queues.set(name, { held: false, waiters: [] });
      const queue = queues.get(name);
      if (options.ifAvailable && (queue.held || queue.waiters.length)) return Promise.resolve().then(() => callback(null));
      return new Promise((resolve, reject) => { queue.waiters.push({ callback, resolve, reject }); pump(queue); });
    },
  };
}
"""


def _run_node(script: str) -> dict:
    wrapped = f"'use strict';\n{LOCK_MANAGER}\n(async () => {{\n{script}\n}})().catch(err => {{ console.error(err); process.exit(1); }});"
    result = subprocess.run(
        [node_runtime(), "-e", wrapped],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_pending_store_cas_and_storage_failure_serialization():
    report = _run_node(
        r"""
        'use strict';
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const babelPath = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
        const files = [
          'WorkbenchTerms.js', 'transport.js', 'resource-contract.js', 'resource-api.js',
          'RunAdoptionAPI.js', 'RunJobAPI.js', 'TrialContract.js', 'TrialAPI.js',
          'SystemRestoreStatus.js', 'SystemMaintenanceAPI.js'
        ];
        const compiled = compile({
          babel_path: babelPath,
          sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
          check_combined: false,
        });

        function createStorage() {
          const data = new Map();
          return {
            data,
            failGet: null,
            failSet: null,
            failRemove: null,
            getItem(k) { if (this.failGet) throw this.failGet; return data.has(k) ? data.get(k) : null; },
            setItem(k, v) { if (this.failSet) throw this.failSet; data.set(k, v); },
            removeItem(k) { if (this.failRemove) throw this.failRemove; data.delete(k); },
          };
        }

        let seq = 1;
        const events = [];
        const w = vm.createContext({
          console, URL, URLSearchParams, AbortController, Set, Map, WeakMap, WeakSet, Error, TypeError, DOMException,
          Math, Number, String, Boolean, Array, Object, JSON, RegExp, Promise, Date, FormData: class {},
          setTimeout, clearTimeout,
          crypto: { getRandomValues: b => { b.fill(seq++); return b; } },
          CustomEvent: class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } },
          location: new URL('http://127.0.0.1:8080/workbench'),
          localStorage: createStorage(),
          sessionStorage: createStorage(),
          navigator: { locks: createLockManager() },
           dispatchEvent(ev) { events.push(ev); },
        });
        w.window = w;
        for (const out of compiled.outputs) vm.runInContext(out.code, w, { filename: out.path });

        const T = w.APSWorkbenchTransport;
        const ref = n => n.toString(16).padStart(48, '0');
        const dataContext = JSON.stringify({ database_scope: 'db', successful_restores: [] });

        // 1. pendingStore CAS rejects stale save(null, old) or save(rejected, old) even when getItem throws!
        {
          const backing = createStorage();
          const store = T.pendingStore({
            key: 'cas_test_v1',
            storage: () => backing,
            event: 'cas_test_event',
            readError: '读取失败',
            conflictError: '记录已冲突',
            writeError: '写入失败',
            removeError: '删除失败',
          });
          const first = { request_key: 'k1', phase: 'pending' };
          const second = { request_key: 'k2', phase: 'pending' };
          store.save(first, null);
          store.save( null, first);
          store.save(second, null);

          // Now getItem fails while a late callback for `first` tries to settle `first` -> must throw conflictError, not overwrite `second`!
          backing.failGet = new Error('getItem blocked');
          const eventsBefore = events.length;
          assert.throws(() => store.save({ ...first, phase: 'rejected' }, first), err => err.conflict === true && /记录已冲突/.test(err.message));
          assert.throws(() => store.save(null, first), err => err.conflict === true && /记录已冲突/.test(err.message));
          assert.equal(events.length, eventsBefore, 'Stale CAS failure must not dispatch event');

          backing.failGet = null;
          assert.deepEqual(store.read(), second, 'Active second record remains intact');
        }

        // 2. APSResourceAPI savePending / clearPending CAS serialization.
        {
          w.sessionStorage = createStorage();
          const resApi = w.APSResourceAPI.create('batches');
          const intent1 = { kind: 'batch', action: 'create', ref: null, request_key: 'resource-' + '1'.repeat(48), input: { business_code: 'B1' } };
          const intent2 = { kind: 'batch', action: 'create', ref: null, request_key: 'resource-' + '2'.repeat(48), input: { business_code: 'B2' } };
          resApi.savePending(intent1);
          assert.throws(() => resApi.savePending(intent2), err => err.conflict === true && /操作记录已变化/.test(err.message), 'Second savePending while pending must fail CAS');

          // Replacing on disk with intent2 prevents stale clearPending(intent1) from erasing intent2.
          w.sessionStorage.setItem(resApi.pendingKey, JSON.stringify({ kind: 'batch', action: 'create', ref: null, request_key: intent2.request_key }));
          assert.throws(() => resApi.clearPending(intent1), err => err.conflict === true && /操作记录已变化/.test(err.message), 'Stale clearPending(intent1) must not delete intent2');
          assert.equal(resApi.readPending().request_key, intent2.request_key);
          resApi.clearPending(intent2);
          assert.equal(resApi.readPending(), null);
        }

        // 3. RunJobAPI begin/attach/finish CAS, idempotent repeated finish, and F03/F04 storage recovery.
        {
          const runStore = createStorage();
          w.localStorage = runStore;
          const p = w.RunJobAPI.pending();
          const inputRef = 'i'.repeat(32);
          const i1 = p.begin(inputRef, dataContext);
          assert.throws(() => p.begin(inputRef, dataContext), /上次排产还没确认结果/);
          const attached = p.attach(i1, ref(10));
          assert.equal(attached.run_ref, ref(10));
          assert.throws(() => p.attach(i1, ref(11)), /上次操作记录已变化/, 'Stale unattached intent cannot overwrite attached run_ref with another ref');
          p.finish(attached, 'found');
          assert.equal(p.read(), null);
          assert.equal(p.recent().intent.request_key, i1.request_key);

          // R2-02: Finish b after a; a late finish(a) and a repeated finish(b) are no-ops: nothing is removed and RECENT keeps b's first conclusion.
          const ib = p.attach(p.begin(inputRef, dataContext), ref(12));
          p.finish(ib, 'found');
          assert.equal(p.recent().intent.request_key, ib.request_key);
          const recentWrites = runStore.data.get(w.RunJobAPI.RECENT_KEY);
          p.finish(attached, 'found');
          p.finish(ib, 'context_replaced');
          assert.equal(runStore.data.get(w.RunJobAPI.RECENT_KEY), recentWrites, 'Repeated or late finish must not rewrite RECENT');
          assert.equal(p.recent().intent.request_key, ib.request_key, 'Stale finish(a) must not overwrite recent().intent (b)');
          assert.equal(p.recent().intent.run_ref, ref(12));
          assert.equal(p.recent().resolution, 'found');

          // F03: attach(intent, runRef) when setItem fails retains authoritative run_ref in memory (error.saved); a locked flush() writes it after recovery.
          const i2 = p.begin(inputRef, dataContext);
          runStore.failSet = new Error('setItem blocked');
          let attachErr = null;
          try { p.attach(i2, ref(20)); } catch (err) { attachErr = err; }
          assert.ok(attachErr && attachErr.saved && attachErr.saved.run_ref === ref(20), 'F03: attach failure must attach error.saved with run_ref');
          runStore.failSet = null;
          assert.throws(() => p.read(), err => err.saved && err.saved.run_ref === ref(20), 'F03: read() never writes; the unflushed attach stays reported');
          const recoveredAttach = (await T.exclusive(w.RunJobAPI.PENDING_KEY, { wait: true }, () => p.flush())).value;
          assert.equal(recoveredAttach.request_key, i2.request_key);
          assert.equal(recoveredAttach.run_ref, ref(20), 'F03: a locked flush() after storage recovery writes and returns attached run_ref');
          assert.equal(JSON.parse(runStore.data.get(w.RunJobAPI.PENDING_KEY)).run_ref, ref(20));

          // F04: reject(intent) when removeItem fails records authoritative null and never resurrects after storage recovery.
          runStore.failRemove = new Error('removeItem blocked');
          assert.throws(() => p.reject(recoveredAttach), /本机无法更新上次操作记录/);
          assert.throws(() => p.read(), /本机无法更新上次操作记录/);
          runStore.failRemove = null;
          await T.exclusive(w.RunJobAPI.PENDING_KEY, { wait: true }, () => p.flush());
          assert.equal(p.read(), null, 'F04: rejected RunJobAPI intent must never resurrect on read() after storage recovery');
          assert.equal(runStore.data.has(w.RunJobAPI.PENDING_KEY), false);
        }

        console.log(JSON.stringify({ ok: true }));
        """
    )
    assert report["ok"] is True


def test_trial_session_terminal_state_survives_remount_and_unmount():
    report = _run_node(
        r"""
        'use strict';
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const babelPath = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
        const files = ['WorkbenchTerms.js', 'transport.js', 'TrialContract.js', 'TrialAPI.js', 'TrialSession.js'];
        const compiled = compile({
          babel_path: babelPath,
          sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
          check_combined: false,
        });

        function createStorage() {
          const data = new Map();
          return {
            data,
            failGet: null,
            failSet: null,
            failRemove: null,
            getItem(k) { if (this.failGet) throw this.failGet; return data.has(k) ? data.get(k) : null; },
            setItem(k, v) { if (this.failSet) throw this.failSet; data.set(k, v); },
            removeItem(k) { if (this.failRemove) throw this.failRemove; data.delete(k); },
          };
        }

        function createHost(w) {
          let cursor = 0;
          const slots = [], effects = [];
          const sameDeps = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
          const React = {
            useState(init) {
              const i = cursor++;
              if (!slots[i]) slots[i] = { value: typeof init === 'function' ? init() : init };
              const s = slots[i];
              return [s.value, next => { s.value = typeof next === 'function' ? next(s.value) : next; }];
            },
            useRef(v) { const i = cursor++; if (!slots[i]) slots[i] = { current: v }; return slots[i]; },
            useEffect(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
                const prev = slots[i];
                slots[i] = { deps };
                effects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
              }
            },
          };
          return {
            render(fn) { cursor = 0; w.React = React; return fn(); },
            flush() { while (effects.length) effects.shift()(); },
            unmount() { for (const s of slots) if (s && s.cleanup) s.cleanup(); },
          };
        }

        let seq = 1;
        const w = vm.createContext({
          console, URL, URLSearchParams, AbortController, Set, Map, WeakMap, WeakSet, Error, TypeError, DOMException,
          Math, Number, String, Boolean, Array, Object, JSON, RegExp, Promise, Date, FormData: class {},
          setTimeout, clearTimeout,
          crypto: { getRandomValues: b => { b.fill(seq++); return b; } },
          location: new URL('http://127.0.0.1:8080/workbench/trial'),
          localStorage: createStorage(),
          navigator: { locks: createLockManager() },
          addEventListener() {}, removeEventListener() {},
          APSResourceSession: { useQuery: () => ({ loading: false }) },
        });
        w.window = w;
        for (const out of compiled.outputs) vm.runInContext(out.code, w, { filename: out.path });

        let lookups = 0, cmdHandler = null;
        w.TrialAPI.command = async (intent, token, key) => cmdHandler(intent, token, key);
        w.TrialAPI.lookup = async () => { lookups++; return { state: 'not_observed', receipt: null }; };

        const rejectedErr = w.APSWorkbenchTransport.failure({
          ok: false,
          committed: false,
          error: { code: 'stale_write', message: '草稿已变化', fields: [], retryable: false, request_ref: '1'.repeat(32) },
        }, 409);

        // 1. Rejected command whose local clear fails survives TrialSession unmount/remount without calling lookup().
        w.localStorage.failRemove = new Error('removeItem blocked');
        cmdHandler = async () => { throw rejectedErr; };

        const host1 = createHost(w);
        const render1 = () => host1.render(() => w.TrialSession.useCommands(() => {}));
        render1(); host1.flush();
        assert.equal(await render1().execute({ action: 'save' }, 'tok'), false);
        const state1 = render1();
        assert.ok(state1.key);
        assert.equal(state1.note, '这次没有写入，但本机操作记录还没清掉。请点「查询结果」重试清理。');
        host1.unmount();

        // Remount while failRemove is still active: must stay in rejected cleanup retry state and do 0 lookups.
        const host2 = createHost(w);
        const render2 = () => host2.render(() => w.TrialSession.useCommands(() => {}));
        render2(); host2.flush();
        let state2 = render2();
        assert.equal(state2.key, state1.key);
        assert.equal(state2.note, '这次没有写入，但本机操作记录还没清掉。请点「查询结果」重试清理。');
        await state2.lookup();
        assert.equal(lookups, 0, 'Remounted TrialSession must not call lookup() for a rejected key');

        // Recover storage and retry via lookup(): local key clears cleanly with 0 network lookups.
        w.localStorage.failRemove = null;
        await render2().lookup();
        state2 = render2();
        assert.equal(state2.key, null);
        assert.equal(state2.error, null);
        assert.equal(w.localStorage.getItem(w.TrialAPI.PENDING_KEY), null);
        assert.equal(lookups, 0);
        host2.unmount();

        // 2. Unmounting while confirmed command is in flight still releases the pending key!
        const tick = () => new Promise(r => setTimeout(r, 0));
        w.localStorage.data.clear();
        let resolveCmd;
        cmdHandler = () => new Promise(res => { resolveCmd = res; });
        const host3 = createHost(w);
        const render3 = () => host3.render(() => w.TrialSession.useCommands(() => {}));
        render3(); host3.flush();
        const execPromise = render3().execute({ action: 'save' }, 'tok');
        await tick();
        assert.ok(w.localStorage.getItem(w.TrialAPI.PENDING_KEY), 'Key reserved while in flight');
        host3.unmount();
        resolveCmd({ data: { scenario_ref: 's'.repeat(48) } });
        await execPromise;
        assert.equal(w.localStorage.getItem(w.TrialAPI.PENDING_KEY), null, 'Confirmed command must clear pending key even if component unmounted');

        // 3. The cross-page lock is held across the command: while `a` is in flight another session reserves nothing.
        //    `a`'s late receipt clears only its own key; then `b` submits, and `b`'s failed clear survives a remount.
        w.localStorage.data.clear();
        w.localStorage.failRemove = null;
        let resolveCmdA;
        cmdHandler = () => new Promise(res => { resolveCmdA = res; });
        const host4 = createHost(w);
        const render4 = () => host4.render(() => w.TrialSession.useCommands(() => {}));
        render4(); host4.flush();
        const execPromiseA = render4().execute({ action: 'save' }, 'tok');
        await tick();
        const keyA = w.localStorage.getItem(w.TrialAPI.PENDING_KEY);
        assert.ok(keyA, 'Old request `a` reserved');
        host4.unmount();

        const receiptB = { data: { scenario_ref: 'b'.repeat(48) } };
        cmdHandler = async () => receiptB;
        const host5 = createHost(w);
        const render5 = () => host5.render(() => w.TrialSession.useCommands(() => {}));
        render5(); host5.flush();
        assert.equal(await render5().execute({ action: 'save' }, 'tok'), false, '`b` is refused while `a` holds the lock');
        assert.equal(render5().error.message, '另一个页面正在提交试调，请稍后重试。');
        assert.equal(w.localStorage.getItem(w.TrialAPI.PENDING_KEY), keyA, 'The refused submission reserved nothing');

        resolveCmdA({ data: { scenario_ref: 'a'.repeat(48) } });
        await execPromiseA;
        assert.equal(w.localStorage.getItem(w.TrialAPI.PENDING_KEY), null, "`a`'s late receipt clears its own key");
        assert.equal(w.TrialAPI.settled, null);

        w.localStorage.failRemove = new Error('removeItem blocked for b');
        render5().clearError();
        assert.equal(await render5().execute({ action: 'save' }, 'tok'), true);
        const keyB = render5().key;
        assert.ok(keyB && keyB !== keyA);
        assert.equal(JSON.stringify(w.TrialAPI.settled), JSON.stringify({ key: keyB, note: '' }),
          'The settled record keeps only the key and note of `b`');
        host5.unmount();

        // Remount: `b`'s key and settled state remain intact; recovering storage and calling lookup() clears `b` cleanly with 0 network lookups.
        lookups = 0;
        const host6 = createHost(w);
        const render6 = () => host6.render(() => w.TrialSession.useCommands(() => {}));
        render6(); host6.flush();
        let state6 = render6();
        assert.equal(state6.key, keyB, 'Remounted session preserves `b` key after `a` late response');
        assert.equal(w.TrialAPI.settled.key, keyB);
        assert.equal(lookups, 0);
        w.localStorage.failRemove = null;
        await state6.lookup();
        state6 = render6();
        assert.equal(state6.key, null);
        assert.equal(state6.error, null);
        assert.equal(w.TrialAPI.settled, null);
        assert.equal(w.localStorage.getItem(w.TrialAPI.PENDING_KEY), null);
        assert.equal(lookups, 0);
        host6.unmount();

        console.log(JSON.stringify({ ok: true }));
        """
    )
    assert report["ok"] is True


def test_system_maintenance_terminal_state_and_session_origin_across_remounts():
    report = _run_node(
        r"""
        'use strict';
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const babelPath = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
        const files = [
          'WorkbenchTerms.js', 'transport.js', 'SystemRestoreStatus.js',
          'SystemMaintenanceAPI.js', 'SystemMaintenanceControls.jsx', 'SystemMaintenanceWorkspace.jsx'
        ];
        const compiled = compile({
          babel_path: babelPath,
          sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
          check_combined: false,
        });

        function createStorage() {
          const data = new Map();
          return {
            data,
            failGet: null,
            failSet: null,
            failRemove: null,
            getItem(k) { if (this.failGet) throw this.failGet; return data.has(k) ? data.get(k) : null; },
            setItem(k, v) { if (this.failSet) throw this.failSet; data.set(k, v); },
            removeItem(k) { if (this.failRemove) throw this.failRemove; data.delete(k); },
          };
        }

        function createHost(w) {
          let cursor = 0;
          const slots = [], effects = [], layoutEffects = [];
          const sameDeps = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
          const React = {
            Fragment: 'fragment',
            createElement(type, props, ...children) {
              const flat = children.flat(Infinity);
              return { type, props: { ...(props || {}), children: flat.length <= 1 ? flat[0] : flat } };
            },
            useState(init) {
              const i = cursor++;
              if (!slots[i]) slots[i] = { value: typeof init === 'function' ? init() : init };
              const s = slots[i];
              return [s.value, next => { s.value = typeof next === 'function' ? next(s.value) : next; }];
            },
            useReducer(red, init) {
              const [v, set] = this.useState(init);
              return [v, act => set(old => red(old, act))];
            },
            useRef(v) { const i = cursor++; if (!slots[i]) slots[i] = { current: v }; return slots[i]; },
            useLayoutEffect(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
                const prev = slots[i];
                slots[i] = { deps };
                layoutEffects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
              }
            },
            useEffect(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
                const prev = slots[i];
                slots[i] = { deps };
                effects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
              }
            },
          };
          function expand(node) {
            if (!node || typeof node !== 'object') return node;
            if (Array.isArray(node)) return node.map(expand);
            if (typeof node.type === 'function') return expand(node.type(node.props || {}));
            const children = node.props && node.props.children !== undefined ? expand(node.props.children) : undefined;
            return { ...node, props: { ...(node.props || {}), children } };
          }
          return {
            render(fn) {
              cursor = 0;
              w.React = React;
              const out = expand(fn());
              while (layoutEffects.length) layoutEffects.shift()();
              while (effects.length) effects.shift()();
              return out;
            },
            unmount() { for (const s of slots) if (s && s.cleanup) s.cleanup(); },
          };
        }

        let seq = 1;
        const w = vm.createContext({
          console, URL, URLSearchParams, AbortController, Set, Map, WeakMap, WeakSet, Error, TypeError, DOMException,
          Math, Number, String, Boolean, Array, Object, JSON, RegExp, Promise, Date, FormData: class {},
          setTimeout, clearTimeout,
          crypto: { getRandomValues: b => { b.fill(seq++); return b; } },
          location: new URL('http://127.0.0.1:8080/workbench?view=system'),
          localStorage: createStorage(),
          navigator: { locks: createLockManager() },
          addEventListener() {}, removeEventListener() {},
          SystemRestorePanel: ({ command }) => { capturedCommand = command; return null; },
          SystemMaintenanceRecords: () => null,
          SystemMaintenanceConfig: () => null,
          WorkbenchReference: 'reference',
          WorkbenchError: 'error-box',
          ResourceControls: { Button: p => w.React.createElement('button', p, p.children), Modal: 'modal' },
        });
        w.window = w;
        for (const out of compiled.outputs) vm.runInContext(out.code, w, { filename: out.path });

        const readyHost = {
          state: 'ready',
          restart_required: false,
          automatic_resume: false,
          operations_available: true,
          result_source: 'external_maintenance_journal',
          references: 'none',
          request_key: null,
        };
        let lookups = 0, changedCalls = 0, currentHost = readyHost, cmdImpl = null, lookupImpl = null;
        w.SystemMaintenanceAPI.host = async () => currentHost;
        w.SystemMaintenanceAPI.command = async (intent, token, input) => cmdImpl(intent, token, input);
        w.SystemMaintenanceAPI.lookup = async intent => { lookups++; return lookupImpl(intent); };

        let capturedCommand = null;
        w.SystemMaintenanceControls.Outcome = ({ command }) => { capturedCommand = command; return null; };

        const rejectedProblem = w.APSWorkbenchTransport.failure({
          ok: false,
          committed: false,
          error: { code: 'maintenance_active', message: '恢复被拒绝', fields: [], retryable: false, request_ref: '1'.repeat(32) },
        }, 409);

        function mountWorkspace(host) {
          return host.render(() => w.SystemMaintenanceWorkspace({
            tab: 'overview', theme: 'light', onSetTheme() {}, pageSize: 10, onPageSize() {}, compact: false, onCompact() {},
            revision: 0, onChanged: () => { changedCalls++; }, onReadSuspendedChange() {}, recordContexts: {}, onRecordContext() {},
            children: 'overview-body',
          }));
        }

        const tick = () => new Promise(r => setTimeout(r, 0));
        // 1. Rejected restore when local finish() fails: remount preserves rejected terminal state, restorePending=false, 0 lookups, acknowledge clears without onChanged.
        w.localStorage.data.clear();
        const host1 = createHost(w);
        mountWorkspace(host1);
        await tick();
        mountWorkspace(host1);
        assert.equal(capturedCommand.host.state, 'ready');

        w.localStorage.failRemove = new Error('removeItem blocked');
        cmdImpl = async () => { throw rejectedProblem; };
        await capturedCommand.execute('restore', 'tok', {});
        mountWorkspace(host1);
        assert.equal(capturedCommand.result.kind, 'rejected');
        assert.equal(capturedCommand.maintenanceRequired, false, 'Rejected restore must not enter maintenanceRequired');
        assert.ok(capturedCommand.storageError);
        host1.unmount();

        const host2 = createHost(w);
        mountWorkspace(host2);
        await tick();
        mountWorkspace(host2);
        assert.equal(capturedCommand.result.kind, 'rejected', 'Remounted workspace preserves rejected result from shared holder');
        assert.equal(capturedCommand.storageError.message, '本机没能更新上次维护操作记录。请不要再操作，联系维护人员。',
          'Reading reports the unflushed removal in plain words instead of writing it');
        assert.equal(capturedCommand.maintenanceRequired, false);
        assert.equal(lookups, 0, 'Remounted workspace must not lookup a rejected command');

        w.localStorage.failRemove = null;
        await capturedCommand.acknowledge();
        mountWorkspace(host2);
        assert.equal(capturedCommand.intent, null);
        assert.equal(capturedCommand.result, null);
        assert.equal(capturedCommand.storageError, null);
        assert.equal(changedCalls, 0, 'Acknowledging a rejected command cleanup must not trigger onChanged');
        host2.unmount();

        // 2. Persisted reload of a completed restore from a prior session has startedHere=false, so restorePending is false when host is ready.
        w.localStorage.data.clear();
        const persistedRestore = { request_key: 'system-' + '9'.repeat(48), action: 'restore', summary: '恢复所选备份' };
        w.localStorage.setItem(w.SystemMaintenanceAPI.PENDING_KEY, JSON.stringify(persistedRestore));
        lookupImpl = async intent => ({
          kind: 'file_operation',
          terminal: true,
          operation: {
            job_ref: 'a'.repeat(32),
            request_key: intent.request_key,
            action: 'restore',
            state: 'rolled_back',
            terminal: true,
            code: 'rolled_back',
            message: '已还原',
            updated_at: '2026-10-30T08:00:00',
            audit_persisted: true,
            replayed: true,
            filename: 'b.db',
            protection_filename: 'p.db',
            history: [],
          },
        });
        const host3 = createHost(w);
        mountWorkspace(host3);
        await new Promise(r => setTimeout(r, 10));
        mountWorkspace(host3);
        assert.equal(lookups, 1);
        assert.equal(capturedCommand.result.terminal, true);
        assert.equal(capturedCommand.maintenanceRequired, false, 'Persisted restore completed in a prior session must not lock maintenanceRequired when host is ready');

        // But if host.state !== 'ready', maintenanceRequired still protects the page!
        currentHost = { ...readyHost, state: 'restart_required', restart_required: true, operations_available: false };
        await capturedCommand.inspectHost();
        mountWorkspace(host3);
        assert.equal(capturedCommand.maintenanceRequired, true, 'Non-ready host state still enforces maintenanceRequired');
        capturedCommand.acknowledge();
        host3.unmount();

        // 3. The maintenance lock is held across the command: while `a` is in flight a remounted page shows `a` and its lookup waits
        //    for the lock, so `b` cannot start before `a`'s late answer is settled. `b` then keeps its session origin
        //    (startedHere / selection) across a remount.
        const terminalOperation = (intent, state, jobRef, message) => ({
          kind: 'file_operation',
          terminal: true,
          operation: {
            job_ref: jobRef.repeat(32),
            request_key: intent.request_key,
            action: intent.action,
            state,
            terminal: true,
            code: state === 'rolled_back' ? 'rolled_back' : 'ok',
            message,
            updated_at: '2026-10-30T08:01:00',
            audit_persisted: true,
            replayed: true,
            filename: 'a.db',
            protection_filename: null,
            history: [],
          },
        });
        currentHost = readyHost;
        w.localStorage.data.clear();
        let resolveCmdA;
        cmdImpl = intent => new Promise(res => { resolveCmdA = res; });
        const host4 = createHost(w);
        mountWorkspace(host4);
        await tick();
        mountWorkspace(host4);
        const execPromiseA = capturedCommand.execute('create', 'tok', {});
        await tick();
        mountWorkspace(host4);
        const intentA = capturedCommand.intent;
        assert.ok(intentA && intentA.action === 'create');
        host4.unmount();

        lookupImpl = async intent => terminalOperation(intent, 'succeeded', 'b', '已创建');
        const lookupsBeforeA = lookups;
        const host5 = createHost(w);
        mountWorkspace(host5);
        await new Promise(r => setTimeout(r, 10));
        mountWorkspace(host5);
        assert.equal(capturedCommand.intent.request_key, intentA.request_key, 'The remounted page shows the in-flight `a`');
        assert.equal(lookups, lookupsBeforeA + 1, 'The remounted page looks `a` up');
        assert.equal(capturedCommand.result, null, "`a`'s lookup result waits for the lock held by `a`'s command");

        resolveCmdA(terminalOperation(intentA, 'succeeded', 'c', '迟到回包'));
        await execPromiseA;
        await new Promise(r => setTimeout(r, 10));
        mountWorkspace(host5);
        assert.equal(capturedCommand.result.terminal, true, "After `a`'s late answer the waiting lookup settles `a`");
        await capturedCommand.acknowledge();
        mountWorkspace(host5);
        assert.equal(capturedCommand.intent, null);

        let resolveCmdB;
        cmdImpl = () => new Promise(res => { resolveCmdB = res; });
        const selB = { key: 'bk-b', record_kind: 'backup_file' };
        const execPromiseB = capturedCommand.execute('restore', 'tok', {}, selB);
        await tick();
        mountWorkspace(host5);
        const intentB = capturedCommand.intent;
        assert.ok(intentB && intentB.action === 'restore' && intentB.request_key !== intentA.request_key);
        assert.equal(capturedCommand.maintenanceRequired, true);
        assert.deepEqual(capturedCommand.selection, selB);
        host5.unmount();

        // Remount (`host6`) while `b` is still in flight: `b` had startedHere=true, so maintenanceRequired stays true.
        lookupImpl = async intent => terminalOperation(intent, 'rolled_back', 'd', '恢复已还原');
        const host6 = createHost(w);
        mountWorkspace(host6);
        await new Promise(r => setTimeout(r, 10));
        mountWorkspace(host6);
        const inspectedB = w.SystemMaintenanceAPI.inspectPending();
        assert.equal(inspectedB.intent.request_key, intentB.request_key);
        assert.equal(inspectedB.startedHere, true, '`b` keeps startedHere === true across the remount');
        assert.deepEqual(inspectedB.selection, selB, '`b` keeps its selection across the remount');
        assert.equal(capturedCommand.intent.request_key, intentB.request_key);
        assert.equal(capturedCommand.maintenanceRequired, true, '`b` keeps maintenanceRequired === true');
        assert.deepEqual(capturedCommand.selection, selB);
        resolveCmdB(terminalOperation(intentB, 'rolled_back', 'e', '恢复已还原'));
        await execPromiseB;
        await new Promise(r => setTimeout(r, 10));
        mountWorkspace(host6);
        assert.equal(capturedCommand.result.terminal, true);
        assert.equal(capturedCommand.maintenanceRequired, true, 'A restore started here stays in maintenance until it is acknowledged');
        host6.unmount();

        // 4. R4-01 & R4-02: Once a request_key settles to terminal:true, late non-terminal lookup/error must not clobber result;
        //    and when current.intent is cleared and localStorage.getItem throws, late settle() must not resurrect the cleared intent.
        {
          const isolatedStore = createStorage();
          w.localStorage = isolatedStore;
          const p = w.SystemMaintenanceAPI.pending();
          const intentC = p.begin('create', { key: 'bk-c', record_kind: 'backup_file' });
          const terminalResult = {
            kind: 'file_operation',
            terminal: true,
            operation: {
              job_ref: 'e'.repeat(32),
              request_key: intentC.request_key,
              action: 'create',
              state: 'succeeded',
              terminal: true,
              code: 'ok',
              message: '备份完成',
              updated_at: '2026-10-30T08:04:00',
              audit_persisted: true,
              replayed: false,
              filename: 'bk-c.db',
              protection_filename: null,
              history: [],
            },
          };
          assert.ok(p.settle(intentC, terminalResult));
          assert.strictEqual(w.SystemMaintenanceAPI.inspectPending().result, terminalResult);

          // R4-01: Late non-terminal lookup or non-terminal error for the same request_key must be rejected (return null) and keep terminalResult.
          assert.equal(p.settle(intentC, { kind: 'not_recorded', message: '尚未记录', terminal: false }), null);
          assert.strictEqual(w.SystemMaintenanceAPI.inspectPending().result, terminalResult, 'R4-01: Late not_recorded lookup must not overwrite terminal result');
          assert.equal(p.settle(intentC, { terminal: false }, new Error('late lookup failed')), null);
          assert.equal(p.settle(intentC, null, new Error('late command failed')), null);
          assert.strictEqual(w.SystemMaintenanceAPI.inspectPending().result, terminalResult, 'R4-01: Late non-terminal error must not overwrite terminal result');
          assert.equal(w.SystemMaintenanceAPI.inspectPending().error, null, 'R4-01: Late non-terminal error must not attach error after terminal result');

          // Finish intentC so holder.session.intent is null, then break getItem and fire a late settle(intentC, ...).
          p.finish(intentC, true);
          assert.equal(w.SystemMaintenanceAPI.inspectPending().intent, null);
          isolatedStore.failGet = new Error('getItem unavailable');
          assert.equal(p.settle(intentC, terminalResult), null, 'R4-02: Late settle when current.intent is null and getItem throws must return null');
          assert.equal(p.settle(intentC, { kind: 'not_recorded', message: '迟到', terminal: false }, new Error('late')), null);
          assert.equal(w.SystemMaintenanceAPI.inspectPending().intent, null, 'R4-02: Cleared intent must not resurrect into holder.session when getItem throws');
          assert.equal(w.SystemMaintenanceAPI.inspectPending().result, null);
        }

        console.log(JSON.stringify({ ok: true }));
        """
    )
    assert report["ok"] is True


def test_cross_page_pending_transitions_are_serialized_by_web_locks():
    report = _run_node(
        r"""
        'use strict';
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const path = require('node:path');
        const vm = require('node:vm');
        const { randomInt } = require('node:crypto');
        const { compile } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const babelPath = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
        const files = ['WorkbenchTerms.js', 'transport.js', 'RunAdoptionAPI.js', 'RunJobAPI.js', 'TrialContract.js', 'TrialAPI.js'];
        const compiled = compile({
          babel_path: babelPath,
          sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
          check_combined: false,
        });

        // One origin = one shared localStorage plus one LockManager. Every access to the storage can fire a hook.
        function createOrigin() {
          const disk = new Map(), locks = createLockManager();
          let hook = null;
          const fire = (op, key, phase) => { if (hook) hook(op, key, phase); };
          return {
            disk, locks,
            failGet: null,
            setHook(fn) { hook = fn; },
            getItem(key) { fire('getItem', key, 'before'); if (this.failGet) throw this.failGet; const value = disk.has(key) ? disk.get(key) : null; fire('getItem', key, 'after'); return value; },
            setItem(key, value) { fire('setItem', key, 'before'); disk.set(key, String(value)); fire('setItem', key, 'after'); },
            failRemove: null,
            removeItem(key) { fire('removeItem', key, 'before'); if (this.failRemove) throw this.failRemove; disk.delete(key); fire('removeItem', key, 'after'); },
          };
        }
        // A page is an isolated realm: its globals are built inside the realm; localStorage and navigator.locks are realm
        // wrappers that only call the origin's getItem/setItem/removeItem and LockManager.request through a bridge.
        function makePage(origin) {
          const ctx = vm.createContext({});
          ctx.__host = {
            getItem: key => origin.getItem(key), setItem: (key, value) => origin.setItem(key, value), removeItem: key => origin.removeItem(key),
            request: (name, options, callback) => origin.locks.request(name, options, callback), byte: () => randomInt(256),
          };
          vm.runInContext(`
            'use strict';
            const host = globalThis.__host;
            delete globalThis.__host;
            globalThis.window = globalThis;
            const listeners = new Map();
            globalThis.addEventListener = (type, fn) => { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); };
            globalThis.removeEventListener = (type, fn) => { if (listeners.has(type)) listeners.get(type).delete(fn); };
            globalThis.dispatchEvent = event => { for (const fn of listeners.get(event.type) || []) fn(event); return true; };
            globalThis.CustomEvent = class CustomEvent { constructor(type, init) { this.type = type; this.detail = init && init.detail; } };
            globalThis.crypto = { getRandomValues(bytes) { for (let i = 0; i < bytes.length; i++) bytes[i] = host.byte(); return bytes; } };
            globalThis.localStorage = { getItem: key => host.getItem(key), setItem: (key, value) => host.setItem(key, value), removeItem: key => host.removeItem(key) };
            globalThis.navigator = { locks: { request: (name, options, callback) => new Promise((resolve, reject) => {
              host.request(name, options, lock => callback(lock ? { name, mode: 'exclusive' } : null)).then(resolve, reject);
            }) } };
          `, ctx);
          for (const out of compiled.outputs) vm.runInContext(out.code, ctx, { filename: out.path });
          return ctx;
        }
        const settled = promise => promise.then(value => ({ value }), error => ({ error }));
        // A runs its locked transition; at the chosen storage access the hook only launches B's locked transition.
        // Both are awaited before any assertion.
        async function interleave(origin, point, runA, launchB) {
          let fired = false, launched = null;
          origin.setHook((op, key, phase) => {
            if (!fired && op === point.op && key === point.key && phase === point.phase) { fired = true; launched = settled(launchB()); }
          });
          const a = await settled(runA());
          origin.setHook(null);
          assert.ok(launched, `The hook fired at ${point.op}/${point.phase}`);
          return { a, b: await launched };
        }
        const ref = n => n.toString(16).padStart(48, '0');
        const inputA = 'a'.repeat(32), inputB = 'b'.repeat(32), ctxRef = JSON.stringify({ database_scope: 'db', successful_restores: [] });
        const accesses = key => ['getItem', 'setItem'].flatMap(op => ['before', 'after'].map(phase => ({ op, key, phase })));
        const cases = [];

        // Codex probe: A's poll finishes X while B, in one locked section, finishes X and begins Y. Whatever access of A launches B,
        // B runs after A: PENDING ends as Y and RECENT keeps A's conclusion for X.
        {
          const probe = createOrigin(), seed = makePage(probe);
          const KEY = seed.RunJobAPI.PENDING_KEY, RECENT = seed.RunJobAPI.RECENT_KEY;
          const points = [{ op: 'getItem', key: KEY }, { op: 'removeItem', key: KEY }, { op: 'setItem', key: RECENT }]
            .flatMap(point => ['before', 'after'].map(phase => ({ ...point, phase })));
          for (const point of points) {
            const origin = createOrigin(), pageA = makePage(origin), pageB = makePage(origin);
            const TA = pageA.APSWorkbenchTransport, TB = pageB.APSWorkbenchTransport;
            const x = pageA.RunJobAPI.pending().attach(pageA.RunJobAPI.pending().begin(inputA, ctxRef), ref(1));
            const { a, b } = await interleave(origin, point,
              () => TA.exclusive(KEY, { wait: true }, () => pageA.RunJobAPI.pending().finish(x, 'found')),
              () => TB.exclusive(KEY, { wait: true }, () => {
                pageB.RunJobAPI.pending().finish(x, 'found');
                return pageB.RunJobAPI.pending().begin(inputB, ctxRef);
              }));
            const label = `${point.op}/${point.key === KEY ? 'PENDING' : 'RECENT'}/${point.phase}`;
            assert.ok(!a.error && !b.error, `Both pages complete (${label})`);
            assert.equal(b.value.acquired, true, `B's section runs after A released the lock (${label})`);
            const y = b.value.value;
            assert.equal(JSON.parse(origin.disk.get(KEY)).request_key, y.request_key, `B's new pending intent survives (${label})`);
            const recent = JSON.parse(origin.disk.get(RECENT));
            assert.equal(recent.intent.request_key, x.request_key, `RECENT keeps the conclusion for X (${label})`);
            assert.equal(pageA.RunJobAPI.pending().read().request_key, y.request_key, `Page A reads B's intent (${label})`);
            cases.push('probe:' + label);
          }
        }

        // TrialAPI double reserve: whichever access of A's reserve launches B, exactly one key is admitted.
        // ifAvailable refuses B at once; a waiting B runs after A and meets the conflict.
        for (const wait of [false, true]) {
          for (const point of accesses('aps_workbench_trial_pending_v1')) {
            const origin = createOrigin(), pageA = makePage(origin), pageB = makePage(origin);
            const KEY = pageA.TrialAPI.PENDING_KEY;
            const { a, b } = await interleave(origin, point,
              () => pageA.APSWorkbenchTransport.exclusive(KEY, {}, () => pageA.TrialAPI.reserve()),
              () => pageB.APSWorkbenchTransport.exclusive(KEY, { wait }, () => pageB.TrialAPI.reserve()));
            const label = `${wait ? 'wait' : 'ifAvailable'} ${point.op}/${point.phase}`;
            assert.equal(a.value.acquired, true);
            if (wait) assert.match(b.error.message, /试调提交/, `A waiting reserve meets the conflict (${label})`);
            else assert.equal(b.value.acquired, false, `ifAvailable refuses the second reserve (${label})`);
            assert.equal(origin.disk.get(KEY), a.value.value, `Only A's key is stored (${label})`);
            cases.push('trial:' + label);
          }
        }

        // RunJob begin | begin: exactly one submission is admitted.
        for (const point of accesses('aps_workbench_run_pending_v1')) {
          const origin = createOrigin(), pageA = makePage(origin), pageB = makePage(origin);
          const KEY = pageA.RunJobAPI.PENDING_KEY;
          const { a, b } = await interleave(origin, point,
            () => pageA.APSWorkbenchTransport.exclusive(KEY, {}, () => pageA.RunJobAPI.pending().begin(inputA, ctxRef)),
            () => pageB.APSWorkbenchTransport.exclusive(KEY, { wait: true }, () => pageB.RunJobAPI.pending().begin(inputB, ctxRef)));
          assert.equal(a.value.acquired, true);
          assert.match(b.error.message, /上次排产还没确认结果/, `The second begin is refused (${point.op}/${point.phase})`);
          assert.equal(JSON.parse(origin.disk.get(KEY)).request_key, a.value.value.request_key);
          cases.push(`run-begin:${point.op}/${point.phase}`);
        }

        // attach | reject+begin: A's poll attaches the run; B (holding the same unattached intent) rejects it and begins anew.
        // B runs after A, so its stale reject conflicts and B begins nothing; A's attach is not lost.
        for (const point of accesses('aps_workbench_run_pending_v1')) {
          const origin = createOrigin(), pageA = makePage(origin), pageB = makePage(origin);
          const KEY = pageA.RunJobAPI.PENDING_KEY;
          const x = pageA.RunJobAPI.pending().begin(inputA, ctxRef);
          const { a, b } = await interleave(origin, point,
            () => pageA.APSWorkbenchTransport.exclusive(KEY, { wait: true }, () => pageA.RunJobAPI.pending().attach(x, ref(2))),
            () => pageB.APSWorkbenchTransport.exclusive(KEY, { wait: true }, () => {
              pageB.RunJobAPI.pending().reject(x);
              return pageB.RunJobAPI.pending().begin(inputB, ctxRef);
            }));
          assert.equal(a.value.value.run_ref, ref(2));
          assert.equal(b.error.conflict, true, `B's stale reject conflicts (${point.op}/${point.phase})`);
          const stored = JSON.parse(origin.disk.get(KEY));
          assert.equal(stored.request_key, x.request_key);
          assert.equal(stored.run_ref, ref(2), `A's attach is kept (${point.op}/${point.phase})`);
          cases.push(`attach-reject:${point.op}/${point.phase}`);
        }

        // Between two lock sections a stale caller cannot remove or re-attach a newer intent, and a repeated finish is a no-op
        // that keeps RECENT's first conclusion.
        {
          const origin = createOrigin(), pageA = makePage(origin), pageB = makePage(origin);
          const TA = pageA.APSWorkbenchTransport, TB = pageB.APSWorkbenchTransport, KEY = pageA.RunJobAPI.PENDING_KEY, RECENT = pageA.RunJobAPI.RECENT_KEY;
          const pA = pageA.RunJobAPI.pending(), pB = pageB.RunJobAPI.pending();
          const { value: x } = await TA.exclusive(KEY, {}, () => pA.begin(inputA, ctxRef));
          const { value: xa } = await TA.exclusive(KEY, { wait: true }, () => { const attached = pA.attach(x, ref(3)); pA.finish(attached, 'found'); return attached; });
          const { value: y } = await TB.exclusive(KEY, {}, () => pB.begin(inputB, ctxRef));
          await assert.rejects(TA.exclusive(KEY, { wait: true }, () => pA.finish(xa, 'found')), err => err.conflict === true && /上次操作记录已变化/.test(err.message));
          await assert.rejects(TA.exclusive(KEY, { wait: true }, () => pA.attach(x, ref(3))), /上次操作记录已变化/);
          assert.equal(JSON.parse(origin.disk.get(KEY)).request_key, y.request_key, 'Stale callers leave the newer intent in place');
          assert.equal(JSON.parse(origin.disk.get(RECENT)).intent.request_key, xa.request_key, 'Stale callers leave RECENT untouched');
          const { value: ya } = await TB.exclusive(KEY, { wait: true }, () => { const attached = pB.attach(y, ref(4)); pB.finish(attached, 'found'); return attached; });
          const recentRaw = origin.disk.get(RECENT);
          await TA.exclusive(KEY, { wait: true }, () => pA.finish(ya, 'context_replaced'));
          await TA.exclusive(KEY, { wait: true }, () => pA.finish(xa, 'found'));
          assert.equal(origin.disk.has(KEY), false);
          assert.equal(origin.disk.get(RECENT), recentRaw, 'Repeated and late finishes are no-ops');
          assert.equal(pA.recent().resolution, 'found');
          assert.equal(pA.recent().intent.request_key, ya.request_key);
          cases.push('stale-between-locks');
        }

        // 5f. Pages of two origins have separate storage and separate locks; interleaving writes to the same key never mixes them.
        {
          const origin1 = createOrigin(), origin2 = createOrigin(), page1 = makePage(origin1), page2 = makePage(origin2);
          let intent2 = null;
          origin1.setHook((op, key, phase) => {
            if (!intent2 && op === 'setItem' && key === page1.RunJobAPI.PENDING_KEY && phase === 'before') intent2 = page2.RunJobAPI.pending().begin(inputB, ctxRef);
          });
          const intent1 = page1.RunJobAPI.pending().begin(inputA, ctxRef);
          origin1.setHook(null);
          assert.ok(intent1 && intent2, '5f: Nested begin on distinct origins both succeed');
          assert.equal(page1.RunJobAPI.pending().read().request_key, intent1.request_key);
          assert.equal(page2.RunJobAPI.pending().read().request_key, intent2.request_key);
        }

        // 5i. When store A's storage() getter throws, its settling save is kept for store A alone and flushed to A's own storage
        // once the getter recovers; store B on another storage object with the same key is untouched.
        {
          const page = makePage(createOrigin());
          const storageA = createOrigin(), storageB = createOrigin();
          let throwA = false;
          const options = { key: 'rf2_shared_key', readError: 'read err', conflictError: 'conflict err', writeError: 'write err' };
          const sa = page.APSWorkbenchTransport.pendingStore({ ...options, storage: () => { if (throwA) throw new Error('storage A unavailable'); return storageA; } });
          const sb = page.APSWorkbenchTransport.pendingStore({ ...options, storage: () => storageB });
          const intent = { phase: 'pending', id: 1 };
          sa.save(intent, null);
          sb.save(intent, null);
          throwA = true;
          let settleErr = null;
          try { sa.save(null, intent); } catch (err) { settleErr = err; }
          assert.ok(settleErr && settleErr.saved === null, '5i: Store A records saved=null');
          assert.equal(JSON.stringify(sb.read()), JSON.stringify(intent), '5i: Store B keeps its record');
          assert.ok(storageB.disk.has('rf2_shared_key'));
          throwA = false;
          assert.equal(sa.flush(), null, '5i: Store A flushes its own null once storage A recovers');
          assert.equal(storageA.disk.has('rf2_shared_key'), false);
        }

        // 5u. Polling and the accept receipt may both attach the same run_ref from the original intent (run_ref null): the repeat is a no-op.
        // Another run_ref is a conflict, also when storage reads fail; the same target with unreadable storage only reports the read failure.
        {
          const origin = createOrigin(), p = makePage(origin).RunJobAPI.pending();
          const original = p.begin(inputA, ctxRef), runRef = 'e'.repeat(48), otherRef = 'f'.repeat(48);
          p.attach(original, runRef);
          const repeated = p.attach(original, runRef);
          assert.equal(repeated.request_key, original.request_key);
          assert.equal(repeated.run_ref, runRef, '5u: Repeated attach of the same run_ref succeeds');
          assert.throws(() => p.attach(original, otherRef), /上次操作记录已变化/, '5u: Attaching another run_ref is a conflict');
          origin.failGet = new Error('getItem blocked');
          assert.throws(() => p.attach(original, runRef), err => err.conflict !== true && /读不到上次排产的操作记录/.test(err.message),
            '5u: With unreadable storage the same target only reports the read failure');
          assert.throws(() => p.attach(original, otherRef), /上次操作记录已变化/, '5u: With unreadable storage another run_ref is still a conflict');
          origin.failGet = null;
          assert.equal(p.read().run_ref, runRef, '5u: The stored intent keeps the first run_ref');
        }

        // RF13-01: page A keeps an unflushed removal of X. Its lock-free read() gets X from getItem; before A resumes, page B, holding the
        // lock, finishes X and begins Y. A's read() only reports its record and never writes, so Y survives; A's locked flush then reads Y.
        {
          const origin = createOrigin(), pageA = makePage(origin), pageB = makePage(origin);
          const TA = pageA.APSWorkbenchTransport, TB = pageB.APSWorkbenchTransport;
          const KEY = pageA.RunJobAPI.PENDING_KEY, pA = pageA.RunJobAPI.pending(), pB = pageB.RunJobAPI.pending();
          const { value: x } = await TA.exclusive(KEY, {}, () => pA.attach(pA.begin(inputA, ctxRef), ref(30)));
          origin.failRemove = new Error('removeItem blocked');
          await assert.rejects(TA.exclusive(KEY, { wait: true }, () => pA.finish(x, 'found')), err => err.saved === null && /无法更新/.test(err.message));
          origin.failRemove = null;
          const writesByA = [];
          let inB = false;
          const watchA = extra => origin.setHook((op, key, phase) => {
            if (!inB && op !== 'getItem') writesByA.push(op + ':' + key);
            if (extra) extra(op, key, phase);
          });
          watchA();
          assert.throws(() => pA.read(), err => err.saved === null && /无法更新/.test(err.message), 'RF13-01: read() reports the unflushed removal');
          assert.equal(JSON.parse(origin.disk.get(KEY)).request_key, x.request_key, 'RF13-01: read() leaves X on disk');
          let bWork = null, releaseB = null, bReady = null, y = null, newBeforeResume = null;
          const bHeld = new Promise(resolve => { bReady = resolve; });
          const bDone = TB.exclusive(KEY, { wait: true }, () => new Promise(release => {
            bWork = () => { inB = true; pB.finish(x, 'found'); y = pB.begin(inputB, ctxRef); inB = false; };
            releaseB = release; bReady();
          }));
          await bHeld;
          watchA((op, key, phase) => {
            if (inB || newBeforeResume !== null || op !== 'getItem' || key !== KEY || phase !== 'after') return;
            bWork();
            newBeforeResume = JSON.parse(origin.disk.get(KEY)).request_key === y.request_key;
          });
          assert.throws(() => pA.read(), err => err.saved === null && /无法更新/.test(err.message), 'RF13-01: A read X, so it still reports its removal');
          origin.setHook(null);
          releaseB(); assert.equal((await bDone).acquired, true);
          console.log('new before A resumes: ' + newBeforeResume);
          assert.equal(newBeforeResume, true, 'RF13-01: B wrote Y before A resumed');
          assert.deepEqual(writesByA, [], 'RF13-01: a lock-free read() never calls setItem/removeItem');
          assert.equal(JSON.parse(origin.disk.get(KEY)).request_key, y.request_key, 'RF13-01: B new record survives A read()');
          const { value: flushed } = await TA.exclusive(KEY, { wait: true }, () => pA.flush());
          assert.equal(flushed.request_key, y.request_key, 'RF13-01: A locked flush drops its stale record and returns Y');
          assert.equal(JSON.parse(origin.disk.get(KEY)).request_key, y.request_key);
          assert.equal(pA.read().request_key, y.request_key);
          cases.push('rf13-01');
        }
        // RF13-02: a finish whose getItem failed keeps its RECENT write with the unflushed removal. Each consumer of that record (locked flush,
        // the issuer's repeated finish, a new begin on the same page) writes RECENT first; a successful RECENT write is not repeated.
        for (const consumer of ['flush', 'retry', 'begin']) {
          const origin = createOrigin(), page = makePage(origin), TP = page.APSWorkbenchTransport, p = page.RunJobAPI.pending();
          const KEY = page.RunJobAPI.PENDING_KEY, RECENT = page.RunJobAPI.RECENT_KEY;
          const { value: x } = await TP.exclusive(KEY, {}, () => p.attach(p.begin(inputA, ctxRef), ref(31)));
          origin.failGet = new Error('getItem blocked');
          await assert.rejects(TP.exclusive(KEY, { wait: true }, () => p.finish(x, 'found')), err => err.saved === null && /读不到上次排产的操作记录/.test(err.message));
          origin.failGet = null;
          assert.equal(origin.disk.has(RECENT), false, `RF13-02: RECENT is not written while getItem fails (${consumer})`);
          let recentWrites = 0, y = null;
          origin.setHook((op, key, phase) => { if (op === 'setItem' && key === RECENT && phase === 'after') recentWrites++; });
          if (consumer === 'flush') {
            origin.failRemove = new Error('removeItem blocked');
            await assert.rejects(TP.exclusive(KEY, { wait: true }, () => p.flush()), err => err.saved === null && /无法更新/.test(err.message));
            origin.failRemove = null;
            assert.equal(recentWrites, 1, 'RF13-02: RECENT is written before the failed removal');
          }
          await TP.exclusive(KEY, { wait: true }, () => {
            if (consumer === 'flush') assert.equal(p.flush(), null);
            else if (consumer === 'retry') p.finish(x, 'found');
            else y = p.begin(inputB, ctxRef);
          });
          origin.setHook(null);
          assert.equal(recentWrites, 1, `RF13-02: RECENT is written exactly once (${consumer})`);
          const recent = JSON.parse(origin.disk.get(RECENT));
          assert.equal(JSON.stringify(recent.intent), JSON.stringify(x), `RF13-02: RECENT keeps intent X (${consumer})`);
          assert.equal(recent.resolution, 'found');
          if (consumer === 'begin') {
            assert.equal(JSON.parse(origin.disk.get(KEY)).request_key, y.request_key, 'RF13-02: the new begin replaces the deferred removal');
          } else {
            assert.equal(origin.disk.has(KEY), false, `RF13-02: PENDING is removed (${consumer})`);
            assert.equal(p.read(), null);
          }
          cases.push('rf13-02:' + consumer);
        }

        console.log(JSON.stringify({ ok: true, cases }));
        """
    )
    assert report["ok"] is True
    assert len(report["cases"]) == 6 + 8 + 4 + 4 + 1 + 1 + 3
