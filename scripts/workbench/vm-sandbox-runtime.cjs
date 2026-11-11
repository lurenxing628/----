'use strict';

const REACT_NAMED_EXPORTS = [
  'default', 'hasVendorRuntime', 'createRoot', 'createPortal', 'flushSync',
  'useState', 'useEffect', 'useLayoutEffect', 'useMemo', 'useCallback', 'useRef',
  'useId', 'useReducer', 'useContext', 'createContext',
  'Fragment', 'Component', 'createElement', 'cloneElement', 'isValidElement', 'Children',
];

function normalizeRelPath(rawPath) {
  if (typeof rawPath !== 'string' || !rawPath.trim()) throw new Error('Source path must be a non-empty string');
  let clean = rawPath.trim().replace(/\\/g, '/');
  if (clean.startsWith('/') || /^[A-Za-z]:/.test(clean)) {
    throw new Error('Missing module in frontend/workbench/app: ' + rawPath);
  }
  clean = clean.replace(/^(\.\/)+/, '');
  if (clean.startsWith('frontend/workbench/app/')) clean = clean.slice('frontend/workbench/app/'.length);
  else if (clean.startsWith('app/')) clean = clean.slice('app/'.length);
  const stack = [];
  for (const seg of clean.split('/')) {
    if (!seg || seg === '.') continue;
    if (seg === '..') {
      if (stack.length > 0 && stack[stack.length - 1] !== '..') stack.pop();
      else stack.push('..');
    } else {
      stack.push(seg);
    }
  }
  clean = stack.join('/');
  if (!clean || clean === '..' || clean.startsWith('../')) {
    throw new Error('Missing module in frontend/workbench/app: ' + rawPath);
  }
  return clean;
}

const HOOK_EXPORTS = REACT_NAMED_EXPORTS.slice(5);

const SANDBOX_RUNTIME_CODE = `(function (__g) {
  function getWin() { return (__g.window && typeof __g.window === 'object') ? __g.window : __g; }
  function isObjOrFn(v) { return Boolean(v && (typeof v === 'object' || typeof v === 'function')); }
  const normalizeRel = ${normalizeRelPath.toString()};
  function getState() {
    if (!Object.prototype.hasOwnProperty.call(__g, '__wbState')) {
      Object.defineProperty(__g, '__wbState', {
        value: {
          factories: Object.create(null), sourceHashes: Object.create(null), modules: Object.create(null),
          liveExports: Object.create(null), evaluating: Object.create(null), stubs: Object.create(null),
          stubsCleared: false, stubDefaultProxies: Object.create(null), moduleProxies: Object.create(null),
        },
        configurable: true, enumerable: false, writable: true,
      });
    }
    const st = __g.__wbState, win = getWin(), extStubs = (win && win.__wbStubs) || __g.__wbStubs;
    if (extStubs && typeof extStubs === 'object') {
      for (const k of Object.keys(extStubs)) {
        const norm = normalizeRel(k);
        if (extStubs[k] === undefined) delete st.stubs[norm]; else st.stubs[norm] = extStubs[k];
      }
    }
    return st;
  }
  getState();
  if (Object.prototype.hasOwnProperty.call(__g, '__wbRuntime')) return;

  class FallbackComponent {
    constructor(props) { this.props = props; }
    setState(u) { this.state = Object.assign({}, this.state || {}, typeof u === 'function' ? u(this.state, this.props) : u); }
  }
  function fallbackCreateContext(dv) {
    const ctx = {
      _currentValue: dv,
      Provider({ value, children }) { ctx._currentValue = value; return children; },
      Consumer({ children }) { return typeof children === 'function' ? children(ctx._currentValue) : children; },
    };
    return ctx;
  }
  let reactSingleton = null;
  function react() {
    if (reactSingleton) return reactSingleton;
    const readVendor = k => { const w = getWin(); return (w && w[k] !== undefined) ? w[k] : __g[k]; };
    const getR = () => readVendor('React') || {}, getDOM = () => readVendor('ReactDOM') || {};
    const reactStubOf = () => { const s = getState().stubs['shared/runtime/react.js']; return isObjOrFn(s) ? s : null; };
    const reactProxy = new Proxy(function () {}, {
      get(_t, prop) {
        const rs = reactStubOf();
        if (rs && prop in rs) return rs[prop];
        const R = getR();
        if (prop === 'createElement') return (type, props, ...ch) => R.createElement(type, props, ...ch);
        if (prop === 'Component') return R.Component || FallbackComponent;
        if (prop === 'Fragment') return ('Fragment' in R) ? R.Fragment : 'fragment';
        if (prop === 'createContext') return typeof R.createContext === 'function' ? R.createContext.bind(R) : fallbackCreateContext;
        const v = R[prop];
        return typeof v === 'function' && !v.prototype ? v.bind(R) : v;
      },
      set(_t, prop, val) { getR()[prop] = val; return true; },
    });
    const mod = {}, defReact = (name, fn) => Object.defineProperty(mod, name, {
      enumerable: true, get: () => { const rs = reactStubOf(); return (rs && name in rs) ? rs[name] : fn(); },
    });
    Object.defineProperty(mod, '__esModule', { value: true, enumerable: false });
    defReact('default', () => reactProxy);
    defReact('hasVendorRuntime', () => { const dom = readVendor('ReactDOM'); return Boolean(readVendor('React') && dom && typeof dom.createRoot === 'function'); });
    for (const domFn of ['createRoot', 'createPortal', 'flushSync']) {
      defReact(domFn, () => { const dom = getDOM(); return typeof dom[domFn] === 'function' ? dom[domFn].bind(dom) : undefined; });
    }
    for (const name of ${JSON.stringify(HOOK_EXPORTS)}) Object.defineProperty(mod, name, { enumerable: true, get: () => reactProxy[name] });
    return (reactSingleton = mod);
  }

  function ensureEvaluated(rel) {
    const st = getState();
    if (rel === 'shared/runtime/react.js' && !st.factories[rel]) return react();
    if (st.modules[rel]) return st.modules[rel];
    if (st.evaluating[rel]) return st.liveExports[rel];
    const fn = st.factories[rel];
    if (typeof fn !== 'function') return undefined;
    st.evaluating[rel] = true;
    try {
      fn();
      if (st.liveExports[rel] !== undefined) st.modules[rel] = st.liveExports[rel];
      return st.modules[rel];
    } finally {
      delete st.evaluating[rel];
      delete st.liveExports[rel];
    }
  }
  function getActiveStub(rel, hasCS, cs) {
    const st = getState();
    if (Object.prototype.hasOwnProperty.call(st.stubs, rel) && st.stubs[rel] !== undefined) return { hasStub: true, stub: st.stubs[rel] };
    if (!st.stubsCleared && hasCS && cs !== undefined) return { hasStub: true, stub: cs };
    return { hasStub: false, stub: undefined };
  }
  function assignStubProp(rel, k, v, hasCS, cs) {
    const { hasStub, stub } = getActiveStub(rel, hasCS, cs);
    if (hasStub && isObjOrFn(stub)) stub[k] = v;
    else { const st = getState(); (st.stubs[rel] || (st.stubs[rel] = Object.create(null)))[k] = v; }
    return true;
  }
  function makeProxy(target, rel, hasCS, cs, getProp, hasProp, collectKeys) {
    const handler = {
      get: (_t, p) => (typeof p === 'symbol' ? undefined : getProp(p, handler)),
      set: (_t, p, v) => assignStubProp(rel, p, v, hasCS, cs),
      has: (_t, p) => (typeof p === 'symbol' ? false : hasProp(p)),
      ownKeys(_t) {
        const keys = new Set(Reflect.ownKeys(_t));
        const { hasStub, stub } = getActiveStub(rel, hasCS, cs);
        if (hasStub && isObjOrFn(stub)) for (const k of Reflect.ownKeys(stub)) if (typeof k === 'string') keys.add(k);
        collectKeys(keys);
        return Array.from(keys);
      },
      getOwnPropertyDescriptor(_t, p) {
        const td = Object.getOwnPropertyDescriptor(_t, p);
        if (td && !td.configurable) return td;
        return handler.has(_t, p) ? { value: handler.get(_t, p), writable: true, enumerable: true, configurable: true } : undefined;
      },
      apply(_t, thisArg, args) {
        const { hasStub, stub } = getActiveStub(rel, hasCS, cs);
        if (hasStub && typeof stub === 'function') return Reflect.apply(stub, thisArg, args);
        if (hasStub && stub && typeof stub.default === 'function') return Reflect.apply(stub.default, thisArg, args);
        const r = ensureEvaluated(rel);
        return Reflect.apply(r && (typeof r.default === 'function' ? r.default : typeof r === 'function' ? r : null), thisArg, args);
      },
    };
    return new Proxy(target, handler);
  }
  function isPlainDefault(v) {
    if (!v || typeof v !== 'object' || Array.isArray(v) || Object.isFrozen(v)) return false;
    const proto = Object.getPrototypeOf(v);
    return proto === Object.prototype || proto === null;
  }
  function getStubDefaultProxy(rel, hasCS, cs) {
    const st = getState(), ck = hasCS ? rel + '\0cs' : rel;
    if (!st.stubDefaultProxies[ck]) {
      const r0 = st.modules[rel];
      st.stubDefaultProxies[ck] = makeProxy(
        (r0 && typeof r0.default === 'function') ? function () {} : {}, rel, hasCS, cs,
        k => {
          const { hasStub, stub } = getActiveStub(rel, hasCS, cs);
          if (hasStub && isObjOrFn(stub)) {
            if (k in stub) return stub[k];
            if (isObjOrFn(stub.default) && k in stub.default) return stub.default[k];
          }
          const r = ensureEvaluated(rel), d = r && r.default !== undefined ? r.default : r;
          return (isObjOrFn(d) && k in d) ? d[k] : (isObjOrFn(r) ? r[k] : undefined);
        },
        k => {
          const { hasStub, stub } = getActiveStub(rel, hasCS, cs);
          if (hasStub && isObjOrFn(stub) && (k in stub || (isObjOrFn(stub.default) && k in stub.default))) return true;
          const r = ensureEvaluated(rel), d = r && r.default !== undefined ? r.default : r;
          return Boolean((isObjOrFn(d) && k in d) || (isObjOrFn(r) && k in r));
        },
        keys => {
          const r = ensureEvaluated(rel), d = r && r.default !== undefined ? r.default : r;
          if (isObjOrFn(d)) for (const k of Reflect.ownKeys(d)) if (typeof k === 'string') keys.add(k);
        }
      );
    }
    return st.stubDefaultProxies[ck];
  }
  function resolveModuleProp(rel, key, hasCS, cs) {
    const { hasStub, stub } = getActiveStub(rel, hasCS, cs);
    if (hasStub) {
      if (stub !== null && typeof stub === 'object') {
        if (key === 'default') return ('default' in stub) ? stub.default : getStubDefaultProxy(rel, hasCS, cs);
        if (key in stub) return stub[key];
        if (isObjOrFn(stub.default) && key in stub.default) return stub.default[key];
        const r = ensureEvaluated(rel);
        return !r ? undefined : ((key in r) ? r[key] : (isObjOrFn(r.default) && key in r.default ? r.default[key] : undefined));
      }
      if (key === 'default') return stub;
      if (stub != null && Object.prototype.hasOwnProperty.call(Object(stub), key) && !(typeof stub === 'function' && (key === 'length' || key === 'name' || key === 'prototype' || key === 'arguments' || key === 'caller'))) return stub[key];
      return stub;
    }
    const st = getState(), rm = st.modules[rel] || (st.evaluating[rel] ? st.liveExports[rel] : ensureEvaluated(rel));
    if (!rm) return undefined;
    return (key === 'default' && isPlainDefault(rm.default)) ? getStubDefaultProxy(rel, hasCS, cs) : rm[key];
  }
  function dep(rel, exportNames, compileStub) {
    const hasCS = arguments.length >= 3, st = getState(), mod = {}, keySet = new Set(exportNames || []);
    if (hasCS && compileStub && typeof compileStub === 'object') for (const k of Object.keys(compileStub)) keySet.add(k);
    if (st.stubs[rel] && typeof st.stubs[rel] === 'object') for (const k of Object.keys(st.stubs[rel])) keySet.add(k);
    if (!keySet.has('__esModule')) Object.defineProperty(mod, '__esModule', { value: true, enumerable: false });
    for (const key of keySet) {
      Object.defineProperty(mod, key, {
        enumerable: true, configurable: true,
        get: () => resolveModuleProp(rel, key, hasCS, compileStub),
        set: v => assignStubProp(rel, key, v, hasCS, compileStub),
      });
    }
    if (!keySet.has('default')) Object.defineProperty(mod, 'default', { enumerable: false, configurable: true, get: () => resolveModuleProp(rel, 'default', hasCS, compileStub) });
    if (!getActiveStub(rel, hasCS, compileStub).hasStub && !st.evaluating[rel] && !st.modules[rel]) ensureEvaluated(rel);
    return mod;
  }
  function registerFactory(rawRel, sourceHash, fn) {
    const rel = normalizeRel(rawRel), st = getState();
    if (st.sourceHashes[rel] === sourceHash && st.factories[rel]) return;
    st.factories[rel] = fn; st.sourceHashes[rel] = sourceHash; delete st.modules[rel];
  }
  function publishLiveExports(rel, ns) { if (ns && typeof ns === 'object') getState().liveExports[rel] = ns; }
  function hasModule(rawRel) {
    const rel = normalizeRel(rawRel), st = getState();
    return rel === 'shared/runtime/react.js' || Boolean(st.modules[rel] || st.factories[rel]);
  }
  function setStub(relPath, stubVal) {
    const st = getState(), rel = normalizeRel(relPath), win = getWin(), extStubs = (win && win.__wbStubs) || __g.__wbStubs;
    if (extStubs && typeof extStubs === 'object') for (const k of Object.keys(extStubs)) if (normalizeRel(k) === rel) delete extStubs[k];
    if (stubVal === undefined) delete st.stubs[rel]; else st.stubs[rel] = stubVal;
  }
  function setStubs(s) { if (s && typeof s === 'object') for (const k of Object.keys(s)) setStub(k, s[k]); }
  function clearStubs() {
    const st = getState(), win = getWin();
    st.stubs = Object.create(null); st.stubsCleared = true;
    if (win && '__wbStubs' in win) delete win.__wbStubs;
    if ('__wbStubs' in __g) delete __g.__wbStubs;
  }
  function getModule(relPath) {
    const rel = normalizeRel(relPath), st = getState();
    if (rel === 'shared/runtime/react.js' && !st.factories[rel]) return react();
    if (!getActiveStub(rel, false, undefined).hasStub) ensureEvaluated(rel);
    if (!st.moduleProxies[rel]) {
      st.moduleProxies[rel] = makeProxy(
        function () {}, rel, false, undefined,
        (prop, h) => {
          if (prop === 'prototype') { const dv = h.get(null, 'default'); if (typeof dv === 'function') return dv.prototype; }
          if (getActiveStub(rel, false, undefined).hasStub) return resolveModuleProp(rel, prop, false, undefined);
          const rm = ensureEvaluated(rel);
          if (!rm) return undefined;
          if (prop === 'default' && isPlainDefault(rm.default)) return getStubDefaultProxy(rel, false, undefined);
          return (prop in rm) ? rm[prop] : (isObjOrFn(rm.default) && prop in rm.default ? rm.default[prop] : undefined);
        },
        prop => {
          const { hasStub, stub } = getActiveStub(rel, false, undefined);
          if (hasStub && isObjOrFn(stub) && prop in stub) return true;
          const rm = ensureEvaluated(rel);
          return Boolean(rm && (prop in rm || (isObjOrFn(rm.default) && prop in rm.default)));
        },
        keys => {
          const rm = ensureEvaluated(rel);
          if (isObjOrFn(rm)) {
            for (const k of Reflect.ownKeys(rm)) if (typeof k === 'string') keys.add(k);
            if (isObjOrFn(rm.default)) for (const k of Object.keys(rm.default)) keys.add(k);
          }
        }
      );
    }
    return st.moduleProxies[rel];
  }
  function runEntry(rawRel) { const rel = normalizeRel(rawRel); ensureEvaluated(rel); return getModule(rel); }
  const w0 = getWin();
  if (w0 && w0 !== __g) {
    for (const k of ['addEventListener', 'removeEventListener', 'dispatchEvent', 'localStorage', 'sessionStorage', 'location', 'history', 'document', 'navigator', 'crypto', 'CustomEvent', 'fetch', 'innerWidth', 'innerHeight', 'matchMedia', 'requestAnimationFrame', 'cancelAnimationFrame']) {
      if (!(k in __g)) Object.defineProperty(__g, k, {
        configurable: true, enumerable: false,
        get() { const win = getWin(), val = win ? win[k] : undefined; return (typeof val === 'function' && !val.prototype) ? val.bind(win) : val; },
        set(v) { const win = getWin(); if (win) win[k] = v; },
      });
    }
  }
  const runtimeApi = { registerFactory, publishLiveExports, dep, react, runEntry, getModule, hasModule, setStub, setStubs, clearStubs, normalizeRel };
  Object.defineProperty(__g, '__wbRuntime', { value: runtimeApi, configurable: true, enumerable: false, writable: true });
  if (w0 && w0 !== __g) Object.defineProperty(w0, '__wbRuntime', { value: runtimeApi, configurable: true, enumerable: false, writable: true });
})(typeof globalThis !== 'undefined' ? globalThis : window);`;

function serializeStubValue(val) {
  if (val === null || val === undefined || typeof val === 'boolean' || typeof val === 'number') return String(val);
  if (typeof val === 'string') return JSON.stringify(val);
  if (typeof val === 'function') {
    const fnCode = '(' + val.toString() + ')', ownKeys = Object.keys(val);
    return ownKeys.length === 0 ? fnCode : 'Object.assign(' + fnCode + ', {' + ownKeys.map(k => JSON.stringify(k) + ': ' + serializeStubValue(val[k])).join(', ') + '})';
  }
  if (Array.isArray(val)) return '[' + val.map(serializeStubValue).join(', ') + ']';
  if (typeof val === 'object') return '{' + Object.keys(val).map(k => JSON.stringify(k) + ': ' + serializeStubValue(val[k])).join(', ') + '}';
  return 'undefined';
}

function normalizeStubs(rawStubs) {
  if (!rawStubs || typeof rawStubs !== 'object') return null;
  const stubs = Object.create(null);
  for (const k of Object.keys(rawStubs)) {
    const val = rawStubs[k];
    if (val === undefined) continue;
    const keys = new Set(['default']);
    if (val !== null && (typeof val === 'object' || typeof val === 'function')) {
      for (const ok of Object.keys(val)) keys.add(ok);
      if (val.default && (typeof val.default === 'object' || typeof val.default === 'function')) {
        for (const dk of Object.keys(val.default)) keys.add(dk);
      }
    }
    stubs[normalizeRelPath(k)] = { keys: Array.from(keys), expr: serializeStubValue(val) };
  }
  return stubs;
}

module.exports = { REACT_NAMED_EXPORTS, SANDBOX_RUNTIME_CODE, normalizeRelPath, normalizeStubs };
