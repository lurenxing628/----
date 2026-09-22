'use strict';
// 无浏览器合同：新增工种弹窗点「刷新最新资料」后，新读到的建档资料要直接接进保存路径（writeContext 不能变成 null），
// 复核区只展示当前资料，不再要求单独的“采用”步骤——否则保存会一直被“还没读到可以保存的资料”拦住（2026-09-21 复审第 1 条）。
// 编译 ProcessOpTypeCreate.jsx 后用最小 hooks 运行时渲染；ResourceForms / Modal / Button 只记录收到的 props。
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [{ path: 'ProcessOpTypeCreate.jsx', code: fs.readFileSync(path.join(root, 'frontend/workbench/app/ProcessOpTypeCreate.jsx'), 'utf8') }] }).outputs[0].code;

// 最小 hooks 运行时：只支持函数组件顶层顺序调用的 useState / useEffect / useRef / useMemo / useId / useReducer，够渲染这个弹窗。
function createRuntime() {
  const hooks = []; let cursor = 0, dirty = false, effects = [], component = null, props = null;
  const slot = init => { const value = hooks[cursor] || (hooks[cursor] = init()); cursor++; return value; };
  const React = {
    Fragment: Symbol('Fragment'),
    createElement: (type, attributes, ...children) => ({ type, props: attributes || {}, children }),
    useState(initial) {
      const entry = slot(() => ({ value: typeof initial === 'function' ? initial() : initial }));
      if (!entry.set) entry.set = next => { const value = typeof next === 'function' ? next(entry.value) : next; if (!Object.is(value, entry.value)) { entry.value = value; dirty = true; } };
      return [entry.value, entry.set];
    },
    useReducer(reducer, initial) {
      const entry = slot(() => ({ value: initial }));
      if (!entry.dispatch) entry.dispatch = action => { entry.value = reducer(entry.value, action); dirty = true; };
      return [entry.value, entry.dispatch];
    },
    useRef(initial) { return slot(() => ({ current: initial })); },
    useMemo(factory, deps) {
      const entry = slot(() => ({}));
      if (!entry.has || !deps || !entry.deps || deps.some((value, index) => !Object.is(value, entry.deps[index]))) { entry.value = factory(); entry.deps = deps; entry.has = true; }
      return entry.value;
    },
    useId() { return slot(() => ({ id: ':r' + hooks.length + ':' })).id; },
    useEffect(create, deps) {
      const entry = slot(() => ({}));
      const changed = !entry.mounted || !deps || !entry.deps || deps.length !== entry.deps.length || deps.some((value, index) => !Object.is(value, entry.deps[index]));
      entry.deps = deps; entry.mounted = true;
      if (changed) effects.push({ entry, create });
    }
  };
  function mount(node) {
    if (node === null || node === undefined || typeof node === 'boolean' || typeof node !== 'object') return;
    if (Array.isArray(node)) { node.forEach(mount); return; }
    if (typeof node.type === 'function') { mount(node.type({ ...node.props, children: node.children })); return; }
    mount(node.children);
  }
  function render() {
    let guard = 0;
    do {
      dirty = false; cursor = 0; effects = [];
      mount(React.createElement(component, props));
      for (const { entry, create } of effects) { if (typeof entry.cleanup === 'function') entry.cleanup(); const cleanup = create(); entry.cleanup = typeof cleanup === 'function' ? cleanup : null; }
    } while (dirty && ++guard < 20);
    if (dirty) throw new Error('渲染没有收敛');
  }
  return { React, start(target, initialProps) { component = target; props = initialProps; render(); }, flush() { if (dirty) render(); } };
}

const runtime = createRuntime();
const context = vm.createContext({ React: runtime.React, console, AbortController });
context.window = context;
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/WorkbenchTerms.js'), 'utf8'), context);
const captured = { forms: [], buttons: [], resets: 0 };
// 合同只看弹窗自身的流程；数据外壳校验由 resource-contract 自己的合同锁，这里最小化替身。
context.APSResourceContract = {
  query: (value, shape) => { if (!value || value.ok !== true || !value.data || !value.meta) throw new Error('bad envelope: ' + shape); return value; },
  failure: message => Object.assign(new Error(message), { code: 'contract' }), resultRef: () => null
};
let listResults = [], command = { phase: 'idle', locked: false, intent: null, result: null, reset() { captured.resets++; return !command.locked; } };
context.APSResourceSession = {
  useCommand: () => command,
  useQuery: (load, deps, enabled = true) => ({ loading: false, error: null, result: enabled ? listResults[0] : null, reload() {} })
};
context.ResourceControls = { Button: props => { captured.buttons.push(props); return null; }, Modal: props => props.children, ErrorBox: () => null };
context.ResourceForms = props => { captured.forms.push(props); return null; };
context.ResourceForms.Feedback = () => null;
vm.runInContext(compiled, context);

const envelope = token => ({ ok: true, schema_version: 1, data: { entities: [], page: { number: 1, size: 20, total: 0, pages: 1 }, create_context: { write_token: token, write_scope: 'op_type:create' } },
  meta: { source: 'production', time_basis: 'factory_local', snapshot_ref: 's'.repeat(32), request_ref: 'op-type-create-' + token, as_of: '2026-09-21T09:00:00' }, warnings: [] });
// 首次读取由 useQuery 替身直接给出 first-token；之后每次真正调用 adapter.list 才拿到新读到的 fresh-token。
const listed = [], responses = [envelope('fresh-token')];
const adapter = { async list(kind, scope, signal) { listed.push({ kind, scope, aborted: signal && signal.aborted }); return responses.shift() || listResults[0]; } };
listResults = [envelope('first-token')];
let checks = 0;
const check = (condition, message) => { assert(condition, message); checks++; };
const latest = () => captured.forms[captured.forms.length - 1];

runtime.start(context.ProcessOpTypeCreate, { adapter, onClose() {}, onCommitted() {} });
check(latest() && latest().action === 'create' && latest().kind === 'op_type', '首次读取后应进入 ResourceForms 新增表单');
check(latest().writeContext && latest().writeContext.write_token === 'first-token', '首次读到的建档资料直接进保存路径');
check(latest().contextReview === null, '首次进入没有复核区');

(async () => {
  const before = captured.forms.length;
  await latest().onReloadContext();
  runtime.flush();
  check(captured.forms.length > before, '刷新后应重新渲染表单');
  check(latest().contextReview && latest().contextReview.data.create_context.write_token === 'fresh-token', '复核区展示新读到的资料');
  check(latest().writeContext && latest().writeContext.write_token === 'fresh-token', '刷新即采用：保存路径拿到的是新读到的建档资料');
  check(captured.forms.slice(1).every(props => props.writeContext !== null), '复核期间 writeContext 不能为 null，否则保存被永久拦住');
  check(!latest().contextBusy && latest().contextError === null, '刷新结束后不再忙碌、没有错误');
  check(captured.resets >= 2 && listed.length === 1 && listed[0].kind === 'op_type', '刷新经过 command.reset，并只按工种重新读了一次列表');
  check(typeof latest().onAcceptContext !== 'function', '不再单独提供“采用”步骤');
  command.locked = true;
  await latest().onReloadContext();
  runtime.flush();
  check(listed.length === 1, '结果待确认（locked）时不发起刷新');
  process.stdout.write(JSON.stringify({ checks, browser: false, database: false }));
})().catch(error => { console.error(error); process.exitCode = 1; });
