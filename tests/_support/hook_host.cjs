'use strict';
// Node 契约共用的有状态 hook 宿主（不是 React）。
// 一个组件实例一份 hook 单元，按调用顺序排列（与 React 相同），状态跨渲染保留；effect 在 flush 时按提交顺序执行，
// 重跑前先执行上一次的 cleanup。一轮渲染（pass）里没再渲染到的实例视为卸载：丢弃它未执行的 effect，执行全部 cleanup。
// 实例身份由驱动方给出：展开组件树时是位置路径 + key + 组件函数，key 一变就是新实例；独立挂载时是驱动方自定的名字。
const sameDeps = (left, right) => Array.isArray(left) && Array.isArray(right) && left.length === right.length
  && left.every((value, index) => Object.is(value, right[index]));

function createHookHost() {
  let current = null, ids = 0;
  function cell(create) {
    if (!current) throw new Error('Hooks need a mounted component instance');
    const instance = current, index = instance.cursor++;
    if (!(index in instance.cells)) instance.cells[index] = create(instance);
    return instance.cells[index];
  }
  function state(initial, reduce) {
    const slot = cell(instance => ({ instance, value: typeof initial === 'function' ? initial() : initial }));
    slot.reduce = reduce;
    if (!slot.dispatch) slot.dispatch = action => {
      const next = slot.reduce(slot.value, action);
      if (!slot.instance.alive || Object.is(next, slot.value)) return;
      slot.value = next; slot.instance.dirty = true; slot.instance.scope.changed = true;
    };
    return [slot.value, slot.dispatch];
  }
  const setValue = (value, next) => typeof next === 'function' ? next(value) : next;
  function useMemo(factory, deps) {
    const slot = cell(() => ({}));
    if (!('deps' in slot) || !sameDeps(slot.deps, deps)) { slot.value = factory(); slot.deps = deps; }
    return slot.value;
  }
  function useEffect(effect, deps) {
    const slot = cell(instance => { const created = { cleanup: null }; instance.effects.push(created); return created; });
    if ('deps' in slot && sameDeps(slot.deps, deps)) return;
    slot.deps = deps;
    current.pending.push(() => { const cleanup = slot.cleanup; slot.cleanup = null; if (cleanup) cleanup(); slot.cleanup = effect(); });
  }
  const hooks = {
    useState: initial => state(initial, setValue),
    useReducer: (reducer, initialArg, init) => state(() => init ? init(initialArg) : initialArg, reducer),
    useRef: initial => cell(() => ({ current: initial })),
    useMemo, useCallback: (callback, deps) => useMemo(() => callback, deps),
    useEffect, useLayoutEffect: useEffect,
    useId: () => cell(() => ({ id: ':hook-' + (++ids) + ':' })).id,
  };
  function dispose(instance) {
    instance.alive = false; instance.pending = [];
    for (const slot of instance.effects) { const cleanup = slot.cleanup; slot.cleanup = null; if (cleanup) cleanup(); }
  }
  // 一组同时挂载的实例（一棵组件树或一个页面）：自己的实例表与 effect 队列。
  function scope() {
    const instances = new Map(), queue = []; let seen = null;
    const self = {
      changed: false,
      // 一轮渲染：fn 里 enter 过的实例保持挂载，其余卸载。
      pass(fn) {
        const previous = seen; seen = new Set(); self.changed = false;
        try { return fn(); } finally {
          const live = seen; seen = previous;
          for (const [identity, instance] of instances) if (!live.has(identity)) { instances.delete(identity); dispose(instance); }
        }
      },
      enter(identity) {
        let instance = instances.get(identity);
        if (!instance) instances.set(identity, instance = { identity, scope: self, cells: [], cursor: 0, effects: [], pending: [], alive: true, dirty: false });
        if (seen) seen.add(identity);
        return instance;
      },
      run(instance, fn) {
        const previous = current; current = instance; instance.cursor = 0; instance.dirty = false;
        try { return fn(); } finally { current = previous; }
      },
      commit(instance) { for (const run of instance.pending) queue.push({ instance, run }); instance.pending = []; },
      // 独立挂载的一个实例：渲染后立即提交它的 effect。
      render(identity, fn) { const instance = self.enter(identity), output = self.run(instance, fn); self.commit(instance); return output; },
      instance: identity => instances.get(identity),
      get pending() { return queue.length > 0; },
      flush() { while (queue.length) { const { instance, run } = queue.shift(); if (instance.alive) run(); } },
      unmount() { queue.length = 0; for (const instance of instances.values()) dispose(instance); instances.clear(); },
    };
    return self;
  }
  return { hooks, scope };
}

function walk(tree) {
  if (tree === null || tree === undefined) return [];
  if (Array.isArray(tree)) return tree.flatMap(walk);
  if (typeof tree !== 'object') return [];
  return [tree, ...walk(tree.children)];
}

// 展开真实 React 元素的组件树驱动。React 是页面加载的 React 运行时（只用它的 createElement / isValidElement / Fragment /
// createContext）；hooks 给页面上的 React 用。挂载的一棵树里，组件实例身份是位置路径 + key + 组件函数：key 或组件一变就是新实例，
// 这一轮没再渲染到的位置卸载并执行 cleanup。状态变化后只重跑变了的组件和父组件给了新元素的组件（同 React 的跳过规则）。
// 宿主节点展开成 {type, props, children}；对象 ref 拿到 refNode() 造的替身 DOM 节点，挂在节点的不可枚举属性 dom 上。
function createTreeHost(React, { refNode = () => ({}) } = {}) {
  const host = createHookHost(), contextValues = new Map(), providerType = React.createContext(null).Provider.$$typeof;
  const useContext = context => contextValues.has(context) ? contextValues.get(context) : context._currentValue;
  function mount(component, props) {
    const scope = host.scope(), rendered = new WeakMap(), providers = new Map(), ids = new Map();
    let element = React.createElement(component, props), tree = null, types = 0;
    const idOf = type => { if (!ids.has(type)) ids.set(type, ++types); return ids.get(type); };
    function expand(node, at, force) {
      if (node === null || node === undefined || typeof node === 'boolean') return null;
      if (typeof node === 'string' || typeof node === 'number') return node;
      if (Array.isArray(node)) return node.map((child, index) => expand(child, at + (child && child.key != null ? '' : '.' + index), force));
      if (!React.isValidElement(node)) throw new Error('Only actual React elements may be expanded');
      const path = node.key != null ? at + '#' + node.key : at;
      if (node.type === React.Fragment) return expand(node.props.children, path + '<>', force);
      if (node.type && node.type.$$typeof === providerType) {
        const context = node.type._context, hadValue = contextValues.has(context), previous = contextValues.get(context);
        const changed = !providers.has(path) || !Object.is(providers.get(path), node.props.value);
        providers.set(path, node.props.value); contextValues.set(context, node.props.value);
        try { return expand(node.props.children, path + '<provider>', force || changed); }
        finally { if (hadValue) contextValues.set(context, previous); else contextValues.delete(context); }
      }
      if (typeof node.type === 'function') {
        if (node.type.prototype && node.type.prototype.isReactComponent) return expand(new node.type(node.props).render(), path + '<class>', force);
        const identity = path + '<' + idOf(node.type) + '>', instance = scope.enter(identity), last = rendered.get(instance);
        let child;
        if (force || instance.dirty || !last || last.element !== node) {
          child = scope.run(instance, () => node.type(node.props)); rendered.set(instance, { element: node, child });
        } else child = last.child;
        const output = expand(child, identity + '/', force);
        // Like React, a component's effects commit after its children's.
        scope.commit(instance);
        return output;
      }
      if (typeof node.type !== 'string') throw new Error('A required component dependency is missing or unsupported in the inspected surface');
      if (Object.prototype.hasOwnProperty.call(node.props, 'dangerouslySetInnerHTML')) throw new Error('Raw HTML is forbidden on this surface');
      const dom = node.ref && typeof node.ref === 'object' ? node.ref.current || (node.ref.current = refNode()) : null;
      const output = { type: node.type, props: node.props, children: expand(node.props.children, path + '<' + node.type + '>', force) };
      if (dom) Object.defineProperty(output, 'dom', { value: dom });
      return output;
    }
    const paint = () => { tree = scope.pass(() => expand(element, '', false)); return tree; };
    paint();
    return {
      get tree() { return tree; },
      get nodes() { return walk(tree); },
      // New props for the root: the root component renders again with them.
      render(nextProps = element.props) { element = React.createElement(component, nextProps); return paint(); },
      // Render the components whose state changed since the last paint, without committing effects.
      update: paint,
      // Commit the pending effects, let started promises answer and render the changed components, until nothing changes.
      async settle(rounds = 30) {
        for (let round = 0, idle = 0; round < rounds; round++) {
          scope.flush();
          await new Promise(resolve => setImmediate(resolve));
          if (scope.changed) { paint(); idle = 0; } else if (!scope.pending && ++idle >= 3) return tree;
        }
        throw new Error('The mounted tree did not settle within ' + rounds + ' rounds');
      },
      unmount() { scope.unmount(); },
    };
  }
  return { hooks: { ...host.hooks, useContext }, mount };
}

module.exports = { createHookHost, createTreeHost, walk };
