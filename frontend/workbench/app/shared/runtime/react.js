const W = typeof window !== 'undefined' ? window : globalThis;
const rawReact = W.React;
const rawReactDOM = W.ReactDOM;

export const hasVendorRuntime = Boolean(
  rawReact &&
  rawReactDOM &&
  typeof rawReactDOM.createRoot === 'function' &&
  typeof rawReactDOM.flushSync === 'function'
);

const fallbackReact = {
  Component: class {},
  createContext: () => ({ Provider: () => null, Consumer: () => null }),
};

const React = rawReact || fallbackReact;
export default React;
export const createRoot = rawReactDOM && typeof rawReactDOM.createRoot === 'function' ? rawReactDOM.createRoot.bind(rawReactDOM) : null;
export const createPortal = rawReactDOM && typeof rawReactDOM.createPortal === 'function' ? rawReactDOM.createPortal.bind(rawReactDOM) : null;
export const flushSync = rawReactDOM && typeof rawReactDOM.flushSync === 'function' ? rawReactDOM.flushSync.bind(rawReactDOM) : null;
