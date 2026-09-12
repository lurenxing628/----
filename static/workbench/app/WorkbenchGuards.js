(function () {
  'use strict';

  const entries = new Map(),
    listeners = new Set();
  let pending = null,
    listening = false,
    externalPermit = null,
    nextPrompt = 0;
  function affected(options = {}) {
    const excluded = options.excludeOwners || [];
    return Array.from(entries.values()).filter(entry => (options.owner === undefined || entry.owner === options.owner) && !excluded.includes(entry.owner) && (entry.dirty || entry.locked));
  }
  function hasDirty(options) {
    return affected(options).length > 0;
  }
  function beforeLeave(event) {
    if (externalPermit) {
      externalPermit = null;
      return;
    }
    if (!hasDirty()) return;
    event.preventDefault();
    event.returnValue = '';
  }
  function getPrompt() {
    if (!pending) return null;
    const rows = affected(pending.options);
    return {
      id: pending.id,
      locked: rows.some(entry => entry.locked),
      messages: Array.from(new Set(rows.map(entry => entry.message)))
    };
  }
  function notify() {
    listeners.forEach(listener => listener(getPrompt()));
  }
  function subscribe(listener) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
      if (!listeners.size && pending) resolvePrompt(pending.id, false);
    };
  }
  function sync() {
    externalPermit = null;
    const needed = hasDirty();
    if (needed !== listening) {
      if (needed) window.addEventListener('beforeunload', beforeLeave);else window.removeEventListener('beforeunload', beforeLeave);
      listening = needed;
    }
    if (pending && !hasDirty(pending.options)) {
      // Everything the prompt protected has been saved or unmounted; leaving is safe, so close the empty prompt.
      const request = pending;
      pending = null;
      notify();
      request.resolve(true);
      return;
    }
    if (pending) notify();
  }
  function register(entry) {
    if (!entry || typeof entry.owner !== 'string' || !entry.owner || typeof entry.message !== 'string') throw new TypeError('草稿保护需要明确的 owner 和说明。');
    const token = {};
    entries.set(token, entry);
    sync();
    return () => {
      entries.delete(token);
      sync();
    };
  }
  function useDirtyGuard({
    owner,
    dirty,
    message,
    locked = false
  }) {
    const generated = React.useId(),
      scope = owner || generated,
      value = React.useRef(null);
    if (!value.current) value.current = {
      owner: scope,
      dirty,
      message,
      locked
    };
    React.useLayoutEffect(() => {
      Object.assign(value.current, {
        owner: scope,
        dirty: !!dirty,
        message,
        locked: !!locked
      });
      sync();
    }, [scope, dirty, message, locked]);
    React.useLayoutEffect(() => register(value.current), []);
    return scope;
  }
  function confirmLeave(options = {}) {
    if (!hasDirty(options)) return Promise.resolve(true);
    if (pending) return Promise.resolve(false);
    if (!listeners.size) return Promise.reject(new Error('草稿确认组件未挂载，已保留当前内容。'));
    return new Promise(resolve => {
      pending = {
        id: ++nextPrompt,
        options,
        resolve
      };
      notify();
    });
  }
  async function leaveExternal(navigate) {
    if (typeof navigate !== 'function') throw new TypeError('外部离开需要明确导航动作。');
    if (!(await confirmLeave())) return false;
    const permit = {};
    externalPermit = permit;
    window.setTimeout(() => {
      if (externalPermit === permit) externalPermit = null;
    }, 0);
    try {
      navigate();
    } catch (error) {
      externalPermit = null;
      throw error;
    }
    return true;
  }
  function resolvePrompt(id, leave) {
    if (!pending || pending.id !== id) return;
    const request = pending;
    if (leave && affected(request.options).some(entry => entry.locked)) return;
    pending = null;
    notify();
    request.resolve(leave);
  }
  window.WorkbenchGuards = {
    register,
    useDirtyGuard,
    hasDirty,
    confirmLeave,
    leaveExternal,
    getPrompt,
    subscribe,
    resolvePrompt
  };
})();
